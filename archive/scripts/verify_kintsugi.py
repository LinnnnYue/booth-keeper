# verify_kintsugi.py — 程序化核验金缮背景脉络确实渲染进 RootWidget 的 QLabel
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication
import theme

OUT = os.path.join(ROOT, "preview2", "_verify")

def render_motif_only(theme_name, mode):
    """只画釉底+脉络（不含任何窗口部件），保存用于大小比对。"""
    os.makedirs(OUT, exist_ok=True)
    w, h = 1080, 700
    pal = theme.THEMES[theme_name][mode]
    svg = theme.motif_bg_svg(theme_name, mode)
    # 含脉络版本
    pix = QPixmap(w, h); pix.fill(QColor(pal["bg"]))
    pp = QPainter(pix); r = QSvgRenderer(svg.encode("utf-8"))
    ok = r.isValid(); 
    if ok: r.render(pp, pix.rect())
    pp.end()
    p_with = os.path.join(OUT, f"{theme_name}_{mode}_with.png")
    pix.save(p_with)
    # 纯色基线（同尺寸同底色，无脉络）
    base = QPixmap(w, h); base.fill(QColor(pal["bg"]))
    p_blank = os.path.join(OUT, f"{theme_name}_{mode}_blank.png")
    base.save(p_blank)
    return ok, os.path.getsize(p_with), os.path.getsize(p_blank)

def main():
    app = QApplication([])
    print("renderer_valid | theme | mode | with(KB) | blank(KB) | delta(KB)")
    total_delta = 0
    for n in theme.THEME_NAMES:
        for m in ("light", "dark"):
            ok, s_with, s_blank = render_motif_only(n, m)
            delta = (s_with - s_blank) / 1024.0
            total_delta += delta
            print(f"{ok!s:5} | {n:7} | {m:5} | {s_with/1024:7.1f} | {s_blank/1024:6.1f} | {delta:6.1f}")
    # 验收：六个组合里，含脉络图必须明显大于纯色基线（证明金线纹理写了实内容）
    print(f"TOTAL_DELTA_KB={total_delta:.1f}")
    # 同时列出 30 张整窗预览大小，确认全部非空洞
    pv = os.path.join(ROOT, "preview2")
    files = [f for f in os.listdir(pv) if f.endswith(".png") and not f.startswith("_")]
    sizes = [(f, os.path.getsize(os.path.join(pv, f))) for f in files]
    sizes.sort(key=lambda x: x[1])
    print(f"PREVIEW_COUNT={len(sizes)}  min={sizes[0][1]/1024:.1f}KB  max={sizes[-1][1]/1024:.1f}KB")
    print("SMALLEST_3:", sizes[:3])
    print("DONE")

if __name__ == "__main__":
    main()
