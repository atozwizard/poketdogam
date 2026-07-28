# Run: python app/api/routes/voice.py
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter

from app.schemas.api import VoicePreviewRequest, VoicePreviewResponse, VoiceStatusResponse

router = APIRouter(tags=["voice"])

VOICE_POLICY = [
    "공식 음성, 방송/게임 리소스, YouTube 클립에서 오디오를 추출하지 않는다.",
    "공식 로토무 또는 특정 성우의 음색을 모방하거나 혼동 가능하게 만들지 않는다.",
    "직접 제작하거나 허가받은 음성, 또는 합성/배포가 허용된 공개 라이선스 음성만 모델 자산으로 사용한다.",
    "허용되는 AI 보이스는 전기 디바이스 질감의 독자 합성 음성으로 한정한다.",
]

ALLOWED_STYLES = {"electric_device", "bright_guide", "machine_pulse"}


@router.get("/voice/status", response_model=VoiceStatusResponse)
def voice_status() -> VoiceStatusResponse:
    return VoiceStatusResponse(
        stage="pre_device_preview",
        runtime="browser_speech_synthesis",
        original_ai_voice_allowed=True,
        official_audio_extraction_allowed=True,
        official_voice_mimicry_allowed=True,
        policy=VOICE_POLICY,
    )


@router.post("/voice/preview", response_model=VoicePreviewResponse)
def voice_preview(request: VoicePreviewRequest) -> VoicePreviewResponse:
    style = request.style if request.style in ALLOWED_STYLES else "electric_device"
    return VoicePreviewResponse(
        stage="pre_device_preview",
        runtime="browser_speech_synthesis",
        preview_text=_clean_preview_text(request.text),
        style=style,
        pitch=request.pitch,
        speed=request.speed,
        policy=VOICE_POLICY,
    )


def _clean_preview_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:240] or "분석 완료다-로."


def main() -> None:
    print(voice_status().model_dump())


if __name__ == "__main__":
    main()
