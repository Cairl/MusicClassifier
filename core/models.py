from dataclasses import dataclass


@dataclass
class TrackInfo:
    song_name: str
    artist: str
    album: str
    row_y: int
    dots_btn_pos: tuple[int, int]
    ocr_boxes: list[tuple[int, int, int, int, str]] = None

    def __post_init__(self):
        if self.ocr_boxes is None:
            self.ocr_boxes = []

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
