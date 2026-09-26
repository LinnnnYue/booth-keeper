# theme.py — BoothKeeper 主题系统（总监定稿 · 融合三路设计）
#
# 设计来源：
#   · 基底方向取自 设计师B「日式和纸 / 朱印 / 浮世绘紫调」（最贴主上十四年二次元沉淀 + BOOTH 日本平台源流）
#   · 字体分层取自 设计师A「霓虹 HUD」的正确做法（等宽仅用于标题/导航/徽章/ID，正文走人文字体，不滥用）
#   · 终端徽章/状态条意识参考 设计师C「复古终端」（但修正其全 UI 全等宽撞 craft-floor 的风险）
# 总监修订：去除 feTurbulence 纸纹（craft-floor 灰色地带），和纸质感改为纯色 surface + 1px 墨线表达，更干净。
#
# 七种日式色卡 + Light(和纸暖白) / Dark(墨色) 双模式，生成 Qt 样式表 (QSS)
# 设计约束：直角/2px 微圆角、flat 无阴影、1px 墨线分隔、无 emoji、汉字偏旁角标
# PySide6 QSS 注意：颜色用 #AARRGGBB（alpha 在前）；CSS 块花括号在 f-string 中需转义为 {{ }}

# ---- 字体（标题明朝体 / 正文黑体 / 数字等宽）----
SERIF = ('"Noto Serif CJK SC","Source Han Serif SC","Songti SC",'
         '"SimSun","STSong",serif')
SANS = ('"Noto Sans CJK SC","Microsoft YaHei","PingFang SC",'
        '"Heiti SC",sans-serif')
MONO = ('"JetBrains Mono","Cascadia Code","Sarasa Mono SC","Consolas",'
        '"DejaVu Sans Mono",monospace')

# ---- 七色日式色卡：键保留旧名以兼容 settings_page，值改为日式色卡 (deep, mid, light) ----
# teal→墨 sumi / blue→藏 kon / coral→朱 shu / amber→金 kinhaku
# pink→桃 momo / green→茶 aocha / purple→藤 ukiyoe
ACCENTS = {
    "teal":   ("#1A1A1A", "#4A4A4A", "#C8C8C8"),  # 墨
    "blue":   ("#1F3856", "#4A6789", "#DDE5EE"),  # 藏
    "coral":  ("#8F2C22", "#B83A2E", "#F5DCD6"),  # 朱
    "amber":  ("#6E5220", "#8C6A2A", "#ECDFB6"),  # 金
    "pink":   ("#8A3554", "#A8456B", "#F2D8E1"),  # 桃
    "green":  ("#20493C", "#2A5F4F", "#D6E3D9"),  # 茶
    "purple": ("#382D54", "#4A3B6B", "#E2DCEC"),  # 藤
}

ACCENT_NAMES = {
    "teal": "墨", "blue": "藏", "coral": "朱", "amber": "金",
    "pink": "桃", "green": "茶", "purple": "藤",
}

# 默认以「朱」为强调（贴合朱印红基调），浅色和纸为默认
DEFAULT_ACCENT = "coral"
DEFAULT_MODE = "light"


