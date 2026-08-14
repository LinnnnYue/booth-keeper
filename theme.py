# theme_next.py — BoothKeeper 主题系统（主题制重构 · 总监视角的「意境升级」）
#
# 设计意图（主上意象 · 金缮 kintsugi 校正版）：
#   「隐约的鎏金枝叶脉络纹路在【背景里】」—— 金线如瓷器金缮裂缝/叶脉，
#     以极淡肌理铺满全窗釉底，是意境而非装饰主体。
#   「素雅 / 古朴 / 大气 / 雍容华贵」—— 釉底为素（月白瓷胎 / 墨釉），
#     金仅作细线、边框、勾选、脉络点缀，绝不填充抢戏（不搞黑底金按钮 / 金箔渐变按钮）。
#   三主题统一铺同系隐约背景脉络：朱印=朱红印脉、鎏金=金缮金线、古纹=青绿叶脉。
#
# 与 theme.py 的关系：
#   · 本文件为 NEW（绝不覆盖 theme.py，旧文件作备份，工程适配由另一 agent 负责）。
#   · 抛弃「七色 accent 切换」，改为「整套视觉打包切换」的主题制：
#       THEMES[name]["light"|"dark"] 为完整 token 包；build_theme 返回整份 QSS。
#   · 保留 build_qss 作为兼容别名（内部调 build_theme）。
#
# PySide6 QSS 能力边界（严格遵守）：
#   · 颜色用 #AARRGGBB（alpha 在前）。
#   · 不支持 feTurbulence / backdrop-filter / @keyframes —— 一律不用。
#   · 脉络/叶脉纹路用【矢量 SVG data-URI background-image】注入特定区域（纯描边，清晰矢量）。
#   · 金箔金属渐变用 qlineargradient 做背景/填充（gradient TEXT 为禁令，但填充渐变金箔允许）。
#   · 形状系统一致：直角 / 2px 微圆角 / flat 无阴影 / 1px 墨线或金线分隔。
#   · 复选框/单选框/滚动条全部主题化（无裸态）。
#   · 无 AI 紫蓝辉光、无 Inter/Roboto/Arial、无纯 #000/#fff 主色、无 emoji、无 eyebrow 胶囊。

import base64
from PySide6.QtGui import QPainter, QColor, QPixmap
from PySide6.QtWidgets import QLabel
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QEvent

# ---- 字体（标题明朝 / 正文黑体 / 数字等宽，全部在 Windows 可落地）----
SERIF = ('"Noto Serif CJK SC","Source Han Serif SC","Songti SC",'
         '"SimSun","STSong",serif')
SANS = ('"Noto Sans CJK SC","Microsoft YaHei","PingFang SC",'
        '"Heiti SC",sans-serif')
MONO = ('"JetBrains Mono","Cascadia Code","Sarasa Mono SC","Consolas",'
        '"DejaVu Sans Mono",monospace')

THEME_NAMES = {"zhuyin": "朱印", "liujin": "鎏金", "guwen": "古纹"}
DEFAULT_THEME = "zhuyin"
DEFAULT_MODE = "light"
# 每主题推荐默认明暗（鎏金默认月白釉，呈现素雅金缮质感）
DEFAULT_MODE_PER_THEME = {"zhuyin": "light", "liujin": "light", "guwen": "light"}

# 每个主题选用哪种纹路母题（对应 _MOTIF 生成器）
THEME_MOTIF = {
    "zhuyin": "vein",    # 朱红印脉 · 竖纹藤蔓
    "liujin": "gold",    # 鎏金脉络 · 细密金线网络（重点打磨）
    "guwen": "leaf",     # 古纹叶脉 · 枝叶枝蔓分叉
}


# =====================================================================
# 矢量 SVG 母题（纯描边，无 feTurbulence；color 为 #RRGGBB，alpha 用 *_opacity）
# =====================================================================
def _svg(uri_inner: str) -> str:
    """包成 base64 data-URI，供 QSS background-image 使用。"""
    raw = ("<svg xmlns='http://www.w3.org/2000/svg' " + uri_inner + "</svg>")
    b64 = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    return "url(data:image/svg+xml;base64," + b64 + ")"


