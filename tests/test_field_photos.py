from __future__ import annotations

import unittest
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
        self.assertLess(result["prototype_holdout_recall_at_3"], 0.90)


if __name__ == "__main__":
    unittest.main()
