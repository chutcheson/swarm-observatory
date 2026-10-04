import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_pipeline.db import connect, set_setting
from swarm_pipeline.engine import reprocess
from swarm_pipeline.project import build_projection, export_projection, status_snapshot


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = connect(Path(self.tmp.name) / "state.sqlite")
        self.addCleanup(self.conn.close)
        set_setting(self.conn, "active_config_hash", "cfg")
        self.conn.execute("INSERT INTO entities(id,dataset,kind,title,metadata) VALUES(?,?,?,?,?)",
                          ("entity-1", "nightingale", "page", "Page title", "{}"))
        self.source_uid = "source-1"
        self.source_text = "A sent a direct message to B about Task X."

    def add_packet(self, packet_id, *, review_decision="approve", stages_done=True,
                   direct=True, source_uid=None, text=None, entity_id="entity-1", observation_id="obs-1",
                   source_start=0, summary_links=None):
        source_uid = source_uid or self.source_uid
        text = text or self.source_text
        quote = "A sent a direct message to B" if direct else "Task X"
        packet = {
            "id": packet_id,
            "entity_id": entity_id,
            "dataset": "nightingale",
            "title": "Page title",
            "sources": [{"uid": source_uid, "logical_id": "page-1", "text": text,
                         "metadata": {"source_start": source_start}}],
            "focus": [{"source_uid": source_uid, "start": 0, "end": len(text)}],
            "context_source_uids": [],
            "coverage": {},
            "links": [],
        }
        self.conn.execute(
            "INSERT INTO packets(id,entity_id,dataset,content_hash,payload,coverage,created_at) VALUES(?,?,?,?,?,?,?)",
            (packet_id, entity_id, "nightingale", packet_id, json.dumps(packet), "{}", "2026-01-01T00:00:00Z"),
        )
        observation = {
            "id": observation_id, "kind": "message" if direct else "annotation",
            "actor": "A" if direct else None, "recipients": ["B"] if direct else [],
            "audience": "direct" if direct else "unknown", "summary": "A reports a message to B.",
            "task": "Task X", "status": "observed_message" if direct else "unclear",
            "evidence": [{"source_uid": source_uid, "quote": quote}], "uncertainties": [],
        }
        payloads = {
            "extract": {"status": "complete", "context_requests": [], "scope_summary": "Scope", "reviewed_source_uids": [source_uid], "observations": [observation], "limitations": []},
            "review": {"status": "complete" if review_decision == "approve" else "needs_context", "context_requests": [], "decision": review_decision, "addressed_observation_ids": [observation_id], "findings": [], "missing_observations": [], "limitations": []},
            "interpret": {"status": "complete", "context_requests": [], "contributions": [], "relations": [], "groups": [], "novel_patterns": [], "limitations": []},
            "summarize": {"status": "complete", "context_requests": [], "title": "Reviewed title", "hover": "A brief hover.", "short": "A reviewed short summary.", "long": "A reviewed long summary with task context and limits.", "links": summary_links or [], "evidence_observation_ids": [observation_id], "limitations": []},
        }
        prev = None
        ids = {}
        for stage in ("extract", "review", "interpret", "summarize"):
            job_id = packet_id + "-" + stage
            ids[stage] = job_id
            status = "done" if stages_done else ("blocked" if stage == "review" else "ready")
            self.conn.execute(
                "INSERT INTO jobs(id,stage,packet_id,queue,status,config_hash,attempt_count,max_attempts,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (job_id, stage, packet_id, "coverage", status, "cfg", 1, 3, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )
            if prev:
                self.conn.execute("INSERT INTO dependencies(job_id,depends_on) VALUES(?,?)", (job_id, prev))
            self.conn.execute("INSERT INTO results(job_id,content_hash,payload,created_at) VALUES(?,?,?,?)",
                              (job_id, "hash", json.dumps(payloads[stage]), "2026-01-01T00:00:00Z"))
            prev = job_id
        if review_decision != "approve":
            self.conn.execute("UPDATE jobs SET status='blocked' WHERE id=?", (ids["review"],))
        return ids

    def test_exports_only_approved_current_lineage_and_keeps_baseline(self):
        ids = self.add_packet("packet-approved")
        stale_ids = self.add_packet("packet-stale")
        self.conn.execute("UPDATE jobs SET status='stale' WHERE id=?", (stale_ids["extract"],))
        self.conn.execute("INSERT INTO invalidations(id,job_id,reason,created_at) VALUES(?,?,?,?)",
                          ("inv-1", stale_ids["extract"], "source changed", "2026-01-02T00:00:00Z"))
        baseline = {"cases": [{"id": "legacy-case"}], "observations": [{"title": "legacy"}]}
        projection = build_projection(self.conn, baseline)
        self.assertEqual(projection["cases"], baseline["cases"])
        self.assertEqual(projection["observations"], baseline["observations"])
        self.assertEqual([r["entity_id"] for r in projection["pipeline"]["records"]], ["entity-1"])
        record = projection["pipeline"]["records"][0]
        self.assertEqual(record["provenance"]["jobs"]["summarize"], ids["summarize"])
        self.assertIn("short", record)
        self.assertEqual(len(projection["pipeline"]["networks"]["communication"]), 1)

    def test_distinct_claims_sharing_a_quote_are_not_erased(self):
        self.add_packet("packet-report")
        ids = self.add_packet("packet-request", observation_id="obs-request")
        result = json.loads(self.conn.execute(
            "SELECT payload FROM results WHERE job_id=?", (ids["extract"],)).fetchone()[0])
        result["observations"][0]["summary"] = "The same passage also contains a request."
        result["observations"][0]["status"] = "proposal"
        self.conn.execute("UPDATE results SET payload=? WHERE job_id=?",
                          (json.dumps(result), ids["extract"]))
        observations = build_projection(self.conn)["pipeline"]["records"][0]["observations"]
        self.assertEqual(len(observations), 2)
        self.assertEqual(len({o["id"] for o in observations}), 2)

    def test_overlapping_packet_evidence_is_deduplicated(self):
        self.add_packet("packet-a")
        ids = self.add_packet("packet-b", observation_id="obs-duplicate")
        result = json.loads(self.conn.execute("SELECT payload FROM results WHERE job_id=?", (ids["interpret"],)).fetchone()[0])
        result["contributions"] = [{"observation_id": "obs-duplicate", "roles": ["scout"], "functions": [], "behaviors": [], "protocol": None}]
        self.conn.execute("UPDATE results SET payload=? WHERE job_id=?", (json.dumps(result), ids["interpret"]))
        record = build_projection(self.conn)["pipeline"]["records"][0]
        self.assertEqual(len(record["packet_ids"]), 2)
        self.assertEqual(len(record["observations"]), 1)
        self.assertEqual(len(record["interpretation"]["contributions"]), 1)
        self.assertEqual(record["interpretation"]["contributions"][0]["observation_id"], record["observations"][0]["id"])
        self.assertEqual(len(build_projection(self.conn)["pipeline"]["networks"]["communication"]), 1)

    def test_different_source_crops_use_absolute_offsets_and_remap_summary_links(self):
        quote = "A sent a direct message to B"
        original_start = 1008
        first_start = 767
        second_start = 900
        self.add_packet("packet-crop-a", text="x" * (original_start - first_start) + quote + "y" * 20,
                        source_start=first_start)
        self.add_packet(
            "packet-crop-b", text="z" * (original_start - second_start) + quote + "w" * 20,
            source_start=second_start, observation_id="obs-crop-b",
            summary_links=[{"type": "observation", "id": "obs-crop-b", "label": "Message"},
                           {"type": "observation", "id": "missing-observation", "label": "Dangling"}],
        )
        record = build_projection(self.conn)["pipeline"]["records"][0]
        self.assertEqual(len(record["observations"]), 1)
        location = record["observations"][0]["evidence"][0]
        self.assertEqual(location["start"], original_start)
        self.assertEqual(location["end"], original_start + len(quote))
        self.assertEqual(record["interpretation"]["contributions"], [])
        scope = next(s for s in record["packet_scopes"] if s["packet_id"] == "packet-crop-b")
        self.assertEqual(len(scope["links"]), 1)
        self.assertEqual(scope["links"][0]["id"], record["observations"][0]["id"])

    def test_reprocessed_downstream_stages_follow_valid_older_ancestors(self):
        ids = self.add_packet("packet-original")
        set_setting(self.conn, "config:cfg", {"max_packet_chars": 40000, "max_attempts": 3})
        outcome = reprocess(self.conn, ids["interpret"], "Clarify protocol interpretation")
        new_packet = outcome["packet_id"]
        new_interpret, new_summary = outcome["created"]
        original_payloads = {
            row["stage"]: json.loads(row["payload"])
            for row in self.conn.execute(
                "SELECT j.stage,r.payload FROM jobs j JOIN results r ON r.job_id=j.id WHERE j.packet_id=?",
                ("packet-original",),
            )
        }
        self.conn.execute("UPDATE jobs SET status='done' WHERE id IN (?,?)", (new_interpret, new_summary))
        for job_id, stage in ((new_interpret, "interpret"), (new_summary, "summarize")):
            self.conn.execute("INSERT INTO results(job_id,content_hash,payload,created_at) VALUES(?,?,?,?)",
                              (job_id, "new-hash", json.dumps(original_payloads[stage]), "2026-01-02T00:00:00Z"))
        pipeline = build_projection(self.conn)["pipeline"]
        self.assertEqual(len(pipeline["records"]), 1)
        record = pipeline["records"][0]
        self.assertEqual(record["packet_ids"], [new_packet])
        self.assertEqual(record["provenance"]["evidence_packet_id"], "packet-original")

    def test_unapproved_or_unsigned_lineage_creates_no_records_or_edges(self):
        self.add_packet("packet-review-blocked", review_decision="revise")
        projection = build_projection(self.conn)["pipeline"]
        self.assertEqual(projection["records"], [])
        self.assertEqual(projection["networks"]["communication"], [])
        self.assertEqual(projection["networks"]["protocol_relations"], [])

    def test_networks_keep_typed_relations_and_evidence(self):
        ids = self.add_packet("packet-networks")
        result = self.conn.execute("SELECT payload FROM results WHERE job_id=?", (ids["interpret"],)).fetchone()[0]
        interpret = json.loads(result)
        protocol = {"family": "relay", "variant": "clock check", "rule": "Report the next time", "state": "observed_use"}
        interpret["contributions"] = [{"observation_id": "obs-1", "roles": ["scout"], "functions": ["advance_warning"], "behaviors": ["reports_time"], "protocol": protocol}]
        interpret["relations"] = [
            {"type": "reply", "source": "A", "target": "B", "basis_observation_ids": ["obs-1"], "status": "explicit"},
            {"type": "protocol_use", "source": "A", "target": "relay", "basis_observation_ids": ["obs-1"], "status": "explicit"},
            {"type": "task_participation", "source": "A", "target": "Task X", "basis_observation_ids": ["obs-1"], "status": "explicit"},
            {"type": "identity_candidate", "source": "A", "target": "Agent-A", "basis_observation_ids": ["obs-1"], "status": "unresolved"},
        ]
        self.conn.execute("UPDATE results SET payload=? WHERE job_id=?", (json.dumps(interpret), ids["interpret"]))
        networks = build_projection(self.conn)["pipeline"]["networks"]
        self.assertTrue(any(edge["type"] == "reply" and edge["evidence"] for edge in networks["communication"]))
        self.assertTrue(any(edge["type"] == "protocol_use" and edge["evidence"] for edge in networks["protocol_relations"]))
        self.assertTrue(any(edge["type"] == "task_participation" and edge["evidence"] for edge in networks["task_relations"]))
        self.assertTrue(any(item["type"] == "identity_candidate" for item in networks["hypotheses"]))

    def test_interpreted_communication_without_matching_direct_pair_is_provisional(self):
        ids = self.add_packet("packet-provisional", direct=False)
        result = self.conn.execute("SELECT payload FROM results WHERE job_id=?", (ids["interpret"],)).fetchone()[0]
        interpret = json.loads(result)
        interpret["relations"] = [{"type": "reply", "source": "A", "target": "B", "basis_observation_ids": ["obs-1"], "status": "explicit"}]
        self.conn.execute("UPDATE results SET payload=? WHERE job_id=?", (json.dumps(interpret), ids["interpret"]))
        networks = build_projection(self.conn)["pipeline"]["networks"]
        self.assertEqual(networks["communication"], [])
        self.assertEqual(len(networks["provisional_communication_relations"]), 1)

    def test_actor_ids_are_scoped_to_entity_even_for_same_literal_name(self):
        self.conn.execute("INSERT INTO entities(id,dataset,kind,title,metadata) VALUES(?,?,?,?,?)",
                          ("entity-2", "transluce", "report", "Other report", "{}"))
        self.add_packet("packet-one")
        self.add_packet("packet-two", entity_id="entity-2")
        networks = build_projection(self.conn)["pipeline"]["networks"]
        actor_a = [a for a in networks["actors"] if a["label"] == "A"]
        self.assertEqual(len(actor_a), 2)
        self.assertEqual({a["entity_id"] for a in actor_a}, {"entity-1", "entity-2"})
        self.assertEqual(len({a["id"] for a in actor_a}), 2)
        edges = [e for e in networks["communication"] if e["source_label"] == "A"]
        self.assertEqual(len(edges), 2)
        self.assertEqual(len({e["source"] for e in edges}), 2)

    def test_status_counts_only_active_configuration(self):
        self.add_packet("older")
        self.conn.execute("UPDATE jobs SET config_hash='old-codex'")
        self.add_packet("current")
        snapshot=status_snapshot(self.conn)
        self.assertEqual(4,snapshot['counts']['jobs'])
        self.assertEqual(4,snapshot['history']['other_config_jobs'])

    def test_status_snapshot_contains_aggregate_counts_without_raw_text(self):
        self.add_packet("packet-status")
        self.conn.execute("UPDATE jobs SET error='PRIVATE SOURCE BODY'")
        self.conn.execute("INSERT INTO sources(uid,dataset,logical_id,kind,text,content_hash,metadata,created_at) VALUES(?,?,?,?,?,?,?,?)",
                          ("source-1", "nightingale", "page-1", "revision", self.source_text, "hash", "{}", "2026-01-01T00:00:00Z"))
        set_setting(self.conn, "config:cfg", {"model": "gpt-6-luna"})
        self.conn.execute("INSERT INTO attempts(id,job_id,status,usage) VALUES(?,?,?,?)",
                          ("attempt-1", "packet-status-extract", "done", json.dumps({"input_tokens": 8, "output_tokens": 4, "note": "PRIVATE"})))
        status = status_snapshot(self.conn)
        serialized = json.dumps(status)
        self.assertEqual(status["counts"]["jobs"], 4)
        self.assertEqual(status["counts"]["sources"], 1)
        self.assertEqual(status["counts"]["packets"], 1)
        self.assertEqual(status["counts"]["entities"], 1)
        self.assertEqual(status["model"], "gpt-6-luna")
        self.assertEqual(status["usage_totals"], {"input_tokens": 8, "output_tokens": 4})
        self.assertNotIn("PRIVATE SOURCE BODY", serialized)
        self.assertNotIn("PRIVATE", serialized)
        self.assertNotIn(self.source_text, serialized)

    def test_export_is_json_and_preserves_baseline_cases(self):
        self.add_packet("packet-export")
        baseline = {"cases": [{"id": "case-360"}]}
        target = Path(self.tmp.name) / "out" / "projection.json"
        returned = export_projection(self.conn, target, baseline)
        loaded = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(loaded, returned)
        self.assertEqual(loaded["cases"], baseline["cases"])
        self.assertIn("pipeline", loaded)
        self.assertFalse(list(target.parent.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