def _motif_sidebar(c: str, kind: str) -> str:
    """侧边栏竖幅纹路（width≈72, height≈720，anchored 左上，no-repeat）。
    密度与时比旧版更高：主脉络加粗、节点加亮、鎏金另叠一层细金网络，
    让纹路从「装饰线」升级为「文明肌理」。"""
    SVG_OPEN = "<svg xmlns='http://www.w3.org/2000/svg' width='72' height='720' viewBox='0 0 72 720'>"
    if kind == "gold":
        body = (
            "<path d='M30 0 C12 80,48 160,30 250 C12 340,48 430,30 520 C16 600,46 660,30 720' "
            "fill='none' stroke='{c}' stroke-width='1.6' stroke-opacity='0.72'/>"
            "<path d='M44 0 C60 90,30 170,46 270 C62 360,34 450,48 560 C60 640,40 690,52 720' "
            "fill='none' stroke='{c}' stroke-width='1.1' stroke-opacity='0.5'/>"
            "<g fill='none' stroke='{c}' stroke-width='0.5' stroke-opacity='0.24'>"
            "<path d='M30 120 C44 130,52 150,46 270'/><path d='M30 250 C16 270,8 290,12 360'/>"
            "<path d='M30 400 C46 410,54 440,48 560'/><path d='M30 520 C16 540,10 560,18 640'/>"
            "<path d='M44 270 C58 280,64 300,52 360'/></g>"
            "<g fill='none' stroke='{c}' stroke-width='1' stroke-opacity='0.5'>"
            "<path d='M30 90 C50 104,62 116,72 134'/><path d='M30 200 C10 216,2 232,0 252'/>"
            "<path d='M30 330 C50 346,62 360,72 378'/><path d='M30 450 C10 468,2 482,0 502'/>"
            "<path d='M44 300 C64 312,70 326,72 344'/><path d='M30 580 C50 596,62 610,72 628'/>"
            "<path d='M30 650 C14 666,8 680,2 700'/></g>"
            "<g fill='{c}' fill-opacity='0.85'>"
            "<circle cx='30' cy='90' r='2.4'/><circle cx='30' cy='250' r='2.4'/>"
            "<circle cx='30' cy='400' r='2.4'/><circle cx='30' cy='560' r='2.4'/>"
            "<circle cx='46' cy='270' r='1.8'/><circle cx='48' cy='560' r='1.8'/></g>"
        ).format(c=c)
        body = body + _seigaiha_layer(c)
    elif kind == "zhuyin":
        # 朱印：回字纹(雷纹)竖列 + 印章方结 + 朱红印脉
        units = []
        for y in range(20, 700, 64):
            units.append(
                "<path d='M14 {y} H58 V{y2} H22 V{y3} H50 V{y4} H30' "
                "fill='none' stroke='{c}' stroke-width='1.4' stroke-opacity='0.8'/>"
                .format(c=c, y=y, y2=y + 44, y3=y + 10, y4=y + 34))
        body = (
            "<path d='M36 0 C22 90,50 180,36 280 C24 380,52 470,36 560 C26 640,48 690,36 720' "
            "fill='none' stroke='{c}' stroke-width='1.4' stroke-opacity='0.55'/>"
            "<g>" + "".join(units) + "</g>"
            "<g fill='none' stroke='{c}' stroke-width='1.6' stroke-opacity='0.7'>"
            "<rect x='24' y='330' width='24' height='24'/><rect x='28' y='334' width='16' height='16' "
            "stroke-opacity='0.4'/></g>"
            "<rect x='31' y='341' width='10' height='10' fill='{c}' fill-opacity='0.85'/>"
        ).format(c=c)
    else:  # guwen（叶脉 + 云雷纹回旋）
        spirals = []
        for (sx, sy) in [(20, 120), (52, 240), (18, 410), (50, 540), (24, 660)]:
            spirals.append(
                "<path d='M{sx} {sy} a8 8 0 1 1 -8 -8 a4 4 0 1 0 4 4' "
                "fill='none' stroke='{c}' stroke-width='1.1' stroke-opacity='0.6'/>"
                .format(sx=sx, sy=sy, c=c))
        body = (
            "<path d='M8 720 C14 560,30 420,30 280 C30 160,44 80,62 0' "
            "fill='none' stroke='{c}' stroke-width='1.6' stroke-opacity='0.6'/>"
            "<g fill='none' stroke='{c}' stroke-width='1' stroke-opacity='0.45'>"
            "<path d='M30 280 C46 250,58 220,62 180'/><path d='M30 360 C48 338,60 312,66 270'/>"
            "<path d='M28 460 C44 440,54 416,60 376'/><path d='M20 560 C36 542,46 518,52 480'/>"
            "<path d='M12 650 C28 634,38 614,44 580'/><path d='M14 420 C28 404,36 384,42 350'/></g>"
            "<g fill='{c}' fill-opacity='0.22'>"
            "<path d='M62 180 C70 172,72 160,66 154 C60 160,60 172,62 180 Z'/>"
            "<path d='M66 270 C74 262,76 250,70 244 C64 250,64 262,66 270 Z'/>"
            "<path d='M60 376 C68 368,70 356,64 350 C58 356,58 368,60 376 Z'/></g>"
            "<g>" + "".join(spirals) + "</g>"
        ).format(c=c)
    return SVG_OPEN + body + "</svg>"


def _motif_title(c: str) -> str:
    """页标题区右侧叶脉/枝蔓花饰（width≈150, height≈44，anchored 右中）。"""
    body = (
        "width='150' height='44' viewBox='0 0 150 44'>"
        "<g fill='none' stroke='{c}' stroke-width='1.2' stroke-opacity='0.55'>"
        "<path d='M0 40 C50 38,95 28,148 6'/>"
        "<path d='M0 30 C40 30,80 22,120 10' stroke-opacity='0.3'/>"
        "</g>"
        "<g fill='none' stroke='{c}' stroke-width='1' stroke-opacity='0.42'>"
        "<path d='M30 36 C42 26,54 18,64 8'/>"
        "<path d='M70 30 C84 22,98 16,112 10'/>"
        "<path d='M104 22 C118 16,132 12,146 10'/>"
        "<path d='M50 33 C58 27,66 22,74 14' stroke-opacity='0.3'/>"
        "</g>"
        "<g fill='{c}' fill-opacity='0.6'>"
        "<circle cx='148' cy='6' r='2.4'/><circle cx='64' cy='8' r='1.8'/>"
        "<circle cx='112' cy='10' r='1.8'/></g>"
    ).format(c=c)
    return _svg(body)


def _motif_card(c: str) -> str:
    """卡片左上角藤蔓卷须（width≈44, height≈44，anchored 左上）。"""
    body = (
        "width='44' height='44' viewBox='0 0 44 44'>"
        "<g fill='none' stroke='{c}' stroke-width='1.1' stroke-opacity='0.5'>"
        "<path d='M0 0 L0 22 C0 34,12 44,44 44'/>"
        "<path d='M0 12 C10 14,18 22,20 34'/>"
        "<path d='M12 0 C14 10,22 18,34 20'/>"
        "<path d='M0 30 C8 32,14 38,18 44' stroke-opacity='0.34'/>"
        "<path d='M30 0 C32 10,40 18,44 30' stroke-opacity='0.34'/>"
        "</g>"
        "<g fill='{c}' fill-opacity='0.55'>"
        "<circle cx='20' cy='34' r='1.6'/><circle cx='34' cy='20' r='1.6'/></g>"
    ).format(c=c)
    return _svg(body)


