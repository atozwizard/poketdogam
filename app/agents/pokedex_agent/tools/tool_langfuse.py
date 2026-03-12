# Run: python app/agents/pokedex_agent/tools/tool_langfuse.py
def record_trace(trace_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "trace_id": trace_id,
        "status": "recorded_stub",
        "keys": list(payload.keys()),
    }


def main() -> None:
    print(record_trace("trace-demo", {"message": "hello"}))


if __name__ == "__main__":
    main()
