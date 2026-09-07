# pages/dragdrop_page.py — 拖拽文件识别分类
import re
import json
import datetime
from pathlib import Path
from PySide6.QtWidgets import (QFrame, QListWidget, QListWidgetItem, QLabel, QPushButton,
    QHBoxLayout, QProgressBar, QVBoxLayout, QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, QThread, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QColor
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
        self.pending = []          # 待归档 [(path, iid)] —— 归档成功后移除，杜绝二次归档
        self._batch = []           # 本次归档快照（进度用）
        self._done_file = Path.home() / ".boothkeeper_done.json"

        self.drop = DropFrame()
        self.drop.files_dropped.connect(self.on_drop)
        self.root.addWidget(self.drop)

        self.lbl_no = QLabel("缺少 ID 的文件（请补名后重新拖入）：")
        self.lbl_no.setObjectName("pageSub")
        self.root.addWidget(self.lbl_no)
        self.no_list = QListWidget()
        self.no_list.setMaximumHeight(84)
        self.root.addWidget(self.no_list)

        # R21（慎之勇者预案）：待归档与已归档左右分栏，视觉+逻辑彻底分开。
        # 待归档：成功/跳过项一旦处理即移出 → 不再存在「目录已存在→替换」二次归档。
        # 已归档：跨会话历史，最新在上。
        self.lbl_q = QLabel("待归档队列：")
        self.lbl_q.setObjectName("pageSub")
        self.lbl_done = QLabel("已归档（历史，最新在上）：")
        self.lbl_done.setObjectName("pageSub")
        cols = QHBoxLayout()
        left_w = QVBoxLayout()
        left_w.addWidget(self.lbl_q)
        self.queue = QListWidget()
        self.queue.setMinimumHeight(150)
        self.queue.setSelectionMode(QListWidget.ExtendedSelection)
        left_w.addWidget(self.queue)
        right_w = QVBoxLayout()
        right_w.addWidget(self.lbl_done)
        self.done_list = QListWidget()
        self.done_list.setObjectName("obs")
        self.done_list.setMinimumHeight(150)
        right_w.addWidget(self.done_list)
        cols.addLayout(left_w, 1)
        cols.addLayout(right_w, 1)
        self.root.addLayout(cols)

        self.bar = QProgressBar()
        self.root.addWidget(self.bar)

        row = QHBoxLayout()
        self.btn_run = QPushButton("开始归档")
        self.btn_run.setObjectName("accent")
        self.btn_run.clicked.connect(self.start)
        self.btn_run.setEnabled(False)
        self.btn_clear = QPushButton("清空待归档")
        self.btn_clear.setObjectName("secondary")
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_his = QPushButton("清空历史")
        self.btn_his.setObjectName("secondary")
        self.btn_his.clicked.connect(self.clear_history)
        row.addWidget(self.btn_run)
        row.addWidget(self.btn_clear)
        row.addWidget(self.btn_his)
        row.addStretch(1)
        self.root.addLayout(row)
        self.spacer()
        self._load_done()

    def _load_done(self):
        """读取跨会话已归档历史（最新在前）。"""
        try:
            data = json.loads(self._done_file.read_text(encoding="utf-8"))
            for e in data.get("entries", []):
                self.done_list.addItem(
                    f"{e.get('t','')}  {e.get('mark','')} {e.get('iid','')}"
                    f" · {e.get('name','')}  →  {e.get('cat','')}")
        except Exception:
            pass

    def _push_done(self, iid, name, cat, mark):
        """成功/跳过项入右栏并持久化（最新在上）。"""
        e = {"t": datetime.datetime.now().strftime("%m-%d %H:%M"),
             "iid": iid, "name": name, "cat": cat, "mark": mark}
        self.done_list.insertItem(
            0, f"{e['t']}  {mark} {iid} · {name}  →  {cat}")
        try:
            data = {"entries": []}
            if self._done_file.exists():
                data = json.loads(self._done_file.read_text(encoding="utf-8"))
            data.setdefault("entries", []).insert(0, e)
            data["entries"] = data["entries"][:500]
            self._done_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass

    def _remove_pending(self, p: str):
        """按 path 从待归档队列移除该项。"""
        for i in range(self.queue.count()):
            if self.queue.item(i).data(Qt.UserRole) == p:
                self.queue.takeItem(i)
                return

    def _mark_pending_fail(self, p: str, msg: str):
        """失败项留在待归档队列并标红（可改源重试）。"""
        for i in range(self.queue.count()):
            it = self.queue.item(i)
            if it.data(Qt.UserRole) == p:
                it.setText(f"{it.text()}   ✕失败: {msg}")
                it.setForeground(QColor("#A32D2D"))
                return

    def on_theme(self, tn, mode):
        self.drop.set_motif(tn, mode)

    def on_drop(self, paths):
        for p in paths:
            name = Path(p).name
            m = ID_RE.search(name)
            if m:
                self.pending.append((p, m.group(1)))
                item = QListWidgetItem(f"{m.group(1)} · {name}")
                item.setData(Qt.UserRole, p)   # 必须：_remove_pending/_mark_fail 靠它匹配
                self.queue.addItem(item)
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
        self.bar.setValue(0)
        self.btn_run.setEnabled(False)

    def clear_history(self):
        """清空右栏已归档历史（含持久化）。"""
        self.done_list.clear()
        try:
            if self._done_file.exists():
                self._done_file.unlink()
        except Exception:
            pass
        self.main.set_status("已清空归档历史")

    def start(self):
        if not self.pending:
            return
        cfg = self.main.config
        self._batch = list(self.pending)   # 快照；成功后逐项移出待归档
        self.bar.setValue(0)
        self.btn_run.setEnabled(False)
        self.worker = DragWorker(
            self._batch, cfg["booth_root"], cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.worker.item_done.connect(self.on_done)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_done(self, r):
        iid = r.get("id")
        p = r.get("path", "")
        name = r.get("name") or Path(p).name
        status = r.get("status")
        # R21：err 留在待归档标红；其余一律移出待归档，入右栏历史（杜绝二次归档）
        if status == "err":
            self._mark_pending_fail(p, r.get("msg", ""))
            self.main.set_status(f"{iid} 归档失败：{r.get('msg','')}")
            self.bar.setValue(int(self._progress() / max(len(self._batch), 1) * 100))
            return
        self._remove_pending(p)
        if status == "ok":
            self._push_done(iid, name, r.get("cat", ""), "✓")
        elif status == "mismatch":
            wrong = r.get("wrong_cat", "")
            dest_cat = r.get("dest_cat", "")
            msg = (
                f"{iid} · {name}\n"
                f"当前所在：{wrong}\n"
                f"官方分类：{dest_cat}\n"
                f"（类目可能错位，是否重归档到「{dest_cat}」？\n"
                f"  原目录内容会留档在目标目录内「旧_日期」子目录，不删除）\n\n"
                f"（点取消则记入右侧历史并跳过该项）"
            )
            if ThemeDialog.confirmation(self, "类目错位", msg):
                self._force_redo(iid, r.get("wrong_path", ""))
            else:
                self._push_done(iid, name, f"{wrong}→{dest_cat}", "✕错位跳过")
        elif status == "exists":
            cur_cat = r.get("dest_cat") or r.get("cat", "")
            # R21：分类一致不再弹窗（直接记历史）；不一致才确认重排
            if cur_cat and cur_cat != r.get("cat", ""):
                msg = (
                    f"{iid} · {name}\n"
                    f"已在「{r.get('cat','')}」类别下，官方分类是「{cur_cat}」\n"
                    f"（类目可能错位，是否重归档到「{cur_cat}」？\n"
                    f"  原目录内容会留档在「旧_日期」子目录，不删除）"
                )
                if ThemeDialog.confirmation(self, "已归档", msg):
                    self._force_redo(iid, r.get("path", ""))
                    return
            self._push_done(iid, name, r.get("cat", ""), "= 已存在")
        elif status == "warn":
            self._push_done(iid, name, r.get("cat", ""), "= 已存在")
        elif status == "delisted":
            self._push_done(iid, name, "已下架商品", "✕下架")
        else:
            self._push_done(iid, name, r.get("cat", ""), "✕")
        self.bar.setValue(int(self._progress() / max(len(self._batch), 1) * 100))

    def _progress(self):
        """本次归档已完成数 = 快照数 − 待归档队列剩余本批项。"""
        remain = sum(1 for i in range(self.queue.count())
                     if self.queue.item(i).data(Qt.UserRole)
                     in {path for path, _ in self._batch})
        return len(self._batch) - remain

    def _force_redo(self, iid: str, source_path: str):
        """强制重归档：单件重跑 archive_item(force=True)，结果入右栏历史。"""
        cfg = self.main.config
        s = bc.make_session(cfg["cookie"])
        if cfg["proxy"]:
            s.proxies.update({"http": cfg["proxy_url"], "https": cfg["proxy_url"]})
        r = archive_item(iid, cfg["booth_root"], s, move_source=source_path, force=True)
        name = r.get("name") or Path(source_path).name
        if r["status"] == "ok":
            old = r.get("archived_old")
            left = f"（旧内容已留档 {Path(old).name}）" if old else ""
            self._push_done(iid, name, r.get("cat", ""), "✓重归档" + left)
        elif r["status"] == "err":
            self.main.set_status(f"{iid} 重归档失败：{r.get('msg','')}")
            self._push_done(iid, name, r.get("cat", ""),
                            f"✕重归档失败:{r.get('msg','')[:30]}")
        else:
            self._push_done(iid, name, r.get("cat", ""), f"✕{r.get('msg','')[:30]}")

    def on_finished(self):
        self.btn_run.setEnabled(True)
        remain = self.queue.count()
        self.main.set_status(
            f"归档完成：本次 {len(self._batch)} 项，"
            f"{'全部处理完毕' if remain == 0 else f'{remain} 项失败留在待归档（标红）'}")
