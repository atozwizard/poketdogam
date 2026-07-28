# Run: python scripts/build_local_dex/export_sqlite.py
from __future__ import annotations

from pathlib import Path
from contextlib import closing
import json
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def export_sqlite(
    db_path: Path,
    *,
    dataset_version: str,
    built_at: str,
    sources: list[dict[str, str]],
    species: list[dict[str, object]],
    forms: list[dict[str, object]],
    stats: list[dict[str, object]],
    evolutions: list[dict[str, object]],
    aliases: list[dict[str, object]],
    type_chart: list[dict[str, object]],
    passages: list[dict[str, object]] | None = None,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("pragma foreign_keys = on")
        _create_schema(conn)
        _insert_rows(conn, "pokemon_species", species)
        _insert_rows(conn, "pokemon_forms", [_strip_runtime_fields(row) for row in forms])
        _insert_rows(conn, "pokemon_stats", stats)
        _insert_rows(conn, "evolution_rules", evolutions)
        _insert_rows(conn, "name_aliases", aliases)
        _insert_rows(conn, "type_chart", type_chart)
        _insert_rows(conn, "dex_passages", passages or [])
        conn.execute(
            """
            insert into dataset_meta(dataset_version, species_count, built_at, sources_json)
            values (?, ?, ?, ?)
            """,
            (dataset_version, len(species), built_at, json.dumps(sources, ensure_ascii=False)),
        )
        conn.commit()


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table pokemon_species (
            pokemon_id integer primary key,
            name_ko text not null,
            name_en text not null,
            name_ja text,
            generation integer not null,
            is_legendary integer not null default 0,
            source text not null,
            created_at text not null,
            updated_at text not null
        );

        create table pokemon_forms (
            form_id text primary key,
            pokemon_id integer not null references pokemon_species(pokemon_id),
            form_name text not null,
            type1 text not null,
            type2 text,
            height_m real,
            weight_kg real,
            rarity_tier text,
            source text not null,
            updated_at text not null,
            unique(pokemon_id, form_name)
        );

        create index idx_pokemon_forms_type1 on pokemon_forms(type1);
        create index idx_pokemon_forms_type2 on pokemon_forms(type2);

        create table pokemon_stats (
            form_id text primary key references pokemon_forms(form_id),
            hp integer not null,
            attack integer not null,
            defense integer not null,
            sp_attack integer not null,
            sp_defense integer not null,
            speed integer not null,
            bst integer not null
        );

        create table evolution_rules (
            rule_id text primary key,
            from_form_id text not null references pokemon_forms(form_id),
            to_form_id text not null references pokemon_forms(form_id),
            trigger_type text not null,
            trigger_value text,
            condition_json text not null default '{}',
            updated_at text not null
        );

        create table type_chart (
            attack_type text not null,
            defense_type text not null,
            multiplier real not null,
            primary key (attack_type, defense_type)
        );

        create table name_aliases (
            alias_id text primary key,
            form_id text not null references pokemon_forms(form_id),
            locale text not null,
            alias_text text not null,
            alias_norm text not null,
            source text not null,
            updated_at text not null,
            unique(form_id, locale, alias_norm)
        );

        create index idx_name_aliases_norm on name_aliases(alias_norm);

        create table tcg_cards (
            tcg_id text primary key,
            form_id text references pokemon_forms(form_id),
            name_printed text not null,
            set_code text,
            collector_number text,
            locale text not null,
            source text not null,
            updated_at text not null
        );

        create table manual_stubs (
            stub_id text primary key,
            pokemon_id integer,
            name_ko text not null,
            name_en text,
            status text not null,
            source_url text not null,
            notes text,
            updated_at text not null
        );

        create table dataset_meta (
            dataset_version text primary key,
            species_count integer not null,
            built_at text not null,
            sources_json text not null
        );

        create table dex_passages (
            passage_id text primary key,
            form_id text not null references pokemon_forms(form_id),
            facet text not null,
            title text not null,
            body text not null,
            searchable_text text not null,
            embedding_csv text not null,
            updated_at text not null
        );
        create index idx_dex_passages_form on dex_passages(form_id);
        create index idx_dex_passages_facet on dex_passages(facet);
        """
    )


def _insert_rows(conn: sqlite3.Connection, table: str, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(columns))
    column_sql = ", ".join(columns)
    sql = f"insert into {table} ({column_sql}) values ({placeholders})"
    conn.executemany(sql, [[row.get(column) for column in columns] for row in rows])


def _strip_runtime_fields(row: dict[str, object]) -> dict[str, object]:
    blocked = {"names", "aliases", "evolves_from_id"}
    return {key: value for key, value in row.items() if key not in blocked}


def main() -> None:
    print("Use scripts/build_local_dex/build.py to export a complete dex.sqlite")


if __name__ == "__main__":
    main()
