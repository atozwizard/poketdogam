from __future__ import annotations

from collections import Counter
from contextlib import closing
from io import BytesIO
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPENVERSE_ENDPOINT = "https://api.openverse.org/v1/images/"
USER_AGENT = (
    "PoketdogamPoC/0.1 "
    "(noncommercial computer-vision evaluation; https://github.com/openai)"
)
DEFAULT_QUERIES = (
    "Pokemon toy",
    "Pokemon figure",
    "Pokemon plush",
    "Pokemon card",
)
ALLOWED_LICENSES = {"by", "by-sa", "by-nc", "by-nc-sa", "cc0", "pdm"}
PHYSICAL_TERMS = {
    "card",
    "cards",
    "doll",
    "figure",
    "figurine",
    "merchandise",
    "pillow",
    "plush",
    "plushes",
    "plushie",
    "stuffed",
    "tcg",
    "toy",
    "toys",
}
EXCLUDED_TERMS = {
    "augmented reality",
    "cosplay",
    "cosplayer",
    "costume",
    "digital art",
    "drawing",
    "graffiti",
    "illustration",
    "manhole",
    "mural",
    "painting",
    "pokemon go",
    "pokemongo",
    "screenshot",
    "tattoo",
}
PERSON_TERMS = {"child", "children", "cosplayer", "people", "person"}


