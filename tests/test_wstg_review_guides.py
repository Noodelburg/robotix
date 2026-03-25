import unittest

from wstg_review_guides import load_review_guides


class WstgReviewGuideTests(unittest.TestCase):
    def test_catalog_classifies_support_and_alias_guides(self):
        catalog = load_review_guides()
        test_cases = catalog["test_cases"]
        support_paths = {
            guide["relative_path"] for guide in catalog["support_docs"]
        }
        alias_pairs = {
            (item["alias_wstg_id"], item["target_wstg_id"])
            for item in catalog["alias_resolution"]
        }
        by_id = {guide["wstg_id"]: guide for guide in test_cases}

        self.assertEqual(len(test_cases), 111)
        self.assertIn(
            "wstg/10-Business_Logic_Testing/00-Introduction_to_Business_Logic.md",
            support_paths,
        )
        self.assertIn(
            "wstg/12-API_Testing/00-API_Testing_Overview.md",
            support_paths,
        )
        self.assertIn(("WSTG-IDNT-05", "WSTG-IDNT-04"), alias_pairs)
        self.assertIn(("WSTG-ATHN-01", "WSTG-CRYP-03"), alias_pairs)
        self.assertIn(
            "wstg/03-Identity_Management_Testing/05-Testing_for_Weak_or_Unenforced_Username_Policy.md",
            by_id["WSTG-IDNT-04"]["support_paths"],
        )


if __name__ == "__main__":
    unittest.main()
