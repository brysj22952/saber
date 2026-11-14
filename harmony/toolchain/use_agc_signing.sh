#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 切换到「华为开发者联盟(AGC)签发」的签名材料,用于 HarmonyOS NEXT 真机。
#
# 前提:已经把 AGC 下载的 .cer(证书链)和 .p7b(描述文件)放到 signing/ 目录,
#       并且有本机生成的 app.p12(见 toolchain/gen_csr.sh)。
#
# 用法:
#   bash toolchain/use_agc_signing.sh <密码> [密钥别名]
#
#   <密码>     app.p12 的密钥库密码(默认 123456)
#   [密钥别名]  app.p12 里的别名(默认 saber-key)
#
# 本脚本做三件事:
#   1. 用 encrypt_signing_password.js 把明文密码加密成 hvigor 要的 hex 串
#   2. 把 .cer 拼成证书链放到 app-cert.pem
#   3. 改写 build-profile.json5 的 signingConfigs
# ---------------------------------------------------------------------------
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
ROOT="$SABER_OHOS_ROOT"
SIGN_DIR="$SIGN_DIR"
PROFILE="$BUILD_PROFILE"
TOOLCHAIN="$TOOLCHAIN_DIR"

PWD_PLAIN="${1:-123456}"
ALIAS="${2:-saber-key}"

P12="$SIGN_DIR/app.p12"
CER="$SIGN_DIR/app.cer"
P7B="$SIGN_DIR/app.p7b"
CHAIN="$SIGN_DIR/app-cert.pem"

echo "==> 1/5 检查文件"
for f in "$P12" "$CER" "$P7B"; do
  if [ ! -f "$f" ]; then
    echo "错误:缺少 $f" >&2
    echo "  先运行 bash toolchain/gen_csr.sh,并把 AGC 下载的文件放到 $SIGN_DIR" >&2
    exit 1
  fi
done
echo "    app.p12   OK"
echo "    app.cer   OK"
echo "    app.p7b   OK"

echo
echo "==> 2/5 检查 material 目录(密码解密密钥)"
if [ ! -d "$SIGN_DIR/material" ]; then
  echo "    从 SDK 插件复制 material ..."
  mkdir -p "$SIGN_DIR/material"
  cp -r "$ROOT/deveco-tools/command-line-tools/hvigor/hvigor-ohos-plugin/res/material/." "$SIGN_DIR/material/"
fi
echo "    $SIGN_DIR/material OK"

echo
echo "==> 3/5 加密密码"
HEX=$(node "$TOOLCHAIN/encrypt_signing_password.js" "$SIGN_DIR" "$PWD_PLAIN")
echo "    storePassword/keyPassword = ${HEX:0:24}... (${#HEX} chars)"

echo
echo "==> 4/5 组装证书链"
# AGC 下载的 .cer 可能是:
#   (a) 完整证书链(叶子 + 中间 CA)—— 直接用
#   (b) 只有一张叶子证书 —— 需要补上级 CA,否则签名报
#       「11013004 Profile cert must a cert chain」
if grep -q "BEGIN CERTIFICATE" "$CER"; then
  COUNT=$(grep -c "BEGIN CERTIFICATE" "$CER")
  echo "    app.cer 含 $COUNT 张证书"
  if [ "$COUNT" -lt 2 ]; then
    echo "    ⚠️ 只有 1 张证书,需要补上级 CA"
    if python3 "$TOOLCHAIN/complete_cert_chain.py" "$CER" "$CHAIN"; then
      echo "    ✓ 已补全证书链"
    else
      cp "$CER" "$CHAIN"
      echo "    ✗ 没能自动补链。签名会报「Profile cert must a cert chain」。"
      echo "      请从 AGC 重新下载完整的证书链,或手动在 app-cert.pem 里"
      echo "      追加上级 CA 证书(叶子在前)。"
    fi
  else
    cp "$CER" "$CHAIN"
  fi
else
  cp "$CER" "$CHAIN"
fi

echo
echo "==> 4.5/5 校验 profile 与证书是否匹配"
# 签名工具要求:
#   1. profile 里的 distribution-certificate 必须与 appCertFile 链的叶子证书完全一致
#      (不一致 -> "verify certificate chain failed! Signature does not match.")
#   2. PEM 末尾必须保留换行符
#      (缺失 -> "Illegal base64 character 20")
python3 - "$P7B" "$CHAIN" <<'PY'
import base64, json, os, re, subprocess, sys, tempfile

p7b, chain = sys.argv[1], sys.argv[2]

def certs_from_pem(text):
    return re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        text, re.S)

def der_of(pem):
    body = "".join(l for l in pem.splitlines() if "CERTIFICATE" not in l)
    return base64.b64decode(body)

# 解出 profile 里的 distribution-certificate
with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
    payload = tmp.name
subprocess.run(["openssl", "smime", "-verify", "-noverify", "-in", p7b,
                "-inform", "DER", "-out", payload],
               capture_output=True, check=False)
try:
    with open(payload) as f:
        prof = json.load(f)
finally:
    os.unlink(payload)

bi = prof["bundle-info"]
# 调试 profile 用 development-certificate,发布 profile 用 distribution-certificate
cert_field = ("development-certificate" if "development-certificate" in bi
              else "distribution-certificate")
if cert_field not in bi:
    print("    ✗ profile 里既没有 development-certificate 也没有 distribution-certificate")
    sys.exit(1)
print("    profile 类型: %s,证书字段: %s" % (prof.get("type"), cert_field))

dc = bi[cert_field]
try:
    dc_der = der_of(dc)
except Exception as e:
    print("    ✗ profile 的 %s base64 解码失败: %s" % (cert_field, e))
    print("      常见原因:PEM 末尾缺少换行符")
    sys.exit(1)

with open(chain) as f:
    chain_certs = certs_from_pem(f.read())
if not chain_certs:
    print("    ✗ app-cert.pem 里没有找到证书")
    sys.exit(1)

if any(der_of(c) == dc_der for c in chain_certs):
    print("    ✓ profile 的 %s 与证书链匹配" % cert_field)
else:
    print("    ✗ profile 的 %s 与证书链不匹配!" % cert_field)
    print("      签名会报「verify certificate chain failed! Signature does not match.」")
    print("      原因:profile 是用另一张证书签发的")
    sys.exit(1)

# 调试 profile 绑定设备白名单,提示一下
di = prof.get("debug-info") or prof.get("debuginfo")
if di and di.get("device-ids"):
    ids = di["device-ids"]
    print("    调试证书绑定设备 %d 台:" % len(ids))
    for u in ids:
        print("      %s" % u)
    print("    ⚠️ 只有白名单里的设备能装这个包,平板的 UDID 必须在其中")
PY

echo
echo "==> 5/5 改写 build-profile.json5"
python3 "$TOOLCHAIN/apply_signing_config.py" "$PROFILE" \
  --store-file "signing/app.p12" \
  --profile-file "signing/app.p7b" \
  --certpath "signing/app-cert.pem" \
  --key-alias "$ALIAS" \
  --password-hex "$HEX"

echo
echo "════ 完成 ════"
cat <<EOF
现在可以重新构建:

    source $TOOLCHAIN_DIR/env.sh
    cd $SABER_REPO_ROOT
    flutter build hap --debug

然后安装到平板:

    bash $TOOLCHAIN/install_on_device.sh
EOF
