#!/usr/bin/env python3
"""Collect Openverse photos only for Generation 1 species still missing from the field set."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import argparse
import json
import sqlite3
import sys

from scripts.collect_open_field_photos import collect_open_field_photos, PROJECT_ROOT


def missing_species_ids(db_path: Path, manifest_path: Path) -> set[int]:
    with closing(sqlite3.connect(db_path)) as conn:
        gen1 = {int(row[0]) for row in conn.execute(
            "select pokemon_id from pokemon_species where generation = 1"
        )}
    covered: set[int] = set()
    if manifest_path.exists():
        for item in json.loads(manifest_path.read_text(encoding="utf-8")).get("items") or []:
            if item.get("benchmark_eligible") or item.get("review_status") == "pending_visual_label_and_license_review":
                covered.add(int(item["expected_pokemon_id"]))
    return gen1 - covered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--manifest-path", default="data/raw/field_photos/manifest.json")
    parser.add_argument("--output-dir", default="data/raw/field_photos/images")
    parser.add_argument(
        "--summary-path",
        default="data/raw/field_photos/openverse_missing_species_summary.json",
    )
    parser.add_argument("--max-downloads", type=int, default=200)
    parser.add_argument("--max-per-species", type=int, default=2)
    parser.add_argument("--max-per-creator", type=int, default=2)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--allow-fan-pages", action="store_true", default=True)
    parser.add_argument("--no-fan-pages", action="store_false", dest="allow_fan_pages")
    parser.add_argument(
        "--license-type",
        default="all",
        choices=["modification", "commercial", "all"],
    )
    args = parser.parse_args()

    missing_before = missing_species_ids(
        PROJECT_ROOT / args.db_path,
        PROJECT_ROOT / args.manifest_path,
    )
    result = collect_open_field_photos(
        db_path=PROJECT_ROOT / args.db_path,
        output_dir=PROJECT_ROOT / args.output_dir,
        manifest_path=PROJECT_ROOT / args.manifest_path,
        summary_path=PROJECT_ROOT / args.summary_path,
        max_pages=args.max_pages,
        max_per_species=args.max_per_species,
        max_per_creator=args.max_per_creator,
        max_downloads=args.max_downloads,
        include_species_search=True,
        allow_fan_pages=args.allow_fan_pages,
        license_type=args.license_type,
        queries=(
            "Pokemon plush",
            "Pokemon figure",
            "Pokemon toy",
            "Pokemon TCG card",
            "Pokemon fan collection",
            "Pokemon merch",
        ),
    )
    missing_after = missing_species_ids(
        PROJECT_ROOT / args.db_path,
        PROJECT_ROOT / args.manifest_path,
    )
    result = {
        **result,
        "missing_species_before": len(missing_before),
        "missing_species_after_download": len(missing_after),
        "note": (
            "New downloads remain benchmark_eligible=false until "
            "review_field_photo_manifest.py approval."
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
