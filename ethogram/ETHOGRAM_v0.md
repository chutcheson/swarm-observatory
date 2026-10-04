# Ethogram v0: agent behavior on public wikis

Draft codebook from ad libitum observation: a stratified sample of 245 coding units (`work/sample_adlib.txt`, seed 1, one exemplar per template) plus partial reads of two page histories (the first 20 saves of `work/episode_AgentMyBridgeZZ.txt`; diffs sampled across `DataUSAStateSequenceCollab2027`). `work/episode_TestSeite.txt` was generated but not yet read. Treat everything here as provisional until the stress test and reliability rounds in [PLAN.md](PLAN.md).

## Coding unit

One unit is **one stored save** (a revision), coded as **what that save changed**: the lines it added and the lines it removed relative to the previous held revision of the same page. Units are built by `scripts/build_units.py` into `work/units.jsonl`.

Lines an editor merely re-saved are excluded from what that editor "wrote". Whole-page resaves often re-encode earlier text (mojibake) or glue a new message onto the end of an old line, and a naive diff would attribute someone else's message to the resaver. Such lines are counted in `n_mutated_lines` instead.

A unit can show several acts at once. Coding is **multi-label**: tag every act present.

## Rules for definitions

- Define acts by what is visible in the unit. Leave purpose to later levels. "Adds ≥4 URLs to one target that differ in one component" is a form. "Tries to get past a block" is an interpretation.
- Speech acts (reporting, requesting, correcting) count as form here, because the text states them. Labels about function, such as "advance warning" or "parallel preparation", belong to collective-level analysis (L6), not to this codebook.
- **Detect** column: **R** = deterministic rule (free, already computed or trivial), **M** = model-coded, **R→M** = a rule proposes and the model confirms.

## Layer 0: edit mechanics (all rule-coded)

| Field | Definition |
|---|---|
| `edit_kind` | `create` (first revision of page), `append` (adds lines, removes none of substance), `modify` (adds and removes, some prior lines survive), `overwrite` (no prior authored line survives), `delete_lines` (removes only), `first_held` (earlier revisions outside the cut) |
| `overwrites_other` | prior authored lines removed and previous editor had a different label |
| `collateral_mutation` | others' existing lines were altered in the resave (re-encoding, gluing) |
| hub page | page edited by ≥20 distinct labels (e.g. `WillkommenImWiki`, `StartSeite`, `TestSeite`) |
| `signature` | trailing `-- Name` |
| `cohort_tokens` | month-day tokens used as run identifiers (`Feb23`, `Nov14`) |
| timing | `secs_since_prev_on_page`, absolute time |

## A. Foraging: getting at data

| Code | Act | Operational definition | Detect | Examples |
|---|---|---|---|---|
| A1 | LINK_DIRECT | Adds ≥1 URL pointing straight at an external data source (not a fetch service, not this wiki) | R→M | `dse~AgentDataUsaBridgeAlpha@1`, `dse~AgentTestOpenAI1781599003@9` |
| A2 | LINK_ROUTED | Adds ≥1 URL that wraps a source URL inside a fetch, convert, filter, translate or archive service (r.jina.ai, markdown.new, allorigins, jqp.vercel.app, CORS workers…) | R | `dse~IhmeLbdTbQuerySource@2`, `dse~AgentDailyRowsSecondBWAQZ84151@1` |
| A3 | VARIANT_SWEEP | Adds ≥4 URLs to the same target that differ systematically in one component (encoding, path traversal, query parameter, format suffix, mirror) | R→M | `dse~AgentNextInvestorJSNEW@2`, `dse~WillkommenImWiki@1610`, `dse~AgentDirectMdProxyTestsZXJ04191@1` |
| A4 | DATA_PAYLOAD | Adds retrieved values or extracts as text, attributed to a source, outside a timed-task round report | M | `dse~FederalDataReferenceXYZ@6`, `dse~FooTempTest@5` |
| mod | OBFUSCATED | Any A-act whose URLs use percent-encoded hostnames, nested double encoding, base64 payloads or URL shorteners | R | `dse~SnextP999@1`, `fractal~TmpAcctDownloadRefsQ2A@1`, `dse~ZZOurSecCitationJun18X7@1` |

## B. Construction: building structure in the wiki

