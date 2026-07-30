# Run: python scripts/build_local_dex/fetch_pokeapi.py
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys
import time
from urllib.parse import urlparse

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"


def fetch_pokeapi_cache(
    cache_dir: Path,
    *,
    limit: int | None,
    sleep_seconds: float = 0.05,
    include_related: bool = True,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resolved_limit = limit or _available_species_count(client)
        for pokemon_id in range(1, resolved_limit + 1):
            for resource in ("pokemon", "pokemon-species"):
                output_path = cache_dir / resource / f"{pokemon_id}.json"
                _fetch_to_path(
                    client,
                    f"{POKEAPI_BASE_URL}/{resource}/{pokemon_id}",
                    output_path,
                    sleep_seconds,
                )

        related_counts = {"pokemon_varieties": 0, "evolution_chains": 0}
        if include_related:
            variety_urls, chain_urls = _related_urls(cache_dir, limit=resolved_limit)
            for url in sorted(variety_urls):
                resource_id = _resource_id(url)
                base_path = cache_dir / "pokemon" / f"{resource_id}.json"
                if base_path.exists():
                    continue
                output_path = cache_dir / "pokemon-varieties" / f"{resource_id}.json"
                _fetch_to_path(client, url, output_path, sleep_seconds)
                related_counts["pokemon_varieties"] += 1
            for url in sorted(chain_urls):
                resource_id = _resource_id(url)
                output_path = cache_dir / "evolution-chain" / f"{resource_id}.json"
                existed = output_path.exists()
                _fetch_to_path(client, url, output_path, sleep_seconds)
                if not existed:
                    related_counts["evolution_chains"] += 1

    manifest = {
        "source": "PokéAPI",
        "source_url": POKEAPI_BASE_URL,
        "usage_scope": "poc_noncommercial_evaluation",
        "data_policy": "factual fields only; sprites, cries, flavor text and official media are not persisted",
        "species_limit": resolved_limit,
        "selection": "explicit_limit" if limit is not None else "all_available",
        "include_related": include_related,
        "related_downloaded": related_counts,
    }
    (cache_dir / "cache-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _fetch_to_path(
    client: httpx.Client,
    url: str,
    output_path: Path,
    sleep_seconds: float,
) -> None:
    if output_path.exists():
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = client.get(url)
    response.raise_for_status()
    output_path.write_text(json.dumps(response.json(), ensure_ascii=False, indent=2), encoding="utf-8")
    time.sleep(sleep_seconds)


def _related_urls(cache_dir: Path, *, limit: int) -> tuple[set[str], set[str]]:
    variety_urls: set[str] = set()
    chain_urls: set[str] = set()
    for pokemon_id in range(1, limit + 1):
        path = cache_dir / "pokemon-species" / f"{pokemon_id}.json"
        if not path.exists():
            continue
        species = json.loads(path.read_text(encoding="utf-8"))
        for variety in species.get("varieties", []):
            if not isinstance(variety, dict):
                continue
            pokemon = variety.get("pokemon")
            if isinstance(pokemon, dict) and pokemon.get("url"):
                variety_urls.add(str(pokemon["url"]))
        chain = species.get("evolution_chain")
        if isinstance(chain, dict) and chain.get("url"):
            chain_urls.add(str(chain["url"]))
    return variety_urls, chain_urls


def _resource_id(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    resource_id = path.split("/")[-1]
    if not resource_id:
        raise ValueError(f"resource id missing from URL: {url}")
    return resource_id


def _available_species_count(client: httpx.Client) -> int:
    response = client.get(f"{POKEAPI_BASE_URL}/pokemon-species", params={"limit": 1})
    response.raise_for_status()
    count = int(response.json().get("count") or 0)
    if count < 1:
        raise ValueError("PokéAPI returned an invalid species count")
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", default="data/raw/pokeapi")
    parser.add_argument("--limit", type=int, default=0, help="Use 0 to fetch every available species")
    parser.add_argument("--base-only", action="store_true")
    args = parser.parse_args()
    fetch_pokeapi_cache(
        PROJECT_ROOT / args.cache_dir,
        limit=args.limit or None,
        include_related=not args.base_only,
    )
    print(
        {
            "cache_dir": args.cache_dir,
            "limit": args.limit or "all_available",
            "include_related": not args.base_only,
        }
    )


if __name__ == "__main__":
    main()
