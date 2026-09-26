# archive_util.py — 共享归档逻辑
# 封装：反查商品 → 分类 →（可选移动源文件）→ 下载封面 → 生成三件套图标
import datetime
import shutil
from pathlib import Path
import booth_core as bc
import diag

# R12：迁移后空目录走回收站（避免永久删，可找回）
# R17：两级清理全失败时留痕——原先静默吞掉，用户会以为空目录已清干净。
try:
    from send2trash import send2trash as _send2trash
    def _remove_to_trash(p: Path) -> None:
        """删除路径到回收站（仅当路径存在时）。回收站失败降级永久删除。"""
        if p.exists():
            try:
                _send2trash(str(p))
            except Exception:
                # 兜底：永久删除
                try:
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                except Exception as e:
                    diag.warn(f"清理失败（回收站与永久删除均失败）：{e}",
                              scope="remove_to_trash", path=str(p))
except ImportError:
    def _remove_to_trash(p: Path) -> None:
        """未安装 send2trash 时 fallback rmtree/unlink（失败留痕）。"""
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        except Exception as e:
            diag.warn(f"清理失败（无 send2trash，永久删除也失败）：{e}",
                      scope="remove_to_trash", path=str(p))


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
    # R17：与 archive_item() 对齐，上报三件套状态——
    # 原先此处静默吞掉封面失败，UI 无从提示，用户只能自己发现缺图。
    cover = dest / "cover.jpg"
    imgs = it.get("images") or []
    cover_ok = cover.exists()
    if imgs and not cover_ok:
        try:
            bc.download_cover(imgs[0]["original"], str(dest), session)
            cover_ok = cover.exists()
        except Exception as e:
            diag.warn(f"封面补全异常：{e}", scope="consolidate_id", iid=iid)
            cover_ok = False
    icon_ok = False
    if cover.exists():
        try:
            bc.make_folder_icon(cover, dest)
            icon_ok = True
        except Exception as e:
            diag.warn(f"图标生成异常：{e}", scope="consolidate_id", iid=iid)
            icon_ok = False

    return {
        "status": "ok", "id": iid, "name": name, "cat": cat,
        "dest": str(dest), "sources": [str(s) for s in sources],
        "merged_files": merged, "dest_in_sources": dest_in_sources,
        "cover_ok": cover_ok, "icon_ok": icon_ok,
    }


# ── R23：留档还原（force 重归档回滚路径）────────────────────────────
# 三处调用点原先各写一份「还原已留档内容」，失败一律静默 pass —— 结果是返回消息
# 写死「已还原」，而磁盘上可能只还原了一半（R17 判为高危：不是没提示，是给了
# 与事实不符的成功承诺）。现收敛为唯一实现，并让调用方拿到真实结果生成消息。
# 演练用例见 tests/test_rollback.py。
_LEGACY_PREFIX = "旧版本_"


def _is_legacy_dir(p: Path) -> bool:
    """是否为 R22 同位置日期留档产物（「旧版本_<时间戳>」目录）。"""
    return p.is_dir() and p.name.startswith(_LEGACY_PREFIX)


def _restore_from_archive(old_dir: Path, dest: Path, iid: str = "") -> tuple[int, list[str]]:
    """把留档目录内的项还原回 dest 根。

    返回 (已还原数, 未能还原的项名列表)。
    重名项不覆盖目标，保留在留档目录内并一并计入「未还原」——对调用方而言
    「没有回到 dest 根」就是未还原，如实计数比分类更重要。
    仅在全部还原成功时移除空壳目录；有残留则保留（内容安全优先于整洁）。
    """
    if old_dir is None or not old_dir.exists():
        return 0, []
    restored, failed = 0, []
    for child in sorted(old_dir.iterdir(), key=lambda p: p.name):
        target = dest / child.name
        if target.exists():
            failed.append(child.name)
            continue
        try:
            shutil.move(str(child), str(target))
            restored += 1
        except Exception as e:
            failed.append(child.name)
            diag.warn(f"还原留档项失败：{child.name} ({e})",
                      scope="restore_archive", iid=iid, path=str(child))
    if not failed:
        try:
            old_dir.rmdir()
        except OSError:
            pass
    return restored, failed


def _describe_restore(restored: int, failed: list, old_dir: Path) -> str:
    """把还原结果转成如实描述 —— 消息必须与磁盘真实状态一致（R23）。"""
    if not failed:
        return "留档内容已还原"
    shown = "、".join(str(x) for x in failed[:3]) + ("…" if len(failed) > 3 else "")
    return f"仅还原 {restored} 项，{len(failed)} 项仍在 {old_dir.name}/（{shown}）"


