#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# prepare_signing.sh —— 准备好签名材料,并把配置写进 ohos/build-profile.json5
#
# 用法:
#   bash toolchain/ohos/prepare_signing.sh
#
# 三种情况,按优先级自动判断:
#
#   1. AGC(华为开发者账号)签发的材料齐全
#      (signing/app.p12 + signing/app.p7b + signing/app.cer)
#      -> 校验证书与 profile 是否配套,写配置
#      -> 产物能装到「调试 Profile 白名单里的 HarmonyOS NEXT 真机」
#
#   2. 已有 OpenHarmony 社区证书材料(signing/saber.p12 + signing/saber.p7b)
#      -> 直接写配置
#      -> 产物只能装到 OpenHarmony 设备 / DevEco 模拟器
#
#   3. 什么都没有
#      -> 用 SDK 自带的社区证书现场生成一套
#      -> 同上,只能装到 OpenHarmony 设备 / 模拟器
#
# 环境变量:
#   STORE_PWD  密钥库密码(默认 123456)
#   ALIAS      密钥别名(默认 saber-key)
# ---------------------------------------------------------------------------
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

STORE_PWD="${STORE_PWD:-123456}"
ALIAS="${ALIAS:-saber-key}"

# 把「社区证书材料」写进 build-profile.json5
write_community_config() {
  local hex
  hex="$(node "$TOOLCHAIN_DIR/encrypt_signing_password.js" "$SIGN_DIR" "$STORE_PWD")"
  python3 "$TOOLCHAIN_DIR/apply_signing_config.py" "$BUILD_PROFILE" \
    --store-file "signing/saber.p12" \
    --profile-file "signing/saber.p7b" \
    --certpath "signing/saber-app-cert.pem" \
    --key-alias "openharmony application release" \
    --password-hex "$hex"
}

# --- 1. AGC 材料 -----------------------------------------------------------
if [ -f "$SIGN_DIR/app.p12" ] && [ -f "$SIGN_DIR/app.p7b" ] && [ -f "$SIGN_DIR/app.cer" ]; then
  echo "==> 检测到 AGC(华为账号)签发的材料"
  exec bash "$TOOLCHAIN_DIR/use_agc_signing.sh" "$STORE_PWD" "$ALIAS"
fi

# --- 2. 已有社区材料 -------------------------------------------------------
if [ -f "$SIGN_DIR/saber.p12" ] && [ -f "$SIGN_DIR/saber.p7b" ]; then
  echo "==> 检测到 OpenHarmony 社区证书材料"
  if [ ! -d "$SIGN_DIR/material" ]; then
    echo "    material/ 缺失,从 SDK 的 hvigor 插件复制"
    mkdir -p "$SIGN_DIR/material"
    cp -r "$DEVECO_TOOLS/hvigor/hvigor-ohos-plugin/res/material/." "$SIGN_DIR/material/"
  fi
  write_community_config
  echo
  echo "    ⚠️ 社区证书只能装到 OpenHarmony 设备 / DevEco 模拟器。"
  echo "       要装 HarmonyOS NEXT 真机,请用华为账号签发的材料(见 docs/ohos.md §4)。"
  exit 0
fi

# --- 3. 现场生成社区材料 ---------------------------------------------------
echo "==> 未找到签名材料,用 SDK 自带的社区证书生成一套"
python3 "$TOOLCHAIN_DIR/make_signing_profile.py"
