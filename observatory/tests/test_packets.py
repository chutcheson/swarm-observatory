import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from swarm_pipeline.ingest import ingest
from swarm_pipeline.packets import prepare_packets


SCHEMA = """
CREATE TABLE sources(uid TEXT PRIMARY KEY,dataset TEXT,logical_id TEXT,kind TEXT,text TEXT,
 content_hash TEXT,metadata TEXT,created_at TEXT);
CREATE TABLE entities(id TEXT PRIMARY KEY,dataset TEXT,kind TEXT,title TEXT,metadata TEXT);
CREATE TABLE packets(id TEXT PRIMARY KEY,entity_id TEXT,dataset TEXT,content_hash TEXT,
 payload TEXT,coverage TEXT,created_at TEXT);
"""


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def setup_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


class PacketTests(unittest.TestCase):
    def _fixture(self, root: Path, revisions, report=True):
        source_root = root / "source"
        write_jsonl(source_root / "pages.jsonl", [{"page_id": "dse/Test", "name": "Test"}])
        write_jsonl(source_root / "revisions.jsonl", revisions)
        write_jsonl(source_root / "events.jsonl", [{"event_id": "event-1", "event_type": "write"}])
        write_jsonl(source_root / "labels.jsonl", [{"label": "AgentA", "pages": ["dse/Test"]}])
        research_root = root / "runs" / "network-v4"
        catalog_path = root / "runs" / "pilot-v1" / "corpus.sqlite"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog = sqlite3.connect(catalog_path)
        catalog.execute("CREATE TABLE records(dataset TEXT,kind TEXT,id TEXT,payload TEXT,PRIMARY KEY(dataset,kind,id))")
        catalog_rows = []
        if report:
            catalog_rows.append(("report-1", {"report_id": "report-1", "report_url": "https://catalog.invalid/r1",
                                               "disposition": "included", "broad_class": "safe test"}))
        catalog_rows.append(("catalog-only", {"report_id": "catalog-only", "disposition": "excluded",
                                               "broad_class": "catalog row only"}))
        catalog.executemany("INSERT INTO records VALUES('transluce','reports',?,?)",
                            [(rid, json.dumps(record)) for rid, record in catalog_rows])
        catalog.commit()
        catalog.close()
        write_json(research_root / "snapshot.json", {"cases": []})
        write_json(research_root / "selection_manifest_transluce.json",
                   {"new_reports": ["missing-report"], "revisited_reports": []})
        evidence = {}
        if report:
            evidence["tr-v4-report-1"] = {
                "title": "Safe report", "text": "GET example.test/path -> 200",
                "extracts": [{"text": "GET example.test/path -> 200",
                              "json_pointers": ["/http_transactions/0/status"]}],
                "transform": "Queries omitted",
            }
        write_json(research_root / "evidence" / "transluce-reviewed.json", evidence)
        return source_root, research_root

    def _revision(self, seq, body, **metadata):
        return {"rev_id": f"dse~Test@{seq}", "page_id": "dse/Test", "seq": seq,
                "body": body, "time": f"2026-01-0{seq}T00:00:00Z",
                "time_grade": "write_date", "winning_clock": "revision.pref_ts",
                "uncertainty_seconds": 1, **metadata}

    def test_ingest_is_idempotent_and_catalog_survives_missing_report(self):
        with TemporaryDirectory() as td:
            source, research = self._fixture(Path(td), [self._revision(1, "alpha")], report=False)
            conn = setup_db()
            self.addCleanup(conn.close)
            first = ingest(conn, source, research)
            before = conn.execute("SELECT count(*) FROM sources").fetchone()[0]
            second = ingest(conn, source, research)
            after = conn.execute("SELECT count(*) FROM sources").fetchone()[0]
            self.assertEqual(before, after)
            self.assertEqual(first["nightingale_revisions"], 1)
            self.assertEqual(second["nightingale_pages"], 1)
            self.assertEqual(second["transluce_catalog_reports"], 1)
            self.assertEqual(second["transluce_catalog_only"], 1)
            page_meta = conn.execute("SELECT metadata FROM entities WHERE id='nightingale:dse/Test'").fetchone()
            self.assertEqual(json.loads(page_meta["metadata"])["latest_revision_id"], "dse~Test@1")
            catalog = conn.execute("SELECT metadata FROM entities WHERE id='transluce:missing-report'").fetchone()
            self.assertTrue(json.loads(catalog["metadata"])["catalog_only"])
            self.assertEqual(conn.execute("SELECT count(*) FROM sources WHERE dataset='transluce'").fetchone()[0], 0)

    def test_catalog_only_records_do_not_create_processing_sources(self):
        with TemporaryDirectory() as td:
            source, research = self._fixture(Path(td), [self._revision(1, "body")], report=True)
            conn = setup_db()
            self.addCleanup(conn.close)
            counts = ingest(conn, source, research)
            self.assertEqual(counts["transluce_catalog_reports"], 2)
            self.assertEqual(counts["transluce_packets"], 1)
            self.assertEqual(counts["transluce_catalog_only"], 1)
            source_rows = conn.execute("SELECT logical_id FROM sources WHERE dataset='transluce'").fetchall()
            self.assertEqual([row[0] for row in source_rows], ["report:report-1"])
            catalog_only = conn.execute("SELECT metadata FROM entities WHERE id='transluce:catalog-only'").fetchone()
            self.assertTrue(json.loads(catalog_only["metadata"])["catalog_only"])

    def test_carry_forward_text_is_context_not_new_focus_and_ids_are_versioned(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            source, research = self._fixture(root, [
                self._revision(1, "same\nkeep\nold tail"),
                self._revision(2, "same\nkeep\nnew tail", label="AgentB"),
            ])
            conn = setup_db()
            self.addCleanup(conn.close)
            ingest(conn, source, research)
            result = prepare_packets(conn, max_chars=300)
            rows = [json.loads(r[0]) for r in conn.execute(
                "SELECT payload FROM packets WHERE dataset='nightingale'")]
            by_revision = {}
            for packet in rows:
                by_revision.setdefault(packet["coverage"]["revision_id"], []).append(packet)
            def focused_text(packets):
                spans = []
                for packet in packets:
                    source_entry = packet["sources"][0]
                    for span in packet["focus"]:
                        absolute = source_entry["metadata"]["source_start"] + span["start"]
                        spans.append((absolute, source_entry["text"][span["start"]:span["end"]]))
                return "".join(value for _, value in sorted(spans))
            v1 = focused_text(by_revision["dse~Test@1"])
            v2 = focused_text(by_revision["dse~Test@2"])
            self.assertEqual(v1, "same\nkeep\nold tail")
            self.assertEqual(v2, "new")
            provenance = by_revision["dse~Test@2"][0]["sources"][0]["metadata"]
            self.assertEqual(provenance["kind"], "nightingale_revision")
            self.assertEqual(provenance["time_grade"], "write_date")
            self.assertEqual(provenance["winning_clock"], "revision.pref_ts")
            self.assertEqual(provenance["declared_revision_writer"], "AgentB")
            self.assertNotIn("author", provenance)
            old_uid = conn.execute("SELECT uid FROM sources WHERE logical_id='dse~Test@2'").fetchone()[0]
            self.assertTrue(by_revision["dse~Test@2"][0]["coverage"]["previous_source_uid"])
            old_packet_ids = {r[0] for r in conn.execute("SELECT id FROM packets")}
            # A source metadata/signature edit produces a new immutable source and packet.
            write_jsonl(source / "revisions.jsonl", [
                self._revision(1, "same\nkeep\nold tail"),
                self._revision(2, "same\nkeep\nnew tail", label="AgentC"),
            ])
            ingest(conn, source, research)
            prepare_packets(conn, max_chars=300)
            new_uid_count = conn.execute("SELECT count(DISTINCT uid) FROM sources WHERE logical_id='dse~Test@2'").fetchone()[0]
            self.assertEqual(new_uid_count, 2)
            self.assertIn(old_uid, {r[0] for r in conn.execute("SELECT uid FROM sources WHERE logical_id='dse~Test@2'")})
            self.assertTrue(old_packet_ids < {r[0] for r in conn.execute("SELECT id FROM packets")})
            self.assertGreaterEqual(result["packets_created"], 2)

    def test_long_revision_is_split_without_losing_offsets(self):
        long_text = "0123456789" * 113
        with TemporaryDirectory() as td:
            source, research = self._fixture(Path(td), [self._revision(1, long_text)])
            conn = setup_db()
            self.addCleanup(conn.close)
            ingest(conn, source, research)
            prepare_packets(conn, max_chars=128)
            rows = [json.loads(r[0]) for r in conn.execute(
                "SELECT payload FROM packets WHERE dataset='nightingale'")]
            self.assertGreater(len(rows), 1)
            recovered = []
            for packet in rows:
                source_entry = packet["sources"][0]
                focus = packet["focus"][0]
                absolute = source_entry["metadata"]["source_start"] + focus["start"]
                recovered.append((absolute, source_entry["text"][focus["start"]:focus["end"]]))
                self.assertLessEqual(sum(len(s["text"]) for s in packet["sources"]), 128)
            self.assertEqual("".join(value for _, value in sorted(recovered)), long_text)

    def test_deleted_span_is_tracked_and_report_packet_is_stable(self):
        with TemporaryDirectory() as td:
            source, research = self._fixture(Path(td), [
                self._revision(1, "before REMOVE after"),
                self._revision(2, "before  after"),
            ])
            conn = setup_db()
            self.addCleanup(conn.close)
            ingest(conn, source, research)
            prepare_packets(conn, max_chars=512)
            packet_count = conn.execute("SELECT count(*) FROM packets").fetchone()[0]
            prepare_packets(conn, max_chars=512)
            self.assertEqual(conn.execute("SELECT count(*) FROM packets").fetchone()[0], packet_count)
            rows = [json.loads(r[0]) for r in conn.execute("SELECT payload FROM packets")]
            deleted = [p for p in rows if p["coverage"]["deleted_spans"]]
            self.assertEqual(len(deleted), 1)
            self.assertEqual(deleted[0]["coverage"]["deleted_spans"][0]["length"], len("REMOVE"))
            trans = [p for p in rows if p["dataset"] == "transluce"]
            self.assertEqual(len(trans), 1)
            self.assertEqual(trans[0]["sources"][0]["text"], "GET example.test/path -> 200")
            trans_meta = trans[0]["sources"][0]["metadata"]
            self.assertEqual(trans_meta["kind"], "transluce_normalized_report")
            self.assertIn("provenance", trans_meta)
            self.assertIn("/http_transactions/0/status", trans_meta["json_pointers"])
            self.assertNotIn("extracts", trans_meta)


if __name__ == "__main__":
    unittest.main()
