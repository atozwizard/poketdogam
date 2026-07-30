# Run: python -m unittest tests/test_local_scan_core.py
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.agents.pokedex_agent.tools.tool_local_dex import LocalDexStore
from scripts.build_local_dex.build import _append_unreleased_official_previews, build_local_dex
from scripts.build_local_dex.validate_dex import validate_fixtures
from scripts.build_local_dex.validate_dex import validate


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LocalScanCoreTest(unittest.TestCase):
    def test_official_preview_is_removed_when_upstream_canonical_name_arrives(self) -> None:
        normalized = {
            "species": [{"pokemon_id": 1026, "name_en": "Browt"}],
            "forms": [],
            "stats": [],
            "evolutions": [],
        }
        previews = {
            "species": [{"pokemon_id": -1000001, "name_en": "Browt"}],
            "forms": [{"pokemon_id": -1000001, "form_id": "preview-browt"}],
            "stats": [],
            "evolutions": [],
        }

        _append_unreleased_official_previews(normalized, previews)

        self.assertEqual(len(normalized["species"]), 1)
        self.assertEqual(normalized["forms"], [])

    def test_build_seed_dex_and_match_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "dex.sqlite"
            meta_path = temp_path / "dex.meta.json"
            result = build_local_dex(
                db_path,
                meta_path,
                dataset_version="test-seed",
                source="seed",
            )

            self.assertEqual(result["validation"]["fixture"]["match_recall_at_3"], 1.0)
            self.assertTrue(db_path.exists())
            self.assertTrue(meta_path.exists())

    def test_fuzzy_korean_scan_text_returns_pikachu(self) -> None:
        store = LocalDexStore(PROJECT_ROOT / "data/dex.sqlite")
        candidates = store.match_name("피카추\nHP 60", top_k=3)

        self.assertGreaterEqual(len(candidates), 1)
        self.assertEqual(candidates[0].pokemon_id, 25)
        self.assertGreaterEqual(candidates[0].confidence, 0.9)

    def test_committed_fixtures_pass_match_gate(self) -> None:
        result = validate_fixtures(
            PROJECT_ROOT / "data/dex.sqlite",
            PROJECT_ROOT / "fixtures/ocr/korean_cards.jsonl",
        )

        self.assertGreaterEqual(result["match_recall_at_3"], 0.9)
        self.assertEqual(result["failures"], [])

    def test_committed_dex_passes_strict_provenance_and_form_gate(self) -> None:
        result = validate(
            PROJECT_ROOT / "data/dex.sqlite",
            PROJECT_ROOT / "fixtures/ocr/korean_cards.jsonl",
            min_species=1025,
            min_fixture_count=30,
            require_nonbase_forms=True,
            require_evolution_conditions=True,
            require_provenance=True,
            require_gen1_visual_coverage=True,
            require_all_announced_generations=True,
            min_official_previews=3,
        )

        self.assertGreaterEqual(result["counts"]["species"], 1028)
        self.assertEqual(result["counts"]["canonical_species"], 1025)
        self.assertEqual(result["counts"]["official_previews"], 3)
        self.assertEqual(result["counts"]["generation_1_species"], 151)
        self.assertEqual(result["covered_generations"], list(range(1, 11)))
        self.assertEqual(
            result["counts"]["generation_1_visual_forms"],
            result["counts"]["generation_1_forms"],
        )
        self.assertGreaterEqual(result["counts"]["nonbase_forms"], 300)
        self.assertGreaterEqual(result["counts"]["evolution_conditions"], 500)
        self.assertEqual(result["orphan_foreign_keys"], 0)


if __name__ == "__main__":
    unittest.main()
