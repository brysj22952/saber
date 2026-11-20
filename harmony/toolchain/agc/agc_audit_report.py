#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取 AGC 控制台里当前版本的**审核报告**原文(被打回时的整改依据)。

用法:
    python3 harmony/toolchain/agc/agc_audit_report.py                # 抓最新的被打回版本
    python3 harmony/toolchain/agc/agc_audit_report.py --version 1.0.2
    python3 harmony/toolchain/agc/agc_audit_report.py --out /tmp/agc_audit_report.txt
    python3 harmony/toolchain/agc/agc_audit_report.py --read-open     # 只读已打开的报告页(不点任何东西)
    python3 harmony/toolchain/agc/agc_audit_report.py --self-test     # 纯函数级自测(不碰浏览器)

--------------------------------------------------------------------------
2026-11-20 用首尔机 CDP(9333)对真实报告页做的 DOM 取证结论 —— 改代码前先看这段
--------------------------------------------------------------------------
1) 报告页有**两种形态**,都要能处理:
     A) .../agc/index.html#/auditReportView  → 正文在 amp iframe(#mainIframeView)里
     B) .../agc/amp/?_=2026...#/auditReport  → 正文直接在顶层文档
   实测 A 形态下顶层文档只有页脚(108 字),**一个 tab 都没有**;报告全文都在 iframe 里。
   旧脚本只按 iframe 找 tab,碰上 B 形态就必然读到 0 个 tab。

2) 报告正文里(实测 1.0.2 的报告):
     .el-tabs__item  2 个:"应用功能 2"(is-active) / "应用资质 1"
     .el-tab-pane   2 个:pane-0 display=block(578 字) / pane-1 display=none(285 字)
   ⚠ 关键: **未激活的 pane 是 display:none,但内容仍然在 DOM 里**;
     Chrome 对 display:none 元素读 innerText 会回落到 textContent,所以文本读得到。
   旧脚本只读 `document.body.innerText`(只含**可见** pane)→「应用资质」那条
   **唯一的阻塞意见**(《Saber官方授权书》)整个丢失。
   实测旧产物 /tmp/agc_audit_report_1.0.2.txt 里 "授权书" 出现 **0 次**。

3) 分类名一共 4 个:应用信息 / 应用功能 / 知识产权 / 应用资质。但**报告页只有 2 个 tab**:
     「应用信息」是报告头部的 .base-info 区(不是 tab);
     「知识产权」在 1.0.2 报告里**根本不存在**(审核员本轮没提该类问题,页面就不渲染)。
   → 所以自检按「页面实际声明的 tab」逐个核对,而不是硬编码 4 个名字;
     4 个标准分类里没出现的,记为「本轮未涉及」并打印出来,不算失败。

4) tab 标题里带问题数徽标(「应用功能 2」),徽标是 .serious-count 里的数字,
   核对时要先把徽标剥掉,否则拿「应用功能 2」去文本里找会找不到。

只读页面,不点任何会改状态的按钮 ✓
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agc_console import Frame  # noqa: E402

# Windows 控制台默认 GBK,自测里打的 ✓/✗ 会 UnicodeEncodeError —— 统一走 UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STANDARD_CATEGORIES = ["应用信息", "应用功能", "知识产权", "应用资质"]
HEADER_MARKERS = ["包名", "版本号", "报告生成时间"]
REPORT_TITLE_MARK = "上架审核报告"
DEFAULT_FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "fixtures", "audit_report_1.0.2.json")


class ReportError(Exception):
    """报告没抓到 / 抓不全 —— 宁可报错,也不要静默返回空。"""


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


def pick_report_target(targets):
    """按 URL 特征挑报告页标签页 —— 不假设它在主标签页(实测软件包管理/审核报告都单独开页)。"""
    pages = [t for t in targets if t.get("type") == "page" and t.get("url")]
    if not pages:
        return None
    for feat in ("auditReportView", "/amp/"):          # 先要 index.html#/auditReportView,再退到 amp 直链
        for t in pages:
            if feat in t["url"]:
                return t
    for t in pages:
        if "auditReport" in t["url"]:
            return t
    return None


