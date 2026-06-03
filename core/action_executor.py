import time
import traceback
import sys
import numpy as np
import pyautogui
from core.models import ClassificationResult
from core.screen_capture import ScreenCapture
from core.template_library import TemplateLibrary


def _log(msg: str):
    print(f"[CLICK] {msg}", file=sys.stderr, flush=True)


class ActionExecutor:
    def __init__(self, screen_capture: ScreenCapture, template_library: TemplateLibrary,
                 after_click_ms: int = 1000, menu_appear_ms: int = 1000):
        self._screen_capture = screen_capture
        self._template_lib = template_library
        self._after_click_ms = after_click_ms
        self._menu_appear_ms = menu_appear_ms

    def _highlight(self, x: int, y: int, label: str = ""):
        try:
            import threading
            if threading.current_thread() is not threading.main_thread():
                return
            from gui.highlight_overlay import HighlightOverlay
            dlg = HighlightOverlay(x, y, 36, 36, label, 300)
            dlg.exec()
        except Exception:
            pass

    # ── Two click modes ────────────────────────────────────────

    def _quick_click(self, template_name: str, use_full_screen: bool = True) -> bool:
        """Wait 500ms fixed, then screenshot + find + click. For fixed-animation menus."""
        _log(f"_quick_click('{template_name}')")
        time.sleep(0.5)
        if use_full_screen:
            screen = self._screen_capture.capture_full_screen(delay_ms=0)
            offset = (0, 0)
        else:
            screen = self._screen_capture.capture_full_window(delay_ms=0)
            if screen is None:
                return False
            offset = self._screen_capture._window_rect[:2] \
                if self._screen_capture._window_rect else (0, 0)
        if screen is None:
            return False
        match = self._template_lib.find_template(screen, template_name)
        if match is None:
            _log(f"  ✗ '{template_name}' not found after 500ms")
            return False
        sx = match.position[0] + offset[0]
        sy = match.position[1] + offset[1]
        _log(f"  found at ({sx},{sy}) conf={match.confidence:.2f}")
        self._highlight(sx, sy, template_name.split("/")[-1])
        pyautogui.click(sx, sy)
        _log(f"  clicked")
        return True

    def _poll_click(self, template_name: str, use_full_screen: bool = True) -> bool:
        """Poll screen until template appears (up to 4s), then click. For variable menus."""
        _log(f"_poll_click('{template_name}')")
        deadline = time.time() + 4.0
        while time.time() < deadline:
            if use_full_screen:
                screen = self._screen_capture.capture_full_screen(delay_ms=0)
                offset = (0, 0)
            else:
                screen = self._screen_capture.capture_full_window(delay_ms=0)
                if screen is None:
                    time.sleep(0.1)
                    continue
                offset = self._screen_capture._window_rect[:2] \
                    if self._screen_capture._window_rect else (0, 0)
            if screen is None:
                time.sleep(0.1)
                continue
            match = self._template_lib.find_template(screen, template_name)
            if match is not None:
                sx = match.position[0] + offset[0]
                sy = match.position[1] + offset[1]
                _log(f"  found at ({sx},{sy}) conf={match.confidence:.2f}")
                self._highlight(sx, sy, template_name.split("/")[-1])
                pyautogui.click(sx, sy)
                _log(f"  clicked")
                return True
            time.sleep(0.1)
        _log(f"  ✗ '{template_name}' not found within 4s")
        return False

    # ── Dots button ─────────────────────────────────────────────

    def click_dots_button(self, dots_pos: tuple[int, int] | None = None) -> bool:
        _log(f"click_dots_button() called, dots_pos={dots_pos}")
        try:
            offset = self._screen_capture._window_rect[:2] \
                if self._screen_capture._window_rect else (0, 0)
            region = self._template_lib.get_cached_region("position/more_button")
            if region is not None:
                cx = region["x"] + region["w"] // 2 + offset[0]
                cy = region["y"] + region["h"] // 2 + offset[1]
                _log(f"  clicking region center: ({cx}, {cy})")
                self._highlight(cx, cy, "⋯")
                pyautogui.click(cx, cy)
                time.sleep(0.5)
                return True
            elif dots_pos is not None:
                _log(f"  no region, fallback to OCR position {dots_pos}")
                self._highlight(dots_pos[0], dots_pos[1], "⋯")
                pyautogui.click(dots_pos[0], dots_pos[1])
                time.sleep(0.5)
                return True
            _log("  FAILED: no region and no OCR position")
            return False
        except Exception:
            traceback.print_exc()
            return False

    def _stable_click(self, template_name: str, max_wait: float = 6.0) -> bool:
        _log(f"_stable_click('{template_name}')")
        deadline = time.time() + max_wait
        while time.time() < deadline:
            screen = self._screen_capture.capture_full_screen(delay_ms=0)
            if screen is None:
                time.sleep(0.1)
                continue
            match = self._template_lib.find_template(screen, template_name)
            if match is None:
                time.sleep(0.1)
                continue

            time.sleep(0.05)
            screen2 = self._screen_capture.capture_full_screen(delay_ms=0)
            if screen2 is None:
                time.sleep(0.1)
                continue
            if screen2.shape != screen.shape or not np.array_equal(screen, screen2):
                _log(f"  screen shifted, re-checking...")
                continue

            sx, sy = match.position
            _log(f"  stable at ({sx},{sy}) conf={match.confidence:.2f}")
            self._highlight(sx, sy, template_name.split("/")[-1])
            pyautogui.click(sx, sy)
            _log(f"  clicked")
            return True

        _log(f"  ✗ '{template_name}' not found or screen never stable within {max_wait}s")
        return False

    # ── Classification ──────────────────────────────────────────

    def classify_track(self, dots_pos: tuple[int, int],
                       playlist_name: str, volume_name: str,
                       track_name: str) -> ClassificationResult:
        _log(f"=== classify_track ===")
        _log(f"  track='{track_name}'  playlist='{playlist_name}'  volume='{volume_name}'")
        _log(f"  dots_pos={dots_pos}")

        # Remember original mouse position before any clicks
        saved_mouse = pyautogui.position()
        _log(f"  original mouse at ({saved_mouse.x}, {saved_mouse.y})")

        # Step 1: Click ⋯
        _log("[Step 1/5] Click ⋯ button")
        if not self.click_dots_button(dots_pos):
            return ClassificationResult(
                success=False, track_name=track_name,
                target_playlist=playlist_name,
                message="三点按钮点击失败",
            )
        _log("  ✓ ⋯ clicked")

        # Step 2: Wait for screen to stabilize, then click "添加到播放列表"
        _log("[Step 2/5] Stable-click '添加到播放列表'")
        if not self._template_lib.has_template("ui/add_to_playlist"):
            _log("  ✗ template ui/add_to_playlist.png missing")
            return ClassificationResult(
                success=False, track_name=track_name,
                target_playlist=playlist_name,
                message="模板 templates/ui/add_to_playlist.png 不存在，请先采集",
            )
        if not self._stable_click("ui/add_to_playlist"):
            _log("  ✗ '添加到播放列表' not found or screen unstable")
            return ClassificationResult(
                success=False, track_name=track_name,
                target_playlist=playlist_name,
                message="未找到「添加到播放列表」按钮或画面未稳定",
            )
        _log("  ✓ '添加到播放列表' clicked")

        # Step 3: Try direct playlist (fixed 500ms)
        _log(f"[Step 3/5] Try direct playlist '{playlist_name}'")
        playlist_found = False
        has_playlist_template = self._template_lib.has_template(f"playlists/{playlist_name}")
        _log(f"  has template = {has_playlist_template}")
        if has_playlist_template:
            if self._quick_click(f"playlists/{playlist_name}", use_full_screen=True):
                playlist_found = True
                _log(f"  ✓ playlist '{playlist_name}' found directly")

        # Step 4: If not found, click volume then playlist (both fixed 500ms)
        if not playlist_found:
            _log(f"[Step 4/5] Click volume '{volume_name}', then playlist")
            if not self._template_lib.has_template(f"volumes/{volume_name}"):
                _log(f"  ✗ template volumes/{volume_name}.png missing")
                return ClassificationResult(
                    success=False, track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"模板 templates/volumes/{volume_name}.png 不存在，请先采集",
                )
            if not self._quick_click(f"volumes/{volume_name}", use_full_screen=True):
                _log(f"  ✗ volume '{volume_name}' not found")
                return ClassificationResult(
                    success=False, track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"未找到卷「{volume_name}」",
                )
            _log(f"  ✓ volume clicked, now finding playlist")
            if not self._template_lib.has_template(f"playlists/{playlist_name}"):
                _log(f"  ✗ template playlists/{playlist_name}.png missing")
                return ClassificationResult(
                    success=False, track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"模板 templates/playlists/{playlist_name}.png 不存在，请先采集",
                )
            if not self._quick_click(f"playlists/{playlist_name}", use_full_screen=True):
                _log(f"  ✗ playlist '{playlist_name}' not found")
                return ClassificationResult(
                    success=False, track_name=track_name,
                    target_playlist=playlist_name,
                    message=f"未找到歌单「{playlist_name}」",
                )
            _log(f"  ✓ playlist clicked via volume")

        # Step 5: Cleanup — toggle menu off
        _log("[Step 5/5] Click ⋯ + Delete (cleanup)")
        if not self.click_dots_button(dots_pos):
            _log("  ✗ second ⋯ click failed (cleanup)")
            return ClassificationResult(
                success=False, track_name=track_name,
                target_playlist=playlist_name,
                message="三点按钮点击失败（删除前）",
            )
        try:
            pyautogui.press("delete")
            time.sleep(0.3)
            _log("  ✓ delete pressed")
        except Exception:
            traceback.print_exc()
            return ClassificationResult(
                success=False, track_name=track_name,
                target_playlist=playlist_name,
                message="删除操作失败",
            )

        # Restore mouse to original position
        pyautogui.moveTo(saved_mouse.x, saved_mouse.y)
        _log(f"  mouse restored to ({saved_mouse.x}, {saved_mouse.y})")

        _log(f"=== classify_track SUCCESS ===")
        return ClassificationResult(
            success=True, track_name=track_name,
            target_playlist=playlist_name,
            message=f"已添加到歌单: {playlist_name}",
        )
