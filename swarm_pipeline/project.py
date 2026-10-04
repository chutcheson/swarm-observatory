"""Build evidence-backed, current projections from the append-only pipeline DB."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .contracts import STAGES, VERSION


def _json(value, default=None):
    if value is None:
        return default
    if isinstance(value, (str, bytes, bytearray)):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default
    return value


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _rows(conn, table):
    return [dict(row) for row in conn.execute(f"SELECT * FROM {table}")]


def _setting(conn, key):
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    except Exception:
        return None
    return _json(row[0]) if row else None


def status_snapshot(conn):
    """Return only aggregate operational status, without job or corpus text."""
    all_jobs = _rows(conn, "jobs")
    active = _setting(conn, "active_config_hash")
    jobs = [j for j in all_jobs if j.get("config_hash") == active]
    current_ids = {j["id"] for j in jobs}
    tickets = [t for t in _rows(conn, "tickets") if t["job_id"] in current_ids]
    by_stage = defaultdict(Counter)
    by_status = Counter()
    for job in jobs:
        stage = job.get("stage") or "unknown"
        status = job.get("status") or "unknown"
        by_stage[stage][status] += 1
        by_status[status] += 1
    config_hash = _setting(conn, "active_config_hash")
    config = _setting(conn, "config:" + config_hash) if config_hash else None
    usage_totals = Counter()
    attempts = [a for a in _rows(conn, "attempts") if a["job_id"] in current_ids]
    for attempt in attempts:
        usage = _json(attempt.get("usage"), {})
        if not isinstance(usage, dict):
            continue
        for key, value in usage.items():
            lowered = str(key).lower()
            if ("token" in lowered or "cost" in lowered or "usd" in lowered) and isinstance(value, (int, float)) and not isinstance(value, bool):
                usage_totals[key] += value
    table_counts = {}
    for table in ("sources", "packets", "entities"):
        table_counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return {
        "version": VERSION,
        "generated_at": _now(),
        "counts": {
            "jobs": len(jobs),
            "tickets": len(tickets),
            "jobs_by_status": dict(sorted(by_status.items())),
            "jobs_by_stage": {
                stage: dict(sorted(counts.items()))
                for stage, counts in sorted(by_stage.items())
            },
            "tickets_by_status": dict(sorted(Counter(t.get("status", "unknown") for t in tickets).items())),
            "tickets_by_kind": dict(sorted(Counter(t.get("kind", "unknown") for t in tickets).items())),
            **table_counts,
            "attempts": len(attempts),
            "attempts_with_usage": sum(bool(_json(a.get("usage"), {})) for a in attempts),
        },
        "model": config.get("model") if isinstance(config, dict) else None,
        "backend": config.get("backend", "codex") if isinstance(config, dict) else None,
        "usage_totals": dict(sorted(usage_totals.items())),
        "history": {"all_jobs": len(all_jobs), "other_config_jobs": len(all_jobs)-len(jobs)},
    }


def _current_valid_jobs(conn):
    """Resolve current done jobs and recursively reject stale/invalid ancestry."""
    jobs = _rows(conn, "jobs")
    results = {r["job_id"]: _json(r.get("payload"), {}) for r in _rows(conn, "results")}
    invalid = {r["job_id"] for r in _rows(conn, "invalidations")}
    dependencies = defaultdict(set)
    for edge in _rows(conn, "dependencies"):
        dependencies[edge["job_id"]].add(edge["depends_on"])
    active = _setting(conn, "active_config_hash")
    if active is None:
        return {}
    by_packet_stage = defaultdict(list)
    by_id = {j["id"]: j for j in jobs}
    for job in jobs:
        if job.get("status") == "done" and job["id"] in results and job["id"] not in invalid:
            if active is None or job.get("config_hash") == active:
                by_packet_stage[(job.get("packet_id"), job.get("stage"))].append(job)
    # There should be one job per packet, stage, and config. Resolve corrupted
    # or migrated duplicates deterministically, preferring the newest result.
    chosen = {}
    for key, candidates in by_packet_stage.items():
        chosen[key] = max(candidates, key=lambda j: (j.get("updated_at") or "", j["id"]))

    memo = {}
    visiting = set()

    def valid(job_id):
        if job_id in memo:
            return memo[job_id]
        if job_id in visiting or job_id not in by_id:
            return False
        job = by_id[job_id]
        if (job.get("status") != "done" or job_id not in results or job_id in invalid
                or (active is not None and job.get("config_hash") != active)):
            memo[job_id] = False
            return False
        visiting.add(job_id)
        ok = all(valid(dep) for dep in dependencies.get(job_id, ()))
        visiting.remove(job_id)
        memo[job_id] = ok
        return ok

    current = {}
    for (packet_id, stage), job in chosen.items():
        if valid(job["id"]):
            current[(packet_id, stage)] = (job, results[job["id"]])
    return current


def _evidence_location(packet, ref):
    """Resolve a quote to all focused source locations in its packet."""
    source = next((s for s in packet.get("sources", []) if s.get("uid") == ref.get("source_uid")), None)
    if source is None or not ref.get("quote"):
        return []
    text, quote = source.get("text", ""), ref["quote"]
    source_offset = int(source.get("metadata", {}).get("source_start", 0) or 0)
    locations = []
    start = 0
    focus = packet.get("focus", [])
    while True:
        pos = text.find(quote, start)
        if pos < 0:
            break
        end = pos + len(quote)
        if any(f.get("source_uid") == ref["source_uid"] and pos < f.get("end", 0) and end > f.get("start", 0) for f in focus):
            locations.append({"source_uid": ref["source_uid"], "logical_id": source.get("logical_id"),
                              "start": source_offset + pos, "end": source_offset + end, "quote": quote})
        start = pos + 1
    return locations


def _locations(packet, refs):
    found = []
    for ref in refs or []:
        found.extend(_evidence_location(packet, ref))
    unique = {(x["source_uid"], x["start"], x["end"]): x for x in found}
    return [unique[k] for k in sorted(unique)]


def _stable_id(prefix, parts):
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _remap_ids(values, mapping):
    return [mapping.get(value, value) for value in values]


def _observation_key(obs, locations=None):
    """A quote can support distinct speech acts; deduplicate identical claims only."""
    return (tuple((e["source_uid"], e["start"], e["end"])
                  for e in (locations if locations is not None else obs["evidence"])),
            obs.get("kind"), obs.get("actor"), tuple(obs.get("recipients", [])),
            obs.get("audience"), obs.get("status"), obs.get("summary"))


def _record(packet_id, packet, evidence_packet_id, evidence_packet, entity, stages):
    extract = stages["extract"][1]
    interpretation = stages["interpret"][1]
    summary = stages["summarize"][1]
    reviewed_ids = {o["id"] for o in extract.get("observations", [])}
    if not set(summary.get("evidence_observation_ids", [])) <= reviewed_ids:
        return None
    obs_out = []
    seen = {}
    obs_id_map = {}
    for obs in extract.get("observations", []):
        locs = _locations(evidence_packet, obs.get("evidence", []))
        if not locs:
            continue
        key = _observation_key(obs, locs)
        if key in seen:
            obs_id_map[obs["id"]] = seen[key]
            continue
        projected_id = _stable_id("obs-", [entity["id"], key])
        seen[key] = projected_id
        obs_id_map[obs["id"]] = projected_id
        obs_out.append({
            "id": projected_id, "source_observation_id": obs["id"], "kind": obs["kind"], "actor": obs["actor"],
            "recipients": obs["recipients"], "audience": obs["audience"],
            "summary": obs["summary"], "task": obs["task"], "status": obs["status"],
            "evidence": locs, "uncertainties": obs["uncertainties"],
        })
    valid_obs_ids = {o["id"] for o in obs_out}
    contributions = []
    for value in interpretation.get("contributions", []):
        mapped = {**value, "observation_id": obs_id_map.get(value.get("observation_id"), value.get("observation_id"))}
        if mapped["observation_id"] in valid_obs_ids:
            contributions.append(mapped)

    def mapped_basis(values):
        return _remap_ids(values, obs_id_map)

    relations, groups, patterns = [], [], []
    for value in interpretation.get("relations", []):
        mapped = {**value, "basis_observation_ids": mapped_basis(value.get("basis_observation_ids", []))}
        if mapped["basis_observation_ids"] and set(mapped["basis_observation_ids"]) <= valid_obs_ids:
            relations.append(mapped)
    for value in interpretation.get("groups", []):
        mapped = {**value, "basis_observation_ids": mapped_basis(value.get("basis_observation_ids", []))}
        if mapped["basis_observation_ids"] and set(mapped["basis_observation_ids"]) <= valid_obs_ids:
            groups.append(mapped)
    for value in interpretation.get("novel_patterns", []):
        mapped = {**value, "basis_observation_ids": mapped_basis(value.get("basis_observation_ids", []))}
        if mapped["basis_observation_ids"] and set(mapped["basis_observation_ids"]) <= valid_obs_ids:
            patterns.append(mapped)
    review = stages["review"][1]
    if (review.get("decision") != "approve" or review.get("status") != "complete"
            or review.get("findings") or review.get("missing_observations")
            or review.get("context_requests")
            or set(review.get("addressed_observation_ids", [])) != reviewed_ids
            or not {obs_id_map.get(x, x) for x in summary.get("evidence_observation_ids", [])} <= valid_obs_ids):
        return None
    links = []
    for link in summary.get("links", []):
        if link.get("type") == "observation":
            mapped_id = obs_id_map.get(link.get("id"))
            if mapped_id not in valid_obs_ids:
                continue
            links.append({**link, "id": mapped_id})
        else:
            links.append(link)
    return {
        "entity_id": entity["id"],
        "dataset": entity.get("dataset"),
        "title": summary.get("title") or packet.get("title") or entity.get("title"),
        "hover": summary.get("hover"),
        "short": summary.get("short"),
        "long": summary.get("long"),
        "packet_ids": [packet_id],
        "packet_scopes": [{
            "packet_id": packet_id,
            "title": packet.get("title"),
            "hover": summary.get("hover"),
            "short": summary.get("short"),
            "long": summary.get("long"),
            "links": links,
            "limitations": summary.get("limitations", []),
        }],
        "observations": obs_out,
        "interpretation": {
            "contributions": contributions,
            "relations": relations,
            "groups": groups,
            "novel_patterns": patterns,
            "limitations": interpretation.get("limitations", []),
        },
        "provenance": {
            "jobs": {stage: stages[stage][0]["id"] for stage in STAGES},
            "evidence_packet_id": evidence_packet_id,
            "review_decision": review.get("decision"),
            "source_uids": sorted({e["source_uid"] for o in obs_out for e in o["evidence"]}),
        },
    }


def _merge_records(records):
    """Merge packet records per entity while deduplicating exact evidence locations."""
    grouped = {}
    for record in records:
        current = grouped.get(record["entity_id"])
        if current is None:
            grouped[record["entity_id"]] = record
            continue
        current["packet_ids"] = sorted(set(current["packet_ids"] + record["packet_ids"]))
        current["packet_scopes"].extend(record["packet_scopes"])
        evidence_seen = {
            _observation_key(o): o["id"] for o in current["observations"]
        }
        observation_id_map = {}
        for obs in record["observations"]:
            key = _observation_key(obs)
            if key in evidence_seen:
                observation_id_map[obs["id"]] = evidence_seen[key]
            else:
                current["observations"].append(obs)
                evidence_seen[key] = obs["id"]
                observation_id_map[obs["id"]] = obs["id"]
        for key in ("contributions", "relations", "groups", "novel_patterns"):
            known = {json.dumps(v, sort_keys=True, separators=(",", ":")) for v in current["interpretation"][key]}
            for original in record["interpretation"][key]:
                value = dict(original)
                if key == "contributions":
                    value["observation_id"] = observation_id_map.get(value["observation_id"], value["observation_id"])
                else:
                    value["basis_observation_ids"] = _remap_ids(value["basis_observation_ids"], observation_id_map)
                marker = json.dumps(value, sort_keys=True, separators=(",", ":"))
                if marker not in known:
                    current["interpretation"][key].append(value)
                    known.add(marker)
        current["interpretation"]["limitations"] = sorted(set(current["interpretation"]["limitations"] + record["interpretation"]["limitations"]))
        current["hover"] = current["packet_scopes"][0].get("hover")
        current["short"] = current["packet_scopes"][0].get("short")
        current["long"] = current["packet_scopes"][0].get("long")
        for stage, job_id in record["provenance"]["jobs"].items():
            current["provenance"].setdefault("jobs_by_packet", {}).setdefault(record["packet_ids"][0], {})[stage] = job_id
        current["provenance"]["source_uids"] = sorted(set(current["provenance"]["source_uids"] + record["provenance"]["source_uids"]))
    for value in grouped.values():
        value["packet_scopes"].sort(key=lambda x: x["packet_id"])
        value["observations"].sort(key=lambda x: x["id"])
    return [grouped[k] for k in sorted(grouped)]


def _actor_ref(entity_id, label):
    return {"id": _stable_id("actor-", [entity_id, label]), "entity_id": entity_id, "label": label}


def _networks(records):
    actors, tasks, protocols = {}, {}, {}
    communication, provisional, protocol_edges, task_edges, hypotheses, group_hypotheses = [], [], [], [], [], []
    comm_seen, provisional_seen, protocol_seen, task_seen = set(), set(), set(), set()
    for record in records:
        entity_id = record["entity_id"]
        obs_by_id = {o["id"]: o for o in record["observations"]}
        direct_pairs = set()

        def register_actor(label):
            ref = _actor_ref(entity_id, label)
            actors[ref["id"]] = ref
            return ref

        for obs in record["observations"]:
            task = obs.get("task")
            if task:
                task_ref = {"id": _stable_id("task-", [entity_id, task]), "entity_id": entity_id, "label": task}
                tasks[task_ref["id"]] = task_ref
            actor = obs.get("actor")
            if actor:
                register_actor(actor)
            if obs.get("kind") == "message" and obs.get("audience") == "direct" and actor:
                source_ref = register_actor(actor)
                for recipient in obs.get("recipients", []):
                    target_ref = register_actor(recipient)
                    direct_pairs.add((actor, recipient, obs["id"]))
                    key = (source_ref["id"], target_ref["id"], obs["id"])
                    if key not in comm_seen:
                        communication.append({"type": "direct_message", "entity_id": entity_id,
                                              "source": source_ref["id"], "source_label": actor,
                                              "target": target_ref["id"], "target_label": recipient,
                                              "observation_id": obs["id"], "evidence": obs["evidence"]})
                        comm_seen.add(key)
        for contribution in record["interpretation"]["contributions"]:
            oid = contribution["observation_id"]
            obs = obs_by_id.get(oid)
            proto = contribution.get("protocol")
            if not obs or not proto:
                continue
            pkey = (entity_id, proto["family"], proto["variant"])
            protocol_ref = {"id": _stable_id("protocol-", list(pkey)), "entity_id": entity_id,
                            "family": proto["family"], "variant": proto["variant"], "rule": proto["rule"]}
            protocols[protocol_ref["id"]] = protocol_ref
            actor = obs.get("actor")
            source_ref = register_actor(actor) if actor else None
            edge_key = (source_ref["id"] if source_ref else None, protocol_ref["id"], proto["state"], oid)
            if edge_key not in protocol_seen:
                protocol_edges.append({"type": "protocol_relation", "entity_id": entity_id,
                                      "source": source_ref["id"] if source_ref else None,
                                      "source_label": actor, "target": protocol_ref["id"],
                                      "state": proto["state"], "observation_id": oid,
                                      "evidence": obs["evidence"]})
                protocol_seen.add(edge_key)
        for relation in record["interpretation"]["relations"]:
            evidence = [e for oid in relation["basis_observation_ids"] for e in obs_by_id.get(oid, {}).get("evidence", [])]
            source_label, target_label = relation["source"], relation["target"]
            item = {"type": relation["type"], "entity_id": entity_id,
                    "source_label": source_label, "target_label": target_label,
                    "status": relation["status"], "basis_observation_ids": relation["basis_observation_ids"],
                    "evidence": evidence}
            if relation["status"] != "explicit":
                hypotheses.append(item)
            elif relation["type"] in ("reply", "delegation", "handoff"):
                matched_ids = [oid for oid in relation["basis_observation_ids"]
                               if (source_label, target_label, oid) in direct_pairs]
                if matched_ids:
                    source_ref, target_ref = register_actor(source_label), register_actor(target_label)
                    key = (relation["type"], source_ref["id"], target_ref["id"], tuple(matched_ids))
                    if key not in comm_seen:
                        matched_evidence = [e for oid in matched_ids for e in obs_by_id.get(oid, {}).get("evidence", [])]
                        communication.append({**item, "source": source_ref["id"], "target": target_ref["id"],
                                              "basis_observation_ids": matched_ids, "evidence": matched_evidence})
                        comm_seen.add(key)
                else:
                    key = (relation["type"], source_label, target_label, tuple(relation["basis_observation_ids"]))
                    if key not in provisional_seen:
                        provisional.append(item)
                        provisional_seen.add(key)
            elif relation["type"] == "protocol_use":
                source_ref = register_actor(source_label)
                target_id = _stable_id("protocol-ref-", [entity_id, target_label])
                protocols.setdefault(target_id, {"id": target_id, "entity_id": entity_id,
                                                  "family": target_label, "variant": None,
                                                  "rule": None, "basis": "explicit_relation"})
                key = (source_ref["id"], target_id, tuple(relation["basis_observation_ids"]))
                if key not in protocol_seen:
                    protocol_edges.append({**item, "source": source_ref["id"], "target": target_id})
                    protocol_seen.add(key)
            elif relation["type"] == "task_participation":
                source_ref = register_actor(source_label)
                target_ref = {"id": _stable_id("task-", [entity_id, target_label]),
                              "entity_id": entity_id, "label": target_label}
                tasks[target_ref["id"]] = target_ref
                key = (source_ref["id"], target_ref["id"], tuple(relation["basis_observation_ids"]))
                if key not in task_seen:
                    task_edges.append({**item, "source": source_ref["id"], "target": target_ref["id"]})
                    task_seen.add(key)
        for group in record["interpretation"]["groups"]:
            group_hypotheses.append({"entity_id": entity_id, "name": group["name"], "kind": group["kind"],
                                     "members": group["members"], "basis": group["basis"],
                                     "basis_observation_ids": group["basis_observation_ids"]})
    return {
        "actors": [actors[k] for k in sorted(actors)],
        "tasks": [tasks[k] for k in sorted(tasks)],
        "protocols": [protocols[k] for k in sorted(protocols)],
        "communication": communication,
        "provisional_communication_relations": provisional,
        "protocol_relations": protocol_edges,
        "task_relations": task_edges,
        "hypotheses": hypotheses,
        "group_hypotheses": group_hypotheses,
    }


def _load_baseline(baseline_path):
    if baseline_path is None:
        return {}
    if isinstance(baseline_path, dict):
        return json.loads(json.dumps(baseline_path))
    with open(baseline_path, encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError("baseline snapshot must be a JSON object")
    return value


def build_projection(conn, baseline_path=None):
    """Build the baseline-preserving research snapshot with a pipeline overlay."""
    current = _current_valid_jobs(conn)
    packet_rows = {r["id"]: r for r in _rows(conn, "packets")}
    entity_rows = {r["id"]: r for r in _rows(conn, "entities")}
    packet_payloads = {pid: _json(row.get("payload"), {}) for pid, row in packet_rows.items()}
    records = []
    all_jobs = {j["id"]: j for j in _rows(conn, "jobs")}
    dependencies = defaultdict(set)
    for edge in _rows(conn, "dependencies"):
        dependencies[edge["job_id"]].add(edge["depends_on"])
    current_summaries = [(pid, value) for (pid, stage), value in current.items() if stage == "summarize"]
    for packet_id, summary_pair in sorted(current_summaries):
        summary_job = summary_pair[0]
        ancestors = set()
        stack = list(dependencies.get(summary_job["id"], ()))
        while stack:
            ancestor = stack.pop()
            if ancestor not in ancestors:
                ancestors.add(ancestor)
                stack.extend(dependencies.get(ancestor, ()))
        lineage_jobs = [summary_job] + [all_jobs[jid] for jid in ancestors if jid in all_jobs]
        stage_values = {"summarize": summary_pair}
        for stage in STAGES[:-1]:
            candidates = [j for j in lineage_jobs if j.get("stage") == stage and (j.get("packet_id"), stage) in current
                          and current[(j.get("packet_id"), stage)][0]["id"] == j["id"]]
            if len(candidates) != 1:
                stage_values[stage] = None
            else:
                stage_values[stage] = current[(candidates[0]["packet_id"], stage)]
        if any(value is None for value in stage_values.values()):
            continue
        # The chain may cross packet revisions, but every stage must descend
        # from the immediately prior stage in the same ancestry.
        stages_valid = True
        for ix, stage in enumerate(STAGES):
            if ix == 0:
                continue
            prior = STAGES[ix - 1]
            stages_valid &= stage_values[prior][0]["id"] in dependencies.get(stage_values[stage][0]["id"], set())
        if not stages_valid:
            continue
        evidence_packet_id = stage_values["extract"][0].get("packet_id")
        evidence_packet = packet_payloads.get(evidence_packet_id, {})
        packet_row = packet_rows.get(packet_id)
        packet = packet_payloads.get(packet_id, {})
        entity = entity_rows.get(packet.get("entity_id"))
        if not packet_row or not entity or not evidence_packet:
            continue
        record = _record(packet_id, packet, evidence_packet_id, evidence_packet, entity, stage_values)
        if record is not None:
            records.append(record)
    records = _merge_records(records)
    networks = _networks(records)
    status = status_snapshot(conn)
    by_stage = status["counts"]["jobs_by_stage"]
    counts = {
        "records": len(records),
        "entities": len(records),
        "packets": sum(len(r["packet_ids"]) for r in records),
        "observations": sum(len(r["observations"]) for r in records),
        "communication_edges": len(networks["communication"]),
        "protocol_edges": len(networks["protocol_relations"]),
        "task_edges": len(networks["task_relations"]),
        "jobs": status["counts"]["jobs"],
    }
    overlay = {
        "version": VERSION,
        "generated_at": status["generated_at"],
        "counts": counts,
        "coverage": {stage: dict(by_stage.get(stage, {})) for stage in STAGES},
        "jobs": status["counts"]["jobs_by_status"],
        "model": status["model"],
        "backend": status["backend"],
        "usage_totals": status["usage_totals"],
        "tickets": {
            "by_status": status["counts"]["tickets_by_status"],
            "by_kind": status["counts"]["tickets_by_kind"],
        },
        "records": records,
        "networks": networks,
        "provenance": {
            "active_config_hash": _setting(conn, "active_config_hash"),
            "baseline_preserved": baseline_path is not None,
            "eligibility": "completed current four-stage ancestry with approved review",
        },
    }
    result = _load_baseline(baseline_path)
    result["pipeline"] = overlay
    return result


def export_projection(conn, path, baseline_path=None):
    """Atomically export a projection JSON file and return the exported object."""
    projection = build_projection(conn, baseline_path=baseline_path)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                         prefix="." + target.name + ".", suffix=".tmp", delete=False) as f:
            temp_path = f.name
            json.dump(projection, f, ensure_ascii=False, sort_keys=True, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, target)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
    return projection
