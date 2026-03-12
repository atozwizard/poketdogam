# Run: python app/agents/pokedex_agent/tools/tool_weather.py
def get_weather_snapshot() -> dict[str, object]:
    return {
        "condition": "unknown",
        "temp_c": None,
        "humidity": None,
    }


def main() -> None:
    print(get_weather_snapshot())


if __name__ == "__main__":
    main()
