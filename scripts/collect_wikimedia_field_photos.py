#!/usr/bin/env python3
"""Collect Generation 1 physical Pokemon photos from Wikimedia Commons.

Items append into the existing field photo manifest with benchmark_eligible=false
until review_field_photo_manifest.py verifies licenses and privacy.
"""

from __future__ import annotations

from collections import Counter
from contextlib import closing
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from urllib.parse import quote

import httpx

from scripts.collect_open_field_photos import (
    ALLOWED_LICENSES,
    ART_ONLY_TERMS,
    EXCLUDED_TERMS,
    FAN_CONTEXT_TERMS,
    PERSON_SOFT_TERMS,
    PERSON_TERMS,
    PHYSICAL_TERMS,
    PROJECT_ROOT,
    USER_AGENT,
    _detect_species,
    _existing_items,
    _generation_one_species,
    _normalize_text,
    _object_kind,
    _utc_timestamp,
)

COMMONS_EXTRA_EXCLUDES = {
    "title card",
    "titlecard",
    "anime",
    "episode",
    "broadcast",
    "sprite",
    "wallpaper",
    "logo",
    "box art",
    "boxart",
}


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
LICENSE_MAP = {
    "cc-zero": "cc0",
    "cc0": "cc0",
    "pd": "pdm",
    "pdm": "pdm",
    "public domain": "pdm",
    "cc-by-4.0": "by",
    "cc-by-3.0": "by",
    "cc-by-2.0": "by",
    "cc-by-sa-4.0": "by-sa",
    "cc-by-sa-3.0": "by-sa",
    "cc-by-sa-2.0": "by-sa",
    "cc-by-nc-4.0": "by-nc",
    "cc-by-nc-3.0": "by-nc",
    "cc-by-nc-sa-4.0": "by-nc-sa",
    "cc-by-nc-sa-3.0": "by-nc-sa",
}


