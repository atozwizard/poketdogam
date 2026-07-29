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
    variety_index: dict[str, str] = {}

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
        variety_index[str(pokemon.get("name") or species.get("name") or pokemon_id)] = form_id
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

        for variety in species.get("varieties", []):
            if not isinstance(variety, dict) or variety.get("is_default"):
                continue
            pokemon_ref = variety.get("pokemon")
            if not isinstance(pokemon_ref, dict):
                continue
            variety_url = str(pokemon_ref.get("url") or "")
            variety_resource_id = _url_resource_id(variety_url)
            variety_path = cache_dir / "pokemon-varieties" / f"{variety_resource_id}.json"
            if not variety_path.exists():
                continue
            variety_pokemon = json.loads(variety_path.read_text(encoding="utf-8"))
            variety_name = str(variety_pokemon.get("name") or pokemon_ref.get("name") or "")
            form_name = _form_name(str(species.get("name") or ""), variety_name)
            if not form_name or any(
                row["pokemon_id"] == pokemon_id and row["form_name"] == form_name for row in form_rows
            ):
                form_name = f"{form_name or 'variant'}-{variety_resource_id}"
            variety_form_id = form_uuid(pokemon_id, form_name)
            variety_index[variety_name] = variety_form_id
            variety_types = _extract_types(variety_pokemon)
            variety_stats = _extract_stats(variety_pokemon)
            form_rows.append(
                {
                    "form_id": variety_form_id,
                    "pokemon_id": pokemon_id,
                    "form_name": form_name,
                    "type1": variety_types[0] if variety_types else "unknown",
                    "type2": variety_types[1] if len(variety_types) > 1 else None,
                    "height_m": round(int(variety_pokemon.get("height") or 0) / 10, 2),
                    "weight_kg": round(int(variety_pokemon.get("weight") or 0) / 10, 2),
                    "source": "pokeapi:variety",
                    "updated_at": built_at,
                    "names": names,
                    "aliases": _variant_aliases(names, form_name, variety_name),
                }
            )
            stat_rows.append(
                {
                    "form_id": variety_form_id,
                    "hp": variety_stats["hp"],
                    "attack": variety_stats["attack"],
                    "defense": variety_stats["defense"],
                    "sp_attack": variety_stats["sp_attack"],
                    "sp_defense": variety_stats["sp_defense"],
                    "speed": variety_stats["speed"],
                    "bst": sum(variety_stats.values()),
                }
            )

    evolution_rows = _normalize_evolution_chains(cache_dir, form_index, variety_index, built_at)
    if not evolution_rows:
        evolution_rows = _fallback_evolutions(form_rows, form_index, built_at)

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


