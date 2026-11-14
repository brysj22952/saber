#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup_ohos_aot.sh —— 在 Linux 主机上打通鸿蒙 release(AOT)构建
#
# 背景(详见 saber/docs/ohos.md §4.9):
#   Flutter-OH 这个 fork 的 release 构建只发布了 macOS / Windows 主机的
#   AOT 工件,Linux 主机一个都没有。所以默认情况下:
#
#     flutter build hap --release
#     → ERROR: "ohos" is not an allowed value for option "--target-os"
#
# 本脚本用三个补丁把这条链打通:
#
#   1. frontend_server 的 --target-os 白名单没有 ohos
#      → 让 flutter_tools 传 'linux'(OHOS 的 Dart 运行时本就是 Linux 系)
#
#   2. 传 'linux' 会让 Platform.isLinux 变成 AOT 编译期常量 true,
#      框架和插件注册表会把鸿蒙误判成桌面 Linux
#      → 打 FLUTTER_OHOS_AOT_BUILD 开关,强制判定为 ohos
#
#   3. 官方 OBS 上那个 linux-x64 的 gen_snapshot 是 kernel 130 的老版本
#      → 换用 3.47.4-ohos-1.0.4 发布的 Windows 版(kernel 138)+ Wine
#
# 幂等:可重复执行,已完成的步骤会跳过。
#
# 用法:
#   bash toolchain/setup_ohos_aot.sh
# ---------------------------------------------------------------------------
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
ROOT="$SABER_OHOS_ROOT"
FLUTTER="$FLUTTER_ROOT"
TOOLCHAIN="$TOOLCHAIN_DIR"
TOOLS="$FLUTTER/packages/flutter_tools"

GS_DIR="$FLUTTER/bin/cache/artifacts/engine/ohos-arm64-release/linux-x64"
GS_URL="https://atomgit.com/oh-flutter/flutter_flutter/releases/download/3.47.4-ohos-1.0.4/ohos-arm64-release-windows-x64.zip"

say() { echo; echo "==> $*"; }

say "1/6 检查 Wine"
if [ ! -x /usr/lib/wine/wine64 ]; then
  echo "    安装 wine64 ..."
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wine64
  # 初始化 prefix(首次需要)
  WINEDEBUG=-all /usr/lib/wine/wine64 wineboot --init >/dev/null 2>&1 || true
else
  echo "    已安装"
fi

say "2/6 准备 Windows 版 gen_snapshot(kernel 138)"
mkdir -p "$TOOLCHAIN/ohos-aot-win" "$GS_DIR"
if [ ! -f "$TOOLCHAIN/ohos-aot-win/gen_snapshot.exe" ]; then
  echo "    下载 ..."
  # 注意:atomgit 的 Release 直链必须带 Referer,否则 401
  curl -sL --max-time 300 \
    -H "Referer: https://atomgit.com/oh-flutter/flutter_flutter/releases" \
    -A "Mozilla/5.0 (X11; Linux x86_64)" \
    -o /tmp/ohos-gs-win.zip "$GS_URL"
  unzip -q -o /tmp/ohos-gs-win.zip -d /tmp/ohos-gs-extract
  cp /tmp/ohos-gs-extract/gen_snapshot.exe "$TOOLCHAIN/ohos-aot-win/"
  rm -rf /tmp/ohos-gs-win.zip /tmp/ohos-gs-extract
else
  echo "    已存在"
fi
cp -f "$TOOLCHAIN/ohos-aot-win/gen_snapshot.exe" "$GS_DIR/gen_snapshot.exe"
echo "    版本检查:"
"$TOOLCHAIN/gen_snapshot_wine.sh" --version 2>&1 | sed 's/^/      /'

say "3/6 安装 gen_snapshot 包装器"
cp -f "$TOOLCHAIN/gen_snapshot_wine.sh" "$GS_DIR/gen_snapshot"
chmod +x "$GS_DIR/gen_snapshot"
echo "    $GS_DIR/gen_snapshot"

