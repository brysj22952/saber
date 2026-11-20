#!/usr/bin/env python3
"""查询 AGC 控制台里当前版本的状态(阶段 5 轮询审核用)。

用法:
    python3 harmony/toolchain/agc/agc_version_status.py            # 读当前浏览器标签页
    python3 harmony/toolchain/agc/agc_version_status.py --url <控制台地址>

设计说明:
* 只复用 harmony/toolchain/agc/agc_console.py 里的 CDP 客户端,**不改动它的既有逻辑**;
* 不在脚本里写死任何 AGC 的 APP ID / 项目 ID(那些是账号私有标识,不能进仓库),
  需要的话用 --url 或直接让浏览器停在「版本/升级」页;
* 状态关键词按 AGC 的实际文案匹配:预审中 / 审核中 / 已上架 / 已发布 / 预审不通过 等。
"""

import argparse
import json
import time
import re
import sys
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from agc_console import Frame  # noqa: E402

# 出现在版本页上的状态词(按优先级排序,先匹配到的先返回)
STATUS_PATTERNS = [
    "预审不通过",
    "审核不通过",
    "正在审核",
    "正在等待审核",
    "审核中",
    "预审中",
    "已上架",
    "已发布",
    "审核通过",
    "准备提交",
    "未提交",
]


def find_cdp_port(default=9333):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % default, timeout=5) as r:
            json.load(r)
        return default
    except Exception:
        pass
    # 退而求其次:找一个能返回 /json/list 的端口
    for port in range(9333, 9343):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=2) as r:
                if json.load(r):
                    return port
        except Exception:
            continue
    raise SystemExit("找不到可用的 CDP 端口(默认 9333)")


def list_targets(port):
    """列出 9333 上的所有标签页。"""
    with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=10) as r:
        return json.load(r)


def pick_app_target(port, match=None):
    """挑「应用详情页」那个标签页 —— **不能假设都在主标签页**。

    2026-11-20 实测(Launch 做的干净实测,本会话独立复核):
      * 真正会**新开标签页**的是版本历史里的「**审核报告**」链接,
        开在 ``#/auditReportView``;
      * 「**软件包管理**」**不会**新开标签页 —— 标签页数恒为 3,
        点「1.0.2 待修改」顶层 hash 变 ``.../myApp/6917621319756237551/v2079739086494559168``、
        点「软件包管理」变 ``.../172249065903274627``,是**同一标签页内切换** ✓。

    而本脚本原来用 ``Frame(port)`` —— 它连的是 ``/json/list`` 里的**第一个** page,
    顺序一变就可能连到**审核报告页**(那个页面没有左侧栏、没有版本列表)✗
    → 读出来永远是「状态: 未识别」✗。

    判据(按优先级):
      1. URL 含 ``#/myApp/`` —— 应用详情页 ✓;
      2. 顶层的 ``.item-text`` 数量 > 0 —— 有左侧栏的页面 ✓;
      3. 兜底:第一个非审核报告页。

    ``match`` 是额外的 URL 子串过滤(给命令行用)。
    """
    pages = [t for t in list_targets(port) if t.get("type") == "page" and t.get("url")]
    if match:
        picked = [t for t in pages if match in t["url"]]
        if picked:
            pages = picked
    # 1) 优先应用详情页
    for t in pages:
        if "#/myApp/" in t["url"]:
            return t
    # 2) 退而求其次:有左侧栏的页面
    for t in pages:
        if "auditReport" in t["url"]:
            continue
        try:
            n = eval_in_target(t, "(() => document.querySelectorAll('.item-text').length)()")
            n = int(n)
        except Exception:
            n = 0
        if n > 0:
            return t
    # 3) 兜底:第一个不是审核报告页的
    for t in pages:
        if "auditReport" not in t["url"]:
            return t
    return None


def eval_in_target(target_info, expr, timeout=30):
    """在指定标签页的顶层上下文里求值(不依赖 Frame 的隔离世界)。"""
    import websocket
    w = websocket.create_connection(target_info["webSocketDebuggerUrl"], timeout=timeout)
    try:
        w.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                           "params": {"expression": expr, "returnByValue": True}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = json.loads(w.recv())
            if msg.get("id") == 1:
                return (msg.get("result", {}).get("result", {}) or {}).get("value")
        return None
    finally:
        try:
            w.close()
        except Exception:
            pass


def _click_sidebar(f, label, exact=True):
    """点顶层文档侧栏里的某一项;点不到返回 False。"""
    if exact:
        expr = (
            "(() => {const el=[...document.querySelectorAll('.item-text')]"
            ".find(e=>e.innerText.trim()==='%s'); if(el){el.click(); return 1;} return 0;})()"
        ) % label
    else:
        expr = (
            "(() => {const el=[...document.querySelectorAll('.item-text')]"
            ".find(e=>e.innerText.trim().includes('%s')); if(el){el.click(); return 1;} return 0;})()"
        ) % label
    return bool(f.c.eval(expr))


def _click_top_nav(f, label):
    """点顶栏(不是侧栏)里的某一项,例如「应用管理」。"""
    expr = (
        "(() => {const els=[...document.querySelectorAll('a,li,span,div')]"
        ".filter(e=>e.children.length===0&&(e.innerText||'').trim()==='%s');"
        " if(!els.length) return 0; els[0].click(); return 1;})()"
    ) % label
    return bool(f.c.eval(expr))


