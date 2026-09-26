#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_rollback.py — force 重归档回滚路径的演练用例

对应 docs/boothkeeper/v1/02-遗留项处置.md §2.2。

四个演练场景（磁盘满 / 文件被占用 / 进程被杀 / 半还原中间态）全部在
tempfile 临时目录内构造，绝不触碰 BOOTH 资产库（BOUNDARY B-1）。

核心断言不是「没崩」，而是 **返回消息声称的状态 == 磁盘真实状态** ——
这正是 R17 判定三处静默点为高危的原因：它会给出一句与事实不符的成功承诺。

运行： python tests/test_rollback.py [-v]
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
CAT = "3D模型"
LEGACY = "旧版本_"

FAKE_ITEM = {
    "name": NAME,
    "category_name": "3Dモデル",   # CATEGORY_MAP → "3D模型"
    "category_parent_name": "",
    "images": [],
}


class RollbackDrill(unittest.TestCase):
    """force 重归档的失败演练。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bk_rollback_"))
        self.root = self.tmp / "库"
        self.dest = self.root / CAT / f"{IID}_{NAME}"
        self.dest.mkdir(parents=True)
        # 上一次归档遗留的旧内容
        (self.dest / "旧A.bin").write_bytes(b"OLD-A")
        (self.dest / "旧B.bin").write_bytes(b"OLD-B")
        # 本次待归档的新内容
        self.src = self.tmp / "新下载"
        self.src.mkdir()
        (self.src / "新A.bin").write_bytes(b"NEW-A")

        # 隔离网络与图标生成：本用例只考文件移动与回滚
        for target, kwargs in (
            ("fetch_item", {"return_value": dict(FAKE_ITEM)}),
            ("download_cover", {"return_value": None}),
            ("make_folder_icon", {"return_value": None}),
        ):
            p = mock.patch.object(au.bc, target, **kwargs)
            p.start()
            self.addCleanup(p.stop)
        # 不污染回收站、不动库根
        for fn in ("_remove_to_trash", "cleanup_empty_parents"):
            p = mock.patch.object(au, fn, lambda *a, **k: None)
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- 观测工具 ----
    def tree(self):
        """dest 下的相对路径集合（磁盘真实状态）。"""
        return sorted(str(p.relative_to(self.dest)).replace("\\", "/")
                      for p in self.dest.rglob("*"))

    def at_root(self):
        """dest 根目录下的文件名（不含子目录内）。"""
        return sorted(p.name for p in self.dest.iterdir() if p.is_file())

    def legacy_dirs(self):
        return sorted(p.name for p in self.dest.iterdir()
                      if p.is_dir() and p.name.startswith(LEGACY))

    def controlled_move(self, fail_on=(), exc=None):
        """构造可控的 shutil.move：第 fail_on 个（1-based）调用抛异常。

        返回 (fake_move, state)。state["n"] 记录总调用数，便于诊断调用序列。
        """
        real = shutil.move
        err = exc if exc is not None else OSError(28, "No space left on device")
        fail_on = set(fail_on)
        state = {"n": 0, "failed_at": []}

        def fake(src, dst, *a, **k):
            state["n"] += 1
            if state["n"] in fail_on:
                state["failed_at"].append(state["n"])
                raise err
            return real(src, dst)
        return fake, state

    def run_force(self, fake):
        with mock.patch.object(au.shutil, "move", fake):
            return au.archive_item(IID, self.root, None,
                                   move_source=str(self.src), force=True)

    def report(self, tag, res, state):
        print(f"\n  [{tag}] 返回 status={res.get('status')}")
        print(f"  [{tag}] 返回 msg   ={res.get('msg')}")
        print(f"  [{tag}] dest 根    ={self.at_root()}")
        print(f"  [{tag}] 留档目录   ={self.legacy_dirs()}")
        print(f"  [{tag}] move 调用  ={state['n']} 次（失败于 {state['failed_at']}）")

    # ---- 演练一：磁盘满 ----
    def test_01_disk_full_when_moving_new_content(self):
        """磁盘满：新内容移入 dest 失败 → 旧内容必须回到 dest 根，消息须如实。

        调用序列：留档移走 旧A/旧B（第 1、2 次）→ 新内容移入（第 3 次，失败）
                → 还原 旧A/旧B（第 4、5 次）
        """
        fake, state = self.controlled_move(fail_on={3})
        res = self.run_force(fake)
        self.report("磁盘满", res, state)

        self.assertEqual(res["status"], "err")
        self.assertIn("移动失败", res["msg"])
        # 核心断言：消息声称的状态 == 磁盘真实状态
        root = self.at_root()
        self.assertIn("旧A.bin", root, "旧内容未还原到 dest 根")
        self.assertIn("旧B.bin", root, "旧内容未还原到 dest 根")
        self.assertEqual(self.legacy_dirs(), [], "留档空壳未移除")

    # ---- 演练二：文件被占用 ----
    def test_02_file_locked_when_moving_new_content(self):
        """文件被占用（Windows 下表现为 PermissionError）→ 同磁盘满，须还原。"""
        fake, state = self.controlled_move(
            fail_on={3}, exc=PermissionError(13, "另一个程序正在使用此文件"))
        res = self.run_force(fake)
        self.report("被占用", res, state)

        self.assertEqual(res["status"], "err")
        root = self.at_root()
        self.assertIn("旧A.bin", root)
        self.assertIn("旧B.bin", root)

    # ---- 演练三：半还原中间态 ----
    def test_03_partial_restore_reported_honestly(self):
        """回滚本身在还原第 2 项时失败 → 消息必须报「未还原」，不得声称已还原。

        调用序列：留档 1、2 → 新内容移入 3（失败）→ 还原 4（成功）、5（失败）
        """
        fake, state = self.controlled_move(fail_on={3, 5})
        res = self.run_force(fake)
        self.report("半还原", res, state)

        self.assertEqual(res["status"], "err")
        survived = self.at_root()
        in_archive = [p for p in self.tree() if p.startswith(LEGACY)]
        print(f"  [半还原] dest 根残留 {survived}；留档目录内 {in_archive}")
        # 至少一项未能还原 → 消息必须承认，而不是写死「已还原」
        self.assertNotIn("（留档内容已还原）", res["msg"],
                         "还原不完整却声称已还原（R17 高危模式）")
        self.assertTrue(
            any(k in res["msg"] for k in ("未还原", "仅还原")),
            f"消息未如实反映部分还原：{res['msg']}")
        # 未还原的项应能在留档目录内找到（一件不丢）
        self.assertTrue(in_archive, "未还原项在留档目录中消失（数据丢失）")

    # ---- 演练四：进程被杀后的中间态 ----
    def test_04_interrupted_state_recovered(self):
        """进程被杀：dest 根已空、仅余「旧版本_*」子目录 → 重新归档须正常且不套娃。"""
        old = self.dest / f"{LEGACY}2026-01-01_000000"
        old.mkdir()
        for f in list(self.dest.iterdir()):
            if f.is_file():
                shutil.move(str(f), str(old / f.name))
        print(f"\n  [中断态] 构造后 dest 根={self.at_root()} 留档={self.legacy_dirs()}")

        fake, state = self.controlled_move()   # 不注入失败
        res = self.run_force(fake)
        self.report("中断态", res, state)

        self.assertEqual(res["status"], "ok")
        # 旧档保留、新内容到位
        self.assertIn("新A.bin", self.at_root())
        self.assertTrue(
            any(p.startswith(f"{LEGACY}2026-01-01_000000/") for p in self.tree()),
            "既有留档内容丢失")
        # 既有留档目录不得被再次留档（避免 旧版本_x/旧版本_y/ 套娃）
        nested = [p for p in self.tree()
                  if p.count(LEGACY) > 1 and p.split("/")[-1].startswith(LEGACY)]
        self.assertEqual(nested, [], f"留档目录被二次留档：{nested}")

    # ---- 演练五：源不存在 ----
    def test_05_source_missing_restores_archive(self):
        """源被删 → 留档内容须还原，且消息如实。"""
        self.src.rename(self.tmp / "新下载_moved")
        fake, state = self.controlled_move()
        res = self.run_force(fake)
        self.report("源不存在", res, state)

        self.assertEqual(res["status"], "err")
        self.assertIn("源文件不存在", res["msg"])
        self.assertIn("旧A.bin", self.at_root())
        self.assertIn("旧B.bin", self.at_root())


if __name__ == "__main__":
    unittest.main(verbosity=2)
