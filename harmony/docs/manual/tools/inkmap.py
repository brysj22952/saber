#!/usr/bin/env python3
"""Print an ink map of a screenshot: a coarse grid marking cells that
differ from the background, so visible content regions can be located.

Usage:
    python3 scripts/inkmap.py <image> [--cell 60] [--min 3]
"""
import sys
from collections import Counter

from PIL import Image


def main():
    path = sys.argv[1]
    cell = 60
    if "--cell" in sys.argv:
        cell = int(sys.argv[sys.argv.index("--cell") + 1])
    minpct = 3.0
    if "--min" in sys.argv:
        minpct = float(sys.argv[sys.argv.index("--min") + 1])

    im = Image.open(path).convert("RGB")
    W, H = im.size
    bg = Counter(im.getdata()).most_common(1)[0][0]

    cols = W // cell
    rows = H // cell
    print(f"{W}x{H} bg={bg} cell={cell} grid={cols}x{rows}")
    for gy in range(rows):
        line = []
        for gx in range(cols):
            box = im.crop((gx * cell, gy * cell, (gx + 1) * cell, (gy + 1) * cell))
            px = list(box.getdata())
            ink = sum(1 for p in px
                      if abs(p[0]-bg[0]) + abs(p[1]-bg[1]) + abs(p[2]-bg[2]) > 40)
            pct = 100 * ink / len(px)
            if pct >= minpct:
                # show intensity bucket
                line.append(" .:*#"[min(3, int(pct / 25))])
            else:
                line.append(" ")
        if "".join(line).strip():
            print(f"y{gy*cell:>5} |{''.join(line)}|")
    print("        " + "".join(str((gx * cell // 1000) % 10) if gx % 10 == 0 else " "
                              for gx in range(cols)))
    print("         x(k)")


if __name__ == "__main__":
    main()
