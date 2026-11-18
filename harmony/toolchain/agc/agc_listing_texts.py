#!/usr/bin/env python3
"""agc_listing_texts.py —— 从 store-listing.md 里抠出要往控制台里贴的三段文案。

**为什么要有这个脚本**:版本表单里那三段文案(App 介绍 / 版本更新说明 / 权限说明)
都带中文标点,手抄一遍最容易出错 —— 抄错一个字就是商店页上肉眼可见的瑕疵,
而审核员就是照着商店页看应用的。唯一的文字来源应该是
`harmony/docs/store-listing.md` 本身,这里只负责**抠出来 + 报长度**。

用法:
    python3 agc_listing_texts.py                 # 打印三段文案(带标记)
    python3 agc_listing_texts.py --write-dir /tmp/listing   # 另存成三个文件
    python3 agc_listing_texts.py --which update  # 只看某一段
    python3 agc_listing_texts.py --check         # 只校验长度(非零退出=超限)
"""
import argparse
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
LISTING = os.path.join(REPO, "harmony", "docs", "store-listing.md")

# 控制台字段上限(取最严的一档;实际控制台给的框都远比这大)
LIMITS = {"intro": 4000, "permission": 1000, "update": 500}

MARK = {
    "intro": ("应用介绍(长文本)", "§2"),
    "permission": ("权限说明", "§3"),
    "update": ("版本更新说明", "§5 的 1.0.3"),
}


def _block(text, header_re):
    """取某个标题下面第一个 ``` 代码块的内容。

    标题用 `[^\n]*` 收尾(不能用 `.*$`:re.S 下 `.` 会跨行,把后面的代码块也吃掉)。
    """
    m = re.search(header_re + r"[^\n]*\n\s*```\n(.*?)\n\s*```", text, re.S | re.M)
    if not m:
        raise SystemExit("在 %s 里找不到 %s 对应的代码块" % (LISTING, header_re))
    return m.group(1).strip()


def load():
    with open(LISTING, encoding="utf-8") as fh:
        text = fh.read()
    return {
        "intro": _block(text, r"^## 2\."),
        "permission": _block(text, r"^## 3\."),
        "update": _block(text, r"^### 1\.0\.3"),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--which", choices=["intro", "permission", "update"],
                    help="只看其中一段")
    ap.add_argument("--write-dir", help="把三段文案另存成三个 txt")
    ap.add_argument("--check", action="store_true", help="只校验长度")
    a = ap.parse_args()

    if not os.path.isfile(LISTING):
        raise SystemExit("找不到 %s" % LISTING)
    texts = load()

    over = []
    for k, v in texts.items():
        n = len(v)
        lim = LIMITS[k]
        flag = "✓" if n <= lim else "✗ 超限"
        if n > lim:
            over.append((k, n, lim))
        if a.check:
            print("%-11s %4d 字符 / 上限 %d  %s" % (k, n, lim, flag))
        else:
            name, sec = MARK[k]
            print("=" * 72)
            print("### %s(%s)—— %d 字符" % (name, sec, n))
            print("=" * 72)
            print(v)
            print()

    if a.write_dir:
        os.makedirs(a.write_dir, exist_ok=True)
        for k, v in texts.items():
            p = os.path.join(a.write_dir, k + ".txt")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(v)
            print("已写出 %s(%d 字符)" % (p, len(v)))

    if over:
        print("\n超限:%s" % ", ".join("%s %d>%d" % o for o in over), file=sys.stderr)
        return 1
    if a.check:
        print("三段文案长度都在控制台字段上限之内 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
