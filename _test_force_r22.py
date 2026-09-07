# _test_force_r22.py — 验证 R22「同位置日期留档」force 重归档逻辑（离线打桩）
import os, sys, shutil, tempfile
from pathlib import Path
sys.path.insert(0, r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper")
import booth_core as bc
import archive_util as au

# ── 打桩：不联网、不生成图像 ──────────────────────────────
_FAKE_ITEM = {
    "id": "1234567", "name": "Test Item", "category_name": "3Dモデル",
    "category_parent_name": None, "images": [],
}
def _fake_fetch(iid, session=None):
    it = dict(_FAKE_ITEM); it["id"] = iid
    return it
def _fake_classify(*a, **k):
    return "3D道具"
def _fake_cover(*a, **k):
    return None
def _fake_icon(*a, **k):
    raise RuntimeError("icon should not run (no cover)")
bc.fetch_item = _fake_fetch
bc.classify = _fake_classify
bc.download_cover = _fake_cover
bc.make_folder_icon = _fake_icon

TMP = Path(tempfile.mkdtemp(prefix="bk_f22_"))
ROOT = TMP / "BOOTH"
ROOT.mkdir()
CAT = ROOT / "3D道具"
CAT.mkdir()
DEST = CAT / "1234567_Test Item"

def build_dest():
    """预置一个旧归档目录（含本体+三件套），模拟『目录已存在』。"""
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "old_body.unitypackage").write_bytes(b"old-pkg")
    (DEST / "cover.jpg").write_bytes(b"jpg")
    (DEST / "desktop.ini").write_text("[.ShellClassInfo]\n", encoding="utf-8")
    (DEST / ".folder_icon.ico").write_bytes(b"ico")
    (DEST / "sub").mkdir()

def cleanup_dest():
    if DEST.exists():
        shutil.rmtree(DEST, ignore_errors=True)

print("== R22 force 留档测试 ==")
ok_cnt = 0

# ── 用例1：dest 已存在旧内容 + force=True + 新源 → 旧内容移入「旧版本_日期」子目录
cleanup_dest(); build_dest()
SRC = TMP / "src_new"; shutil.rmtree(SRC, ignore_errors=True)
SRC.mkdir()
(SRC / "new_body.zip").write_bytes(b"new-pkg")
s = bc.make_session()
r = au.archive_item("1234567", str(ROOT), s, move_source=str(SRC), force=True)
print("  状态:", r["status"], "| msg:", r.get("msg",""))
assert r["status"] == "ok", r
old = r.get("archived_old")
print("  留档子目录:", old)
assert old and "旧版本_" in Path(old).name, "应产生 旧版本_日期 子目录"
assert (Path(old) / "old_body.unitypackage").exists(), "旧本体应留档"
assert (Path(old) / "desktop.ini").exists(), "旧 ini 应留档"
assert not (DEST / "old_body.unitypackage").exists(), "旧本体应移出根"
assert (DEST / "new_body.zip").exists(), "新本体应落 dest 根"
assert not (DEST / "sub").exists(), "旧子目录应随留档移走"
ok_cnt += 1
print("  用例1 OK：旧内容整体留档、新内容落根")

# ── 用例2：dest 已存在 + force + 源已不存在（无 move_source）→ err，旧内容不动
cleanup_dest(); build_dest()
r = au.archive_item("1234567", str(ROOT), s, move_source=str(DEST / "not_exist"), force=True)
print("  状态:", r["status"], "| msg:", r.get("msg",""))
assert r["status"] == "err", r
assert (DEST / "old_body.unitypackage").exists(), "旧内容应原样保留"
assert not any(p.name.startswith("旧版本_") for p in DEST.iterdir()), "无源时不应留档"
ok_cnt += 1
print("  用例2 OK：源缺失 → err 且目录原样")

# ── 用例3：dest 不存在 + force 等同普通归档
cleanup_dest()
SRC2 = TMP / "src2"; shutil.rmtree(SRC2, ignore_errors=True)
SRC2.mkdir(); (SRC2 / "a.zip").write_bytes(b"a")
r = au.archive_item("1234567", str(ROOT), s, move_source=str(SRC2), force=True)
print("  状态:", r["status"])
assert r["status"] == "ok"
assert (DEST / "a.zip").exists()
assert r.get("archived_old") is None
ok_cnt += 1
print("  用例3 OK：dest 不存在 → 正常归档，无留档")

shutil.rmtree(TMP, ignore_errors=True)
print(f"\nALL {ok_cnt} CASES PASSED")
