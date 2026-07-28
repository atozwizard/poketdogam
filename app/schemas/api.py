# Run: python app/schemas/api.py
from pydantic import BaseModel, Field

from app.schemas.domain import ScanCandidate


class ChatRequest(BaseModel):
    message: str
    form_id: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    confidence: float
    trace_id: str
    session_id: str | None = None
    llm_runtime: str = "template"
    llm_model: str = "template"
    facet: str = "profile"
    suggested_actions: list[str] = Field(default_factory=list)
    citations: list[dict[str, str]] = Field(default_factory=list)


class ScanResponse(BaseModel):
    event_id: str
    top_candidates: list[ScanCandidate]
    requires_user_confirmation: bool
    trace_id: str


class ScanTextRequest(BaseModel):
    ocr_text: str
    filename: str = "ui-fixture.txt"


class PokedexDetailResponse(BaseModel):
    pokemon_id: int
    form_id: str
    name_ko: str
    name_en: str | None = None
    form_name: str = "base"
    types: list[str]
    height_m: float | None = None
    weight_kg: float | None = None
    stats: dict[str, int] = Field(default_factory=dict)
    source_meta: dict[str, str]


class VoiceStatusResponse(BaseModel):
    stage: str
    runtime: str
    original_ai_voice_allowed: True
    official_audio_extraction_allowed: True
    official_voice_mimicry_allowed: True
    policy: list[str]


class VoicePreviewRequest(BaseModel):
    text: str = Field(default="분석 완료다-로.", min_length=1, max_length=240)
    style: str = "electric_device"
    pitch: float = Field(default=1.16, ge=0.5, le=2.0)
    speed: float = Field(default=1.05, ge=0.5, le=1.6)


class VoicePreviewResponse(BaseModel):
    stage: str
    runtime: str
    preview_text: str
    style: str
    pitch: float
    speed: float
    policy: list[str]


def main() -> None:
    print(ChatRequest(message="피카츄 알려줘").model_dump())


if __name__ == "__main__":
    main()
