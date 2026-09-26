# R12 一键合并修复：41 件同 ID 多目录 → 合并到官方类目 + send2trash 旧源
import json, sys
from pathlib import Path
sys.path.insert(0, r'D:\Lin_Agent\WB-WorkSpace\BoothKeeper')
import booth_core as bc
from archive_util import consolidate_id

cfg = json.loads(Path.home().joinpath('.boothkeeper.json').read_text(encoding='utf-8'))
s = bc.make_session(cfg['cookie'])
if cfg['proxy']:
    s.proxies.update({'http': cfg['proxy_url'], 'https': cfg['proxy_url']})

root = Path(cfg['booth_root'])

# 41 件同 ID 多目录——全部自动合并
from collections import defaultdict
id_to_dirs = defaultdict(list)
import re
ID_DIR_RE = re.compile(r'^(\d{7})[\s_\-－　ー]+(.+)$')
for d in root.rglob('*'):
    if d.is_dir():
        m = ID_DIR_RE.match(d.name)
        if m:
            id_to_dirs[m.group(1)].append(d)
dupes = {iid: dirs for iid, dirs in id_to_dirs.items() if len(dirs) > 1}
print(f'=== R12 一键合并：{len(dupes)} 件同 ID 多目录 ===')

ok, fail = 0, 0
for iid, dirs in dupes.items():
    r = consolidate_id(iid, str(root), s)
    if r['status'] == 'ok':
        ok += 1
        size = sum(f.stat().st_size for f in Path(r['dest']).iterdir() if f.is_file())
        print(f'  ✓ {iid} | {r["cat"]} | {r["merged_files"]} 文件合并 | {size/1024:.0f} KB')
    else:
        fail += 1
        print(f'  ✕ {iid} | {r.get("msg","?")}')

print(f'\n=== 总计：成功 {ok} / 失败 {fail} ===')

# 核验：再扫同 ID 多目录
print('\n=== 核验：再次扫描同 ID 多目录 ===')
id_to_dirs2 = defaultdict(list)
for d in root.rglob('*'):
    if d.is_dir():
        m = ID_DIR_RE.match(d.name)
        if m:
            id_to_dirs2[m.group(1)].append(d)
dupes2 = {iid: dirs for iid, dirs in id_to_dirs2.items() if len(dirs) > 1}
if dupes2:
    print(f'  ⚠ 还有 {len(dupes2)} 件多目录：')
    for iid, dirs in list(dupes2.items())[:10]:
        print(f'    {iid}: {[str(d.parent.name) for d in dirs]}')
else:
    print('  ✓ 0 件多目录（全部合并完成）')