import unittest

from reviewer import canonicalize_guide_output, route_guide_chunks


class ReviewerCoreTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "root_path": "/tmp/repo",
            "chunks": [
                {
                    "id": "chunk-0001",
                    "name": "billing",
                    "reason": "payment handlers",
                    "total_lines": 20,
                    "file_count": 1,
                    "files": [{"path": "src/billing.py", "lines": 20}],
                },
                {
                    "id": "chunk-0002",
                    "name": "profile",
                    "reason": "account updates",
                    "total_lines": 15,
                    "file_count": 1,
                    "files": [{"path": "src/profile.py", "lines": 15}],
                },
            ],
            "chunk_by_id": {},
            "known_chunk_ids": {"chunk-0001", "chunk-0002"},
            "files_by_chunk": {
                "chunk-0001": {"src/billing.py"},
                "chunk-0002": {"src/profile.py"},
            },
            "known_paths": {"src/billing.py", "src/profile.py"},
        }
        self.context["chunk_by_id"] = {
            chunk["id"]: chunk for chunk in self.context["chunks"]
        }
        self.guide = {
            "wstg_id": "WSTG-BUSL-10",
            "title": "Test Payment Functionality",
            "relative_path": "wstg/10-Business_Logic_Testing/10-Test-Payment-Functionality.md",
            "area": "10-Business_Logic_Testing",
            "markdown": "Payment flows, payment gateways, and card handling.",
            "support_paths": [],
        }

    def test_route_guide_chunks_falls_back_to_lexical_ranking(self):
        import reviewer

        original_call_ai = reviewer.call_ai

        try:
            reviewer.call_ai = lambda *args, **kwargs: {"summary": "", "ranked_chunks": []}
            routing = route_guide_chunks(
                self.guide,
                support_markdown="",
                system_map_output={"summary": "", "system_map": {}, "coverage_gaps": []},
                chunks=self.context["chunks"],
                ai_cmd="fake",
            )
        finally:
            reviewer.call_ai = original_call_ai

        self.assertTrue(routing["selected_chunk_ids"])
        self.assertEqual(routing["selected_chunk_ids"][0], "chunk-0001")

    def test_canonicalize_guide_output_drops_invalid_findings_and_rebuilds_metrics(self):
        guide = {
            "wstg_id": "WSTG-INPV-20",
            "title": "Testing for Mass Assignment",
            "relative_path": "wstg/07-Input_Validation_Testing/20-Testing_for_Mass_Assignment.md",
            "area": "07-Input_Validation_Testing",
            "support_paths": [],
        }
        raw_output = {
            "status": "pass",
            "summary": "raw summary",
            "input": {
                "routed_chunk_ids": ["chunk-0002"],
                "reviewed_chunk_ids": ["chunk-0002"],
                "review_depth": "initial",
            },
            "candidate_findings": [
                {
                    "title": "bad certainty",
                    "certainty": "confirmed",
                    "weakness_summary": "nope",
                    "attack_path": {
                        "entrypoint": "endpoint",
                        "controllable_input": "body",
                        "control_gap": "bad",
                        "sensitive_sink_or_boundary": "db",
                        "impact": "bad",
                        "assumptions": [],
                    },
                    "evidence": [
                        {
                            "chunk_id": "chunk-0002",
                            "files": ["src/profile.py"],
                            "rationale": "test",
                        }
                    ],
                    "counter_evidence": ["maybe safe"],
                    "remediation_direction": "fix it",
                },
                {
                    "title": "mass assignment in profile update",
                    "certainty": "plausible",
                    "weakness_summary": "handler persists request-controlled model fields",
                    "attack_path": {
                        "entrypoint": "profile update endpoint",
                        "controllable_input": "request body",
                        "control_gap": "server trusts client supplied fields",
                        "sensitive_sink_or_boundary": "account record persistence",
                        "impact": "internal-only fields may be updated",
                        "assumptions": ["serializer writes the model as shown"],
                    },
                    "evidence": [
                        {
                            "chunk_id": "chunk-0002",
                            "files": ["src/profile.py"],
                            "rationale": "handler binds and persists request fields",
                        }
                    ],
                    "counter_evidence": ["a serializer elsewhere may filter fields"],
                    "remediation_direction": "apply an allowlist",
                },
            ],
            "rejected_hypotheses": [],
            "coverage_gaps": [],
        }

        payload, problems = canonicalize_guide_output(
            raw_output=raw_output,
            guide=guide,
            context=self.context,
            system_map_path="/tmp/repo/chunks/system-map.json",
        )

        self.assertTrue(problems)
        self.assertEqual(payload["status"], "needs_review")
        self.assertEqual(len(payload["candidate_findings"]), 1)
        self.assertEqual(payload["metrics"]["candidate_finding_count"], 1)
        self.assertEqual(payload["candidate_findings"][0]["finding_id"], "WSTG-INPV-20-F001")


if __name__ == "__main__":
    unittest.main()
