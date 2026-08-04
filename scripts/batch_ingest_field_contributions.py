#!/usr/bin/env python3
"""Batch-ingest contributor field photos from a CSV manifest.

CSV columns:
  image_path,pokemon_id,creator,license_code,license_url,landing_url,object_kind
"""

from __future__ import annotations

from pathlib import Path
import argparse
import csv
import json
import sys

from scripts.ingest_field_contribution import ingest_contribution


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def batch_ingest(
    *,
    csv_path: Path,
    output_dir: Path,
    manifest_path: Path,
    db_path: Path,
) -> dict[str, object]:
    results: list[dict[str, object]] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"image_path", "pokemon_id", "creator", "license_code", "license_url"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV must include columns: {sorted(required)}")
        for row in reader:
            image = Path(row["image_path"])
            if not image.is_absolute():
                image = (csv_path.parent / image).resolve()
            try:
                result = ingest_contribution(
                    image_path=image,
                    pokemon_id=int(row["pokemon_id"]),
                    creator=str(row["creator"]),
                    license_code=str(row["license_code"]),
                    license_url=str(row["license_url"]),
                    landing_url=str(row.get("landing_url") or f"file://{image}"),
                    object_kind=str(row.get("object_kind") or "figure_or_toy"),
                    output_dir=output_dir,
                    manifest_path=manifest_path,
                    db_path=db_path,
                )
            except Exception as exc:  # noqa: BLE001 - batch boundary
                result = {
                    "status": "error",
                    "image_path": str(image),
                    "error": str(exc),
                }
            results.append(result)
    ingested = sum(1 for item in results if item.get("status") == "ingested")
    duplicates = sum(1 for item in results if item.get("status") == "duplicate")
    errors = sum(1 for item in results if item.get("status") == "error")
    counts = {}
    if manifest_path.exists():
        counts = json.loads(manifest_path.read_text(encoding="utf-8")).get("counts") or {}
    return {
        "rows": len(results),
        "ingested": ingested,
        "duplicates": duplicates,
        "errors": errors,
        "manifest_counts": counts,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--output-dir", default="data/raw/field_photos/contributions")
    parser.add_argument("--manifest", default="data/raw/field_photos/contributions_manifest.json")
    parser.add_argument("--db-path", default="data/dex.sqlite")
    args = parser.parse_args()
    try:
        result = batch_ingest(
            csv_path=PROJECT_ROOT / args.csv,
            output_dir=PROJECT_ROOT / args.output_dir,
            manifest_path=PROJECT_ROOT / args.manifest,
            db_path=PROJECT_ROOT / args.db_path,
        )
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["errors"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
