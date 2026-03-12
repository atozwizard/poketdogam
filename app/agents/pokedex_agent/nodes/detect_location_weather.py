# Run: python app/agents/pokedex_agent/nodes/detect_location_weather.py
from app.agents.pokedex_agent.state import AgentState
from app.agents.pokedex_agent.tools.tool_weather import get_weather_snapshot


def run(state: AgentState) -> AgentState:
    state.weather = get_weather_snapshot()
    return state


def main() -> None:
    state = AgentState()
    print(run(state))


if __name__ == "__main__":
    main()
