# Run: python app/agents/pokedex_agent/nodes/retrieve_hybrid_graphrag.py
from app.agents.pokedex_agent.state import AgentState
from app.agents.pokedex_agent.tools.tool_graphdb import fetch_graph_context
from app.agents.pokedex_agent.tools.tool_supabase import fetch_pokedex_context


def run(state: AgentState, query: str) -> AgentState:
    state.retrieval_context = {
        "vector": fetch_pokedex_context(query),
        "graph": fetch_graph_context(query),
    }
    return state


def main() -> None:
    state = AgentState()
    print(run(state, "피카츄"))


if __name__ == "__main__":
    main()
