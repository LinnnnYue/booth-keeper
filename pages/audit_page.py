# pages/audit_page.py — 目录巡检与版本巡检
# R11 重构：拆成 3 个独立功能区（本地巡检 / 联网巡检 / 本体补全），
# 每个区自带按钮 + 进度条 + 列表 + 状态，不再「开始巡检」一次性全跑导致「本体检测中…」假死感。
import re
from pathlib import Path
from PySide6.QtWidgets import (QListWidget, QPushButton, QHBoxLayout, QLabel,
    QProgressBar, QFrame)
from PySide6.QtCore import Qt, QThread, Signal
from pages.base import BasePage
from pages.notify import ThemeDialog
import booth_core as bc

# R6 修复：原 r"^(\d{7})_(.+)$" 只接下划线，主上 7903148 Pixel Holy Halo（空格分隔）
# 完全跳过。改为「下划线 / 半角空格 / 全角空格 / 连字符 / 中文全角连字符 / 日文长音 ー」全部接。
ID_DIR_RE = re.compile(r"^(\d{7})[\s_\-－　ー]+(.+)$")


def _ver_tuple(tag):
    if not tag:
        return ()
    m = re.search(r"(\d+(?:\.\d+)*)", tag)
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def _ver_gt(a, b):
    """a 是否严格大于 b（按版本号数字逐段比较）。"""
    ta, tb = _ver_tuple(a), _ver_tuple(b)
    if not ta or not tb:
        return False
    n = max(len(ta), len(tb))
    ta = ta + (0,) * (n - len(ta))
    tb = tb + (0,) * (n - len(tb))
    return ta > tb


# R10 修复：本体的扩展名（商品文件类型）
BODY_EXTENSIONS = frozenset({
    ".zip", ".unitypackage", ".blend", ".fbx", ".obj", ".gltf", ".glb",
    ".png", ".jpg", ".jpeg", ".pdf", ".mp4", ".wav", ".mp3", ".txt",
    ".rar", ".7z", ".tar", ".gz", ".bz2",  # 压缩包
})


def has_body(d: Path) -> bool:
    """R10 检测目录是否含商品本体文件（非三件套）。"""
    for f in d.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() in BODY_EXTENSIONS and f.stat().st_size > 1024:
            return True
    return False


def _iter_library_dirs(root: Path):
    """迭代 BOOTH 库中所有 ID_xxx 商品目录（rglob 预过滤，性能快）。"""
    for d in root.rglob("*"):
        if d.is_dir() and ID_DIR_RE.match(d.name):
            yield d


def scan_library(root, on_progress=None):
    """遍历 BOOTH 库，定位 ID_标题 商品目录，检查三件套 + 本体缺失 + 本地版本。

    R11：纯本地扫描（秒级），on_progress(done, total) 回调实时进度。
    """
    root = Path(root)
    out = []
    if not root.exists():
        return out
    dirs = list(_iter_library_dirs(root))
    total = len(dirs)
    for idx, d in enumerate(dirs, 1):
        if on_progress:
            on_progress(idx, total)
        m = ID_DIR_RE.match(d.name)
        if not m:
            continue
        iid, name = m.group(1), m.group(2)
        missing = []
        if not (d / "cover.jpg").exists():
            missing.append("封面")
        if not (d / ".folder_icon.ico").exists():
            missing.append("图标")
        if not (d / "desktop.ini").exists():
            missing.append("ini")
        # R10: 检测本体缺失（纯本地 stat，快）
        body_missing = not has_body(d)
        out.append({
            "id": iid, "name": name, "path": str(d),
            "missing": missing, "local_tag": bc.extract_version_tag(d.name),
            "body_missing": body_missing,  # True = 缺本体文件
        })
    return out


class ScanWorker(QThread):
    """R11 本地巡检：只做三件套 + 本体缺失（纯本地，秒级）。
    不再耦合联网错位检测（错位检测拆到 MismatchWorker 独立跑）。"""
    progress = Signal(int, int)  # (done, total)
    item = Signal(dict)
    done = Signal(list)

    def __init__(self, root):
        super().__init__()
        self.root = root

    def run(self):
        items = scan_library(self.root, on_progress=self.progress.emit)
        for it in items:
            self.item.emit(it)
        self.done.emit(items)


