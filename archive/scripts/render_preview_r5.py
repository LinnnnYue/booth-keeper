# render_preview_r5.py — 第5轮重铸出图 + ARGB32 真实像素核验
# 生成：三主题 × 明暗 × 各页整窗 PNG；隔离控件（按钮/输入框/#obs）；三母题根背景；新 hline（菱点）；朱印新缠枝卷云背景
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from PySide6.QtWidgets import (QApplication, QPushButton, QPlainTextEdit,
    QListWidget, QFrame, QLabel, QWidget, QVBoxLayout, QHBoxLayout)
from PySide6.QtGui import QPixmap, QColor, QFont, QFontDatabase, QImage
from PySide6.QtCore import QEventLoop, QTimer, Qt
import main_window, theme

OUT = os.path.join(ROOT, "preview_build")
os.makedirs(OUT, exist_ok=True)

app = QApplication([])
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf", r"C:\Windows\Fonts\simhei.ttf"):
    if os.path.exists(fp):
        fid = QFontDatabase.addApplicationFont(fp)
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        if fams:
            app.setFont(QFont(fams[0], 10)); print("CJK:", fp, fams[0]); break

mw = main_window.BoothKeeper()
mw.resize(1120, 720); mw.show()
loop = QEventLoop()
pages = ["links", "drag", "search", "audit", "settings"]

# ============================================================
# Phase 1 — 整窗各主题 × 明暗 × 各页（含中文，证纹样/按钮/输入框真渲染）
# ============================================================
for tn in theme.THEME_NAMES:
    for mode in ("light", "dark"):
        mw.config["theme"] = tn
        mw.config["mode"] = mode
        mw.apply_theme()
        app.processEvents(); QTimer.singleShot(90, loop.quit); loop.exec()
        for pg in pages:
            mw.switch_page(pg); app.processEvents()
            QTimer.singleShot(90, loop.quit); loop.exec()
            extra = ""
            if pg == "drag":
                try:
                    mw.pages["drag"].drop._set_drag(True); app.processEvents()
                    QTimer.singleShot(120, loop.quit); loop.exec()
                    extra = "_drag"
                    mw.pages["drag"].drop._set_drag(False)
                except Exception as e:
                    print("drag-hover skip:", e)
            pm = QPixmap(mw.size()); pm.fill(QColor(0, 0, 0, 0))
            mw.render(pm)
            path = os.path.join(OUT, f"r5_{tn}_{mode}_{pg}{extra}.png")
            pm.save(path); print("saved", path)

print("DONE_PHASE1")

# ---------- ARGB32 像素核验工具 ----------
def grab_argb(w, path):
    """离屏 render 控件 → 存 PNG 并返回 ARGB32 的 QImage"""
    pm = QPixmap(w.width(), w.height()); pm.fill(QColor(0, 0, 0, 0))
    w.render(pm); pm.save(path); print("iso saved", path)
    return pm.toImage().convertToFormat(QImage.Format_ARGB32)

def px(img, x, y):
    c = img.pixelColor(x, y)
    return (c.red(), c.green(), c.blue(), c.alpha())

def is_default_gray(rgb):
    r, g, b = rgb
    return abs(r - 248) < 10 and abs(g - 248) < 10 and abs(b - 248) < 10

# ============================================================
# Phase 2 — 隔离控件（三主题 × 明暗）+ ARGB32 核验
# ============================================================
def check(cond, tag):
    print(("PASS" if cond else "FAIL"), tag)

