#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/_count_proxy_writes.py — 手工写 session.proxies 的跨版本计数

口径与 tests/check_proxy_single_source.py 一致（AST 判定，注释不计）。
跨 ref 计算时对同语义文件集取并集：拆分后 booth_core.py 的内容位于 bk_*.py。

用法：
    python tests/_count_proxy_writes.py            # 工作区
    python tests/_count_proxy_writes.py 4d3c6b6    # 指定 commit
"""
import ast
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_proxy_single_source import _collect  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = ["booth_core.py", "archive_util.py", "main_window.py", "theme.py"]
EXTRA = ["diag.py"]


def _src(rel: str, ref: str | None) -> str | None:
    if ref:
        r = subprocess.run(["git", "show", f"{ref}:{rel}"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8")
        return r.stdout if r.returncode == 0 else None
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else None


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else None
    rels = BASE + EXTRA
    rels += sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                   for p in (ROOT / "pages").glob("*.py"))
    rels += sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                   for p in ROOT.glob("bk_*.py"))

    total, per = 0, {}
    for rel in rels:
        src = _src(rel, ref)
        if src is None:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        hits = _collect(Path(ROOT / rel), tree)
        if hits:
            per[rel] = len(hits)
            total += len(hits)

    print(f"=== 手工写 .proxies 计数（{'工作区' if not ref else ref}）===")
    for f, n in sorted(per.items()):
        print(f"  {f}: {n}")
    print(f"合计 = {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
