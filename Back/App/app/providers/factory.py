from sqlalchemy.orm import Session

from app.providers.base import MusicProvider
from app.providers.demo import DemoMusicProvider
from app.providers.spotify import SpotifyProvider


def get_provider(db: Session, venue_id: str) -> MusicProvider:
    if db is None:
        return DemoMusicProvider()
    try:
        return SpotifyProvider(db, venue_id)
    except ValueError:
        return DemoMusicProvider()