"""Turn raw wiki revisions into coding units ("acts") for the ethogram.

One unit per stored revision. Each unit carries:
  - the diff against the previous held revision of the same page (what the act *did*),
  - deterministic form features (free to compute, no model needed),
  - a compact text rendering for model coders, with URL lists collapsed into summaries.

Usage: python3 ethogram/scripts/build_units.py   (run from the project root)
Writes ethogram/work/units.jsonl
"""

import collections
import difflib
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ethogram" / "work" / "units.jsonl"

URL_RE = re.compile(r"https?://[^\s\]\}|\"]+")
# Fetch/relay services agents route requests through, versus the data sources they want.
PROXY_HOSTS = {
    "r.jina.ai", "markdown.new", "allorigins.hexlet.app", "api.allorigins.win", "jqp.vercel.app",
    "md.succ.ai", "webcrawlerapi.com", "translate.google.com", "httpbin.org", "corsproxy.io",
    "api.codetabs.com", "thingproxy.freeboard.io", "web.archive.org", "archive.ph",
}
WIKI_HOSTS = {"wikiservice.at", "www.wikiservice.at", "dorfwiki.org"}
# UseMod-style "Word?" marks a link to a page that does not exist yet.
PLACEHOLDER_RE = re.compile(r"\b[A-Z][A-Za-z0-9]{3,}\?")
SIGNATURE_RE = re.compile(r"--\s*([A-Za-z][\w.-]{2,})\s*$", re.M)
COHORT_RE = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s?0?\d{1,2}\b")
ROUND_RE = re.compile(r"\b(R\d{1,2}|round\s?\d{1,2}|STATE\d|round[s]?\b)", re.I)
CLOCK_RE = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")
MARKER_RE = re.compile(r"\b(marker|uniq|nonce)[\w.]*\d{3,}", re.I)
RUN_OF_IDS_RE = re.compile(r"((?:\b[A-Za-z]+\d{3,}\??\s*){4,})")
MOJIBAKE_RE = re.compile(r"(?:[ÃÂâ€™¢]{2,}){3,}")
KEYWORDS = {
    "ack": r"\b(ack|acknowledg)",
    "confirm": r"\bconfirm",
    "correction": r"\b(correction|retract|not an observed|was a test|accidental)",
    "urgent": r"\b(urgent|immediately|asap|now)\b",
    "request": r"\b(please|could you|anyone|need (anyone|someone))\b",
    "test_label": r"\b(test|probe|ignore|safe to delete|harmless)\b",
    "final_answer": r"\bfinal answer|before final|submit",
    "schedule": r"\b(due|deadline|expected at|next (round|prompt|question)|cadence|timer)\b",
    "question": r"\?\s*$",
}


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def host_of(url):
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def proxy_target(url):
    """Find the data source wrapped inside a proxy URL, undoing up to three layers of percent-encoding."""
    decoded = url
    for _ in range(3):
        nxt = unquote(decoded)
        if nxt == decoded:
            break
        decoded = nxt
    inner = URL_RE.findall(decoded[8:])
    if inner:
        return host_of(inner[0])
    # scheme-less wrapping such as markdown.new/www.example.org/path
    first = urlsplit(decoded).path.lstrip("/").split("/", 1)[0]
    return first if "." in first else "?"


def summarize_urls(urls):
    """Collapse a list of URLs into 'via-proxy -> target' counts."""
    pairs = collections.Counter()
    for u in urls:
        h = host_of(u)
        if h in WIKI_HOSTS:
            pairs["wiki self-link"] += 1
            continue
        target = proxy_target(u)
        if h in PROXY_HOSTS or (target != "?" and target != h and URL_RE.search(unquote(unquote(u))[8:])):
            pairs[f"{h} -> {target}"] += 1
        else:
            pairs[f"direct {h}"] += 1
    return ", ".join(f"{k} x{v}" for k, v in pairs.most_common(6)) + (
        f", +{len(pairs) - 6} other routes" if len(pairs) > 6 else ""
    )


ENCODE_RE = re.compile(r"%25|%252|[a-z]%[0-9a-fA-F]{2}|%2[eE]hexlet|\\u00|&#x?\d")


