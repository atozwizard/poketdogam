# Run: python app/agents/pokedex_agent/tools/tool_graphdb.py
def fetch_graph_context(query: str) -> dict[str, object]:
    return {
        "query": query,
        "graph_paths": [],
        "source": "graphdb",
    }


def main() -> None:
    print(fetch_graph_context("피카츄"))


if __name__ == "__main__":
    main()
