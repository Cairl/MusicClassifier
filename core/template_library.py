import cv2
import numpy as np
import re
import traceback
from pathlib import Path
from core.models import MatchResult
from core.playlist_config import PlaylistConfig


class TemplateLibrary:
    def __init__(self, templates_dir: Path, threshold: float = 0.8):
        self._templates_dir = Path(templates_dir)
        self._threshold = threshold

    _VALID_NAME_RE = re.compile(r"^[\w\-/]+$")

    def _template_path(self, name: str) -> Path | None:
        if not self._VALID_NAME_RE.match(name):
            return None
        return self._templates_dir / f"{name}.png"

    def find_template(self, screenshot: np.ndarray, name: str) -> MatchResult | None:
        path = self._template_path(name)
        if path is None or not path.exists():
            return None
        template = cv2.imread(str(path))
        if template is None:
            return None
        if screenshot.shape[:2] < template.shape[:2]:
            return None
        try:
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        except Exception:
            traceback.print_exc()
            return None
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < self._threshold:
            return None
        th, tw = template.shape[:2]
        center_x = max_loc[0] + tw // 2
        center_y = max_loc[1] + th // 2
        return MatchResult(position=(center_x, center_y), confidence=max_val)

    def has_template(self, name: str) -> bool:
        path = self._template_path(name)
        return path is not None and path.exists()

    def save_template(self, name: str, image: np.ndarray) -> None:
        path = self._template_path(name)
        if path is None:
            raise ValueError(f"\u65e0\u6548\u7684\u6a21\u677f\u540d\u79f0: {name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), image)

    def list_templates(self) -> dict[str, list[str]]:
        if not self._templates_dir.exists():
            return {}
        result: dict[str, list[str]] = {}
        for category_dir in sorted(self._templates_dir.iterdir()):
            if category_dir.is_dir():
                names = [p.stem for p in sorted(category_dir.glob("*.png"))]
                if names:
                    result[category_dir.name] = names
        return result

    def get_missing_templates(self, config: PlaylistConfig) -> list[str]:
        required = ["ui/add_to_playlist"]
        for vol_name in config.get_volumes():
            required.append(f"volumes/{vol_name}")
        for mood in config.get_all_moods_flat():
            required.append(f"playlists/{mood['playlist']}")
        return [name for name in required if not self.has_template(name)]

    def delete_template(self, name: str) -> None:
        path = self._template_path(name)
        if path is not None and path.exists():
            path.unlink()
