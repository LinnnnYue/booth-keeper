"""归档异常契约测试网（P4 §3.1 + §3.2）。

对应 docs/boothkeeper/v1/03-残留项处置.md 验收口径 1~7。

三条铁律（承 P3 教训）：
  1. 断言「兜底分支被执行过」（以 diag 记录为证），而非仅断言「没崩」——
     P3 曾因 mock 打错位置（`au` 而非 `au.bc`）收获一次伪绿，耗时 1.5s→0.06s 是唯一线索。
  2. 断言「失败件被上报」而非「函数返回了个 dict」。
  3. BOUNDARY B-1：全部在临时目录内，不触碰 BOOTH 资产库；不发起真实网络请求。

可独立重跑：QT_QPA_PLATFORM=offscreen python tests/test_archive_contract.py
（QThread 需 offscreen；本文件 setUpModule 会自建 QApplication，无需外部准备）
"""
import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, ".")
sys.path.insert(0, str(_HERE))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import requests  # noqa: E402

import archive_util as au  # noqa: E402
from _diag_capture import DiagTestCase  # noqa: E402

BOOM_ID = "2000002"
FAKE_ITEM = {"name": "テスト商品", "category_name": "3Dモデル",
             "category_parent_name": "3Dモデル", "images": []}

_app = None


def setUpModule():
    """DragWorker 是 QThread，构造前需有 QApplication。"""
    global _app
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])


def mk_corpus(n=1, tmp_prefix="contract_"):
    tmp = Path(tempfile.mkdtemp(prefix=tmp_prefix))
    root = tmp / "lib"
    root.mkdir()
    dirs = []
    for i in range(1, n + 1):
        p = tmp / f"f{i}"
        p.mkdir()
        (p / "a.bin").write_bytes(b"x")
        dirs.append(p)
    return tmp, root, dirs


# ─────────────────────────────────────────────────────────────
# 验收口径 1~2、4、6、7：archive_item 永不抛异常
# ─────────────────────────────────────────────────────────────