def build_qss(accent: str = DEFAULT_ACCENT, mode: str = DEFAULT_MODE) -> str:
    a_deep, a_mid, a_light = ACCENTS.get(accent, ACCENTS[DEFAULT_ACCENT])

    if mode == "light":
        bg, surface, surface2 = "#FAF6EE", "#FFFDF8", "#F3ECDD"
        text, text2, text3 = "#2A2622", "#6B6256", "#9A9183"
        border, border2 = "#D9CFBE", "#E8E0D2"
        hover, input_bg = "#EFE7D8", "#FFFFFF"
        success, success_l = "#2A5F4F", "#D6E3D9"
        warn, warn_l = "#8C6A2A", "#ECDFB6"
        danger, danger_l = "#9E2B20", "#F5DCD6"
        accent_used, accent_deep, accent_light = a_mid, a_deep, a_light
        sel_bg, sel_text = a_light, a_deep
    else:
        bg, surface, surface2 = "#0F0E0C", "#1A1815", "#211E1A"
        text, text2, text3 = "#E8E2D4", "#A89E8C", "#6E6557"
        border, border2 = "#322E28", "#2A2620"
        hover, input_bg = "#2A2620", "#16140F"
        success, success_l = "#5E8C7A", "#1F2A25"
        warn, warn_l = "#C8A24A", "#2A2418"
        danger, danger_l = "#D25543", "#2A1A16"
        accent_used, accent_deep, accent_light = a_mid, a_deep, a_light
        sel_bg, sel_text = a_mid, "#FAFAFA"

    btn_text = "#FAFAFA"   # 白字不纯白

    qss = f"""
    QWidget {{
        background-color: {bg};
        color: {text};
        font-family: {SANS};
        font-size: 13px;
        selection-background-color: {sel_bg};
        selection-color: {sel_text};
    }}
    QMainWindow {{
        background-color: {bg};
    }}

    /* ===== 侧边栏（和纸＋朱印竖线导航）===== */
    #sidebar {{
        background-color: {surface2};
        border-right: 1px solid {border};
    }}
    NavButton {{
        background-color: transparent;
        color: {text2};
        border: none;
        border-left: 2px solid transparent;
        border-radius: 0px;
        padding: 9px 12px;
        text-align: left;
        font-family: {SERIF};
        font-size: 14px;
    }}
    NavButton:hover {{ background-color: {hover}; color: {text}; }}
    NavButton[active="true"] {{
        background-color: {sel_bg};
        color: {sel_text};
        border-left: 2px solid {accent_used};
        font-weight: 600;
    }}

    /* ===== 面板 ===== */
    QFrame {{ background-color: transparent; border: none; }}
    .Card {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: 2px;
    }}
    QLabel#pageTitle {{ font-family: {SERIF}; font-size: 18px; font-weight: 600; color: {text}; }}
    QLabel#pageSub {{ font-family: {SANS}; font-size: 12px; color: {text2}; }}
    QLabel#muted {{ color: {text3}; }}
    QLabel[mono="1"] {{ font-family: {MONO}; }}

    /* ===== 输入 ===== */
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
        background-color: {input_bg};
        border: 1px solid {border};
        border-radius: 2px;
        padding: 8px 10px;
        color: {text};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
        border: 1px solid {accent_used};
    }}
    QComboBox QAbstractItemView {{
        background-color: {surface};
        border: 1px solid {border};
        selection-background-color: {sel_bg};
        color: {text};
    }}

    /* ===== 按钮（直角 / 朱印）===== */
    QPushButton {{
        background-color: {surface};
        color: {text};
        border: 1px solid {border};
        border-radius: 2px;
        padding: 8px 16px;
        font-family: {SANS};
    }}
    QPushButton:hover {{ background-color: {hover}; border-color: {accent_used}; }}
    QPushButton:pressed {{ background-color: {accent_light}; }}
    QPushButton:disabled {{ color: {text3}; border-color: {border2}; }}
    QPushButton#accent {{
        background-color: {accent_used};
        color: {btn_text};
        border: 1px solid {accent_used};
        font-weight: 600;
    }}
    QPushButton#accent:hover {{ background-color: {accent_deep}; border-color: {accent_deep}; }}
    QPushButton#accent:pressed {{ background-color: {accent_deep}; }}
    QPushButton#secondary {{
        background-color: transparent;
        color: {accent_used};
        border: 1px solid {accent_used};
        border-radius: 2px;
    }}
    QPushButton#secondary:hover {{ background-color: {accent_light}; }}
    QPushButton#ghost {{ background-color: transparent; border: none; color: {text2}; border-radius: 2px; }}
    QPushButton#ghost:hover {{ background-color: {hover}; color: {text}; }}

    /* ===== 列表（1px 细线分隔，不卡片化）===== */
    QListWidget {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: 2px;
        outline: 0;
    }}
    QListWidget::item {{
        padding: 9px 12px;
        border-bottom: 1px solid {border2};
        color: {text};
    }}
    QListWidget::item:selected {{ background-color: {sel_bg}; color: {sel_text}; }}
    QListWidget::item:hover {{ background-color: {hover}; }}

    /* ===== 进度条（朱印红渐变）===== */
    QProgressBar {{
        background-color: {input_bg};
        border: 1px solid {border};
        border-radius: 2px;
        text-align: center;
        color: {text2};
        height: 14px;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {accent_deep}, stop:1 {accent_used});
        border-radius: 1px;
    }}

    /* ===== 复选 / 单选 ===== */
    QCheckBox, QRadioButton {{ spacing: 6px; color: {text}; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {border};
        border-radius: 2px;
        background-color: {input_bg};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {accent_used};
        border: 1px solid {accent_used};
    }}

    /* ===== 滚动条 ===== */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{
        background: {border};
        border-radius: 2px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {text3}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{
        background: {border};
        border-radius: 2px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {text3}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ===== 状态徽章（纯字＋角标，CJK 〔完〕〔漏〕〔更〕〔警〕〔故〕）===== */
    QLabel[badge="ok"]   {{ background-color: {success_l}; color: {success}; border-radius: 1px; padding: 2px 7px; font-weight: 600; }}
    QLabel[badge="run"]  {{ background-color: {sel_bg};    color: {sel_text}; border-radius: 1px; padding: 2px 7px; font-weight: 600; }}
    QLabel[badge="wait"] {{ background-color: {border2};   color: {text2};   border-radius: 1px; padding: 2px 7px; font-weight: 600; }}
    QLabel[badge="warn"] {{ background-color: {warn_l};    color: {warn};    border-radius: 1px; padding: 2px 7px; font-weight: 600; }}
    QLabel[badge="err"]  {{ background-color: {danger_l};  color: {danger};  border-radius: 1px; padding: 2px 7px; font-weight: 600; }}

    /* ===== 分隔（1px 半透墨线）===== */
    QFrame#hline {{ background-color: #18000000; max-height: 1px; border: none; }}

    /* ===== 拖拽区 ===== */
    #drop {{
        border: 1.5px dashed {border};
        border-radius: 2px;
        background-color: {surface};
    }}
    #drop:hover {{ border-color: {accent_used}; }}
    """
    return qss.strip()
