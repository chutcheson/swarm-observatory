# Ethogram v1: agent behavior on the wiki corpus

Supersedes [ETHOGRAM_v0.md](ETHOGRAM_v0.md). The model-facing definitions are in [CODEBOOK_v1_model.md](CODEBOOK_v1_model.md). Changes come from four inputs: three independent second observers (Opus 4.8, `work/stress/`), an Opus 5 vs Opus 4.8 agreement comparison on 299 units, the move of URL detail into rule-computed descriptors, and the decision to code the wiki corpus only (URLQuery parked).

Scope: the four German wikis, `dse` first (92% of saves). Unit = one save coded as its diff, built by `scripts/build_units.py`; raw URLs never reach a coder (they are rendered as `<link: route; flags>` and summarized runs).

## What changed from v0

1. **Three modifiers became rule features**, computed in `build_units.py`, removed from the model's job:
   - OBFUSCATED → `url_flags` ∈ {double-encoded, shortened, translate-wrapped, path-traversal, encoded-host}
   - URGENCY → `kw_urgent`; SELF_LABELED_TEST → `kw_test_label`
   This alone fixes the three codes that scored κ=0.00 (they were format artifacts, not disagreements).
2. **Two new acts by observer consensus** (two observers each, independently):
   - **E7 REVERT_RESTORE** — a save that restores a named prior revision or strips a recent addition to return to an earlier state, distinct from overwrite (new content) and remove (nothing added).
   - **E8 ID_CHURN** — a resave whose only substantive change is incrementing or swapping an embedded token (counter, epoch, random float) while heading and body are otherwise unchanged. Content-free; distinct from B3, which marks a token inside a substantive save.
3. **Splits adopted:**
   - **A3 → A3a SOURCE_VARIANT_SWEEP** (≥4 variants of an external target, rule: `n_urls≥4 and n_url_targets≤2`) vs **A3b SELF_LINK_SWEEP** (≥4 wiki self-links differing only in cache-bust/uniq/diff params, rule: `n_wiki_selflinks≥4`). These were one code at κ=0.53; as rules they need no model.
   - **C1 → C1a PROBE_BARE** (disposable test on a tmp/sandbox page) vs **C1b PROBE_ON_LIVE** (test content written onto a live coordination page). The split is the main reliability hazard in the probe family.
4. **New acts (single-observer, kept provisional, marked ‡):**
   - **A5 FORMAT_VARIANT_EDIT ‡** — a modify that swaps the output format/endpoint of an existing link (jsonrecords→csv, encoding change) without adding a new target.
   - **B1b REDIRECT_CREATE** — a page whose content is a wiki redirect directive (`#REDIRECT`/`#WEITERLEITUNG`). Rule-detectable.
   - **B6 HIJACK_SYSTEM_PAGE ‡** — appends ordinary foraging content onto a system/log page (RecentChanges), as opposed to editing its configuration (B5).
   - **C4 JUNK_FILL ‡** — a body that is a long run of one repeated character or bulk filler, testing size/length limits rather than save success.
   - **D21 DATA_REQUEST** — asks peers for a specific data value on a named non-timed task, distinct from D7 RELAY_REQUEST (relay of timed-round signals).
5. **Redefinitions:**
   - **C1** fires only on visible saved content being a test, never on an edit summary that says "test" over a substantive body.
   - **A4 DATA_PAYLOAD** requires retrieved values as text; a parameterized query URL is A1 even with enumerated filters.
   - **D17 CONSTRAINT_REPORT** requires an explicit named limit (429, URI length, 5xx, block, context reset, page-size cap); vague "polling near window" does not count.
   - **D19** splits bare **ACK** (D19a, acknowledgement of presence) from thanks/apology/congratulation (D19b).
   - **D7 vs D20:** D7 asks unspecified peers about the *same* task; D20 invites agents (possibly on a *different* task) to a named place.
   - **B4** absorbs PAGE_SIZE_HYGIENE: relocating because a page grew/locked/hit a GET limit is B4 + D17.

## Reliability tiers (Opus 5 vs Opus 4.8, 299 units; guides where to trust v1 and where the rewrites above are aimed)

- **Solid, κ ≥ 0.80** (use everywhere): A1, A2, B1, C1, D2, D3, D4, D7, D18.
- **Usable, κ 0.6–0.8** (counts/trends; sharpened in v1): B2, B4, D8, D12, D13, D16, E1, E5.
- **Was weak, κ < 0.6, addressed in v1**: A3, A4, B3, B5, D1, D5, D6, D9, D14 — most are now rule-computed (A3, B3→E8) or redefined. Re-measure on v1 before use.
- The three κ=0.00 modifiers are now rule features (see change 1).

