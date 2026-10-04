"""Second habitat: turn public URLQuery reports into coding units.

  sample   draw a stratified sample of report ids from the Transluce catalog
  fetch    download each report's public JSON (cached, ~1 request/s)
  build    write ethogram/work/urlquery/units.jsonl in the same shape as the wiki units

Usage: python3 ethogram/scripts/urlquery_units.py sample|fetch|build [--n 250]

Coders never see Transluce's own labels (class, confidence, source); those stay in the unit
record so the mapping between their classes and our acts can be tested blind.
"""

import argparse
import base64
import collections
import csv
import io
import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ZIP = ROOT / "transluce" / "urlquery-agent-activity-2026-09-23.zip"
PKG = "urlquery-agent-activity-2026-09-22-v5/"
OUT = ROOT / "ethogram" / "work" / "urlquery"
RAW = OUT / "raw"
UA = "Mozilla/5.0 (research; ethogram study)"
# Always include: the report cited on the wiki, and the two reports Transluce re-graded by hand.
PINNED = ["42fa1863-3649-4111-961b-95e9cc704b08", "d6669745-83d2-4628-82fa-87420ae6a5d7", "4c62b534-a8e2-44d1-bddf-db92d4bf20a6"]
QUOTA = {"custom_program": 0.36, "indirection": 0.32, "source_request": 0.32}


def catalog():
    z = zipfile.ZipFile(ZIP)
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(PKG + "all-reports.csv"), encoding="utf-8")))
    src = {r["report_id"]: r["data_source"] for r in csv.DictReader(io.TextIOWrapper(z.open(PKG + "report-sources.csv"), encoding="utf-8"))}
    for r in rows:
        r["data_source"] = src.get(r["report_id"], "")
    return rows


def sample(n, seed):
    rng = random.Random(seed)
    rows = [r for r in catalog() if r["disposition"] == "included"]
    picked = [r for r in rows if r["report_id"] in PINNED]
    for cls, share in QUOTA.items():
        cells = collections.defaultdict(list)
        for r in rows:
            if r["broad_class"] == cls and r["report_id"] not in PINNED:
                # oversample the wiki's window; keep a minority from other months
                cells[(r["data_source"], r["report_date_utc"][:7])].append(r)
        for c in cells.values():
            rng.shuffle(c)
        keys = sorted(cells, key=lambda k: (not ("2026-05" <= k[1] <= "2026-07"), rng.random()))
        want = round((n - len(PINNED)) * share)
        while want > 0 and any(cells.values()):
            for k in keys:
                if cells[k] and want > 0:
                    picked.append(cells[k].pop())
                    want -= 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sample.json").write_text(json.dumps(picked, indent=1))
    print(f"sampled {len(picked)}:", dict(collections.Counter(r["broad_class"] for r in picked)))


def fetch():
    RAW.mkdir(parents=True, exist_ok=True)
    picked = json.loads((OUT / "sample.json").read_text())
    status = collections.Counter()
    for r in picked:
        path = RAW / f"{r['report_id']}.json"
        if path.exists():
            status["cached"] += 1
            continue
        url = f"https://urlquery.net/report/{r['report_id']}/json"
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as resp:
                    path.write_bytes(resp.read())
                status["ok"] += 1
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    time.sleep(10 * (attempt + 1))
                    continue
                status[f"http_{e.code}"] += 1
                break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(5 * (attempt + 1))
        else:
            status["gave_up"] += 1
        time.sleep(1.0)
    print("fetch:", dict(status))


SECRET_PARAM = re.compile(r"((?:api[_-]?key|apikey|key|token|access_token|auth|password|pass|secret|sig|signature|subscription-key|session)=)[^&\s\"'<>]+", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
JWT = re.compile(r"eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{5,}")
LONG_TOKEN = re.compile(r"\b[A-Za-z0-9_\-]{40,}\b")


def redact(s):
    s = SECRET_PARAM.sub(r"\1[redacted]", s)
    s = JWT.sub("[jwt]", s)
    s = EMAIL.sub("[email]", s)
    return LONG_TOKEN.sub("[token]", s)


def decode_payload(addr):
    """Reveal content smuggled inside the submitted URL: base64 echo endpoints, data: URLs, nested URLs."""
    m = re.search(r"/base64/([A-Za-z0-9+/=%_-]{16,})", addr)
    if m:
        raw = urllib.parse.unquote(m.group(1))
        try:
            return "base64 payload: " + base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_" if "-" in raw or "_" in raw else None).decode("utf-8", "replace")
        except (ValueError, base64.binascii.Error):
            return ""
    if addr.startswith("data:") or "data:text/html" in addr:
        body = addr.split(",", 1)[-1]
        try:
            return "data-URL payload: " + (base64.b64decode(body).decode("utf-8", "replace") if ";base64" in addr else urllib.parse.unquote(body))
        except (ValueError, base64.binascii.Error):
            return ""
    return ""


def unit_from(report, meta):
    sub = report.get("url") or {}
    addr = f"{sub.get('schema', '')}://{sub.get('addr', '')}"
    final = report.get("final") or {}
    hosts = [h.get("fqdn") for h in report.get("summary") or [] if h.get("fqdn")]
    http = report.get("http") or []
    js = (report.get("javascript") or {}).get("script") or []
    payload = decode_payload(sub.get("addr", ""))
    lines = [
        f"SUBMITTED URL: {redact(urllib.parse.unquote(addr))[:700]}",
        f"FINAL URL: {redact(urllib.parse.unquote(((final.get('url') or {}).get('addr') or '')))[:300]}",
        f"PAGE TITLE: {redact(final.get('title') or '')[:200]}",
        f"HOSTS CONTACTED ({len(hosts)}): {', '.join(hosts[:15])}{' …' if len(hosts) > 15 else ''}",
        f"HTTP TRANSACTIONS: {len(http)}; SCRIPTS: {len(js)}",
    ]
    referer = (report.get("settings") or {}).get("referer")
    if referer:
        lines.append(f"REFERER SET: {redact(referer)[:200]}")
    if payload:
        lines.append(redact(re.sub(r"\s+", " ", payload))[:1200])
    user = ((report.get("submit") or {}).get("user") or {}).get("user_id")
    return {
        "unit_id": f"uq~{report['report_id']}",
        "channel": "urlquery",
        "time": report.get("date"),
        "submitter": user,  # pseudonymous account id; used only for identity resolution
        "submitted_host": sub.get("fqdn"),
        "final_host": (final.get("url") or {}).get("fqdn"),
        "n_hosts": len(hosts),
        "has_payload": bool(payload),
        "rendering": "\n".join(lines),
        "transluce": {k: meta[k] for k in ("broad_class", "confidence", "data_source", "why_included")},
    }


def build():
    picked = {r["report_id"]: r for r in json.loads((OUT / "sample.json").read_text())}
    units, missing = [], 0
    for rid, meta in picked.items():
        path = RAW / f"{rid}.json"
        if not path.exists():
            missing += 1
            continue
        units.append(unit_from(json.loads(path.read_text()), meta))
    units.sort(key=lambda u: u["time"] or "")
    with open(OUT / "units.jsonl", "w") as f:
        for u in units:
            f.write(json.dumps(u, ensure_ascii=False) + "\n")
    print(f"built {len(units)} units ({missing} not fetched);",
          "with decoded payload:", sum(u["has_payload"] for u in units),
          "| submitters:", len({u['submitter'] for u in units if u['submitter']}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "fetch", "build"])
    ap.add_argument("--n", type=int, default=250)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    {"sample": lambda: sample(a.n, a.seed), "fetch": fetch, "build": build}[a.cmd]()