def _motif_bg_svg(c: str, light: bool = True) -> str:
    """背景脉络原始 SVG（<svg>...</svg>），供 QSvgRenderer 渲染（离屏/真机皆可）。
    与 _motif_bg(data URI) 共享同一路径/颜色/不透明度参数。"""
    # light 主线 0.55 / 细线 0.32 / 节点 0.65；dark 主线 0.45 / 细线 0.26 / 节点 0.55
    # 用 accent_deep（更深金）作脉络色，与 accent 协调且对比清晰；描边略粗确保可辨
    s = 4.2 if light else 3.4
    a_main = round(0.13 * s, 3)
    a_fine = round(0.07 * s, 3)
    a_node = round(0.16 * s, 3)
    sw_main = 1.2 if light else 1.0
    sw_fine = 0.6 if light else 0.5
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='780' viewBox='0 0 1200 780'>"
        "<g fill='none' stroke='{c}' stroke-width='{sm}' stroke-opacity='{am}'>"
        "<path d='M90 -5 C220 120,150 240,300 330 C470 440,360 560,540 660 C640 720,700 760,760 785'/>"
        "<path d='M1210 -5 C1020 110,1140 250,980 360 C820 470,940 600,760 700 C700 735,680 760,660 785'/>"
        "<path d='M-5 300 C160 320,240 380,360 420 C520 470,560 560,720 600 C880 640,1020 660,1205 670'/>"
        "<path d='M-5 560 C180 580,300 620,460 660 C640 705,820 700,1000 720 C1100 730,1160 740,1205 745'/>"
        "</g>"
        "<g fill='none' stroke='{c}' stroke-width='{sf}' stroke-opacity='{af}'>"
        "<path d='M300 330 C360 300,420 280,500 250'/>"
        "<path d='M540 660 C600 620,660 600,740 580'/>"
        "<path d='M980 360 C920 320,880 300,820 270'/>"
        "<path d='M360 420 C420 400,480 390,540 370'/>"
        "<path d='M760 700 C800 660,840 640,900 610'/>"
        "<path d='M460 660 C500 700,540 720,580 750'/>"
        "</g>"
        "<g fill='{c}' fill-opacity='{an}'>"
        "<circle cx='300' cy='330' r='2'/><circle cx='540' cy='660' r='2'/>"
        "<circle cx='980' cy='360' r='2'/><circle cx='360' cy='420' r='2'/>"
        "<circle cx='760' cy='700' r='2'/><circle cx='460' cy='660' r='2'/></g>"
        "</svg>"
    ).format(c=c, sm=sw_main, sf=sw_fine, am=a_main, af=a_fine, an=a_node)


def _motif_bg(c: str, light: bool = True) -> str:
    """背景脉络 data URI（供 QSS background-image）。真机渲染可用，离屏 QPA 不渲染。
    实际 #root 背景由 RootWidget paintEvent + motif_bg_svg() 绘制，保证离屏/真机一致。"""
    return _svg(_motif_bg_svg(c, light))


def _motif_bg_cinnabar(c: str, light: bool = True) -> str:
    """朱印根背景：朱红缠枝卷云（非方母题）——流动藤蔓 + 卷云头 + 小叶，
    取代原「回字嵌套方」（主上判为怪异）。跟随朱印色系、与鎏金金线/古纹叶脉各异。
    双引号 SVG + 加粗描边 + 提亮 opacity，确保离屏/真机可见。"""
    a = 0.22 if light else 0.17
    a2 = 0.16 if light else 0.12
    vines = [
        "M90 -5 C200 120,140 240,240 330 C360 440,300 560,420 660 C500 740,560 760,600 800",
        "M1180 -5 C1040 110,1140 240,1000 360 C860 470,960 600,820 700 C760 740,740 760,720 800",
        "M-5 280 C160 300,260 360,360 420 C520 470,560 560,720 600 C900 650,1040 660,1205 670",
        "M-5 540 C180 560,300 600,460 660 C640 710,820 700,1000 720 C1100 730,1160 740,1205 745",
    ]
    clouds = []
    for (cx, cy) in [(300, 330), (540, 660), (980, 360), (360, 420),
                     (760, 700), (460, 660), (820, 540), (240, 250)]:
        clouds.append(
            '<path d="M{cx} {cy} a11 11 0 1 1 -11 -11 a5 5 0 1 0 5 5" '
            'fill="none" stroke="{c}" stroke-width="1.4" stroke-opacity="{a2}"/>'
            .format(cx=cx, cy=cy, c=c, a2=a2))
    leaves = [
        "M240 330 q22 -12 30 8 q-8 14 -30 -8 Z",
        "M420 660 q22 -12 30 8 q-8 14 -30 -8 Z",
        "M1000 360 q-22 -12 -30 8 q8 14 30 -8 Z",
        "M720 600 q22 -12 30 8 q-8 14 -30 -8 Z",
        "M360 420 q-22 -12 -30 8 q8 14 30 -8 Z",
        "M820 700 q22 -12 30 8 q-8 14 -30 -8 Z",
    ]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">'
        '<g fill="none" stroke="{c}" stroke-width="1.8" stroke-opacity="{a}">'
        + "".join('<path d="{}"/>'.format(p) for p in vines) +
        '</g>'
        '<g fill="none" stroke="{c}" stroke-width="1.4" stroke-opacity="{a2}">'
        + "".join(clouds) +
        '</g>'
        '<g fill="{c}" fill-opacity="{a2}">'
        + "".join('<path d="{}"/>'.format(p) for p in leaves) +
        '</g></svg>'
    ).format(c=c, a=a, a2=a2)


def _motif_bg_leaf(c: str, light: bool = True) -> str:
    """古纹根背景：枝叶叶脉——青绿主茎分叉 + 小型叶形，极淡铺陈。
    主上要求：古纹改用自身色系对应母题（叶脉）。
    双引号 + 加粗 + 提亮 opacity，确保离屏可见。"""
    a = 0.26 if light else 0.20
    a2 = 0.22
    stems = [
        "M120 -5 C160 160,80 320,140 500 C180 640,120 720,160 805",
        "M520 -5 C480 180,560 340,500 520 C460 660,540 740,500 805",
        "M900 -5 C940 200,860 360,920 540 C960 660,900 740,940 805",
        "M-5 480 C160 500,300 560,460 620 C620 680,800 700,1000 720",
    ]
    leaves = [
        "M160 250 q22 -12 30 8 q-8 14 -30 -8 Z",
        "M140 500 q-22 -12 -30 8 q8 14 30 -8 Z",
        "M500 300 q22 -12 30 8 q-8 14 -30 -8 Z",
        "M920 360 q-22 -12 -30 8 q8 14 30 -8 Z",
        "M940 620 q22 -12 30 8 q-8 14 -30 -8 Z",
        "M460 640 q-22 -12 -30 8 q8 14 30 -8 Z",
        "M300 560 q22 -12 30 8 q-8 14 -30 -8 Z",
        "M700 690 q-22 -12 -30 8 q8 14 30 -8 Z",
    ]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">'
        '<g fill="none" stroke="{}" stroke-width="1.8" stroke-opacity="{}">'
        + "".join('<path d="{}"/>'.format(p) for p in stems) +
        '</g>'
        '<g fill="{}" stroke="none" fill-opacity="{}">'
        + "".join('<path d="{}"/>'.format(p) for p in leaves) +
        '</g></svg>'
    ).format(c, a, c, a2)


