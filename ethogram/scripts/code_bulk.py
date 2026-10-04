"""L1e bulk coding: the model-coded acts of CODEBOOK_v1_model.md over the social stream.

Selects the units that need a model (signalling cues, unconfirmed probes, prose that no rule
codes), codes each distinct text once and copies its codes to exact duplicates. Resumable:
units already coded in a run are skipped on re-run, so an interrupted run just restarts.

  work/bulk/<run>/batches/<name>.json   one file per request: unit ids, served model, output
  work/bulk/<run>/codes.jsonl           merged per-unit codes for that run (all duplicates)
  work/model_codes.jsonl                the main run's codes, read by rule_code.py and the viewer

Usage:
  ethogram/.venv/bin/python ethogram/scripts/code_bulk.py --pilot 3          # first 3 batches
  ethogram/.venv/bin/python ethogram/scripts/code_bulk.py                    # the whole stream
  ethogram/.venv/bin/python ethogram/scripts/code_bulk.py --run rel_opus48 --model claude-opus-4-8 --sample 300
  ethogram/.venv/bin/python ethogram/scripts/code_bulk.py --merge-only
"""

import argparse
import collections
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from llm import call_json
from rule_code import rule_codes
from stress_test import fmt, is_social

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "ethogram" / "work"
CODEBOOK = ROOT / "ethogram" / "CODEBOOK_v1_model.md"
MAIN_RUN = "v1_main"

CODES = ["C1a", "C1b", "C2", "A4", "B4", "B5", "B6"] + [f"D{i}" for i in range(1, 19)] + ["D19a", "D19b", "D20", "D21", "E3", "E7"]

SYSTEM = """You code units for an ethology-style study of AI agents' behavior on four public wikis (May-July 2026), using the codebook below. Many AI agent runs, mostly working on eval-style data-retrieval tasks, left these edits. Each unit is one save. For every unit, return its number `n`, the codes of all acts present (an empty list when none applies), and the extraction fields. Code form, not purpose, and code each unit from its own text.

<codebook>
{codebook}
</codebook>"""

