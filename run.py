# run.py — Booth Keeper 入口
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from main_window import BoothKeeper


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Booth Keeper")
    app.setStyle("Fusion")  # 跨平台一致基底，便于 QSS 接管
    win = BoothKeeper()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
