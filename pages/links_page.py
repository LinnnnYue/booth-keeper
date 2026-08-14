# pages/links_page.py — 批量链接处理
import re
from pathlib import Path
from PySide6.QtWidgets import (QPlainTextEdit, QPushButton, QListWidget, QListWidgetItem,
    QHBoxLayout, QLabel, QProgressBar, QFrame)
from PySide6.QtCore import Qt, QThread, Signal
from pages.base import BasePage
from pages.notify import ThemeDialog
import booth_core as bc

# R6 修复：原 r"booth\.pm/(?:ja/)?items/(\d{7})" 不认 zh-cn/en/ko 等所有 locale，
# 改为「任意 locale 段（包括无 locale）」+ 「裸 7 位 ID」两种识别方式。
URL_RE = re.compile(
    r"(?:https?://)?booth\.pm/(?:[a-zA-Z][a-zA-Z\-]*/)?items/(\d{7})",
    re.IGNORECASE)
BARE_ID_RE = re.compile(r"(?<![\dA-Za-z])(\d{7})(?![\dA-Za-z])")


class LinksWorker(QThread):
    log = Signal(str)
    item_done = Signal(dict)
    finished = Signal()

    def __init__(self, ids, root, proxy, proxy_url, cookie):
        super().__init__()
        self.ids = ids
        self.root = Path(root)
        self.proxy = proxy
        self.proxy_url = proxy_url
        self.cookie = cookie

    def run(self):
        s = bc.make_session(self.cookie)
        if self.proxy:
            s.proxies.update({"http": self.proxy_url, "https": self.proxy_url})
        for iid in self.ids:
            try:
                it = bc.fetch_item(iid, s)
                if not it:
                    self.item_done.emit({"id": iid, "status": "err", "msg": "未找到商品"})
                    continue
                name = it.get("name") or iid
                cat = bc.classify(it.get("category_name"), it.get("category_parent_name")) or "未分类"
                dest = self.root / cat / f"{iid}_{bc.sanitize(name)}"
                dup = dest.exists()
                dest.mkdir(parents=True, exist_ok=True)
                cover = dest / "cover.jpg"
                imgs = it.get("images") or []
                if imgs and not cover.exists():
                    try:
                        bc.download_cover(imgs[0]["original"], str(dest), s)
                    except Exception as e:
                        self.log.emit(f"{iid} 封面失败: {e}")
                if cover.exists():
                    try:
                        bc.make_folder_icon(cover, dest)
                    except Exception as e:
                        self.log.emit(f"{iid} 图标失败: {e}")
                self.item_done.emit({
                    "id": iid, "name": name, "cat": cat,
                    "status": "ok" if not dup else "warn", "dup": dup,
                })
            except Exception as e:
                self.item_done.emit({"id": iid, "status": "err", "msg": str(e)[:80]})
        self.finished.emit()


class LinksPage(BasePage):
    def __init__(self, main):
        super().__init__(main)
        self.worker = None
        self.header("批量链接处理", "从聊天记录粘贴 Booth 链接，自动剔除杂音并批量归档")

        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("在此粘贴包含 Booth 链接的聊天文本……\n示例：booth.pm/items/3290806 免费！GoGo Loco")
        self.edit.setMinimumHeight(110)
        self.root.addWidget(self.edit)

        row = QHBoxLayout()
        self.btn_parse = QPushButton("解析链接")
        self.btn_parse.setObjectName("accent")
        self.btn_parse.clicked.connect(self.parse)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setObjectName("secondary")
        self.btn_clear.clicked.connect(lambda: self.edit.clear())
        self.lbl_count = QLabel("尚未解析")
        self.lbl_count.setObjectName("muted")
        row.addWidget(self.btn_parse)
        row.addWidget(self.btn_clear)
        row.addStretch(1)
        row.addWidget(self.lbl_count)
        self.root.addLayout(row)

        self.hline()
        self.lbl_queue = QLabel("下载队列")
        self.lbl_queue.setObjectName("pageSub")
        self.root.addWidget(self.lbl_queue)
        self.queue = QListWidget()
        self.queue.setObjectName("obs")
        self.queue.setMinimumHeight(180)
        self.root.addWidget(self.queue)

        self.bar = QProgressBar()
        self.bar.setValue(0)
        self.root.addWidget(self.bar)

        self.hline()
        row2 = QHBoxLayout()
        self.btn_run = QPushButton("开始归档")
        self.btn_run.setObjectName("accent")
        self.btn_run.clicked.connect(self.start)
        self.btn_run.setEnabled(False)
        row2.addWidget(self.btn_run)
        row2.addStretch(1)
        self.root.addLayout(row2)

        self.pending = []  # 解析出的 id 列表

    def parse(self):
        """从用户粘贴的大段文本/截图中识别 booth.pm 链接（含所有 locale 前缀如 zh-cn/ja/en）
        + 兜底裸 7 位 ID（前后非数字/字母，避免误识别版本号/电话）。"""
        text = self.edit.toPlainText()
        ids = []
        seen = set()
        # 先抓 URL 形式（权威：含完整路径的链接，含 zh-cn/ja/en/ko/无前缀）
        for m in URL_RE.finditer(text):
            iid = m.group(1)
            if iid not in seen:
                seen.add(iid); ids.append(iid)
        # 再抓裸 7 位 ID（兜底：URL 漏掉时仍能识别）
        for m in BARE_ID_RE.finditer(text):
            iid = m.group(1)
            if iid not in seen:
                seen.add(iid); ids.append(iid)
        self.pending = ids
        self.lbl_count.setText(f"解析到 {len(ids)} 个有效商品 ID")
        self.btn_run.setEnabled(len(ids) > 0)
        if not ids:
            ThemeDialog.information(self, "提示",
                "未从文本中识别到 booth.pm/items/ 形式的七位 ID 链接，\n"
                "或裸 7 位 Booth ID。\n\n"
                "示例：\n"
                "  https://booth.pm/zh-cn/items/3290806\n"
                "  booth.pm/items/3290806\n"
                "  3290806（裸 ID）")

    def start(self):
        if not self.pending:
            return
        cfg = self.main.config
        self.queue.clear()
        self.bar.setValue(0)
        self.btn_run.setEnabled(False)
        self.btn_parse.setEnabled(False)
        self.worker = LinksWorker(
            self.pending, cfg["booth_root"], cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.worker.log.connect(self.main.set_status)
        self.worker.item_done.connect(self.on_done)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_done(self, d):
        iid = d["id"]
        if d["status"] == "ok":
            item = QListWidgetItem(f"{iid} · {d.get('name','')}  →  {d.get('cat','')}")
            item.setData(Qt.UserRole, "ok")
        elif d["status"] == "warn":
            item = QListWidgetItem(f"{iid} · {d.get('name','')}  →  已存在，跳过")
            item.setData(Qt.UserRole, "warn")
        else:
            item = QListWidgetItem(f"{iid}  ✕ {d.get('msg','失败')}")
            item.setData(Qt.UserRole, "err")
        self.queue.addItem(item)
        done = self.queue.count()
        self.bar.setValue(int(done / len(self.pending) * 100))

    def on_finished(self):
        self.btn_run.setEnabled(True)
        self.btn_parse.setEnabled(True)
        self.main.set_status(f"归档完成：{self.queue.count()} 项")