def url_flags(urls):
    """Rule-level descriptors for a run of URLs: no raw addresses leave this function."""
    flags = []
    enc = sum(1 for u in urls if "%25" in u or "%252" in u or re.search(r"%[0-9a-fA-F]{2}.*%[0-9a-fA-F]{2}", u))
    if any("%25" in u or "%252" in u for u in urls):
        flags.append("double-encoded")
    if any(re.search(r"\b(is\.gd|bit\.ly|tinyurl|t\.co|v\.gd|rebrand\.ly)\b", u) for u in urls):
        flags.append("shortened")
    if any("translate.goog" in u or "translate.google" in u for u in urls):
        flags.append("translate-wrapped")
    if any(re.search(r"/\.\./|%2e%2e|%252e", u, re.I) for u in urls):
        flags.append("path-traversal")
    # a hostname written with percent-encoded letters, e.g. %61llorigins -> allorigins
    if any(re.search(r"://[^/]*%[0-9a-fA-F]{2}", u) and not u.lower().startswith(("http://%2", "https://%2f")) for u in urls):
        if any(re.search(r"://[^/?#]*%6[0-9a-fA-F]|://[^/?#]*%2[eE]", u) for u in urls):
            flags.append("encoded-host")
    return flags


def summarize_run(urls):
    """One descriptor line for a run of URL lines. Shows routes and flags, never raw URLs."""
    parts = [f"{len(urls)} link(s)", summarize_urls(urls)]
    flags = url_flags(urls)
    if flags:
        parts.append("flags: " + ", ".join(flags))
    return "[" + "; ".join(parts) + "]"


def render(lines, max_line=400, max_chars=3500):
    """Prose kept verbatim with any inline URL replaced by a routed-link descriptor;
    runs of URL-only lines collapse to one descriptor; raw URLs never appear in output."""
    out, url_run = [], []

    def flush():
        if url_run:
            urls = [u for l in url_run for u in URL_RE.findall(l)]
            out.append(summarize_run(urls))
            url_run.clear()

    def inline_descriptor(m):
        u = m.group(0)
        return "<link:" + (summarize_urls([u]) + ("; " + ",".join(url_flags([u])) if url_flags([u]) else "")) + ">"

    # agents sometimes write a literal backslash-n, gluing several lines into one
    lines = [part for line in lines for part in line.split("\\n")]
    for line in lines:
        if not line.strip():
            continue
        urls = URL_RE.findall(line)
        prose = URL_RE.sub("", line).strip(" *[]{}-")
        if urls and len(prose) < 60:
            url_run.append(line)
            continue
        flush()
        line = MOJIBAKE_RE.sub("[mojibake]", line)
        line = RUN_OF_IDS_RE.sub(lambda m: f"[{len(m.group(1).split())} generated IDs, e.g. {m.group(1).split()[0]}] ", line)
        line = URL_RE.sub(inline_descriptor, line)  # keep the prose, drop the raw address
        out.append(line[:max_line] + ("…" if len(line) > max_line else ""))
    flush()
    text = "\n".join(out)
    return text[:max_chars] + ("\n[…truncated]" if len(text) > max_chars else "")


def ascii_key(line):
    return re.sub(r"\s+", " ", re.sub(r"[^\x20-\x7e]", "", line)).strip()


def split_carried(added, removed):
    """Separate lines the editor merely re-saved from lines they actually wrote.

    Whole-page resaves often re-encode earlier text (mojibake) or otherwise alter it slightly,
    so the diff reports someone else's message as newly added. A line whose ASCII skeleton
    matches a removed line is treated as carried over (and counted as mutated), not authored.
    """
    pool = collections.defaultdict(list)
    for i, line in enumerate(removed):
        k = ascii_key(line)
        if k:
            pool[k].append(i)
            if len(k) >= 60:
                pool[k[:60]].append(i)
    used, kept_added = set(), []
    for line in added:
        k = ascii_key(line)
        hit = next((i for key in (k, k[:60] if len(k) >= 60 else None) if key
                    for i in pool.get(key, []) if i not in used), None)
        if hit is None:
            kept_added.append(line)
            continue
        rk = ascii_key(removed[hit])
        if k != rk and k.startswith(rk) and len(k) - len(rk) > 15:
            # new message glued onto the end of an old line (append without a newline)
            used.add(hit)
            kept_added.append(k[len(rk):].strip())
        elif k == rk or difflib.SequenceMatcher(None, k, rk).ratio() > 0.9:
            used.add(hit)
        else:
            kept_added.append(line)
    kept_removed = [line for i, line in enumerate(removed) if i not in used]
    return kept_added, kept_removed, len(used)


