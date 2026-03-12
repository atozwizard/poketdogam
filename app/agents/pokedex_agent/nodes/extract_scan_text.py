# Run: python app/agents/pokedex_agent/nodes/extract_scan_text.py
from app.agents.pokedex_agent.state import AgentState
from app.agents.pokedex_agent.tools.tool_upstage_document_ocr import extract_document_text


def run(state: AgentState, image_bytes: bytes, filename: str) -> AgentState:
    result = extract_document_text(image_bytes=image_bytes, filename=filename)
    state.scan_text = str(result.get("text", ""))
    return state


def main() -> None:
    state = AgentState()
    print(run(state, b"demo", "sample.png"))


if __name__ == "__main__":
    main()
