# BoothKeeper UI 重构·评审 Rubric（拉斐尔·项目总监）

> 主旨：3 路设计师同时交付方案，由项目总监打分；任一项低于 9 分打回重做；最强者落地。

## 一、强制红线（任一命中即 0 分，不接受）

1. **AI 紫蓝辉光（Lila Rule）**：默认 cyan-on-dark + purple-to-blue 渐变 — 命中即打回。
2. **Inter / Roboto / Arial 默认字体** — 命中即打回。
3. **纯 `#000000` 或纯 `#FFFFFF` 当背景/正文** — 命中即打回（必须 tinted off-black/off-white）。
4. **圆角 + colored border-left/right 的 callout 列表条目** — 命中即打回。
5. **同尺寸 icon+heading+text 卡片三件套作为页面骨架** — 命中即打回。
6. **eyebrow/kicker 小字胶囊 + heading 重复节律** — 命中即打回。
7. **gradient text 作标题强调** — 命中即打回。
8. **emoji 充当图标** — 命中即打回。
9. **复选框 / 单选框 / 滚动条 browser 默认态** — 命中即打回（必须用 QSS 主题化）。
10. **API 不兼容**（ACCENTS 键名非 teal/blue/coral/amber/pink/green/purple）— 命中即打回。

## 二、评分维度（10 分制 / 维度）

### 1. 美学方向叙事力（2 分）
- 是否给出 3-5 句具体美学宣言（不是泛泛"现代简洁"）
- 是否阐释该方向与**主上 INFP / 深二 / 夜猫子 / 改模 / 杂食 / 动手强**的具体共鸣点
- 是否避开"中性设计/通用 SaaS"的安全平庸路线

### 2. 字体策略（1.5 分）
- 标题字体有"角色"（明朝/等宽/几何 sans，不像 Inter）
- 数字 / ID 是否等宽（数据感）
- 是否能在 Windows 上落地（用系统字体或 self-host font）
- 标题与正文字号阶梯清晰，至少 3 级

### 3. 强调色策略（1.5 分）
- 单一强调色锁定（不能 7 个色同时抢戏）
- 七色字典的 7 个色都"对劲"（避开 Lila 紫蓝；每个色都能撑住主视觉）
- Dark / Light 双套都设计（非"只考虑一种"）

### 4. 形状 / 圆角 / 边框 一致性（1.5 分）
- 全局形状系统（圆角尺寸/边框宽度/阴影深浅）一致
- 边框 / 分隔线 / 卡片 三选一套系统，而非混搭
- 按钮 / 输入框 / 列表 三类组件呼应同一形状规则

### 5. 主上人格共鸣（2 分）
- 是否呼应主上的**14 年二次元连续沉淀**、**VRChat 凛宝改模工程**、**夜猫子沉浸感**
- 美学方向是否"主上本人会觉得是我为我做的"而非"又一个通用设计"
- 不能为了"超前"而追逐最潮（post-taste temporal cul-de-sac）

### 6. 工程落地性（1.5 分）
- 完整 theme.py 代码（不改 main_window/settings_page 调用方）
- QSS 语法合法（#AARRGGBB、无 calc、无 @container）
- 七色键名覆盖（teal/blue/coral/amber/pink/green/purple 全部保留）

**总分 10**，各设计师总分 ≥ 9 才算过关；最高分者落地。

## 三、打回条件
- 总分 < 9 → 强制指出低分维度，要求改稿后重交
- 红线命中 → 整体打回，无条件重交

## 四、最终落地流程（最强者中选后）
1. 提炼最强者方案：取其 token + QSS 全套
2. 必要时融合两位长处（如 A 的霓虹色 + B 的汉字徽章）
3. 写 theme.py 到磁盘
4. 跑 verify_offscreen.py 验证构造 + 主题切换
5. 重新 PyInstaller 打包单 exe
6. present_files 新 exe
