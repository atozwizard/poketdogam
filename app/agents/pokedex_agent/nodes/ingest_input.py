# Run: python app/agents/pokedex_agent/nodes/ingest_input.py
from app.agents.pokedex_agent.state import AgentState


def run(state: AgentState, input_text: str) -> AgentState:
    state.input_text = input_text.strip()
    state.intent = "scan" if "scan" in input_text.lower() else "chat"
    return state


def main() -> None:
    state = AgentState()
    print(run(state, "피카츄 알려줘"))


if __name__ == "__main__":
    main()
