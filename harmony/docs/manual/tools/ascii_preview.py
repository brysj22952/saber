#!/usr/bin/env python3
"""Render a screenshot as an ASCII/ANSI preview so the layout can be
inspected without a vision model.

Usage:
    python3 scripts/ascii_preview.py <image> [--cols 120] [--rows 45] [--color]
"""
import sys

from PIL import Image

CHARS = " .:-=+*#%@"


def main():
    path = sys.argv[1]
    cols = 120
    rows = 45
    color = "--color" in sys.argv
    if "--cols" in sys.argv:
        cols = int(sys.argv[sys.argv.index("--cols") + 1])
    if "--rows" in sys.argv:
        rows = int(sys.argv[sys.argv.index("--rows") + 1])

    im = Image.open(path).convert("RGB")
    w, h = im.size
    # keep the aspect ratio roughly square-ish in terminal cells
    cell_w = w / cols
    cell_h = cell_w / 0.5
    rows = min(rows, max(1, int(h / cell_h)))

    small = im.resize((cols, rows), Image.LANCZOS)
    px = small.load()
    out = []
    for y in range(rows):
        line = []
        for x in range(cols):
            r, g, b = px[x, y]
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            ch = CHARS[min(len(CHARS) - 1, int(lum * len(CHARS)))]
            if color:
                line.append(f"\x1b[38;2;{r};{g};{b}m{ch}\x1b[0m")
            else:
                line.append(ch)
        out.append("".join(line))
    print("\n".join(out))
    print(f"\n[{w}x{h} -> {cols}x{rows}]")


if __name__ == "__main__":
    main()
