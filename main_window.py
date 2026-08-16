# main_window.py — Booth Keeper 主窗口框架
import sys
import json
from pathlib import Path
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QLabel, QPushButton, QStatusBar, QApplication)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QPainter, QColor, QPalette, QPixmap, QBrush, QIcon
from PySide6.QtSvg import QSvgRenderer
import theme
from pages.links_page import LinksPage
from pages.dragdrop_page import DragDropPage
from pages.search_page import SearchPage
from pages.audit_page import AuditPage
from pages.settings_page import SettingsPage

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONFIG_PATH = Path.home() / ".boothkeeper.json"
try:
    from _version import __version__  # type: ignore
except Exception:
    __version__ = "1.1.0"

DEFAULT_CONFIG = {
    "theme": theme.DEFAULT_THEME,
    "booth_root": r"G:\Lin_File\BOOTH",
    "proxy": True,
    "proxy_url": "http://127.0.0.1:20122/",
    "auto_check_update": True,  # R10：启动时自动检查更新
    "cookie": "",
}

NAV = [
    ("links", "批量链接"),
    ("drag", "拖拽分类"),
    ("search", "实验检索"),
    ("audit", "目录巡检"),
    ("settings", "设置"),
]


class NavButton(QPushButton):
    def __init__(self, key, label, parent=None):
        super().__init__(label, parent)
        self.key = key
        self.setFixedHeight(42)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("active", False)

    def set_active(self, on: bool):
        self.setProperty("active", on)
        self.style().unpolish(self)
        self.style().polish(self)


