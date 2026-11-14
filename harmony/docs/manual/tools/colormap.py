#!/usr/bin/env python3
"""Print a colour-index map of a screenshot.

Each cell shows a symbol for the dominant colour in that cell, so the
UI structure (panels, buttons, canvas, text) can be located precisely.

Usage:
    python3 scripts/colormap.py <image> [--cell 60] [--box x1,y1,x2,y2]
"""
import sys
from collections import Counter

from PIL import Image

SYMBOLS = " .:-=+*#%@&o0123456789abcdefghijklmnopqrstuvwxyz"


def main():
    path = sys.argv[1]
    cell = 60
    if "--cell" in sys.argv:
        cell = int(sys.argv[sys.argv.index("--cell") + 1])
    box = None
    if "--box" in sys.argv:
        box = tuple(int(v) for v in sys.argv[sys.argv.index("--box") + 1].split(","))

    im = Image.open(path).convert("RGB")
    if box:
        im = im.crop(box)
    W, H = im.size

    counts = Counter(im.getdata())
    palette = [c for c, _ in counts.most_common(24)]
    # merge near-duplicates
    merged = []
    for c in palette:
        if not any(all(abs(c[k] - m[k]) < 12 for k in range(3)) for m in merged):
            merged.append(c)
    palette = merged[:20]

    print(f"image {W}x{H} cell={cell}")
    print("legend:")
    for i, c in enumerate(palette):
        print(f"  {SYMBOLS[i]} = rgb{c}  ({100*counts[c]/(W*H):5.2f}%)")

    cols = W // cell
    rows = H // cell
    print()
    for gy in range(rows):
        line = []
        for gx in range(cols):
            box_px = im.crop((gx * cell, gy * cell, (gx + 1) * cell, (gy + 1) * cell))
            px = list(box_px.getdata())
            dom = Counter(px).most_common(1)[0][0]
            best, bestd = 0, 10 ** 9
            for i, c in enumerate(palette):
                d = sum(abs(dom[j] - c[j]) for j in range(3))
                if d < bestd:
                    best, bestd = i, d
            line.append(SYMBOLS[best])
        print(f"y{gy*cell:>5}|{''.join(line)}|")
    print("     |" + "".join(str((gx * cell // 100) % 10) if gx % 5 == 0 else " "
                             for gx in range(cols)) + "|  (x in 100px)")


if __name__ == "__main__":
    main()
