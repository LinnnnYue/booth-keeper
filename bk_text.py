#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bk_text — 文件名清洗与查询生成

由 booth_core.py 拆分而来（R23）。负责把 BOOTH 商品名/下载文件名规范化为
安全目录名，以及从混乱文件名反推可用的搜索查询词。
"""

import re
from pathlib import Path

__all__ = [
    "INVALID",
    "extract_version_tag",
    "name_similarity",
    "sanitize",
    "sanitize_filename",
    "sanitize_query",
]


INVALID = r'<>:"/\\|?*'


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
