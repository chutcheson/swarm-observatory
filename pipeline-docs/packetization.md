# Source ingestion and packetization

`swarm_pipeline.ingest.ingest(conn, source_root, research_root)` imports the
Nightingale `pages.jsonl`, `revisions.jsonl`, `events.jsonl`, and `labels.jsonl`
records, plus the reviewed normalized Transluce evidence packets. The raw
Transluce HTTP JSON archive is not opened. The local read-only pilot inventory
adds the complete report catalog as entities: the current catalog has 38,160
distinct report IDs. Only the 32 reviewed normalized packets create Transluce
sources and processing packets; catalog-only report rows carry allowlisted
metadata and never receive invented evidence. Each imported source UID hashes its
dataset, logical ID, text, and metadata. Reimporting identical input is
idempotent; a body or metadata edit creates a new UID and leaves old versions
intact. Page/report entity metadata points to the latest imported source and
revision. Nightingale page catalog rows and Transluce selection entries are
entities, so a catalog entry remains visible even if its normalized report
packet is missing.

`prepare_packets(conn, entity_ids=None, max_chars=40000)` compares ordered
Nightingale revisions within each page. A page's first nonempty revision is
entirely focus. Later insertions and replacements become focus; unchanged
carry-forward text remains context. Deletions have no focus interval, so the
packet records their previous-version source UID, exact character offsets,
length, and SHA-256 digest under `coverage.deleted_spans`.

Each packet focus span indexes its `sources[].text` excerpt. The excerpt's
`metadata.source_start` is its absolute start offset in the immutable revision,
so the exact original range is `source_start + focus.start` through
`source_start + focus.end`. `metadata.source_end` records the excerpt boundary.
Context before and after focus is explicitly counted in source metadata and in
`coverage.context`; context never increases the focus interval. Deletion offsets
are already absolute offsets into the prior immutable source. Long spans are
split at exact character boundaries, with the original offset carried for
every excerpt. No focus text is dropped.

If an already imported logical revision receives a metadata-only update, a
context-only packet records the changed metadata keys and both immutable source
UIDs. This makes an edited signature or source context reviewable without
marking unchanged body text as a new contribution.

The default text budget is 40,000 characters per packet; callers can pass a
smaller positive limit for tests or constrained workers. Context and any
deleted-version excerpt are included in that budget. The estimate is a
character limit rather than a token guarantee; downstream stages may apply a
model-specific token limit. IDs and payload hashes are deterministic, and
`INSERT OR IGNORE` makes repeated packet preparation idempotent.

Normalized Transluce packet text is taken only from `evidence/transluce-reviewed.json`.
It retains the recorded safe excerpt text, extraction pointers, and
transformation metadata as inert strings. Packet source metadata preserves a
compact `kind` and `provenance` label plus report/date/source fields and JSON
pointers; it omits the bulky extract objects. Nightingale packet metadata keeps
allowlisted clock and page fields. A revision label is recorded as
`declared_revision_writer`, with provenance text clarifying that this archive
label does not verify the message author. Missing selected reports produce a
catalog-only entity and no packet.
