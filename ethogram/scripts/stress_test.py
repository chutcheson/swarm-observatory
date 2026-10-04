"""L1b stress test: independent second observers code fresh units against the codebook
and propose revisions.

Usage: ethogram/.venv/bin/python ethogram/scripts/stress_test.py [--n 150] [--only O1,O2]
Writes ethogram/work/stress/<observer>.json (units shown + model output) and logs each call.
"""

import argparse
import collections
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from llm import call_json
from sample import family_group, regime

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "ethogram" / "work"
CODEBOOK = ROOT / "ethogram" / "ETHOGRAM_v0.md"
# Opus 5.5's cyber classifier declines most batches of this corpus (decline_probe: 8/12 slices);
# Opus 5 declined none, so Opus-tier runs use Opus 5.
MODEL = "claude-opus-5"


def is_social(u):
    cues = u["signature"] or u["cohort_tokens"] or u["n_round_refs"] or u["n_clock_refs"] or any(
        u[k] for k in ("kw_ack", "kw_correction", "kw_request", "kw_schedule", "kw_final_answer")
    )
    return bool(cues) and u["prose_chars"] >= 25


def fmt(u):
    head = [
        u["unit_id"], f"wiki={u['wiki']}", u["time"], f"label={u['label'] or '(blank)'}",
        u["edit_kind"] + (f" (removes text by {u['prev_label']})" if u["overwrites_other"] else ""),
        f"family={u['page_family']}", f"page_editors={u['page_n_labels']}", f"summary={u['change_summary']!r}",
    ]
    if u["n_mutated_lines"]:
        head.append(f"resaved_others_lines_altered={u['n_mutated_lines']}")
    body = u["rendering"] or "[no added text]"
    rem = f"\nREMOVED: {u['removed_preview']}" if u["removed_preview"] and u["edit_kind"] != "append" else ""
    return "### " + " | ".join(head) + "\n" + body + rem


def round_robin(pools, n, rng, taken):
    """Draw up to n units, cycling over pools so small strata are represented; one per template."""
    seen_t = set()
    for p in pools.values():
        rng.shuffle(p)
    out = []
    while len(out) < n and any(pools.values()):
        for key in list(pools):
            while pools[key]:
                u = pools[key].pop()
                if u["unit_id"] in taken or u["template_hash"] in seen_t:
                    continue
                out.append(u)
                taken.add(u["unit_id"])
                seen_t.add(u["template_hash"])
                break
            if len(out) >= n:
                break
    return out


def strata(units, n, seed):
    rng = random.Random(seed)
    adlib = set(re.findall(r"^### (\S+)", (WORK / "sample_adlib.txt").read_text(), re.M))
    fresh = [u for u in units if u["unit_id"] not in adlib]
    taken = set()

    def pools(key, keep):
        d = collections.defaultdict(list)
        for u in fresh:
            if keep(u):
                d[key(u)].append(u)
        return d

    social = round_robin(pools(lambda u: (family_group(u["page_family"]), u["wiki"], u["time"][:10]), is_social), n, rng, taken)
    structural = round_robin(
        pools(lambda u: (regime(u), u["wiki"], u["page_n_labels"] >= 20), lambda u: not is_social(u) and u["rendering"]),
        n, rng, taken,
    )
    edge_pools = {
        "short_social": [u for u in fresh if is_social(u) and u["prose_chars"] < 200],
        "collateral": [u for u in fresh if u["collateral_mutation"]],
        "removal": [u for u in fresh if u["edit_kind"] == "delete_lines"],
        "first_held": [u for u in fresh if u["edit_kind"] == "first_held"],
        "odd_family": [u for u in fresh if u["page_family"] in ("unknown", "mixed-task", "off_store_unclassified")],
        "small_wikis": [u for u in fresh if u["wiki"] != "dse"],
        "social_overwrite": [u for u in fresh if u["overwrites_other"] and is_social(u)],
        "system_pages": [u for u in fresh if re.search(r"RecentChanges|Admin|StartSeite|WillkommenImWiki|TestSeite|SandBox", u["page_id"])],
    }
    edge = round_robin(edge_pools, n, rng, taken)
    return {
        "O1_social": ("social-signaling stream: units with signatures, cohort names, round/clock references or request/ack/correction cues", social),
        "O2_structural": ("structural stream: link lists, scaffolding, probes and other non-prose edits, spread over wikis and hub vs non-hub pages", structural),
        "O3_edge": ("edge cases: short messages, resaves that altered others' text, removals, odd page families, the three small wikis, system/hub pages", edge),
    }


SYSTEM = """You are a second observer in an ethology-style study of AI agents' behavior on public wikis. A first observer drafted an ethogram (a codebook of behaviors) from one sample of the record. Your job is to stress-test it on fresh units: code each unit with the codebook, and find what the codebook misses, blurs or gets wrong.

The record: many AI agent runs, mostly working on eval-style data-retrieval tasks, edited four public wikis in May–July 2026. Each unit is one save, shown as what it changed: the lines it added, plus a preview of lines it removed. Rendering conventions: runs of URL lines are summarized as `[N URL line(s): via-host -> target-host xK, ...; e.g. first-url | last-url]`; runs of generated identifiers as `[N generated IDs, e.g. X]`; `[mojibake]` marks collapsed encoding damage; `REMOVED:` shows removed lines; lines the editor merely re-saved are excluded from the added text. The header gives edit mechanics that are already computed by rule.

Coding rules: codes describe what is visible in the unit (form), not inferred purpose. A unit can carry several codes. Use code ids such as A2 or D12, and modifier names (OBFUSCATED, SELF_LABELED_TEST, URGENCY) where they apply. Layer 0 mechanics and the rule-coded E acts are computed separately; tag them only when the unit shows something the rule would miss.

Be a critical observer: the value of your work is in disagreement. When no code fits, set fit to "none" and describe the behavior in the note. When a code fits awkwardly, set fit to "partial" and say why. Keep notes brief, and leave them empty when there is nothing to add. Then propose concrete revisions: new acts (each with an operational definition another coder could apply from the unit alone, plus example unit ids from your batch), splits of codes that lump distinct behaviors, merges of codes you could not tell apart, definitions to sharpen, and codes that look unnecessary. Also say whether the rendering hid anything you needed to code reliably."""