def motif_bg_svg(theme_name: str, mode: str = None) -> str:
    """按主题+明暗返回背景纹路原始 SVG（用于 RootWidget paintEvent，离屏/真机皆渲染）。
    主上要求：金缮仅鎏金主题；朱印/古纹各用自身色系对应母题（回字纹/叶脉），跟随颜色。"""
    if mode not in ("light", "dark"):
        mode = DEFAULT_MODE_PER_THEME.get(theme_name, DEFAULT_MODE)
    pal = THEMES[theme_name][mode]
    c = pal["accent_deep"]
    if theme_name == "liujin":
        return _motif_bg_svg(c, light=(mode == "light"))            # 金缮脉络（金线）
    elif theme_name == "zhuyin":
        return _motif_bg_cinnabar(c, light=(mode == "light"))    # 朱红缠枝卷云（非方）
    else:
        return _motif_bg_leaf(c, light=(mode == "light"))          # 青绿叶脉


def taiji_svg_raw(accent: str, bg: str) -> str:
    """太极（阴阳鱼）原始 SVG，供 QSvgRenderer 渲染成 QIcon（明暗切换按钮）。
    阳半用 accent（金），阴半用釉底 bg，外圈金线描边——含蓄表达「明暗/阴阳」之辩。"""
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 100 100'>"
        "<circle cx='50' cy='50' r='46' fill='none' stroke='{a}' stroke-width='3'/>"
        "<path d='M50 4 A46 46 0 0 1 50 96 A23 23 0 0 1 50 50 A23 23 0 0 0 50 4 Z' fill='{a}'/>"
        "<circle cx='50' cy='27' r='9' fill='{b}'/>"
        "<circle cx='50' cy='73' r='9' fill='{a}'/>"
        "</svg>"
    ).format(a=accent, b=bg)


def _seigaiha_layer(c: str) -> str:
    """青海波层（阴阳师风同心半圆鳞波纹），作为侧栏底纹。
    透明度提到 0.16/0.11/0.07 三层外浓内淡并放大半径，使鳞波在真机釉底上
    清晰可辨却仍素雅（不再等于隐形）。返回若干 <path>，叠加到侧栏竖纹之下。"""
    a = 0.16
    r = 22
    parts = []
    y = 0
    row = 0
    while y < 720 + r:
        off = (row % 2) * r  # 行间交错，呈鳞片状
        x = off - r
        while x < 72 + r:
            for k in range(3, 0, -1):  # 三层同心半圆（朝上），外浓内淡形成立体鳞波
                rr = r * k / 3.0
                op = a if k == 3 else (a * 0.7 if k == 2 else a * 0.45)
                w = 0.9 if k == 3 else 0.6
                parts.append(
                    "<path d='M{0:.1f} {1:.1f} A{2:.1f} {2:.1f} 0 0 1 {3:.1f} {1:.1f}' "
                    "fill='none' stroke='{c}' stroke-width='{w}' stroke-opacity='{op}'/>"
                    .format(x - rr, y, rr, x + rr, c=c, op=op, w=w))
            x += 2 * r
        y += r
        row += 1
    return "".join(parts)


def _motif_thunder(c: str) -> str:
    """雷纹（回字纹）分隔线，200×10，阴阳师风硬朗回折。返回原始 <svg>（供 QLabel 平铺）。
    注：使用双引号 + 加粗笔画，确保离屏 QSvgRenderer 有效渲染（单引号 + stroke-opacity 在 <g> 上有解析陷阱）。"""
    parts = []
    for i in range(0, 200, 16):
        parts.append(
            '<path d="M{} 1 H{} V9 H{} V3 H{} V7"/>'.format(i, i + 12, i + 3, i + 9)
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="10" viewBox="0 0 200 10">'
        '<g fill="none" stroke="{}" stroke-width="1.4">{}</g>'
        '</svg>'
    ).format(c, "".join(parts))


def asa_no_ha(c: str, op: float = 0.18) -> str:
    """麻叶纹（阴阳师风几何母题）——填入拖拽区，作为「可放置」的隐性提示纹理。
    拖入时 op=0.30 提亮点亮。返回原始 <svg>（供 QLabel 平铺）。
    注：双引号 + 加粗 1.2，确保离屏可见。"""
    W = 28
    lines = [
        "M14 0 L14 28",          # 竖
        "M0 0 L28 28",           # 撇
        "M28 0 L0 28",           # 捺
        "M0 14 L28 14",          # 横
        "M0 0 L14 14 L28 0",     # 上三角
        "M0 28 L14 14 L28 28",   # 下三角
    ]
    body = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{W}" viewBox="0 0 {W} {W}">'
        '<g fill="none" stroke="{c}" stroke-width="1.2" stroke-opacity="{op}">'
        '{u}</g>'
        '</svg>'
    ).format(W=W, c=c, op=op, u="".join('<path d="{}"/>'.format(p) for p in lines))
    return body


def seal_svg(accent: str) -> str:
    """印章（阴阳师风品牌印记）——方篆式几何印章，置于侧栏品牌区。
    不依赖 CJK 字体（用几何笔画构成「守」意象的抽象印面），真机/离屏皆稳定渲染。"""
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'>"
        "<rect x='2' y='2' width='36' height='36' rx='3' fill='none' "
        "stroke='{a}' stroke-width='2.4'/>"
        "<rect x='7' y='7' width='26' height='26' rx='2' fill='none' "
        "stroke='{a}' stroke-width='1' stroke-opacity='0.55'/>"
        # 内部「守」意象：外方内十字 + 中心方点（印章常见构成）
        "<path d='M20 11 L20 29 M11 20 L29 20' stroke='{a}' stroke-width='2.2' "
        "stroke-linecap='square'/>"
        "<rect x='16.5' y='16.5' width='7' height='7' fill='{a}' fill-opacity='0.9'/>"
        "</svg>"
    ).format(a=accent)