SCHEMA = {
    "type": "object",
    "properties": {
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "codes": {"type": "array", "items": {"type": "string", "enum": CODES}},
                    "addressees": {"type": "array", "items": {"type": "string"}},
                    "self_ids": {"type": "array", "items": {"type": "string"}},
                    "gap": {"type": "string"},
                },
                "required": ["n", "codes", "addressees", "self_ids", "gap"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["units"],
    "additionalProperties": False,
}


def stream_reason(u, rc):
    """Why a unit needs the model pass; None means the rule layer covers it."""
    if not u["rendering"]:
        return None
    if is_social(u):
        return "social"
    if "C1_WRITE_PROBE?" in rc:
        return "probe_candidate"
    if not rc and u["prose_chars"] >= 25:
        return "uncoded_prose"
    if u["prose_chars"] >= 200 and u["url_line_frac"] < 0.5:
        return "prose"
    return None


def dedup_key(u):
    return (u["wiki"], u["page_family"], u["edit_kind"], u["rendering"], u["removed_preview"])


def load_stream():
    """Return representatives (one per distinct text, earliest save) and key -> member unit ids."""
    units = [json.loads(l) for l in open(WORK / "units.jsonl")]
    groups = collections.defaultdict(list)
    reasons = collections.Counter()
    for u in units:
        r = stream_reason(u, rule_codes(u))
        if r:
            reasons[r] += 1
            groups[dedup_key(u)].append(u)
    reps, members = [], {}
    for k, us in groups.items():
        us.sort(key=lambda x: x["time"])
        reps.append(us[0])
        members[us[0]["unit_id"]] = [x["unit_id"] for x in us]
    reps.sort(key=lambda u: (u["wiki"], u["page_id"], u["seq"]))
    return reps, members, reasons


def done_ids(run_dir):
    got = {}
    for f in sorted((run_dir / "batches").glob("*.json")):
        rec = json.loads(f.read_text())
        for uid, row in rec["coded"].items():
            got[uid] = row | {"served": rec["served"]}
    return got


def code_batch(run, run_dir, name, units, model, effort, system):
    """Code one batch; on a refusal or truncation, split it and code the halves."""
    body = "\n\n".join(f"#{i + 1} {fmt(u)}" for i, u in enumerate(units))
    user = f"Batch of {len(units)} units, ordered by page and time.\n<units>\n{body}\n</units>"
    try:
        data, rec = call_json(f"bulk_{run}", name, model, system, user, SCHEMA, effort=effort, max_tokens=32000)
    except RuntimeError as e:
        if len(units) == 1:
            out = {"unit_ids": [units[0]["unit_id"]], "served": None, "coded": {}, "declined": [units[0]["unit_id"]], "error": str(e)[:300]}
            (run_dir / "batches" / f"{name}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
            return [(name, 0.0, 1, None)]
        mid = len(units) // 2
        return (code_batch(run, run_dir, f"{name}a", units[:mid], model, effort, system)
                + code_batch(run, run_dir, f"{name}b", units[mid:], model, effort, system))
    coded = {}
    for row in data["units"]:
        i = row["n"] - 1
        if 0 <= i < len(units) and units[i]["unit_id"] not in coded:
            coded[units[i]["unit_id"]] = {k: row[k] for k in ("codes", "addressees", "self_ids", "gap")}
    if len(units) > 1 and len(coded) < len(units) / 2:
        # a fallback model sometimes answers a declined batch with an empty list; split it like a refusal
        mid = len(units) // 2
        return (code_batch(run, run_dir, f"{name}a", units[:mid], model, effort, system)
                + code_batch(run, run_dir, f"{name}b", units[mid:], model, effort, system))
    out = {
        "unit_ids": [u["unit_id"] for u in units],
        "served": rec["model_served"],
        "fallback": bool(rec["fallback_switches"]),
        "usage": rec["usage_detail"],
        "est_cost_usd": rec["est_cost_usd"],
        "seconds": rec["seconds"],
        "coded": coded,
    }
    (run_dir / "batches" / f"{name}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return [(name, rec["est_cost_usd"], len(units) - len(coded), rec["model_served"])]


def merge(run, members):
    """Write per-unit codes for a run, copying each representative's codes to its duplicates."""
    run_dir = WORK / "bulk" / run
    got = done_ids(run_dir)
    rows = []
    for rep, row in got.items():
        for uid in members.get(rep, [rep]):
            rows.append({"unit_id": uid, "rep": rep, "run": run, "served": row["served"], **{k: row[k] for k in ("codes", "addressees", "self_ids", "gap")}})
    rows.sort(key=lambda r: r["unit_id"])
    with open(run_dir / "codes.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if run == MAIN_RUN:
        (WORK / "model_codes.jsonl").write_text((run_dir / "codes.jsonl").read_text())
    return len(got), len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=MAIN_RUN)
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--pilot", type=int, default=0, help="code only the first N pending batches")
    ap.add_argument("--sample", type=int, default=0, help="code a random sample of N representatives (reliability runs)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--merge-only", action="store_true")
    args = ap.parse_args()

    reps, members, reasons = load_stream()
    run_dir = WORK / "bulk" / args.run
    (run_dir / "batches").mkdir(parents=True, exist_ok=True)
    print(f"stream: {sum(reasons.values())} units {dict(reasons)} -> {len(reps)} distinct texts")
    if args.merge_only:
        n_rep, n_units = merge(args.run, members)
        print(f"merged {args.run}: {n_rep} texts -> {n_units} units")
        return

    if args.sample:
        rng = random.Random(args.seed)
        reps = rng.sample(reps, args.sample)  # shuffled, so batches differ from the main run's
    got = done_ids(run_dir)
    pending = [u for u in reps if u["unit_id"] not in got]
    batches = [pending[i:i + args.batch] for i in range(0, len(pending), args.batch)]
    if args.pilot:
        batches = batches[: args.pilot]
    prefix = time.strftime("%H%M%S")
    print(f"{len(got)} texts already coded; {len(pending)} pending in {len(batches)} batches ({args.model}, effort {args.effort})")

    system = [{"type": "text", "text": SYSTEM.format(codebook=CODEBOOK.read_text()), "cache_control": {"type": "ephemeral"}}]
    cost, missing, served = 0.0, 0, collections.Counter()
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(code_batch, args.run, run_dir, f"{prefix}_{i:04d}", b, args.model, args.effort, system) for i, b in enumerate(batches)]
        for k, fut in enumerate(as_completed(futs), 1):
            try:
                results = fut.result()
            except Exception as e:  # network or API errors: leave the batch pending for the next run
                print(f"  batch failed: {type(e).__name__}: {str(e)[:200]}", flush=True)
                continue
            for name, c, miss, model in results:
                cost += c
                missing += miss
                served[model] += 1
            if k % 10 == 0 or k == len(futs):
                print(f"  {k}/{len(futs)} batches | ${cost:.2f} | {time.time() - t0:.0f}s | missing {missing} | served {dict(served)}", flush=True)
    n_rep, n_units = merge(args.run, members)
    print(f"done: ${cost:.2f} this pass | {n_rep} texts coded ({n_units} units) in {args.run} | missing/declined {missing}")


if __name__ == "__main__":
    main()
