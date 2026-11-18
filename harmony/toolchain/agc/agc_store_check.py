#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上架后核对:把商店详情页的 6 项逐一验一遍。

用法:
    python3 harmony/toolchain/agc/agc_store_check.py --app-id <AGC APP ID> \
        --name 赛博手写笔记

原理:
    1. 用 CDP 新开一个标签页,访问华为应用市场的应用详情页
       https://appgallery.huawei.com/app/C<appId>(国内站;不同区域站的域名可能不同);
    2. 抓页面上的全部图片链接与全部超链接;
    3. 逐项核对:
         名称     —— 正文里出现应用名
         图标     —— 把商店图片跟本地 1024 图标做缩放后逐像素比较,取最像的一张
         截图     —— 本地四张截图各自在商店图片里找最像的一张
         介绍     —— 正文里出现我们提交的介绍文案里的关键句
         隐私政策 —— 页面里指向 privacy-policy.html 的链接存在,且能正常打开
    4. 打印每项的结论,并保留一份 JSON 报告到 /tmp/agc_store_check.json。

注意:
    * APP ID 只作为命令行参数传入,不写进仓库 ✓;
    * 商店页是前端渲染的,所以必须用浏览器打开,curl 拿不到内容 ✓;
    * 商店会对图片重新编码,所以比较的是**缩放到同尺寸后的像素**,
      不是文件字节 ✓;
    * 还没上架时访问 `/app/C<appId>` 会被重定向到商店首页 —— 正文里找不到
      应用名,脚本会直接说「还没上架」 ✓;
    * 刚上架时可能有 CDN 缓存延迟,找不到属正常,过几分钟再试 ✓。
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.request

import websocket
from PIL import Image

DEFAULT_PORT = 9333
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DEFAULT_ICON = os.path.join(REPO, "harmony", "assets", "app-icon-1024.png")
DEFAULT_SHOTS = os.path.join(REPO, "harmony", "docs", "store-screenshots")
# 介绍文案里挑一句比较独特的(商店里应该原样出现)
DEFAULT_INTRO_MARK = "完全离线可用"
# 我们自己的隐私政策网址(应用市场里填的是这个)。
# 注意:商店页脚**自己**也有 privacy.consumer.huawei.com 的通用法律链接,
# 那些不算数 —— 必须能找到我们这个网址,才算「隐私政策链接已生效」。
DEFAULT_PRIVACY_URL = "https://brysj22952.github.io/saber/privacy-policy.html"


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


EXTRACT_JS = r"""(() => {
  const imgs = [...document.querySelectorAll('img')].map(i => ({
    src: i.currentSrc || i.src || '',
    w: i.naturalWidth || 0,
    h: i.naturalHeight || 0
  })).filter(i => i.src && /^https?:/.test(i.src));
  const links = [...document.querySelectorAll('a')]
    .map(a => a.href).filter(h => h && /^https?:/.test(h));
  return {
    title: document.title || '',
    body: (document.body.innerText || '').replace(/\s+/g, ' '),
    imgs, links
  };
})()"""


