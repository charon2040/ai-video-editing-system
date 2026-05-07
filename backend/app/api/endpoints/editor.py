from fastapi import APIRouter

from app.api.editor import ai, exports, projects, timeline

router = APIRouter()
router.include_router(projects.router)
router.include_router(timeline.router)
router.include_router(exports.router)
router.include_router(ai.router)
