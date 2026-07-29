# Run: python app/api/routes/scan.py
from pathlib import Path
import sys
from time import perf_counter
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.agents.pokedex_agent.graph import PokedexAgentGraph
from app.agents.pokedex_agent.state import AgentState
from app.schemas.domain import ScanCandidate
from app.schemas.api import ScanResponse, ScanTextRequest

router = APIRouter(tags=["scan"])
agent = PokedexAgentGraph()
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
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
    state, candidates = agent.run_scan(
        image_bytes=image_bytes,
        filename=image.filename or _default_filename(content_type),
        content_type=content_type,
    )
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
        guidance = "카드 이름 영역이 선명하게 보이도록 다시 촬영하거나 이름으로 검색하세요."
    else:
        scan_status = "no_match"
        guidance = "읽힌 이름과 일치하는 후보가 없습니다. 이름을 직접 검색하세요."
    return ScanResponse(
        event_id=str(uuid4()),
        top_candidates=candidates,
        requires_user_confirmation=not candidates or candidates[0].confidence < 0.9,
        trace_id=state.trace_id,
        ocr_engine=state.ocr_engine or "unknown",
        dataset_version=state.dataset_version or "unknown",
        latency_ms=round((perf_counter() - started_at) * 1000, 2),
        scan_status=scan_status,
        guidance=guidance,
    )


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
