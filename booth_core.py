#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
booth_common.py — BOOTH 技能共享层（三合一）

统一三子技能（free-collector 下载 / archive-organizer 按ID整理 / name-search 按名搜索）
的公共逻辑：CATEGORY_MAP + 分类汉化 + BOOTH 请求会话 + 封面下载 + 文件夹图标三件套
（含完整性契约）+ 文件名清洗（装饰 Unicode 过滤 + 驼峰拆词 + 纯日文主体搜索）。

用法（由 booth.py 子命令调用，不直接运行）。
"""
import os
import re
import sys
import io
import time
import gzip
import ctypes
import tempfile
import zipfile
import tarfile
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image

try:
    from send2trash import send2trash
except Exception:
    send2trash = None

# ── 常量 ──────────────────────────────────────────────────────────
BOOTH_BASE = "https://booth.pm/ja"
SEARCH_URL = f"{BOOTH_BASE}/items"
ITEM_JSON  = f"{BOOTH_BASE}/items/{{id}}.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
      "Accept-Language": "ja,en;q=0.9,zh-CN;q=0.8"}
PROXY = os.environ.get("HTTPS_PROXY", "http://127.0.0.1:20122/")
MAX_RETRIES = 3
INVALID = r'<>:"/\\|?*'

# ── BOOTH 类目 → 中文（统一 30+ 映射；key 取自 JSON category.name）──
CATEGORY_MAP = {
    # 3D / VRChat 头像系
    "3Dアバター": "3D头像", "3D衣装・アクセサリー": "3D服饰",
    "3Dモデル": "3D模型", "3Dモデル（その他）": "3D模型（其他）",
    "3D装飾品": "3D饰品", "3D環境・ワールド": "3D环境",
    "3Dキャラクター": "3D角色", "3D小道具": "3D道具",
    "アバター": "头像", "アバターアイテム": "头像物品", "アバターギミック": "头像机关",
    "アクセサリ": "饰品", "アクセサリー": "饰品", "衣装・アクセサリー": "服饰饰品",
    "衣装": "服饰",
    # R7 修复：主上 BOOTH 根目录现有『3D发型』目录，但 BOOTH 的 ヘアー/髪/ヘア 全部归父级 3Dモデル
    # → 映射从「发型」改成「3D发型」与主上现有目录同前缀，避免新建「发型」目录
    "髪": "3D发型", "ヘアー": "3D发型", "ヘア": "3D发型",
    # R12 修复：BOOTH 现在用「中日表示」（日文汉字混合）cat_name = "3Dxxx"，
    # 漏映射会 fallback 父级 "3Dモデル" → "3D模型" 误判。
    # 补全 BOOTH 子分类中日表示映射：
    "3D髪型": "3D发型",      # 3D Hair（8674016 等）
    "3D衣装": "3D服饰",      # 3D Clothing（4689398 等）
    "3D小道具": "3D道具",     # 3D Prop（7447820 等）
    "3Dモーション・アニメーション": "3D动作",  # 3D Motion
    "バッジ": "徽章",
    "モーション": "动作", "ギミック": "机关", "リギング": "绑定",
    "テクスチャ": "贴图", "テクスチャ素材": "贴图素材", "シェーダー": "着色器",
    "エフェクト": "特效", "ツール": "工具", "ツール・プラグイン": "工具插件",
    "物理": "物理", "VR": "VR",
    "3Dモーション・アニメーション": "3D动作",
    "3Dツール・システム": "3D工具", "3D衣装": "3D服饰",
    # R7+1 修复：补全「3Dモーション / 3Dモーション」（笔误），「3Dシェーダー・マテリアル」用主上已有的「着色器」
    "3Dモーション": "3D动作", "3Dシェーダー・マテリアル": "着色器",
    "3Dテクスチャ": "3D贴图",
    "テクスチャ・素材": "贴图素材",
    # R12+1 修复：BOOTH 官网类目「ソフトウェア」「素材（その他）」缺映射 → 新建日语目录
    "ソフトウェア": "软件",
    "ソフトウェア・ハードウェア": "软件",
    "素材（その他）": "素材数据",  # その他=其他，归入素材数据
    # 音频 / 素材 / 视觉
    "ﾓｼﾞｬｰﾙｱｲﾃﾑ": "AR物品", "音声": "语音", "効果音・SE": "音效",
    "BGM": "BGM", "素材": "素材", "イラスト": "插画", "漫画": "漫画",
    "小説": "小说", "ポスター": "海报", "その他": "其他",
    # 游戏 / VRChat 道具（付费重灾区）
    "ゲーム": "游戏", "ゲーム関連商品": "游戏相关", "フリーゲーム": "免费游戏",
    # 下载器补充（与 name-search 同源，防目录分裂）
    "3Dテクスチャ": "3D贴图", "3D衣装": "3D服饰", "3D装飾品": "3D饰品",
    "3Dモデル": "3D模型", "3Dキャラクター": "3D角色", "3D小道具": "3D道具",
    "3D環境・ワールド": "3D环境", "3Dモーション・アニメーション": "3D动作",
    "3Dツール・システム": "3D工具", "ポスター": "海报", "イラスト": "插画",
    "素材データ": "素材数据", "音楽": "音乐",
    # R7+1 修复：去重「アバター」，统一映射为「头像」（原来下载器补充里写了「虚拟形象」覆盖了上文的「头像」）
    # 后续「アバターアイテム/アバターギミック」也同步统一为头像子项
    "アクセサリー": "配饰",
}
CATEGORY_PARENT_MAP = {"3Dモデル": "3D模型", "ゲーム": "游戏", "アバター": "头像"}

# R7+1：父类属于以下时，子分类强制加 3D 前缀
_THREED_PARENTS = frozenset({
    "3Dモデル",
    "3Dモデル（その他）",
    "3D衣装・アクセサリー",
    "アバター",  # 头像下子项也是 3D（衣服/饰品/发型都按 3D）
})


def classify(cat_name: str, cat_parent: str = "") -> str:
    """BOOTH 类目 → 中文。优先精确；退回父级；再退回保留日文原名（绝不臆造）。

    R7+1 父级 3D 前缀规则：当父类是 3D 系（3Dモデル / 3Dモデル（その他）/ アバター），
    但 cat_name 映射出的中文不含「3D」前缀时，自动补「3D」前缀——让子分类归入主上
    现有 3D前缀目录结构（如 衣装 + 3Dモデル → 3D服饰 而非服饰）。
    """
    if not cat_name:
        return "未分类"
    if cat_name in CATEGORY_MAP:
        result = CATEGORY_MAP[cat_name]
    elif cat_parent and cat_parent in CATEGORY_MAP:
        result = CATEGORY_MAP[cat_parent]
    elif cat_parent and cat_parent in CATEGORY_PARENT_MAP:
        result = CATEGORY_PARENT_MAP[cat_parent]
    else:
        result = cat_name  # 兜底不臆造
    # R7+1 父级 3D 前缀规则（白名单父类）
    if cat_parent in _THREED_PARENTS and not result.startswith("3D"):
        return "3D" + result
    return result


# ── 请求会话 ──────────────────────────────────────────────────────
def make_session(cookie: str = "", ua: str = "") -> requests.Session:
    s = requests.Session()
    h = dict(UA)
    if ua:
        h["User-Agent"] = ua
    s.headers.update(h)
    if PROXY:
        s.proxies = {"https": PROXY, "http": PROXY}
    if cookie:
        load_cookie(s, cookie)
    return s


def retry_request(method: str, url: str, session: requests.Session,
                  retries: int | None = None, **kwargs):
    """transport 错误指数退避重试（ConnectionError/Timeout/ChunkedEncodingError）。
    HTTP 状态码留给调用方判断（404 页可优雅处理而非重试）。

    R16：新增 retries 参数——非关键请求（如封面下载）应快速失败，
    避免 timeout=60 × 3 次 导致单商品卡 3 分钟。"""
    n = int(retries) if retries else MAX_RETRIES
    for attempt in range(1, n + 1):
        try:
            return session.request(method, url, **kwargs)
        except (requests.ConnectionError, requests.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            if attempt < n:
                time.sleep(attempt * 2)
            else:
                raise


def load_cookie(session: requests.Session, cookie_arg: str):
    """cookie_arg: 'k=v; k2=v2' 串 / Netscape cookies.txt 路径 / 存原始 Cookie 串的文本文件路径。
    会话 Cookie 真名 `_plaza_session_nktz7u`，建议连同 cf_clearance 一起。"""
    if not cookie_arg:
        return
    p = Path(cookie_arg)
    if p.is_file():
        text = p.read_text(encoding="utf-8", errors="ignore").strip()
        if any("\t" in line and not line.startswith("#") for line in text.splitlines()):
            loaded = 0
            for line in text.splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 7 and "booth" in parts[0]:
                    session.cookies.set(parts[5], parts[6], domain=parts[0])
                    loaded += 1
            if loaded > 0:
                return
        cookie_arg = text
    for pair in cookie_arg.split(";"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            session.cookies.set(k.strip(), v.strip(), domain=".booth.pm")


# ── 元数据 / 封面 ────────────────────────────────────────────────
def _normalize_item(d: dict | None) -> dict | None:
    """把 BOOTH JSON API 的原始 dict 拍扁成调用方期望的 schema：

        id, name, category_name, category_parent, category_parent_name,
        images, shop, price, price_text, brand, thumbnail

    历史坑：R6 之前 fetch_item 直接返回 raw JSON，调用方（如 archive_item、LinksWorker
    的 classify(it.get("category_name"), it.get("category_parent_name"))）永远拿到 None，
    因为真键是 it["category"]["name"] / it["category"]["parent"]["name"]——全归「未分类」。
    统一在此规范化后所有调用方一致可用。raw JSON 存在 _raw 字段供审计用。"""
    if not d:
        return None
    cat = d.get("category") or {}
    cat_parent = cat.get("parent") or {}
    return {
        "id": str(d.get("id", "")),
        "name": d.get("name") or "",
        "category_name": cat.get("name") or "",
        "category_parent": cat_parent.get("name") or "",
        "category_parent_name": cat_parent.get("name") or "",
        "images": d.get("images") or [],
        "shop": d.get("shop") or {},
        "price": d.get("price"),
        "price_text": f"¥ {d.get('price')}" if d.get("price") is not None else "",
        "brand": (d.get("shop") or {}).get("name", "") or "",
        "thumbnail": _thumb_from_json(d),
        "_raw": d,  # 保留 raw 供审计/扩展
    }


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


def fetch_item(item_id: str, session: requests.Session | None = None) -> dict | None:
    """拉 BOOTH JSON API 并返回规范化 schema。失败返回 None。"""
    s = session or make_session()
    try:
        r = retry_request("GET", ITEM_JSON.format(id=item_id), s,
                          headers={**UA, "Accept": "application/json"}, timeout=30)
        if r and r.status_code == 200:
            return _normalize_item(r.json())
    except Exception:
        pass
    return None


def probe_reachable(session: requests.Session | None = None,
                    timeout: int = 15) -> tuple[bool, str]:
    """连通性探针：确认 BOOTH 当前可达（网络/代理正常）。

    用 BOOTH 首页做探测端点。返回 (可达, 说明)。
    主上的严谨要求：判定「已下架」前必须先确认网络可达，
    否则 404 可能是网络/代理故障伪装的，不是真下架。"""
    s = session or make_session()
    try:
        r = retry_request("GET", BOOTH_BASE + "/", s, headers=UA,
                          timeout=timeout, retries=1)
        if r is None:
            return False, "请求无响应"
        return r.status_code < 500, f"HTTP {r.status_code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:60]}"


def probe_item_http(item_id: str, session: requests.Session | None = None,
                    timeout: int = 20) -> int | None:
    """探商品页 HTTP 状态码。None = 网络层异常（超时/代理断/连接失败）。

    与 fetch_item 的区别：无论如何都返回真实状态（200/404/其他），
    不把「网络坏了」和「商品下架」混为一谈。"""
    s = session or make_session()
    try:
        r = retry_request("GET", f"{BOOTH_BASE}/items/{item_id}", s,
                          headers={**UA, "Accept-Language": "ja;q=0.9"},
                          timeout=timeout, retries=1)
        return r.status_code if r is not None else None
    except Exception:
        return None


def classify_item_state(item_id: str,
                        session: requests.Session | None = None,
                        probe: bool = True) -> tuple[str, str]:
    """判定商品当前状态，返回 (state, 原因)。

    state 三态：
      - "ok"      可正常访问
      - "delisted" 真·已下架（BOOTH 可达 + 商品页确实 404）
      - "unknown"  无法判定（网络/代理异常，不妄断下架）

    严格逻辑（主上要求）：只有「连通性探针通过 + 商品 404」才判定已下架；
    网络不可达一律 unknown，避免把网络故障误判为商品下架。"""
    s = session or make_session()
    if probe:
        ok, why = probe_reachable(s, timeout=15)
        if not ok:
            return "unknown", f"BOOTH 当前不可达（{why}），无法判定是否下架"
    code = probe_item_http(item_id, s, timeout=20)
    if code == 200:
        return "ok", "商品页可正常访问"
    if code == 404:
        return "delisted", "商品页 404 且 BOOTH 可达 → 确为已下架"
    if code is None:
        return "unknown", "商品页请求异常（超时/代理断），无法判定"
    return "unknown", f"商品页返回 HTTP {code}（非 404），状态不明"


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


def build_search_queries(path: str | Path) -> list[str]:
    """由本地文件/文件夹生成搜索候选（顺序敏感，首个最可能命中）。"""
    sig = probe_package(path)
    cands, seen = [], set()
    outer = sig["outer"]

    def add(q):
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            cands.append(q)

    if outer:
        add(outer)
    for n in sig["names"]:
        add(n)
    for a in sig["authors"]:
        for n in sig["names"]:
            if a.lower() in n.lower():
                continue    # 名字已含作者（如 'BLVK NailRing'），避免 'BLVK BLVK NailRing'
            add(f"{a} {n}")  # 作者+商品 组合（最强过滤）
    for a in sig["authors"]:
        add(a)
    # 兜底：sanitize_query 老路（驼峰拆词 / 日文主体 / 去版本号）
    for q in sanitize_query(outer) if outer else []:
        add(q)
    return cands[:8]


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
                except Exception:
                    pass
    return moved


def rank_search_results(items: list[dict], sig: dict | None) -> list[dict]:
    """对搜索结果按输入信号打分排序（名称相似度 + 作者/店名命中加权）。

    依据 2026-08-31 全量学习：包内 Assets 首层目录多为作者名，
    结果店名/品牌命中作者名 → 强证据。返回 items 原样增 score 字段并降序。"""
    sig = sig or {}
    refs = [x for x in ([sig.get("outer", "")] + list(sig.get("names", []) or [])) if x]
    authors = list(sig.get("authors", []) or [])
    scored = []
    for it in items or []:
        name = it.get("name", "")
        s = max((name_similarity(name, r) for r in refs), default=0.0)
        shop = f"{it.get('shop','')} {it.get('brand','')}"
        if authors and any(a.lower() in shop.lower() for a in authors):
            s = min(1.0, s + 0.25)
        it["score"] = round(s, 2)
        scored.append(it)
    scored.sort(key=lambda x: -x.get("score", 0))
    return scored


def fetch_item_downloads(item_id: str, session: requests.Session | None = None) -> list[dict]:
    """从 BOOTH 商品页面 HTML 解析所有下载链接 + 文件名 + 大小。

    R9 修复：JSON API 的 `files` 字段为空——必须解析商品页面 HTML 找真实下载链接。
    返回 [{name, url, size_text, size_bytes}, ...]，失败返回 []。

    匹配规则（兼容 BOOTH 多语言/多模板）：
      - `https://booth.pm/downloadables/{file_id}?variation_id={var_id}` 主下载链接
      - 紧邻 <a> 内的文件名（`{filename}.zip` / `.unitypackage` 等）
      - 紧邻文件大小文本（`13.5 MB` / `1.2 GB`）
    """
    s = session or make_session()
    html_url = f"{BOOTH_BASE}/items/{item_id}"
    out: list[dict] = []
    try:
        r = retry_request("GET", html_url, s,
                          headers={**UA, "Accept-Language": "ja,en;q=0.9,zh-CN;q=0.8"},
                          timeout=30)
        if not r or r.status_code != 200:
            return out
        html = r.text
    except Exception:
        return out
    # BOOTH 下载按钮结构（实测 2026-08-16）：
    #   <a class="btn add-cart" title="RuinHalo_v1.01.zip"
    #      href="https://booth.pm/downloadables/6413961?variation_id=11372934">
    #     ...
    #     <span>RuinHalo_v1.01</span><div>.zip</div><div>&nbsp;(1.82 MB)</div>
    #   </a>
    # 提取逻辑：先按 href 匹配整段 <a ...>...</a> 块，从块内 title/span/div 拼文件名。
    a_block_re = re.compile(
        r"<a\b[^>]*?href=[\"']https?://booth\.pm/downloadables/\d+[^\"']*[\"'][^>]*>"
        r"(.*?)</a>",
        re.IGNORECASE | re.DOTALL)
    url_re = re.compile(
        r"https?://booth\.pm/downloadables/(\d+)(?:\?[^\"']*variation_id=(\d+))?",
        re.IGNORECASE)
    seen: set = set()
    for block_m in a_block_re.finditer(html):
        block = block_m.group(0)
        url_m = url_re.search(block)
        if not url_m:
            continue
        full_url = url_m.group(0)
        if full_url in seen:
            continue
        seen.add(full_url)
        # 文件名：优先 title="..."，其次 <span>...</span><div>.zip</div> 拼接
        name = ""
        title_m = re.search(r"\btitle=[\"']([^\"']*\.[a-z0-9]{2,5})[\"']", block, re.IGNORECASE)
        if title_m:
            name = title_m.group(1).strip()
        else:
            file_stem = ""
            ext = ""
            stem_m = re.search(
                r"<span\b[^>]*>([^<>\n]+)</span>\s*<div\b[^>]*>\s*\.([a-z0-9]{2,5})",
                block, re.IGNORECASE)
            if stem_m:
                file_stem, ext = stem_m.group(1).strip(), "." + stem_m.group(2).strip()
            else:
                div_m = re.search(r"class=[\"']text-14[\"'][^>]*>([^<>\n]+)<", block, re.IGNORECASE)
                if div_m:
                    name = div_m.group(1).strip()
            if not name and file_stem:
                name = file_stem + ext
        # 文件大小
        size_text = ""
        size_bytes = 0
        size_m = re.search(r"\(([\d.]+)\s*(KB|MB|GB)\)", block, re.IGNORECASE)
        if size_m:
            size_text = f"{size_m.group(1)} {size_m.group(2).upper()}"
            try:
                val = float(size_m.group(1))
                unit = size_m.group(2).upper()
                if unit.startswith("K"):
                    size_bytes = int(val * 1024)
                elif unit.startswith("M"):
                    size_bytes = int(val * 1024 * 1024)
                elif unit.startswith("G"):
                    size_bytes = int(val * 1024 * 1024 * 1024)
            except Exception:
                pass
        out.append({
            "name": name,
            "url": full_url,
            "size_text": size_text,
            "size_bytes": size_bytes,
        })
    return out


def fetch_item_downloads_with_auth(item_id: str, session=None) -> list[dict]:
    """同 fetch_item_downloads，但会尝试添加 download_token 参数（受 BOOTH 反盗链保护）。

    若商品页提示未登录，原始下载链接会被 302 重定向到登录页。
    标准做法：登录态 cookie + Referer header + 显式 Accept。
    """
    return fetch_item_downloads(item_id, session)


def _parse_price(price_val) -> int:
    if isinstance(price_val, int):
        return price_val
    if isinstance(price_val, str):
        nums = re.sub(r'[^\d]', '', price_val)
        return int(nums) if nums else 0
    return -1


def _thumb_from_json(d: dict) -> str:
    imgs = d.get("images") or []
    if imgs and isinstance(imgs, list):
        first = imgs[0]
        if isinstance(first, dict):
            return first.get("original") or first.get("resized") or ""
    return ""


def refine_from_json(item: dict, session: requests.Session | None = None) -> dict:
    """用 JSON API 权威字段覆盖搜索卡片（洁净标题 + 精确类目 + 封面）。
    R6 适配：fetch_item 已返回规范化 schema，直接拼覆盖。"""
    d = fetch_item(item["id"], session)
    if not d:
        return item
    return {
        "id": item["id"],
        "name": d.get("name") or item["name"],
        "price": _parse_price(d.get("price")) if d.get("price") is not None else item.get("price", -1),
        "price_text": item.get("price_text", "") or d.get("price_text", ""),
        "brand": item.get("brand", ""),
        "shop": d.get("shop") or item.get("shop", ""),
        "category": d.get("category_name", ""),
        "category_name": d.get("category_name", "") or item.get("category_name", ""),
        "category_parent": d.get("category_parent_name", ""),
        "category_parent_name": d.get("category_parent_name", ""),
        "thumbnail": item.get("thumbnail", "") or d.get("thumbnail", ""),
    }


def _pximg_full(url: str, size: str = "1000x1000") -> str:
    """Booth pximg 图片 URL 修正：
    - original URL 缺 /c/<size>/ 前缀，直接 GET 会 404；
    - resized URL 通常是 c/72x72_a2_g5/... 的缩略图；
    统一转成可用的全尺寸图链。
    """
    if "booth.pximg.net" not in url:
        return url
    # resized 形如 .../c/72x72_a2_g5/<shop>/i/... → 替换尺寸
    up = re.sub(r"/c/\d+x\d+[^/]*/", f"/c/{size}/", url)
    if f"/c/{size}/" in up:
        return up
    # original 无前缀 → 插入 /c/<size>/
    return re.sub(r"(https://booth\.pximg\.net)/", r"\1/c/" + size + "/", url, count=1)


def download_cover(thumb_url: str, dest_dir: Path | str | None = None,
                   session: requests.Session | None = None,
                   timeout: int = 20, retries: int = 2) -> Path | None:
    """下载封面到 dest_dir/cover.jpg。

    R16：
      - 默认 timeout=20 / retries=2（原 60/3）。封面属非关键资源，代理抖动时
        原参数会让单个商品卡住 ~186 秒，批量归档直接卡死。
      - 代理失败自动降级直连重试一次：booth.pximg.net 是图片 CDN，
        不少代理节点只放行 booth.pm 而卡住 pximg，直连反而能通。
      - 失败后本体仍算归档成功，三件套可用巡检页「修复三件套」补齐。"""
    if not thumb_url:
        return None
    url = thumb_url  # 对齐 G 盘主源：original 全尺寸图直接下载，_pximg_full 对 _base_resized 误插 /c/size/ 会 403
    s = session or make_session()
    # Windows 下若传 /tmp/... 会被解析为当前盘符根目录，不存在；
    # 未传目录时回退到系统临时目录。
    dest_dir = Path(dest_dir) if dest_dir else Path(tempfile.gettempdir())
    dest_dir.mkdir(parents=True, exist_ok=True)
    cover = dest_dir / "cover.jpg"

    def _fetch(sess, n_retry):
        r = retry_request("GET", url, sess,
                          headers={**UA, "Referer": "https://booth.pm/"},
                          timeout=timeout, retries=n_retry)
        if not r:
            return None
        r.raise_for_status()
        cover.write_bytes(r.content)
        return cover

    # ① 按调用方 session（可能带代理）尝试
    try:
        if _fetch(s, retries):
            return cover
    except Exception as e:
        print(f"  封面下载失败(代理): {e}")

    # ② 降级：临时摘掉代理直连再试一次
    saved = dict(s.proxies)
    if saved:
        try:
            s.proxies.clear()
            if _fetch(s, 1):
                print("  封面已通过直连兜底下载成功")
                return cover
        except Exception as e:
            print(f"  封面直连兜底也失败: {e}")
        finally:
            s.proxies.update(saved)
    return None


# ── 文件名清洗 ───────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    """移除 Windows 非法字符 + 装饰 Unicode（血泪坑：装饰 Unicode 目录名
    会被 Explorer 永久拒绝应用 desktop.ini）。保留 ASCII/中日韩/全角。"""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    cleaned = []
    for ch in name:
        code = ord(ch)
        try:
            import unicodedata
            cat = unicodedata.category(ch)
        except Exception:
            cat = None
        if (0x1F300 <= code <= 0x1F9FF
                or 0x2000 <= code <= 0x27BF
                or 0x2B0 <= code <= 0x2FF
                or 0x2070 <= code <= 0x209F
                or cat in ('Me', 'Mn')
                or cat == 'Cn'):
            continue
        cleaned.append(ch)
    name = ''.join(cleaned)
    name = re.sub(r'\s+', ' ', name).strip('. ')
    return name[:80] if name else "unnamed"


def sanitize(name: str, max_len: int = 70) -> str:
    out = "".join(c for c in name if c not in INVALID and ord(c) >= 32)
    out = re.sub(r"\s+", " ", out).strip().rstrip(". ")
    if len(out) > max_len:
        out = out[:max_len].rstrip(". ")
    return out or "untitled"


_VERSION_RE = re.compile(
    r'(?:ver(?:sion)?\.?|v\.?)\s*(\d+(?:\.\d+)*)', re.IGNORECASE)


def extract_version_tag(filename: str) -> str:
    """从文件名提取版本标记（如 Ver_2.00 / v1.01 / _v100 / 2.0）。

    用于 organize_file 生成目标文件名时**保留版本信息**——血泪教训：
    メカ弾エフェクトVer_2.00.unitypackage 被整理成纯标题文件名后版本号丢失，
    用户无法区分 2.00 / 1.01 两个免费版本。返回规范化 "Ver_x.y" 或空串。
    """
    stem = Path(filename).stem
    m = _VERSION_RE.search(stem)
    if m:
        return f"Ver_{m.group(1)}"
    # 无 ver 前缀的裸版本号（如 name_2.0 / name-1.01）
    m2 = re.search(r'[_\-\s](\d+\.\d+(?:\.\d+)*)\s*$', stem)
    if m2:
        return f"Ver_{m2.group(1)}"
    return ""


def _title_tokens(name: str) -> list[str]:
    """商品名/文件名 → token 列表（清洗 + 拆词）。

    R17：在拉丁字母与非英数字（中日韩/假名）边界拆词——
    'CatHeartアクセサリー' → [catheart, アクセサリー]，避免 token 整段失配。"""
    s = name or ""
    # 日文引号「」『』→ 空格（保留内容，只拆词；勿用「去内容」正则删掉商品名）
    s = s.replace("「", " ").replace("」", " ").replace("『", " ").replace("』", " ")
    s = re.sub(r"[（(\[【].*?[)）\]】]", " ", s)
    s = re.sub(r"[\u2764\U0001F300-\U0001FAFF\U0001F000-\U0001FAFF]", "", s)
    s = re.sub(r"(?:v(?:er(?:sion)?)?\.?|ver\.?)\s*\d+(?:\.\d+)*", " ", s, flags=re.I)
    s = re.sub(r"\d+\.\d+(?:\.\d+)*(?:\s*[_.-])?", " ", s)
    if re.search(r"[A-Za-z]", s) and re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", s):
        s = re.sub(r"([A-Za-z])([\u3040-\u30ff\u4e00-\u9fff])", r"\1 \2", s)
        s = re.sub(r"([\u3040-\u30ff\u4e00-\u9fff])([A-Za-z])", r"\1 \2", s)
    s = re.sub(r"[_＋+\-—/\\.]", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip().lower()
    return [t for t in s.split() if t and not t.isdigit() and len(t) >= 2]


def name_similarity(a: str, b: str) -> float:
    """字符串与商品名的匹配分 0~1（真值覆盖率 70% + Jaccard 30%）。

    用于实验结果打分排序：文件名/包内名 与 搜索结果 name 的相似度。
    双清洗后比较，降低装饰符（【無料】等）干扰。"""
    ta, tb = set(_title_tokens(a)), set(_title_tokens(b))
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    return round(0.7 * len(inter) / len(tb) + 0.3 * len(inter) / len(ta | tb), 3)


def sanitize_query(filename: str) -> list[str]:
    """
    从文件名生成 BOOTH 搜索候选关键词（按优先级排序，首个最可能命中）。
    策略（主上妙招合集）：
      0. 下划线 → 空格（BOOTH 不认下划线）
      1. 去扩展名、去括号内容
      1.5 驼峰拆词：LunariaPaperFan → Lunaria Paper Fan（BOOTH 对驼峰不友好）
      1.6 **纯日文主体**：去尾部英文/版本号，只留日文段（メカ弾エフェクトVer_2.00 → メカ弾エフェクト）
      2. 去版本号：_v100 / v2 / 2.0 / Ver1.0
      3. 去尾部中文（主上备注）
      4. 只取最长连续 ASCII 段
      5. 去 VRChat 常见后缀词
    """
    name = Path(filename).stem
    name = name.replace('_', ' ')
    name = re.sub(r'[\(（\[【].*?[\)）\]】]', '', name)
    split_camel = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name).strip()
    split_camel = re.sub(r'\s+', ' ', split_camel)

    # 纯日文主体：去尾部英文/数字/版本号，只留日文连续段
    ja_parts = re.findall(r'[\u3040-\u30ff\u4e00-\u9fff][\u3040-\u30ff\u4e00-\u9fff・ー]*', name)
    ja_body = "".join(ja_parts).strip() if ja_parts else ""

    candidates = []
    c1 = name.strip()
    if c1:
        candidates.append(c1)
    if split_camel and split_camel != c1:
        candidates.append(split_camel)
    if ja_body and ja_body != c1 and ja_body != split_camel and len(ja_body) >= 2:
        candidates.append(ja_body)  # 纯日文主体（主上：メカ弾エフェクトVer_2.00 → メカ弾エフェクト）

    c2 = re.sub(r'[_\-\s]?(?:v(?:er(?:sion)?)?\.?|version\s*)\d+(?:\.\d+)*[_\-\s]?', '', name, flags=re.I)
    c2 = re.sub(r'[_\-\s]\d+\.\d+(?:\.\d+)*$', '', c2)
    c2 = c2.strip()
    if c2 and c2 not in candidates:
        candidates.append(c2)

    c3 = re.sub(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff].*$', '', c2).strip()
    if c3 and c3 not in candidates and len(c3) >= 3:
        candidates.append(c3)

    ascii_parts = re.findall(r'[A-Za-z][A-Za-z0-9_]{2,}', name)
    for part in sorted(ascii_parts, key=len, reverse=True):
        if part not in candidates and len(part) >= 4:
            candidates.append(part)

    vrc_stoppers = ['vrchat', 'vrc', 'unitypackage', 'package', 'prefab',
                    'gimmick', 'shader', 'world', 'avatar',
                    '玩家', '加入', '退出', '弹窗', '提示', '通知', '音效']
    c5 = c2
    for stop in vrc_stoppers:
        c5 = re.sub(rf'[_\-\s]?{re.escape(stop)}[_\-\s]?', ' ', c5, flags=re.I)
    c5 = re.sub(r'\s+', ' ', c5).strip()
    if c5 and c5 not in candidates and len(c5) >= 3:
        candidates.append(c5)

    seen = set()
    unique = []
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique if unique else [name]


# ── Windows 文件夹图标（完整性契约）─────────────────────────────
class IconContractError(RuntimeError):
    """三件套不齐全时抛出（防 Hermes 类 agent 留半成品 desktop.ini 误导 Explorer）。"""


def set_attrs(path, attrs: int):
    if os.name != "nt":
        return
    ctypes.windll.kernel32.SetFileAttributesW(str(path), attrs)


def _get_attrs(path) -> int:
    """返回文件属性位（Windows）。失败返回 0。"""
    if os.name != "nt":
        return 0
    a = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    return a if a != 0xFFFFFFFF else 0


def _notify_shell():
    """触发 Windows Explorer 全 shell 刷新（图标缓存）。"""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SHChangeNotify(0x00008000, 0x0000, None, None)
    except Exception:
        pass


def set_hidden(path_str: str):
    """Hidden + System 同时设（2026-08-02 修正：之前只设 H 漏 S，
    导致 desktop.ini 属性不全、Explorer 拒读）。"""
    if os.name != "nt":
        return
    FILE_ATTRIBUTE_HIDDEN = 0x02
    FILE_ATTRIBUTE_SYSTEM = 0x04
    attrs = ctypes.windll.kernel32.GetFileAttributesW(path_str)
    if attrs != 0xFFFFFFFF:
        ctypes.windll.kernel32.SetFileAttributesW(path_str, attrs | FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)


def _get_pidl_pair(folder_path: str):
    ole32 = ctypes.windll.ole32
    shell32 = ctypes.windll.shell32
    pidl = ctypes.c_void_p()
    shell32.SHParseDisplayName(folder_path, 0, None, ctypes.byref(ctypes.c_ulong()), ctypes.byref(pidl))
    return None, pidl


def _verify_icon_contract(ico_path, ini_path, folder_path):
    if not ico_path.exists():
        raise IconContractError(f"ico 缺失：{ico_path}")
    if ico_path.stat().st_size < 1024:
        raise IconContractError(f"ico 过小（<1KB）：{ico_path}")
    if not ini_path.exists():
        raise IconContractError(f"ini 缺失：{ini_path}")
    try:
        txt = ini_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        txt = ini_path.read_bytes().decode("utf-8", "replace")
    if "IconResource=.folder_icon.ico" not in txt:
        raise IconContractError(f"ini 缺 IconResource=.folder_icon.ico 字段：{ini_path}")
    a = ctypes.windll.kernel32.GetFileAttributesW(str(folder_path))
    if a == 0xFFFFFFFF or not (a & 0x01):
        ctypes.windll.kernel32.SetFileAttributesW(str(folder_path), a | 0x01)


# R24（2026-09-08 主上实测钦定）：desktop.ini 的 shell 原生标准格式。
# 旧版只写「[.ShellClassInfo]\nIconResource=...」（无 [ViewState]/IconIndex 段）→
# Explorer 不认 → 目录永远黄色默认图标。标准格式带 [ViewState] FolderType=Generic
# + IconResource + IconIndex=0（CRLF 行尾），与资源管理器「更改图标」写入的形态一致。
# 单一来源：make_folder_icon / normalize_desktop_ini / fix_folder_system_attr 全部引用。
DESKTOP_INI_STANDARD = (
    "[ViewState]\r\n"
    "FolderType=Generic\r\n"
    "[.ShellClassInfo]\r\n"
    "IconResource=.folder_icon.ico,0\r\n"
    "IconIndex=0\r\n"
)


def make_folder_icon(cover_path: Path, folder_path: Path):
    """cover.jpg → .folder_icon.ico + desktop.ini（三件套），含完整性契约。

    血泪坑（2026-08-01/02）：
      - 宽幅 cover 直接 save 会生成非正方形 ICO（256x154）→ 缩略图居中小图 → 先贴正方形画布
      - desktop.ini/ico 缺 H/S 属性 → Explorer 拒读 → 写完自检三件套
      - 写完不校验 → Hermes 类 agent 留残缺 desktop.ini → 自检 raise IconContractError
    血泪坑（2026-09-08 主上实测）：
      - 父目录只设 R(0x01) 漏 S(0x04) → Explorer 永远不读 desktop.ini → 黄色默认图标
        且重启电脑也无效（不是 IconCache 缓存问题，是 desktop.ini 从未被读过）
      - 修法：父目录设 R(0x01) | S(0x04)，且写完后向父目录发 SHCNE_UPDATEDIR
        （让打开父目录视图的 Explorer 重新读 desktop.ini 缓存）
    血泪坑（2026-09-08 傍晚 R24，26 目录实锤）：
      - S 位补全 + 重启电脑后仍黄的目录，根因是 desktop.ini 为旧版「裸格式」
        （只有 [.ShellClassInfo]+IconResource，缺 [ViewState]/IconIndex 段）→
        shell 层 SHGetSetFolderCustomSettings 读回空、SHGetFileInfo 恒返回默认索引
      - 修法：desktop.ini 统一写 shell 原生标准格式 DESKTOP_INI_STANDARD
        （[ViewState] FolderType=Generic + IconResource + IconIndex=0, CRLF），
        26 个目录重写后全部立即恢复（用户当场确认）
    """
    if not cover_path or not cover_path.exists():
        raise IconContractError(f"cover 缺失：{cover_path}")
    try:
        img = Image.open(cover_path).convert("RGBA")
        side = max(img.size)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        ico_path = folder_path / ".folder_icon.ico"
        ini_path = folder_path / "desktop.ini"
        ini_content = DESKTOP_INI_STANDARD
        for p in (ico_path, ini_path):
            if p.exists():
                try:
                    ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
                except Exception:
                    pass
        canvas.save(str(ico_path), format="ICO", sizes=sizes)
        ini_path.write_text(ini_content, encoding="utf-8")
        set_hidden(str(ini_path))
        set_hidden(str(ico_path))
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(folder_path))
        # R23（2026-09-08 钦定）：父目录必须 R(0x01) | S(0x04) 双设，
        # 否则 Explorer 拒读 desktop.ini（与 ico/ini 自身的 H+S 同理）。
        # ⚠️ 父目录绝不能加 H(0x02) —— 加了资源管理器默认隐藏，整个目录从视图中消失！
        ctypes.windll.kernel32.SetFileAttributesW(str(folder_path), attrs | 0x01 | 0x04)
        _verify_icon_contract(ico_path, ini_path, folder_path)
        # 通知 Explorer 刷新图标缓存
        try:
            _, pidl_item = _get_pidl_pair(str(folder_path))
            ctypes.windll.shell32.SHChangeNotify(0x00000008, 0x0000, pidl_item, None)
            ctypes.windll.ole32.CoTaskMemFree(pidl_item)
        except Exception:
            ctypes.windll.shell32.SHChangeNotify(0x00008000, 0x0000, None, None)
        # R23：额外发 SHCNE_UPDATEDIR 给父目录，让正打开父目录视图的 Explorer
        # 主动重读 desktop.ini 缓存并刷新子目录视图。
        try:
            ctypes.windll.shell32.SHChangeNotify(0x00000005, 0x0000, None, None)  # SHCNE_UPDATEDIR
        except Exception:
            pass
    except IconContractError:
        raise
    except Exception as e:
        ini = folder_path / "desktop.ini"
        if ini.exists():
            try:
                ctypes.windll.kernel32.SetFileAttributesW(str(ini), 0x80)
                ini.unlink()
            except Exception:
                pass
        raise IconContractError(f"图标设置失败（已清理残缺 desktop.ini）：{e}")


# ── 全库修复：补 System 标志（R23，2026-09-08 主上实测）─────────────
def normalize_desktop_ini(folder_path) -> bool:
    """把目录的 desktop.ini 归一化为 shell 原生标准格式（R24）。

    幂等：已是标准格式（含 [ViewState] 与 IconIndex=）→ 不动，返回 False；
    旧版裸格式（缺任一字段）→ 重写为 DESKTOP_INI_STANDARD。标准格式是裸格式的
    超集（裸格式的 IconResource 语义被完整保留），因此重写无信息丢失。
    写前清属性（防 PermissionError），写后补 H+S，并发 SHCNE_UPDATEITEM/UPDATEDIR。

    返回 True 表示发生了重写；目录无三件套/无 ini 时返回 False。
    """
    folder_path = Path(folder_path)
    ini_path = folder_path / "desktop.ini"
    if not ini_path.exists():
        return False
    try:
        raw = ini_path.read_bytes()
    except Exception:
        return False
    if raw[:2] == b"\xff\xfe":
        txt = raw.decode("utf-16-le", errors="replace")
    elif raw[:3] == b"\xef\xbb\xbf":
        txt = raw.decode("utf-8", errors="replace")
    else:
        txt = raw.decode("utf-8", errors="replace")
    if "[ViewState]" in txt and "IconIndex=" in txt:
        return False  # 已是标准格式
    K = ctypes.windll.kernel32
    try:
        K.SetFileAttributesW(str(ini_path), 0x80)  # 清 H/S → NORMAL
        ini_path.write_text(DESKTOP_INI_STANDARD, encoding="utf-8")
    except Exception as e:
        raise IconContractError(f"desktop.ini 归一化失败：{ini_path} ({e})") from e
    a = K.GetFileAttributesW(str(ini_path))
    K.SetFileAttributesW(str(ini_path), a | 0x02 | 0x04)  # H+S
    try:
        ctypes.windll.shell32.SHChangeNotify(0x2, 0x5, str(folder_path), None)
        ctypes.windll.shell32.SHChangeNotify(0x5, 0x5, str(folder_path.parent), None)
    except Exception:
        pass
    return True


def fix_folder_system_attr(roots: list[str] | None = None,
                           on_progress=None) -> dict:
    """扫描 BOOTH 大类目录（3D服饰/3D发型/...），一键修复「黄色默认图标」。

    两项修复（R23 + R24）：
      1. 补 S(0x04)+R(0x01) 给「三件套齐全但父目录缺 S 位」的目录 —— 否则
         Explorer 根本不读 desktop.ini（重启电脑也无效）。
      2. desktop.ini 归一化为 shell 原生标准格式（normalize_desktop_ini）——
         旧版裸格式（缺 [ViewState]/IconIndex）同样不被 shell 采用。
    非破坏性：仅设文件系统属性位 + 重写 desktop.ini 文本，零本体文件增删。
    返回 {scanned, fixed, normalized, failed, examples: [...]}（兼容旧键）。
    """
    DEFAULT_ROOTS = [
        r"G:\Lin_File\BOOTH\3D服饰",
        r"G:\Lin_File\BOOTH\3D发型",
        r"G:\Lin_File\BOOTH\3D饰品",
        r"G:\Lin_File\BOOTH\3D模型",
        r"G:\Lin_File\BOOTH\3D工具",
        r"G:\Lin_File\BOOTH\3D动作",
    ]
    if not roots:
        roots = DEFAULT_ROOTS
    SHELL = ctypes.windll.shell32
    fixed = 0; normalized = 0; failed = 0; examples: list[str] = []
    for root in roots:
        rp = Path(root)
        if not rp.exists():
            continue
        for d in rp.iterdir():
            if not d.is_dir():
                continue
            ini = d / "desktop.ini"; ico = d / ".folder_icon.ico"
            if not (ini.exists() and ico.exists()):
                continue
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(d))
            if attrs != 0xFFFFFFFF and not (attrs & 0x04):
                new = attrs | 0x04 | 0x01 | 0x20  # S + R + A（注意：禁 H 隐藏！）
                try:
                    ctypes.windll.kernel32.SetFileAttributesW(str(d), new)
                    fixed += 1
                    if len(examples) < 3:
                        examples.append(d.name)
                    # 通知 Explorer 刷新父目录视图
                    try:
                        SHELL.SHChangeNotify(0x00000005, 0x0000, None, None)  # SHCNE_UPDATEDIR
                    except Exception:
                        pass
                except Exception as e:
                    failed += 1
                    if on_progress:
                        on_progress(f"  失败: {d.name} ({e})")
            # R24：desktop.ini 老格式 → 归一化为标准格式（幂等）
            try:
                if normalize_desktop_ini(d):
                    normalized += 1
                    if len(examples) < 3:
                        examples.append(d.name + " (ini归一化)")
            except IconContractError as e:
                failed += 1
                if on_progress:
                    on_progress(f"  ini归一化失败: {d.name} ({e})")
            if on_progress and (fixed + normalized + failed) % 50 == 0:
                on_progress(f"  进度: 补S {fixed} / 归一化 {normalized} / 失败 {failed}")
    if on_progress:
        on_progress(f"完成：补S {fixed} 件 / ini归一化 {normalized} 件 / 失败 {failed} 件")
    return {"scanned": fixed + normalized + failed, "fixed": fixed,
            "normalized": normalized, "failed": failed, "examples": examples}


# ── 搜索 / 评分（按名搜索核心）──────────────────────────────────
def search_booth(query: str, session: requests.Session | None = None) -> list[dict]:
    """用 ?q= 搜索 BOOTH，返回匹配商品列表（data-* 卡片解析）。"""
    s = session or make_session()
    try:
        r = s.get(f"{SEARCH_URL}?q={quote(query)}", timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"  搜索失败: {e}")
        return []
    html = r.text
    items = []
    for m in re.finditer(r'data-product-id="(\d+)"', html):
        pid = m.group(1)
        start = max(0, m.start() - 300)
        end = min(len(html), m.end() + 4000)
        ctx = html[start:end]

        def attr(pattern, default=""):
            match = re.search(pattern, ctx)
            return unescape_html(match.group(1)) if match else default

        name = attr(r'data-product-name="([^"]*)"')
        price = attr(r'data-product-price="([^"]*)"')
        brand = attr(r'data-product-brand="([^"]*)"')
        category = attr(r'data-product-category="([^"]*)"')
        shop_m = re.search(r'item-card__shop-name[^>]*>([^<]+)<', ctx)
        shop = shop_m.group(1).strip() if shop_m else brand
        thumb_m = re.search(r'data-original="(https://booth\.pximg\.net/[^"]*)"', ctx)
        thumb = thumb_m.group(1) if thumb_m else ""
        cat_name_m = re.search(r'item-card__category-anchor[^>]*>([^<]+)<', ctx)
        cat_name = cat_name_m.group(1).strip() if cat_name_m else ""
        price_text_m = re.search(r'price[^>]*>([^<]*\d+[^<]*)<', ctx)
        price_text = price_text_m.group(1).strip() if price_text_m else f"¥ {price}"
        items.append({
            "id": pid, "name": name, "price": int(price) if price.isdigit() else -1,
            "price_text": price_text, "brand": brand, "shop": shop,
            "category": category, "category_name": cat_name, "thumbnail": thumb,
        })
    return items


def unescape_html(s: str) -> str:
    from html import unescape
    return unescape(s)


def _norm(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


_json_cache: dict = {}


def _canonical_name(item_id: str, session=None) -> str:
    if item_id in _json_cache:
        return _json_cache[item_id]
    d = fetch_item(item_id, session)
    _json_cache[item_id] = (d or {}).get("name", "") or ""
    return _json_cache[item_id]


def extract_unitypkg_resource_names(zip_path: str) -> set[str]:
    """解 zip 内 .unitypackage（gzip+tar），读 pathname 文件内容提资源名。
    首段目录名通常是店铺名/作者名（硬锚点），prefab/anim 名是商品主题。"""
    import tarfile
    import zipfile
    names: set[str] = set()
    if not zip_path or not os.path.isfile(zip_path):
        return names
    try:
        with zipfile.ZipFile(zip_path) as z:
            for n in z.namelist():
                if not n.lower().endswith('.unitypackage'):
                    continue
                raw = z.read(n)
                with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tf:
                    for member in tf.getmembers():
                        if not member.isfile():
                            continue
                        if os.path.basename(member.name) == 'pathname':
                            try:
                                f = tf.extractfile(member)
                                if f is None:
                                    continue
                                for line in f.read().decode('utf-8', 'replace').splitlines():
                                    for seg in line.replace('\\', '/').split('/'):
                                        if not seg or seg.startswith('.'):
                                            continue
                                        stem = seg.rsplit('.', 1)[0] if '.' in seg else seg
                                        if stem and len(stem) >= 2:
                                            names.add(stem)
                            except Exception:
                                continue
    except Exception:
        pass
    return names


def score_and_pick(query: str, items: list[dict], prefer_free=False,
                   source_zip_path: str = "", session=None) -> tuple[dict | None, bool]:
    """评分选最佳。单结果也必须名称命中（血泪坑）；标题不命中时解 UnityPackage 验真。"""
    if not items:
        return None, False
    qn = _norm(query)
    scored = []
    for idx, it in enumerate(items):
        name_l = it["name"].lower()
        cn = _canonical_name(it["id"], session)
        s = 0
        if qn and qn in _norm(name_l):
            s += 100
        if qn and qn in _norm(cn):
            s += 100
        for w in re.split(r'[_\-\s]+', query.lower()):
            if len(w) >= 3 and w in name_l:
                s += 20
        s += max(0, 10 - idx * 2)
        if len(name_l) > len(query) * 5 and len(cn) > len(query) * 5:
            s -= 10
        scored.append((s, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored or scored[0][0] <= 0:
        if len(items) == 1:
            it = items[0]
            cn = _norm(_canonical_name(it["id"], session))
            if qn and (qn in cn or qn in _norm(it["name"])):
                return items[0], False
            if source_zip_path:
                res_names = extract_unitypkg_resource_names(source_zip_path)
                if res_names:
                    qn_norm = _norm(query)
                    for r in res_names:
                        rn = _norm(r)
                        if qn_norm and (qn_norm in rn or rn in qn_norm):
                            return items[0], False
                        for w in re.split(r'[_\-\s]+', query.lower()):
                            if len(w) >= 3 and w in r.lower():
                                return items[0], False
            return None, False
        return None, False
    best_s = scored[0][0]
    ambiguous = False
    if len(scored) > 1 and (best_s - scored[1][0]) < 30:
        ambiguous = True
    best_cn = _norm(_canonical_name(scored[0][1]["id"], session))
    best_price = scored[0][1]["price"]
    for s2, it2 in scored[1:]:
        if _norm(_canonical_name(it2["id"], session)) == best_cn and it2["price"] != best_price:
            ambiguous = True
    return scored[0][1], ambiguous


# ── 压缩包水印识别 ─────────────────────────────────────────────
WATERMARK_PATTERNS = [
    r'https?://([\w-]+)\.booth\.pm/?',
    r'booth\.pm/[\w/]+/items/(\d+)',
    r'booth\.pm/items/(\d+)',
]


def detect_watermark_url_in_zip(filepath: str) -> str:
    """读 zip 内 .url/.txt/readme 找 BOOTH 店铺 URL 或商品 ID 链接。"""
    import zipfile
    fp = Path(filepath)
    if not fp.exists() or fp.suffix.lower() not in ('.zip',):
        return ""
    try:
        with zipfile.ZipFile(fp) as z:
            for n in z.namelist():
                ln = n.lower()
                if ln.endswith('.url') or ln.endswith('.txt') or 'readme' in ln or 'info' in ln:
                    try:
                        content = z.read(n).decode('utf-8', errors='replace')
                        for pat in WATERMARK_PATTERNS:
                            m = re.search(pat, content)
                            if m:
                                full = re.search(r'https?://[^\s"<>]+', content)
                                return full.group(0) if full else m.group(0)
                    except Exception:
                        continue
    except Exception:
        return ""
    return ""


def extract_shop_id_from_url(url: str) -> str:
    m = re.search(r'https?://([\w-]+)\.booth\.pm', url)
    return m.group(1) if m else ""


def list_shop_items(shop_subdomain: str, session=None) -> list[dict]:
    """店铺 `/items?page=N` 翻页列商品（店铺根有 Cloudflare 护盾，必须走 /items）。"""
    s = session or make_session()
    items = []
    for page in range(1, 6):
        try:
            r = s.get(f"https://{shop_subdomain}.booth.pm/items?page={page}", timeout=30)
            if r.status_code != 200:
                break
            ids = re.findall(r'data-product-id="(\d+)"', r.text)
            if not ids:
                break
            for pid in ids:
                d = fetch_item(pid, s)
                if not d:
                    continue
                cat = d.get("category") or {}
                items.append({
                    "id": pid, "name": d.get("name", ""),
                    "price": _parse_price(d.get("price")),
                    "price_text": "", "brand": "", "shop": (d.get("shop") or ""),
                    "category": cat.get("name", ""), "category_name": cat.get("name", ""),
                    "category_parent": (cat.get("parent") or {}).get("name", ""),
                    "thumbnail": _thumb_from_json(d),
                })
            time.sleep(0.5)
        except Exception:
            break
    return items
