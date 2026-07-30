from __future__ import annotations

import argparse
import json
from pathlib import Path


MIN_FORM_COUNT = 238
MIN_FORM_RECALL_AT_3 = 0.90
REQUIRED_SCENARIOS = {"studio", "camera", "partial"}


def validate_visual_benchmark(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"visual benchmark is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    scope = payload.get("scope") or {}
    aggregate = payload.get("aggregate") or {}
    by_scenario = payload.get("by_scenario") or {}

    form_count = int(scope.get("form_count") or 0)
    if form_count < MIN_FORM_COUNT:
        raise ValueError(f"visual benchmark form scope is incomplete: {form_count}")
    scenarios = set(scope.get("scenarios") or [])
    missing_scenarios = sorted(REQUIRED_SCENARIOS - scenarios)
    if missing_scenarios:
        raise ValueError(f"visual benchmark scenarios are missing: {missing_scenarios}")
    expected_queries = form_count * len(scenarios)
    query_count = int(aggregate.get("query_count") or 0)
    if query_count != expected_queries:
        raise ValueError(
            f"visual benchmark query scope mismatch: {query_count} != {expected_queries}"
        )

    failures: list[str] = []
    aggregate_recall = float(aggregate.get("form_recall_at_3") or 0.0)
    if aggregate_recall < MIN_FORM_RECALL_AT_3:
        failures.append(f"aggregate={aggregate_recall:.4f}")
    for scenario in sorted(REQUIRED_SCENARIOS):
        scenario_recall = float(
            (by_scenario.get(scenario) or {}).get("form_recall_at_3") or 0.0
        )
        if scenario_recall < MIN_FORM_RECALL_AT_3:
            failures.append(f"{scenario}={scenario_recall:.4f}")
    if failures:
        raise ValueError(
            "visual form recall@3 below 90% gate: " + ", ".join(failures)
        )
    if payload.get("passed") is not True:
        raise ValueError("visual benchmark did not record a passing result")
    baseline = (
        (payload.get("baseline_full_frame_only") or {}).get("aggregate") or {}
    )
    baseline_recall = float(baseline.get("form_recall_at_3") or 0.0)
    if baseline_recall >= aggregate_recall:
        raise ValueError(
            "visual benchmark must preserve a lower full-frame baseline for comparison"
        )

    excluded = set(scope.get("excludes") or [])
    if "user_camera_field_samples" not in excluded:
        raise ValueError("visual benchmark must disclose that field samples are excluded")
    return {
        "form_count": form_count,
        "query_count": query_count,
        "form_recall_at_3": aggregate_recall,
        "baseline_form_recall_at_3": baseline_recall,
        "scenario_form_recall_at_3": {
            scenario: float(by_scenario[scenario]["form_recall_at_3"])
            for scenario in sorted(REQUIRED_SCENARIOS)
        },
        "passed": True,
        "field_accuracy_claimed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="data/vision/benchmark.json")
    args = parser.parse_args()
    result = validate_visual_benchmark(Path(args.path))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