# =====================================================================
# UI 纹样渲染通道（Qt6 的 QSS background-image 不支持 url(data:...)，
# 故纹样一律经 QLabel/QSvgRenderer 渲染为 pixmap——离屏/真机皆真实可见，
# 且能被程序化验证，不再靠"假设真机渲染"。）
# =====================================================================
def render_motif_pixmap(svg: str, w: int, h: int) -> "QPixmap":
    """把原始 SVG 渲染成透明背景 QPixmap。"""
    r = QSvgRenderer(svg.encode("utf-8"))
    pm = QPixmap(w, h)
    pm.fill(QColor(0, 0, 0, 0))
    if r.isValid():
        p = QPainter(pm)
        r.render(p, pm.rect())
        p.end()
    return pm


def render_tiled_pixmap(svg: str, w: int, h: int, tw: int, th: int) -> "QPixmap":
    """把一个小 SVG 单元(视图 tw×th)平铺成 w×h 的透明 pixmap。"""
    r = QSvgRenderer(svg.encode("utf-8"))
    tile = QPixmap(tw, th)
    tile.fill(QColor(0, 0, 0, 0))
    if r.isValid():
        p = QPainter(tile)
        r.render(p, tile.rect())
        p.end()
    out = QPixmap(w, h)
    out.fill(QColor(0, 0, 0, 0))
    pp = QPainter(out)
    pp.drawTiledPixmap(out.rect(), tile)
    pp.end()
    return out


class MotifBackdrop(QLabel):
    """垫在父控件之下的纹样背景层（QLabel 承载 pixmap，置于最底、不拦鼠标）。
    始终按【父控件】尺寸渲染——因为本控件通常不进布局，父控件 resize 时自身
    不会收到 resizeEvent；故在父上装事件过滤器，父一缩放即重绘。
    vw：渲染虚拟宽度（竖幅纹按自然宽锚定左缘，余下露底色；None 则铺满父宽）。"""
    def __init__(self, parent=None, svg: str = "", tile: bool = False,
                 tw: int = 28, th: int = 28, vw: int = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.lower()
        self._svg = svg
        self._tile = tile
        self._tw, self._th = tw, th
        self._vw = vw
        if parent is not None:
            parent.installEventFilter(self)
        self._render()

    def set_motif(self, svg: str):
        self._svg = svg
        self._render()

    def _psize(self):
        if self.parent() is not None:
            return self.parent().width(), self.parent().height()
        return self.width(), self.height()

    def _render(self):
        w, h = self._psize()
        if w <= 0 or h <= 0 or not self._svg:
            self.clear()
            return
        rw = self._vw if self._vw else w
        rh = h
        if self._tile:
            pm = render_tiled_pixmap(self._svg, rw, rh, self._tw, self._th)
        else:
            pm = render_motif_pixmap(self._svg, rw, rh)
        self.setPixmap(pm)
        self.setGeometry(0, 0, rw, rh)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._render()

    def eventFilter(self, obj, ev):
        if obj is self.parent() and ev.type() == QEvent.Resize:
            self._render()
        return super().eventFilter(obj, ev)


# ---- 主题差异化纹样（供 UI 调取的 raw SVG 接口）----
def motif_sidebar_raw(theme_name: str, mode: str = None) -> str:
    """侧栏纹样 raw SVG（按主题形状区分：金缮/朱印/古纹）。"""
    if mode not in ("light", "dark"):
        mode = DEFAULT_MODE_PER_THEME.get(theme_name, DEFAULT_MODE)
    pal = THEMES[theme_name][mode]
    kind = {"zhuyin": "zhuyin", "liujin": "gold", "guwen": "guwen"}[theme_name]
    return _motif_sidebar(pal["accent"], kind)


def motif_thunder_raw(theme_name: str, mode: str = None) -> str:
    if mode not in ("light", "dark"):
        mode = DEFAULT_MODE_PER_THEME.get(theme_name, DEFAULT_MODE)
    return _motif_thunder(THEMES[theme_name][mode]["accent"])


def motif_drop_raw(theme_name: str, mode: str = None, hi: bool = False) -> str:
    if mode not in ("light", "dark"):
        mode = DEFAULT_MODE_PER_THEME.get(theme_name, DEFAULT_MODE)
    return asa_no_ha(THEMES[theme_name][mode]["accent"], op=0.32 if hi else 0.18)


def motif_diamond_raw(theme_name: str, mode: str = None) -> str:
    """素净分隔线中心小菱点（accent 描边菱形），取代原雷纹「@」母题。
    双引号 SVG，单色，清晰可见。"""
    if mode not in ("light", "dark"):
        mode = DEFAULT_MODE_PER_THEME.get(theme_name, DEFAULT_MODE)
    c = THEMES[theme_name][mode]["accent"]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">'
        '<path d="M7 1 L13 7 L7 13 L1 7 Z" fill="none" stroke="{c}" '
        'stroke-width="1.4" stroke-opacity="0.8"/></svg>'
    ).format(c=c)


