# Run: python app/schemas/api.py
from pydantic import BaseModel

from app.schemas.domain import ScanCandidate


class ChatRequest(BaseModel):
    message: str
    form_id: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    confidence: float
    trace_id: str
    citations: list[dict[str, str]] = []


class ScanResponse(BaseModel):
    event_id: str
    top_candidates: list[ScanCandidate]
    requires_user_confirmation: bool
    trace_id: str


class PokedexDetailResponse(BaseModel):
    pokemon_id: int
    form_id: str
    name_ko: str
    types: list[str]
    source_meta: dict[str, str]


def main() -> None:
    print(ChatRequest(message="피카츄 알려줘").model_dump())


if __name__ == "__main__":
    main()
