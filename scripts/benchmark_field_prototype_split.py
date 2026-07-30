from __future__ import annotations

from collections import defaultdict
from contextlib import closing
import argparse
import json
from pathlib import Path
import sqlite3
import statistics
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.vision.visual_matcher import MODEL_ID, VisualDexMatcher


TARGET_RECALL_AT_3 = 0.90


def benchmark_field_prototype_split(
    *,
    db_path: Path,
    model_path: Path,
    manifest_path: Path,
    output_path: Path,
) -> dict[str, object]:
    import numpy as np

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    eligible = [
        item
        for item in (manifest.get("items") or [])
        if item.get("benchmark_eligible") is True
    ]
    train, test = _split_by_species(eligible)
    if not train or not test:
        raise ValueError("field pilot needs at least two eligible images per species")

    official_matrix, official_meta = _official_references(db_path)
    matcher = VisualDexMatcher(db_path=db_path, model_path=model_path)
    prototype_vectors = []
    prototype_meta: list[dict[str, object]] = []
    for index, item in enumerate(train, start=1):
        image_bytes = (PROJECT_ROOT / str(item["local_path"])).read_bytes()
        views = matcher._embed_views(image_bytes, include_grid=True)
        for view_index, view in enumerate(views):
            prototype_vectors.append(np.asarray(view, dtype=np.float32))
            prototype_meta.append(
                {
                    "form_id": str(item["expected_form_id"]),
                    "pokemon_id": int(item["expected_pokemon_id"]),
                    "reference_kind": "open_license_field_train_prototype",
                    "source_id_hash": _source_hash(str(item["source_id"])),
                    "view_index": view_index,
                }
            )
        if index % 10 == 0 or index == len(train):
            print(f"embedded train prototypes {index}/{len(train)}", file=sys.stderr)

    prototype_matrix = np.stack(prototype_vectors)
    augmented_matrix = np.concatenate([official_matrix, prototype_matrix], axis=0)
    augmented_meta = [*official_meta, *prototype_meta]
    cases: list[dict[str, object]] = []
    latencies_ms: list[float] = []
    for index, item in enumerate(test, start=1):
        image_bytes = (PROJECT_ROOT / str(item["local_path"])).read_bytes()
        started = time.perf_counter()
        query_views = np.asarray(
            matcher._embed_views(image_bytes, include_grid=True),
            dtype=np.float32,
        )
        official_scores = (official_matrix @ query_views.T).max(axis=1)
        augmented_scores = (augmented_matrix @ query_views.T).max(axis=1)
        official_ids = _rank_species(official_scores, official_meta, limit=3)
        augmented_ids = _rank_species(augmented_scores, augmented_meta, limit=3)
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies_ms.append(elapsed_ms)
        expected_id = int(item["expected_pokemon_id"])
        cases.append(
            {
                "sample_id": _source_hash(str(item["source_id"])),
                "expected_pokemon_id": expected_id,
                "object_kind": str(item["object_kind"]),
                "creator_key": _source_hash(str(item["source_creator"])),
                "official_top1": bool(official_ids and official_ids[0] == expected_id),
                "official_top3": expected_id in official_ids,
                "augmented_top1": bool(augmented_ids and augmented_ids[0] == expected_id),
                "augmented_top3": expected_id in augmented_ids,
                "official_candidate_ids": official_ids,
                "augmented_candidate_ids": augmented_ids,
            }
        )
        if index % 10 == 0 or index == len(test):
            print(f"evaluated field holdout {index}/{len(test)}", file=sys.stderr)

    result = _summarize(
        train=train,
        test=test,
        cases=cases,
        prototype_count=len(prototype_meta),
        latencies_ms=latencies_ms,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def _split_by_species(
    items: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    groups: dict[int, list[dict[str, object]]] = defaultdict(list)
    for item in items:
        groups[int(item["expected_pokemon_id"])].append(item)
    train: list[dict[str, object]] = []
    test: list[dict[str, object]] = []
    for pokemon_id in sorted(groups):
        group = sorted(groups[pokemon_id], key=lambda item: str(item["source_id"]))
        if len(group) < 2:
            continue
        for index, item in enumerate(group):
            (test if index % 2 else train).append(item)
    return train, test


def _official_references(db_path: Path):
    import numpy as np

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select v.form_id, v.embedding_blob, f.pokemon_id
            from visual_reference_embeddings v
            join pokemon_forms f on f.form_id = v.form_id
            join pokemon_species s on s.pokemon_id = f.pokemon_id
            where v.model_id = ? and s.generation = 1
            order by f.pokemon_id, f.form_name, v.reference_id
            """,
            (MODEL_ID,),
        ).fetchall()
    vectors = [
        np.frombuffer(row["embedding_blob"], dtype=np.float32).copy()
        for row in rows
    ]
    return np.stack(vectors), [
        {
            "form_id": str(row["form_id"]),
            "pokemon_id": int(row["pokemon_id"]),
            "reference_kind": "official_artwork_derived",
        }
        for row in rows
    ]


def _rank_species(scores, metadata: list[dict[str, object]], *, limit: int) -> list[int]:
    best: dict[int, float] = {}
    for score, item in zip(scores, metadata):
        pokemon_id = int(item["pokemon_id"])
        best[pokemon_id] = max(float(score), best.get(pokemon_id, float("-inf")))
    return [
        pokemon_id
        for pokemon_id, _ in sorted(best.items(), key=lambda pair: -pair[1])[:limit]
    ]


def _summarize(
    *,
    train: list[dict[str, object]],
    test: list[dict[str, object]],
    cases: list[dict[str, object]],
    prototype_count: int,
    latencies_ms: list[float],
) -> dict[str, object]:
    official_top3 = _ratio(cases, "official_top3")
    augmented_top3 = _ratio(cases, "augmented_top3")
    train_creators = {str(item["source_creator"]) for item in train}
    test_creators = {str(item["source_creator"]) for item in test}
    independent_test = [
        item for item in test if str(item["source_creator"]) not in train_creators
    ]
    sorted_latency = sorted(latencies_ms)
    p95_index = max(0, min(len(sorted_latency) - 1, int(len(sorted_latency) * 0.95) - 1))
    return {
        "schema_version": 1,
        "benchmark": "open_license_field_prototype_holdout_experiment",
        "created_at": _utc_timestamp(),
        "scope": {
            "train_image_count": len(train),
            "test_image_count": len(test),
            "prototype_embedding_count": prototype_count,
            "covered_species_count": len(
                {int(item["expected_pokemon_id"]) for item in [*train, *test]}
            ),
            "train_creator_count": len(train_creators),
            "test_creator_count": len(test_creators),
            "creator_independent_test_count": len(independent_test),
            "raw_media_committed": False,
        },
        "split_policy": (
            "Within each species, source IDs are sorted and alternated train/test. "
            "No file or transformed duplicate crosses the split."
        ),
        "metrics": {
            "official_reference_species_recall_at_1": _ratio(cases, "official_top1"),
            "official_reference_species_recall_at_3": official_top3,
            "field_augmented_species_recall_at_1": _ratio(cases, "augmented_top1"),
            "field_augmented_species_recall_at_3": augmented_top3,
            "improvement_percentage_points_at_3": round(
                (augmented_top3 - official_top3) * 100,
                2,
            ),
        },
        "latency_ms": {
            "mean": round(statistics.mean(latencies_ms), 2),
            "p95": round(sorted_latency[p95_index], 2),
        },
        "sample_recall_target_met": augmented_top3 >= TARGET_RECALL_AT_3,
        "generation_wide_90_percent_claimable": False,
        "failure_samples": [
            {
                "sample_id": case["sample_id"],
                "expected_pokemon_id": case["expected_pokemon_id"],
                "augmented_candidate_ids": case["augmented_candidate_ids"],
            }
            for case in cases
            if not case["augmented_top3"]
        ][:50],
        "interpretation": (
            "This experiment estimates whether field-derived prototypes can close the "
            "domain gap. Most train/test images share one creator and object series, "
            "so even a passing pilot result is not Generation 1 generalization evidence."
        ),
    }


def _ratio(items: list[dict[str, object]], key: str) -> float:
    if not items:
        return 0.0
    return round(sum(bool(item[key]) for item in items) / len(items), 4)


def _source_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


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
        default="data/vision/field_prototype_experiment.json",
    )
    args = parser.parse_args()
    result = benchmark_field_prototype_split(
        db_path=PROJECT_ROOT / args.db_path,
        model_path=PROJECT_ROOT / args.model_path,
        manifest_path=PROJECT_ROOT / args.manifest_path,
        output_path=PROJECT_ROOT / args.output_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
