#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上架后核对:确认应用市场里已经能看到这个应用。

用法:
    python3 harmony/toolchain/agc/agc_store_check.py --app-id <AGC APP ID> [--name Saber]

原理:
    1. 用 CDP 新开一个标签页,访问华为应用市场的应用详情页
       https://appgallery.huawei.com/app/C<appId>(国内站;不同区域站的域名可能不同);
    2. 等页面渲染完,读标题与正文,看应用名/包名是否出现;
    3. 顺便把页面上抓到的「开发者/版本/更新时间」等信息打出来,人工核对。

注意:
    * APP ID 只作为命令行参数传入,不写进仓库 ✓;
    * 商店页是前端渲染的,所以必须用浏览器打开,curl 拿不到内容 ✓;
    * 页面顶部有 Cookie 横幅,会盖住部分内容 —— 正文里仍然能读到应用信息,脚本不代点横幅 ✓;
    * 还没上架时访问 `/app/C<appId>` 会被重定向到商店首页 —— 这正好可以当作「还没上架」的判据 ✓;
    * 刚上架时可能有 CDN 缓存延迟,404/未找到属正常,过几分钟再试 ✓。
"""
import argparse
import json
import sys
import time
import urllib.request

import websocket

DEFAULT_PORT = 9333


def find_cdp_port(default=DEFAULT_PORT):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % default, timeout=5) as r:
            json.load(r)
        return default
    except Exception:
        pass
    for port in range(default, default + 10):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=2) as r:
                if json.load(r):
                    return port
        except Exception:
            continue
    raise SystemExit("找不到可用的 CDP 端口(默认 %d)" % default)


class WS:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=60)
        self._id = 0

    def send(self, method, **params):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                return msg

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True, help="AGC 里的 APP ID(不要写进仓库)")
    ap.add_argument("--name", default="Saber", help="应用名,用来在页面里核对")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--host", default="https://appgallery.huawei.com")
    args = ap.parse_args()

    port = args.port or find_cdp_port()
    url = "%s/app/C%s" % (args.host.rstrip("/"), args.app_id)

    # 找一个浏览器级连接(拿它来开新标签页)
    with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % port, timeout=10) as r:
        browser_ws = json.load(r)["webSocketDebuggerUrl"]
    b = WS(browser_ws)
    target = b.send("Target.createTarget", url="about:blank")["result"]["targetId"]
    b.close()

    time.sleep(2)
    with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=10) as r:
        pages = [p for p in json.load(r) if p.get("id") == target]
    if not pages:
        raise SystemExit("新标签页没建起来")
    c = WS(pages[0]["webSocketDebuggerUrl"])
    try:
        c.send("Page.enable")
        c.send("Page.navigate", url=url)
        time.sleep(14)
        title = c.send(
            "Runtime.evaluate",
            expression="(() => document.title)()",
            returnByValue=True,
        )["result"]["result"].get("value")
        body = c.send(
            "Runtime.evaluate",
            expression="(() => document.body.innerText.replace(/\\s+/g, ' '))()",
            returnByValue=True,
        )["result"]["result"].get("value") or ""
        print("URL  : %s" % url)
        print("标题 : %s" % title)
        hit = args.name in body
        print("是否出现应用名「%s」: %s" % (args.name, "是 ✓" if hit else "否 ✗"))
        print("---- 页面正文(前 600 字)----")
        print(body[:600])
    finally:
        c.close()
        # 关掉刚才开的标签页,免得越开越多
        try:
            b2 = WS(browser_ws)
            b2.send("Target.closeTarget", targetId=target)
            b2.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
