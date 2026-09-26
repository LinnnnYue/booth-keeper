# verify_offscreen.py — 无显示环境下的构造验证（开发用，可删除）
import os
import sys

ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
sys.path.insert(0, ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
import theme
from main_window import BoothKeeper

app = QApplication([])
app.setStyle("Fusion")
win = BoothKeeper()

for key in ["links", "drag", "search", "audit", "settings"]:
    win.switch_page(key)

for mode in ["light", "dark"]:
    win.config["mode"] = mode
    win.apply_theme()

for acc in list(theme.ACCENTS.keys()):
    win.config["accent"] = acc
    win.apply_theme()

print("CONSTRUCT OK accent=teal pages:", list(win.pages.keys()))
print("OK")
