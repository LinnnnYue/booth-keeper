#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""booth_core — 兼容门面（R23 拆分后保留）

本模块原为 1439 行单体。R23 按既有分段边界拆为下列模块：

    bk_domain   领域常量与类目映射（纯数据，无外部依赖）
    bk_text     文件名清洗与查询生成
    bk_shell    Windows 文件夹图标与 Shell 属性
    bk_net      请求会话、商品元数据与下载（代理唯一真源）
    bk_local    本地目录扫描、包完整性与版本隔离
    bk_search   搜索、评分与商品识别

**为什么保留这个文件**：调用点遍布 5 个页面模块、archive_util.py 与
archive/scripts/ 下的历史脚本，一律写作 `import booth_core as bc`。
门面让这次拆分对调用方完全不可见，是回归风险最低的拆法。

**为什么用 __getattr__ 转发而非 `from x import *`**：
`PROXY` 是可变模块级变量，`apply_proxy()` 会改写它。若用静态 star-import，
门面的 `bc.PROXY` 会永远停在导入瞬间的旧值 —— 出现「代理改了但门面读不到」
的隐性不一致。动态转发保证读到的是各模块的实时值。

⚠️ 重导出在此处是**设计意图，不是技术债**。请勿因「看起来冗余」而删除本文件。
"""
import bk_domain as _bk_domain
import bk_text as _bk_text
import bk_shell as _bk_shell
import bk_net as _bk_net
import bk_local as _bk_local
import bk_search as _bk_search

_MODULES = (_bk_domain, _bk_text, _bk_shell, _bk_net, _bk_local, _bk_search)

__all__ = [
    "BODY_EXTENSIONS",
    "BOOTH_BASE",
    "CATEGORY_MAP",
    "CATEGORY_PARENT_MAP",
    "DESKTOP_INI_STANDARD",
    "INVALID",
    "ITEM_JSON",
    "IconContractError",
    "MAX_RETRIES",
    "PROXY",
    "SEARCH_URL",
    "UA",
    "WATERMARK_PATTERNS",
    "_THREED_PARENTS",
    "_VERSION_RE",
    "_canonical_name",
    "_get_attrs",
    "_get_pidl_pair",
    "_iter_library_dirs",
    "_json_cache",
    "_norm",
    "_normalize_item",
    "_notify_shell",
    "_parse_price",
    "_pximg_full",
    "_thumb_from_json",
    "_title_tokens",
    "_ver_tuple",
    "_verify_icon_contract",
    "_version_of",
    "_versionless",
    "apply_proxy",
    "build_search_queries",
    "classify",
    "classify_item_state",
    "detect_watermark_url_in_zip",
    "download_cover",
    "extract_shop_id_from_url",
    "extract_unitypkg_resource_names",
    "extract_version_tag",
    "fetch_item",
    "fetch_item_downloads",
    "fetch_item_downloads_with_auth",
    "fix_folder_system_attr",
    "has_body",
    "is_corrupt_package",
    "isolate_old_versions",
    "list_shop_items",
    "load_cookie",
    "make_folder_icon",
    "make_session",
    "name_similarity",
    "normalize_desktop_ini",
    "probe_item_http",
    "probe_package",
    "probe_reachable",
    "proxy_map",
    "rank_search_results",
    "refine_from_json",
    "retry_request",
    "sanitize",
    "sanitize_filename",
    "sanitize_query",
    "scan_corrupt_in_library",
    "score_and_pick",
    "search_booth",
    "set_attrs",
    "set_hidden",
    "unescape_html",
]


def __getattr__(name):
    """转发到子模块（含可变模块级变量，保证读到实时值）。"""
    for m in _MODULES:
        if name in vars(m):
            return vars(m)[name]
    raise AttributeError(f"module 'booth_core' has no attribute {name!r}")


def __dir__():
    return sorted(set(__all__) | {k for k in globals() if not k.startswith("_")})
