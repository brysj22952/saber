#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取 AGC 控制台里当前版本的**审核报告**原文(被打回时的整改依据)。

用法:
    python3 harmony/toolchain/agc/agc_audit_report.py                # 抓最新的被打回版本
    python3 harmony/toolchain/agc/agc_audit_report.py --version 1.0.2
    python3 harmony/toolchain/agc/agc_audit_report.py --out /tmp/agc_audit_report.txt

原理:
    1. 点顶层侧栏的「版本历史记录」,进到历史表格;
    2. 在状态是「待修改 / 不通过」的那一行里找到「审核报告」链接并点它
       (它会开一个新标签页,URL 形如 …/agc/index.html#/auditReportView);
    3. 新标签页里再套一层 amp iframe,报告正文在 iframe 里,
       所以顶层和 iframe 的文字都读一遍,拼起来;
    4. 写进 --out 指定的文件,并在标准输出打印一份摘要。

注意:
    * 报告只在**被打回**之后才有,审核中时点不到链接 —— 这时返回非 0 并说明 ✓;
    * 只读页面,不点任何会改状态的按钮 ✓;
    * 轮询器与本脚本共用同一个浏览器标签页,**不要同时跑**(会互相把页面导航坏)。
"""
import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agc_console import Frame  # noqa: E402


def find_cdp_port(default=9333):
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


def list_targets(port):
    with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=10) as r:
        return json.load(r)


def click_sidebar(f, label):
    expr = (
        "(() => {const el=[...document.querySelectorAll('.item-text')]"
        ".find(e=>e.innerText.trim()==='%s'); if(el){el.click(); return 1;} return 0;})()"
    ) % label
    return bool(f.c.eval(expr))


def eval_in_target(target_info, expr, timeout=40):
    """在指定标签页的顶层上下文里求值。"""
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


READ_JS = r"""(() => {
  const parts = [];
  const push = (t) => { if (t && t.trim()) parts.push(t.trim()); };
  push(document.body.innerText || '');
  document.querySelectorAll('iframe').forEach(fr => {
    try { if (fr.contentDocument && fr.contentDocument.body) push(fr.contentDocument.body.innerText || ''); }
    catch (e) { /* 跨域就读不到,忽略 */ }
  });
  return parts.join('\n');
})()"""

# 报告正文在 amp iframe 里,6 条问题分在 4 个 tab 上(应用信息/应用功能/知识产权/应用资质),
# 只读当前 tab 只能拿到一部分 —— 所以下面把每个 tab 都点一遍。
TABS_JS = r"""(() => {
  const out = [];
  document.querySelectorAll('iframe').forEach(fr => {
    let d = null; try { d = fr.contentDocument; } catch (e) {}
    if (!d) return;
    [...d.querySelectorAll('.el-tabs__item')].forEach((t, i) => {
      out.push({i, text: (t.innerText || '').trim(), active: t.classList.contains('is-active')});
    });
  });
  return out;
})()"""

CLICK_TAB_JS = r"""((idx) => {
  let done = 0;
  document.querySelectorAll('iframe').forEach(fr => {
    let d = null; try { d = fr.contentDocument; } catch (e) {}
    if (!d) return;
    const tabs = [...d.querySelectorAll('.el-tabs__item')];
    if (tabs[idx]) { tabs[idx].click(); done = 1; }
  });
  return done;
})"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--out", default="/tmp/agc_audit_report.txt")
    ap.add_argument("--version", default=None, help="指定版本号(如 1.0.2);默认取最近一条被打回的")
    ap.add_argument("--port-open-timeout", type=int, default=40)
    args = ap.parse_args()

    port = args.port or find_cdp_port()
    before = {p.get("id") for p in list_targets(port)}

    f = Frame(port)
    try:
        # 1. 进「版本历史记录」
        if not click_sidebar(f, "版本历史记录"):
            print("提示: 侧栏里没找到「版本历史记录」,尝试重新载入控制台", file=sys.stderr)
            f.c.send("Page.reload")
            time.sleep(16)
            f.close()
            f = Frame(port)
            click_sidebar(f, "版本历史记录")
        time.sleep(9)
        f.close()
        f = Frame(port)

        # 2. 在历史表格里找「审核报告」链接
        #    优先:状态含「待修改/不通过」的行;其次:任何有该链接的行。
        click_js = r"""(() => {
          const rows = [...document.querySelectorAll('tr, .el-table__row')];
          const bad = [], any = [];
          rows.forEach(r => {
            const txt = (r.innerText || '').replace(/\s+/g, ' ');
            const link = [...r.querySelectorAll('a')].find(a => (a.innerText || '').trim() === '审核报告');
            if (!link) return;
            any.push(link);
            if (/待修改|不通过|驳回/.test(txt)) bad.push(link);
          });
          const pick = (bad[0] || any[0]);
          if (!pick) return {ok: 0, reason: '页面上没有「审核报告」链接(可能还没被打回)'};
          pick.click();
          return {ok: 1, rows: rows.length, bad: bad.length};
        })()"""
        res = f.ev(click_js) or {}
    finally:
        f.close()

    if not res.get("ok"):
        print("没抓到审核报告:%s" % res.get("reason", "未知原因"))
        print("(审核报告只有被打回之后才会出现;当前可能还在审核中)")
        return 3

    # 3. 等新标签页
    new_page = None
    deadline = time.time() + args.port_open_timeout
    while time.time() < deadline:
        for p in list_targets(port):
            if p.get("id") not in before and "auditReport" in (p.get("url") or ""):
                new_page = p
                break
        if new_page:
            break
        time.sleep(1.5)

    if not new_page:
        # 退一步:只要出现新标签页(URL 里可能没有 auditReport)
        for p in list_targets(port):
            if p.get("id") not in before:
                new_page = p
                break
    if not new_page:
        print("点了「审核报告」但没等到新标签页")
        return 4

    time.sleep(9)
    # 先看有几个 tab,再逐个点开读
    tabs = eval_in_target(new_page, TABS_JS) or []
    print("报告页面有 %d 个 tab:%s"
          % (len(tabs), " / ".join(t.get("text", "") for t in tabs)), file=sys.stderr)
    parts = []
    if tabs:
        for t in tabs:
            eval_in_target(new_page, CLICK_TAB_JS.replace("((idx) =>", "(%d) =>" % t["i"], 1))
            time.sleep(3)
            piece = eval_in_target(new_page, READ_JS) or ""
            if piece.strip():
                parts.append("========== tab: %s ==========\n%s" % (t.get("text", ""), piece.strip()))
        text = "\n\n".join(parts)
    else:
        text = eval_in_target(new_page, READ_JS) or ""

    text = text.strip()
    if not text:
        print("新标签页打开���了,但没读到报告文字")
        return 5

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print("审核报告已保存:%s(%d 字)" % (args.out, len(text)))
    print("---- 摘要(前 1500 字)----")
    print(text[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
