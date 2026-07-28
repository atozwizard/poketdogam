# Run: python app/agents/pokedex_agent/nodes/retrieve_local_dex.py
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.state import AgentState
from app.agents.pokedex_agent.tools.tool_local_dex import get_local_dex


def run(state: AgentState, query: str) -> AgentState:
    store = get_local_dex()
    state.dataset_version = store.dataset_meta()["dataset_version"]

    form_id = state.entities.get("form_id") or ""
    detail = store.get_form(form_id) if form_id else None
    if detail is None:
        detail = store.search_first(query)

    if detail is None:
        if not store.is_available():
            state.error = {"code": "dex_missing", "message": f"Local dex not found: {store.db_path}"}
        else:
            state.error = {"code": "detail_not_found", "message": "No local dex detail matched query"}
        state.retrieval_context = {"source": "local_dex", "detail": None}
        return state

    state.entities.update(
        {
            "form_id": detail["form_id"],
            "pokemon_id": str(detail["pokemon_id"]),
            "name_ko": detail["name_ko"],
        }
    )
    state.retrieval_context = {"source": "local_dex", "detail": detail}
    return state


def main() -> None:
    state = AgentState(input_text="피카츄 알려줘")
    print(run(state, state.input_text))


if __name__ == "__main__":
    main()
