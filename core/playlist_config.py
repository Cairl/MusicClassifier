import json
from pathlib import Path


class PlaylistConfig:
    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

    def __init__(self, config_path: str | None = None):
        self._config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        self._data = self._load()

    def _load(self) -> dict:
        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"volumes": [], "action_delays": {}, "apple_music_window_title": "Apple Music"}

    def get_volumes(self) -> list[str]:
        return [v["name"] for v in self._data.get("volumes", [])]

    def get_moods(self, volume_name: str) -> list[str]:
        for v in self._data.get("volumes", []):
            if v["name"] == volume_name:
                return [f"{m['name']} ({m['tag']})" for m in v["moods"]]
        return []

    def get_playlist_name(self, volume_name: str, mood_display: str) -> str:
        mood_name = mood_display.split(" (")[0] if " (" in mood_display else mood_display
        for v in self._data.get("volumes", []):
            if v["name"] == volume_name:
                for m in v["moods"]:
                    if m["name"] == mood_name:
                        return m["playlist"]
        return mood_name

    def get_all_playlists(self) -> list[str]:
        result = []
        for v in self._data.get("volumes", []):
            for m in v.get("moods", []):
                display = f"{v['name']} > {m['name']} ({m['tag']})"
                result.append(display)
        return result

    def get_playlist_name_from_display(self, display: str) -> str:
        parts = display.split(" > ")
        if len(parts) != 2:
            return display
        volume_name = parts[0]
        mood_part = parts[1]
        mood_name = mood_part.split(" (")[0] if " (" in mood_part else mood_part
        for v in self._data.get("volumes", []):
            if v["name"] == volume_name:
                for m in v["moods"]:
                    if m["name"] == mood_name:
                        return m["playlist"]
        return mood_name

    @property
    def after_click_ms(self) -> int:
        return self._data.get("action_delays", {}).get("after_click_ms", 700)

    @property
    def before_screenshot_ms(self) -> int:
        return self._data.get("action_delays", {}).get("before_screenshot_ms", 300)

    @property
    def menu_appear_ms(self) -> int:
        return self._data.get("action_delays", {}).get("menu_appear_ms", 500)

    @property
    def window_title(self) -> str:
        return self._data.get("apple_music_window_title", "Apple Music")
