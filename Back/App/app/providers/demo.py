from app.providers.base import MusicProvider, Track


class DemoMusicProvider(MusicProvider):
    name = "demo"
    _current_track_id: str | None = None
    _is_playing = False

    _tracks = (
        Track("demo", "1", "LUNA", "Feid", is_explicit=False),
        Track("demo", "2", "Classy 101", "Feid, Young Miko", is_explicit=True),
        Track("demo", "3", "Ojitos Lindos", "Bad Bunny, Bomba Estereo"),
        Track("demo", "4", "Todo Contigo", "Alvaro de Luna"),
        Track("demo", "5", "La Falda", "Myke Towers", is_explicit=True),
    )

    def search_tracks(self, query: str, limit: int = 10) -> list[Track]:
        normalized = query.strip().lower()
        if not normalized:
            return []
        return [track for track in self._tracks if normalized in f"{track.title} {track.artist}".lower()][:limit]

    def get_track(self, track_id: str) -> Track | None:
        return next((track for track in self._tracks if track.provider_track_id == track_id), None)

    def play(self, track_id: str) -> Track:
        track = self.get_track(track_id)
        if track is None:
            raise ValueError("Track not found")
        self._current_track_id = track_id
        self._is_playing = True
        return track

    def pause(self) -> None:
        self._is_playing = False

    def resume(self) -> None:
        if self._current_track_id:
            self._is_playing = True

    def skip(self) -> None:
        self._current_track_id = None
        self._is_playing = False

    def get_current_track(self) -> Track | None:
        return self.get_track(self._current_track_id) if self._current_track_id else None


def get_music_provider() -> MusicProvider:
    return DemoMusicProvider()