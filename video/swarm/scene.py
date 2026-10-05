"""SwarmScene: a Scene paced by narration beats.

    with self.beat("s02_b1") as b:
        self.play(...)
        b.wait_word("trace")      # wait until the narrator reaches a word
        self.play(...)
    # on exit: waits out the rest of the clip (+ pad)

Durations and word timestamps come from audio/beats/manifest.json. If a
clip is missing, the duration is estimated from the script text.
"""
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

from manim import *  # noqa: F401,F403

from .style import AUDIO, BG, ROOT

sys.path.insert(0, str(ROOT / "script"))
from narration import SCENES  # noqa: E402

_TEXT = {b["id"]: b["text"] for s in SCENES for b in s["beats"]}
_MAN = {}
_mp = AUDIO / "manifest.json"
if _mp.exists():
    _MAN = {r["id"]: r for r in json.loads(_mp.read_text())["beats"]}

NO_AUDIO = os.environ.get("SWARM_NO_AUDIO") == "1"
TIMING_LOG = ROOT / "build" / "timing"


def _norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


class Beat:
    def __init__(self, scene, bid):
        self.scene = scene
        self.id = bid
        meta = _MAN.get(bid)
        self.meta = meta
        if meta:
            self.duration = meta["duration"]
            self.words = meta.get("words", [])
        else:
            n = len(re.findall(r"[A-Za-z0-9']+", _TEXT.get(bid, "")))
            self.duration = n / 2.45
            self.words = []
        self.t0 = scene.renderer.time

    @property
    def elapsed(self):
        return self.scene.renderer.time - self.t0

    def word_time(self, word, occurrence=1):
        """Start time (s, relative to the beat) of the n-th occurrence of `word`
        (matches by prefix, ignoring punctuation/case). Multi-word phrases match
        on their first word followed by the rest."""
        target = [_norm(w) for w in word.split()]
        ws = self.words
        seen = 0
        for i in range(len(ws)):
            ok = True
            for k, tw in enumerate(target):
                if i + k >= len(ws) or not _norm(ws[i + k]["w"]).startswith(tw):
                    ok = False
                    break
            if ok:
                seen += 1
                if seen == occurrence:
                    return ws[i]["s"]
        if not ws:
            # no timestamps: estimate from the text's word positions
            toks = re.findall(r"[A-Za-z0-9']+", _TEXT.get(self.id, ""))
            for i, t in enumerate(toks):
                if _norm(t).startswith(target[0]):
                    seen += 1
                    if seen == occurrence:
                        return self.duration * i / max(1, len(toks))
        print(f"[beat {self.id}] word not found: {word!r}", file=sys.stderr)
        return None

    def wait_until(self, t_rel, min_wait=0.0):
        dt = t_rel - self.elapsed
        if dt > 1 / 60:
            self.scene.wait(dt)
        elif min_wait > 0:
            self.scene.wait(min_wait)

    def wait_word(self, word, occurrence=1, lead=0.0):
        t = self.word_time(word, occurrence)
        if t is not None:
            self.wait_until(t - lead)

    def until_word(self, word, occurrence=1, lead=0.0, minimum=0.3):
        """Seconds from now until the word (for run_time of an animation)."""
        t = self.word_time(word, occurrence)
        if t is None:
            return minimum
        return max(minimum, t - lead - self.elapsed)

    def remaining(self, pad=0.0):
        return max(0.0, self.duration + pad - self.elapsed)


class SwarmScene(Scene):
    def setup(self):
        self.camera.background_color = BG
        self._timing = []

    @contextmanager
    def beat(self, bid, pad=0.3, audio_offset=0.0):
        b = Beat(self, bid)
        if b.meta and not NO_AUDIO:
            self.add_sound(str(AUDIO / b.meta["file"]), time_offset=audio_offset)
        yield b
        over = b.elapsed - (b.duration + pad)
        if over < -1 / 60:
            self.wait(-over)
        self._timing.append({"beat": bid, "start": round(b.t0, 3), "duration": b.duration,
                             "end": round(self.renderer.time, 3), "overrun": round(max(0, over), 3)})
        if over > 0.05:
            print(f"[beat {bid}] animations overran narration by {over:.2f}s", file=sys.stderr)

    def tear_down(self):
        try:
            TIMING_LOG.mkdir(parents=True, exist_ok=True)
            (TIMING_LOG / f"{type(self).__name__}.json").write_text(
                json.dumps({"scene": type(self).__name__, "total": round(self.renderer.time, 3),
                            "beats": self._timing}, indent=1))
        except Exception as e:  # pragma: no cover
            print("timing log failed:", e, file=sys.stderr)
