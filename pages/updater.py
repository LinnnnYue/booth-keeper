# pages/updater.py — 检查更新
# 拉 GitHub latest release API → 比版本号 → 提示用户
import re
import json
import webbrowser
from pathlib import Path
import requests

GITHUB_API = "https://api.github.com/repos/linnnnnnnnnnnnnnnnnnnnn/booth-keeper/releases/latest"
GITHUB_RELEASES = "https://github.com/linnnnnnnnnnnnnnnnnnnnn/booth-keeper/releases"
PROXY = "http://127.0.0.1:20122/"
UA = {"User-Agent": "BoothKeeper/1.0 (update-check)"}


def _parse_version(ver: str) -> tuple:
    """'1.0.1' → (1, 0, 1)，'v1.0.1' / '1.0.1-rc' 也兼容。"""
    if not ver:
        return ()
    m = re.search(r"v?(\d+(?:\.\d+)*)", ver)
    if not m:
        return ()
    return tuple(int(x) for x in m.group(1).split("."))


def parse_local_version() -> str:
    """读本地版本（写在 app_icon 的 __version__ 或打包时 -D APP_VERSION）。

    简化：从 main_window 模块顶层 __version__ 属性读（PyInstaller 打包时由 spec 注入）。
    """
    try:
        from main_window import __version__
        return __version__
    except Exception:
        pass
    # 兜底：从 _version.py 文件读
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


def fetch_latest_release(proxy: bool = False) -> dict | None:
    """拉 GitHub latest release JSON。返回 dict 含 tag_name / html_url / assets。
    失败返回 None（不抛异常）。"""
    try:
        r = requests.get(
            GITHUB_API,
            headers=UA,
            proxies={"http": PROXY, "https": PROXY} if proxy else None,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def check_update(proxy: bool = False) -> dict:
    """检查更新主函数。返回 dict：
      {
        'has_update': bool,
        'local': '1.0.1',
        'remote': '1.1.0',
        'local_v': (1, 0, 1),
        'remote_v': (1, 1, 0),
        'url': 'https://github.com/...',
        'release': {...原始 release dict...} 或 None,
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
            "error": "网络失败或 GitHub API 限流",
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