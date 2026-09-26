# preview_render.py — BoothKeeper 视觉预览生成（临时脚本，总监可能复用）
#
# 用途：在 Qt offscreen 模式下把 BoothKeeper 主窗口渲染成 PNG，供主上提前审美拍板，
#       无需等待 exe。严禁修改任何现有源码（theme.py / main_window.py / pages/*），
#       本文件为新建临时脚本。
#
# 运行（优先托管 Python）：
#   C:\Users\19388\.workbuddy\binaries\python\envs\default\Scripts\python.exe preview_render.py
#   # 回退：
#   C:\Users\19388\.workbuddy\binaries\python\versions\3.13.12\python.exe preview_render.py
#
# 必须在 import PySide6 之前设置 QT_QPA_PLATFORM=offscreen。

import os
import sys
import traceback

# ---- 关键：offscreen 平台必须在 import PySide6 之前设置 ----
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# offscreen 无显示器，禁用字体回退告警刷屏（CJK 字体缺失属预期，不影响布局/配色）
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")

ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, "preview")
os.makedirs(OUT_DIR, exist_ok=True)

# 需要预览的配色/模式组合（至少三套：朱浅色 / 墨深色 / 藤浅色）
COMBOS = [
    ("coral", "light"),
    ("teal", "dark"),
    ("purple", "light"),
]

# 五页尽量全：批量链接 / 拖拽分类 / 实验检索 / 目录巡检 / 设置
PAGES = ["links", "drag", "search", "audit", "settings"]

generated = []          # 成功生成的 (path, desc)
cjk_warning = False     # 是否观察到 CJK 字体缺失告警


def populate_samples(win):
    """往各页列表填充纯 UI 示例数据（不触发任何网络），让截图更具代表性。"""
    try:
        lp = win.pages.get("links")
        if lp:
            lp.edit.setPlainText(
                "booth.pm/items/3290806 免费！GoGo Loco\n"
                "https://booth.pm/ja/items/1234567 Kirisame Ver3.0")
            for txt in [
                "3290806 · GoGo Loco  →  3Dモデル/衣装",
                "1234567 · Kirisame Ver3.0  →  3Dモデル/アバター",
            ]:
                lp.queue.addItem(txt)
            lp.bar.setValue(40)
            lp.lbl_count.setText("解析到 2 个有效商品 ID")

        dp = win.pages.get("drag")
        if dp:
            for txt in ["3290806 · [folder] GoGo_Loco_v2", "2222222 · Kirisame_Model"]:
                dp.queue.addItem(txt)
            dp.no_list.addItem("screenshot_uncropped.png  （缺 ID）")
            dp.bar.setValue(20)

        sp = win.pages.get("search")
        if sp:
            for txt in [
                "3290806 · GoGo Loco   |   ¥0   |   AuthorA",
                "1234567 · Kirisame Ver3.0   |   ¥1,200   |   AuthorB",
            ]:
                sp.list.addItem(txt)
            sp.lbl.setText("命中 2 条（显示前 20）。建议人工核对后归档。")

        ap = win.pages.get("audit")
        if ap:
            for txt, miss in [
                ("3290806 · GoGo Loco   [完整]", False),
                ("2222222 · Kirisame Ver3.0   [缺封面]", True),
                ("1111111 · Sample Pack   [完整]", False),
            ]:
                ap.list_scan.addItem(txt)
            for txt in ["2222222 · Kirisame Ver3.0   本地 2.0 → 官方 3.1  可更新"]:
                ap.list_ver.addItem(txt)
            ap.lbl_stat.setText("共 3 件，1 件缺失三件套")
            ap.bar.setValue(100)
    except Exception:
        # 填充失败不影响主流程（降级为空白页截图）
        pass


