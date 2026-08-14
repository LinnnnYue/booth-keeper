# pages/dragdrop_page.py — 拖拽文件识别分类
import re
from pathlib import Path
from PySide6.QtWidgets import (QFrame, QListWidget, QLabel, QPushButton, QHBoxLayout,
    QProgressBar, QVBoxLayout, QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, QThread, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from pages.base import BasePage
from pages.notify import ThemeDialog
import theme
import booth_core as bc
from archive_util import archive_item

ID_RE = re.compile(r"(?<!\d)(\d{7})(?!\d)")


class DropFrame(QFrame):
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(132)
        self.setObjectName("drop")
        self._tn = theme.DEFAULT_THEME
        self._mode = theme.DEFAULT_MODE
        self._motif = None
        lay = QVBoxLayout(self)
        self.hint = QLabel("拖入文件或文件夹到此区域\n将自动提取名称中的七位 Booth ID 并反查归档")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setObjectName("muted")
        lay.addWidget(self.hint)

        # 麻叶纹背景层（QLabel 垫底层，拖入时提亮）
        # 拖入态高亮层（脉冲淡入淡出，替代 CSS @keyframes —— Qt6 QSS 不支持动画）
        self._glow = QLabel(self)
        self._glow.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._glow.lower()
        self._glow.hide()
        self._eff = QGraphicsOpacityEffect(self._glow)
        self._eff.setOpacity(0.0)
        self._glow.setGraphicsEffect(self._eff)
        self._anim = QPropertyAnimation(self._eff, b"opacity")
        self._anim.setDuration(1000)
        self._anim.setLoopCount(-1)
        self._anim.setKeyValueAt(0.0, 0.12)
        self._anim.setKeyValueAt(0.5, 0.5)
        self._anim.setKeyValueAt(1.0, 0.12)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)

    def set_motif(self, theme_name, mode, hi=False):
        """初始化/切换主题：建麻叶背景层 + 同步高亮层底色。"""
        self._tn, self._mode = theme_name, mode
        pal = theme.THEMES[theme_name][mode]
        self._glow.setStyleSheet(f"background-color: {pal['accent_light']};")
        self._resize_glow()
        if self._motif is None:
            self._motif = theme.MotifBackdrop(
                self, svg=theme.motif_drop_raw(theme_name, mode, hi=hi),
                tile=True, tw=28, th=28)
        else:
            self._motif.set_motif(theme.motif_drop_raw(theme_name, mode, hi=hi))

    def _resize_glow(self):
        self._glow.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._resize_glow()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            self._set_drag(True)
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            self._set_drag(True)
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._set_drag(False)

    def dropEvent(self, e: QDropEvent):
        self._set_drag(False)
        paths = [u.toLocalFile() for u in e.mimeData().urls()]
        self.files_dropped.emit(paths)
        e.acceptProposedAction()

    def _set_drag(self, on: bool):
        """拖入态切换：点亮金线 + 提亮麻叶纹 + 脉冲高亮（QSS #drop[drag=1] 触发）。"""
        self.setProperty("drag", "1" if on else "0")
        self.style().unpolish(self)
        self.style().polish(self)
        if self._motif is not None:
            self._motif.set_motif(theme.motif_drop_raw(self._tn, self._mode, hi=on))
        if on:
            self._glow.show()
            if self._anim.state() != QPropertyAnimation.Running:
                self._anim.start()
        else:
            self._anim.stop()
            self._eff.setOpacity(0.0)
            self._glow.hide()


class DragWorker(QThread):
    item_done = Signal(dict)
    finished = Signal()

    def __init__(self, jobs, root, proxy, proxy_url, cookie):
        super().__init__()
        self.jobs = jobs
        self.root = root
        self.proxy = proxy
        self.proxy_url = proxy_url
        self.cookie = cookie

    def run(self):
        s = bc.make_session(self.cookie)
        if self.proxy:
            s.proxies.update({"http": self.proxy_url, "https": self.proxy_url})
        for path, iid in self.jobs:
            r = archive_item(iid, self.root, s, move_source=path, force=False)
            r["path"] = path
            self.item_done.emit(r)
        self.finished.emit()