def pick_console_target(port):
    """挑「**有左侧栏**的控制台标签页」(应用详情/版本历史记录页)。

    2026-11-20 实测踩到的坑:点「审核报告」会**新开**一个标签页
    (URL 含 auditReportView),而那个页面**没有左侧栏**。
    agc_console.CDP 默认连 `/json/list` 里的第一个 page 标签,
    两个都是 developer.huawei.com → 排序并列 → 可能连到审核报告页 ✗
    → 于是「版本历史记录」点不到,报「没抓到审核报告」✗。

    判据:页面上 `.item-text`(左侧栏项)数量 > 0 的那个标签页 ✓。
    """
    for page in list_targets(port):
        if page.get("type") != "page":
            continue
        try:
            n = eval_in_target(page,
                               "(() => document.querySelectorAll('.item-text').length)()")
            n = int(n)
        except Exception:
            n = 0
        if n > 0:
            return page
    return None


def eval_in_target(target_info, expr, timeout=60):
    """在指定标签页的顶层上下文里求值。"""
    import websocket
    w = websocket.create_connection(target_info["webSocketDebuggerUrl"], timeout=timeout)
    try:
        w.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                           "params": {"expression": expr, "returnByValue": True,
                                      "awaitPromise": True}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = json.loads(w.recv())
            if msg.get("id") == 1:
                res = msg.get("result", {}) or {}
                if res.get("exceptionDetails"):
                    return {"__error__": json.dumps(res["exceptionDetails"], ensure_ascii=False)[:800]}
                return (res.get("result", {}) or {}).get("value")
        return None
    finally:
        try:
            w.close()
        except Exception:
            pass


# 一次性把「顶层文档 + 所有可读的 iframe 文档」里的 tab / pane / 报告头都取回来。
COLLECT_JS = r"""
(() => {
  const docs = [];
  const push = (label, d) => { if (d) docs.push({label: label, doc: d}); };
  push('顶层文档', document);
  document.querySelectorAll('iframe').forEach((fr, i) => {
    let d = null;
    try { d = fr.contentDocument; } catch (e) {}
    push('iframe#' + i + '(' + (fr.id || fr.className || '?') + ')', d);
  });
  const out = {url: location.href, docs: []};
  for (const item of docs) {
    const d = item.doc;
    const tabs = [...d.querySelectorAll('.el-tabs__item')].map((t, i) => {
      const badge = t.querySelector('.serious-count');
      const badgeText = badge ? (badge.innerText || '').trim() : '';
      const full = (t.innerText || '').replace(/\s+/g, ' ').trim();
      const title = (badgeText && full.endsWith(badgeText))
        ? full.slice(0, full.length - badgeText.length).trim() : full;
      return {i: i, id: t.id || '', title: title, full: full,
              active: t.classList.contains('is-active'),
              ariaSelected: t.getAttribute('aria-selected'),
              controls: t.getAttribute('aria-controls') || ''};
    });
    const panes = [...d.querySelectorAll('.el-tab-pane')].map((p, i) => {
      let display = '?';
      try { display = (d.defaultView || window).getComputedStyle(p).display; } catch (e) {}
      return {i: i, id: p.id || '', cls: p.className || '', display: display,
              visible: display !== 'none', text: (p.innerText || '')};
    });
    const baseInfo = [...d.querySelectorAll('.base-info')]
      .map(e => (e.innerText || '').replace(/\s+/g, ' ').trim());
    // 页面框架文字(标题、结论、页脚…),把 .el-tab-pane 摘掉后再取,
    // 这样既有「上架审核报告」「审核未通过,共检测出错误问题3个。」,又不会重复 pane 的内容。
    let chrome = '';
    try {
      const clone = d.body.cloneNode(true);
      clone.querySelectorAll('.el-tab-pane').forEach(p => p.remove());
      chrome = (clone.innerText || '').replace(/\s+/g, ' ').trim();
    } catch (e) {}
    out.docs.push({label: item.label, tabs: tabs, panes: panes, baseInfo: baseInfo,
                   chrome: chrome,
                   bodyLen: (d.body ? (d.body.innerText || '').length : 0)});
  }
  return out;
})()
"""

# 备选方案:点 tab(只有当某个 pane 的文本是空的时候才用)
CLICK_TAB_JS = r"""
((tabId) => {
  let done = 0;
  const docs = [document];
  document.querySelectorAll('iframe').forEach(fr => {
    try { if (fr.contentDocument) docs.push(fr.contentDocument); } catch (e) {}
  });
  for (const d of docs) {
    const t = d.querySelector('#' + tabId) || d.querySelector('.el-tabs__item');
    if (t) { t.click(); done = 1; break; }
  }
  return done;
})"""


