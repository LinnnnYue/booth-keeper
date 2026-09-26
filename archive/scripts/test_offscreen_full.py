# test_offscreen_full.py — 离屏程序化多维自测（真正渲染，回应「你这些都测了没」）
# 覆盖主上第 4 轮 6 点：纹样可见 / 输入框色差 / 按钮设计 / 三主题差异 / 拖入动画 / 全维度。
import os, sys, json
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtCore import Qt, QEventLoop, QTimer
import theme

RES = []  # (name, passed, detail)

def check(name, cond, detail=""):
    RES.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), name, ("— " + detail) if detail else "")

def hexrgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def close(c1, c2, tol=50):
    return all(abs(a - b) <= tol for a, b in zip(c1, c2))

def saturated(rgb):
    r, g, b = rgb
    return (max(r, g, b) - min(r, g, b)) > 35

def count_in_img(img, pred):
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if pred((c.red(), c.green(), c.blue())):
                n += 1
    return n

def pm_to_img(pm):
    # 用 ARGB32 保真 alpha（RGB32 会丢 alpha → 假阳性，所有像素 alpha=255）
    return pm.toImage().convertToFormat(QImage.Format_ARGB32)

# ---------------------------------------------------------------------------
# 1) QSS 完整性：6 套均无未解析占位符、无 url(data:)（已修的根因）
# ---------------------------------------------------------------------------
app = QApplication([])
for tn in theme.THEME_NAMES:
    for m in ("light", "dark"):
        qss = theme.build_theme(tn, m)
        no_ph = "<" not in qss
        no_url = "url(" not in qss
        check(f"QSS[{tn}/{m}] 无占位符&无url()", no_ph and no_url,
              f"len={len(qss)} ph={no_ph} url={no_url}")

# ---------------------------------------------------------------------------
# 2) 母题 SVG 真渲染：各纹样渲染出非透明像素（证明图案真的画出来，非隐形）
# ---------------------------------------------------------------------------
def render_ok(svg, w, h, tile=False, tw=28, th=28):
    if tile:
        pm = theme.render_tiled_pixmap(svg, w, h, tw, th)
    else:
        pm = theme.render_motif_pixmap(svg, w, h)
    img = pm_to_img(pm)
    # ARGB32 真测：用 alpha>20 判真可见（亚像素抗锯齿 alpha<20 忽略）
    npix = 0
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > 20:
                npix += 1
    return npix

for tn in theme.THEME_NAMES:
    pal = theme.THEMES[tn]["light"]
    side = render_ok(theme.motif_sidebar_raw(tn), 72, 600, tile=True, tw=72, th=720)
    thu = render_ok(theme.motif_thunder_raw(tn), 400, 10, tile=True, tw=200, th=10)
    drop = render_ok(theme.motif_drop_raw(tn), 200, 130, tile=True, tw=28, th=28)
    root = render_ok(theme.motif_bg_svg(tn), 300, 200)
    check(f"motif[{tn}] sidebar 非透明像素", side > 500, f"npix={side}")
    check(f"motif[{tn}] thunder 非透明像素", thu > 200, f"npix={thu}")
    check(f"motif[{tn}] drop(麻叶) 非透明像素", drop > 100, f"npix={drop}")
    check(f"motif[{tn}] root背景 非透明像素", root > 200, f"npix={root}")

# ---------------------------------------------------------------------------
# 3) 全窗集成：离屏启动 BoothKeeper，抓取真实控件像素验证
#    （嵌套控件单独 grab 在离屏下常返回空白，故统一抓整窗再用 mapTo 定位采样）
# ---------------------------------------------------------------------------
from PySide6.QtCore import QPoint
import main_window
mw = main_window.BoothKeeper()
mw.resize(1080, 700)
mw.show()
app.processEvents()
loop = QEventLoop()
QTimer.singleShot(120, loop.quit)
loop.exec()

def grab_window():
    return pm_to_img(mw.grab())

def region_of(w):
    pt = w.mapTo(mw, QPoint(0, 0))
    return (pt.x(), pt.y(), pt.x() + w.width(), pt.y() + w.height())

def sample_any(img, r, pred):
    x0, y0, x1, y1 = r
    for y in range(max(0, y0), min(img.height(), y1)):
        for x in range(max(0, x0), min(img.width(), x1)):
            c = img.pixelColor(x, y)
            if pred((c.red(), c.green(), c.blue())):
                return True
    return False

def sample_center(img, r):
    x = (r[0] + r[2]) // 2
    y = (r[1] + r[3]) // 2
    c = img.pixelColor(x, y)
    return (c.red(), c.green(), c.blue())

# 3a) 侧栏纹样可见：抓取侧栏，统计「饱和且接近 accent」的像素（母题描边）
def sidebar_has_motif(tn):
    pal = theme.THEMES[tn][mw.config.get("mode") or theme.DEFAULT_MODE_PER_THEME[tn]]
    ac = hexrgb(pal["accent"])
    surf2 = hexrgb(pal["surface2"])
    img = pm_to_img(mw.sidebar.grab())
    cnt = count_in_img(img, lambda c: saturated(c) and close(c, ac, 60)
                        and not close(c, surf2, 30))
    return cnt

for tn in theme.THEME_NAMES:
    mw.config["theme"] = tn
    mw.apply_theme()
    app.processEvents()
    QTimer.singleShot(60, loop.quit); loop.exec()
    cnt = sidebar_has_motif(tn)
    check(f"集成[{tn}] 侧栏纹样可见(描边像素)", cnt > 30, f"accent描边像素={cnt}")

