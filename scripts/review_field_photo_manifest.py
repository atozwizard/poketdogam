from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = (
    "PoketdogamPoC/0.1 "
    "(noncommercial computer-vision evaluation; https://github.com/openai)"
)


def review_manifest(
    *,
    manifest_path: Path,
    summary_path: Path,
    attribution_path: Path,
    rejected_source_ids: dict[str, str],
    max_workers: int = 6,
    reuse_existing_license_review: bool = False,
) -> dict[str, object]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        raise ValueError("field photo manifest has no items")

    if reuse_existing_license_review:
        verifications = {
            str(item["source_id"]): dict(item.get("license_review") or {})
            for item in items
        }
        if not all("verified" in result for result in verifications.values()):
            raise ValueError("existing manifest has incomplete license reviews")
    else:
        verifications = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_verify_source_license, item): str(item["source_id"])
                for item in items
            }
            for future in as_completed(futures):
                source_id = futures[future]
                try:
                    verifications[source_id] = future.result()
                except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                    verifications[source_id] = {
                        "verified": False,
                        "reason": f"{type(exc).__name__}: {exc}",
                    }
                print(
                    f"verified licenses {len(verifications)}/{len(items)}",
                    file=sys.stderr,
                )

    reviewed_at = _utc_timestamp()
    for item in items:
        source_id = str(item["source_id"])
        verification = verifications[source_id]
        item["license_review"] = {
            **verification,
            "reviewed_at": reviewed_at,
            "method": "source_landing_page_contains_declared_license_url",
        }
        rejection_reason = rejected_source_ids.get(source_id)
        if rejection_reason:
            item["visual_review_status"] = "rejected"
            item["visual_review_reason"] = rejection_reason
            item["benchmark_eligible"] = False
        else:
            item["visual_review_status"] = "approved"
            item["visual_review_reason"] = (
                "single labeled physical subject confirmed in contact-sheet review; "
                "no identifiable person or personal data observed"
            )
            item["benchmark_eligible"] = bool(verification["verified"])
        item["review_status"] = (
            "approved_for_local_field_pilot"
            if item["benchmark_eligible"]
            else "rejected_or_license_unverified"
        )

    payload["reviewed_at"] = reviewed_at
    payload["review_method"] = (
        "human contact-sheet label/privacy review plus automated source-page "
        "license URL verification"
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = _review_summary(payload)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    attribution_path.write_text(
        json.dumps(_attribution_payload(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def _verify_source_license(item: dict[str, object]) -> dict[str, object]:
    landing_url = str(item.get("source_landing_url") or "")
    license_url = str(item.get("license_url") or "").rstrip("/")
    if not landing_url.startswith("https://") or not license_url.startswith("https://"):
        raise ValueError("source and license URLs must use HTTPS")
    body = ""
    last_error = ""
    for attempt in range(4):
        completed = subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "--max-time",
                "30",
                "--user-agent",
                USER_AGENT,
                landing_url,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            body = completed.stdout
            break
        last_error = completed.stderr.strip()
        time.sleep(0.5 * (attempt + 1))
    if not body:
        raise RuntimeError(f"curl could not load source page: {last_error}")
    normalized_body = body.replace("\\/", "/")
    verified = license_url in normalized_body
    return {
        "verified": verified,
        "http_status": 200,
        "final_landing_url": landing_url,
        "reason": (
            "declared license URL found on source page"
            if verified
            else "declared license URL not found on source page"
        ),
    }


def _review_summary(payload: dict[str, object]) -> dict[str, object]:
    items = payload["items"]
    eligible = [item for item in items if item.get("benchmark_eligible") is True]
    rejected = [item for item in items if item.get("visual_review_status") == "rejected"]
    unverified = [
        item
        for item in items
        if not (item.get("license_review") or {}).get("verified")
    ]
    species_counts = Counter(
        str(item["expected_pokemon_id"]) for item in eligible
    )
    creator_counts = Counter(str(item["source_creator"]) for item in eligible)
    kind_counts = Counter(str(item["object_kind"]) for item in eligible)
    return {
        "schema_version": 1,
        "collection": payload["collection"],
        "created_at": payload["created_at"],
        "reviewed_at": payload["reviewed_at"],
        "status": "field_pilot_ready_not_generation_wide",
        "downloaded_candidate_count": len(items),
        "benchmark_eligible_count": len(eligible),
        "rejected_visual_or_privacy_count": len(rejected),
        "license_unverified_count": len(unverified),
        "covered_species_count": len(species_counts),
        "covered_creator_count": len(creator_counts),
        "species_sample_counts": dict(
            sorted(species_counts.items(), key=lambda pair: int(pair[0]))
        ),
        "creator_sample_counts": dict(sorted(creator_counts.items())),
        "object_kind_counts": dict(sorted(kind_counts.items())),
        "raw_media_committed": False,
        "generation_1_coverage_complete": len(species_counts) == 151,
        "interpretation": (
            "Eligible images form a narrow open-license field pilot. Repeated images "
            "from one creator and missing Generation 1 species prevent a 90% "
            "generation-wide accuracy claim."
        ),
    }


def _attribution_payload(payload: dict[str, object]) -> dict[str, object]:
    items = [
        item
        for item in payload["items"]
        if item.get("benchmark_eligible") is True
    ]
    return {
        "schema_version": 1,
        "collection": payload["collection"],
        "usage_scope": payload["usage_scope"],
        "raw_media_included": False,
        "notice": (
            "Attribution metadata for local QA photographs. The photographs themselves "
            "are Git-ignored and not distributed with the application."
        ),
        "items": [
            {
                "source_title": item["source_title"],
                "source_creator": item["source_creator"],
                "source_creator_url": item["source_creator_url"],
                "source_landing_url": item["source_landing_url"],
                "license_code": item["license_code"],
                "license_version": item["license_version"],
                "license_url": item["license_url"],
                "attribution": item["attribution"],
                "expected_pokemon_id": item["expected_pokemon_id"],
                "object_kind": item["object_kind"],
            }
            for item in items
        ],
    }


def _utc_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest-path",
        default="data/raw/field_photos/manifest.json",
    )
    parser.add_argument(
        "--summary-path",
        default="data/vision/field_collection.json",
    )
    parser.add_argument(
        "--attribution-path",
        default="data/vision/field_attribution.json",
    )
    parser.add_argument(
        "--reject",
        action="append",
        default=[],
        help="source_id=reason; repeat for each rejected item",
    )
    parser.add_argument("--max-workers", type=int, default=6)
    parser.add_argument("--reuse-existing-license-review", action="store_true")
    args = parser.parse_args()
    rejected: dict[str, str] = {}
    for value in args.reject:
        source_id, separator, reason = value.partition("=")
        if not separator or not source_id or not reason:
            raise ValueError("--reject must use source_id=reason")
        rejected[source_id] = reason
    result = review_manifest(
        manifest_path=PROJECT_ROOT / args.manifest_path,
        summary_path=PROJECT_ROOT / args.summary_path,
        attribution_path=PROJECT_ROOT / args.attribution_path,
        rejected_source_ids=rejected,
        max_workers=max(1, min(args.max_workers, 8)),
        reuse_existing_license_review=args.reuse_existing_license_review,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
