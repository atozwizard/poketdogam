# Run: python -m unittest tests/test_rag_session.py
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import tempfile
import unittest

from app.agents.pokedex_agent.rag.analyze_query import analyze_query
from app.agents.pokedex_agent.rag.embeddings import decode_embedding, encode_embedding, hash_embed
from app.agents.pokedex_agent.rag.hybrid_retrieve import hybrid_retrieve
from app.agents.pokedex_agent.rag.expand_hops import expand_hops
from app.agents.pokedex_agent.session.carryover import apply_carryover
from app.agents.pokedex_agent.session.store import FlowState, SessionStore
from scripts.build_local_dex.build import build_local_dex


class RagSessionTest(unittest.TestCase):
    def test_binary_hash_embedding_round_trip(self) -> None:
        original = hash_embed("피카츄 전기 타입")
        restored = decode_embedding(encode_embedding(original))

        self.assertEqual(len(restored), 256)
        self.assertAlmostEqual(sum(value * value for value in restored), 1.0, places=5)
        self.assertEqual(decode_embedding("0.5,-0.5"), [0.5, -0.5])

    def test_carryover_rewrites_followup(self) -> None:
        state = FlowState(active_form_id="x", active_name_ko="피카츄", last_facet="weakness")
        rewritten, analysis = apply_carryover("그럼?", state)
        self.assertIn("피카츄", rewritten)
        self.assertEqual(analysis.facet, "weakness")

    def test_hybrid_retrieve_on_seed_dex(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            db_path = temp / "dex.sqlite"
            meta_path = temp / "dex.meta.json"
            build_local_dex(db_path, meta_path, source="seed", dataset_version="rag-test")
            analysis = analyze_query("피카츄 약점")
            result = hybrid_retrieve("피카츄 약점", analysis, db_path=db_path)
            self.assertEqual(result["strategy"], "hybrid_rrf+hash+graph_hops")
            self.assertIsNotNone(result["detail"])
            self.assertGreaterEqual(len(result["passages"]), 1)
            self.assertTrue(result["hops"].get("type_relations") or result["hops"].get("trace"))

    def test_session_store_persists_flow_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(Path(temp_dir) / "sessions.sqlite")
            session = store.ensure()
            state = FlowState(active_form_id="f1", active_name_ko="피카츄", last_facet="evolution")
            store.append_turn(session.session_id, role="user", content="피카츄", flow_state=None)
            store.append_turn(session.session_id, role="assistant", content="답", flow_state=state)
            again = store.ensure(session.session_id)
            self.assertEqual(again.flow_state.active_name_ko, "피카츄")
            self.assertEqual(again.flow_state.last_facet, "evolution")

    def test_dual_type_matchups_multiply_all_defense_types(self) -> None:
        from app.agents.pokedex_agent.tools.tool_local_dex import LocalDexStore

        store = LocalDexStore()
        detail = store.search_first("리자몽")
        self.assertIsNotNone(detail)
        hops = expand_hops(store.db_path, form_id=detail["form_id"], facet="weakness")
        matchups = {item["attack_type"]: item["multiplier"] for item in hops["type_relations"]}
        self.assertEqual(matchups["rock"], 4.0)
        self.assertNotIn("ground", matchups)

    def test_expired_session_deletes_plaintext_turns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(Path(temp_dir) / "sessions.sqlite")
            session = store.ensure()
            store.append_turn(session.session_id, role="user", content="민감한 대화", flow_state=None)
            with closing(store._connect()) as conn:
                conn.execute(
                    "update sessions set last_active_at = ? where session_id = ?",
                    (0, session.session_id),
                )
                conn.commit()

            store.ensure(session.session_id)
            self.assertEqual(store.recent_turns(session.session_id), [])

    def test_concurrent_first_requests_create_one_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(Path(temp_dir) / "sessions.sqlite")
            session_id = "shared-session"
            with ThreadPoolExecutor(max_workers=8) as executor:
                records = list(executor.map(lambda _: store.ensure(session_id), range(16)))

            self.assertEqual({record.session_id for record in records}, {session_id})
            with closing(store._connect()) as conn:
                count = conn.execute(
                    "select count(*) from sessions where session_id = ?", (session_id,)
                ).fetchone()[0]
            self.assertEqual(count, 1)

    def test_stale_exchange_cannot_overwrite_newer_flow_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(Path(temp_dir) / "sessions.sqlite")
            first = store.ensure("shared-session")
            stale = store.ensure("shared-session")
            first_state = FlowState(active_form_id="f1", active_name_ko="피카츄")
            stale_state = FlowState(active_form_id="f2", active_name_ko="이브이")

            self.assertTrue(
                store.append_exchange(
                    first.session_id,
                    user_content="첫 요청",
                    assistant_content="첫 답변",
                    flow_state=first_state,
                    expected_turn_count=first.turn_count,
                )
            )
            self.assertFalse(
                store.append_exchange(
                    stale.session_id,
                    user_content="경합 요청",
                    assistant_content="늦은 답변",
                    flow_state=stale_state,
                    expected_turn_count=stale.turn_count,
                )
            )
            current = store.ensure(first.session_id)
            self.assertEqual(current.flow_state.active_name_ko, "피카츄")
            history = store.recent_turns(first.session_id, limit=10)
            self.assertEqual(len(history), 4)
            self.assertEqual({turn["content"] for turn in history}, {"첫 요청", "첫 답변", "경합 요청", "늦은 답변"})

    def test_session_deletion_wins_over_late_stream_persist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(Path(temp_dir) / "sessions.sqlite")
            session = store.ensure("delete-race")
            self.assertTrue(store.delete(session.session_id))

            persisted = store.append_exchange(
                session.session_id,
                user_content="삭제 직전 요청",
                assistant_content="늦은 답변",
                flow_state=FlowState(active_name_ko="피카츄"),
                expected_turn_count=session.turn_count,
            )

            self.assertFalse(persisted)
            self.assertEqual(store.recent_turns(session.session_id), [])


if __name__ == "__main__":
    unittest.main()
