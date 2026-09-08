# BoothKeeper 1.5.5 发版记录

> 2026-09-08 · R24 黄色图标根治版

## 本次修复：目录图标「补 S 后仍黄」真根因

**现象**：部分文件夹（尤其拖拽分类归档的）即使补了 System 标志、重启电脑后，
Explorer 里仍是黄色默认文件夹图标（只显示「上半图片预览 + 黄色文件夹」）。

**根因（26 目录指纹审计 + shell 层铁证）**：
- 这批目录的 `desktop.ini` 是**旧版裸格式**——只有 `[.ShellClassInfo]` + `IconResource`
  两行，**缺 `[ViewState] FolderType=Generic` 段和 `IconIndex=0` 行**。
- Windows shell 只认带 `[ViewState]` 的**标准格式** desktop.ini（资源管理器
  「更改图标」写出的形态）。裸格式被静默忽略 → 图标永不生效。
- 审计数据：黄名单 26 目录 vs 对照 196 目录在属性/BOM/ico 结构等全部维度零差异，
  唯独 desktop.ini 缺段是隐藏判别特征（此前 S 位修复假设因此失效）。

**修复**：
1. `booth_core.py` 新增模块常量 `DESKTOP_INI_STANDARD`
   （`[ViewState]` + `FolderType=Generic` + `IconResource` + `IconIndex=0`，CRLF）
   —— `make_folder_icon` / `normalize_desktop_ini` / `fix_folder_system_attr` 单一来源。
2. 新增 `normalize_desktop_ini()`：幂等归一化——老格式 desktop.ini 重写为标准格式
   （标准格式是裸格式超集，无信息丢失），已是标准格式则不动。
3. `fix_folder_system_attr()` 升级为「补 S + ini 归一化」双修，返回 `normalized` 计数；
   audit 页按钮改「一键修复黄色图标（补S+ini归一化）」。
4. 全库 367 个目录已归一化（20 个潜伏老格式被重写，347 个已是标准格式），
   26 个用户反馈目录重写后**全部立即恢复**（用户当场确认）。

**测试**：`test_folder_icon_fix.py` 4/4 通过（标准格式输出 / 老格式修复 / 幂等 / force 保留 S）。

## 附：上一版 1.5.4 内容回顾
- 拖拽分类左右分栏；成功项移出待归档队列（补 data 匹配，根除「归档完还在队列」）
- force 重归档改同位置 `旧版本_日期` 子目录留档（旧内容永不删除）
- 打包配置换回最初 app_icon 图标

## 两种下载
- **Windows 安装包** `BoothKeeper_Setup_1.5.5.exe`（73.9 MB）
- **zip 解压即用** `BoothKeeper_portable_v1.5.5.zip`（73.1 MB，CRC 校验完好）
