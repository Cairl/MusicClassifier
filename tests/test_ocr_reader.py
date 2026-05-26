import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from core.ocr_reader import OCRReader
from core.models import TrackInfo


class TestOCRReader:
    def test_init(self):
        reader = OCRReader()
        assert reader._ocr is None

    def test_parse_ocr_results_to_tracks(self):
        reader = OCRReader()
        ocr_results = [
            [[10, 200, 300, 230], ("Beta", 0.98)],
            [[10, 260, 300, 290], ("α·Pav", 0.95)],
            [[10, 320, 300, 350], ("Everything Is Quiet Now", 0.97)],
            [[10, 380, 300, 410], ("Elijah Who", 0.93)],
        ]
        tracks = reader._parse_to_tracks(ocr_results, img_width=800, window_offset=(300, 100))
        assert len(tracks) >= 1
        if tracks:
            assert tracks[0].song_name == "Beta"

    def test_empty_ocr_results(self):
        reader = OCRReader()
        tracks = reader._parse_to_tracks([], img_width=800, window_offset=(0, 0))
        assert tracks == []

    def test_find_dots_button_position(self):
        reader = OCRReader()
        pos = reader._estimate_dots_pos(row_y=200, img_width=800, window_offset=(300, 100))
        assert pos[0] > 300
        assert pos[1] == 200 + 100 + 30
