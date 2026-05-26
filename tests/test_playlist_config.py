import json
import tempfile
import pytest
from core.playlist_config import PlaylistConfig


class TestPlaylistConfig:
    def test_load_default_config(self):
        config = PlaylistConfig()
        volumes = config.get_volumes()
        assert len(volumes) == 5
        assert "风之卷" in volumes

    def test_get_moods_for_volume(self):
        config = PlaylistConfig()
        moods = config.get_moods("月之卷")
        assert "新月 (CALM)" in moods
        assert "满月 (VIGOROUS)" in moods

    def test_get_moods_invalid_volume(self):
        config = PlaylistConfig()
        moods = config.get_moods("不存在")
        assert moods == []

    def test_get_playlist_name(self):
        config = PlaylistConfig()
        name = config.get_playlist_name("月之卷", "新月 (CALM)")
        assert name == "新月"

    def test_load_from_file(self):
        data = {
            "volumes": [
                {
                    "name": "测试卷",
                    "moods": [
                        {"name": "测试情绪", "tag": "TEST", "playlist": "测试歌单"}
                    ]
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            path = f.name
        config = PlaylistConfig(path)
        assert config.get_volumes() == ["测试卷"]
        assert config.get_moods("测试卷") == ["测试情绪 (TEST)"]
