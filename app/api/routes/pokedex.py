# Run: python app/api/routes/pokedex.py
from fastapi import APIRouter

from app.schemas.api import PokedexDetailResponse

router = APIRouter(tags=["pokedex"])


@router.get("/pokedex/forms/{form_id}", response_model=PokedexDetailResponse)
def get_pokedex_form(form_id: str) -> PokedexDetailResponse:
    return PokedexDetailResponse(
        pokemon_id=25,
        form_id=form_id,
        name_ko="피카츄",
        types=["electric"],
        source_meta={"version": "scaffold", "updated_at": "2026-03-12T00:00:00+09:00"},
    )


def main() -> None:
    print(get_pokedex_form("base"))


if __name__ == "__main__":
    main()
