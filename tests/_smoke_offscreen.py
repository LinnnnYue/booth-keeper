"""离屏冒烟：验证拆分 + diag 通道后主窗口可正常构建（不写用户配置）。

用法：
    QT_QPA_PLATFORM=offscreen python tests/_smoke_offscreen.py

纪律：不调用任何 `_autosave()` / 设置页写盘路径，避免污染 `~/.boothkeeper.json`。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    import main_window
    import diag

    w = main_window.BoothKeeper()
    pages = list(w.pages.keys()) if hasattr(w, "pages") else []
    print("title      =", w.windowTitle())
    print("pages      =", pages)
    print("diag_btn   =", hasattr(w, "diag_btn"))
    print("diag_panel =", getattr(w, "_diag_panel", None) is not None)

    # 诊断通道：sink 收报 + 环形缓冲
    got = []
    diag.set_sink(lambda rec: got.append(rec))
    diag.warn("冒烟：告警级", scope="smoke")
    diag.error("冒烟：错误级", scope="smoke")
    diag.info("冒烟：信息级", scope="smoke")
    print("sink 收到  =", len(got), [r["level"] for r in got])
    print("缓冲条数   =", len(diag.recent(100)))
    diag.set_sink(None)

    # 面板构建（不写盘）
    w.show_diag_panel()
    panel = getattr(w, "_diag_panel", None)
    print("面板可见   =", panel is not None and panel.isVisible())
    print("面板行数   =", panel.row_count() if panel is not None and hasattr(panel, "row_count") else "n/a")
    del app
    return 0


if __name__ == "__main__":
    sys.exit(main())
