"""Find out which units make a model decline, by coding stress batches in small slices with no fallback.

Usage: ethogram/.venv/bin/python ethogram/scripts/decline_probe.py --model claude-opus-5-5 [--size 25] [--batches O1_social,O2_structural]
Writes ethogram/work/decline_probe/<model>.json
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from llm import call_json
from stress_test import CODEBOOK, SCHEMA, SYSTEM, fmt

WORK = Path(__file__).resolve().parents[2] / "ethogram" / "work"


def probe(model, name, units, effort):
    user = (
        f"Codebook v0:\n<codebook>\n{CODEBOOK.read_text()}\n</codebook>\n\n"
        f"Your batch: {len(units)} units.\n<units>\n" + "\n\n".join(fmt(u) for u in units) + "\n</units>"
    )
    try:
        _, rec = call_json(f"decline_probe_{model}", name, model, SYSTEM, user, SCHEMA, effort=effort, max_tokens=32000, fallback=False)
    except RuntimeError:
        rec = json.loads((WORK / "llm_log" / f"decline_probe_{model}" / f"{name}.json").read_text())
    return {
        "slice": name,
        "unit_ids": [u["unit_id"] for u in units],
        "stop_reason": rec["stop_reason"],
        "stop_details": rec["stop_details"],
        "served": rec["model_served"],
        "usage": rec["usage"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--size", type=int, default=25)
    ap.add_argument("--batches", default="O1_social,O2_structural,O3_edge")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--max-slices", type=int, default=0, help="probe only the first N slices of each batch")
    args = ap.parse_args()
    units = {u["unit_id"]: u for u in map(json.loads, open(WORK / "units.jsonl"))}
    jobs = []
    for b in args.batches.split(","):
        ids = json.loads((WORK / "stress" / f"{b}.json").read_text())["unit_ids"]
        for i in range(0, len(ids), args.size):
            if args.max_slices and i // args.size >= args.max_slices:
                break
            jobs.append((f"{b}_{i // args.size:02d}", [units[x] for x in ids[i:i + args.size]]))
    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(lambda j: probe(args.model, j[0], j[1], args.effort), jobs))
    out = WORK / "decline_probe"
    out.mkdir(exist_ok=True)
    (out / f"{args.model}.json").write_text(json.dumps(results, indent=1))
    for r in results:
        sd = r["stop_details"] or {}
        print(f"{r['slice']:18s} {r['stop_reason']:9s} {sd.get('category') or '':22s} in={r['usage']['input_tokens']:6d} out={r['usage']['output_tokens']:5d}  {(sd.get('explanation') or '')[:90]}")
    declined = sum(r["stop_reason"] == "refusal" for r in results)
    print(f"{args.model}: {declined}/{len(results)} slices declined")


if __name__ == "__main__":
    main()
