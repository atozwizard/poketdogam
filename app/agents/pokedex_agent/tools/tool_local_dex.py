# Run: python app/agents/pokedex_agent/tools/tool_local_dex.py
from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.matching import rank_aliases
from app.config.settings import get_settings
from app.schemas.domain import ScanCandidate


def resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


class LocalDexStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        settings = get_settings()
        self.db_path = resolve_project_path(str(db_path or settings.dex_sqlite_path))

    def is_available(self) -> bool:
        return self.db_path.exists()

    def dataset_meta(self) -> dict[str, Any]:
        if not self.is_available():
            return {"dataset_version": "missing", "species_count": 0, "sources": []}
        with closing(self._connect()) as conn:
            row = conn.execute(
                "select dataset_version, species_count, built_at, sources_json from dataset_meta "
                "order by built_at desc limit 1"
            ).fetchone()
        if row is None:
            return {"dataset_version": "unknown", "species_count": 0, "sources": []}
        return {
            "dataset_version": row["dataset_version"],
            "species_count": row["species_count"],
            "built_at": row["built_at"],
            "sources": json.loads(row["sources_json"] or "[]"),
        }

    def match_name(
        self,
        raw_text: str,
        *,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[ScanCandidate]:
        if not self.is_available():
            return []

        settings = get_settings()
        top_k = top_k or settings.local_match_top_k
        threshold = threshold if threshold is not None else settings.local_match_threshold
        aliases = self._aliases()
        matches = rank_aliases(raw_text, aliases, top_k=top_k, threshold=threshold)
        if not matches:
            return []

        candidates: list[ScanCandidate] = []
        for match in matches:
            detail = self.get_form(match.form_id)
            if detail is None:
                continue
            candidates.append(
                ScanCandidate(
                    form_id=match.form_id,
                    pokemon_id=detail["pokemon_id"],
                    name_ko=detail["name_ko"],
                    name_en=detail.get("name_en"),
                    form_name=detail.get("form_name") or "base",
                    types=detail.get("types", []),
                    confidence=match.score,
                    matched_alias=match.matched_alias,
                    match_reason=match.reason,
                )
            )
        return candidates

    def search_first(self, query: str) -> dict[str, Any] | None:
        candidates = self.match_name(query, top_k=1, threshold=0.55)
        if not candidates:
            return None
        return self.get_form(candidates[0].form_id)

    def get_form(self, form_id: str) -> dict[str, Any] | None:
        if not self.is_available():
            return None
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                select
                    f.form_id,
                    f.pokemon_id,
                    f.form_name,
                    f.type1,
                    f.type2,
                    f.height_m,
                    f.weight_kg,
                    f.source,
                    f.updated_at,
                    s.name_ko,
                    s.name_en,
                    s.name_ja,
                    s.generation,
                    s.is_legendary,
                    st.hp,
                    st.attack,
                    st.defense,
                    st.sp_attack,
                    st.sp_defense,
                    st.speed,
                    st.bst
                from pokemon_forms f
                join pokemon_species s on s.pokemon_id = f.pokemon_id
                left join pokemon_stats st on st.form_id = f.form_id
                where f.form_id = ?
                """,
                (form_id,),
            ).fetchone()
        if row is None:
            return None

        stats = {
            "hp": row["hp"],
            "attack": row["attack"],
            "defense": row["defense"],
            "sp_attack": row["sp_attack"],
            "sp_defense": row["sp_defense"],
            "speed": row["speed"],
            "bst": row["bst"],
        }
        types = [row["type1"], row["type2"]]
        meta = self.dataset_meta()
        return {
            "form_id": row["form_id"],
            "pokemon_id": row["pokemon_id"],
            "name_ko": row["name_ko"],
            "name_en": row["name_en"],
            "name_ja": row["name_ja"],
            "generation": row["generation"],
            "is_legendary": bool(row["is_legendary"]),
            "form_name": row["form_name"],
            "types": [item for item in types if item],
            "height_m": row["height_m"],
            "weight_kg": row["weight_kg"],
            "stats": {key: value for key, value in stats.items() if value is not None},
            "source_meta": {
                "source": row["source"],
                "updated_at": row["updated_at"],
                "dataset_version": meta["dataset_version"],
            },
        }

    def _aliases(self) -> list[dict[str, str]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                select form_id, alias_text, alias_norm
                from name_aliases
                order by locale, alias_text
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def get_local_dex() -> LocalDexStore:
    return LocalDexStore()


def main() -> None:
    query = " ".join(sys.argv[1:]) or "피카추 HP 60"
    store = get_local_dex()
    if not store.is_available():
        print({"available": False, "db_path": str(store.db_path)})
        return
    print([item.model_dump() for item in store.match_name(query)])


if __name__ == "__main__":
    main()
