# Run: python app/api/routes/scan.py
from pathlib import Path
from io import BytesIO
import asyncio
from threading import BoundedSemaphore
import sys
from time import perf_counter
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.agents.pokedex_agent.graph import PokedexAgentGraph
from app.agents.pokedex_agent.state import AgentState
from app.config.settings import get_settings
from app.schemas.domain import ScanCandidate
from app.schemas.api import ScanResponse, ScanTextRequest

router = APIRouter(tags=["scan"])
agent = PokedexAgentGraph()
scan_capacity = BoundedSemaphore(value=1)
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "image/heif",
    "image/tiff",
}


@router.post("/scan", response_model=ScanResponse)
async def scan(image: UploadFile = File(...)) -> ScanResponse:
    started_at = perf_counter()
    content_type = (image.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="PNG, JPEG, WebP, HEIC 또는 TIFF 이미지만 업로드할 수 있습니다.",
        )
    image_bytes = await image.read(MAX_UPLOAD_BYTES + 1)
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="이미지 크기는 8MB 이하여야 합니다.")
    if not _matches_image_signature(image_bytes, content_type):
        raise HTTPException(status_code=415, detail="파일 내용이 유효한 이미지 형식이 아닙니다.")
    _validate_image_dimensions(image_bytes, content_type)
    settings = get_settings()
    try:
        state, candidates = await asyncio.wait_for(
            run_in_threadpool(
                _run_scan_with_capacity,
                image_bytes,
                image.filename or _default_filename(content_type),
                content_type,
            ),
            timeout=settings.scan_timeout_seconds,
        )
    except ScanCapacityError as exc:
        raise HTTPException(
            status_code=429,
            detail="이미지 분석이 진행 중입니다. 잠시 후 다시 시도하세요.",
            headers={"Retry-After": "1"},
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="이미지 분석 시간이 초과되었습니다. 더 작은 이미지로 다시 시도하세요.",
        ) from exc
    return _scan_response(state, candidates, started_at)


@router.post("/scan/text", response_model=ScanResponse)
def scan_text(request: ScanTextRequest) -> ScanResponse:
    started_at = perf_counter()
    state, candidates = agent.run_scan(
        image_bytes=request.ocr_text.encode("utf-8"),
        filename=request.filename,
    )
    return _scan_response(state, candidates, started_at)


def _scan_response(state: AgentState, candidates: list[ScanCandidate], started_at: float) -> ScanResponse:
    if candidates:
        scan_status = "matched"
        guidance = "후보가 맞는지 확인한 뒤 컬렉션에 저장하세요."
    elif not state.scan_text:
        scan_status = "no_text"
        guidance = (
            "조명을 밝게 하고 대상을 70% 이상 채운 뒤 다시 촬영하세요. "
            "카드는 이름을 위쪽 카드명 영역에 맞추고, 인형·굿즈는 배경을 "
            "단순하게 만드세요. 계속 실패하면 이름으로 검색하세요."
        )
    else:
        scan_status = "no_match"
        guidance = (
            "읽힌 이름과 일치하는 후보가 없습니다. 카드명 영역과 초점을 "
            "확인해 다시 찍거나 이름을 직접 검색하세요."
        )
    return ScanResponse(
        event_id=str(uuid4()),
        top_candidates=candidates,
        requires_user_confirmation=True,
        trace_id=state.trace_id,
        ocr_engine=state.ocr_engine or "unknown",
        visual_engine=state.visual_engine or "unavailable",
        recognition_mode=_recognition_mode(candidates),
        dataset_version=state.dataset_version or "unknown",
        latency_ms=round((perf_counter() - started_at) * 1000, 2),
        scan_status=scan_status,
        guidance=guidance,
    )


def _recognition_mode(candidates: list[ScanCandidate]) -> str:
    sources = {source for item in candidates for source in item.evidence_sources}
    if {"ocr", "visual_embedding"}.issubset(sources):
        return "ocr+visual_embedding"
    if "visual_embedding" in sources:
        return "visual_embedding"
    return "ocr"


class ScanCapacityError(RuntimeError):
    pass


def _run_scan_with_capacity(
    image_bytes: bytes,
    filename: str,
    content_type: str,
) -> tuple[AgentState, list[ScanCandidate]]:
    if not scan_capacity.acquire(timeout=1.0):
        raise ScanCapacityError
    try:
        return agent.run_scan(image_bytes, filename, content_type)
    finally:
        scan_capacity.release()


def _matches_image_signature(image_bytes: bytes, content_type: str) -> bool:
    if not image_bytes:
        return False
    if content_type == "image/png":
        return image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return image_bytes.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP"
    if content_type in {"image/heic", "image/heif"}:
        return len(image_bytes) >= 12 and image_bytes[4:8] == b"ftyp"
    if content_type == "image/tiff":
        return image_bytes.startswith((b"II*\x00", b"MM\x00*"))
    return False


def _validate_image_dimensions(image_bytes: bytes, content_type: str) -> None:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="이미지 검증 모듈을 사용할 수 없습니다.") from exc

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=415, detail="이미지 구조를 확인할 수 없습니다.") from exc

    if width < 32 or height < 32:
        raise HTTPException(status_code=422, detail="이미지는 가로·세로 각각 32px 이상이어야 합니다.")
    if width * height > MAX_IMAGE_PIXELS:
        raise HTTPException(
            status_code=413,
            detail="디코딩된 이미지 해상도는 4천만 픽셀 이하여야 합니다.",
        )


def _default_filename(content_type: str) -> str:
    suffix = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/heic": "heic",
        "image/heif": "heif",
        "image/tiff": "tiff",
    }.get(content_type, "bin")
    return f"upload.{suffix}"


def main() -> None:
    print("UploadFile 기반 route module")


if __name__ == "__main__":
    main()