# 3b) 主操作按钮（#accent）填充正确：直接 render 按钮，扫描有无 btn_fill 像素
mw.config["theme"] = "liujin"; mw.apply_theme(); app.processEvents()
QTimer.singleShot(40, loop.quit); loop.exec()
links = mw.pages["links"]
mw.switch_page("links"); app.processEvents()
QTimer.singleShot(60, loop.quit); loop.exec()

def render_widget(w):
    pm = QPixmap(w.width(), w.height())
    pm.fill(QColor(0, 0, 0, 0))
    w.render(pm)
    return pm_to_img(pm)

btn = links.btn_run  # #accent
pal = theme.THEMES["liujin"][mw.config.get("mode") or "light"]
bf = hexrgb(pal["btn_fill"])
img = render_widget(btn)
found_fill = sample_any(img, (0, 0, img.width(), img.height()),
                         lambda c: close(c, bf, 45))
check("集成 主按钮#accent 填充≈btn_fill", found_fill, f"btn_fill={bf}")

# 3c/3d) 输入框与 #obs：离屏对「滚动区子控件」抓图/渲染有已知限制（视口不绘），
#        故改用「隔离控件 + 应用同款 QSS」直接 render，验证 QSS 对该类控件确实
#        渲染出左规与底色差（等价于真机同款渲染路径）。
from PySide6.QtWidgets import QPlainTextEdit, QListWidget
app.setStyleSheet(theme.build_theme("liujin", "light"))
pal_l = theme.THEMES["liujin"]["light"]
ac = hexrgb(pal_l["accent"])
inbg = hexrgb(pal_l["input_bg"])
surf2 = hexrgb(pal_l["surface2"])

te = QPlainTextEdit(); te.resize(360, 90); te.show(); app.processEvents()
QTimer.singleShot(60, loop.quit); loop.exec()
pm = QPixmap(te.width(), te.height()); pm.fill(QColor(0, 0, 0, 0)); te.render(pm)
ti = pm_to_img(pm)
mid = ti.height() // 2
left_accent = any(close((ti.pixelColor(x, mid).red(),
                          ti.pixelColor(x, mid).green(),
                          ti.pixelColor(x, mid).blue()), ac, 75)
                 for x in range(0, 7))
edit_c = (ti.pixelColor(ti.width() // 2, mid).red(),
          ti.pixelColor(ti.width() // 2, mid).green(),
          ti.pixelColor(ti.width() // 2, mid).blue())
check("集成 输入框左规(4px accent 边)", left_accent,
      f"accent={ac} 左缘含accent={left_accent}")
check("集成 输入框底色=input_bg", close(edit_c, inbg, 18),
      f"edit_center={edit_c} input_bg={inbg}")

obs_w = QListWidget(); obs_w.setObjectName("obs")
obs_w.resize(360, 180); obs_w.show(); app.processEvents()
QTimer.singleShot(60, loop.quit); loop.exec()
pm2 = QPixmap(obs_w.width(), obs_w.height()); pm2.fill(QColor(0, 0, 0, 0)); obs_w.render(pm2)
oi = pm_to_img(pm2)
obs_c = (oi.pixelColor(oi.width() // 2, oi.height() // 2).red(),
         oi.pixelColor(oi.width() // 2, oi.height() // 2).green(),
         oi.pixelColor(oi.width() // 2, oi.height() // 2).blue())
check("集成 #obs 底色=surface2", close(obs_c, surf2, 18), f"obs={obs_c} surface2={surf2}")
check("集成 #obs 与输入框 底色差", not close(obs_c, edit_c, 18),
      f"obs={obs_c} edit={edit_c}")

# 3e) 三主题根背景确为「不同」母题（金缮仅鎏金；朱印回字/古纹叶脉）
def root_kind(tn):
    s = theme.motif_bg_svg(tn, "light")
    return ("thunder_grid" if (s.count("<rect") > 20)
            else "leaf" if "M160 250" in s else "kintsugi")
kinds = {tn: root_kind(tn) for tn in theme.THEME_NAMES}
check("集成 鎏金根背景=金缮", kinds["liujin"] == "kintsugi", str(kinds))
check("集成 朱印根背景≠金缮", kinds["zhuyin"] != "kintsugi", kinds["zhuyin"])
check("集成 古纹根背景≠金缮", kinds["guwen"] != "kintsugi", kinds["guwen"])

# 3f) 拖入动画：切到拖拽页→触发拖入态 → 脉冲动画运行 + 高亮层可见；离开 → 停止隐藏
mw.switch_page("drag"); app.processEvents()
QTimer.singleShot(60, loop.quit); loop.exec()
drag = mw.pages["drag"]
drag.on_theme("liujin", "light")
app.processEvents()
QTimer.singleShot(40, loop.quit); loop.exec()
drag.drop._set_drag(True)
app.processEvents()
QTimer.singleShot(120, loop.quit); loop.exec()
# 动画运行 → 透明度被驱动（>0.05）；离开后归零
anim_active = drag.drop._eff.opacity() > 0.05
glow_visible = drag.drop._glow.isVisible()
check("集成 拖入动画运行+高亮可见", anim_active and glow_visible,
      f"opacity={drag.drop._eff.opacity():.3f} glow_visible={glow_visible}")
drag.drop._set_drag(False)
app.processEvents()
anim_stopped = drag.drop._anim.state() != 2
glow_hidden = not drag.drop._glow.isVisible()
check("集成 离开拖入→动画停+高亮隐", anim_stopped and glow_hidden,
      f"stopped={anim_stopped} hidden={glow_hidden}")

# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
passed = sum(1 for _, p, _ in RES if p)
total = len(RES)
print("\n==== 多维自测汇总 ====")
print(f"{passed}/{total} 通过")
fails = [n for n, p, _ in RES if not p]
if fails:
    print("未通过：", fails)
    sys.exit(1)
print("全部通过 ✅")