SCHEMA = {
    "type": "object",
    "properties": {
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string"},
                    "codes": {"type": "array", "items": {"type": "string"}},
                    "fit": {"type": "string", "enum": ["good", "partial", "none"]},
                    "note": {"type": "string"},
                },
                "required": ["unit_id", "codes", "fit", "note"],
                "additionalProperties": False,
            },
        },
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["new_act", "split", "merge", "redefine", "drop", "modifier", "rendering"]},
                    "codes_affected": {"type": "array", "items": {"type": "string"}},
                    "name": {"type": "string"},
                    "definition": {"type": "string"},
                    "rationale": {"type": "string"},
                    "example_unit_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["kind", "codes_affected", "name", "definition", "rationale", "example_unit_ids"],
                "additionalProperties": False,
            },
        },
        "general_observations": {"type": "string"},
    },
    "required": ["units", "proposals", "general_observations"],
    "additionalProperties": False,
}


URLQUERY_ADDENDUM = """

This batch comes from a second habitat. Each unit is one report from a public URL-scanning service: an agent submitted a URL and the service's browser visited it, so the scanner works as a remote browser. Shown: the submitted URL (percent-decoded), the final URL, the page title, the hosts contacted, HTTP and script counts, and, when the URL smuggled content (base64 echo endpoints, data: URLs), the decoded payload. Secrets are redacted. There is no prose channel and no shared page here.

The codebook was built on wiki edits. Code these units with it wherever an act transfers. The main question is portability: for every act in the codebook, judge whether it is portable (the same behavior could appear on any substrate), wiki-specific (it depends on wiki mechanics), or unclear here. Propose portable acts, defined independently of substrate, plus scanner-specific forms for behavior the codebook cannot express."""

PORTABILITY = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "verdict": {"type": "string", "enum": ["portable", "wiki_specific", "unclear"]},
            "note": {"type": "string"},
        },
        "required": ["code", "verdict", "note"],
        "additionalProperties": False,
    },
}


def fmt_urlquery(u):
    return f"### {u['unit_id']} | channel=urlquery | {u['time']} | hosts={u['n_hosts']}\n{u['rendering']}"


def run_observer(name, desc, units, habitat="wiki"):
    system, schema, render = SYSTEM, SCHEMA, fmt
    if habitat == "urlquery":
        system = SYSTEM + URLQUERY_ADDENDUM
        schema = json.loads(json.dumps(SCHEMA))
        schema["properties"]["portability"] = PORTABILITY
        schema["required"].append("portability")
        render = fmt_urlquery
    user = (
        f"Codebook v0:\n<codebook>\n{CODEBOOK.read_text()}\n</codebook>\n\n"
        f"Your batch: {len(units)} units from the {desc}.\n<units>\n" + "\n\n".join(render(u) for u in units) + "\n</units>"
    )
    data, rec = call_json("stress_v0", name, MODEL, system, user, schema, effort="high")
    out = WORK / "stress"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps({"stratum": desc, "unit_ids": [u["unit_id"] for u in units], "result": data}, indent=1, ensure_ascii=False))
    return name, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--only", default="")
    ap.add_argument("--dry", action="store_true", help="print batch sizes, make no API calls")
    ap.add_argument("--urlquery", action="store_true", help="run the second-habitat observer (O4) on URLQuery units")
    args = ap.parse_args()
    if args.urlquery:
        uq = [json.loads(l) for l in open(WORK / "urlquery" / "units.jsonl")]
        rng = random.Random(args.seed)
        rng.shuffle(uq)
        batch = sorted(uq[: args.n], key=lambda u: u["time"] or "")
        print(f"O4_urlquery: {len(batch)} units, {sum(len(fmt_urlquery(u)) for u in batch)} chars")
        if not args.dry:
            name, rec = run_observer("O4_urlquery", "URL-scanner habitat (a stratified sample of public reports)", batch, habitat="urlquery")
            print(f"{name}: {rec['stop_reason']}, served by {rec['model_served']}, {rec['seconds']}s, {rec['usage']}, ~${rec['est_cost_usd']}")
        return
    units = [json.loads(l) for l in open(WORK / "units.jsonl")]
    plan = strata(units, args.n, args.seed)
    if args.only:
        plan = {k: v for k, v in plan.items() if k in args.only.split(",")}
    for name, (desc, us) in plan.items():
        chars = sum(len(fmt(u)) for u in us)
        print(f"{name}: {len(us)} units, {chars} chars, wikis={dict(collections.Counter(u['wiki'] for u in us))}")
    if args.dry:
        return
    with ThreadPoolExecutor(len(plan)) as ex:
        for name, rec in ex.map(lambda kv: run_observer(kv[0], *kv[1]), plan.items()):
            print(f"{name}: {rec['stop_reason']}, served by {rec['model_served']}, {rec['seconds']}s, "
                  f"{rec['usage']}, ~${rec['est_cost_usd']}")


if __name__ == "__main__":
    main()
