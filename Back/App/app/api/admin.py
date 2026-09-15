from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.core.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


class VenueSettingsUpdate(BaseModel):
    session_max_hours: int = Field(ge=1, le=24)
    session_idle_minutes: int = Field(ge=5, le=240)
    request_cooldown_minutes: int = Field(ge=0, le=120)
    max_pending_per_session: int = Field(ge=1, le=20)
    explicit_content_allowed: bool
    same_artist_window: int = Field(ge=1, le=20)
    same_artist_limit: int = Field(ge=1, le=10)
@router.get("/status")
def admin_status(_: dict[str, str] = Depends(require_admin)) -> dict[str, bool]:
    return {"authenticated": True}


@router.get("/settings")
def get_settings(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    row = db.execute(text("select * from venue_settings where venue_id = :venue_id"), {"venue_id": admin["venue_id"]}).mappings().first()
    if row is None:
        db.execute(text("insert into venue_settings (venue_id) values (:venue_id)"), {"venue_id": admin["venue_id"]})
        db.commit()
        row = db.execute(text("select * from venue_settings where venue_id = :venue_id"), {"venue_id": admin["venue_id"]}).mappings().first()
    return dict(row)


@router.patch("/settings")
def update_settings(payload: VenueSettingsUpdate, admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    values = payload.model_dump()
    values["venue_id"] = admin["venue_id"]
    db.execute(text("""
        insert into venue_settings (
            venue_id, session_max_hours, session_idle_minutes, request_cooldown_minutes,
            max_pending_per_session, explicit_content_allowed, same_artist_window, same_artist_limit
        ) values (
            :venue_id, :session_max_hours, :session_idle_minutes, :request_cooldown_minutes,
            :max_pending_per_session, :explicit_content_allowed, :same_artist_window, :same_artist_limit
        ) on conflict (venue_id) do update set
            session_max_hours = excluded.session_max_hours,
            session_idle_minutes = excluded.session_idle_minutes,
            request_cooldown_minutes = excluded.request_cooldown_minutes,
            max_pending_per_session = excluded.max_pending_per_session,
            explicit_content_allowed = excluded.explicit_content_allowed,
            same_artist_window = excluded.same_artist_window,
            same_artist_limit = excluded.same_artist_limit
    """), values)
    db.commit()
    return get_settings(admin, db)


@router.get("/sessions")
def active_sessions(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(text("""
        select s.id, s.table_id, s.created_at, s.last_activity, s.expires_at, s.status,
               v.name as venue_name
        from sessions s join venues v on v.id = s.venue_id
        where s.status = 'ACTIVE' and s.venue_id = :venue_id order by s.last_activity desc
    """), {"venue_id": admin["venue_id"]}).mappings().all()
    return [dict(row) for row in rows]


@router.post("/sessions/{session_id}/revoke")
def revoke_session(session_id: str, admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    result = db.execute(text("update sessions set status = 'REVOKED' where id = :id and venue_id = :venue_id and status = 'ACTIVE'"), {"id": session_id, "venue_id": admin["venue_id"]})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Active session not found")
    db.commit()
    return {"status": "REVOKED", "session_id": session_id}