class RootWidget(QWidget):
    """根容器：用底层 QLabel 承载合成 pixmap（釉底+金缮脉络），lower() 至最底。
    QLabel 是真子部件，pixmap 必渲染——离屏/真机通吃，绕开 QSS 吞 paintEvent 的陷阱。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("root")
        # 底层背景标签：承载釉底+金缮脉络合成图，置于所有子部件之下、不拦鼠标
        self._bg = QLabel(self)
        self._bg.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._bg.lower()
        self._hex = "#F4F1EA"
        self._svg = ""

    def set_theme_bg(self, hex_color: str, svg_str: str):
        self._hex = hex_color or "#F4F1EA"
        self._svg = svg_str or ""
        self._compose()

    def _compose(self):
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0 or not self._svg:
            self._bg.clear()
            return
        pix = QPixmap(w, h)
        pix.fill(QColor(self._hex))
        pp = QPainter(pix)
        r = QSvgRenderer(self._svg.encode("utf-8"))
        if r.isValid():
            r.render(pp, pix.rect())
        pp.end()
        self._bg.setPixmap(pix)
        self._bg.setGeometry(0, 0, w, h)
        self._bg.lower()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._compose()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._compose()


class BoothKeeper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Booth Keeper v{__version__}")
        self.resize(1080, 700)
        self.config = self.load_config()
        self.pages = {}
        self.build_ui()
        self.apply_theme()
        self.switch_page("links")
        # R10：启动后自动检查更新（延迟 2s 避免阻塞 UI）
        if self.config.get("auto_check_update", True):
            QTimer.singleShot(2000, self.auto_check_update)

    def auto_check_update(self):
        """启动时自动检查更新。检测到新版弹主题化主题对话框。"""
        try:
            from pages import updater
            info = updater.check_update(proxy=self.config.get("proxy", False))
            if info.get("error"):
                return  # 静默失败，不打扰用户
            if info["has_update"]:
                # 延迟到主窗口 ready 后再弹
                QTimer.singleShot(0, lambda: self._show_update_dialog(info))
        except Exception:
            pass

    def _show_update_dialog(self, info):
        msg = (
            f"🎉 发现新版本！\n\n"
            f"  当前版本：{info['local']}\n"
            f"  最新版本：{info['remote']}\n\n"
            f"点「确定」前往 GitHub Release 下载（Windows 安装包 / zip 便携版）。\n\n"
            f"安装包升级时会自动关闭旧进程，无需手动退出。")
        if ThemeDialog.confirmation(self, "有新版本可用", msg):
            from pages import updater
            updater.open_release_page()

    # ---- 配置 ----
    def load_config(self):
        cfg = dict(DEFAULT_CONFIG)
        try:
            if CONFIG_PATH.exists():
                cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
        cfg.setdefault("theme", theme.DEFAULT_THEME)
        # 防御：清理旧「七色 accent」版本残留字段；mode 非法则回退 light
        cfg.pop("accent", None)  # 旧版 accent 名（teal 等）已废弃
        if cfg.get("mode") not in ("light", "dark"):
            cfg.pop("mode", None)
        return cfg

    def save_config(self):
        CONFIG_PATH.write_text(
            json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- UI ----
    def build_ui(self):
        root = RootWidget()
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setSpacing(0)
        h.setContentsMargins(0, 0, 0, 0)

        # 侧边栏
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        # R6 修复：172 → 196（原 172 + 24），保证「Booth Keeper」完整显字不截断
        self.sidebar.setFixedWidth(196)
        sv = QVBoxLayout(self.sidebar)
        sv.setContentsMargins(14, 18, 14, 14)
        sv.setSpacing(4)
        # 品牌行：品牌名 + 阴阳师印章（几何「守」印面，不依赖 CJK 字体）
        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        brand = QLabel("Booth Keeper")
        brand.setObjectName("pageTitle")
        # R6 修复：原 16px → 14px（保证 196px 侧栏内不截断）
        brand.setStyleSheet("font-size:14px;")
        brand.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.brand_seal = QLabel()
        # R6 修复：原 34 → 28（小一点让位品牌文字）
        self.brand_seal.setFixedSize(28, 28)
        self.brand_seal.setAlignment(Qt.AlignCenter)
        brand_row.addWidget(brand)
        brand_row.addStretch(1)
        brand_row.addWidget(self.brand_seal)
        sv.addLayout(brand_row)
        sub = QLabel("展位守护者")
        sub.setObjectName("brandSub")
        sub.setStyleSheet("font-size:11px;")
        sv.addWidget(sub)
        sv.addSpacing(12)
        self.nav_btns = {}
        for key, label in NAV:
            b = NavButton(key, label)
            b.clicked.connect(lambda _, k=key: self.switch_page(k))
            self.nav_btns[key] = b
            sv.addWidget(b)
        sv.addStretch(1)
        # 主题切换（中式主题名循环）
        self.theme_btn = QPushButton("主題 · " + theme.THEME_NAMES[self.config["theme"]])
        self.theme_btn.setObjectName("ghost")
        self.theme_btn.clicked.connect(self.cycle_theme)
        sv.addWidget(self.theme_btn)
        # 明暗切换（太极图标 + 明/暗），阴阳即明暗
        self.mode_btn = QPushButton()
        self.mode_btn.setObjectName("ghost")
        self.mode_btn.setFixedHeight(36)
        self.mode_btn.clicked.connect(self.toggle_mode)
        sv.addWidget(self.mode_btn)
        h.addWidget(self.sidebar)

        # 侧栏纹样背景层（QLabel 垫底层，三主题差异化：金缮青海波/朱印回字纹/古纹叶脉）
        self.sidebar_motif = theme.MotifBackdrop(
            self.sidebar, svg="", tile=True, tw=72, th=720, vw=72)

        # 内容区
        self.stack = QStackedWidget()
        self.pages["links"] = LinksPage(self)
        self.pages["drag"] = DragDropPage(self)
        self.pages["search"] = SearchPage(self)
        self.pages["audit"] = AuditPage(self)
        self.pages["settings"] = SettingsPage(self)
        for p in self.pages.values():
            self.stack.addWidget(p)
        h.addWidget(self.stack, 1)

        self.setStatusBar(QStatusBar())
        self.set_status("就绪")

    def switch_page(self, key):
        if key in self.pages:
            self.stack.setCurrentWidget(self.pages[key])
            for k, b in self.nav_btns.items():
                b.set_active(k == key)

    def cycle_theme(self):
        order = list(theme.THEME_NAMES.keys())
        cur = self.config.get("theme", theme.DEFAULT_THEME)
        nxt = order[(order.index(cur) + 1) % len(order)]
        self.config["theme"] = nxt
        self.save_config()
        self.apply_theme()

    def toggle_mode(self):
        """明暗切换（太极即阴阳）。"""
        cur = self.config.get("mode") or theme.DEFAULT_MODE_PER_THEME[self.config["theme"]]
        nxt = "dark" if cur == "light" else "light"
        self.config["mode"] = nxt
        self.save_config()
        self.apply_theme()
        self.set_status("明暗已切换：" + ("亮色" if nxt == "light" else "深色"))

    def _taiji_icon(self, accent: str, bg: str) -> QIcon:
        """渲染太极 SVG 为 QIcon（明暗切换按钮）。"""
        svg = theme.taiji_svg_raw(accent, bg)
        r = QSvgRenderer(svg.encode("utf-8"))
        pm = QPixmap(40, 40)
        pm.fill(QColor(0, 0, 0, 0))
        if r.isValid():
            p = QPainter(pm)
            r.render(p, pm.rect())
            p.end()
        return QIcon(pm)

    def _seal_label(self, accent: str):
        """渲染阴阳师印章 SVG 为 QLabel pixmap（品牌点睛，几何「守」印面）。"""
        svg = theme.seal_svg(accent)
        r = QSvgRenderer(svg.encode("utf-8"))
        # R6 修复：与 brand_seal 固定尺寸保持一致（28×28）
        pm = QPixmap(28, 28)
        pm.fill(QColor(0, 0, 0, 0))
        if r.isValid():
            p = QPainter(pm)
            r.render(p, pm.rect())
            p.end()
        self.brand_seal.setPixmap(pm)

    def apply_theme(self):
        tn = self.config["theme"]
        mode = self.config.get("mode") or theme.DEFAULT_MODE_PER_THEME[tn]
        # 关键修复：必须用【全局】QApplication.setStyleSheet，而非 self.setStyleSheet（窗口级）。
        # 窗口级样式表无法稳定传播到 QStackedWidget 内的页按钮（实测 accent 按钮退化为默认灰），
        # 主上所见「白字无边框」即此根因。全局样式表层级最高、必达全部控件。
        app = QApplication.instance()
        app.setStyleSheet(theme.build_theme(tn, mode))
        # 同步主题状态到通知模块（ThemeDialog 据此选色板）
        from pages.notify import set_current_theme
        set_current_theme(tn, mode)
        for w in [self] + list(self.pages.values()):
            w.style().unpolish(w)
            w.style().polish(w)
        # 同步根容器：釉底 + 主题背景纹路 SVG（底层 QLabel，离屏/真机皆渲染）
        pal = theme.THEMES[tn][mode]
        root = self.centralWidget()
        if isinstance(root, RootWidget):
            root.set_theme_bg(pal["bg"], theme.motif_bg_svg(tn, mode))
        # 侧栏纹样（三主题差异化）
        if getattr(self, "sidebar_motif", None) is not None:
            self.sidebar_motif.set_motif(theme.motif_sidebar_raw(tn, mode))
        # 各页纹样（雷纹分隔 / 麻叶拖入区 / 拖入动画）随主题刷新
        for p in self.pages.values():
            if hasattr(p, "refresh_motifs"):
                p.refresh_motifs(tn, mode)
            if hasattr(p, "on_theme"):
                p.on_theme(tn, mode)
        # 侧栏按钮
        self.theme_btn.setText("主題 · " + theme.THEME_NAMES[tn])
        self.mode_btn.setIcon(self._taiji_icon(pal["accent"], pal["bg"]))
        self.mode_btn.setIconSize(QSize(20, 20))
        self.mode_btn.setText(("　明" if mode == "light" else "　暗"))
        # 品牌印章随主题刷新
        self._seal_label(pal["accent"])

    def set_status(self, msg):
        self.statusBar().showMessage(msg)