# =====================================================================
# 主题 token 包（每主题含 light / dark 两方案，嵌套 dict）
# 键：bg/surface/surface2/text/text2/text3/border/border2/hover/input_bg
#     accent/accent_deep/accent_light/btn_fill/btn_fill_hover/btn_fill_press
#     success/success_l/warn/warn_l/danger/danger_l/sel_bg/sel_text
#     (vein 颜色取自 THEME_MOTIF 对应，于 build_theme 内取用)
# =====================================================================
THEMES = {
    # ---------------- 朱印：和纸暖白 + 朱红印 + 明朝体（明亮基准）----------------
    "zhuyin": {
        "light": {
            "bg": "#FAF6EE", "surface": "#FFFDF8", "surface2": "#F3ECDD",
            "text": "#2A2622", "text2": "#6B6256", "text3": "#9A9183",
            "border": "#D9CFBE", "border2": "#E8E0D2",
            "hover": "#EFE7D8", "input_bg": "#FCFAF4",
            "accent": "#B83A2E", "accent_deep": "#8F2C22", "accent_light": "#F5DCD6",
            "btn_fill": "#B83A2E", "btn_fill_hover": "#8F2C22", "btn_fill_press": "#8F2C22",
            "success": "#2A5F4F", "success_l": "#D6E3D9",
            "warn": "#8C6A2A", "warn_l": "#ECDFB6",
            "danger": "#9E2B20", "danger_l": "#F5DCD6",
            "sel_bg": "#F5DCD6", "sel_text": "#8F2C22",
        },
        "dark": {
            "bg": "#0F0E0C", "surface": "#1A1815", "surface2": "#211E1A",
            "text": "#E8E2D4", "text2": "#A89E8C", "text3": "#6E6557",
            "border": "#322E28", "border2": "#2A2620",
            "hover": "#2A2620", "input_bg": "#16140F",
            "accent": "#C8453A", "accent_deep": "#A8332A", "accent_light": "#F5DCD6",
            "btn_fill": "#C8453A", "btn_fill_hover": "#A8332A", "btn_fill_press": "#A8332A",
            "success": "#5E8C7A", "success_l": "#1F2A25",
            "warn": "#C8A24A", "warn_l": "#2A2418",
            "danger": "#D25543", "danger_l": "#2A1A16",
            "sel_bg": "#C8453A", "sel_text": "#FAFAFA",
        },
    },

    # ---------------- 鎏金：素雅釉底（月白瓷胎 / 墨釉）+ 隐约金缮脉络 + 金仅作点缀 ----------------
    "liujin": {
        "light": {
            # 月白瓷胎：暖白釉底，金以极淡脉络铺陈，主按钮走墨色（古朴），绝不金箔填充
            "bg": "#F4F1EA", "surface": "#FBF7EF", "surface2": "#ECE3D2",
            "text": "#2B2415", "text2": "#6E6147", "text3": "#9C8E70",
            "border": "#D8C9A6", "border2": "#E6DBC2",
            "hover": "#ECE1C9", "input_bg": "#FAF5EA",
            "accent": "#B8902F", "accent_deep": "#8C6A2A", "accent_light": "#F2E4BE",
            # 鎏金主按钮：墨色实心（古朴雍容），金只作背景脉络与细线/勾选点缀
            "btn_fill": "#2B2415", "btn_fill_hover": "#3A3220", "btn_fill_press": "#1C1810",
            "success": "#3E6B4F", "success_l": "#DDE7D6",
            "warn": "#B8862F", "warn_l": "#F0E6C8",
            "danger": "#9E3B22", "danger_l": "#F3DFD6",
            "sel_bg": "#F2E4BE", "sel_text": "#6E5220",
        },
        "dark": {
            # 墨釉：近黑暖墨底，金缮脉络略显，主按钮走古铜实心（雍容不张扬）
            "bg": "#23211C", "surface": "#2A261E", "surface2": "#322C20",
            "text": "#EDE3C8", "text2": "#B6A884", "text3": "#7C715A",
            "border": "#3A3122", "border2": "#2A2417",
            "hover": "#2E281C", "input_bg": "#1A160F",
            "accent": "#C9A24B", "accent_deep": "#B8862F", "accent_light": "#F2E4BE",
            # 墨釉主按钮：古铜实心，金作细线/脉络点缀
            "btn_fill": "#7A5C28", "btn_fill_hover": "#8C6A2A", "btn_fill_press": "#5A4420",
            "success": "#5E8C6A", "success_l": "#1C2A22",
            "warn": "#C8A24A", "warn_l": "#2A2418",
            "danger": "#C8553C", "danger_l": "#2A1813",
            "sel_bg": "#C9A24B", "sel_text": "#1A140A",
        },
    },

    # ---------------- 古纹：古朴青绿/赭石 + 枝叶叶脉纹路意境 ----------------
    "guwen": {
        "light": {
            "bg": "#F1EFE6", "surface": "#F8F6ED", "surface2": "#E7E3D5",
            "text": "#2A2E26", "text2": "#5E6452", "text3": "#8C917E",
            "border": "#CFCAB6", "border2": "#DEDAC9",
            "hover": "#E9E5D8", "input_bg": "#FCFBF6",
            "accent": "#3F6B52", "accent_deep": "#2F5142", "accent_light": "#D6E3D9",
            "btn_fill": "#3F6B52", "btn_fill_hover": "#2F5142", "btn_fill_press": "#2F5142",
            "success": "#3F6B52", "success_l": "#D6E3D9",
            "warn": "#9C6B3F", "warn_l": "#EBDDC8",
            "danger": "#9E3B22", "danger_l": "#F3DFD6",
            "sel_bg": "#D6E3D9", "sel_text": "#2F5142",
        },
        "dark": {
            "bg": "#0E1210", "surface": "#161A16", "surface2": "#1E231D",
            "text": "#DDE3D6", "text2": "#9DA892", "text3": "#6B7163",
            "border": "#2C332B", "border2": "#232A22",
            "hover": "#20271F", "input_bg": "#12160F",
            "accent": "#5C9A7C", "accent_deep": "#4F8068", "accent_light": "#D6E3D9",
            "btn_fill": "#5C9A7C", "btn_fill_hover": "#4F8068", "btn_fill_press": "#4F8068",
            "success": "#5C9A7C", "success_l": "#16241C",
            "warn": "#B08A4A", "warn_l": "#262015",
            "danger": "#C0623C", "danger_l": "#2A1813",
            "sel_bg": "#5C9A7C", "sel_text": "#0E1210",
        },
    },
}

# 鎏金进度条金箔渐变（横向）
_GOLD_PROGRESS = "qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #936F2C,stop:0.5 #C9A24B,stop:1 #EBD27F)"

