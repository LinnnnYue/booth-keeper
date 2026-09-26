# test_qa_r5.py — 第5轮总监质检（真机像素采样，ARGB32 保真）
# 隔离渲染实际控件 + 应用同款 QSS，采样 fill/text/border 像素，确证是否真上色。
# 同时核验母题非透明像素（三主题根背景 + hline + 麻叶）。
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper")

from PySide6.QtWidgets import (QApplication, QPushButton, QPlainTextEdit,
    QListWidget, QWidget, QFrame)
from PySide6.QtGui import QPixmap, QImage, QColor
from PySide6.QtCore import QEventLoop, QTimer, Qt
import theme

OUT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper\preview_build"
os.makedirs(OUT, exist_ok=True)
RES = []

def close(a, b, tol=36):
    return all(abs(a[i]-b[i]) <= tol for i in range(3))

def argb(pm):
    return pm.toImage().convertToFormat(QImage.Format_ARGB32)

def render_iso(w, path):
    w.show(); app.processEvents()
    QTimer.singleShot(60, loop.quit); loop.exec()
    pm = QPixmap(w.size()); pm.fill(QColor(0,0,0,0))
    w.render(pm); pm.save(path)
    return argb(pm)

def dom_color(img):
    """返回不透明像素的众数颜色（排除近白/近黑噪声）。"""
    from collections import Counter
    cnt = Counter()
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() < 200:
                continue
            cnt[(c.red()//8*8, c.green()//8*8, c.blue()//8*8)] += 1
    if not cnt:
        return None
    (r,g,b), _ = cnt.most_common(1)[0]
    return (r,g,b)

def npix_alpha(img, thr=20):
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x,y).alpha() > thr:
                n += 1
    return n

def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0,2,4))

def check(name, ok, detail=""):
    RES.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + ("  " + detail if detail else ""))

app = QApplication([])
loop = QEventLoop()

for tn in theme.THEME_NAMES:
    for mode in ("light", "dark"):
        pal = theme.THEMES[tn][mode]
        qss = theme.build_theme(tn, mode)
        app.setStyleSheet(qss)
        bf = hex2rgb(pal["btn_fill"]); bd = hex2rgb(pal["accent_deep"])
        ac = hex2rgb(pal["accent"]); ibg = hex2rgb(pal["input_bg"])
        s2 = hex2rgb(pal["surface2"])

        # ---- accent 按钮（空标签隔离采样，避文字干扰）----
        b = QPushButton("")
        b.setObjectName("accent"); b.setFixedSize(160, 38)
        img = render_iso(b, os.path.join(OUT, f"_qa_accent_{tn}_{mode}.png"))
        fill = dom_color(img)
        fill_ok = fill is not None and close(fill, bf)
        check(f"[{tn}/{mode}] accent填充={fill}≈btn_fill{bf}", fill_ok)
        b.deleteLater()

        # ---- secondary 按钮 ----
        b2 = QPushButton("")
        b2.setObjectName("secondary"); b2.setFixedSize(160, 38)
        img2 = render_iso(b2, os.path.join(OUT, f"_qa_secondary_{tn}_{mode}.png"))
        fc = img2.pixelColor(img2.width()//2, img2.height()//2)
        center_trans = fc.alpha() < 80   # 透明底=secondary正确
        # 边缘找 accent 描边
        edge_accent = False
        for y in range(2, img2.height()-2):
            for x in (1, img2.width()-2):
                c = img2.pixelColor(x, y)
                if c.alpha() > 120 and close((c.red(),c.green(),c.blue()), ac, 40):
                    edge_accent = True; break
            if edge_accent: break
        check(f"[{tn}/{mode}] secondary透明底={center_trans} 描边accent={edge_accent}",
              center_trans and edge_accent)
        b2.deleteLater()

        # ---- 输入框（QPlainTextEdit）----
        e = QPlainTextEdit("")
        e.setFixedSize(420, 90)
        img3 = render_iso(e, os.path.join(OUT, f"_qa_input_{tn}_{mode}.png"))
        left = img3.pixelColor(2, img3.height()//2)      # 4px accent 左规
        ctr = img3.pixelColor(img3.width()//2, img3.height()//2)
        left_ok = left.alpha()>120 and close((left.red(),left.green(),left.blue()), ac, 45)
        center_ok = close((ctr.red(),ctr.green(),ctr.blue()), ibg, 30)
        check(f"[{tn}/{mode}] 输入框左规={ (left.red(),left.green(),left.blue()) }≈accent", left_ok)
        check(f"[{tn}/{mode}] 输入框底={ (ctr.red(),ctr.green(),ctr.blue()) }≈input_bg", center_ok)
        e.deleteLater()

        # ---- #obs 列表 ----
        o = QListWidget(); o.setObjectName("obs"); o.setFixedSize(360, 160)
        img4 = render_iso(o, os.path.join(OUT, f"_qa_obs_{tn}_{mode}.png"))
        octr = img4.pixelColor(img4.width()//2, img4.height()//2)
        otop = img4.pixelColor(img4.width()//2, 1)       # border-top 2px accent
        octr_ok = close((octr.red(),octr.green(),octr.blue()), s2, 30)
        otop_ok = otop.alpha()>120 and close((otop.red(),otop.green(),otop.blue()), ac, 45)
        check(f"[{tn}/{mode}] #obs底≈surface2={ (octr.red(),octr.green(),octr.blue()) }", octr_ok)
        check(f"[{tn}/{mode}] #obs顶规≈accent", otop_ok)
        o.deleteLater()

print("\n=== 母题非透明像素（ARGB32）===")
for tn in theme.THEME_NAMES:
    for motif, fn, w, h, tile, tw, th in [
        ("root", theme.motif_bg_svg, 360, 240, False, 0, 0),
        ("hline", theme.motif_thunder_raw, 360, 10, True, 200, 10),
        ("drop", theme.motif_drop_raw, 360, 160, True, 28, 28),
    ]:
        svg = fn(tn) if motif != "root" else fn(tn, "light")
        if tile:
            pm = theme.render_tiled_pixmap(svg, w, h, tw, th)
        else:
            pm = theme.render_motif_pixmap(svg, w, h)
        n = npix_alpha(argb(pm))
        check(f"[{tn}] {motif} 母题像素={n}", n > 50, f"({w}x{h})")
        pm.save(os.path.join(OUT, f"_qa_{motif}_{tn}.png"))

fails = [r for r in RES if not r[1]]
print(f"\n总计 {len(RES)} 项，失败 {len(fails)} 项")
sys.exit(1 if fails else 0)
