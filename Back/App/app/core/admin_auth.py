import httpx
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db

settings = get_settings()


def require_admin(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Supabase access token required")
    publishable_key = settings.supabase_publishable_key or settings.sb_publishable_key
    if not settings.supabase_url or not publishable_key:
        raise HTTPException(status_code=503, detail="Supabase Auth is not configured")

    token = authorization.split(" ", 1)[1].strip()
    try:
        response = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={"apikey": publishable_key, "Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="Supabase Auth unavailable") from error
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Supabase access token")

    user = response.json()
    admin = db.execute(text("""
        select id, venue_id, email from admin_users
        where provider_user_id = :provider_user_id and email = :email
    """), {"provider_user_id": user.get("id"), "email": user.get("email")}).mappings().first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not an administrator")
    return {"id": str(admin["id"]), "venue_id": str(admin["venue_id"]), "email": admin["email"]}
