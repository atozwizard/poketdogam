# Run: python scripts/build_local_dex/normalize_dex.py
from __future__ import annotations

from pathlib import Path
from pprint import pprint
import sys
from uuid import NAMESPACE_URL, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_local_dex.seed_data import EVOLUTION_SEED, POKEMON_SEED


def form_uuid(pokemon_id: int, form_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"poketdogam:form:{pokemon_id}:{form_name}"))


def rule_uuid(from_form_id: str, to_form_id: str, trigger_type: str, trigger_value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"poketdogam:evolution:{from_form_id}:{to_form_id}:{trigger_type}:{trigger_value}"))


def normalize_seed_records(built_at: str) -> dict[str, list[dict[str, object]]]:
    species_rows: list[dict[str, object]] = []
    form_rows: list[dict[str, object]] = []
    stat_rows: list[dict[str, object]] = []
    form_index: dict[tuple[int, str], str] = {}

    for item in POKEMON_SEED:
        pokemon_id = int(item["pokemon_id"])
        names = item["names"]
        assert isinstance(names, dict)
        species_rows.append(
            {
                "pokemon_id": pokemon_id,
                "name_ko": names.get("ko", ""),
                "name_en": names.get("en", ""),
                "name_ja": names.get("ja", ""),
                "generation": int(item["generation"]),
                "is_legendary": int(bool(item.get("is_legendary", False))),
                "source": "seed:pokeapi-compatible",
                "created_at": built_at,
                "updated_at": built_at,
            }
        )

        for form in item["forms"]:
            assert isinstance(form, dict)
            form_name = str(form["form_name"])
            form_id = form_uuid(pokemon_id, form_name)
            types = list(form["types"])
            stats = dict(form["stats"])
            form_index[(pokemon_id, form_name)] = form_id
            form_rows.append(
                {
                    "form_id": form_id,
                    "pokemon_id": pokemon_id,
                    "form_name": form_name,
                    "type1": types[0],
                    "type2": types[1] if len(types) > 1 else None,
                    "height_m": form.get("height_m"),
                    "weight_kg": form.get("weight_kg"),
                    "source": "seed:pokeapi-compatible",
                    "updated_at": built_at,
                    "names": names,
                    "aliases": form.get("aliases", []),
                }
            )
            stat_rows.append(
                {
                    "form_id": form_id,
                    "hp": int(stats["hp"]),
                    "attack": int(stats["attack"]),
                    "defense": int(stats["defense"]),
                    "sp_attack": int(stats["sp_attack"]),
                    "sp_defense": int(stats["sp_defense"]),
                    "speed": int(stats["speed"]),
                    "bst": sum(int(value) for value in stats.values()),
                }
            )

    evolution_rows: list[dict[str, object]] = []
    for rule in EVOLUTION_SEED:
        from_key = rule["from"]
        to_key = rule["to"]
        assert isinstance(from_key, tuple)
        assert isinstance(to_key, tuple)
        from_form_id = form_index[(int(from_key[0]), str(from_key[1]))]
        to_form_id = form_index[(int(to_key[0]), str(to_key[1]))]
        trigger_type = str(rule["trigger_type"])
        trigger_value = str(rule["trigger_value"])
        evolution_rows.append(
            {
                "rule_id": rule_uuid(from_form_id, to_form_id, trigger_type, trigger_value),
                "from_form_id": from_form_id,
                "to_form_id": to_form_id,
                "trigger_type": trigger_type,
                "trigger_value": trigger_value,
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


def main() -> None:
    normalized = normalize_seed_records("2026-07-28T00:00:00+09:00")
    pprint({key: len(value) for key, value in normalized.items()})


if __name__ == "__main__":
    main()
