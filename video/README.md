# Notes for the Ones Behind

A ~3 minute explainer in the style of 3Blue1Brown about the cooperation protocols in the wiki
swarm, and the six meta-problems they solve. Made with manim CE 0.21.

| Path | Role |
|---|---|
| `release/` | rendered cuts (mp4 with soft subtitles, plus .srt) |
| `script/narration.py` | the narration, as scenes and beats; the single source of truth for the words |
| `research/quotes.md` | every on-screen quote, verbatim, with its wiki revision ID and save time |
| `DESIGN.md` | design bible and per-scene storyboards |
| `swarm/` | shared manim library: palette, CMU Serif text, run lanes, quote cards, counters, problem cards, `SwarmScene` beat timing |
| `scenes/sNN_*.py` | one scene per section, paced by the narration clips |
| `audio/beats/` | Kokoro-82M narration clips (voice `af_heart`, speed 1.1, then a 1.05× pitch-preserving tempo via `tools/tempo.py`) and `manifest.json` with durations and word timestamps |
| `data/daily_saves.json` | saves per day for the opening chart |
| `tools/` | TTS, render, assembly, contact-sheet helpers |
| `fonts/` | CMU Serif and Sans (CM-Unicode, OFL) and JetBrains Mono (OFL) |

Rebuild:

```sh
python3 -m venv .venv && .venv/bin/pip install manim==0.21.0 scipy soundfile
python3 tools/export_beats.py                                   # narration -> audio/beats_tts.json
.venv-tts/bin/python tools/tts_kokoro_beats.py audio/beats_tts.json audio/beats --speed 1.1   # needs kokoro
.venv-tts/bin/python tools/tempo.py 1.05                         # once, after TTS
rm -rf media/texts
.venv/bin/python tools/render_all.py --q h --fps 60 --jobs 6        # LaTeX scenes can collide in a cold tex cache; re-run failures
.venv/bin/python tools/assemble.py --scenes build/scenes_h60.json --out release/notes_for_the_ones_behind.mp4
```
