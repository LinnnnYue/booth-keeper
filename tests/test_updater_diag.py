"""updater 静默点留痕测试网（P4 §3.3 + §3.4）。

对应 docs/boothkeeper/v1/03-残留项处置.md 验收口径 8~10。

两处加固的返回值均**不变**（行为向后兼容），只增可观测性；故用例同时断言
「留痕发生」与「返回值不变」，并各配一个反向用例防止「加了日志但永不触发」
或「正常路径也打日志」两种失效。

可独立重跑：python tests/test_updater_diag.py
（不涉及 Qt，无需 offscreen）
"""
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, ".")
sys.path.insert(0, str(_HERE))

from _diag_capture import DiagTestCase  # noqa: E402


class TestProxyResolveDiagnostics(DiagTestCase):

    def test_01_proxy_resolve_failure_warns(self):
        """口径 8：代理解析失败 → warn 记录，且返回值仍为 None（行为不变）。"""
        from pages import updater
        import booth_core
        with mock.patch.object(booth_core, "proxy_map",
                               side_effect=RuntimeError("proxy cfg broken")):
            res = updater._resolve_proxies(None)
        self.assertIsNone(res, "返回值必须保持 None（降级行为不变）")
        warns = self.cap.by(level="warn", scope="updater")
        self.assertEqual(len(warns), 1,
                         f"应有 1 条 updater warn，实得 {self.cap.records}")
        self.assertIn("proxy cfg broken", warns[0]["msg"])

    def test_02_proxy_disabled_does_not_warn(self):
        """口径 8（反向）：proxy=False 强制直连是正常路径，不应留痕。"""
        from pages import updater
        self.assertIsNone(updater._resolve_proxies(False))
        self.assertEqual(self.cap.records, [],
                         f"强制直连不应产生任何记录：{self.cap.records}")


class TestLocalVersionDiagnostics(DiagTestCase):

    def test_03_version_all_sources_unavailable_warns(self):
        """口径 9：三源全不可用 → 返回 0.0.0 且留痕。"""
        from pages import updater
        with mock.patch.dict(sys.modules,
                             {"_version": None, "main_window": None}), \
             mock.patch.object(Path, "exists", return_value=False):
            ver = updater.parse_local_version()
        self.assertEqual(ver, "0.0.0", "返回值必须保持 0.0.0（向后兼容）")
        warns = self.cap.by(level="warn", scope="updater")
        self.assertEqual(len(warns), 1,
                         f"应有 1 条 updater warn，实得 {self.cap.records}")

    def test_04_version_available_does_not_warn(self):
        """口径 10：正常取到版本号时不产生 warn（无误报）。"""
        from pages import updater
        fake = types.ModuleType("_version")
        fake.__version__ = "9.9.9"
        with mock.patch.dict(sys.modules, {"_version": fake}):
            ver = updater.parse_local_version()
        self.assertEqual(ver, "9.9.9")
        self.assertEqual(self.cap.records, [],
                         f"正常路径不应有任何记录：{self.cap.records}")

    def test_05_later_source_success_does_not_warn(self):
        """口径 10（补充）：降级链第二级命中即返回，不应留痕。"""
        from pages import updater
        fake_mw = types.ModuleType("main_window")
        fake_mw.__version__ = "8.8.8"
        with mock.patch.dict(sys.modules,
                             {"_version": None, "main_window": fake_mw}):
            ver = updater.parse_local_version()
        self.assertEqual(ver, "8.8.8")
        self.assertEqual(self.cap.records, [],
                         f"降级链中途命中不应留痕：{self.cap.records}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
