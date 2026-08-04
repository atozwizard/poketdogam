#!/usr/bin/env python3
"""All-generation derived-image recognition benchmark.

Uses temporary PokéAPI sprite/artwork downloads (discarded after embed) as the
in-game recognition domain. Product certification uses the flat all-generation
ranking path; the generation-aided ranking is a laboratory diagnostic only.
Field-photo evidence is reported separately and never upgrades this benchmark
into a multi-media or physical-object certification.
"""

from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.vision.visual_matcher import MODEL_ID, VisualDexMatcher, _calibrate_similarity
from scripts.benchmark_visual_recognition import (
    SCENARIOS,
    _make_holdout_image,
    _rank,
)
from scripts.build_visual_index import _download_references, _reference_records


SPECIES_TARGET = 1025
MEDIA_KIND_TARGET = 4
TARGET_SPECIES_RECALL_AT_3 = 0.90
# Collector-president interim floor while Gen7–9 close the remaining gap to 90%.
PER_GENERATION_FLOOR = 0.85
PER_GENERATION_STRETCH = 0.90


def benchmark_universal_recognition(
    *,
    db_path: Path,
    cache_dir: Path,
    model_path: Path,
    output_path: Path,
    cert_path: Path,
    max_workers: int = 12,
    scenarios: tuple[str, ...] = SCENARIOS,
    base_forms_only: bool = True,
    generations: tuple[int, ...] = tuple(range(1, 10)),
) -> dict[str, object]:
    import numpy as np
    from PIL import Image

    records: list[dict[str, object]] = []
    for generation in generations:
        gen_records = _reference_records(cache_dir, db_path, generation=generation)
        if base_forms_only:
            gen_records = [item for item in gen_records if item.get("form_name") == "base"]
        records.extend(gen_records)
    # Holdout queries use one preferred source image per form.
    deduped: dict[str, dict[str, object]] = {}
    for record in records:
        deduped.setdefault(str(record["form_id"]), record)
    records = list(deduped.values())
    if not records:
        raise ValueError("no universal benchmark references found")

    matrices = {
        generation: _load_generation_matrix(db_path, generation=generation)
        for generation in generations
    }
    all_matrix, all_meta = _load_all_generation_matrix(db_path)
    matcher = VisualDexMatcher(db_path=db_path, model_path=model_path)
    cases: list[dict[str, object]] = []
    cross_cases: list[dict[str, object]] = []
    cross_by_generation: dict[int, list[dict[str, object]]] = defaultdict(list)
    latencies_ms: list[float] = []
    by_generation: dict[int, list[dict[str, object]]] = defaultdict(list)

    with tempfile.TemporaryDirectory(prefix="poketdogam-universal-bench-") as temp_dir:
        downloaded = _download_references(records, Path(temp_dir), max_workers=max_workers)
        total = len(downloaded) * len(scenarios)
        completed = 0
        for record in downloaded:
            source_path = Path(record["path"])
            generation = int(record["generation"])
            reference_matrix, reference_meta = matrices[generation]
            with Image.open(source_path) as source:
                rgba = source.convert("RGBA")
            for scenario in scenarios:
                image_bytes = _make_holdout_image(
                    rgba,
                    scenario=scenario,
                    seed_key=f"universal:{record['form_id']}:{scenario}",
                )
                started = time.perf_counter()
                queries = matcher._embed_views(image_bytes, include_grid=True)
                if queries:
                    query_matrix = np.asarray(queries, dtype=np.float32)
                    scores = (reference_matrix @ query_matrix.T).max(axis=1)
                    ranked_forms, ranked_species = _rank(scores, reference_meta)
                    cross_scores = (all_matrix @ query_matrix.T).max(axis=1)
                    _, cross_species = _rank(cross_scores, all_meta)
                else:
                    ranked_forms, ranked_species = [], []
                    cross_species = []
                elapsed_ms = (time.perf_counter() - started) * 1000
                latencies_ms.append(elapsed_ms)
                form_ids = [item["form_id"] for item in ranked_forms[:3]]
                pokemon_ids = [int(item["pokemon_id"]) for item in ranked_species[:3]]
                cross_ids = [int(item["pokemon_id"]) for item in cross_species[:3]]
                expected_form_id = str(record["form_id"])
                expected_pokemon_id = int(record["pokemon_id"])
                case = {
                    "media_kind": "in_game_transform",
                    "scenario": scenario,
                    "generation": generation,
                    "expected_form_id": expected_form_id,
                    "expected_pokemon_id": expected_pokemon_id,
                    "form_top1": bool(form_ids and form_ids[0] == expected_form_id),
                    "form_top3": expected_form_id in form_ids,
                    "species_top1": bool(
                        pokemon_ids and pokemon_ids[0] == expected_pokemon_id
                    ),
                    "species_top3": expected_pokemon_id in pokemon_ids,
                    "predicted_pokemon_ids": pokemon_ids,
                }
                cases.append(case)
                by_generation[generation].append(case)
                cross_case = {
                    **case,
                    "species_top1": bool(
                        cross_ids and cross_ids[0] == expected_pokemon_id
                    ),
                    "species_top3": expected_pokemon_id in cross_ids,
                    "form_top1": False,
                    "form_top3": False,
                }
                cross_cases.append(cross_case)
                cross_by_generation[generation].append(cross_case)
                completed += 1
                if completed % 100 == 0 or completed == total:
                    print(f"universal benchmarked {completed}/{total}", file=sys.stderr)

    corpus = _corpus_inventory(db_path)
    aggregate = _metrics(cases)
    cross_aggregate = _metrics(cross_cases)
    generation_metrics = {
        str(generation): _metrics(items)
        for generation, items in sorted(by_generation.items())
    }
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    result = {
        "schema_version": 1,
        "benchmark": "universal_all_generation_multi_media_recognition",
        "created_at": created_at,
        "model_id": MODEL_ID,
        "scope": {
            "generations": list(generations),
            "species_target": SPECIES_TARGET,
            "base_forms_only": base_forms_only,
            "query_form_count": len(records),
            "scenarios": list(scenarios),
            "recognition_mode": "visual_only_generation_scoped_index",
            "cross_generation_diagnostic": "visual_only_all_generation_index",
            "product_recognition_mode": "visual_only_all_generation_index",
            "evaluated_media_kinds": ["in_game_transform"],
            "media_kinds_authorized": [
                "in_game_sprite_or_artwork",
                "user_screenshot",
                "plush",
                "figure_or_toy",
                "card",
                "sticker",
                "goods",
            ],
            "official_media_retained_in_product": False,
            "raw_media_committed": False,
        },
        "corpus": corpus,
        "target": {
            "metric": "species_recall_at_3",
            "minimum": TARGET_SPECIES_RECALL_AT_3,
            "species": SPECIES_TARGET,
            "media_kinds": MEDIA_KIND_TARGET,
        },
        "aggregate": aggregate,
        "cross_generation_aggregate": cross_aggregate,
        "cross_generation_by_generation": {
            str(generation): _metrics(items)
            for generation, items in sorted(cross_by_generation.items())
        },
        "by_generation": generation_metrics,
        "latency_ms": {
            "p50": _percentile(latencies_ms, 0.50),
            "p95": _percentile(latencies_ms, 0.95),
        },
        "interpretation": (
            "In-game transform holdout over all Generation 1–9 base forms. "
            "The product does not know the target generation, so certification uses "
            "cross_generation_aggregate. aggregate and by_generation use a target-"
            "generation hint and are laboratory diagnostics only. Physical photos, "
            "cards, plush, and goods are not evaluated by this benchmark. Source "
            "images are temporary; product UI still ships zero official media."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    cert = _build_cert(result)
    cert_path.write_text(
        json.dumps(cert, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return cert


def _load_all_generation_matrix(db_path: Path):
    return _load_generation_matrix(db_path, generation=None)


def _load_generation_matrix(db_path: Path, *, generation: int | None):
    import numpy as np

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        if generation is None:
            rows = conn.execute(
                """
                select
                    v.reference_id,
                    v.form_id,
                    v.embedding_blob,
                    f.pokemon_id,
                    s.generation
                from visual_reference_embeddings v
                join pokemon_forms f on f.form_id = v.form_id
                join pokemon_species s on s.pokemon_id = f.pokemon_id
                where v.model_id = ?
                  and v.reference_kind = 'temporary_source_to_derived_embedding'
                  and s.generation between 1 and 9
                order by f.pokemon_id, f.form_name, v.reference_id
                """,
                (MODEL_ID,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                select
                    v.reference_id,
                    v.form_id,
                    v.embedding_blob,
                    f.pokemon_id,
                    s.generation
                from visual_reference_embeddings v
                join pokemon_forms f on f.form_id = v.form_id
                join pokemon_species s on s.pokemon_id = f.pokemon_id
                where v.model_id = ?
                  and v.reference_kind = 'temporary_source_to_derived_embedding'
                  and s.generation = ?
                order by f.pokemon_id, f.form_name, v.reference_id
                """,
                (MODEL_ID, generation),
            ).fetchall()
    if not rows:
        raise ValueError(f"visual reference index empty for generation={generation}")
    vectors = [
        np.frombuffer(row["embedding_blob"], dtype=np.float32).copy() for row in rows
    ]
    return np.stack(vectors), [
        {
            "reference_id": str(row["reference_id"]),
            "form_id": str(row["form_id"]),
            "pokemon_id": int(row["pokemon_id"]),
            "generation": int(row["generation"]),
        }
        for row in rows
    ]


def _corpus_inventory(db_path: Path) -> dict[str, object]:
    with closing(sqlite3.connect(db_path)) as conn:
        in_game_species = int(
            conn.execute(
                """
                select count(distinct f.pokemon_id)
                from visual_reference_embeddings v
                join pokemon_forms f on f.form_id = v.form_id
                join pokemon_species s on s.pokemon_id = f.pokemon_id
                where v.reference_kind = 'temporary_source_to_derived_embedding'
                  and s.generation between 1 and 9
                """
            ).fetchone()[0]
        )
        in_game_refs = int(
            conn.execute(
                """
                select count(*) from visual_reference_embeddings
                where reference_kind = 'temporary_source_to_derived_embedding'
                """
            ).fetchone()[0]
        )
        field_species = int(
            conn.execute(
                """
                select count(distinct f.pokemon_id)
                from visual_reference_embeddings v
                join pokemon_forms f on f.form_id = v.form_id
                where v.reference_kind = 'open_license_field_photo_derived'
                """
            ).fetchone()[0]
        )
        field_refs = int(
            conn.execute(
                """
                select count(*) from visual_reference_embeddings
                where reference_kind = 'open_license_field_photo_derived'
                """
            ).fetchone()[0]
        )

    manifest_path = PROJECT_ROOT / "data/raw/field_photos/manifest.json"
    object_kinds: dict[str, int] = {}
    creators = 0
    screenshots = 0
    if manifest_path.exists():
        items = json.loads(manifest_path.read_text(encoding="utf-8")).get("items") or []
        eligible = [item for item in items if item.get("benchmark_eligible") is True]
        creators = len({str(item.get("source_creator") or "").casefold() for item in eligible})
        for item in eligible:
            kind = str(item.get("object_kind") or "unknown")
            object_kinds[kind] = object_kinds.get(kind, 0) + 1
            tags = " ".join(str(tag) for tag in (item.get("source_tags") or []))
            blob = f"{item.get('source_title', '')} {tags} {item.get('discovery_query', '')}".casefold()
            if "screenshot" in blob or "game capture" in blob:
                screenshots += 1

    media_kinds = {"in_game_sprite_or_artwork"}
    if field_refs:
        media_kinds.add("open_license_field_photo")
    for kind in object_kinds:
        media_kinds.add(kind)
    if screenshots:
        media_kinds.add("user_screenshot")
    if object_kinds.get("plush"):
        media_kinds.add("plush")
    if object_kinds.get("card"):
        media_kinds.add("card")
    if any(key in object_kinds for key in ("figure_or_toy", "sticker", "goods")):
        media_kinds.update(
            key for key in object_kinds if key in {"figure_or_toy", "sticker", "goods"}
        )

    return {
        "in_game_species_count": in_game_species,
        "in_game_reference_count": in_game_refs,
        "field_species_count": field_species,
        "field_reference_count": field_refs,
        "field_creator_count": creators,
        "field_object_kind_counts": object_kinds,
        "media_kinds_present": sorted(media_kinds),
        "media_kind_count": len(media_kinds),
        "total_recognizable_samples": in_game_refs + field_refs,
    }


def _metrics(cases: list[dict[str, object]]) -> dict[str, object]:
    if not cases:
        return {
            "query_count": 0,
            "species_recall_at_1": 0.0,
            "species_recall_at_3": 0.0,
            "form_recall_at_1": 0.0,
            "form_recall_at_3": 0.0,
        }
    return {
        "query_count": len(cases),
        "species_recall_at_1": round(
            sum(1 for case in cases if case["species_top1"]) / len(cases), 4
        ),
        "species_recall_at_3": round(
            sum(1 for case in cases if case["species_top3"]) / len(cases), 4
        ),
        "form_recall_at_1": round(
            sum(1 for case in cases if case["form_top1"]) / len(cases), 4
        ),
        "form_recall_at_3": round(
            sum(1 for case in cases if case["form_top3"]) / len(cases), 4
        ),
    }


def _build_cert(benchmark: dict[str, object]) -> dict[str, object]:
    corpus = benchmark["corpus"]
    aggregate = benchmark["aggregate"]
    cross_aggregate = benchmark.get("cross_generation_aggregate") or {}
    generation_aided_recall = float(aggregate["species_recall_at_3"])
    product_recall = float(cross_aggregate.get("species_recall_at_3") or 0.0)
    species = int(corpus["in_game_species_count"])
    samples = int(cross_aggregate.get("query_count") or 0)
    scope = benchmark.get("scope") or {}
    evaluated_media_kinds = list(scope.get("evaluated_media_kinds") or [])
    evaluated_media_kind_count = len(evaluated_media_kinds)
    by_generation = benchmark.get("by_generation") or {}
    per_gen_recalls = {
        str(generation): float((metrics or {}).get("species_recall_at_3") or 0.0)
        for generation, metrics in by_generation.items()
    }
    below_floor = {
        generation: value
        for generation, value in per_gen_recalls.items()
        if value < PER_GENERATION_FLOOR
    }
    below_stretch = {
        generation: value
        for generation, value in per_gen_recalls.items()
        if value < PER_GENERATION_STRETCH
    }
    min_per_gen_recall = min(per_gen_recalls.values()) if per_gen_recalls else 0.0
    accuracy_progress = min(
        100.0,
        product_recall / TARGET_SPECIES_RECALL_AT_3 * 100.0,
    )
    coverage_progress = (
        min(
            species / SPECIES_TARGET,
            samples / SPECIES_TARGET,
            evaluated_media_kind_count / MEDIA_KIND_TARGET,
        )
        * 100.0
    )
    score = round(accuracy_progress * 0.7 + coverage_progress * 0.3, 1)
    certified = (
        score >= 95.0
        and product_recall >= TARGET_SPECIES_RECALL_AT_3
        and species >= SPECIES_TARGET
        and samples >= SPECIES_TARGET
        and evaluated_media_kind_count >= MEDIA_KIND_TARGET
    )
    return {
        "schema_version": 3,
        "certification": "product_open_search_derived_recognition",
        "created_at": benchmark["created_at"],
        "score": score,
        "target": 95.0,
        "certified": certified,
        # Compatibility field: from schema v3 onward this is always the actual
        # product path with no target-generation hint.
        "species_recall_at_3": product_recall,
        "product_open_search_species_recall_at_3": product_recall,
        "generation_scoped_lab_species_recall_at_3": generation_aided_recall,
        "generation_scoped_lab_gate_met": (
            generation_aided_recall >= TARGET_SPECIES_RECALL_AT_3
            and min_per_gen_recall >= PER_GENERATION_FLOOR
            and not below_floor
        ),
        "min_per_generation_species_recall_at_3": min_per_gen_recall,
        "per_generation_species_recall_at_3": per_gen_recalls,
        "weak_generations": below_stretch,
        "generations_below_floor": below_floor,
        "per_generation_stretch_met": not below_stretch,
        "covered_species": species,
        "recognizable_samples": samples,
        "evaluated_media_kind_count": evaluated_media_kind_count,
        "evaluated_media_kinds": evaluated_media_kinds,
        "corpus_media_kind_count": int(corpus["media_kind_count"]),
        "corpus_media_kinds_present": corpus["media_kinds_present"],
        "derived_reference_count": int(corpus["total_recognizable_samples"]),
        "requirements": {
            "species": SPECIES_TARGET,
            "samples": SPECIES_TARGET,
            "evaluated_media_kinds": MEDIA_KIND_TARGET,
            "top3_recall": TARGET_SPECIES_RECALL_AT_3,
            "per_generation_floor": PER_GENERATION_FLOOR,
            "per_generation_stretch": PER_GENERATION_STRETCH,
        },
        "gaps": {
            "species": max(0, SPECIES_TARGET - species),
            "samples": max(0, SPECIES_TARGET - samples),
            "evaluated_media_kinds": max(
                0,
                MEDIA_KIND_TARGET - evaluated_media_kind_count,
            ),
            "recall": max(
                0.0,
                round(TARGET_SPECIES_RECALL_AT_3 - product_recall, 4),
            ),
            "per_generation_to_floor": {
                generation: round(PER_GENERATION_FLOOR - value, 4)
                for generation, value in below_floor.items()
            },
            "per_generation_to_stretch": {
                generation: round(PER_GENERATION_STRETCH - value, 4)
                for generation, value in below_stretch.items()
            },
        },
        "benchmark_path": "data/vision/universal_benchmark.json",
        "field_pilot": {
            "species": corpus["field_species_count"],
            "samples": corpus["field_reference_count"],
            "creators": corpus["field_creator_count"],
        },
        "cross_generation_species_recall_at_3": product_recall,
        "interpretation": (
            "Certified only when the no-hint, flat all-generation product path reaches "
            f"Top-3 {TARGET_SPECIES_RECALL_AT_3:.0%} and at least "
            f"{MEDIA_KIND_TARGET} media kinds have actually been evaluated. "
            "Generation-scoped scores are laboratory diagnostics and corpus media-kind "
            "labels are coverage inventory, not accuracy evidence. Physical field "
            "accuracy remains a separate gate."
        ),
    }


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return round(ordered[index], 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--cache-dir", default="data/raw/pokeapi")
    parser.add_argument(
        "--model-path",
        default="data/vision/mobilenet_v3_small.tflite",
    )
    parser.add_argument(
        "--output-path",
        default="data/vision/universal_benchmark.json",
    )
    parser.add_argument(
        "--cert-path",
        default="data/vision/universal_recognition_cert.json",
    )
    parser.add_argument("--max-workers", type=int, default=12)
    parser.add_argument(
        "--scenarios",
        default="studio,camera,partial",
        help="Comma-separated holdout scenarios",
    )
    parser.add_argument("--include-alternate-forms", action="store_true")
    args = parser.parse_args()
    scenarios = tuple(
        part.strip() for part in args.scenarios.split(",") if part.strip()
    )
    cert = benchmark_universal_recognition(
        db_path=PROJECT_ROOT / args.db_path,
        cache_dir=PROJECT_ROOT / args.cache_dir,
        model_path=PROJECT_ROOT / args.model_path,
        output_path=PROJECT_ROOT / args.output_path,
        cert_path=PROJECT_ROOT / args.cert_path,
        max_workers=max(1, args.max_workers),
        scenarios=scenarios or SCENARIOS,
        base_forms_only=not args.include_alternate_forms,
    )
    print(json.dumps(cert, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
