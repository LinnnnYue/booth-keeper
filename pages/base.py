# pages/base.py — 页面基类
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame,
    QHBoxLayout)
from PySide6.QtCore import Qt
import theme


class BasePage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self._tn = main.config.get("theme", theme.DEFAULT_THEME)
        self._mode = (main.config.get("mode")
                      or theme.DEFAULT_MODE_PER_THEME.get(self._tn, theme.DEFAULT_MODE))
        self._motifs = []  # (MotifBackdrop, kind) 列表，随主题刷新
        # 外层滚动区域（透明视口 + 主题滚动条，小窗不裁切内容）
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        inner = QWidget()
        self.root = QVBoxLayout(inner)
        self.root.setContentsMargins(28, 22, 28, 22)
        self.root.setSpacing(14)
        self.root.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(inner)
        # 关键：滚动内容层必须透明，透出根容器(RootWidget)的釉底+脉络。
        # 必须在 setWidget 之后设置——setWidget 会把 inner 的 autoFill 重置回 True，
        # 否则 Fusion 默认窗色涂满内容区，把背景金线彻底盖死。样式兜底双保险。
        inner.setAutoFillBackground(False)
        # 注意：【绝不给 inner/scroll/viewport 设 setStyleSheet】——Qt 实测，父控件一旦拥有
        # 自己的样式表，其后代的 QPushButton#accent 等类型选择器规则会失效（被隔离出全局
        # 样式表），导致按钮退化为默认灰「白字无边框」。透出根背景纹样仅靠
        # setAutoFillBackground(False) 即可，禁止用样式表双保险。
        self.scroll.setAutoFillBackground(False)
        self.scroll.viewport().setAutoFillBackground(False)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.scroll)

    def header(self, title: str, sub: str):
        t = QLabel(title)
        t.setObjectName("pageTitle")
        s = QLabel(sub)
        s.setObjectName("pageSub")
        self.root.addWidget(t)
        self.root.addWidget(s)
        self.root.addSpacing(6)

    def spacer(self):
        self.root.addStretch(1)

    def hline(self):
        """素净分隔线：QFrame#hline（全局 QSS 细线）+ 中心 accent 小菱点（QLabel 菱形）。
        已去除原雷纹「@」母题。"""
        f = QFrame()
        f.setObjectName("hline")
        f.setFrameShape(QFrame.NoFrame)
        f.setFixedHeight(14)
        self.root.addWidget(f)
        dia = QLabel(f)
        dia.setFixedSize(14, 14)
        dia.setPixmap(theme.render_motif_pixmap(
            theme.motif_diamond_raw(self._tn, self._mode), 14, 14))
        hl = QHBoxLayout(f)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addStretch(1)
        hl.addWidget(dia)
        hl.addStretch(1)
        self._motifs.append((dia, "diamond"))

    def refresh_motifs(self, theme_name: str, mode: str):
        """切换主题时由 main_window.apply_theme 调用，重绘所有纹样背景层。"""
        self._tn, self._mode = theme_name, mode
        for bd, kind in self._motifs:
            if kind == "diamond":
                bd.setPixmap(theme.render_motif_pixmap(
                    theme.motif_diamond_raw(theme_name, mode), 14, 14))
