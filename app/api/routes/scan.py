# Run: python app/api/routes/scan.py
from uuid import uuid4

from fastapi import APIRouter, File, UploadFile

from app.agents.pokedex_agent.graph import PokedexAgentGraph
from app.schemas.api import ScanResponse

router = APIRouter(tags=["scan"])
agent = PokedexAgentGraph()


@router.post("/scan", response_model=ScanResponse)
async def scan(image: UploadFile = File(...)) -> ScanResponse:
    image_bytes = await image.read()
    state, candidates = agent.run_scan(image_bytes=image_bytes, filename=image.filename or "upload.bin")
    return ScanResponse(
        event_id=str(uuid4()),
        top_candidates=candidates,
        requires_user_confirmation=True,
        trace_id=state.trace_id,
    )


def main() -> None:
    print("UploadFile 기반 route module")


if __name__ == "__main__":
    main()
