from __future__ import annotations

import unittest
from pathlib import Path

from app.schemas.domain import ScanCandidate
from app.vision.fusion import fuse_candidates
from app.vision.visual_matcher import _center_square_views, visual_runtime_status
from scripts.validate_visual_benchmark import validate_visual_benchmark


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def candidate(
    form_id: str,
    pokemon_id: int,
    score: float,
    *,
    source: str,
) -> ScanCandidate:
    return ScanCandidate(
        form_id=form_id,
        pokemon_id=pokemon_id,
        name_ko=form_id,
        confidence=score,
        evidence_sources=[source],
    )


class VisualFusionTest(unittest.TestCase):
    def test_gen1_visual_index_covers_every_committed_form(self) -> None:
        status = visual_runtime_status()

        self.assertTrue(status["available"])
        self.assertEqual(status["reference_count"], 238)
        self.assertEqual(status["scope"], "generation_1_all_forms")

    def test_matcher_builds_full_and_two_center_views(self) -> None:
        from PIL import Image

        image = Image.new("RGB", (640, 480))
        views = _center_square_views(image)

        self.assertEqual([view.size for view in views], [(326, 326), (268, 268)])

    def test_visual_benchmark_passes_each_scenario_at_ninety_percent(self) -> None:
        result = validate_visual_benchmark(
            PROJECT_ROOT / "data/vision/benchmark.json"
        )

        self.assertTrue(result["passed"])
        self.assertFalse(result["field_accuracy_claimed"])
        self.assertGreaterEqual(result["form_recall_at_3"], 0.9)

    def test_weak_ocr_yields_to_strong_visual_candidate(self) -> None:
        fused = fuse_candidates(
            [candidate("wrong", 1, 0.6, source="ocr")],
            [candidate("pikachu", 25, 0.95, source="visual_embedding")],
            top_k=3,
        )

        self.assertEqual(fused[0].form_id, "pikachu")
        self.assertEqual(fused[0].evidence_sources, ["visual_embedding"])

    def test_matching_evidence_is_combined_and_limited_to_top_three(self) -> None:
        fused = fuse_candidates(
            [
                candidate("pikachu", 25, 0.94, source="ocr"),
                candidate("raichu", 26, 0.7, source="ocr"),
            ],
            [
                candidate("pikachu", 25, 0.9, source="visual_embedding"),
                candidate("eevee", 133, 0.84, source="visual_embedding"),
                candidate("mew", 151, 0.8, source="visual_embedding"),
            ],
            top_k=3,
        )

        self.assertEqual(len(fused), 3)
        self.assertEqual(fused[0].form_id, "pikachu")
        self.assertEqual(fused[0].evidence_sources, ["ocr", "visual_embedding"])
        self.assertIsNotNone(fused[0].ocr_confidence)
        self.assertIsNotNone(fused[0].visual_confidence)


if __name__ == "__main__":
    unittest.main()
