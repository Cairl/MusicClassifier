import time
import traceback
import pyautogui
from core.models import ClassificationResult
from core.screen_capture import ScreenCapture
from core.template_library import TemplateLibrary


class ActionExecutor:
    def __init__(self, screen_capture: ScreenCapture, template_library: TemplateLibrary,
                 after_click_ms: int = 700, menu_appear_ms: int = 500):
        self._screen_capture = screen_capture
        self._template_lib = template_library
        self._after_click_ms = after_click_ms
        self._menu_appear_ms = menu_appear_ms

    # ── Click helpers ───────────────────────────────────────────

    def click_dots_button(self, dots_pos: tuple[int, int] | None = None) -> bool:
        """Click the three-dots (⋯) button on the focused song row.
        Uses cached X (fixed position) + OCR Y (correct row) for precision."""
        try:
            # Get cached X position (dots button X is fixed in Apple Music)
            offset = self._screen_capture._window_rect[:2] \
                if self._screen_capture._window_rect else (0, 0)
            cached = self._template_lib.find_fixed_position("ui/more_button", offset)

            if cached is not None and dots_pos is not None:
                # Use cached X (fixed column) + OCR Y (correct row)
                pyautogui.click(cached[0], dots_pos[1])
                time.sleep(self._after_click_ms / 1000)
                return True
            elif cached is not None:
                # No OCR position — use cached position directly
                pyautogui.click(cached[0], cached[1])
                time.sleep(self._after_click_ms / 1000)
                return True
            elif dots_pos is not None:
                # Fallback: use OCR position directly
                pyautogui.click(dots_pos[0], dots_pos[1])
                time.sleep(self._after_click_ms / 1000)
                return True

            return False
        except Exception:
            traceback.print_exc()
            return False

    def _screenshot_and_find(self, template_name: str,
                             use_full_screen: bool = False) -> tuple[int, int] | None:
        """Capture screen and find template. Returns (screen_x, screen_y)."""
        if use_full_screen:
            screen = self._screen_capture.capture_full_screen(
                delay_ms=int(self._menu_appear_ms))
            offset = (0, 0)
        else:
            screen = self._screen_capture.capture_full_window(
                delay_ms=int(self._menu_appear_ms))
            if screen is None:
                return None
            offset = self._screen_capture._window_rect[:2] \
                if self._screen_capture._window_rect else (0, 0)
        if screen is None:
            return None
        match = self._template_lib.find_template(screen, template_name)
        if match is None:
            return None
        screen_x = match.position[0] + offset[0]
        screen_y = match.position[1] + offset[1]
        return (screen_x, screen_y)

    def _click_template(self, template_name: str,
                        use_full_screen: bool = False) -> bool:
        """Find template and click."""
        pos = self._screenshot_and_find(template_name, use_full_screen)
        if pos is None:
            return False
        pyautogui.click(pos[0], pos[1])
        time.sleep(self._after_click_ms / 1000)
        return True

    # ── Classification ──────────────────────────────────────────

    def classify_track(self, dots_pos: tuple[int, int],
                       playlist_name: str, volume_name: str,
                       track_name: str) -> ClassificationResult:
        # Step 1: Click the ⋯ button
        if not self.click_dots_button(dots_pos):
            return ClassificationResult(
                success=False, track_name=track_name,
                target_playlist=playlist_name,
                message="三点按钮点击失败",
            )

        # Step 2: Find and click "添加到播放列表" (context menu — full screen search)
        if not self._template_lib.has_template("ui/add_to_playlist"):
            return ClassificationResult(
                success=False, track_name=track_name,
                target_playlist=playlist_name,
                message="模板 templates/ui/add_to_playlist.png 不存在，请先采集",
            )
        if not self._click_template("ui/add_to_playlist", use_full_screen=True):
            return ClassificationResult(
                success=False, track_name=track_name,
                target_playlist=playlist_name,
                message="未找到「添加到播放列表」按钮",
            )

        # Step 3: Try direct playlist click (submenu — full screen)
        playlist_found = False
        if self._template_lib.has_template(f"playlists/{playlist_name}"):
            if self._click_template(f"playlists/{playlist_name}", use_full_screen=True):
                playlist_found = True

        # Step 4: If not found directly, click volume then playlist
        if not playlist_found:
            if not self._template_lib.has_template(f"volumes/{volume_name}"):
                return ClassificationResult(
                    success=False, track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"模板 templates/volumes/{volume_name}.png 不存在，请先采集",
                )
            if not self._click_template(f"volumes/{volume_name}", use_full_screen=True):
                return ClassificationResult(
                    success=False, track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"未找到卷「{volume_name}」",
                )
            if not self._template_lib.has_template(f"playlists/{playlist_name}"):
                return ClassificationResult(
                    success=False, track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"模板 templates/playlists/{playlist_name}.png 不存在，请先采集",
                )
            if not self._click_template(f"playlists/{playlist_name}", use_full_screen=True):
                return ClassificationResult(
                    success=False, track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"未找到歌单「{playlist_name}」",
                )

        # Step 5: Click ⋯ again + Delete (cleanup)
        if not self.click_dots_button(dots_pos):
            return ClassificationResult(
                success=False, track_name=track_name,
                target_playlist=playlist_name,
                message="三点按钮点击失败（删除前）",
            )
        try:
            pyautogui.press("delete")
            time.sleep(self._after_click_ms / 1000)
        except Exception:
            traceback.print_exc()
            return ClassificationResult(
                success=False, track_name=track_name,
                target_playlist=playlist_name,
                message="删除操作失败",
            )

        return ClassificationResult(
            success=True, track_name=track_name,
            target_playlist=playlist_name,
            message=f"已添加到歌单: {playlist_name}",
        )
