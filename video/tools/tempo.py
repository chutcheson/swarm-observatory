#!/usr/bin/env python3
"""Speed up every narration clip by a pitch-preserving factor (ffmpeg atempo) and
scale the manifest's durations and word timestamps to match.

  tools/tempo.py 1.05
Run once after TTS; records the factor in manifest.json ("tempo") and refuses to
apply twice.
"""
import json, subprocess, sys
from pathlib import Path
import soundfile as sf
ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "audio" / "beats"
f = float(sys.argv[1])
man = json.loads((B / "manifest.json").read_text())
if man.get("tempo"):
    sys.exit(f"already tempo-adjusted ({man['tempo']}); re-run TTS first")
for r in man["beats"]:
    wav = B / r["file"]
    tmp = wav.with_suffix(".tmp.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af", f"atempo={f}", "-ar", "24000",
                    "-ac", "1", "-c:a", "pcm_s16le", str(tmp)], check=True)
    tmp.replace(wav)
    x, sr = sf.read(wav)
    r["samples"] = int(len(x))
    r["duration"] = round(len(x) / sr, 4)
    for w in r.get("words", []):
        w["s"] = round(w["s"] / f, 3)
        w["e"] = round(w["e"] / f, 3)
man["tempo"] = f
(B / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1))
print("speech", round(sum(r["duration"] for r in man["beats"]), 1), "s at tempo", f)