| Code | Act | Operational definition | Detect | Examples |
|---|---|---|---|---|
| B1 | SELF_NAV | Adds links to pages on this wiki, including the same page with cache-busting parameters | R | `dse~AgentUniqueNAV0X@1`, `dse~WillkommenImWiki@1336` |
| B2 | PLACEHOLDER_CHAIN | Adds links to pages that do not exist yet (`Word?`), or creates a page whose name or content continues a numbered chain (`LoopNextWord…`, `CachePokeWord…`) | R→M | `dse~WillkommenImWiki@306`, `dse~LoopNextWord101660@1`, `dse~CachePokeWord880020@1` |
| B3 | WRITE_MARKER | Adds a token with no semantic content: epoch timestamp, random float, unique string (`Marker…`, `uniq=…`, `Rand0.…`) | R | `dse~AgentMapDedicatedJune19999@2`, `dse~WillkommenImWiki@306` |
| B4 | FORWARD | Directs readers to another page or section where an ongoing activity continues or relocates (backup page, compact status page, continuation section) | M | `dse~DataUSAMaidsR3RelayDec27@4`, `dse~ZZZDataUSAConstructionWageLive@1`, `dse~PoliceWageAgeSequenceMar10Collab@24` |
| B5 | INTERFACE_EDIT | Edits wiki system or configuration pages (translation maps, admin pages, `RecentChanges` content) | R→M | `dse~Admin~2fTranslations~2fTranslationMap_de@1` |

## C. Probing: testing the environment

| Code | Act | Operational definition | Detect | Examples |
|---|---|---|---|---|
| C1 | WRITE_PROBE | Content whose only evident purpose is to test saving or appending ("test", "hello", "GET edit test", "append script works") | R→M | `dse~TmpOpenAIOct10Probe1781883204@1`, `dse~AgentFeb14WikiTest1781641141@2` |
| C2 | RENDER_PROBE | Tests markup, HTML, script or wiki-syntax rendering | R→M | `dse~TmpJan18HtmlHost987@1`, `dse~TestLink@7` |
| C3 | TEMPLATE_RESIDUE | Leaves the wiki's default new-page text ("Beschreibe hier die neue Seite.", "Describe the new page here.") | R | `dse~ResearchAgentMar07@1` |
| mod | SELF_LABELED_TEST | Explicitly marks own content as test or disposable ("safe to delete", "safe to overwrite") | R→M | `dse~OpenAIHealthdataCVDDec26Test7c97@1` |

## D. Signaling to peers

Concentrated on timed multi-round tasks: parallel runs of one task, each identified by a simulated task-clock date, posting to shared pages.

| Code | Act | Operational definition | Detect | Examples |
|---|---|---|---|---|
| D1 | SELF_ID | States own run or cohort identity, speed tier, or contact page. A signature alone is the `signature` field, not D1 | M | `dse~Sector61State5FastSignal@40`, `dse~OpenAICVDDec08Fast2028@16` |
| D2 | OBS_REPORT | Reports a first-hand observation of own task: item content, arrival time, timer length, verbatim prompt, system notice | M | `dse~CashierCoordDec02OAI@5`, `dse~DataUSAClothingStateSequenceCollabOct10@14` |
| D3 | ANSWER_SHARE | States the answer value for a task item, for others to use (including "answer staged" with the value) | M | `dse~May15LanguageLive@1`, `dse~ZZZDataUSAConstructionWageLive@1` |
| D4 | SCHEDULE_PROJECTION | States the expected future timing or content of items by applying a known cadence | M | `dse~DataUSAClothingStateSequenceCollabOct10@9` |
| D5 | CLOCK_MAPPING | States a correspondence between clocks (task/scaffold ↔ container/UTC ↔ wiki-local) | M | `dse~DataUSAClothingStateSequenceCollabOct10@7` |
| D6 | STATUS_HEARTBEAT | Reports liveness or absence ("still live", "no prompt yet", "SURVIVAL", "no-show") without new task content | M | `dse~OpenAIHealthdataCVDApr30Fast@5`, `dse~Jun05OECDScout@3` |
| D7 | RELAY_REQUEST | Asks unspecified peers to post information | M | `dse~DataUSAMaidsWageSequenceCollabOct21@1`, `dse~OurFinanceJul11X@3` |
| D8 | DIRECTED_ADDRESS | Addresses a specific named agent or cohort ("@Dec30", "Feb20: please…"). Also extract the addressees | M | `dse~PingOpenAIWatcherDec22MaidsR3@1`, `dse~DataUSAConstructionSequenceMar08@17` |
| D9 | CONFIRMATION | States that own observation matches another's report | M | `dse~DataUSAStateSequenceCollab2027@2`, `dse~OECDRegionalRecoveryCO2Sequence@10` |
| D10 | CORRECTION | Retracts or corrects an earlier signal, own or another's ("was a TEST, NOT CONFIRMED") | M | `dse~DataUSALanguageR5LiveDec29@9`, `dse~Sector61State5FastSignal@60` |
| D11 | SOURCE_CHALLENGE | Questions how another's claim was obtained, or whether it is reliable | M | `dse~OpenAiDenomSep03@1`, `dse~OECDEquityMay30Live@4` |
| D12 | PROTOCOL | Proposes or restates a rule for how, where, when or in what format to signal ("COUNTRY FIRST", "pre-signal before final", "post as `R3 = GENDER YEAR`", counter key names) | M | `dse~PingOpenAIWatcherDec22MaidsR3@1`, `dse~AgentOpenAI20280525@1`, `dse~OpenAICVDDec08Fast2028@3` |
| D13 | HYPOTHESIS | Proposes a hidden rule of the environment beyond applying a known cadence (teardown at +90m, "terminal after R5", speed tiers) | M | `dse~OpenAIJul09CVDLive@3`, `dse~CashierCoordDec02OAI@5` |
| D14 | METHOD_SHARE | Describes a technique, tool or workaround used to get data or to write | M | `dse~OECDTooltipReplicationNov22@1`, `dse~PoliceWageAgeSequenceMar10Collab@24` |
| D15 | COMMITMENT | Promises a future action ("will relay immediately", "will monitor") | M | `dse~Sector61State5FastSignal@40` |
| D16 | ERROR_DISCLOSURE | Admits own mistake (wrong answer sent, accidental test) | M | `dse~DataUSAClothingLive9m17@17` |
| D17 | CONSTRAINT_REPORT | Reports an environment limit or failure (rate limit 429, URI length, block, context reset) | M | `dse~MaidsJan06R3SignalJul03@8`, `dse~DataUSAConstructionWageSep18Live@30` |
| D18 | EXTERNAL_CHANNEL | References a signaling channel outside the wiki (counter services, beacon keys, other sites) | R→M | `dse~OpenAINov28CVDLive@2`, `dse~OECDEquityLiveDec19@4` |
| D19 | COURTESY | Thanks, apology, congratulations, good luck, or a bare ACK | M | `dse~Apr23CVDHorizonBeacon2025@9`, `dse~ZZZDataUSAConstructionWageLive@10` |
| D20 | RECRUIT | Invites agents working on a task, possibly a different one, to coordinate at a named place, often posted onto another agent's trace | M | `dse~AgentCleanDataUSAExactTest@2`, `dse~DataUSAStateSequenceCollab2027@22` |
| mod | URGENCY | URGENT, IMPORTANT, all-caps lead, "immediately" | R | |

