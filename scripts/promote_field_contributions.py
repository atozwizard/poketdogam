#!/usr/bin/env python3
"""Promote reviewed contribution photos into the main field photo manifest."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def promote(
    *,
    contributions_manifest: Path,
    field_manifest: Path,
    images_dir: Path,
) -> dict[str, object]:
    contrib = json.loads(contributions_manifest.read_text(encoding="utf-8"))
    field = json.loads(field_manifest.read_text(encoding="utf-8")) if field_manifest.exists() else {
        "schema_version": 1,
        "collection": "open_licensed_user_photography_candidates",
        "items": [],
    }
    existing_ids = {str(item.get("source_id")) for item in field.get("items") or []}
    existing_sha = {str(item.get("normalized_sha256")) for item in field.get("items") or []}
    promoted = 0
    skipped = 0
    images_dir.mkdir(parents=True, exist_ok=True)
    for item in contrib.get("items") or []:
        if item.get("review_status") not in {"approved", "benchmark_ready"}:
            skipped += 1
            continue
        if not item.get("benchmark_eligible"):
            skipped += 1
            continue
        source_id = str(item.get("source_id"))
        digest = str(item.get("normalized_sha256") or "")
        if source_id in existing_ids or (digest and digest in existing_sha):
            skipped += 1
            continue
        src = PROJECT_ROOT / str(item["local_path"])
        dest = images_dir / src.name
        if src.exists() and src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
            item = {
                **item,
                "local_path": str(dest.relative_to(PROJECT_ROOT)),
                "source_provider": item.get("source_provider") or "user_contribution",
            }
        field.setdefault("items", []).append(item)
        existing_ids.add(source_id)
        if digest:
            existing_sha.add(digest)
        promoted += 1
    field_manifest.parent.mkdir(parents=True, exist_ok=True)
    field_manifest.write_text(json.dumps(field, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "promoted": promoted,
        "skipped": skipped,
        "field_manifest_items": len(field.get("items") or []),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contributions-manifest",
        default="data/raw/field_photos/contributions_manifest.json",
    )
    parser.add_argument("--field-manifest", default="data/raw/field_photos/manifest.json")
    parser.add_argument("--images-dir", default="data/raw/field_photos/images")
    args = parser.parse_args()
    result = promote(
        contributions_manifest=PROJECT_ROOT / args.contributions_manifest,
        field_manifest=PROJECT_ROOT / args.field_manifest,
        images_dir=PROJECT_ROOT / args.images_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
