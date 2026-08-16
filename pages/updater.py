# pages/updater.py — 检查更新
# 拉 GitHub latest release → 比版本号 → 提示用户
# R13+1 修复：改用 HTML 重定向法（releases/latest → 302 Location 取 tag），
#   不消耗 GitHub API 配额（无 token 限流 60/h），API 仅作兜底。
import re
import json
import webbrowser
from pathlib import Path
import requests

GITHUB_API = "https://api.github.com/repos/linnnnnnnnnnnnnnnnnnnnn/booth-keeper/releases/latest"
GITHUB_RELEASES = "https://github.com/linnnnnnnnnnnnnnnnnnnnn/booth-keeper/releases"
PROXY = "http://127.0.0.1:20122/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"}


def _parse_version(ver: str) -> tuple:
    """'1.0.1' → (1, 0, 1)，'v1.0.1' / '1.0.1-rc' 也兼容。"""
    if not ver:
        return ()
    m = re.search(r"v?(\d+(?:\.\d+)*)", ver)
    if not m:
        return ()
    return tuple(int(x) for x in m.group(1).split("."))


def parse_local_version() -> str:
    """读本地版本。优先级：_version 模块（打包后随 PYZ 注入）→ main_window 属性 → 文件。"""
    try:
        from _version import __version__
        if __version__:
            return __version__
    except Exception:
        pass
    try:
        from main_window import __version__
        if __version__:
            return __version__
    except Exception:
        pass
    ver_file = Path(__file__).parent.parent / "_version.py"
    if ver_file.exists():
        try:
            content = ver_file.read_text(encoding="utf-8")
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if m:
                return m.group(1)
        except Exception:
            pass
    return "0.0.0"


def _fetch_html_tag(proxies) -> str | None:
    """HTML 重定向法：GET /releases/latest（302）→ Location 头 → 提取 tag。
    不消耗 API 配额，永不限流。失败返回 None。"""
    try:
        r = requests.get(GITHUB_RELEASES + "/latest", headers=UA,
                         proxies=proxies, timeout=15, allow_redirects=False)
        loc = r.headers.get("Location", "")
        m = re.search(r"/releases/tag/([^/]+)/?$", loc)
        if m:
            return m.group(1)
        # 某些网络环境下直接 200 返回页面，从页面里抓 tag
        if r.status_code == 200:
            m2 = re.search(r"/releases/tag/(v?[\d.]+)", r.text)
            if m2:
                return m2.group(1)
    except Exception:
        pass
    return None


def _fetch_api_release(proxies) -> dict | None:
    """API 法（可能被限流，仅兜底）。"""
    try:
        r = requests.get(GITHUB_API, headers=UA, proxies=proxies, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def fetch_latest_release(proxy: bool = False) -> dict | None:
    """拉最新 release 信息。返回 dict 含 tag_name / html_url / assets。
    通道：HTML 重定向法（主）→ API（兜底）；代理失败自动直连。
    全部失败返回 None（不抛异常）。"""
    proxies = {"http": PROXY, "https": PROXY} if proxy else None

    # 通道 1：HTML 重定向法（无配额）
    tag = _fetch_html_tag(proxies)
    if tag:
        return {
            "tag_name": tag,
            "html_url": f"{GITHUB_RELEASES}/tag/{tag}",
            "assets": [],
        }

    # 通道 2：API（可能限流 403）
    release = _fetch_api_release(proxies)
    if release:
        return release

    # 通道 3：代理失败 → 直连重试（部分环境直连可达）
    if proxies:
        tag = _fetch_html_tag(None)
        if tag:
            return {
                "tag_name": tag,
                "html_url": f"{GITHUB_RELEASES}/tag/{tag}",
                "assets": [],
            }
        release = _fetch_api_release(None)
        if release:
            return release
    return None


def check_update(proxy: bool = False) -> dict:
    """检查更新主函数。返回 dict：
      {
        'has_update': bool,
        'local': '1.3.1',
        'remote': '1.4.0',
        'local_v': (1, 3, 1),
        'remote_v': (1, 4, 0),
        'url': 'https://github.com/...',
        'release': {...原始 release dict...} 或 None,
        'error': None 或 '...',
      }
    """
    local_v = _parse_version(parse_local_version())
    remote = fetch_latest_release(proxy)
    if not remote:
        return {
            "has_update": False,
            "local": parse_local_version(),
            "remote": "",
            "local_v": local_v,
            "remote_v": (),
            "url": GITHUB_RELEASES,
            "release": None,
            "error": "网络失败或无法访问 GitHub",
        }
    remote_v = _parse_version(remote.get("tag_name", ""))
    return {
        "has_update": bool(remote_v and remote_v > local_v),
        "local": parse_local_version(),
        "remote": remote.get("tag_name", ""),
        "local_v": local_v,
        "remote_v": remote_v,
        "url": remote.get("html_url", GITHUB_RELEASES),
        "release": remote,
        "error": None,
    }


def open_release_page() -> None:
    """打开最新 release 页面（用于「去下载」按钮）。"""
    webbrowser.open(GITHUB_RELEASES)
