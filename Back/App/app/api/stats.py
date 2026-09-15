from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.core.database import get_db

router = APIRouter(prefix="/admin/stats", tags=["statistics"])


@router.get("")
def statistics(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    venue_id = admin["venue_id"]
    totals = db.execute(text("""
        select count(*) filter (where requested_at >= current_date) as requests_today,
               count(*) filter (where status = 'PENDING') as pending_tracks,
               coalesce(sum(votes), 0) as votes_total
        from queue_items where venue_id = :venue_id
    """), {"venue_id": venue_id}).mappings().one()
    active_sessions = db.execute(text("""
        select count(*) from sessions
        where venue_id = :venue_id and status = 'ACTIVE' and expires_at > now()
    """), {"venue_id": venue_id}).scalar_one()
    popular = db.execute(text("""
        select t.title, t.artist, sum(qi.votes) as votes
        from queue_items qi join tracks t on t.id = qi.track_id
        where qi.venue_id = :venue_id group by t.id order by votes desc limit 5
    """), {"venue_id": venue_id}).mappings().all()
    return {"requests_today": totals["requests_today"], "pending_tracks": totals["pending_tracks"], "votes_total": totals["votes_total"], "active_sessions": active_sessions, "popular_tracks": [dict(row) for row in popular]}