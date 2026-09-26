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
- [x] 推送至 origin/main（用户于 R17 拍板放行）— 验收：`git ls-remote origin main` = `0faa030`，与本地 HEAD 一致 ✅

## P1 — 根目录治理（收敛历史包袱）· R17 完成

- [x] 盘出根目录一次性脚本清单，产出「保留 / 归档 / 删除」建议表交用户确认 — 验收：产出 `review/2026-09-27-根目录处置表.md`，覆盖处置前 66 项全集并逐项标注类别与理由；用户已确认 ✅
- [x] 建归档目录并把一次性脚本移入 — **偏离原计划**：原拟 `legacy/oneoff/`，实际采用 `archive/scripts/`。理由：`legacy` 暗示「待删的遗留」，本批实为「保留备查的历史证据」，语义相反 — 验收：根目录 `ls *.py` 仅剩 6 个运行必需文件；24 项被 git 识别为重命名，`git log --follow` 可追溯 ✅
- [x] 处理本地未跟踪文件 — 实测 15 项（原记录 17 项系首次统计口径差异，以实测为准）：`rel_v1.3.4`~`v1.5.1_notes.md`（9 份）与 `作者卡片注入说明.md`、`author_card_template.html` 归入 `archive/`；`_rescue_dl_8545487.py`、`_rewrite_ini_26.py`、`fix_folder_icons.py` 归 `archive/scripts/` — 验收：`git status --porcelain | grep '^??'` 计数为 0 ✅
- [x] 修正 `.gitignore` 与入库内容的一致性 — 根因定位：旧规则无前导斜杠（如 `preview3.py`）会匹配**任意层级**同名文件。修正为全部加前导 `/`，只约束根目录。4 组同类矛盾（`SCORE_TABLE_*` / `render_preview*` / `test_*` / `rel_v*_notes`）全部消除 — 验收：逐条核对无冲突，归档后文件不再被误忽略 ✅
- [x] 统一发版记录位置 — **偏离原计划**：原拟 `docs/releases/`，实际分流为 `archive/release-notes/`（14 份发版草稿）与 `archive/score-tables/`（5 份验收评分表），因两者性质不同（文案草稿 vs 验收记录），混放会降低可检索性；README「更新日志」改为指向 `archive/score-tables/` — 验收：根目录无 `rel_v*.md` 与 `SCORE_TABLE_*.md` ✅
- [x] 修正 README 失效链接（合并原「第 141 行链接指向 R7」一项）— 三处全改：`preview_build/` ×2、更新日志链接、`booth_core.py` 行号链接格式 — 验收：脚本提取 README 12 个相对链接，全部可达 ✅

## P2 — 门面与可移植性修正 · R17 完成

- [x] 拆分 `LICENSE.txt` — **偏离原计划**：中文项目说明与免责声明实际移入 `README.md` 的「协议」章节，未新建 `NOTICE.md`。理由：README 已有「⚠️ 风险提示」「📜 协议」两节，语义集中且访客更易见 — 验收：`LICENSE.txt` 仅含 MIT 正文 ✅；GitHub 端 `spdx_id` 由 `NOASSERTION` 变 `MIT` 需推送后由 GitHub 重新扫描，属外部平台行为，本地不可验证 ⏳
- [x] 更新 `pages/updater.py` 硬编码用户名为 `LinnnnYue` — 同时处理 `pages/settings_page.py`、`README.md`，共 6 处 — 验收：`rg 'linnnnnnnnnnnnnnnnnnnnn/booth-keeper' --glob '*.py'` 命中 0 ✅
- [x] 代理策略改为「默认直连、设置页可选启用」（用户 R17 拍板）— 实现：新增 `booth_core.apply_proxy()` 作为唯一真源；`PROXY` 常量去掉 `127.0.0.1:20122` 兜底（仅尊重环境变量 `HTTPS_PROXY`）；`DEFAULT_CONFIG["proxy"]` → `False`；`updater.py` 移除自持硬编码常量；启动与设置页保存时注入 — 验收：实测四项（默认直连 / 启用代理 / 关闭回直连 / 空 URL 直连）全部符合预期 ✅
- [x] README 修正：改写两处 `preview_build/` 引用；`[booth_core.py:42-77](booth_core.py)` 改为标准 GitHub 行号链接格式 — 验收：README 所有相对链接指向的路径在仓库树中真实存在 ✅
- [x] 评审 `archive_util.py` 的静默失败点 — 产出 `review/2026-09-27-静默失败点评审.md`：全项目 36 处静默点逐处定性（含所属函数名），处置 7 处，残留 29 处已分三类（保持 18 / 建议加固 8 / 高危 3）— 验收：记录含每处现行行为与建议处置，附脚本化复现方式 ✅

