#!/usr/bin/env python3
"""抓取华为应用市场用的商店截图(平板横屏,16:9)。

用法:
    python3 harmony/toolchain/capture_store_screenshots.py [--device 10.0.0.4:39551] [--out harmony/docs/store-screenshots]

踩过的坑(都在下面代码里注明):
  * 商店要求:3~10 张、最小 1920*1080、宽高比 16:9 ⇒ 必须把悬浮窗拉成 16:9 再截,
    否则前端直接报「图片尺寸不符合要求」。
  * 悬浮窗顶部有 70px 系统标题栏,截图只取标题栏以下的**内容区**,
    所以窗口整体宽高比要按 (h-70) 算。
  * 应用重启后悬浮窗宽高会被还原 ⇒ 每张图之前都要重新校准尺寸。
  * 一次 `hdc shell` 里把「点击 → 截图」做完,不要拆开;万一中途点到窗口外,
    桌面/浏览器会被拉到前台,截出来就不是应用了。所以截图前会再 dump 一次校验前台。
  * 截图只裁应用窗口,桌面、任务栏、其它应用一律不带进去。
"""
import argparse
import json
import os
import re
import subprocess
import time

BUNDLE = "com.sabernotes.saber"
PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(PKG_DIR)
APP_TEXTS = ("首页", "全部笔记", "白板", "设置")
SHOTS = [
    ("home", []),                       # 首页(笔记列表)
    ("fabmenu", ["tap:fab"]),           # 右下角悬浮按钮展开的快捷菜单
    ("editor", ["tap:firstNote", "stroke"]),  # 手写编辑器(画两笔)
    ("whiteboard", ["tap:白板"]),        # 白板
]


def sh(device, cmd, timeout=240):
    args = ["hdc", "-t", device, "shell", cmd] if device else ["hdc", "shell", cmd]
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def recv(device, remote, local):
    args = ["hdc", "-t", device, "file", "recv", remote, local] if device else \
           ["hdc", "file", "recv", remote, local]
    subprocess.run(args, capture_output=True, text=True, timeout=180)


def dump_layout(device, tag):
    remote = f"/data/local/tmp/lay_{tag}.json"
    sh(device, f"uitest dumpLayout -p {remote}")
    local = f"/tmp/lay_{tag}.json"
    recv(device, remote, local)
    with open(local, encoding="utf-8") as fh:
        return json.load(fh)


