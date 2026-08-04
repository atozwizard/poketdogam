from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.schemas.domain import ScanCandidate
from app.vision.fusion import fuse_candidates
from app.vision.visual_matcher import (
    _center_square_views,
    _calibrate_similarity,
    _grid_square_views,
    MODEL_ID,
    VisualDexMatcher,
    get_visual_matcher,
    visual_runtime_status,
)
from scripts.validate_visual_benchmark import validate_visual_benchmark


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def candidate(
    form_id: str,
    pokemon_id: int,
    score: float,
    *,
    source: str,
    form_name: str = "base",
) -> ScanCandidate:
    return ScanCandidate(
        form_id=form_id,
        pokemon_id=pokemon_id,
        name_ko=form_id,
        form_name=form_name,
        confidence=score,
        evidence_sources=[source],
    )


class VisualFusionTest(unittest.TestCase):
    def test_visual_matcher_singleton_is_thread_safe(self) -> None:
        with ThreadPoolExecutor(max_workers=8) as executor:
            matchers = list(executor.map(lambda _: get_visual_matcher(), range(32)))

        self.assertEqual(len({id(matcher) for matcher in matchers}), 1)

    def test_reference_cache_tracks_atomic_database_replacement(self) -> None:
        def build_database(path: Path, pokemon_id: int, name: str) -> None:
            with closing(sqlite3.connect(path)) as conn:
                conn.executescript(
                    """
                    create table visual_reference_embeddings (
                        form_id text, embedding_blob blob, model_id text,
                        reference_kind text, generation_scope integer
                    );
                    create table pokemon_forms (
                        form_id text, pokemon_id integer, form_name text,
                        type1 text, type2 text
                    );
                    create table pokemon_species (
                        pokemon_id integer, name_ko text, name_en text,
                        generation integer
                    );
                    """
                )
                conn.execute(
                    "insert into pokemon_species values (?, ?, ?, 1)",
                    (pokemon_id, name, name),
                )
                conn.execute(
                    "insert into pokemon_forms values ('base', ?, 'base', 'normal', null)",
                    (pokemon_id,),
                )
                conn.execute(
                    "insert into visual_reference_embeddings values ('base', ?, ?, 'derived', 1)",
                    (sqlite3.Binary(b"\0\0\0\0"), MODEL_ID),
                )
                conn.commit()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "dex.sqlite"
            replacement = root / "replacement.sqlite"
            model = root / "model.tflite"
            model.write_bytes(b"test")
            build_database(database, 25, "피카츄")
            matcher = VisualDexMatcher(db_path=database, model_path=model)
            self.assertEqual(matcher._reference_rows()[0]["pokemon_id"], 25)

            build_database(replacement, 133, "이브이")
            os.replace(replacement, database)

            self.assertEqual(matcher._reference_rows()[0]["pokemon_id"], 133)

    def test_gen1_visual_index_covers_every_committed_form(self) -> None:
        status = visual_runtime_status()

        self.assertTrue(status["available"])
        self.assertEqual(status["gen1_form_count"], 238)
        self.assertIsNone(status["scan_default_generation"])
        self.assertIn(status["scope"], {"generation_1_all_forms", "all_generations_all_forms"})
        self.assertGreaterEqual(status["reference_count"], 238)

    def test_matcher_builds_full_and_two_center_views(self) -> None:
        from PIL import Image

        image = Image.new("RGB", (640, 480))
        views = _center_square_views(image)

        self.assertEqual([view.size for view in views], [(326, 326), (268, 268)])

    def test_matcher_builds_eighteen_position_crops(self) -> None:
        from PIL import Image

        image = Image.new("RGB", (640, 480))
        views = _grid_square_views(image)

        self.assertEqual(len(views), 18)
        self.assertEqual(
            [view.size for view in views],
            [(240, 240)] * 9 + [(153, 153)] * 9,
        )

    def test_visual_score_is_a_cosine_comparison_not_probability(self) -> None:
        self.assertEqual(_calibrate_similarity(-1.0), 0.0)
        self.assertEqual(_calibrate_similarity(0.0), 0.5)
        self.assertEqual(_calibrate_similarity(1.0), 1.0)

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

    def test_equal_scores_prefer_base_form(self) -> None:
        fused = fuse_candidates(
            [
                candidate("pikachu-rock-star", 25, 1.0, source="ocr", form_name="rock-star"),
                candidate("pikachu-base", 25, 1.0, source="ocr", form_name="base"),
            ],
            [],
            top_k=3,
        )

        self.assertEqual(fused[0].form_id, "pikachu-base")


if __name__ == "__main__":
    unittest.main()