def archive_item(iid: str, root, session, move_source: str = None, force: bool = False) -> dict:
    """归档一件 Booth 商品 —— 对外的稳定契约入口。

    **契约（R24 起）**：本函数**永不抛异常**。无论内部发生什么，都返回含 `status`
    字段的 dict（失败时 `status == "err"`）。调用方**无需**自行包 try；包了亦无害。

    设计理由：原实现未声明该契约，三个批量调用点因此各自猜测 ——
    `ArchiveWorker` / `FixMismatchWorker` 包了 try，`DragWorker` 没包，同一次异常
    在两个调用点产生不同后果。实测（tests/_probe_batch_abort.py）：注入单件异常时
    DragWorker 4 件只处理 1 件、3 件静默丢弃且 `finished` 不发射（UI 状态机悬挂），
    而另两个调用点 4/4 不受影响。把不变式固化在函数边界上，比要求每个调用点都记得
    包 try 更可靠 —— 未来新增的调用点自动受保护。

    真正的实现是 `_archive_item`（内部逻辑与本次加固前逐字一致）；本函数只做最外层
    兜底。兜底必须留痕（diag.error），否则等于用「静默返回 err」换掉「崩溃」。
    """
    try:
        return _archive_item(iid, root, session, move_source, force)
    except Exception as e:
        diag.error(f"归档异常：{type(e).__name__}: {e}",
                   scope="archive_item", iid=iid)
        return {"status": "err", "msg": f"归档异常：{type(e).__name__}: {e}",
                "id": iid}


