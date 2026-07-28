# Run: python app/api/routes/pokedex.py
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, HTTPException

from app.agents.pokedex_agent.tools.tool_local_dex import get_local_dex
from app.schemas.api import PokedexDetailResponse

router = APIRouter(tags=["pokedex"])


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
