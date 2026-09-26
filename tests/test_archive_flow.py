#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_archive_flow.py — 归档主流程回归基线

对应 docs/boothkeeper/v1/02-遗留项处置.md 的验收口径：2.2-5 / 2.3-5 / 2.4-4
均要求「归档主流程行为零回归」。本文件把该主流程固化为可重跑的断言，
供 refactor（2.3 QThread 提取、2.4 booth_core 拆分）前后逐项比对。

覆盖六条路径：
  1. 首次归档          → ok
  2. 重复归档          → exists
  3. 同 ID 错位        → mismatch
  4. force 重归档      → ok + 旧版本_<时间戳>/ 留档
  5. 已下架商品        → delisted
  6. 连不上 BOOTH      → err（R17 安全分支：不妄断下架、不搬源文件）

全部在 tempfile 临时目录内构造，绝不触碰 BOOTH 资产库（BOUNDARY B-1）。
网络与图标生成一律 mock，本用例只考归档的目录决策与文件搬运。

运行： python tests/test_archive_flow.py [-v]
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import archive_util as au  # noqa: E402

IID = "1234567"
NAME = "测试商品"
CAT = "3D模型"          # 3Dモデル → CATEGORY_MAP → 3D模型
WRONG_CAT = "3D发型"    # 3Dヘアー → 3D发型

ITEM = {
    "name": NAME,
    "category_name": "3Dモデル",
    "category_parent_name": "",
    "images": [],
}


class ArchiveFlow(unittest.TestCase):
    """归档主流程的五条路径。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bk_flow_"))
        self.root = self.tmp / "库"
        self.root.mkdir(parents=True)
        self.src = self.tmp / "新下载"
        self.src.mkdir()
        (self.src / "body.zip").write_bytes(b"NEW")

        self.item = dict(ITEM)
        for target, kwargs in (
            ("fetch_item", {"side_effect": lambda *a, **k: dict(self.item)}),
            ("download_cover", {"return_value": None}),
            ("make_folder_icon", {"return_value": None}),
        ):
            p = mock.patch.object(au.bc, target, **kwargs)
            p.start()
            self.addCleanup(p.stop)
        for fn in ("_remove_to_trash", "cleanup_empty_parents"):
            p = mock.patch.object(au, fn, lambda *a, **k: None)
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def dest(self, cat=CAT):
        return self.root / cat / f"{IID}_{NAME}"

    def legacy_dirs(self, cat=CAT):
        d = self.dest(cat)
        if not d.exists():
            return []
        return sorted(p.name for p in d.iterdir()
                      if p.is_dir() and p.name.startswith("旧版本_"))

    def roots(self, cat=CAT):
        d = self.dest(cat)
        if not d.exists():
            return []
        return sorted(p.name for p in d.iterdir())

    # ---------------- 1. 首次归档 ----------------
    def test_01_first_archive_ok(self):
        res = au.archive_item(IID, self.root, session=None, move_source=str(self.src))
        self.assertEqual(res["status"], "ok", res)
        self.assertEqual(res.get("cat"), CAT, res)
        self.assertIn("body.zip", self.roots())
        self.assertEqual(self.legacy_dirs(), [])

    # ---------------- 2. 重复归档 ----------------
    def test_02_duplicate_reports_exists(self):
        au.archive_item(IID, self.root, session=None, move_source=str(self.src))
        res = au.archive_item(IID, self.root, session=None, move_source=str(self.src))
        self.assertEqual(res["status"], "exists", res)
        self.assertEqual(self.legacy_dirs(), [])

    # ---------------- 3. 同 ID 错位 ----------------
    def test_03_misplaced_reports_mismatch(self):
        # 手工把商品放在错类目下
        wrong = self.root / WRONG_CAT / f"{IID}_{NAME}"
        wrong.mkdir(parents=True)
        (wrong / "stale.bin").write_bytes(b"OLD")

        res = au.archive_item(IID, self.root, session=None, move_source=str(self.src))
        self.assertEqual(res["status"], "mismatch", res)
        self.assertEqual(res.get("cat"), CAT, f"官方类目应为 {CAT}: {res}")
        self.assertEqual(res.get("wrong_cat"), WRONG_CAT, res)

    # ---------------- 4. force 重归档（留档） ----------------
    def test_04_force_archives_old_version(self):
        au.archive_item(IID, self.root, session=None, move_source=str(self.src))
        # 再造一份新内容，模拟二次下载
        src2 = self.tmp / "新下载2"
        src2.mkdir()
        (src2 / "body2.zip").write_bytes(b"NEW2")

        res = au.archive_item(IID, self.root, session=None,
                              move_source=str(src2), force=True)
        self.assertEqual(res["status"], "ok", res)
        self.assertTrue(res.get("archived_old"), f"应报告已留档: {res}")
        self.assertEqual(len(self.legacy_dirs()), 1, self.roots())

        # 旧内容必须完整躺在留档目录里，新内容落在根
        legacy = self.dest() / self.legacy_dirs()[0]
        names = sorted(p.name for p in legacy.iterdir())
        self.assertIn("body.zip", names, names)
        self.assertIn("body2.zip", self.roots())
        # 不套娃：留档目录内不得再出现 旧版本_*
        self.assertEqual(
            [p.name for p in legacy.iterdir() if p.name.startswith("旧版本_")], [])

    # ---------------- 5. 已下架商品 ----------------
    def test_05_delisted_goes_to_delisted_bucket(self):
        # fetch 返 None + 连通探针通过 → 判下架。
        # 注意：必须 patch `au.bc.classify_item_state`（archive_util 内的调用是
        # `bc.classify_item_state`），否则会真的发网络请求、结果随 BOOTH 侧状态漂移。
        with mock.patch.object(au.bc, "fetch_item", return_value=None), \
             mock.patch.object(au.bc, "classify_item_state",
                               return_value=("delisted", "HTTP 404")):
            res = au.archive_item(IID, self.root, session=None,
                                  move_source=str(self.src))
        self.assertEqual(res["status"], "delisted", res)
        self.assertTrue((self.root / "已下架商品").exists(),
                        f"应落入 已下架商品/：{[p.name for p in self.root.iterdir()]}")

    # ---------------- 6. fetch 失败但连不上 → 不妄断下架（R17 安全分支） ----------------
    def test_06_unreachable_does_not_guess_delisted(self):
        with mock.patch.object(au.bc, "fetch_item", return_value=None), \
             mock.patch.object(au.bc, "classify_item_state",
                               return_value=("unknown", "timeout")):
            res = au.archive_item(IID, self.root, session=None,
                                  move_source=str(self.src))
        self.assertEqual(res["status"], "err", res)
        self.assertFalse((self.root / "已下架商品").exists(),
                         "连不上时不得擅自归入已下架商品")
        self.assertTrue(self.src.exists(), "判定失败时不得搬走源文件")


if __name__ == "__main__":
    unittest.main(verbosity=2)