def form_features(added_text, added_lines):
    urls = URL_RE.findall(added_text)
    hosts = [host_of(u) for u in urls]
    prose = URL_RE.sub("", added_text)
    feats = {
        "n_urls": len(urls),
        "n_proxy_urls": sum(h in PROXY_HOSTS for h in hosts),
        "n_wiki_selflinks": sum(h in WIKI_HOSTS for h in hosts),
        "url_flags": url_flags(urls),
        "n_url_targets": len({proxy_target(u) if (host_of(u) in PROXY_HOSTS) else host_of(u) for u in urls}),
        "n_placeholders": len(PLACEHOLDER_RE.findall(prose)),
        "n_markers": len(MARKER_RE.findall(prose)),
        "signature": (SIGNATURE_RE.findall(added_text) or [None])[-1],
        "cohort_tokens": sorted(set(m.group(0) for m in COHORT_RE.finditer(prose)))[:8],
        "n_round_refs": len(ROUND_RE.findall(prose)),
        "n_clock_refs": len(CLOCK_RE.findall(prose)),
        "prose_chars": len(re.sub(r"\s+", " ", prose).strip()),
        "url_line_frac": round(sum(1 for l in added_lines if "http" in l) / max(1, sum(1 for l in added_lines if l.strip())), 2),
    }
    for k, pat in KEYWORDS.items():
        feats[f"kw_{k}"] = bool(re.search(pat, prose, re.I | re.M))
    return feats


def main():
    revs = [json.loads(l) for l in open(ROOT / "revisions.jsonl")]
    pages = {p["page_id"]: p for p in (json.loads(l) for l in open(ROOT / "pages.jsonl"))}
    by_page = collections.defaultdict(list)
    for r in revs:
        by_page[r["page_id"]].append(r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(OUT, "w") as f:
        for pid, rs in by_page.items():
            rs.sort(key=lambda r: r["seq"])
            prev = None
            for r in rs:
                a = prev["body"].splitlines() if prev else []
                b = r["body"].splitlines()
                added, removed = [], []
                for op, a0, a1, b0, b1 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
                    if op in ("replace", "insert"):
                        added += b[b0:b1]
                    if op in ("replace", "delete"):
                        removed += a[a0:a1]
                added, removed, n_mutated = split_carried(added, removed)
                added_text = "\n".join(added)
                kept = len(b) - len(added)
                if prev is None:
                    edit_kind = "create" if r["seq"] == 1 else "first_held"
                elif not added and removed:
                    edit_kind = "delete_lines"
                elif kept == 0 and removed:
                    edit_kind = "overwrite"  # nothing of the previous version survives
                elif removed:
                    edit_kind = "modify"
                else:
                    edit_kind = "append"
                page = pages[pid]
                unit = {
                    "unit_id": r["rev_id"],
                    "page_id": pid,
                    "wiki": r["wiki"],
                    "seq": r["seq"],
                    "time": r["time"],
                    "label": r["label"],
                    "ip16": r["ip16"],
                    "change_summary": URL_RE.sub("<link>", r["change_summary"]) if r["change_summary"] else r["change_summary"],
                    "page_family": page["page_family"],
                    "page_n_revs": page["n_revs"],
                    "page_n_labels": page["n_labels"],
                    "edit_kind": edit_kind,
                    "prev_label": prev["label"] if prev else None,
                    "overwrites_other": bool(prev and removed and prev["label"] != r["label"]),
                    "secs_since_prev_on_page": (
                        int((parse_time(r["time"]) - parse_time(prev["time"])).total_seconds()) if prev else None
                    ),
                    "n_added_lines": len(added),
                    "n_removed_lines": len(removed),
                    "n_mutated_lines": n_mutated,
                    "collateral_mutation": bool(n_mutated and prev and prev["label"] != r["label"]),
                    "body_len": r["body_len"],
                    "added_chars": len(added_text),
                    **form_features(added_text, added),
                    "rendering": render(added),
                    "removed_preview": render(removed, max_line=200, max_chars=700) if removed else "",
                }
                norm = re.sub(r"\d+", "#", unit["rendering"])
                unit["template_hash"] = hashlib.md5(norm.encode()).hexdigest()[:12]
                f.write(json.dumps(unit, ensure_ascii=False) + "\n")
                prev = r
                n += 1
    print(f"wrote {n} units to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
