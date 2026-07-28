# Run: python scripts/build_local_dex/fetch_pokeapi.py --limit 25
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys
import time

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"


def fetch_pokeapi_cache(cache_dir: Path, *, limit: int, sleep_seconds: float = 0.05) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for pokemon_id in range(1, limit + 1):
            for resource in ("pokemon", "pokemon-species"):
                output_path = cache_dir / resource / f"{pokemon_id}.json"
                if output_path.exists():
                    continue
                output_path.parent.mkdir(parents=True, exist_ok=True)
                response = client.get(f"{POKEAPI_BASE_URL}/{resource}/{pokemon_id}")
                response.raise_for_status()
                output_path.write_text(json.dumps(response.json(), ensure_ascii=False, indent=2), encoding="utf-8")
                time.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", default="data/raw/pokeapi")
    parser.add_argument("--limit", type=int, default=1025)
    args = parser.parse_args()
    fetch_pokeapi_cache(PROJECT_ROOT / args.cache_dir, limit=args.limit)
    print({"cache_dir": args.cache_dir, "limit": args.limit})


if __name__ == "__main__":
    main()
