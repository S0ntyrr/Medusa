from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.admin import router as admin_router
from app.api.admin_queue import router as admin_queue_router
from app.api.blocklist import router as blocklist_router
from app.api.spotify import router as spotify_router
from app.api.stats import router as stats_router
from app.api.music import router as music_router
from app.api.player import router as player_router
from app.api.queue import router as queue_router
from app.api.sessions import router as sessions_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title="Medusa Granizados API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(health_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(admin_queue_router, prefix="/api")
app.include_router(blocklist_router, prefix="/api")
app.include_router(spotify_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(music_router, prefix="/api")
app.include_router(player_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(queue_router, prefix="/api")