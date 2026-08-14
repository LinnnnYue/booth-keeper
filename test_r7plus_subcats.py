import sys, os
sys.path.insert(0, '.')
from pathlib import Path
import booth_core as bc

root = Path('G:/Lin_File/BOOTH')
existing = set()
for d in root.iterdir():
    if d.is_dir():
        existing.add(d.name)

# 综合核查（主上关心的所有子分类）
sub_cats = [
    ('ヘアー', '3Dモデル', 'Hair 3D 模型子项', '3D发型'),
    ('衣装', '3Dモデル', '服装 3D 模型子项', '3D服饰'),
    ('衣装', 'アバター', '服装 头像子项', '3D服饰'),
    ('モーション', '3Dモデル', '动作 3D 模型子项', '3D动作'),
    ('テクスチャ', '3Dモデル', '贴图 3D 模型子项', '3D贴图'),
    ('ツール', '3Dモデル', '工具 3D 模型子项', '3D工具'),
    ('シェーダー', '3Dモデル', '着色器 3D 模型子项', '3D着色器'),
    ('エフェクト', '3Dモデル', '特效 3D 模型子项', '3D特效'),
    ('ギミック', '3Dモデル', '机关 3D 模型子项', '3D机关'),
    ('リギング', '3Dモデル', '绑定 3D 模型子项', '3D绑定'),
    ('物理', '3Dモデル', '物理 3D 模型子项', '3D物理'),
    ('VR', '3Dモデル', 'VR 3D 模型子项', '3DVR'),
    ('3Dモーション', '', '3D 动作（顶级，笔误修复）', '3D动作'),
    ('3Dシェーダー・マテリアル', '', '3D 着色器（顶级，走主上有目录）', '着色器'),
    ('アバター', '', '头像（顶级，去重修复）', '头像'),
    ('アバターアイテム', 'アバター', '头像物品 头像子项', '3D头像物品'),
    ('アバターギミック', 'アバター', '头像机关 头像子项', '3D头像机关'),
    ('アクセサリ', '', '饰品（半角）', '饰品'),
    ('アクセサリー', '', '饰品（全角，主上有「配饰」）', '配饰'),
    ('衣装', '', '服饰（顶级，无父类）', '服饰'),
    ('モーション', '', '动作（顶级，无父类）', '动作'),
]
pass_n = fail_n = 0
for cat_name, cat_parent, desc, expected in sub_cats:
    result = bc.classify(cat_name, cat_parent)
    ok = result == expected
    status = 'PASS' if ok else 'FAIL'
    print(f'  [{status}] classify({cat_name!r}, {cat_parent!r}) -> {result!r} (期望 {expected!r})  # {desc}')
    if ok: pass_n += 1
    else: fail_n += 1
print(f'\n汇总: {pass_n} PASS / {fail_n} FAIL')

# 重跑主上 7032906 真实场景
raw = {
    'id': 7032906,
    'name': '【10アバター対応】 𝐏♡𝐏.𝐇𝐚𝐢𝐫 𝟏𝟒',
    'category': {'name': 'ヘアー', 'parent': {'name': '3Dモデル'}},
}
norm = bc._normalize_item(raw)
cat = bc.classify(norm['category_name'], norm['category_parent_name'])
print(f'\n7032906 验证: -> {cat}  (期望 3D发型)  {"PASS" if cat == "3D发型" else "FAIL"}')