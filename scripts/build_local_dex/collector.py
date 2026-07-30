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
from scripts.build_local_dex.validate_dex import validate
from scripts.build_visual_index import build_visual_index


def collect_dex(
    *,
    source: str = "seed",
    limit: int | None = None,
    fetch: bool = False,
    dry_run: bool = False,
    db_path: Path | None = None,
    meta_path: Path | None = None,
    visual_index_path: Path | None = None,
) -> dict[str, object]:
    db_path = db_path or (PROJECT_ROOT / "data" / "dex.sqlite")
    meta_path = meta_path or (PROJECT_ROOT / "data" / "dex.meta.json")
    visual_index_path = visual_index_path or (
        PROJECT_ROOT / "data" / "vision" / "gen1_visual_index.json"
    )

    with tempfile.TemporaryDirectory(prefix="poketdogam-dex-") as temp_dir:
        temp = Path(temp_dir)
        staging_db = temp / "dex.sqlite"
        staging_meta = temp / "dex.meta.json"
        staging_visual_index = temp / "gen1_visual_index.json"
        result = build_local_dex(
            staging_db,
            staging_meta,
            source=source,
            limit=limit,
            fetch=fetch,
        )
        visual_result = None
        if source == "pokeapi":
            visual_result = build_visual_index(
                db_path=staging_db,
                cache_dir=PROJECT_ROOT / "data" / "raw" / "pokeapi",
                model_path=PROJECT_ROOT / "data" / "vision" / "mobilenet_v3_small.tflite",
                output_path=staging_visual_index,
            )
            strict_validation = validate(
                staging_db,
                PROJECT_ROOT / "fixtures" / "ocr" / "korean_cards.jsonl",
                min_species=1028,
                min_fixture_count=30,
                require_nonbase_forms=True,
                require_evolution_conditions=True,
                require_provenance=True,
                require_gen1_visual_coverage=True,
                require_all_announced_generations=True,
                min_official_previews=3,
            )
            result["visual_index"] = visual_result
            result["validation"] = strict_validation
            _attach_visual_meta(staging_meta, visual_result)
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
        if staging_visual_index.exists():
            visual_index_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staging_visual_index, visual_index_path)
        report["committed_paths"] = {"db": str(db_path), "meta": str(meta_path)}
        if staging_visual_index.exists():
            report["committed_paths"]["visual_index"] = str(visual_index_path)
        return report


def _attach_visual_meta(meta_path: Path, visual_result: dict[str, object]) -> None:
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["visual_index"] = {
        key: value
        for key, value in visual_result.items()
        if key not in {"output_path"}
    }
    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("seed", "pokeapi"), default="seed")
    parser.add_argument("--limit", type=int, default=0, help="Use 0 for all available species")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            collect_dex(
                source=args.source,
                limit=args.limit or None,
                fetch=args.fetch,
                dry_run=args.dry_run,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
