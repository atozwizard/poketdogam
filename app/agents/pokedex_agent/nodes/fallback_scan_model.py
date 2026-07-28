# Run: python app/agents/pokedex_agent/nodes/fallback_scan_model.py
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.state import AgentState
from app.config.settings import get_settings


def run(state: AgentState) -> AgentState:
    settings = get_settings()
    state.fallback_used = True
    state.llm_provider_used = "local"
    state.llm_model_used = settings.scan_fallback_model
    state.error = {"code": "manual_search_required", "message": "Local matcher confidence was below threshold"}
    return state


def main() -> None:
    state = AgentState()
    print(run(state))


if __name__ == "__main__":
    main()
