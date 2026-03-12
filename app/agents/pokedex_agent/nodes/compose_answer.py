# Run: python app/agents/pokedex_agent/nodes/compose_answer.py
from app.agents.pokedex_agent.state import AgentState
from app.config.settings import get_settings


def run(state: AgentState) -> AgentState:
    settings = get_settings()
    state.llm_provider_used = "litellm" if settings.use_litellm else "direct"
    state.llm_model_used = settings.llm_model
    subject = state.entities.get("name_ko") or state.input_text or "포켓몬"
    state.response_text = f"{subject}에 대한 응답 초안입니다."
    return state


def main() -> None:
    state = AgentState(input_text="피카츄 알려줘")
    print(run(state))


if __name__ == "__main__":
    main()