def _open_version_page(f, port, target_id=None):
    """回到「应用 → 版本/升级」页。

    浏览器可能停在项目级页面(侧栏是「总览/证书/Profile/…」,没有「版本/升级」),
    这时点顶栏的「应用管理」——它会直接进到最近打开的那个应用,再点侧栏的「版本/升级」。

    2026-11-20 修:重建 Frame 时必须带上 ``target_id`` ——
    不带就会连回 ``/json/list`` 里的第一个 page(可能是审核报告页)✗。
    """
    if _click_sidebar(f, "版本/升级"):
        return
    if _click_top_nav(f, "应用管理"):
        time.sleep(10)
        f.close()
        f = Frame(port, target_id=target_id)
    _click_sidebar(f, "版本/升级")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--url", default=None, help="控制台地址;给了就跳转过去再读")
    ap.add_argument("--raw", action="store_true", help="把整页文本打出来")
    ap.add_argument("--match", default=None,
                    help="只考虑顶层 URL 含这个子串的标签页(如 '#/myApp/')")
    ap.add_argument(
        "--bundle",
        default="com.sabernotes.saber",
        help="期望看到的包名;页面上没有它就说明连到了别的应用/别的标签页,直接跳过",
    )
    args = ap.parse_args()

    port = args.port or find_cdp_port()
    sidebar = ""

    # 2026-11-20 修:原来用 Frame(port) —— 它连 /json/list 里的**第一个** page,
    # 顺序一变就可能连到**审核报告页**(没有左侧栏、没有版本列表)✗
    # → 读出来永远是「状态: 未识别」✗。现在按 URL 特征挑应用详情页 ✓。
    target = pick_app_target(port, match=args.match)
    if not target:
        print("状态: 找不到应用详情页标签页(是不是登录态过期了?)")
        return
    print("应用标签页:%s" % target.get("url"), file=sys.stderr)

    f = Frame(port, target_id=target.get("id"))
    try:
        if args.url:
            f.c.send("Page.navigate", url=args.url)
            time.sleep(18)
        else:
            # 先点到应用的「版本/升级」页,保证读到的是版本状态而不是别的页面。
            # 点完如果没读到包名(页面没切过来 / 有人同时在操作控制台),再点一次;
            # 还是会话被重定向到「华为 APIs 使用协议」这类页面,就把整个控制台重载一次。
            for attempt in range(3):
                _open_version_page(f, port, target_id=target.get("id"))
                time.sleep(9)
                # 路由切换后 iframe 的隔离世界会被重建,旧 ctx 失效 ⇒ 重新建一个 Frame
                f.close()
                f = Frame(port, target_id=target.get("id"))
                text = f.ev("(() => document.body.innerText.replace(/\\s+/g, ' '))()") or ""
                if args.bundle and args.bundle in text:
                    break
                if attempt < 2:
                    time.sleep(6)
            else:
                # 兜底:重载控制台(SPA 会按 hash 回到原来的路由)
                f.c.send("Page.reload")
                time.sleep(16)
                f.close()
                f = Frame(port, target_id=target.get("id"))
                text = f.ev("(() => document.body.innerText.replace(/\\s+/g, ' '))()") or ""
        text = f.ev("(() => document.body.innerText.replace(/\\s+/g, ' '))()") or ""
        # iframe 里的版本页可能还在加载,没读到状态就再等一轮
        if "状态" not in (text or ""):
            time.sleep(10)
            text = f.ev("(() => document.body.innerText.replace(/\\s+/g, ' '))()") or ""
        # 版本列表在顶层文档的侧栏里(形如 "1.0.1 预审中"),
        # 一个应用可能有多个历史版本,只有版本号最大的那个才是当前要盯的。
        sidebar = f.c.eval(
            """(() => [...document.querySelectorAll('.item-text')]
                 .map(e => (e.innerText || '').trim())
                 .filter(t => /^\\d+\\.\\d+\\.\\d+/.test(t))
                 .join('\\n'))()"""
        ) or ""
    finally:
        f.close()

    if args.raw:
        print(text[:3000])
        return

    # 页面上得有我们这个应用的包名,否则说明连到了别的标签页/别的应用,宁可不报
    if args.bundle and args.bundle not in (text or ""):
        print("状态: 跳过(页面上没有包名 %s,可能连到了别的标签页)" % args.bundle)
        return

    # 版本号最大的那条 = 当前版本(旧版本还留在列表里,不能只看第一个)
    latest = None
    for line in (sidebar or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        mv = re.match(r"^(\d+\.\d+\.\d+)\s*(.*)$", line)
        if not mv:
            continue
        key = tuple(int(x) for x in mv.group(1).split("."))
        if latest is None or key > latest[0]:
            latest = (key, mv.group(1), mv.group(2).strip())

    if latest:
        print("版本: %s" % latest[1])
        status = latest[2]
        if status:
            print("状态: %s" % status)
        else:
            print("状态: 未识别(侧栏里该版本没有状态词)")
        if "不通过" in status:
            print("提示: 状态含「不通过」,点「检测报告」按报告修复后重新提交")
        return

    # 侧栏没读到就退回整页文本匹配
    found = [s for s in STATUS_PATTERNS if s in text]
    m = re.search(r"状态：\s*([^\s]+)", text)
    if m:
        print("状态: %s" % m.group(1))
    elif found:
        print("状态: %s" % found[0])
    else:
        print("状态: 未识别(页面上没有状态关键词,可能不在版本页)")

    # 状态里带「不通过」才提示去看检测报告(页面的说明文字里也会出现「检测报告」四个字)
    if "不通过" in (m.group(1) if m else ""):
        print("提示: 状态含「不通过」,点「检测报告」按报告修复后重新提交")
    v = re.search(r"(\d+\.\d+\.\d+)\s*新版本", text)
    if v:
        print("版本: %s" % v.group(1))


if __name__ == "__main__":
    main()