def fetch_image(url):
    """下载一张图片并转成 PIL 对象;失败返回 None。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read()
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return None


# 比较用的缩放尺寸与判定阈值。
# 阈值 8.0 的依据(本地实测):
#   * 同一张图(哪怕商店重新编码成 JPEG q80、或缩到 480×270)→ 差值 0.03~0.44
#   * 我们四张截图里最像的一对(editor vs whiteboard,都是白底画布)→ 3.27
#   * 不同截图之间 → 10.7~23.0
# 所以 8.0 能把「我们的图」和「不是我们的图」分开;editor/whiteboard 那一对
# 会互相匹配,但两张都是我们的,不影响结论 ✓。
CMP_SIZE = 128
CMP_THRESHOLD = 8.0
AR_TOL = 0.06


def aspect(im):
    w, h = im.size
    return (w / h) if h else 0.0


def pixel_diff(a, b, size=CMP_SIZE):
    """两张图缩放到同尺寸后的平均像素差(0=完全一样,255=完全相反)。"""
    pa = a.resize((size, size), Image.LANCZOS).tobytes()
    pb = b.resize((size, size), Image.LANCZOS).tobytes()
    return sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)


def filter_ar(candidates, want, tol=AR_TOL):
    """按长宽比筛选候选图(图标是 1:1,截图是 16:9)。"""
    out = []
    for url, im in candidates:
        if abs(aspect(im) - want) <= tol:
            out.append((url, im))
    return out


def best_match(target, candidates, size=CMP_SIZE):
    """在候选图里找跟 target 最像的一张,返回 (url, 差值)。"""
    best = (None, None)
    for url, im in candidates:
        d = pixel_diff(target, im, size)
        if best[1] is None or d < best[1]:
            best = (url, d)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True, help="AGC 里的 APP ID(不要写进仓库)")
    ap.add_argument("--name", default="赛博手写笔记", help="应用名,用来在页面里核对")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--host", default="https://appgallery.huawei.com")
    ap.add_argument("--icon", default=DEFAULT_ICON, help="本地商店图标(1024 PNG)")
    ap.add_argument("--shots-dir", default=DEFAULT_SHOTS, help="本地商店截图目录")
    ap.add_argument("--intro-mark", default=DEFAULT_INTRO_MARK, help="介绍文案里的关键句")
    ap.add_argument("--privacy-url", default=DEFAULT_PRIVACY_URL,
                    help="我们自己的隐私政策网址(商店里填的那个)")
    ap.add_argument("--url", default=None,
                    help="直接指定要核对的页面 URL(默认按 --app-id 拼 /app/C<id>)。"
                         "想按商店搜索结果核对时用这个。")
    args = ap.parse_args()

    port = args.port or find_cdp_port()
    url = args.url or "%s/app/C%s" % (args.host.rstrip("/"), args.app_id)

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
        time.sleep(16)
        res = c.send(
            "Runtime.evaluate",
            expression=EXTRACT_JS,
            returnByValue=True,
        )["result"]["result"].get("value") or {}
        title = res.get("title", "")
        body = res.get("body", "")
        img_urls = res.get("imgs", [])
        links = res.get("links", [])
    finally:
        c.close()
        try:
            b2 = WS(browser_ws)
            b2.send("Target.closeTarget", targetId=target)
            b2.close()
        except Exception:
            pass

    print("URL  : %s" % url)
    print("标题 : %s" % title)
    print("图片 : %d 张,链接 : %d 条" % (len(img_urls), len(links)))

    report = {"url": url, "title": title, "checks": {}}

    # ---------- 1. 名称 ----------
    # 注意:搜索结果页会把搜索词回显在正文里,正文里出现应用名**不等于**应用已上架,
    # 所以用 --url 指定的搜索页只适合粗看「有没有搜到」,
    # 真正的核对要走 /app/C<appId> 详情页(URL 里不含应用名,不会回显)。
    name_ok = args.name in body
    echo_risk = args.url is not None and args.name in (args.url or "")
    report["checks"]["名称"] = {"ok": name_ok, "detail": args.name, "echo_risk": echo_risk}
    print("\n[名称] %s —— %s%s"
          % ("✓" if name_ok else "✗", args.name,
             "(注意:搜索页会回显搜索词,不能据此判断已上架)" if echo_risk else ""))

    if not name_ok:
        print("\n✗ 页面正文里找不到应用名,多半是**还没上架**"
              "(未上架时该地址会跳商店首页)。等审核通过后再跑一次。")
        print("---- 页面正文(前 400 字)----")
        print(body[:400])
        with open("/tmp/agc_store_check.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return 2

    # ---------- 2. 图片下载 ----------
    print("\n下载商店图片中 …")
    candidates = []
    for iu in img_urls:
        im = fetch_image(iu["src"])
        if im is not None:
            candidates.append((iu["src"], im))
    print("  可用图片 %d / %d 张" % (len(candidates), len(img_urls)))

    # ---------- 3. 图标(只跟正方形候选比,避免跟 16:9 的截图混淆)----------
    icon_ok = False
    if os.path.exists(args.icon) and candidates:
        local = Image.open(args.icon).convert("RGB")
        squares = filter_ar(candidates, 1.0)
        url_best, diff = best_match(local, squares or candidates)
        icon_ok = diff is not None and diff < CMP_THRESHOLD
        report["checks"]["图标"] = {"ok": icon_ok, "diff": diff, "url": url_best,
                                    "squares": len(squares)}
        print("\n[图标] %s —— 与本地 1024 图标缩放后平均像素差 %.2f(阈值 %.1f,%d 张正方形候选)"
              % ("✓" if icon_ok else "✗", diff if diff is not None else -1, CMP_THRESHOLD, len(squares)))
        print("       商店上的图标: %s" % (url_best or "(没找到)"))
    else:
        report["checks"]["图标"] = {"ok": False, "detail": "本地图标或商店图片缺失"}

    # ---------- 4. 截图(只跟 16:9 候选比)----------
    # 判据是「集合对得上」:商店上的每一张 16:9 图片,都要能对上我们本地的一张,
    # 而且我们本地的四张都要在商店上找得到。
    shot_results = []
    wides = filter_ar(candidates, 16 / 9)
    if os.path.isdir(args.shots_dir):
        locals_ = []
        for name in sorted(os.listdir(args.shots_dir)):
            if not name.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            locals_.append((name, Image.open(os.path.join(args.shots_dir, name)).convert("RGB")))
        # 每张本地截图 → 商店里最像的一张
        matched_urls = set()
        for name, local in locals_:
            url_best, diff = best_match(local, wides)
            ok = diff is not None and diff < CMP_THRESHOLD
            if ok and url_best:
                matched_urls.add(url_best)
            shot_results.append({"name": name, "ok": ok, "diff": diff, "url": url_best})
            print("\n[截图] %s %s —— 与商店图片最像的一张差 %.2f"
                  % (name, "✓" if ok else "✗", diff if diff is not None else -1))
        # 商店上的每一张宽图 → 能不能对上本地某一张
        extra = []
        for url, im in wides:
            diffs = [(pixel_diff(local, im), name) for name, local in locals_]
            d, name = min(diffs) if diffs else (None, None)
            ok = d is not None and d < CMP_THRESHOLD
            extra.append({"url": url, "match": name, "diff": d, "ok": ok})
            print("      商店宽图 %s → %s %s(差 %.2f)"
                  % (url.split("/")[-1][:40], name, "✓" if ok else "✗", d if d is not None else -1))
        report["checks"]["截图"] = {"ok": bool(shot_results) and all(x["ok"] for x in shot_results)
                                    and all(x["ok"] for x in extra),
                                    "local": shot_results, "store": extra,
                                    "wides": len(wides)}

    # ---------- 5. 介绍 ----------
    intro_ok = args.intro_mark in body
    report["checks"]["介绍"] = {"ok": intro_ok, "mark": args.intro_mark}
    print("\n[介绍] %s —— 正文含「%s」" % ("✓" if intro_ok else "✗", args.intro_mark))

    # ---------- 6. 隐私政策 ----------
    # 商店页脚自己也有 Huawei 的通用法律链接(privacy.consumer.huawei.com/...),
    # 那些**不算** —— 必须找到我们自己填的那个网址,并能打开。
    pol_links = [l for l in links if args.privacy_url in l]
    in_body = args.privacy_url in body
    pol_status = None
    for l in pol_links[:3]:
        try:
            req = urllib.request.Request(l, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                pol_status = r.status
                break
        except Exception as e:
            pol_status = "打开失败:%s" % e
    if not pol_links and in_body:
        # 网址以纯文本出现(不是 <a href>),也认 —— 但仍要确认它能打开
        try:
            req = urllib.request.Request(args.privacy_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                pol_status = r.status
        except Exception as e:
            pol_status = "打开失败:%s" % e
    pol_ok = bool(pol_links) or in_body
    pol_ok = pol_ok and (pol_status == 200)
    report["checks"]["隐私政策"] = {"ok": pol_ok, "links": pol_links[:3],
                                    "in_body": in_body, "status": pol_status,
                                    "expect": args.privacy_url}
    print("\n[隐私政策] %s —— 找到我们的政策网址:%s,HTTP %s"
          % ("✓" if pol_ok else "✗", "是" if (pol_links or in_body) else "否", pol_status))
    for l in pol_links[:3]:
        print("        %s" % l)
    if not pol_ok:
        other = [l for l in links if "privacy" in l.lower() or "隐私" in l][:5]
        print("        (页面上其它带 privacy 的链接 —— 多半是商店自己的通用法律链接,不算):")
        for l in other:
            print("          %s" % l)

    def check_ok(v):
        if isinstance(v, dict) and "ok" in v:
            return bool(v["ok"])
        return True

    all_ok = all(check_ok(v) for v in report["checks"].values())
    print("\n合计: %s" % ("全部通过 ✓" if all_ok else "有未通过项 ✗"))
    with open("/tmp/agc_store_check.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("报告: /tmp/agc_store_check.json")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
