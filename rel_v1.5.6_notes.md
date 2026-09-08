# BoothKeeper 1.5.6 发版记录

> 2026-09-08 · 收款码可扫码修复版

## 本次修复：捐赠二维码无法扫码定位

**现象**：设置页「支持作者」嵌入的微信收款码图片自 1.3.4 commit 引入起 finder pattern（定位块）即被破坏，**所有 QR 解码器（OpenCV QRCodeDetector / pyzbar）都识别失败**；手机微信扫码同样无法定位。

**根因**：原 `assets/donate_qr.png`（1.3.4 commit 引入至今未变）整图最长水平连续黑带仅 110 px，而标准 QR 三个 finder pattern 第 1 行至少需 200 px 全黑横带才能定位。

**修复**：
- 替换为新捐赠码主图（575×575 RGBA PNG，圆角绿框、头像、✓ 徽标）
- pyzbar 解码验证：`wxp://f2f0SdcUHgETIY_5MW8U2iG98R7kCyiopIWz7TCKYMinwITkIaJ2LEjWe2khChCq6EjK`（合法微信收款码 URL）
- finder 位置：`Rect(left=62, top=62, width=448, height=450)`（标准 7 modules 位置）

## 两种下载
- **Windows 安装包** `BoothKeeper_Setup_1.5.6.exe`
- **zip 解压即用** `BoothKeeper_portable_v1.5.6.zip`
