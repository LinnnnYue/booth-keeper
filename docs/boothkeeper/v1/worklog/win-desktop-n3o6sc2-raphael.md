# worklog — DESKTOP-N3O6SC2 / 拉斐尔（智慧之王）

> 本文件由 dev-flow skill 分发，逐字拷贝为 `worklog/<平台>-<机器名>-<写作者>.md` 后使用。
> 记录规则（第 0 铁律/分工/恢复流程/条目模板/双写顺序/记录纪律）见上一级目录 `../WORKLOG-PROTOCOL.md`，本文件不重复规则。
> 纪律：只写自己的文件；条目倒序（最新在顶）；开工开条目、收工更新同一条目不新开。

- 机器：DESKTOP-N3O6SC2
- 写作者：拉斐尔（WorkBuddy Agent）
- 协议：`../WORKLOG-PROTOCOL.md`

---

## [v1]-raphael-20260927-0110 R17：主上拍板后逐项处置（P0 收尾 + P1 + P2 全量） — 2026-09-27 01:10 开始

- **执行者**: 拉斐尔（WorkBuddy Agent，机器：DESKTOP-N3O6SC2）
- **目标**: 主上指令「准了，挨个处理」——批准上一轮提出的三处待拍板项（push / P1 归档 / P2-3 代理策略），并要求逐项处置。执行范围：P0 末项（push）+ P1 全部 + P2 全部。
- **上下文**: 上一轮已产出 `review/2026-09-27-仓库与代码现状审查.md`（9 项优点 + 12 项待办 T1~T12）。主上批准后，本轮把 T1~T7、T10 全部落地，T8/T9/T11 部分项降级为 P3 登记。
- **进展**:
  1. **push**：`58b82b1..0faa030` 推送成功，`git ls-remote` 与本地 HEAD 一致。
  2. **T1 代理解耦**：`booth_core` 新增 `apply_proxy()` / `proxy_map()` 作为唯一真源；`PROXY` 常量去掉 `127.0.0.1:20122` 硬兜底（保留环境变量 `HTTPS_PROXY` 尊重）；`DEFAULT_CONFIG["proxy"]` → `False`；`main_window.__init__` 启动时注入；设置页 `_collect()` 末尾即时注入（改完无需重启）；`updater.py` 移除自持常量、`fetch_latest_release(proxy=None)` 改为跟随全局。
  3. **T2/T3/T4 仓库卫生**：51 项根目录产物 `git mv` 至 `archive/{scripts,release-notes,score-tables,design}`（30/14/5/4），建 `archive/README.md` 索引；重写 `.gitignore`（所有散落规则加前导 `/`）；`assets/logo/*.svg` 补入库。
  4. **T5 LICENSE**：还原纯 MIT 正文，中文说明与免责声明移入 README「协议」章节。
  5. **T6 用户名**：6 处 `linnnnnnnnnnnnnnnnnnnnn/booth-keeper` → `LinnnnYue/booth-keeper`。
  6. **T7 README**：三处失效引用全改，实测 12 个相对链接全部可达。
  7. **T10 静默点**：全项目 36 处逐处定性（AST 自动定位所属函数），处置 7 处，产出 `review/2026-09-27-静默失败点评审.md`。
  8. 产出 `review/2026-09-27-根目录处置表.md`（P1 首项验收底稿：66 项全集逐项标注）。
- **验证**（2026-09-27 实测，全部通过）:
  - 代理四项行为：默认 `''` → `session.proxies={}`；`apply_proxy(url, True)` → 双向代理映射；`enabled=False` → `{}`；空 URL → `{}`（PASS）
  - `updater._resolve_proxies(None)` 走全局、`(False)` 强制直连（PASS）
  - `py_compile` 全量通过（`booth_core` / `archive_util` / `main_window` / `theme` / `pages/*.py`）
  - `QT_QPA_PLATFORM=offscreen` 实例化 → `title= Booth Keeper v1.5.6`，`pages= ['links','drag','search','audit','settings']`（PASS）
  - 设置页回归：`chk_proxy=True`、URL 随配置、`_autosave()` 后状态栏「设置已自动保存」、全局代理正确注入为 `127.0.0.1:20122/`（PASS）
  - README 相对链接可达性：12/12 PASS
  - 旧用户名源码区命中：0
  - 静默点计数：36 → 29（脚本化口径见评审文档 §5）
  - 根目录非目录文件：66 → 15；未跟踪：15 → 0
  - `_remove_to_trash` 冒烟：以 `tempfile.mkdtemp()` 临时目录测试，未触碰 BOOTH 资产库（合规 B-1）
