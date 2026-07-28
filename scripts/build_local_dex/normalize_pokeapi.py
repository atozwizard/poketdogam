# Run: python scripts/build_local_dex/normalize_pokeapi.py
from __future__ import annotations

from pathlib import Path
from pprint import pprint
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_local_dex.normalize_dex import form_uuid, rule_uuid
from scripts.build_local_dex.seed_data import POKEMON_SEED


def normalize_pokeapi_cache(
    cache_dir: Path,
    built_at: str,
    *,
    limit: int | None = None,
) -> dict[str, list[dict[str, object]]]:
    pokemon_dir = cache_dir / "pokemon"
    species_dir = cache_dir / "pokemon-species"
    if not pokemon_dir.exists() or not species_dir.exists():
        raise FileNotFoundError(f"PokéAPI cache missing under {cache_dir}")

    ids = sorted(int(path.stem) for path in species_dir.glob("*.json"))
    if limit is not None:
        ids = [pokemon_id for pokemon_id in ids if pokemon_id <= limit]
    if not ids:
        raise ValueError(f"no pokemon-species cache files found in {species_dir}")

    seed_aliases = _seed_ocr_aliases()
    species_rows: list[dict[str, object]] = []
    form_rows: list[dict[str, object]] = []
    stat_rows: list[dict[str, object]] = []
    form_index: dict[int, str] = {}

    for pokemon_id in ids:
        species_path = species_dir / f"{pokemon_id}.json"
        pokemon_path = pokemon_dir / f"{pokemon_id}.json"
        if not species_path.exists() or not pokemon_path.exists():
            continue

        species = json.loads(species_path.read_text(encoding="utf-8"))
        pokemon = json.loads(pokemon_path.read_text(encoding="utf-8"))
        names = _extract_names(species)
        generation = _extract_generation(species)
        form_id = form_uuid(pokemon_id, "base")
        form_index[pokemon_id] = form_id
        types = _extract_types(pokemon)
        stats = _extract_stats(pokemon)

        species_rows.append(
            {
                "pokemon_id": pokemon_id,
                "name_ko": names.get("ko", ""),
                "name_en": names.get("en", ""),
                "name_ja": names.get("ja", ""),
                "generation": generation,
                "is_legendary": int(bool(species.get("is_legendary") or species.get("is_mythical"))),
                "source": "pokeapi",
                "created_at": built_at,
                "updated_at": built_at,
            }
        )
        form_rows.append(
            {
                "form_id": form_id,
                "pokemon_id": pokemon_id,
                "form_name": "base",
                "type1": types[0] if types else "unknown",
                "type2": types[1] if len(types) > 1 else None,
                "height_m": round(int(pokemon.get("height") or 0) / 10, 2),
                "weight_kg": round(int(pokemon.get("weight") or 0) / 10, 2),
                "source": "pokeapi",
                "updated_at": built_at,
                "names": names,
                "aliases": seed_aliases.get(pokemon_id, []),
                "evolves_from_id": _evolves_from_id(species),
            }
        )
        stat_rows.append(
            {
                "form_id": form_id,
                "hp": stats["hp"],
                "attack": stats["attack"],
                "defense": stats["defense"],
                "sp_attack": stats["sp_attack"],
                "sp_defense": stats["sp_defense"],
                "speed": stats["speed"],
                "bst": sum(stats.values()),
            }
        )

    evolution_rows: list[dict[str, object]] = []
    for form in form_rows:
        evolves_from_id = form.get("evolves_from_id")
        if not isinstance(evolves_from_id, int):
            continue
        from_form_id = form_index.get(evolves_from_id)
        to_form_id = str(form["form_id"])
        if not from_form_id:
            continue
        evolution_rows.append(
            {
                "rule_id": rule_uuid(from_form_id, to_form_id, "pokeapi_chain", "evolves_from"),
                "from_form_id": from_form_id,
                "to_form_id": to_form_id,
                "trigger_type": "pokeapi_chain",
                "trigger_value": "evolves_from",
                "condition_json": "{}",
                "updated_at": built_at,
            }
        )

    return {
        "species": species_rows,
        "forms": form_rows,
        "stats": stat_rows,
        "evolutions": evolution_rows,
    }


def _extract_names(species: dict[str, object]) -> dict[str, str]:
    names: dict[str, str] = {}
    for item in species.get("names", []):
        if not isinstance(item, dict):
            continue
        language = item.get("language")
        if not isinstance(language, dict):
            continue
        code = str(language.get("name") or "")
        value = str(item.get("name") or "").strip()
        if not value:
            continue
        if code == "ko":
            names["ko"] = value
        elif code == "en":
            names["en"] = value
        elif code in {"ja-Hrkt", "ja"} and "ja" not in names:
            names["ja"] = value
    return names


def _extract_generation(species: dict[str, object]) -> int:
    generation = species.get("generation")
    if not isinstance(generation, dict):
        return 0
    url = str(generation.get("url") or "")
    try:
        return int(url.rstrip("/").split("/")[-1])
    except (TypeError, ValueError):
        return 0


def _extract_types(pokemon: dict[str, object]) -> list[str]:
    typed: list[tuple[int, str]] = []
    for item in pokemon.get("types", []):
        if not isinstance(item, dict):
            continue
        type_info = item.get("type")
        if not isinstance(type_info, dict):
            continue
        typed.append((int(item.get("slot") or 0), str(type_info.get("name") or "unknown")))
    typed.sort(key=lambda pair: pair[0])
    return [name for _, name in typed]


def _extract_stats(pokemon: dict[str, object]) -> dict[str, int]:
    mapping = {
        "hp": "hp",
        "attack": "attack",
        "defense": "defense",
        "special-attack": "sp_attack",
        "special-defense": "sp_defense",
        "speed": "speed",
    }
    stats = {value: 0 for value in mapping.values()}
    for item in pokemon.get("stats", []):
        if not isinstance(item, dict):
            continue
        stat = item.get("stat")
        if not isinstance(stat, dict):
            continue
        key = mapping.get(str(stat.get("name") or ""))
        if key:
            stats[key] = int(item.get("base_stat") or 0)
    return stats


def _evolves_from_id(species: dict[str, object]) -> int | None:
    evolves_from = species.get("evolves_from_species")
    if not isinstance(evolves_from, dict):
        return None
    url = str(evolves_from.get("url") or "")
    try:
        return int(url.rstrip("/").split("/")[-1])
    except (TypeError, ValueError):
        return None


def _seed_ocr_aliases() -> dict[int, list[str]]:
    aliases: dict[int, list[str]] = {}
    for item in POKEMON_SEED:
        pokemon_id = int(item["pokemon_id"])
        collected: list[str] = []
        for form in item["forms"]:
            assert isinstance(form, dict)
            for alias in form.get("aliases", []):
                if isinstance(alias, str):
                    collected.append(alias)
        if collected:
            aliases[pokemon_id] = collected
    return aliases


def main() -> None:
    cache_dir = PROJECT_ROOT / "data/raw/pokeapi"
    normalized = normalize_pokeapi_cache(cache_dir, "2026-07-28T00:00:00+09:00", limit=25)
    pprint({key: len(value) for key, value in normalized.items()})


if __name__ == "__main__":
    main()
