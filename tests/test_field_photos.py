from __future__ import annotations

import json
import unittest
from contextlib import closing
from pathlib import Path

from scripts.collect_open_field_photos import (
    _candidate_from_result,
    _detect_species,
    _species_aliases,
)
from scripts.validate_field_benchmark import validate_field_benchmark


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def species(pokemon_id: int, name: str) -> dict[str, object]:
    return {
        "pokemon_id": pokemon_id,
        "name_en": name,
        "form_id": name.casefold().replace(" ", "-"),
        "aliases": _species_aliases(name),
    }


class FieldPhotoCollectionTest(unittest.TestCase):
    def test_species_detection_requires_a_token_boundary(self) -> None:
        scope = [species(25, "Pikachu"), species(26, "Raichu")]

        self.assertEqual(
            [item["pokemon_id"] for item in _detect_species("pikachu plush", scope)],
            [25],
        )
        self.assertEqual(_detect_species("pikachus plush", scope), [])

    def test_ambiguous_or_person_photo_is_not_a_candidate(self) -> None:
        scope = [species(1, "Bulbasaur"), species(25, "Pikachu")]
        base = {
            "id": "sample",
            "url": "https://images.example.test/sample.jpg",
            "foreign_landing_url": "https://example.test/photo",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "license": "by",
            "license_version": "4.0",
            "creator": "Photographer",
            "title": "Bulbasaur and Pikachu plush toys",
            "tags": [],
            "width": 800,
            "height": 800,
        }

        self.assertIsNone(
            _candidate_from_result(base, species=scope, query="Pokemon plush")
        )
        person = {**base, "title": "Child holding a Bulbasaur plush"}
        self.assertIsNone(
            _candidate_from_result(person, species=scope, query="Pokemon plush")
        )

    def test_fan_page_collection_photo_is_allowed(self) -> None:
        scope = [species(1, "Bulbasaur"), species(25, "Pikachu")]
        multi = {
            "id": "fan-multi",
            "url": "https://images.example.test/fan.jpg",
            "foreign_landing_url": "https://fanpage.example.test/my-pokemon-collection",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "license": "by",
            "license_version": "4.0",
            "creator": "Fan Collector",
            "title": "Bulbasaur and Pikachu fan collection shelf",
            "tags": [{"name": "pokemon"}, {"name": "collection"}],
            "width": 800,
            "height": 800,
        }
        candidate = _candidate_from_result(
            multi,
            species=scope,
            query="Pokemon fan collection",
            allow_fan_pages=True,
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertTrue(candidate["fan_page_context"])
        self.assertEqual(candidate["expected_pokemon_id"], 1)
        self.assertIn("multi_species_primary", str(candidate["label_basis"]))

        child = {
            **multi,
            "id": "fan-child",
            "title": "Child holding a Bulbasaur plush in my collection",
        }
        self.assertIsNone(
            _candidate_from_result(
                child,
                species=scope,
                query="Pokemon fan collection",
                allow_fan_pages=True,
            )
        )

    def test_name_band_crop_targets_card_title_region(self) -> None:
        from app.agents.pokedex_agent.tools.tool_ocr_ondevice import name_band_crop_box

        box = name_band_crop_box(1000, 620)
        self.assertEqual(box["left"], 100)
        self.assertEqual(box["top"], 50)
        self.assertEqual(box["width"], 800)
        self.assertEqual(box["height"], 112)

    def test_committed_field_evidence_is_consistent_and_non_claiming(self) -> None:
        result = validate_field_benchmark(
            collection_path=PROJECT_ROOT / "data/vision/field_collection.json",
            benchmark_path=PROJECT_ROOT / "data/vision/field_benchmark.json",
            experiment_path=(
                PROJECT_ROOT / "data/vision/field_prototype_experiment.json"
            ),
            attribution_path=PROJECT_ROOT / "data/vision/field_attribution.json",
        )

        self.assertTrue(result["passed"])
        self.assertFalse(result["generation_wide_90_percent_claimable"])
        self.assertLess(result["production_path_recall_at_3"], 0.90)
        self.assertLess(result["covered_species_count"], 1025)

    def test_physical_loo_shows_path_but_does_not_claim_generation_wide(self) -> None:
        loo_path = PROJECT_ROOT / "data/vision/field_loo_physical_experiment.json"
        self.assertTrue(loo_path.exists())
        payload = json.loads(loo_path.read_text(encoding="utf-8"))
        self.assertFalse(payload["generation_wide_90_percent_claimable"])
        self.assertGreater(payload["recall_at_3"], 0.0)
        self.assertLess(payload["species_count"], 1025)

    def test_physical_field_refs_are_embedded_for_product_scan(self) -> None:
        import sqlite3

        with closing(sqlite3.connect(PROJECT_ROOT / "data/dex.sqlite")) as conn:
            count = int(
                conn.execute(
                    "select count(*) from visual_reference_embeddings "
                    "where reference_kind = 'open_license_field_photo_derived'"
                ).fetchone()[0]
            )
        self.assertGreaterEqual(count, 91)

    def test_field_coverage_gap_export_lists_missing_species(self) -> None:
        from scripts.export_field_coverage_gap import export_gap

        result = export_gap(
            db_path=PROJECT_ROOT / "data/dex.sqlite",
            manifest_path=PROJECT_ROOT / "data/raw/field_photos/manifest.json",
            json_out=PROJECT_ROOT / "data/vision/field_coverage_gap.json",
            csv_out=PROJECT_ROOT / "data/vision/field_coverage_gap.csv",
        )
        self.assertGreaterEqual(result["in_game_embedded_species"], 1025)
        self.assertGreaterEqual(result["covered_species"], 28)
        self.assertLess(result["covered_species"], 1025)
        payload = json.loads(
            (PROJECT_ROOT / "data/vision/field_coverage_gap.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["targets"]["species"], 1025)
        self.assertGreaterEqual(payload["current"]["in_game_embedded_species"], 1025)
        self.assertIn("plush", payload["current"]["object_kind_counts"])


if __name__ == "__main__":
    unittest.main()
