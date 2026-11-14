#!/usr/bin/env python3
"""Dump the HarmonyOS UI hierarchy of the foreground app and print a compact
text outline (type / text / description / bounds), so the layout can be
described and annotated without a vision model.

Usage:
    python3 scripts/uidump.py                # print outline of current screen
    python3 scripts/uidump.py --json         # print raw node list as JSON
    python3 scripts/uidump.py --min-text 2   # only nodes with text length >= 2
"""
import json
import re
import subprocess
import sys

HDC = "/root/hzq/saber-ohos/ohos-sdk-root/ohos-sdk/18/toolchains/hdc"
REMOTE = "/data/local/tmp/layout.json"


def dump():
    subprocess.run([HDC, "shell", "uitest", "dumpLayout", "-p", REMOTE],
                   capture_output=True, text=True)
    out = subprocess.run([HDC, "file", "recv", REMOTE, "/tmp/layout.json"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"dumpLayout 失败: {out.stderr}")
    with open("/tmp/layout.json", encoding="utf-8") as f:
        return json.load(f)


def walk(node, depth=0):
    yield depth, node
    for c in node.get("children", []) or []:
        yield from walk(c, depth + 1)


def attrs(node):
    a = node.get("attributes", {}) or {}
    return {
        "type": a.get("type", ""),
        "text": a.get("text", ""),
        "desc": a.get("description", "") or a.get("hint", ""),
        "id": a.get("id", ""),
        "bounds": a.get("bounds", ""),
        "clickable": a.get("clickable", ""),
        "enabled": a.get("enabled", ""),
        "visible": a.get("visible", ""),
    }


def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    min_text = 0
    if "--min-text" in args:
        min_text = int(args[args.index("--min-text") + 1])

    data = dump()
    out = []
    for depth, node in walk(data):
        a = attrs(node)
        if as_json:
            out.append(a)
            continue
        label = a["text"] or a["desc"] or ""
        if len(label) < min_text and not a["id"]:
            continue
        if not label and not a["id"]:
            continue
        out.append({
            "depth": depth,
            "type": a["type"],
            "label": label,
            "id": a["id"],
            "bounds": a["bounds"],
            "clickable": a["clickable"],
        })

    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    for o in out:
        print(f"{'  ' * o['depth']}[{o['type']:<18}] {o['label']!r:<46} "
              f"id={o['id']!r:<28} {o['bounds']} click={o['clickable']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
