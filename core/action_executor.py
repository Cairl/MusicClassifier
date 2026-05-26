import time
import pyautogui
from core.models import ClassificationResult
from core.screen_capture import ScreenCapture
from core.ocr_reader import OCRReader


class ActionExecutor:
    def __init__(self, screen_capture: ScreenCapture, ocr_reader: OCRReader, after_click_ms: int = 700, menu_appear_ms: int = 500):
        self._screen_capture = screen_capture
        self._ocr_reader = ocr_reader
        self._after_click_ms = after_click_ms
        self._menu_appear_ms = menu_appear_ms

    def click_dots_button(self, dots_pos: tuple[int, int]) -> bool:
        try:
            pyautogui.click(dots_pos[0], dots_pos[1])
            time.sleep(self._after_click_ms / 1000)
            return True
        except Exception:
            return False

    def click_add_to_playlist(self) -> bool:
        try:
            screen = self._screen_capture.capture_full_window(delay_ms=int(self._menu_appear_ms))
            if screen is None:
                return False
            offset = self._screen_capture._window_rect[:2] if self._screen_capture._window_rect else (0, 0)
            items = self._ocr_reader.read_playlist_names(screen, offset)
            for text, pos in items:
                if "添加到歌单" in text or "Add to Playlist" in text:
                    pyautogui.click(pos[0], pos[1])
                    time.sleep(self._after_click_ms / 1000)
                    return True
            return False
        except Exception:
            return False

    def click_target_playlist(self, playlist_name: str) -> ClassificationResult:
        try:
            screen = self._screen_capture.capture_full_window(delay_ms=int(self._menu_appear_ms))
            if screen is None:
                return ClassificationResult(
                    success=False,
                    track_name="",
                    target_playlist=playlist_name,
                    message="截图失败，无法定位目标歌单",
                )
            offset = self._screen_capture._window_rect[:2] if self._screen_capture._window_rect else (0, 0)
            items = self._ocr_reader.read_playlist_names(screen, offset)
            for text, pos in items:
                if playlist_name in text or text in playlist_name:
                    pyautogui.click(pos[0], pos[1])
                    time.sleep(self._after_click_ms / 1000)
                    return ClassificationResult(
                        success=True,
                        track_name="",
                        target_playlist=playlist_name,
                        message=f"已添加到歌单: {playlist_name}",
                    )
            return ClassificationResult(
                success=False,
                track_name="",
                target_playlist=playlist_name,
                message=f"未找到歌单: {playlist_name}",
            )
        except Exception as e:
            return ClassificationResult(
                success=False,
                track_name="",
                target_playlist=playlist_name,
                message=f"操作异常: {str(e)}",
            )

    def classify_track(self, dots_pos: tuple[int, int], playlist_name: str, track_name: str) -> ClassificationResult:
        if not self.click_dots_button(dots_pos):
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="三点按钮点击失败",
            )
        if not self.click_add_to_playlist():
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="未找到「添加到歌单」选项",
            )
        result = self.click_target_playlist(playlist_name)
        result.track_name = track_name
        return result
