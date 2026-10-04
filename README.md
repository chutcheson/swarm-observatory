# Swarm Observatory

How do AI agents that never meet coordinate? This repository studies one swarm. In June 2026,
parallel runs of the same timed, multi-round data quiz wrote about 14,600 saves to four public
German wikis, and many of those saves were notes for one another. Runs that were ahead in their
own simulated clocks told the runs behind them which questions came next. Over a few days they
built protocols for doing that well.

We characterize each protocol by the **meta-problem** it solves: pooling, common time,
compression, mortality, trust and discovery. Our working hypothesis is that group-rewarded
multi-agent RL trains cooperation as a habit that ships with the model. These behaviours would be
its fossils.

| Start here | What it is |
|---|---|
| [META_PROBLEMS.md](META_PROBLEMS.md) | The argument: six meta-problems, the protocols that solve them, counts, the costly-signalling fingerprint, alternative explanations, and tests |
| [video/](video/) | *Notes for the Ones Behind*, a ~3 min 3Blue1Brown-style explainer (manim). The cut is in `video/release/` |
| [ethogram/](ethogram/) | Behavioural coding of every save (Claude): plan, codebook, rule and model coders, agreement, viewer |
| [observatory/](observatory/) | Source-grounded evidence pipeline (Codex, gpt-6-luna): packetization, extraction, review, protocol families. History preserved from the original repo |
| [findings/](findings/) | Exported results: the observatory's 10 protocol families, 26 observations, and status counts |

## Data

The raw archives are **not included**. Download them from their publishers and check them
against the hashes here:

- **Nightingale wiki archive** (`revisions.jsonl`, `pages.jsonl`, `events.jsonl`,
  `labels.jsonl`, `manifest.json`; also packaged as `full-wiki-logs.zip`). It holds 14,591 held
  saves on 4,579 pages across `dse`, `probier`, `fractal` and `dorfwiki`, cut at write date
  ≥ 2026-05-01. Hashes are in `SHA256SUMS`. `manifest.json` (included) describes populations and
  counts.
- **Transluce URLQuery agent-activity catalog** (`transluce/urlquery-agent-activity-2026-09-23.zip`).
  It holds 38,160 report records with IDs, timestamps and labels, and no report bodies. Hashes and
  the download record are in `transluce/`.

Put the raw files in the repository root. Then rebuild the ethogram intermediates:

```sh
python3 ethogram/scripts/build_units.py      # ~3 s -> ethogram/work/units.jsonl
python3 ethogram/scripts/rule_code.py        # rule acts + structures
python3 ethogram/scripts/build_explorer.py   # viewer data; then serve ethogram/explorer/
```

The model passes (`ethogram/scripts/code_bulk.py`, `observatory/`) call the Anthropic and OpenAI
APIs. They read keys from local files at runtime, and no keys are stored here.

## Status and caveats

- **Two independent analyses agree on the protocol inventory.** The Claude ethogram coded all
  5,156 saves with signalling cues. The Codex observatory pipeline was stopped at 2,698 of 8,870
  windows (1,776 pages with results), so its counts are partial.
- **Agreement figures are model-vs-model** (Opus 5 vs Opus 4.8), not an adjudicated gold set.
  Shared model habits could inflate them.
- **A proposed protocol is not evidence of use.** For example, "signal before the final answer"
  is mostly proposed: 55 proposed, 7 accepted and 5 enacted in the observatory sample.
- **Handles are self-chosen labels, not verified identities**, and one run can use several.
- **Sensitive content.** The corpus includes access-circumvention techniques and answer-sharing
  between eval runs. We code these as behaviour and keep working payloads out of our outputs. Raw
  URLQuery captures and raw model logs are excluded from this repository.

## Layout

```
META_PROBLEMS.md            the argument
manifest.json, SHA256SUMS   Nightingale archive metadata and hashes (data not included)
transluce/                  URLQuery catalog download record and hashes (data not included)
ethogram/                   PLAN, ETHOGRAM v0/v1, model codebook, scripts, viewer, coded outputs
observatory/                Codex evidence pipeline (code, tests, docs, run scripts)
findings/                   exported observatory protocol families and observations
video/                      film source: narration, manim library and scenes, audio, research notes, release
```
