# -*- coding: utf-8 -*-
"""
test_folder_icon_fix.py — 验证 R23/R24 修复

1. make_folder_icon：父目录 R+S 双设 + desktop.ini 为 shell 标准格式
   （[ViewState]/FolderType/IconResource/IconIndex，缺则 Explorer 不认 → 黄图标）
2. fix_folder_system_attr / normalize_desktop_ini：老格式 desktop.ini 归一化为标准格式
3. normalize_desktop_ini 幂等：标准格式目录调用后不变
4. force 重归档后 S 位保留
"""
import os
import sys
import random
import shutil
import tempfile
import ctypes
from pathlib import Path

# 注入 BoothKeeper
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import booth_core as bc
from PIL import Image

random.seed(42)

def noisy_img(w, h, seed=0):
    """生成内容复杂的图（防纯色压缩后 ico <1KB 被完整性契约误拦）"""
    rnd = random.Random(seed)
    im = Image.new("RGB", (w, h))
    im.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
                for _ in range(w * h)])
    return im

KERNEL = ctypes.windll.kernel32
ATTR_R, ATTR_S, ATTR_H = 0x01, 0x04, 0x02

def get_attrs(p):
    a = KERNEL.GetFileAttributesW(str(p)); return a if a != 0xFFFFFFFF else 0

def test_basic():
    """make_folder_icon 后：父目录 R+S；desktop.ini 为标准格式"""
    print("─── TEST 1: make_folder_icon → R+S + 标准格式 ini ───")
    tmp = Path(tempfile.mkdtemp(prefix="bkfix_"))
    try:
        cover = tmp / "src_cover.jpg"
        noisy_img(600, 500, 1).save(cover, "JPEG", quality=90)
        dest = tmp / "TEST_9999999_FolderIcon"
        dest.mkdir()
        shutil.copy2(cover, dest / "cover.jpg")
        bc.make_folder_icon(dest / "cover.jpg", dest)

        pa = get_attrs(dest)
        ok = bool(pa & ATTR_S) and bool(pa & ATTR_R)
        ini = (dest / "desktop.ini").read_text(encoding="utf-8")
        std = all(s in ini for s in ("[ViewState]", "FolderType=Generic",
                                     "IconResource=.folder_icon.ico", "IconIndex=0"))
        ini_a = get_attrs(dest / "desktop.ini")
        ini_hs = bool(ini_a & ATTR_H) and bool(ini_a & ATTR_S)
        print(f"  父目录 0x{pa:x} R+S={'✓' if ok else '✗'}")
        print(f"  ini 标准格式={'✓' if std else '✗'}  ini H+S={'✓' if ini_hs else '✗'}")
        ok = ok and std and ini_hs
        print(f"  结果: {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_fix_legacy():
    """老格式 desktop.ini（缺 ViewState）+ 父目录无 S → fix 后全部达标"""
    print("\n─── TEST 2: fix_folder_system_attr 修老格式（R24）───")
    tmp = Path(tempfile.mkdtemp(prefix="bkfix_"))
    try:
        d = tmp / "OLD_DIR_8888888"
        d.mkdir()
        KERNEL.SetFileAttributesW(str(d), 0x01 | 0x10)  # R + D（无 S）
        # 老格式 ini（旧版 BoothKeeper 裸格式）
        (d / "desktop.ini").write_text(
            "[.ShellClassInfo]\r\nIconResource=.folder_icon.ico,0\r\n",
            encoding="utf-8")
        (d / ".folder_icon.ico").write_bytes(b"")  # 占位（内容非本次验证点）
        before = get_attrs(d)
        print(f"  修复前: dir=0x{before:x} S={'✓' if before & ATTR_S else '✗'}")

        r = bc.fix_folder_system_attr(roots=[str(tmp)])
        after = get_attrs(d)
        ini_txt = (d / "desktop.ini").read_text(encoding="utf-8")
        has_viewstate = "[ViewState]" in ini_txt and "IconIndex=" in ini_txt
        ok = (after & ATTR_S) and has_viewstate and r.get("normalized", 0) >= 1
        print(f"  修复后: dir=0x{after:x} S={'✓' if after & ATTR_S else '✗'}  "
              f"ini标准={'✓' if has_viewstate else '✗'}  "
              f"报告 normalized={r.get('normalized')}")
        print(f"  结果: {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_normalize_idempotent():
    """normalize_desktop_ini 幂等：标准格式目录调用后返回 False 且内容不变"""
    print("\n─── TEST 3: normalize_desktop_ini 幂等 ───")
    tmp = Path(tempfile.mkdtemp(prefix="bkfix_"))
    try:
        cover = tmp / "c.jpg"
        noisy_img(300, 300, 2).save(cover, "JPEG", quality=90)
        d = tmp / "IDEM_6666666"
        d.mkdir()
        shutil.copy2(cover, d / "cover.jpg")
        bc.make_folder_icon(d / "cover.jpg", d)
        before = (d / "desktop.ini").read_text(encoding="utf-8")
        changed = bc.normalize_desktop_ini(d)
        after = (d / "desktop.ini").read_text(encoding="utf-8")
        ok = (changed is False) and (before == after)
        print(f"  返回 False（未改动）={'✓' if changed is False else '✗'}  内容一致={'✓' if before == after else '✗'}")
        print(f"  结果: {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_force_archive_keeps_S():
    """force 重归档后，make_folder_icon 应保持 S 位（不被 move 漏掉）"""
    print("\n─── TEST 4: force 重归档后 S 位仍在 ───")
    tmp = Path(tempfile.mkdtemp(prefix="bkfix_"))
    try:
        src_cover = tmp / "src_cover2.jpg"
        noisy_img(400, 400, 3).save(src_cover, "JPEG", quality=90)
        dest = tmp / "TEST_7777777_Force"
        dest.mkdir()
        shutil.copy2(src_cover, dest / "cover.jpg")
        bc.make_folder_icon(dest / "cover.jpg", dest)
        before_S = bool(get_attrs(dest) & ATTR_S)

        Image.new("RGB", (400, 400), (200, 50, 50)).save(src_cover, "JPEG", quality=85)
        shutil.copy2(src_cover, dest / "cover.jpg")
        bc.make_folder_icon(dest / "cover.jpg", dest)
        after_S = bool(get_attrs(dest) & ATTR_S)
        ok = before_S and after_S
        print(f"  首次归档后 S: {before_S}  force 后 S: {after_S}")
        print(f"  结果: {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    r1 = test_basic()
    r2 = test_fix_legacy()
    r3 = test_normalize_idempotent()
    r4 = test_force_archive_keeps_S()
    print(f"\n汇总: {sum([r1, r2, r3, r4])}/4 通过")
    sys.exit(0 if all([r1, r2, r3, r4]) else 1)
