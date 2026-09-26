#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/_split_booth_core.py — 一次性拆解工具（R23 §2.4）

把 booth_core.py 按既有分段边界机械搬运为四个模块，并生成兼容门面。
**不改一个字符的逻辑** —— 只做「按定义切片 + 重新装配 import 头 + 加 __all__」。

关键设计：门面用模块级 __getattr__ 动态转发，而非 `from x import *`。
原因：`PROXY` 是可变模块级变量，apply_proxy() 会改写它；静态 import 会让
`bc.PROXY` 永远停在导入瞬间的旧值，造成「代理改了但门面读不到」的隐性 bug。

运行： python tests/_split_booth_core.py [--dry-run]
"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "booth_core.py"

# ── 分配表：每个顶层符号归属哪个新模块 ──────────────────────────────
ASSIGN = {
    "bk_domain": [
        "CATEGORY_MAP", "CATEGORY_PARENT_MAP", "classify", "_THREED_PARENTS",
    ],
    "bk_text": [
        "INVALID", "sanitize_filename", "sanitize", "_VERSION_RE",
        "extract_version_tag", "_title_tokens", "name_similarity", "sanitize_query",
    ],
    "bk_shell": [
        "IconContractError", "set_attrs", "_get_attrs", "_notify_shell", "set_hidden",
        "_get_pidl_pair", "_verify_icon_contract", "DESKTOP_INI_STANDARD",
        "make_folder_icon", "normalize_desktop_ini", "fix_folder_system_attr",
    ],
    "bk_net": [
        "BOOTH_BASE", "SEARCH_URL", "ITEM_JSON", "UA", "PROXY", "MAX_RETRIES",
        "apply_proxy", "proxy_map", "make_session", "retry_request", "load_cookie",
        "_normalize_item", "_json_cache", "fetch_item", "probe_reachable",
        "probe_item_http", "classify_item_state", "fetch_item_downloads",
        "fetch_item_downloads_with_auth", "_parse_price", "_thumb_from_json",
        "refine_from_json", "_pximg_full", "download_cover",
    ],
    "bk_local": [
        "BODY_EXTENSIONS", "has_body", "_iter_library_dirs", "probe_package",
        "is_corrupt_package", "scan_corrupt_in_library", "_version_of",
        "_versionless", "_ver_tuple", "isolate_old_versions",
    ],
    "bk_search": [
        "build_search_queries", "rank_search_results", "search_booth",
        "unescape_html", "_norm", "_canonical_name",
        "extract_unitypkg_resource_names", "score_and_pick",
        "WATERMARK_PATTERNS", "detect_watermark_url_in_zip",
        "extract_shop_id_from_url", "list_shop_items",
    ],
}

MODULE_DOC = {
    "bk_domain": """bk_domain — BOOTH 领域常量与类目映射

由 booth_core.py 拆分而来（R23）。本模块只含纯数据与纯函数，无任何外部依赖，
是其余模块的依赖底层。
""",
    "bk_text": """bk_text — 文件名清洗与查询生成

由 booth_core.py 拆分而来（R23）。负责把 BOOTH 商品名/下载文件名规范化为
安全目录名，以及从混乱文件名反推可用的搜索查询词。
""",
    "bk_shell": """bk_shell — Windows 文件夹图标与 Shell 属性

由 booth_core.py 拆分而来（R23）。封装 Explorer 文件夹图标三件套
（cover.jpg / .folder_icon.ico / desktop.ini）的生成、校验与全库修复。

⚠️ 本模块含 Windows 专有 API（ctypes.windll），非 Windows 平台不可用。
""",
    "bk_net": """bk_net — 请求会话、商品元数据与下载

由 booth_core.py 拆分而来（R23）。含 R17 建立的代理唯一真源
（apply_proxy / proxy_map）—— 全项目所有请求会话均应经 make_session() 获得，
不得逐处手工 `s.proxies.update(...)`（会在 URL 为空时污染全局映射）。
""",
    "bk_local": """bk_local — 本地目录扫描、包完整性与版本隔离

由 booth_core.py 拆分而来（R23）。纯粹操作磁盘：判断目录是否含本体文件、
解析压缩包是否损坏、把旧版本文件移入 v{N}/ 子目录。不发任何网络请求。
""",
    "bk_search": """bk_search — 搜索、评分与商品识别

由 booth_core.py 拆分而来（R23）。按名搜索 BOOTH、给候选结果打分排序、
从压缩包内资源名反推商品身份、识别水印与店铺。依赖 bk_net 发请求。
""",
}

# 跨模块 import（人工确定 + 验证兜底）
CROSS = {
    "bk_domain": [],
    "bk_text": [],
    "bk_shell": [],
    "bk_net": [
        "from bk_domain import *",
        "from bk_text import *",
    ],
    "bk_local": [
        "from bk_text import *",
        "from bk_text import _VERSION_RE",
    ],
    "bk_search": [
        "from bk_domain import *",
        "from bk_text import *",
        "from bk_net import *",
        "from bk_net import _json_cache, _parse_price, _thumb_from_json",
        "from bk_local import *",
    ],
}


