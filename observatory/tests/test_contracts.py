"""Evidence contract tests: claims need exact, focused, locally attributable text."""
import unittest

from swarm_pipeline.contracts import InvalidResult, validate_result

TEXT = "Mira: @Jon, prepare the benchmark results by Friday."
PACKET = {
    "entity_id": "task-1", "dataset": "synthetic", "title": "Benchmark task",
    "sources": [{"uid": "source-v1", "logical_id": "message-1", "text": TEXT, "metadata": {}}],
    "focus": [{"source_uid": "source-v1", "start": 0, "end": len(TEXT)}],
    "context_source_uids": [], "coverage": {}, "links": [],
}


def observation(*, quote=TEXT, actor="Mira", recipients=("Jon",), audience="direct"):
    return {
        "id": "obs-1", "kind": "message", "actor": actor, "recipients": list(recipients),
        "audience": audience, "summary": "Mira asks Jon to prepare results.",
        "task": "Prepare benchmark results by Friday.", "status": "proposal",
        "evidence": [{"source_uid": "source-v1", "quote": quote}], "uncertainties": [],
    }


def extract(obs):
    return {
        "status": "complete", "context_requests": [], "scope_summary": "One message.",
        "reviewed_source_uids": ["source-v1"], "observations": [obs], "limitations": [],
    }


class ContractTests(unittest.TestCase):
    def test_accepts_exact_focus_quote_with_literal_actor_and_recipient(self):
        self.assertEqual(extract(observation()), validate_result("extract", extract(observation()), PACKET))

    def test_rejects_non_exact_evidence(self):
        result = extract(observation(quote="Mira asks Jon to prepare the results."))
        with self.assertRaisesRegex(InvalidResult, "non-exact"):
            validate_result("extract", result, PACKET)

    def test_rejects_context_only_evidence_as_new_observation(self):
        packet = {**PACKET, "focus": []}
        with self.assertRaisesRegex(InvalidResult, "no focus evidence"):
            validate_result("extract", extract(observation()), packet)

    def test_actor_must_be_literal_in_supporting_quote(self):
        result = extract(observation(actor="Jordan"))
        with self.assertRaisesRegex(InvalidResult, "Actor must occur"):
            validate_result("extract", result, PACKET)

    def test_direct_recipient_must_be_literal_in_supporting_quote(self):
        result = extract(observation(recipients=("Alex",)))
        with self.assertRaisesRegex(InvalidResult, "Recipient must be literal"):
            validate_result("extract", result, PACKET)

    def test_partial_name_is_not_a_recipient(self):
        with self.assertRaisesRegex(InvalidResult, "Recipient must be literal"):
            validate_result("extract", extract(observation(recipients=("Jo",))), PACKET)

    def test_generic_pronoun_is_not_a_recipient_identity(self):
        with self.assertRaisesRegex(InvalidResult, "Recipient must be literal"):
            validate_result("extract", extract(observation(recipients=("your R6",))), PACKET)

    def test_summary_rejects_supplied_id_with_invented_label(self):
        result = {
            "status": "complete", "context_requests": [], "title": "Benchmark preparation",
            "hover": "Mira asks Jon to prepare results.", "short": "Mira asks Jon to prepare results.",
            "long": "The message records a request to prepare benchmark results.",
            "links": [{"type": "observation", "id": "obs-1", "label": "Invented observation label"}],
            "evidence_observation_ids": ["obs-1"], "limitations": [],
        }
        previous = {"extract": {"observations": [observation()]}}
        allowed = [{"type": "observation", "id": "obs-1", "label": "Mira asks Jon to prepare results."}]
        with self.assertRaisesRegex(InvalidResult, "Summary link not supplied"):
            validate_result("summarize", result, PACKET, previous, allowed)

    def test_direct_audience_requires_actor_and_recipient(self):
        result = extract(observation(actor=None, recipients=()))
        with self.assertRaisesRegex(InvalidResult, "Direct communication requires"):
            validate_result("extract", result, PACKET)


if __name__ == "__main__":
    unittest.main()