def _url_resource_id(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def _form_name(species_name: str, variety_name: str) -> str:
    prefix = f"{species_name}-"
    if variety_name.startswith(prefix):
        return variety_name[len(prefix) :]
    return variety_name or "variant"


FORM_LABELS_KO = {
    "alola": "알로라",
    "galar": "가라르",
    "hisui": "히스이",
    "paldea": "팔데아",
    "mega": "메가",
    "gmax": "거다이맥스",
    "origin": "오리진",
    "therian": "영물",
    "attack": "어택",
    "defense": "디펜스",
    "speed": "스피드",
}


def _variant_aliases(names: dict[str, str], form_name: str, variety_name: str) -> list[str]:
    ko_name = str(names.get("ko") or "")
    tokens = form_name.split("-")
    ko_form = " ".join(FORM_LABELS_KO.get(token, token) for token in tokens)
    aliases = [variety_name, f"{ko_name} {ko_form}".strip(), f"{ko_form} {ko_name}".strip()]
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _normalize_evolution_chains(
    cache_dir: Path,
    form_index: dict[int, str],
    variety_index: dict[str, str],
    built_at: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for path in sorted((cache_dir / "evolution-chain").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        chain = payload.get("chain")
        if isinstance(chain, dict):
            _walk_evolution_chain(chain, None, form_index, variety_index, built_at, rows, seen)
    return rows


def _walk_evolution_chain(
    node: dict[str, object],
    parent_species_id: int | None,
    form_index: dict[int, str],
    variety_index: dict[str, str],
    built_at: str,
    rows: list[dict[str, object]],
    seen: set[str],
) -> None:
    species = node.get("species")
    current_species_id = _species_id(species)
    if parent_species_id and current_species_id:
        default_from_form_id = form_index.get(parent_species_id)
        default_to_form_id = form_index.get(current_species_id)
        if default_from_form_id and default_to_form_id:
            details = node.get("evolution_details")
            normalized_details = details if isinstance(details, list) and details else [{}]
            for detail in normalized_details:
                detail = detail if isinstance(detail, dict) else {}
                from_form_id = variety_index.get(
                    str(detail.get("from_form") or ""),
                    default_from_form_id,
                )
                to_form_id = variety_index.get(
                    str(detail.get("evolved_form") or ""),
                    default_to_form_id,
                )
                trigger = detail.get("trigger")
                trigger_type = (
                    str(trigger.get("name") or "unknown") if isinstance(trigger, dict) else "unknown"
                )
                condition = _evolution_condition(detail)
                trigger_value = _trigger_summary(trigger_type, condition)
                identifier_value = json.dumps(condition, ensure_ascii=False, sort_keys=True)
                rule_id = rule_uuid(from_form_id, to_form_id, trigger_type, identifier_value)
                if rule_id in seen:
                    continue
                seen.add(rule_id)
                rows.append(
                    {
                        "rule_id": rule_id,
                        "from_form_id": from_form_id,
                        "to_form_id": to_form_id,
                        "trigger_type": trigger_type,
                        "trigger_value": trigger_value,
                        "condition_json": json.dumps(condition, ensure_ascii=False, sort_keys=True),
                        "updated_at": built_at,
                    }
                )
    children = node.get("evolves_to")
    if not isinstance(children, list):
        return
    for child in children:
        if isinstance(child, dict):
            _walk_evolution_chain(
                child,
                current_species_id,
                form_index,
                variety_index,
                built_at,
                rows,
                seen,
            )


def _species_id(species: object) -> int | None:
    if not isinstance(species, dict):
        return None
    try:
        return int(_url_resource_id(str(species.get("url") or "")))
    except (TypeError, ValueError):
        return None


def _evolution_condition(detail: dict[str, object]) -> dict[str, object]:
    condition: dict[str, object] = {}
    for key, value in detail.items():
        if key == "trigger" or value in (None, False, "", 0):
            continue
        if isinstance(value, dict):
            normalized = value.get("name") or value.get("url")
        else:
            normalized = value
        if normalized not in (None, False, "", 0):
            condition[key] = normalized
    return condition


def _trigger_summary(trigger_type: str, condition: dict[str, object]) -> str:
    if condition.get("item"):
        return str(condition["item"])
    if condition.get("min_level"):
        return f"level {condition['min_level']}"
    if condition.get("held_item"):
        return f"hold {condition['held_item']}"
    if condition.get("known_move"):
        return f"know {condition['known_move']}"
    if condition.get("location"):
        return f"at {condition['location']}"
    if condition.get("time_of_day"):
        return f"{condition['time_of_day']} {trigger_type}"
    return trigger_type


def _fallback_evolutions(
    form_rows: list[dict[str, object]],
    form_index: dict[int, str],
    built_at: str,
) -> list[dict[str, object]]:
    rows = []
    for form in form_rows:
        evolves_from_id = form.get("evolves_from_id")
        if not isinstance(evolves_from_id, int):
            continue
        from_form_id = form_index.get(evolves_from_id)
        to_form_id = str(form["form_id"])
        if not from_form_id:
            continue
        rows.append(
            {
                "rule_id": rule_uuid(from_form_id, to_form_id, "unknown", "evolves_from"),
                "from_form_id": from_form_id,
                "to_form_id": to_form_id,
                "trigger_type": "unknown",
                "trigger_value": "condition unavailable",
                "condition_json": "{}",
                "updated_at": built_at,
            }
        )
    return rows


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
