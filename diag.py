"""分级诊断通道 —— 为打包环境提供后台异常可见性。

背景：PyInstaller --windowed 模式下 stdout 被丢弃，`print()` 写下的告警
在用户机器上完全不可见（详见 docs/boothkeeper/v1/02-遗留项处置.md §2.1）。

四条设计约束：
  1. 本模块不依赖 PySide6 —— 逻辑层（booth_core / archive_util）必须能在
     无 GUI 环境下被测试，若为上报而 import Qt 会破坏这一点。
  2. 线程安全 —— 上报方是 QThread 内运行的 Worker，接收方是 GUI 线程。
  3. 默认 sink 为 stdout —— 未注册接收方时行为与改造前的 print 一致。
  4. 环形缓冲 —— 保留最近若干条，供日志面板一次性回溯。

用法：
    import diag
    diag.warn("图标生成失败", scope="archive_item", iid=iid)

    # GUI 侧（main_window 启动时）：
    diag.set_sink(lambda rec: bridge.record.emit(rec))   # 由桥对象转到主线程
"""

from __future__ import annotations

import sys
import threading
import time
from collections import deque

LEVELS = ("info", "warn", "error")

# 环形缓冲容量。归档一批 50 件商品时，每件最多产生 1~2 条告警，
# 500 条足以覆盖「单次会话内出现的所有异常」，且内存占用可忽略。
_BUFFER_MAX = 500

_lock = threading.Lock()
_buffer: deque = deque(maxlen=_BUFFER_MAX)
_sink = None


def _default_sink(record: dict) -> None:
    """未注册接收方时的兜底：写到 stdout，与改造前的 print 行为一致。"""
    scope = f"{record['scope']}: " if record["scope"] else ""
    ctx = record.get("ctx") or {}
    suffix = ("  " + " ".join(f"{k}={v}" for k, v in ctx.items())) if ctx else ""
    print(f"[{record['level']}] {scope}{record['msg']}{suffix}")


def report(level: str, msg: str, scope: str = "", **ctx) -> dict:
    """上报一条诊断记录。这是唯一入口。

    level: "info" | "warn" | "error"。非法值按 "info" 处理（不抛异常——
    诊断通道自身的错误绝不该影响业务流程）。
    返回记录 dict，便于调用方复用（如塞进返回消息）。
    """
    if level not in LEVELS:
        level = "info"
    record = {
        "level": level,
        "msg": str(msg),
        "scope": scope,
        "ts": time.time(),
        "ctx": ctx,
    }
    with _lock:
        _buffer.append(record)
        sink = _sink
    # sink 在锁外调用：避免 sink 自身再触发 report 造成死锁
    handler = sink or _default_sink
    try:
        handler(record)
    except Exception:
        # 上报通道的失败必须被吞掉，否则会把「记录错误」变成「引发错误」
        pass
    return record


def info(msg: str, scope: str = "", **ctx) -> dict:
    return report("info", msg, scope, **ctx)


def warn(msg: str, scope: str = "", **ctx) -> dict:
    return report("warn", msg, scope, **ctx)


def error(msg: str, scope: str = "", **ctx) -> dict:
    return report("error", msg, scope, **ctx)


def set_sink(fn) -> None:
    """注册接收方。fn(record: dict)；传 None 恢复默认 stdout 输出。"""
    global _sink
    with _lock:
        _sink = fn


def recent(n: int = 100, level: str | None = None) -> list:
    """取环形缓冲最近 n 条（时间正序）。level 非空时按级别过滤。"""
    with _lock:
        snap = list(_buffer)
    if level:
        snap = [r for r in snap if r["level"] == level]
    return snap[-n:] if n else snap


def clear() -> None:
    """清空缓冲（日志面板「清空」按钮用）。不影响 sink 注册状态。"""
    with _lock:
        _buffer.clear()


def count(level: str | None = None) -> int:
    """按级别计数，用于「本次会话共 N 条告警」这类汇总。"""
    with _lock:
        if level is None:
            return len(_buffer)
        return sum(1 for r in _buffer if r["level"] == level)
