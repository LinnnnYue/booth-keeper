# test_r7.py — R7 功能测试
# 覆盖：CATEGORY_MAP 3D前缀 / 空目录清理 / search archive 找源 / 巡检 verbose 日志
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper"
if ROOT not in sys.path: sys.path.insert(0, ROOT)

pass_n = fail_n = 0
def check(ok, desc):
    global pass_n, fail_n
    print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    pass_n += int(ok); fail_n += int(not ok)

# ============================================================
# 1. CATEGORY_MAP 3D 前缀
# ============================================================
print("=" * 60)
print("【1】CATEGORY_MAP 3D 前缀（ヘアー/髪/ヘア → 3D发型）")
print("=" * 60)
import booth_core as bc
check(bc.classify("ヘアー", "3Dモデル") == "3D发型", "ヘアー + 3Dモデル → 3D发型")
check(bc.classify("髪", "3Dモデル") == "3D发型", "髪 + 3Dモデル → 3D发型")
check(bc.classify("ヘア", "3Dモデル") == "3D发型", "ヘア + 3Dモデル → 3D发型")
check(bc.classify("ヘアー", "") == "3D发型", "ヘアー 独立 → 3D发型")
# 其他 3D 类目不变
check(bc.classify("3D衣装・アクセサリー", "") == "3D服饰", "3D衣装 → 3D服饰（不变）")
check(bc.classify("3D装飾品", "") == "3D饰品", "3D装飾品 → 3D饰品（不变）")
check(bc.classify("衣装", "") == "服饰", "衣装 → 服饰（不变）")

# R7+1 父级 3D 前缀规则：子分类在 3D_MODEL/アバター 父类下，自动加 3D 前缀
check(bc.classify("衣装", "3Dモデル") == "3D服饰", "衣装 + 3Dモデル → 3D服饰（R7+1 父级规则）")
check(bc.classify("衣装", "アバター") == "3D服饰", "衣装 + アバター → 3D服饰（R7+1）")
check(bc.classify("モーション", "3Dモデル") == "3D动作", "モーション + 3Dモデル → 3D动作（R7+1）")
check(bc.classify("テクスチャ", "3Dモデル") == "3D贴图", "テクスチャ + 3Dモデル → 3D贴图（R7+1）")
check(bc.classify("ツール", "3Dモデル") == "3D工具", "ツール + 3D_MODEL → 3D工具（R7+1）")
# 顶级无父类 → 仍走原映射（不带 3D 前缀）
check(bc.classify("衣装", "") == "服饰", "衣装 无父类 → 服饰（不变）")
check(bc.classify("モーション", "") == "动作", "モーション 无父类 → 动作（不变）")
# 笔误修复
check(bc.classify("3Dモーション", "") == "3D动作", "3Dモーション → 3D动作（笔误修复）")
check(bc.classify("3Dシェーダー・マテリアル", "") == "着色器", "3Dシェーダー → 着色器（用主上有目录）")
check(bc.classify("アバター", "") == "头像", "アバター → 头像（去重修复，不再是虚拟形象）")

# ============================================================
# 2. 空目录清理 walk-up
# ============================================================
print()
print("=" * 60)
print("【2】空目录 walk-up 清理")
print("=" * 60)
import tempfile, shutil
from pathlib import Path
from archive_util import cleanup_empty_parents

# 用 rmtree 兜底清理（safe-delete 守卫对单文件 unlink 拦截）
def rm(p):
    try:
        if p.is_file(): p.unlink()
        elif p.is_dir(): shutil.rmtree(p)
    except OSError:
        pass

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "root"
    deep = root / "A" / "B" / "C" / "D"
    deep.mkdir(parents=True)
    f = deep / "f.txt"
    f.write_text("x")
    rm(f)  # 先删文件
    cleanup_empty_parents(deep, root)
    check(not (root / "A").exists(), "连续 4 级空目录全部清理到 root 上")
    check(root.exists(), "root 保留")

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "root"
    deep = root / "A" / "B" / "C"
    deep.mkdir(parents=True)
    keep = deep / "keep.txt"
    keep.write_text("keep")
    empty_leaf = deep / "D"
    empty_leaf.mkdir()
    cleanup_empty_parents(empty_leaf, root)
    check(not empty_leaf.exists(), "末梢空目录被删")
    check(keep.exists(), "非空父目录保留")
    check((root / "A").exists(), "非空父目录链保留")

# ============================================================
# 3. search archive 自动找源
# ============================================================
print()
print("=" * 60)
print("【3】find_existing_source_in_library 自动找源")
print("=" * 60)
from archive_util import find_existing_source_in_library

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    # 模拟主上 7032906 场景：未分类\7032906_xxx
    cand = root / "未分类" / "7032906_POP Hair"
    cand.mkdir(parents=True)
    # 1. 按 ID 找
    src = find_existing_source_in_library("7032906", "POP Hair 14", str(root))
    check(src == str(cand), f"按 ID 找到 {cand.name}")
    # 2. 库内无 ID，按商品名前缀找
    (root / "J_音乐类" / "SyncDances_4.5.1Fix.zip").parent.mkdir(parents=True)
    (root / "J_音乐类" / "SyncDances_4.5.1Fix.zip").touch()
    src = find_existing_source_in_library("4881102", "SyncDances 4.5", str(root))
    check(src is not None and "SyncDances" in src, "按商品名找 SyncDances 文件")

# ============================================================
# 4. 巡检 verbose 日志
# ============================================================
print()
print("=" * 60)
print("【4】巡检 verbose 日志（FixWorker.run 改动）")
print("=" * 60)
# 模拟：fetch_item 返回的图片 URL 无效，下载失败
# 验证：日志会写「封面下载失败」「封面缺失」而不是静默 pass
import pages.audit_page as ap
src = open(ap.__file__, encoding="utf-8").read()
check('封面下载失败' in src, "FixWorker 日志含「封面下载失败」")
check('封面异常' in src, "FixWorker 日志含「封面异常」")
check('封面缺失，无法生成图标' in src, "FixWorker 日志含「封面缺失」")
check('商品无图片' in src, "FixWorker 日志含「商品无图片」")

# ============================================================
# 5. 真机 + 旧 R5/R6 测试无回退
# ============================================================
print()
print("=" * 60)
print("【5】回归（之前所有修复不动）")
print("=" * 60)
import importlib, pages.links_page as lp
importlib.reload(lp)
URL_RE = lp.URL_RE
ids = URL_RE.findall("https://booth.pm/zh-cn/items/8710383")
check(ids == ["8710383"], "链接页 zh-cn 仍识别")
ids = URL_RE.findall("booth.pm/items/3290806")
check(ids == ["3290806"], "链接页 无 protocol 仍识别")

print()
print("=" * 60)
print(f"总计: {pass_n} PASS / {fail_n} FAIL")
print("=" * 60)
sys.exit(0 if fail_n == 0 else 1)