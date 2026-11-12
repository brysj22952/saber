#!/usr/bin/env python3
"""Patch Flutter-OH's flutter_tools so plugin-symlink failures are tolerated on Windows.

Why
---
Creating symlinks on Windows requires "Developer Mode". Without it every
flutter command (even `flutter pub get`) aborts with:

    Building with plugins requires symlink support.

and the underlying error is ERROR_PRIVILEGE_NOT_HELD (1314).

This fork is "Flutter for Ohos" (features.dart: isOhosEnabled is constant true):
  * the ohos build never uses the windows/ or linux/ plugin symlinks
    (those are desktop-build artifacts);
  * you cannot build a Linux/macOS desktop app from a Windows host anyway.

So two changes:
  A. under the ohos fork, skip the windows/ plugin symlinks entirely;
  B. turn symlink failures caused by missing privileges (1314) into a warning
     instead of aborting the whole command.

Note
----
* Only relevant on Windows (Linux/macOS can create symlinks without privileges).
* This touches the same file as the "move the ohos branch to the front of the
  plugin registry" patch in toolchain/ohos/setup_ohos_aot.sh, but a different
  place; the two do not conflict.

Usage:
    python toolchain/ohos/windows/patch_flutter_tools_symlink.py [--flutter <FLUTTER_ROOT>]
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

# --- A) skip windows/ plugin symlinks ---------------------------------------
ANCHOR_A_OLD = """  if (localFeatureFlags.isWindowsEnabled && project.windows.existsSync()) {
    _createPlatformPluginSymlinks(
      project.windows.pluginSymlinkDirectory,"""

ANCHOR_A_NEW = """  // OHOS: this fork is "Flutter for Ohos"; the Windows desktop build is out of
  // scope. Creating plugin symlinks on Windows needs developer mode (otherwise
  // ERROR_PRIVILEGE_NOT_HELD / 1314), and without it even `flutter pub get`
  // aborts. The ohos build does not use the windows/ plugin symlinks, so skip.
  if (localFeatureFlags.isWindowsEnabled &&
      project.windows.existsSync() &&
      !localFeatureFlags.isOhosEnabled) {
    _createPlatformPluginSymlinks(
      project.windows.pluginSymlinkDirectory,"""

MARKER_A = ("!localFeatureFlags.isOhosEnabled", "OHOS: this fork is \"Flutter for Ohos\"")

# --- B) 1314 -> warning ------------------------------------------------------
ANCHOR_B_OLD = """      throwToolExit('Building with plugins requires symlink support.\\n\\n$instructions');"""

ANCHOR_B_NEW = """      // OHOS: Windows not in developer mode cannot create symlinks (error 1314).
      // The ohos build does not need the windows/ or linux/ plugin symlinks
      // (those are desktop-build artifacts), so downgrade this to a warning
      // instead of aborting the whole command.
      globals.printWarning(
        'OHOS: skipped plugin symlink (Windows needs developer mode): '
        '$destination',
      );
      return;"""

MARKER_B = (
    "OHOS: skipped plugin symlink",
    "OHOS: 跳过插件符号链接",
    "OHOS: Windows not in developer mode cannot create symlinks",
)


def apply_one(
    path: pathlib.Path,
    old: str,
    new: str,
    markers: tuple[str, ...],
    label: str,
) -> bool:
    """Return True when the file was changed (False when already patched)."""
    src = path.read_text(encoding="utf-8")
    if any(m in src for m in markers):
        print(f"    [skip] {label}: already patched")
        return False
    if old not in src:
        print(f"    [error] {label}: anchor not found (flutter_tools version changed?)", file=sys.stderr)
        raise SystemExit(2)
    path.write_text(src.replace(old, new, 1), encoding="utf-8")
    print(f"    [ok] {label}: patched")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flutter", default="", help="Flutter-OH SDK root")
    args = ap.parse_args()

    root_arg = args.flutter or os.environ.get("FLUTTER_ROOT", "")
    if not root_arg:
        print("[error] need --flutter or FLUTTER_ROOT", file=sys.stderr)
        return 1
    root = pathlib.Path(root_arg)
    target = root / "packages" / "flutter_tools" / "lib" / "src" / "flutter_plugins.dart"
    if not target.is_file():
        print(f"[error] not found: {target}", file=sys.stderr)
        return 1

    changed = False
    ok = apply_one(target, ANCHOR_A_OLD, ANCHOR_A_NEW, MARKER_A, "A skip windows/ links")
    changed = changed or ok
    ok = apply_one(target, ANCHOR_B_OLD, ANCHOR_B_NEW, MARKER_B, "B 1314 -> warning")
    changed = changed or ok
    if not ok:
        return 2

    # The tool source changed -> let flutter rebuild its snapshot.
    # (只有真的改了源码才删,否则每次构建都要重建工具,白白多花一分钟。)
    if changed:
        for name in ("flutter_tools.stamp", "flutter_tools.snapshot"):
            p = root / "bin" / "cache" / name
            if p.exists():
                p.unlink()
                print(f"    [ok] removed {name} (flutter rebuilds it on next run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