# 通用 QSS 模板：占位符用 <KEY>（避免 f-string 大量花括号转义）
_QSS_TEMPLATE = """
    QWidget {
        color: <TEXT>;
        font-family: <SANS>;
        font-size: 13px;
        selection-background-color: <SEL_BG>;
        selection-color: <SEL_TEXT>;
    }
    /* 注：去掉全局 background-color，让 #root 的金缮背景纹穿透至内容区——
       卡片/侧栏/列表各自有 surface 底色，无背景的子部件透出根容器釉底与金线脉络。 */
    QMainWindow {
        background-color: <BG>;
    }

    /* ===== 根容器 #root 的釉底+金缮脉络由 RootWidget paintEvent 绘制（离屏/真机皆可见），
       此处不写 QSS #root 背景，避免覆盖 paintEvent。===== */

    /* ===== 侧边栏（和纸/玄底，纹样由 QLabel 背景层 MotifBackdrop 渲染）===== */
    #sidebar {
        background-color: <SURFACE2>;
        border-right: 1px solid <BORDER>;
    }
    NavButton {
        background-color: transparent;
        color: <TEXT2>;
        border: none;
        border-left: 2px solid transparent;
        border-radius: 0px;
        padding: 9px 12px;
        text-align: left;
        font-family: <SERIF>;
        font-size: 14px;
    }
    NavButton:hover { background-color: <HOVER>; color: <TEXT>; }
    NavButton[active="true"] {
        background-color: <SEL_BG>;
        color: <SEL_TEXT>;
        border-left: 2px solid <ACCENT>;
        font-weight: 600;
    }

    /* ===== 面板 ===== */
    QFrame { background-color: transparent; border: none; }
    .Card {
        background-color: <SURFACE>;
        border: 1px solid <ACCENT>;
        border-radius: 2px;
    }
    QLabel#pageTitle {
        font-family: <SERIF>;
        font-size: 18px;
        font-weight: 600;
        color: <TEXT>;
        padding-right: 28px;
    }
    QLabel#pageSub {
        font-family: <SANS>; font-size: 12.5px; color: <TEXT2>;
        border-left: 3px solid <ACCENT>; padding-left: 9px; padding-top: 2px; padding-bottom: 2px;
        font-weight: 600; letter-spacing: 0.5px;
    }
    QLabel#muted { color: <TEXT3>; }
    QLabel#brandSub { color: <TEXT2>; font-weight: 600; letter-spacing: 1px; }
    QLabel[mono="1"] { font-family: <MONO>; }

    /* ===== 输入（清晰有色边缘：accent_deep 全框 + accent 4px 左规，亮色下也醒目）===== */
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
        background-color: <INPUT_BG>;
        border: 1.5px solid <ACCENT_DEEP>;
        border-left: 4px solid <ACCENT>;
        border-radius: 2px;
        padding: 8px 10px;
        color: <TEXT>;
    }
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
        border: 1.5px solid <ACCENT>;
        border-left: 4px solid <ACCENT>;
    }
    QComboBox QAbstractItemView {
        background-color: <SURFACE>;
        border: 1px solid <BORDER>;
        selection-background-color: <SEL_BG>;
        color: <TEXT>;
    }

    /* ===== 按钮（直角 / 三级清晰 / 描金点睛）===== */
    QPushButton {
        background-color: <SURFACE>;
        color: <TEXT>;
        border: 1px solid <BORDER>;
        border-radius: 2px;
        padding: 9px 18px;
        font-family: <SANS>;
        min-height: 20px;
    }
    QPushButton:hover { background-color: <HOVER>; border-color: <ACCENT>; }
    QPushButton:pressed { background-color: <ACCENT_LIGHT>; }
    QPushButton:disabled { color: <TEXT3>; border-color: <BORDER2>; background-color: <SURFACE>; }
    QPushButton:focus { outline: none; border: 1px solid <ACCENT>; }
    QPushButton#accent {
        background-color: <BTN_FILL>;
        color: <BTN_TEXT>;
        border: 1px solid <ACCENT_DEEP>;
        border-top: 1px solid <ACCENT_LIGHT>;
        font-weight: 600;
        padding: 9px 20px;
    }
    QPushButton#accent:hover { background-color: <BTN_FILL_HOVER>; border-color: <ACCENT_DEEP>; }
    QPushButton#accent:pressed { background-color: <BTN_FILL_PRESS>; border-top: 1px solid <ACCENT_DEEP>; }
    QPushButton#accent:disabled { color: <BTN_TEXT>; background-color: <BORDER2>; border-color: <BORDER>; }
    QPushButton#secondary {
        background-color: transparent;
        color: <ACCENT>;
        border: 1.5px solid <ACCENT>;
        border-radius: 2px;
        font-weight: 600;
        padding: 8px 18px;
    }
    QPushButton#secondary:hover { background-color: <ACCENT_LIGHT>; border-color: <ACCENT_DEEP>; }
    QPushButton#secondary:disabled { color: <TEXT3>; border-color: <BORDER2>; }
    QPushButton#ghost { background-color: transparent; border: none; color: <TEXT2>; border-radius: 2px; padding: 8px 12px; }
    QPushButton#ghost:hover { background-color: <HOVER>; color: <TEXT>; }

    /* ===== 列表（1px 细线分隔，不卡片化）===== */
    QListWidget {
        background-color: <SURFACE>;
        border: 1px solid <BORDER>;
        border-radius: 2px;
        outline: 0;
    }
    QListWidget::item {
        padding: 9px 12px;
        border-bottom: 1px solid <BORDER2>;
        color: <TEXT>;
    }
    QListWidget::item:selected { background-color: <SEL_BG>; color: <SEL_TEXT>; }
    QListWidget::item:hover { background-color: <HOVER>; }

    /* 观测/队列面板：深一档面色 + 金顶规，与输入框（浅色金左规）拉开色差 */
    QListWidget#obs {
        background-color: <SURFACE2>;
        border: 1px solid <BORDER>;
        border-top: 2px solid <ACCENT>;
        border-radius: 2px;
        outline: 0;
    }

    /* ===== 进度条（主题色 / 鎏金金箔渐变）===== */
    QProgressBar {
        background-color: <INPUT_BG>;
        border: 1px solid <BORDER>;
        border-radius: 2px;
        text-align: center;
        color: <TEXT2>;
        height: 14px;
    }
    QProgressBar::chunk {
        background: <PRGBAR_FILL>;
        border-radius: 1px;
    }

    /* ===== 复选 / 单选（自定义指示，无裸态）===== */
    QCheckBox, QRadioButton { spacing: 6px; color: <TEXT>; }
    QCheckBox::indicator, QRadioButton::indicator {
        width: 16px; height: 16px;
        border: 1px solid <BORDER>;
        border-radius: 2px;
        background-color: <INPUT_BG>;
    }
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {
        background-color: <ACCENT>;
        border: 1px solid <ACCENT_DEEP>;
        image: none;
    }
    QCheckBox::indicator:checked {
        /* 勾选态：实心 accent 方块（矢量小勾在 Qt6 的 QSS background-image 不支持，
           故改用实心色块表达已选，清晰无歧义）*/
        background-color: <ACCENT>;
    }
    QRadioButton::indicator { border-radius: 8px; }
    QRadioButton::indicator:checked {
        background-color: <ACCENT>;
    }

    /* ===== 滚动条（主题化，无裸态）===== */
    QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
    QScrollBar::handle:vertical {
        background: <BORDER>;
        border-radius: 2px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover { background: <TEXT3>; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
    QScrollBar::handle:horizontal {
        background: <BORDER>;
        border-radius: 2px;
        min-width: 30px;
    }
    QScrollBar::handle:horizontal:hover { background: <TEXT3>; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

    /* ===== 状态徽章（纯字＋角标，CJK 〔完〕〔漏〕〔更〕〔警〕〔故〕）===== */
    QLabel[badge="ok"]   { background-color: <SUCCESS_L>; color: <SUCCESS>; border-radius: 1px; padding: 2px 7px; font-weight: 600; }
    QLabel[badge="run"]  { background-color: <SEL_BG>;    color: <SEL_TEXT>; border-radius: 1px; padding: 2px 7px; font-weight: 600; }
    QLabel[badge="wait"] { background-color: <BORDER2>;   color: <TEXT2>;   border-radius: 1px; padding: 2px 7px; font-weight: 600; }
    QLabel[badge="warn"] { background-color: <WARN_L>;    color: <WARN>;    border-radius: 1px; padding: 2px 7px; font-weight: 600; }
    QLabel[badge="err"]  { background-color: <DANGER_L>;  color: <DANGER>;  border-radius: 1px; padding: 2px 7px; font-weight: 600; }

    /* ===== 工具提示（主题化，无裸态）===== */
    QToolTip {
        background-color: <SURFACE2>;
        color: <TEXT>;
        border: 1px solid <ACCENT>;
        border-radius: 2px;
        padding: 6px 9px;
        font-family: <SANS>;
        font-size: 12px;
    }

    /* ===== 滚动区域（透明视口 + 主题滚动条）===== */
    QScrollArea { background: transparent; border: none; }
    QScrollArea > QWidget#qt_scrollarea_viewport { background: transparent; border: none; }

    /* ===== 分隔（素净细线 + 中心 accent 小菱点，取代原雷纹「@」母题）===== */
    QFrame#hline {
        background: transparent;
        border: none;
        border-top: 1px solid <BORDER>;
        max-height: 14px; min-height: 14px;
    }

    /* ===== 拖拽区（麻叶纹由 QLabel 背景层 MotifBackdrop 渲染）===== */
    #drop {
        border: 1.5px dashed <BORDER>;
        border-radius: 2px;
        background-color: <SURFACE2>;
    }
    #drop:hover { border-color: <ACCENT>; }
    #drop[drag="1"] {
        border: 2px solid <ACCENT>;
        background-color: <SEL_BG>;
    }
    """


