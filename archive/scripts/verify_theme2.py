# verify_theme2.py — BoothKeeper 主题制验证 + 预览生成（临时脚本）
#
# 验证：三主题 × 明暗六套 build_theme 全调用无异常；构造完整 MainWindow，
#       逐主题切换 + 逐页抓图，确认可运行、可渲染。
# 生成 preview2/ 下三主题代表态（鎏金默认深玄）五页截图，供主上审美拍板。
#
# 运行（托管 Python，必须 offscreen）：
#   QT_QPA_PLATFORM=offscreen <managed python> verify_theme2.py

import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")

ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, "preview2")
os.makedirs(OUT_DIR, exist_ok=True)

PAGES = ["links", "drag", "search", "audit", "settings"]
generated = []


def populate_samples(win):
    """往各页填充纯 UI 示例数据（不触发网络）。"""
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
            for txt in [
                "3290806 · GoGo Loco   [完整]",
                "2222222 · Kirisame Ver3.0   [缺封面]",
                "1111111 · Sample Pack   [完整]",
            ]:
                ap.list_scan.addItem(txt)
            for txt in ["2222222 · Kirisame Ver3.0   本地 2.0 → 官方 3.1  可更新"]:
                ap.list_ver.addItem(txt)
            ap.lbl_stat.setText("共 3 件，1 件缺失三件套")
            ap.bar.setValue(100)
    except Exception:
        pass


def main():
    import theme
    from PySide6.QtWidgets import QApplication
    from main_window import BoothKeeper

    # 1) 六套 build_theme 调用验证
    for n in theme.THEME_NAMES:
        for m in ("light", "dark"):
            q = theme.build_theme(n, m)
            assert q and "{" in q, (n, m)
    print("BUILD_THEME_6_OK")

    # 2) 构造完整主窗口 + 逐主题切换 + 逐页抓图
    app = QApplication([])
    app.setStyle("Fusion")
    win = BoothKeeper()
    win.show()
    app.processEvents()
    populate_samples(win)

    combos = [(n, m) for n in theme.THEME_NAMES for m in ("light", "dark")]
    for t, m in combos:
        win.config["theme"] = t
        win.config["mode"] = m
        win.apply_theme()
        app.processEvents()
        try:
            win.pages.get("settings").mark_theme()
        except Exception:
            pass
        for page in PAGES:
            win.switch_page(page)
            app.processEvents()
            win.repaint()
            pix = win.grab()
            name = f"{t}_{m}_{page}.png"
            path = os.path.join(OUT_DIR, name)
            if pix.save(path):
                generated.append((path, f"{theme.THEME_NAMES[t]} · {m} · {page} 页"))
            else:
                print("WARN save failed", path)

    print(f"PREVIEW_GENERATED {len(generated)}")
    for p, d in generated:
        print("  ", p, "|", d)
    print("DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        print("FAILED")
