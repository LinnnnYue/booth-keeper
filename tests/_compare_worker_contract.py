#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/_compare_worker_contract.py — 一次性核验：2.3 改造前后 Worker 信号契约

对应 docs/boothkeeper/v1/02-遗留项处置.md §2.3 验收口径 2：
「10 个 Worker 的公开信号名与参数不变」。

做法：从指定 commit 读取改造前的页面文件，与工作区当前文件各自解析出
「类名 → {信号名: 参数元组}」，逐项比对差异。

用法：python tests/_compare_worker_contract.py [<改造前commit>]
默认 commit = 4d3c6b6（R17 末次提交，改造前）。
"""
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "4d3c6b6"

PAGE_FILES = [
    "pages/search_page.py",
    "pages/links_page.py",
    "pages/dragdrop_page.py",
    "pages/audit_page.py",
]


def parse_signals(src: str) -> dict:
    """返回 {类名: {信号名: 参数元组}}，只看继承 QThread 的类。"""
    tree = ast.parse(src)
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(b.attr)
        if not any("Thread" in b or "Task" in b for b in bases):
            continue
        sigs = {}
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            is_signal = (isinstance(item.value, ast.Call)
                         and isinstance(item.value.func, ast.Name)
                         and item.value.func.id == "Signal")
            if not is_signal:
                continue
            for tgt in item.targets:
                if isinstance(tgt, ast.Name):
                    args = []
                    for a in item.value.args:
                        try:
                            args.append(ast.literal_eval(a))
                        except Exception:
                            args.append(ast.unparse(a))
                    sigs[tgt.id] = tuple(args)
        if sigs or bases:
            out[node.name] = sigs
    return out


def git_show(rel: str) -> str:
    r = subprocess.run(["git", "show", f"{BASE}:{rel}"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"取 {BASE}:{rel} 失败：{r.stderr.strip()}")
    return r.stdout


def main() -> int:
    all_before, all_after = {}, {}
    for rel in PAGE_FILES:
        before = parse_signals(git_show(rel))
        after = parse_signals((ROOT / rel).read_text(encoding="utf-8"))
        for k in set(before) | set(after):
            all_before[f"{rel}::{k}"] = before.get(k, {})
            all_after[f"{rel}::{k}"] = after.get(k, {})

    keys = sorted(set(all_before) & set(all_after))
    print(f"=== Worker 信号契约比对（{BASE} vs 工作区）===")
    print(f"比对类数 = {len(keys)}")

    bad = 0
    only_before = sorted(set(all_before) - set(all_after))
    if only_before:
        print("  仅改造前存在:", only_before)
        bad += len(only_before)

    for k in keys:
        b, a = all_before[k], all_after[k]
        if b == a:
            print(f"  OK   {k:44s} {a}")
        else:
            print(f"  DIFF {k}")
            print(f"        改造前 {b}")
            print(f"        改造后 {a}")
            bad += 1

    print(f"不一致 = {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
