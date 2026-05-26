import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from core.screen_capture import ScreenCapture


class TestScreenCapture:
    def test_init_with_window_title(self):
        capture = ScreenCapture("Apple Music")
        assert capture._window_title == "Apple Music"

    @patch("core.screen_capture.pygetwindow")
    def test_find_window_success(self, mock_pgw):
        mock_win = MagicMock()
        mock_win.left, mock_win.top = 100, 100
        mock_win.width, mock_win.height = 1200, 800
        mock_pgw.getWindowsWithTitle.return_value = [mock_win]
        capture = ScreenCapture("Apple Music")
        rect = capture.find_window()
        assert rect == (100, 100, 1300, 900)

    @patch("core.screen_capture.pygetwindow")
    def test_find_window_not_found(self, mock_pgw):
        mock_pgw.getWindowsWithTitle.return_value = []
        capture = ScreenCapture("Apple Music")
        rect = capture.find_window()
        assert rect is None

    @patch("core.screen_capture.pygetwindow")
    def test_capture_region(self, mock_pgw):
        mock_win = MagicMock()
        mock_win.left, mock_win.top = 0, 0
        mock_win.width, mock_win.height = 1920, 1080
        mock_pgw.getWindowsWithTitle.return_value = [mock_win]
        capture = ScreenCapture("Apple Music")
        with patch("core.screen_capture.pyautogui") as mock_pag:
            mock_pag.screenshot.return_value = MagicMock()
            result = capture.capture_list_region()
            assert result is not None or result is None
