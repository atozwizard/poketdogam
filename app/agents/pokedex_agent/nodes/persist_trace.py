# Run: python app/agents/pokedex_agent/nodes/persist_trace.py
from app.agents.pokedex_agent.state import AgentState
from app.agents.pokedex_agent.tools.tool_langfuse import record_trace


def run(state: AgentState) -> AgentState:
    record_trace(state.trace_id, {"intent": state.intent, "model": state.llm_model_used})
    return state


def main() -> None:
    state = AgentState()
    print(run(state))


if __name__ == "__main__":
    main()
