# pages/search_page.py — 实验性检索
import re
from pathlib import Path
from urllib.parse import unquote
from PySide6.QtWidgets import (QPlainTextEdit, QPushButton, QListWidget, QListWidgetItem,
    QHBoxLayout, QLabel, QProgressBar, QFrame)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from pages.base import BasePage
from pages.notify import ThemeDialog
import booth_core as bc
from archive_util import archive_item, find_existing_source_in_library


class DroppableTextEdit(QPlainTextEdit):
    """实验检索输入框：显式接受文件/文件夹拖放，把本地路径以 file:// 形式填入输入框。
    不依赖 QPlainTextEdit 默认拖放（真机对目录/多文件可能表现不稳定）。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e: QDropEvent):
        md = e.mimeData()
        if md.hasUrls():
            paths = []
            for u in md.urls():
                loc = u.toLocalFile()
                if loc:
                    # 标准化为 file:///X:/... 形式（与 Qt 默认一致）
                    paths.append(QUrl.fromLocalFile(loc).toString())
            if paths:
                cur = self.toPlainText().rstrip()
                merged = (cur + "\n" + "\n".join(paths)).strip() if cur else "\n".join(paths)
                self.setPlainText(merged)
                e.acceptProposedAction()
                return
        super().dropEvent(e)


def _looks_like_path(s: str) -> bool:
    """检测输入是否像文件路径（含 /,\\,file://,盘符）。"""
    s = s.strip()
    if s.startswith("file://") or s.startswith("/") or s.startswith("\\"):
        return True
    if re.match(r"^[a-zA-Z]:[/\\]", s):
        return True
    if "/" in s and ".zip" in s.lower() or ".png" in s.lower() or ".unitypackage" in s.lower():
        return True
    return False


def _extract_file_path(s: str) -> str:
    """从 file URL / 文件路径提取完整本地路径（不剥扩展名）。
    QUrl.toLocalFile 正确处理 file:///X:/...（三斜杠），避免残留前导 / 导致 exists() 失效。"""
    s = s.strip()
    if s.startswith("file://"):
        try:
            return QUrl(s).toLocalFile()
        except Exception:
            pass
    return s