def render_full_window():
    """首选：构造完整 MainWindow 实例并逐页抓图。"""
    from PySide6.QtWidgets import QApplication
    import theme
    from main_window import BoothKeeper

    app = QApplication([])
    app.setStyle("Fusion")
    win = BoothKeeper()
    win.show()
    app.processEvents()

    populate_samples(win)

    for accent, mode in COMBOS:
        win.config["accent"] = accent
        win.config["mode"] = mode
        win.apply_theme()
        try:
            win.pages.get("settings").mark_accent()
        except Exception:
            pass
        app.processEvents()
        for page in PAGES:
            win.switch_page(page)
            app.processEvents()
            win.repaint()
            pix = win.grab()
            name = f"{accent}_{mode}_{page}.png"
            path = os.path.join(OUT_DIR, name)
            ok = pix.save(path)
            if ok:
                generated.append((path, f"{accent}/{mode} · {page} 页"))
            else:
                print("WARN: save failed", path)

    # 额外：一张「朱浅色·全窗口」作为封面概览（链接页）
    return True


def render_fallback_minimal():
    """降级：若完整构造失败，逐页构造典型控件截图。"""
    from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit, QListWidget, QFrame, QProgressBar)
    import theme

    app = QApplication([])
    app.setStyle("Fusion")

    def make_page(title, sub, accent, mode):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 22, 28, 22)
        t = QLabel(title); t.setObjectName("pageTitle")
        s = QLabel(sub); s.setObjectName("pageSub")
        lay.addWidget(t); lay.addWidget(s); lay.addSpacing(8)
        ed = QLineEdit(); lay.addWidget(ed)
        row = QHBoxLayout()
        b1 = QPushButton("主操作"); b1.setObjectName("accent")
        b2 = QPushButton("次要"); b2.setObjectName("ghost")
        row.addWidget(b1); row.addWidget(b2)
        lay.addLayout(row)
        lw = QListWidget()
        for x in ["示例条目 A", "示例条目 B", "示例条目 C"]:
            lw.addItem(x)
        lay.addWidget(lw)
        bar = QProgressBar(); bar.setValue(55); lay.addWidget(bar)
        w.setStyleSheet(theme.build_qss(accent, mode))
        return w

    for accent, mode in COMBOS:
        for page, (tt, ss) in {
            "links": ("批量链接处理", "从聊天记录粘贴 Booth 链接，自动剔除杂音并批量归档"),
            "drag": ("拖拽分类", "拖入文件或文件夹，自动提取七位 ID 反查归档"),
            "search": ("实验检索", "输入文件名或关键词，自动检索 Booth 并匹配"),
            "audit": ("目录巡检", "巡检 BOOTH 库的三件套完整性与命名规范"),
            "settings": ("设置", "主题、归档路径与网络"),
        }.items():
            w = make_page(tt, ss, accent, mode)
            w.show()
            app.processEvents(); w.repaint()
            pix = w.grab()
            name = f"{accent}_{mode}_{page}.png"
            path = os.path.join(OUT_DIR, name)
            if pix.save(path):
                generated.append((path, f"[降级] {accent}/{mode} · {page} 页（最小复刻）"))


def main():
    global cjk_warning
    ok_full = False
    try:
        render_full_window()
        ok_full = True
    except Exception as e:
        print("FULL WINDOW FAILED, fallback to minimal pages:")
        traceback.print_exc()
        try:
            render_fallback_minimal()
        except Exception:
            traceback.print_exc()

    # 检测 CJK 字体告警
    summary = [
        "=== BoothKeeper 视觉预览生成报告 ===",
        f"输出目录：{OUT_DIR}",
        f"模式：{'完整主窗口' if ok_full else '降级最小复刻'}",
        f"成功生成 PNG：{len(generated)} 张",
        "",
        "文件列表：",
    ]
    for p, d in generated:
        summary.append(f"  {p}  |  {d}")

    print("\n".join(summary))
    print(f"\nCJK 字体缺失告警：{'观测到（offscreen 环境预期内，不影响布局与配色判断）' if cjk_warning else '未捕获（或已被 QT_LOGGING_RULES 抑制）'}")
    print("DONE")


if __name__ == "__main__":
    main()
