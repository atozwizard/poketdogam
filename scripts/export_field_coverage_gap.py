#!/usr/bin/env python3
"""Export Generation 1–9 recognition-coverage gaps for contributor campaigns."""

from __future__ import annotations

from collections import Counter
from contextlib import closing
from pathlib import Path
import argparse
import csv
import json
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def export_gap(
    *,
    db_path: Path,
    manifest_path: Path,
    json_out: Path,
    csv_out: Path,
) -> dict[str, object]:
    with closing(sqlite3.connect(db_path)) as conn:
        species_rows = [
            {
                "pokemon_id": int(row[0]),
                "name_en": str(row[1]),
                "name_ko": str(row[2]),
                "generation": int(row[3]),
            }
            for row in conn.execute(
                """
                select pokemon_id, name_en, name_ko, generation
                from pokemon_species
                where generation between 1 and 9
                order by pokemon_id
                """
            )
        ]
        in_game_species = {
            int(row[0])
            for row in conn.execute(
                """
                select distinct f.pokemon_id
                from visual_reference_embeddings v
                join pokemon_forms f on f.form_id = v.form_id
                join pokemon_species s on s.pokemon_id = f.pokemon_id
                where v.reference_kind = 'temporary_source_to_derived_embedding'
                  and s.generation between 1 and 9
                """
            )
        }
    items = []
    if manifest_path.exists():
        items = [
            item
            for item in json.loads(manifest_path.read_text(encoding="utf-8")).get("items") or []
            if item.get("benchmark_eligible") is True
        ]
    by_species: Counter[int] = Counter(int(item["expected_pokemon_id"]) for item in items)
    creators = {str(item.get("source_creator") or "").casefold() for item in items}
    object_kinds = Counter(str(item.get("object_kind") or "unknown") for item in items)
    covered = [
        {
            **species,
            "sample_count": by_species[species["pokemon_id"]],
            "in_game_embedded": species["pokemon_id"] in in_game_species,
            "status": (
                "field_covered"
                if by_species[species["pokemon_id"]]
                else ("in_game_only" if species["pokemon_id"] in in_game_species else "missing")
            ),
        }
        for species in species_rows
    ]
    field_missing = [row for row in covered if row["status"] != "field_covered"]
    payload = {
        "schema_version": 2,
        "targets": {
            "species": 1025,
            "samples": 1025,
            "media_kinds": 4,
            "top3_recall": 0.9,
            "field_pilot_creators": 30,
            "field_pilot_samples": 453,
        },
        "current": {
            "eligible_field_samples": len(items),
            "field_covered_species": len(by_species),
            "field_covered_creators": len(creators),
            "in_game_embedded_species": len(in_game_species),
            "object_kind_counts": dict(sorted(object_kinds.items())),
        },
        "gaps": {
            "field_species": max(0, 1025 - len(by_species)),
            "field_creators": max(0, 30 - len(creators)),
            "field_samples": max(0, 453 - len(items)),
            "in_game_species": max(0, 1025 - len(in_game_species)),
        },
        "contribution_brief": [
            "Photograph cards, plush, figures, stickers, goods, or capture clean screenshots.",
            "Fill at least 70% of the frame; keep the card-name band readable for cards.",
            "No children or identifiable bystanders in frame.",
            "Declare license (owner_granted or CC) and creator name.",
            "Ingest with scripts/ingest_field_contribution.py or scripts/batch_ingest_field_contributions.py.",
        ],
        "missing_species": field_missing,
        "covered_species": [row for row in covered if row["status"] == "field_covered"],
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "pokemon_id",
                "name_en",
                "name_ko",
                "generation",
                "sample_count",
                "in_game_embedded",
                "status",
                "priority",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        for row in covered:
            writer.writerow(
                {
                    **row,
                    "priority": "high" if row["status"] == "missing" else "maintain",
                }
            )
    return {
        "missing_species": len(field_missing),
        "covered_species": len(by_species),
        "eligible_samples": len(items),
        "in_game_embedded_species": len(in_game_species),
        "json_out": str(json_out),
        "csv_out": str(csv_out),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--manifest-path", default="data/raw/field_photos/manifest.json")
    parser.add_argument("--json-out", default="data/vision/field_coverage_gap.json")
    parser.add_argument("--csv-out", default="data/vision/field_coverage_gap.csv")
    args = parser.parse_args()
    result = export_gap(
        db_path=PROJECT_ROOT / args.db_path,
        manifest_path=PROJECT_ROOT / args.manifest_path,
        json_out=PROJECT_ROOT / args.json_out,
        csv_out=PROJECT_ROOT / args.csv_out,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