def collect_open_field_photos(
    *,
    db_path: Path,
    output_dir: Path,
    manifest_path: Path,
    summary_path: Path,
    max_pages: int = 12,
    max_per_species: int = 8,
    max_per_creator: int = 8,
    max_downloads: int = 200,
    queries: tuple[str, ...] = DEFAULT_QUERIES,
    include_species_search: bool = False,
) -> dict[str, object]:
    species = _generation_one_species(db_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = _discover_candidates(
        species,
        queries=queries,
        max_pages=max_pages,
        include_species_search=include_species_search,
    )

    selected = _existing_items(manifest_path)
    species_counts: Counter[int] = Counter(
        int(item["expected_pokemon_id"]) for item in selected
    )
    creator_counts: Counter[str] = Counter(
        str(item["source_creator"]).casefold() for item in selected
    )
    seen_source_ids = {str(item["source_id"]) for item in selected}
    seen_sha256 = {str(item["normalized_sha256"]) for item in selected}
    rejected: Counter[str] = Counter()
    with httpx.Client(
        timeout=45.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for candidate in candidates:
            if len(selected) >= max_downloads:
                break
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
                    client,
                    str(candidate["download_url"]),
                )
            except (httpx.HTTPError, OSError, ValueError) as exc:
                rejected[f"download:{type(exc).__name__}"] += 1
                continue
            digest = hashlib.sha256(normalized).hexdigest()
            if digest in seen_sha256:
                rejected["duplicate_content"] += 1
                continue
            extension = "jpg"
            filename = f"{pokemon_id:03d}-{source_id}.{extension}"
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
                f"downloaded {len(selected)}/{max_downloads}: "
                f"#{pokemon_id} {candidate['expected_name_en']}",
                file=sys.stderr,
            )

    manifest = {
        "schema_version": 1,
        "collection": "open_licensed_user_photography_candidates",
        "created_at": _utc_timestamp(),
        "source": {
            "name": "Openverse API",
            "endpoint": OPENVERSE_ENDPOINT,
            "policy": (
                "Openverse indexes open-license metadata but does not guarantee its "
                "accuracy; every item requires source-page license verification."
            ),
        },
        "usage_scope": "local_noncommercial_poc_quality_assurance_only",
        "raw_media_policy": (
            "Git-ignored QA input; never bundled in web, Android, Dex, or product assets"
        ),
        "privacy_policy": (
            "Search metadata with person/cosplay terms is excluded; EXIF is stripped. "
            "A human must still reject visible people or personal data."
        ),
        "items": selected,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = _collection_summary(
        manifest,
        discovered_count=len(candidates),
        rejected=rejected,
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def _generation_one_species(db_path: Path) -> list[dict[str, object]]:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select
                s.pokemon_id,
                s.name_en,
                f.form_id
            from pokemon_species s
            join pokemon_forms f
              on f.pokemon_id = s.pokemon_id and f.form_name = 'base'
            where s.generation = 1
            order by s.pokemon_id
            """
        ).fetchall()
    if len(rows) != 151:
        raise ValueError(f"Generation 1 species scope must be 151, got {len(rows)}")
    return [
        {
            "pokemon_id": int(row["pokemon_id"]),
            "name_en": str(row["name_en"]),
            "form_id": str(row["form_id"]),
            "aliases": _species_aliases(str(row["name_en"])),
        }
        for row in rows
    ]


def _discover_candidates(
    species: list[dict[str, object]],
    *,
    queries: tuple[str, ...],
    max_pages: int,
    include_species_search: bool,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    with httpx.Client(
        timeout=45.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for query in queries:
            for page in range(1, max_pages + 1):
                payload = _openverse_page(client, query=query, page=page)
                results = payload.get("results") or []
                if not isinstance(results, list):
                    break
                for item in results:
                    candidate = _candidate_from_result(
                        item,
                        species=species,
                        query=query,
                    )
                    if candidate is not None:
                        candidates.append(candidate)
                page_count = min(int(payload.get("page_count") or 0), max_pages)
                print(
                    f"discovered {len(candidates)} candidates: "
                    f"{query} page {page}/{page_count}",
                    file=sys.stderr,
                )
                if page >= page_count:
                    break
                time.sleep(0.25)
        if include_species_search:
            for index, item in enumerate(species, start=1):
                for object_term in ("toy figure", "plush", "card"):
                    query = f"{item['name_en']} Pokemon {object_term}"
                    payload = _openverse_page(client, query=query, page=1)
                    results = payload.get("results") or []
                    if isinstance(results, list):
                        for result in results:
                            candidate = _candidate_from_result(
                                result,
                                species=species,
                                query=query,
                            )
                            if candidate is not None:
                                candidates.append(candidate)
                    time.sleep(0.2)
                if index % 10 == 0 or index == len(species):
                    print(
                        f"species searches {index}/{len(species)}: "
                        f"{len(candidates)} total candidates",
                        file=sys.stderr,
                    )
    return candidates


def _existing_items(manifest_path: Path) -> list[dict[str, object]]:
    if not manifest_path.exists():
        return []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    existing: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        local_path = PROJECT_ROOT / str(item.get("local_path") or "")
        if local_path.is_file() and item.get("normalized_sha256"):
            existing.append(item)
    return existing


def _openverse_page(
    client: httpx.Client,
    *,
    query: str,
    page: int,
) -> dict[str, object]:
    params = {
        "q": query,
        "license_type": "modification",
        "category": "photograph",
        "mature": "false",
        "page_size": 20,
        "page": page,
    }
    for attempt in range(4):
        response = client.get(OPENVERSE_ENDPOINT, params=params)
        if response.status_code != 429:
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Openverse returned a non-object response")
            return payload
        retry_after = min(float(response.headers.get("Retry-After", "2")), 30.0)
        time.sleep(retry_after * (attempt + 1))
    raise httpx.HTTPStatusError(
        "Openverse rate limit did not recover",
        request=response.request,
        response=response,
    )


def _candidate_from_result(
    item: object,
    *,
    species: list[dict[str, object]],
    query: str,
) -> dict[str, object] | None:
    if not isinstance(item, dict):
        return None
    license_code = str(item.get("license") or "").lower()
    if license_code not in ALLOWED_LICENSES:
        return None
    required = (
        item.get("id"),
        item.get("url"),
        item.get("foreign_landing_url"),
        item.get("license_url"),
        item.get("creator"),
    )
    if not all(required):
        return None
    title = html.unescape(str(item.get("title") or "")).strip()
    tags = [
        html.unescape(str(tag.get("name") or "")).strip()
        for tag in (item.get("tags") or [])
        if isinstance(tag, dict) and tag.get("name")
    ]
    searchable = _normalize_text(" ".join([title, *tags]))
    terms = set(searchable.split())
    if not terms.intersection(PHYSICAL_TERMS):
        return None
    if any(term in searchable for term in EXCLUDED_TERMS):
        return None
    if terms.intersection(PERSON_TERMS):
        return None
    matches = _detect_species(searchable, species)
    if len(matches) != 1:
        return None
    match = matches[0]
    kind = _object_kind(searchable)
    width = int(item.get("width") or 0)
    height = int(item.get("height") or 0)
    if width < 320 or height < 320:
        return None
    return {
        "source_id": str(item["id"]),
        "source_provider": str(item.get("source") or item.get("provider") or ""),
        "source_title": title,
        "source_creator": str(item["creator"]),
        "source_creator_url": str(item.get("creator_url") or ""),
        "source_landing_url": str(item["foreign_landing_url"]),
        "download_url": str(item["url"]),
        "license_code": license_code,
        "license_version": str(item.get("license_version") or ""),
        "license_url": str(item["license_url"]),
        "attribution": str(item.get("attribution") or ""),
        "license_verification_status": (
            "openverse_metadata_requires_manual_source_page_verification"
        ),
        "source_width": width,
        "source_height": height,
        "source_tags": tags,
        "discovery_query": query,
        "object_kind": kind,
        "expected_pokemon_id": int(match["pokemon_id"]),
        "expected_name_en": str(match["name_en"]),
        "expected_form_id": str(match["form_id"]),
        "label_basis": "single exact Generation 1 species token in title_or_tags",
    }


def _detect_species(
    searchable: str,
    species: list[dict[str, object]],
) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for item in species:
        if any(_contains_phrase(searchable, alias) for alias in item["aliases"]):
            matches.append(item)
    return matches


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])",
            text,
        )
    )


def _species_aliases(name: str) -> tuple[str, ...]:
    normalized = _normalize_text(name)
    if name == "Nidoran♀":
        return ("nidoran female", "nidoran f", "nidoranf")
    if name == "Nidoran♂":
        return ("nidoran male", "nidoran m", "nidoranm")
    if name == "Mr. Mime":
        return ("mr mime", "mrmime")
    if name == "Farfetch'd":
        return ("farfetchd", "farfetch d")
    return (normalized, normalized.replace(" ", ""))


def _normalize_text(value: str) -> str:
    value = value.casefold().replace("é", "e").replace("♀", " female ")
    value = value.replace("♂", " male ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def _object_kind(searchable: str) -> str:
    terms = set(searchable.split())
    if terms.intersection({"card", "cards", "tcg"}):
        return "card"
    if terms.intersection({"plush", "plushes", "plushie", "stuffed", "pillow"}):
        return "plush"
    return "figure_or_toy"


def _download_and_normalize(
    client: httpx.Client,
    url: str,
) -> tuple[bytes, dict[str, int]]:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("Run with `uv run --extra vision` to collect photos") from exc

    response = client.get(url)
    response.raise_for_status()
    content = response.content
    if not content or len(content) > 24 * 1024 * 1024:
        raise ValueError("image is empty or exceeds the 24MB collection limit")
    with Image.open(BytesIO(content)) as source:
        source.verify()
    with Image.open(BytesIO(content)) as source:
        if source.width * source.height > 40_000_000:
            raise ValueError("image exceeds the 40 megapixel safety limit")
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="JPEG", quality=90, optimize=True)
        normalized = output.getvalue()
        media = {"width": image.width, "height": image.height}
    return normalized, media


def _collection_summary(
    manifest: dict[str, object],
    *,
    discovered_count: int,
    rejected: Counter[str],
) -> dict[str, object]:
    items = manifest["items"]
    eligible = [item for item in items if item.get("benchmark_eligible") is True]
    species_counts = Counter(str(item["expected_pokemon_id"]) for item in items)
    kind_counts = Counter(str(item["object_kind"]) for item in items)
    provider_counts = Counter(str(item["source_provider"]) for item in items)
    license_counts = Counter(str(item["license_code"]) for item in items)
    return {
        "schema_version": 1,
        "collection": manifest["collection"],
        "created_at": manifest["created_at"],
        "status": "visual_and_license_review_required_before_benchmark",
        "discovered_candidate_count": discovered_count,
        "downloaded_candidate_count": len(items),
        "covered_species_count": len(species_counts),
        "species_sample_counts": dict(sorted(species_counts.items(), key=lambda pair: int(pair[0]))),
        "object_kind_counts": dict(sorted(kind_counts.items())),
        "provider_counts": dict(sorted(provider_counts.items())),
        "license_counts": dict(sorted(license_counts.items())),
        "rejected_counts": dict(sorted(rejected.items())),
        "raw_media_committed": False,
        "benchmark_eligible_count": len(eligible),
        "interpretation": (
            "Downloaded items are open-license candidate photographs, not a validated "
            "field benchmark. Human visual labels, visible-person rejection, and "
            "source-page license checks are still required."
        ),
    }


def _utc_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--output-dir", default="data/raw/field_photos/images")
    parser.add_argument(
        "--manifest-path",
        default="data/raw/field_photos/manifest.json",
    )
    parser.add_argument(
        "--summary-path",
        default="data/vision/field_collection.json",
    )
    parser.add_argument("--max-pages", type=int, default=12)
    parser.add_argument("--max-per-species", type=int, default=8)
    parser.add_argument("--max-per-creator", type=int, default=8)
    parser.add_argument("--max-downloads", type=int, default=200)
    parser.add_argument("--species-search", action="store_true")
    args = parser.parse_args()
    result = collect_open_field_photos(
        db_path=PROJECT_ROOT / args.db_path,
        output_dir=PROJECT_ROOT / args.output_dir,
        manifest_path=PROJECT_ROOT / args.manifest_path,
        summary_path=PROJECT_ROOT / args.summary_path,
        max_pages=max(1, min(args.max_pages, 12)),
        max_per_species=max(1, args.max_per_species),
        max_per_creator=max(1, args.max_per_creator),
        max_downloads=max(1, args.max_downloads),
        include_species_search=args.species_search,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
