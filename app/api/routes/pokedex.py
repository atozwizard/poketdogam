# Run: python app/api/routes/pokedex.py
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, HTTPException, Query

from app.agents.pokedex_agent.tools.tool_local_dex import get_local_dex
from app.schemas.api import PokedexDetailResponse, PokedexSearchResponse

router = APIRouter(tags=["pokedex"])


@router.get("/pokedex/search", response_model=PokedexSearchResponse)
def search_pokedex(
    query: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=20),
) -> PokedexSearchResponse:
    store = get_local_dex()
    return PokedexSearchResponse(
        query=query,
        matches=store.search(query, limit=limit),
        dataset_version=str(store.dataset_meta()["dataset_version"]),
    )


@router.get("/pokedex/forms/{form_id}", response_model=PokedexDetailResponse)
def get_pokedex_form(form_id: str) -> PokedexDetailResponse:
    detail = get_local_dex().get_form(form_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Local dex form not found")
    return PokedexDetailResponse(**detail)


def main() -> None:
    print(get_pokedex_form("base"))


if __name__ == "__main__":
    main()
