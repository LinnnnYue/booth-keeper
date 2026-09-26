# 00-README — BoothKeeper 开发文档总览（v1）

## 自包含背景

BoothKeeper（展位守护者）是一站式 BOOTH.pm 资产整理桌面端：PySide6 + Python 3.13，PyInstaller 单 exe / onedir / NSIS 安装包三形态，零云端依赖。核心四功能：批量链接处理、拖拽分类、实验性检索、目录巡检 + 错位纠正。

项目自 2026-08-14 起以「R 轮次」迭代至 **1.5.6**，共 13 份发版记录（`rel_v1.3.4` → `rel_v1.5.6`）与 7 份评分表（`SCORE_TABLE_R4` → `R10`），但**从未建立 docs/ 文档体系**：需求、决策、踩坑全部散落在根目录脚本、发版记录与代码注释里。

本板块（v1）的任务是**给项目补上流程与文档骨架**，并把已经积累的历史包袱收敛掉，不改变任何功能行为。

## 目标

1. 接入 devskill 流程规范（`devskill/` 为本仓规范本体，逐字拷贝生效）。
2. 建立 `docs/` 版本化文档体系，把后续开发纳入「需求 → 评审 → plan → 执行 → worklog」闭环。
3. 定义并登记项目红线（BOOTH 资产库只读、版本号三处同步、与 booth-toolkit 分类规则一致）。
4. 收敛根目录散落文件（一次性脚本、发版记录、评分表）。

## 文档地图

| 文件 | 作用 |
|---|---|
| `00-README.md` | 本文件：总览、目标、文档地图、红线索引 |
| `01-流程规范接入.md` | 需求与方案（五段）：为什么接入、怎么做、不做什么、怎么验收 |
| `DISCIPLINE.md` | 纪律（dev-flow skill 逐字拷贝，**禁止改写**） |
| `WORKLOG-PROTOCOL.md` | 工作日志协议（dev-flow skill 逐字拷贝，**禁止改写**） |
| `plan.md` | 唯一执行计划：P0..PN + 逐项 checkbox（**进度唯一真源**） |
| `worklog/` | 工作日志，`<平台>-<机器名>-<写作者>.md` 每人一个文件 |
| `review/` | 评审记录：谁评审、结论、证据 |
| `BOUNDARY.md` | 边界文件：能做/不能做/反复修改史 |

## 红线索引

- **R1 BOOTH 资产库只读**：测试一律用临时目录，禁止拿真实库当沙盒 → `BOUNDARY.md` B-1
- **R2 docs/ 不可删**：需求文档、worklog、review/、BOUNDARY.md 永留 → `BOUNDARY.md` B-2
- **R3 版本号三处同步**：`_version.py` / `.spec` / 发版记录 → `BOUNDARY.md` B-3
- **R4 与 booth-toolkit 分类规则一致** → `BOUNDARY.md` B-4
- **R5 禁止新增根目录散落文件** → `BOUNDARY.md` B-5
- **通用红线**：无需求文档不开工、无 plan 项不写码、不 push 等于没做 → `DISCIPLINE.md` §9
