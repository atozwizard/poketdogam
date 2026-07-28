# Run: python app/agents/pokedex_agent/rag/expand_hops.py
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def expand_hops(
    db_path: Path,
    *,
    form_id: str,
    facet: str,
    hop_limit: int = 2,
) -> dict[str, object]:
    if not form_id or not db_path.exists():
        return {"evolutions": [], "type_relations": [], "trace": []}

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        evolutions: list[dict[str, object]] = []
        type_relations: list[dict[str, object]] = []
        trace: list[dict[str, object]] = []

        if facet in {"evolution", "profile"} and hop_limit >= 1:
            evo_rows = conn.execute(
                """
                select e.rule_id, e.from_form_id, e.to_form_id, e.trigger_type, e.trigger_value,
                       sf.name_ko as from_name, st.name_ko as to_name
                from evolution_rules e
                join pokemon_forms ff on ff.form_id = e.from_form_id
                join pokemon_species sf on sf.pokemon_id = ff.pokemon_id
                join pokemon_forms tf on tf.form_id = e.to_form_id
                join pokemon_species st on st.pokemon_id = tf.pokemon_id
                where e.from_form_id = ? or e.to_form_id = ?
                """,
                (form_id, form_id),
            ).fetchall()
            evolutions = [dict(row) for row in evo_rows]
            trace.append({"hop": 1, "type": "evolution", "count": len(evolutions)})

        if facet in {"weakness", "resistance", "type", "profile"} and hop_limit >= 1:
            form = conn.execute(
                "select type1, type2 from pokemon_forms where form_id = ?",
                (form_id,),
            ).fetchone()
            if form is not None:
                types = [form["type1"]] + ([form["type2"]] if form["type2"] else [])
                for defense_type in types:
                    if facet in {"weakness", "profile"}:
                        rows = conn.execute(
                            """
                            select attack_type, defense_type, multiplier
                            from type_chart
                            where defense_type = ? and multiplier >= 2.0
                            order by multiplier desc
                            """,
                            (defense_type,),
                        ).fetchall()
                        type_relations.extend(dict(row) | {"relation": "weak_to"} for row in rows)
                    if facet in {"resistance", "profile"}:
                        rows = conn.execute(
                            """
                            select attack_type, defense_type, multiplier
                            from type_chart
                            where defense_type = ? and multiplier > 0 and multiplier <= 0.5
                            order by multiplier asc
                            """,
                            (defense_type,),
                        ).fetchall()
                        type_relations.extend(dict(row) | {"relation": "resists"} for row in rows)
                trace.append({"hop": 1, "type": "type_chart", "count": len(type_relations)})

    return {"evolutions": evolutions, "type_relations": type_relations[:24], "trace": trace}


def main() -> None:
    from app.agents.pokedex_agent.tools.tool_local_dex import LocalDexStore

    store = LocalDexStore()
    detail = store.search_first("피카츄")
    if detail:
        print(expand_hops(store.db_path, form_id=detail["form_id"], facet="weakness"))


if __name__ == "__main__":
    main()