def strip_badge(full):
    """tab 标题「应用功能 2」→ 「应用功能」;没有徽标就原样返回。"""
    full = (full or "").strip()
    return re.sub(r"\s*\d+\s*$", "", full) if re.search(r"\s\d+$", full) else full


def build_report(raw):
    """把 COLLECT_JS 的原始结果整理成 (正文, 元信息)。纯函数,便于自测。"""
    if not raw or raw.get("__error__"):
        raise ReportError("页面求值失败:%s" % (raw or {}).get("__error__"))
    docs = raw.get("docs") or []
    if not docs:
        raise ReportError("页面上没读到任何可读文档(顶层与 iframe 都读不到)")

    blocks = []
    titles = []          # 页面实际声明的 tab 标题(去掉徽标)
    panes_found = 0
    used_docs = []

    for doc in docs:
        tabs = doc.get("tabs") or []
        panes = doc.get("panes") or []
        if not tabs and not panes and not doc.get("baseInfo"):
            continue
        used_docs.append("%s(tabs=%d panes=%d)" % (doc.get("label"), len(tabs), len(panes)))
        for t in tabs:
            title = strip_badge(t.get("title") or t.get("full") or "")
            if title and title not in titles:
                titles.append(title)
        for bi in doc.get("baseInfo") or []:
            if bi:
                blocks.append("=== 报告头部信息 ===\n%s" % bi.strip())
        chrome = (doc.get("chrome") or "").strip()
        if chrome:
            blocks.append("=== 报告页正文框架 ===\n%s" % chrome)
        # tab 标题 → pane 的对应关系(靠 aria-controls / id 序号),没有就按顺序配
        by_id = {p.get("id"): p for p in panes if p.get("id")}
        for idx, p in enumerate(panes):
            panes_found += 1
            title = ""
            for t in tabs:
                ctrl = t.get("controls") or ""
                if ctrl and ctrl == p.get("id"):
                    title = strip_badge(t.get("title") or t.get("full") or "")
                    break
            if not title and idx < len(tabs):
                title = strip_badge(tabs[idx].get("title") or tabs[idx].get("full") or "")
            if not title:
                title = p.get("id") or ("pane#%d" % idx)
            text = (p.get("text") or "").strip()
            blocks.append("=== 分类: %s (class=%s display=%s%s) ===\n%s"
                          % (title, p.get("cls"), p.get("display"),
                             "" if p.get("visible") else " [未激活但内容在DOM里]",
                             text if text else "(空)"))
    text = "\n\n".join(blocks).strip()
    meta = {
        "url": raw.get("url"),
        "tab_titles": titles,
        "pane_count": panes_found,
        "docs": used_docs,
        "text_len": len(text),
    }
    if panes_found == 0:
        raise ReportError("页面上没找到 .el-tab-pane(报告正文没渲染出来?):%s" % used_docs)
    return text, meta


def verify_report(text, meta, expect_version=None, strict_categories=False):
    """自检:抓到的文本必须真的包含报告的各个分类与头部信息。缺任一就报错。"""
    problems = []
    missing_tabs = [t for t in meta.get("tab_titles", []) if t not in text]
    if missing_tabs:
        problems.append("以下 tab 的内容没抓到:%s" % "、".join(missing_tabs))
    if not meta.get("tab_titles"):
        problems.append("页面没声明任何 tab 分类(报告页结构可能变了)")
    missing_headers = [m for m in HEADER_MARKERS if m not in text]
    if missing_headers:
        problems.append("报告头部信息缺失:%s" % "、".join(missing_headers))
    if REPORT_TITLE_MARK not in text:
        problems.append("没找到报告标题「%s」" % REPORT_TITLE_MARK)
    if expect_version:
        m = re.search(r"版本号[:：]\s*([0-9][0-9A-Za-z.\-]*)", text)
        got = m.group(1) if m else None
        if got and got != expect_version:
            problems.append("版本号对不上:期望 %s,实际读到 %s" % (expect_version, got))
    present = [c for c in STANDARD_CATEGORIES if c in text]
    absent = [c for c in STANDARD_CATEGORIES if c not in text]
    if strict_categories and absent:
        problems.append("以下标准分类没出现:%s" % "、".join(absent))
    if problems:
        raise ReportError("审核报告自检不通过:" + "; ".join(problems))
    return {"present_categories": present, "absent_categories": absent}