class MismatchWorker(QThread):
    """R11 独立联网错位检测：遍历本地已扫目录，fetch_item 拿官方分类比对当前目录。
    独立于本地巡检，用户可单独跑，实时进度。"""
    progress = Signal(int, int)
    mismatch = Signal(dict)
    done = Signal(list)

    def __init__(self, items, proxy=False, proxy_url="", cookie=""):
        super().__init__()
        self.items = items
        self.proxy = proxy
        self.proxy_url = proxy_url
        self.cookie = cookie

    def run(self):
        s = bc.make_session(self.cookie)
        if self.proxy:
            s.proxies.update({"http": self.proxy_url, "https": self.proxy_url})
        total = len(self.items)
        mismatches = []
        for idx, it in enumerate(self.items, 1):
            self.progress.emit(idx, total)
            try:
                d = bc.fetch_item(it["id"], s)
                if not d:
                    continue
                cat_name = d.get("category_name", "") or ""
                cat_parent = d.get("category_parent_name", "") or ""
                dest_cat = bc.classify(cat_name, cat_parent) or "未分类"
                wrong_cat = Path(it["path"]).parent.name
                if dest_cat != wrong_cat and dest_cat != "未分类":
                    mismatches.append({
                        "id": it["id"], "name": it["name"],
                        "wrong_cat": wrong_cat, "dest_cat": dest_cat,
                        "wrong_path": it["path"],
                    })
                    self.mismatch.emit(mismatches[-1])
            except Exception:
                continue
        self.done.emit(mismatches)


class FixWorker(QThread):
    """修复三件套：封面 + 图标 + ini。"""
    prog = Signal(str)
    finished = Signal(int)

    def __init__(self, items, proxy, proxy_url, cookie):
        super().__init__()
        self.items = [i for i in items if i["missing"]]
        self.proxy = proxy
        self.proxy_url = proxy_url
        self.cookie = cookie

    def run(self):
        s = bc.make_session(self.cookie)
        if self.proxy:
            s.proxies.update({"http": self.proxy_url, "https": self.proxy_url})
        fixed = 0
        for it in self.items:
            dest = Path(it["path"])
            try:
                d = bc.fetch_item(it["id"], s)
                if not d:
                    self.prog.emit(f"跳过 {it['id']}：无法获取商品（网络/代理/Cookie？）")
                    continue
                imgs = d.get("images") or []
                cover_ok = False
                if imgs and not (dest / "cover.jpg").exists():
                    try:
                        cover = bc.download_cover(imgs[0].get("original", ""), str(dest), s)
                        cover_ok = bool(cover and cover.exists())
                        if not cover_ok:
                            self.prog.emit(f"  · {it['id']} 封面下载失败（thumb={imgs[0].get('original','')[:60]}）")
                    except Exception as e:
                        self.prog.emit(f"  · {it['id']} 封面异常: {e}")
                        cover_ok = (dest / "cover.jpg").exists()
                if not imgs:
                    self.prog.emit(f"  · {it['id']} 商品无图片（API 异常？）")
                if (dest / "cover.jpg").exists():
                    try:
                        bc.make_folder_icon(dest / "cover.jpg", dest)
                        fixed += 1
                        self.prog.emit(f"已修复 {it['id']} · {it['name']}")
                    except Exception as e:
                        self.prog.emit(f"  · {it['id']} make_folder_icon 失败: {e}")
                else:
                    self.prog.emit(f"未修复 {it['id']}：封面缺失，无法生成图标")
            except Exception as e:
                self.prog.emit(f"失败 {it['id']}: {e}")
        self.finished.emit(fixed)