class TestArchiveItemNeverRaises(DiagTestCase):

    def _call(self):
        tmp, root, dirs = mk_corpus()
        try:
            return au.archive_item("1234567", root, session=None,
                                   move_source=str(dirs[0]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_01_network_exceptions_return_err(self):
        """口径 1：4 类注入异常下均返回 status=err，不抛。"""
        cases = [
            ("ConnectionError", requests.ConnectionError("net down")),
            ("ProxyError", requests.exceptions.ProxyError("proxy bad")),
            ("Timeout", requests.exceptions.Timeout("t/o")),
            ("RuntimeError（非网络）", RuntimeError("boom")),
        ]
        for label, exc in cases:
            with self.subTest(injected=label):
                with mock.patch.object(au.bc, "fetch_item",
                                       side_effect=exc):
                    res = self._call()
                self.assertIsInstance(res, dict, f"{label}: 未返回 dict")
                self.assertEqual(res.get("status"), "err",
                                 f"{label}: 状态应为 err，实得 {res!r}")
                self.assertEqual(res.get("id"), "1234567")

    def test_02_classify_state_exception_returns_err(self):
        """口径 2：fetch 返 None + classify_item_state 抛异常 → status=err。"""
        with mock.patch.object(au.bc, "fetch_item", return_value=None), \
             mock.patch.object(au.bc, "classify_item_state",
                               side_effect=RuntimeError("probe blew up")):
            res = self._call()
        self.assertEqual(res.get("status"), "err", res)
        self.assertEqual(res.get("id"), "1234567")

    def test_03_fallback_branch_actually_executed(self):
        """口径 4（防伪绿）：以 diag error 记录为证，兜底分支确实被执行过。"""
        with mock.patch.object(au.bc, "fetch_item",
                               side_effect=RuntimeError("boom")):
            self._call()
        errs = self.cap.by(level="error", scope="archive_item")
        self.assertEqual(len(errs), 1,
                         f"应有 1 条 archive_item error 记录，实得 {len(errs)}")
        self.assertIn("RuntimeError", errs[0]["msg"])
        self.assertIn("boom", errs[0]["msg"])

    def test_04_diag_record_carries_item_id(self):
        """口径 6：ctx 里带 iid，可在诊断面板按商品定位。"""
        with mock.patch.object(au.bc, "fetch_item",
                               side_effect=RuntimeError("boom")):
            self._call()
        errs = self.cap.by(level="error", scope="archive_item")
        self.assertEqual(errs[0]["ctx"].get("iid"), "1234567", errs[0])

    def test_05_happy_path_produces_no_error_record(self):
        """口径 7：正常归档路径不产生新的 error 记录（无误报）。"""
        tmp, root, dirs = mk_corpus()
        try:
            with mock.patch.object(au.bc, "fetch_item",
                                   return_value=dict(FAKE_ITEM)):
                res = au.archive_item("1234567", root, session=None,
                                      move_source=str(dirs[0]))
            self.assertEqual(res.get("status"), "ok", res)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(self.cap.by(level="error"), [],
                         f"正常路径不应有 error：{self.cap.records}")


# ─────────────────────────────────────────────────────────────
# 验收口径 3：DragWorker 不再静默丢件、UI 不再悬挂
# ─────────────────────────────────────────────────────────────

class TestBatchResilience(DiagTestCase):

    @staticmethod
    def _boom_on_second(iid, session=None):
        if iid == BOOM_ID:
            raise RuntimeError("注入异常：该件 fetch 炸")
        return dict(FAKE_ITEM, name=f"商品{iid}")

    def _run_drag(self, n_jobs, fetch_side_effect):
        from pages.dragdrop_page import DragWorker
        tmp, root, dirs = mk_corpus(n_jobs, "contract_batch_")
        jobs = [(str(d), f"200000{i+1}") for i, d in enumerate(dirs)]
        done, failed, fin = [], [], []
        w = DragWorker(jobs, root)
        w.item_done.connect(done.append)
        w.failed.connect(failed.append)
        w.finished.connect(lambda: fin.append(1))
        with mock.patch.object(au.bc, "fetch_item",
                               side_effect=fetch_side_effect):
            w.run()
        return tmp, len(jobs), done, failed, fin

    def test_06_single_failure_does_not_abort_batch(self):
        """口径 3：注入单件异常时，处理件数 == 投放件数。"""
        tmp, n, done, failed, fin = self._run_drag(4, self._boom_on_second)
        try:
            self.assertEqual(len(done), n,
                             f"应处理 {n} 件，实为 {len(done)} 件 —— 仍有静默丢件")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_07_finished_signal_still_emitted(self):
        """口径 3：注入下 finished 仍发射（否则 UI 状态机悬挂）。"""
        tmp, n, done, failed, fin = self._run_drag(4, self._boom_on_second)
        try:
            self.assertTrue(fin, "finished 未发射 —— UI 状态机将悬挂")
            self.assertEqual(failed, [],
                             f"单件失败不应冒泡到 worker 级 failed：{failed}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_08_failed_item_reported_as_err_not_dropped(self):
        """口径 3：失败的那一件以 status=err 上报，而非消失。"""
        tmp, n, done, failed, fin = self._run_drag(4, self._boom_on_second)
        try:
            boom = [r for r in done if r.get("id") == BOOM_ID]
            self.assertEqual(len(boom), 1, f"第 2 件未上报：{done}")
            self.assertEqual(boom[0].get("status"), "err", boom[0])
            ok_ids = [r.get("id") for r in done if r.get("status") == "ok"]
            self.assertEqual(len(ok_ids), 3, f"应成功 3 件，实得 {ok_ids}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_09_baseline_no_injection_all_succeed(self):
        """对照基线：不注入异常时 4/4 成功（防止本用例掩盖别的回归）。"""
        def fetch_ok(iid, session=None):
            return dict(FAKE_ITEM, name=f"商品{iid}")

        tmp, n, done, failed, fin = self._run_drag(4, fetch_ok)
        try:
            self.assertEqual(len(done), n)
            self.assertEqual([r.get("status") for r in done], ["ok"] * n)
            self.assertTrue(fin)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
