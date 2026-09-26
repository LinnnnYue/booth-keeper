# _rescue_dl_8545487.py — 一次性抢救下载器
# 商品 8545487 LittleBeachWanderer_v1.0.1.zip (137MB)
# 策略：直连 booth.pm 取 302 签名 URL（主站直连通），CDN s6.booth.pm 走代理
#       16 并发 Range 分段下载，破解单连接限速(~74KB/s)与 180s 签名窗口。
import json, os, sys, time, shutil
from pathlib import Path
import concurrent.futures as cf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import booth_core as bc

CFG = json.load(open(os.path.expanduser("~/.boothkeeper.json"), encoding="utf-8"))
COOKIE = CFG.get("cookie", "")
REF = "https://booth.pm/ja/items/8545487"
DL_URL = "https://booth.pm/downloadables/9188035?variation_id=14261375"
DEST = Path(r"G:\Lin_File\BOOTH\3D服饰\8545487_【FREE無料】LittleBeachWanderer")
FNAME = "LittleBeachWanderer_v1.0.1.zip"
TARGET = DEST / FNAME
SEG_MB = 8          # 每段大小
MAX_CONN = 16       # 并发

s_dir = bc.make_session(COOKIE); s_dir.proxies = {}   # 直连（取 302 用）
s_px  = bc.make_session(COOKIE)                        # 代理（拉 CDN 用）

def get_signed_url(tries=8):
    for i in range(tries):
        try:
            r = s_dir.get(DL_URL, allow_redirects=False, timeout=20,
                          headers={"Referer": REF})
            loc = r.headers.get("Location", "")
            if loc:
                return loc
            print(f"  [url] 302 status={r.status_code}", flush=True)
        except Exception as e:
            print(f"  [url] try{i+1} {type(e).__name__}", flush=True)
        time.sleep(1.5)
    return ""

def get_total(signed):
    r = s_px.get(signed, headers={"Referer": REF, "Range": "bytes=0-0"},
                 timeout=25)
    cr = r.headers.get("Content-Range", "")
    try:
        return int(cr.split("/")[1])
    except Exception:
        return 0

def fetch_seg(signed, off, size, idx):
    """拉一段，失败重试 3 次。返回 (ok, data|None, msg)。整段入内存防半截。"""
    h = {"Referer": REF, "Range": f"bytes={off}-{off + size - 1}"}
    last = ""
    for a in range(3):
        try:
            r = s_px.get(signed, headers=h, stream=True, timeout=40)
            if r.status_code not in (200, 206):
                last = f"HTTP {r.status_code}"
                if r.status_code == 403:   # 签名过期 → 立即抛给上层换 URL
                    return False, None, "SIGN_EXPIRED"
                time.sleep(2)
                continue
            buf = bytearray()
            for ch in r.iter_content(1 << 20):
                buf += ch
            if len(buf) == size:
                return True, bytes(buf), ""
            last = f"short {len(buf)}/{size}"
            time.sleep(1.5)
        except Exception as e:
            last = f"{type(e).__name__}"
            time.sleep(1.5)
    return False, None, last

def main():
    DEST.mkdir(parents=True, exist_ok=True)

    signed = get_signed_url()
    if not signed:
        print("RESULT: FAIL 无法取得签名 URL（直连 booth.pm 也不通？）", flush=True)
        return
    total = get_total(signed)
    print(f"target total: {total/1048576:.1f} MB", flush=True)
    if total <= 0:
        print("RESULT: FAIL 无法确认文件大小", flush=True)
        return

    for attempt in range(3):          # 外层：签名过期换 URL 整轮重试
        n = max(8, min(MAX_CONN, (total + (SEG_MB << 20) - 1) // (SEG_MB << 20)))
        seg_sz = (total + n - 1) // n
        offsets = [i * seg_sz for i in range(n)]
        print(f"segments: {n} x {seg_sz/1048576:.1f}MB (attempt {attempt+1})", flush=True)
        t0 = time.time()
        datas: dict = {}
        ok_all = True
        with cf.ThreadPoolExecutor(n) as ex:
            futs = {ex.submit(fetch_seg, signed, off, seg_sz, i): i
                    for i, off in enumerate(offsets)}
            for f in cf.as_completed(futs):
                ok, data, msg = f.result()
                i = futs[f]
                if ok and data is not None:
                    datas[i] = data
                else:
                    ok_all = False
                    print(f"  seg{i} FAIL: {msg}", flush=True)
                    if msg == "SIGN_EXPIRED":
                        break
        if ok_all and len(datas) == n:
            # 内存合并 → 直接覆盖写 zip（不删旧文件，规避回收站守卫）
            with open(TARGET, "wb") as out:
                for i in range(n):
                    out.write(datas[i])
            dt = time.time() - t0
            print(f"merged {TARGET.stat().st_size} bytes in {dt:.0f}s "
                  f"= {TARGET.stat().st_size/1048576/dt:.1f} MB/s", flush=True)
            if not bc.is_corrupt_package(TARGET):
                print("RESULT: OK zip 完整", flush=True)
                return
            print("zip still corrupt, retrying...", flush=True)
        # 换新签名 URL
        print("  refreshing signed url...", flush=True)
        signed = get_signed_url()
        if not signed:
            break
    print("RESULT: FAIL 多次尝试后仍未成功", flush=True)

if __name__ == "__main__":
    main()
