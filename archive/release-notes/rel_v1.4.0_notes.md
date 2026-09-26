# Booth Keeper v1.4.0 — 修复归档 AttributeError（真正根因）

## 修复
- **归档不动文件（真正根因）**：`search_page.py` 调用 `bc.find_existing_source_in_library(...)`，但该函数定义在 `archive_util` 模块里，`booth_core` 里没有。每次调用都抛 `AttributeError`，被 Qt 事件循环静默吞掉 → `archive()` 直接退出 → 文件不移动。
- 现已从 `archive_util` 正确导入 `find_existing_source_in_library`，归档链路恢复正常。

## 说明
- v1.3.8~v1.3.9 的路径解析、拖放、兜底等修复均保留
- 保留调试日志（`~/.boothkeeper_archive_debug.log`），确认正常后后续版本移除

## 两种下载
- **Windows 安装包** `BoothKeeper_Setup_1.4.0.exe`（77 MB）
- **zip 解压即用** `BoothKeeper_portable_v1.4.0.zip`（76 MB）
