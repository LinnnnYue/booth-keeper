# -*- coding: utf-8 -*-
"""R24 根治扫尾：全库 6 大类扫描「老格式 desktop.ini」(缺 [ViewState]/IconIndex)，
统一重写为 shell 原生标准格式（与 make_folder_icon 输出一致，无信息丢失），
并清理本次排障遗留的 desktop.ini.bak_shellfmt / desktop.ini.bak 备份。
安全：只改 desktop.ini 文件本身；目录属性不动（不加 H）。"""
import ctypes, os
from pathlib import Path

k = ctypes.windll.kernel32
GA = k.GetFileAttributesW
SA = k.SetFileAttributesW
shell32 = ctypes.windll.shell32

ROOTS = [r'G:\Lin_File\BOOTH\3D服饰', r'G:\Lin_File\BOOTH\3D发型',
         r'G:\Lin_File\BOOTH\3D饰品', r'G:\Lin_File\BOOTH\3D模型',
         r'G:\Lin_File\BOOTH\3D工具', r'G:\Lin_File\BOOTH\3D动作']

INI_STANDARD = ("[ViewState]\r\nFolderType=Generic\r\n"
                "[.ShellClassInfo]\r\nIconResource=.folder_icon.ico,0\r\nIconIndex=0\r\n")

def read_ini(p):
    raw = p.read_bytes()
    if raw[:2] == b'\xff\xfe':
        return raw.decode('utf-16-le', errors='replace')
    if raw[:3] == b'\xef\xbb\xbf':
        return raw.decode('utf-8', errors='replace')
    return raw.decode('utf-8', errors='replace')

def notify_folder(d):
    try: shell32.SHChangeNotify(0x2, 0x5, str(d), None)
    except Exception: pass
    try: shell32.SHChangeNotify(0x5, 0x5, str(d.parent), None)
    except Exception: pass

legacy, clean, cleaned_bak, total = 0, 0, 0, 0
for root in ROOTS:
    rp = Path(root)
    if not rp.exists(): continue
    for d in sorted(rp.iterdir()):
        if not d.is_dir(): continue
        ini = d / 'desktop.ini'
        ico = d / '.folder_icon.ico'
        if not (ini.exists() and ico.exists()): continue
        total += 1
        txt = read_ini(ini)
        is_legacy = ('[ViewState]' not in txt) or ('IconIndex=' not in txt)
        if is_legacy:
            try:
                SA(str(ini), 0x80)  # 清 H/S → NORMAL，否则 PermissionError
                ini.write_text(INI_STANDARD, encoding='utf-8')
            except PermissionError:
                print(f'LOCKED {d.name[:52]}')
                continue
            a = GA(str(ini))
            SA(str(ini), a | 0x02 | 0x04)
            notify_folder(d)
            legacy += 1
            print(f'REWRITE {d.name[:52]}')
        else:
            clean += 1
        # 清理本次排障遗留备份
        for bak_name in ('desktop.ini.bak_shellfmt', 'desktop.ini.bak'):
            bp = d / bak_name
            if bp.exists():
                try:
                    SA(str(bp), 0x80)
                    os.remove(str(bp))
                    cleaned_bak += 1
                except Exception as e:
                    print(f'  清理 {bak_name} 失败: {e}')

try: shell32.SHChangeNotify(0x08000000, 0, None, None)
except Exception: pass
print(f'\n总计三件套目录 {total} | 老格式重写 {legacy} | 已是标准格式 {clean} | 清理遗留备份 {cleaned_bak}')