def lead_start(lines, start):
    """向上吸收紧邻的注释/空行，让定义带上自己的注释块。"""
    i = start - 2
    while i >= 0:
        s = lines[i].strip()
        if s.startswith("#") or s == "":
            i -= 1
        else:
            break
    return i + 2


def collect(src):
    tree = ast.parse(src)
    items = []
    for node in tree.body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        for n in names:
            items.append((n, node.lineno, node.end_lineno))
    return items


def needed_imports(code):
    out = []
    tests = [
        ("os", r"\bos\."), ("re", r"(?<![\w.])re\."), ("sys", r"\bsys\."),
        ("io", r"\bio\."), ("time", r"\btime\."), ("gzip", r"\bgzip\."),
        ("ctypes", r"\bctypes\."), ("tempfile", r"\btempfile\."),
        ("zipfile", r"\bzipfile\."), ("tarfile", r"\btarfile\."),
        ("requests", r"\brequests\."), ("diag", r"\bdiag\."),
    ]
    for mod, pat in tests:
        if re.search(pat, code):
            out.append(f"import {mod}")
    if re.search(r"\bPath\b", code):
        out.append("from pathlib import Path")
    if re.search(r"\bquote\(", code):
        out.append("from urllib.parse import quote")
    if re.search(r"\bImage\b", code):
        out.append("from PIL import Image")
    if re.search(r"\bsend2trash\b", code):
        out.append("try:\n    from send2trash import send2trash\nexcept Exception:\n    send2trash = None")
    return out


def main():
    dry = "--dry-run" in sys.argv
    src = SRC.read_text(encoding="utf-8")
    # 输入源保险：本脚本只接受「拆解前的单体」。若 SRC 已是生成的门面（含
    # __getattr__ 转发），重跑会把门面当源码切 —— 必须先恢复单体再运行。
    if "__getattr__" in src or "import bk_domain as _bk_domain" in src:
        print("!! booth_core.py 已是门面，不是拆解前的单体。")
        print("   请先恢复单体（如 cp <备份> booth_core.py）再运行本脚本。")
        sys.exit(2)
    lines = src.splitlines(keepends=True)
    items = collect(src)

    # 校验分配表覆盖全部顶层符号
    assigned = {n for names in ASSIGN.values() for n in names}
    actual = {n for n, _, _ in items}
    missing = actual - assigned
    extra = assigned - actual
    if missing:
        print("!! 未分配符号:", sorted(missing)); sys.exit(1)
    if extra:
        print("!! 分配表含不存在的符号:", sorted(extra)); sys.exit(1)
    print(f"顶层符号 {len(actual)} 个，分配表完整 ✓")

    # 切片（按行号，带上注释，互不重叠）
    order = sorted(items, key=lambda x: x[1])
    block = {}
    prev_end = 0
    for name, start, end in order:
        ls = max(lead_start(lines, start), prev_end + 1)
        block[name] = "".join(lines[ls - 1:end])
        prev_end = end

    owner = {n: m for m, names in ASSIGN.items() for n in names}
    pub_all = {}
    report = {}

    for mod, names in ASSIGN.items():
        chunks = [block[n] for n in names]
        body = "\n".join(c.rstrip("\n") for c in chunks) + "\n"
        imps = needed_imports(body)
        cross = CROSS[mod]
        pubs = sorted(n for n in names if not n.startswith("_"))
        pub_all[mod] = pubs

        head = ['#!/usr/bin/env python3', '# -*- coding: utf-8 -*-',
                '"""' + MODULE_DOC[mod] + '"""']
        allimp = imps + cross
        if allimp:
            head.append("")
            head.extend(allimp)
        head.append("")
        head.append("__all__ = [")
        for n in pubs:
            head.append(f'    "{n}",')
        head.append("]")
        head.append("")
        out = "\n".join(head) + "\n\n" + body
        nlines = out.count("\n")
        report[mod] = (nlines, len(names))

        if not dry:
            (ROOT / f"{mod}.py").write_text(out, encoding="utf-8")
        print(f"  {mod}.py  {nlines:5d} 行  {len(names):2d} 个符号  "
              f"(公共 {len(pubs)})  依赖: {', '.join(cross) or '无'}")

    # 门面
    mods = list(ASSIGN.keys())
    facade = '''#!/usr/bin/env python3
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
'''
    for m in mods:
        facade += f"import {m} as _{m}\n"
    facade += "\n_MODULES = (" + ", ".join(f"_{m}" for m in mods) + ")\n\n"
    all_names = sorted(n for names in ASSIGN.values() for n in names)
    facade += "__all__ = [\n"
    for n in all_names:
        facade += f'    "{n}",\n'
    facade += "]\n\n\n"
    facade += '''def __getattr__(name):
    """转发到子模块（含可变模块级变量，保证读到实时值）。"""
    for m in _MODULES:
        if name in vars(m):
            return vars(m)[name]
    raise AttributeError(f"module 'booth_core' has no attribute {name!r}")


def __dir__():
    return sorted(set(__all__) | {k for k in globals() if not k.startswith("_")})
'''
    if not dry:
        (ROOT / "booth_core.py").write_text(facade, encoding="utf-8")
    print(f"  booth_core.py  {facade.count(chr(10)):5d} 行  门面（转发 {len(all_names)} 个符号）")


if __name__ == "__main__":
    main()
