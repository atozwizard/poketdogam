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
    "Pokemon TCG",
    "Pokemon merch",
    "Pokemon merchandise",
    "Pokemon collection",
    "Pokemon fan collection",
    "Pokemon fan merch",
    "Pokemon display shelf",
    "Pokemon statue",
    "Pokemon nendoroid",
    "Pokemon funko",
    "Pokemon keychain",
    "Pokemon sticker",
    "Pokemon goods",
    "Pokemon acrylic stand",
    "Pokemon amiibo",
)
FAN_PAGE_QUERIES = (
    "Pokemon fan page merch",
    "Pokemon fan photography",
    "Pokemon collector shelf",
    "Pokemon room collection",
    "Pokemon desk figure",
    "Pokemon acrylic stand",
    "my Pokemon collection",
    "Pokemon haul unboxing",
)
SCREENSHOT_QUERIES = (
    "Pokemon game screenshot",
    "Pokemon Switch screenshot",
    "Pokemon Scarlet Violet screenshot",
    "Pokemon GO screenshot",
    "Pokemon in-game screenshot",
)
ALLOWED_LICENSES = {"by", "by-sa", "by-nc", "by-nc-sa", "cc0", "pdm"}
PHYSICAL_TERMS = {
    "acrylic",
    "amiibo",
    "badge",
    "card",
    "cards",
    "collection",
    "collector",
    "display",
    "doll",
    "fanmerch",
    "figure",
    "figurine",
    "funko",
    "goods",
    "keychain",
    "merch",
    "merchandise",
    "nendoroid",
    "pillow",
    "pin",
    "plush",
    "plushes",
    "plushie",
    "shelf",
    "shelfie",
    "standee",
    "statue",
    "sticker",
    "stickers",
    "stuffed",
    "tcg",
    "toy",
    "toys",
}
SCREENSHOT_TERMS = {
    "screenshot",
    "screenshots",
    "game capture",
    "game screenshot",
    "switch screenshot",
    "in game",
    "ingame",
    "pokemon go",
    "pokemongo",
}
FAN_CONTEXT_TERMS = {
    "fan",
    "fanart photo",
    "fanmade",
    "fanmerch",
    "fanpage",
    "fan page",
    "fandom",
    "collector",
    "collection",
    "haul",
    "shelfie",
    "my pokemon",
    "display case",
}
EXCLUDED_TERMS = {
    "augmented reality",
    "cosplay",
    "cosplayer",
    "costume",
    "episode",
    "graffiti",
    "manhole",
    "mural",
    "tattoo",
    "title card",
    "titlecard",
    "broadcast",
}
# Soft excludes: only reject when fan-context / screenshot / in-game scope is absent.
ART_ONLY_TERMS = {
    "digital art",
    "drawing",
    "illustration",
    "painting",
    "anime",
    "wallpaper",
}
SCREENSHOT_HARD_EXCLUDES_WHEN_DISABLED = {
    "pokemon go",
    "pokemongo",
    "screenshot",
    "game capture",
    "game screenshot",
}
PERSON_TERMS = {"child", "children", "cosplayer"}
PERSON_SOFT_TERMS = {"people", "person"}


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
    allow_fan_pages: bool = False,
    allow_screenshots: bool = False,
    all_generations: bool = False,
    license_type: str = "modification",
    require_photograph_category: bool = True,
) -> dict[str, object]:
    species = (
        _all_generation_species(db_path)
        if all_generations
        else _generation_one_species(db_path)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    search_queries = tuple(queries)
    if allow_fan_pages:
        search_queries = tuple(dict.fromkeys([*search_queries, *FAN_PAGE_QUERIES]))
    if allow_screenshots:
        search_queries = tuple(dict.fromkeys([*search_queries, *SCREENSHOT_QUERIES]))
    candidates = _discover_candidates(
        species,
        queries=search_queries,
        max_pages=max_pages,
        include_species_search=include_species_search,
        allow_fan_pages=allow_fan_pages,
        allow_screenshots=allow_screenshots,
        license_type=license_type,
        require_photograph_category=require_photograph_category,
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

    existing_source = {}
    if manifest_path.exists():
        existing_source = (
            json.loads(manifest_path.read_text(encoding="utf-8")).get("source") or {}
        )
    manifest = {
        "schema_version": 1,
        "collection": "open_licensed_user_photography_candidates",
        "created_at": _utc_timestamp(),
        "source": {
            **existing_source,
            "name": "Openverse API",
            "endpoint": OPENVERSE_ENDPOINT,
            "allow_fan_pages": allow_fan_pages,
            "license_type": license_type,
            "policy": (
                "Openverse indexes open-license metadata but does not guarantee its "
                "accuracy; every item requires source-page license verification. "
                "Fan-page/collection photography is permitted when allow_fan_pages "
                "is enabled."
            ),
        },
        "usage_scope": "local_noncommercial_poc_quality_assurance_only",
        "raw_media_policy": (
            "Git-ignored QA input; never bundled in web, Android, Dex, or product assets"
        ),
        "privacy_policy": (
            "Search metadata with child/cosplay terms is excluded; EXIF is stripped. "
            "Fan-page soft filters may allow collection context; a human must still "
            "reject visible people or personal data."
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
    return _species_scope(db_path, generations=(1,), expected_count=151)


def _all_generation_species(db_path: Path) -> list[dict[str, object]]:
    return _species_scope(
        db_path,
        generations=tuple(range(1, 10)),
        expected_count=1025,
    )


def _species_scope(
    db_path: Path,
    *,
    generations: tuple[int, ...],
    expected_count: int | None,
) -> list[dict[str, object]]:
    placeholders = ",".join("?" for _ in generations)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            select
                s.pokemon_id,
                s.name_en,
                s.generation,
                f.form_id
            from pokemon_species s
            join pokemon_forms f
              on f.pokemon_id = s.pokemon_id and f.form_name = 'base'
            where s.generation in ({placeholders})
            order by s.pokemon_id
            """,
            generations,
        ).fetchall()
    if expected_count is not None and len(rows) != expected_count:
        raise ValueError(
            f"species scope for generations {generations} must be "
            f"{expected_count}, got {len(rows)}"
        )
    return [
        {
            "pokemon_id": int(row["pokemon_id"]),
            "name_en": str(row["name_en"]),
            "generation": int(row["generation"]),
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
    allow_fan_pages: bool = False,
    allow_screenshots: bool = False,
    license_type: str = "modification",
    require_photograph_category: bool = True,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    with httpx.Client(
        timeout=45.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for query in queries:
            for page in range(1, max_pages + 1):
                payload = _openverse_page(
                    client,
                    query=query,
                    page=page,
                    license_type=license_type,
                    require_photograph_category=require_photograph_category,
                )
                results = payload.get("results") or []
                if not isinstance(results, list):
                    break
                for item in results:
                    candidate = _candidate_from_result(
                        item,
                        species=species,
                        query=query,
                        allow_fan_pages=allow_fan_pages,
                        allow_screenshots=allow_screenshots,
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
            object_terms = [
                "toy figure",
                "plush",
                "card",
                "sticker",
                "merch collection",
                "fan collection",
            ]
            if allow_screenshots:
                object_terms.extend(["game screenshot", "switch screenshot"])
            for index, item in enumerate(species, start=1):
                for object_term in object_terms:
                    query = f"{item['name_en']} Pokemon {object_term}"
                    payload = _openverse_page(
                        client,
                        query=query,
                        page=1,
                        license_type=license_type,
                        require_photograph_category=require_photograph_category,
                    )
                    results = payload.get("results") or []
                    if isinstance(results, list):
                        for result in results:
                            candidate = _candidate_from_result(
                                result,
                                species=species,
                                query=query,
                                allow_fan_pages=allow_fan_pages,
                                allow_screenshots=allow_screenshots,
                            )
                            if candidate is not None:
                                candidates.append(candidate)
                    time.sleep(0.15)
                if index % 25 == 0 or index == len(species):
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
    license_type: str = "modification",
    require_photograph_category: bool = True,
) -> dict[str, object]:
    params = {
        "q": query,
        "license_type": license_type,
        "mature": "false",
        "page_size": 20,
        "page": page,
    }
    if require_photograph_category:
        params["category"] = "photograph"
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
    allow_fan_pages: bool = False,
    allow_screenshots: bool = False,
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
    landing = str(item.get("foreign_landing_url") or "").casefold()
    provider = str(item.get("source") or item.get("provider") or "").casefold()
    searchable = _normalize_text(" ".join([title, *tags, query, provider]))
    terms = set(searchable.split())
    fan_context = allow_fan_pages and (
        any(term in searchable for term in FAN_CONTEXT_TERMS)
        or "fan" in landing
        or "fandom" in landing
        or "deviantart" in landing
        or "tumblr" in landing
        or "/blog/" in landing
        or "fanpage" in landing
        or "fan-page" in landing
        or "fan_page" in landing
    )
    screenshot_context = allow_screenshots and (
        any(term in searchable for term in SCREENSHOT_TERMS)
        or "screenshot" in landing
    )
    has_physical = bool(terms.intersection(PHYSICAL_TERMS))
    if not has_physical and not fan_context and not screenshot_context:
        return None
    if any(term in searchable for term in EXCLUDED_TERMS):
        return None
    if not allow_screenshots and any(
        term in searchable for term in SCREENSHOT_HARD_EXCLUDES_WHEN_DISABLED
    ):
        return None
    if (
        not fan_context
        and not screenshot_context
        and any(term in searchable for term in ART_ONLY_TERMS)
    ):
        return None
    if terms.intersection(PERSON_TERMS):
        return None
    if (
        not fan_context
        and not screenshot_context
        and terms.intersection(PERSON_SOFT_TERMS)
    ):
        return None
    matches = _detect_species(searchable, species)
    if not matches:
        return None
    if len(matches) > 1:
        if not fan_context and not screenshot_context:
            return None
        title_norm = _normalize_text(title)
        match = sorted(
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
        label_basis = "multi_species_primary_token_in_title_or_tags"
    else:
        match = matches[0]
        label_basis = "single exact species token in title_or_tags"
    kind = _object_kind(searchable, screenshot_context=screenshot_context)
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
        "expected_generation": int(match.get("generation") or 0) or None,
        "label_basis": label_basis,
        "fan_page_context": bool(fan_context),
        "screenshot_context": bool(screenshot_context),
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


def _object_kind(searchable: str, *, screenshot_context: bool = False) -> str:
    terms = set(searchable.split())
    if screenshot_context or terms.intersection(SCREENSHOT_TERMS):
        return "user_screenshot"
    if terms.intersection({"sticker", "stickers"}):
        return "sticker"
    if terms.intersection({"goods", "amiibo", "keychain", "badge", "pin"}):
        return "goods"
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
    fan_count = sum(1 for item in items if item.get("fan_page_context") is True)
    return {
        "schema_version": 1,
        "collection": manifest["collection"],
        "created_at": manifest["created_at"],
        "status": "visual_and_license_review_required_before_benchmark",
        "discovered_candidate_count": discovered_count,
        "downloaded_candidate_count": len(items),
        "covered_species_count": len(species_counts),
        "fan_page_context_count": fan_count,
        "species_sample_counts": dict(sorted(species_counts.items(), key=lambda pair: int(pair[0]))),
        "object_kind_counts": dict(sorted(kind_counts.items())),
        "provider_counts": dict(sorted(provider_counts.items())),
        "license_counts": dict(sorted(license_counts.items())),
        "rejected_counts": dict(sorted(rejected.items())),
        "raw_media_committed": False,
        "benchmark_eligible_count": len(eligible),
        "interpretation": (
            "Downloaded items are open-license candidate photographs, including "
            "fan-page/collection photography when enabled. Human visual labels, "
            "visible-person rejection, and source-page license checks are still required."
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
    parser.add_argument(
        "--allow-fan-pages",
        action="store_true",
        help="Permit fan-page/collection photography and broader merch queries",
    )
    parser.add_argument(
        "--allow-screenshots",
        action="store_true",
        help="Permit user/in-game screenshot photography in open collection",
    )
    parser.add_argument(
        "--all-generations",
        action="store_true",
        help="Label/search across Generation 1–9 (1025 species) instead of Gen1 only",
    )
    parser.add_argument(
        "--license-type",
        default="modification",
        choices=["modification", "commercial", "all"],
    )
    parser.add_argument(
        "--allow-non-photograph-category",
        action="store_true",
        help="Do not restrict Openverse results to category=photograph",
    )
    args = parser.parse_args()
    result = collect_open_field_photos(
        db_path=PROJECT_ROOT / args.db_path,
        output_dir=PROJECT_ROOT / args.output_dir,
        manifest_path=PROJECT_ROOT / args.manifest_path,
        summary_path=PROJECT_ROOT / args.summary_path,
        max_pages=max(1, min(args.max_pages, 20)),
        max_per_species=max(1, args.max_per_species),
        max_per_creator=max(1, args.max_per_creator),
        max_downloads=max(1, args.max_downloads),
        include_species_search=args.species_search,
        allow_fan_pages=args.allow_fan_pages,
        allow_screenshots=args.allow_screenshots,
        all_generations=args.all_generations,
        license_type=args.license_type,
        require_photograph_category=not args.allow_non_photograph_category,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
