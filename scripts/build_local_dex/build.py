# Run: python scripts/build_local_dex/build.py --source pokeapi --limit 1025
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
from scripts.build_local_dex.build_type_chart import build_type_chart_rows
from scripts.build_local_dex.export_sqlite import export_sqlite
from scripts.build_local_dex.fetch_pokeapi import fetch_pokeapi_cache
from scripts.build_local_dex.normalize_dex import normalize_seed_records
from scripts.build_local_dex.normalize_pokeapi import normalize_pokeapi_cache
from scripts.build_local_dex.validate_dex import validate


def build_local_dex(
    db_path: Path,
    meta_path: Path,
    *,
    dataset_version: str | None = None,
    source: str = "seed",
    cache_dir: Path | None = None,
    limit: int = 1025,
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
            }
        ]
    elif source == "pokeapi":
        if fetch:
            fetch_pokeapi_cache(cache_dir, limit=limit, sleep_seconds=sleep_seconds)
        dataset_version = dataset_version or f"pokeapi-gen1-9-{built_at[:10]}"
        normalized = normalize_pokeapi_cache(cache_dir, built_at, limit=limit)
        sources = [
            {
                "name": "pokeapi",
                "url": "https://pokeapi.co",
                "note": f"Cached PokéAPI species/pokemon build up to id={limit}.",
            },
            {
                "name": "seed:ocr-aliases",
                "url": "scripts/build_local_dex/seed_data.py",
                "note": "Manual OCR aliases merged by pokemon_id when available.",
            },
        ]
    else:
        raise ValueError(f"unsupported source: {source}")

    aliases = build_alias_rows(normalized["forms"], built_at)
    type_chart = build_type_chart_rows()

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
    )

    meta = {
        "dataset_version": dataset_version,
        "built_at": built_at,
        "source": source,
        "limit": limit if source == "pokeapi" else len(normalized["species"]),
        "species_count": len(normalized["species"]),
        "form_count": len(normalized["forms"]),
        "alias_count": len(aliases),
        "type_chart_count": len(type_chart),
        "sources": sources,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    fixture_path = PROJECT_ROOT / "fixtures/ocr/korean_cards.jsonl"
    validation = validate(db_path, fixture_path)
    return {"meta": meta, "validation": validation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--meta-path", default="data/dex.meta.json")
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--source", choices=("seed", "pokeapi"), default="seed")
    parser.add_argument("--cache-dir", default="data/raw/pokeapi")
    parser.add_argument("--limit", type=int, default=1025)
    parser.add_argument("--fetch", action="store_true", help="Fetch missing PokéAPI cache before build")
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    args = parser.parse_args()

    result = build_local_dex(
        PROJECT_ROOT / args.db_path,
        PROJECT_ROOT / args.meta_path,
        dataset_version=args.dataset_version,
        source=args.source,
        cache_dir=PROJECT_ROOT / args.cache_dir,
        limit=args.limit,
        fetch=args.fetch,
        sleep_seconds=args.sleep_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
