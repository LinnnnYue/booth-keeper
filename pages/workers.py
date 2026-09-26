# pages/workers.py — 后台任务公共基类
#
# 背景（docs/boothkeeper/v1/02-遗留项处置.md §2.3）：
# 项目原有 11 个 QThread 子类，各自在 run() 开头手写同一段会话装配 ——
# 建 session 之后，若 self.proxy 为真，就把 self.proxy_url 手工塞进 session
# 的 proxies 字典（http / https 两个键）。
#
# 这段手工装配绕过了 R17 建立的 booth_core.apply_proxy() 唯一真源：若配置里
# proxy_url 为空而开关未关，两个键会被写成空串，覆盖全局映射，使请求
# 既不按代理走也不按直连走。此外多数 Worker 没有异常兜底，未捕获异常会直接
# 崩在 run() 里且无任何记录。
#
# 本基类收敛三件事：会话装配、异常兜底与上报、（可选）会话依赖开关。
# 子类的业务逻辑与信号契约保持不变 —— UI 连接代码零改动。
#
# 回归防线：tests/check_proxy_single_source.py 以 AST 扫描全仓，确保
# 「手工写 session.proxies」这一写法不再出现（注释不算）。
import diag
import booth_core as bc
from PySide6.QtCore import QThread, Signal


class BoothTask(QThread):
    """后台任务基类。

    子类实现 work(session) 即可：
      - 需要网络的子类：用 session 发请求（基类已按全局真源配置好代理）
      - 纯本地任务的子类：置 needs_session = False，忽略 session 参数

    基类不发射「完成」信号 —— 各 Worker 的完成信号名与参数各不相同
    （finished / done / result），且被 UI 直接连线，强行统一会破坏契约。
    """
    failed = Signal(str)          # 未捕获异常的统一出口（基类兜底时发射）
    needs_session = True          # 纯本地任务置 False，跳过建会话

    def __init__(self, cookie: str = ""):
        super().__init__()
        self.cookie = cookie

    def session(self):
        """按全局真源建立请求会话。

        代理状态由 booth_core.apply_proxy() 唯一决定（main_window 启动时注入），
        本层不接受、也不再向上游索取 proxy / proxy_url 参数。
        """
        return bc.make_session(self.cookie)

    def work(self, session):
        raise NotImplementedError

    def run(self):
        name = type(self).__name__
        s = None
        if self.needs_session:
            try:
                s = self.session()
            except Exception as e:
                diag.error(f"会话初始化失败：{e}", scope=name)
                self.failed.emit(str(e))
                return
        try:
            self.work(s)
        except Exception as e:
            # 兜底：原先无 except 的 Worker 会把异常抛进 Qt 事件循环，界面只表现为
            # 「点了没反应」。现统一留痕并通知 UI（子类自行处理过的错误不会到此）。
            diag.error(f"后台任务异常：{e}", scope=name)
            self.failed.emit(str(e))
