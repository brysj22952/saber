#!/usr/bin/env python3
"""Chrome DevTools Protocol driver for the logged-in GitHub browser.

Target tab selection (in order):
  1. explicit --tab <substr> argument
  2. CDP_TAB environment variable
  3. most recently opened github.com tab
  4. first github.com tab

Usage:
    python3 cdp.py eval "<js>"
    python3 cdp.py goto <url>
    python3 cdp.py newtab <url>
    python3 cdp.py text
    python3 cdp.py click "<selector>"
    python3 cdp.py shot <file.png>
    python3 cdp.py list
"""
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import websocket

CDP_HTTP = "http://127.0.0.1:9333"


def _get(url, method="GET"):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def list_tabs():
    tabs = json.loads(_get(f"{CDP_HTTP}/json/list"))
    return [t for t in tabs if t.get("type") == "page"]


def pick_tab(substr=None):
    substr = substr or os.environ.get("CDP_TAB")
    tabs = list_tabs()
    if substr:
        for t in tabs:
            if substr in t.get("url", ""):
                return t
        print(f"no tab matching {substr!r}; available:", file=sys.stderr)
        for t in tabs:
            print(f"  {t['id']} {t.get('url','')}", file=sys.stderr)
        return None
    gh = [t for t in tabs if "github.com" in t.get("url", "")]
    pool = gh or tabs
    # prefer the tab with the most specific (longest) github url -> usually the one we opened last
    pool = sorted(pool, key=lambda t: len(t.get("url", "")), reverse=True)
    return pool[0] if pool else None


class Session:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=90)
        self._id = 0

    def send(self, method, **params):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def eval(self, expr, awaitp=False):
        r = self.send(
            "Runtime.evaluate",
            expression=expr,
            returnByValue=True,
            awaitPromise=awaitp,
            userGesture=True,
        )
        if r.get("exceptionDetails"):
            d = r["exceptionDetails"]
            return {"__error__": d.get("exception", {}).get("description") or str(d)}
        return r.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    args = sys.argv[2:]
    tab_sub = None
    if args and args[0].startswith("--tab="):
        tab_sub = args[0][6:]
        args = args[1:]

    if cmd == "list":
        for t in list_tabs():
            print(f"{t['id']}  {t.get('title','')[:40]:42s} {t.get('url','')[:100]}")
        return 0

    if cmd == "newtab":
        url = args[0]
        q = urllib.parse.quote(url, safe="")
        try:
            print(_get(f"{CDP_HTTP}/json/new?{q}", method="PUT"))
        except Exception:
            print(_get(f"{CDP_HTTP}/json/new?{q}"))
        return 0

    tab = pick_tab(tab_sub)
    if tab is None:
        return 1
    s = Session(tab["webSocketDebuggerUrl"])
    try:
        if cmd == "eval":
            out = s.eval(args[0])
            print(out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, indent=2))
        elif cmd == "goto":
            s.send("Page.navigate", url=args[0])
            time.sleep(float(args[1]) if len(args) > 1 else 3)
            print("navigated ->", s.eval("location.href"))
        elif cmd == "text":
            print(s.eval("document.body ? document.body.innerText : ''"))
        elif cmd == "click":
            print(s.eval(f"""(() => {{
              const el = document.querySelector({json.dumps(args[0])});
              if (!el) return 'NOT FOUND';
              el.scrollIntoView({{block:'center'}});
              el.click();
              return 'clicked: ' + (el.innerText || el.value || el.tagName).slice(0,120);
            }})()"""))
        elif cmd == "shot":
            r = s.send("Page.captureScreenshot", format="png")
            with open(args[0], "wb") as f:
                f.write(base64.b64decode(r["data"]))
            print(f"saved {args[0]}")
        elif cmd == "wait":
            time.sleep(float(args[0]))
        else:
            print(__doc__)
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
