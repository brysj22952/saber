#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成鸿蒙版「赛博手写笔记」的应用图标。

背景(2026-11-17 第 2 轮审核驳回):
  1. 第 1 轮:商店上传的图标**带透明背景** → 要求纯色背景;
  2. 第 1 轮:商店图标与**应用安装后终端显示的图标不一致** → 要求两者是同一张图;
  3. 第 1 轮:「知识产权」判定应用与市场上已有的「Saber」**名称/图标相似**
     → 第 2 轮改名「赛博手写笔记」,图标也要彻底换掉;
  4. 第 2 轮:包内**单层图只有 144×144**,标准要求 **1024×1024**
     → 包内资源直接放 1024×1024 原图。

所以这里现画一张**全新**的图标:深色石板底 + 青色霓虹触控笔 + 电路节点,
配色刻意避开上游 Saber 那张「靛蓝底 + 黄色笔尖」,天然不带 alpha。

用法:
    python3 harmony/toolchain/make_app_icon.py
    # 产出(全部 1024×1024,RGB 无 alpha):
    #   harmony/assets/app-icon-1024.png                     商店上传用
    #   ohos/entry/src/main/resources/base/media/icon.png     包内 ability 图标
    #   ohos/AppScope/resources/base/media/app_icon.png       包内应用图标(桌面/最近任务)
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SS = 4  # 超采样倍数,画完再缩小,边缘更干净

BG_TOP = (14, 20, 33)       # 深石板
BG_BOTTOM = (23, 38, 58)
NEON = (34, 211, 238)       # 青
NEON_DIM = (14, 116, 144)
WHITE = (240, 253, 255)


def _gradient(size):
    img = Image.new("RGB", (size, size), BG_TOP)
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(size - 1, 1)
        draw.line(
            [(0, y), (size, y)],
            fill=tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)),
        )
    return img


def draw_icon(size=1024):
    """画一张 size×size 的图标(RGB,无 alpha)。"""
    s = size * SS
    img = _gradient(s)
    draw = ImageDraw.Draw(img)

    # 圆角底板:深色底上再压一层更深的圆角方块,形成描边感
    pad = int(s * 0.06)
    radius = int(s * 0.22)
    draw.rounded_rectangle(
        [pad, pad, s - pad, s - pad],
        radius=radius,
        fill=(9, 14, 24),
        outline=NEON_DIM,
        width=max(int(s * 0.006), 2),
    )

    # 电路走线:两条折线 + 端点,呼应「赛博」
    line_w = max(int(s * 0.012), 3)
    for idx, (pts, dot) in enumerate(
        [
            ([(0.22, 0.78), (0.34, 0.78), (0.34, 0.66)], (0.34, 0.66)),
            ([(0.78, 0.26), (0.68, 0.26), (0.68, 0.36)], (0.68, 0.36)),
        ]
    ):
        scaled = [(int(px * s), int(py * s)) for px, py in pts]
        draw.line(scaled, fill=NEON_DIM, width=line_w, joint="curve")
        r = int(s * 0.022)
        x, y = int(dot[0] * s), int(dot[1] * s)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=NEON)

    # 触控笔:斜着的白笔身 + 青色笔尖
    cx, cy = 0.52 * s, 0.5 * s
    length = 0.56 * s
    width = 0.13 * s
    angle = -35  # 度

    import math

    rad = math.radians(angle)
    ux, uy = math.cos(rad), math.sin(rad)

    # 笔尖(三角形)
    tip_len = length * 0.22
    tip = (cx + ux * length / 2, cy + uy * length / 2)
    left = (cx - ux * length / 2 + uy * width / 2, cy - uy * length / 2 - ux * width / 2)
    right = (cx - ux * length / 2 - uy * width / 2, cy - uy * length / 2 + ux * width / 2)
    draw.polygon([tip, left, right], fill=NEON)

    # 笔身(矩形)
    back = (cx - ux * length / 2, cy - uy * length / 2)
    draw.polygon(
        [
            left,
            right,
            (right[0] - ux * length * 0.30, right[1] - uy * length * 0.30),
            (left[0] - ux * length * 0.30, left[1] - uy * length * 0.30),
        ],
        fill=WHITE,
    )
    # 笔帽
    cap_w = width * 0.9
    cap = [
        (left[0], left[1]),
        (right[0], right[1]),
        (right[0] - ux * length * 0.06 - uy * cap_w / 2, right[1] - uy * length * 0.06 + ux * cap_w / 2),
        (left[0] - ux * length * 0.06 - uy * cap_w / 2, left[1] - uy * length * 0.06 + ux * cap_w / 2),
    ]
    draw.polygon(cap, fill=NEON)

    # 笔身上一道青色装饰线
    draw.line(
        [
            (back[0] - ux * length * 0.22, back[1] - uy * length * 0.22),
            (back[0] - ux * length * 0.30, back[1] - uy * length * 0.30),
        ],
        fill=NEON_DIM,
        width=max(int(s * 0.02), 4),
    )

    return img.resize((size, size), Image.LANCZOS)


def main():
    size = 1024
    icon = draw_icon(size)
    assert icon.mode == "RGB", icon.mode

    targets = [
        os.path.join(ROOT, "harmony", "assets", "app-icon-1024.png"),
        os.path.join(ROOT, "ohos", "entry", "src", "main", "resources", "base", "media", "icon.png"),
        os.path.join(ROOT, "ohos", "AppScope", "resources", "base", "media", "app_icon.png"),
    ]
    for path in targets:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        icon.save(path, "PNG")
        print(f"✓ {path} ({size}x{size}, RGB 无 alpha)")


if __name__ == "__main__":
    main()
