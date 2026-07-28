# Run: python -m unittest tests/test_rag_session.py
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.agents.pokedex_agent.rag.analyze_query import analyze_query
from app.agents.pokedex_agent.rag.hybrid_retrieve import hybrid_retrieve
from app.agents.pokedex_agent.session.carryover import apply_carryover
from app.agents.pokedex_agent.session.store import FlowState, SessionStore
from scripts.build_local_dex.build import build_local_dex


class RagSessionTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
