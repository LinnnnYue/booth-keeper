# pages/audit_page.py — 目录巡检与版本巡检
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


def scan_library(root):
    """遍历 BOOTH 库，定位 ID_标题 商品目录，检查三件套并提取本地版本。"""
    root = Path(root)
    out = []
    if not root.exists():
        return out
    for d in root.rglob("*"):
        if not d.is_dir():
            continue
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
        out.append({
            "id": iid, "name": name, "path": str(d),
            "missing": missing, "local_tag": bc.extract_version_tag(d.name),
        })
    return out


class ScanWorker(QThread):
    """R8 强化：扫描同时联网比对官方分类，错位项通过 mismatch 信号单独 emit。"""
    item = Signal(dict)
    done = Signal(list)
    mismatch = Signal(dict)        # 单件错位：{id, name, wrong_cat, dest_cat, wrong_path}
    mismatch_done = Signal(list)    # 全部错位 list

    def __init__(self, root, proxy=False, proxy_url="", cookie=""):
        super().__init__()
        self.root = root
        self.proxy = proxy
        self.proxy_url = proxy_url
        self.cookie = cookie

    def run(self):
        items = scan_library(self.root)
        for it in items:
            self.item.emit(it)
        self.done.emit(items)
        # 联网错位检测（遍历 items，fetch_item 拿官方分类）
        s = bc.make_session(self.cookie)
        if self.proxy:
            s.proxies.update({"http": self.proxy_url, "https": self.proxy_url})
        mismatches = []
        for it in items:
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
        self.mismatch_done.emit(mismatches)


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


class FixWorker(QThread):
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
    found = Signal(dict)
    prog = Signal(str)
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
        for it in self.items:
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


