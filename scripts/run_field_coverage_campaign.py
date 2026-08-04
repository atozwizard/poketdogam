#!/usr/bin/env python3
"""Run the collector-president field coverage campaign.

1. Export Gen1–9 field gaps
2. Collect open-license merch/screenshot candidates for missing field species
3. Print the next contributor priority slice
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.collect_open_field_photos import collect_open_field_photos
from scripts.export_field_coverage_gap import export_gap


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-downloads", type=int, default=150)
    parser.add_argument("--max-per-species", type=int, default=2)
    parser.add_argument("--max-per-creator", type=int, default=3)
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--priority-limit", type=int, default=40)
    parser.add_argument(
        "--species-search",
        action="store_true",
        help="Also run per-species Openverse queries (slow for 1025 species)",
    )
    parser.add_argument("--skip-collect", action="store_true")
    args = parser.parse_args()

    gap = export_gap(
        db_path=PROJECT_ROOT / "data/dex.sqlite",
        manifest_path=PROJECT_ROOT / "data/raw/field_photos/manifest.json",
        json_out=PROJECT_ROOT / "data/vision/field_coverage_gap.json",
        csv_out=PROJECT_ROOT / "data/vision/field_coverage_gap.csv",
    )
    collect_summary: dict[str, object] | None = None
    if not args.skip_collect:
        collect_summary = collect_open_field_photos(
            db_path=PROJECT_ROOT / "data/dex.sqlite",
            output_dir=PROJECT_ROOT / "data/raw/field_photos/images",
            manifest_path=PROJECT_ROOT / "data/raw/field_photos/manifest.json",
            summary_path=PROJECT_ROOT
            / "data/raw/field_photos/campaign_collection_summary.json",
            max_pages=max(1, args.max_pages),
            max_per_species=max(1, args.max_per_species),
            max_per_creator=max(1, args.max_per_creator),
            max_downloads=max(1, args.max_downloads),
            include_species_search=args.species_search,
            allow_fan_pages=True,
            allow_screenshots=True,
            all_generations=True,
            license_type="all",
            require_photograph_category=False,
        )
        gap = export_gap(
            db_path=PROJECT_ROOT / "data/dex.sqlite",
            manifest_path=PROJECT_ROOT / "data/raw/field_photos/manifest.json",
            json_out=PROJECT_ROOT / "data/vision/field_coverage_gap.json",
            csv_out=PROJECT_ROOT / "data/vision/field_coverage_gap.csv",
        )

    payload = json.loads(
        (PROJECT_ROOT / "data/vision/field_coverage_gap.json").read_text(encoding="utf-8")
    )
    missing = payload.get("missing_species") or []
    priority = [
        row
        for row in missing
        if row.get("status") == "missing" or row.get("status") == "in_game_only"
    ][: max(1, args.priority_limit)]
    report = {
        "campaign": "collector_president_field_coverage",
        "gap": gap,
        "collection": collect_summary,
        "next_contributor_targets": priority,
        "next_actions": [
            "Review new downloads with scripts/review_field_photo_manifest.py",
            "Reject privacy/mislabels, then rebuild_wild_accuracy_artifacts.sh",
            "For stubborn gaps, ingest owner-granted photos via "
            "scripts/ingest_field_contribution.py",
        ],
    }
    out = PROJECT_ROOT / "data/vision/field_coverage_campaign.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
