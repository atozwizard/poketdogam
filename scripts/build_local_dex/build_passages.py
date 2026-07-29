# Run: python scripts/build_local_dex/build_passages.py
from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.rag.embeddings import encode_embedding, hash_embed


def build_passage_rows(
    species: list[dict[str, object]],
    forms: list[dict[str, object]],
    stats: list[dict[str, object]],
    evolutions: list[dict[str, object]],
    built_at: str,
) -> list[dict[str, object]]:
    species_by_id = {int(item["pokemon_id"]): item for item in species}
    stats_by_form = {str(item["form_id"]): item for item in stats}
    evo_by_from: dict[str, list[dict[str, object]]] = {}
    for rule in evolutions:
        evo_by_from.setdefault(str(rule["from_form_id"]), []).append(rule)

    rows: list[dict[str, object]] = []
    for form in forms:
        form_id = str(form["form_id"])
        pokemon_id = int(form["pokemon_id"])
        species_row = species_by_id.get(pokemon_id, {})
        names = form.get("names") if isinstance(form.get("names"), dict) else {}
        name_ko = str(names.get("ko") or species_row.get("name_ko") or "")
        name_en = str(names.get("en") or species_row.get("name_en") or "")
        types = [str(form.get("type1") or "")]
        if form.get("type2"):
            types.append(str(form["type2"]))
        type_text = "/".join(types)
        aliases = form.get("aliases") if isinstance(form.get("aliases"), list) else []
        alias_text = " ".join(str(item) for item in aliases)

        profile_body = (
            f"{name_ko}({name_en})는 {species_row.get('generation')}세대 "
            f"{type_text} 타입 포켓몬이다."
        )
        rows.append(
            _passage(
                form_id,
                "profile",
                f"{name_ko} 기본 정보",
                profile_body,
                f"[name] {name_ko} {name_en} | [types] {type_text} | [aliases] {alias_text}",
                built_at,
            )
        )

        stat = stats_by_form.get(form_id)
        if stat:
            stats_body = (
                f"{name_ko} 종족값 HP {stat['hp']}, 공격 {stat['attack']}, 방어 {stat['defense']}, "
                f"특공 {stat['sp_attack']}, 특방 {stat['sp_defense']}, 스피드 {stat['speed']}, "
                f"합계 {stat['bst']}."
            )
            rows.append(
                _passage(
                    form_id,
                    "stats",
                    f"{name_ko} 종족값",
                    stats_body,
                    f"[name] {name_ko} | [facet] stats | {stats_body}",
                    built_at,
                )
            )

        evo_rules = evo_by_from.get(form_id, [])
        if evo_rules:
            evo_body = f"{name_ko} 진화 규칙 {len(evo_rules)}건이 로컬 도감에 있다."
            rows.append(
                _passage(
                    form_id,
                    "evolution",
                    f"{name_ko} 진화",
                    evo_body,
                    f"[name] {name_ko} | [facet] evolution | {evo_body}",
                    built_at,
                )
            )

        rows.append(
            _passage(
                form_id,
                "type",
                f"{name_ko} 타입",
                f"{name_ko}의 타입은 {type_text}이다.",
                f"[name] {name_ko} | [facet] type | [types] {type_text}",
                built_at,
            )
        )
    return rows


def _passage(
    form_id: str,
    facet: str,
    title: str,
    body: str,
    searchable_text: str,
    built_at: str,
) -> dict[str, object]:
    passage_id = str(uuid5(NAMESPACE_URL, f"poketdogam:passage:{form_id}:{facet}:{title}"))
    embedding = hash_embed(searchable_text)
    return {
        "passage_id": passage_id,
        "form_id": form_id,
        "facet": facet,
        "title": title,
        "body": body,
        "searchable_text": searchable_text,
        "embedding_blob": encode_embedding(embedding),
        "updated_at": built_at,
    }


def main() -> None:
    print("Use build.py / collector pipeline to generate passages.")


if __name__ == "__main__":
    main()
