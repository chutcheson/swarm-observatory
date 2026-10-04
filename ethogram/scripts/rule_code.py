"""Rule layer: deterministic codes and interaction structures for the wiki corpus.

No model is used here. These are the acts v1 marks rule-coded, plus the L2-L5 structures
(actor identity, roles, overwrite network, source->target foraging flow, timing) that a
portrayal draws on. Writes ethogram/work/coded.jsonl and ethogram/work/structures.json.

Usage: ethogram/.venv/bin/python ethogram/scripts/rule_code.py [--wiki dse]
"""

import argparse
import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "ethogram" / "work"


def rule_codes(u):
    """Assign the v1 rule-coded acts to one unit from its deterministic features."""
    c = set()
    ek = u["edit_kind"]
    # foraging
    if u["n_urls"]:
        direct = u["n_urls"] - u["n_proxy_urls"] - u["n_wiki_selflinks"]
        if u["n_proxy_urls"]:
            c.add("A2_LINK_ROUTED")
        if direct > 0:
            c.add("A1_LINK_DIRECT")
        if u["n_urls"] >= 4 and u["n_url_targets"] <= 2 and u["n_proxy_urls"] + direct >= 4:
            c.add("A3a_SOURCE_VARIANT_SWEEP")
        if u["n_wiki_selflinks"] >= 4:
            c.add("A3b_SELF_LINK_SWEEP")
    # construction
    if u["n_wiki_selflinks"] and "A3b_SELF_LINK_SWEEP" not in c:
        c.add("B1_SELF_NAV")
    if re.search(r"#\s*(REDIRECT|WEITERLEITUNG)", u["rendering"], re.I):
        c.add("B1b_REDIRECT_CREATE")
    if u["n_placeholders"] >= 3 or re.search(r"(LoopNextWord|CachePokeWord|NextChild|Continue\w*\d{3,}\?)", u["rendering"]):
        c.add("B2_PLACEHOLDER_CHAIN")
    if u["n_markers"]:
        c.add("B3_WRITE_MARKER")
    if re.search(r"RecentChanges|StartSeite|WillkommenImWiki", u["page_id"]) and (u["n_urls"] or u["prose_chars"] > 40) and u["page_family"] != "relay-coordination":
        pass  # system-page hijack is habitat-specific; left for the model pass to confirm
    # content-free churn vs real edits: only a marker/float/epoch changed
    body = re.sub(r"\s+", " ", u["rendering"]).strip()
    only_token = bool(body) and u["prose_chars"] < 25 and not u["n_urls"] and (u["n_markers"] or re.fullmatch(r"[\W\d._]*(marker|mark|rand|hb|poke)?[\W\d._]*", body, re.I))
    if ek in ("overwrite", "modify", "append") and only_token:
        c.add("E8_ID_CHURN")
    # probing (form only)
    if u["change_summary"] and re.search(r"\btest|probe\b", u["change_summary"] or "", re.I) and u["prose_chars"] < 120 and not u["n_urls"]:
        c.add("C1_WRITE_PROBE?")  # '?' = needs model to confirm visible content is the test
    if re.search(r"Beschreibe hier die neue Seite|Describe the new page here", u["rendering"]):
        c.add("C3_TEMPLATE_RESIDUE")
    if re.search(r"(.)\1{40,}", u["rendering"]):
        c.add("C4_JUNK_FILL")
    # acting on others
    if u["overwrites_other"] and ek == "overwrite":
        c.add("E1_OVERWRITE_OTHER")  # v0 definition: no prior authored line survives
    elif u["overwrites_other"] and ek == "modify":
        c.add("E1b_PARTIAL_OVERWRITE")  # removes some of another label's lines while adding its own
    if ek == "delete_lines":
        c.add("E4_REMOVE")
    if re.search(r"\brevert|rollback|restore[d]? (to )?(revision|version)|wiederherg", (u["change_summary"] or "") + " " + u["rendering"], re.I):
        c.add("E7_REVERT_RESTORE")
    for fl in u["url_flags"]:
        c.add("mod:OBFUSCATED")
    if u["kw_urgent"]:
        c.add("mod:URGENCY")
    if u["kw_test_label"]:
        c.add("mod:SELF_LABELED_TEST")
    return sorted(c)


IDENT_RE = re.compile(r"\b([A-Z][A-Za-z]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[A-Za-z0-9]*)\b")


def actor_key(u):
    """Best available identity: signature if present, else handle; blank handles fall back to ip16."""
    return u["signature"] or u["label"] or f"ip:{u['ip16']}"


SYSTEMS = {"A": "Foraging", "B": "Construction", "C": "Probing", "D": "Signaling", "E": "Acting on others"}
ROLE_OF_SYSTEM = {"A": "forager", "B": "builder", "C": "prober", "D": "signaler", "E": "overwriter"}
E_ON_OTHERS = {"E1", "E1b", "E3", "E7"}  # E4 removals and E8 token churn are not acts on others' content


def save_systems(codes):
    """The act systems one save shows; modifiers and self-directed E acts are left out."""
    out = set()
    for c in codes:
        if c.startswith("mod:"):
            continue
        head = c.split("_")[0].rstrip("?")
        if head[0] == "E" and head not in E_ON_OTHERS:
            continue
        out.add(head[0])
    return out


