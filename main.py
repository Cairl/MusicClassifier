#! python3.12
import os
import sys
import ctypes
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except Exception:
        traceback.print_exc()
        input("启动失败，按回车退出...")
        return

    try:
        from gui.main_window import MainWindow
        from core.playlist_config import PlaylistConfig
    except Exception:
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "启动失败", traceback.format_exc())
        return

    app = QApplication(sys.argv)
    try:
        config = PlaylistConfig()
        window = MainWindow(config)
        window.show()
    except Exception:
        QMessageBox.critical(None, "启动失败", traceback.format_exc())
        return
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("程序异常退出，按回车关闭...")
