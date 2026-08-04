from __future__ import annotations

from collections import defaultdict
import argparse
import json
from pathlib import Path
import statistics
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.tools.tool_local_dex import LocalDexStore
from app.agents.pokedex_agent.tools.tool_ocr_ondevice import extract_ondevice_text
from app.vision.fusion import fuse_candidates
from app.vision.visual_matcher import VisualDexMatcher


TARGET_RECALL_AT_3 = 0.90


def benchmark_field_photos(
    *,
    db_path: Path,
    model_path: Path,
    manifest_path: Path,
    output_path: Path,
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = [
        item
        for item in (manifest.get("items") or [])
        if item.get("benchmark_eligible") is True
    ]
    if not items:
        raise ValueError("field manifest has no benchmark-eligible items")

    matcher = VisualDexMatcher(db_path=db_path, model_path=model_path)
    store = LocalDexStore(db_path)
    cases: list[dict[str, object]] = []
    latencies_ms: list[float] = []
    for index, item in enumerate(items, start=1):
        image_path = PROJECT_ROOT / str(item["local_path"])
        image_bytes = image_path.read_bytes()
        started = time.perf_counter()
        visual, raw_visual = matcher.match_with_diagnostics(
            image_bytes,
            top_k=5,
            include_physical=False,
        )
        ocr = extract_ondevice_text(
            image_bytes,
            image_path.name,
            "image/jpeg",
        )
        ocr_candidates = store.match_name(str(ocr.get("text") or ""), top_k=5)
        fused = fuse_candidates(ocr_candidates, visual, top_k=3)
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies_ms.append(elapsed_ms)

        expected_id = int(item["expected_pokemon_id"])
        visual_ids = _unique_species_ids(visual, limit=3)
        raw_visual_ids = _unique_raw_species_ids(raw_visual, limit=3)
        fused_ids = _unique_species_ids(fused, limit=3)
        cases.append(
            {
                "sample_id": str(item["source_id"])[:12],
                "expected_pokemon_id": expected_id,
                "object_kind": str(item["object_kind"]),
                "creator_key": _creator_key(str(item["source_creator"])),
                "visual_top1": bool(visual_ids and visual_ids[0] == expected_id),
                "visual_top3": expected_id in visual_ids,
                "raw_visual_top1": bool(
                    raw_visual_ids and raw_visual_ids[0] == expected_id
                ),
                "raw_visual_top3": expected_id in raw_visual_ids,
                "fused_top1": bool(fused_ids and fused_ids[0] == expected_id),
                "fused_top3": expected_id in fused_ids,
                "visual_candidate_ids": visual_ids,
                "raw_visual_candidate_ids": raw_visual_ids,
                "raw_visual_similarities": [
                    float(candidate["similarity"]) for candidate in raw_visual[:3]
                ],
                "fused_candidate_ids": fused_ids,
                "ocr_engine": str(ocr.get("engine") or "unknown"),
                "ocr_character_count": len(str(ocr.get("text") or "")),
                "latency_ms": round(elapsed_ms, 2),
            }
        )
        if index % 10 == 0 or index == len(items):
            print(f"field benchmark {index}/{len(items)}", file=sys.stderr)

    result = _summarize(cases, manifest=manifest, latencies_ms=latencies_ms)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def _unique_species_ids(candidates, *, limit: int) -> list[int]:
    result: list[int] = []
    for candidate in candidates:
        pokemon_id = int(candidate.pokemon_id or 0)
        if pokemon_id and pokemon_id not in result:
            result.append(pokemon_id)
        if len(result) >= limit:
            break
    return result


def _unique_raw_species_ids(
    candidates: list[dict[str, object]],
    *,
    limit: int,
) -> list[int]:
    result: list[int] = []
    for candidate in candidates:
        pokemon_id = int(candidate["pokemon_id"])
        if pokemon_id not in result:
            result.append(pokemon_id)
        if len(result) >= limit:
            break
    return result


def _creator_key(creator: str) -> str:
    import hashlib

    return hashlib.sha256(creator.encode("utf-8")).hexdigest()[:12]


def _summarize(
    cases: list[dict[str, object]],
    *,
    manifest: dict[str, object],
    latencies_ms: list[float],
) -> dict[str, object]:
    by_kind: dict[str, list[dict[str, object]]] = defaultdict(list)
    by_creator: dict[str, list[dict[str, object]]] = defaultdict(list)
    for case in cases:
        by_kind[str(case["object_kind"])].append(case)
        by_creator[str(case["creator_key"])].append(case)

    aggregate = _metrics(cases)
    species_count = len({int(case["expected_pokemon_id"]) for case in cases})
    creator_count = len(by_creator)
    sample_target_met = float(aggregate["fused_species_recall_at_3"]) >= TARGET_RECALL_AT_3
    generation_wide_claimable = (
        sample_target_met
        and species_count == 151
        and creator_count >= 30
        and len(cases) >= 453
    )
    sorted_latency = sorted(latencies_ms)
    p95_index = max(0, min(len(sorted_latency) - 1, int(len(sorted_latency) * 0.95) - 1))
    failures = [
        {
            "sample_id": case["sample_id"],
            "expected_pokemon_id": case["expected_pokemon_id"],
            "object_kind": case["object_kind"],
            "visual_candidate_ids": case["visual_candidate_ids"],
            "raw_visual_candidate_ids": case["raw_visual_candidate_ids"],
            "fused_candidate_ids": case["fused_candidate_ids"],
        }
        for case in cases
        if not case["fused_top3"]
    ][:50]
    return {
        "schema_version": 1,
        "benchmark": "open_license_user_photography_field_pilot",
        "created_at": _utc_timestamp(),
        "scope": {
            "sample_count": len(cases),
            "covered_species_count": species_count,
            "covered_creator_count": creator_count,
            "generation_1_species_target": 151,
            "raw_media_committed": False,
            "license_verified_for_every_sample": all(
                bool((item.get("license_review") or {}).get("verified"))
                for item in manifest["items"]
                if item.get("benchmark_eligible") is True
            ),
        },
        "target": {
            "metric": "fused_species_recall_at_3",
            "minimum": TARGET_RECALL_AT_3,
            "generation_wide_minimum_scope": {
                "species": 151,
                "creators": 30,
                "samples": 453,
            },
        },
        "aggregate": aggregate,
        "by_object_kind": {
            kind: _metrics(items)
            for kind, items in sorted(by_kind.items())
        },
        "by_creator": {
            creator: _metrics(items)
            for creator, items in sorted(by_creator.items())
        },
        "latency_ms": {
            "mean": round(statistics.mean(latencies_ms), 2),
            "p95": round(sorted_latency[p95_index], 2),
        },
        "sample_recall_target_met": sample_target_met,
        "generation_wide_90_percent_claimable": generation_wide_claimable,
        "failure_count": len([case for case in cases if not case["fused_top3"]]),
        "failure_samples": failures,
        "interpretation": (
            "This is a narrow field pilot. Results are dominated by one creator and "
            "cannot establish Generation 1 field accuracy until the declared species, "
            "creator, and sample coverage gates are met."
        ),
    }


def _metrics(items: list[dict[str, object]]) -> dict[str, object]:
    return {
        "sample_count": len(items),
        "visual_species_recall_at_1": _ratio(items, "visual_top1"),
        "visual_species_recall_at_3": _ratio(items, "visual_top3"),
        "raw_visual_species_recall_at_1": _ratio(items, "raw_visual_top1"),
        "raw_visual_species_recall_at_3": _ratio(items, "raw_visual_top3"),
        "fused_species_recall_at_1": _ratio(items, "fused_top1"),
        "fused_species_recall_at_3": _ratio(items, "fused_top3"),
    }


def _ratio(items: list[dict[str, object]], key: str) -> float:
    if not items:
        return 0.0
    return round(sum(bool(item[key]) for item in items) / len(items), 4)


def _utc_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--model-path", default="data/vision/mobilenet_v3_small.tflite")
    parser.add_argument(
        "--manifest-path",
        default="data/raw/field_photos/manifest.json",
    )
    parser.add_argument(
        "--output-path",
        default="data/vision/field_benchmark.json",
    )
    args = parser.parse_args()
    result = benchmark_field_photos(
        db_path=PROJECT_ROOT / args.db_path,
        model_path=PROJECT_ROOT / args.model_path,
        manifest_path=PROJECT_ROOT / args.manifest_path,
        output_path=PROJECT_ROOT / args.output_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
