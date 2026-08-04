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


# All-generation visual embeddings (esp. Gen7–9 aug densification) exceed 32MB.
MAX_DEX_BYTES = 96 * 1024 * 1024


def validate(
    db_path: Path,
    fixture_path: Path | None = None,
    *,
    min_species: int = 1,
    max_db_bytes: int = MAX_DEX_BYTES,
    min_fixture_count: int = 1,
    require_nonbase_forms: bool = False,
    require_evolution_conditions: bool = False,
    require_provenance: bool = False,
    require_gen1_visual_coverage: bool = False,
    require_all_announced_generations: bool = False,
    min_official_previews: int = 0,
) -> dict[str, object]:
    if not db_path.exists():
        raise FileNotFoundError(f"dex sqlite does not exist: {db_path}")

    with closing(sqlite3.connect(db_path)) as conn:
        counts = {
            "species": _count(conn, "pokemon_species"),
            "forms": _count(conn, "pokemon_forms"),
            "nonbase_forms": int(
                conn.execute("select count(*) from pokemon_forms where form_name != 'base'").fetchone()[0]
            ),
            "evolution_rules": _count(conn, "evolution_rules"),
            "evolution_conditions": int(
                conn.execute(
                    "select count(*) from evolution_rules where condition_json not in ('', '{}')"
                ).fetchone()[0]
            ),
            "aliases": _count(conn, "name_aliases"),
            "type_chart": _count(conn, "type_chart"),
            "canonical_species": int(
                conn.execute(
                    """
                    select count(distinct pokemon_id)
                    from pokemon_forms
                    where record_status = 'canonical'
                    """
                ).fetchone()[0]
            ),
            "official_previews": int(
                conn.execute(
                    """
                    select count(distinct pokemon_id)
                    from pokemon_forms
                    where record_status = 'officially_announced_unnumbered'
                    """
                ).fetchone()[0]
            ),
            "generation_1_species": int(
                conn.execute(
                    "select count(*) from pokemon_species where generation = 1"
                ).fetchone()[0]
            ),
            "generation_1_forms": int(
                conn.execute(
                    """
                    select count(*)
                    from pokemon_forms f
                    join pokemon_species s on s.pokemon_id = f.pokemon_id
                    where s.generation = 1
                    """
                ).fetchone()[0]
            ),
            "visual_references": _count(conn, "visual_reference_embeddings"),
            "generation_1_visual_forms": int(
                conn.execute(
                    """
                    select count(distinct v.form_id)
                    from visual_reference_embeddings v
                    join pokemon_forms f on f.form_id = v.form_id
                    join pokemon_species s on s.pokemon_id = f.pokemon_id
                    where s.generation = 1
                    """
                ).fetchone()[0]
            ),
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
        missing_names = int(
            conn.execute(
                """
                select count(*) from pokemon_species
                where trim(name_ko) = '' or trim(name_en) = ''
                """
            ).fetchone()[0]
        )
        orphan_foreign_keys = len(conn.execute("pragma foreign_key_check").fetchall())
        meta_row = conn.execute(
            "select sources_json from dataset_meta order by built_at desc limit 1"
        ).fetchone()
        sources = json.loads(meta_row[0]) if meta_row and meta_row[0] else []
        covered_generations = [
            int(row[0])
            for row in conn.execute(
                "select distinct generation from pokemon_species order by generation"
            )
        ]
        schema_version = int(conn.execute("pragma user_version").fetchone()[0])
        quick_check = str(conn.execute("pragma quick_check").fetchone()[0])
        indexes = {
            str(row[0])
            for row in conn.execute(
                """
                select name from sqlite_master
                where type = 'index' and name is not null
                """
            ).fetchall()
        }

    db_size_bytes = db_path.stat().st_size
    if counts["species"] < min_species or counts["forms"] == 0 or counts["aliases"] == 0:
        raise ValueError(f"local dex has empty required tables: {counts}")
    if db_size_bytes > max_db_bytes:
        raise ValueError(f"local dex exceeds size gate: {db_size_bytes} > {max_db_bytes}")
    if counts["type_chart"] != 324:
        raise ValueError(f"type_chart must contain 18x18 rows, got {counts['type_chart']}")
    if duplicate_aliases:
        raise ValueError(f"duplicate aliases found: {duplicate_aliases}")
    if missing_names:
        raise ValueError(f"required localized names missing: {missing_names}")
    if orphan_foreign_keys:
        raise ValueError(f"orphan foreign keys found: {orphan_foreign_keys}")
    if schema_version != 1:
        raise ValueError(f"schema version must be 1, got {schema_version}")
    if quick_check != "ok":
        raise ValueError(f"sqlite quick_check failed: {quick_check}")
    required_indexes = {
        "idx_evolution_from",
        "idx_evolution_to",
        "idx_visual_reference_form",
        "idx_visual_reference_model",
    }
    missing_indexes = sorted(required_indexes - indexes)
    if missing_indexes:
        raise ValueError(f"required indexes missing: {missing_indexes}")
    if require_nonbase_forms and counts["nonbase_forms"] == 0:
        raise ValueError("non-base form coverage is required")
    if require_evolution_conditions and counts["evolution_conditions"] == 0:
        raise ValueError("evolution condition coverage is required")
    if require_provenance:
        if not isinstance(sources, list) or not sources:
            raise ValueError("dataset provenance sources are required")
        missing_provenance = [
            source.get("name", "unknown")
            for source in sources
            if not isinstance(source, dict)
            or not source.get("url")
            or not source.get("usage_scope")
            or not source.get("license_status")
            or not source.get("content_policy")
        ]
        if missing_provenance:
            raise ValueError(f"dataset provenance incomplete: {missing_provenance}")
    if counts["official_previews"] < min_official_previews:
        raise ValueError(
            "official preview coverage below gate: "
            f"{counts['official_previews']} < {min_official_previews}"
        )
    if require_gen1_visual_coverage:
        if counts["generation_1_species"] != 151:
            raise ValueError(
                f"generation 1 species coverage must be 151, got {counts['generation_1_species']}"
            )
        if counts["generation_1_visual_forms"] != counts["generation_1_forms"]:
            raise ValueError(
                "generation 1 visual coverage incomplete: "
                f"{counts['generation_1_visual_forms']} / {counts['generation_1_forms']}"
            )
    if require_all_announced_generations:
        missing_generations = sorted(set(range(1, 11)) - set(covered_generations))
        if missing_generations:
            raise ValueError(f"announced generation coverage incomplete: {missing_generations}")

    fixture_result = None
    if fixture_path is not None and fixture_path.exists():
        fixture_result = validate_fixtures(db_path, fixture_path)
        if fixture_result["total"] < min_fixture_count:
            raise ValueError(
                f"fixture count below gate: {fixture_result['total']} < {min_fixture_count}"
            )
        if fixture_result["match_recall_at_3"] < 0.9:
            raise ValueError(f"fixture match@3 below gate: {fixture_result}")

    return {
        "counts": counts,
        "db_size_bytes": db_size_bytes,
        "missing_names": missing_names,
        "orphan_foreign_keys": orphan_foreign_keys,
        "schema_version": schema_version,
        "sqlite_quick_check": quick_check,
        "provenance_source_count": len(sources) if isinstance(sources, list) else 0,
        "covered_generations": covered_generations,
        "fixture": fixture_result,
    }


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
    parser.add_argument("--min-species", type=int, default=1028)
    parser.add_argument("--min-official-previews", type=int, default=3)
    parser.add_argument("--min-fixtures", type=int, default=30)
    parser.add_argument("--allow-base-only", action="store_true")
    parser.add_argument("--allow-missing-evolution-conditions", action="store_true")
    parser.add_argument("--allow-incomplete-gen1-visual", action="store_true")
    args = parser.parse_args()
    result = validate(
        PROJECT_ROOT / args.db_path,
        PROJECT_ROOT / args.fixtures,
        min_species=args.min_species,
        min_fixture_count=args.min_fixtures,
        require_nonbase_forms=not args.allow_base_only,
        require_evolution_conditions=not args.allow_missing_evolution_conditions,
        require_provenance=True,
        require_gen1_visual_coverage=not args.allow_incomplete_gen1_visual,
        require_all_announced_generations=True,
        min_official_previews=args.min_official_previews,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
