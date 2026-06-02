import json
import cv2
import numpy as np
import re
import traceback
from pathlib import Path
from PIL import Image
from core.models import MatchResult
from core.playlist_config import PlaylistConfig


class TemplateLibrary:
    def __init__(self, templates_dir: Path, threshold: float = 0.8):
        self._templates_dir = Path(templates_dir)
        self._threshold = threshold
        self._coords_path = self._templates_dir / "coords.json"

    _VALID_NAME_RE = re.compile(r"^[\w\-/]+$")

    def _template_path(self, name: str) -> Path | None:
        if not self._VALID_NAME_RE.match(name):
            return None
        return self._templates_dir / f"{name}.png"

    # ── Coordinate cache (for fixed-position UI elements) ────────

    def _load_coords(self) -> dict:
        if self._coords_path.exists():
            try:
                return json.loads(self._coords_path.read_text(encoding='utf-8'))
            except Exception:
                return {}
        return {}

    def _save_coords(self, data: dict) -> None:
        self._coords_path.parent.mkdir(parents=True, exist_ok=True)
        self._coords_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def save_region(self, name: str, x: int, y: int, w: int, h: int,
                    window_offset: tuple[int, int]) -> None:
        """Save the region position of a template relative to the window.
        This allows click automation to use cached coordinates instead of
        re-running template matching for fixed-position elements."""
        data = self._load_coords()
        data[name] = {
            "x": x - window_offset[0],
            "y": y - window_offset[1],
            "w": w,
            "h": h,
        }
        self._save_coords(data)

    def get_cached_region(self, name: str) -> dict | None:
        """Return cached region {x, y, w, h} (window-relative) or None."""
        data = self._load_coords()
        return data.get(name)

    def delete_coords(self, name: str) -> None:
        data = self._load_coords()
        data.pop(name, None)
        self._save_coords(data)

    # ── Template image operations ────────────────────────────────

    def find_template(self, screenshot: np.ndarray, name: str) -> MatchResult | None:
        path = self._template_path(name)
        if path is None or not path.exists():
            return None
        # Read template as RGB (PIL), keep in RGB
        template_pil = Image.open(str(path))
        template = np.array(template_pil)
        if template is None or template.size == 0:
            return None
        if screenshot.shape[:2] < template.shape[:2]:
            return None
        # cv2.matchTemplate works in any color space as long as both match
        # Both are RGB → RGB comparison is correct
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

    def find_fixed_position(self, name: str,
                            window_offset: tuple[int, int]) -> tuple[int, int] | None:
        """Use cached region to get screen-absolute click position
        without template matching. Falls back to template matching if
        no cached position exists."""
        region = self.get_cached_region(name)
        if region is None:
            return None
        cx = region["x"] + region["w"] // 2 + window_offset[0]
        cy = region["y"] + region["h"] // 2 + window_offset[1]
        return (cx, cy)

    def has_template(self, name: str) -> bool:
        path = self._template_path(name)
        return path is not None and path.exists()

    def save_template(self, name: str, image: np.ndarray) -> None:
        path = self._template_path(name)
        if path is None:
            raise ValueError(f"无效的模板名称: {name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Use PIL to save RGB image directly — no BGR conversion needed
        Image.fromarray(image).save(str(path))

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

    def list_all_names(self) -> list[str]:
        names: list[str] = []
        for category, items in self.list_templates().items():
            for item in items:
                names.append(f"{category}/{item}")
        return names

    def get_missing_templates(self, config: PlaylistConfig) -> list[str]:
        required = ["ui/add_to_playlist", "ui/more_button"]
        for vol_name in config.get_volumes():
            required.append(f"volumes/{vol_name}")
        for mood in config.get_all_moods_flat():
            required.append(f"playlists/{mood['playlist']}")
        return [name for name in required if not self.has_template(name)]

    def delete_template(self, name: str) -> None:
        path = self._template_path(name)
        if path is not None and path.exists():
            path.unlink()
        self.delete_coords(name)
