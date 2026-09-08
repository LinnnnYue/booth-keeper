# -*- coding: utf-8 -*-
"""全库图标指纹审计：黄目录 vs 正常目录 逐维度对照，揪出判别特征。"""
import ctypes, io, sys
from pathlib import Path
from PIL import Image

k = ctypes.windll.kernel32
GA = k.GetFileAttributesW
ATTRS = lambda v: ''.join(n for n, b in [('R',1),('H',2),('S',4),('A',0x20),
                                          ('NI',0x2000),('Off',0x1000)] if v & b) or '-'

YELLOW_IDS = {'7042776','8383304','6949296','6220132','7389778','6200953','5674632',
              '7021465','6033509','6567440','7172562','7148608','6818558','5613949',
              '5760880','6834469','6515860','6499853','6114837','5988032','5739125',
              '5722778','7763987','8417939','8589747','8749497'}

ROOT = Path(r'G:\Lin_File\BOOTH\3D服饰')

def has_supplementary(name):
    # 名字含增补平面字符（emoji 等，UTF-16 需代理对）→ Windows API 走 W 通路时的潜在差异
    return any(ord(c) > 0xFFFF for c in name)

def ini_fingerprint(p):
    raw = p.read_bytes()
    head = raw[:4].hex()
    bom = 'UTF16LE' if raw[:2] == b'\xff\xfe' else ('UTF8BOM' if raw[:3] == b'\xef\xbb\xbf'
          else ('UTF16BE' if raw[:2] == b'\xfe\xff' else 'plain'))
    # 统一解码
    try:
        if bom == 'UTF16LE': txt = raw.decode('utf-16-le')
        elif bom == 'UTF16BE': txt = raw.decode('utf-16-be')
        else: txt = raw.decode('utf-8')
    except Exception:
        txt = raw.decode('utf-8', errors='replace')
    lines = txt.strip().splitlines()
    icon_line = next((l for l in lines if 'IconResource' in l), '')
    return dict(bom=bom, head=head, nln=len(lines),
                icon_line=icon_line,
                nlines_raw=len(raw.split(b'\n')))

def ico_fingerprint(p):
    raw = p.read_bytes()
    size = len(raw)
    has_png = b'\x89PNG' in raw
    frames = []
    try:
        im = Image.open(p)
        n = getattr(im, 'n_frames', 1)
        for i in range(n):
            im.seek(i)
            frames.append(f"{im.size[0]}x{im.size[1]}/{im.mode}")
        ok = True
    except Exception as e:
        ok = False
        frames = [f"ERR {type(e).__name__}"]
    return dict(size=size, has_png=has_png, ok=ok, frames=frames)

rows = []
for d in sorted(ROOT.iterdir()):
    if not d.is_dir(): continue
    ini = d/'desktop.ini'; ico = d/'.folder_icon.ico'; cover = d/'cover.jpg'
    if not (ini.exists() and ico.exists()): continue
    fid = d.name.split('_')[0] if '_' in d.name else d.name
    name = d.name
    a_dir = GA(str(d)); a_ini = GA(str(ini)); a_ico = GA(str(ico))
    ini_f = ini_fingerprint(ini)
    ico_f = ico_fingerprint(ico)
    cover_ok = cover.exists()
    cover_size = cover.stat().st_size if cover_ok else 0
    rows.append(dict(
        fid=fid, name=name, yellow=fid in YELLOW_IDS,
        dir_attr=ATTRS(a_dir), ini_attr=ATTRS(a_ini), ico_attr=ATTRS(a_ico),
        bom=ini_f['bom'], ini_head=ini_f['head'],
        icon_line=ini_f['icon_line'],
        ico_size=ico_f['size'], ico_png=ico_f['has_png'], ico_ok=ico_f['ok'],
        ico_frames=ico_f['frames'],
        cover=cover_ok, cover_size=cover_size,
        emoji=has_supplementary(name),
    ))

Y = [r for r in rows if r['yellow']]
N = [r for r in rows if not r['yellow']]
print(f"3D服饰 共 {len(rows)} 个三件套目录 | 黄名单 {len(Y)} | 对照 {len(N)}\n")

def tab(field, fn=lambda v: v):
    from collections import Counter
    cy, cn = Counter(fn(r[field]) for r in Y), Counter(fn(r[field]) for r in N)
    print(f"── {field} ──")
    for val in sorted(set(cy) | set(cn), key=str):
        print(f"   {str(val)[:70]:<72} 黄:{cy.get(val,0):<4} 正常:{cn.get(val,0)}")
    print()

tab('dir_attr'); tab('ini_attr'); tab('ico_attr')
tab('bom'); tab('ini_head')
tab('ico_png'); tab('ico_ok')
tab('cover')
tab('emoji')
tab('ico_size', lambda s: '<1KB' if s < 1024 else ('1-5KB' if s < 5120 else ('5-20KB' if s < 20480 else '>20KB')))
tab('cover_size', lambda s: '0' if s == 0 else ('<50KB' if s < 51200 else ('50-200KB' if s < 204800 else '>200KB')))

print("── IconResource 行分布(前8种) ──")
from collections import Counter
c = Counter(r['icon_line'] for r in rows)
for line, n in c.most_common(8):
    tag = '黄' if any(r['yellow'] and r['icon_line']==line for r in rows) else '仅正常'
    print(f"   [{n:>3}] {tag:<6} {line!r}")

print("\n── 黄目录明细 ──")
for r in Y:
    print(f"  {'Y' if r['yellow'] else 'N'} {r['fid']} emoji={int(r['emoji'])} "
          f"dir[{r['dir_attr']}] ini[{r['ini_attr']}/{r['bom']}] ico[{r['ico_attr']}] "
          f"icof={r['ico_frames']} icon_line={r['icon_line']!r}")

print("\n── 对照样本(正常目录取 5) ──")
for r in N[:5]:
    print(f"  N {r['fid']} emoji={int(r['emoji'])} "
          f"dir[{r['dir_attr']}] ini[{r['ini_attr']}/{r['bom']}] ico[{r['ico_attr']}] "
          f"icof={r['ico_frames']} icon_line={r['icon_line']!r}")
