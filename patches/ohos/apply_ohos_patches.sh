#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# OpenHarmony(鸿蒙)构建前的依赖补丁。
#
# 与 patches/pre、patches/post 的既有做法一致:直接修改 pub cache 里的文件。
# 若在本地误执行,可用 `flutter pub cache repair` 还原。
#
# 需要修的三个点:
#
#  1. 穷尽的 switch (defaultTargetPlatform)
#     Flutter-OH 给 TargetPlatform 增加了 `ohos` 成员。Flutter 3.32 之后
#     cupertino / material 被拆成 cupertino_ui / material_ui 两个 pub 包,
#     它们以及 flutter_quill / super_clipboard / background_downloader
#     内部对 TargetPlatform 的 switch 是穷尽的,不加分支会直接编译失败:
#       "The type 'TargetPlatform' is not exhaustively matched by the switch
#        cases since it doesn't match 'TargetPlatform.ohos'."
#     由 patch_target_platform_ohos.py 统一扫描 pub cache 处理。
#
#  2. super_native_extensions
#     它的 build hook 会调用 Rust 工具链交叉编译原生扩展(还依赖 glib/gobject),
#     鸿蒙端没有对应产物,直接跳过。
#
#  3. pdfium_dart
#     它的 build hook 会从 GitHub 下载预编译的 pdfium 动态库(只有
#     android/linux/macos/windows 版本),鸿蒙端没有,直接跳过。
#     代价是鸿蒙版暂时不支持 PDF 预览/导入。
#
# 用法: bash patches/ohos/apply_ohos_patches.sh
# ---------------------------------------------------------------------------
set -euo pipefail

if [ -z "${PUB_CACHE:-}" ]; then
  echo "Warning: PUB_CACHE is not set. Defaulting to \$HOME/.pub-cache"
  PUB_CACHE="$HOME/.pub-cache"
fi

echo "PUB_CACHE=$PUB_CACHE"

patched=0
skipped=0

# --- 1) TargetPlatform.ohos 穷尽性 ------------------------------------------
# 给所有对 defaultTargetPlatform 做穷尽 switch 的依赖包补上 ohos 分支。
# 见 patch_target_platform_ohos.py 的说明。
echo "==> 1/3 修补 TargetPlatform.ohos 穷尽性"
python3 "$(dirname "$0")/patch_target_platform_ohos.py" --cache "$PUB_CACHE"
patched=$((patched + 1))

# --- 2) super_native_extensions:跳过 Rust 交叉编译 --------------------------
echo "==> 2/3 跳过 super_native_extensions 的 Rust 原生扩展构建"
for f in "${PUB_CACHE}"/hosted/*/super_native_extensions-*/hook/build.dart; do
  if [ ! -f "$f" ]; then
    echo "  [skip] 未找到 super_native_extensions"
    skipped=$((skipped + 1))
    continue
  fi
  if grep -q "OpenHarmony" "$f"; then
    echo "  [skip] 已打过补丁"
    skipped=$((skipped + 1))
    continue
  fi
  cat > "$f" <<'DART'
import 'package:hooks/hooks.dart';

/// OpenHarmony:跳过 Rust 原生扩展的交叉编译。
///
/// 上游会用 native_toolchain_rust 编译 `rust/` 目录下的 crate,并依赖
/// glib / gobject 等 Linux 桌面库;鸿蒙端既没有对应的 Rust 目标产物,
/// 也不需要这些能力,这里直接产出空资产。
void main(List<String> args) async {
  await build(args, (input, output) async {
    // no code assets
  });
}
DART
  echo "  [ok] $(basename "$(dirname "$(dirname "$f")")")/hook/build.dart 已改为空实现"
  patched=$((patched + 1))
done

# --- 3) pdfium_dart:跳过预编译 pdfium 下载 ---------------------------------
echo "==> 3/3 跳过 pdfium_dart 的预编译 pdfium 下载"
for f in "${PUB_CACHE}"/hosted/*/pdfium_dart-*/hook/build.dart; do
  if [ ! -f "$f" ]; then
    echo "  [skip] 未找到 pdfium_dart"
    skipped=$((skipped + 1))
    continue
  fi
  if grep -q "OpenHarmony" "$f"; then
    echo "  [skip] 已打过补丁"
    skipped=$((skipped + 1))
    continue
  fi
  cat > "$f" <<'DART'
import 'package:code_assets/code_assets.dart';
import 'package:hooks/hooks.dart';

const _assetName = 'libpdfium';

/// OpenHarmony:跳过预编译 pdfium 的下载。
///
/// 上游会从 https://github.com/bblanchon/pdfium-binaries 下载
/// android/linux/macos/windows 四个平台的动态库,鸿蒙端没有对应产物。
/// 这里不产出任何 code asset,鸿蒙版因此暂时不支持 PDF 预览/导入。
void main(List<String> args) async {
  await build(args, (input, output) async {
    if (!input.config.buildCodeAssets) return;
    // 不添加任何 CodeAsset
  });
}
DART
  echo "  [ok] pdfium_dart/hook/build.dart 已改为空实现"
  patched=$((patched + 1))
done

