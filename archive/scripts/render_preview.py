# render_preview.py — 离屏整窗抓图，生成各主题各页真实预览 PNG（佐证重铸落地）
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QColor, QFont, QFontDatabase
from PySide6.QtCore import QEventLoop, QTimer
import main_window
import theme

OUT = os.path.join(ROOT, "preview_build")
os.makedirs(OUT, exist_ok=True)

app = QApplication([])
# 离屏 QPA 默认无 CJK 字体：手动加载系统 msyh.ttc（Microsoft YaHei）
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf", r"C:\Windows\Fonts\simhei.ttf"):
    if os.path.exists(fp):
        fid = QFontDatabase.addApplicationFont(fp)
        fams_added = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        if fams_added:
            app.setFont(QFont(fams_added[0], 10))
            print("CJK font loaded:", fp, "->", fams_added[0])
            break
mw = main_window.BoothKeeper()
mw.resize(1120, 720)
mw.show()
loop = QEventLoop()

pages = ["links", "drag", "search", "audit", "settings"]

for tn in theme.THEME_NAMES:
    mw.config["theme"] = tn
    mw.apply_theme()
    app.processEvents()
    QTimer.singleShot(80, loop.quit); loop.exec()
    for pg in pages:
        mw.switch_page(pg); app.processEvents()
        QTimer.singleShot(80, loop.quit); loop.exec()
        # 顺便让拖拽页显示拖入高亮（多一张展示动画态）
        extra = ""
        if pg == "drag":
            mw.pages["drag"].drop._set_drag(True); app.processEvents()
            QTimer.singleShot(120, loop.quit); loop.exec()
            extra = "_drag"
            mw.pages["drag"].drop._set_drag(False)
        pm = QPixmap(mw.size()); pm.fill(QColor(0,0,0,0))
        mw.render(pm)
        path = os.path.join(OUT, f"{tn}_{pg}{extra}.png")
        pm.save(path)
        print("saved", path)

print("DONE_PHASE1")

# -----------------------------------------------------------------------------
# Phase 2 — 隔离控件真渲染图（证明输入框色差 / #obs 色差 / 主+次按钮设计）
# 离屏整窗抓图不绘滚动区子控件的 QSS 背景，故隔离 render 才可信。
# -----------------------------------------------------------------------------
from PySide6.QtWidgets import QPlainTextEdit, QListWidget, QPushButton, QLabel, QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import QSize

def render_iso(w, path):
    """对能自绘的控件（QPushButton / QPlainTextEdit / QListWidget）走 render"""
    pm = QPixmap(w.width(), w.height())
    pm.fill(QColor(0, 0, 0, 0))
    w.render(pm)
    pm.save(path)
    print("iso saved", path)

def render_motif_to_file(svg, w, h, tw, th, path):
    """母题预览：直接渲染 + 保存 tiled pixmap，绕开离屏 child-render 陷阱"""
    pm = theme.render_tiled_pixmap(svg, w, h, tw, th)
    pm.save(path)
    print("motif saved", path)

def make_label(text, obj=None):
    l = QLabel(text)
    if obj: l.setObjectName(obj)
    l.setMinimumHeight(28)
    l.setMinimumWidth(80)
    return l

for tn in theme.THEME_NAMES:
    qss = theme.build_theme(tn, "light")
    app.setStyleSheet(qss)
    app.processEvents()
    QTimer.singleShot(40, loop.quit); loop.exec()

    # 输入框（liujin/朱印/古纹 三主题同款）：4px accent 左规 + input_bg
    te = QPlainTextEdit()
    te.setObjectName("input")
    te.setPlainText("BOOTH ID 列表\n每行一条，如 1234567\n或粘贴若干条 …")
    te.resize(360, 110); te.show()
    app.processEvents(); QTimer.singleShot(80, loop.quit); loop.exec()
    render_iso(te, os.path.join(OUT, f"iso_input_{tn}.png"))
    te.close(); te.deleteLater()

    # #obs（观测区）：surface2 深一档
    lw = QListWidget()
    lw.setObjectName("obs")
    lw.addItems(["[INFO] 归档 1/12 item_3987211",
                 "[INFO] 归档 2/12 item_4011333",
                 "[WARN] 已跳过重复 item_3910001"])
    lw.resize(360, 180); lw.show()
    app.processEvents(); QTimer.singleShot(80, loop.quit); loop.exec()
    render_iso(lw, os.path.join(OUT, f"iso_obs_{tn}.png"))
    lw.close(); lw.deleteLater()

    # 主按钮 #accent
    b1 = QPushButton("开始归档"); b1.setObjectName("accent")
    b1.resize(140, 40); b1.show()
    app.processEvents(); QTimer.singleShot(60, loop.quit); loop.exec()
    render_iso(b1, os.path.join(OUT, f"iso_btn_accent_{tn}.png"))
    b1.close(); b1.deleteLater()

    # 次按钮 #secondary（清空/修复/浏览）
    b2 = QPushButton("清空"); b2.setObjectName("secondary")
    b2.resize(120, 40); b2.show()
    app.processEvents(); QTimer.singleShot(60, loop.quit); loop.exec()
    render_iso(b2, os.path.join(OUT, f"iso_btn_secondary_{tn}.png"))
    b2.close(); b2.deleteLater()

    # hline（雷纹横条）— 离屏 child 不复合，直接渲染 motif pixmap（这就是真机看到的样子）
    render_motif_to_file(theme.motif_thunder_raw(tn, "light"), 640, 10, 200, 10,
                         os.path.join(OUT, f"iso_hline_{tn}.png"))

    # 拖拽区（麻叶）— 离屏 child 不复合，直接渲染 motif pixmap
    # 静态
    render_motif_to_file(theme.motif_drop_raw(tn, "light"), 420, 180, 28, 28,
                         os.path.join(OUT, f"iso_drop_{tn}.png"))
    # 拖入高亮：麻叶(hi=True) + 半透 accent_light 叠加（模拟 _glow 脉冲峰值时刻）
    pm_base = theme.render_tiled_pixmap(theme.motif_drop_raw(tn, "light", hi=True),
                                        420, 180, 28, 28)
    from PySide6.QtGui import QPainter
    pm_overlay = QPixmap(420, 180)
    al = theme.THEMES[tn]["light"].get("accent_light")
    pm_overlay.fill(QColor(al) if al else QColor(0, 0, 0, 0))
    p = QPainter(pm_base)
    p.setOpacity(0.45); p.drawPixmap(0, 0, pm_overlay); p.end()
    pm_base.save(os.path.join(OUT, f"iso_drop_hover_{tn}.png"))
    print("drop hover saved", tn)

print("DONE")
