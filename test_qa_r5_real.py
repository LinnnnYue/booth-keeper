# test_qa_r5_real.py — 启动真实 BoothKeeper，采样【实际页按钮】像素，
# 复现真机路径（apply_theme 用 self.setStyleSheet 窗口级），确证传播是否生效。
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper")

from PySide6.QtWidgets import QApplication, QWidget, QPushButton
from PySide6.QtGui import QImage, QColor, QPixmap
from PySide6.QtCore import QEventLoop, QTimer
import theme
import main_window

OUT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper\preview_build"
os.makedirs(OUT, exist_ok=True)
RES = []

def argb(pm): return pm.toImage().convertToFormat(QImage.Format_ARGB32)
def hex2rgb(h): h=h.lstrip("#"); return tuple(int(h[i:i+2],16) for i in (0,2,4))
def close(a,b,tol=40): return all(abs(a[i]-b[i])<=tol for i in range(3))

def sample(w, path):
    """直接 render 实际控件（不走父背板，故避 scroll-child 陷阱），返回 (fill众数, img)。"""
    w.show(); app.processEvents()
    QTimer.singleShot(50, loop.quit); loop.exec()
    pm = QPixmap(w.size()); pm.fill(QColor(0,0,0,0))
    w.render(pm); pm.save(path)
    return argb(pm)

def dom_color(img):
    from collections import Counter
    cnt=Counter()
    for y in range(img.height()):
        for x in range(img.width()):
            c=img.pixelColor(x,y)
            if c.alpha()<200: continue
            cnt[(c.red()//8*8,c.green()//8*8,c.blue()//8*8)]+=1
    return cnt.most_common(1)[0][0] if cnt else None

def is_default_gray(fill):
    """Qt Fusion 默认按钮底≈(248,248,248)近白灰；已上色则带主题色（非中性灰）。"""
    if fill is None: return False
    r,g,b = fill
    return abs(r-g)<12 and abs(g-b)<12 and r>232

app = QApplication([])
loop = QEventLoop()
mw = main_window.BoothKeeper()

# 真实 App 路径：apply_theme 内部用 self.setStyleSheet（窗口级）
for tn in ["zhuyin","liujin","guwen"]:
    for mode in ["light","dark"]:
        mw.config["theme"]=tn; mw.config["mode"]=mode
        mw.apply_theme()
        app.processEvents()
        pal = theme.THEMES[tn][mode]
        bf = hex2rgb(pal["btn_fill"])
        # 取各页真实按钮实例
        targets = []
        links = mw.pages["links"]
        targets.append(("links.解析链接", links.btn_parse))
        targets.append(("links.清空", links.btn_clear))
        drag = mw.pages["drag"]
        targets.append(("drag.开始归档", drag.btn_run))
        targets.append(("drag.清空", drag.btn_clear))
        search = mw.pages["search"]
        targets.append(("search.检索", search.btn_search))
        targets.append(("search.归档选中", search.btn_archive))
        audit = mw.pages["audit"]
        targets.append(("audit.开始巡检", audit.btn_scan))
        targets.append(("audit.修复", audit.btn_fix))
        targets.append(("audit.开始版本巡检", audit.btn_ver))
        settings = mw.pages["settings"]
        targets.append(("settings.保存设置", settings.root.findChild(QWidget,"") ))  # 占位
        # settings 保存按钮无 objectName 引用，用遍历
        for b in settings.findChildren(QWidget):
            if isinstance(b, QPushButton) and b.text()=="保存设置":
                targets[-1] = ("settings.保存设置", b); break
        for nm, btn in targets:
            img = sample(btn, os.path.join(OUT, f"_real_{nm.replace('.','_')}_{tn}_{mode}.png"))
            fill = dom_color(img)
            # 已上色 = 非 Qt 默认灰（accent填充/禁用BORDER2/secondary透明+accent描边 均非中性灰）
            ok = fill is not None and not is_default_gray(fill)
            RES.append((f"[{tn}/{mode}] {nm}填充={fill} 已上色", ok))
            print(("PASS " if ok else "FAIL ")+f"[{tn}/{mode}] {nm} 填充={fill}")

fails=[r for r in RES if not r[1]]
print(f"\n真实App按钮采样 总计 {len(RES)}，失败 {len(fails)}")
for f in fails: print("  ✗", f[0])
sys.exit(1 if fails else 0)
