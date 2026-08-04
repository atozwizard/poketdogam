# Run: python app/main.py
from pathlib import Path
import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager, suppress
from threading import Lock
from time import perf_counter

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents.pokedex_agent.tools.tool_local_dex import get_local_dex
from app.agents.pokedex_agent.tools.tool_ocr_ondevice import available_ocr_engines
from app.api.routes.chat import router as chat_router, sessions as chat_sessions
from app.api.routes.pokedex import router as pokedex_router
from app.api.routes.scan import router as scan_router
from app.api.routes.voice import router as voice_router
from app.vision.visual_matcher import visual_runtime_status
from app.config.settings import get_settings


UI_DIR = Path(__file__).resolve().parent / "ui"
METRICS_LOCK = Lock()
REQUEST_METRICS: dict[str, object] = {
    "requests_total": 0,
    "errors_total": 0,
    "latency_ms_total": 0.0,
    "routes": defaultdict(int),
}


def _record_request_metric(method: str, path: str, status_code: int, latency_ms: float) -> None:
    with METRICS_LOCK:
        REQUEST_METRICS["requests_total"] = int(REQUEST_METRICS["requests_total"]) + 1
        REQUEST_METRICS["latency_ms_total"] = (
            float(REQUEST_METRICS["latency_ms_total"]) + latency_ms
        )
        if status_code >= 500:
            REQUEST_METRICS["errors_total"] = int(REQUEST_METRICS["errors_total"]) + 1
        routes = REQUEST_METRICS["routes"]
        if isinstance(routes, defaultdict):
            routes[f"{method} {path} {status_code}"] += 1


async def _session_cleanup_loop() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(chat_sessions.cleanup_expired)
        except Exception:
            # Cleanup is retried on the next interval. Request paths also delete
            # expired sessions, so a transient SQLite lock must not stop the app.
            continue


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    cleanup_task = asyncio.create_task(_session_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


def create_app() -> FastAPI:
    settings = get_settings()
    docs_enabled = settings.environment != "production"
    app = FastAPI(
        title="Poketdogam API",
        version="0.1.0",
        lifespan=_lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.include_router(chat_router, prefix="/v1")
    app.include_router(scan_router, prefix="/v1")
    app.include_router(pokedex_router, prefix="/v1")
    app.include_router(voice_router, prefix="/v1")
    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

    @app.middleware("http")
    async def security_headers(request, call_next) -> Response:
        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = (perf_counter() - started_at) * 1000
            _record_request_metric(request.method, request.url.path, 500, latency_ms)
            raise
        latency_ms = (perf_counter() - started_at) * 1000
        _record_request_metric(
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
        )
        response.headers["X-Process-Time-Ms"] = f"{latency_ms:.2f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/v1") else "no-cache"
        return response

    @app.get("/metrics")
    def metrics() -> dict[str, object]:
        with METRICS_LOCK:
            requests_total = int(REQUEST_METRICS["requests_total"])
            return {
                "requests_total": requests_total,
                "errors_total": int(REQUEST_METRICS["errors_total"]),
                "mean_latency_ms": round(
                    float(REQUEST_METRICS["latency_ms_total"]) / max(1, requests_total),
                    2,
                ),
                "routes": dict(REQUEST_METRICS["routes"]),
            }

    @app.get("/health")
    def health() -> dict[str, object]:
        return readiness()

    @app.get("/health/live")
    def liveness() -> dict[str, str]:
        return {"status": "alive", "version": app.version}

    @app.get("/health/ready")
    def readiness() -> dict[str, object]:
        store = get_local_dex()
        meta = store.dataset_meta()
        integrity = store.integrity_status()
        visual = visual_runtime_status()
        database_ready = (
            store.is_available()
            and int(meta.get("species_count") or 0) > 0
            and bool(integrity.get("valid"))
        )
        ready = database_ready and bool(visual.get("available"))
        ocr_engines = available_ocr_engines()
        return {
            "status": "ready" if ready else "degraded",
            "version": app.version,
            "dataset_version": meta.get("dataset_version"),
            "species_count": meta.get("species_count"),
            "ocr_engines": ocr_engines,
            "visual_recognition": visual,
            "components": {
                "database": "ready" if database_ready else "degraded",
                "visual_model": "ready" if visual.get("available") else "degraded",
                "ocr": "ready" if ocr_engines else "optional_unavailable",
            },
            "artifact_integrity": integrity,
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

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
