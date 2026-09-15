from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.core.database import get_db

router = APIRouter(prefix="/admin/queue", tags=["admin-queue"])


@router.get("")
def admin_queue(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(text("""
        select qi.id, qi.status, qi.votes, qi.score, qi.requested_at,
               t.id as track_id, t.title, t.artist, t.is_explicit
        from queue_items qi join tracks t on t.id = qi.track_id
        where qi.venue_id = :venue_id and qi.status in ('PENDING', 'PLAYING')
        order by qi.status desc, qi.score desc, qi.requested_at asc
    """), {"venue_id": admin["venue_id"]}).mappings().all()
    return [dict(row) for row in rows]


@router.delete("/{queue_id}")
def remove_queue_item(queue_id: str, admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    result = db.execute(text("""
        update queue_items set status = 'REMOVED', finished_at = now()
        where id = :id and venue_id = :venue_id and status in ('PENDING', 'PLAYING')
    """), {"id": queue_id, "venue_id": admin["venue_id"]})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Queue item not found")
    db.commit()
    return {"status": "REMOVED", "queue_id": queue_id}


@router.post("/{queue_id}/skip")
def skip_queue_item(queue_id: str, admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    result = db.execute(text("""
        update queue_items set status = 'SKIPPED', finished_at = now()
        where id = :id and venue_id = :venue_id and status in ('PENDING', 'PLAYING')
    """), {"id": queue_id, "venue_id": admin["venue_id"]})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Queue item not found")
    db.commit()
    return {"status": "SKIPPED", "queue_id": queue_id}


@router.post("/recalculate")
def recalculate_scores(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, int]:
    result = db.execute(text("""
        update queue_items
        set score = votes * 3 + extract(epoch from (now() - requested_at)) / 60
        where venue_id = :venue_id and status = 'PENDING'
    """), {"venue_id": admin["venue_id"]})
    db.commit()
    return {"updated": result.rowcount}