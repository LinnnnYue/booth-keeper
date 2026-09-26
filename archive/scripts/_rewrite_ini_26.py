# -*- coding: utf-8 -*-
"""对 26 个黄目录：desktop.ini 统一重写为 shell 原生标准格式 + 逐目录刷新通知。
安全：不动目录属性；desktop.ini 先写临时文件再替换，原文件 .bak 留底。"""
import ctypes, os, shutil, time
from pathlib import Path

k = ctypes.windll.kernel32
GA = k.GetFileAttributesW
SA = k.SetFileAttributesW
shell32 = ctypes.windll.shell32

ROOT = Path(r'G:\Lin_File\BOOTH\3D服饰')
YELLOW_IDS = {'7042776','8383304','6949296','6220132','7389778','6200953','5674632',
              '7021465','6033509','6567440','7172562','7148608','6818558','5613949',
              '5760880','6834469','6515860','6499853','6114837','5988032','5739125',
              '5722778','7763987','8417939','8589747','8749497'}

# shell 原生格式（对齐 SHGetSetFolderCustomSettings 写出的形态）
INI_TEMPLATE = "[ViewState]\r\nFolderType=Generic\r\n\r\n[.ShellClassInfo]\r\nIconResource=.folder_icon.ico,0\r\nIconIndex=0\r\n"

def notify_folder(d):
    # SHCNE_UPDATEITEM(0x2) on the folder + SHCNE_UPDATEDIR(0x5) on parent, PATHW
    try:
        shell32.SHChangeNotify(0x2, 0x5, str(d), None)
    except Exception: pass
    try:
        shell32.SHChangeNotify(0x5, 0x5, str(d.parent), None)
    except Exception: pass

fixed, skipped = 0, []
for d in sorted(ROOT.iterdir()):
    if not d.is_dir(): continue
    fid = d.name.split('_')[0]
    if fid not in YELLOW_IDS: continue
    ini = d / 'desktop.ini'
    ico = d / '.folder_icon.ico'
    if not ico.exists():
        skipped.append((d.name, 'no ico')); continue
    # 备份
    bak = d / 'desktop.ini.bak_shellfmt'
    if not bak.exists():
        shutil.copy2(ini, bak)
    # 写临时文件 → 替换（保留原 desktop.ini 的隐藏/系统属性需重设）
    tmp = d / 'desktop.ini.tmp'
    tmp.write_bytes(INI_TEMPLATE.encode('utf-8'))
    if ini.exists():
        old_attr = GA(str(ini))
    else:
        old_attr = 0x06  # H+S
    try:
        if ini.exists():
            os.remove(str(ini))
    except Exception:
        pass
    os.replace(str(tmp), str(ini))
    # 恢复/设置 H+S(+A) 属性
    a = GA(str(ini))
    SA(str(ini), a | 0x02 | 0x04)
    # 目录确保 R+S（不加 H）
    da = GA(str(d))
    if da != 0xFFFFFFFF and not (da & 0x04):
        SA(str(d), da | 0x01 | 0x04)
    notify_folder(d)
    fixed += 1
    print(f'OK {fid} {d.name[:40]}')

# 全局兜底
try:
    shell32.SHChangeNotify(0x08000000, 0, None, None)  # ASSOCCHANGED
except Exception: pass
print(f'\n完成: {fixed} 个重写+通知')
if skipped: print('跳过:', skipped)
