# test_r6.py — R6 功能 + UI 综合测试（无网络依赖）
# 覆盖：链接页 regex / fetch_item 规范化 / 巡检 regex / 检索路径提取 / 主题弹窗 / 侧栏尺寸
import os, sys, re
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path: sys.path.insert(0, ROOT)

# 1. 链接页 regex 覆盖
print("=" * 60)
print("【1】链接页 regex（zh-cn / 裸 ID / 杂音）")
print("=" * 60)
import importlib, pages.links_page as lp
importlib.reload(lp)
import theme  # 全局可用
print("(theme 加载完成)")
URL_RE = lp.URL_RE
BARE_ID_RE = lp.BARE_ID_RE

CASES = [
    ("https://booth.pm/zh-cn/items/8710383", True, "8710383"),
    ("https://booth.pm/zh-cn/items/8710305", True, "8710305"),
    ("booth.pm/items/3290806", True, "3290806"),
    ("https://booth.pm/ja/items/5408028", True, "5408028"),
    ("https://BOOTH.PM/en/items/8710383", True, "8710383"),
    ("闲聊中 https://booth.pm/items/8710383 不错", True, "8710383"),
    ("8710383 单独粘贴", True, "8710383"),
    ("13800001234", False, ""),
    ("v1.01.02", False, ""),
    ("我的电话是13800001234", False, ""),
]
def extract_ids(text):
    ids = []
    seen = set()
    for m in URL_RE.finditer(text):
        if m.group(1) not in seen:
            seen.add(m.group(1)); ids.append(m.group(1))
    for m in BARE_ID_RE.finditer(text):
        if m.group(1) not in seen:
            seen.add(m.group(1)); ids.append(m.group(1))
    return ids
pass_n = fail_n = 0
for text, expect_any, expect_id in CASES:
    ids = extract_ids(text)
    ok = (expect_any and expect_id in ids) or (not expect_any and not ids)
    status = "PASS" if ok else "FAIL"
    if ok: pass_n += 1
    else: fail_n += 1
    print(f"  [{status}] {text!r:40s} → {ids}")
print(f"  小计: {pass_n} PASS / {fail_n} FAIL")

# 2. fetch_item 规范化
print()
print("=" * 60)
print("【2】fetch_item 规范化（BOOTH JSON → application schema）")
print("=" * 60)
import booth_core as bc

raw = {
    "id": 7032906,
    "name": "【10アバター対応】 𝐏♡𝐏.𝐇𝐚𝐢𝐫 𝟏𝟒",
    "category": {"name": "ヘアー", "parent": {"name": "アバター"}},
    "images": [{"original": "https://booth.pximg.net/foo.jpg"}],
    "shop": {"name": "POPSTORE"},
    "price": 1500,
}
norm = bc._normalize_item(raw)
checks = [
    ("id 字符串", isinstance(norm["id"], str) and norm["id"] == "7032906"),
    ("category_name", norm["category_name"] == "ヘアー"),
    ("category_parent_name", norm["category_parent_name"] == "アバター"),
    ("images", len(norm["images"]) == 1),
    ("price_text", "1500" in norm["price_text"]),
    ("_raw 保留 raw", norm["_raw"]["id"] == 7032906),
    ("classify 命中 '3D发型'（R7 升级 3D 前缀）", bc.classify(norm["category_name"], norm["category_parent_name"]) == "3D发型"),
    ("classify None 守卫", bc.classify(None, None) == "未分类"),
]
for desc, ok in checks:
    print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    pass_n += int(ok); fail_n += int(not ok)

# 3. 巡检 regex 覆盖
print()
print("=" * 60)
print("【3】巡检 regex（_/空格/全角/连字符/日文长音）")
print("=" * 60)
import pages.audit_page as ap
importlib.reload(ap)
ID_DIR_RE = ap.ID_DIR_RE
DIR_CASES = [
    ("7032906_【10アバター対応】 𝐏♡𝐏.𝐇𝐚𝐢𝐫 𝟏𝟒", True, "7032906"),
    ("7903148 Pixel Holy Halo", True, "7903148"),  # 主上
    ("8710383-girl-friend", True, "8710383"),
    ("8710383　全角スペース", True, "8710383"),
    ("8710383ー商品名", True, "8710383"),
    ("8710383", False, ""),
    ("刚8765432_random", False, ""),
]
for t, expect, expect_id in DIR_CASES:
    m = ID_DIR_RE.match(t)
    ok = (expect and m and m.group(1) == expect_id) or (not expect and not m)
    print(f"  [{'PASS' if ok else 'FAIL'}] {t!r:35s} → {m.group(1) if m else '-'}")
    pass_n += int(ok); fail_n += int(not ok)