## P3 — 遗留项处置 · R23 完成

> 需求文档：[`02-遗留项处置.md`](02-遗留项处置.md)（四节 + 共同红线）。
> 实施顺序：2.1 通道 + 2.2 加固 → 2.3 QThread → 2.4 拆分；测试网为 2.4 前置。
> 本轮**偏离立项方案 4 处**，均已在需求文档对应小节与 worklog `[v1]-raphael-20260927-0230` 如实登记：
> ① 模块数 4 → **6**（`bk_net` 单文件 968 行触犯 <620 口径）；
> ② Worker 数 10 → **11**（立项漏计 `audit_page` 2 个）；
> ③ 基类统一 `finished` 信号**否掉**（会破坏信号契约不变的验收口径）；
> ④ 2.3-1 验收由文本 `rg` 改 **AST** 判定（文本口径无法区分代码与注释）。

- [x] 写 P3 四项需求文档 — 产出 [`02-遗留项处置.md`](02-遗留项处置.md)：每项含现象/目标/方案与取舍/不做什么/验收口径五段，并定实施顺序与依赖 — 验收：五段标题齐全，含 4 处取舍论证与「附：四项共同红线」✅
- [x] 建回归测试网（2.4 前置）— 产出 `tests/test_rollback.py`（5 用例）、`tests/test_archive_flow.py`（6 用例）、`tests/check_module_deps.py`、`tests/check_proxy_single_source.py`、`tests/_smoke_offscreen.py`、`tests/_compare_worker_contract.py` — 验收：全部可独立重跑，退出码 0 ✅
- [x] 后台异常统一上报通道 — 新增 `diag.py`（115 行，零依赖）+ `pages/diag_panel.py`（207 行）+ `main_window` 桥接与状态栏入口；替换 11 处 `print`（逻辑层残留 0）；加固 8 处静默点 — 验收：环形缓冲 FIFO / 跨线程 sink / 未注册时回落 stdout / UI 未就绪不崩 / 计数为「未读」语义，逐项实测通过 ✅
- [x] `force` 重归档回滚路径加固 — 提取 `_restore_from_archive` / `_describe_restore` / `_is_legacy_dir`，三处调用点统一；消除「部分还原却报完全还原」的假成功消息，并修掉 `旧版本_*` 套娃缺陷 — 验收：`tests/test_rollback.py` 5/5 通过；半还原消息为「仅还原 1 项，1 项仍在 旧版本_2026-09-27_015609/（旧B.bin）」与磁盘一致 ✅
- [x] QThread 样板提取 — 新增 `pages/workers.py` 的 `BoothTask(QThread)` 模板方法基类，迁移 **11** 个 Worker；构造函数去掉 `proxy` / `proxy_url`；另发现并修掉 2 处 UI 线程内代理绕过（`search_page` / `dragdrop_page`）— 验收：`tests/check_proxy_single_source.py` 违规 0（含 1 条登记白名单）；`tests/_compare_worker_contract.py` 11 类信号契约差异 0；空 URL 污染场景由 `{'http':'','https':''}` 变为 `{}` ✅
- [x] `booth_core.py` 单体拆分 — 1439 行 → `bk_net`(449) / `bk_search`(307) / `bk_shell`(304) / `bk_local`(258) / `bk_text`(177) / `bk_domain`(99)，`booth_core.py` 改为 116 行门面（模块级 `__getattr__` 动态转发）— 验收：公共符号 51 = 51（差异集为空）；调用点消失 0 个；全部模块 < 620 行；`tests/test_archive_flow.py` 6/6 与 `tests/test_rollback.py` 5/5 全绿；离屏启动 `title`/`pages` 与拆分前一致 ✅
- [x] 回填 worklog 并提交推送 — worklog 条目 `[v1]-raphael-20260927-0230` 记实测与四处偏离；需求文档 3 小节按实测更正 — 验收：`git log --format=%h -1` 见本轮提交，`git ls-remote origin main` 与本地 HEAD 一致 ✅

<!-- 新阶段在末尾顺延编号追加（P4、P5…）；新需求先走需求文档评审再插入或新起 PX。 -->
