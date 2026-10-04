# Pipeline projection and export

`build_projection(conn, baseline_path=None)` produces an in-memory projection
of the pipeline's currently publishable records. `export_projection(conn,
path, baseline_path=None)` writes that projection as JSON, using a temporary
file and atomic replacement so readers never see a partial export. Both
functions are deterministic apart from the generated timestamp.

## Evidence and eligibility

The projection is an evidence-backed view of pipeline results, not a second
source corpus. It contains only completed, approved summaries whose packet,
configuration, and full dependency ancestry remain current. Pending, rejected,
blocked, failed, stale, invalidated, or otherwise incomplete work is excluded.
In particular, a completed descendant cannot make an invalid or stale ancestor
publishable again.

Each exported record identifies its entity and packet scope and carries source
provenance down to evidence locations. When packets overlap, identical evidence
locations are included once; distinct source spans remain distinct. Records
retain separate short, long, and hover summaries where supplied by the approved
result. Evidence offsets refer to the original source text, including when a
packet contains a cropped excerpt. Summary links to observations are remapped
to projected observation IDs; dangling observation links are dropped. Missing
summary forms are omitted rather than fabricated.

## Typed networks

Networks are derived only from approved, evidence-backed structured results.
Actor IDs are scoped to an entity and the literal source label. Repeated labels
in different entities remain separate nodes; the projection makes no automatic
identity merges. Communication edges require an explicitly named actor and
directly identified recipient(s). Interpreted reply, delegation, and handoff
relations stay provisional unless their basis includes a reviewed direct
message from that source to that recipient. An audience, co-occurrence, or
unverified identity match does not create a communication edge. Protocol edges
describe explicitly stated protocol relations. Task edges describe explicitly
stated task or dependency relations. Each edge keeps its type, evidence
references, and provenance.

Unresolved identity equivalences and other inferred relations may be retained
as hypotheses, clearly separate from asserted network edges. Unsigned or
unapproved output creates no records or edges. Text summaries alone do not
establish structured network relations.

## Baseline compatibility

When a previous 360-case snapshot is supplied, the original snapshot remains
intact under the top-level research fields. Pipeline additions live in a
separate `pipeline` overlay with its own version, timestamp, counts, coverage,
job and ticket status, records, networks, and provenance. Pipeline records do
not replace baseline cases or claim baseline identities. A pipeline record may
also be exposed as a research-UI-compatible case only when its fields and
evidence meet the existing case contract; such cases must be clearly marked as
pipeline additions and keep pipeline evidence provenance.

## Status and privacy

Status output is aggregate operational metadata: job counts by stage and state,
ticket counts by state and kind, source/packet/entity totals, the configured
model, and numeric usage totals. It omits individual job errors, source text,
packet text, raw model output, embedded programs, credentials, and other corpus
content. The projection never fetches source URLs or executes source content.
