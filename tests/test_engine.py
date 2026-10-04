"""Behavioral queue tests using a tiny, local SQLite database."""
import tempfile
import unittest
from pathlib import Path

from swarm_pipeline import db, engine

TEXT = "Mira: @Jon, prepare the benchmark results by Friday."
PACKET = {
    "entity_id": "task-1",
    "dataset": "synthetic",
    "title": "Benchmark task",
    "sources": [{"uid": "source-v1", "logical_id": "message-1", "text": TEXT, "metadata": {}}],
    "focus": [{"source_uid": "source-v1", "start": 0, "end": len(TEXT)}],
    "context_source_uids": [],
    "coverage": {"focus_chars": len(TEXT)},
    "links": [],
}


def observation():
    return {
        "id": "obs-1", "kind": "message", "actor": "Mira", "recipients": ["Jon"],
        "audience": "direct", "summary": "Mira asks Jon to prepare results.",
        "task": "Prepare benchmark results by Friday.", "status": "proposal",
        "evidence": [{"source_uid": "source-v1", "quote": TEXT}], "uncertainties": [],
    }


def extraction(status="complete", context_requests=None):
    return {
        "status": status, "context_requests": context_requests or [], "scope_summary": "One message.",
        "reviewed_source_uids": ["source-v1"], "observations": [observation()], "limitations": [],
    }


def approval(decision="approve"):
    return {
        "status": "complete", "context_requests": [], "decision": decision,
        "addressed_observation_ids": ["obs-1"], "findings": [], "missing_observations": [], "limitations": [],
    }


def interpretation():
    return {
        "status": "complete", "context_requests": [],
        "contributions": [{"observation_id": "obs-1", "roles": ["coordinator"], "functions": ["task assignment"],
                            "behaviors": ["requests preparation"], "protocol": None}],
        "relations": [], "groups": [], "novel_patterns": [], "limitations": [],
    }