say "4/6 补丁:flutter_tools 传 --target-os=linux"
PATCHED_TOOLS=0
if ! grep -q "FLUTTER_OHOS_AOT_TARGET_OS" "$TOOLS/lib/src/build_system/targets/common.dart"; then
  python3 - "$TOOLS/lib/src/build_system/targets/common.dart" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = """      TargetPlatform.ohos_arm64 ||
      TargetPlatform.ohos_x64 => 'ohos',"""
new = """      // OHOS: AOT 的 --target-os 用 'linux' 而不是 'ohos'。
      // 官方 frontend_server 的白名单里没有 'ohos',而 fork 的 ohos 定制版
      // 只发布了 Mach-O / PE,Linux 主机跑不了。详见 docs/ohos.md §4.9。
      TargetPlatform.ohos_arm64 ||
      TargetPlatform.ohos_x64 =>
        globals.platform.environment['FLUTTER_OHOS_AOT_TARGET_OS'] ?? 'linux',"""
assert old in s, "common.dart 锚点未找到"
s = s.replace(old, new, 1)
s = s.replace("import '../../globals.dart' as globals show xcode;",
              "import '../../globals.dart' as globals show platform, xcode;", 1)
open(p, 'w').write(s)
print("    已打补丁")
PY
  PATCHED_TOOLS=1
else
  echo "    已打过"
fi

say "5/6 补丁:框架在 AOT 下强制判定为 ohos"
python3 "$TOOLCHAIN/patch_ohos_aot_platform.py"

say "6/6 补丁:插件注册表把 ohos 分支提到最前"
if ! grep -q "鸿蒙分支必须放在最前面" "$TOOLS/lib/src/flutter_plugins.dart"; then
  python3 - "$TOOLS/lib/src/flutter_plugins.dart" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()

old = """  static void register() {
    if (Platform.isAndroid) {
      {{#android}}
$_dartPluginRegisterWith
      {{/android}}
    } else if (Platform.isIOS) {"""
new = """  static void register() {
    // OHOS: 鸿蒙分支必须放在最前面。
    // --target-os=linux 会把 Platform.isLinux 折叠成常量 true,导致鸿蒙上
    // 注册的是 Linux 桌面插件(path_provider_linux 等),应用白屏。
    if (const bool.fromEnvironment('FLUTTER_OHOS_AOT_BUILD') ||
        Platform.operatingSystem == 'ohos') {
      {{#ohos}}
$_dartPluginRegisterWith
      {{/ohos}}
    } else if (Platform.isAndroid) {
      {{#android}}
$_dartPluginRegisterWith
      {{/android}}
    } else if (Platform.isIOS) {"""
assert old in s, "flutter_plugins.dart 头部锚点未找到"
s = s.replace(old, new, 1)

old2 = """    } else if (Platform.isWindows) {
      {{#windows}}
$_dartPluginRegisterWith
      {{/windows}}
    } else if (Platform.operatingSystem == 'ohos') {
      {{#ohos}}
$_dartPluginRegisterWith
      {{/ohos}}
    }
  }
}"""
new2 = """    } else if (Platform.isWindows) {
      {{#windows}}
$_dartPluginRegisterWith
      {{/windows}}
    }
  }
}"""
assert old2 in s, "flutter_plugins.dart 尾部锚点未找到"
s = s.replace(old2, new2, 1)
open(p, 'w').write(s)
print("    已打补丁")
PY
  PATCHED_TOOLS=1
else
  echo "    已打过"
fi

if [ "$PATCHED_TOOLS" -eq 1 ]; then
  say "重建 flutter_tools 快照(改了工具源码)"
  rm -f "$FLUTTER/bin/cache/flutter_tools.snapshot" "$FLUTTER/bin/cache/flutter_tools.stamp"
  ( cd "$FLUTTER" && bin/flutter --version >/dev/null 2>&1 ) || true
  echo "    完成"
fi

say "自检"
export WINEDEBUG=-all
echo -n "  gen_snapshot: "
"$GS_DIR/gen_snapshot" --version 2>&1 | head -1
echo -n "  wine:         "
[ -x /usr/lib/wine/wine64 ] && echo ok || echo MISSING

cat <<'EOF'

════════════════════════════════════════
 完成。现在可以构建 release:
     bash saber-harmony.sh build
════════════════════════════════════════
EOF
