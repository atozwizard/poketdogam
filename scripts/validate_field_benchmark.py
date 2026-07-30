from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_RECALL_AT_3 = 0.90
GENERATION_WIDE_MINIMUM = {
    "species": 151,
    "creators": 30,
    "samples": 453,
}


def validate_field_benchmark(
    *,
    collection_path: Path,
    benchmark_path: Path,
    experiment_path: Path,
    attribution_path: Path,
) -> dict[str, object]:
    collection = _load_object(collection_path)
    benchmark = _load_object(benchmark_path)
    experiment = _load_object(experiment_path)
    attribution = _load_object(attribution_path)

    eligible_count = _positive_int(
        collection.get("benchmark_eligible_count"),
        "collection benchmark_eligible_count",
    )
    if collection.get("raw_media_committed") is not False:
        raise ValueError("field collection must not commit raw media")
    if int(collection.get("license_unverified_count", -1)) != 0:
        raise ValueError("every eligible field sample must have a verified license")
    if int(collection.get("covered_species_count", 0)) > 151:
        raise ValueError("Generation 1 field collection cannot exceed 151 species")

    attribution_items = attribution.get("items")
    if not isinstance(attribution_items, list):
        raise ValueError("field attribution items must be a list")
    if len(attribution_items) != eligible_count:
        raise ValueError(
            "field attribution count must equal benchmark-eligible sample count"
        )
    if attribution.get("raw_media_included") is not False:
        raise ValueError("field attribution artifact must not include raw media")
    for index, item in enumerate(attribution_items):
        if not isinstance(item, dict):
            raise ValueError(f"field attribution item {index} must be an object")
        for key in (
            "source_creator",
            "source_landing_url",
            "license_code",
            "license_url",
            "expected_pokemon_id",
            "object_kind",
        ):
            if not item.get(key):
                raise ValueError(f"field attribution item {index} missing {key}")
        if not str(item["source_landing_url"]).startswith("https://"):
            raise ValueError(f"field attribution item {index} has a non-HTTPS source")
        if not str(item["license_url"]).startswith("https://"):
            raise ValueError(f"field attribution item {index} has a non-HTTPS license")

    scope = _object(benchmark.get("scope"), "benchmark scope")
    aggregate = _object(benchmark.get("aggregate"), "benchmark aggregate")
    target = _object(benchmark.get("target"), "benchmark target")
    minimum_scope = _object(
        target.get("generation_wide_minimum_scope"),
        "benchmark generation-wide minimum scope",
    )
    if int(scope.get("sample_count", 0)) != eligible_count:
        raise ValueError("field benchmark sample count does not match collection")
    if scope.get("raw_media_committed") is not False:
        raise ValueError("field benchmark must not commit raw media")
    if scope.get("license_verified_for_every_sample") is not True:
        raise ValueError("field benchmark includes a license-unverified sample")
    if float(target.get("minimum", 0.0)) != TARGET_RECALL_AT_3:
        raise ValueError("field benchmark target must remain Top-3 recall >= 0.90")
    if {
        key: int(minimum_scope.get(key, 0))
        for key in GENERATION_WIDE_MINIMUM
    } != GENERATION_WIDE_MINIMUM:
        raise ValueError("field benchmark generation-wide coverage gate changed")

    recall = _ratio(
        aggregate.get("fused_species_recall_at_3"),
        "fused species recall@3",
    )
    sample_target_met = recall >= TARGET_RECALL_AT_3
    if benchmark.get("sample_recall_target_met") is not sample_target_met:
        raise ValueError("field benchmark sample target flag is inconsistent")
    expected_claimable = (
        sample_target_met
        and int(scope.get("covered_species_count", 0))
        >= GENERATION_WIDE_MINIMUM["species"]
        and int(scope.get("covered_creator_count", 0))
        >= GENERATION_WIDE_MINIMUM["creators"]
        and int(scope.get("sample_count", 0))
        >= GENERATION_WIDE_MINIMUM["samples"]
    )
    if benchmark.get("generation_wide_90_percent_claimable") is not expected_claimable:
        raise ValueError("field benchmark generation-wide claim flag is inconsistent")

    experiment_scope = _object(experiment.get("scope"), "experiment scope")
    experiment_metrics = _object(experiment.get("metrics"), "experiment metrics")
    experimental_recall = _ratio(
        experiment_metrics.get("field_augmented_species_recall_at_3"),
        "field-augmented species recall@3",
    )
    if experiment_scope.get("raw_media_committed") is not False:
        raise ValueError("field prototype experiment must not commit raw media")
    if (
        experiment.get("sample_recall_target_met")
        is not (experimental_recall >= TARGET_RECALL_AT_3)
    ):
        raise ValueError("field prototype experiment target flag is inconsistent")
    if experiment.get("generation_wide_90_percent_claimable") is not False:
        raise ValueError("narrow field prototype experiment cannot make a Gen1 claim")

    return {
        "passed": True,
        "eligible_sample_count": eligible_count,
        "covered_species_count": int(scope["covered_species_count"]),
        "covered_creator_count": int(scope["covered_creator_count"]),
        "production_path_recall_at_3": recall,
        "prototype_holdout_recall_at_3": experimental_recall,
        "generation_wide_90_percent_claimable": expected_claimable,
    }


def _load_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _object(payload, str(path))


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _positive_int(value: object, label: str) -> int:
    result = int(value or 0)
    if result <= 0:
        raise ValueError(f"{label} must be positive")
    return result


def _ratio(value: object, label: str) -> float:
    result = float(value or 0.0)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{label} must be between zero and one")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--collection-path",
        default="data/vision/field_collection.json",
    )
    parser.add_argument(
        "--benchmark-path",
        default="data/vision/field_benchmark.json",
    )
    parser.add_argument(
        "--experiment-path",
        default="data/vision/field_prototype_experiment.json",
    )
    parser.add_argument(
        "--attribution-path",
        default="data/vision/field_attribution.json",
    )
    args = parser.parse_args()
    result = validate_field_benchmark(
        collection_path=PROJECT_ROOT / args.collection_path,
        benchmark_path=PROJECT_ROOT / args.benchmark_path,
        experiment_path=PROJECT_ROOT / args.experiment_path,
        attribution_path=PROJECT_ROOT / args.attribution_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
