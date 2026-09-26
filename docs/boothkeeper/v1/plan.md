# boothkeeper 执行计划（v1）

> 本文件由 dev-flow skill 模板派生；仅替换 `<尖括号>` 内容。
> 纪律：做一个勾一个，禁止做完补勾、禁止伪勾（未做保持 `[ ]` 并注明原因）；checkbox 四态 `[ ]`未开工 / `[~]`进行中 / `[x]`完成 / `[!]`受阻，与 worklog 状态 🔄/✅/⛔ 一一对应；本文件只管执行——论证回需求文档、过程回 worklog、评审回 review/；写完立即提交，合并先拉新。

## P0 — 规范接入与文档骨架（建立 dev-flow 流程本体）

- [x] 置入 `devskill/` 规范本体，与源仓逐字一致 — 验收：`diff -r devskill/ <源>/devskill/` 无输出
- [x] 项目化 `AGENT.md`（替换占位、删除「接入你的项目」小节、写入本项目红线与接手协议）— 验收：`rg '<[^>]+>' AGENT.md` 无尖括号占位命中
- [x] 建立 `docs/REGISTRY.md` 并登记 `docs/boothkeeper/v1/` 一行 — 验收：表格含该路径，说明 ≤100 字
- [x] 建立 `docs/boothkeeper/v1/` 五段需求文档 `01-流程规范接入.md` — 验收：五段标题齐全（现象/目标/方案与取舍/不做什么/验收口径），无执行项拆分与进度勾选
- [x] 逐字拷贝 `DISCIPLINE.md` 与 `WORKLOG-PROTOCOL.md` 进 `v1/` — 验收：与 `devskill/` 同名文件 `diff` 无输出
- [x] 建 `BOUNDARY.md` 并登记 B-1 ~ B-5 红线 — 验收：每条含「能做/不能做/原因/反复修改史/出处」五字段
- [x] 建 `docs/boothkeeper/v1/worklog/win-desktop-n3o6sc2-raphael.md` 并写入首条 worklog — 验收：文件头含机器/写作者/协议指向，条目含目标/验证/代码状态/状态
- [x] 建 `review/` 目录占位 — 验收：`find docs/boothkeeper/v1/review` 返回目录本身（含 `.gitkeep`）
- [x] 提交 P0 全部产物 — 验收：`git log -1 --format=%h -- docs/boothkeeper/` = `30e06f8`（18 文件）
- [ ] 推送至 origin/main（**待主上确认**；公开仓库，推送即对访客可见）— 验收：`git ls-remote origin main` 与本地 HEAD 一致

## P1 — 根目录治理（收敛历史包袱）

> 前置：P0 全部 `[x]`。本阶段第一项产出的**归档清单须经用户确认后**才执行移动。

- [~] 盘出根目录一次性脚本清单，产出「保留 / 归档 / 删除」建议表交用户确认 — 验收：清单覆盖 `rg -l '^# *(_|fix_r|test_r|test_qa|render_preview|preview|verify_)' *.py` 全集，逐项标状态与理由
- [ ] 建 `legacy/oneoff/` 并把已入库的一次性脚本移入（`_forensic_icons.py`、`_normalize_ini_all.py`、`_test_drag_r21.py`、`_test_force_r22.py`、`fix_r9/r10/r12_*.py`、`render_preview_r5/r6.py`、`render_r7plus_mismatch.py`、`test_qa_r5*.py`、`test_r6.py`、`test_r7*.py`、`test_folder_icon_fix.py`、`render_preview.py`、`preview3/4.py`、`preview_render.py`、`verify_*.py`）— 验收：根目录 `ls *.py` 仅剩 `run.py` / `booth_core.py` / `main_window.py` / `theme.py` / `archive_util.py` / `_version.py`
- [ ] 处理本地 17 项未跟踪文件：`rel_v1.3.4`~`rel_v1.4.1_notes.md` 与 `作者卡片注入说明.md`、`author_card_template.html` 归入 `docs/releases/` 或 `legacy/`；`_rescue_dl_8545487.py`、`_rewrite_ini_26.py`、`fix_folder_icons.py` 归 `legacy/oneoff/` — 验收：`git status --porcelain` 清空（除刻意保留项，须逐项说明）
- [ ] 修正 `.gitignore` 与入库内容的一致性：同类性质文件不得一半忽略一半入库 — 验收：`rg 'SCORE_TABLE|preview|verify_' .gitignore` 与实际入库结果无冲突（逐条核对）
- [ ] 统一发版记录位置：`rel_v*.md` / `SCORE_TABLE_*.md` 移入 `docs/releases/`（保留原文件名），README 更新日志改为指向该目录 — 验收：根目录无 `rel_v*.md` 与 `SCORE_TABLE_*.md`；README「更新日志」段落链接可达
- [ ] 修正 README 第 141 行链接（现指向 R7，最新为 R10）— 验收：链接指向的路径在仓库中真实存在

## P2 — 门面与可移植性修正

> 前置：P0 全部 `[x]`。**P2-3 会改变默认网络行为，须用户拍板后再执行。**

- [ ] 拆分 `LICENSE.txt`：正文仅保留纯 MIT 文本，中文项目说明与免责声明移入 `NOTICE.md` — 验收：GitHub 仓库页 License 显示为 `MIT`（非 `NOASSERTION`）
- [ ] 更新 `pages/updater.py:11-12` 硬编码用户名为 `LinnnnYue`（现依赖旧名重定向）— 验收：`rg 'linnnnnnnnnnnnnnnnnnnnn/booth-keeper' --glob '*.py'` 无命中；`python -c "from pages import updater; print(updater.check_update())"` 返回 `has_update` 字段可判定
- [ ] **待用户拍板**：代理策略改为「默认直连、设置页可选启用代理」（现 `booth_core.py:40` 默认指向 `127.0.0.1:20122`，无代理环境下所有请求先失败重试 3 次）— 验收：无代理环境（`HTTPS_PROXY` 未设）下 `python -c "import booth_core as bc; bc.fetch_item('7032906')"` 3 秒内返回非 None
- [ ] README 修正：删除或改写两处 `preview_build/` 引用（该目录被 `.gitignore` 忽略，访客不可见）；`[booth_core.py:42-77](booth_core.py)` 改为标准 GitHub 行号链接格式 — 验收：README 中所有相对链接指向的路径在仓库树中真实存在
- [ ] 评审 `archive_util.py` 的静默失败点（`download_cover` / `make_folder_icon` / `_remove_to_trash` 的 `except: pass`），改为至少记录到 worklog 或 UI 状态 — 验收：产出 `review/` 记录一份，列出每处静默点的现行行为与建议处置

<!-- 新阶段在末尾顺延编号追加（P3、P4…）；新需求先走需求文档评审再插入或新起 PX。 -->
