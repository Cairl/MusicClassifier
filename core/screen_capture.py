import time
import pygetwindow
import pyautogui
import numpy as np
from PIL import Image


class ScreenCapture:
    def __init__(self, window_title: str, list_region_ratio: tuple | None = None):
        self._window_title = window_title
        self._list_region_ratio = list_region_ratio or (0.10, 0.30, 0.98, 0.88)
        self._window_rect: tuple | None = None

    def find_window(self) -> tuple | None:
        windows = pygetwindow.getWindowsWithTitle(self._window_title)
        if not windows:
            return None
        win = windows[0]
        self._window_rect = (win.left, win.top, win.left + win.width, win.top + win.height)
        return self._window_rect

    def activate_window(self) -> bool:
        windows = pygetwindow.getWindowsWithTitle(self._window_title)
        if not windows:
            return False
        win = windows[0]
        try:
            win.activate()
            time.sleep(0.5)
        except Exception:
            try:
                win.minimize()
                time.sleep(0.2)
                win.restore()
                time.sleep(0.5)
            except Exception:
                return False
        self._window_rect = (win.left, win.top, win.left + win.width, win.top + win.height)
        return True

    def capture_list_region(self, delay_ms: int = 300) -> np.ndarray | None:
        if not self._window_rect:
            rect = self.find_window()
            if not rect:
                return None
        time.sleep(delay_ms / 1000)
        left, top, right, bottom = self._window_rect
        w = right - left
        h = bottom - top
        rl, rt, rr, rb = self._list_region_ratio
        region_left = int(left + w * rl)
        region_top = int(top + h * rt)
        region_right = int(left + w * rr)
        region_bottom = int(top + h * rb)
        # pyautogui.screenshot region = (left, top, width, height)
        screenshot = pyautogui.screenshot(
            region=(region_left, region_top,
                    region_right - region_left, region_bottom - region_top))
        return np.array(screenshot)

    def capture_full_window(self, delay_ms: int = 300) -> np.ndarray | None:
        if not self._window_rect:
            rect = self.find_window()
            if not rect:
                return None
        time.sleep(delay_ms / 1000)
        left, top, right, bottom = self._window_rect
        screenshot = pyautogui.screenshot(region=(left, top, right - left, bottom - top))
        return np.array(screenshot)

    def get_window_rect(self) -> tuple | None:
        """Return current window rect (left, top, right, bottom) or None."""
        return self._window_rect

    def capture_full_screen(self, delay_ms: int = 3000) -> np.ndarray | None:
        time.sleep(delay_ms / 1000)
        screenshot = pyautogui.screenshot()
        return np.array(screenshot)
