# Run: python app/schemas/domain.py
from pydantic import BaseModel, Field


class ScanCandidate(BaseModel):
    form_id: str
    pokemon_id: int | None = None
    name_ko: str
    name_en: str | None = None
    form_name: str = "base"
    types: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    matched_alias: str | None = None
    match_reason: str | None = None


class WeatherInfo(BaseModel):
    condition: str = "unknown"
    temp_c: float | None = None
    humidity: int | None = None


def main() -> None:
    print(ScanCandidate(form_id="demo", pokemon_id=25, name_ko="피카츄", confidence=0.91).model_dump())


if __name__ == "__main__":
    main()