def _bounds(attr):
    m = re.match(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", attr or "")
    return tuple(map(int, m.groups())) if m else None


def _walk(node):
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


def find_window(layout):
    """找悬浮窗:屏幕上尺寸最大的那个 root 节点。"""
    best = None
    for node in _walk(layout):
        a = node.get("attributes", {})
        if a.get("type") != "root":
            continue
        b = _bounds(a.get("bounds"))
        if not b:
            continue
        w, h = b[2] - b[0], b[3] - b[1]
        if 600 < w < 3120 and 400 < h < 2080:
            if best is None or w * h > best[2] * best[3]:
                best = b
    return best


def find_title_h(layout, win):
    x1, y1, x2, y2 = win
    for node in _walk(layout):
        a = node.get("attributes", {})
        if a.get("type") != "Row":
            continue
        b = _bounds(a.get("bounds"))
        if not b:
            continue
        if abs(b[0] - x1) < 5 and abs(b[2] - x2) < 5 and 0 < b[3] - b[1] <= 120 and b[1] <= y1 + 5:
            return b[3] - b[1]
    return 70


def texts(layout):
    out = []
    for node in _walk(layout):
        t = (node.get("attributes", {}).get("text") or "").strip()
        if t:
            out.append(t)
    return out


def front_window(layout):
    """dump 树里第一个「大 root」= 最前台的窗口。"""
    for node in _walk(layout):
        a = node.get("attributes", {})
        if a.get("type") != "root":
            continue
        b = _bounds(a.get("bounds"))
        if not b:
            continue
        w, h = b[2] - b[0], b[3] - b[1]
        if 600 < w < 3120 and 400 < h < 2080:
            return b
    return None


def app_in_foreground(layout):
    """前台是不是我们的应用:最前面的窗口 + 应用特有的文字。"""
    ts = texts(layout)
    return sum(1 for t in APP_TEXTS if t in ts) >= 3


def find_text(layout, text, win):
    for node in _walk(layout):
        a = node.get("attributes", {})
        if (a.get("text") or "").strip() == text:
            b = _bounds(a.get("bounds"))
            if b and b[0] >= win[0] and b[2] <= win[2]:
                return b
    return None


def find_first_note(layout, win):
    for node in _walk(layout):
        a = node.get("attributes", {})
        if a.get("type") != "Image":
            continue
        # 笔记卡片的标题挂在 text 或 description 上(两个属性都可能)
        desc = (a.get("description") or "").strip() or (a.get("text") or "").strip()
        b = _bounds(a.get("bounds"))
        if desc and desc != "导入" and b and b[0] >= win[0] and b[1] >= win[1]:
            return b
    return None


def fab_center(win):
    """右下角悬浮按钮:内容区右下角往里 84px。"""
    x1, y1, x2, y2 = win
    return (x2 - 84, y2 - 84)


def fit_16x9(device, layout=None, verbose=True):
    """把悬浮窗宽度调成「内容区 = 16:9」,返回 (窗口矩形, 标题栏高)。"""
    layout = layout or dump_layout(device, "fit")
    win = find_window(layout)
    if not win:
        raise SystemExit("找不到悬浮窗(应用没在前台?)")
    title_h = find_title_h(layout, win)
    w, h = win[2] - win[0], win[3] - win[1]
    target_w = round((h - title_h) * 16 / 9)
    delta = target_w - w
    if verbose:
        print(f"  窗口 {w}x{h} 标题栏 {title_h} 内容 {w}x{h - title_h} 目标宽 {target_w} Δ{delta}")
    if abs(delta) > 2:
        x2, y2 = win[2], win[3]
        sh(device, f"uitest uiInput swipe {x2 - 1} {y2 - 1} {x2 - 1 + delta} {y2 - 1} 400")
        time.sleep(3)
        layout = dump_layout(device, "fit2")
        win = find_window(layout)
        title_h = find_title_h(layout, win)
        if verbose:
            w, h = win[2] - win[0], win[3] - win[1]
            print(f"  调整后 {w}x{h} 内容 {w}x{h - title_h} 比例 {(w)/(h - title_h):.4f}")
    return win, title_h, layout


def capture(device, out_dir, name, actions):
    # 启动应用,拿到窗口矩形
    sh(device, f"aa force-stop {BUNDLE}; sleep 2; aa start -a EntryAbility -b {BUNDLE}; sleep 9")
    layout = dump_layout(device, name + "_pre")
    front = front_window(layout)
    if not app_in_foreground(layout) and not (front and front[2] - front[0] > 1500):
        raise SystemExit(f"{name}: 应用不在前台,放弃")
    win, title_h, layout = fit_16x9(device, layout)
    x1, y1, x2, y2 = win

    steps = []
    for act in actions:
        if act == "tap:fab":
            cx, cy = fab_center(win)
            steps.append(f"uitest uiInput click {cx} {cy}")
            steps.append("sleep 3")
        elif act == "tap:firstNote":
            note = find_first_note(layout, win)
            if not note:
                raise SystemExit(f"{name}: 找不到笔记卡片")
            cx, cy = (note[0] + note[2]) // 2, (note[1] + note[3]) // 2
            steps.append(f"uitest uiInput click {cx} {cy}")
            steps.append("sleep 5")
        elif act == "tap:白板":
            wb = find_text(layout, "白板", win)
            if not wb:
                raise SystemExit(f"{name}: 找不到白板入口")
            cx, cy = (wb[0] + wb[2]) // 2, (wb[1] + wb[3]) // 2
            steps.append(f"uitest uiInput click {cx} {cy}")
            steps.append("sleep 5")
        elif act == "stroke":
            cx = (x1 + x2) // 2
            steps.append(f"uitest uiInput swipe {cx - 260} {y1 + 430} {cx - 120} {y1 + 570} 400")
            steps.append("sleep 1")
            steps.append(f"uitest uiInput swipe {cx - 120} {y1 + 570} {cx + 120} {y1 + 390} 400")
            steps.append("sleep 2")

    remote = f"/data/local/tmp/shot_{name}.jpeg"
    vremote = f"/data/local/tmp/verify_{name}.json"
    cmd = "; ".join([
        *steps,
        f"uitest dumpLayout -p {vremote}",
        f"snapshot_display -f {remote}",
    ])
    sh(device, cmd, timeout=300)

    # 校验:截图那一刻前台必须是应用
    vlocal = f"/tmp/verify_{name}.json"
    recv(device, vremote, vlocal)
    with open(vlocal, encoding="utf-8") as fh:
        vlayout = json.load(fh)
    front = front_window(vlayout)
    if not front or abs(front[0] - x1) > 8 or abs(front[2] - x2) > 8:
        raise SystemExit(f"{name}: 截图时前台不是应用窗口(front={front}),放弃")

    local = f"/tmp/shot_{name}.jpeg"
    recv(device, remote, local)
    if not os.path.exists(local):
        raise SystemExit(f"{name}: 截图没拿到")
    from PIL import Image
    img = Image.open(local)
    crop = img.crop((x1, y1 + title_h, x2, y2))
    cw, ch = crop.size
    if cw / ch > 16 / 9:
        crop = crop.crop((0, 0, int(ch * 16 / 9), ch))
    elif cw / ch < 16 / 9:
        crop = crop.crop((0, 0, cw, int(cw * 9 / 16)))
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, name + ".png")
    crop.save(dst, "PNG")
    print(f"  {name}: {crop.size[0]}x{crop.size[1]} 比例 {crop.size[0]/crop.size[1]:.4f} -> {dst}")
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default=os.environ.get("HARMONY_DEVICE", ""))
    ap.add_argument("--out", default=os.path.join(REPO, "harmony", "docs", "store-screenshots"))
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    for name, actions in SHOTS:
        if args.only and name != args.only:
            continue
        print(f"[{name}]")
        capture(args.device, args.out, name, actions)


if __name__ == "__main__":
    main()
