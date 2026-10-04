"""Read-only import of Nightingale archives and reviewed Transluce packets.

Corpus strings are stored as inert text. This module never follows source URLs or
interprets programs embedded in a report.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESEARCH_ROOT = PIPELINE_ROOT / "runs" / "network-v4"
DEFAULT_SOURCE_ROOT = Path("/Users/campbellhutcheson/Projects/swarm-communication")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _uid(dataset: str, logical_id: str, text: str, metadata: dict[str, Any]) -> str:
    # Including content and metadata gives append-only, versioned source IDs.
    return "source-" + _hash([dataset, logical_id, text, metadata])[:24]


def _insert_source(conn: sqlite3.Connection, dataset: str, logical_id: str,
                   kind: str, text: str, metadata: dict[str, Any]) -> str:
    uid = _uid(dataset, logical_id, text, metadata)
    conn.execute(
        "INSERT OR IGNORE INTO sources(uid,dataset,logical_id,kind,text,content_hash,metadata,created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (uid, dataset, logical_id, kind, text, hashlib.sha256(text.encode("utf-8")).hexdigest(),
         canonical_json(metadata), datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")),
    )
    return uid


def _insert_entity(conn: sqlite3.Connection, entity_id: str, dataset: str,
                   kind: str, title: str, metadata: dict[str, Any]) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO entities(id,dataset,kind,title,metadata) VALUES(?,?,?,?,?)",
        (entity_id, dataset, kind, title, canonical_json(metadata)),
    )


def _update_entity_metadata(conn: sqlite3.Connection, entity_id: str,
                            updates: dict[str, Any]) -> None:
    row = conn.execute("SELECT metadata FROM entities WHERE id=?", (entity_id,)).fetchone()
    if row is None:
        return
    metadata = json.loads(row["metadata"])
    metadata.update(updates)
    conn.execute("UPDATE entities SET metadata=? WHERE id=?",
                 (canonical_json(metadata), entity_id))


def _jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON in {path}:{line_no}") from exc


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _transluce_catalog(research_root: Path) -> dict[str, dict[str, Any]]:
    """Read report catalog metadata from the existing pilot inventory, read-only."""
    catalog_path = research_root.parent / "pilot-v1" / "corpus.sqlite"
    if not catalog_path.exists():
        return {}
    catalog_conn = sqlite3.connect(catalog_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        rows = catalog_conn.execute(
            "SELECT id,payload FROM records WHERE dataset='transluce' AND kind='reports' ORDER BY id"
        )
        allowed = {"report_id", "report_url", "report_date_utc", "timestamp_precision",
                   "disposition", "confidence", "broad_class", "why_included", "caveat"}
        return {
            str(record.get("report_id") or record_id): {
                key: value for key, value in record.items() if key in allowed
            }
            for record_id, payload in rows
            for record in [json.loads(payload)]
        }
    finally:
        catalog_conn.close()


def ingest(conn: sqlite3.Connection, source_root: str | Path = DEFAULT_SOURCE_ROOT,
           research_root: str | Path = DEFAULT_RESEARCH_ROOT) -> dict[str, int]:
    """Import all Nightingale catalog/source records and reviewed Transluce 32.

    Repeated runs are idempotent. New content creates new source UIDs, leaving
    earlier versions intact. Only normalized, reviewed Transluce evidence is
    imported; the raw HTTP JSON archive is never read.
    """
    source_root, research_root = Path(source_root), Path(research_root)
    counts = {"nightingale_pages": 0, "nightingale_revisions": 0,
              "nightingale_events": 0, "nightingale_labels": 0,
              "transluce_packets": 0, "transluce_catalog_reports": 0,
              "transluce_catalog_only": 0, "entities": 0}

    pages: dict[str, dict[str, Any]] = {}
    for row in _jsonl(source_root / "pages.jsonl"):
        page_id = str(row["page_id"])
        pages[page_id] = row
        eid = "nightingale:" + page_id
        _insert_entity(conn, eid, "nightingale", "page", page_id, {"page": row})
        text = canonical_json(row)
        catalog_uid = _insert_source(conn, "nightingale", "catalog:" + page_id, "page_catalog", text,
                                     {"entity_id": eid, "record_id": page_id})
        _update_entity_metadata(conn, eid, {"catalog_source_uid": catalog_uid})
        counts["nightingale_pages"] += 1
    counts["entities"] += len(pages)

    for row in _jsonl(source_root / "revisions.jsonl"):
        logical_id = str(row["rev_id"])
        page_id = str(row.get("page_id", ""))
        eid = "nightingale:" + page_id
        body = str(row.get("body") or "")
        metadata = {k: v for k, v in row.items() if k != "body"}
        metadata["entity_id"] = eid
        source_uid = _insert_source(conn, "nightingale", logical_id, "revision", body, metadata)
        current = conn.execute("SELECT metadata FROM entities WHERE id=?", (eid,)).fetchone()
        current_meta = json.loads(current["metadata"]) if current else {}
        seq = int(row.get("seq") or 0)
        if seq >= int(current_meta.get("latest_revision_seq") or -1):
            _update_entity_metadata(conn, eid, {"latest_revision_seq": seq,
                                                "latest_revision_id": logical_id,
                                                "latest_revision_source_uid": source_uid})
        counts["nightingale_revisions"] += 1

    for filename, kind, id_field, count_key in (
        ("events.jsonl", "event", "event_id", "nightingale_events"),
        ("labels.jsonl", "label", "label", "nightingale_labels"),
    ):
        for idx, row in enumerate(_jsonl(source_root / filename)):
            logical_id = str(row.get(id_field) or f"{kind}:{idx}")
            _insert_source(conn, "nightingale", logical_id, kind, canonical_json(row),
                           {"record_id": logical_id})
            counts[count_key] += 1

    # Build report entities from the reviewed dashboard snapshot. Only safe
    # normalized extracts are stored as source text below.
    snapshot_path = research_root / "snapshot.json"
    snapshot_cases: dict[str, dict[str, Any]] = {}
    if snapshot_path.exists():
        snapshot = _read_json(snapshot_path)
        snapshot_cases = {str(c.get("source_id")): c for c in snapshot.get("cases", [])
                          if c.get("dataset") == "transluce"}

    evidence_path = research_root / "evidence" / "transluce-reviewed.json"
    evidence = _read_json(evidence_path) if evidence_path.exists() else {}
    if not isinstance(evidence, dict):
        raise ValueError("Normalized Transluce evidence must be a mapping")
    catalog = _transluce_catalog(research_root)
    counts["transluce_catalog_reports"] = len(catalog)

    manifest_path = research_root / "selection_manifest_transluce.json"
    manifest = _read_json(manifest_path) if manifest_path.exists() else {}
    catalog_ids = set(manifest.get("new_reports", [])) | set(manifest.get("revisited_reports", []))
    for record in manifest.get("records", []):
        if isinstance(record, str):
            catalog_ids.add(record)
        elif isinstance(record, dict) and record.get("report_id"):
            catalog_ids.add(str(record["report_id"]))

    packet_ids: set[str] = set()
    for key, packet in sorted(evidence.items()):
        report_id = str(packet.get("report_id") or key.removeprefix("tr-v4-"))
        # The reviewed archive's keys are tr-v4-<UUID>.
        if report_id.startswith("tr-v4-"):
            report_id = report_id[len("tr-v4-"):]
        packet_ids.add(report_id)
        catalog_ids.add(report_id)
        case = snapshot_cases.get(report_id, {})
        title = str(case.get("title") or packet.get("title") or report_id)
        eid = "transluce:" + report_id
        _insert_entity(conn, eid, "transluce", "report", title,
                       {"report_id": report_id, "reviewed_packet": True,
                        "catalog_record": catalog.get(report_id)})
        safe_text = str(packet.get("text") or "\n".join(
            str(x.get("text", "")) for x in packet.get("extracts", [])
        ))
        metadata = {
            "entity_id": eid,
            "report_id": report_id,
            "title": title,
            "source_url": packet.get("source_url"),
            "time": packet.get("time"),
            "transform": packet.get("transform") or packet.get("transform_description"),
            "extracts": packet.get("extracts", []),
            "provenance": "reviewed normalized v4 packet; inert excerpts",
        }
        source_uid = _insert_source(conn, "transluce", "report:" + report_id, "normalized_report",
                                    safe_text, metadata)
        _update_entity_metadata(conn, eid, {"normalized_source_uid": source_uid,
                                            "reviewed_packet": True,
                                            "catalog_only": False,
                                            "packet_missing": False})
        counts["transluce_packets"] += 1
    # Selection/catalog records survive when a normalized report is absent;
    # they deliberately have no source text and produce no processing packet.
    catalog_ids.update(catalog)
    for report_id in sorted(catalog_ids - packet_ids):
        eid = "transluce:" + report_id
        case = snapshot_cases.get(report_id, {})
        _insert_entity(conn, eid, "transluce", "report",
                       str(case.get("title") or report_id),
                       {"report_id": report_id, "reviewed_packet": False,
                        "catalog_record": catalog.get(report_id),
                        "catalog_only": True, "packet_missing": True})
    counts["transluce_catalog_only"] = len(set(catalog) - packet_ids)
    counts["entities"] += len(catalog_ids)
    return counts