def _extract_basename(s: str) -> str:
    """从文件路径/file URL/裸字符串提 basename + 剥扩展名。"""
    s = _extract_file_path(s)
    # 取最后一段
    s = s.replace("\\", "/").rstrip("/")
    name = s.split("/")[-1] if "/" in s else s
    # 剥常见扩展
    for ext in (".zip", ".png", ".jpg", ".unitypackage", ".rar", ".7z", ".tar", ".gz"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break
    return name.strip()


class SearchWorker(QThread):
    """R6 多候选：接受候选查询列表，按顺序逐一搜索，合并去重（保留首次出现的顺序）。
    返回值: [{id, name, price_text, shop, ...}, ...]"""
    result = Signal(list, int)  # (items, candidates_used)
    error = Signal(str)

    def __init__(self, queries, proxy, proxy_url, cookie):
        super().__init__()
        self.queries = queries if isinstance(queries, list) else [queries]
        self.proxy = proxy
        self.proxy_url = proxy_url
        self.cookie = cookie

    def run(self):
        s = bc.make_session(self.cookie)
        if self.proxy:
            s.proxies.update({"http": self.proxy_url, "https": self.proxy_url})
        seen = set()
        merged = []
        used = 0
        try:
            for q in self.queries:
                if not q or not q.strip():
                    continue
                used += 1
                items = bc.search_booth(q.strip(), s)
                for it in items:
                    pid = str(it.get("id", ""))
                    if pid and pid not in seen:
                        seen.add(pid)
                        merged.append(it)
            self.result.emit(merged, used)
        except Exception as e:
            self.error.emit(str(e))


class ArchiveWorker(QThread):
    item_done = Signal(dict)
    finished = Signal()

    def __init__(self, ids, root, proxy, proxy_url, cookie):
        super().__init__()
        self.ids = ids
        self.root = root
        self.proxy = proxy
        self.proxy_url = proxy_url
        self.cookie = cookie
        self.moves = {}  # R7：id → BOOTH 库内源路径（由 SearchPage.archive 注入）

    def run(self):
        s = bc.make_session(self.cookie)
        if self.proxy:
            s.proxies.update({"http": self.proxy_url, "https": self.proxy_url})
        for iid in self.ids:
            src = self.moves.get(iid)
            try:
                r = archive_item(iid, self.root, s, move_source=src)
            except Exception as e:
                r = {"status": "err", "msg": str(e)}
            r["id"] = iid
            self.item_done.emit(r)
        self.finished.emit()


class SearchPage(BasePage):
    """实验性检索。

    R6 增强：
      - 输入检测（file://、盘符路径、含扩展名）→ 提取 basename → sanitize_query 生成多候选
      - 多候选顺序搜索，合并去重，UI 显示「已尝试 X 个候选」
    R17 增强（多信号 + 打分）：
      - 拖入文件/压缩包 → probe_package 深挖包内信号（外层名/包内名/作者名）
      - search_booth 结果按相似度打分排序，显示匹配度与置信分级（高/中/低）
      - 高置信可放心归档，低置信红色提示先人工核对
    """
    def __init__(self, main):
        super().__init__(main)
        self.header("实验检索",
            "输入文件名/路径/关键词，自动生成搜索候选并匹配；可接入 Cookie/Token（设置页）。不保证稳定准确")
        self.worker = None
        self.archiver = None
        self.items = []
        self._sig = None        # R17：当前输入的信号元（打分用）
        self._done = []

        self.edit = DroppableTextEdit()
        self.edit.setPlaceholderText(
            "粘贴文件名、关键词或文件路径（自动提取 basename）。\n"
            "示例：star_eclipse_halo_1.0.0  或  file:///G:/.../star_eclipse_halo_1.0.0.zip")
        self.edit.setMinimumHeight(80)
        self.root.addWidget(self.edit)

        row = QHBoxLayout()
        self.btn_search = QPushButton("检索")
        self.btn_search.setObjectName("accent")
        self.btn_search.clicked.connect(self.search)
        self.lbl = QLabel("")
        self.lbl.setObjectName("muted")
        row.addWidget(self.btn_search)
        row.addStretch(1)
        row.addWidget(self.lbl)
        self.root.addLayout(row)

        self.hline()
        self.list = QListWidget()
        self.list.setObjectName("obs")
        self.list.setMinimumHeight(200)
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        self.list.itemDoubleClicked.connect(self.open_in_browser)
        self.root.addWidget(self.list)

        self.bar = QProgressBar()
        self.root.addWidget(self.bar)

        row2 = QHBoxLayout()
        self.btn_archive = QPushButton("归档选中")
        self.btn_archive.setObjectName("accent")
        self.btn_archive.clicked.connect(self.archive)
        self.btn_archive.setEnabled(False)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setObjectName("secondary")
        self.btn_clear.clicked.connect(self.clear_all)
        row2.addWidget(self.btn_archive)
        row2.addWidget(self.btn_clear)
        row2.addStretch(1)
        self.root.addLayout(row2)
        self.spacer()

    def _build_queries(self, raw: str) -> list[str]:
        """输入 → 候选查询列表（顺序敏感）。

        R17：若输入是存在的文件/目录 → probe_package 深挖包内信号，
        用 build_search_queries 生成多候选（外层名→包内名→作者+商品→兜底），
        并把信号元存 self._sig 供结果打分。"""
        raw = raw.strip()
        if not raw:
            return []
        self._sig = None
        if _looks_like_path(raw):
            p = Path(_extract_file_path(raw))
            if p.exists():
                self._sig = bc.probe_package(p)
                queries = bc.build_search_queries(p)
                if queries:
                    return queries
            base = _extract_basename(raw)
        else:
            base = raw
        # 兜底：booth_core.sanitize_query 老路
        candidates = bc.sanitize_query(base)
        if raw != base and raw not in candidates:
            candidates.append(raw)
        seen, out = set(), []
        for c in candidates:
            c = c.strip()
            if c and c not in seen:
                seen.add(c); out.append(c)
        return out

    def search(self):
        raw = self.edit.toPlainText().strip()
        if not raw:
            return
        queries = self._build_queries(raw)
        if not queries:
            self.lbl.setText("输入为空或无法生成候选。")
            return
        cfg = self.main.config
        self.list.clear()
        self.lbl.setText(f"检索中…（{len(queries)} 个候选：{queries[:3]}{'...' if len(queries) > 3 else ''}）")
        self.btn_archive.setEnabled(False)
        self.worker = SearchWorker(queries, cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.worker.result.connect(self.on_result)
        self.worker.error.connect(lambda e: self.lbl.setText("错误: " + e))
        self.worker.start()

    def on_result(self, items, used):
        # R17 打分排序：名称相似度 + 作者/店名命中加权，高分置顶
        if getattr(self, "_sig", None):
            items = bc.rank_search_results(items, self._sig)
        self.items = items
        self.list.clear()
        for it in items[:20]:
            score = it.get("score", 0)
            if score >= 0.6:
                tag = "高置信"
            elif score >= 0.35:
                tag = "中置信"
            else:
                tag = "低置信"
            item = QListWidgetItem(
                f"[{100*score:3.0f}% {tag}] {it['id']} · {it.get('name','')}   |   {it.get('price_text','')}   |   {it.get('shop','')}")
            item.setData(Qt.UserRole, it["id"])
            self.list.addItem(item)
        self.lbl.setText(
            f"用 {used} 个候选搜到 {len(items)} 条（按匹配度排序，置信分级：高=可直接归档，中=建议核对，低=可能不符）。双击可开浏览器核对。")
        self.btn_archive.setEnabled(len(items) > 0)

    def open_in_browser(self, item):
        """双击搜索条目 → 浏览器打开 BOOTH 商品页核对。"""
        import webbrowser
        iid = item.data(Qt.UserRole)
        if iid:
            webbrowser.open(f"https://booth.pm/ja/items/{iid}")

    def archive(self):
        sel = self.list.selectedItems()
        if not sel:
            ThemeDialog.information(self, "提示", "请先选择要归档的商品（单击选中）。")
            return
        ids = [it.data(Qt.UserRole) for it in sel]
        cfg = self.main.config
        # R7 修复：每个待归档 ID 在 BOOTH 根全库广搜源文件/目录，命中即作为 move_source
        moves = {}
        skipped = []
        for iid in ids:
            it = next((x for x in self.items if str(x.get("id")) == str(iid)), None)
            name = (it or {}).get("name", "")
            src = find_existing_source_in_library(str(iid), name, cfg["booth_root"])
            if src:
                moves[iid] = src
            else:
                skipped.append(iid)

        # R15 兜底
        if skipped and not moves:
            raw_input = self.edit.toPlainText()
            found = None
            for line in raw_input.splitlines():
                line = line.strip()
                if not line or not _looks_like_path(line):
                    continue
                p = Path(_extract_file_path(line))
                exists = p.exists()
                if exists:
                    found = str(p)
                    break
            if found:
                for iid in skipped:
                    moves[iid] = found
                skipped = []

        if skipped and not moves:
            ThemeDialog.information(self, "未找到源文件",
                f"在 BOOTH 根（{cfg['booth_root']}）下未找到任何待归档商品对应的源文件/目录。\n\n"
                f"未命中 ID：{', '.join(map(str, skipped))}\n\n"
                f"如需移动，可在「拖拽分类」页直接拖入源文件。")
            return

        archive_ids = [iid for iid in ids if iid in moves]
        if not archive_ids:
            return

        self._done = []
        self.bar.setValue(0)
        self.archiver = ArchiveWorker(archive_ids, cfg["booth_root"], cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.archiver.moves = moves
        self.archiver.item_done.connect(self.on_archive_done)
        self.archiver.finished.connect(self.on_finished)
        self.archiver.start()

    def on_archive_done(self, r):
        self._done.append(r)
        if r["status"] == "ok":
            src_note = "（含源文件搬移）" if r.get("dest") and "moved" in r else ""
            self.lbl.setText(f"已归档：{r.get('name','')} → {r.get('cat','')} {src_note}")
        elif r["status"] == "exists":
            self.lbl.setText(f"已存在跳过：{r.get('name','')}")
        else:
            # R17：归档失败 → 若为「未找到商品」，严谨判定是否真下架
            # （BOOTH 可达 + 商品 404 = 确已下架；网络异常 = 不妄断）
            msg = r.get("msg", "")
            if "未找到商品" in msg:
                cfg = self.main.config
                sess = bc.make_session(cfg.get("cookie", ""))
                if cfg.get("proxy"):
                    sess.proxies.update({"http": cfg["proxy_url"],
                                         "https": cfg["proxy_url"]})
                state, why = bc.classify_item_state(str(r.get("id", "")), sess)
                if state == "delisted":
                    self.lbl.setText(
                        f"⚠ {r.get('id')} 确为已下架（BOOTH 可达，商品 404）。"
                        f"可将源文件移入 BOOTH/已下架商品/")
                elif state == "unknown":
                    self.lbl.setText(f"⛔ {r.get('id')} 无法判定是否下架：{why}")
                else:
                    self.lbl.setText(f"失败 {r.get('id','')}：{msg}")
            else:
                self.lbl.setText(f"失败 {r.get('id','')}：{msg}")
        # R7 修复：分母用本次归档的选中数（self.ids），不是搜索结果总数
        total = len(self._done) or 1
        # self.archiver.ids 是注入的归档列表
        denom = max(1, len(getattr(self.archiver, 'ids', []) or [1]))
        self.bar.setValue(int(total / denom * 100))

    def on_finished(self):
        ok = sum(1 for r in self._done if r["status"] == "ok")
        self.main.set_status(f"检索归档完成：{ok} 成功 / {len(self._done)} 总计")

    def clear_all(self):
        self.items = []
        self._done = []
        self.list.clear()
        self.edit.clear()
        self.bar.setValue(0)
        self.btn_archive.setEnabled(False)
        self.lbl.setText("")
