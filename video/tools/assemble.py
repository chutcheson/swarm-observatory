#!/usr/bin/env python3
"""Assemble the film from rendered scenes.

  tools/assemble.py --scenes build/scenes_h60.json --out build/notes_for_the_ones_behind.mp4

1. Concatenate scene videos (video only, stream copy).
2. Build a 48 kHz narration track by placing every beat clip at
   scene offset + beat start (from build/timing/<Class>.json, written by the render).
3. Optionally lay a music bed under it (cue plan below), ducked under speech.
4. Loudness-normalize (two-pass loudnorm, -16 LUFS / -1.5 dBTP), mux, add soft subtitles.
Also writes <out>.srt and <out>.chapters.txt.
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "script"))
from narration import SCENES  # noqa: E402

SR = 48000
CHAPTER_TITLES = {s["id"]: s["title"] for s in SCENES}
TEXT = {b["id"]: b["text"] for s in SCENES for b in s["beats"]}


def dur(path):
    return float(json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]))["format"]["duration"])


def resample(x, sr):
    """Polyphase resampling to 48 kHz (exact rational ratio, high quality)."""
    from math import gcd
    from scipy.signal import resample_poly
    if sr == SR:
        return x
    g = gcd(sr, SR)
    return resample_poly(x, SR // g, sr // g, axis=0).astype(np.float32)


def load_wav48(path):
    x, sr = sf.read(path, dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(1)
    return resample(x, sr)


def srt_time(t):
    t = max(0.0, t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}".replace(",1000", ",999")


def captions_for_beat(bid, t0, words, beat_dur, max_chars=84):
    """Split the canonical text into caption chunks timed by the TTS word stamps."""
    text = TEXT[bid]
    cw = re.findall(r"\S+", text)
    toks = [w for w in words if re.search(r"[A-Za-z0-9]", w["w"])]
    n = len(cw)

    def t_of(i, which="s"):
        if toks and len(toks) == n:
            return toks[i][which]
        # proportional fallback
        if toks:
            j = min(len(toks) - 1, int(round(i * (len(toks) - 1) / max(1, n - 1))))
            return toks[j][which]
        return beat_dur * (i + (1 if which == "e" else 0)) / max(1, n)
    def ends(w, pat):
        return re.search(pat, w) is not None
    SENT = r"[.?!]['\u201d\u2019\"]?$"
    CLAUSE = r"[,;:\u2014]$"
    chunks, cur = [], []
    for i, w in enumerate(cw):
        cur.append(i)
        clen = sum(len(cw[k]) + 1 for k in cur)
        nxt = len(cw[i + 1]) + 1 if i + 1 < n else 0
        if (ends(w, SENT) and clen >= 18) or (ends(w, CLAUSE) and clen >= 42):
            chunks.append(cur)
            cur = []
        elif clen + nxt > 84:
            # too long: back up to the last clause break, if it leaves a sensible head
            cut = None
            for j in range(len(cur) - 2, 0, -1):
                if ends(cw[cur[j]], CLAUSE) or ends(cw[cur[j]], SENT):
                    head = sum(len(cw[k]) + 1 for k in cur[: j + 1])
                    if head >= 16:
                        cut = j
                        break
            if cut is None:
                chunks.append(cur)
                cur = []
            else:
                chunks.append(cur[: cut + 1])
                cur = cur[cut + 1:]
    if cur:
        if chunks and sum(len(cw[k]) + 1 for k in cur) < 14:
            chunks[-1] += cur          # don't leave a tiny orphan caption
        else:
            chunks.append(cur)
    out = []
    for c in chunks:
        out.append((t0 + t_of(c[0], "s"), t0 + t_of(c[-1], "e") + 0.25, " ".join(cw[k] for k in c)))
    # no overlaps
    for i in range(len(out) - 1):
        if out[i][1] > out[i + 1][0] - 0.02:
            out[i] = (out[i][0], out[i + 1][0] - 0.02, out[i][2])
    return out


def wrap2(s, width=52):
    import textwrap
    lines = textwrap.wrap(s, width)
    if len(lines) <= 2:
        return "\n".join(lines)
    mid = len(s) // 2
    k = s.rfind(" ", 0, mid + 8)
    return s[:k] + "\n" + s[k + 1:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--music", action="store_true")
    ap.add_argument("--music_db", type=float, default=-17.0, help="music bed gain before ducking (dB)")
    a = ap.parse_args()
    scenes = json.loads(Path(a.scenes).read_text())
    bad = [s for s in scenes if not s["ok"]]
    if bad:
        sys.exit(f"failed scenes: {bad}")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    man = {r["id"]: r for r in json.loads((ROOT / "audio/beats/manifest.json").read_text())["beats"]}
    work = ROOT / "build" / "assemble"
    work.mkdir(parents=True, exist_ok=True)
    # ---- 1. video concat
    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{s['mp4']}'\n" for s in scenes))
    vid = work / "video.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-an", "-c", "copy",
                    str(vid)], check=True)
    total = dur(vid)
    # ---- 2. narration track + captions + chapters
    narr = np.zeros(int(total * SR) + SR, dtype=np.float32)
    caps, chapters = [], []
    off = 0.0
    for s in scenes:
        d = dur(s["mp4"])
        tl = json.loads((ROOT / "build" / "timing" / f"{s['cls']}.json").read_text())
        sid = s["file"][:3]
        chapters.append((off, CHAPTER_TITLES.get(sid, s["cls"])))
        for bt in tl["beats"]:
            bid = bt["beat"]
            clip = load_wav48(ROOT / "audio/beats" / man[bid]["file"])
            i0 = int(round((off + bt["start"]) * SR))
            narr[i0:i0 + len(clip)] += clip[: max(0, len(narr) - i0)]
            caps += captions_for_beat(bid, off + bt["start"], man[bid].get("words", []), man[bid]["duration"])
        off += d
    narr = narr[: int(round(total * SR))]          # exactly the video's length
    sf.write(work / "narration.wav", narr, SR, subtype="FLOAT")
    # subtitles
    srt = out.with_suffix(".srt")
    with open(srt, "w") as fh:
        for i, (t0, t1, txt) in enumerate(caps, 1):
            fh.write(f"{i}\n{srt_time(t0)} --> {srt_time(t1)}\n{wrap2(txt)}\n\n")
    with open(out.with_suffix(".chapters.txt"), "w") as fh:
        for t, name in chapters:
            m, s_ = divmod(int(t), 60)
            fh.write(f"{m:d}:{s_:02d} {name}\n")
    # ---- 3. music bed
    mix_in = work / "narration.wav"
    if a.music:
        bed = build_music_bed(scenes, total, work)
        if bed is not None:
            # duck the bed under the narration, then sum
            mixed = work / "mix.wav"
            subprocess.run([
                "ffmpeg", "-v", "error", "-y", "-i", str(work / "narration.wav"), "-i", str(bed), "-filter_complex",
                f"[1:a]aformat=channel_layouts=stereo,volume={a.music_db}dB[m];[0:a]aformat=channel_layouts=stereo,asplit=2[v][sc];"
                "[m][sc]sidechaincompress=threshold=0.03:ratio=4:attack=30:release=1000:makeup=1[md];"
                "[v][md]amix=inputs=2:normalize=0:duration=first[out]",
                "-map", "[out]", "-ar", str(SR), str(mixed)], check=True)
            mix_in = mixed
    # ---- 4. loudness (two pass) + mux
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(mix_in), "-af",
                           "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    js = json.loads(meas[meas.rfind("{"):meas.rfind("}") + 1])
    ln = (f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(vid), "-i", str(mix_in), "-i", str(srt),
                    "-map", "0:v", "-map", "1:a", "-map", "2:s", "-c:v", "copy",
                    "-af", ln + f",aresample={SR}", "-c:a", "aac", "-b:a", "256k", "-ac", "2",
                    "-c:s", "mov_text", "-metadata:s:s:0", "language=eng",
                    "-metadata", "title=Notes for the Ones Behind (Swarm Observatory)",
                    "-movflags", "+faststart", str(out)], check=True)
    print(f"wrote {out}  ({total/60:.2f} min), {len(caps)} captions, loudness in {js['input_i']} LUFS")


# --------------------------------------------------------------------------- music
MUSIC = ROOT / "music" / "bed.wav"


def build_music_bed(scenes, total, work):
    """Optional: loop music/bed.wav under the whole film (fade in/out). None if absent."""
    if not MUSIC.exists():
        print("no music/bed.wav; narration only")
        return None
    out = work / "bed.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", str(MUSIC), "-t", f"{total:.3f}",
                    "-af", f"afade=t=in:d=2,afade=t=out:st={max(0, total - 3):.3f}:d=3", "-ar", str(SR), str(out)],
                   check=True)
    return out


if __name__ == "__main__":
    main()
