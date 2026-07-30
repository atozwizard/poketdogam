from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from io import BytesIO
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import sys
import tempfile
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.vision.visual_matcher import MODEL_ID, VisualDexMatcher, _calibrate_similarity
from scripts.build_visual_index import _download_references, _reference_records


SCENARIOS = ("studio", "camera", "partial")
TARGET_FORM_RECALL_AT_3 = 0.90


def benchmark_visual_recognition(
    *,
    db_path: Path,
    cache_dir: Path,
    model_path: Path,
    output_path: Path,
    generation: int = 1,
    max_workers: int = 10,
    limit: int | None = None,
) -> dict[str, object]:
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Run with `uv run --extra vision` for visual benchmarks") from exc

    records = _reference_records(cache_dir, db_path, generation=generation)
    if limit is not None:
        records = records[: max(1, limit)]
    if not records:
        raise ValueError(f"no benchmark references found for generation {generation}")

    reference_matrix, reference_meta = _load_reference_matrix(db_path, generation=generation)
    matcher = VisualDexMatcher(db_path=db_path, model_path=model_path)
    cases: list[dict[str, object]] = []
    latencies_ms: list[float] = []

    with tempfile.TemporaryDirectory(prefix="poketdogam-benchmark-") as temp_dir:
        downloaded = _download_references(
            records,
            Path(temp_dir),
            max_workers=max_workers,
        )
        total = len(downloaded) * len(SCENARIOS)
        completed = 0
        for record in downloaded:
            source_path = Path(record["path"])
            with Image.open(source_path) as source:
                rgba = source.convert("RGBA")
            for scenario in SCENARIOS:
                image_bytes = _make_holdout_image(
                    rgba,
                    scenario=scenario,
                    seed_key=f"{record['form_id']}:{scenario}",
                )
                started = time.perf_counter()
                queries = matcher._embed_views(image_bytes, include_grid=True)
                if queries:
                    query_matrix = np.asarray(queries, dtype=np.float32)
                    scores = (reference_matrix @ query_matrix.T).max(axis=1)
                    ranked_forms, ranked_species = _rank(
                        scores,
                        reference_meta,
                    )
                    baseline_scores = reference_matrix @ query_matrix[0]
                    baseline_forms, baseline_species = _rank(
                        baseline_scores,
                        reference_meta,
                    )
                else:
                    ranked_forms, ranked_species = [], []
                    baseline_forms, baseline_species = [], []
                elapsed_ms = (time.perf_counter() - started) * 1000
                latencies_ms.append(elapsed_ms)
                expected_form_id = str(record["form_id"])
                expected_pokemon_id = int(record["pokemon_id"])
                form_ids = [item["form_id"] for item in ranked_forms[:3]]
                pokemon_ids = [int(item["pokemon_id"]) for item in ranked_species[:3]]
                baseline_form_ids = [
                    item["form_id"] for item in baseline_forms[:3]
                ]
                baseline_pokemon_ids = [
                    int(item["pokemon_id"]) for item in baseline_species[:3]
                ]
                cases.append(
                    {
                        "scenario": scenario,
                        "expected_form_id": expected_form_id,
                        "expected_pokemon_id": expected_pokemon_id,
                        "form_top1": bool(form_ids and form_ids[0] == expected_form_id),
                        "form_top3": expected_form_id in form_ids,
                        "species_top1": bool(
                            pokemon_ids and pokemon_ids[0] == expected_pokemon_id
                        ),
                        "species_top3": expected_pokemon_id in pokemon_ids,
                        "baseline_form_top1": bool(
                            baseline_form_ids
                            and baseline_form_ids[0] == expected_form_id
                        ),
                        "baseline_form_top3": expected_form_id in baseline_form_ids,
                        "baseline_species_top1": bool(
                            baseline_pokemon_ids
                            and baseline_pokemon_ids[0] == expected_pokemon_id
                        ),
                        "baseline_species_top3": (
                            expected_pokemon_id in baseline_pokemon_ids
                        ),
                        "predicted_form_ids": form_ids,
                        "predicted_pokemon_ids": pokemon_ids,
                    }
                )
                completed += 1
                if completed % 50 == 0 or completed == total:
                    print(f"benchmarked {completed}/{total}", file=sys.stderr)

    result = _summarize(
        cases,
        generation=generation,
        form_count=len(records),
        reference_count=len(reference_meta),
        latencies_ms=latencies_ms,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def _load_reference_matrix(
    db_path: Path,
    *,
    generation: int,
):
    import numpy as np

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select
                v.reference_id,
                v.form_id,
                v.embedding_blob,
                f.pokemon_id
            from visual_reference_embeddings v
            join pokemon_forms f on f.form_id = v.form_id
            join pokemon_species s on s.pokemon_id = f.pokemon_id
            where v.model_id = ? and s.generation = ?
            order by f.pokemon_id, f.form_name, v.reference_id
            """,
            (MODEL_ID, generation),
        ).fetchall()
    if not rows:
        raise ValueError("visual reference index is empty")
    vectors = [
        np.frombuffer(row["embedding_blob"], dtype=np.float32).copy()
        for row in rows
    ]
    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1:
        raise ValueError(f"inconsistent embedding dimensions: {sorted(dimensions)}")
    return np.stack(vectors), [
        {
            "reference_id": str(row["reference_id"]),
            "form_id": str(row["form_id"]),
            "pokemon_id": int(row["pokemon_id"]),
        }
        for row in rows
    ]


def _rank(scores, metadata: list[dict[str, object]]):
    best_by_form: dict[str, dict[str, object]] = {}
    for score, item in zip(scores, metadata):
        similarity = float(score)
        confidence = _calibrate_similarity(similarity)
        if confidence < 0.08:
            continue
        form_id = str(item["form_id"])
        current = best_by_form.get(form_id)
        if current is None or confidence > float(current["confidence"]):
            best_by_form[form_id] = {
                "form_id": form_id,
                "pokemon_id": int(item["pokemon_id"]),
                "confidence": confidence,
            }
    ranked_forms = sorted(
        best_by_form.values(),
        key=lambda item: (-float(item["confidence"]), int(item["pokemon_id"]), str(item["form_id"])),
    )
    best_by_species: dict[int, dict[str, object]] = {}
    for item in ranked_forms:
        pokemon_id = int(item["pokemon_id"])
        if pokemon_id not in best_by_species:
            best_by_species[pokemon_id] = item
    return ranked_forms, list(best_by_species.values())


def _make_holdout_image(image, *, scenario: str, seed_key: str) -> bytes:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

    seed = int.from_bytes(
        hashlib.sha256(seed_key.encode("utf-8")).digest()[:8],
        "big",
    )
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    subject = image.crop(bbox) if bbox else image

    if scenario == "studio":
        canvas_size = (512, 512)
        scale = 0.70 + ((seed >> 3) % 7) / 100
        angle = -7 + ((seed >> 7) % 15)
        brightness = 0.92 + ((seed >> 12) % 15) / 100
        contrast = 0.94 + ((seed >> 17) % 15) / 100
        blur = 0.0
        occlusion = 0.0
    elif scenario == "camera":
        canvas_size = (640, 480)
        scale = 0.48 + ((seed >> 3) % 10) / 100
        angle = -12 + ((seed >> 7) % 25)
        brightness = 0.78 + ((seed >> 12) % 28) / 100
        contrast = 0.84 + ((seed >> 17) % 28) / 100
        blur = 0.45 + ((seed >> 22) % 45) / 100
        occlusion = 0.0
    elif scenario == "partial":
        canvas_size = (512, 512)
        scale = 0.78 + ((seed >> 3) % 8) / 100
        angle = -9 + ((seed >> 7) % 19)
        brightness = 0.88 + ((seed >> 12) % 19) / 100
        contrast = 0.90 + ((seed >> 17) % 22) / 100
        blur = 0.25
        occlusion = 0.08 + ((seed >> 22) % 5) / 100
    else:
        raise ValueError(f"unknown scenario: {scenario}")

    subject = _adjust_rgba(
        subject,
        brightness=brightness,
        contrast=contrast,
    )
    max_width = int(canvas_size[0] * scale)
    max_height = int(canvas_size[1] * scale)
    subject.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    subject = subject.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )

    base_color = (
        40 + (seed % 176),
        40 + ((seed >> 8) % 176),
        40 + ((seed >> 16) % 176),
    )
    canvas = Image.new("RGB", canvas_size, base_color)
    noise = Image.effect_noise(canvas_size, 18).convert("RGB")
    canvas = Image.blend(canvas, noise, 0.055 if scenario != "studio" else 0.025)
    max_x = max(0, canvas.width - subject.width)
    max_y = max(0, canvas.height - subject.height)
    offset_x = int(max_x * (0.36 + ((seed >> 25) % 29) / 100))
    offset_y = int(max_y * (0.31 + ((seed >> 31) % 31) / 100))
    canvas.paste(subject, (offset_x, offset_y), subject)

    if occlusion:
        draw = ImageDraw.Draw(canvas)
        width = max(12, int(subject.width * occlusion))
        left = offset_x + int(subject.width * (0.15 + ((seed >> 37) % 45) / 100))
        top = offset_y + int(subject.height * 0.62)
        draw.rounded_rectangle(
            (left, top, left + width, top + int(subject.height * 0.22)),
            radius=8,
            fill=tuple(max(0, channel - 20) for channel in base_color),
        )
    if blur:
        canvas = canvas.filter(ImageFilter.GaussianBlur(radius=blur))

    output = BytesIO()
    quality = 76 if scenario == "camera" else 86
    canvas.save(output, format="JPEG", quality=quality, optimize=True)
    return output.getvalue()


def _adjust_rgba(image, *, brightness: float, contrast: float):
    from PIL import Image, ImageEnhance

    alpha = image.getchannel("A")
    rgb = Image.new("RGB", image.size, "white")
    rgb.paste(image.convert("RGB"), mask=alpha)
    rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    adjusted = rgb.convert("RGBA")
    adjusted.putalpha(alpha)
    return adjusted


def _summarize(
    cases: list[dict[str, object]],
    *,
    generation: int,
    form_count: int,
    reference_count: int,
    latencies_ms: list[float],
) -> dict[str, object]:
    by_scenario: dict[str, list[dict[str, object]]] = defaultdict(list)
    for case in cases:
        by_scenario[str(case["scenario"])].append(case)

    def metrics(items: list[dict[str, object]]) -> dict[str, object]:
        total = len(items)
        return {
            "query_count": total,
            "form_recall_at_1": _ratio(items, "form_top1"),
            "form_recall_at_3": _ratio(items, "form_top3"),
            "species_recall_at_1": _ratio(items, "species_top1"),
            "species_recall_at_3": _ratio(items, "species_top3"),
        }

    aggregate = metrics(cases)
    baseline_aggregate = _baseline_metrics(cases)
    failures = [
        {
            "scenario": item["scenario"],
            "expected_form_id": item["expected_form_id"],
            "expected_pokemon_id": item["expected_pokemon_id"],
            "predicted_form_ids": item["predicted_form_ids"],
            "predicted_pokemon_ids": item["predicted_pokemon_ids"],
        }
        for item in cases
        if not item["form_top3"]
    ][:50]
    sorted_latency = sorted(latencies_ms)
    p95_index = max(0, min(len(sorted_latency) - 1, int(len(sorted_latency) * 0.95) - 1))
    scenario_metrics = {
        scenario: metrics(items)
        for scenario, items in sorted(by_scenario.items())
    }
    baseline_scenario_metrics = {
        scenario: _baseline_metrics(items)
        for scenario, items in sorted(by_scenario.items())
    }
    passed = (
        float(aggregate["form_recall_at_3"]) >= TARGET_FORM_RECALL_AT_3
        and all(
            float(item["form_recall_at_3"]) >= TARGET_FORM_RECALL_AT_3
            for item in scenario_metrics.values()
        )
    )
    return {
        "schema_version": 1,
        "benchmark": "generation_1_transformed_reference_holdout",
        "scope": {
            "generation": generation,
            "form_count": form_count,
            "scenarios": list(SCENARIOS),
            "recognition_mode": "visual_only",
            "dataset_kind": "synthetic_transforms_of_temporary_indirect_reference_images",
            "excludes": [
                "physical_plush_photos",
                "user_camera_field_samples",
                "official_product_media_retention",
            ],
        },
        "model_id": MODEL_ID,
        "reference_count": reference_count,
        "target": {
            "metric": "form_recall_at_3",
            "minimum": TARGET_FORM_RECALL_AT_3,
            "applies_to": "aggregate_and_each_scenario",
        },
        "aggregate": aggregate,
        "by_scenario": scenario_metrics,
        "baseline_full_frame_only": {
            "aggregate": baseline_aggregate,
            "by_scenario": baseline_scenario_metrics,
        },
        "improvement_percentage_points": {
            "form_recall_at_1": round(
                (
                    float(aggregate["form_recall_at_1"])
                    - float(baseline_aggregate["form_recall_at_1"])
                )
                * 100,
                2,
            ),
            "form_recall_at_3": round(
                (
                    float(aggregate["form_recall_at_3"])
                    - float(baseline_aggregate["form_recall_at_3"])
                )
                * 100,
                2,
            ),
        },
        "latency_ms": {
            "mean": round(statistics.mean(latencies_ms), 2) if latencies_ms else 0.0,
            "p95": round(sorted_latency[p95_index], 2) if sorted_latency else 0.0,
        },
        "passed": passed,
        "failure_count": sum(1 for item in cases if not item["form_top3"]),
        "failure_samples": failures,
        "interpretation": (
            "This gate measures transformed indirect reference images. "
            "It does not establish 90% accuracy on physical toys, cards, or field camera photos."
        ),
    }


def _ratio(items: list[dict[str, object]], key: str) -> float:
    if not items:
        return 0.0
    return round(sum(bool(item[key]) for item in items) / len(items), 4)


def _baseline_metrics(items: list[dict[str, object]]) -> dict[str, object]:
    return {
        "query_count": len(items),
        "form_recall_at_1": _ratio(items, "baseline_form_top1"),
        "form_recall_at_3": _ratio(items, "baseline_form_top3"),
        "species_recall_at_1": _ratio(items, "baseline_species_top1"),
        "species_recall_at_3": _ratio(items, "baseline_species_top3"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--cache-dir", default="data/raw/pokeapi")
    parser.add_argument("--model-path", default="data/vision/mobilenet_v3_small.tflite")
    parser.add_argument("--output-path", default="data/vision/benchmark.json")
    parser.add_argument("--generation", type=int, default=1)
    parser.add_argument("--max-workers", type=int, default=10)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    result = benchmark_visual_recognition(
        db_path=PROJECT_ROOT / args.db_path,
        cache_dir=PROJECT_ROOT / args.cache_dir,
        model_path=PROJECT_ROOT / args.model_path,
        output_path=PROJECT_ROOT / args.output_path,
        generation=args.generation,
        max_workers=args.max_workers,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
