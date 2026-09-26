#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/check_proxy_single_source.py — 代理真源唯一性检查（AST 级）

对应 docs/boothkeeper/v1/02-遗留项处置.md §2.3 验收口径 1。

为什么不用 `rg "s.proxies.update"`：文本检索无法区分**代码**与**注释/文档**。
本基类的说明性注释里必然要提到这个旧写法，用文本口径会误报；反过来，
换个变量名（`sess.proxies[...] = ...`）就漏报。故以 AST 判定。

判定规则：扫描 pages/ 与项目根的一次性脚本之外的 .py，若出现
  - `<任意表达式>.proxies.update(...)`
  - `<任意表达式>.proxies[...] = ...`
  - `<任意表达式>.proxies = ...`
即视为「手工写代理」，报错退出。

白名单（ALLOW）：极少数**非配置语义**的合法用法需显式登记，且必须写明理由。
白名单越小越好 —— 每加一条都等于放弃一处自动化防线。

退出码：0 = 无违规；1 = 有违规。
用法：python tests/check_proxy_single_source.py
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 不参与扫描：归档脚本（历史证据，允许保留旧写法）、测试自身与本检查器
SKIP_DIRS = {"archive", "tests", "build", "dist", ".git", "__pycache__",
             "preview", "preview2", "preview_build",
             "build_artifacts_trash", "devskill", "docs", "assets"}

# 白名单：key = (相对路径, 函数名, 行号)，value = 为何不算违规
ALLOW = {
    ("bk_net.py", "download_cover", 444):
        "封面直连兜底：先 dict(s.proxies) 存档、清空试直连，finally 还原存档。"
        "语义是「临时旁路后复原」，不是「配置代理」，不参与真源决策。",
}


def _is_proxies(node: ast.AST) -> bool:
    """判断表达式是否为 `<something>.proxies` 属性访问。"""
    return (isinstance(node, ast.Attribute)
            and node.attr == "proxies"
            and not isinstance(node.ctx, ast.Store))


def _collect(path: Path, tree: ast.AST) -> list[tuple[str, str, int, str]]:
    """返回 [(相对路径, 所属函数名, 行号, 说明)]。"""
    hits: list[tuple[str, str, int, str]] = []
    rel = str(path.relative_to(ROOT)).replace("\\", "/")

    def visit(node: ast.AST, func: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = func
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name
            lineno = getattr(child, "lineno", 0)

            if (isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "update"
                    and _is_proxies(child.func.value)):
                hits.append((rel, func, lineno, "手工调用 .proxies.update()"))
            elif isinstance(child, ast.Assign):
                for tgt in child.targets:
                    base = tgt.value if isinstance(tgt, ast.Subscript) else tgt
                    if _is_proxies(base):
                        hits.append((rel, func, lineno, "手工给 .proxies 赋值"))
            visit(child, name)

    visit(tree, "<module>")
    return hits


def scan(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as e:
        return [f"{path.relative_to(ROOT)}: 解析失败 {e}"]

    bad: list[str] = []
    for rel, func, lineno, what in _collect(path, tree):
        if (rel, func, lineno) in ALLOW:
            continue
        bad.append(f"{rel}:{lineno} [{func}] {what}")
    return bad


def main() -> int:
    files = [p for p in ROOT.rglob("*.py")
             if not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)]
    bad: list[str] = []
    for f in sorted(files):
        bad.extend(scan(f))

    print("=== 代理真源唯一性检查（AST）===")
    print(f"扫描文件数 = {len(files)}   白名单条目 = {len(ALLOW)}")
    if bad:
        for h in bad:
            print("  VIOLATION", h)
        print(f"违规 = {len(bad)}")
        return 1
    print("  OK  未发现未登记的手工代理写法")
    return 0


if __name__ == "__main__":
    sys.exit(main())
