# Run: python app/api/routes/scan.py
from pathlib import Path
import sys
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, File, UploadFile

from app.agents.pokedex_agent.graph import PokedexAgentGraph
from app.schemas.domain import ScanCandidate
from app.schemas.api import ScanResponse, ScanTextRequest

router = APIRouter(tags=["scan"])
agent = PokedexAgentGraph()


@router.post("/scan", response_model=ScanResponse)
async def scan(image: UploadFile = File(...)) -> ScanResponse:
    image_bytes = await image.read()
    state, candidates = agent.run_scan(image_bytes=image_bytes, filename=image.filename or "upload.bin")
    return _scan_response(state.trace_id, candidates)


@router.post("/scan/text", response_model=ScanResponse)
def scan_text(request: ScanTextRequest) -> ScanResponse:
    state, candidates = agent.run_scan(
        image_bytes=request.ocr_text.encode("utf-8"),
        filename=request.filename,
    )
    return _scan_response(state.trace_id, candidates)


def _scan_response(trace_id: str, candidates: list[ScanCandidate]) -> ScanResponse:
    return ScanResponse(
        event_id=str(uuid4()),
        top_candidates=candidates,
        requires_user_confirmation=not candidates or candidates[0].confidence < 0.9,
        trace_id=trace_id,
    )


def main() -> None:
    print("UploadFile 기반 route module")


if __name__ == "__main__":
    main()
