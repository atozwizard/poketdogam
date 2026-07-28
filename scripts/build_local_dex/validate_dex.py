# Run: python scripts/build_local_dex/validate_dex.py data/dex.sqlite
from __future__ import annotations

from pathlib import Path
import argparse
from contextlib import closing
import json
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.tools.tool_local_dex import LocalDexStore


def validate(db_path: Path, fixture_path: Path | None = None) -> dict[str, object]:
    if not db_path.exists():
        raise FileNotFoundError(f"dex sqlite does not exist: {db_path}")

    with closing(sqlite3.connect(db_path)) as conn:
        counts = {
            "species": _count(conn, "pokemon_species"),
            "forms": _count(conn, "pokemon_forms"),
            "aliases": _count(conn, "name_aliases"),
            "type_chart": _count(conn, "type_chart"),
        }
        duplicate_aliases = conn.execute(
            """
            select count(*) from (
                select form_id, locale, alias_norm, count(*) as count
                from name_aliases
                group by form_id, locale, alias_norm
                having count > 1
            )
            """
        ).fetchone()[0]

    if counts["species"] == 0 or counts["forms"] == 0 or counts["aliases"] == 0:
        raise ValueError(f"local dex has empty required tables: {counts}")
    if counts["type_chart"] != 324:
        raise ValueError(f"type_chart must contain 18x18 rows, got {counts['type_chart']}")
    if duplicate_aliases:
        raise ValueError(f"duplicate aliases found: {duplicate_aliases}")

    fixture_result = None
    if fixture_path is not None and fixture_path.exists():
        fixture_result = validate_fixtures(db_path, fixture_path)
        if fixture_result["match_recall_at_3"] < 0.9:
            raise ValueError(f"fixture match@3 below gate: {fixture_result}")

    return {"counts": counts, "fixture": fixture_result}


def validate_fixtures(db_path: Path, fixture_path: Path) -> dict[str, object]:
    store = LocalDexStore(db_path)
    total = 0
    matched = 0
    failures: list[dict[str, object]] = []
    with fixture_path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            total += 1
            fixture = json.loads(line)
            expected_id = int(fixture["expected_pokemon_id"])
            candidates = store.match_name(str(fixture["ocr_text"]), top_k=3)
            candidate_ids = [candidate.pokemon_id for candidate in candidates]
            if expected_id in candidate_ids:
                matched += 1
            else:
                failures.append(
                    {
                        "id": fixture.get("id"),
                        "expected_pokemon_id": expected_id,
                        "candidate_ids": candidate_ids,
                    }
                )
    recall = matched / total if total else 0.0
    return {
        "total": total,
        "matched": matched,
        "match_recall_at_3": recall,
        "failures": failures,
    }


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"select count(*) from {table}").fetchone()[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("db_path", nargs="?", default="data/dex.sqlite")
    parser.add_argument("--fixtures", default="fixtures/ocr/korean_cards.jsonl")
    args = parser.parse_args()
    result = validate(PROJECT_ROOT / args.db_path, PROJECT_ROOT / args.fixtures)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
