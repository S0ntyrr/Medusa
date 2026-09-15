from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.sessions import _active_session
from app.core.database import get_db

router = APIRouter(prefix="/queue", tags=["queue"])


class QueueRequest(BaseModel):
    provider: str = Field(default="demo", min_length=1, max_length=40)
    provider_track_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(min_length=1, max_length=200)
    is_explicit: bool = False


def _session_or_401(session_id: str | None, db: Session) -> dict:
    if not session_id:
        raise HTTPException(status_code=401, detail="Session required")
    return _active_session(session_id, db)


@router.get("")
def get_queue(
    medusa_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    session = _session_or_401(medusa_session, db)
    rows = db.execute(text("""
        select qi.id, qi.status, qi.votes, qi.score, t.title, t.artist, t.artwork_url
        from queue_items qi join tracks t on t.id = qi.track_id
        where qi.venue_id = :venue_id and qi.status in ('PENDING', 'PLAYING')
        order by qi.status desc, qi.score desc, qi.requested_at asc
    """), {"venue_id": session["venue_id"]}).mappings().all()
    return [dict(row) for row in rows]


@router.post("/request", status_code=201)
def request_track(
    payload: QueueRequest,
    medusa_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    session = _session_or_401(medusa_session, db)
    venue_settings = db.execute(text("select * from venue_settings where venue_id = :venue_id"), {"venue_id": session["venue_id"]}).mappings().first()
    max_pending = venue_settings["max_pending_per_session"] if venue_settings else 3
    cooldown_minutes = venue_settings["request_cooldown_minutes"] if venue_settings else 10
    artist_window = venue_settings["same_artist_window"] if venue_settings else 5
    artist_limit = venue_settings["same_artist_limit"] if venue_settings else 2
    if payload.is_explicit and venue_settings and not venue_settings["explicit_content_allowed"]:
        raise HTTPException(status_code=422, detail="Explicit content is not allowed at this venue")
    blocked = db.execute(text("""
        select 1 from blocked_tracks bt
        join tracks t on t.id = bt.track_id
        where bt.venue_id = :venue_id and t.provider = :provider and t.provider_track_id = :provider_track_id
    """), {"venue_id": session["venue_id"], "provider": payload.provider, "provider_track_id": payload.provider_track_id}).first()
    artist_blocked = db.execute(text("select 1 from blocked_artists where venue_id = :venue_id and lower(artist_name) = lower(:artist)"), {"venue_id": session["venue_id"], "artist": payload.artist}).first()
    if blocked or artist_blocked:
        raise HTTPException(status_code=422, detail="This track or artist is blocked at this venue")
    recent_artist_count = db.execute(text("""
        select count(*) from queue_items qi join tracks t on t.id = qi.track_id
        where qi.venue_id = :venue_id and qi.status in ('PENDING', 'PLAYING')
          and lower(t.artist) = lower(:artist)
          and qi.requested_at >= now() - (:window_minutes * interval '1 minute')
    """), {"venue_id": session["venue_id"], "artist": payload.artist, "window_minutes": artist_window * 10}).scalar_one()
    if recent_artist_count >= artist_limit:
        raise HTTPException(status_code=422, detail="Artist limit reached for this venue")
    pending = db.execute(text("""
        select count(*) as total from queue_items
        where session_id = :session_id and status = 'PENDING'
    """), {"session_id": session["id"]}).scalar_one()
    if pending >= max_pending:
        raise HTTPException(status_code=429, detail="Maximum pending tracks reached")

    recent = db.execute(text("""
        select requested_at from queue_items
        where session_id = :session_id order by requested_at desc limit 1
    """), {"session_id": session["id"]}).scalar_one_or_none()
    if recent and (datetime.now(timezone.utc) - recent).total_seconds() < cooldown_minutes * 60:
        raise HTTPException(status_code=429, detail="Please wait before requesting another track")

    track_id = db.execute(text("""
        insert into tracks (id, provider, provider_track_id, title, artist, is_explicit)
        values (:id, :provider, :provider_track_id, :title, :artist, :is_explicit)
        on conflict (provider, provider_track_id) do update set title = excluded.title, artist = excluded.artist
        returning id
    """), {"id": str(uuid4()), **payload.model_dump()}).scalar_one()
    queue_id = str(uuid4())
    db.execute(text("""
        insert into queue_items (id, venue_id, session_id, track_id, score)
        values (:id, :venue_id, :session_id, :track_id, 0)
    """), {"id": queue_id, "venue_id": session["venue_id"], "session_id": session["id"], "track_id": track_id})
    db.commit()
    return {"id": queue_id, "status": "PENDING"}


@router.post("/{queue_id}/vote")
def vote_for_track(
    queue_id: str,
    medusa_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    session = _session_or_401(medusa_session, db)
    item = db.execute(text("""
        select id from queue_items where id = :queue_id and venue_id = :venue_id and status = 'PENDING'
    """), {"queue_id": queue_id, "venue_id": session["venue_id"]}).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Queue item not found")
    try:
        db.execute(text("insert into votes (id, queue_item_id, session_id) values (:id, :queue_id, :session_id)"),
                   {"id": str(uuid4()), "queue_id": queue_id, "session_id": session["id"]})
    except Exception as error:
        db.rollback()
        if "unique" in str(error).lower() or "duplicate" in str(error).lower():
            raise HTTPException(status_code=409, detail="Already voted") from error
        raise
    votes = db.execute(text("update queue_items set votes = votes + 1, score = score + 3 where id = :id returning votes"),
                       {"id": queue_id}).scalar_one()
    db.commit()
    return {"votes": votes}