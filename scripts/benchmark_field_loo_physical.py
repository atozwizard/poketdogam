#!/usr/bin/env python3
"""Build leave-one-out physical field prototypes from licensed photos.

This measures how well open-license physical photos work as references without
contaminating the sample under test. Results are experiment-only until the
151/30/453 coverage gate is met.
"""

from __future__ import annotations

from array import array
from collections import defaultdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import argparse
import json
import math
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.vision.visual_matcher import MODEL_ID, VisualDexMatcher


def run_loo(
    *,
    db_path: Path,
    model_path: Path,
    manifest_path: Path,
    output_path: Path,
) -> dict[str, object]:
    items = [
        item
        for item in json.loads(manifest_path.read_text(encoding="utf-8")).get("items", [])
        if item.get("benchmark_eligible") is True
    ]
    matcher = VisualDexMatcher(db_path=db_path, model_path=model_path)
    embeddings: list[dict[str, object]] = []
    for item in items:
        image_bytes = (PROJECT_ROOT / item["local_path"]).read_bytes()
        vectors = matcher._embed_views(image_bytes, include_grid=False)
        if not vectors:
            continue
        embeddings.append(
            {
                "sample_id": str(item["source_id"])[:12],
                "pokemon_id": int(item["expected_pokemon_id"]),
                "creator": str(item["source_creator"]),
                "vector": vectors[0],
            }
        )

    hits_at_1 = 0
    hits_at_3 = 0
    cases = []
    for probe in embeddings:
        scored: list[tuple[float, int]] = []
        for ref in embeddings:
            if ref["sample_id"] == probe["sample_id"]:
                continue
            sim = sum(a * b for a, b in zip(probe["vector"], ref["vector"]))
            scored.append((sim, int(ref["pokemon_id"])))
        scored.sort(reverse=True)
        species: list[int] = []
        seen: set[int] = set()
        for _, pokemon_id in scored:
            if pokemon_id in seen:
                continue
            seen.add(pokemon_id)
            species.append(pokemon_id)
            if len(species) >= 3:
                break
        top1 = bool(species and species[0] == probe["pokemon_id"])
        top3 = probe["pokemon_id"] in species
        hits_at_1 += int(top1)
        hits_at_3 += int(top3)
        cases.append(
            {
                "sample_id": probe["sample_id"],
                "expected_pokemon_id": probe["pokemon_id"],
                "top1": top1,
                "top3": top3,
                "candidate_ids": species,
            }
        )

    total = max(1, len(embeddings))
    payload = {
        "schema_version": 1,
        "experiment": "licensed_field_photo_leave_one_out",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "model_id": MODEL_ID,
        "sample_count": len(embeddings),
        "species_count": len({item["pokemon_id"] for item in embeddings}),
        "creator_count": len({item["creator"] for item in embeddings}),
        "recall_at_1": round(hits_at_1 / total, 4),
        "recall_at_3": round(hits_at_3 / total, 4),
        "generation_wide_90_percent_claimable": False,
        "interpretation": (
            "LOO physical prototypes estimate an upper bound for species that already "
            "have licensed photos. They do not satisfy the 151/30/453 wild gate."
        ),
        "cases": cases,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--model-path", default="data/vision/mobilenet_v3_small.tflite")
    parser.add_argument("--manifest", default="data/raw/field_photos/manifest.json")
    parser.add_argument("--output", default="data/vision/field_loo_physical_experiment.json")
    args = parser.parse_args()
    result = run_loo(
        db_path=PROJECT_ROOT / args.db_path,
        model_path=PROJECT_ROOT / args.model_path,
        manifest_path=PROJECT_ROOT / args.manifest,
        output_path=PROJECT_ROOT / args.output,
    )
    print(json.dumps(
        {
            "sample_count": result["sample_count"],
            "recall_at_1": result["recall_at_1"],
            "recall_at_3": result["recall_at_3"],
            "generation_wide_90_percent_claimable": False,
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
