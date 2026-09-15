from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.token_crypto import decrypt_token, encrypt_token
from app.providers.base import MusicProvider, Track


class SpotifyProvider(MusicProvider):
    name = "spotify"
    api_url = "https://api.spotify.com/v1"

    def __init__(self, db: Session, venue_id: str):
        self.db = db
        self.venue_id = venue_id
        self.settings = get_settings()
        self._connection = self._load_connection()

    def _load_connection(self) -> dict[str, Any]:
        row = self.db.execute(text("""
            select access_token_encrypted, refresh_token_encrypted, expires_at
            from music_provider_connections
            where venue_id = :venue_id and provider = 'spotify'
        """), {"venue_id": self.venue_id}).mappings().first()
        if row is None:
            raise ValueError("Spotify is not connected for this venue")
        return dict(row)

    def _access_token(self) -> str:
        expires_at = self._connection["expires_at"]
        if expires_at and expires_at > datetime.now(timezone.utc) + timedelta(seconds=30):
            return decrypt_token(self._connection["access_token_encrypted"])
        refresh_token = self._connection.get("refresh_token_encrypted")
        if not refresh_token:
            raise ValueError("Spotify refresh token is unavailable")
        import base64
        credentials = base64.b64encode(f"{self.settings.spotify_client_id}:{self.settings.spotify_client_secret}".encode()).decode()
        response = httpx.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "refresh_token", "refresh_token": decrypt_token(refresh_token)},
            headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        response.raise_for_status()
        tokens = response.json()
        access_token = tokens["access_token"]
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600)))
        self.db.execute(text("""
            update music_provider_connections
            set access_token_encrypted = :access_token, expires_at = :expires_at
            where venue_id = :venue_id and provider = 'spotify'
        """), {"access_token": encrypt_token(access_token), "expires_at": expires_at, "venue_id": self.venue_id})
        self.db.commit()
        self._connection["access_token_encrypted"] = encrypt_token(access_token)
        self._connection["expires_at"] = expires_at
        return access_token

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any] | list[Any] | None:
        response = httpx.request(method, f"{self.api_url}{path}", headers={"Authorization": f"Bearer {self._access_token()}"}, timeout=10, **kwargs)
        if response.status_code == 204:
            return None
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _track(item: dict[str, Any]) -> Track:
        artists = ", ".join(artist["name"] for artist in item.get("artists", []))
        images = item.get("album", {}).get("images", [])
        return Track("spotify", item["id"], item["name"], artists, images[0]["url"] if images else None, item.get("explicit", False))

    def search_tracks(self, query: str, limit: int = 10) -> list[Track]:
        data = self._request("GET", "/search", params={"q": query, "type": "track", "limit": limit}) or {}
        return [self._track(item) for item in data.get("tracks", {}).get("items", [])]

    def get_track(self, track_id: str) -> Track | None:
        try:
            result = self._request("GET", f"/tracks/{track_id}")
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return None
            raise
        return self._track(result) if isinstance(result, dict) else None

    def play(self, track_id: str) -> Track:
        track = self.get_track(track_id)
        if track is None:
            raise ValueError("Track not found")
        self._request("PUT", "/me/player/play", json={"uris": [f"spotify:track:{track_id}"]})
        return track

    def pause(self) -> None:
        self._request("PUT", "/me/player/pause")

    def resume(self) -> None:
        self._request("PUT", "/me/player/play")

    def skip(self) -> None:
        self._request("POST", "/me/player/next")

    def get_current_track(self) -> Track | None:
        data = self._request("GET", "/me/player")
        item = data.get("item") if isinstance(data, dict) else None
        return self._track(item) if isinstance(item, dict) and item.get("type") == "track" else None