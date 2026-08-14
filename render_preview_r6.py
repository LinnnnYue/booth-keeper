# render_preview_r6.py — R6 出图 + 视觉校验
# 主题化弹窗（3 主题 × 2 模式）+ 修复后侧栏（完整 Booth Keeper）
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtGui import QPixmap, QColor, QFont, QFontDatabase
from PySide6.QtCore import QEventLoop, QTimer
import theme
from pages.notify import ThemeDialog
import main_window

OUT = os.path.join(ROOT, "preview_build")
os.makedirs(OUT, exist_ok=True)

app = QApplication([])
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf"):
    if os.path.exists(fp):
        fid = QFontDatabase.addApplicationFont(fp)
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        if fams: app.setFont(QFont(fams[0], 10)); break

# 离屏 grab() 不抓 opacity 动画，把 effect 改为瞬时 1.0
import pages.notify as nm
_orig_init = nm.ThemeDialog.__init__
def _patched_init(self, parent, title, body, kind="info", buttons=None, default=""):
    _orig_init(self, parent, title, body, kind, buttons, default)
    eff = self.graphicsEffect()
    if eff is not None:
        eff.setOpacity(1.0)
nm.ThemeDialog.__init__ = _patched_init

# render 脚本直接调 ThemeDialog 时绕开 main_window.apply_theme，需手动同步全局主题状态
import theme as _theme_mod
for _tn, _mode in [(tn, mode) for tn in _theme_mod.THEME_NAMES for mode in ("light", "dark")]:
    pass  # 下面循环里手动调


# ---------- 1. 主题化弹窗（三主题 × 2 模式） ----------
print("[1] 主题化弹窗出图")
for tn in theme.THEME_NAMES:
    for mode in ("light", "dark"):
        app.setStyleSheet(theme.build_theme(tn, mode))
        nm.set_current_theme(tn, mode)  # 同步 ThemeDialog 全局状态
        loop = QEventLoop()
        d = ThemeDialog(None, "提示",
            "未从文本中识别到 booth.pm/items/ 形式的七位 ID 链接。\n\n"
            "示例：\n"
            "  https://booth.pm/zh-cn/items/3290806\n"
            "  booth.pm/items/3290806\n"
            "  3290806（裸 7 位 ID）",
            kind="info")
        d.resize(520, 260)
        d.show()
        QTimer.singleShot(150, loop.quit); loop.exec()
        pm = d.grab()
        path = os.path.join(OUT, f"r6_dlg_{tn}_{mode}.png")
        pm.save(path); print(f"  saved {path}")

# 主题化 confirmation
print("\n[2] 主题化 confirmation 弹窗")
for tn in theme.THEME_NAMES:
    for mode in ("light", "dark"):
        app.setStyleSheet(theme.build_theme(tn, mode))
        nm.set_current_theme(tn, mode)
        loop = QEventLoop()
        d = ThemeDialog(None, "已归档",
            "7032906 · 【10アバター対応】 𝐏♡𝐏.𝐇𝐚𝐢𝐫 𝟏𝟒\n"
            "已在「发型」类别下。\n"
            "是否清掉旧目录并重新归档到当前分类？\n\n"
            "（点取消则跳过该项）",
            kind="ask")
        d.resize(540, 280)
        d.show()
        QTimer.singleShot(180, loop.quit); loop.exec()
        pm = d.grab()
        path = os.path.join(OUT, f"r6_dlg_confirm_{tn}_{mode}.png")
        pm.save(path); print(f"  saved {path}")

# ---------- 3. 修复后侧栏（Booth Keeper 完整显字） ----------
print("\n[3] 修复后侧栏整图")
mw = main_window.BoothKeeper()
mw.resize(1120, 320)
mw.show()
loop = QEventLoop()
QTimer.singleShot(120, loop.quit); loop.exec()
for tn in theme.THEME_NAMES:
    mw.config["theme"] = tn
    mw.config["mode"] = "light"
    mw.apply_theme()
    QTimer.singleShot(120, loop.quit); loop.exec()
    pm = QPixmap(mw.size()); pm.fill(QColor(0, 0, 0, 0))
    mw.render(pm)
    path = os.path.join(OUT, f"r6_sidebar_{tn}_light.png")
    pm.save(path); print(f"  saved {path}")

# 暗主题侧栏
for tn in theme.THEME_NAMES:
    mw.config["theme"] = tn
    mw.config["mode"] = "dark"
    mw.apply_theme()
    QTimer.singleShot(120, loop.quit); loop.exec()
    pm = QPixmap(mw.size()); pm.fill(QColor(0, 0, 0, 0))
    mw.render(pm)
    path = os.path.join(OUT, f"r6_sidebar_{tn}_dark.png")
    pm.save(path); print(f"  saved {path}")

# ---------- 4. 完整 links / drag / search / audit 页（三主题明） ----------
print("\n[4] 整窗 4 页（zhuyin/light）")
mw.config["theme"] = "zhuyin"
mw.config["mode"] = "light"
mw.apply_theme()
QTimer.singleShot(120, loop.quit); loop.exec()
mw.resize(1120, 720)
for pg in ("links", "drag", "search", "audit"):
    mw.switch_page(pg)
    QTimer.singleShot(120, loop.quit); loop.exec()
    pm = QPixmap(mw.size()); pm.fill(QColor(0, 0, 0, 0))
    mw.render(pm)
    path = os.path.join(OUT, f"r6_full_{pg}_zhuyin_light.png")
    pm.save(path); print(f"  saved {path}")

print("\nDONE")