def summary():
    return {
        "status": "complete", "context_requests": [], "title": "Benchmark preparation",
        "hover": "Mira asks Jon to prepare benchmark results.",
        "short": "Mira asks Jon to prepare results by Friday.",
        "long": "The message records a request to prepare benchmark results by Friday.",
        "links": [], "evidence_observation_ids": ["obs-1"], "limitations": [],
    }


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self.tmp.name) / "state.sqlite")
        self.config_hash = engine.configure(self.conn, {"max_attempts": 2, "lease_seconds": 30})
        self.packet_ids = []
        self._insert_packet("packet-a", PACKET)
        self._insert_packet("packet-b", {**PACKET, "entity_id": "task-2", "title": "Unrelated task"})

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _insert_packet(self, pid, payload):
        payload = {**payload, "id": pid}
        self.conn.execute("INSERT INTO entities VALUES(?,?,?,?,?)",
                          (payload["entity_id"], payload["dataset"], "task", payload["title"], "{}"))
        self.conn.execute("INSERT INTO packets VALUES(?,?,?,?,?,?,?)",
                          (pid, payload["entity_id"], payload["dataset"], db.digest(payload), db.canonical(payload),
                           db.canonical(payload["coverage"]), db.now()))
        self.packet_ids.append(pid)

    def _enqueue(self, pid="packet-a"):
        return engine.enqueue(self.conn, [pid], config_hash=self.config_hash)

    def _claim(self, stage, pid="packet-a"):
        job = self.conn.execute("SELECT id FROM jobs WHERE packet_id=? AND stage=? ORDER BY created_at DESC LIMIT 1",
                                (pid, stage)).fetchone()
        self.assertIsNotNone(job)
        claimed = engine.claim(self.conn, "test-worker", stage=stage, job_id=job["id"])
        self.assertIsNotNone(claimed)
        return claimed

    def _run_extract_review(self, pid="packet-a"):
        self._enqueue(pid)
        ext = self._claim("extract", pid)
        engine.submit(self.conn, ext["job_id"], ext["lease_token"], extraction())
        rev = self._claim("review", pid)
        engine.submit(self.conn, rev["job_id"], rev["lease_token"], approval())
        return ext, rev

    def test_expired_lease_fences_stale_worker(self):
        self._enqueue()
        first = self._claim("extract")
        self.conn.execute("UPDATE jobs SET lease_until=0 WHERE id=?", (first["job_id"],))
        second = self._claim("extract")
        self.assertNotEqual(first["lease_token"], second["lease_token"])
        with self.assertRaisesRegex(ValueError, "stale worker output rejected"):
            engine.submit(self.conn, first["job_id"], first["lease_token"], extraction())
        self.assertEqual("leased", self.conn.execute("SELECT status FROM jobs WHERE id=?", (first["job_id"],)).fetchone()[0])
        engine.submit(self.conn, second["job_id"], second["lease_token"], extraction())
        self.assertEqual("done", self.conn.execute("SELECT status FROM jobs WHERE id=?", (first["job_id"],)).fetchone()[0])

    def test_retryable_failure_resumes_then_stops_at_max_attempts(self):
        self._enqueue()
        first = self._claim("extract")
        self.assertEqual("ready", engine.fail(self.conn, first["job_id"], first["lease_token"], "temporary", retryable=True))
        self.conn.execute("UPDATE jobs SET available_at=0 WHERE id=?", (first["job_id"],))
        second = self._claim("extract")
        self.assertEqual(2, self.conn.execute("SELECT attempt_count FROM jobs WHERE id=?", (second["job_id"],)).fetchone()[0])
        self.assertEqual("failed", engine.fail(self.conn, second["job_id"], second["lease_token"], "still broken", retryable=True))
        self.assertIsNone(engine.claim(self.conn, "test-worker", job_id=second["job_id"]))
        self.assertEqual(1, self.conn.execute("SELECT count(*) FROM tickets WHERE job_id=? AND kind='failure'", (second["job_id"],)).fetchone()[0])

    def test_review_block_prevents_interpretation_until_reprocessed(self):
        self._enqueue()
        ext = self._claim("extract")
        engine.submit(self.conn, ext["job_id"], ext["lease_token"], extraction())
        rev = self._claim("review")
        engine.submit(self.conn, rev["job_id"], rev["lease_token"], approval("revise"))
        interpret = self.conn.execute("SELECT id FROM jobs WHERE packet_id='packet-a' AND stage='interpret'").fetchone()[0]
        self.assertEqual("blocked", self.conn.execute("SELECT status FROM jobs WHERE id=?", (rev["job_id"],)).fetchone()[0])
        self.assertIsNone(engine.claim(self.conn, "test-worker", job_id=interpret))
        self.assertEqual(1, self.conn.execute("SELECT count(*) FROM tickets WHERE job_id=? AND kind='review'", (rev["job_id"],)).fetchone()[0])

    def test_invalidating_upstream_supersedes_descendant_open_ticket(self):
        self._enqueue()
        ext = self._claim("extract")
        engine.submit(self.conn, ext["job_id"], ext["lease_token"], extraction())
        rev = self._claim("review")
        engine.submit(self.conn, rev["job_id"], rev["lease_token"], approval("revise"))
        ticket = self.conn.execute("SELECT id,status FROM tickets WHERE job_id=? AND kind='review'", (rev["job_id"],)).fetchone()
        self.assertEqual("open", ticket["status"])
        affected = engine.invalidate(self.conn, ext["job_id"], "Upstream evidence changed")
        self.assertIn(rev["job_id"], affected)
        self.assertEqual("superseded", self.conn.execute("SELECT status FROM tickets WHERE id=?", (ticket["id"],)).fetchone()[0])

    def test_new_active_config_prevents_claiming_old_ready_job(self):
        self._enqueue()
        old_extract = self.conn.execute("SELECT id FROM jobs WHERE packet_id='packet-a' AND stage='extract'").fetchone()[0]
        new_hash = engine.configure(self.conn, {"model": "different-model", "max_attempts": 2, "lease_seconds": 30})
        self.assertNotEqual(self.config_hash, new_hash)
        self.assertIsNone(engine.claim(self.conn, "test-worker", job_id=old_extract))
        self.assertEqual("ready", self.conn.execute("SELECT status FROM jobs WHERE id=?", (old_extract,)).fetchone()[0])
        engine.enqueue(self.conn, ["packet-a"], config_hash=new_hash)
        new_extract = self.conn.execute("SELECT id FROM jobs WHERE packet_id='packet-a' AND stage='extract' AND config_hash=?", (new_hash,)).fetchone()[0]
        self.assertIsNotNone(engine.claim(self.conn, "test-worker", job_id=new_extract))

    def test_complete_four_stage_flow(self):
        self._enqueue()
        for stage, result in [("extract", extraction()), ("review", approval()), ("interpret", interpretation()), ("summarize", summary())]:
            job = self._claim(stage)
            self.assertEqual(stage, job["stage"])
            engine.submit(self.conn, job["job_id"], job["lease_token"], result)
        self.assertEqual(4, self.conn.execute("SELECT count(*) FROM jobs WHERE packet_id='packet-a' AND status='done'").fetchone()[0])
        self.assertEqual(4, self.conn.execute("SELECT count(*) FROM results").fetchone()[0])

    def test_missing_context_creates_ticket_and_holds_downstream(self):
        self._enqueue()
        request = {"entity_id": "task-1", "source_uid": "source-v1", "reason": "Need the prior message in the thread."}
        ext = self._claim("extract")
        result = extraction("needs_context", [request])
        result["observations"] = []
        result["reviewed_source_uids"] = ["source-v1"]
        engine.submit(self.conn, ext["job_id"], ext["lease_token"], result)
        self.assertEqual("blocked", self.conn.execute("SELECT status FROM jobs WHERE id=?", (ext["job_id"],)).fetchone()[0])
        self.assertEqual(1, self.conn.execute("SELECT count(*) FROM tickets WHERE job_id=? AND kind='context' AND status='open'", (ext["job_id"],)).fetchone()[0])
        review = self.conn.execute("SELECT id FROM jobs WHERE packet_id='packet-a' AND stage='review'").fetchone()[0]
        self.assertIsNone(engine.claim(self.conn, "test-worker", job_id=review))
        self.assertIsNone(self.conn.execute("SELECT 1 FROM results WHERE job_id=?", (review,)).fetchone())

    def test_targeted_reprocess_preserves_upstream_and_unrelated_outputs(self):
        old_extract, old_review = self._run_extract_review("packet-a")
        old_interpret = self._claim("interpret")
        engine.submit(self.conn, old_interpret["job_id"], old_interpret["lease_token"], interpretation())
        old_summary = self._claim("summarize")
        engine.submit(self.conn, old_summary["job_id"], old_summary["lease_token"], summary())
        other = self._run_extract_review("packet-b")
        unrelated_before = self.conn.execute("SELECT id,status FROM jobs WHERE packet_id='packet-b'").fetchall()
        outcome = engine.reprocess(self.conn, old_interpret["job_id"], "Interpretation needs a second pass")
        self.assertEqual("done", self.conn.execute("SELECT status FROM jobs WHERE id=?", (old_extract["job_id"],)).fetchone()[0])
        self.assertEqual("done", self.conn.execute("SELECT status FROM jobs WHERE id=?", (old_review["job_id"],)).fetchone()[0])
        self.assertEqual("stale", self.conn.execute("SELECT status FROM jobs WHERE id=?", (old_interpret["job_id"],)).fetchone()[0])
        self.assertEqual("stale", self.conn.execute("SELECT status FROM jobs WHERE id=?", (old_summary["job_id"],)).fetchone()[0])
        self.assertTrue(all(self.conn.execute("SELECT status FROM jobs WHERE id=?", (r["id"],)).fetchone()[0] == r["status"] for r in unrelated_before))
        self.assertTrue(all(self.conn.execute("SELECT 1 FROM results WHERE job_id=?", (r["id"],)).fetchone() for r in unrelated_before if r["status"] == "done"))
        self.assertEqual(["interpret", "summarize"], [self.conn.execute("SELECT stage FROM jobs WHERE id=?", (jid,)).fetchone()[0] for jid in outcome["created"]])
        new_interpret = self.conn.execute("SELECT id FROM jobs WHERE packet_id=? AND stage='interpret'", (outcome["packet_id"],)).fetchone()[0]
        deps = [r[0] for r in self.conn.execute("SELECT depends_on FROM dependencies WHERE job_id=?", (new_interpret,))]
        self.assertEqual([old_review["job_id"]], deps)
        self.assertEqual(2, len(other))


if __name__ == "__main__":
    unittest.main()
