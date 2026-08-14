# render_r7plus_mismatch.py — R7+1 错位 dialog 出图
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase, QPixmap
from PySide6.QtCore import QEventLoop, QTimer
import theme
from pages.notify import ThemeDialog
import pages.notify as nm

app = QApplication([])
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf"):
    if os.path.exists(fp):
        fid = QFontDatabase.addApplicationFont(fp)
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        if fams: app.setFont(QFont(fams[0], 10)); break

# 离屏 grab() 不抓 opacity 动画，把 effect 改为瞬时 1.0
_orig_init = nm.ThemeDialog.__init__
def _patched_init(self, parent, title, body, kind="info", buttons=None, default=""):
    _orig_init(self, parent, title, body, kind, buttons, default)
    eff = self.graphicsEffect()
    if eff is not None: eff.setOpacity(1.0)
nm.ThemeDialog.__init__ = _patched_init

OUT = os.path.join(ROOT, "preview_build")

for tn in theme.THEME_NAMES:
    for mode in ("light", "dark"):
        app.setStyleSheet(theme.build_theme(tn, mode))
        nm.set_current_theme(tn, mode)
        loop = QEventLoop()
        d = ThemeDialog(None, "类目错位",
            "7032906 · 【10アバター対応】 𝐏♡𝐏.𝐇𝐚𝐢𝐫 𝟏𝟒 【VRChat用ヘアモデル】\n\n"
            "当前所在：3D模型\n"
            "官方分类：3D发型\n"
            "（类目可能错位，是否清掉旧目录并重新归档到「3D发型」？）\n\n"
            "（点取消则跳过该项）",
            kind="ask")
        d.resize(560, 320)
        d.show()
        QTimer.singleShot(180, loop.quit); loop.exec()
        pm = d.grab()
        path = os.path.join(OUT, f"r7plus_mismatch_{tn}_{mode}.png")
        pm.save(path); print(f"saved {path}")

print("DONE")