# Run: python app/agents/pokedex_agent/tools/tool_supabase.py
def fetch_pokedex_context(query: str) -> dict[str, object]:
    return {
        "query": query,
        "vector_hits": [],
        "source": "supabase",
    }


def main() -> None:
    print(fetch_pokedex_context("피카츄"))


if __name__ == "__main__":
    main()
