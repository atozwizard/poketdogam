# Run: python scripts/build_local_dex/collector.py --source seed --dry-run
"""RSLF-inspired collector: source → normalize → passages → validate → atomic swap."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import shutil
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_local_dex.build import build_local_dex


def collect_dex(
    *,
    source: str = "seed",
    limit: int = 1025,
    fetch: bool = False,
    dry_run: bool = False,
    db_path: Path | None = None,
    meta_path: Path | None = None,
) -> dict[str, object]:
    db_path = db_path or (PROJECT_ROOT / "data" / "dex.sqlite")
    meta_path = meta_path or (PROJECT_ROOT / "data" / "dex.meta.json")

    with tempfile.TemporaryDirectory(prefix="poketdogam-dex-") as temp_dir:
        temp = Path(temp_dir)
        staging_db = temp / "dex.sqlite"
        staging_meta = temp / "dex.meta.json"
        result = build_local_dex(
            staging_db,
            staging_meta,
            source=source,
            limit=limit,
            fetch=fetch,
        )
        report = {
            "status": "dry_run" if dry_run else "committed",
            "source": source,
            "limit": limit,
            "staging": {
                "db": str(staging_db),
                "meta": str(staging_meta),
            },
            "result": result,
        }
        if dry_run:
            return report

        db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staging_db, db_path)
        shutil.copy2(staging_meta, meta_path)
        report["committed_paths"] = {"db": str(db_path), "meta": str(meta_path)}
        return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("seed", "pokeapi"), default="seed")
    parser.add_argument("--limit", type=int, default=1025)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            collect_dex(source=args.source, limit=args.limit, fetch=args.fetch, dry_run=args.dry_run),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