- **决策与坑**:
  - **偏离 plan 三处，均已如实标注**：①归档目录由 `legacy/oneoff/` 改为 `archive/scripts/`（后者语义是「保留备查的历史证据」，`legacy` 暗示「待删」，相反）；②发版记录分流为 `archive/release-notes/` 与 `archive/score-tables/`（文案草稿与验收记录性质不同，混放降低可检索性）；③LICENSE 的中文说明移入 README 而非新建 `NOTICE.md`（README 已有风险提示与协议两节，更集中易见）。
  - **T4 根因**：旧 `.gitignore` 规则无前导斜杠 → 匹配任意层级同名文件 → 既会误伤归档后的脚本，又造成同类文件「一半入库一半被忽略」。改为统一加 `/` 后两个问题同时消除。
  - **T14 重要认知**：老用户 `~/.boothkeeper.json` 中的 `proxy: true` **优先于**新默认值——这是正确行为（否则等于篡改用户设置）。实测本机配置为 `proxy=True` 且 `127.0.0.1:20122` 端口在线，故主上使用体验与改动前一致；**默认直连只对新用户生效**。若老用户要切直连，需在设置页关闭开关。
  - **T16 流程教训（自查）**：离屏测试中调用 `sp._autosave()` 会写用户配置文件 `~/.boothkeeper.json`。本次为等值写回（7 键齐全，`cookie` 1037 字符完好，仅 mtime 更新），未造成破坏，但属不必要的写入。**后续 UI 测试应只读验证，或临时重定向 `CONFIG_PATH` 至临时目录**。
  - **回滚路径不动**：`archive_item` 三处高危静默点（L285/L312/L349）位于 force 重归档的回滚路径，改动需覆盖磁盘满 / 文件占用 / 进程被杀 / 半还原中间态的真机演练。未建演练环境前改动风险高于现状，故只登记 P3，不擅动。
  - **`download_cover` 定性修正**：上一轮审查表述为「失败静默」不够准确——中间层有 `print`，缺的是「全部通道失败时」的末端留痕。本轮已补齐，并在评审文档中修正描述。
  - **`consolidate_id` 与 `archive_item` 状态上报不对称**（本轮新发现 T13）：后者返回 `cover_ok`/`icon_ok`，前者不含，导致「补全路径缺图」在 UI 完全不可见。已对齐。
- **代码状态**: 本轮改动尚未提交（工作区改动：`booth_core.py` / `archive_util.py` / `main_window.py` / `pages/updater.py` / `pages/settings_page.py` / `pages/links_page.py` / `README.md` / `LICENSE.txt` / `.gitignore` / `.gitattributes`；新增 `archive/` 51 项 + `docs/boothkeeper/v1/review/` 2 份；`assets/logo/` 3 项入库）。P0 的 `0faa030` 已 push，本轮提交后需再次 push。合并前请先 `git pull`。
- **状态**: ✅完成（P0 + P1 + P2 全绿；T8/T9/T11 余项已入 P3 登记）
- **下一步**: ①提交并推送本轮改动（公开仓库，若主上要求可再确认一次）；②P3 四项（`booth_core` 拆分 / QThread 重构 / 回滚路径加固 / 异常统一上报通道）待主上决定是否立项；③`LICENSE.txt` 的 GitHub `spdx_id` 变化需推送后由 GitHub 重新扫描确认。

---

## [v1]-raphael-20260927-0050 devskill 规范接入与文档骨架 — 2026-09-27 00:50 开始