def collect_wikimedia_field_photos(
    *,
    db_path: Path,
    output_dir: Path,
    manifest_path: Path,
    summary_path: Path,
    max_per_species: int = 3,
    max_per_creator: int = 3,
    max_downloads: int = 200,
    species_limit: int | None = None,
    allow_fan_pages: bool = False,
) -> dict[str, object]:
    species = _generation_one_species(db_path)
    if species_limit:
        species = species[:species_limit]
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = _existing_items(manifest_path)
    species_counts: Counter[int] = Counter(int(item["expected_pokemon_id"]) for item in selected)
    creator_counts: Counter[str] = Counter(
        str(item["source_creator"]).casefold() for item in selected
    )
    seen_source_ids = {str(item["source_id"]) for item in selected}
    seen_sha256 = {str(item["normalized_sha256"]) for item in selected}
    rejected: Counter[str] = Counter()
    discovered = 0
    object_terms = ("plush", "figure", "toy", "card")
    if allow_fan_pages:
        object_terms = (
            "plush",
            "figure",
            "toy",
            "card",
            "collection",
            "merch",
            "fan collection",
        )

    with httpx.Client(
        timeout=45.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for index, item in enumerate(species, start=1):
            if len(selected) >= max_downloads:
                break
            if species_counts[int(item["pokemon_id"])] >= max_per_species:
                continue
            for object_term in object_terms:
                if len(selected) >= max_downloads:
                    break
                if species_counts[int(item["pokemon_id"])] >= max_per_species:
                    break
                query = f'{item["name_en"]} Pokemon {object_term}'
                pages = _commons_search(client, query=query, limit=20)
                discovered += len(pages)
                for page in pages:
                    candidate = _candidate_from_commons(
                        page,
                        species=species,
                        query=query,
                        allow_fan_pages=allow_fan_pages,
                    )
                    if candidate is None:
                        rejected["filtered"] += 1
                        continue
                    source_id = str(candidate["source_id"])
                    pokemon_id = int(candidate["expected_pokemon_id"])
                    creator_key = str(candidate["source_creator"]).casefold()
                    if source_id in seen_source_ids:
                        rejected["duplicate_source_id"] += 1
                        continue
                    if species_counts[pokemon_id] >= max_per_species:
                        rejected["species_cap"] += 1
                        continue
                    if creator_counts[creator_key] >= max_per_creator:
                        rejected["creator_cap"] += 1
                        continue
                    try:
                        normalized, media = _download_and_normalize(
                            client, str(candidate["download_url"])
                        )
                    except (httpx.HTTPError, OSError, ValueError):
                        rejected["download_failed"] += 1
                        continue
                    digest = hashlib.sha256(normalized).hexdigest()
                    if digest in seen_sha256:
                        rejected["duplicate_content"] += 1
                        continue
                    filename = f"{pokemon_id:03d}-{source_id}.jpg"
                    output_path = output_dir / filename
                    output_path.write_bytes(normalized)
                    selected.append(
                        {
                            **candidate,
                            "local_path": str(output_path.relative_to(PROJECT_ROOT)),
                            "normalized_sha256": digest,
                            "normalized_width": media["width"],
                            "normalized_height": media["height"],
                            "normalized_mime": "image/jpeg",
                            "normalization": (
                                "RGB JPEG, max edge 1600px, EXIF and embedded metadata removed"
                            ),
                            "review_status": "pending_visual_label_and_license_review",
                            "benchmark_eligible": False,
                        }
                    )
                    seen_source_ids.add(source_id)
                    seen_sha256.add(digest)
                    species_counts[pokemon_id] += 1
                    creator_counts[creator_key] += 1
                    print(
                        f"wikimedia downloaded {len(selected)}: "
                        f"#{pokemon_id} {candidate['expected_name_en']}",
                        file=sys.stderr,
                    )
                time.sleep(0.15)
            if index % 20 == 0 or index == len(species):
                print(
                    f"wikimedia species {index}/{len(species)} · "
                    f"downloaded={len(selected)} discovered={discovered}",
                    file=sys.stderr,
                )

    existing_source = {}
    if manifest_path.exists():
        existing_source = json.loads(manifest_path.read_text(encoding="utf-8")).get("source") or {}
    manifest = {
        "schema_version": 1,
        "collection": "open_licensed_user_photography_candidates",
        "created_at": _utc_timestamp(),
        "source": {
            **existing_source,
            "wikimedia_commons": {
                "endpoint": COMMONS_API,
                "allow_fan_pages": allow_fan_pages,
                "policy": (
                    "Commons metadata is provisional; every item requires human privacy "
                    "review and source-page license verification before benchmark use. "
                    "Fan-page/collection photography is permitted when allow_fan_pages "
                    "is enabled."
                ),
            },
        },
        "usage_scope": "local_noncommercial_poc_quality_assurance_only",
        "raw_media_policy": (
            "Git-ignored QA input; never bundled in web, Android, Dex, or product assets"
        ),
        "privacy_policy": (
            "Person/cosplay terms excluded; EXIF stripped. Humans must still reject "
            "visible people or personal data."
        ),
        "items": selected,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "schema_version": 1,
        "collection": "wikimedia_commons_field_expansion",
        "created_at": _utc_timestamp(),
        "status": "visual_and_license_review_required_before_benchmark",
        "discovered_candidate_count": discovered,
        "downloaded_candidate_count": len(selected),
        "covered_species_count": len(species_counts),
        "allow_fan_pages": allow_fan_pages,
        "species_sample_counts": dict(
            sorted(species_counts.items(), key=lambda pair: int(pair[0]))
        ),
        "rejected_counts": dict(sorted(rejected.items())),
        "targets": {"species": 151, "creators": 30, "samples": 453},
        "raw_media_committed": False,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def _commons_search(client: httpx.Client, *, query: str, limit: int) -> list[dict[str, object]]:
    response = client.get(
        COMMONS_API,
        params={
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata|mime|user",
            "iiurlwidth": 1600,
        },
    )
    response.raise_for_status()
    pages = (response.json().get("query") or {}).get("pages") or {}
    return [page for page in pages.values() if isinstance(page, dict)]


def _candidate_from_commons(
    page: dict[str, object],
    *,
    species: list[dict[str, object]],
    query: str,
    allow_fan_pages: bool = False,
) -> dict[str, object] | None:
    title = str(page.get("title") or "")
    infos = page.get("imageinfo") or []
    if not isinstance(infos, list) or not infos:
        return None
    info = infos[0] if isinstance(infos[0], dict) else {}
    meta = info.get("extmetadata") if isinstance(info.get("extmetadata"), dict) else {}
    text_blob = " ".join(
        [
            title,
            _meta_value(meta, "ImageDescription"),
            _meta_value(meta, "ObjectName"),
            _meta_value(meta, "Categories"),
            query,
        ]
    )
    searchable = _normalize_text(text_blob)
    terms = set(searchable.split())
    fan_context = allow_fan_pages and any(
        term in searchable for term in FAN_CONTEXT_TERMS
    )
    if any(term in searchable for term in EXCLUDED_TERMS | COMMONS_EXTRA_EXCLUDES):
        return None
    if terms.intersection(PERSON_TERMS):
        return None
    if not fan_context and terms.intersection(PERSON_SOFT_TERMS):
        return None
    if not fan_context and any(term in searchable for term in ART_ONLY_TERMS):
        return None
    has_physical = bool(terms.intersection(PHYSICAL_TERMS))
    if not has_physical and not fan_context:
        return None
    # Require physical object signal beyond the query keyword "card" alone.
    physical_hits = [term for term in PHYSICAL_TERMS if term in searchable]
    if physical_hits == ["card"] or physical_hits == ["cards"]:
        if "tcg" not in searchable and "trading" not in searchable and "booster" not in searchable:
            if not fan_context:
                return None
    matches = _detect_species(searchable, species)
    if not matches:
        return None
    if len(matches) > 1:
        if not fan_context:
            return None
        title_norm = _normalize_text(title)
        matched = sorted(
            matches,
            key=lambda item: min(
                (
                    title_norm.find(alias)
                    for alias in item["aliases"]
                    if alias in title_norm
                ),
                default=10_000,
            ),
        )[0]
        label_basis = "commons_fan_page_primary_species_token"
    else:
        matched = matches[0]
        label_basis = "commons_title_description_single_species_match"
    license_raw = _meta_value(meta, "LicenseShortName").casefold()
    license_code = LICENSE_MAP.get(license_raw)
    if license_code is None:
        for key, mapped in LICENSE_MAP.items():
            if key in license_raw:
                license_code = mapped
                break
    if license_code not in ALLOWED_LICENSES:
        return None
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    if width < 320 or height < 320:
        return None
    download_url = str(info.get("url") or info.get("thumburl") or "")
    if not download_url:
        return None
    page_id = page.get("pageid") or title
    creator = str(info.get("user") or _meta_value(meta, "Artist") or "wikimedia-unknown")
    creator = re.sub(r"<[^>]+>", "", creator).strip() or "wikimedia-unknown"
    landing = f"https://commons.wikimedia.org/wiki/{quote(title.replace(' ', '_'))}"
    license_url = _meta_value(meta, "LicenseUrl") or landing
    return {
        "source_id": f"commons-{page_id}",
        "source_provider": "wikimedia_commons",
        "source_title": title,
        "source_creator": creator[:120],
        "source_creator_url": "",
        "source_landing_url": landing,
        "download_url": download_url,
        "license_code": license_code,
        "license_version": "",
        "license_url": license_url,
        "attribution": f"{creator} / {license_code} / Wikimedia Commons",
        "license_verification_status": "commons_metadata_requires_manual_source_page_verification",
        "source_width": width,
        "source_height": height,
        "source_tags": [query],
        "discovery_query": query,
        "object_kind": _object_kind(searchable),
        "expected_pokemon_id": int(matched["pokemon_id"]),
        "expected_name_en": str(matched["name_en"]),
        "expected_form_id": str(matched["form_id"]),
        "label_basis": label_basis,
        "fan_page_context": bool(fan_context),
    }


def _meta_value(meta: dict[str, object], key: str) -> str:
    item = meta.get(key)
    if isinstance(item, dict):
        return str(item.get("value") or "")
    return str(item or "")


def _download_and_normalize(client: httpx.Client, url: str) -> tuple[bytes, dict[str, int]]:
    from PIL import Image

    response = client.get(url)
    response.raise_for_status()
    with Image.open(BytesIO(response.content)) as image:
        rgb = image.convert("RGB")
        rgb.thumbnail((1600, 1600))
        if min(rgb.size) < 320:
            raise ValueError("image too small after normalize")
        buffer = BytesIO()
        rgb.save(buffer, format="JPEG", quality=90, optimize=True)
        return buffer.getvalue(), {"width": rgb.width, "height": rgb.height}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--output-dir", default="data/raw/field_photos/images")
    parser.add_argument("--manifest-path", default="data/raw/field_photos/manifest.json")
    parser.add_argument(
        "--summary-path",
        default="data/raw/field_photos/wikimedia_collection_summary.json",
    )
    parser.add_argument("--max-per-species", type=int, default=3)
    parser.add_argument("--max-per-creator", type=int, default=3)
    parser.add_argument("--max-downloads", type=int, default=250)
    parser.add_argument("--species-limit", type=int, default=0)
    parser.add_argument(
        "--allow-fan-pages",
        action="store_true",
        help="Permit fan-page/collection photography queries and softer multi-species labels",
    )
    args = parser.parse_args()
    result = collect_wikimedia_field_photos(
        db_path=PROJECT_ROOT / args.db_path,
        output_dir=PROJECT_ROOT / args.output_dir,
        manifest_path=PROJECT_ROOT / args.manifest_path,
        summary_path=PROJECT_ROOT / args.summary_path,
        max_per_species=args.max_per_species,
        max_per_creator=args.max_per_creator,
        max_downloads=args.max_downloads,
        species_limit=args.species_limit or None,
        allow_fan_pages=args.allow_fan_pages,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
