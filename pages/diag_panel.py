# pages/diag_panel.py — 诊断日志面板
# 背景：打包后 stdout 不可见，后台异常需要可见出口（详见 02-遗留项处置.md §2.1）。
# 本面板是 diag 通道的 GUI 接收端之一：状态栏显示摘要，本面板提供完整回溯。
#
# 设计要点：
#   - 非模态：用户开着面板继续操作，新记录实时追加（archiving 过程中最需要这个）
#   - 级别筛选用分段按钮（模式选择的标准控件形态），不用下拉框
#   - 着色从 theme.THEMES 当前色板取，随主窗主题切换刷新
import html
import time

import theme
import diag
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QPlainTextEdit, QWidget)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor

_FILTERS = (("全部", None), ("警告", "warn"), ("错误", "error"))


class DiagPanel(QDialog):
    """诊断日志面板。由主窗口持有单例，点击状态栏按钮显示。"""

    cleared = Signal()  # 用户点了「清空」→ 主窗口据此重置未查看计数

    def __init__(self, parent=None, tn: str = None, mode: str = None):
        super().__init__(parent)
        self.setObjectName("diagPanel")
        self.setWindowTitle("诊断日志")
        self.setWindowFlags(self.windowFlags() | Qt.WindowTitleHint
                            | Qt.WindowCloseButtonHint | Qt.WindowMinMaxButtonsHint)
        self.setModal(False)
        self.resize(760, 460)
        self._tn = tn or theme.DEFAULT_THEME
        self._mode = mode or theme.DEFAULT_MODE
        self._filter = None
        self._btns = {}
        self._build()
        self.reload()

    # ---- 构建 ----
    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(10)

        head = QLabel("  诊断日志")
        head.setObjectName("dlgTitle")
        v.addWidget(head)

        # 工具行：级别分段 + 计数 + 清空
        tools = QHBoxLayout()
        tools.setSpacing(6)
        for label, key in _FILTERS:
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.setMinimumWidth(60)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, k=key: self._set_filter(k))
            self._btns[key] = b
            tools.addWidget(b)
        self.counter = QLabel("")
        self.counter.setObjectName("diagCounter")
        tools.addSpacing(8)
        tools.addWidget(self.counter)
        tools.addStretch(1)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setObjectName("ghost")
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.clicked.connect(self._clear)
        tools.addWidget(self.clear_btn)
        v.addLayout(tools)

        self.log = QPlainTextEdit()
        self.log.setObjectName("diagLog")
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.NoWrap)
        f = QFont()
        f.setFamilies(["JetBrains Mono", "Cascadia Code", "Sarasa Mono SC", "Consolas"])
        f.setPointSize(9)
        self.log.setFont(f)
        v.addWidget(self.log, 1)

        foot = QHBoxLayout()
        foot.addStretch(1)
        close = QPushButton("关闭")
        close.setObjectName("secondary")
        close.setFixedHeight(32)
        close.setMinimumWidth(80)
        close.clicked.connect(self.hide)
        foot.addWidget(close)
        v.addLayout(foot)

        self._polish()
        self._sync_buttons()

    # ---- 数据 ----
    def reload(self):
        """从环形缓冲整体重绘（打开面板或清空后调用）。"""
        self.log.clear()
        for rec in diag.recent(0, self._filter):
            self._append_row(rec, scroll=False)
        self._move_to_end()
        self._update_counter()

    def append(self, record: dict):
        """实时追加一条（由主窗口在收到 diag 记录时调用）。"""
        if self._filter and record["level"] != self._filter:
            self._update_counter()
            return
        at_end = self._at_end()
        self._append_row(record, scroll=at_end)
        self._update_counter()

    def refresh_theme(self, tn: str, mode: str):
        """主窗切换主题时刷新配色（不重绘内容，只改样式与已有行的颜色→整体重载更简单）。"""
        self._tn = tn
        self._mode = mode
        self._polish()
        self.reload()

    # ---- 内部 ----
    def _pal(self) -> dict:
        themes = theme.THEMES
        return themes.get(self._tn, themes[theme.DEFAULT_THEME]).get(
            self._mode, themes[theme.DEFAULT_THEME]["light"])

    def _polish(self):
        pal = self._pal()
        css = f"""
            QDialog#diagPanel {{
                background-color: {pal['surface']};
                border-top: 3px solid {pal['accent']};
            }}
            QPlainTextEdit#diagLog {{
                background-color: {pal['input_bg']};
                border: 1px solid {pal['border']};
                border-radius: 2px;
                padding: 6px;
                selection-background-color: {pal['sel_bg']};
                selection-color: {pal['sel_text']};
            }}
            QLabel#diagCounter {{
                color: {pal['text3']};
                font-size: 12px;
            }}
        """
        self.setStyleSheet(css)

    def _colors(self, level: str) -> str:
        pal = self._pal()
        return {"error": pal["danger"], "warn": pal["warn"]}.get(level, pal["text2"])

    def _append_row(self, rec: dict, scroll: bool = True):
        ts = time.strftime("%H:%M:%S", time.localtime(rec["ts"]))
        tag = {"error": "ERR ", "warn": "WARN", "info": "INFO"}.get(rec["level"], "INFO")
        scope = f"[{rec['scope']}] " if rec.get("scope") else ""
        ctx = rec.get("ctx") or {}
        suffix = ("  " + " ".join(f"{k}={v}" for k, v in ctx.items())) if ctx else ""
        color = self._colors(rec["level"])
        pal = self._pal()
        row = (f'<span style="color:{pal["text3"]}">{ts}</span> '
               f'<span style="color:{color};font-weight:700">{tag}</span> '
               f'<span style="color:{pal["text"]}">{html.escape(scope)}{html.escape(rec["msg"])}</span>'
               f'<span style="color:{pal["text3"]}">{html.escape(suffix)}</span>')
        self.log.appendHtml(row)
        if scroll:
            self._move_to_end()

    def _move_to_end(self):
        self.log.moveCursor(QTextCursor.End)

    def _at_end(self) -> bool:
        bar = self.log.verticalScrollBar()
        return bar.value() >= bar.maximum() - 4

    def _set_filter(self, key):
        self._filter = key
        self._sync_buttons()
        self.reload()

    def _sync_buttons(self):
        for key, btn in self._btns.items():
            btn.setObjectName("accent" if key == self._filter else "ghost")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _clear(self):
        diag.clear()
        self.reload()
        self.cleared.emit()

    def _update_counter(self):
        n_warn = diag.count("warn")
        n_err = diag.count("error")
        total = diag.count()
        if self._filter:
            shown = len(diag.recent(0, self._filter))
            self.counter.setText(f"显示 {shown} / 共 {total} 条")
        else:
            parts = [f"共 {total} 条"]
            if n_warn:
                parts.append(f"警告 {n_warn}")
            if n_err:
                parts.append(f"错误 {n_err}")
            self.counter.setText("　".join(parts))
