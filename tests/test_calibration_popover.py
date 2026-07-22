import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gui.calibration_popover import CalibrationPopover


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_popover_emits_correct_cell_coordinates():
    _app()
    pop = CalibrationPopover()
    received = []
    pop.corrected.connect(lambda v, a: received.append((v, a)))
    pop._emit_cell(0, 0)
    assert received == [(-2 / 3, 2 / 3)]
    pop._emit_cell(2, 2)
    assert received[-1] == (2 / 3, -2 / 3)


def test_popover_center_cell_is_zero():
    _app()
    pop = CalibrationPopover()
    received = []
    pop.corrected.connect(lambda v, a: received.append((v, a)))
    pop._emit_cell(1, 1)
    assert received == [(0.0, 0.0)]
