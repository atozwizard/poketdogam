# Run: python scripts/build_local_dex/build.py --source pokeapi
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_local_dex.build_aliases import build_alias_rows
from scripts.build_local_dex.build_passages import build_passage_rows
from scripts.build_local_dex.build_type_chart import build_type_chart_rows
from scripts.build_local_dex.export_sqlite import export_sqlite
from scripts.build_local_dex.fetch_pokeapi import fetch_pokeapi_cache
from scripts.build_local_dex.normalize_dex import normalize_seed_records
from scripts.build_local_dex.normalize_official_previews import normalize_official_previews
from scripts.build_local_dex.normalize_pokeapi import normalize_pokeapi_cache
from scripts.build_local_dex.validate_dex import validate


def build_local_dex(
    db_path: Path,
    meta_path: Path,
    *,
    dataset_version: str | None = None,
    source: str = "seed",
    cache_dir: Path | None = None,
    limit: int | None = None,
    fetch: bool = False,
    sleep_seconds: float = 0.05,
) -> dict[str, object]:
    built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    cache_dir = cache_dir or (PROJECT_ROOT / "data/raw/pokeapi")

    if source == "seed":
        dataset_version = dataset_version or f"seed-{built_at[:10]}"
        normalized = normalize_seed_records(built_at)
        sources = [
            {
                "name": "seed:pokeapi-compatible",
                "url": "https://pokeapi.co",
                "note": "Offline seed subset for Local Scan Core development and CI.",
                "usage_scope": "automated_test_only",
                "license_status": "not_for_product_distribution",
                "content_policy": "factual derivative fields; no official media",
            }
        ]
    elif source == "pokeapi":
        if fetch:
            fetch_pokeapi_cache(cache_dir, limit=limit, sleep_seconds=sleep_seconds)
        dataset_version = dataset_version or f"multisource-all-generations-{built_at[:10]}"
        normalized = normalize_pokeapi_cache(cache_dir, built_at, limit=limit)
        official_previews = normalize_official_previews(
            PROJECT_ROOT / "data/official_previews.json",
            built_at,
        )
        _append_unreleased_official_previews(normalized, official_previews)
        sources = [
            {
                "name": "pokeapi",
                "url": "https://pokeapi.co",
                "note": (
                    f"Cached factual species, variety and evolution fields up to species id={limit}."
                    if limit is not None
                    else "All factual species, variety and evolution fields available in the local cache."
                ),
                "usage_scope": "poc_noncommercial_evaluation",
                "license_status": "product_license_pending_after_poc_acceptance",
                "content_policy": "names, measurements, stats, types and evolution facts only; no media",
            },
            {
                "name": "pokemon-winds-waves-official-preview",
                "url": "https://windswaves.pokemon.com/en-us/",
                "note": "Officially announced, unnumbered next-generation Pokémon facts.",
                "usage_scope": "poc_noncommercial_evaluation",
                "license_status": "product_license_pending_after_poc_acceptance",
                "content_policy": "names, category, type, measurements and ability only; no media",
            },
            {
                "name": "seed:ocr-aliases",
                "url": "scripts/build_local_dex/seed_data.py",
                "note": "Manual OCR aliases merged by pokemon_id when available.",
                "usage_scope": "poc_noncommercial_evaluation",
                "license_status": "project_authored_derivative",
                "content_policy": "OCR error variants only",
            },
        ]
    else:
        raise ValueError(f"unsupported source: {source}")

    aliases = build_alias_rows(normalized["forms"], built_at)
    type_chart = build_type_chart_rows()
    passages = build_passage_rows(
        normalized["species"],
        normalized["forms"],
        normalized["stats"],
        normalized["evolutions"],
        built_at,
    )

    export_sqlite(
        db_path,
        dataset_version=dataset_version,
        built_at=built_at,
        sources=sources,
        species=normalized["species"],
        forms=normalized["forms"],
        stats=normalized["stats"],
        evolutions=normalized["evolutions"],
        aliases=aliases,
        type_chart=type_chart,
        passages=passages,
    )

    meta = {
        "dataset_version": dataset_version,
        "built_at": built_at,
        "source": source,
        "limit": limit if source == "pokeapi" else len(normalized["species"]),
        "species_count": len(normalized["species"]),
        "canonical_species_count": len(
            [item for item in normalized["species"] if int(item["pokemon_id"]) > 0]
        ),
        "official_preview_count": len(
            [item for item in normalized["species"] if int(item["pokemon_id"]) < 0]
        ),
        "form_count": len(normalized["forms"]),
        "alias_count": len(aliases),
        "passage_count": len(passages),
        "type_chart_count": len(type_chart),
        "usage_scope": "poc_noncommercial_evaluation" if source == "pokeapi" else "automated_test_only",
        "license_status": (
            "product_license_pending_after_poc_acceptance"
            if source == "pokeapi"
            else "not_for_product_distribution"
        ),
        "derivative_data_only": True,
        "official_media_included": False,
        "sources": sources,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    fixture_path = PROJECT_ROOT / "fixtures/ocr" / (
        "korean_cards.jsonl" if source == "pokeapi" else "seed_smoke.jsonl"
    )
    validation = validate(
        db_path,
        fixture_path,
        min_species=(limit or 1025) if source == "pokeapi" else 1,
        min_fixture_count=30 if source == "pokeapi" else 1,
        require_nonbase_forms=source == "pokeapi",
        require_evolution_conditions=source == "pokeapi",
        require_provenance=True,
    )
    return {"meta": meta, "validation": validation}


def _append_unreleased_official_previews(
    normalized: dict[str, list[dict[str, object]]],
    previews: dict[str, list[dict[str, object]]],
) -> None:
    canonical_names = {
        str(item.get("name_en") or "").strip().casefold()
        for item in normalized["species"]
    }
    preview_species = [
        item
        for item in previews["species"]
        if str(item.get("name_en") or "").strip().casefold() not in canonical_names
    ]
    included_ids = {int(item["pokemon_id"]) for item in preview_species}
    preview_forms = [
        item for item in previews["forms"] if int(item["pokemon_id"]) in included_ids
    ]
    included_form_ids = {str(item["form_id"]) for item in preview_forms}

    normalized["species"].extend(preview_species)
    normalized["forms"].extend(preview_forms)
    normalized["stats"].extend(
        item for item in previews["stats"] if str(item["form_id"]) in included_form_ids
    )
    normalized["evolutions"].extend(
        item
        for item in previews["evolutions"]
        if str(item["from_form_id"]) in included_form_ids
        and str(item["to_form_id"]) in included_form_ids
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--meta-path", default="data/dex.meta.json")
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--source", choices=("seed", "pokeapi"), default="seed")
    parser.add_argument("--cache-dir", default="data/raw/pokeapi")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum canonical species id. Use 0 to include every cached/available species.",
    )
    parser.add_argument("--fetch", action="store_true", help="Fetch missing PokéAPI cache before build")
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    args = parser.parse_args()

    result = build_local_dex(
        PROJECT_ROOT / args.db_path,
        PROJECT_ROOT / args.meta_path,
        dataset_version=args.dataset_version,
        source=args.source,
        cache_dir=PROJECT_ROOT / args.cache_dir,
        limit=args.limit or None,
        fetch=args.fetch,
        sleep_seconds=args.sleep_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
