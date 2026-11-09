#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# env.sh —— Saber 鸿蒙(HarmonyOS NEXT)构建环境变量
#
# 用法:
#   source toolchain/ohos/env.sh
#
# 路径全部可覆盖;不设置时按下面的默认布局推导:
#
#   <SABER_OHOS_ROOT>/
#   ├── flutter/                         Flutter-OH SDK
#   ├── ohos-sdk-root/ohos-sdk/          OpenHarmony SDK
#   ├── deveco-tools/command-line-tools/ DevEco 命令行工具(ohpm / hvigor / SDK)
#   └── saber/                           本仓库
#
# SABER_OHOS_ROOT 默认取「仓库的上一级目录」。
# ---------------------------------------------------------------------------

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

export SABER_OHOS_ROOT

# --- Flutter-OH SDK (tag 3.47.9-ohos-1.0.0) ------------------------------
export FLUTTER_ROOT
export PATH="$FLUTTER_ROOT/bin:$PATH"

# --- OpenHarmony SDK ------------------------------------------------------
# 布局: <OHOS_SDK_HOME>/18/{ets,js,native,previewer,toolchains}
export OHOS_SDK_HOME
export OHOS_HOME="$OHOS_SDK_HOME"
export HOS_SDK_HOME="$OHOS_SDK_HOME"
export OHOS_API_DIR

# --- DevEco 命令行工具 (ohpm 5.1.3 / hvigor 5.18.5) -----------------------
export DEVECO_TOOLS
export DEVECO_NODE_HOME="$DEVECO_TOOLS/tool/node"
export PATH="$DEVECO_TOOLS/bin:$DEVECO_TOOLS/tool/node/bin:$PATH"

# --- 原生工具链 (llvm / clang for ohos targets) + hdc ---------------------
export OHOS_NDK_HOME="$OHOS_API_DIR/native"
export PATH="$OHOS_API_DIR/native/llvm/bin:$OHOS_API_DIR/toolchains:$PATH"

# --- Flutter 配置 ---------------------------------------------------------
# 官方源在国内访问不稳定,默认走镜像;有直连条件可以 unset 这两个。
export FLUTTER_STORAGE_BASE_URL="${FLUTTER_STORAGE_BASE_URL:-https://storage.flutter-io.cn}"
export PUB_HOSTED_URL="${PUB_HOSTED_URL:-https://pub.flutter-io.cn}"
export FLUTTER_SUPPRESS_ANALYTICS=true
export LANG=C.UTF-8

export PUB_CACHE
