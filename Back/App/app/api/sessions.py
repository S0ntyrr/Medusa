import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db

router = APIRouter(prefix="/session", tags=["sessions"])
settings = get_settings()


class SessionCreateRequest(BaseModel):
    venue_slug: str = "medusa-granizados"
    table_label: str | None = None


def _device_hash(request: Request) -> str:
    fingerprint = f"{request.client.host if request.client else 'unknown'}:{request.headers.get('user-agent', '')}"
    return hmac.new(settings.secret_key.encode(), fingerprint.encode(), hashlib.sha256).hexdigest()


def _expiry(last_activity: datetime, max_hours: int, idle_minutes: int) -> datetime:
    return min(
        last_activity + timedelta(minutes=idle_minutes),
        last_activity + timedelta(hours=max_hours),
    )


@router.post("/create", status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreateRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    venue = db.execute(
        text("select id from venues where slug = :slug"), {"slug": payload.venue_slug}
    ).mappings().first()
    if venue is None:
        raise HTTPException(status_code=404, detail="Venue not found")

    table_id = None
    if payload.table_label:
        table = db.execute(
            text("select id from venue_tables where venue_id = :venue_id and label = :label"),
            {"venue_id": venue["id"], "label": payload.table_label},
        ).mappings().first()
        if table is None:
            raise HTTPException(status_code=404, detail="Table not found")
        table_id = table["id"]

    now = datetime.now(timezone.utc)
    venue_settings = db.execute(text("select session_max_hours, session_idle_minutes from venue_settings where venue_id = :venue_id"), {"venue_id": venue["id"]}).mappings().first()
    max_hours = venue_settings["session_max_hours"] if venue_settings else settings.session_max_hours
    idle_minutes = venue_settings["session_idle_minutes"] if venue_settings else settings.session_idle_minutes
    session_id = str(uuid4())
    db.execute(
        text("""
            insert into sessions (id, venue_id, table_id, device_hash, last_activity, expires_at)
            values (:id, :venue_id, :table_id, :device_hash, :last_activity, :expires_at)
        """),
        {"id": session_id, "venue_id": venue["id"], "table_id": table_id,
         "device_hash": _device_hash(request), "last_activity": now, "expires_at": _expiry(now, max_hours, idle_minutes)},
    )
    db.commit()
    response.set_cookie("medusa_session", session_id, httponly=True, secure=False, samesite="lax", max_age=settings.session_max_hours * 3600)
    return {"status": "ACTIVE", "expires_at": _expiry(now, max_hours, idle_minutes).isoformat()}


def _active_session(session_id: str, db: Session) -> dict:
    session = db.execute(text("""
        select id, venue_id, status, expires_at, last_activity
        from sessions where id = :id
    """), {"id": session_id}).mappings().first()
    now = datetime.now(timezone.utc)
    if session is None or session["status"] != "ACTIVE" or session["expires_at"] <= now:
        raise HTTPException(status_code=401, detail="Session expired")
    venue_settings = db.execute(text("select session_max_hours, session_idle_minutes from venue_settings where venue_id = :venue_id"), {"venue_id": session["venue_id"]}).mappings().first()
    idle_minutes = venue_settings["session_idle_minutes"] if venue_settings else settings.session_idle_minutes
    if session["last_activity"] + timedelta(minutes=idle_minutes) <= now:
        db.execute(text("update sessions set status = 'EXPIRED' where id = :id"), {"id": session_id})
        db.commit()
        raise HTTPException(status_code=401, detail="Session expired")
    return session


@router.post("/heartbeat")
def heartbeat(
    medusa_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not medusa_session:
        raise HTTPException(status_code=401, detail="Session required")
    _active_session(medusa_session, db)
    now = datetime.now(timezone.utc)
    venue_settings = db.execute(text("select session_max_hours, session_idle_minutes from venue_settings where venue_id = (select venue_id from sessions where id = :id)"), {"id": medusa_session}).mappings().first()
    max_hours = venue_settings["session_max_hours"] if venue_settings else settings.session_max_hours
    idle_minutes = venue_settings["session_idle_minutes"] if venue_settings else settings.session_idle_minutes
    db.execute(text("update sessions set last_activity = :now, expires_at = :expires_at where id = :id"),
               {"now": now, "expires_at": _expiry(now, max_hours, idle_minutes), "id": medusa_session})
    db.commit()
    return {"status": "ACTIVE", "expires_at": _expiry(now, max_hours, idle_minutes).isoformat()}


@router.get("/status")
def session_status(
    medusa_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str | bool]:
    if not medusa_session:
        return {"active": False, "status": "MISSING"}
    session = _active_session(medusa_session, db)
    return {"active": True, "status": session["status"], "expires_at": session["expires_at"].isoformat()}