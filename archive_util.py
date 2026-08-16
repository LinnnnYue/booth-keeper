# archive_util.py — 共享归档逻辑
# 封装：反查商品 → 分类 →（可选移动源文件）→ 下载封面 → 生成三件套图标
import shutil
from pathlib import Path
import booth_core as bc

# R12：迁移后空目录走回收站（避免永久删，可找回）
try:
    from send2trash import send2trash as _send2trash
    def _remove_to_trash(p: Path) -> None:
        """删除路径到回收站（仅当路径存在时）。"""
        if p.exists():
            try:
                _send2trash(str(p))
            except Exception:
                # 兜底：永久删除
                try:
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
                except Exception:
                    pass
except ImportError:
    def _remove_to_trash(p: Path) -> None:
        """未安装 send2trash 时 fallback rmtree/unlink。"""
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        except Exception:
            pass


def cleanup_empty_parents(start: Path, root: Path, max_levels: int = 6):
    """从 start 向 root 方向走，每层若该目录为空（无任何子项）则送回收站；遇非空或 root 停。
    root 永远不删（库根目录）；中间任意空目录都清。

    R12：走 send2trash 而非永久 rmdir，用户可从回收站找回。
    """
    cur = start
    for _ in range(max_levels):
        if cur == root or cur.parent == cur:
            break
        try:
            if not cur.exists() or any(cur.iterdir()):
                return
            _remove_to_trash(cur)
        except OSError:
            return
        cur = cur.parent


def find_existing_source_in_library(iid: str, name: str, root: str) -> str | None:
    """在 BOOTH 根全库广搜源文件/目录，按 ID 优先（7032906_xxx 命名的目录），
    再按 item 名（简版去除版本号/装饰 + 多变体）匹配，最后按文件 main keyword 匹配。
    返回首个命中路径；用于 R7 SearchPage.archive 自动找源后 move。
    """
    lib = Path(root)
    if not lib.exists():
        return None
    # 0. 全库搜空目录（防止未分类堆积源）
    for d in lib.rglob(f"{iid}_*"):
        if d.is_dir():
            return str(d)
    # 1. 按商品名生成多变的 hint（_ 与空格互换、去掉版本号）
    name_hint = name.split("Ver")[0].split("ver")[0].split("v1")[0].split("_")[0].strip()
    if len(name_hint) >= 4:
        candidates = [name_hint[:16], name_hint[:16].replace(" ", "_"),
                      name_hint[:16].replace(" ", "")]
        for hint in candidates:
            for d in lib.rglob(f"*{hint}*"):
                if d.is_dir():
                    return str(d)
            for f in lib.rglob(f"*{hint}*"):
                if f.is_file() and f.suffix.lower() in (".zip", ".unitypackage", ".rar", ".7z", ".tar", ".gz"):
                    return str(f)
    return None


def consolidate_id(iid: str, root, session) -> dict:
    """R12 一键合并：同 ID 的所有目录（分布在不同类目下）合并到官方类目。

    处理流程：
      1. 找所有 ID_xxx 命名的目录（rglob）
      2. fetch_item 拿官方分类 + 名称
      3. 找官方类目对应目录（不存在则新建）
      4. 合并所有源目录的真实文件 + 三件套到目标
      5. send2trash 旧源目录

    返回 {status, dest, sources, merged_files, dest_cat}。
    """
    root = Path(root)
    it = bc.fetch_item(iid, session)
    if not it:
        return {"status": "err", "msg": "未找到商品", "id": iid}
    name = it.get("name") or iid
    cat = bc.classify(it.get("category_name"), it.get("category_parent_name")) or "未分类"
    dest = root / cat / f"{iid}_{bc.sanitize(name)}"

    # 找所有同 ID 目录
    sources = [d for d in root.rglob(f"{iid}_*") if d.is_dir()]
    if not sources:
        return {"status": "err", "msg": "库内未找到该 ID 目录", "id": iid}

    # 检查 dest 是否已在 sources（不需重新创建）
    dest_in_sources = any(d.resolve() == dest.resolve() for d in sources)

    # 创建 dest
    dest.mkdir(parents=True, exist_ok=True)

    merged = 0
    for src in sources:
        if src.resolve() == dest.resolve():
            continue
        if not src.exists():
            continue
        # 搬源目录所有文件（隐藏文件也搬）
        for child in list(src.iterdir()):
            if not child.is_file():
                continue
            target = dest / child.name
            # 同名不覆盖（保留先到 + 大文件）
            if target.exists() and target.stat().st_size > 0:
                if child.stat().st_size > target.stat().st_size:
                    # 源文件比目标大 → 覆盖（用更完整的源）
                    target.unlink()
                    shutil.move(str(child), str(target))
                    merged += 1
                else:
                    # 源文件比目标小 → 删源（目标已更完整）
                    _remove_to_trash(child)
                continue
            shutil.move(str(child), str(target))
            merged += 1
        # 源目录空 → send2trash
        if not any(src.iterdir()):
            _remove_to_trash(src)
        # walk-up 清空父目录
        cleanup_empty_parents(src, root)

    # 补全三件套（cover/ico/ini）
    cover = dest / "cover.jpg"
    imgs = it.get("images") or []
    if imgs and not cover.exists():
        try:
            bc.download_cover(imgs[0]["original"], str(dest), session)
        except Exception:
            pass
    if cover.exists():
        try:
            bc.make_folder_icon(cover, dest)
        except Exception:
            pass

    return {
        "status": "ok", "id": iid, "name": name, "cat": cat,
        "dest": str(dest), "sources": [str(s) for s in sources],
        "merged_files": merged, "dest_in_sources": dest_in_sources,
    }


