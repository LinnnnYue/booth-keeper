# REGISTRY — 板块登记表

> 规则：每行 = 板块路径 + 干什么（≤100 字）。新增板块必须在同一 commit 登记一行；板块范围显著扩大时同 commit 修订该行。**漏登/漏改 = 违规**（AGENT.md 红线引用）。

| 板块路径 | 干什么 |
|---|---|
| `docs/boothkeeper/v1/` | dev-flow 流程本体与决策记录：需求文档（`0N-*.md`）、执行计划 `plan.md`（进度唯一真源）、`worklog/`、`review/`、`BOUNDARY.md`、`DISCIPLINE.md`。已含 P0~P4：规范接入、根目录治理、门面与可移植性修正、遗留项处置（诊断通道 / 回滚加固 / Worker 基类 / `booth_core` 拆分）、残留项处置（异常契约兜底 / 兜底留痕 / updater 静默点） |
| `tests/` | 回归与检查脚本（标准库 `unittest`，无 pytest 依赖）：`test_rollback.py`(5)、`test_archive_flow.py`(6)、`test_archive_contract.py`(14)、`check_module_deps.py`、`check_proxy_single_source.py` 为常驻检查；`_` 前缀者为一次性/度量工具（`_smoke_offscreen.py`、`_compare_worker_contract.py`、`_count_silent.py`、`_count_proxy_writes.py`、`_split_booth_core.py`）。**红线：全部用例只在 `tempfile` 临时目录内操作，绝不触碰 BOOTH 资产库（BOUNDARY B-1）** |
| `archive/` | 历史过程产物归档区：一次性脚本 30 / 发版草稿 14 / 验收评分表 5 / 设计文档 4。只搬运不改写，索引见 `archive/README.md` |
