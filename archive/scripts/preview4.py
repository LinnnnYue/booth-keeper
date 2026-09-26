# preview4.py — 纹样系统总览（离屏可渲染矢量母题，针对性回应「纹样没看到」）
# 离屏 QSS background-image 不渲染，但 QSvgRenderer 可把每个母题 SVG 单独渲染成图。
# 本脚本把青海波侧栏纹 / 雷纹分隔 / 麻叶纹拖拽区 / 印章 / 太极 各自放大渲染、
# 垫上对应主题底色，拼成总览图——主上可直观确认纹样现已清晰可辨且有层次。
import os, sys, base64
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path: sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt, QSize
import theme
from PIL import Image, ImageDraw

OUT = os.path.join(ROOT, "preview2")
os.makedirs(OUT, exist_ok=True)

def svg_from_datauri(uri: str) -> str:
    """从 theme 生成的 SVG 解出原始字符串，供 QSvgRenderer 单独渲染。
    兼容三种形式：url(data:...;base64,...) / data:...;base64,... / 原始 <svg>。"""
    s = uri.lstrip()
    if s.startswith("url(data:") or s.startswith("data:"):
        inner = s[len("url("):] if s.startswith("url(") else s
        b64 = inner.split(",", 1)[1].rstrip(")")
        return base64.b64decode(b64).decode("utf-8")
    return uri

_render_counter = {"i": 0}
def render_svg(uri: str, w: int, h: int) -> Image.Image:
    r = QSvgRenderer(svg_from_datauri(uri).encode("utf-8"))
    pm = QPixmap(w, h)
    pm.fill(QColor(0, 0, 0, 0))
    if r.isValid():
        p = QPainter(pm)
        r.render(p, pm.rect())
        p.end()
    _render_counter["i"] += 1
    tmp = os.path.join(OUT, f"_tmp_svg_{_render_counter['i']}.png")
    pm.save(tmp)
    img = Image.open(tmp).convert("RGBA")
    try: os.remove(tmp)
    except Exception: pass
    return img

def qpm_to_pil(pm: QPixmap) -> Image.Image:
    pm.save(os.path.join(OUT, "_tmp_svg.png"))
    return Image.open(os.path.join(OUT, "_tmp_svg.png")).convert("RGBA")

def tile_bg(rgb, w, h):
    return Image.new("RGBA", (w, h), rgb + (255,))

def paste_centered(bg, fg, label=None):
    if fg is None: return bg
    fw, fh = fg.size
    x = max(0, (bg.width - fw)//2); y = max(0, (bg.height - fh)//2)
    bg.paste(fg, (x, y), fg)
    return bg

def label_img(img, text, rgb_text=(60,55,48,255)):
    d = ImageDraw.Draw(img)
    try:
        from PIL import ImageFont
        f = ImageFont.load_default()
        d.text((8, 6), text, fill=rgb_text, font=f)
    except Exception:
        d.text((8, 6), text, fill=rgb_text)
    return img

def hex2rgb(h):
    h=h.lstrip("#"); return (int(h[0:2],16),int(h[2:4],16),int(h[4:6],16))

def build():
    app = QApplication([])
    themes = ["zhuyin", "liujin", "guwen"]
    motif_kind = theme.THEME_MOTIF
    rows = []
    for t in themes:
        pal = theme.THEMES[t]["light"]
        accent = pal["accent"]
        vein = accent
        surf2 = hex2rgb(pal["surface2"])
        bg = hex2rgb(pal["bg"])
        # 各母题目标尺寸
        sidebar = render_svg(theme._motif_sidebar(vein, motif_kind[t]), 144, 720)
        thunder = render_svg(theme._motif_thunder(vein), 400, 44)
        asa = render_svg(theme.asa_no_ha(vein, op=0.22), 220, 140)  # 拖入提亮态
        seal = render_svg(theme.seal_svg(accent), 96, 96)
        taiji = render_svg(theme.taiji_svg_raw(accent, pal["bg"]), 96, 96)

        tiles = []
        # 侧栏青海波+脉络（取中段 144x260 以清晰展示鳞波层次）
        s_crop = sidebar.crop((0, 200, 144, 460)) if sidebar else None
        s = tile_bg(surf2, 160, 280); paste_centered(s, s_crop); tiles.append(label_img(s, "Seigaiha sidebar"))
        # 雷纹
        th = tile_bg(bg, 420, 64); paste_centered(th, thunder); tiles.append(label_img(th, "Thunder divider"))
        # 麻叶纹拖拽区
        a = tile_bg(surf2, 240, 160); paste_centered(a, asa); tiles.append(label_img(a, "Asa-no-ha drop"))
        # 印章
        se = tile_bg(bg, 120, 120); paste_centered(se, seal); tiles.append(label_img(se, "Seal brand"))
        # 太极
        tj = tile_bg(bg, 120, 120); paste_centered(tj, taiji); tiles.append(label_img(tj, "Taiji mode"))

        # 拼成一行
        row_h = max(t.height for t in tiles)
        row = Image.new("RGBA", (sum(x.width for x in tiles)+10*len(tiles), row_h),
                        (0,0,0,0))
        x = 0
        for tl in tiles:
            row.paste(tl, (x, 0), tl); x += tl.width + 10
        # 顶部主题名
        head = Image.new("RGBA", (row.width, 26), (0,0,0,0))
        dh = ImageDraw.Draw(head)
        dh.text((4,4), f"THEME: {t.upper()}  ({theme.THEME_NAMES[t]})", fill=(40,35,28,255))
        full = Image.new("RGBA", (row.width, 30 + row.height), (0,0,0,0))
        full.paste(head, (0,0)); full.paste(row, (0,30))
        rows.append(full)

    mont = Image.new("RGBA", (max(r.width for r in rows), sum(r.height for r in rows)+10*len(rows)),
                     (245,243,237,255))
    y = 0
    for r in rows:
        mont.paste(r, (0, y), r); y += r.height + 10
    out = os.path.join(OUT, "motif_overview.png")
    mont.convert("RGB").save(out)
    print("SAVED", out, os.path.getsize(out)//1024, "KB")
    # 清理临时
    try: os.remove(os.path.join(OUT, "_tmp_svg.png"))
    except Exception: pass

if __name__ == "__main__":
    build()
