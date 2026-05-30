import time
import traceback
import pyautogui
from core.models import ClassificationResult, MatchResult
from core.screen_capture import ScreenCapture
from core.template_library import TemplateLibrary


class ActionExecutor:
    def __init__(self, screen_capture: ScreenCapture, template_library: TemplateLibrary, after_click_ms: int = 700, menu_appear_ms: int = 500):
        self._screen_capture = screen_capture
        self._template_lib = template_library
        self._after_click_ms = after_click_ms
        self._menu_appear_ms = menu_appear_ms

    def click_dots_button(self, dots_pos: tuple[int, int]) -> bool:
        try:
            pyautogui.click(dots_pos[0], dots_pos[1])
            time.sleep(self._after_click_ms / 1000)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def _screenshot_and_find(self, template_name: str) -> tuple[int, int] | None:
        screen = self._screen_capture.capture_full_window(delay_ms=int(self._menu_appear_ms))
        if screen is None:
            return None
        match = self._template_lib.find_template(screen, template_name)
        if match is None:
            return None
        offset = self._screen_capture._window_rect[:2] if self._screen_capture._window_rect else (0, 0)
        return (match.position[0] + offset[0], match.position[1] + offset[1])

    def _click_template(self, template_name: str) -> bool:
        pos = self._screenshot_and_find(template_name)
        if pos is None:
            return False
        pyautogui.click(pos[0], pos[1])
        time.sleep(self._after_click_ms / 1000)
        return True

    def classify_track(self, dots_pos: tuple[int, int], playlist_name: str, volume_name: str, track_name: str) -> ClassificationResult:
        if not self.click_dots_button(dots_pos):
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="三点按钮点击失败",
            )

        if not self._template_lib.has_template("ui/add_to_playlist"):
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="模板 templates/ui/add_to_playlist.png 不存在，请先采集",
            )

        if not self._click_template("ui/add_to_playlist"):
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="未找到「添加到播放列表」按钮",
            )

        playlist_found_directly = False
        if self._template_lib.has_template(f"playlists/{playlist_name}"):
            if self._click_template(f"playlists/{playlist_name}"):
                playlist_found_directly = True

        if not playlist_found_directly:
            if not self._template_lib.has_template(f"volumes/{volume_name}"):
                return ClassificationResult(
                    success=False,
                    track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"模板 templates/volumes/{volume_name}.png 不存在，请先采集",
                )

            if not self._click_template(f"volumes/{volume_name}"):
                return ClassificationResult(
                    success=False,
                    track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"未找到歌单「{playlist_name}」或卷「{volume_name}」",
                )

            if not self._template_lib.has_template(f"playlists/{playlist_name}"):
                return ClassificationResult(
                    success=False,
                    track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"模板 templates/playlists/{playlist_name}.png 不存在，请先采集",
                )

            if not self._click_template(f"playlists/{playlist_name}"):
                return ClassificationResult(
                    success=False,
                    track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"未找到歌单「{playlist_name}」或卷「{volume_name}」",
                )

        if not self.click_dots_button(dots_pos):
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="三点按钮点击失败（删除前）",
            )

        try:
            pyautogui.press("delete")
            time.sleep(self._after_click_ms / 1000)
        except Exception:
            traceback.print_exc()
            return ClassificationResult(
                success=False,
                track_name=track_name,
                target_playlist=playlist_name,
                message="删除操作失败",
            )

        return ClassificationResult(
            success=True,
            track_name=track_name,
            target_playlist=playlist_name,
            message=f"已添加到歌单: {playlist_name}",
        )
