#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bk_search — 搜索、评分与商品识别

由 booth_core.py 拆分而来（R23）。按名搜索 BOOTH、给候选结果打分排序、
从压缩包内资源名反推商品身份、识别水印与店铺。依赖 bk_net 发请求。
"""

import os
import re
import io
import time
import zipfile
import tarfile
import requests
import diag
from pathlib import Path
from urllib.parse import quote
from bk_domain import *
from bk_text import *
from bk_net import *
from bk_net import _json_cache, _parse_price, _thumb_from_json
from bk_local import *

__all__ = [
    "WATERMARK_PATTERNS",
    "build_search_queries",
    "detect_watermark_url_in_zip",
    "extract_shop_id_from_url",
    "extract_unitypkg_resource_names",
    "list_shop_items",
    "rank_search_results",
    "score_and_pick",
    "search_booth",
    "unescape_html",
]




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


# ── 搜索 / 评分（按名搜索核心）──────────────────────────────────
def search_booth(query: str, session: requests.Session | None = None) -> list[dict]:
    """用 ?q= 搜索 BOOTH，返回匹配商品列表（data-* 卡片解析）。"""
    s = session or make_session()
    try:
        r = s.get(f"{SEARCH_URL}?q={quote(query)}", timeout=30)
        r.raise_for_status()
    except Exception as e:
        diag.warn(f"搜索失败：{e}", scope="search_booth", query=query)
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
