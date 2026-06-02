#! python3.12
import os
import sys
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))


def main():
    # Qt manages DPI awareness automatically
    
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont
    except Exception as e:
        print(f"[FATAL] 导入 PySide6 失败: {e}", file=sys.stderr, flush=True)
        input("启动失败，按回车退出...")
        return

    try:
        from gui.main_window import MainWindow
        from core.playlist_config import PlaylistConfig
    except Exception as e:
        print(f"[FATAL] 导入模块失败: {e}", file=sys.stderr, flush=True)
        traceback.print_exc()
        input("启动失败，按回车退出...")
        return

    app = QApplication(sys.argv)
    font = QFont("Microsoft JhengHei", 9)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    try:
        config = PlaylistConfig()
        window = MainWindow(config)
        window.show()
    except Exception as e:
        print(f"[FATAL] 启动异常: {e}", file=sys.stderr, flush=True)
        traceback.print_exc()
        input("启动失败，按回车退出...")
        return
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("程序异常退出，按回车关闭...")
