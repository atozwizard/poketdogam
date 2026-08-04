#!/usr/bin/env python3
"""Ingest user-contributed recognition photos across Generation 1–9 media kinds.

Photos stay under data/raw/ (gitignored). Only reviewed, license-declared items can
enter the committed field attribution/benchmark path via review_field_photo_manifest.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from contextlib import closing
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import argparse
import json
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def ingest_contribution(
    *,
    image_path: Path,
    pokemon_id: int,
    creator: str,
    license_code: str,
    license_url: str,
    landing_url: str,
    object_kind: str,
    output_dir: Path,
    manifest_path: Path,
    db_path: Path,
) -> dict[str, object]:
    if license_code not in {"by", "by-sa", "by-nc", "by-nc-sa", "cc0", "pdm", "owner_granted"}:
        raise ValueError(f"unsupported license_code: {license_code}")
    if object_kind not in {
        "card",
        "figure_or_toy",
        "plush",
        "sticker",
        "goods",
        "user_screenshot",
    }:
        raise ValueError(f"unsupported object_kind: {object_kind}")

    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            """
            select pokemon_id, name_en, name_ko, generation from pokemon_species
            where pokemon_id = ? and generation between 1 and 9
            """,
            (pokemon_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"pokemon_id {pokemon_id} is not a Generation 1–9 species")

    from PIL import Image

    image_path = image_path if image_path.is_absolute() else (PROJECT_ROOT / image_path)
    output_dir = output_dir if output_dir.is_absolute() else (PROJECT_ROOT / output_dir)
    manifest_path = (
        manifest_path if manifest_path.is_absolute() else (PROJECT_ROOT / manifest_path)
    )
    db_path = db_path if db_path.is_absolute() else (PROJECT_ROOT / db_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        rgb.thumbnail((1600, 1600))
        buffer = BytesIO()
        rgb.save(buffer, format="JPEG", quality=90, optimize=True)
        payload = buffer.getvalue()
        width, height = rgb.size

    digest = sha256(payload).hexdigest()
    local_name = f"contrib-{digest[:16]}.jpg"
    local_path = output_dir / local_name
    local_path.write_bytes(payload)

    manifest = {"schema_version": 1, "items": []}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = list(manifest.get("items") or [])
    if any(item.get("normalized_sha256") == digest for item in items):
        return {"status": "duplicate", "sha256": digest}

    item = {
        "source_id": f"contribution:{digest[:20]}",
        "source_provider": "user_contribution",
        "source_title": f"{row[1]} {object_kind}",
        "source_creator": creator.strip() or "anonymous",
        "source_creator_url": "",
        "source_landing_url": landing_url,
        "download_url": str(image_path),
        "license_code": license_code,
        "license_version": "",
        "license_url": license_url,
        "attribution": f"{creator} / {license_code}",
        "license_verification_status": "pending_review",
        "source_width": width,
        "source_height": height,
        "source_tags": [object_kind, "contribution"],
        "discovery_query": "user_contribution",
        "object_kind": object_kind,
        "expected_pokemon_id": int(row[0]),
        "expected_generation": int(row[3]),
        "expected_name_en": str(row[1]),
        "expected_form_id": str(row[1]).casefold().replace(" ", "-"),
        "label_basis": "contributor_declared_species",
        "local_path": str(local_path.relative_to(PROJECT_ROOT)),
        "normalized_sha256": digest,
        "normalized_width": width,
        "normalized_height": height,
        "normalized_mime": "image/jpeg",
        "normalization": "rgb_jpeg_max_1600_exif_stripped",
        "review_status": "pending",
        "benchmark_eligible": False,
        "ingested_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    items.append(item)
    manifest.update(
        {
            "schema_version": 1,
            "collection": "field_photo_contributions",
            "updated_at": item["ingested_at"],
            "items": items,
            "counts": {
                "items": len(items),
                "species": len({int(i["expected_pokemon_id"]) for i in items}),
                "creators": len({str(i["source_creator"]).casefold() for i in items}),
            },
            "targets": {
                "species": 1025,
                "media_kinds": 4,
                "samples": 1025,
                "top3_recall": 0.9,
            },
        }
    )
    temporary = manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(manifest_path)
    return {"status": "ingested", "item": item, "counts": manifest["counts"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--pokemon-id", type=int, required=True)
    parser.add_argument("--creator", required=True)
    parser.add_argument("--license-code", required=True)
    parser.add_argument("--license-url", required=True)
    parser.add_argument("--landing-url", default="")
    parser.add_argument("--object-kind", default="figure_or_toy")
    parser.add_argument("--output-dir", default="data/raw/field_photos/contributions")
    parser.add_argument("--manifest", default="data/raw/field_photos/contributions_manifest.json")
    parser.add_argument("--db-path", default="data/dex.sqlite")
    args = parser.parse_args()
    result = ingest_contribution(
        image_path=PROJECT_ROOT / args.image,
        pokemon_id=args.pokemon_id,
        creator=args.creator,
        license_code=args.license_code,
        license_url=args.license_url,
        landing_url=args.landing_url or f"file://{args.image}",
        object_kind=args.object_kind,
        output_dir=PROJECT_ROOT / args.output_dir,
        manifest_path=PROJECT_ROOT / args.manifest,
        db_path=PROJECT_ROOT / args.db_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc
