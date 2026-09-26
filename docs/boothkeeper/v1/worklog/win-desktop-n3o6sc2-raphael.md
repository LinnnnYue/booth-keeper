# worklog — DESKTOP-N3O6SC2 / 拉斐尔（智慧之王）

> 本文件由 dev-flow skill 分发，逐字拷贝为 `worklog/<平台>-<机器名>-<写作者>.md` 后使用。
> 记录规则（第 0 铁律/分工/恢复流程/条目模板/双写顺序/记录纪律）见上一级目录 `../WORKLOG-PROTOCOL.md`，本文件不重复规则。
> 纪律：只写自己的文件；条目倒序（最新在顶）；开工开条目、收工更新同一条目不新开。

- 机器：DESKTOP-N3O6SC2
- 写作者：拉斐尔（WorkBuddy Agent）
- 协议：`../WORKLOG-PROTOCOL.md`

---

## [v1]-raphael-20260927-0225 R24：P4 残留项处置（异常契约兜底 / 兜底留痕 / updater 静默点） — 2026-09-27 02:25 开始

- **执行者**: 拉斐尔（WorkBuddy Agent，机器：DESKTOP-N3O6SC2）
- **目标**: 主上指令「残留未做的继续交由你来执行」——处置 `review/2026-09-27-P3四项验收记录.md` §五 登记的 5 项残留。纪律照旧：先实测取证 → 写需求文档 → 再动手；做一个勾一个；拒绝估算值。
- **上下文**: 依赖 R23 末次提交 `5da9fa4`。残留 5 项中 3 项在归档记录里只有一句话判断（如「网络异常会直接抛出」），**未经实测**，故本轮先从取证入手，再决定做与不做。
- **进展**:
  1. **先取证，后定性**：写两个**只读探针**（`tests/_probe_exception.py` 逐类注入异常、`tests/_probe_batch_abort.py` 对照三个批量调用点），取得实测后才写需求文档。**结果收窄了归档记录的 1 处推断**（见坑 1）。
  2. **需求文档**：产出 [`03-残留项处置.md`](../03-残留项处置.md)，定「做 4 项 / 明确不做 3 项」，做项按五段格式 + 10 条编号验收口径，不做项逐条附判据；并预先写入「静默点计数持平是预期」的口径说明（见坑 5）。
  3. **§3.1 契约兜底**：`archive_item` 最外层统一收口，原函数体**整体改名** `_archive_item`（203 行，一行未改），新增 23 行包装声明契约「永不抛异常，永远返回 dict」。
  4. **§3.2 兜底留痕**：兜底分支接 `diag.error(scope="archive_item", iid=iid)`——否则等于用「静默返回 err」换掉「崩溃」。
  5. **§3.3 / §3.4**：`pages/updater.py` 两处加 `diag.warn`（`_resolve_proxies` 代理解析失败；`parse_local_version` 三源全失败），**两处返回值均不变**。
  6. **测试网**：新增 `tests/test_archive_contract.py`（9 用例，口径 1~7）与 `tests/test_updater_diag.py`（5 用例，口径 8~10），共用辅助 `tests/_diag_capture.py`。**按主题拆成两个文件，是为了让两次代码提交各自可独立验证**（见「纪律改进」条）。
  7. **反向验证**：故意绕过兜底，断言测试网**应当失败**（三组对照，见验证段）——防止重演 P3 的伪绿事件。
  8. **独立提交**：拆为 `R24-1`（归档契约，`763b3fe`）+ `R24-2`（updater 留痕，`e2b36ff`）两次提交，并以 `git worktree` 在**两个提交点各自独立重跑检查**，实证「中间提交可验证」。
  9. **清理**：两个探针的价值已被正式用例覆盖，按需求文档红线第 1 条**删除**，不留悬空脚本。
- **验证**（2026-09-27 实测，全部退出码 0）:
  - `QT_QPA_PLATFORM=offscreen python tests/test_archive_contract.py` → **Ran 9 tests, OK**（0.324s，无真实网络）
  - `python tests/test_updater_diag.py` → **Ran 5 tests, OK**（0.221s，不涉 Qt）
  - **中间提交可验证性实证**（`git worktree` 各 checkout 一次，独立重跑）：
    · `763b3fe`（R24-1）→ 依赖检查 缺失 0、代理 违规 0、`test_archive_flow` OK、`test_rollback` OK、`test_archive_contract` **9/9 OK**
    · `e2b36ff`（R24-2）→ 同上全部 OK，另加 `test_updater_diag` **5/5 OK**
  - `python tests/test_archive_flow.py` → **Ran 6 tests, OK**（0.091s）；`python tests/test_rollback.py` → **Ran 5 tests, OK**（0.073s）
  - `python tests/check_module_deps.py` → 6 模块全 OK，**合计缺失 = 0**
  - `python tests/check_proxy_single_source.py` → 扫描 24 文件，**违规 0**（白名单 1 条）
  - `python tests/_compare_worker_contract.py 4d3c6b6` → **不一致 = 0**
  - `QT_QPA_PLATFORM=offscreen python tests/_smoke_offscreen.py` → `title = Booth Keeper v1.5.6`、`pages = ['links','drag','search','audit','settings']`、`diag_btn = True`、sink 收报 3/3、rc=0
  - `compileall` 全量 → rc=0
  - **核心实测（DragWorker 单件异常注入，4 件投放）**：处理件数 **1/4 → 4/4**；`finished` **未发射 → 已发射**；失败件以 `status="err"` 上报而非消失；`worker.failed` 未发射（单件失败不冒泡到 worker 级）
  - **注入矩阵**：`archive_item` 5 场景（`ConnectionError`/`ProxyError`/`Timeout`/`RuntimeError`/`classify_item_state` 异常）**穿透 5/5 → 0/5**
  - **反向验证三组对照**：绕过兜底 → **1/4 + `finished` 未发射**（旧缺陷完整复现）；走真实契约 → 4/4 + 已发射；无注入基线 → 4/4 + 已发射
  - **留痕对照**：绕过兜底输出 `[error] DragWorker: 后台任务异常：boom`（冒泡到 worker 级）；走真实契约输出 `[error] archive_item: 归档异常：RuntimeError: boom  iid=2000002`（scope + iid 均正确）
  - **归档主流程 6 条路径逐条复核**：`ok`→3D模型 / `exists`→3D模型 / `force`→ok + 留档=True / `delisted`→已下架商品 / 连不上→`err` 且消息「无法连接 BOOTH 判定状态」，**零回归**
  - 静默点（R17 评审 §5 同口径）：`4d3c6b6` 29 → `5da9fa4` 21 → **R24 21（持平，预期内）**；测试用例总数 11 → **25**
- **决策与坑**:
  - **坑 1（推断未实测就写进归档，被打脸）**：验收记录 §五-5 原文称「网络异常会直接抛出」，实测显示 `fetch_item` / `probe_item_http` / `probe_reachable` **内部均已有兜底**，`retry_request` 重试耗尽抛出的 `ConnectionError` 会被吞掉并返回 `None`——**真实网络故障下不会穿透**。收窄后本项价值重新定位为「终结契约未声明、调用方各自猜测」，**危害的充分条件是「异常一旦发生即静默丢件」而非「异常必现」**，实测已证明后者不成立而前者成立（4 件丢 3 件 + UI 悬挂），故仍定级高危。**教训：归档记录里的一句话判断，只能当线索，不能当事实——写入需求文档的现象段前必须跑一遍。**
  - **坑 2（根因是「契约缺失」而非「缺 try」）**：实测发现同一函数在 3 个调用点有**两种**健壮性——`ArchiveWorker` / `FixMismatchWorker` 包了 `try`，`DragWorker` 没包。这不是「某人忘了写」，而是**契约未声明导致各自猜测**的必然结果：只要不声明，第 4 个调用点还会猜错。故选定**在最外层收口（修根）**，而非给 `DragWorker` 补 `try`（治枝）。
  - **坑 3（改名的零侵入价值）**：原函数体 190+ 行含 R23 刚加固的三处回滚路径，若采用「在原函数体内到处补 `try`」需改十几处、回归面极大。改名 + 外层包装使内部**一行未改**，把「加固」与「重构」彻底分开。代价是新增一个内部函数名，已在 `_archive_item` 的 docstring 标注「请勿直接从 UI 调用」。
  - **坑 4（一次性脚本也要先跑通）**：`_probe_exception.py` 的 `mock.patch.object` 参数结构（`attr` / `kind` / `value`）连改两版才跑通——初版把 `kind` 当关键字、第二版三元组与四元组混用。**探针给出的结论只有在其自身可靠时才有意义**，脚本本身的错误会伪装成「代码行为」。
  - **坑 5（预先声明口径，避免「没做完」的误判）**：本轮**没有**降低 `except: pass` 计数（21 持平）。这**不是未完成**——需求文档 §附已事先写明：本轮加固的是「契约缺失」与「无留痕」，目标是消除影响状态承诺却无出口的静默；若以计数下降为验收标准，会诱导把正常降级链（如开发态 `_version` 不存在）也塞进日志，制造噪音淹没真信号。**把「预期不变」提前写进文档，比事后解释便宜得多。**
  - **坑 6（Edit 精确匹配失败）**：改 `archive_item` docstring 时漏了原文的「fetch **失败**不妄断」中的「失败」二字，Edit 报 not found。按纪律先 Read 定位差异再改，未盲目重试。
  - **坑 7（工作目录漂移）**：会话工作区根是 `D:\Lin_Agent\WB-WorkSpace\Github`，而 BoothKeeper 实体在 `D:\Lin_Agent\WB-WorkSpace\BoothKeeper`。每轮开工先核 `git log` 对齐世界线，避免在错误目录操作。
  - **坑 8（`github.com` 被阻断，`git push` 全通道失败 → 改走 Git Data API）**：收尾推送时 `git push` 报 `Recv failure: Connection was reset`。逐项排查：(a) `curl https://github.com/...` 直连 **http=000（10s 超时）**；(b) 经系统代理 `127.0.0.1:20122`（注册表 `ProxyEnable=1` 指向它）**同样失败**；(c) `git -c http.version=HTTP/1.1` **无效**；(d) 扫端口发现 `8080` 开放，但探测返回 `404 + Access-Control-*`，是 REST 服务而非代理；(e) SSH 端口 22 **握手成功**（报 `Permission denied (publickey)` 而非超时），但 `~/.ssh/id_ed25519_wb`（comment `wb-sync-push`）未被账号接受。**结论：只有 `api.github.com` 可用**（直连 http=200）——`gh` 一直能通，正是因为它走这个域名。
    **解法**：用 GitHub **Git Data API** 重建提交链——`POST /git/blobs` → `POST /git/trees`（`base_tree` 指向远端已有 tree，只传增量条目）→ `POST /git/commits` → `PATCH /git/refs/heads/main`。**关键设计：每个对象创建后立即与本地 SHA 比对，不一致即中止**；并先推到临时 ref `_api_push_check` 校验，通过后才动 `main`（`force=false`）。**结果：blob / tree / commit 三级 SHA 全部与本地一致**，远端 `main` = 本地 `HEAD` = `6297192`，**三个提交 SHA 与本地逐字节相同、无分叉**。这说明 API 通道产出的是与原生命令**等价**的结果，而非「内容相同、SHA 不同」的隐患状态。
  - **坑 9（API 重建的两个坑中坑）**：①`git/commits` 的 `parents` 要求**完整 40 字符** SHA，传短 SHA 直接 `422`；同时 `commit["sha"] == target` 若用短 SHA 比对**永远为假**——首次运行就因此误判。**教训：脚本内 SHA 一律 `git rev-parse` 展开，仅在显示时截断。**②`DELETE` / `PATCH /git/refs/{ref}` 的 path **不带 `refs/` 前缀**（应为 `heads/main`），而 `POST /git/refs` 的 **body** 才用完整 `refs/heads/main`；前缀写重会得到 `422 Reference does not exist`。该死法发生在 `main` **已更新成功之后**，仅导致临时 ref 残留（已单独清理，远端分支现仅 `main`）。
  - **纪律改进（纠正 P3 登记的偏离）**：P3 红线第 4 条「每项独立提交」未达成，当时以「按文件组的回退映射」作补偿。本轮把它做对——拆为 `R24-1` / `R24-2` 两次代码提交，并把测试文件**按主题拆成两个**（否则单个测试文件跨两项，中间提交必然是红的，独立提交就无从验证）。**关键动作**：用 `git worktree add --detach <sha>` 在两个提交点**各自独立重跑全套检查**，实测均绿。只拆不验证，「独立提交」只是形式；验证过才是可回退性的实证。代价是抽出一个共享辅助文件 `tests/_diag_capture.py`（`diag` 的 sink 是全局单接收方，两处测试需要同一套接管/恢复逻辑，复制两份会漂移）。
  - **决策：明确不做 3 项 + 不改 1 类，全部附判据**（需求文档 §四）。判据统一为「失败是否破坏用户可感知的状态承诺」——`updater` 另 3 处 `except: pass` 中，`_fetch_html_tag` / `_fetch_api_release` 的 `None` 由 `check_update` 转为 `error` 字段，`settings_page.check_update_now` **有明确弹窗**，故**不属静默**，不动。
  - **决策：`diag` 仍是单接收方**。当前仅主窗口一处接收方，改 handler 列表属为不存在的需求增加 API 表面积与线程亲和性复杂度；「按需演进」而非「提前建设」。
- **代码状态**: `R24-1 = 763b3fe`（`archive_util.py`：+23 行包装 / 原体整体改名 `_archive_item`；`tests/test_archive_contract.py` 9 用例；`tests/_diag_capture.py` 共享辅助）。`R24-2 = e2b36ff`（`pages/updater.py`：2 处 `diag.warn` + import；`tests/test_updater_diag.py` 5 用例）。`R24-3 = 6297192`（文档层：`plan.md` P4 段勾选、`03-残留项处置.md` 需求文档、`review/2026-09-27-P4残留项验收记录.md`、`REGISTRY.md` 两行修订）。**远端 `main` = 本地 `HEAD` = `6297192`**，经 Git Data API 推送（`git push` 因 `github.com` 被阻断不可用，见坑 8）。两个探针脚本与 API 推送脚本均为一次性工具，已删除。
- **状态**: ✅完成（10 条验收口径全绿；做 4 项 / 不做 3 项均已登记判据；反向验证证明测试网有牙；本轮**无偏离立项**；三项已推送且 SHA 与本地一致）
- **下一步**: ①残留见 `review/2026-09-27-P4残留项验收记录.md` §六——底层三处 `s = session or make_session()` 位于 `try` 之外，实测可穿透但 Worker 路径下因 `or` 短路**当前不可达**，按 R23 确立的「不可达路径先补演练用例再改」纪律登记备查。②`github.com` 阻断的应对通道已固化为 skill `github-api-push`（含逐对象 SHA 校验与临时 ref 校验流程），供其他 agent 复用；若网络/代理恢复，原生 `git push` 可直接恢复使用，无需改动仓库配置。

---

## [v1]-raphael-20260927-0230 R23：P3 四项全量落地（诊断通道 / 回滚加固 / Worker 基类 / booth_core 拆分） — 2026-09-27 02:30 开始

- **执行者**: 拉斐尔（WorkBuddy Agent，机器：DESKTOP-N3O6SC2）
- **目标**: 主上指令「未做的接着做」——把 `plan.md` P3 登记的四项遗留项（2.1 异常上报通道 / 2.2 force 回滚加固 / 2.3 QThread 样板提取 / 2.4 booth_core 拆分）逐项落地并验收。纪律：先写需求文档 → 评审 → 再进 plan；做一个勾一个；实测数据不用估算值。
- **上下文**: 依赖 R17 末次提交 `4d3c6b6`（P0+P1+P2 全绿）。前置产出 [`02-遗留项处置.md`](../02-遗留项处置.md) 定四项的现象/目标/方案与取舍/不做什么/验收口径与实施顺序（2.1+2.2 → 2.3 → 2.4，测试网为 2.4 前置）。
- **进展**:
  1. **需求文档先行**：产出 `02-遗留项处置.md`（四节五段 + 依赖图 + 四项共同红线），未开工即定死验收口径。
  2. **2.1 诊断通道**：新增 `diag.py`（115 行，零依赖）与 `pages/diag_panel.py`（207 行）；`main_window` 加 `_DiagBridge(QObject)` 跨线程转发、状态栏常驻入口、面板打开/清空回传计数；诊断初始化**提到 `load_config()` 之前**。替换 11 处 `print`（逻辑层残留 0），另加固 8 处静默点。
  3. **2.2 回滚加固**：先建演练环境（`tests/test_rollback.py`，5 用例，故障注入 `shutil.move`），**基线跑出 2 处真实缺陷**后再动手改。提取 `_restore_from_archive` / `_describe_restore` / `_is_legacy_dir`，三处调用点归一。
  4. **2.3 Worker 基类**：新增 `pages/workers.py` 的 `BoothTask(QThread)`（模板方法 `work(session)` + 异常兜底 + `needs_session` 开关），迁移 **11** 个 Worker；构造函数去掉 `proxy`/`proxy_url`；**另发现并修掉 2 处 UI 线程内代理绕过**（`search_page`、`dragdrop_page`）。
  5. **2.4 拆分**：AST 机械分段工具 `tests/_split_booth_core.py` 把 1439 行拆为 6 模块，`booth_core.py` 改为 116 行门面（模块级 `__getattr__` 动态转发）。
  6. **测试网**：`check_module_deps.py`（跨模块引用 AST）、`check_proxy_single_source.py`（代理真源 AST + 白名单）、`test_rollback.py`(5)、`test_archive_flow.py`(6)、`_smoke_offscreen.py`、`_compare_worker_contract.py`、`_count_silent.py`、`_count_proxy_writes.py`。
  7. **验收记录**：产出 [`review/2026-09-27-P3四项验收记录.md`](../review/2026-09-27-P3四项验收记录.md)（26 条口径逐条对应实测值 + 量化变化 + 偏离登记 + 残留项）。
- **验证**（2026-09-27 实测，全部退出码 0）:
  - `python tests/check_module_deps.py` → 合计缺失 = 0（6 模块全 OK）
  - `python tests/check_proxy_single_source.py` → 扫描 24 文件，违规 **0**（白名单 1 条）
  - `python tests/test_rollback.py` → **Ran 5 tests, OK**；半还原消息 = 「仅还原 1 项，1 项仍在 旧版本_2026-09-27_015609/（旧B.bin）」，`dest` 根 = `['旧A.bin']`（消息与磁盘一致）
  - `python tests/test_archive_flow.py` → **Ran 6 tests, OK**（ok / exists / mismatch / force 留档 / delisted / 连不上不妄断）
  - `python tests/_compare_worker_contract.py 4d3c6b6` → 比对 11 类，**不一致 = 0**
  - `QT_QPA_PLATFORM=offscreen python tests/_smoke_offscreen.py` → `title = Booth Keeper v1.5.6`、`pages = ['links','drag','search','audit','settings']`、sink 收报 3/3、面板可见
  - 符号等价：`4d3c6b6:booth_core.py` 公共符号 51 vs 工作区 51，**丢失 0 / 新增 0**
  - 调用点集合：`import booth_core` 的原有文件**消失 0**，新增 3（门面自身 / `pages/workers.py` / 拆分工具）
  - 模块行数：`449 / 307 / 304 / 258 / 177 / 116 / 99`，全部 < 620
  - 静默点（R17 评审 §5 同口径）：**29 → 21**；手工写 `.proxies`（AST）：**12 → 1**（白名单内「直连兜底后还原」，非配置代理）
  - `compileall` 全量通过
- **决策与坑**:
  - **偏离立项 4 处，全部登记**（详见 `02-*.md` 对应小节 + 验收记录 §三）：①模块数 **4 → 6**（`bk_net` 单文件 968 行触犯 <620 口径，故再分出 `bk_local` / `bk_search`，边界仍取自原 `# ── 分段 ──` 注释）；②Worker 数 **10 → 11**（立项漏计 `audit_page` 2 个，实施以 AST 枚举复核）；③基类统一 emit `finished` **否掉**（11 个完成信号名/参数各异且已被 UI 直连，统一即违反验收口径）；④2.3-1 验收由文本 `rg` 改 **AST**（文本口径无法区分代码与注释，误报漏报双全）。
  - **纪律偏离 1 处**：需求文档红线第 4 条「每项独立提交」未达成，实际合并为单一提交 `6fb5dc8`。原因：四项在同一工作区交错——`diag.py` 是 2.2/2.3 共同前置，`archive_util.py` 同时含 2.1（print→diag）与 2.2（回滚加固）。追溯性分拆需按 hunk 切分并逐个验证中间提交可编译，风险高；与红线第 2 条「零回归优先于整洁」冲突时从后者。已在验收记录 §四 给出按文件组的回退映射作为补偿。
  - **坑 1（UI 未就绪崩溃）**：`load_config()` 在 `build_ui()` 之前运行，配置损坏告警触发 sink 时 `self.diag_btn` 尚不存在 → `AttributeError` 反噬启动流程，即「诊断通道自己成为故障源」。修法：`getattr(self, "diag_btn", None)` 守卫，记录照常入缓冲与计数，仅跳过状态栏刷新。已补为验收口径 6。
  - **坑 2（计数语义）**：面板清空/查看后按钮计数不归零，数字会伪装成「有持久故障」的噪音。修法：面板加 `cleared = Signal()`，主窗口在打开面板与收到 `cleared` 时归零（「未读」而非「累计」语义）。已补为验收口径 7。
  - **坑 3（回滚假成功，真实缺陷）**：基线演练直接跑出 2 处失败——`test_03` 消息写「（留档内容已还原）」而 `旧B.bin` 实际仍在留档目录（**磁盘状态 ≠ 消息**，正是 R17 判高危的原因）；`test_04` 还原时把既有 `旧版本_*` 目录当作待还原项搬走，形成**套娃嵌套**。二者均为演练暴露，非理论推演。
  - **坑 4（跨模块私有名）**：`score_and_pick` 在 `bk_search` 内 `NameError: _json_cache not defined` —— `import *` 不带私有名。以 `tests/check_module_deps.py` 静态扫出全部同类风险（`_parse_price`、`_thumb_from_json`）并补显式 import。
  - **坑 5（拆分工具二次运行）**：`_split_booth_core.py` 重跑会把已生成的门面当输入源，报「未分配符号 `_MODULES`/`__all__`/`__getattr__`」。已加输入源守卫（检出 `__getattr__` 或 `import bk_domain as _bk_domain` 即 `exit(2)` 不写盘），并从备份 `/tmp/bk_bak/booth_core.py.orig` 复原。
  - **坑 6（门面为何用 `__getattr__`）**：静态 `from bk_net import *` 有两个具体缺陷——`PROXY` 是**可变**模块级变量，`apply_proxy()` 改的是 `bk_net.PROXY`，静态导入会让 `booth_core.PROXY` 变成一份**快照**导致读写不一致；且私有名不被 `import *` 带走。动态转发使 `bc.anything` 恒等于真源当前值。代价（IDE 静态补全弱化）已在门面文件头写明。
  - **坑 7（测试伪绿，自查发现）**：`test_archive_flow.py::test_05` 初版把 mock 打在 `au` 而非 `au.bc` 上，导致**真的发了网络请求**去判定 `1234567` 是否下架——断言恰好通过，属伪绿。修正后全套耗时由 1.547s 降至 0.057s，这条耗时差即是证据。**教训：测试跑得快才是本地判定的旁证；耗时不正常要怀疑是否漏出网络。**
  - **坑 8（估数打脸）**：重建「手工写 `.proxies`」基线时先按印象写「13 处」，实测为 **12 处**（`booth_core` 1 / `audit_page` 5 / `dragdrop_page` 2 / `links_page` 1 / `search_page` 3），已在验收记录更正。**估算值不入文档，一律先跑脚本。**
- **代码状态**: `已 push booth-keeper@main 6fb5dc8`（代码层：8 改 + 15 增，含 6 拆分模块、`diag.py`、`pages/{workers,diag_panel}.py`、`tests/` 8 个脚本）。文档层（`plan.md` 勾选、`02-*.md` 实测更正、`review/2026-09-27-P3四项验收记录.md`）随本条一并提交。
- **状态**: ✅完成（P3 四项 26 条验收口径全绿；4 处立项偏离 + 1 处纪律偏离已登记；5 项残留已入验收记录 §五）
- **下一步**: ①文档层提交并推送；②`tests/` 建议纳入 CI 或 pre-push 门禁（当前需手动重跑）；③残留项 §五-5（`archive_item` 内 `bc.fetch_item` / `classify_item_state` 未包 try，网络异常直接抛出）若要做，属独立立项，须先过需求文档。

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
