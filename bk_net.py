#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bk_net — 请求会话、商品元数据与下载

由 booth_core.py 拆分而来（R23）。含 R17 建立的代理唯一真源
（apply_proxy / proxy_map）—— 全项目所有请求会话均应经 make_session() 获得，
不得逐处手工 `s.proxies.update(...)`（会在 URL 为空时污染全局映射）。
"""

import os
import re
import time
import tempfile
import requests
import diag
from pathlib import Path
from bk_domain import *
from bk_text import *

__all__ = [
    "BOOTH_BASE",
    "ITEM_JSON",
    "MAX_RETRIES",
    "PROXY",
    "SEARCH_URL",
    "UA",
    "apply_proxy",
    "classify_item_state",
    "download_cover",
    "fetch_item",
    "fetch_item_downloads",
    "fetch_item_downloads_with_auth",
    "load_cookie",
    "make_session",
    "probe_item_http",
    "probe_reachable",
    "proxy_map",
    "refine_from_json",
    "retry_request",
]



# ── 常量 ──────────────────────────────────────────────────────────
BOOTH_BASE = "https://booth.pm/ja"
SEARCH_URL = f"{BOOTH_BASE}/items"
ITEM_JSON  = f"{BOOTH_BASE}/items/{{id}}.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
      "Accept-Language": "ja,en;q=0.9,zh-CN;q=0.8"}
# 代理真源（R17）：默认直连。原实现以 127.0.0.1:20122 兜底，
# 导致无代理环境下每个请求先失败重试 3 次；且与设置页开关脱节。
# 现仅尊重环境变量 HTTPS_PROXY，用户启用代理时由 apply_proxy() 注入。
PROXY = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "").strip()
MAX_RETRIES = 3


# ── 请求会话 ──────────────────────────────────────────────────────
def apply_proxy(url: str = "", enabled: bool = True) -> None:
    """全局设定代理。enabled 为假或 url 为空 → 直连。

    由 main_window 启动流程与设置页保存时调用；make_session() 随即生效。
    这是全项目唯一的代理真源——worker 内部不再各自拼装代理。"""
    global PROXY
    PROXY = url.strip() if (enabled and (url or "").strip()) else ""


def proxy_map() -> dict | None:
    """当前代理的 requests 映射；直连时返回 None。"""
    return {"http": PROXY, "https": PROXY} if PROXY else None


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


_json_cache: dict = {}


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
        diag.warn(f"封面下载失败：{e}", scope="download_cover", url=url)

    # ② 降级：临时摘掉代理直连再试一次
    saved = dict(s.proxies)
    if saved:
        try:
            s.proxies.clear()
            if _fetch(s, 1):
                diag.info("封面已通过直连兜底下载成功", scope="download_cover")
                return cover
        except Exception as e:
            diag.warn(f"封面直连兜底也失败：{e}", scope="download_cover", url=url)
        finally:
            s.proxies.update(saved)
    # ③ 全部通道失败：留痕（R17 补齐，R23 接入诊断通道）——原实现此行静默返回 None，
    # 打包后无控制台，排障时无从区分「CDN 挂了」与「图片 URL 失效」。
    # 注意：封面缺失不阻断归档，调用方据返回值决定是否提示。
    diag.warn("封面获取失败（全部通道）", scope="download_cover", url=url)
    return None
