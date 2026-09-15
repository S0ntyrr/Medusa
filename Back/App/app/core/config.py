from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    frontend_url: str = "http://localhost:3000"
    secret_key: str = "development-only-change-me"
    session_max_hours: int = 3
    session_idle_minutes: int = 30
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    sb_publishable_key: str = ""
    allowed_origins: str = "http://localhost:3000"
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://localhost:8000/api/admin/spotify/callback"
    spotify_scopes: str = "user-read-email user-read-private user-read-playback-state user-modify-playback-state streaming"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()