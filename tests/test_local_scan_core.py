# Run: python -m unittest tests/test_local_scan_core.py
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.agents.pokedex_agent.tools.tool_local_dex import LocalDexStore
from scripts.build_local_dex.build import build_local_dex
from scripts.build_local_dex.validate_dex import validate_fixtures


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LocalScanCoreTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
