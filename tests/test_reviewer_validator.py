import unittest

from reviewer_validator import audit_guide_output


class ReviewerValidatorTests(unittest.TestCase):
    def test_audit_guide_output_flags_missing_counter_evidence_and_bad_file_reference(self):
        guide = {
            "wstg_id": "WSTG-ATHZ-04",
            "title": "Testing for Insecure Direct Object References",
            "relative_path": "wstg/05-Authorization_Testing/04-Testing_for_Insecure_Direct_Object_References.md",
            "area": "05-Authorization_Testing",
            "support_paths": [],
        }
        context = {
            "root_path": "/tmp/repo",
            "known_chunk_ids": {"chunk-0001"},
            "known_paths": {"src/invoices.py"},
            "files_by_chunk": {"chunk-0001": {"src/invoices.py"}},
        }
        output = {
            "status": "pass",
            "summary": "summary",
            "guide": {
                "wstg_id": guide["wstg_id"],
                "title": guide["title"],
                "path": guide["relative_path"],
                "area": guide["area"],
                "support_paths": [],
            },
            "input": {
                "root": "/tmp/repo",
                "system_map_path": "/tmp/repo/chunks/system-map.json",
                "routed_chunk_ids": ["chunk-0001"],
                "reviewed_chunk_ids": ["chunk-0001"],
                "review_depth": "initial",
            },
            "candidate_findings": [
                {
                    "finding_id": "WSTG-ATHZ-04-F001",
                    "title": "idor in invoice handler",
                    "certainty": "plausible",
                    "weakness_summary": "summary",
                    "attack_path": {
                        "entrypoint": "invoice endpoint",
                        "controllable_input": "invoice id",
                        "control_gap": "missing owner check",
                        "sensitive_sink_or_boundary": "invoice retrieval",
                        "impact": "cross-user access",
                        "assumptions": [],
                    },
                    "evidence": [
                        {
                            "chunk_id": "chunk-0001",
                            "files": ["src/other.py"],
                            "rationale": "bad path",
                        }
                    ],
                    "counter_evidence": [],
                    "remediation_direction": "scope queries to owner",
                }
            ],
            "rejected_hypotheses": [],
            "coverage_gaps": [],
            "metrics": {
                "routed_chunk_count": 1,
                "reviewed_chunk_count": 1,
                "candidate_finding_count": 1,
                "rejected_hypothesis_count": 0,
                "coverage_gap_count": 0,
                "expansion_performed": False,
            },
        }

        issues = audit_guide_output(
            output,
            guide,
            context,
            "/tmp/repo/chunks/system-map.json",
            "WSTG-ATHZ-04.json",
        )
        messages = [issue["message"] for issue in issues]

        self.assertTrue(any("no counter_evidence" in message for message in messages))
        self.assertTrue(any("do not match the referenced chunk" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