def archive_item(iid: str, root, session, move_source: str = None, force: bool = False) -> dict:
    """把一件 Booth 商品归档到 root/类目/ID_标题/。

    返回状态：
      - "ok": 归档成功
      - "exists": 目标目录已存在，未强制覆盖
      - "mismatch": 同 ID 在其他类目下找到（错位），dest 是官方类目
      - "err": 失败

    R7+1 强化：扫整个 BOOTH 库找同 ID（id_xxx 命名的目录），若在不同类目下 → 报 mismatch，
    避免主上疑惑「我手动移到了 3D模型 为啥不直接落 3D发型」。
    """
    it = bc.fetch_item(iid, session)
    if not it:
        return {"status": "err", "msg": "未找到商品", "id": iid}
    name = it.get("name") or iid
    cat = bc.classify(it.get("category_name"), it.get("category_parent_name")) or "未分类"
    dest = Path(root) / cat / f"{iid}_{bc.sanitize(name)}"
    if dest.exists() and not force:
        return {
            "status": "exists", "msg": "已存在",
            "name": name, "cat": cat, "id": iid, "dest": str(dest),
            "dest_cat": cat,  # R7+1：dest 实际分类（官方）
        }
    # R7+1 错位检测：同 ID 在其他类目
    if not force:
        try:
            for d in Path(root).rglob(f"{iid}_*"):
                if d.is_dir() and d.resolve() != dest.resolve():
                    wrong_cat = d.parent.name
                    return {
                        "status": "mismatch", "msg": f"已在「{wrong_cat}」类别下（错位）",
                        "name": name, "cat": cat, "id": iid, "dest": str(dest),
                        "wrong_path": str(d), "wrong_cat": wrong_cat, "dest_cat": cat,
                    }
        except OSError:
            pass
    if dest.exists() and force:
        # 强制重归档：先清掉旧目录（含残留 cover/ico/ini）
        # R12 修复：若 source=dest（同位置重归档），不能 send2trash 整个目录——
        # 会把 zip/unitypackage 等真实文件也送回收站。改为只清残留 cover/ico/ini
        # 和非本体文件，保留本体 zip 等真实商品文件。
        if move_source and Path(move_source).resolve() == dest.resolve():
            # 同位置：仅清残留三件套外的多余文件（不碰本体 zip）
            # R12：直接 import BODY_EXTENSIONS（已在 booth_core）
            for f in list(dest.iterdir()):
                if not f.is_file():
                    continue
                # 保留：本体（zip/unitypackage 等）、已下载的 cover.jpg
                if f.suffix.lower() in bc.BODY_EXTENSIONS \
                        or f.name == 'cover.jpg' \
                        or f.name == '.folder_icon.ico' \
                        or f.name == 'desktop.ini':
                    continue
                # 删除：隐藏/系统/临时文件（Thumbs.db, .DS_Store, debug_out.txt 等）
                _remove_to_trash(f)
        else:
            # 跨位置：旧 dest 整个目录走回收站
            try:
                _remove_to_trash(dest)
            except Exception as e:
                return {"status": "err", "msg": f"清旧目录失败:{e}", "id": iid}
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"status": "err", "msg": f"建目录失败:{e}", "id": iid}

    if move_source:
        src = Path(move_source)
        # 源可能已被先前归档搬走（如 force re-categorize 时），无需 move
        if src.exists():
            try:
                if src.is_dir():
                    # R7 修复：先记录源目录的子项数，确保移动彻底；
                    # 移动后兜底删 desktop.ini / Thumbs.db 等隐藏文件，
                    # 再 walk-up 清理连续空目录（最多到根目录）
                    children = list(src.iterdir())
                    for child in children:
                        if child.name in ("desktop.ini", "Thumbs.db", ".DS_Store"):
                            continue  # 隐藏/系统文件不搬，留在原地，rglob 一起清
                        shutil.move(str(child), str(dest / child.name))
                    # 删隐藏/系统文件（一般仅 desktop.ini / Thumbs.db）
                    for leftover in list(src.iterdir()):
                        if leftover.name in ("desktop.ini", "Thumbs.db", ".DS_Store"):
                            try:
                                leftover.unlink()
                            except Exception:
                                pass
                    # 源空 → R12 走 send2trash 回收站而非 rmdir 永久删
                    if not any(src.iterdir()):
                        _remove_to_trash(src)
                    # walk-up 连续清理空父目录（最多到 root）
                    cleanup_empty_parents(src, Path(root))
                else:
                    shutil.move(str(src), str(dest / src.name))
            except Exception as e:
                return {"status": "err", "msg": f"移动失败:{e}", "id": iid}

    cover = dest / "cover.jpg"
    imgs = it.get("images") or []
    if imgs and not cover.exists():
        try:
            bc.download_cover(imgs[0]["original"], str(dest), session)
        except Exception:
            pass
    if cover.exists():
        try:
            bc.make_folder_icon(cover, dest)
        except Exception:
            pass
    return {"status": "ok", "name": name, "cat": cat, "id": iid, "dest": str(dest)}
