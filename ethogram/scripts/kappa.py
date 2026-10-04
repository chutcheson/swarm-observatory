"""Per-act agreement between two coding runs of the model-coded acts (L1c/L1d reliability).

Compares the texts both runs coded, leaving out texts either run had served by the other
run's model (a refusal fallback would otherwise compare a model with itself). Reports Cohen's
kappa with a bootstrap 95% interval, positives per coder, and a tier against the agreement bar
in PLAN.md: solid >= 0.80, usable 0.60-0.80, weak < 0.60, sparse when either coder has < 5.

Usage: ethogram/.venv/bin/python ethogram/scripts/kappa.py [--a v1_main] [--b rel_opus48]
Writes ethogram/work/kappa_v1.json.
"""

import argparse
import json
import random
from pathlib import Path

from code_bulk import CODES

WORK = Path(__file__).resolve().parents[2] / "ethogram" / "work"


def load(run):
    rows = {}
    for r in map(json.loads, open(WORK / "bulk" / run / "codes.jsonl")):
        if r["unit_id"] == r["rep"]:
            rows[r["rep"]] = r
    return rows


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def tier(k, na, nb):
    if min(na, nb) < 5:
        return "sparse"
    return "solid" if k >= 0.8 else "usable" if k >= 0.6 else "weak"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="v1_main")
    ap.add_argument("--b", default="rel_opus48")
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    A, B = load(args.a), load(args.b)
    model_b = next(iter(B.values()))["served"]
    model_a = next(iter(A.values()))["served"]
    ids = sorted(i for i in set(A) & set(B) if A[i]["served"] != model_b and B[i]["served"] != model_a)
    print(f"{args.a} vs {args.b}: {len(set(A) & set(B))} shared texts, {len(ids)} after dropping cross-served fallbacks")
    rng = random.Random(0)
    boots = [[rng.randrange(len(ids)) for _ in ids] for _ in range(args.boot)]
    out = {"a": args.a, "b": args.b, "n": len(ids), "acts": {}}
    for c in CODES:
        a = [c in A[i]["codes"] for i in ids]
        b = [c in B[i]["codes"] for i in ids]
        na, nb = sum(a), sum(b)
        if na + nb == 0:
            continue
        k = kappa(a, b)
        ks = sorted(kappa([a[j] for j in s], [b[j] for j in s]) for s in boots)
        lo, hi = ks[int(0.025 * len(ks))], ks[int(0.975 * len(ks)) - 1]
        out["acts"][c] = {"kappa": round(k, 3), "ci": [round(lo, 3), round(hi, 3)], "pos_a": na, "pos_b": nb, "tier": tier(k, na, nb)}
        print(f"{c:5s} {args.a}={na:3d} {args.b}={nb:3d}  kappa={k:5.2f}  [{lo:5.2f}, {hi:5.2f}]  {tier(k, na, nb)}")
    (WORK / "kappa_v1.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