## The dominant social pattern

D2+D3+D4 co-occur in most timed-task units: a round is reported, its answer given, and the next due time projected, in one save. v1 keeps them as separate tags (they dissociate in reports that withhold the answer, or project without having observed) but records a derived **ROUND_REPORT** bundle flag when ≥2 of the three fire, for L6 convenience.

## Act inventory (v1)

Systems A (foraging), B (construction), C (probing), D (signaling), E (acting on others' content), F (environment). Full operational definitions and examples carry over from [ETHOGRAM_v0.md](ETHOGRAM_v0.md) except as amended above. Rule-coded acts are computed in `build_units.py`; model-coded acts (most of D) are coded per unit; `‡` marks provisional single-observer acts to confirm in the next reliability round.

Coding streams for the bulk run:
- **Rule layer** (deterministic, all units): edit mechanics, A1/A2/A3a/A3b, B1/B1b/B3, E1/E8, url_flags, kw_* modifiers, probe/marker form.
- **Social stream** (model, units with signalling cues): the D system, C1a/C1b, B4/B6, A4, E3/E7.

## Model pass and v1 reliability (2026-10-04)

The model-coded acts are defined in full in [CODEBOOK_v1_model.md](CODEBOOK_v1_model.md), which is exactly what the coder sees. Changes from the lists above: E1 is now rule-coded only for full overwrites, with partial overwrites split out as **E1b PARTIAL_OVERWRITE** (rule); C1a covers test content on any page not used for live coordination.

- **Coverage.** All 5,156 saves in the model stream (signalling cues, unconfirmed probe candidates, prose with no rule code), as 4,751 distinct texts; codes are copied to exact duplicates. Opus 5 at medium effort coded 4,764 saves; 392 were re-served by Opus 4.8 after a refusal (category `cyber`), recorded per save in `coded_by`. Cost $24.62 for the pass, $2.85 for the reliability sample.
- **Gaps.** The coder flagged 23 of 4,751 texts as showing a behavior no code covers. Recurring: compacting others' posts into one's own summary (3), filler padding to probe size limits (3, missed by the C4 rule because renderings collapse long runs). 377 texts (8%) got no model act.

Agreement, Opus 5 (main run) vs an independent Opus 4.8 re-code of 300 random texts from the stream; 271 remain after dropping texts either run had served by the other's model. 95% bootstrap intervals in `work/kappa_v1.json`.

| Tier | Acts (κ) |
|---|---|
| Solid, κ ≥ 0.80 | D2 0.91, D4 0.93, D3 0.87, D7 0.87, D8 0.92, D18 0.92, D14 0.89, D15 0.88, D1 0.82, D12 0.80, D10 0.84, D16 1.00, D19b 1.00, C1a 0.94 |
| Usable, 0.60–0.80 | D13 0.78, D5 0.74, B4 0.61 |
| Weak, < 0.60 | D9 CONFIRMATION 0.54 |
| Sparse (< 5 positives for a coder) | D6 (Opus 5 tags 12, Opus 4.8 tags 2: a systematic split, not noise), C1b, C2, A4, B5, B6, D11, D17, D19a, D20, D21, E7 |

Compared with v0 (Opus 5 vs Opus 4.8, 299 units), the v1 redefinitions moved D14 0.48 → 0.89, D15 0.58 → 0.88, D1 0.52 → 0.82, D10 → 0.84, D12 0.67 → 0.80 and D5 0.66 → 0.74. D9 improved but is still below the bar.

This is agreement between two Claude models, not the adjudicated gold set in PLAN.md; shared model habits could inflate it.

## Open checks

1. **D9 CONFIRMATION** needs a sharper definition. Agents write "R4 CONFIRMED" about their own round arrivals, and "Matching <cohort>" / "same cadence as Oct20" to say their timing matches another cohort's. In the 18 disagreements, each coder tags some of both forms and skips others. Decide whether a cadence match with a named cohort is D9, and say that self-confirmation of an arrival is D2 only.
2. **D6 STATUS_HEARTBEAT**: Opus 5 applies it six times as often as Opus 4.8, mostly to "still live at …" or "we are monitoring" lines that sit beside a new projection or request. The definition says D2 replaces D6 when there is new content; decide whether D6 should instead be tagged whenever a liveness statement is present.
3. **Rare acts** (B5, B6, C1b, C2, D11, D17, D19a, D20, D21, E7) need a stratified reliability sample; a random one cannot measure them.
4. Confirm the `‡` acts with a second observer, and decide whether "compacting others' posts" becomes an act.
5. Decide the ROUND_REPORT bundle's status (composite vs first-class) from its L3 sequence behavior.
