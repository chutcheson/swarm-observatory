# Design bible: "Notes for the Ones Behind"

A ~3:00 explainer in the style of 3Blue1Brown, made with manim CE 0.21. Thesis: if labs trained
models in groups and rewarded the group (multi-agent RL), cooperation becomes a habit that ships
with the model. We look for its fossils in a wiki where parallel AI agent runs left notes for
each other, and characterize each protocol by the **meta-problem** it solves.

Narration: `script/narration.py` (single source of truth). Clips: `audio/beats/*.wav` (Kokoro
af_heart, speed 1.1, tempo 1.05) with word timestamps in `audio/beats/manifest.json`. Quotes and sources:
`research/quotes.md`. **Every on-screen agent message must be verbatim from that file** (you may
show an excerpt, marked with "…"). Never show URLs or counter endpoints.

## Look

- Background `BG` near-black, flat. No paper texture. Lots of negative space.
- Type: CMU Serif (`tx()`), the 3b1b face, for titles, labels, math-like annotations; italics for
  asides and labels. JetBrains Mono (`mono()`, `mono_para()`) only for agent messages, tokens and
  handles. Math with `MathTex` (LaTeX is installed).
- Colour carries meaning. Each meta-problem owns one hue (see `PROBLEMS` in `swarm/style.py`):
  1 Pooling `C_POOL` blue · 2 Common time `C_TIME` yellow · 3 Compression `C_CHAN` teal ·
  4 Mortality `C_MORT` red · 5 Trust `C_TRUST` purple · 6 Discovery `C_DISC` green.
  Reward / the hypothesis is `C_REWARD` gold. Agent runs are soft white `glow_dot()`s (`RUN`).
  Text `INK`, secondary `INK_2`, labels `DIM`, rules and empty slots `FAINT`.
- Motion: 3b1b grammar. `Write`/`Create` for diagrams, `FadeIn(shift=...)` for text,
  `TransformMatchingShapes`/`ReplacementTransform` to show one thing becoming another,
  `Indicate`/`Circumscribe`/`Flash` sparingly for emphasis, `LaggedStart` for groups. Smooth
  rate functions; nothing bouncy. Keep ~0.3 s of stillness after a key reveal.
- One idea on screen at a time. Clear the frame between ideas (`FadeOut`). Nothing overlaps;
  keep 0.4 units from the frame edge (frame is 14.22 x 8 units).
- Each problem scene (s03–s08) opens by writing `problem_header(n)` top-left and keeps it there.
- Every scene ends on a clean exit: fade everything out in the last ~0.4 s of its last beat, so
  scenes can be cut together.

## Library (`from swarm import *`)

`SwarmScene` with `with self.beat("s03_b1") as b:` → plays that clip; `b.wait_word("token")`
waits until the narrator reaches a word; `b.until_word("token")` returns seconds until it (use as
`run_time`); on exit it waits out the rest of the clip plus a 0.35 s pad. Overruns are printed
("animations overran narration") and must be fixed.

Components (`swarm/components.py`): `glow_dot`, `RunLanes` (parallel staggered runs against
shared time; `.tick(i,k)`, `.tick_x(i,k)`, `.y(i)`, `.point(i,x)`, `.seen(i,k,color)`),
`now_line`, `quote_card(text, sig, color, header=...)` (`.body`, `.sig`, `.bg`), `packet(label,
color)`, `counter_box(value, label, color)` (`.num` is an `Integer`), `wiki_page(title, lines)`,
`problem_card(n)`, `blank_card(n)`, `problem_grid()`, `problem_header(n)`, `problem_icon(n)`,
`timer_ring()` → `(ring, frac_tracker)`, `clock_face()`, `number_line_clock(label, ticks=...)`.
Do not edit `swarm/`; put any helper you need in your own scene file.

## Scenes (durations are the narration clips; the scene adds 0.35 s per beat)

### s00 Notes on a wiki (b1 9.9 s, b2 4.9 s) — built by the lead
b1: Real saves-per-day histogram (24 May–2 Jul 2026) assembles from falling dots; an `Integer`
counts to 14,591 on "fourteen thousand". On "notes from AI agents", a handful of dots lift out and
thin lines flick between them, then fade on "never meet".
b2: The s00 quote card types in: "When round #5 arrives, answer first…" with "answer first"
underlined yellow and "STATE5-XX" teal.

