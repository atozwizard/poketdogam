# Run: python scripts/build_local_dex/seed_data.py
from __future__ import annotations

from pprint import pprint


POKEMON_SEED: list[dict[str, object]] = [
    {
        "pokemon_id": 1,
        "names": {"ko": "이상해씨", "en": "Bulbasaur", "ja": "フシギダネ"},
        "generation": 1,
        "is_legendary": False,
        "forms": [
            {
                "form_name": "base",
                "types": ["grass", "poison"],
                "height_m": 0.7,
                "weight_kg": 6.9,
                "stats": {"hp": 45, "attack": 49, "defense": 49, "sp_attack": 65, "sp_defense": 65, "speed": 45},
                "aliases": ["이상해 씨", "bulba saur"],
            }
        ],
    },
    {
        "pokemon_id": 4,
        "names": {"ko": "파이리", "en": "Charmander", "ja": "ヒトカゲ"},
        "generation": 1,
        "is_legendary": False,
        "forms": [
            {
                "form_name": "base",
                "types": ["fire"],
                "height_m": 0.6,
                "weight_kg": 8.5,
                "stats": {"hp": 39, "attack": 52, "defense": 43, "sp_attack": 60, "sp_defense": 50, "speed": 65},
                "aliases": ["파이 리", "char mander"],
            }
        ],
    },
    {
        "pokemon_id": 7,
        "names": {"ko": "꼬부기", "en": "Squirtle", "ja": "ゼニガメ"},
        "generation": 1,
        "is_legendary": False,
        "forms": [
            {
                "form_name": "base",
                "types": ["water"],
                "height_m": 0.5,
                "weight_kg": 9.0,
                "stats": {"hp": 44, "attack": 48, "defense": 65, "sp_attack": 50, "sp_defense": 64, "speed": 43},
                "aliases": ["꼬북이", "꼬 부기"],
            }
        ],
    },
    {
        "pokemon_id": 25,
        "names": {"ko": "피카츄", "en": "Pikachu", "ja": "ピカチュウ"},
        "generation": 1,
        "is_legendary": False,
        "forms": [
            {
                "form_name": "base",
                "types": ["electric"],
                "height_m": 0.4,
                "weight_kg": 6.0,
                "stats": {"hp": 35, "attack": 55, "defense": 40, "sp_attack": 50, "sp_defense": 50, "speed": 90},
                "aliases": ["피카추", "피카 츄", "피까츄", "pikachu ex", "pikachu v", "피카츄 ex", "피카츄 v"],
            }
        ],
    },
    {
        "pokemon_id": 26,
        "names": {"ko": "라이츄", "en": "Raichu", "ja": "ライチュウ"},
        "generation": 1,
        "is_legendary": False,
        "forms": [
            {
                "form_name": "base",
                "types": ["electric"],
                "height_m": 0.8,
                "weight_kg": 30.0,
                "stats": {"hp": 60, "attack": 90, "defense": 55, "sp_attack": 90, "sp_defense": 80, "speed": 110},
                "aliases": ["라이 추", "raichu ex"],
            },
            {
                "form_name": "alola",
                "types": ["electric", "psychic"],
                "height_m": 0.7,
                "weight_kg": 21.0,
                "stats": {"hp": 60, "attack": 85, "defense": 50, "sp_attack": 95, "sp_defense": 85, "speed": 110},
                "aliases": ["알로라 라이츄", "alolan raichu", "라이츄 알로라"],
            },
        ],
    },
    {
        "pokemon_id": 133,
        "names": {"ko": "이브이", "en": "Eevee", "ja": "イーブイ"},
        "generation": 1,
        "is_legendary": False,
        "forms": [
            {
                "form_name": "base",
                "types": ["normal"],
                "height_m": 0.3,
                "weight_kg": 6.5,
                "stats": {"hp": 55, "attack": 55, "defense": 50, "sp_attack": 45, "sp_defense": 65, "speed": 55},
                "aliases": ["이 부이", "eevee ex", "eevee v"],
            }
        ],
    },
    {
        "pokemon_id": 150,
        "names": {"ko": "뮤츠", "en": "Mewtwo", "ja": "ミュウツー"},
        "generation": 1,
        "is_legendary": True,
        "forms": [
            {
                "form_name": "base",
                "types": ["psychic"],
                "height_m": 2.0,
                "weight_kg": 122.0,
                "stats": {"hp": 106, "attack": 110, "defense": 90, "sp_attack": 154, "sp_defense": 90, "speed": 130},
                "aliases": ["뮤 투", "mew two", "mewtwo ex"],
            }
        ],
    },
    {
        "pokemon_id": 172,
        "names": {"ko": "피츄", "en": "Pichu", "ja": "ピチュー"},
        "generation": 2,
        "is_legendary": False,
        "forms": [
            {
                "form_name": "base",
                "types": ["electric"],
                "height_m": 0.3,
                "weight_kg": 2.0,
                "stats": {"hp": 20, "attack": 40, "defense": 15, "sp_attack": 35, "sp_defense": 35, "speed": 60},
                "aliases": ["피 추", "pichu"],
            }
        ],
    },
    {
        "pokemon_id": 1025,
        "names": {"ko": "복숭악동", "en": "Pecharunt", "ja": "モモワロウ"},
        "generation": 9,
        "is_legendary": True,
        "forms": [
            {
                "form_name": "base",
                "types": ["poison", "ghost"],
                "height_m": 0.3,
                "weight_kg": 0.3,
                "stats": {"hp": 88, "attack": 88, "defense": 160, "sp_attack": 88, "sp_defense": 88, "speed": 88},
                "aliases": ["복숭 악동", "pecharunt"],
            }
        ],
    },
]


EVOLUTION_SEED: list[dict[str, object]] = [
    {"from": (172, "base"), "to": (25, "base"), "trigger_type": "friendship", "trigger_value": "high_friendship"},
    {"from": (25, "base"), "to": (26, "base"), "trigger_type": "item", "trigger_value": "thunder_stone"},
]


def main() -> None:
    pprint({"species_count": len(POKEMON_SEED), "evolution_count": len(EVOLUTION_SEED)})


if __name__ == "__main__":
    main()
