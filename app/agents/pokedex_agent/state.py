# Run: python app/agents/pokedex_agent/state.py
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(slots=True)
class AgentState:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str | None = None
    input_text: str = ""
    input_image_ref: str = ""
    location: dict[str, str | float] = field(default_factory=dict)
    weather: dict[str, str | float | int | None] = field(default_factory=dict)
    intent: str = "unknown"
    ocr_engine: str = ""
    visual_engine: str = ""
    scan_text: str = ""
    match_candidates: list[dict[str, object]] = field(default_factory=list)
    entities: dict[str, str] = field(default_factory=dict)
    retrieval_context: dict[str, object] = field(default_factory=dict)
    llm_runtime: str = "template"
    llm_provider_used: str = ""
    llm_model_used: str = ""
    fallback_used: bool = False
    response_text: str = ""
    dataset_version: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    error: dict[str, str] = field(default_factory=dict)


def main() -> None:
    print(AgentState())


if __name__ == "__main__":
    main()
