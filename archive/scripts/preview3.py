# preview3.py — 合成整合预览：把 UI 抓图背景抠透明，垫上已验证的金缮纹理
# 目的：离屏抓图不合成 _bg 子标签(QSS背景图/视口透明度均丢)，故手动合成，
#       让主上能看到「金缮脉络在背景里 + UI 浮于其上」的整合效果。
# 说明：离屏无 CJK 字体，文字会显示成方框；侧栏/标题/卡片角的矢量纹饰
#       (QSS background-image) 离屏也不渲染，真机才有——预览仅代表金缮背景层。
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path: sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
import theme
from main_window import BoothKeeper
from PIL import Image

OUT = os.path.join(ROOT, "preview2")
VERIFY = os.path.join(OUT, "_verify")
PAGES = ["links", "settings"]
COMBOS = [("zhuyin","light"), ("zhuyin","dark"),
          ("liujin","light"), ("liujin","dark"),
          ("guwen","light"), ("guwen","dark")]

def hex2rgb(h):
    h=h.lstrip("#"); return (int(h[0:2],16),int(h[2:4],16),int(h[4:6],16))

def composite_one(ui_path, tex_path, out_path, bg_rgb):
    ui = Image.open(ui_path).convert("RGBA")
    tex = Image.open(tex_path).convert("RGBA").resize(ui.size)
    br,bg_,bb = bg_rgb
    data = list(ui.getdata()); new=[]
    for (r,g,b,a) in data:
        # 中性灰(Fusion 默认窗色) 或 主题主底色 → 抠透明，露出底下金缮
        if (abs(r-239)<8 and abs(g-239)<8 and abs(b-239)<8) or \
           (abs(r-br)<7 and abs(g-bg_)<7 and abs(b-bb)<7):
            new.append((r,g,b,0))
        else:
            new.append((r,g,b,a))
    ui.putdata(new)
    out = Image.alpha_composite(tex, ui)
    out.save(out_path)
    return os.path.getsize(out_path)

def main():
    app = QApplication([]); app.setStyle("Fusion")
    win = BoothKeeper(); win.show(); app.processEvents()
    made=[]
    for (t,m) in COMBOS:
        win.config["theme"]=t; win.config["mode"]=m
        win.apply_theme(); app.processEvents()
        bg_rgb = hex2rgb(theme.THEMES[t][m]["bg"])
        tex_path = os.path.join(VERIFY, f"{t}_{m}_with.png")
        for page in PAGES:
            win.switch_page(page); app.processEvents(); win.repaint(); app.processEvents()
            root = win.centralWidget()
            gp = os.path.join(OUT, "_dbg", f"ui_{t}_{m}_{page}.png"); root.grab().save(gp)
            out = os.path.join(OUT, f"comp_{t}_{m}_{page}.png")
            sz = composite_one(gp, tex_path, out, bg_rgb)
            made.append((out, sz))
            print(f"  {out}  {sz/1024:.1f}KB")
    print(f"COMPOSITE_MADE={len(made)}")
    print("DONE")

if __name__=="__main__":
    main()
