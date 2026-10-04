#!/usr/bin/env python3
"""Render all scenes (in parallel) at a given quality, with narration audio.

  tools/render_all.py [--q h|k|m|l] [--fps 60] [--jobs 8] [--only s03,s11]
Outputs media/videos/<file>/<res>/<Class>.mp4 (manim's layout) and writes
build/scenes_<q>.json listing the files in film order.
"""
import argparse, json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
# manim CE 0.21 (pip install manim==0.21.0); override with $MANIM
MANIM = os.environ.get("MANIM", str(ROOT / ".venv/bin/manim"))
ap = argparse.ArgumentParser()
ap.add_argument("--q", default="h"); ap.add_argument("--fps", type=int, default=60)
ap.add_argument("--jobs", type=int, default=8); ap.add_argument("--only", default="")
a = ap.parse_args()
files = sorted((ROOT / "scenes").glob("s[0-9][0-9]_*.py"))
if a.only:
    keep = set(a.only.split(","))
    files = [f for f in files if f.name[:3] in keep]
jobs = []
for f in files:
    m = re.search(r"^class (S\d\d\w*)\(SwarmScene\)", f.read_text(), re.M)
    if m:
        jobs.append((f, m.group(1)))
res = {"l": "480p", "m": "720p", "h": "1080p", "k": "2160p"}[a.q]
def run(job):
    f, cls = job
    log = ROOT / "build" / "logs" / f"{f.stem}_{a.q}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    env = dict(os.environ); env.pop("SWARM_NO_AUDIO", None)
    cmd = [MANIM, f"-q{a.q}", "--fps", str(a.fps), "--disable_caching", str(f), cls]
    with open(log, "w") as fh:
        r = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env=env)
    out = ROOT / "media" / "videos" / f.stem / f"{res}{a.fps}" / f"{cls}.mp4"
    ok = r.returncode == 0 and out.exists()
    print(f"{'OK ' if ok else 'ERR'} {cls:22s} {time.time()-t0:7.1f}s  {out if ok else log}", flush=True)
    return (f.stem, cls, str(out), ok)
with ThreadPoolExecutor(a.jobs) as ex:
    results = list(ex.map(run, jobs))
man = ROOT / "build" / f"scenes_{a.q}{a.fps}.json"
# merge with any existing manifest so partial (--only) renders keep the full film list
prev = {r["file"]: r for r in json.loads(man.read_text())} if man.exists() else {}
for s_, c, p, ok in results:
    prev[s_] = {"file": s_, "cls": c, "mp4": p, "ok": ok}
man.write_text(json.dumps([prev[k] for k in sorted(prev)], indent=1))
print("wrote", man, "failures:", sum(not r[3] for r in results))
