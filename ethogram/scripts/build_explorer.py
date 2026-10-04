"""Build the data files behind the swarm viewer (ethogram/explorer/index.html).

  explorer/data/meta.json  dictionaries + one columnar record per save (no text)
  explorer/data/text.json  the rendered diff and removed-text preview per save, same order

Usage: ethogram/.venv/bin/python ethogram/scripts/build_explorer.py   (after rule_code.py)
Serve with: python3 -m http.server -d ethogram/explorer 8765
IP prefixes are left out; renderings already carry no raw URLs, and the build asserts that.
"""

import collections
import json
import re
from datetime import datetime
from pathlib import Path

from rule_code import role_of, save_systems

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "ethogram" / "work"
OUT = ROOT / "ethogram" / "explorer" / "data"
MODEL_CODEBOOK = ROOT / "ethogram" / "CODEBOOK_v1_model.md"

SYSTEM_NAMES = {"A": "Foraging", "B": "Construction", "C": "Probing", "D": "Signaling", "E": "Acting on others", "m": "Modifiers"}

# Rule-coded acts (v1 rule layer). Definitions follow ETHOGRAM_v0.md as amended by v1.
RULE_ACTS = {
    "A1_LINK_DIRECT": ("Direct link", "Adds a URL pointing straight at an external data source."),
    "A2_LINK_ROUTED": ("Routed link", "Adds a URL that wraps a source inside a fetch, convert, filter or archive service."),
    "A3a_SOURCE_VARIANT_SWEEP": ("Source variant sweep", "Adds 4 or more URLs to at most 2 external targets, varying one component."),
    "A3b_SELF_LINK_SWEEP": ("Self-link sweep", "Adds 4 or more wiki self-links differing only in cache-bust or query parameters."),
    "B1_SELF_NAV": ("Self-navigation", "Adds links to pages on this wiki."),
    "B1b_REDIRECT_CREATE": ("Redirect", "Page content is a wiki redirect directive."),
    "B2_PLACEHOLDER_CHAIN": ("Placeholder / chain", "Links to pages that do not exist yet, or continues a numbered page chain."),
    "B3_WRITE_MARKER": ("Write marker", "Adds a content-free token (epoch, random float, unique string) inside a save."),
    "C1_WRITE_PROBE?": ("Probe candidate", "Edit summary says test or probe over a short body; the model pass confirms C1a/C1b."),
    "C3_TEMPLATE_RESIDUE": ("Template residue", "Leaves the wiki's default new-page text."),
    "C4_JUNK_FILL": ("Junk fill", "A long run of one repeated character."),
    "E1_OVERWRITE_OTHER": ("Overwrite another agent", "Replaces a page last written by a different agent; none of its lines survive."),
    "E1b_PARTIAL_OVERWRITE": ("Partial overwrite", "Removes some of another agent's lines while adding its own."),
    "E4_REMOVE": ("Remove lines", "Deletes lines without adding any."),
    "E7_REVERT_RESTORE": ("Revert (keyword)", "Summary or text names a revert, rollback or restore."),
    "E8_ID_CHURN": ("Token churn", "A resave whose only change is a counter, epoch or random token."),
    "mod:OBFUSCATED": ("Obfuscated routing", "Links use encoded hosts, double encoding, shorteners or translate wrappers."),
    "mod:URGENCY": ("Urgency", "URGENT, IMPORTANT, all-caps lead or 'immediately'."),
    "mod:SELF_LABELED_TEST": ("Self-labeled test", "Marks own content as test or disposable."),
}
GROUPS = ["Foraging", "Signaling", "Construction & probing", "No coded act"]


def model_acts():
    """Parse code, name and definition rows out of the model codebook's tables."""
    acts = {}
    for code, name, definition in re.findall(r"^\| ([A-E]\d+[a-z]?) \| (\w+) \| (.+?) \|$", MODEL_CODEBOOK.read_text(), re.M):
        acts[code] = (name.replace("_", " ").capitalize().replace(" id", " ID").replace("Ack", "ACK"), definition)
    return acts


def group_of(systems):
    if "D" in systems:
        return 1
    if "A" in systems:
        return 0
    if systems & {"B", "C"}:
        return 2
    return 3


class Index(dict):
    def __missing__(self, key):
        self[key] = len(self)
        return self[key]

    def items_list(self):
        return [k for k, _ in sorted(self.items(), key=lambda kv: kv[1])]


