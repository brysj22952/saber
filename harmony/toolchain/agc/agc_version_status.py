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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--url", default=None, help="控制台地址;给了就跳转过去再读")
    ap.add_argument("--raw", action="store_true", help="把整页文本打出来")
    args = ap.parse_args()

    port = args.port or find_cdp_port()
    f = Frame(port)
    try:
        if args.url:
            f.c.send("Page.navigate", url=args.url)
            import time

            time.sleep(18)
        text = f.ev("(() => document.body.innerText.replace(/\\s+/g, ' '))()") or ""
    finally:
        f.close()

    if args.raw:
        print(text[:3000])
        return

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
