# Run: python app/agents/pokedex_agent/nodes/fallback_scan_model.py
from app.agents.pokedex_agent.state import AgentState
from app.config.settings import get_settings


def run(state: AgentState) -> AgentState:
    settings = get_settings()
    state.fallback_used = True
    state.llm_provider_used = "litellm" if settings.use_litellm else "direct"
    state.llm_model_used = settings.scan_fallback_model
    return state


def main() -> None:
    state = AgentState()
    print(run(state))


if __name__ == "__main__":
    main()
