import pytest
from PySide6.QtWidgets import QApplication

from gui.quadrant_chart import QuadrantChart


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class TestQuadrantChart:
    def test_initial_state(self, app):
        chart = QuadrantChart()
        assert chart._arousal == 0.0
        assert chart._valence == 0.0
        assert chart._quadrant == ""
        assert chart._confidence == 0.0
        assert chart._dot_visible is False

    def test_update_mood_sets_values(self, app):
        chart = QuadrantChart()
        chart.update_mood(0.5, -0.3, "TENSE", 0.7)
        assert chart._arousal == 0.5
        assert chart._valence == -0.3
        assert chart._quadrant == "TENSE"
        assert chart._confidence == 0.7
        assert chart._dot_visible is True

    def test_reset_clears_state(self, app):
        chart = QuadrantChart()
        chart.update_mood(0.5, -0.3, "TENSE", 0.7)
        chart.reset()
        assert chart._arousal == 0.0
        assert chart._valence == 0.0
        assert chart._quadrant == ""
        assert chart._confidence == 0.0
        assert chart._dot_visible is False

    def test_dot_position_vigorous(self, app):
        chart = QuadrantChart()
        chart.resize(200, 160)
        chart.update_mood(0.8, 0.6, "VIGOROUS", 0.8)
        x, y = chart._dot_pixel_pos()
        w, h = chart.width(), chart.height()
        assert x > w / 2
        assert y < h / 2

    def test_dot_position_melancholy(self, app):
        chart = QuadrantChart()
        chart.resize(200, 160)
        chart.update_mood(-0.8, -0.6, "MELANCHOLY", 0.8)
        x, y = chart._dot_pixel_pos()
        w, h = chart.width(), chart.height()
        assert x < w / 2
        assert y > h / 2

    def test_recommended_quadrant_property(self, app):
        chart = QuadrantChart()
        chart.update_mood(0.5, 0.5, "VIGOROUS", 0.8)
        assert chart.recommended_quadrant == "VIGOROUS"

    def test_no_recommendation_when_low_confidence(self, app):
        chart = QuadrantChart()
        chart.update_mood(0.5, 0.5, "VIGOROUS", 0.3)
        assert chart.recommended_quadrant is None
