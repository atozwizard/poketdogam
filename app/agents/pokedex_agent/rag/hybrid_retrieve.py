# Run: python app/agents/pokedex_agent/rag/hybrid_retrieve.py
"""Hybrid lexical + hash-vector retrieve with RRF (ThinkFlow/RSLF light)."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.rag.analyze_query import QueryAnalysis
from app.agents.pokedex_agent.rag.embeddings import cosine, hash_embed
from app.agents.pokedex_agent.rag.expand_hops import expand_hops
from app.agents.pokedex_agent.tools.tool_local_dex import LocalDexStore


def rrf_fuse(rank_lists: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranked in rank_lists:
        for rank, item_id in enumerate(ranked, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


def hybrid_retrieve(
    query: str,
    analysis: QueryAnalysis,
    *,
    form_id: str | None = None,
    top_k: int = 5,
    db_path: Path | None = None,
) -> dict[str, object]:
    store = LocalDexStore(db_path)
    if not store.is_available():
        return {"detail": None, "passages": [], "hops": {}, "scores": {}, "strategy": "unavailable"}

    detail = store.get_form(form_id) if form_id else None
    if detail is None:
        detail = store.search_first(analysis.normalized) or store.search_first(query)

    lexical_ids = _lexical_passage_ids(store.db_path, analysis.search_queries, form_id=detail["form_id"] if detail else None)
    vector_ids = _vector_passage_ids(store.db_path, analysis.search_queries, form_id=detail["form_id"] if detail else None)
    fused = rrf_fuse([lexical_ids, vector_ids])
    passage_ids = [item_id for item_id, _ in fused[:top_k]]
    passages = _fetch_passages(store.db_path, passage_ids)

    hops = {}
    if detail is not None:
        hops = expand_hops(store.db_path, form_id=detail["form_id"], facet=analysis.facet, hop_limit=2)

    return {
        "detail": detail,
        "passages": passages,
        "hops": hops,
        "scores": {item_id: score for item_id, score in fused[:top_k]},
        "strategy": "hybrid_rrf+hash+graph_hops",
        "facet": analysis.facet,
        "rewritten_query": analysis.normalized,
    }


def _lexical_passage_ids(db_path: Path, queries: list[str], *, form_id: str | None) -> list[str]:
    if not _has_passages(db_path):
        return []
    ids: list[str] = []
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        for query in queries:
            like = f"%{query.split()[0]}%" if query else "%"
            sql = "select passage_id from dex_passages where searchable_text like ?"
            params: list[object] = [like]
            if form_id:
                sql += " and form_id = ?"
                params.append(form_id)
            sql += " limit 20"
            for row in conn.execute(sql, params).fetchall():
                if row["passage_id"] not in ids:
                    ids.append(row["passage_id"])
        if form_id and not ids:
            for row in conn.execute(
                "select passage_id from dex_passages where form_id = ? limit 10",
                (form_id,),
            ).fetchall():
                ids.append(row["passage_id"])
    return ids


def _vector_passage_ids(db_path: Path, queries: list[str], *, form_id: str | None) -> list[str]:
    if not _has_passages(db_path):
        return []
    query_vec = hash_embed(" ".join(queries))
    scored: list[tuple[str, float]] = []
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        sql = "select passage_id, embedding_csv, form_id from dex_passages"
        rows = conn.execute(sql).fetchall()
        for row in rows:
            if form_id and row["form_id"] != form_id:
                # still allow some global recall, but soft-prioritize later via RRF lists
                pass
            emb = [float(part) for part in str(row["embedding_csv"] or "").split(",") if part]
            if not emb:
                continue
            score = cosine(query_vec, emb)
            if form_id and row["form_id"] == form_id:
                score += 0.05
            scored.append((row["passage_id"], score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return [passage_id for passage_id, _ in scored[:20]]


def _fetch_passages(db_path: Path, passage_ids: list[str]) -> list[dict[str, object]]:
    if not passage_ids or not _has_passages(db_path):
        return []
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in passage_ids)
        rows = conn.execute(
            f"""
            select passage_id, form_id, facet, title, body, searchable_text
            from dex_passages
            where passage_id in ({placeholders})
            """,
            passage_ids,
        ).fetchall()
    by_id = {row["passage_id"]: dict(row) for row in rows}
    return [by_id[item_id] for item_id in passage_ids if item_id in by_id]


def _has_passages(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            "select name from sqlite_master where type='table' and name='dex_passages'"
        ).fetchone()
    return row is not None


def main() -> None:
    from app.agents.pokedex_agent.rag.analyze_query import analyze_query

    analysis = analyze_query("피카츄 약점")
    print(hybrid_retrieve("피카츄 약점", analysis)["strategy"])


if __name__ == "__main__":
    main()
