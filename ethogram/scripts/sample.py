"""Draw samples of coding units.

  adlib    stratified sample for open-ended reading (ethogram drafting)
  episode  every unit on one page in order (focal sampling of a whole interaction)

Usage:
  python3 ethogram/scripts/sample.py adlib [--n 260] [--seed 1]
  python3 ethogram/scripts/sample.py episode dse/DataUSAStateSequenceCollab2027
"""

import argparse
import collections
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "ethogram" / "work" / "units.jsonl"


def regime(u):
    """Coarse form-only stratum, used for sampling balance, not as a category."""
    if u["page_family"] == "probe-test" or (u["kw_test_label"] and u["prose_chars"] < 200):
        return "probe"
    if u["prose_chars"] >= 200 and u["url_line_frac"] < 0.5:
        return "prose"
    if u["n_placeholders"] >= 3 or u["n_markers"] or u["n_wiki_selflinks"] >= 3:
        return "scaffold"
    if u["n_urls"] >= 3:
        return "links"
    if u["edit_kind"] == "delete_lines":
        return "removal"
    return "other"


def family_group(fam):
    if fam in ("relay-coordination", "source-cache-url-list", "loop-chain-infrastructure", "probe-test"):
        return fam
    if fam in ("off_store_unclassified", "source-or-unclassified", "unknown", "mixed-task"):
        return "unclassified"
    return "task-specific"


def fmt(u):
    head = (
        f"### {u['unit_id']} | {u['time']} | label={u['label']} | {u['edit_kind']}"
        f"{' (overwrites ' + str(u['prev_label']) + ')' if u['overwrites_other'] else ''}"
        f" | fam={u['page_family']} | page_revs={u['page_n_revs']} | summary={u['change_summary']!r}"
    )
    body = u["rendering"] or "[no added text]"
    rem = f"\n  REMOVED: {u['removed_preview']}" if u["removed_preview"] and u["edit_kind"] != "append" else ""
    return f"{head}\n{body}{rem}\n"


def adlib(units, n, seed):
    rng = random.Random(seed)
    quota = {"prose": 0.42, "links": 0.18, "scaffold": 0.12, "probe": 0.1, "removal": 0.06, "other": 0.12}
    cells = collections.defaultdict(list)
    seen_templates = set()
    rng.shuffle(units)
    for u in units:
        if u["template_hash"] in seen_templates:
            continue  # one exemplar per template keeps near-duplicates from crowding the sample
        seen_templates.add(u["template_hash"])
        cells[(regime(u), family_group(u["page_family"]))].append(u)
    picked = []
    for reg, share in quota.items():
        groups = [k for k in cells if k[0] == reg]
        want = round(n * share)
        # round-robin across family groups so small groups are represented
        while want > 0 and any(cells[g] for g in groups):
            for g in groups:
                if cells[g] and want > 0:
                    picked.append(cells[g].pop())
                    want -= 1
    picked.sort(key=lambda u: u["time"])
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["adlib", "episode"])
    ap.add_argument("page", nargs="?")
    ap.add_argument("--n", type=int, default=260)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    units = [json.loads(l) for l in open(UNITS)]
    if args.mode == "adlib":
        picked = adlib(units, args.n, args.seed)
        print(f"# ad libitum sample: {len(picked)} units, seed {args.seed}")
        print(collections.Counter(regime(u) for u in picked))
    else:
        picked = sorted((u for u in units if u["page_id"] == args.page), key=lambda u: u["seq"])
        print(f"# episode {args.page}: {len(picked)} units")
    for u in picked:
        print(fmt(u))


if __name__ == "__main__":
    main()
