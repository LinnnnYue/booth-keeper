"""测试辅助：diag sink 接管（非用例文件，`_` 前缀以免被 discovery 当测试收集）。

`sink` 是全局单接收方（R23 设计），测试需临时接管以断言「留痕确实发生」。
统一在此处接管与恢复，避免各测试文件各写一份。
"""
import unittest

import diag


class DiagCapture:
    """收集 diag 记录，供「分支确实执行过」类断言使用。"""

    def __init__(self):
        self.records = []

    def __call__(self, rec):
        self.records.append(rec)

    def by(self, level=None, scope=None):
        out = self.records
        if level:
            out = [r for r in out if r["level"] == level]
        if scope:
            out = [r for r in out if r["scope"] == scope]
        return out


class DiagTestCase(unittest.TestCase):
    """基类：接管 diag sink，用例结束后恢复（默认回落 stdout）。"""

    def setUp(self):
        self.cap = DiagCapture()
        diag.set_sink(self.cap)

    def tearDown(self):
        diag.set_sink(None)
