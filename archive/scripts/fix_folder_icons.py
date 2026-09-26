# -*- coding: utf-8 -*-
"""
fix_folder_icons.py — 一次性补 System 标志修复 BOOTH 库全库「黄色默认图标」

根因：make_folder_icon 在旧版本只给父目录设了 R(0x01) 位，漏了 S(0x04)。
Windows 要求 IconResource 的 desktop.ini 必须父目录带 S 位才会被 Explorer 接受。
后果：重启电脑也无法生效（不读 desktop.ini）。

用法：
  python fix_folder_icons.py            # 干跑，预演
  python fix_folder_icons.py --apply    # 实际修复
  python fix_folder_icons.py --root "G:\\Lin_File\\BOOTH\\3D服饰"   # 指定子目录

非破坏性：仅设文件系统属性位，零文件增删。
"""
import os
import sys
import ctypes
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

if os.name != "nt":
    print("仅 Windows 可用"); sys.exit(1)

# BOOTH 库根（可被 --root 覆盖）
DEFAULT_ROOTS = [
    r"G:\Lin_File\BOOTH\3D服饰",
    r"G:\Lin_File\BOOTH\3D发型",
    r"G:\Lin_File\BOOTH\3D饰品",
    r"G:\Lin_File\BOOTH\3D模型",
    r"G:\Lin_File\BOOTH\3D工具",
    r"G:\Lin_File\BOOTH\3D动作",
]
EXTRA_ROOTS_FROM_CONFIG = r"~/.boothkeeper.json"  # 库根的备选来源

KERNEL = ctypes.windll.kernel32
SHELL = ctypes.windll.shell32

ATTR_R = 0x01
ATTR_S = 0x04
ATTR_H = 0x02
ATTR_A = 0x20
ATTR_D = 0x10
ATTR_NI = 0x2000  # Not Indexed

# ---------- 属性 ----------
def get_attrs(p: str) -> int:
    a = KERNEL.GetFileAttributesW(p)
    return a if a != 0xFFFFFFFF else 0

def set_attrs(p: str, attrs: int) -> bool:
    return bool(KERNEL.SetFileAttributesW(p, attrs))

# ---------- 父目录通知 ----------
def notify_parent(p: str):
    """发 SHCNE_UPDATEDIR 给父目录（让 Explorer 重新读父目录 desktop.ini，
    并刷新该父目录的子目录视图），失败兜底发 SHCNE_ASSOCCHANGED。"""
    parent = str(Path(p).parent)
    try:
        SHELL.SHChangeNotify(0x00000005, 0x0000, None, None)  # SHCNE_UPDATEDIR
        SHELL.SHChangeNotify(0x00000002, 0x0000, None, None)  # SHCNE_UPDATEITEM
    except Exception:
        pass
    try:
        SHELL.SHChangeNotify(0x08000000, 0x0000, None, None)  # SHCNE_ASSOCCHANGED 兜底
    except Exception:
        pass

# ---------- 单目录检测 ----------
def needs_fix(folder: Path) -> dict | None:
    """返回 fix 信息：{folder, missing: 'S'/'H', has_ini, has_ico}；不需要修则 None。"""
    if not folder.is_dir():
        return None
    ini = folder / "desktop.ini"
    ico = folder / ".folder_icon.ico"
    if not (ini.exists() and ico.exists()):
        # 三件套不全 → 不归本脚本管（走重归档流程）
        return None
    pa = get_attrs(str(folder))
    if pa == 0:
        return None
    if pa & ATTR_S:        # 已经有 S
        return None
    return {
        "folder": str(folder),
        "attrs": pa,
        "missing": "S",
        "has_ico": True,
        "has_ini": True,
    }

def apply_one(info: dict) -> tuple[str, str]:
    f = info["folder"]
    cur = get_attrs(f)
    if cur == 0:
        return f, "skip(GONE)"
    # 同时补 H（父目录建议也带 H，因为 desktop.ini 自身已 H）
    new = cur | ATTR_S | ATTR_H | ATTR_A
    if set_attrs(f, new):
        notify_parent(f)
        return f, "ok"
    return f, "fail"

# ---------- 扫描 ----------
def gather_targets(roots: list[str]) -> list[dict]:
    out = []
    for root in roots:
        rp = Path(root)
        if not rp.exists():
            continue
        # 扫一级子目录（3D服饰、3D发型等就是 BOOTH 大类，每个商品目录是大类的直接子目录）
        for d in rp.iterdir():
            if not d.is_dir():
                continue
            info = needs_fix(d)
            if info:
                out.append(info)
    return out

# ---------- 入口 ----------
def main():
    apply = "--apply" in sys.argv
    custom_root = None
    if "--root" in sys.argv:
        i = sys.argv.index("--root")
        if i + 1 < len(sys.argv):
            custom_root = sys.argv[i + 1]
    roots = [custom_root] if custom_root else DEFAULT_ROOTS
    print(f"[{time.strftime('%H:%M:%S')}] 扫描根: {roots}")
    targets = gather_targets(roots)
    print(f"命中需要补 S 位的目录: {len(targets)}")
    if not targets:
        print("无需要修复的目录。"); return 0
    for t in targets[:5]:
        print("  示例:", t["folder"], f"attrs=0x{t['attrs']:x} 缺={t['missing']}")
    if not apply:
        print("\n(干跑模式 — 不会修改任何文件，加 --apply 实际执行)")
        return 0
    print("\n开始修复 ...")
    ok = 0
    fail = 0
    with ThreadPoolExecutor(8) as ex:
        for path, status in ex.map(apply_one, targets):
            if status == "ok":
                ok += 1
            else:
                fail += 1
            if fail and fail < 5:
                print(f"  失败: {path}  {status}")
    print(f"\n完成: ok={ok}  fail={fail}  total={len(targets)}")
    print("提示: 若资源管理器仍显示旧图标，请切换视图模式（大图标 ↔ 详细信息）触发重绘。")
    print("      极端情况：ie4uinit.exe -show  →  重启 explorer.exe")
    return 0 if fail == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
