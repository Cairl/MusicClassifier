import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from core.playlist_config import PlaylistConfig


def main():
    app = QApplication(sys.argv)
    config = PlaylistConfig()
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
