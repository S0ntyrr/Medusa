from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.core.database import get_db

router = APIRouter(prefix="/admin/blocklist", tags=["blocklist"])


class ArtistBlock(BaseModel):
    artist_name: str = Field(min_length=1, max_length=200)


@router.post("/tracks/{track_id}")
def block_track(track_id: str, admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    exists = db.execute(text("select 1 from tracks where id = :track_id"), {"track_id": track_id}).first()
    if exists is None:
        raise HTTPException(status_code=404, detail="Track not found")
    db.execute(text("""
        insert into blocked_tracks (venue_id, track_id) values (:venue_id, :track_id)
        on conflict (venue_id, track_id) do nothing
    """), {"venue_id": admin["venue_id"], "track_id": track_id})
    db.commit()
    return {"status": "BLOCKED", "track_id": track_id}


@router.delete("/tracks/{track_id}")
def unblock_track(track_id: str, admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("delete from blocked_tracks where venue_id = :venue_id and track_id = :track_id"), {"venue_id": admin["venue_id"], "track_id": track_id})
    db.commit()
    return {"status": "UNBLOCKED", "track_id": track_id}


@router.post("/artists")
def block_artist(payload: ArtistBlock, admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("""
        insert into blocked_artists (venue_id, artist_name) values (:venue_id, :artist_name)
        on conflict (venue_id, artist_name) do nothing
    """), {"venue_id": admin["venue_id"], "artist_name": payload.artist_name})
    db.commit()
    return {"status": "BLOCKED", "artist_name": payload.artist_name}


@router.delete("/artists/{artist_name}")
def unblock_artist(artist_name: str, admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("delete from blocked_artists where venue_id = :venue_id and artist_name = :artist_name"), {"venue_id": admin["venue_id"], "artist_name": artist_name})
    db.commit()
    return {"status": "UNBLOCKED", "artist_name": artist_name}