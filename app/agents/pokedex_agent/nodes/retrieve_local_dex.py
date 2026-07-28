# Run: python app/agents/pokedex_agent/nodes/retrieve_local_dex.py
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.rag.analyze_query import analyze_query
from app.agents.pokedex_agent.rag.hybrid_retrieve import hybrid_retrieve
from app.agents.pokedex_agent.state import AgentState


def run(state: AgentState, query: str) -> AgentState:
    analysis = analyze_query(query)
    form_id = state.entities.get("form_id") or None
    result = hybrid_retrieve(query, analysis, form_id=form_id)
    state.retrieval_context = result
    detail = result.get("detail")
    if isinstance(detail, dict):
        state.entities["form_id"] = str(detail.get("form_id") or "")
        state.entities["name_ko"] = str(detail.get("name_ko") or "")
        state.dataset_version = str(detail.get("source_meta", {}).get("dataset_version") or state.dataset_version)
    return state


def main() -> None:
    state = AgentState(input_text="피카츄 약점")
    print(run(state, state.input_text).retrieval_context.get("strategy"))


if __name__ == "__main__":
    main()
