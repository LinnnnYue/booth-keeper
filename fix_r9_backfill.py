# 手动补齐脚本 — R9 一键下载 6760332/8622764/8711310 三个商品的实际文件
# 主上任务：从商品页 HTML 找下载链接 → 下载到对应目录
import json, sys, time
from pathlib import Path
sys.path.insert(0, r'D:\Lin_Agent\WB-WorkSpace\BoothKeeper')
import booth_core as bc

cfg = json.loads(Path.home().joinpath('.boothkeeper.json').read_text(encoding='utf-8'))
s = bc.make_session(cfg['cookie'])
if cfg['proxy']:
    s.proxies.update({'http': cfg['proxy_url'], 'https': cfg['proxy_url']})

root = Path(cfg['booth_root'])
target_ids = ['6760332', '8622764', '8711310']

for iid in target_ids:
    print(f'\n=== {iid} ===')
    # 找现有目录
    found = list(root.rglob(f'{iid}_*'))
    if not found:
        print(f'  ❌ 未找到 {iid}_* 目录')
        continue
    dest = found[0]
    print(f'  dest: {dest.parent.name}/{dest.name}')
    # 解析下载链接
    downloads = bc.fetch_item_downloads(iid, s)
    if not downloads:
        print(f'  ❌ 未找到下载链接')
        continue
    for dl in downloads:
        fname = dl.get('name') or f'{iid}_file.zip'
        target = dest / fname
        if target.exists() and target.stat().st_size > 0:
            print(f'  ✓ 已存在 {fname} ({target.stat().st_size} bytes)')
            continue
        print(f'  下载 {fname} ({dl.get("size_text", "")})...')
        # 下载（带 Referer 防盗链）
        referer = f'https://booth.pm/ja/items/{iid}'
        try:
            r = bc.retry_request(
                'GET', dl['url'], s,
                headers={**bc.UA, 'Referer': referer},
                timeout=120, stream=True)
            if not r:
                print(f'  ✕ {fname} 网络失败')
                continue
            if r.status_code != 200:
                print(f'  ✕ {fname} HTTP {r.status_code}')
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, 'wb') as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
            actual = target.stat().st_size
            print(f'  ✓ {fname} ({actual} bytes, {actual / 1024 / 1024:.2f} MB)')
        except Exception as e:
            print(f'  ✕ {fname} {e}')
    # 重做图标（已有 cover.jpg + ico）
    cover = dest / 'cover.jpg'
    if cover.exists():
        try:
            bc.make_folder_icon(cover, dest)
            print(f'  ✓ 图标已重建')
        except Exception as e:
            print(f'  ✕ 图标重建失败: {e}')

print('\n=== 核验 ===')
for iid in target_ids:
    found = list(root.rglob(f'{iid}_*'))
    if found:
        d = found[0]
        files = list(d.iterdir())
        big = [f for f in files if f.is_file() and f.stat().st_size > 10000]
        print(f'  {iid}: {d.parent.name}/{d.name}  共 {len(files)} 项 (含 {len(big)} 个大文件)')
        for f in big:
            print(f'    {f.name}  ({f.stat().st_size / 1024 / 1024:.2f} MB)')