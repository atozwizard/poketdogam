# Run: python app/agents/pokedex_agent/graph.py
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.nodes.compose_answer import run as compose_answer
from app.agents.pokedex_agent.nodes.extract_scan_text import run as extract_scan_text
from app.agents.pokedex_agent.nodes.ingest_input import run as ingest_input
from app.agents.pokedex_agent.nodes.match_local_dex import run as match_local_dex
from app.agents.pokedex_agent.nodes.persist_trace import run as persist_trace
from app.agents.pokedex_agent.nodes.retrieve_local_dex import run as retrieve_context
from app.agents.pokedex_agent.state import AgentState
from app.schemas.domain import ScanCandidate
from app.vision.fusion import fuse_candidates
from app.vision.visual_matcher import MODEL_ID, get_visual_matcher


class PokedexAgentGraph:
    def run_chat(self, message: str, form_id: str | None = None) -> AgentState:
        state = AgentState(input_text=message)
        state.entities = {"form_id": form_id or ""}
        ingest_input(state, message)
        retrieve_context(state, message)
        compose_answer(state)
        persist_trace(state)
        return state

    def run_scan(
        self,
        image_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> tuple[AgentState, list[ScanCandidate]]:
        state = AgentState()
        state.intent = "scan"
        extract_scan_text(state, image_bytes, filename, content_type)
        match_local_dex(state)
        ocr_candidates = [ScanCandidate(**candidate) for candidate in state.match_candidates]
        visual_candidates: list[ScanCandidate] = []
        if content_type and content_type.startswith("image/"):
            visual_candidates = get_visual_matcher().match(image_bytes, top_k=5)
            state.visual_engine = MODEL_ID if visual_candidates else "unavailable"
        candidates = fuse_candidates(ocr_candidates, visual_candidates, top_k=3)
        state.match_candidates = [candidate.model_dump() for candidate in candidates]
        persist_trace(state)
        return state, candidates


def main() -> None:
    agent = PokedexAgentGraph()
    print(agent.run_chat("피카츄 알려줘"))


if __name__ == "__main__":
    main()