def parse_version(text):
    m = re.search(r"版本号[:：]\s*([0-9][0-9A-Za-z.\-]*)", text)
    return m.group(1) if m else None


def self_test(fixture=DEFAULT_FIXTURE, expect_version="1.0.2"):
    """纯函数级自测:用仓库里存下来的真实报告页 DOM 快照跑一遍解析 + 自检。"""
    if not os.path.exists(fixture):
        print("自测失败:找不到快照文件 %s" % fixture, file=sys.stderr)
        return 2
    with open(fixture, encoding="utf-8") as fh:
        raw = json.load(fh)
    text, meta = build_report(raw)
    info = verify_report(text, meta, expect_version=expect_version)
    ok = True

    def check(cond, desc, extra=""):
        nonlocal ok
        print("  %s %-46s %s" % ("✓" if cond else "✗", desc, extra))
        if not cond:
            ok = False

    print("自测:审核报告解析(%s)" % fixture)
    check(meta["pane_count"] >= 2, "抓到 %d 个 .el-tab-pane" % meta["pane_count"], ">=2")
    check("应用功能" in text, "读到「应用功能」分类")
    check("应用资质" in text, "读到「应用资质」分类")
    check("授权书" in text, "读到「应用资质」的阻塞意见(《Saber官方授权书》)")
    check("导入PDF格式的文件无响应" in text, "读到「应用功能」的问题2原文")
    check(parse_version(text) == expect_version, "版本号 = %s" % parse_version(text))
    check("应用信息" in text, "读到报告头部「应用信息」")
    check("知识产权" not in text, "「知识产权」本轮未涉及(报告里确实没有)")
    # 回归:模拟旧脚本的错法(只读可见 pane)必须抓不到授权书 —— 说明新写法确实修好了
    visible_only = "\n\n".join(
        p.get("text") or "" for doc in raw.get("docs", [])
        for p in doc.get("panes", []) if p.get("visible"))
    check("授权书" not in visible_only, "回归对照:只读可见 pane 确实抓不到「授权书」")
    check("授权书" in text, "新写法能抓到「授权书」")

    if not ok:
        print("自测有失败项 ✗", file=sys.stderr)
        return 1
    print("自测全部通过 ✓")
    print("  页面声明的 tab:%s" % "、".join(meta["tab_titles"]))
    print("  读到 %d 字;标准分类命中 %s;本轮未涉及 %s"
          % (meta["text_len"], "、".join(info["present_categories"]),
             "、".join(info["absent_categories"]) or "无"))
    return 0


