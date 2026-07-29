# Run: python app/agents/pokedex_agent/nodes/extract_scan_text.py
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.pokedex_agent.state import AgentState
from app.agents.pokedex_agent.tools.tool_ocr_ondevice import extract_ondevice_text


def run(
    state: AgentState,
    image_bytes: bytes,
    filename: str,
    content_type: str | None = None,
) -> AgentState:
    result = extract_ondevice_text(
        image_bytes=image_bytes,
        filename=filename,
        content_type=content_type,
    )
    state.input_image_ref = filename
    state.scan_text = str(result.get("text", ""))
    state.ocr_engine = str(result.get("engine", "os_ocr_adapter"))
    return state


def main() -> None:
    state = AgentState()
    print(run(state, b"demo", "sample.png"))


if __name__ == "__main__":
    main()
