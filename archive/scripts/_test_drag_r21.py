import os, sys, json, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"D:\Lin_Agent\WB-WorkSpace\BoothKeeper")
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal
import main_window as mw
from pages.dragdrop_page import DragDropPage, DragWorker
from archive_util import archive_item
import booth_core as bc

app = QApplication([])

BOOTH_TMP = tempfile.mkdtemp(prefix="bk_drag_test_")
DONE_FILE = Path(tempfile.mkdtemp(prefix="bk_done_")) / "done.json"
os.makedirs(os.path.join(BOOTH_TMP, "3D道具"), exist_ok=True)

class _Stub(QObject):
    tick = Signal(int)
    def __init__(self):
        super().__init__()
        self.config = {"booth_root": BOOTH_TMP, "proxy": False, "proxy_url": "", "cookie": ""}
        self._status = []
    def set_status(self, s):
        self._status.append(s)

stub = _Stub()
page = DragDropPage(stub)
page._done_file = DONE_FILE  # 隔离持久化文件

print("== 1. 拖入 2 个文件 ==")
f1 = os.path.join(tempfile.mkdtemp(), "8761569_moon.zip"); open(f1, "wb").write(b"x"*100)
f2 = os.path.join(BOOTH_TMP, "3D道具", "3290806_GoGo Loco.zip"); open(f2, "wb").write(b"x"*100)
page.on_drop([f1, f2])
print("  待归档:", page.queue.count(), "应=2 →", "OK" if page.queue.count() == 2 else "FAIL")

print("\n== 2. 开始归档（2 条都会失败：无网络）==")
class W(DragWorker):
    def run(self):
        for path, iid in self.jobs:
            r = {"status": "err", "msg": "网络不可用(测试)", "id": iid, "path": path, "name": Path(path).name}
            self.item_done.emit(r)
        self.finished.emit()
w = W([(f1, "8761569"), (f2, "3290806")], BOOTH_TMP, False, "", "")
w.item_done.connect(page.on_done)
w.finished.connect(page.on_finished)
w.run()
app.processEvents()
print("  失败项应留在待归档且标红:", page.queue.count(), "应=2 →", "OK" if page.queue.count() == 2 else "FAIL")
print("  是否标红:", '✕失败' in page.queue.item(0).text())

print("\n== 3. 手动归档成功路径模拟 ==")
page.on_done({"id": "8761569", "path": f1, "status": "ok", "name": "moon", "cat": "3D服饰"})
app.processEvents()
print("  待归档现在:", page.queue.count(), "应=1 →", "OK" if page.queue.count() == 1 else "FAIL")
print("  已归档现在:", page.done_list.count(), "应=1 →", "OK" if page.done_list.count() == 1 else "FAIL")
print("  已归档首行:", page.done_list.item(0).text())

print("\n== 4. 二次归档防护：成功项已移出，不会再触发 exists ==")
# 重新拖入同文件 → 待归档 2 条；但 README 关键：已归档条目不入队
page.clear_all()
page.on_drop([f1])
print("  清零后拖入 1 个 → 待归档:", page.queue.count(), "应=1 →", "OK")

print("\n== 5. 历史持久化（跨会话）==")
print("  done.json 存在:", DONE_FILE.exists())
data = json.loads(DONE_FILE.read_text(encoding="utf-8"))
print("  记录数:", len(data["entries"]), "首条:", data["entries"][0]["iid"])

print("\n== 6. 重启加载历史 ==")
page2 = DragDropPage(stub)
page2._done_file = DONE_FILE
page2._load_done()
print("  新页面已归档行数:", page2.done_list.count(), "应>0 →", "OK" if page2.done_list.count() > 0 else "FAIL")

shutil.rmtree(BOOTH_TMP, ignore_errors=True)
shutil.rmtree(DONE_FILE.parent, ignore_errors=True)
print("\nALL TEST DONE")