### s01 A working hypothesis (b1 7.2, b2 13.1, b3 5.8)
b1: smallcaps "WORKING HYPOTHESIS". A rounded box labelled *training* holds four agent dots in a
ring. On "rewarded the whole group", a gold "+1" token drops in and splits into four that land on
every dot.
b2: Two columns: *individual reward* `R_i = r_i` and *group reward* `R_i = \sum_j r_j`. Under
each, an act of helping: a red bar −c (cost to the helper) appears in both; a blue bar +b (benefit
to the other) appears in both, but only counts on the right (left: greyed, crossed). Net: left
−c, right b − c > 0 ("helping pays" in gold, on "pays"). On "habit that ships with the model":
one dot leaves the training box, crosses a vertical dashed boundary labelled *deployment*, keeping
a faint gold halo.
b3: In the deployed space, the discovery icon (magnifier) drifts over dim dots; then centred
serif italic: "What problem does it solve?"

### s02 Scouts and the ones behind (b1 7.4, b2 9.4)
b1: `RunLanes` with five runs (Feb23, Nov01, Dec17, Apr10, Sep13), staggered starts, appear lane
by lane on "many copies". On "own simulated clock", small `clock_face`s beside each label, hands
at different angles. A thin axis label under the lanes: *shared time →*.
b2: A `now_line` sweeps right; round markers light (`seen`) as it passes. Freeze where Feb23 has
seen R3 and the others have not. On "scout", Feb23's R3 marker flashes blue and curved arrows run
from it down to the R3 markers of the runs behind (which are still ahead of the now line). On
"six problems", lanes fade and six `blank_card`s appear in a 3×2 grid.

### s03 Pooling — who knows what? (b1 11.4)
Header 1. Three run dots, each inside a faint circle (private knowledge) holding a tiny mono label
of what it saw ("R2: Business", "R4: Visual & Perf. Arts", "R1: Education"). On "standard report",
three labelled slots appear: *question*, *answer*, *next due*; then the s03 quote card, with
"Visual & Performing Arts" boxed blue (question), "2,134" (answer), "Likely #5 Psychology" (what
comes next). On "one sensor network", the private circles dissolve and lines connect every dot to
a central wiki page and to each other; a soft pulse travels along them.

### s04 Common time — when is now? (b1 11.4, b2 4.9)
Header 2. Two `number_line_clock`s: *task clock* (top, yellow) and *shared clock* (bottom). Run A's
readings join with vertical mapping lines (same rate). On "fast-forward", run B's mapping lines
fan out: a short span of shared time maps onto a long span of task time; label from the ChatGPTAug11
quote: "~27m28 task time in ~1m27 shared". On "trade readings", the AgentOpenResearch excerpt
("my task clock now 22:24:30 … Wiki-local now ~00:14") flies in as a packet between two runs; then
the runs reorder by who is really ahead.
b2: An empty, dashed round slot with "?"; a stamp "NO-SHOW" lands in it; the OpenAIResearcherAug08
quote with "Even a no-show update helps." highlighted.

### s05 Compression — what fits in thirteen seconds? (b1 13.6)
Header 3. A `timer_ring` labelled 13 s depletes (≈2 s, illustrative). A paragraph of grey prose
(a long report) squeezes into "COUNTRY FIRST" (from the CVD quote) and then into a `packet`
"STATE5-NH". On "gender and year into a single number": `MathTex` CODE = 2 + 2(year − 2014) + sex,
sex = 0 female, 1 male; worked example F 2017 → 2 + 2·3 + 0 = 8, marked on a number line 0–24;
small caption with the OpenAIMay31Maids excerpt.

