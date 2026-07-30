# Run: python app/agents/pokedex_agent/tools/tool_local_dex.py
from __future__ import annotations

import json
from contextlib import closing
from functools import lru_cache
from hashlib import sha256
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

    def integrity_status(self) -> dict[str, object]:
        settings = get_settings()
        meta_path = resolve_project_path(settings.dex_meta_path)
        if not self.db_path.exists() or not meta_path.exists():
            return {"valid": False, "schema_version": 0, "reason": "artifact_missing"}
        return _cached_integrity_status(
            str(self.db_path),
            self.db_path.stat().st_mtime_ns,
            self.db_path.stat().st_size,
            str(meta_path),
            meta_path.stat().st_mtime_ns,
        )

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
        return sorted(
            candidates,
            key=lambda item: (
                -float(item.confidence),
                item.form_name != "base",
                int(item.pokemon_id or 0),
                item.form_id,
            ),
        )[:top_k]

    def search_first(self, query: str) -> dict[str, Any] | None:
        candidates = self.match_name(query, top_k=1, threshold=0.55)
        if not candidates:
            return None
        return self.get_form(candidates[0].form_id)

    def search(self, query: str, *, limit: int = 10) -> list[ScanCandidate]:
        return self.match_name(query, top_k=limit, threshold=0.55)

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
                    f.canonical_key,
                    f.record_status,
                    f.localization_status,
                    f.category_en,
                    f.ability_en,
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
        normalized_types = [item for item in types if item]
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
            "types": normalized_types,
            "height_m": row["height_m"],
            "weight_kg": row["weight_kg"],
            "canonical_key": row["canonical_key"],
            "record_status": row["record_status"],
            "localization_status": row["localization_status"],
            "category_en": row["category_en"],
            "ability_en": row["ability_en"],
            "stats": {key: value for key, value in stats.items() if value is not None},
            "evolutions": self._evolutions(form_id),
            **self._type_matchups(normalized_types),
            "source_meta": {
                "source": row["source"],
                "updated_at": row["updated_at"],
                "dataset_version": meta["dataset_version"],
                "record_status": row["record_status"],
                "localization_status": row["localization_status"],
            },
        }

    def _evolutions(self, form_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                select
                    e.from_form_id,
                    e.to_form_id,
                    e.trigger_type,
                    e.trigger_value,
                    e.condition_json,
                    source_species.name_ko as from_name,
                    target_species.name_ko as to_name
                from evolution_rules e
                join pokemon_forms source_form on source_form.form_id = e.from_form_id
                join pokemon_species source_species on source_species.pokemon_id = source_form.pokemon_id
                join pokemon_forms target_form on target_form.form_id = e.to_form_id
                join pokemon_species target_species on target_species.pokemon_id = target_form.pokemon_id
                where e.from_form_id = ? or e.to_form_id = ?
                order by source_species.pokemon_id, target_species.pokemon_id
                """,
                (form_id, form_id),
            ).fetchall()

        evolutions: list[dict[str, Any]] = []
        for row in rows:
            try:
                condition = json.loads(row["condition_json"] or "{}")
            except json.JSONDecodeError:
                condition = {}
            evolutions.append(
                {
                    "from_form_id": row["from_form_id"],
                    "to_form_id": row["to_form_id"],
                    "from_name": row["from_name"],
                    "to_name": row["to_name"],
                    "trigger_type": row["trigger_type"],
                    "trigger_value": row["trigger_value"],
                    "condition": condition if isinstance(condition, dict) else {},
                }
            )
        return evolutions

    def _type_matchups(self, defense_types: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not defense_types:
            return {"weaknesses": [], "resistances": [], "immunities": []}

        placeholders = ",".join("?" for _ in defense_types)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                select attack_type, defense_type, multiplier
                from type_chart
                where defense_type in ({placeholders})
                order by attack_type
                """,
                defense_types,
            ).fetchall()

        multipliers: dict[str, float] = {}
        for row in rows:
            attack_type = str(row["attack_type"])
            multipliers[attack_type] = multipliers.get(attack_type, 1.0) * float(row["multiplier"])

        matchups = [
            {"type": attack_type, "multiplier": round(multiplier, 2)}
            for attack_type, multiplier in multipliers.items()
        ]
        weaknesses = sorted(
            (item for item in matchups if item["multiplier"] > 1.0),
            key=lambda item: (-item["multiplier"], item["type"]),
        )
        resistances = sorted(
            (item for item in matchups if 0.0 < item["multiplier"] < 1.0),
            key=lambda item: (item["multiplier"], item["type"]),
        )
        immunities = sorted(
            (item for item in matchups if item["multiplier"] == 0.0),
            key=lambda item: item["type"],
        )
        return {
            "weaknesses": weaknesses,
            "resistances": resistances,
            "immunities": immunities,
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
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn


def get_local_dex() -> LocalDexStore:
    return LocalDexStore()


@lru_cache(maxsize=4)
def _cached_integrity_status(
    db_path_value: str,
    db_mtime_ns: int,
    db_size: int,
    meta_path_value: str,
    meta_mtime_ns: int,
) -> dict[str, object]:
    del db_mtime_ns, meta_mtime_ns
    db_path = Path(db_path_value)
    meta_path = Path(meta_path_value)
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        expected = (metadata.get("artifacts") or {}).get("dex.sqlite") or {}
        if int(expected.get("size_bytes") or -1) != db_size:
            return {"valid": False, "schema_version": 0, "reason": "size_mismatch"}
        digest = sha256()
        with db_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != str(expected.get("sha256") or ""):
            return {"valid": False, "schema_version": 0, "reason": "sha256_mismatch"}
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
            schema_version = int(conn.execute("pragma user_version").fetchone()[0])
            quick_check = str(conn.execute("pragma quick_check").fetchone()[0])
        valid = schema_version >= 1 and quick_check == "ok"
        return {
            "valid": valid,
            "schema_version": schema_version,
            "reason": "ok" if valid else "sqlite_integrity",
        }
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error):
        return {"valid": False, "schema_version": 0, "reason": "verification_error"}


def main() -> None:
    query = " ".join(sys.argv[1:]) or "피카추 HP 60"
    store = get_local_dex()
    if not store.is_available():
        print({"available": False, "db_path": str(store.db_path)})
        return
    print([item.model_dump() for item in store.match_name(query)])


if __name__ == "__main__":
    main()
