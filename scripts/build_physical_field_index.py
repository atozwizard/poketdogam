#!/usr/bin/env python3
"""Embed licensed field photos as supplemental physical visual references.

Production scan can use these derived embeddings. The official field_benchmark
sprite path stays uncontaminated by filtering reference_kind during evaluation.
"""

from __future__ import annotations

from array import array
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
import argparse
import json
import math
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.vision.visual_matcher import MODEL_ID, VisualDexMatcher


PHYSICAL_KIND = "open_license_field_photo_derived"


def build_physical_field_index(
    *,
    db_path: Path,
    model_path: Path,
    attribution_path: Path,
    manifest_path: Path,
    generation_scope: int = 1,
) -> dict[str, object]:
    attribution_items = json.loads(attribution_path.read_text(encoding="utf-8")).get("items") or []
    manifest_items = [
        item
        for item in json.loads(manifest_path.read_text(encoding="utf-8")).get("items") or []
        if item.get("benchmark_eligible") is True
    ]
    by_landing = {str(item.get("source_landing_url") or ""): item for item in manifest_items}
    items: list[dict[str, object]] = []
    for attr in attribution_items:
        landing = str(attr.get("source_landing_url") or "")
        match = by_landing.get(landing)
        if match is None:
            continue
        items.append({**attr, "local_path": match["local_path"], "normalized_sha256": match.get("normalized_sha256")})
    if not items:
        raise ValueError("no attributed field photos with local paths to embed")

    matcher = VisualDexMatcher(db_path=db_path, model_path=model_path)
    built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows: list[dict[str, object]] = []
    with closing(sqlite3.connect(db_path)) as conn:
        form_by_species = {
            int(row[0]): str(row[1])
            for row in conn.execute(
                """
                select pokemon_id, form_id from pokemon_forms
                where form_name = 'base'
                """
            )
        }

    for item in items:
        pokemon_id = int(item["expected_pokemon_id"])
        form_id = form_by_species.get(pokemon_id)
        if not form_id:
            continue
        image_path = PROJECT_ROOT / str(item["local_path"])
        if not image_path.exists():
            continue
        vectors = matcher._embed_views(image_path.read_bytes(), include_grid=False)
        if not vectors:
            continue
        values = vectors[0]
        normalized = array("f", values)
        source_key = str(item.get("normalized_sha256") or item.get("source_landing_url"))
        reference_id = str(
            uuid5(
                NAMESPACE_URL,
                f"poketdogam:physical:{MODEL_ID}:{form_id}:{source_key}",
            )
        )
        rows.append(
            {
                "reference_id": reference_id,
                "form_id": form_id,
                "model_id": MODEL_ID,
                "embedding_blob": normalized.tobytes(),
                "dimension": len(normalized),
                "reference_kind": PHYSICAL_KIND,
                "source_name": "open_license_field_photo",
                "source_url_sha256": source_key[:64],
                "generation_scope": generation_scope,
                "created_at": built_at,
            }
        )

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("pragma foreign_keys = on")
        conn.execute(
            "delete from visual_reference_embeddings where reference_kind = ?",
            (PHYSICAL_KIND,),
        )
        columns = [
            "reference_id",
            "form_id",
            "model_id",
            "embedding_blob",
            "dimension",
            "reference_kind",
            "source_name",
            "source_url_sha256",
            "generation_scope",
            "created_at",
        ]
        conn.executemany(
            f"insert into visual_reference_embeddings ({','.join(columns)}) "
            f"values ({','.join('?' for _ in columns)})",
            [[row[column] for column in columns] for row in rows],
        )
        conn.commit()

    return {
        "model_id": MODEL_ID,
        "reference_kind": PHYSICAL_KIND,
        "embedded_count": len(rows),
        "species_count": len({row["form_id"] for row in rows}),
        "generation_wide_90_percent_claimable": False,
        "policy": "derived embeddings only; raw photos remain gitignored",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--model-path", default="data/vision/mobilenet_v3_small.tflite")
    parser.add_argument(
        "--attribution-path",
        default="data/vision/field_attribution.json",
    )
    parser.add_argument("--manifest-path", default="data/raw/field_photos/manifest.json")
    args = parser.parse_args()
    result = build_physical_field_index(
        db_path=PROJECT_ROOT / args.db_path,
        model_path=PROJECT_ROOT / args.model_path,
        attribution_path=PROJECT_ROOT / args.attribution_path,
        manifest_path=PROJECT_ROOT / args.manifest_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
