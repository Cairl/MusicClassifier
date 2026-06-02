import re
import cv2
import numpy as np
from paddleocr import PaddleOCR
from core.models import TrackInfo


class OCRReader:
    DOTS_X_RATIO = 0.95
    HEADER_KEYWORDS = {"播放", "随机播放", "艺人", "专辑", "时长", "歌曲"}
    DURATION_PATTERN = re.compile(r"^\d{1,2}:\d{2}$")

    SONG_X_MAX = 0.28
    ARTIST_X_MAX = 0.55
    ALBUM_X_MAX = 0.78

    SONG_CROP_X_MAX = 0.30
    SONG_CROP_SCALE = 3

    def __init__(self):
        self._ocr: PaddleOCR | None = None

    def _ensure_ocr(self):
        if self._ocr is None:
            self._ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)

    def read_tracks(self, image: np.ndarray, window_offset: tuple[int, int] = (0, 0),
                    song_region_box: tuple[int, int, int, int] | None = None,
                    artist_region_box: tuple[int, int, int, int] | None = None) -> list[TrackInfo]:
        self._ensure_ocr()
        
        # If position templates exist, only OCR those specific regions
        if song_region_box is not None or artist_region_box is not None:
            return self._read_tracks_by_position(
                image, window_offset, song_region_box, artist_region_box)
        
        # Fallback: full-image OCR with column classification
        return self._read_tracks_full(image, window_offset)

    def _read_tracks_by_position(self, image: np.ndarray,
                                  window_offset: tuple[int, int],
                                  song_box: tuple[int, int, int, int] | None,
                                  artist_box: tuple[int, int, int, int] | None) -> list[TrackInfo]:
        """OCR using pre-defined position regions instead of full-image scan."""
        h, w = image.shape[:2]
        song_name = ""
        artist = ""
        row_y = 0
        dots_pos = (0, 0)

        if song_box:
            sx, sy, sw, sh = song_box
            # Convert window-relative to image-relative
            sx = max(0, sx - window_offset[0])
            sy = max(0, sy - window_offset[1])
            sw = min(sw, w - sx)
            sh = min(sh, h - sy)
            if sw > 10 and sh > 10:
                crop = image[sy:sy+sh, sx:sx+sw]
                result = self._ocr.ocr(crop, cls=True)
                if result and result[0]:
                    # Group by Y position, keep only the first row
                    rows: dict[int, list[str]] = {}
                    for line in result[0]:
                        box = line[0]
                        text = line[1][0]
                        conf = line[1][1]
                        if conf < 0.5:
                            continue
                        y_center = int(sum(p[1] for p in box) / 4)
                        row_key = y_center // 20 * 20
                        rows.setdefault(row_key, []).append(text)
                    if rows:
                        first_row_key = min(rows.keys())
                        song_name = " ".join(rows[first_row_key])
                        row_y = sy + sh // 2

        if artist_box:
            ax, ay, aw, ah = artist_box
            ax = max(0, ax - window_offset[0])
            ay = max(0, ay - window_offset[1])
            aw = min(aw, w - ax)
            ah = min(ah, h - ay)
            if aw > 10 and ah > 10:
                crop = image[ay:ay+ah, ax:ax+aw]
                result = self._ocr.ocr(crop, cls=True)
                if result and result[0]:
                    texts = [line[1][0] for line in result[0] if line[1][1] >= 0.5]
                    if texts:
                        artist = " ".join(texts)
                        if row_y == 0:
                            row_y = ay + ah // 2

        img_w = image.shape[1]
        dots_pos = self._estimate_dots_pos(row_y, img_w, window_offset)
        track = TrackInfo(
            song_name=song_name or "未知歌曲",
            artist=artist,
            album="",
            row_y=row_y,
            dots_btn_pos=dots_pos,
        )
        return [track]

    def _read_tracks_full(self, image: np.ndarray, window_offset: tuple[int, int]) -> list[TrackInfo]:
        result = self._ocr.ocr(image, cls=True)
        if not result or not result[0]:
            return []
        ocr_lines = []
        for line in result[0]:
            box = line[0]
            text = line[1][0]
            confidence = line[1][1]
            x_min = int(min(p[0] for p in box))
            y_min = int(min(p[1] for p in box))
            x_max = int(max(p[0] for p in box))
            y_max = int(max(p[1] for p in box))
            ocr_lines.append(([x_min, y_min, x_max, y_max], (text, confidence)))
        tracks = self._parse_to_tracks(ocr_lines, image.shape[1], window_offset)
        tracks = self._refine_song_names(image, tracks, window_offset)
        return tracks

    def _is_header_text(self, text: str) -> bool:
        for kw in self.HEADER_KEYWORDS:
            if kw in text:
                return True
        return False

    def _classify_column(self, x_center: int, img_width: int) -> str:
        ratio = x_center / img_width
        if ratio < self.SONG_X_MAX:
            return "song"
        elif ratio < self.ARTIST_X_MAX:
            return "artist"
        elif ratio < self.ALBUM_X_MAX:
            return "album"
        else:
            return "other"

    def _parse_to_tracks(self, ocr_results: list, img_width: int, window_offset: tuple[int, int]) -> list[TrackInfo]:
        if not ocr_results:
            return []
        classified: list[tuple] = []
        for box, (text, conf) in ocr_results:
            x_center = (box[0] + box[2]) // 2
            y_center = (box[1] + box[3]) // 2
            col = self._classify_column(x_center, img_width)
            if self.DURATION_PATTERN.match(text.strip()):
                col = "duration"
            classified.append((box, text, conf, col, y_center))
        rows: dict[int, list] = {}
        for item in classified:
            _, _, _, _, y_center = item
            row_key = y_center // 80 * 80
            if row_key not in rows:
                rows[row_key] = []
            rows[row_key].append(item)
        tracks = []
        for row_key in sorted(rows.keys()):
            items = rows[row_key]
            all_text = " ".join(t[1] for t in items)
            if self._is_header_text(all_text):
                continue
            song_parts = []
            artist_parts = []
            album_parts = []
            for box, text, conf, col, _ in items:
                if col == "song":
                    song_parts.append(text)
                elif col == "artist":
                    artist_parts.append(text)
                elif col == "album":
                    album_parts.append(text)
            song_name = " ".join(song_parts) if song_parts else ""
            artist = " ".join(artist_parts) if artist_parts else ""
            album = " ".join(album_parts) if album_parts else ""
            if not song_name and artist:
                song_name = artist
                artist = ""
            row_y = row_key
            dots_pos = self._estimate_dots_pos(row_y, img_width, window_offset)
            tracks.append(TrackInfo(
                song_name=song_name,
                artist=artist,
                album=album,
                row_y=row_y,
                dots_btn_pos=dots_pos,
            ))
        return tracks

    def _refine_song_names(self, image: np.ndarray, tracks: list[TrackInfo], window_offset: tuple[int, int]) -> list[TrackInfo]:
        h, w = image.shape[:2]
        crop_x_max = int(w * self.SONG_CROP_X_MAX)
        song_region = image[:, :crop_x_max]
        scaled = cv2.resize(song_region, None, fx=self.SONG_CROP_SCALE, fy=self.SONG_CROP_SCALE, interpolation=cv2.INTER_CUBIC)
        result = self._ocr.ocr(scaled, cls=True)
        if not result or not result[0]:
            return tracks
        refined_rows: dict[int, str] = {}
        for line in result[0]:
            box = line[0]
            text = line[1][0]
            conf = line[1][1]
            if conf < 0.5:
                continue
            y_center = int(min(p[1] for p in box) / self.SONG_CROP_SCALE)
            row_key = y_center // 80 * 80
            if row_key not in refined_rows:
                refined_rows[row_key] = text
            else:
                refined_rows[row_key] += " " + text
        for track in tracks:
            if track.row_y in refined_rows:
                refined = refined_rows[track.row_y].strip()
                if refined and len(refined) > len(track.song_name):
                    track.song_name = refined
        return tracks

    def _estimate_dots_pos(self, row_y: int, img_width: int, window_offset: tuple[int, int]) -> tuple[int, int]:
        abs_x = int(window_offset[0] + img_width * self.DOTS_X_RATIO)
        abs_y = window_offset[1] + row_y + 30
        return (abs_x, abs_y)

    def read_playlist_names(self, image: np.ndarray, window_offset: tuple[int, int] = (0, 0)) -> list[tuple[str, tuple[int, int]]]:
        self._ensure_ocr()
        result = self._ocr.ocr(image, cls=True)
        if not result or not result[0]:
            return []
        playlists = []
        for line in result[0]:
            box = line[0]
            text = line[1][0]
            conf = line[1][1]
            if conf < 0.5:
                continue
            x_center = int(sum(p[0] for p in box) / 4) + window_offset[0]
            y_center = int(sum(p[1] for p in box) / 4) + window_offset[1]
            playlists.append((text, (x_center, y_center)))
        return playlists