- **执行者**: 拉斐尔（WorkBuddy Agent，机器：DESKTOP-N3O6SC2）
- **目标**: 完成 plan.md 的 P0 全部执行项——置入 devskill 规范本体、项目化 AGENT.md、建立 docs/ 文档体系与红线登记。对应验收 A1~A10。
- **上下文**: 主上委派「按你说的作为可试点置入 BoothKeeper 试试」。前置事实：仓库截至 1.5.6 无任何 docs/ 体系；根目录散落 22+ 个一次性脚本（部分已入库）、13 份 `rel_v*.md`、5 份 `SCORE_TABLE_*.md`；`git status` 有 17 项未跟踪。规范源取自 `D:\Lin_Agent\WB-WorkSpace\Github\ClaiDevSkill`（经 `gh api` 逐文件拉取，因本机 git 走 127.0.0.1 代理不通）。
- **进展**:
  1. 置入 `devskill/`（8 个文件）到仓库根，源与目标逐字一致。
  2. 建立 `docs/REGISTRY.md`，登记 `docs/boothkeeper/v1/` 板块一行。
  3. 建立 `docs/boothkeeper/v1/`：`00-README.md`（总览+文档地图+红线索引）、`01-流程规范接入.md`（五段需求，含 10 条可复核现象）、`plan.md`（P0~P2、逐项验收口径）、`BOUNDARY.md`（B-1~B-5）。
  4. 逐字拷贝 `DISCIPLINE.md` / `WORKLOG-PROTOCOL.md` 进 `v1/`。
  5. 项目化根目录 `AGENT.md`（替换占位、改写项目硬约束 5 条、补接手协议）。
  6. 建本 worklog 文件与 `review/` 目录占位。
- **验证**（2026-09-27 实测，全部通过）:
  - `diff -r devskill/ D:/Lin_Agent/WB-WorkSpace/Github/ClaiDevSkill/devskill/` → 无输出（A1 PASS）
  - `diff docs/boothkeeper/v1/DISCIPLINE.md devskill/DISCIPLINE.md` 与 `WORKLOG-PROTOCOL.md` 同理 → 无输出（A4 PASS）
  - `rg '<[^>]{2,}>' AGENT.md` → 无命中（A2 PASS）
  - `find docs -type f` → 9 个文件就位（A3 PASS）
  - `QT_QPA_PLATFORM=offscreen` 实例化 BoothKeeper → `title= Booth Keeper v1.5.6`，`pages= 5`（A10 PASS，功能零回归）
- **决策与坑**:
  - 历史不追补：1.0~1.5.6 的需求文档与 worklog 不回填（成本极高且会引入推测内容），改为「从现在起生效」。已记入需求文档 §3 取舍表。
  - 领域维度选单领域 `docs/boothkeeper/`，不拆多领域——单体桌面应用在当前规模下多领域拆分只增加路径决策成本。
  - 根目录存量脚本采「归档到 `legacy/oneoff/` 而非删除」（可追溯），且须用户确认清单后执行，故 P1 首项标 `[~]`。
  - P2-3（代理默认值改为直连）会改变网络行为，标为「待用户拍板」，未擅自执行。
  - 本次顺序瑕疵如实记录：P0 的脚手架与 `plan.md` 系同步建立（plan 写成时 P0 产物已就位），因此 P0 各勾选凭据为「产物已存在且可复核」，而非「先写 plan 再执行」。后续阶段严格按「先 plan 后执行」。
- **代码状态**: `已本地 commit 30e06f8（boothkeeper@main，18 文件）`；**未 push**（`main...origin/main [ahead 1]`）。公开仓库，推送前待用户确认。合并前请先 `git pull`。
- **状态**: 🔄进行中（P0 除 push 外全部完成；P1/P2 未开工）
- **下一步**: ①确认是否 push `30e06f8` 至 origin/main；②确认 P1 归档清单（根目录 22+ 一次性脚本 / 13 份 `rel_v*.md` / 5 份 `SCORE_TABLE_*.md` 的保留-归档-删除建议表）；③P2-3 代理默认策略（现默认走 `127.0.0.1:20122`）是否改为默认直连。
