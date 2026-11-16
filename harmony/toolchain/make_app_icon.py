#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成鸿蒙版 Saber 的应用图标。

为什么需要它(华为应用市场 2026-11-16 第 1 轮审核驳回):
  1. 商店上传的图标**带透明背景** → 要求纯色背景;
  2. 商店图标与**应用安装后终端显示的图标不一致** → 要求两者是同一张图;
  3. 「知识产权」判定应用与市场上已有的「Saber」**名称/图标相同** → 图标要与上游
     那个黄色钢笔尖 logo 明显不同。

所以这里现画一张**全新**的图标:靛蓝渐变圆角方块 + 白色触控笔 + 金色笔尖装饰,
不依赖任何上游素材,天然不带 alpha。

用法:
    python3 harmony/toolchain/make_app_icon.py
    # 产出:
    #   harmony/assets/app-icon-1024.png        商店用(1024×1024,PNG,无 alpha)
    #   ohos/entry/src/main/resources/base/media/icon.png      包内 ability 图标
    #   ohos/AppScope/resources/base/media/app_icon.png        包内应用图标(桌面/最近任务)
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SS = 4  # 超采样倍数,画完再缩小,边缘更干净


def draw_icon(size=1024):
    """画一张 size×size 的图标(RGB,无 alpha)。"""
    s = size * SS
    img = Image.new("RGB", (s, s), (26, 35, 126))
    d = ImageDraw.Draw(img)

    # 圆角方块 + 竖向渐变底
    radius = int(s * 0.22)
    grad_top, grad_bottom = (63, 81, 181), (21, 27, 92)
    for y in range(s):
        t = y / max(s - 1, 1)
        col = tuple(int(grad_top[i] + (grad_bottom[i] - grad_top[i]) * t) for i in range(3))
        d.line([(0, y), (s, y)], fill=col)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=255)
    img = img.convert("RGBA")
    img.putalpha(mask)
    d = ImageDraw.Draw(img)

    # 一支斜着的触控笔:笔杆(白)+ 笔尖(金)+ 尾部的小圆
    pen = [
        # 笔杆:左下 → 右上 的长条,末端收窄
        (0.26, 0.74, 0.40, 0.86),
    ]
    # 笔身用四点多边形画,让它有"斜握"的感觉
    body = [
        (0.30 * s, 0.80 * s),
        (0.66 * s, 0.36 * s),
        (0.76 * s, 0.44 * s),
        (0.40 * s, 0.88 * s),
    ]
    d.polygon(body, fill=(255, 255, 255, 255))

    # 笔尖(金色三角),指向右上
    tip = [
        (0.66 * s, 0.36 * s),
        (0.76 * s, 0.44 * s),
        (0.86 * s, 0.20 * s),
    ]
    d.polygon(tip, fill=(255, 200, 60, 255))

    # 笔尾的深色小段,增加层次
    tail = [
        (0.30 * s, 0.80 * s),
        (0.40 * s, 0.88 * s),
        (0.34 * s, 0.94 * s),
        (0.24 * s, 0.86 * s),
    ]
    d.polygon(tail, fill=(30, 41, 110, 255))

    # 左下角一颗金色小圆点,呼应"星屑"
    r = s * 0.045
    d.ellipse(
        [0.19 * s - r, 0.86 * s - r, 0.19 * s + r, 0.86 * s + r],
        fill=(255, 200, 60, 255),
    )

    img = img.convert("RGB")  # 去掉 alpha,满足"纯色背景"
    return img.resize((size, size), Image.LANCZOS)


def main():
    out_paths = {
        "harmony/assets/app-icon-1024.png": 1024,
        "ohos/entry/src/main/resources/base/media/icon.png": 144,
        "ohos/AppScope/resources/base/media/app_icon.png": 144,
    }
    master = draw_icon(1024)
    for rel, size in out_paths.items():
        path = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img = master if size == 1024 else master.resize((size, size), Image.LANCZOS)
        img.save(path, format="PNG", optimize=True)
        print("写出 %-58s %dx%d  %d KB" % (rel, size, size, os.path.getsize(path) // 1024))


if __name__ == "__main__":
    main()
