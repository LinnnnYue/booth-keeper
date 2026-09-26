#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bk_shell — Windows 文件夹图标与 Shell 属性

由 booth_core.py 拆分而来（R23）。封装 Explorer 文件夹图标三件套
（cover.jpg / .folder_icon.ico / desktop.ini）的生成、校验与全库修复。

⚠️ 本模块含 Windows 专有 API（ctypes.windll），非 Windows 平台不可用。
"""

import os
import ctypes
import diag
from pathlib import Path
from PIL import Image

__all__ = [
    "DESKTOP_INI_STANDARD",
    "IconContractError",
    "fix_folder_system_attr",
    "make_folder_icon",
    "normalize_desktop_ini",
    "set_attrs",
    "set_hidden",
]




# ── Windows 文件夹图标（完整性契约）─────────────────────────────
class IconContractError(RuntimeError):
    """三件套不齐全时抛出（防 Hermes 类 agent 留半成品 desktop.ini 误导 Explorer）。"""


def set_attrs(path, attrs: int):
    if os.name != "nt":
        return
    ctypes.windll.kernel32.SetFileAttributesW(str(path), attrs)


def _get_attrs(path) -> int:
    """返回文件属性位（Windows）。失败返回 0。"""
    if os.name != "nt":
        return 0
    a = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    return a if a != 0xFFFFFFFF else 0


def _notify_shell():
    """触发 Windows Explorer 全 shell 刷新（图标缓存）。"""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SHChangeNotify(0x00008000, 0x0000, None, None)
    except Exception:
        pass


def set_hidden(path_str: str):
    """Hidden + System 同时设（2026-08-02 修正：之前只设 H 漏 S，
    导致 desktop.ini 属性不全、Explorer 拒读）。"""
    if os.name != "nt":
        return
    FILE_ATTRIBUTE_HIDDEN = 0x02
    FILE_ATTRIBUTE_SYSTEM = 0x04
    attrs = ctypes.windll.kernel32.GetFileAttributesW(path_str)
    if attrs != 0xFFFFFFFF:
        ctypes.windll.kernel32.SetFileAttributesW(path_str, attrs | FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)


def _get_pidl_pair(folder_path: str):
    ole32 = ctypes.windll.ole32
    shell32 = ctypes.windll.shell32
    pidl = ctypes.c_void_p()
    shell32.SHParseDisplayName(folder_path, 0, None, ctypes.byref(ctypes.c_ulong()), ctypes.byref(pidl))
    return None, pidl


def _verify_icon_contract(ico_path, ini_path, folder_path):
    if not ico_path.exists():
        raise IconContractError(f"ico 缺失：{ico_path}")
    if ico_path.stat().st_size < 1024:
        raise IconContractError(f"ico 过小（<1KB）：{ico_path}")
    if not ini_path.exists():
        raise IconContractError(f"ini 缺失：{ini_path}")
    try:
        txt = ini_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        txt = ini_path.read_bytes().decode("utf-8", "replace")
    if "IconResource=.folder_icon.ico" not in txt:
        raise IconContractError(f"ini 缺 IconResource=.folder_icon.ico 字段：{ini_path}")
    a = ctypes.windll.kernel32.GetFileAttributesW(str(folder_path))
    if a == 0xFFFFFFFF or not (a & 0x01):
        ctypes.windll.kernel32.SetFileAttributesW(str(folder_path), a | 0x01)


# R24（2026-09-08 主上实测钦定）：desktop.ini 的 shell 原生标准格式。
# 旧版只写「[.ShellClassInfo]\nIconResource=...」（无 [ViewState]/IconIndex 段）→
# Explorer 不认 → 目录永远黄色默认图标。标准格式带 [ViewState] FolderType=Generic
# + IconResource + IconIndex=0（CRLF 行尾），与资源管理器「更改图标」写入的形态一致。
# 单一来源：make_folder_icon / normalize_desktop_ini / fix_folder_system_attr 全部引用。
DESKTOP_INI_STANDARD = (
    "[ViewState]\r\n"
    "FolderType=Generic\r\n"
    "[.ShellClassInfo]\r\n"
    "IconResource=.folder_icon.ico,0\r\n"
    "IconIndex=0\r\n"
)


def make_folder_icon(cover_path: Path, folder_path: Path):
    """cover.jpg → .folder_icon.ico + desktop.ini（三件套），含完整性契约。

    血泪坑（2026-08-01/02）：
      - 宽幅 cover 直接 save 会生成非正方形 ICO（256x154）→ 缩略图居中小图 → 先贴正方形画布
      - desktop.ini/ico 缺 H/S 属性 → Explorer 拒读 → 写完自检三件套
      - 写完不校验 → Hermes 类 agent 留残缺 desktop.ini → 自检 raise IconContractError
    血泪坑（2026-09-08 主上实测）：
      - 父目录只设 R(0x01) 漏 S(0x04) → Explorer 永远不读 desktop.ini → 黄色默认图标
        且重启电脑也无效（不是 IconCache 缓存问题，是 desktop.ini 从未被读过）
      - 修法：父目录设 R(0x01) | S(0x04)，且写完后向父目录发 SHCNE_UPDATEDIR
        （让打开父目录视图的 Explorer 重新读 desktop.ini 缓存）
    血泪坑（2026-09-08 傍晚 R24，26 目录实锤）：
      - S 位补全 + 重启电脑后仍黄的目录，根因是 desktop.ini 为旧版「裸格式」
        （只有 [.ShellClassInfo]+IconResource，缺 [ViewState]/IconIndex 段）→
        shell 层 SHGetSetFolderCustomSettings 读回空、SHGetFileInfo 恒返回默认索引
      - 修法：desktop.ini 统一写 shell 原生标准格式 DESKTOP_INI_STANDARD
        （[ViewState] FolderType=Generic + IconResource + IconIndex=0, CRLF），
        26 个目录重写后全部立即恢复（用户当场确认）
    """
    if not cover_path or not cover_path.exists():
        raise IconContractError(f"cover 缺失：{cover_path}")
    try:
        img = Image.open(cover_path).convert("RGBA")
        side = max(img.size)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        ico_path = folder_path / ".folder_icon.ico"
        ini_path = folder_path / "desktop.ini"
        ini_content = DESKTOP_INI_STANDARD
        for p in (ico_path, ini_path):
            if p.exists():
                try:
                    ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
                except Exception:
                    pass
        canvas.save(str(ico_path), format="ICO", sizes=sizes)
        ini_path.write_text(ini_content, encoding="utf-8")
        set_hidden(str(ini_path))
        set_hidden(str(ico_path))
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(folder_path))
        # R23（2026-09-08 钦定）：父目录必须 R(0x01) | S(0x04) 双设，
        # 否则 Explorer 拒读 desktop.ini（与 ico/ini 自身的 H+S 同理）。
        # ⚠️ 父目录绝不能加 H(0x02) —— 加了资源管理器默认隐藏，整个目录从视图中消失！
        ctypes.windll.kernel32.SetFileAttributesW(str(folder_path), attrs | 0x01 | 0x04)
        _verify_icon_contract(ico_path, ini_path, folder_path)
        # 通知 Explorer 刷新图标缓存
        try:
            _, pidl_item = _get_pidl_pair(str(folder_path))
            ctypes.windll.shell32.SHChangeNotify(0x00000008, 0x0000, pidl_item, None)
            ctypes.windll.ole32.CoTaskMemFree(pidl_item)
        except Exception:
            ctypes.windll.shell32.SHChangeNotify(0x00008000, 0x0000, None, None)
        # R23：额外发 SHCNE_UPDATEDIR 给父目录，让正打开父目录视图的 Explorer
        # 主动重读 desktop.ini 缓存并刷新子目录视图。
        # 刷新失败不影响图标契约本身（下次进目录仍是有效图标），故记 info 级：
        # 只入诊断缓冲，不弹状态栏、不打扰操作。
        try:
            ctypes.windll.shell32.SHChangeNotify(0x00000005, 0x0000, None, None)  # SHCNE_UPDATEDIR
        except Exception as e:
            diag.info(f"Explorer 刷新通知失败（图标本身有效）：{e}",
                      scope="make_folder_icon", path=str(folder_path))
    except IconContractError:
        raise
    except Exception as e:
        ini = folder_path / "desktop.ini"
        # R23：清理结果如实反映在异常消息里 —— 原先无论成功失败都写死
        # 「已清理残缺 desktop.ini」，清理失败时即对用户撒谎（R17 高危模式）。
        cleaned = False
        if ini.exists():
            try:
                ctypes.windll.kernel32.SetFileAttributesW(str(ini), 0x80)
                ini.unlink()
                cleaned = True
            except Exception as ce:
                diag.warn(f"残缺 desktop.ini 清理失败（将残留于目录内）：{ce}",
                          scope="make_folder_icon", path=str(ini))
        tail = ("已清理残缺 desktop.ini" if cleaned
                else "残缺 desktop.ini 仍残留（清理失败，见诊断日志）")
        raise IconContractError(f"图标设置失败（{tail}）：{e}")


# ── 全库修复：补 System 标志（R23，2026-09-08 主上实测）─────────────
def normalize_desktop_ini(folder_path) -> bool:
    """把目录的 desktop.ini 归一化为 shell 原生标准格式（R24）。

    幂等：已是标准格式（含 [ViewState] 与 IconIndex=）→ 不动，返回 False；
    旧版裸格式（缺任一字段）→ 重写为 DESKTOP_INI_STANDARD。标准格式是裸格式的
    超集（裸格式的 IconResource 语义被完整保留），因此重写无信息丢失。
    写前清属性（防 PermissionError），写后补 H+S，并发 SHCNE_UPDATEITEM/UPDATEDIR。

    返回 True 表示发生了重写；目录无三件套/无 ini 时返回 False。
    """
    folder_path = Path(folder_path)
    ini_path = folder_path / "desktop.ini"
    if not ini_path.exists():
        return False
    try:
        raw = ini_path.read_bytes()
    except Exception:
        return False
    if raw[:2] == b"\xff\xfe":
        txt = raw.decode("utf-16-le", errors="replace")
    elif raw[:3] == b"\xef\xbb\xbf":
        txt = raw.decode("utf-8", errors="replace")
    else:
        txt = raw.decode("utf-8", errors="replace")
    if "[ViewState]" in txt and "IconIndex=" in txt:
        return False  # 已是标准格式
    K = ctypes.windll.kernel32
    try:
        K.SetFileAttributesW(str(ini_path), 0x80)  # 清 H/S → NORMAL
        ini_path.write_text(DESKTOP_INI_STANDARD, encoding="utf-8")
    except Exception as e:
        raise IconContractError(f"desktop.ini 归一化失败：{ini_path} ({e})") from e
    a = K.GetFileAttributesW(str(ini_path))
    K.SetFileAttributesW(str(ini_path), a | 0x02 | 0x04)  # H+S
    try:
        ctypes.windll.shell32.SHChangeNotify(0x2, 0x5, str(folder_path), None)
        ctypes.windll.shell32.SHChangeNotify(0x5, 0x5, str(folder_path.parent), None)
    except Exception as e:
        diag.info(f"Explorer 刷新通知失败（ini 已归一化，下次进目录生效）：{e}",
                  scope="normalize_desktop_ini", path=str(folder_path))
    return True


def fix_folder_system_attr(roots: list[str] | None = None,
                           on_progress=None) -> dict:
    """扫描 BOOTH 大类目录（3D服饰/3D发型/...），一键修复「黄色默认图标」。

    两项修复（R23 + R24）：
      1. 补 S(0x04)+R(0x01) 给「三件套齐全但父目录缺 S 位」的目录 —— 否则
         Explorer 根本不读 desktop.ini（重启电脑也无效）。
      2. desktop.ini 归一化为 shell 原生标准格式（normalize_desktop_ini）——
         旧版裸格式（缺 [ViewState]/IconIndex）同样不被 shell 采用。
    非破坏性：仅设文件系统属性位 + 重写 desktop.ini 文本，零本体文件增删。
    返回 {scanned, fixed, normalized, failed, examples: [...]}（兼容旧键）。
    """
    DEFAULT_ROOTS = [
        r"G:\Lin_File\BOOTH\3D服饰",
        r"G:\Lin_File\BOOTH\3D发型",
        r"G:\Lin_File\BOOTH\3D饰品",
        r"G:\Lin_File\BOOTH\3D模型",
        r"G:\Lin_File\BOOTH\3D工具",
        r"G:\Lin_File\BOOTH\3D动作",
    ]
    if not roots:
        roots = DEFAULT_ROOTS
    SHELL = ctypes.windll.shell32
    fixed = 0; normalized = 0; failed = 0; examples: list[str] = []
    for root in roots:
        rp = Path(root)
        if not rp.exists():
            continue
        for d in rp.iterdir():
            if not d.is_dir():
                continue
            ini = d / "desktop.ini"; ico = d / ".folder_icon.ico"
            if not (ini.exists() and ico.exists()):
                continue
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(d))
            if attrs != 0xFFFFFFFF and not (attrs & 0x04):
                new = attrs | 0x04 | 0x01 | 0x20  # S + R + A（注意：禁 H 隐藏！）
                try:
                    ctypes.windll.kernel32.SetFileAttributesW(str(d), new)
                    fixed += 1
                    if len(examples) < 3:
                        examples.append(d.name)
                    # 通知 Explorer 刷新父目录视图
                    try:
                        SHELL.SHChangeNotify(0x00000005, 0x0000, None, None)  # SHCNE_UPDATEDIR
                    except Exception:
                        pass
                except Exception as e:
                    failed += 1
                    if on_progress:
                        on_progress(f"  失败: {d.name} ({e})")
            # R24：desktop.ini 老格式 → 归一化为标准格式（幂等）
            try:
                if normalize_desktop_ini(d):
                    normalized += 1
                    if len(examples) < 3:
                        examples.append(d.name + " (ini归一化)")
            except IconContractError as e:
                failed += 1
                if on_progress:
                    on_progress(f"  ini归一化失败: {d.name} ({e})")
            if on_progress and (fixed + normalized + failed) % 50 == 0:
                on_progress(f"  进度: 补S {fixed} / 归一化 {normalized} / 失败 {failed}")
    if on_progress:
        on_progress(f"完成：补S {fixed} 件 / ini归一化 {normalized} 件 / 失败 {failed} 件")
    return {"scanned": fixed + normalized + failed, "fixed": fixed,
            "normalized": normalized, "failed": failed, "examples": examples}
