#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bk_local — 本地目录扫描、包完整性与版本隔离

由 booth_core.py 拆分而来（R23）。纯粹操作磁盘：判断目录是否含本体文件、
解析压缩包是否损坏、把旧版本文件移入 v{N}/ 子目录。不发任何网络请求。
"""

import os
import re
import io
import gzip
import zipfile
import tarfile
import diag
from pathlib import Path
from bk_text import *
from bk_text import _VERSION_RE

__all__ = [
    "BODY_EXTENSIONS",
    "has_body",
    "is_corrupt_package",
    "isolate_old_versions",
    "probe_package",
    "scan_corrupt_in_library",
]




# R7 修复：本体的扩展名（商品文件类型）—— R12 移到 booth_core 供 archive_util 复用
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


def probe_package(path: str | Path,
                  max_upkg_bytes: int = 80 * 1024 * 1024) -> dict:
    """从本地 zip / unitypackage / 文件夹提取检索信号（R17 多信号）。

    返回:
      {
        "kind": "zip" | "upkg" | "dir" | "none",
        "outer": 外层文件名去扩展的清洗名（原始信号）,
        "authors": [作者/社团名候选],   # 包内 Assets 第一层（BLVK, SNOW_XTAL 等）
        "names":   [商品名候选],         # 包内第二层 + 顶层文件名（NailRing, CatHeart_acc）
        "count": 解析到的条目数,
      }

    动机：unitypackage 路径 Assets/{作者}/{商品}/... 天然拆开作者与商品；
    BOOTH 搜索时「作者 + 商品」组合命中率远高于单独商品名。"""
    p = Path(path)
    outer = sanitize_filename(str(p.stem)).strip()
    authors, names, count = [], [], 0

    def _feed_upkg(data: bytes):
        nonlocal count
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                for m in tf:
                    if not m.isfile() or os.path.basename(m.name) != "pathname":
                        continue
                    f = tf.extractfile(m)
                    if not f:
                        continue
                    s = f.read().decode("utf-8", "ignore").strip()
                    parts = [x for x in s.replace("\\", "/").split("/") if x]
                    idx = 1 if parts and parts[0].lower() == "assets" and len(parts) > 1 else 0
                    if len(parts) > idx:
                        a = sanitize_filename(parts[idx]).strip()
                        if a and len(a) >= 2:
                            authors.append(a)
                    if len(parts) > idx + 1:
                        nm = sanitize_filename(parts[idx + 1]).strip()
                        if nm and len(nm) >= 2:
                            names.append(nm)
                        count += 1
        except Exception:
            pass

    try:
        if p.is_dir():
            kind = "dir"
            for child in sorted(p.iterdir()):
                if child.is_file():
                    nm = sanitize_filename(child.stem).strip()
                    if nm and len(nm) >= 2:
                        names.append(nm)
                    if child.suffix.lower() == ".unitypackage" and child.stat().st_size <= max_upkg_bytes:
                        try:
                            _feed_upkg(child.read_bytes())
                        except Exception:
                            pass
                elif child.is_dir():
                    a = sanitize_filename(child.name).strip()
                    if a and len(a) >= 2:
                        authors.append(a)
        elif p.suffix.lower() == ".zip":
            kind = "zip"
            with zipfile.ZipFile(p) as z:
                for n in z.namelist()[:400]:
                    parts = [x for x in n.replace("\\", "/").split("/") if x]
                    base = sanitize_filename(os.path.splitext(parts[-1])[0]).strip() if parts else ""
                    if base and len(base) >= 2 and not base.startswith("__MACOSX"):
                        if len(parts) == 1:
                            names.append(base)
                        else:
                            authors.append(base)  # 顶层目录名（作者/通用目录）
                    if n.lower().endswith(".unitypackage"):
                        try:
                            if z.getinfo(n).file_size <= max_upkg_bytes:
                                _feed_upkg(z.read(n))
                        except Exception:
                            pass
        elif p.suffix.lower() == ".unitypackage":
            kind = "upkg"
            if p.stat().st_size <= max_upkg_bytes:
                _feed_upkg(p.read_bytes())
        else:
            kind = "none"
    except Exception:
        kind = "none"

    # 去重保留顺序；过滤常见通用目录名
    DROP = {"textures", "material", "materials", "prefab", "prefabs", "fbx",
            "animation", "animations", "shader", "shaders", "psd", "scripts",
            "resources", "assets", "models", "docs", "readme", "sample"}
    authors = list(dict.fromkeys(a for a in authors if a.lower() not in DROP))
    names = list(dict.fromkeys(n for n in names if n.lower() not in DROP))
    return {"kind": kind, "outer": outer, "authors": authors[:6],
            "names": names[:8], "count": count}


def is_corrupt_package(path: str | Path) -> bool:
    """校验本地压缩包完整性。

    - zip：is_zipfile + 读中央目录（截断/坏 zip → BadZipFile → 判损坏）
    - unitypackage：gzip + tarfile 能列条目
    - rar / 7z：无内置解析库 → 不误报，返回 False

    背景：『已存在且 size>0 就跳过』会把断下载残留的半截文件当已完成，
    用户换节点/换代理重跑会跳过损坏文件（R18 bug）。下载前必须二次校验。"""
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext == ".zip":
            if not zipfile.is_zipfile(p):
                return True
            with zipfile.ZipFile(p) as z:
                _ = z.namelist()      # 触发中央目录读取；损坏 → BadZipFile
            return False
        if ext == ".unitypackage":
            with gzip.open(p, "rb") as g:
                with tarfile.open(fileobj=g, mode="r:") as tf:
                    tf.next()      # TarFile 非迭代器，须用 .next()；损坏 → ReadError
            return False
    except Exception:
        return True
    return False  # rar/7z 无法校验


def scan_corrupt_in_library(root: str | Path) -> list[dict]:
    """扫描 BOOTH 库全目录，返回损坏包清单 [{path, iid, size}]（R18 修复用）。"""
    root = Path(root)
    out = []
    for d in root.rglob("*"):
        if not d.is_dir():
            continue
        m = re.match(r"^(\d{5,8})_", d.name)
        if not m:
            continue
        for f in d.iterdir():
            if not f.is_file():
                continue
            if f.suffix.lower() not in (".zip", ".unitypackage"):
                continue
            if is_corrupt_package(f):
                out.append({"path": str(f), "iid": m.group(1), "size": f.stat().st_size})
    return out


def _version_of(name: str) -> str:
    """从文件名提取版本号（'V1' / 'v1.0.1' / 'Ver 2.00' / '1.01'），无则空串。"""
    s = Path(name).stem
    m = re.search(r"(?:v(?:er(?:sion)?)?\s*[._\-\s]*)(\d+(?:\.\d+)*)", s, re.I)
    if m:
        return m.group(1)
    m = re.search(r"(\d+)\.(\d+)(?:\.\d+)*", s)
    if m:
        return m.group(0)
    return ""


def _versionless(name: str) -> str:
    """去掉版本号后的基名（小写、去分隔符），用于识别『同一商品不同版本』。"""
    s = re.sub(r"(?:v(?:er(?:sion)?)?\s*[._\-\s]*\d+(?:\.\d+)*)", "", name, flags=re.I)
    s = re.sub(r"\d+\.\d+(?:\.\d+)*", "", s)
    return re.sub(r"[\s_.\-]+", "", Path(s).stem).lower()


def _ver_tuple(s: str) -> tuple:
    return tuple(int(x) for x in re.split(r"[._\-]", s) if x.isdigit())


def isolate_old_versions(dest: str | Path, new_download_names: list[str]) -> list[str]:
    """R20 版本隔离（慎之勇者预案）：下载列表含新版本时，
    把目录根的旧版本包移入 `v{旧版本号}/` 子目录，新版保持在外层。

    例：根目录已有 MoonlightPostKipV1.zip，downloads 含 MoonlightPostKipV2.zip
      → MoonlightPostKipV1.zip 移入 v1/。旧的损坏/完好都移，保留历史版本。
    返回已移动的文件名列表。"""
    dest = Path(dest)
    moved = []
    root_files = [f for f in dest.iterdir()
                  if f.is_file() and f.suffix.lower() in (".zip", ".unitypackage")
                  and not f.name.startswith("_")]
    for nf in new_download_names:
        if not nf:
            continue
        nkey = _versionless(nf)
        nver = _version_of(nf)
        if not nkey or not nver:
            continue
        for f in root_files:
            fkey = _versionless(f.name)
            fver = _version_of(f.name)
            if fkey == nkey and fver and fver != nver and _ver_tuple(fver) < _ver_tuple(nver):
                sub = dest / f"v{fver}"
                try:
                    sub.mkdir(parents=True, exist_ok=True)
                    f.rename(sub / f.name)
                    moved.append(f.name)
                except Exception as e:
                    # R23：隔离失败留痕。原先静默吞掉 → 旧版本文件原地残留，
                    # 用户却以为已归入 v<版本> 子目录（磁盘状态与预期不符）。
                    diag.warn(f"旧版本隔离失败：{f.name} ({e})",
                              scope="isolate_old_versions", file=f.name)
    return moved
