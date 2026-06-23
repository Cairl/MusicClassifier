"""Render MainWindow with mocked services to verify layout fits 240x360.

Writes a screenshot to layout_check.png. Does NOT require PaddleOCR/audio.
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    app = QApplication.instance() or QApplication(sys.argv)

    # Mock heavy services before constructing MainWindow
    with patch("core.screen_capture.ScreenCapture") as MockSC, \
         patch("core.ocr_reader.OCRReader") as MockOCR, \
         patch("core.template_library.TemplateLibrary") as MockTL, \
         patch("core.action_executor.ActionExecutor") as MockAE, \
         patch("core.audio_capture.AudioCaptureManager") as MockAC, \
         patch("core.audio_analyzer.AudioAnalyzer") as MockAA, \
         patch("core.music2emo_client.Music2EmoClient") as MockM2E, \
         patch("process_audio_capture.ProcessAudioCapture") as MockPAC:

        MockPAC.is_supported = MagicMock(return_value=True)

        from core.playlist_config import PlaylistConfig
        from gui.main_window import MainWindow

        cfg = PlaylistConfig(ROOT / "config.json")
        win = MainWindow(cfg)

        # Inject a fake track for visualization
        from core.models import TrackInfo
        fake = TrackInfo(
            song_name="测试歌曲名 - 较长内容验证 ellipsis",
            artist="歌手名",
            album="专辑名",
            row_y=0,
            dots_btn_pos=(0, 0),
        )
        win._handle_track_detected(fake)
        # Simulate mood analyzed
        win._quadrant_chart.update_mood(0.6, 0.5, "VIGOROUS", 0.85)
        win._playlist_grid.highlight_quadrant("VIGOROUS")
        win._set_status("活力", "#e65100", "#fff3e0", 600)

        win.show()
        win.resize(360, 520)

        def dump():
            pix = win.grab()
            out = ROOT / "layout_check.png"
            pix.save(str(out))
            print(f"[OK] saved {out}  size={pix.size().width()}x{pix.size().height()}")
            from PySide6.QtWidgets import QWidget
            for child in win.findChildren(QWidget):
                r = child.geometry()
                if r.width() > 0 and r.height() > 0:
                    print(f"  {child.__class__.__name__:20s} "
                          f"obj={child.objectName() or '-':20s} "
                          f"geom={r.x()},{r.y()},{r.width()},{r.height()} "
                          f"visible={child.isVisible()}")
            qc = win._quadrant_chart
            print(f"\n  [QuadrantChart] _chart_rect={qc._chart_rect()}  "
                  f"width={qc.width()} height={qc.height()}")

        QTimer.singleShot(300, dump)
        app.exec()


if __name__ == "__main__":
    main()
