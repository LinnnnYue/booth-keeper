# R12 一键修正现场 7 件错位 — 用 archive_item(force=True) 重建到正确类目
# 同时走 send2trash 回收站自动清空原错位目录
import json, sys
from pathlib import Path
sys.path.insert(0, r'D:\Lin_Agent\WB-WorkSpace\BoothKeeper')
import booth_core as bc
from archive_util import archive_item

cfg = json.loads(Path.home().joinpath('.boothkeeper.json').read_text(encoding='utf-8'))
s = bc.make_session(cfg['cookie'])
if cfg['proxy']:
    s.proxies.update({'http': cfg['proxy_url'], 'https': cfg['proxy_url']})

root = Path(cfg['booth_root'])

# 主上现场发现 7 件错位（含部分已对）
target_ids = ['8674016', '4689398', '2219616', '4973351', '7437926', '5056077', '7447820']

print('=== 一键修正 7 件错位（force 重归档 + send2trash 原目录） ===')
for iid in target_ids:
    print(f'\n--- {iid} ---')
    # 1. 找当前目录
    found = list(root.rglob(f'{iid}_*'))
    if not found:
        print(f'  ❌ 未找到 {iid}_* 目录（已修正？）')
        continue
    wrong_path = str(found[0])
    print(f'  当前: {found[0].parent.name}/{found[0].name}')
    # 2. fetch_item 拿官方分类
    item = bc.fetch_item(iid, s)
    if not item:
        print(f'  ❌ fetch_item 失败')
        continue
    cat_name = item.get('category_name', '')
    cat_parent = item.get('category_parent_name', '')
    official_cat = bc.classify(cat_name, cat_parent) or '未分类'
    print(f'  官方: {official_cat} ({cat_name} / {cat_parent})')
    # 3. force=True 重建到正确目录（archive_util 会 send2trash 源空目录）
    r = archive_item(iid, str(root), s, move_source=wrong_path, force=True)
    cat = r.get('cat', '?')
    dest = r.get('dest', '?')
    if r['status'] == 'ok':
        dest_name = Path(dest).name
        print(f'  ✓ 已重归档到 {cat}/{dest_name}')
        # 验证最终位置
        if Path(dest).exists():
            n_files = len(list(Path(dest).iterdir()))
            print(f'  ✓ 现含 {n_files} 项')
    else:
        msg = r.get('msg', r.get('status'))
        print(f'  ✕ 失败: {msg}')

# 核验：再扫一遍错位
print('\n=== 核验：再扫 7 件类目 ===')
for iid in target_ids:
    item = bc.fetch_item(iid, s)
    if not item:
        continue
    cat_name = item.get('category_name', '')
    cat_parent = item.get('category_parent_name', '')
    official_cat = bc.classify(cat_name, cat_parent) or '未分类'
    found = list(root.rglob(f'{iid}_*'))
    if found:
        current = found[0].parent.name
        status = '✓' if current == official_cat else f'✗ 当前 {current}'
        print(f'  {status} {iid}: 当前 {current} | 官方 {official_cat}')
    else:
        print(f'  ⚠ {iid}: 目录不存在')

# 核验：原错位的空目录是否走回收站了
print('\n=== 核验：原错位空目录应走回收站 ===')
expected_gone = [
    '3D发型/8674016_【VRC向けHair】めかくれゔぁんぷへあー/MekakureVampHair',
    '3D模型/4689398_PuppetCat Ears/Tail Set 布偶貓の耳/尾',
    # 等
]
for path_str in expected_gone:
    p = root / path_str
    if p.exists():
        n = len(list(p.iterdir()))
        print(f'  ⚠ {path_str} 还在（{n} 项）')
    else:
        print(f'  ✓ {path_str} 已清空（send2trash 回收站）')