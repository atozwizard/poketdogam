# Run: python app/agents/pokedex_agent/session/store.py
"""ThinkFlow-style session + flow_state carryover (local SQLite)."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import json
import sqlite3
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_DB = PROJECT_ROOT / "data" / "sessions.sqlite"
TTL_SECONDS = 1800
MAX_TURNS = 24


@dataclass(slots=True)
class FlowState:
    active_form_id: str = ""
    active_name_ko: str = ""
    last_facet: str = "profile"
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "active_form_id": self.active_form_id,
            "active_name_ko": self.active_name_ko,
            "last_facet": self.last_facet,
            "evidence_ids": self.evidence_ids,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> "FlowState":
        payload = payload or {}
        evidence = payload.get("evidence_ids")
        return cls(
            active_form_id=str(payload.get("active_form_id") or ""),
            active_name_ko=str(payload.get("active_name_ko") or ""),
            last_facet=str(payload.get("last_facet") or "profile"),
            evidence_ids=[str(item) for item in evidence] if isinstance(evidence, list) else [],
        )


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    flow_state: FlowState
    turn_count: int = 0
    last_active_at: float = 0.0


class SessionStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def ensure(self, session_id: str | None = None) -> SessionRecord:
        sid = session_id or str(uuid4())
        now = time.time()
        with closing(self._connect()) as conn:
            self._delete_expired(conn, now=now, exclude_session_id=sid)
            row = conn.execute(
                "select session_id, flow_state_json, turn_count, last_active_at from sessions where session_id = ?",
                (sid,),
            ).fetchone()
            if row is None:
                state = FlowState()
                conn.execute(
                    """
                    insert into sessions(session_id, flow_state_json, turn_count, created_at, last_active_at)
                    values (?, ?, 0, ?, ?)
                    """,
                    (sid, json.dumps(state.to_dict(), ensure_ascii=False), now, now),
                )
                conn.commit()
                return SessionRecord(session_id=sid, flow_state=state, turn_count=0, last_active_at=now)

            if now - float(row["last_active_at"]) > TTL_SECONDS:
                state = FlowState()
                conn.execute("delete from turns where session_id = ?", (sid,))
                conn.execute(
                    "update sessions set flow_state_json = ?, turn_count = 0, last_active_at = ? where session_id = ?",
                    (json.dumps(state.to_dict(), ensure_ascii=False), now, sid),
                )
                conn.commit()
                return SessionRecord(session_id=sid, flow_state=state, turn_count=0, last_active_at=now)

            return SessionRecord(
                session_id=sid,
                flow_state=FlowState.from_dict(json.loads(row["flow_state_json"] or "{}")),
                turn_count=int(row["turn_count"]),
                last_active_at=float(row["last_active_at"]),
            )

    def append_turn(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        metadata: dict[str, object] | None = None,
        flow_state: FlowState | None = None,
    ) -> None:
        now = time.time()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                insert into turns(turn_id, session_id, role, content, metadata_json, created_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    session_id,
                    role,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                ),
            )
            if flow_state is not None:
                conn.execute(
                    """
                    update sessions
                    set flow_state_json = ?, turn_count = turn_count + 1, last_active_at = ?
                    where session_id = ?
                    """,
                    (json.dumps(flow_state.to_dict(), ensure_ascii=False), now, session_id),
                )
            else:
                conn.execute(
                    "update sessions set turn_count = turn_count + 1, last_active_at = ? where session_id = ?",
                    (now, session_id),
                )
            # Cap history
            ids = [
                row["turn_id"]
                for row in conn.execute(
                    "select turn_id from turns where session_id = ? order by created_at desc",
                    (session_id,),
                ).fetchall()
            ]
            for stale in ids[MAX_TURNS:]:
                conn.execute("delete from turns where turn_id = ?", (stale,))
            conn.commit()

    def append_exchange(
        self,
        session_id: str,
        *,
        user_content: str,
        assistant_content: str,
        assistant_metadata: dict[str, object] | None = None,
        flow_state: FlowState,
    ) -> None:
        now = time.time()
        with closing(self._connect()) as conn:
            try:
                conn.execute("begin immediate")
                for role, content, metadata in (
                    ("user", user_content, {}),
                    ("assistant", assistant_content, assistant_metadata or {}),
                ):
                    conn.execute(
                        """
                        insert into turns(turn_id, session_id, role, content, metadata_json, created_at)
                        values (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid4()),
                            session_id,
                            role,
                            content,
                            json.dumps(metadata, ensure_ascii=False),
                            now,
                        ),
                    )
                conn.execute(
                    """
                    update sessions
                    set flow_state_json = ?, turn_count = turn_count + 2, last_active_at = ?
                    where session_id = ?
                    """,
                    (json.dumps(flow_state.to_dict(), ensure_ascii=False), now, session_id),
                )
                ids = [
                    row["turn_id"]
                    for row in conn.execute(
                        "select turn_id from turns where session_id = ? order by created_at desc, rowid desc",
                        (session_id,),
                    ).fetchall()
                ]
                for stale in ids[MAX_TURNS:]:
                    conn.execute("delete from turns where turn_id = ?", (stale,))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def recent_turns(self, session_id: str, limit: int = 6) -> list[dict[str, object]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                select role, content, metadata_json, created_at
                from turns
                where session_id = ?
                order by created_at desc
                limit ?
                """,
                (session_id, limit),
            ).fetchall()
        result = []
        for row in reversed(rows):
            result.append(
                {
                    "role": row["role"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata_json"] or "{}"),
                    "created_at": row["created_at"],
                }
            )
        return result

    def delete(self, session_id: str) -> bool:
        with closing(self._connect()) as conn:
            conn.execute("delete from turns where session_id = ?", (session_id,))
            deleted = conn.execute("delete from sessions where session_id = ?", (session_id,)).rowcount
            conn.commit()
        return bool(deleted)

    def cleanup_expired(self, now: float | None = None) -> int:
        with closing(self._connect()) as conn:
            deleted = self._delete_expired(conn, now=now or time.time())
            conn.commit()
        return deleted

    def _delete_expired(
        self,
        conn: sqlite3.Connection,
        *,
        now: float,
        exclude_session_id: str | None = None,
    ) -> int:
        cutoff = now - TTL_SECONDS
        sql = "select session_id from sessions where last_active_at < ?"
        params: list[object] = [cutoff]
        if exclude_session_id:
            sql += " and session_id != ?"
            params.append(exclude_session_id)
        expired = [str(row["session_id"]) for row in conn.execute(sql, params).fetchall()]
        for session_id in expired:
            conn.execute("delete from turns where session_id = ?", (session_id,))
            conn.execute("delete from sessions where session_id = ?", (session_id,))
        return len(expired)

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                create table if not exists sessions (
                    session_id text primary key,
                    flow_state_json text not null,
                    turn_count integer not null default 0,
                    created_at real not null,
                    last_active_at real not null
                );
                create table if not exists turns (
                    turn_id text primary key,
                    session_id text not null references sessions(session_id),
                    role text not null,
                    content text not null,
                    metadata_json text not null,
                    created_at real not null
                );
                create index if not exists idx_turns_session on turns(session_id, created_at);
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("pragma foreign_keys = on")
        conn.row_factory = sqlite3.Row
        return conn


def main() -> None:
    store = SessionStore(PROJECT_ROOT / "data" / "sessions_demo.sqlite")
    session = store.ensure()
    store.append_turn(session.session_id, role="user", content="피카츄 알려줘", flow_state=session.flow_state)
    print({"session_id": session.session_id, "iso": datetime.now(timezone.utc).isoformat()})


if __name__ == "__main__":
    main()
