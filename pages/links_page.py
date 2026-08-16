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
    """R9 修复：之前只下载封面 + 做图标，从未下载商品本体（unitypackage/zip/blend/fbx等）。

    新流程：fetch_item（JSON API）→ 反查类目 → 建 dest → 拉商品页面 HTML 找下载链接列表
    → 逐个下载到 dest → 下载封面 + 做图标。"""
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
                # R10 修复：dest 已存在不再 early-skip——必须走 fetch_item_downloads + 缺失补全流程
                # （否则 v1.0.0 时代归档的目录会一直「已存在，跳过」，本体永远下载不到）
                dup = dest.exists()
                dest.mkdir(parents=True, exist_ok=True)
                # R9: 先下载商品本体（之前缺失的核心步骤）
                downloads = bc.fetch_item_downloads(iid, s)
                downloaded_files = []
                missing_files = []
                if downloads:
                    for dl in downloads:
                        fname = dl.get("name") or f"{iid}_{bc.sanitize(name)}.zip"
                        target = dest / fname
                        if target.exists() and target.stat().st_size > 0:
                            # 文件已存在 + 大小 > 0 → 跳过（不算下载）
                            downloaded_files.append(fname)
                            continue
                        # 文件缺失 → 下载补全
                        missing_files.append(fname)
                        try:
                            self.log.emit(
                                f"{iid} 补全下载 {fname} ({dl.get('size_text','')})...")
                            self._download_with_referer(dl["url"], str(target), s,
                                                         referer_id=iid)
                            if target.exists() and target.stat().st_size > 0:
                                downloaded_files.append(fname)
                                self.log.emit(f"{iid} ✓ {fname}")
                            else:
                                self.log.emit(f"{iid} ✕ {fname} 下载失败")
                        except Exception as e:
                            self.log.emit(f"{iid} {fname} 下载异常: {e}")
                else:
                    self.log.emit(f"{iid} 商品页未找到下载链接（可能需 Cookie 登录）")
                # 封面 + 图标
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
                # R10: status 区分 "ok"/"warn"
                # - ok: 新建（dest 不存在过）或本次补全了 ≥1 个文件
                # - warn: dest 已存在且无补全（仅 cover/ico/ini 已有，本体也齐全）
                if missing_files and downloaded_files:
                    status = "ok"  # 至少补了一些
                    self.log.emit(
                        f"{iid} 补全完成：{len(downloaded_files)} 文件")
                elif missing_files and not downloaded_files:
                    status = "warn"  # 试图补全但都失败
                    self.log.emit(
                        f"{iid} 补全失败：{len(missing_files)} 个文件未下载")
                else:
                    status = "warn" if dup else "ok"
                self.item_done.emit({
                    "id": iid, "name": name, "cat": cat,
                    "status": status, "dup": dup,
                    "files": downloaded_files,
                    "missing": missing_files,
                    "is_backfill": dup and downloaded_files,  # R10: 标记是补全而非新建
                })
            except Exception as e:
                self.item_done.emit({"id": iid, "status": "err", "msg": str(e)[:80]})
        self.finished.emit()

    def _download_with_referer(self, url: str, dest_path: str, s, referer_id: str):
        """下载 BOOTH 文件，需 Referer header 防盗链。"""
        referer = f"https://booth.pm/ja/items/{referer_id}"
        r = bc.retry_request(
            "GET", url, s,
            headers={**bc.UA, "Referer": referer},
            timeout=120, stream=True)
        if not r:
            raise RuntimeError("网络请求失败")
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)


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
        # R10 新增：显示下载的文件列表 + 补全标识
        files = d.get("files", [])
        missing = d.get("missing", [])
        is_backfill = d.get("is_backfill", False)
        if files:
            files_summary = f"  ({len(files)} 文件)"
        else:
            files_summary = "  ⚠ 无文件"
        if is_backfill:
            files_summary += "  🔄 补全"
        if d["status"] == "ok":
            prefix = "🔄 补全" if is_backfill else "✓"
            item = QListWidgetItem(
                f"{iid} · {d.get('name','')}  →  {d.get('cat','')} {prefix}{files_summary}")
            item.setData(Qt.UserRole, "ok")
        elif d["status"] == "warn":
            if missing and not files:
                # 试图补全但都失败
                item = QListWidgetItem(
                    f"{iid} · {d.get('name','')}  ⚠ 补全失败 ({len(missing)} 文件未下)")
                item.setData(Qt.UserRole, "err")
            else:
                item = QListWidgetItem(
                    f"{iid} · {d.get('name','')}  →  已存在，跳过{files_summary}")
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
