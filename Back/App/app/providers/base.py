from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Track:
    provider: str
    provider_track_id: str
    title: str
    artist: str
    artwork_url: str | None = None
    is_explicit: bool = False


class MusicProvider(ABC):
    name: str

    @abstractmethod
    def search_tracks(self, query: str, limit: int = 10) -> list[Track]:
        raise NotImplementedError

    @abstractmethod
    def get_track(self, track_id: str) -> Track | None:
        raise NotImplementedError

    @abstractmethod
    def play(self, track_id: str) -> Track:
        raise NotImplementedError

    @abstractmethod
    def pause(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def resume(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def skip(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_current_track(self) -> Track | None:
        raise NotImplementedError