def role_of(save_sys):
    """Coarse role from an actor's saves: the content system present in at least half of its coded saves.

    Acting on others (E) is relational, not a kind of content, so it is reported as a separate
    overwrite rate rather than a role. Ties break in a fixed order: D, A, B, C.
    """
    coded = [s - {"E"} for s in save_sys if s - {"E"}]
    if not coded:
        return "uncoded"
    share = collections.Counter(x for s in coded for x in s)
    sys_ = min(share, key=lambda k: (-share[k], "DABC".index(k)))
    return ROLE_OF_SYSTEM[sys_] if share[sys_] / len(coded) >= 0.5 else "mixed"


def load_model_codes():
    path = WORK / "model_codes.jsonl"
    if not path.exists():
        return {}
    return {r["unit_id"]: r for r in map(json.loads, open(path))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki", default="all")
    args = ap.parse_args()
    units = [json.loads(l) for l in open(WORK / "units.jsonl")]
    if args.wiki != "all":
        units = [u for u in units if u["wiki"] == args.wiki]
    model = load_model_codes()
    for u in units:
        u["rule_codes"] = rule_codes(u)
        u["actor"] = actor_key(u)
        m = model.get(u["unit_id"])
        u["model_codes"] = m["codes"] if m else []
        u["addressees"] = m["addressees"] if m else []
        u["self_ids"] = m["self_ids"] if m else []
        u["gap"] = m["gap"] if m else ""
        u["coded_by"] = m["served"] if m else None
    # resolve the previous editor on each page to an actor, so overwrite edges and roles share one identity
    by_page = collections.defaultdict(list)
    for u in units:
        by_page[u["page_id"]].append(u)
    for us in by_page.values():
        us.sort(key=lambda x: x["seq"])
        for prev, u in zip([None] + us[:-1], us):
            u["prev_actor"] = prev["actor"] if prev else None
    with open(WORK / "coded.jsonl", "w") as f:
        for u in units:
            f.write(json.dumps(u, ensure_ascii=False) + "\n")

    C = collections.Counter
    code_freq = C(c for u in units for c in u["rule_codes"] + u["model_codes"])

    # L2 overwrite network: whose authored content each save removed (full or partial overwrite)
    overwrite_edges = C(
        (u["actor"], u["prev_actor"]) for u in units
        if u["overwrites_other"] and u["edit_kind"] in ("overwrite", "modify") and u["prev_actor"] and u["prev_actor"] != u["actor"]
    )
    self_overwrites = sum(1 for u in units if u["overwrites_other"] and u["prev_actor"] == u["actor"])
    # L2 signaling network: who addresses whom by name (D8 addressees, as written)
    address_edges = C((u["actor"], a.strip().lstrip("@")) for u in units for a in u["addressees"] if a.strip())

    # L4 roles: every actor, from the systems present in each of its saves
    actor_saves = collections.defaultdict(list)
    for u in units:
        actor_saves[u["actor"]].append(save_systems(u["rule_codes"] + u["model_codes"]))
    roles = C(role_of(s) for s in actor_saves.values())

    # L5 foraging flow: via-host -> target-host counts across all link runs (routes only, no URLs)
    route = C()
    for u in units:
        for m in re.finditer(r"([a-z0-9.%-]+) -> ([a-z0-9.?%-]+) x(\d+)", u["rendering"]):
            route[(m.group(1), m.group(2))] += int(m.group(3))

    by_hour = C(u["time"][:13] for u in units)
    page_editors = collections.defaultdict(set)
    for u in units:
        page_editors[u["page_id"]].add(u["actor"])

    structures = {
        "n_units": len(units),
        "n_model_coded": sum(1 for u in units if u["coded_by"]),
        "code_freq": dict(code_freq.most_common()),
        "n_actors": len(actor_saves),
        "roles": dict(roles),
        "top_overwrite_pairs": [{"overwriter": a, "overwritten": b, "n": n} for (a, b), n in overwrite_edges.most_common(25)],
        "overwrite_edges_total": sum(overwrite_edges.values()),
        "self_overwrites_excluded": self_overwrites,
        "top_address_pairs": [{"from": a, "to": b, "n": n} for (a, b), n in address_edges.most_common(25)],
        "top_routes": [{"via": v, "to": t, "n": n} for (v, t), n in route.most_common(30)],
        "saves_by_hour": dict(sorted(by_hour.items())),
        "most_contested_pages": [
            {"page": p, "revs": n, "editors": len(page_editors[p])}
            for p, n in C(u["page_id"] for u in units).most_common(15)
        ],
    }
    (WORK / "structures.json").write_text(json.dumps(structures, indent=1, ensure_ascii=False))
    print(f"coded {len(units)} units ({args.wiki}); model-coded {structures['n_model_coded']}; {len(actor_saves)} actors; roles {dict(roles)}")
    print("top codes:", dict(code_freq.most_common(14)))
    print(f"overwrite edges: {sum(overwrite_edges.values())} (self-overwrites excluded: {self_overwrites}) | address edges: {sum(address_edges.values())} | routes: {len(route)}")


if __name__ == "__main__":
    main()