class DragDropPage(BasePage):
    def __init__(self, main):
        super().__init__(main)
        self.header("拖拽分类", "拖入文件或文件夹，自动提取七位 ID 反查归档；缺 ID 则提示补名后重拖")
        self.worker = None
        self.pending = []

        self.drop = DropFrame()
        self.drop.files_dropped.connect(self.on_drop)
        self.root.addWidget(self.drop)

        self.lbl_no = QLabel("缺少 ID 的文件（请补名后重新拖入）：")
        self.lbl_no.setObjectName("pageSub")
        self.root.addWidget(self.lbl_no)
        self.no_list = QListWidget()
        self.no_list.setMaximumHeight(84)
        self.root.addWidget(self.no_list)

        self.lbl_q = QLabel("待归档队列：")
        self.lbl_q.setObjectName("pageSub")
        self.root.addWidget(self.lbl_q)
        self.queue = QListWidget()
        self.queue.setMinimumHeight(150)
        self.root.addWidget(self.queue)

        self.bar = QProgressBar()
        self.root.addWidget(self.bar)

        row = QHBoxLayout()
        self.btn_run = QPushButton("开始归档")
        self.btn_run.setObjectName("accent")
        self.btn_run.clicked.connect(self.start)
        self.btn_run.setEnabled(False)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setObjectName("secondary")
        self.btn_clear.clicked.connect(self.clear_all)
        row.addWidget(self.btn_run)
        row.addWidget(self.btn_clear)
        row.addStretch(1)
        self.root.addLayout(row)
        self.spacer()

    def on_theme(self, tn, mode):
        self.drop.set_motif(tn, mode)

    def on_drop(self, paths):
        for p in paths:
            name = Path(p).name
            m = ID_RE.search(name)
            if m:
                self.pending.append((p, m.group(1)))
                self.queue.addItem(f"{m.group(1)} · {name}")
            else:
                self.no_list.addItem(name)
        self.btn_run.setEnabled(len(self.pending) > 0)
        if paths:
            self.main.set_status(
                f"已识别 {len(self.pending)} 个含 ID，{self.no_list.count()} 个缺 ID")

    def clear_all(self):
        self.pending = []
        self.queue.clear()
        self.no_list.clear()
        self.btn_run.setEnabled(False)
        self.bar.setValue(0)

    def start(self):
        if not self.pending:
            return
        cfg = self.main.config
        self.queue.clear()
        self.bar.setValue(0)
        self.btn_run.setEnabled(False)
        self.worker = DragWorker(
            self.pending, cfg["booth_root"], cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.worker.item_done.connect(self.on_done)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_done(self, r):
        iid = r.get("id")
        name = r.get("name") or Path(r.get("path", "")).name
        if r["status"] == "ok":
            self.queue.addItem(f"{iid} · {name}  →  {r.get('cat', '')}")
        elif r["status"] == "mismatch":
            # R7+1 错位 dialog：明确「已在 X 类目 / 官方是 Y」
            wrong = r.get("wrong_cat", "")
            dest_cat = r.get("dest_cat", "")
            msg = (
                f"{iid} · {name}\n"
                f"当前所在：{wrong}\n"
                f"官方分类：{dest_cat}\n"
                f"（类目可能错位，是否清掉旧目录并重新归档到「{dest_cat}」？）\n\n"
                f"（点取消则跳过该项）"
            )
            if ThemeDialog.confirmation(self, "类目错位", msg):
                self._force_redo(iid, r.get("wrong_path", ""))
            else:
                self.queue.addItem(f"{iid} · {name}  错位跳过：{wrong} → 期望 {dest_cat}")
        elif r["status"] == "exists":
            # R7+1 强化：dialog 文案显式说出「当前分类」+「官方分类」，避免主上疑惑
            existing_cat = r.get("cat", "")
            cur_cat = r.get("dest_cat", existing_cat)
            if cur_cat and cur_cat != existing_cat:
                msg = (
                    f"{iid} · {name}\n"
                    f"当前所在：{existing_cat}\n"
                    f"官方分类：{cur_cat}\n"
                    f"（类目可能错位，是否清掉旧目录并重新归档到「{cur_cat}」？）\n\n"
                    f"（点取消则跳过该项）"
                )
            else:
                msg = (
                    f"{iid} · {name}\n"
                    f"已在「{existing_cat}」类别下。\n"
                    f"是否清掉旧目录并重新归档到当前分类？\n\n"
                    f"（点取消则跳过该项）"
                )
            if ThemeDialog.confirmation(self, "已归档", msg):
                self._force_redo(iid, r.get("path", ""))
            else:
                self.queue.addItem(f"{iid} · {name}  已存在，跳过")
        elif r["status"] == "warn":
            self.queue.addItem(f"{iid} · {name}  已存在，跳过")
        else:
            self.queue.addItem(f"{iid}  ✕  {r.get('msg', '')}")
        total = len(self.pending) or 1
        self.bar.setValue(int(self.queue.count() / total * 100))

    def _force_redo(self, iid: str, source_path: str):
        """强制重归档：单件重跑 archive_item(force=True)，同步 push 进度到队列。"""
        cfg = self.main.config
        s = bc.make_session(cfg["cookie"])
        if cfg["proxy"]:
            s.proxies.update({"http": cfg["proxy_url"], "https": cfg["proxy_url"]})
        r = archive_item(iid, cfg["booth_root"], s, move_source=source_path, force=True)
        name = r.get("name") or Path(source_path).name
        if r["status"] == "ok":
            self.queue.addItem(f"{iid} · {name}  →  {r.get('cat', '')}  [重归档]")
        elif r["status"] == "err":
            self.queue.addItem(f"{iid} · {name}  ✕  重归档失败:{r.get('msg', '')}")
        else:
            self.queue.addItem(f"{iid} · {name}  ✕  {r.get('msg', '')}")

    def on_finished(self):
        self.btn_run.setEnabled(True)
        self.main.set_status(f"归档完成：{self.queue.count()} 项")
