# Run: python app/agents/pokedex_agent/tools/tool_langfuse.py
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import json
import sqlite3
import time


PROJECT_ROOT = Path(__file__).resolve().parents[4]
TRACE_DB = PROJECT_ROOT / "data" / "observability.sqlite"
TRACE_RETENTION_SECONDS = 7 * 24 * 60 * 60
ALLOWED_TRACE_KEYS = {
    "intent",
    "model",
    "ocr_engine",
    "match_score",
    "dataset_version",
    "facet",
    "strategy",
    "error_code",
}


def record_trace(trace_id: str, payload: dict[str, object]) -> dict[str, object]:
    sanitized = {key: payload.get(key) for key in ALLOWED_TRACE_KEYS if key in payload}
    TRACE_DB.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    try:
        with closing(sqlite3.connect(TRACE_DB)) as conn:
            conn.execute(
                """
                create table if not exists traces (
                    trace_id text primary key,
                    payload_json text not null,
                    created_at real not null
                )
                """
            )
            conn.execute("delete from traces where created_at < ?", (now - TRACE_RETENTION_SECONDS,))
            conn.execute(
                """
                insert into traces(trace_id, payload_json, created_at)
                values (?, ?, ?)
                on conflict(trace_id) do update
                set payload_json = excluded.payload_json, created_at = excluded.created_at
                """,
                (trace_id, json.dumps(sanitized, ensure_ascii=False), now),
            )
            conn.commit()
    except sqlite3.Error as exc:
        return {"trace_id": trace_id, "status": "local_error", "error": type(exc).__name__}
    return {"trace_id": trace_id, "status": "recorded_local", "keys": sorted(sanitized)}


def main() -> None:
    print(record_trace("trace-demo", {"message": "hello"}))


if __name__ == "__main__":
    main()