class VersionWorker(QThread):
    """版本巡检（独立联网）：比对官方版本号。"""
    found = Signal(dict)
    prog = Signal(str)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, items, proxy, proxy_url, cookie):
        super().__init__()
        self.items = items
        self.proxy = proxy
        self.proxy_url = proxy_url
        self.cookie = cookie

    def run(self):
        s = bc.make_session(self.cookie)
        if self.proxy:
            s.proxies.update({"http": self.proxy_url, "https": self.proxy_url})
        total = len(self.items)
        for idx, it in enumerate(self.items, 1):
            self.progress.emit(idx, total)
            try:
                d = bc.fetch_item(it["id"], s)
                if not d:
                    self.prog.emit(f"无法获取 {it['id']}")
                    continue
                oname = d.get("name", "")
                otag = bc.extract_version_tag(oname)
                if _ver_gt(otag, it["local_tag"]):
                    self.found.emit({
                        "id": it["id"], "name": it["name"],
                        "local": it["local_tag"], "official": otag,
                    })
                self.prog.emit(
                    f"核对 {it['id']}: 本地 {it['local_tag'] or '-'} / 官方 {otag or '-'}")
            except Exception as e:
                self.prog.emit(f"错误 {it['id']}: {e}")
        self.finished.emit()


class FixMismatchWorker(QThread):
    """R8 一键纠正错位：单件 archive_item(force=True) 重建到正确分类。"""
    prog = Signal(str)
    finished = Signal(int)

    def __init__(self, items, root, proxy, proxy_url, cookie):
        super().__init__()
        self.items = items
        self.root = root
        self.proxy = proxy
        self.proxy_url = proxy_url
        self.cookie = cookie

    def run(self):
        s = bc.make_session(self.cookie)
        if self.proxy:
            s.proxies.update({"http": self.proxy_url, "https": self.proxy_url})
        from archive_util import archive_item
        fixed = 0
        for m in self.items:
            try:
                r = archive_item(m["id"], self.root, s,
                                 move_source=m["wrong_path"], force=True)
                if r["status"] == "ok":
                    fixed += 1
                    self.prog.emit(f"已纠正 {m['id']} · {m['name']}  →  {r.get('cat','')}")
                else:
                    self.prog.emit(f"跳过 {m['id']}：{r.get('msg','')}")
            except Exception as e:
                self.prog.emit(f"错误 {m['id']}：{e}")
        self.finished.emit(fixed)


class BackfillWorker(QThread):
    """R10 一键补全本体：拉取 BOOTH 商品页下载链接补齐缺失。"""
    prog = Signal(str)
    progress = Signal(int, int)
    finished = Signal(int)

    def __init__(self, items, root, proxy, proxy_url, cookie):
        super().__init__()
        self.items = [i for i in items if i.get("body_missing")]
        self.root = root
        self.proxy = proxy
        self.proxy_url = proxy_url
        self.cookie = cookie

    def run(self):
        s = bc.make_session(self.cookie)
        if self.proxy:
            s.proxies.update({"http": self.proxy_url, "https": self.proxy_url})
        total = len(self.items)
        fixed = 0
        for idx, it in enumerate(self.items, 1):
            self.progress.emit(idx, total)
            dest = Path(it["path"])
            try:
                downloads = bc.fetch_item_downloads(it["id"], s)
                if not downloads:
                    self.prog.emit(
                        f"  · {it['id']} · {it['name']} 商品页未找到下载链接")
                    continue
                # 已存在的文件（无论何种）不重复下
                existing = {f.name for f in dest.iterdir() if f.is_file()
                             and f.stat().st_size > 0}
                ok = False
                for dl in downloads:
                    fname = dl.get("name") or f"{it['id']}_file.zip"
                    if fname in existing:
                        self.prog.emit(f"  · {it['id']} {fname} 已存在，跳过")
                        continue
                    target = dest / fname
                    try:
                        referer = f"https://booth.pm/ja/items/{it['id']}"
                        r = bc.retry_request(
                            "GET", dl["url"], s,
                            headers={**bc.UA, "Referer": referer},
                            timeout=120, stream=True)
                        if not r or r.status_code != 200:
                            self.prog.emit(
                                f"  · {it['id']} {fname} HTTP {r.status_code if r else 'None'}")
                            continue
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with open(target, "wb") as f:
                            for chunk in r.iter_content(chunk_size=64 * 1024):
                                if chunk:
                                    f.write(chunk)
                        if target.exists() and target.stat().st_size > 0:
                            ok = True
                            self.prog.emit(
                                f"  ✓ {it['id']} {fname} ({target.stat().st_size / 1024 / 1024:.2f} MB)")
                    except Exception as e:
                        self.prog.emit(f"  · {it['id']} {fname} 异常: {e}")
                if ok:
                    fixed += 1
            except Exception as e:
                self.prog.emit(f"  · {it['id']} 异常: {e}")
        self.finished.emit(fixed)