def read_open_report(port, out=None):
    """只读:从当前已经打开着的报告页标签页里取报告(不导航、不点击)。"""
    targets = list_targets(port)
    t = pick_report_target(targets)
    if not t:
        raise ReportError("当前没有打开着的审核报告页标签页")
    print("用已打开的报告页标签页读取(只读,不导航):%s" % t.get("url"))
    raw = eval_in_target(t, COLLECT_JS)
    text, meta = build_report(raw)
    info = verify_report(text, meta)
    print("审核报告已保存:%s(%d 字)" % (out, len(text)))
    print("---- 摘要(前 1500 字)----")
    print(text[:1500])
    return text, meta, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--out", default="/tmp/agc_audit_report.txt")
    ap.add_argument("--version", default=None,
                    help="指定版本号(如 1.0.2);抓到的报告版本对不上会报错")
    ap.add_argument("--port-open-timeout", type=int, default=40)
    ap.add_argument("--read-open", action="store_true",
                    help="只读当前已打开的报告页(不点任何东西,适合别人正在用控制台时)")
    ap.add_argument("--self-test", action="store_true", help="纯函数级自测(不碰浏览器)")
    ap.add_argument("--fixture", default=DEFAULT_FIXTURE, help="自测用的 DOM 快照文件")
    ap.add_argument("--dump-raw", default=None, help="把原始 DOM 快照存到这个文件(用来做自测素材)")
    ap.add_argument("--strict-categories", action="store_true",
                    help="要求 4 个标准分类全部出现(默认只要求页面实际声明的 tab)")
    args = ap.parse_args()

    if args.self_test:
        return self_test(args.fixture)

    port = args.port or find_cdp_port()

    if args.read_open:
        text, meta, info = read_open_report(port, args.out)
        if args.dump_raw:
            with open(args.dump_raw, "w", encoding="utf-8") as fh:
                json.dump(json.loads(json.dumps(eval_in_target(
                    pick_report_target(list_targets(port)), COLLECT_JS))),
                    fh, ensure_ascii=False, indent=1)
            print("原始 DOM 快照已保存:%s" % args.dump_raw)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("页面声明的 tab:%s" % "、".join(meta["tab_titles"]))
        print("标准分类命中 %s;本轮未涉及 %s"
              % ("、".join(info["present_categories"]),
                 "、".join(info["absent_categories"]) or "无"))
        return 0

    before = {p.get("id") for p in list_targets(port)}

    # 2026-11-20 新增:定向挑「有左侧栏的控制台标签页」(见 pick_console_target)
    console = pick_console_target(port)
    if not console:
        print("找不到有左侧栏的控制台标签页(是不是登录态过期了?)", file=sys.stderr)
        return 8
    console_id = console.get("id")
    print("控制台标签页:%s" % console_id, file=sys.stderr)

    f = Frame(port, target_id=console_id)
    try:
        # 1. 进「版本历史记录」
        if not click_sidebar(f, "版本历史记录"):
            print("提示: 侧栏里没找到「版本历史记录」,尝试重新载入控制台", file=sys.stderr)
            f.c.send("Page.reload")
            time.sleep(16)
            f.close()
            f = Frame(port, target_id=console_id)
            click_sidebar(f, "版本历史记录")
        time.sleep(9)
        f.close()
        # 这里必须带上 target_id:不然又连回没有左侧栏的审核报告页 ✗
        f = Frame(port, target_id=console_id)

        # 2. 在历史表格里找「审核报告」链接
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

    # 3. 等报告页标签页 —— 按 URL 特征找,不要假设它在主标签页
    deadline = time.time() + args.port_open_timeout
    new_page = None
    while time.time() < deadline:
        for p in list_targets(port):
            if p.get("id") not in before and "auditReport" in (p.get("url") or ""):
                new_page = p
                break
        if new_page:
            break
        time.sleep(1.5)
    if not new_page:
        new_page = pick_report_target(list_targets(port))
    if not new_page:
        raise ReportError("点了「审核报告」但没等到报告页标签页")

    # 4. 报告正文是异步渲染的,轮询到 pane 真的出现为止
    raw = None
    deadline = time.time() + max(args.port_open_timeout, 40)
    while time.time() < deadline:
        raw = eval_in_target(new_page, COLLECT_JS)
        try:
            build_report(raw)
            break
        except ReportError:
            time.sleep(2)
    try:
        text, meta = build_report(raw)
    except ReportError as e:
        print("审核报告抓取失败:%s" % e)
        return 5

    # 5. 备选方案:某个 pane 是空的 → 点它的 tab 再读一次
    empty = [p for doc in (raw.get("docs") or [])
             for p in (doc.get("panes") or []) if not (p.get("text") or "").strip()]
    if empty:
        for t in (raw.get("docs") or [{}])[0].get("tabs", []):
            if t.get("id"):
                eval_in_target(new_page, CLICK_TAB_JS.replace("((tabId)", "(%s)" % json.dumps(t["id"]), 1))
                time.sleep(2.5)
        raw = eval_in_target(new_page, COLLECT_JS)
        text, meta = build_report(raw)

    try:
        info = verify_report(text, meta, expect_version=args.version,
                             strict_categories=args.strict_categories)
    except ReportError as e:
        print("审核报告抓取失败:%s" % e)
        return 6

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    if args.dump_raw:
        with open(args.dump_raw, "w", encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False, indent=1)
    print("审核报告已保存:%s(%d 字)" % (args.out, len(text)))
    print("页面声明的 tab:%s" % "、".join(meta["tab_titles"]))
    print("标准分类命中 %s;本轮未涉及 %s"
          % ("、".join(info["present_categories"]),
             "、".join(info["absent_categories"]) or "无"))
    print("---- 摘要(前 1500 字)----")
    print(text[:1500])
    return 0


def click_sidebar(f, label):
    expr = (
        "(() => {const el=[...document.querySelectorAll('.item-text')]"
        ".find(e=>e.innerText.trim()==='%s'); if(el){el.click(); return 1;} return 0;})()"
    ) % label
    return bool(f.c.eval(expr))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ReportError as e:
        print("审核报告抓取失败:%s" % e, file=sys.stderr)
        sys.exit(5)
