# pages/settings_page.py — 设置
import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (QLabel, QPushButton, QLineEdit, QCheckBox, QFrame,
    QFileDialog, QHBoxLayout, QVBoxLayout)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from pages.base import BasePage
from pages.notify import ThemeDialog
import theme


def asset_path(name: str) -> str:
    """定位资源：开发模式 BoothKeeper/assets/，打包模式 <sys._MEIPASS>/assets/。"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'assets', name)
    return os.path.join(os.path.dirname(__file__), '..', 'assets', name)


class SettingsPage(BasePage):
    def __init__(self, main):
        super().__init__(main)
        self.header("设置", "主题、归档路径与网络")

        # 主题（三选一，整套视觉意境切换）
        self.add_label("主题（三选一，整套视觉意境切换）")
        self.theme_row = QHBoxLayout()
        self.theme_btns = {}
        for key, name in theme.THEME_NAMES.items():
            accent = theme.THEMES[key]["light"]["accent"]
            b = QPushButton(name)
            b.setFixedSize(72, 38)
            b.clicked.connect(lambda _, k=key: self.pick_theme(k))
            b._accent = accent
            self.theme_btns[key] = b
            self.theme_row.addWidget(b)
        self.root.addLayout(self.theme_row)
        self.mark_theme()

        self.hline()

        # 明暗（亮色 / 深色）
        self.add_label("明暗（亮色 / 深色）")
        mode_row = QHBoxLayout()
        self.mode_btns = {}
        for key, name in (("light", "亮色"), ("dark", "深色")):
            b = QPushButton(name)
            b.setFixedSize(72, 38)
            b.clicked.connect(lambda _, k=key: self.pick_mode(k))
            self.mode_btns[key] = b
            mode_row.addWidget(b)
        self.root.addLayout(mode_row)
        self.mark_mode()

        self.hline()

        # BOOTH 根目录
        self.add_label("BOOTH 归档根目录")
        root_row = QHBoxLayout()
        self.edit_root = QLineEdit(self.main.config["booth_root"])
        self.btn_browse = QPushButton("浏览")
        self.btn_browse.setObjectName("secondary")
        self.btn_browse.clicked.connect(self.browse_root)
        root_row.addWidget(self.edit_root, 1)
        root_row.addWidget(self.btn_browse)
        self.root.addLayout(root_row)

        # 代理
        self.add_label("网络代理（访问 Booth 多数需代理）")
        self.chk_proxy = QCheckBox("启用代理")
        self.chk_proxy.setChecked(bool(self.main.config["proxy"]))
        self.chk_proxy.stateChanged.connect(self.on_proxy_toggle)
        self.root.addWidget(self.chk_proxy)
        self.edit_proxy = QLineEdit(self.main.config["proxy_url"])
        self.edit_proxy.setEnabled(bool(self.main.config["proxy"]))
        self.root.addWidget(self.edit_proxy)

        # Cookie
        self.add_label("Booth Cookie（可选，访问受限商品）")
        self.edit_cookie = QLineEdit(self.main.config.get("cookie", ""))
        self.edit_cookie.setEchoMode(QLineEdit.Password)
        self.edit_cookie.setPlaceholderText("留空即可，仅在受限时填写")
        self.root.addWidget(self.edit_cookie)

        # R10：自动检查更新
        self.add_label("自动检查更新（启动时）")
        self.chk_auto_update = QCheckBox("启动 BoothKeeper 时自动检查新版本")
        self.chk_auto_update.setChecked(bool(self.main.config.get("auto_check_update", True)))
        self.root.addWidget(self.chk_auto_update)

        self.btn_check_update = QPushButton("立即检查更新")
        self.btn_check_update.setObjectName("secondary")
        self.btn_check_update.clicked.connect(self.check_update_now)
        self.root.addWidget(self.btn_check_update)

        self.hline()
        save = QPushButton("保存设置")
        save.setObjectName("accent")
        save.clicked.connect(self.save)
        self.root.addWidget(save)

        # R8：支持作者（爱发电 + 微信收款码）
        self.hline()
        self.root.addSpacing(8)
        support_title = QLabel("☕ 支持作者")
        support_title.setObjectName("pageTitle")
        self.root.addWidget(support_title)

        intro = QLabel(
            "本工具由主上自用分享，永久免费开源。\n"
            "如果帮到了你，欢迎扫码支持继续维护 ✨")
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        self.root.addWidget(intro)

        # 二列布局：左侧 QR 码 + 右侧爱发电链接 / GitHub stars
        support_row = QHBoxLayout()
        support_row.setSpacing(20)
        support_row.setAlignment(Qt.AlignTop)

        # QR 码（固定 140x140，确保扫码识别率）
        qr_label = QLabel()
        qr_path = asset_path("donate_qr.png")
        if os.path.exists(qr_path):
            pm = QPixmap(qr_path)
            if not pm.isNull():
                pm = pm.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                qr_label.setPixmap(pm)
        qr_label.setFixedSize(148, 148)
        qr_label.setAlignment(Qt.AlignCenter)
        qr_label.setStyleSheet(
            "background-color: transparent;"
            "border: 1.5px solid ACCENT_PLACEHOLDER;"
            "border-radius: 4px;".replace("ACCENT_PLACEHOLDER", "#888"))
        support_row.addWidget(qr_label)

        # 右侧链接与说明
        info_col = QVBoxLayout()
        info_col.setSpacing(6)

        afdian_label = QLabel(
            '<a href="https://afdian.com/a/LinnYue" style="color: #888;">'
            '<b>爱发电 · LinnYue</b></a>')
        afdian_label.setOpenExternalLinks(True)
        afdian_label.setTextFormat(Qt.RichText)
        afdian_label.setStyleSheet("font-size: 13px;")
        info_col.addWidget(afdian_label)

        gh_label = QLabel(
            '<a href="https://github.com/linnnnnnnnnnnnnnnnnnnnn/booth-keeper" '
            'style="color: #888;"><b>GitHub · 点 ⭐ 鼓励</b></a>')
        gh_label.setOpenExternalLinks(True)
        gh_label.setTextFormat(Qt.RichText)
        gh_label.setStyleSheet("font-size: 13px;")
        info_col.addWidget(gh_label)

        wechat_hint = QLabel("微信扫一扫（左）")
        wechat_hint.setObjectName("muted")
        wechat_hint.setStyleSheet("font-size: 11px;")
        info_col.addWidget(wechat_hint)

        sponsor_note = QLabel(
            "赞助全部用于支付 LLM API 费用 + 服务器，\n"
            "主上承诺：本工具永不开源化收费。")
        sponsor_note.setObjectName("muted")
        sponsor_note.setWordWrap(True)
        sponsor_note.setStyleSheet("font-size: 11px;")
        info_col.addWidget(sponsor_note)

        info_col.addStretch(1)
        support_row.addLayout(info_col, 1)

        self.root.addLayout(support_row)
        self.root.addSpacing(12)

        self.spacer()

    def add_label(self, t):
        l = QLabel(t)
        l.setObjectName("pageSub")
        self.root.addWidget(l)

    def mark_theme(self):
        cur = self.main.config["theme"]
        for k, b in self.theme_btns.items():
            ac = b._accent
            if k == cur:
                b.setStyleSheet(
                    f"background-color:{ac};color:#FAFAFA;border:1px solid {ac};"
                    f"border-radius:2px;font-weight:600;")
            else:
                b.setStyleSheet(
                    f"background-color:transparent;color:{ac};border:1px solid {ac};"
                    f"border-radius:2px;")

    def pick_theme(self, k):
        self.main.config["theme"] = k
        self.main.save_config()
        self.main.apply_theme()
        self.mark_theme()
        self.mark_mode()
        self.main.set_status(f"主题已切换：{theme.THEME_NAMES[k]}")

    def mark_mode(self):
        cur = self.main.config.get("mode") or theme.DEFAULT_MODE_PER_THEME[
            self.main.config["theme"]]
        ac = theme.THEMES[self.main.config["theme"]][cur]["accent"]
        for k, b in self.mode_btns.items():
            if k == cur:
                b.setStyleSheet(
                    f"background-color:{ac};color:#FAFAFA;border:1px solid {ac};"
                    f"border-radius:2px;font-weight:600;")
            else:
                b.setStyleSheet(
                    f"background-color:transparent;color:{ac};border:1px solid {ac};"
                    f"border-radius:2px;")

    def pick_mode(self, k):
        self.main.config["mode"] = k
        self.main.save_config()
        self.main.apply_theme()
        self.mark_mode()
        self.main.set_status("明暗已切换：" + ("亮色" if k == "light" else "深色"))

    def on_proxy_toggle(self, state):
        self.edit_proxy.setEnabled(state == 2)

    def browse_root(self):
        d = QFileDialog.getExistingDirectory(self, "选择 BOOTH 根目录",
                                             self.edit_root.text())
        if d:
            self.edit_root.setText(d)

    def save(self):
        self.main.config["booth_root"] = self.edit_root.text().strip()
        self.main.config["proxy"] = self.chk_proxy.isChecked()
        self.main.config["proxy_url"] = self.edit_proxy.text().strip()
        self.main.config["cookie"] = self.edit_cookie.text().strip()
        self.main.config["auto_check_update"] = self.chk_auto_update.isChecked()
        self.main.save_config()
        self.main.apply_theme()
        self.main.set_status("设置已保存")

    def check_update_now(self):
        """立即检查更新：拉 GitHub latest release → 比版本号 → 提示。"""
        self.btn_check_update.setEnabled(False)
        self.btn_check_update.setText("检查中…")
        try:
            from pages import updater
            cfg = self.main.config
            info = updater.check_update(proxy=cfg.get("proxy", False))
            self.btn_check_update.setEnabled(True)
            self.btn_check_update.setText("立即检查更新")
            if info.get("error"):
                ThemeDialog.warning(self, "检查更新失败",
                    f"无法访问 GitHub API：\n{info['error']}\n\n"
                    f"请检查网络/代理设置。")
                return
            local, remote = info["local"], info["remote"]
            if info["has_update"]:
                msg = (
                    f"发现新版本！\n\n"
                    f"  当前版本：{local}\n"
                    f"  最新版本：{remote}\n\n"
                    f"点「确定」前往下载页面（Release 含 Windows 安装包 + zip 便携版）。")
                if ThemeDialog.confirmation(self, "有新版本可用", msg):
                    updater.open_release_page()
            else:
                ThemeDialog.information(self, "已是最新",
                    f"当前版本：{local}\n"
                    f"最新版本：{remote}\n\n"
                    f"无需更新 ✨")
        except Exception as e:
            self.btn_check_update.setEnabled(True)
            self.btn_check_update.setText("立即检查更新")
            ThemeDialog.error(self, "错误", f"检查更新异常：\n{e}")