def _section(self, title: str) -> QLabel:
    """功能区标题（带 accent 左规）。"""
    lbl = QLabel(title)
    lbl.setObjectName("pageSub")
    self.root.addWidget(lbl)
    return lbl


class AuditPage(BasePage):
    """R11 重构：3 个独立功能区。

    ① 本地巡检  —— 开始巡检（快）→ 三件套缺失 / 修复三件套
    ② 联网巡检  —— 错位检测 / 版本检测（独立跑）/ 一键纠正错位
    ③ 本体补全  —— 检测缺本体 / 一键补全本体
    """
    def __init__(self, main):
        super().__init__(main)
        self.header("目录巡检", "三件套完整性 / 类目错位 / 版本比对 / 本体缺失，分区独立巡检")
        self.scan_items = []
        self._mismatch_items = []
        self._all_scan_items = []
        self.scan_worker = self.fix_worker = self.ver_worker = None
        self.mismatch_worker = self.fix_mismatch_worker = self.backfill_worker = None

        # ═══════════ ① 本地巡检（快，秒级）═══════════
        _section(self, "① 本地巡检（三件套 + 本体缺失，纯本地扫描）")
        row1 = QHBoxLayout()
        self.btn_scan = QPushButton("开始巡检")
        self.btn_scan.setObjectName("accent")
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_fix = QPushButton("修复三件套")
        self.btn_fix.setObjectName("secondary")
        self.btn_fix.setEnabled(False)
        self.btn_fix.clicked.connect(self.start_fix)
        self.lbl_stat = QLabel("")
        self.lbl_stat.setObjectName("muted")
        self.lbl_stat.setProperty("mono", "1")
        row1.addWidget(self.btn_scan)
        row1.addWidget(self.btn_fix)
        row1.addStretch(1)
        row1.addWidget(self.lbl_stat)
        self.root.addLayout(row1)

        self.scan_bar = QProgressBar()
        self.scan_bar.setValue(0)
        self.scan_bar.setFormat("")
        self.root.addWidget(self.scan_bar)

        self.list_scan = QListWidget()
        self.list_scan.setObjectName("obs")
        self.list_scan.setMinimumHeight(150)
        self.root.addWidget(self.list_scan)

        # 三件套统计徽章
        brow = QHBoxLayout()
        self.badge_ok = QLabel("完整 0")
        self.badge_ok.setProperty("badge", "ok")
        self.badge_miss = QLabel("缺失 0")
        self.badge_miss.setProperty("badge", "warn")
        brow.addWidget(self.badge_ok)
        brow.addWidget(self.badge_miss)
        brow.addStretch(1)
        self.root.addLayout(brow)

        self.root.addSpacing(10)

        # ═══════════ ② 联网巡检（独立跑，各自进度）═══════════
        _section(self, "② 联网巡检（错位 / 版本比对，需联网）")
        row2 = QHBoxLayout()
        self.btn_mismatch = QPushButton("错位检测")
        self.btn_mismatch.setObjectName("accent")
        self.btn_mismatch.clicked.connect(self.start_mismatch)
        self.btn_ver = QPushButton("版本检测")
        self.btn_ver.setObjectName("accent")
        self.btn_ver.clicked.connect(self.start_version)
        self.btn_ver.setEnabled(False)
        row2.addWidget(self.btn_mismatch)
        row2.addWidget(self.btn_ver)
        row2.addStretch(1)
        self.root.addLayout(row2)

        self.mismatch_bar = QProgressBar()
        self.mismatch_bar.setValue(0)
        self.mismatch_bar.setFormat("")
        self.root.addWidget(self.mismatch_bar)

        self.list_mismatch = QListWidget()
        self.list_mismatch.setObjectName("obs")
        self.list_mismatch.setMinimumHeight(90)
        self.root.addWidget(self.list_mismatch)

        row3 = QHBoxLayout()
        self.btn_fix_mismatch = QPushButton("一键纠正错位")
        self.btn_fix_mismatch.setObjectName("secondary")
        self.btn_fix_mismatch.setEnabled(False)
        self.btn_fix_mismatch.clicked.connect(self.start_fix_mismatch)
        row3.addWidget(self.btn_fix_mismatch)
        row3.addStretch(1)
        self.root.addLayout(row3)

        # 版本检测区（独立进度 + 列表）
        self.ver_bar = QProgressBar()
        self.ver_bar.setValue(0)
        self.ver_bar.setFormat("")
        self.root.addWidget(self.ver_bar)
        self.list_ver = QListWidget()
        self.list_ver.setObjectName("obs")
        self.list_ver.setMinimumHeight(90)
        self.root.addWidget(self.list_ver)

        self.root.addSpacing(10)

        # ═══════════ ③ 本体补全（独立）═══════════
        _section(self, "③ 本体补全（缺 zip/unitypackage 等，需联网）")
        row4 = QHBoxLayout()
        self.btn_backfill_scan = QPushButton("检测缺本体")
        self.btn_backfill_scan.setObjectName("accent")
        self.btn_backfill_scan.clicked.connect(self.start_backfill_scan)
        self.btn_backfill = QPushButton("一键补全本体")
        self.btn_backfill.setObjectName("secondary")
        self.btn_backfill.setEnabled(False)
        self.btn_backfill.clicked.connect(self.start_backfill)
        self.lbl_backfill = QLabel("")
        self.lbl_backfill.setObjectName("muted")
        self.lbl_backfill.setProperty("mono", "1")
        row4.addWidget(self.btn_backfill_scan)
        row4.addWidget(self.btn_backfill)
        row4.addStretch(1)
        row4.addWidget(self.lbl_backfill)
        self.root.addLayout(row4)

        self.backfill_bar = QProgressBar()
        self.backfill_bar.setValue(0)
        self.backfill_bar.setFormat("")
        self.root.addWidget(self.backfill_bar)

        self.list_backfill = QListWidget()
        self.list_backfill.setObjectName("obs")
        self.list_backfill.setMinimumHeight(90)
        self.root.addWidget(self.list_backfill)

        self.spacer()

    # ──────── ① 本地巡检 ────────
    def start_scan(self):
        root = self.main.config["booth_root"]
        if not Path(root).exists():
            ThemeDialog.warning(self, "路径无效",
                f"BOOTH 根目录不存在：\n{root}\n请在设置页配置。")
            return
        self.list_scan.clear()
        self.scan_bar.setValue(0)
        self.lbl_stat.setText("巡检中…")
        self.btn_scan.setEnabled(False)
        self.btn_fix.setEnabled(False)
        self.btn_ver.setEnabled(False)
        self.scan_worker = ScanWorker(root)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.item.connect(self.on_scan_item)
        self.scan_worker.done.connect(self.on_scan_done)
        self.scan_worker.start()

    def _on_scan_progress(self, done, total):
        if total:
            self.scan_bar.setValue(int(done / total * 100))
            self.scan_bar.setFormat(f"扫描 {done}/{total}")
        else:
            self.scan_bar.setFormat("无商品目录")

    def on_scan_item(self, it):
        if it["missing"]:
            tag = "缺" + "/".join(it["missing"])
        else:
            tag = "完整"
        body_tag = " ⚠缺本体" if it.get("body_missing") else ""
        self.list_scan.addItem(f"{it['id']} · {it['name']}   [{tag}]{body_tag}")

    def on_scan_done(self, items):
        self.scan_items = items
        self._all_scan_items = items
        total = len(items)
        missing = sum(1 for i in items if i["missing"])
        self.lbl_stat.setText(f"共 {total} 件，{missing} 件缺失三件套")
        self.badge_ok.setText(f"完整 {total - missing}")
        self.badge_miss.setText(f"缺失 {missing}")
        self.scan_bar.setFormat(f"完成（{total} 件）")
        self.scan_bar.setValue(100)
        self.btn_scan.setEnabled(True)
        self.btn_fix.setEnabled(missing > 0)
        self.btn_ver.setEnabled(total > 0)
        self.main.set_status(f"巡检完成：{total} 件，{missing} 件待修复")

    def start_fix(self):
        if not self.scan_items:
            return
        cfg = self.main.config
        self.list_scan.addItem("── 修复日志 ──")
        self.btn_fix.setEnabled(False)
        self.fix_worker = FixWorker(
            self.scan_items, cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.fix_worker.prog.connect(lambda m: self.list_scan.addItem(m))
        self.fix_worker.finished.connect(self.on_fix_done)
        self.fix_worker.start()

    def on_fix_done(self, fixed):
        self.list_scan.addItem(f"修复完成：{fixed} 件已重建三件套")
        self.btn_fix.setEnabled(False)
        self.main.set_status(f"三件套修复完成：{fixed} 件")

    # ──────── ② 联网巡检：错位检测 ────────
    def start_mismatch(self):
        if not self.scan_items:
            # 若没扫过，先快速本地扫描再错位检测
            self.list_mismatch.clear()
            self.mismatch_bar.setFormat("先做本地巡检…")
            root = self.main.config["booth_root"]
            self.scan_worker = ScanWorker(root)
            self.scan_worker.done.connect(self._run_mismatch_after_scan)
            self.scan_worker.start()
            return
        self._run_mismatch_after_scan(self.scan_items)

    def _run_mismatch_after_scan(self, items):
        self._all_scan_items = items
        self.list_mismatch.clear()
        self.mismatch_bar.setValue(0)
        self.btn_mismatch.setEnabled(False)
        cfg = self.main.config
        self.mismatch_worker = MismatchWorker(
            items, cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.mismatch_worker.progress.connect(self._on_mismatch_progress)
        self.mismatch_worker.mismatch.connect(self.on_mismatch_item)
        self.mismatch_worker.done.connect(self.on_mismatch_done)
        self.mismatch_worker.start()

    def _on_mismatch_progress(self, done, total):
        if total:
            self.mismatch_bar.setValue(int(done / total * 100))
            self.mismatch_bar.setFormat(f"错位检测 {done}/{total}")

    def on_mismatch_item(self, m):
        self.list_mismatch.addItem(
            f"{m['id']} · {m['name']}   [{m['wrong_cat']} → 期望 {m['dest_cat']}]")

    def on_mismatch_done(self, items):
        self._mismatch_items = items
        self.mismatch_bar.setFormat(f"完成（发现 {len(items)} 件错位）")
        self.mismatch_bar.setValue(100)
        self.btn_mismatch.setEnabled(True)
        self.btn_fix_mismatch.setEnabled(len(items) > 0)
        self.main.set_status(f"错位检测完成：{len(items)} 件")

    def start_fix_mismatch(self):
        items = self._mismatch_items
        if not items:
            return
        cfg = self.main.config
        self.btn_fix_mismatch.setEnabled(False)
        self.list_mismatch.addItem("── 纠正日志 ──")
        self.fix_mismatch_worker = FixMismatchWorker(items, cfg["booth_root"],
            cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.fix_mismatch_worker.prog.connect(self.list_mismatch.addItem)
        self.fix_mismatch_worker.finished.connect(self.on_fix_mismatch_done)
        self.fix_mismatch_worker.start()

    def on_fix_mismatch_done(self, fixed):
        n = len(self._mismatch_items)
        self.list_mismatch.addItem(f"── 纠正完成：{fixed}/{n} 件已重归档 ──")
        self.btn_fix_mismatch.setEnabled(False)
        self.main.set_status(f"错位纠正完成：{fixed} 件")

    # ──────── ② 联网巡检：版本检测 ────────
    def start_version(self):
        if not self.scan_items:
            ThemeDialog.information(self, "提示", "请先执行本地巡检，再比对版本。")
            return
        cfg = self.main.config
        self.list_ver.clear()
        self.ver_bar.setValue(0)
        self.btn_ver.setEnabled(False)
        self.ver_worker = VersionWorker(
            self.scan_items, cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.ver_worker.found.connect(self.on_ver_found)
        self.ver_worker.progress.connect(self._on_ver_progress)
        self.ver_worker.prog.connect(lambda m: self.main.set_status(m))
        self.ver_worker.finished.connect(self.on_ver_done)
        self.ver_worker.start()

    def _on_ver_progress(self, done, total):
        if total:
            self.ver_bar.setValue(int(done / total * 100))
            self.ver_bar.setFormat(f"版本比对 {done}/{total}")

    def on_ver_found(self, r):
        self.list_ver.addItem(
            f"{r['id']} · {r['name']}   本地 {r['local'] or '-'} → 官方 {r['official']}  可更新")

    def on_ver_done(self):
        self.ver_bar.setValue(100)
        self.ver_bar.setFormat(f"完成（{self.list_ver.count()} 件可更新）")
        self.btn_ver.setEnabled(True)
        self.main.set_status("版本巡检完成")

    # ──────── ③ 本体补全 ────────
    def start_backfill_scan(self):
        """本地快速扫描（三件套 + 本体缺失），秒级。"""
        root = self.main.config["booth_root"]
        if not Path(root).exists():
            ThemeDialog.warning(self, "路径无效",
                f"BOOTH 根目录不存在：\n{root}\n请在设置页配置。")
            return
        self.list_backfill.clear()
        self.backfill_bar.setValue(0)
        self.btn_backfill_scan.setEnabled(False)
        self.btn_backfill.setEnabled(False)
        self.lbl_backfill.setText("本体检测中…")
        self.scan_worker = ScanWorker(root)
        self.scan_worker.progress.connect(self._on_backfill_scan_progress)
        self.scan_worker.done.connect(self.on_backfill_scan_done)
        self.scan_worker.start()

    def _on_backfill_scan_progress(self, done, total):
        if total:
            self.backfill_bar.setValue(int(done / total * 100))
            self.backfill_bar.setFormat(f"本体扫描 {done}/{total}")

    def on_backfill_scan_done(self, items):
        self._all_scan_items = items
        body_missing = [it for it in items if it.get("body_missing")]
        self.list_backfill.clear()
        for it in body_missing:
            self.list_backfill.addItem(f"{it['id']} · {it['name']}   ⚠缺本体")
        self.backfill_bar.setFormat(f"完成（发现 {len(body_missing)} 件缺本体）")
        self.backfill_bar.setValue(100)
        self.btn_backfill_scan.setEnabled(True)
        self.btn_backfill.setEnabled(len(body_missing) > 0)
        if body_missing:
            self.lbl_backfill.setText(f"发现 {len(body_missing)} 件缺本体")
        else:
            self.lbl_backfill.setText("无本体缺失 ✓")
        self.main.set_status(f"本体检测完成：{len(body_missing)} 件缺本体")

    def start_backfill(self):
        items = getattr(self, "_all_scan_items", [])
        body_items = [it for it in items if it.get("body_missing")]
        if not body_items:
            return
        cfg = self.main.config
        self.btn_backfill.setEnabled(False)
        self.btn_backfill_scan.setEnabled(False)
        self.lbl_backfill.setText(f"正在补全 {len(body_items)} 件…")
        self.list_backfill.addItem("── 补全日志 ──")
        self.backfill_worker = BackfillWorker(body_items, cfg["booth_root"],
            cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.backfill_worker.progress.connect(self._on_backfill_progress)
        self.backfill_worker.prog.connect(self.list_backfill.addItem)
        self.backfill_worker.finished.connect(self.on_backfill_done)
        self.backfill_worker.start()

    def _on_backfill_progress(self, done, total):
        if total:
            self.backfill_bar.setValue(int(done / total * 100))
            self.backfill_bar.setFormat(f"补全下载 {done}/{total}")

    def on_backfill_done(self, fixed):
        n = len([it for it in getattr(self, "_all_scan_items", [])
                  if it.get("body_missing")])
        self.lbl_backfill.setText(f"补全完成：{fixed}/{n} 件")
        self.backfill_bar.setFormat(f"完成（{fixed} 件已下载）")
        self.backfill_bar.setValue(100)
        self.btn_backfill.setEnabled(False)
        self.btn_backfill_scan.setEnabled(True)
        self.list_backfill.addItem(f"── 补全完成：{fixed} 件本体已下载 ──")
        self.main.set_status(f"本体补全完成：{fixed} 件")