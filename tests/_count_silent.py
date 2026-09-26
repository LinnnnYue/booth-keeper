#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/_count_silent.py — 静默失败点计数（与 review/2026-09-27-静默失败点评审.md §5 同口径）

口径：`except ...:` 语句的下一行紧跟 `pass`（脚本化提取，非人工抽样）。
跨 ref 计算时对**同语义文件集**取并集：拆分后 booth_core.py 的内容位于
bk_*.py，故旧基线计算时把 booth_core.py 与当前 bk_*.py 同归一组。

用法：
    python tests/_count_silent.py            # 工作区
    python tests/_count_silent.py 4d3c6b6    # 指定 commit
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 与旧口径一致的四文件 + pages/ 全部
BASE_FILES = ["booth_core.py", "archive_util.py", "main_window.py", "theme.py"]
# R23 新增（拆分产物 + 诊断通道）
NEW_FILES = ["diag.py"]


def _count_lines(lines: list[str]) -> int:
    return sum(1 for i, ln in enumerate(lines)
               if ln.strip() == "pass" and i > 0
               and lines[i - 1].strip().startswith("except"))


def _read(path: str, ref: str | None) -> list[str] | None:
    if ref:
        r = subprocess.run(["git", "show", f"{ref}:{path}"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8")
        return r.stdout.splitlines() if r.returncode == 0 else None
    p = ROOT / path
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else None


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else None
    pages = sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                   for p in (ROOT / "pages").glob("*.py"))
    # 拆分产物：旧状态不存在（git show 失败即跳过），新状态是 booth_core 的等价体
    bk = sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                for p in ROOT.glob("bk_*.py"))
    files = BASE_FILES + NEW_FILES + bk + pages
    if ref:
        # 旧状态：拆分尚未发生，bk_*.py 不存在（git show 会失败并跳过）
        pass

    total, per = 0, {}
    for f in files:
        lines = _read(f, ref)
        if lines is None:
            continue
        n = _count_lines(lines)
        if n:
            per[f] = n
            total += n

    print(f"=== 静默点计数（{'工作区' if not ref else ref}）===")
    for f, n in sorted(per.items()):
        print(f"  {f}: {n}")
    print(f"合计 = {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
