"""Deterministic, bounded packetization of source revisions and safe reports."""
from __future__ import annotations

import difflib
import hashlib
import json
import sqlite3
from collections import defaultdict
from typing import Any

from .ingest import canonical_json


DEFAULT_MAX_CHARS = 40_000
DEFAULT_CONTEXT_CHARS = 240


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _insert_packet(conn: sqlite3.Connection, payload: dict[str, Any]) -> bool:
    packet_id = "packet-" + _hash(payload)[:24]
    packet = {"id": packet_id, **payload}
    content_hash = _hash(packet)
    cur = conn.execute(
        "INSERT OR IGNORE INTO packets(id,entity_id,dataset,content_hash,payload,coverage,created_at) "
        "VALUES(?,?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
        (packet_id, payload["entity_id"], payload["dataset"], content_hash,
         canonical_json(packet), canonical_json(payload["coverage"])),
    )
    return cur.rowcount == 1


def _source_rows(conn: sqlite3.Connection, dataset: str, kind: str):
    return conn.execute(
        "SELECT uid,logical_id,text,metadata,created_at FROM sources WHERE dataset=? AND kind=? ORDER BY logical_id,created_at,uid",
        (dataset, kind),
    ).fetchall()


def _entity_titles(conn: sqlite3.Connection, dataset: str) -> dict[str, str]:
    return {r["id"]: r["title"] for r in conn.execute(
        "SELECT id,title FROM entities WHERE dataset=?", (dataset,)
    )}