def _check_mark(c: str) -> str:
    """勾选指示小勾（矢量描边，随主题色）。"""
    body = (
        "width='16' height='16' viewBox='0 0 16 16'>"
        "<path d='M3 8.5 L6.5 12 L13 4' fill='none' stroke='{c}' "
        "stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/>"
    ).format(c=c)
    return _svg(body)


def build_theme(name: str = DEFAULT_THEME, mode: str = None) -> str:
    """返回某主题某模式的完整 QSS 字符串。mode 为 None 时用该主题推荐默认明暗。"""
    theme = THEMES.get(name, THEMES[DEFAULT_THEME])
    if mode not in ("light", "dark"):
        mode = DEFAULT_MODE_PER_THEME.get(name, DEFAULT_MODE)
    pal = theme.get(mode, theme[DEFAULT_MODE])

    # 鎏金进度条用金箔渐变，其余用主题色
    if name == "liujin":
        prgbar_fill = _GOLD_PROGRESS
    else:
        prgbar_fill = ("qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                       "stop:0 {d},stop:1 {a})").format(d=pal["accent_deep"], a=pal["accent"])

    btn_text = "#FAFAFA"  # 按钮白字（非纯 #FFFFFF）

    tokens = {
        "BG": pal["bg"], "SURFACE": pal["surface"], "SURFACE2": pal["surface2"],
        "TEXT": pal["text"], "TEXT2": pal["text2"], "TEXT3": pal["text3"],
        "BORDER": pal["border"], "BORDER2": pal["border2"],
        "HOVER": pal["hover"], "INPUT_BG": pal["input_bg"],
        "ACCENT": pal["accent"], "ACCENT_DEEP": pal["accent_deep"], "ACCENT_LIGHT": pal["accent_light"],
        "BTN_FILL": pal["btn_fill"], "BTN_FILL_HOVER": pal["btn_fill_hover"], "BTN_FILL_PRESS": pal["btn_fill_press"],
        "SUCCESS": pal["success"], "SUCCESS_L": pal["success_l"],
        "WARN": pal["warn"], "WARN_L": pal["warn_l"],
        "DANGER": pal["danger"], "DANGER_L": pal["danger_l"],
        "SEL_BG": pal["sel_bg"], "SEL_TEXT": pal["sel_text"],
        "BTN_TEXT": btn_text,
        "PRGBAR_FILL": prgbar_fill,
        "SANS": SANS, "SERIF": SERIF, "MONO": MONO,
    }

    qss = _QSS_TEMPLATE
    for k, v in tokens.items():
        qss = qss.replace("<" + k + ">", v)
    return qss.strip()


def build_qss(theme_name: str = DEFAULT_THEME, mode: str = DEFAULT_MODE) -> str:
    """兼容别名（旧 settings_page 等调用方迁移后使用主题名而非 accent 名）。"""
    # 若传了旧七色 accent 名，平稳回退到朱印基准，避免崩溃
    if theme_name not in THEMES:
        theme_name = DEFAULT_THEME
    return build_theme(theme_name, mode)


if __name__ == "__main__":
    # 自验：6 套全部返回非空合法 QSS
    for n in THEME_NAMES:
        for m in ("light", "dark"):
            q = build_theme(n, m)
            assert q and "{" in q, (n, m)
            print(n, m, len(q))