def _archive_item(iid: str, root, session, move_source: str = None, force: bool = False) -> dict:
    """把一件 Booth 商品归档到 root/类目/ID_标题/。

    返回状态：
      - "ok": 归档成功
      - "exists": 目标目录已存在，未强制覆盖
      - "mismatch": 同 ID 在其他类目下找到（错位），dest 是官方类目
      - "delisted": 确为已下架（连通性探针通过 + 404），归入 root/已下架商品
      - "err": 失败

    R7+1 强化：扫整个 BOOTH 库找同 ID（id_xxx 命名的目录），若在不同类目下 → 报 mismatch，
    避免主上疑惑「我手动移到了 3D模型 为啥不直接落 3D发型」。
    R17：fetch 失败不妄断 —— 用 classify_item_state 严谨判定（网络可达 + 404 才算下架）。
    R24：本函数可抛异常，由外层 `archive_item` 统一兜底 —— 请勿直接从 UI 调用本函数。
    """

    def _move_into(src_path, dst_dir):
        """把源文件/目录内容搬进 dst_dir，并兜底清理空目录。"""
        src = Path(src_path)
        if src.is_dir():
            for child in list(src.iterdir()):
                if child.name in ("desktop.ini", "Thumbs.db", ".DS_Store"):
                    continue
                shutil.move(str(child), str(dst_dir / child.name))
            try:
                for leftover in list(src.iterdir()):
                    leftover.unlink()
            except Exception:
                pass
            if not any(src.iterdir()):
                _remove_to_trash(src)
            cleanup_empty_parents(src, Path(root))
        else:
            shutil.move(str(src), str(dst_dir / src.name))

    it = bc.fetch_item(iid, session)
    if not it:
        # fetch 失败 → 严谨判定：连通性探针 + 商品页 HTTP
        state, why = bc.classify_item_state(iid, session)
        if state == "delisted":
            dst = Path(root) / "已下架商品" / f"{iid}_{bc.sanitize(iid)}"
            try:
                dst.mkdir(parents=True, exist_ok=True)
                if move_source and Path(move_source).exists():
                    _move_into(move_source, dst)
                return {"status": "delisted", "msg": "已下架，归入「已下架商品」",
                        "id": iid, "name": iid, "cat": "已下架商品", "dest": str(dst),
                        "cover_ok": False, "icon_ok": False}
            except Exception as e:
                return {"status": "err", "msg": f"已下架但迁移失败:{e}", "id": iid}
        if state == "unknown":
            return {"status": "err", "msg": f"无法连接 BOOTH 判定状态（{why}），未归档", "id": iid}
        return {"status": "err", "msg": f"未找到商品（{why}）", "id": iid}
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
        except OSError as e:
            # R17：错位扫描失败 → 记录但不中止（root 个别子目录不可遍历时，
            # 仍应允许单件归档）。后果是可能漏判错位而在其他类目新建重复目录，
            # 故必须留痕，不能静默。R23：接入诊断通道（原先只 print，打包后不可见）。
            diag.warn(f"错位扫描未完成（root 不可遍历？）：{e}",
                      scope="archive_item", iid=iid)
    old_archived = None
    if dest.exists() and force:
        # R22（同位置日期留档）：force 重归档不再「改名备份 + 成功回收旧档」——
        # 主上钦定方案：同位置内新建「旧版本_日期时间」子目录，dest 原有内容
        # 整体移入（标注日期永久留档，不删、不进回收站）；新归档内容直接落 dest 根。
        # 三件套（cover/ico/ini）随后按需重建刷新。
        same_pos = bool(move_source and
                        Path(move_source).resolve() == dest.resolve())
        if not same_pos:
            # dest 有旧内容 → 移入「旧版本_日期_时间」子目录留档（一件不丢）
            rollback_note = "未产生需还原的留档"
            try:
                # 先枚举 dest 现有子项（避免把稍后新建的留档目录自己也搬进去）。
                # R23：跳过既有的「旧版本_*」—— 它们本就是留档产物，再被留档会形成
                # 旧版本_新/旧版本_旧/ 套娃。真机触发场景：上次 force 在「留档完成、
                # 新内容未落」时被中断（见 tests/test_rollback.py 演练四）。
                children = [c for c in dest.iterdir() if not _is_legacy_dir(c)]
                if children:
                    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
                    old_dir = dest / f"旧版本_{stamp}"
                    n = 1
                    while old_dir.exists():
                        old_dir = dest / f"旧版本_{stamp}_{n}"
                        n += 1
                    old_dir.mkdir()
                    try:
                        for child in children:
                            shutil.move(str(child), str(old_dir / child.name))
                    except Exception:
                        # 留档中途失败 → 回滚已移入项，dest 尽量保持原状
                        restored, failed = _restore_from_archive(old_dir, dest, iid)
                        rollback_note = _describe_restore(restored, failed, old_dir)
                        if failed:
                            diag.error(
                                f"留档中途失败，且回滚不完整：{len(failed)} 项仍留在留档目录",
                                scope="archive_item", iid=iid, failed=",".join(failed))
                        raise
                    old_archived = old_dir
            except Exception as e:
                # 留档失败 → dest 尽量还原，报错不归档。消息按实际回滚结果生成，
                # 不再笼统写「目录已尽量还原」（R23）。
                return {"status": "err",
                        "msg": f"旧内容留档失败:{e}（{rollback_note}）", "id": iid}
        # same_pos（源即目标目录）：无新内容可入根，仅刷新三件套，不做任何删除
    else:
        same_pos = False
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"status": "err", "msg": f"建目录失败:{e}", "id": iid}

    if move_source and not same_pos:
        src = Path(move_source)
        # R22：force 归档源必须存在，否则归档必成空目录——
        # 若已发生旧内容留档则先还原留档，再报错（绝不「留档后失败」）。
        if not src.exists():
            # R23：还原结果如实入消息 —— 原实现无论成败都写「已还原留档内容」，
            # 还原失败时即对用户撒谎（详见 tests/test_rollback.py 演练五）。
            restored, failed = _restore_from_archive(old_archived, dest, iid)
            note = (_describe_restore(restored, failed, old_archived)
                    if old_archived else "无留档内容需还原")
            if failed:
                diag.error(f"源不存在，且留档还原不完整：{len(failed)} 项仍在留档目录",
                           scope="archive_item", iid=iid, failed=",".join(failed))
            return {"status": "err", "msg": f"源文件不存在（{note}，未重归档）",
                    "id": iid, "name": name, "cat": cat}
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
                # R22：移动失败 → 还原已留档的旧内容，商品一件不丢
                # R23：还原结果如实入消息（原写死「留档内容已还原」，还原不完整时
                # 用户读到的是一句与磁盘状态不符的承诺 —— 演练三即此场景）。
                restored, failed = _restore_from_archive(old_archived, dest, iid)
                note = (_describe_restore(restored, failed, old_archived)
                        if old_archived else "无留档内容需还原")
                if failed:
                    diag.error(f"移动失败，且留档还原不完整：{len(failed)} 项仍在留档目录",
                               scope="archive_item", iid=iid, failed=",".join(failed))
                return {"status": "err", "msg": f"移动失败:{e}（{note}）", "id": iid}

    cover = dest / "cover.jpg"
    imgs = it.get("images") or []
    cover_ok = cover.exists()
    if imgs and not cover_ok:
        try:
            bc.download_cover(imgs[0]["original"], str(dest), session)
            cover_ok = cover.exists()
        except Exception:
            cover_ok = False
    icon_ok = False
    if cover.exists():
        try:
            bc.make_folder_icon(cover, dest)
            icon_ok = True
        except Exception:
            icon_ok = False
    # R22（同位置日期留档）：归档/移动/封面全部成功 → 旧内容已留档于 dest 内
    # 「旧版本_日期时间」子目录（永不回收、永不删除）。返回 archived_old 供 UI 提示。
    return {"status": "ok", "name": name, "cat": cat, "id": iid, "dest": str(dest),
            "cover_ok": cover_ok, "icon_ok": icon_ok,
            "archived_old": str(old_archived) if old_archived is not None else None}
