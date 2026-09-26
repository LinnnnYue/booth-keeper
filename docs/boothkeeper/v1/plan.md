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

## P4 — 残留项处置 · R24

> 需求文档：[`03-残留项处置.md`](03-残留项处置.md)。
> 来源：`review/2026-09-27-P3四项验收记录.md` §五 5 项残留 + 主上指令「残留未做的继续交由你来执行」。
> **处置分界：做 4 项、明确不做 3 项**（不做项均附判据，见需求文档 §四）。
> 本轮**收窄了归档记录的 1 处推断**：`fetch_item` 内部已有 `try`，真实网络故障
> **不会**穿透；真正暴露面是「契约未声明 + 调用方各自猜测」，详见 §3.1。

- [x] 写 P4 需求文档 — 产出 [`03-残留项处置.md`](03-残留项处置.md)：现象段全部引用本轮实测（先跑两个**只读探针**取证：逐类异常注入 + 三个批量调用点对照；探针在结论转入正式用例后已删除，不留悬空脚本），含处置分界表、4 项五段论证、3 项不做项判据、口径说明 — 验收：五段标题齐全，10 条验收口径编号连续，不做项逐条附判据 ✅
- [x] `archive_item` 异常契约兜底（高危）— 最外层统一收口，契约改为「永不抛异常，永远返回 dict」；原函数体改名 `_archive_item` 零侵入（包装 23 行 / 原体 203 行）— 验收：4 类注入异常 + `classify_item_state` 异常共 5 场景均返回 `status="err"` 不抛；`DragWorker` 处理件数由 **1/4 → 4/4**、`finished` 由**未发射 → 已发射** ✅
- [x] 兜底路径可观测 — 兜底分支接 `diag.error`，`scope="archive_item"` 且 `ctx["iid"]` 可定位 — 验收：注入时收到 `scope="archive_item"` / `iid=2000002` 的 error 记录；正常归档路径 error 记录数 = 0 ✅
- [x] `updater` 两处静默留痕 — `_resolve_proxies` 代理解析失败与 `parse_local_version` 三源全失败，各加 `diag.warn`（返回值均不变）— 验收：两处各产生 1 条 warn；反向用例（`proxy=False` 强制直连 / 取到版本号 / 降级链第二级命中）记录数均为 0，无误报 ✅
- [x] 建异常契约测试网 — 新增 `tests/test_archive_contract.py`（9 用例，口径 1~7）+ `tests/test_updater_diag.py`（5 用例，口径 8~10）+ 共享辅助 `tests/_diag_capture.py`；**按主题拆成两个文件**是为让两次代码提交各自可验证（单文件跨两项则中间提交必然红）— 验收：分别 `Ran 9 tests` / `Ran 5 tests`，均 `OK`，退出码 0，不发起真实网络 ✅；另以 `git worktree` 在两个提交点独立重跑，均绿
- [x] 全量回归 — 依赖检查 缺失 0 / 代理真源 违规 0 / 回滚演练 5/5 / 归档主流程 6/6 / Worker 契约 差异 0 / 离屏冒烟 rc=0 / `py_compile` rc=0 — 验收：全部通过；归档主流程 6 条路径（`ok`/`exists`/`mismatch`/`force` 留档/`delisted`/连不上不妄断）逐条复核零回归；静默点 21 **与 P3 后持平**（符合需求文档口径说明：本轮以消除「无留痕」为目标，不以降低 `except: pass` 计数为目标）✅
- [x] 回填文档并提交推送 — plan 勾选 + review 验收记录 + worklog 条目；清理两个一次性探针；另以 `R24-4` 补记推送通道受阻与解法 — 验收：**远端 `main` = 本地 `HEAD`**（经 `gh api` 核验，推送后即刻核对）✅。⚠️ **验证手段已变**：`git ls-remote` / `git push` 因 `github.com` 被阻断不可用，本轮实际走 **Git Data API**（`blob→tree→commit→ref`，逐对象 SHA 校验 + 临时 ref 预检），各提交 SHA 与本地逐字节一致、无分叉，详见验收记录 §八。**注：验收口径锚定「远端与本地是否同 SHA」这一结论，不写死具体 SHA 值**——写死会随下一次提交立刻失真

<!-- 新阶段在末尾顺延编号追加（P4、P5…）；新需求先走需求文档评审再插入或新起 PX。 -->
