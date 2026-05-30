from dataclasses import dataclass


@dataclass
class TrackInfo:
    song_name: str
    artist: str
    album: str
    row_y: int
    dots_btn_pos: tuple[int, int]

    def display_text(self) -> str:
        if self.artist:
            return f"{self.song_name} — {self.artist}"
        return self.song_name


@dataclass
class ClassificationResult:
    success: bool
    track_name: str
    target_playlist: str
    message: str


@dataclass
class MatchResult:
    position: tuple[int, int]
    confidence: float
