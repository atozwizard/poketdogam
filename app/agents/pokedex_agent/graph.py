# Run: python app/agents/pokedex_agent/graph.py
from uuid import uuid4

from app.agents.pokedex_agent.nodes.compose_answer import run as compose_answer
from app.agents.pokedex_agent.nodes.detect_location_weather import run as detect_location_weather
from app.agents.pokedex_agent.nodes.extract_scan_text import run as extract_scan_text
from app.agents.pokedex_agent.nodes.ingest_input import run as ingest_input
from app.agents.pokedex_agent.nodes.persist_trace import run as persist_trace
from app.agents.pokedex_agent.nodes.retrieve_hybrid_graphrag import run as retrieve_context
from app.agents.pokedex_agent.state import AgentState
from app.schemas.domain import ScanCandidate


class PokedexAgentGraph:
    def run_chat(self, message: str, form_id: str | None = None) -> AgentState:
        state = AgentState()
        state.entities = {"form_id": form_id or ""}
        ingest_input(state, message)
        detect_location_weather(state)
        retrieve_context(state, form_id or message)
        compose_answer(state)
        persist_trace(state)
        return state

    def run_scan(self, image_bytes: bytes, filename: str) -> tuple[AgentState, list[ScanCandidate]]:
        state = AgentState()
        state.intent = "scan"
        extract_scan_text(state, image_bytes, filename)
        state.llm_provider_used = "litellm"
        state.llm_model_used = "gemini"
        persist_trace(state)
        candidates = [
            ScanCandidate(
                form_id=f"stub-{uuid4()}",
                pokemon_id=25,
                name_ko="피카츄",
                confidence=0.52,
            ),
            ScanCandidate(
                form_id=f"stub-{uuid4()}",
                pokemon_id=172,
                name_ko="피츄",
                confidence=0.31,
            ),
        ]
        return state, candidates


def main() -> None:
    agent = PokedexAgentGraph()
    print(agent.run_chat("피카츄 알려줘"))


if __name__ == "__main__":
    main()