### s06 Mortality — what outlives the run? (b1 8.9, b2 14.8)
Header 4. b1: One lane R1…R5. At R5 a red wall labelled *final answer*; beyond it the lane is a
fading dashed line. The run dot travels and stops at the wall, then dims on "ends the run".
b2: Two rows. Top, *answer → relay*: the dot answers (✓) then emits a packet that fizzles past the
wall (✗). Bottom, *signal → answer*: the packet leaves before the wall and reaches a
`counter_box` above; then the answer (✓). On "counters that outlive the run", the run fades but
the counter stays lit. On "courier", a small dot detaches before the wall and keeps moving past it
to drop its packet on a wiki page. Along the bottom, a compact 16 June timestrip from quotes.md:
10:23 answer first · 21:51 signal FIRST · 22:01 counter · 22:03 courier.

### s07 Trust — is the signal real? (b1 11.3)
Header 5. A `counter_box` "MD5" at 1. A burst of extra counters (HI5 MT5 IA5 WV5 ID5) pops up
within a beat: label *noise*. On "reading a counter carelessly", an eye (problem_icon 5) looks at
one counter and it ticks 1→2 with a red flash, label "/up". On "flag noise, own their mistakes":
the COUNTER NOISE excerpt (22:42), then the CLARIFY reply (22:43) with "Sorry for noise." —
one minute apart. On "read only": the April11OECDScout line, large: "Observers please READ only,
never /up."

### s08 Discovery — what are the rules? (b1 13.7)
Header 6. A run's last answer, then silence: "?" beyond it, with two hypotheses branching: *ends
at the final answer* / *ends on a timer*. On "experiments with controls": a three-way tree for
silence (*never launched* / *ended at answer* / *ended at deadline*) and two markers (launch, then
after the 65 s deadline) that split it; excerpt of the CashierCoordJun09OAI line. On "proof": a
timeline Q1 12:40:35 → R5 window ends 14:55:34 and Q1 + 2h15m = 14:55:35; zoom on the 1 s gap;
the HORIZON PROOF quote.

### s09 The fingerprint (b1 9.8, b2 8.9)
b1: The two order chips from s06 (answer → relay, signal → answer). A 13 s `timer_ring` split into
a red *signal* slice and the rest *answer*: the slice eats the agent's own answer time. Under
`R_i = r_i`, the value of signaling to the signaller is a red bar −c.
b2: Swap to `R_i = \sum_j r_j`: blue bars rise on the waiting runs; net b − c in gold. On "argued
over that trade, out loud": two quote cards facing each other with "vs": the AgentNov11OAI line
("…FIRST, then answer within 13s.") and "Do not risk the answer for signaling." (OpenAIFeb28Watcher).

### s10 Six meta-problems (b1 8.6, b2 11.0, then a 3 s end card)
b1: The six `problem_card`s appear one by one, each landing on its word (Pooling, common time,
compression, mortality, trust, discovery). Then a title above: "Six meta-problems" and below in
italics: "that any group rewarded together must solve".
b2: Under the grid, three small caveats appear in turn: "proposed ≠ used", "helpfulness is an
alternative", "next: tell them apart". On "kept solving them", the grid dims and a field of agent
dots with flickering message lines fills the frame. End card (after the clip): "Notes for the Ones
Behind" in serif, "Swarm Observatory" in smallcaps, and a credits line: "Data: Nightingale wiki
archive, June 2026 · quotes verbatim, handles self-chosen".

## Workflow for a scene builder

1. Read this file, `script/narration.py`, `research/quotes.md`, and `swarm/` (components.py,
   style.py, scene.py). Look at `scenes/s00_cold_open.py` as the reference for idiom.
2. Write `scenes/sNN_<name>.py` with exactly one class `SNN<Name>(SwarmScene)`. The first lines:
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
   from swarm import *
   ```
3. Preview at 720p into your own media dir (never the shared `media/`):
   `cd video && .venv/bin/manim -qm --media_dir build/preview_<you> scenes/sNN_x.py SNNX`
   Then a contact sheet: `.venv/bin/python tools/contact.py <mp4> build/qa/sNN.png --every 1`
   and Read the PNG. Check: no overlaps or clipped text, nothing off-frame, quotes verbatim,
   animations land on their words, no "overran narration" warnings in the log.
4. Iterate until it is clean and beautiful. Report the file, duration, and anything you could not
   resolve.
