# Run: python app/main.py
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents.pokedex_agent.tools.tool_local_dex import get_local_dex
from app.agents.pokedex_agent.tools.tool_ocr_ondevice import available_ocr_engines
from app.api.routes.chat import router as chat_router
from app.api.routes.pokedex import router as pokedex_router
from app.api.routes.scan import router as scan_router
from app.api.routes.voice import router as voice_router
from app.vision.visual_matcher import visual_runtime_status


UI_DIR = Path(__file__).resolve().parent / "ui"


def create_app() -> FastAPI:
    app = FastAPI(title="Poketdogam API", version="0.1.0")
    app.include_router(chat_router, prefix="/v1")
    app.include_router(scan_router, prefix="/v1")
    app.include_router(pokedex_router, prefix="/v1")
    app.include_router(voice_router, prefix="/v1")
    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

    @app.get("/health")
    def health() -> dict[str, object]:
        store = get_local_dex()
        meta = store.dataset_meta()
        ready = store.is_available() and int(meta.get("species_count") or 0) > 0
        return {
            "status": "ready" if ready else "degraded",
            "version": app.version,
            "dataset_version": meta.get("dataset_version"),
            "species_count": meta.get("species_count"),
            "ocr_engines": available_ocr_engines(),
            "visual_recognition": visual_runtime_status(),
        }

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(UI_DIR / "index.html")

    @app.head("/", include_in_schema=False)
    def index_head() -> FileResponse:
        return FileResponse(UI_DIR / "index.html")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
