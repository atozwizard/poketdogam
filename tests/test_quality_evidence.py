from __future__ import annotations

from pathlib import Path
import unittest

from scripts.benchmark_universal_recognition import _build_cert
from scripts.evaluate_quality_score import evaluate


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QualityEvidenceTest(unittest.TestCase):
    def test_generation_aided_lab_score_cannot_certify_product_search(self) -> None:
        benchmark = {
            "created_at": "2026-08-04T00:00:00+00:00",
            "scope": {"evaluated_media_kinds": ["in_game_transform"]},
            "corpus": {
                "in_game_species_count": 1025,
                "total_recognizable_samples": 4969,
                "media_kind_count": 7,
                "media_kinds_present": [
                    "in_game_sprite_or_artwork",
                    "card",
                    "plush",
                    "figure_or_toy",
                    "goods",
                    "user_screenshot",
                    "open_license_field_photo",
                ],
                "field_species_count": 28,
                "field_reference_count": 91,
                "field_creator_count": 20,
            },
            "aggregate": {
                "query_count": 3075,
                "species_recall_at_3": 0.95,
            },
            "cross_generation_aggregate": {
                "query_count": 3075,
                "species_recall_at_3": 0.70,
            },
            "by_generation": {
                str(generation): {"species_recall_at_3": 0.95}
                for generation in range(1, 10)
            },
        }

        cert = _build_cert(benchmark)

        self.assertFalse(cert["certified"])
        self.assertEqual(cert["species_recall_at_3"], 0.70)
        self.assertEqual(cert["generation_scoped_lab_species_recall_at_3"], 0.95)
        self.assertTrue(cert["generation_scoped_lab_gate_met"])
        self.assertEqual(cert["evaluated_media_kind_count"], 1)

    def test_scoreboard_keeps_product_lab_and_field_evidence_separate(self) -> None:
        result = evaluate()
        evidence = result["field_evidence"]

        self.assertLess(
            evidence["product_open_search_top3_recall"],
            evidence["generation_aided_lab_top3_recall"],
        )
        self.assertEqual(
            evidence["field_pilot_top3_recall"],
            0.0989,
        )
        self.assertFalse(result["product_open_search_certification"]["certified"])
        self.assertFalse(result["wild_accuracy_certification"]["certified"])
        self.assertFalse(result["system_test_authorized"])
        self.assertTrue(result["mvp_engineering_go"])

    def test_full_system_authorization_requires_exact_physical_gate(self) -> None:
        source = (PROJECT_ROOT / "scripts/evaluate_quality_score.py").read_text(
            encoding="utf-8"
        )

        authorization_block = source.split("all_scores_meet_target = (", 1)[1].split(
            ")\n    mvp_engineering_go", 1
        )[0]
        self.assertIn("and product_open_search_certified", authorization_block)
        self.assertIn("and wild_accuracy_certified", authorization_block)


if __name__ == "__main__":
    unittest.main()
