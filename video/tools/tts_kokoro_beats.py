#!/usr/bin/env python3
"""Render narration beats with Kokoro (runs inside the c3-kokoro container on the Spark).

Input: JSON list of {"id", "tts"}; output: <id>.wav (24 kHz mono PCM16) per beat,
plus manifest.json with durations and word timestamps (for subtitles).
Unchanged beats (same text hash + voice + speed) are skipped on re-runs.
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import soundfile as sf
from kokoro import KPipeline

SR = 24_000

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("beats", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--speed", type=float, default=0.95)
    ap.add_argument("--gap", type=float, default=0.22, help="silence between chunks (s)")
    a = ap.parse_args()
    rows = json.loads(a.beats.read_text(encoding="utf-8"))
    a.out.mkdir(parents=True, exist_ok=True)
    man_path = a.out / "manifest.json"
    old = {}
    if man_path.exists():
        old = {r["id"]: r for r in json.loads(man_path.read_text())["beats"]}
    pipe = KPipeline(lang_code="a")
    gap = np.zeros(int(SR * a.gap), dtype=np.float32)
    out_rows = []
    for row in rows:
        bid, text = row["id"], row["tts"].strip()
        key = hashlib.sha256(f"{text}|{a.voice}|{a.speed}|{a.gap}".encode()).hexdigest()
        wav = a.out / f"{bid}.wav"
        if bid in old and old[bid].get("key") == key and wav.exists():
            out_rows.append(old[bid]); print("skip", bid, flush=True); continue
        chunks, words, t0 = [], [], 0.0
        for res in pipe(text, voice=a.voice, speed=a.speed, split_pattern=r"\n+"):
            audio = np.asarray(res.audio, dtype=np.float32).reshape(-1)
            if not audio.size:
                continue
            if chunks:
                chunks.append(gap); t0 += a.gap
            for tok in (res.tokens or []):
                if tok.start_ts is None or tok.end_ts is None:
                    continue
                words.append({"w": tok.text, "ws": tok.whitespace, "s": round(t0 + tok.start_ts, 3), "e": round(t0 + tok.end_ts, 3)})
            chunks.append(audio); t0 += audio.size / SR
        samples = np.concatenate(chunks)
        sf.write(wav, samples, SR, subtype="PCM_16")
        r = {"id": bid, "file": wav.name, "samples": int(samples.size), "duration": round(samples.size / SR, 4),
             "key": key, "voice": a.voice, "speed": a.speed, "words": words}
        out_rows.append(r)
        print(f"{bid} {r['duration']:.2f}s words={len(words)}", flush=True)
    man_path.write_text(json.dumps({"sr": SR, "beats": out_rows}, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
