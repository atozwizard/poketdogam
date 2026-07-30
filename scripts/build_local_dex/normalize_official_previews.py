from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.build_local_dex.normalize_dex import form_uuid


def normalize_official_previews(
    preview_path: Path,
    built_at: str,
) -> dict[str, list[dict[str, object]]]:
    if not preview_path.exists():
        return {"species": [], "forms": [], "stats": [], "evolutions": []}

    payload = json.loads(preview_path.read_text(encoding="utf-8"))
    records = payload.get("pokemon")
    if not isinstance(records, list):
        raise ValueError("official preview manifest must contain a pokemon list")

    species_rows: list[dict[str, object]] = []
    form_rows: list[dict[str, object]] = []
    seen_ids: set[int] = set()
    seen_keys: set[str] = set()
    for raw in records:
        if not isinstance(raw, dict):
            continue
        pokemon_id = int(raw["provisional_id"])
        canonical_key = str(raw["canonical_key"])
        if pokemon_id >= 0:
            raise ValueError(f"official preview id must be negative: {pokemon_id}")
        if pokemon_id in seen_ids or canonical_key in seen_keys:
            raise ValueError(f"duplicate official preview identity: {canonical_key}")
        seen_ids.add(pokemon_id)
        seen_keys.add(canonical_key)

        name_en = _required_text(raw, "name_en")
        name_ko = str(raw.get("name_ko") or name_en)
        form_name = str(raw.get("form_name") or "base")
        types = [str(item) for item in raw.get("types", []) if str(item)]
        if not types:
            raise ValueError(f"official preview types missing: {canonical_key}")
        names = {"ko": name_ko, "en": name_en, "ja": ""}
        source = "official-preview:pokemon-winds-waves"

        species_rows.append(
            {
                "pokemon_id": pokemon_id,
                "name_ko": name_ko,
                "name_en": name_en,
                "name_ja": "",
                "generation": int(raw["generation"]),
                "is_legendary": 0,
                "source": source,
                "created_at": built_at,
                "updated_at": built_at,
            }
        )
        form_rows.append(
            {
                "form_id": form_uuid(pokemon_id, form_name),
                "pokemon_id": pokemon_id,
                "form_name": form_name,
                "type1": types[0],
                "type2": types[1] if len(types) > 1 else None,
                "height_m": _optional_float(raw.get("height_m")),
                "weight_kg": _optional_float(raw.get("weight_kg")),
                "source": source,
                "updated_at": built_at,
                "names": names,
                "aliases": [name_en.lower(), canonical_key],
                "record_status": str(raw.get("record_status") or "officially_announced_unnumbered"),
                "localization_status": str(raw.get("localization_status") or "unknown"),
                "category_en": str(raw.get("category_en") or ""),
                "ability_en": str(raw.get("ability_en") or ""),
                "canonical_key": canonical_key,
            }
        )

    return {
        "species": species_rows,
        "forms": form_rows,
        "stats": [],
        "evolutions": [],
    }


def _required_text(raw: dict[str, Any], key: str) -> str:
    value = str(raw.get(key) or "").strip()
    if not value:
        raise ValueError(f"official preview field missing: {key}")
    return value


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