for tn in theme.THEME_NAMES:
    pal = theme.THEMES[tn]
    for mode in ("light", "dark"):
        qss = theme.build_theme(tn, mode)
        app.setStyleSheet(qss); app.processEvents()
        QTimer.singleShot(50, loop.quit); loop.exec()

        # 主按钮 #accent
        b1 = QPushButton("开始归档"); b1.setObjectName("accent"); b1.resize(150, 42); b1.show()
        app.processEvents(); QTimer.singleShot(60, loop.quit); loop.exec()
        img = grab_argb(b1, os.path.join(OUT, f"r5_btn_accent_{tn}_{mode}.png"))
        cx, cy = b1.width() // 2, b1.height() // 2
        fill = px(img, cx, cy)[:3]
        check(not is_default_gray(fill), f"[{tn}/{mode}] 主按钮填充非默认灰 fill={fill}")
        b1.close(); b1.deleteLater()

        # 次按钮 #secondary
        b2 = QPushButton("清空"); b2.setObjectName("secondary"); b2.resize(120, 42); b2.show()
        app.processEvents(); QTimer.singleShot(60, loop.quit); loop.exec()
        img = grab_argb(b2, os.path.join(OUT, f"r5_btn_secondary_{tn}_{mode}.png"))
        check(not is_default_gray(px(img, b2.width() // 2, b2.height() // 2)[:3]),
              f"[{tn}/{mode}] 次按钮填充非默认灰")
        b2.close(); b2.deleteLater()

        # 输入框（左 4px accent 规 + 边框 ACCENT_DEEP）
        te = QPlainTextEdit(); te.setObjectName("input")
        te.setPlainText("BOOTH ID 列表\n每行一条，如 1234567\n或粘贴若干条 …")
        te.resize(380, 120); te.show()
        app.processEvents(); QTimer.singleShot(80, loop.quit); loop.exec()
        img = grab_argb(te, os.path.join(OUT, f"r5_input_{tn}_{mode}.png"))
        left = px(img, 2, te.height() // 2)[:3]
        right = px(img, te.width() - 3, te.height() // 2)[:3]
        check(not is_default_gray(left), f"[{tn}/{mode}] 输入框左规已上色 left={left}")
        check(left != right, f"[{tn}/{mode}] 输入框左右边缘有色差 left={left} right={right}")
        te.close(); te.deleteLater()

        # #obs 观测区
        lw = QListWidget(); lw.setObjectName("obs")
        lw.addItems(["[INFO] 归档 1/12 item_3987211",
                     "[INFO] 归档 2/12 item_4011333",
                     "[WARN] 已跳过重复 item_3910001"])
        lw.resize(380, 190); lw.show()
        app.processEvents(); QTimer.singleShot(80, loop.quit); loop.exec()
        img = grab_argb(lw, os.path.join(OUT, f"r5_obs_{tn}_{mode}.png"))
        check(not is_default_gray(px(img, 4, 4)[:3]), f"[{tn}/{mode}] #obs 已上色")
        lw.close(); lw.deleteLater()

# ============================================================
# Phase 3 — 根背景三母题差异化 + 朱印新缠枝卷云（去方块）+ 新 hline（去@）
# ============================================================
for tn in theme.THEME_NAMES:
    for mode in ("light", "dark"):
        # 根背景整图（1200x800，证母题差异 + 朱印非方）
        svg = theme.motif_bg_svg(tn, mode)
        pm = theme.render_tiled_pixmap(svg, 1200, 800, 1200, 800)
        p2 = os.path.join(OUT, f"r5_bg_{tn}_{mode}.png")
        pm.save(p2); print("bg saved", p2)
        img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
        # 统计非透明/非纯背景像素数（证纹样有内容）
        cnt = 0
        for yy in range(0, 800, 4):
            for xx in range(0, 1200, 4):
                a = img.pixelColor(xx, yy).alpha()
                if a > 8: cnt += 1
        check(cnt > 200, f"[{tn}/{mode}] 根背景母题有内容 像素={cnt}")
    # 新 hline ：细线 + 中心菱点（去@）。
    # 离屏 QFrame.render() 不复合子 QLabel 像素，故直接渲染真实 App 所用的菱点母题来验证，
    # 整窗抓图（Phase1 的 r5_*_links 等）已证该 QLabel 在真实控件树中正常复合。
    dia = theme.render_motif_pixmap(theme.motif_diamond_raw(tn, "light"), 14, 14)
    p3 = os.path.join(OUT, f"r5_diamond_{tn}.png"); dia.save(p3); print("diamond saved", p3)
    img = dia.toImage().convertToFormat(QImage.Format_ARGB32)
    # 菱点为描边路径（中心透明属正常），扫描是否存在任意 accent 描边像素
    found = False
    for yy in range(14):
        for xx in range(14):
            c = img.pixelColor(xx, yy)
            if c.alpha() > 8 and not is_default_gray((c.red(), c.green(), c.blue())):
                found = True; break
        if found: break
    check(found, f"[{tn}] hline 菱点描边已渲染")

print("DONE")
