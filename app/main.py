# Run: python app/main.py
from fastapi import FastAPI

from app.api.routes.chat import router as chat_router
from app.api.routes.pokedex import router as pokedex_router
from app.api.routes.scan import router as scan_router


def create_app() -> FastAPI:
    app = FastAPI(title="Poketdogam API", version="0.1.0")
    app.include_router(chat_router, prefix="/v1")
    app.include_router(scan_router, prefix="/v1")
    app.include_router(pokedex_router, prefix="/v1")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