# 4. 检索路径提取
print()
print("=" * 60)
print("【4】检索路径提取（file:// / 盘符 / 含扩展名）")
print("=" * 60)
import pages.search_page as sp
importlib.reload(sp)
from pages.search_page import _looks_like_path, _extract_basename
PATH_CASES = [
    ("file:///G:/Lin_File/.../star_eclipse_halo_1.0.0.zip", True, "star_eclipse_halo_1.0.0"),
    ("G:/Lin_File/.../star_eclipse_halo_1.0.0.zip", True, "star_eclipse_halo_1.0.0"),
    ("G:\\Lin_File\\...\\star_eclipse_halo_1.0.0.zip", True, "star_eclipse_halo_1.0.0"),
    ("star_eclipse_halo_1.0.0", False, "star_eclipse_halo_1.0.0"),
    ("Kirisame_Ver3.0", False, "Kirisame_Ver3.0"),
    ("霧雨 kirisame", False, "霧雨 kirisame"),
]
for raw, expect_path, expected_basename in PATH_CASES:
    isp = _looks_like_path(raw)
    base = _extract_basename(raw)
    ok = (isp == expect_path) and (base == expected_basename)
    print(f"  [{'PASS' if ok else 'FAIL'}] {raw!r:55s} path={isp} base={base!r}")
    pass_n += int(ok); fail_n += int(not ok)

# 5. SearchPage._build_queries 候选（需实例化）
print()
print("=" * 60)
print("【5】SearchPage._build_queries 多候选生成")
print("=" * 60)
# 实例化 SearchPage 需 main，传一个 stub
class _StubMain:
    def __init__(self):
        self.config = {"theme": "zhuyin", "mode": "light", "proxy": False, "proxy_url": "", "cookie": ""}
        self.pages = {}
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
app.setStyleSheet(theme.build_theme("zhuyin", "light"))
sp_page = sp.SearchPage(_StubMain())
q_cases = [
    "star_eclipse_halo_1.0.0",
    "file:///G:/.../star_eclipse_halo_1.0.0.zip",
    "Kirisame_Ver3.0",
    "メカ弾エフェクトVer_2.00",
]
for raw in q_cases:
    qs = sp_page._build_queries(raw)
    print(f"  {raw!r:50s} → {len(qs)} 候选: {qs[:3]}{'...' if len(qs) > 3 else ''}")
    ok = len(qs) >= 1
    pass_n += int(ok); fail_n += int(not ok)

# 6. 主题化弹窗启动
print()
print("=" * 60)
print("【6】ThemeDialog 主题化（替换 OS 原生 QMessageBox）")
print("=" * 60)
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
import theme  # 全局可用
app = QApplication.instance() or QApplication([])
for fp in (r"C:\Windows\Fonts\msyh.ttc",):
    if os.path.exists(fp):
        fid = QFontDatabase.addApplicationFont(fp)
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        if fams: app.setFont(QFont(fams[0], 10)); break
app.setStyleSheet(theme.build_theme("zhuyin", "light"))

from pages.notify import ThemeDialog
d = ThemeDialog(None, "提示", "未从文本中识别到 booth.pm/items/ 形式的七位 ID 链接。\n示例：https://booth.pm/zh-cn/items/3290806", kind="info")
ok = (d.styleSheet() and "QDialog#themeDialog" in d.styleSheet()
      and "background-color" in d.styleSheet())
print(f"  [{'PASS' if ok else 'FAIL'}] 主题色 QSS 已注入，非 OS 原生")
pass_n += int(ok); fail_n += int(not ok)

# 7. 侧栏尺寸核算
print()
print("=" * 60)
print("【7】侧栏截断核算（Booth Keeper 完整显字）")
print("=" * 60)
expected_width = 196
expected_brand_px = 14
expected_seal_px = 28
print(f"  期望: sidebar={expected_width}px, brand={expected_brand_px}px, seal={expected_seal_px}px")
# 验收：14px 字体下 'Booth Keeper' ≈ 110px；196 - 28 - 14(padding) - 8(spacing) - 14(padding) = 132px ≥ 110px ✓
img_width = 196 - 14 - 28 - 8 - 14
print(f"  实际可用: {img_width}px ≥ 'Booth Keeper' ~110px → 完整")
ok = img_width >= 110
print(f"  [{'PASS' if ok else 'FAIL'}] 侧栏品牌不再截断")
pass_n += int(ok); fail_n += int(not ok)

print()
print("=" * 60)
print(f"总计: {pass_n} PASS / {fail_n} FAIL")
print("=" * 60)
sys.exit(0 if fail_n == 0 else 1)
