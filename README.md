# Swarm research pipeline

The repeatable local pipeline is implemented in `swarm_pipeline/`, with `pipeline.py` as its CLI. Start with [the operator guide](pipeline-docs/RUNBOOK.txt). The existing supervised research runs below remain frozen.

The default worker uses the OpenAI Responses API with `gpt-6-luna`, reading the key from `~/.keys/openai` at runtime. Requests have no tools, use strict output schemas and carry per-call output limits. The optional Codex CLI backend remains available; historical results keep their original configuration. Nothing runs in the background unless explicitly launched. The queue supports separate extraction, review, interpretation and summary jobs, exact evidence checks, context tickets, retries, leases, scoped invalidation and candidate export. Pipeline candidates do not overwrite the 360-case research release.

---

# Swarm research pilot

This directory contains the first supervised analysis run for the Swarm Observatory. The source archives remain unchanged in `~/Projects/swarm-communication`.

## What is complete versus queued

- `runs/pilot-v1/inventory.json` inventories all downloaded rows and their archive hashes.
- `corpus.sqlite` indexes the full Nightingale corpus and the deduplicated Transluce report catalog.
- `jobs` records queued full-corpus work separately from provisional pilot case results. A completed case window does not imply that its full page history was analyzed.
- `selection_manifest_*.json` records pilot sampling decisions, included source records, and omitted context.
- `results/analysis_*.json` contains Luna's case-level findings. `evidence_*.json` preserves the exact text used to support them.
- `results/independent_*.json` records a second model's independent checks. Model agreement is not a human-labelled accuracy benchmark.
- `publication_validation.json` rejects missing or non-exact citations before a frontend snapshot can be written.

## Execution

From this directory's parent:

```sh
python3 swarm-analysis/scripts/inventory.py
python3 swarm-analysis/scripts/register_jobs.py
python3 swarm-analysis/scripts/validate_pilot.py --results swarm-analysis/runs/pilot-v1/results --output swarm-analysis/runs/pilot-v1/results/qa_report.json
python3 swarm-analysis/scripts/assemble_pilot.py
```

The sampling scripts document their own inputs and selection rules. Semantic outputs were produced by supervised `gpt-6-luna` subagents with high reasoning in this Codex session, not by an unattended API service. The shared worker contract is in `WORKER_INSTRUCTIONS.md`. No API key, autonomous scheduler, or unattended full-corpus model runner is configured by these scripts.

Scripts that serialize the annotated findings reproduce this frozen model analysis; they do not invoke Luna or perform a new analysis. Preserve the run outputs alongside the sampling manifest. A fresh semantic pass requires new worker dispatch and review.

## Evidence and inference

A revision writer label is not authenticated authorship of everything in that revision. A quote may be carried forward from an earlier edit. Actor and addressee strings are stated identities; cross-case identity resolution remains provisional. The UI's addressed-exchange graph is case-scoped. Shared use of a convention is not proof of communication, common origin, or membership in a swarm.

Transluce's downloaded ZIP contains catalog metadata and report links, not the full report bodies. Rendered public report pages captured during the pilot are a separate evidence layer. Detection labels and inclusion rationales do not prove a successful exploit or identify an operator.

The pilot is purposive and enriched for useful test cases. It cannot estimate population prevalence. Citation validity is a mechanical check; semantic accuracy, missed events, protocol definitions, and group boundaries require further evaluation. Full-corpus dispatch should use the error analysis to revise packet construction and definitions before increasing coverage.

## Next supervised pass

1. Extract atomic contributions from revision differences, retaining the prior revision and enough surrounding conversation to interpret replies. Do not count carried-forward text as another message. Preserve explicit page-continuation links separately from inferred conversation continuity.
2. Resolve stated handles within a conversation first. Store proposed cross-page identity links with evidence and alternatives; do not merge identities from labels or shared infrastructure alone.
3. Review the enriched conversations for missed messages as well as unsupported claims. Keep disagreements and unknowns. Freeze the resulting extraction contract before scaling.
4. Dispatch bounded page-history packets from the full-corpus job table. Store each attempt and its input hash, validate citations and schema, and retry only failed or revised packets. Long pages require successive windows rather than only their last six revisions.
5. Acquire permitted Transluce report content in a separate evidence pass. Where only overview/catalog evidence is available, keep that limitation in the result and exclude it from agent-communication edges.
6. Cluster tasks, interaction communities, and protocol use as separate derived products. Compare alternative grouping rules rather than forcing one partition to mean all three. Generate linked short and long summaries from the accepted findings, then publish a new immutable dashboard snapshot.

## Expansion v2

`runs/expansion-v2` is a separate supervised run; `pilot-v1` remains frozen. Its contract distinguishes coordination function, dynamic role, and interaction protocol, then separates protocol family, task-specific variant, and cited episode. A proposed rule, a promise to follow it, and observed use are different states.

`prepare_expansion.py` freezes 72 Nightingale histories (24 revisited plus 48 new pages), with 1,614 available revisions. Selection deliberately favors active pages in several task neighborhoods, along with peripheral and no-coordination controls. Full histories are available to the workers as differences; the worker coverage fields state what was parsed, scanned, and semantically read. This is not exhaustive atomic event extraction or a representative prevalence sample. The Transluce worker maintains its own disjoint expansion selection and report captures.

`assemble_expansion.py` checks coverage, original revision text, exact quotations, original Transluce catalog fields, reproducible decoded text, and taxonomy references. `--publish` additionally requires a completed review record and writes the viewer snapshot. Quote validity is not semantic accuracy. The published viewer preserves the old pilot separately, and distinguishes unanalysed linked-page context from sampled cases.

The source manifests, worker instructions, actual Luna outputs, supervisor checks, and independent review belong together. Re-running serialization reconstructs a frozen result; it does not run a new semantic analysis. `orchestration.json` records the in-session worker assignments. No background execution is implied.
