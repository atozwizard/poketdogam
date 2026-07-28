# Run: python app/agents/pokedex_agent/nodes/match_local_dex.py
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.state import AgentState
from app.agents.pokedex_agent.tools.tool_local_dex import get_local_dex


def run(state: AgentState, raw_text: str | None = None) -> AgentState:
    query = raw_text if raw_text is not None else state.scan_text or state.input_text
    store = get_local_dex()
    state.dataset_version = store.dataset_meta()["dataset_version"]
    candidates = store.match_name(query)
    state.match_candidates = [candidate.model_dump() for candidate in candidates]
    if candidates:
        top = candidates[0]
        state.entities.update(
            {
                "form_id": top.form_id,
                "pokemon_id": str(top.pokemon_id or ""),
                "name_ko": top.name_ko,
            }
        )
    elif not store.is_available():
        state.error = {"code": "dex_missing", "message": f"Local dex not found: {store.db_path}"}
    else:
        state.error = {"code": "match_not_found", "message": "No local dex candidate matched input"}
    return state


def main() -> None:
    state = AgentState(scan_text="피카추 HP 60")
    print(run(state))


if __name__ == "__main__":
    main()
