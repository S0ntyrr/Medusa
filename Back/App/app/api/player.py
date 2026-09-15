from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.core.database import get_db
from app.providers.factory import get_provider

router = APIRouter(prefix="/player", tags=["player"])


class PlayRequest(BaseModel):
    track_id: str = Field(min_length=1, max_length=200)


def _track_response(provider) -> dict | None:
    track = provider.get_current_track()
    if track is None:
        return None
    return {**track.__dict__, "is_playing": True}


@router.get("/current")
def current_track(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    provider = get_provider(db, admin["venue_id"])
    track = _track_response(provider)
    return {"track": track, "is_playing": track is not None}


@router.post("/play")
def play_track(payload: PlayRequest, admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    provider = get_provider(db, admin["venue_id"])
    try:
        provider.play(payload.track_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"track": _track_response(provider), "is_playing": True}


@router.post("/pause")
def pause_track(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    provider = get_provider(db, admin["venue_id"])
    provider.pause()
    return {"track": _track_response(provider), "is_playing": False}


@router.post("/resume")
def resume_track(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    provider = get_provider(db, admin["venue_id"])
    provider.resume()
    track = _track_response(provider)
    return {"track": track, "is_playing": track is not None}


@router.post("/skip")
def skip_track(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    provider = get_provider(db, admin["venue_id"])
    provider.skip()
    return {"track": None, "is_playing": False}
