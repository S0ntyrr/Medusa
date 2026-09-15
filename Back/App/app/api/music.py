from fastapi import APIRouter, Cookie, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.sessions import _active_session
from app.core.database import get_db
from app.providers.factory import get_provider

router = APIRouter(prefix="/music", tags=["music"])


@router.get("/search")
def search_tracks(query: str = Query(min_length=1, max_length=100), limit: int = Query(default=10, ge=1, le=25), medusa_session: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> list[dict]:
    session = _active_session(medusa_session, db) if medusa_session else None
    if session:
        provider = get_provider(db, str(session["venue_id"]))
    else:
        from app.providers.demo import DemoMusicProvider
        provider = DemoMusicProvider()
    return [track.__dict__ for track in provider.search_tracks(query, limit)]


@router.get("/tracks/{track_id}")
def get_track(track_id: str, medusa_session: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict:
    session = _active_session(medusa_session, db) if medusa_session else None
    if session:
        provider = get_provider(db, str(session["venue_id"]))
    else:
        from app.providers.demo import DemoMusicProvider
        provider = DemoMusicProvider()
    track = provider.get_track(track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return track.__dict__