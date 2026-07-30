# Run: python app/schemas/api.py
from pydantic import BaseModel, Field

from app.schemas.domain import ScanCandidate


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
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
    ocr_engine: str
    visual_engine: str = "unavailable"
    recognition_mode: str = "ocr"
    dataset_version: str
    latency_ms: float = Field(ge=0.0)
    scan_status: str = "matched"
    guidance: str = ""


class ScanTextRequest(BaseModel):
    ocr_text: str = Field(min_length=1, max_length=10000)
    filename: str = Field(default="ui-fixture.txt", min_length=1, max_length=255)


class EvolutionSummary(BaseModel):
    from_form_id: str
    to_form_id: str
    from_name: str
    to_name: str
    trigger_type: str
    trigger_value: str | None = None
    condition: dict[str, object] = Field(default_factory=dict)


class TypeMatchup(BaseModel):
    type: str
    multiplier: float


class PokedexDetailResponse(BaseModel):
    pokemon_id: int
    form_id: str
    name_ko: str
    name_en: str | None = None
    name_ja: str | None = None
    generation: int | None = None
    is_legendary: bool = False
    form_name: str = "base"
    types: list[str]
    height_m: float | None = None
    weight_kg: float | None = None
    canonical_key: str | None = None
    record_status: str = "canonical"
    localization_status: str = "complete"
    category_en: str | None = None
    ability_en: str | None = None
    stats: dict[str, int] = Field(default_factory=dict)
    evolutions: list[EvolutionSummary] = Field(default_factory=list)
    weaknesses: list[TypeMatchup] = Field(default_factory=list)
    resistances: list[TypeMatchup] = Field(default_factory=list)
    immunities: list[TypeMatchup] = Field(default_factory=list)
    source_meta: dict[str, str]


class PokedexSearchResponse(BaseModel):
    query: str
    matches: list[ScanCandidate]
    dataset_version: str


class VoiceStatusResponse(BaseModel):
    stage: str
    runtime: str
    original_ai_voice_allowed: bool
    official_audio_extraction_allowed: bool
    official_voice_mimicry_allowed: bool
    policy: list[str]


class NarrationRequest(BaseModel):
    form_id: str = Field(min_length=1, max_length=120)


class NarrationResponse(BaseModel):
    form_id: str
    pokemon_id: int
    name_ko: str
    narration_text: str
    grounded_fields: list[str]
    dataset_version: str


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
