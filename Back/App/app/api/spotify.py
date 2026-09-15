import base64
import hashlib
import hmac
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.core.token_crypto import encrypt_token
from app.providers.spotify import SpotifyProvider

router = APIRouter(prefix="/admin/spotify", tags=["spotify"])
settings = get_settings()


def _sign_state(value: str) -> str:
    digest = hmac.new(settings.secret_key.encode(), value.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


@router.get("/connect")
def connect(admin: dict[str, str] = Depends(require_admin)) -> dict[str, str]:
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        raise HTTPException(status_code=503, detail="Spotify OAuth is not configured")
    nonce = secrets.token_urlsafe(24)
    payload = f"{admin['venue_id']}:{nonce}"
    state = f"{payload}:{_sign_state(payload)}"
    query = urllib.parse.urlencode({
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": settings.spotify_scopes,
        "state": state,
        "show_dialog": "true",
    })
    return {"authorization_url": f"https://accounts.spotify.com/authorize?{query}", "state": state}


@router.get("/callback")
def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        return RedirectResponse(f"{settings.frontend_url}/admin?spotify_error={urllib.parse.quote(error)}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Spotify OAuth callback is incomplete")
    parts = state.rsplit(":", 2)
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    venue_id, nonce, signature = parts
    payload = f"{venue_id}:{nonce}"
    if not hmac.compare_digest(signature, _sign_state(payload)):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    basic = base64.b64encode(f"{settings.spotify_client_id}:{settings.spotify_client_secret}".encode()).decode()
    try:
        token_response = httpx.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": settings.spotify_redirect_uri},
            headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        token_response.raise_for_status()
        tokens = token_response.json()
        profile = httpx.get("https://api.spotify.com/v1/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}, timeout=10)
        profile.raise_for_status()
    except (httpx.HTTPError, KeyError) as exc:
        raise HTTPException(status_code=502, detail="Spotify OAuth exchange failed") from exc

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600)))
    db.execute(text("""
        insert into music_provider_connections
          (venue_id, provider, provider_account_id, access_token_encrypted, refresh_token_encrypted, expires_at)
        values (:venue_id, 'spotify', :account_id, :access_token, :refresh_token, :expires_at)
        on conflict (venue_id, provider) do update set
          provider_account_id = excluded.provider_account_id,
          access_token_encrypted = excluded.access_token_encrypted,
          refresh_token_encrypted = excluded.refresh_token_encrypted,
          expires_at = excluded.expires_at
    """), {"venue_id": venue_id, "account_id": profile.json().get("id"), "access_token": encrypt_token(tokens["access_token"]), "refresh_token": encrypt_token(tokens["refresh_token"]) if tokens.get("refresh_token") else None, "expires_at": expires_at})
    db.commit()
    return RedirectResponse(f"{settings.frontend_url}/admin?spotify=connected")


@router.get("/status")
def status(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str | bool | None]:
    row = db.execute(text("select provider_account_id, expires_at from music_provider_connections where venue_id = :venue_id and provider = 'spotify'"), {"venue_id": admin["venue_id"]}).mappings().first()
    return {"connected": row is not None, "account_id": row["provider_account_id"] if row else None, "expires_at": row["expires_at"].isoformat() if row and row["expires_at"] else None}


@router.get("/player-token")
def player_token(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        token = SpotifyProvider(db, admin["venue_id"])._access_token()
    except (ValueError, httpx.HTTPError) as error:
        raise HTTPException(status_code=503, detail="Spotify player is not available") from error
    return {"access_token": token}