def _compact_source_metadata(dataset: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Keep compact provenance while excluding bulky or unsafe source fields."""
    if dataset == "nightingale":
        allowed = (
            "entity_id", "page_id", "wiki", "name", "seq", "rcs_rev", "time",
            "time_grade", "winning_clock", "uncertainty_seconds", "request_time",
            "success_time", "recent_changes_time", "write_date", "archived_at",
            "request_action", "change_summary", "related_event_id", "relation_type",
            "round_id", "body_sha256", "body_len", "lines",
        )
        compact = {key: metadata[key] for key in allowed if key in metadata}
        if "label" in metadata:
            compact["declared_revision_writer"] = metadata["label"]
        compact.update({
            "kind": "nightingale_revision",
            "provenance": "Archived page revision. The declared revision writer is an archive label, not a verified message author.",
        })
        return compact
    extracts = metadata.get("extracts", [])
    pointers = sorted({pointer for item in extracts if isinstance(item, dict)
                       for pointer in item.get("json_pointers", []) if isinstance(pointer, str)})
    compact = {key: metadata[key] for key in (
        "entity_id", "report_id", "title", "source_url", "time", "transform"
    ) if key in metadata}
    if "provenance" in metadata:
        compact["provenance"] = metadata["provenance"]
    if pointers:
        compact["json_pointers"] = pointers
    compact["kind"] = "transluce_normalized_report"
    compact.setdefault("provenance", "Reviewed normalized report excerpts; inert text only.")
    return compact


def _span_packet(entity_id: str, dataset: str, title: str, uid: str,
                 logical_id: str, text: str, start: int, end: int,
                 deleted: list[dict[str, Any]], previous_uid: str | None,
                 previous_text: str,
                 source_metadata: dict[str, Any],
                 previous_metadata: dict[str, Any] | None,
                 max_chars: int, context_chars: int) -> dict[str, Any]:
    """Make one packet for one exact focus interval (or deletion-only change)."""
    context_chars = min(context_chars, max(0, max_chars // 6))
    budget = max(1, max_chars - context_chars * 4)
    # For overlong changes, split only the focus text. Every piece keeps exact
    # original offsets; a trailing/leading context excerpt is outside focus.
    chunks = [(start, end)] if end > start else [(start, end)]
    if end - start > budget:
        chunks = [(a, min(end, a + budget)) for a in range(start, end, budget)]
    outputs = []
    for focus_start, focus_end in chunks:
        a = max(0, focus_start - context_chars)
        b = min(len(text), focus_end + context_chars)
        excerpt = text[a:b]
        local_start, local_end = focus_start - a, focus_end - a
        source = {"uid": uid, "logical_id": logical_id, "text": excerpt,
                  "metadata": {**source_metadata, "revision_id": logical_id, "source_start": a,
                               "source_end": b, "focus_start": focus_start,
                               "focus_end": focus_end, "role": "focus_and_context",
                               "context_before_chars": local_start,
                               "context_after_chars": len(excerpt) - local_end}}
        sources = [source]
        if deleted and previous_uid:
            old_start = int(deleted[0]["start"])
            old_end = int(deleted[0]["end"])
            old_a = max(0, old_start - context_chars)
            old_b = min(len(previous_text), old_start + context_chars)
            sources.append({
                "uid": previous_uid, "logical_id": str(deleted[0].get("logical_id", "")),
                "text": previous_text[old_a:old_b],
                "metadata": {**(previous_metadata or {}), "source_start": old_a, "source_end": old_b,
                             "deleted_start": old_start, "deleted_end": old_end,
                             "role": "deleted_context"},
            })
        coverage = {
            "revision_id": logical_id,
            "previous_source_uid": previous_uid,
            "focus_characters": focus_end - focus_start,
            "deleted_spans": deleted,
            "context": {"source_start": a, "source_end": b,
                        "before_focus_chars": local_start,
                        "after_focus_chars": len(excerpt) - local_end},
        }
        focus = ([{"source_uid": uid, "start": local_start, "end": local_end}]
                 if focus_end > focus_start else [])
        # Deletions are evidence locations in the previous immutable version;
        # they are not converted to zero-width focus spans.
        outputs.append({
            "entity_id": entity_id, "dataset": dataset,
            "title": f"{title} · {logical_id}", "sources": sources,
            "focus": focus, "context_source_uids": ([previous_uid] if previous_uid else []),
            "coverage": coverage, "links": [],
        })
    if end == start and not outputs:
        outputs = []
    return outputs


def _nightingale_packets(conn: sqlite3.Connection, max_chars: int,
                         context_chars: int,
                         allowed: set[str] | None = None) -> tuple[int, int, int]:
    titles = _entity_titles(conn, "nightingale")
    rows = _source_rows(conn, "nightingale", "revision")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        meta = json.loads(row["metadata"])
        grouped[str(meta.get("entity_id") or "")].append({
            "uid": row["uid"], "logical_id": row["logical_id"], "text": row["text"],
            "meta": meta, "created_at": row["created_at"],
        })
    made = focus_total = deleted_total = 0
    for entity_id, revisions in sorted(grouped.items()):
        if allowed is not None and entity_id not in allowed:
            continue
        # Keep every source version, but compare the latest imported version of
        # each logical revision in the page's chronological body history.
        versions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for revision in revisions:
            versions[revision["logical_id"]].append(revision)
        latest = []
        for logical_id, candidates in versions.items():
            candidates.sort(key=lambda r: (r.get("created_at") or "", r["uid"]))
            latest.append(candidates[-1])
            if len(candidates) > 1:
                prior = candidates[-2]
                current = candidates[-1]
                prior_meta = {k: v for k, v in prior["meta"].items() if k != "entity_id"}
                current_meta = {k: v for k, v in current["meta"].items() if k != "entity_id"}
                changed = sorted(k for k in set(prior_meta) | set(current_meta)
                                 if prior_meta.get(k) != current_meta.get(k))
                if changed:
                    text = str(current["text"] or "")
                    limit = max(1, max_chars)
                    for absolute_start in range(0, max(1, len(text)), limit):
                        excerpt = text[absolute_start:absolute_start + limit]
                        payload = {
                            "entity_id": entity_id, "dataset": "nightingale",
                            "title": f"{titles.get(entity_id, entity_id)} · {logical_id} metadata update",
                            "sources": [{"uid": current["uid"], "logical_id": logical_id,
                                         "text": excerpt,
                                         "metadata": {**_compact_source_metadata("nightingale", current["meta"]),
                                                      "revision_id": logical_id,
                                                      "source_start": absolute_start,
                                                      "source_end": absolute_start + len(excerpt),
                                                      "role": "metadata_change_context"}}],
                            "focus": [], "context_source_uids": [prior["uid"]],
                            "coverage": {"revision_id": logical_id,
                                         "metadata_change": {"previous_source_uid": prior["uid"],
                                                             "current_source_uid": current["uid"],
                                                             "changed_keys": changed}},
                            "links": [],
                        }
                        if _insert_packet(conn, payload):
                            made += 1
        revisions = latest
        revisions.sort(key=lambda r: (int(r["meta"].get("seq") or 0), r["logical_id"]))
        previous: dict[str, Any] | None = None
        title = titles.get(entity_id, entity_id)
        for rev in revisions:
            text = str(rev["text"] or "")
            if previous is None:
                spans = [(0, len(text))] if text else []
                deleted: list[dict[str, Any]] = []
            else:
                matcher = difflib.SequenceMatcher(a=previous["text"], b=text, autojunk=False)
                spans = []
                deleted = []
                for tag, a0, a1, b0, b1 in matcher.get_opcodes():
                    if tag in ("insert", "replace") and b1 > b0:
                        spans.append((b0, b1))
                    if tag in ("delete", "replace") and a1 > a0:
                        deleted.append({"source_uid": previous["uid"], "start": a0,
                                        "end": a1, "length": a1 - a0,
                                        "text_sha256": hashlib.sha256(
                                            previous["text"][a0:a1].encode("utf-8")
                                        ).hexdigest()})
            # Each changed interval gets its own bounded packet(s). For a pure
            # deletion, create a zero-focus packet so the deletion is auditable.
            if not spans and deleted:
                spans = [(0, 0)]
            # Associate deletion metadata with the first focus packet only.
            for index, (start, end) in enumerate(spans):
                dmeta = deleted if index == 0 else []
                for packet_payload in _span_packet(
                    entity_id, "nightingale", title, rev["uid"], rev["logical_id"],
                    text, start, end, dmeta, previous["uid"] if previous else None,
                    previous["text"] if previous else "",
                    _compact_source_metadata("nightingale", rev["meta"]),
                    _compact_source_metadata("nightingale", previous["meta"]) if previous else None,
                    max_chars, context_chars,
                ):
                    if _insert_packet(conn, packet_payload):
                        made += 1
                    focus_total += sum(span["end"] - span["start"]
                                       for span in packet_payload["focus"])
                    if dmeta:
                        deleted_total += len(dmeta)
            previous = rev
    return made, focus_total, deleted_total


def _transluce_packets(conn: sqlite3.Connection, max_chars: int,
                       context_chars: int,
                       allowed: set[str] | None = None) -> tuple[int, int]:
    titles = _entity_titles(conn, "transluce")
    made = focused = 0
    for row in _source_rows(conn, "transluce", "normalized_report"):
        text = str(row["text"] or "")
        if not text:
            continue
        metadata = json.loads(row["metadata"])
        entity_id = str(metadata["entity_id"])
        if allowed is not None and entity_id not in allowed:
            continue
        title = titles.get(entity_id, entity_id)
        for packet_payload in _span_packet(
            entity_id, "transluce", title, row["uid"], row["logical_id"],
            text, 0, len(text), [], None, "",
            _compact_source_metadata("transluce", metadata), None,
            max_chars, context_chars,
            # No previous source for normalized report packets.
        ):
            if _insert_packet(conn, packet_payload):
                made += 1
            focused += sum(s["end"] - s["start"] for s in packet_payload["focus"])
    return made, focused


def prepare_packets(conn: sqlite3.Connection, entity_ids: list[str] | None = None,
                    max_chars: int = DEFAULT_MAX_CHARS) -> dict[str, int]:
    """Create deterministic immutable packets within a character budget.

    Focus intervals cover each nonempty Nightingale contribution exactly once;
    surrounding text is carried as context and never counted as focus. Removed
    text is recorded with its prior source UID, offsets, length, and hash.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    # `entity_ids` is an optional selection filter used by the CLI. Keep all
    # repository sources available, while the root's default can select a slice.
    allowed = set(entity_ids) if entity_ids is not None else None
    if allowed == set():
        return {"packets_created": 0, "focus_characters": 0,
                "deleted_spans": 0, "max_chars": max_chars}
    night_made, night_focus, deleted = _nightingale_packets(
        conn, max_chars, DEFAULT_CONTEXT_CHARS, allowed)
    trans_made, trans_focus = _transluce_packets(
        conn, max_chars, DEFAULT_CONTEXT_CHARS, allowed)
    return {"packets_created": night_made + trans_made,
            "focus_characters": night_focus + trans_focus,
            "deleted_spans": deleted, "max_chars": max_chars}
