#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/check_module_deps.py — 跨模块引用完整性静态检查

背景：R23 把 booth_core.py 拆为 6 个 bk_* 模块后，某模块引用了定义在另一模块的
符号却忘记 import 时，`py_compile` 不会报错 —— 只有真正执行到那一行才抛 NameError。
`from x import *` 只带出公共符号，因此**私有符号的跨模块引用**是主要风险源
（实际发生过：bk_search 漏 import `_json_cache` / `_parse_price` / `_thumb_from_json`）。

本脚本用 AST 做静态解析：收集每个模块的顶层定义、显式导入、星号导入来源、
局部绑定与函数参数，再检查所有 Load 上下文的名字是否可解析。退出码非零即失败，
可直接接入 CI 或 pre-commit。

运行： python tests/check_module_deps.py
"""
import ast
import builtins
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULES = ["bk_domain", "bk_text", "bk_shell", "bk_net", "bk_local", "bk_search"]


def parse(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    defined, imported, stars = set(), set(), []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            defined |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined.add(node.target.id)
        elif isinstance(node, ast.Import):
            for a in node.names:
                imported.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "*":
                    stars.append(node.module)
                else:
                    imported.add(a.asname or a.name)
    return tree, defined, imported, stars


def exported(info, name):
    """星号导入实际带出的名字：有 __all__ 则按 __all__，否则为全部非下划线名。"""
    tree = info[name][0]
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == "__all__" for t in node.targets):
            return {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
    return {n for n in info[name][1] if not n.startswith("_")}


def main():
    info = {}
    for m in MODULES:
        p = ROOT / f"{m}.py"
        if not p.exists():
            print(f"!! 缺少模块 {m}.py")
            return 1
        info[m] = parse(p)

    owner = {}
    for m in MODULES:
        for n in info[m][1] | info[m][2] | exported(info, m):
            owner.setdefault(n, m)

    bnames = set(dir(builtins))
    total = 0
    print("=== 跨模块引用未 import 检查 ===")
    for m in MODULES:
        tree, defined, imported, stars = info[m]
        visible = set(defined) | set(imported) | bnames
        for s in stars:
            if s:
                visible |= exported(info, s)
        visible |= {n.id for n in ast.walk(tree)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        for n in ast.walk(tree):
            if isinstance(n, ast.arg):
                visible.add(n.arg)
            if isinstance(n, ast.ExceptHandler) and n.name:
                visible.add(n.name)
        loads = {n.id for n in ast.walk(tree)
                 if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        unresolved = sorted(x for x in loads - visible
                            if x in owner and owner[x] != m)
        if unresolved:
            total += len(unresolved)
            print(f"  FAIL {m} 缺: "
                  + ", ".join(f"{x}(定义于 {owner[x]})" for x in unresolved))
        else:
            print(f"  OK   {m}")
    print(f"合计缺失 = {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