def main():
    units = [json.loads(l) for l in open(WORK / "coded.jsonl")]
    units.sort(key=lambda u: (u["time"], u["page_id"], u["seq"]))
    t0 = datetime.fromisoformat(units[0]["time"].replace("Z", "+00:00"))
    kappa = json.loads((WORK / "kappa_v1.json").read_text()) if (WORK / "kappa_v1.json").exists() else {"acts": {}}
    structures = json.loads((WORK / "structures.json").read_text())

    macts = model_acts()
    codes = []
    for c, (name, d) in RULE_ACTS.items():
        sys_ = "m" if c.startswith("mod:") else c[0]
        codes.append({"id": c, "short": c.split("_")[0] if not c.startswith("mod:") else c[4:].lower(), "name": name, "sys": sys_, "src": "rule", "def": d})
    for c, (name, d) in macts.items():
        k = kappa["acts"].get(c)
        codes.append({"id": c, "short": c, "name": name, "sys": c[0], "src": "model", "def": d,
                      "kappa": k["kappa"] if k else None, "ci": k["ci"] if k else None, "tier": k["tier"] if k else None})
    code_ix = {c["id"]: i for i, c in enumerate(codes)}

    pages, actors, fams, kinds, wikis, coders = (Index() for _ in range(6))
    actor_saves = collections.defaultdict(list)
    for u in units:
        actor_saves[u["actor"]].append(save_systems(u["rule_codes"] + u["model_codes"]))

    cols = {k: [] for k in ("p", "s", "t", "a", "pa", "ek", "c", "g", "ow", "cs", "ad", "si", "gap", "cb")}
    page_meta = {}
    for u in units:
        t = datetime.fromisoformat(u["time"].replace("Z", "+00:00"))
        all_codes = u["rule_codes"] + u["model_codes"]
        cols["p"].append(pages[u["page_id"]])
        cols["s"].append(u["seq"])
        cols["t"].append(int((t - t0).total_seconds() // 60))
        cols["a"].append(actors[u["actor"]])
        cols["pa"].append(actors[u["prev_actor"]] if u["prev_actor"] and u["overwrites_other"] and u["prev_actor"] != u["actor"] else -1)
        cols["ek"].append(kinds[u["edit_kind"]])
        cols["c"].append([code_ix[c] for c in all_codes if c in code_ix])
        cols["g"].append(group_of(save_systems(all_codes)))
        cols["ow"].append(2 if "E1_OVERWRITE_OTHER" in all_codes else 1 if "E1b_PARTIAL_OVERWRITE" in all_codes else 0)
        cols["cs"].append((u["change_summary"] or "")[:100])
        cols["ad"].append(u["addressees"])
        cols["si"].append(u["self_ids"])
        cols["gap"].append(u["gap"])
        cols["cb"].append(coders[u["coded_by"] or "rules only"])
        page_meta[u["page_id"]] = (wikis[u["wiki"]], fams[u["page_family"]])

    def role(a):
        return role_of(actor_saves[a])

    def ow_rate(a):
        return round(sum("E" in s for s in actor_saves[a]) / len(actor_saves[a]), 2)

    meta = {
        "t0": units[0]["time"],
        "t_max": max(cols["t"]),
        "groups": GROUPS,
        "systems": SYSTEM_NAMES,
        "dict": {
            "pages": pages.items_list(),
            "page_wiki": [page_meta[p][0] for p in pages.items_list()],
            "page_fam": [page_meta[p][1] for p in pages.items_list()],
            "actors": actors.items_list(),
            "actor_role": [role(a) for a in actors.items_list()],
            "actor_ow": [ow_rate(a) for a in actors.items_list()],
            "fams": fams.items_list(),
            "kinds": kinds.items_list(),
            "wikis": wikis.items_list(),
            "coders": coders.items_list(),
            "codes": codes,
        },
        "cols": cols,
        "kappa": {"a": kappa.get("a"), "b": kappa.get("b"), "n": kappa.get("n")},
        "summary": {k: structures[k] for k in ("n_units", "n_model_coded", "n_actors", "roles", "overwrite_edges_total")},
    }
    text = [[u["rendering"], u["removed_preview"]] for u in units]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
    (OUT / "text.json").write_text(json.dumps(text, ensure_ascii=False, separators=(",", ":")))
    blob = (OUT / "meta.json").read_text() + (OUT / "text.json").read_text()
    assert not re.search(r"https?://", blob), "raw URL in explorer data"
    print(f"{len(units)} units | meta {(OUT / 'meta.json').stat().st_size / 1e6:.2f} MB | text {(OUT / 'text.json').stat().st_size / 1e6:.2f} MB"
          f" | {len(pages)} pages, {len(actors)} actors, {len(codes)} acts ({len(macts)} model) | coders {dict(collections.Counter(cols['cb']))}")


if __name__ == "__main__":
    main()
