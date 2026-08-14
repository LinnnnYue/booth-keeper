# pages/notify.py — 主题化弹窗（替换 OS 原生 QMessageBox）
# 根因：QMessageBox.information 是 OS 原生对话框（Windows 上是黑底黑字黑框），不跟 QSS，
# 主上 R6 反馈「未从文本中识别到 ...」 提示框黑底黑字看不清。
# 修复：自建 QDialog 套主题 QSS，沿用 theme.build_theme 模板的 SURFACE/BG/TEXT/ACCENT。
# 提供四个静态方法：information / warning / confirmation / ask（ask 返回 bool）。
import theme
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QSize

# 当前主题/模式（main_window.apply_theme 调用时刷新）
_CURRENT_TN = "zhuyin"
_CURRENT_MODE = "light"


def set_current_theme(tn: str, mode: str):
    """main_window.apply_theme 调用此函数刷新全局当前主题，让 ThemeDialog 选用对的色板。"""
    global _CURRENT_TN, _CURRENT_MODE
    _CURRENT_TN = tn
    _CURRENT_MODE = mode


class ThemeDialog(QDialog):
    """应用主题色的弹窗，无 OS 原生干扰。

    用法：
        ThemeDialog.information(parent, "提示", "...")
        ThemeDialog.warning(parent, "警告", "...")
        if ThemeDialog.confirmation(parent, "确认", "..."): ...
    """

    LV_KIND = ("info", "warn", "error", "ask")

    def __init__(self, parent, title: str, body: str, kind: str = "info",
                 buttons: list[str] | None = None, default: str = ""):
        super().__init__(parent)
        self.parsed_kind = kind if kind in self.LV_KIND else "info"
        self.setObjectName("themeDialog")
        self.setWindowTitle(title)
        # 无标题栏系统菜单/无 maxmin，仅保留关闭
        self.setWindowFlags(self.windowFlags() | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setMaximumWidth(620)

        self._build(title, body, buttons or self._default_buttons(kind), default)
        self._polish()
        # 入场动画（轻轻的 0.18s 透明度淡入，主题化点睛）
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._anim = anim

    def _default_buttons(self, kind: str) -> list[str]:
        if kind in ("info", "warn", "error"):
            return ["OK"]
        if kind == "ask":
            return ["取消", "确定"]
        return ["OK"]

    def _build(self, title: str, body: str, buttons: list[str], default: str):
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 18)
        v.setSpacing(14)

        # 顶规条：4px accent
        head = QLabel(f"  {title}")
        head.setObjectName("dlgTitle")
        v.addWidget(head)

        # 主信息区
        body_lbl = QLabel(body)
        body_lbl.setObjectName("dlgBody")
        body_lbl.setWordWrap(True)
        body_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(body_lbl)

        # 按钮行
        self.btns = []
        h = QHBoxLayout()
        h.setSpacing(8)
        h.addStretch(1)
        for b in buttons:
            btn = QPushButton(b)
            obj = "accent" if b in ("确定", "OK", "是") else "secondary"
            btn.setObjectName(obj)
            btn.setFixedHeight(34)
            btn.setMinimumWidth(80)
            btn.clicked.connect(lambda _, name=b: self._on_click(name))
            self.btns.append(btn)
            h.addWidget(btn)
        v.addLayout(h)

        # 默认聚焦
        if default and default in buttons:
            pass
        self._btn_names = list(buttons)
        self._result = None

    def _on_click(self, name: str):
        self._result = name
        self.accept()

    # ---- 静态工厂 ----
    @staticmethod
    def information(parent, title: str, body: str):
        d = ThemeDialog(parent, title, body, kind="info")
        d.exec()
        return d._result

    @staticmethod
    def warning(parent, title: str, body: str):
        d = ThemeDialog(parent, title, body, kind="warn")
        d.exec()
        return d._result

    @staticmethod
    def confirmation(parent, title: str, body: str) -> bool:
        """返回 True=用户点「确定」，False=「取消」/关闭。"""
        d = ThemeDialog(parent, title, body, kind="ask")
        d.exec()
        return d._result == "确定"

    @staticmethod
    def error(parent, title: str, body: str):
        d = ThemeDialog(parent, title, body, kind="error")
        d.exec()
        return d._result

    # ---- 样式与父级同步 ----
    def _polish(self):
        """注入主题 QSS（仅针对本控件，不污染全局）。

        颜色从 theme.THEMES[当前主题][当前模式] 取，跟随主窗状态。
        """
        global _CURRENT_TN, _CURRENT_MODE
        pal = theme.THEMES.get(_CURRENT_TN, theme.THEMES["zhuyin"]).get(_CURRENT_MODE, theme.THEMES[_CURRENT_TN]["light"])
        accent = pal["accent"]
        accent_deep = pal["accent_deep"]
        bg = pal["surface"]
        text = pal["text"]
        sub = pal["text2"]
        border = pal["border"]
        accent = pal["accent"]
        accent_deep = pal["accent_deep"]
        bg = pal["surface"]
        text = pal["text"]
        sub = pal["text2"]
        border = pal["border"]
        css = f"""
            QDialog#themeDialog {{
                background-color: {bg};
                border: 1.5px solid {accent_deep};
                border-top: 3px solid {accent};
                border-radius: 2px;
            }}
            QLabel#dlgTitle {{
                color: {text};
                font-family: {theme.SERIF};
                font-size: 14px;
                font-weight: 700;
                padding: 4px 0 6px 0;
                border-bottom: 1px solid {border};
            }}
            QLabel#dlgBody {{
                color: {text};
                font-family: {theme.SANS};
                font-size: 13px;
                line-height: 1.55;
                padding: 4px 0 4px 0;
            }}
        """
        self.setStyleSheet(css)