# --- 4) window_manager:鸿蒙上没有原生实现 --------------------------------
# window_manager 是桌面专用插件,鸿蒙没有对应的原生侧。
# Saber 的 main.dart 用 `Platform.isWindows || Platform.isLinux || Platform.isMacOS`
# 判断是否调用 windowManager.ensureInitialized()。
#
# 而本工程在 Linux 主机上用 --target-os=linux 编 AOT(见 docs/ohos.md §4.9),
# 这让 Platform.isLinux 变成编译期常量 true,那行判断在鸿蒙上也会成立,
# 于是抛出 MissingPluginException,main() 的 Future.wait 直接中断 —— 白屏。
#
# 这里让 window_manager 在缺少原生实现时静默降级(鸿蒙本来也不需要它)。
for f in "$PUB_CACHE"/hosted/*/window_manager-*/lib/src/window_manager.dart; do
  [ -f "$f" ] || continue
  if grep -q "OHOS: 缺少原生实现时静默降级" "$f"; then
    skipped=$((skipped + 1))
    continue
  fi
  python3 - "$f" <<'PYEOF'
import sys
path = sys.argv[1]
src = open(path).read()

old = """  Future<void> ensureInitialized() async {
    await _channel.invokeMethod('ensureInitialized');
  }"""
new = """  Future<void> ensureInitialized() async {
    // OHOS: 缺少原生实现时静默降级。
    // 鸿蒙没有 window_manager 的原生侧,而 Platform.isLinux 在
    // --target-os=linux 的 AOT 快照里恒为 true,Saber 会误以为在桌面上
    // 而调用本方法。异常会中断 main() 的 Future.wait 导致白屏。
    try {
      await _channel.invokeMethod('ensureInitialized');
    } on MissingPluginException {
      // 鸿蒙上不需要窗口管理,忽略。
    }
  }"""

if old not in src:
    print("SKIP: ensureInitialized 未匹配")
    sys.exit(0)
src = src.replace(old, new, 1)

# setFullScreen 同理
old2 = """  Future<void> setFullScreen(bool isFullScreen) async {
    await _channel.invokeMethod('setFullScreen', {'isFullScreen': isFullScreen});
  }"""
new2 = """  Future<void> setFullScreen(bool isFullScreen) async {
    // OHOS: 同上,鸿蒙上没有原生实现。
    try {
      await _channel.invokeMethod('setFullScreen', {'isFullScreen': isFullScreen});
    } on MissingPluginException {
      // 忽略
    }
  }"""
if old2 in src:
    src = src.replace(old2, new2, 1)

# 确保 MissingPluginException 可引用
if "import 'package:flutter/services.dart'" not in src:
    src = src.replace("import 'package:flutter/foundation.dart';",
                      "import 'package:flutter/foundation.dart';\n"
                      "import 'package:flutter/services.dart' show MissingPluginException;", 1)

open(path, 'w').write(src)
print("PATCHED")
PYEOF
  echo "  [ok] window_manager 已加鸿蒙降级"
  patched=$((patched + 1))
done

# --- 5) url_launcher_ohos:没有内嵌浏览器页面时退回系统浏览器 --------------
# url_launcher 的鸿蒙实现对 http/https 链接默认走「应用内嵌 WebView」
# (openUrlInWebView),而原生侧要求宿主应用在 launchUrl 的 headers 里带上
# harmony_browser_page,并且真的实现并注册了那个 WebView 页面,否则只会弹一个
# 「请在 launch 函数的 headers 参数中添加 harmony_browser_page ...」的 toast,
# 链接根本打不开。
#
# Saber 没有(也不打算)实现那个内嵌浏览器页面,所以这里改成:只要调用方没有
# 显式提供 harmony_browser_page,就直接用系统浏览器打开
# (原生侧的 launchUrl -> startAbility + entity.system.browsable)。
#
# 注意 url_launcher 是 git 依赖,不在 hosted/ 下,路径形如
#   $PUB_CACHE/git/flutter_packages-<sha>/packages/url_launcher/url_launcher_ohos/
for f in "${PUB_CACHE}"/git/*/packages/url_launcher/url_launcher_ohos/lib/url_launcher_ohos.dart; do
  [ -f "$f" ] || continue
  if grep -q "OHOS: 内嵌浏览器页面未注册" "$f"; then
    echo "  [skip] url_launcher_ohos 已打过补丁"
    skipped=$((skipped + 1))
    continue
  fi
  python3 - "$f" <<'PYEOF'
import sys
path = sys.argv[1]
src = open(path).read()

old = """    final bool succeeded;
    if (useWebView) {"""
new = """    final bool succeeded;
    // OHOS: 内嵌浏览器页面未注册时退回系统浏览器。
    // 鸿蒙的 url_launcher 对 http/https 默认走应用内嵌 WebView,而原生侧要求
    // 宿主应用传 harmony_browser_page 并真的实现那个页面,否则只弹一个 toast。
    final bool hasHarmonyBrowserPage =
        headers.containsKey('harmony_browser_page');
    if (useWebView && !hasHarmonyBrowserPage) {
      succeeded = await _hostApi.launchUrl(url, headers);
    } else if (useWebView) {"""

if old not in src:
    print("SKIP: launch() 未匹配")
    sys.exit(0)
src = src.replace(old, new, 1)
open(path, 'w').write(src)
print("PATCHED")
PYEOF
  echo "  [ok] url_launcher_ohos 已改为默认用系统浏览器"
  patched=$((patched + 1))
done

echo "==> 完成:修补 $patched 处,跳过 $skipped 处"
