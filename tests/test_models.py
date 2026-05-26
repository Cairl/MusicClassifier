import pytest
from core.models import TrackInfo, ClassificationResult


class TestTrackInfo:
    def test_create_track_info(self):
        track = TrackInfo(
            song_name="Beta",
            artist="α·Pav",
            album="Pavonis ~ Piano Collection II ~",
            row_y=200,
            dots_btn_pos=(1500, 200),
        )
        assert track.song_name == "Beta"
        assert track.artist == "α·Pav"
        assert track.album == "Pavonis ~ Piano Collection II ~"
        assert track.row_y == 200
        assert track.dots_btn_pos == (1500, 200)

    def test_track_info_display_text(self):
        track = TrackInfo(
            song_name="Beta",
            artist="α·Pav",
            album="Pavonis ~ Piano Collection II ~",
            row_y=200,
            dots_btn_pos=(1500, 200),
        )
        assert track.display_text() == "Beta — α·Pav"

    def test_track_info_display_text_no_artist(self):
        track = TrackInfo(
            song_name="Beta",
            artist="",
            album="Album",
            row_y=200,
            dots_btn_pos=(1500, 200),
        )
        assert track.display_text() == "Beta"


class TestClassificationResult:
    def test_success_result(self):
        result = ClassificationResult(
            success=True,
            track_name="Beta",
            target_playlist="新月",
            message="已分类到: 月之卷 > 新月",
        )
        assert result.success is True
        assert result.track_name == "Beta"

    def test_failure_result(self):
        result = ClassificationResult(
            success=False,
            track_name="Beta",
            target_playlist="",
            message="三点按钮定位失败",
        )
        assert result.success is False