class AuditPage(BasePage):
    def __init__(self, main):
        super().__init__(main)
        self.header("目录巡检", "巡检 BOOTH 库的三件套完整性与命名规范；实验性联网比对官方版本号")
        self.scan_items = []
        self.scan_worker = self.fix_worker = self.ver_worker = None

        # 本地巡检
        row1 = QHBoxLayout()
        self.btn_scan = QPushButton("开始巡检")
        self.btn_scan.setObjectName("accent")
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_fix = QPushButton("修复缺失三件套")
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

        self.list_scan = QListWidget()
        self.list_scan.setObjectName("obs")
        self.list_scan.setMinimumHeight(220)
        self.root.addWidget(self.list_scan)

        # 巡检结果徽章（主题化 badge：数字等宽 + 状态色块）
        self.badge_ok = QLabel("完整 0")
        self.badge_ok.setProperty("badge", "ok")
        self.badge_miss = QLabel("缺失 0")
        self.badge_miss.setProperty("badge", "warn")
        brow = QHBoxLayout()
        brow.addWidget(self.badge_ok)
        brow.addWidget(self.badge_miss)
        brow.addStretch(1)
        self.root.addLayout(brow)

        self.root.addSpacing(8)

        # 版本巡检（实验性）
        warn = QLabel("实验性功能：联网比对官方商品名中的版本号，可能不准确，更新前请人工核对。")
        warn.setObjectName("muted")
        warn.setWordWrap(True)
        self.root.addWidget(warn)

        row2 = QHBoxLayout()
        self.btn_ver = QPushButton("开始版本巡检")
        self.btn_ver.setObjectName("accent")
        self.btn_ver.clicked.connect(self.start_version)
        self.btn_ver.setEnabled(False)
        self.lbl_vstat = QLabel("")
        self.lbl_vstat.setObjectName("muted")
        self.lbl_vstat.setProperty("mono", "1")
        row2.addWidget(self.btn_ver)
        row2.addStretch(1)
        row2.addWidget(self.lbl_vstat)
        self.root.addLayout(row2)

        self.bar = QProgressBar()
        self.root.addWidget(self.bar)

        self.list_ver = QListWidget()
        self.list_ver.setObjectName("obs")
        self.list_ver.setMinimumHeight(150)
        self.root.addWidget(self.list_ver)
        self.spacer()

        # R8：错位纠正区（巡检同步跑）
        warn2 = QLabel("错位纠正：扫描时同步联网比对官方分类，错位项目列于此。点下方按钮一键重归档。")
        warn2.setObjectName("muted")
        warn2.setWordWrap(True)
        self.root.addWidget(warn2)

        row3 = QHBoxLayout()
        self.btn_mismatch = QPushButton("一键纠正错位")
        self.btn_mismatch.setObjectName("accent")
        self.btn_mismatch.clicked.connect(self.start_fix_mismatch)
        self.btn_mismatch.setEnabled(False)
        self.lbl_mismatch = QLabel("")
        self.lbl_mismatch.setObjectName("muted")
        self.lbl_mismatch.setProperty("mono", "1")
        row3.addWidget(self.btn_mismatch)
        row3.addStretch(1)
        row3.addWidget(self.lbl_mismatch)
        self.root.addLayout(row3)

        self.list_mismatch = QListWidget()
        self.list_mismatch.setObjectName("obs")
        self.list_mismatch.setMinimumHeight(120)
        self.root.addWidget(self.list_mismatch)

    # ---- 本地巡检 ----
    def start_scan(self):
        root = self.main.config["booth_root"]
        if not Path(root).exists():
            ThemeDialog.warning(self, "路径无效",
                f"BOOTH 根目录不存在：\n{root}\n请在设置页配置。")
            return
        self.list_scan.clear()
        self.list_mismatch.clear()
        self.lbl_stat.setText("巡检中…")
        self.lbl_mismatch.setText("错位检测中…")
        self.btn_scan.setEnabled(False)
        self.btn_fix.setEnabled(False)
        self.btn_ver.setEnabled(False)
        self.btn_mismatch.setEnabled(False)
        cfg = self.main.config
        # R8：本地巡检 + 联网错位检测一并跑（一个 worker 跑完两项）
        self.scan_worker = ScanWorker(root, cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.scan_worker.item.connect(self.on_scan_item)
        self.scan_worker.done.connect(self.on_scan_done)
        self.scan_worker.mismatch.connect(self.on_mismatch_item)
        self.scan_worker.mismatch_done.connect(self.on_mismatch_done)
        self.scan_worker.start()

    def on_scan_item(self, it):
        if it["missing"]:
            tag = "缺" + "/".join(it["missing"])
        else:
            tag = "完整"
        self.list_scan.addItem(f"{it['id']} · {it['name']}   [{tag}]")

    def on_mismatch_item(self, m):
        """R8 错位项信号（联网比对）。"""
        self.list_mismatch.addItem(
            f"{m['id']} · {m['name']}   [{m['wrong_cat']} → 期望 {m['dest_cat']}]")

    def on_mismatch_done(self, items):
        """R8 错位检测完成，启用一键纠正按钮。"""
        self._mismatch_items = items
        if items:
            self.lbl_mismatch.setText(f"检测到 {len(items)} 件错位")
            self.btn_mismatch.setEnabled(True)
        else:
            self.lbl_mismatch.setText("无错位 ✓")
            self.btn_mismatch.setEnabled(False)

    def start_fix_mismatch(self):
        """R8 一键纠正错位：单件 archive_item(force=True) 从 wrong 移到 dest。"""
        items = getattr(self, "_mismatch_items", [])
        if not items:
            return
        cfg = self.main.config
        self.btn_mismatch.setEnabled(False)
        self.lbl_mismatch.setText(f"正在纠正 {len(items)} 件…")
        self.fix_mismatch_worker = FixMismatchWorker(items, cfg["booth_root"],
            cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.fix_mismatch_worker.prog.connect(self.list_mismatch.addItem)
        self.fix_mismatch_worker.finished.connect(self.on_fix_mismatch_done)
        self.fix_mismatch_worker.start()

    def on_fix_mismatch_done(self, fixed):
        n = len(getattr(self, "_mismatch_items", []))
        self.lbl_mismatch.setText(f"纠正完成：{fixed}/{n} 件")
        self.btn_mismatch.setEnabled(False)
        self.list_mismatch.addItem(f"── 纠正完成：{fixed} 件已重归档 ──")
        self.main.set_status(f"错位纠正完成：{fixed} 件")

    def on_scan_done(self, items):
        self.scan_items = items
        total = len(items)
        missing = sum(1 for i in items if i["missing"])
        self.lbl_stat.setText(f"共 {total} 件，{missing} 件缺失三件套")
        self.badge_ok.setText(f"完整 {total - missing}")
        self.badge_miss.setText(f"缺失 {missing}")
        self.btn_scan.setEnabled(True)
        self.btn_fix.setEnabled(missing > 0)
        self.btn_ver.setEnabled(total > 0)
        self.main.set_status(f"巡检完成：{total} 件，{missing} 件待修复")

    # ---- 修复 ----
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

    # ---- 版本巡检 ----
    def start_version(self):
        if not self.scan_items:
            ThemeDialog.information(self, "提示", "请先执行本地巡检，再比对版本。")
            return
        cfg = self.main.config
        self.list_ver.clear()
        self.bar.setValue(0)
        self.btn_ver.setEnabled(False)
        self.ver_worker = VersionWorker(
            self.scan_items, cfg["proxy"], cfg["proxy_url"], cfg["cookie"])
        self.ver_worker.found.connect(self.on_ver_found)
        self.ver_worker.prog.connect(lambda m: self.main.set_status(m))
        self.ver_worker.finished.connect(self.on_ver_done)
        self.ver_worker.start()

    def on_ver_found(self, r):
        self.list_ver.addItem(
            f"{r['id']} · {r['name']}   本地 {r['local'] or '-'} → 官方 {r['official']}  可更新")

    def on_ver_done(self):
        self.bar.setValue(100)
        self.btn_ver.setEnabled(True)
        if self.list_ver.count() == 0:
            self.lbl_vstat.setText("未检测到更高版本")
        else:
            self.lbl_vstat.setText(f"发现 {self.list_ver.count()} 件可更新")
        self.main.set_status("版本巡检完成")
