#!/usr/bin/env python3
"""Probe a screenshot: report colours / ink density for named rectangles.

Usage:
    python3 scripts/probe.py <image> x1,y1,x2,y2 [x1,y1,x2,y2 ...]
"""
import sys
from collections import Counter

from PIL import Image


def main():
    im = Image.open(sys.argv[1]).convert("RGB")
    W, H = im.size
    full = Counter(im.getdata())
    bg = full.most_common(1)[0][0]
    print(f"image {W}x{H}  background={bg} ({100*full[bg]/(W*H):.1f}%)")

    for spec in sys.argv[2:]:
        x1, y1, x2, y2 = (int(v) for v in spec.split(","))
        crop = im.crop((x1, y1, x2, y2))
        px = list(crop.getdata())
        n = len(px)
        ink = sum(1 for p in px if abs(p[0]-bg[0]) + abs(p[1]-bg[1]) + abs(p[2]-bg[2]) > 40)
        top = Counter(px).most_common(3)
        mean = tuple(sum(p[i] for p in px) // n for i in range(3))
        print(f"  [{x1:>5},{y1:>5}]-[{x2:>5},{y2:>5}] "
              f"{x2-x1}x{y2-y1}  ink={100*ink/n:5.1f}%  mean={mean}  top={top}")


if __name__ == "__main__":
    main()
