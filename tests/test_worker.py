"""Worker orchestration tests with a fake Codex process and temporary SQLite state."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_pipeline import contracts, db, engine, worker


TEXT = "A short synthetic message."
PACKET = {
    "entity_id": "task-1", "dataset": "synthetic", "title": "Synthetic task",
    "sources": [{"uid": "source-v1", "logical_id": "message-1", "text": TEXT, "metadata": {}}],
    "focus": [{"source_uid": "source-v1", "start": 0, "end": len(TEXT)}],
    "context_source_uids": [], "coverage": {}, "links": [],
}


def empty_extraction():
    return {
        "status": "complete", "context_requests": [], "scope_summary": "One short message.",
        "reviewed_source_uids": ["source-v1"], "observations": [], "limitations": [],
    }


class FakeProcess:
    """Small Popen stand-in that writes the same files the CLI worker consumes."""

    def __init__(self, argv, *, stdin, stdout, stderr, cwd, start_new_session, text, outcome):
        self.argv = argv
        self.stdout = stdout
        self.stderr = stderr
        self.cwd = Path(cwd)
        self.returncode = outcome["returncode"]
        self.result = outcome.get("result", empty_extraction())
        self.usage = outcome.get("usage", {"input_tokens": 1, "output_tokens": 1})
        self.asserted_transport = (stdin, start_new_session, text)

    def communicate(self, prompt, timeout=None):
        self.prompt = prompt
        if self.usage is not None:
            self.stdout.write(json.dumps({"usage": self.usage}) + "\n")
            self.stdout.flush()
        if self.returncode == 0:
            output_path = Path(self.argv[self.argv.index("--output-last-message") + 1])
            output_path.write_text(json.dumps(self.result))
        return (None, None)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "state.sqlite"
        self.state_dir = self.root / "state"
        self.conn = db.connect(self.db_path)
        self.config_hash = engine.configure(self.conn, {"backend": "codex", "max_attempts": 2, "lease_seconds": 5})

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def insert_packet(self, packet_id, entity_id):
        payload = {**PACKET, "id": packet_id, "entity_id": entity_id}
        self.conn.execute("INSERT INTO entities VALUES(?,?,?,?,?)",
                          (entity_id, "synthetic", "task", "Synthetic task", "{}"))
        self.conn.execute("INSERT INTO packets VALUES(?,?,?,?,?,?,?)",
                          (packet_id, entity_id, "synthetic", db.digest(payload), db.canonical(payload),
                           db.canonical(payload["coverage"]), db.now()))
        engine.enqueue(self.conn, [packet_id], config_hash=self.config_hash)

    def fake_processes(self, outcomes):
        calls = []

        def popen(argv, **kwargs):
            outcome = outcomes[len(calls)]
            process = FakeProcess(argv, **kwargs, outcome=outcome)
            calls.append(process)
            return process

        return calls, popen

    def test_run_once_uses_read_only_frozen_schema_structured_cli(self):
        self.insert_packet("packet-a", "task-1")
        calls, popen = self.fake_processes([{"returncode": 0}])
        changed_schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
        with patch.object(worker.subprocess, "Popen", side_effect=popen), patch.object(contracts, "SCHEMAS", {"extract": changed_schema}):
            result = worker.run_once(self.db_path, self.state_dir, stage="extract", timeout=5)

        self.assertEqual("done", result["status"])
        self.assertEqual(1, len(calls))
        argv = calls[0].argv
        self.assertEqual((worker.subprocess.PIPE, True, True), calls[0].asserted_transport)
        self.assertEqual("read-only", argv[argv.index("--sandbox") + 1])
        self.assertEqual("gpt-6-luna", argv[argv.index("--model") + 1])
        for flag in ("features.apps=false", "features.plugins=false", "features.multi_agent=false", "features.browser_use=false"):
            self.assertIn(flag, argv)
        self.assertIn("--output-schema", argv)
        self.assertIn("--output-last-message", argv)
        self.assertEqual("-", argv[-1])
        self.assertIn("END_EVIDENCE_DATA", calls[0].prompt)
        saved = self.conn.execute("SELECT payload FROM results WHERE job_id=?", (result["job_id"],)).fetchone()
        self.assertEqual(empty_extraction(), json.loads(saved[0]))

    def test_run_waits_for_retry_without_spending_job_cap_on_idle_poll(self):
        self.insert_packet("packet-a", "task-1")
        calls, popen = self.fake_processes([
            {"returncode": 1, "usage": {"input_tokens": 1, "output_tokens": 1}},
            {"returncode": 0, "usage": {"input_tokens": 1, "output_tokens": 1}},
        ])
        original_fail = engine.fail

        def short_retry(conn, jid, token, error, retryable=True, usage=None):
            state = original_fail(conn, jid, token, error, retryable=retryable, usage=usage)
            if state == "ready":
                conn.execute("UPDATE jobs SET available_at=? WHERE id=?", (time.time() + 0.02, jid))
            return state

        with patch.object(worker.subprocess, "Popen", side_effect=popen), patch.object(engine, "fail", side_effect=short_retry):
            report = worker.run(self.db_path, self.state_dir, max_jobs=2, max_seconds=10, max_tokens=100)

        self.assertEqual(2, len(calls))
        self.assertEqual(2, report["completed_attempts"])
        self.assertEqual(2, self.conn.execute("SELECT count(*) FROM attempts").fetchone()[0])
        statuses = [row[0] for row in self.conn.execute("SELECT status FROM attempts ORDER BY started_at")]
        self.assertEqual(["failed", "done"], statuses)
        self.assertEqual("done", self.conn.execute("SELECT status FROM jobs WHERE packet_id='packet-a' AND stage='extract'").fetchone()[0])

    def test_missing_usage_stops_further_dispatch(self):
        self.insert_packet("packet-a", "task-1")
        self.insert_packet("packet-b", "task-2")
        calls, popen = self.fake_processes([{"returncode": 0, "usage": None}])
        with patch.object(worker.subprocess, "Popen", side_effect=popen):
            report = worker.run(self.db_path, self.state_dir, max_jobs=2, max_seconds=10, max_tokens=100)

        self.assertEqual(1, len(calls))
        self.assertEqual(1, report["completed_attempts"])
        self.assertEqual("usage unavailable; stopped further automatic dispatch", report["stop_reason"])
        self.assertEqual(1, self.conn.execute("SELECT count(*) FROM jobs WHERE stage='extract' AND status='done'").fetchone()[0])
        self.assertEqual(1, self.conn.execute("SELECT count(*) FROM jobs WHERE stage='extract' AND status='ready'").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
