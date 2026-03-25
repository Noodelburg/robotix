import json
import tempfile
import unittest
from pathlib import Path

from reviewer import run_reviewer


class ReviewerSmokeTests(unittest.TestCase):
    def test_run_reviewer_writes_per_guide_json_and_index(self):
        import reviewer

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "repo"
            root.mkdir()
            source_file = root / "profile.py"
            source_file.write_text(
                "def update_profile(data):\n    model = data\n    return model\n",
                encoding="utf-8",
            )
            input_path = root / "repository-input.json"
            input_path.write_text(
                json.dumps(
                    {
                        "root": str(root),
                        "chunks": [
                            {
                                "id": "chunk-0001",
                                "name": "profile",
                                "reason": "account update flow",
                                "total_lines": 3,
                                "file_count": 1,
                                "files": [{"path": "profile.py", "lines": 3}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            system_map_path = root / "system-map.json"
            system_map_path.write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "summary": "System map summary",
                        "system_map": {
                            "entrypoints": [],
                            "trust_boundaries": [],
                            "identity_and_privilege_zones": [],
                            "data_stores": [],
                            "external_integrations": [],
                            "sensitive_operations": [],
                        },
                        "coverage_gaps": [],
                    }
                ),
                encoding="utf-8",
            )
            guide = {
                "title": "Testing for Mass Assignment",
                "wstg_id": "WSTG-INPV-20",
                "path": str(root / "wstg" / "20.md"),
                "relative_path": "wstg/07-Input_Validation_Testing/20-Testing_for_Mass_Assignment.md",
                "area": "07-Input_Validation_Testing",
                "classification": "test_case",
                "markdown": "Mass assignment review guide",
                "merged_target_wstg_id": "",
                "support_paths": [
                    "wstg/07-Input_Validation_Testing/README.md",
                    "wstg/03-Identity_Management_Testing/05-Testing_for_Weak_or_Unenforced_Username_Policy.md",
                ],
                "alias_paths": [
                    "wstg/03-Identity_Management_Testing/05-Testing_for_Weak_or_Unenforced_Username_Policy.md",
                ],
            }
            support_doc = {
                "title": "Input Validation README",
                "wstg_id": "",
                "path": str(root / "wstg" / "README.md"),
                "relative_path": "wstg/07-Input_Validation_Testing/README.md",
                "area": "07-Input_Validation_Testing",
                "classification": "support",
                "markdown": "support markdown",
                "merged_target_wstg_id": "",
                "support_paths": [],
                "alias_paths": [],
            }
            alias_doc = {
                "title": "Weak Username Policy",
                "wstg_id": "WSTG-IDNT-05",
                "path": str(root / "wstg" / "alias.md"),
                "relative_path": "wstg/03-Identity_Management_Testing/05-Testing_for_Weak_or_Unenforced_Username_Policy.md",
                "area": "03-Identity_Management_Testing",
                "classification": "merged_alias",
                "markdown": "alias markdown",
                "merged_target_wstg_id": "WSTG-INPV-20",
                "support_paths": [],
                "alias_paths": [],
            }
            catalog = {
                "test_cases": [guide],
                "support_docs": [support_doc],
                "merged_aliases": [alias_doc],
                "guides_by_path": {
                    support_doc["relative_path"]: support_doc,
                    alias_doc["relative_path"]: alias_doc,
                    guide["relative_path"]: guide,
                },
                "alias_resolution": [
                    {
                        "alias_wstg_id": alias_doc["wstg_id"],
                        "alias_path": alias_doc["relative_path"],
                        "target_wstg_id": guide["wstg_id"],
                        "target_path": guide["relative_path"],
                    }
                ],
                "issues": [],
            }
            output_dir = root / "reviews" / "wstg"

            def fake_call_ai(prompt, cmd=None):
                if "rank repository chunks for a WSTG-guided security review worker" in prompt:
                    return {
                        "summary": "route summary",
                        "ranked_chunks": [
                            {
                                "chunk_id": "chunk-0001",
                                "relevance": "high",
                                "rationale": "profile flow",
                            }
                        ],
                    }

                if "review the provided repository chunk through the lens" in prompt:
                    return {
                        "summary": "chunk summary",
                        "candidate_findings": [
                            {
                                "title": "mass assignment in update_profile",
                                "certainty": "plausible",
                                "weakness_summary": "request-controlled fields are passed through directly",
                                "attack_path": {
                                    "entrypoint": "update_profile",
                                    "controllable_input": "data argument",
                                    "control_gap": "no allowlist before model update",
                                    "sensitive_sink_or_boundary": "profile model",
                                    "impact": "internal fields may be modified",
                                    "assumptions": ["the passed data is persisted later"],
                                },
                                "evidence": [
                                    {
                                        "chunk_id": "chunk-0001",
                                        "files": ["profile.py"],
                                        "rationale": "request data is assigned directly",
                                    }
                                ],
                                "counter_evidence": [
                                    "a later serializer may still restrict fields"
                                ],
                                "remediation_direction": "allowlist writable fields",
                            }
                        ],
                        "rejected_hypotheses": [],
                        "coverage_gaps": [],
                    }

                if "consolidate a guide-level WSTG review result" in prompt:
                    return {
                        "summary": "merged summary",
                        "candidate_findings": [
                            {
                                "title": "mass assignment in update_profile",
                                "certainty": "plausible",
                                "weakness_summary": "request-controlled fields are passed through directly",
                                "attack_path": {
                                    "entrypoint": "update_profile",
                                    "controllable_input": "data argument",
                                    "control_gap": "no allowlist before model update",
                                    "sensitive_sink_or_boundary": "profile model",
                                    "impact": "internal fields may be modified",
                                    "assumptions": ["the passed data is persisted later"],
                                },
                                "evidence": [
                                    {
                                        "chunk_id": "chunk-0001",
                                        "files": ["profile.py"],
                                        "rationale": "request data is assigned directly",
                                    }
                                ],
                                "counter_evidence": [
                                    "a later serializer may still restrict fields"
                                ],
                                "remediation_direction": "allowlist writable fields",
                            }
                        ],
                        "rejected_hypotheses": [],
                        "coverage_gaps": [],
                    }

                raise AssertionError("Unexpected prompt")

            original_load_review_guides = reviewer.load_review_guides
            original_call_ai = reviewer.call_ai

            try:
                reviewer.load_review_guides = lambda: catalog
                reviewer.call_ai = fake_call_ai
                index_payload = run_reviewer(input_path, system_map_path, output_dir)
            finally:
                reviewer.load_review_guides = original_load_review_guides
                reviewer.call_ai = original_call_ai

            guide_output_path = output_dir / "WSTG-INPV-20.json"
            index_path = output_dir / "index.json"

            self.assertTrue(guide_output_path.exists())
            self.assertTrue(index_path.exists())
            guide_output = json.loads(guide_output_path.read_text(encoding="utf-8"))

            self.assertEqual(guide_output["guide"]["support_paths"], guide["support_paths"])
            self.assertEqual(len(guide_output["candidate_findings"]), 1)
            self.assertEqual(index_payload["guide_runs"][0]["wstg_id"], "WSTG-INPV-20")
            self.assertEqual(len(index_payload["finding_catalog"]), 1)
            self.assertEqual(
                index_payload["alias_resolution"][0]["alias_wstg_id"],
                "WSTG-IDNT-05",
            )


if __name__ == "__main__":
    unittest.main()