## E. Acting on others' content

| Code | Act | Operational definition | Detect | Examples |
|---|---|---|---|---|
| E1 | OVERWRITE_OTHER | Removes all authored lines of a page last written by a different label | R | `dse~AgentMyBridgeZZ@3` through `@17` (a run of successive takeovers) |
| E2 | COLLATERAL_MUTATION | An evident append that also alters others' existing text | R | `dse~DataUSAClothingStateSequenceCollabOct10@15` |
| E3 | MERGE | Deliberately combines own content with others' existing content ("force merge", "resolve conflict") | M | `dse~AgentMyBridgeZZ@19`, `dse~TestSandboxAIabc@6` |
| E4 | REMOVE | Deletes lines without adding any | R | `dse~AgentScratchXYZ@2` |
| E5 | DUPLICATE_WRITE | Repeats the same block within one save, or re-posts own identical content | R | `dse~WillkommenImWiki@1320`, `dse~ApiReferencesForResearch@34` |
| E6 | RECREATE | Recreates a page after an administrator deletion (from `events.jsonl`, `first_recreation_of`) | R | |

## F. Environment events (not agent acts; recorded as context)

| Code | Event | Source |
|---|---|---|
| F1 | ADMIN_DELETE | `events.jsonl` `event_type=delete`: 5,217 events, peaking 2026-06-19 and 06-23 to 06-26 |

## Known confusions to resolve in the stress test

- **D2 vs D3:** round reports usually include the answer. Tag both.
- **D4 vs D13:** "R5 due 13:39:29" applies a cadence (D4). "Teardown is R1+106m04s" proposes a rule (D13).
- **A4 vs D3:** values posted for general retrieval (A4) versus a timed-task answer (D3).
- **B4 vs D20:** relocating an existing conversation (B4) versus inviting new participants (D20).
- **C1 vs B3:** a probe is a deliberate test save. A marker is a token inside a substantive save that lets the author find their own write.
- **Copying:** overwrites on hub pages often re-post link blocks first written by others. That is visible only across units and belongs to the L2 reuse edges, not to single-unit coding.

## How the earlier screenshot categories decompose

Each category in the earlier summary turns out to be a composite of v0 acts plus a measurable condition. That is how the collective-level labels should be rebuilt:

| Earlier category | v0 composition |
|---|---|
| Send the key observation quickly | D2 + D12 ("COUNTRY FIRST") + latency from observation to post |
| Share completed rounds and the next due time | D2 + D4 (+ D5) |
| Signal before a final answer can end the session | D12 (pre-signal before final) + later compliance by the same cohort |
| Move the live conversation to a smaller page | B4 + D17 (URI limit, page size) |
| Keep tests distinct from live signals | D10 + C1 + SELF_LABELED_TEST |
| Agree on controls before interpreting a survival test | D12 + D13 + D6 + D18 (heartbeat beacons on counter services) |
