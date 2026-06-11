import logging
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.protected_files import router as protected_files_router
from app.api.routes.system import router as system_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.voice_profiles import router as voice_profiles_router
from app.core.config import ensure_runtime_dirs, settings
from app.services.cosyvoice_runtime_service import cosyvoice_runtime_service
from app.services.auth_service import auth_service
from app.services.task_service import task_service


class _AccessLogFilter(logging.Filter):
    _polling_paths = (
        "GET /api/tasks",
        "GET /api/voice-profiles",
        "GET /api/health",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(path in message for path in self._polling_paths)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("uvicorn.access").addFilter(_AccessLogFilter())

ensure_runtime_dirs()
recovered_count = task_service.recover_interrupted_tasks()
auth_service.ensure_default_user()
if recovered_count:
    logging.getLogger(__name__).warning(
        "Recovered %s interrupted tasks after service restart.",
        recovered_count,
    )

app = FastAPI(title=settings.project_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
if settings.frontend_dist_dir.exists():
    assets_dir = settings.frontend_dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend_assets")
app.include_router(auth_router)
app.include_router(tasks_router)
app.include_router(system_router)
app.include_router(voice_profiles_router)
app.include_router(protected_files_router)


def _warm_cosyvoice_service() -> None:
    try:
        cosyvoice_runtime_service.ensure_service_running()
        logging.getLogger(__name__).info("CosyVoice persistent service is ready.")
    except Exception:
        logging.getLogger(__name__).exception("Failed to warm CosyVoice persistent service.")


@app.on_event("startup")
async def startup_event() -> None:
    threading.Thread(target=_warm_cosyvoice_service, daemon=True).start()


@app.get("/")
async def read_index():
    frontend_index = settings.frontend_dist_dir / "index.html"
    if frontend_index.exists():
        return FileResponse(frontend_index)
    return FileResponse(settings.static_dir / "index.html")


@app.get(f"{settings.api_prefix}/health")
async def health():
    return {"status": "ok", "project": settings.project_name}


@app.get("/{full_path:path}")
async def read_frontend_app(full_path: str):
    if full_path.startswith(settings.api_prefix.strip("/") + "/"):
        raise HTTPException(status_code=404, detail="API route not found")
    frontend_index = settings.frontend_dist_dir / "index.html"
    if frontend_index.exists():
        return FileResponse(frontend_index)
    return FileResponse(settings.static_dir / "index.html")
