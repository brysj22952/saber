# Saber 鸿蒙(HarmonyOS NEXT)适配说明

本文档记录 Saber 适配到 **鸿蒙 / HarmonyOS NEXT** 平台的全过程:
怎么把上游那个 Flutter 桌面/移动应用,变成一个能装进鸿蒙平板的 `.hap` 包。

适配遵循的原则:**尽量不改动原有代码,只新增文件**。
Saber 的业务源码(`lib/`、`pubspec.yaml`)一个字节都没改,
所有改动都是「新增目录 / 新增脚本 / 新增文档」。

| 新增内容 | 说明 |
|---|---|
| [`ohos/`](../ohos/) | 鸿蒙工程骨架(`flutter create --platforms ohos` 生成),含签名配置 |
| [`packages/stow_secure/`](../packages/stow_secure/) | `stow_secure` 的鸿蒙实现(底层用 `shared_preferences`) |
| [`patches/ohos/`](../patches/ohos/) | 构建前对 pub cache 的修补(见 [patches/ohos/README.md](../patches/ohos/README.md)) |
| [`scripts/build_ohos.sh`](../scripts/build_ohos.sh) | 一键构建脚本 |
| [`toolchain/ohos/`](../toolchain/ohos/) | 主机侧工具链:SDK 修补、AOT 打通、签名、设备安装 |
| [`docs/ohos.md`](ohos.md) | 本文档 |

> **工具链也放进仓库了。**
> SDK 声明树同步、API 回补、AOT 补丁、签名材料生成、装设备 ——
> 这些活儿以前散在仓库外的 `toolchain/` 目录里,别人复现不了。
> 现在统一收进 `toolchain/ohos/`,路径全部可移植,见
> [toolchain/ohos/README.md](../toolchain/ohos/README.md)。

---

## 0. 快速开始

### 0.1 准备环境

需要三样东西:

| 组件 | 版本 | 备注 |
|---|---|---|
| Flutter | [Flutter-OH](https://atomgit.com/oh-flutter/flutter_flutter) `3.47.9-ohos-1.0.0` | **不是官方 Flutter** —— 官方版没有 OHOS 平台支持 |
| 鸿蒙 SDK | HarmonyOS **6.0.1(API 21)** | DevEco command-line-tools 6.0.1.251 |
| 构建工具 | ohpm 5.1.3 + hvigor 5.18.5 | command-line-tools 自带 |

> 官方 Flutter 没有 `TargetPlatform.ohos`,也没有 OHOS 的构建目标,
> 用官方版跑 `flutter build hap` 会直接报 "Unknown operating system"。
> 必须用 [Flutter-OH](https://atomgit.com/oh-flutter/flutter_flutter) 这个 fork。

把它们摆成下面这样(目录名可以自己改,改完设置环境变量就行):

```
<工作区>/
├── flutter/                          # Flutter-OH SDK
├── ohos-sdk-root/ohos-sdk/           # OpenHarmony SDK
├── deveco-tools/command-line-tools/  # DevEco 命令行工具
└── saber/                            # 本仓库
```

### 0.2 一条命令构建

```bash
cd saber
source toolchain/ohos/env.sh          # 导出 FLUTTER_ROOT / OHOS_SDK_HOME / PATH ...
bash scripts/build_ohos.sh --debug    # 首次建议 --debug,失败信息更全
```

产物:

```
build/ohos/hap/entry-default-signed.hap
```

> `env.sh` 会按「仓库的上一级目录」推导所有路径。
> 你的目录布局不一样的话,先 `export SABER_OHOS_ROOT=/你的/工作区` 再 source。

### 0.3 装到平板

```bash
bash toolchain/ohos/install_on_device.sh
```

或者手动:

```bash
hdc install build/ohos/hap/entry-default-signed.hap
hdc shell aa start -a EntryAbility -b com.sabernotes.saber
```

> ⚠️ **签名的坑在鸿蒙上比在 Android 上大得多。**
> 鸿蒙安装时强制验签,证书链不被设备信任就装不上(没有「未知来源」旁路)。
> 用 SDK 自带的 OpenHarmony 社区证书只能装到 OpenHarmony 设备 / 模拟器;
> 要装到 HarmonyOS NEXT 真机(如 MatePad Edge),必须用**华为开发者账号**
> 签发的证书 + 绑定设备 UDID 的 Profile。
> 完整流程见 [§3 签名](#3-签名hap-最容易踩坑的一环) 与 [§4 装到真机](#4-装到-harmonyos-next-真机如-matepad-edge)。

### 0.4 出问题时先看这里

| 现象 | 先看 |
|---|---|
| `flutter build hap` 报不认识 ohos | 用错 Flutter 了,必须是 Flutter-OH |
| 白屏 + `MissingPlatformDirectoryException` | release 构建没带 `--dart-define=FLUTTER_OHOS_AOT_BUILD=true`,见 [§4.9](#49-linux-主机上的-releaseaot构建--已打通) |
| 白屏 + `MissingPluginException ... window_manager` | 同上 |
| 签名相关报错(`Illegal base64 character 20` 等) | [§4.7 常见报错对照](#47-常见报错对照) |
| 装不上真机(`code:9568257`) | 证书不是华为账号签发的,见 [§3.6](#36-本地签名的适用范围) |
| 交互掉帧(每 100ms 一次 JANK) | 用的是 debug 包,改用 release,见 [§4.9](#49-linux-主机上的-releaseaot构建--已打通) |

---

## 1. 环境

### 1.1 组件与版本

| 组件 | 版本 |
|---|---|
| Flutter | [Flutter-OH](https://atomgit.com/oh-flutter/flutter_flutter) `3.47.9-ohos-1.0.0` |
| 鸿蒙 SDK | HarmonyOS **6.0.1(API 21)**(DevEco command-line-tools 6.0.1.251) |
| 构建工具 | ohpm 5.1.3 + hvigor 5.18.5 |
| JDK | 17 |

### 1.2 环境变量

`toolchain/ohos/env.sh` 一次性导出下列变量:

| 变量 | 作用 | 默认值 |
|---|---|---|
| `FLUTTER_ROOT` | Flutter-OH SDK | `<工作区>/flutter` |
| `OHOS_SDK_HOME` | OpenHarmony SDK | `<工作区>/ohos-sdk-root/ohos-sdk` |
| `DEVECO_SDK_HOME` | HarmonyOS SDK(Flutter-OH 用) | `<工作区>/deveco-tools/command-line-tools/sdk` |
| `DEVECO_SDK_ROOT` | 真正的 SDK 内容目录 | `<工作区>/deveco-tools/command-line-tools/sdk/default` |
| `DEVECO_TOOLS` | DevEco 命令行工具 | `<工作区>/deveco-tools/command-line-tools` |
| `PUB_CACHE` | pub 缓存 | `<工作区>/.pub-cache` |

> `DEVECO_SDK_HOME` 与 `DEVECO_SDK_ROOT` 差一层,是**故意**的:
> Flutter-OH 按 `sdk/<apiVersion 对应的目录>` 定位 SDK,所以它要的是
> `sdk/` 这一层;而工具脚本要访问 `openharmony/toolchains/lib/hap-sign-tool.jar`
> 这类路径,用的是真正放内容的那一层 `sdk/default`。
> 之前两者混用,导致「source 了 env.sh 之后 `gen_csr.sh` 找不到签名工具」。

想换目录布局,设 `SABER_OHOS_ROOT` 即可:

```bash
export SABER_OHOS_ROOT=/your/workspace
source toolchain/ohos/env.sh
```

### 1.3 产物与安装

构建产物:

```
build/ohos/hap/entry-default-signed.hap
```

安装到设备:

```bash
hdc install build/ohos/hap/entry-default-signed.hap
hdc shell aa start -a EntryAbility -b com.sabernotes.saber
```

---


## 2. 做了什么适配

### 2.1 存储层

Saber 把配置分成两类([`lib/data/prefs.dart`](../lib/data/prefs.dart)):

* `PlainStow` → `shared_preferences`
* `SecureStow` → `stow_secure` → `flutter_secure_storage`

`flutter_secure_storage` 至今没有鸿蒙实现,直接用会在启动时抛 `MissingPluginException`。
因此在 `packages/stow_secure/` 下放了一份鸿蒙实现(API 与上游完全一致),
底层改用 `shared_preferences`,再通过依赖覆盖换掉上游那个依赖
`flutter_secure_storage` 的实现:

```yaml
# toolchain/ohos/pubspec_overrides.yaml
dependency_overrides:
  stow_secure:
    path: packages/stow_secure
```

> 覆盖文件本体放在 `toolchain/ohos/pubspec_overrides.yaml`,
> 由 `scripts/build_ohos.sh` 在构建前复制到仓库根目录。
> **不放根目录是有意的**:pub 会自动读取根目录的 `pubspec_overrides.yaml`,
> 放在那里的话,上游 CI 和任何克隆了本仓库的人跑 `flutter pub get`
> 都会被强制去拉 gitcode 上的鸿蒙分支插件 —— 与鸿蒙无关的
> Android / Linux / Windows 构建也会跟着变慢、变得不稳。
> 细节见 [toolchain/ohos/README.md](../toolchain/ohos/README.md)。

> ⚠️ 安全提示:`shared_preferences` 落在应用沙箱内的普通文件,不等同于 KeyStore 的
> 硬件级加密。正式上架前建议把 `packages/stow_secure` 换成基于鸿蒙 `huks`
> (密钥托管服务)的实现。

### 2.2 官方插件的鸿蒙实现

用 [OpenHarmony-TPC/flutter_packages](https://gitcode.com/openharmony-tpc/flutter_packages)
里的鸿蒙分支覆盖了三个用得到的官方插件:

| 插件 | 用途 |
|---|---|
| `shared_preferences` | 本地配置 |
| `path_provider` | 应用数据目录 |
| `url_launcher` | 打开链接 |

### 2.3 `TargetPlatform.ohos`

Flutter-OH 给 `TargetPlatform` 增加了 `ohos` 成员,一些第三方包里的
`switch (TargetPlatform)` 是穷尽的,会直接编译失败:

```
The type 'TargetPlatform' is not exhaustively matched by the switch cases
since it doesn't match 'TargetPlatform.ohos'.
```

目前需要处理的有 `flutter_quill`、`flex_color_picker`,
在 `patches/ohos/apply_ohos_patches.sh` 里给它们补上 `case TargetPlatform.ohos:`
(按移动端处理)。

### 2.4 原生资产(native assets)

| 包 | 问题 | 处理 |
|---|---|---|
| `super_native_extensions` | build hook 用 Rust 交叉编译,依赖 glib/gobject,鸿蒙没有对应产物 | 跳过 hook |
| `pdfium_dart` | build hook 从 GitHub 下载预编译 pdfium(只有 android/linux/macos/windows) | 跳过 hook |

---

## 3. 签名(HAP 最容易踩坑的一环)

鸿蒙的签名配置有三处约束,任何一处不对都会在 `SignHap` 阶段失败。

### 3.1 `storePassword` 不是明文

hvigor 5.x 起,`ohos/build-profile.json5` 中的 `storePassword` / `keyPassword`
**不是明文密码**,而是 AES-128-GCM 加密后的十六进制串:

* 长度必须 **≥ 32 且为偶数**,否则报
  `00303116 Configuration Error — The length of the storePassword or keyPassword field ... is less than 32.`
* 密钥由**与 `.p12` 同级目录**下的 `material/` 目录派生:

  ```
  ohos/signing/
  ├── saber.p12
  ├── material/
  │   ├── fd/{0,1,2}/<sha256>    # 三个 16 字节分量
  │   ├── ac/<sha256>            # 16 字节 PBKDF2 salt
  │   └── ce/<sha256>            # rootKey 加密的工作密钥
  ├── saber.p7b                  # 签好的 provisioning profile
  └── saber-app-cert.pem         # 应用证书链(3 级 + 2 root)
  ```

本仓库的 `toolchain/ohos/encrypt_signing_password.js` 就是这套算法的逆运算,
`toolchain/ohos/make_signing_profile.py` 负责生成 profile 与证书链。

### 3.2 `certpath` 必须是证书链

`certpath` 指向的**不能是单张证书**,必须是完整链,否则报
`11013004 Profile cert must a cert chain`。
直接复用 SDK 提供的 `OpenHarmonyApplication.pem` 即可。

### 3.3 profile 的证书字段:调试 vs 发布

两种 profile 的 `bundle-info` 字段**不一样**,这是最容易搞混的地方:

| profile 类型 | 证书字段 | 设备绑定 |
|---|---|---|
| `release`(发布) | `distribution-certificate` | 无 |
| `debug`(调试) | `development-certificate` | `debug-info.device-ids` 列出允许安装的设备 UDID |

调试 profile 的 `bundle-info` 里**没有** `distribution-certificate`,
只有 `development-certificate`。写脚本时两种都要兼容。

SDK 里对应的模板文件:

```
<SDK>/openharmony/toolchains/lib/UnsgnedReleasedProfileTemplate.json
<SDK>/openharmony/toolchains/lib/UnsgnedDebugProfileTemplate.json
```

调试 profile 里的证书字段同样必须填**单张**叶子证书(PEM 文本),
且 PEM 末尾要有换行符(见 §3.4)。

`toolchain/ohos/make_debug_profile.py` 可以生成带设备白名单的调试 profile:

```bash
python3 toolchain/ohos/make_debug_profile.py \
  saber/ohos/signing/app.p12 \
  saber/ohos/signing/app.cer \
  saber/ohos/signing/app-debug.p7b \
  <平板的UDID>
```

`toolchain/ohos/use_agc_signing.sh` 的校验逻辑已经同时支持两种字段。

### 3.4 PEM 末尾必须留换行符 ⚠️

这是个非常隐蔽的坑:如果 `distribution-certificate` 的 PEM 文本
**末尾少了换行符**,签名会报:

```
ERROR: 11010001 Unknown error
Error Message: Illegal base64 character 20
```

`20` 是十六进制的 ASCII 码,指的是**空格**。原因是签名工具按行剥离
`-----BEGIN/END CERTIFICATE-----` 后,最后一行残留了尾部空白。

所以 PEM 必须是这个形态(注意 `END CERTIFICATE-----` 后面还有一个 `\n`):

```
-----BEGIN CERTIFICATE-----\n
MIIC...\n
...\n
-----END CERTIFICATE-----\n
```

`toolchain/ohos/use_agc_signing.sh` 里带了校验,会在改配置之前就把这个问题查出来。

### 3.5 profile 与证书必须配套

签名工具会校验 profile 里的证书字段(`distribution-certificate` 或
`development-certificate`)与 `certpath` 证书链的叶子证书**完全一致**,
否则报:

```
verify certificate chain failed! Signature does not match.
```

也就是说 `.p7b` 和 `.cer` 必须来自同一次证书申请,不能混用。

### 3.6 本地签名的适用范围

当前签名材料来自 SDK 内置的 **OpenHarmony 官方调试证书**:

* ✅ 可安装到 OpenHarmony 设备与 DevEco 模拟器
* ❌ **不能**安装到 HarmonyOS NEXT 真机 —— 真机只认华为开发者账号签发的材料

**已在真机上实测确认**(HUAWEI MatePad Edge,`QXS-W20`,HarmonyOS 7.0.0 / API 26):

```
$ hdc install -r entry-default-signed.hap
error: failed to install bundle. code:9568257 error: fail to verify pkcs7 file.
```

注意这个错误码是 `9568257`,**不是** `9568393`(签名不匹配)——
说明设备根本不认识这条证书链的根,连比对的机会都没有。

原因在 OpenHarmony 的应用完整性校验模块里说得很清楚
([security_appverify](https://github.com/openharmony/security_appverify)):

> 为了方便开源社区开发者,版本中预置了公钥证书和对应的私钥……
> **在 OpenHarmony 商用版本中应替换此公钥证书和对应的私钥。**

MatePad Edge 跑的是 HarmonyOS 6(商用版),系统预置的根证书是**华为的**,
不是 OpenHarmony 社区的那套,所以社区调试证书验签必然失败。

真机安装流程见下一节。

> **调试能不能免证书?**
>
> 不能。鸿蒙没有 Android 那种「未知来源」旁路 —— 安装时系统会强制验签,
> 证书链不信任就装不上。但**调试证书比发布证书轻得多**:
> 免费、不需要审核、不需要上架,只要账号完成实名认证就能自助签发。
> 详见下一节的 §4.3。

---

## 4. 装到 HarmonyOS NEXT 真机(如 MatePad Edge)

HarmonyOS NEXT 设备**只认华为开发者账号签发的证书**。整个流程是:

```
本地生成密钥对+CSR  →  AGC 签发 .cer  →  AGC 签发 .p7b(绑定设备 UDID)
      →  改 build-profile.json5  →  重新构建  →  hdc install
```

`toolchain/ohos/` 下已经把每一步都脚本化了。

### 4.0 实测环境(2026-11)

| 项 | 值 |
|---|---|
| 设备 | HUAWEI MatePad Edge,型号 `QXS-W20` |
| 系统 | HarmonyOS `7.0.0.111(SP16C00E111R6P5)` |
| API | `26` |
| 应用 `minAPIVersion` | `60001021`(API 21)—— 满足设备下限,不会被版本拦 |
| `deviceTypes` | `default` / `tablet` / `2in1` |
| UDID | 64 位十六进制,用 `hdc shell bm get --udid` 读 |

连接方式用的是**无线调试**:设备开「无线调试」后监听一个高位端口,
在开发机上 `hdc tconn <设备IP>:<端口>`,首次需要设备上点「信任」。
连上后 `hdc list targets -v` 会显示 `Connected`(未授权时是 `Unauthorized`)。

**已实测通过**:

```
$ hdc install -r entry-default-signed.hap
install bundle successfully.

$ hdc shell aa start -a EntryAbility -b com.sabernotes.saber
start ability successfully.
```

界面渲染正常,点击「+」可展开「导入笔记 / 新建笔记」,新建笔记能打开完整的
手写编辑器工具栏;无 Dart 异常、无崩溃。

完整的部署记录(含 UDID、APP ID、证书名)见仓库根目录的
`DEPLOY-RECORD.md`。

### 4.1 准备:注册账号 + 拿到 Bundle Name

1. 注册 [华为开发者联盟](https://developer.huawei.com/consumer/cn/)(免费,个人开发者)。
2. 完成**实名认证**(个人开发者一般即时通过;企业认证需 1~3 个工作日)。
   这是自助签发调试证书的前置条件 —— 认证完就能进 AGC 了。
3. 在 [AppGallery Connect](https://developer.huawei.com/consumer/cn/service/josp/agc/index.html)
   创建应用,拿到 **Bundle Name**。
   ⚠️ 这个 Bundle Name 必须同时写进 `ohos/AppScope/app.json5`,
   且与 `.p7b` 里的 `bundle-name` 一致,否则设备拒绝安装。
4. 平板开启「开发者选项 → USB 调试」,并用数据线连到这台机器。

> **调试 vs 上架的差别**:调试证书免费、自助签发、**不需要提交审核**,
> 也不需要上架。调试证书有数量限制(每个账号通常 1 个调试 + 1 个发布证书),
> 而且 debug profile 里的 `debug-info.device-ids` 会绑定设备 UDID ——
> 换设备要重新生成 profile。

### 4.2 生成密钥对与 CSR

```bash
bash toolchain/ohos/gen_csr.sh
```

产出:

| 文件 | 用途 |
|---|---|
| `saber/ohos/signing/app.p12` | 密钥库(默认密码 `123456`,别名 `saber-key`) |
| `saber/ohos/signing/app.csr` | 证书签名请求,拿去 AGC 申请证书 |

> 这一步不需要联网,也不需要华为账号,可以先跑。
>
> ⚠️ 密钥对**只能生成一次**。已经用它申请过证书之后再换密钥对,
> 之前签发的 `.cer` / `.p7b` 会全部失效(签名时报 `Certificates Error`)。
> 脚本默认不覆盖已有密钥对,确实要换才加 `--force`。

### 4.3 在 AGC 申请证书与 Profile

1. AGC →「用户与访问」→「证书管理」→「新建证书」→ 类型选**调试**
   → 上传 `app.csr` → 下载 `.cer`(证书链)。
2. AGC →「用户与访问」→「证书管理」→「Profile」→「新建」:

   | 字段 | 值 |
   |---|---|
   | 证书 | 上一步的 `.cer` |
   | 包名 | 你在 AGC 创建应用的 Bundle Name |
   | 设备 | 平板的 UDID(见下) |

3. 保存后下载 `.p7b`。

获取平板 UDID:

```bash
<SDK>/hms/toolchains/hdc shell bm get --udid
```

### 4.4 切换签名材料并构建

把下载到的文件放到 `saber/ohos/signing/`:

```
app.cer     # AGC 签发的证书链
app.p7b     # AGC 签发的 profile
```

然后:

```bash
bash toolchain/ohos/use_agc_signing.sh 123456 saber-key
```

这个脚本会:

1. 用 `encrypt_signing_password.js` 把明文密码加密成 hvigor 需要的 hex 串;
2. 把 `.cer` 复制成 `app-cert.pem`;
3. **校验** profile 的 `distribution-certificate` 与证书链是否匹配
   (不匹配会直接报错,而不是让你等到构建失败);
4. 改写 `ohos/build-profile.json5` 的 `signingConfigs`。

然后重新构建:

```bash
source toolchain/ohos/env.sh
flutter build hap --debug
```

### 4.5 安装与启动

```bash
bash toolchain/ohos/install_on_device.sh
```

等价于:

```bash
hdc install build/ohos/hap/entry-default-signed.hap
hdc shell aa start -a EntryAbility -b com.sabernotes.saber
```

### 4.6 平板适配

`ohos/entry/src/main/module.json5` 的 `deviceTypes` 已经加上 `tablet` 与 `2in1`:

```json5
"deviceTypes": ["default", "tablet", "2in1"]
```

只写 `phone` 的话,平板上装不上或显示异常。

### 4.7 常见报错对照

| 报错 | 原因 | 处理 |
|---|---|---|
| `Illegal base64 character 20` | PEM 末尾缺换行符 | 见 §3.4,`use_agc_signing.sh` 会提前检出 |
| `verify certificate chain failed! Signature does not match.` | `.p7b` 和 `.cer` 不是同一次申请 | 重新申请,两者必须配套 |
| `Profile cert must a cert chain` | `certpath` 指向了单张证书 | 要用完整证书链 |
| `11010001 ... storePassword ... less than 32` | 密码没加密 | 走 `use_agc_signing.sh`,别手填明文 |
| 安装报「签名证书不匹配」 | `.p7b` 里的 Bundle Name 与应用实际包名不一致 | 两边都要改成同一个 |
| `code:9568393` | Profile 没包含这台设备的 UDID | 在 AGC 的 Profile 里补上 UDID 重新生成 |
| `failed to verify pkcs7 file` | 证书链顺序/内容不对 | 确认 `certpath` 是链且 PEM 格式正确 |

### 4.8 上架前的检查项

1. **许可证**:Saber 是 **GPL-3.0** 授权。用它构建的鸿蒙应用也必须以 GPL-3.0
   开源(公开完整源码),这是 GPL 的硬性要求。闭源上架属于违反许可证。
2. **签名**:上架必须用华为账号签发的**发布证书 + 发布 Profile**,
   `type` 需为 `release`(调试证书无法上架)。
3. **包名**:`com.sabernotes.saber`(见 `ohos/AppScope/app.json5`),
   必须换成你自己在 AppGallery Connect 上申请的 Bundle Name。
4. **权限**:`ohos/entry/src/main/module.json5` 里目前只申请了 `INTERNET`。
   若后续用到文件、剪贴板、相册等能力,需要补充对应权限。
5. **API 版本**:当前 `compileSdkVersion` / `compatibleSdkVersion` /
   `targetSdkVersion` 均为 `6.0.1(21)`。

### 4.9 Linux 主机上的 release(AOT)构建 —— 已打通

#### 结论

`bash scripts/build_ohos.sh`(默认 release)在 Linux 主机上**可以构建**,
走的是本仓库 `toolchain/ohos/setup_ohos_aot.sh` 装好的三处补丁。

| 指标 | debug | **release** |
|---|---|---|
| 包体积 | 246 MB | **39 MB** |
| 交互时掉帧 | 约每 100 ms 一次 `ReportJANKEvent` | **0** |

#### 为什么默认做不到

1. `build_system/targets/common.dart` 把 `TargetPlatform.ohos*` 映射成
   `'ohos'` 传给 frontend_server 的 `--target-os`,仅在 `if (aot)` 时传。
2. 官方 Dart SDK 3.13.7 的 `--target-os` 白名单只有
   `android / fuchsia / ios / linux / macos / windows`,**没有 ohos**。
3. fork 为此提供了定制 runtime `dart-sdk-ohos.zip`,但包内是
   **Mach-O arm64**(macOS),Linux 上 `Exec format error`。
4. AOT 还要 `gen_snapshot`。fork 只发布了 `ohos-arm64-release-darwin-x64.zip`;
   官方 OBS 上那个 `linux-x64` 版本是 **kernel 130**(Dart 3.12.2)的老产物,
   与本工具链的 kernel 138 不兼容:
   `Can't load Kernel binary: Invalid kernel format version (expected 130, found 138)`。
5. 核对 `3.47.9-ohos-1.0.0` 的**全部 15 个附件**:没有任何 linux 主机工件。

#### 本仓库怎么解的

`toolchain/ohos/setup_ohos_aot.sh` 依次做六件事(幂等,可重复跑):

1. **装 Wine**(`wine64`)
2. **下载 Windows 版 gen_snapshot** —— 取自 `3.47.4-ohos-1.0.4`,
   它是 kernel 138,与当前工具链匹配
   > atomgit 的 Release 直链**必须带 `Referer` 头**,否则 401
3. **装包装器** —— 把 `ohos-arm64-release/linux-x64/gen_snapshot`
   换成一个调用 `wine gen_snapshot.exe "$@"` 的脚本,flutter 无感知
4. **补丁:flutter_tools 传 `--target-os=linux`** —— OHOS 的 Dart 运行时
   本来就是 Linux 系统调用,语义上成立
5. **补丁:框架强制判定 ohos** —— 见下
6. **补丁:插件注册表把 ohos 分支提到最前** —— 见下

#### 第 5、6 步补丁为什么必须

`--target-os` 的作用是**把 `Platform.isXxx` 常量折叠进 AOT 快照**。
用 `linux` 编出来的包里 `Platform.isLinux` 恒为 `true`,于是 Flutter 里
这些「Linux 在前、ohos 在后」的判断全部走错:

```dart
// foundation/_platform_io.dart —— defaultTargetPlatform
} else if (Platform.isLinux) {          // ← 先命中,变成 TargetPlatform.linux
  result = TargetPlatform.linux;
} else if (Platform.operatingSystem == 'ohos') {   // ← 永远走不到
  result = TargetPlatform.ohos;
}
```

后果串起来是这样的:

| 现象 | 根因 |
|---|---|
| 白屏,日志 `MissingPlatformDirectoryException` | 插件注册表注册了 `path_provider_linux`,拿不到文档目录 |
| 白屏,日志 `MissingPluginException ... window_manager` | `main.dart` 的 `Platform.isWindows \|\| isLinux \|\| isMacOS` 判断成立,调用了桌面插件 |

对应补丁:

- `toolchain/ohos/patch_ohos_aot_platform.py` 给 `_platform_io.dart` 和
  `_window_io.dart` 加了编译期开关 `FLUTTER_OHOS_AOT_BUILD`,
  为 true 时直接判定 `TargetPlatform.ohos`
- `flutter_tools/lib/src/flutter_plugins.dart` 的模板里把 ohos 分支
  提到最前,并用同一个开关兜住
- `patches/ohos/apply_ohos_patches.sh` 第 4 项给 `window_manager`
  加了 `MissingPluginException` 降级(鸿蒙本来就不需要窗口管理)

构建时通过 `--dart-define=FLUTTER_OHOS_AOT_BUILD=true` 打开开关,
`build_ohos.sh` 已经内置。

#### 遗留说明

这套是**工具链侧的权宜之计**。彻底干净的做法是从 Dart 源码构建一份
`TargetOS` 白名单含 `ohos` 的 `frontend_server`,那样两个补丁都能撤掉。
目前没做是因为需要完整 Dart SDK 源码树 + 交叉编译,成本较高。

#### 附带发现:本地 `dart-sdk-ohos` 可能残缺

`update_dart_sdk.sh` 的下载条件是
`[ ! -x bin/cache/dart-sdk-ohos/bin/dartaotruntime ]`。
文件存在(哪怕是残缺副本)就**永远不会重新下载**。
本机之前就是这种情况:目录里只有 3 个文件。


## 5. 已知限制

| 功能 | 状态 |
|---|---|
| 笔记的增删改查、画板、缩略图 | ✅ 可用 |
| PDF 预览 / 导入图片 | ❌ 不支持(缺鸿蒙版 pdfium) |
| Nextcloud 同步 | ⚠️ 依赖 `url_launcher`/`http`,同步本身可用,但登录页跳转需要真机验证 |
| 后台同步(WorkManager) | ❌ 无鸿蒙实现,同步只在应用前台进行 |
| Android 手写笔(OnyxSDK) | ❌ 本来就只支持 Android,鸿蒙端自动跳过 |
| 分享、导出、系统相册 | ❌ 对应插件暂无鸿蒙实现 |
| Sentry 崩溃上报 | ⚠️ 仅在用户主动同意后启用,鸿蒙端需另配 native SDK |
| `printing`(导出 PDF) | ⚠️ 插件无鸿蒙实现,启动时会被忽略(不影响启动) |

---

## 6. 工具链侧的坑

Flutter-OH 的 Linux 主机支持还不完整,以下都是工具链侧的工作。
相关脚本都在 `toolchain/ohos/` 下,记录在此方便复现:

1. **`dart-sdk-ohos.zip` 里没有 Linux x64 的 Dart SDK**(只有 macOS 的
   `dartaotruntime`),因此 `frontend_server` 需要用打过补丁的 Dart SDK 源码
   自行编译(补丁内容:给 CFE 的 `Abi` 加上 `ohos` 系 ABI,否则编译期会报
   `Type IntPtr has no mapping for ABI ... "ohos"`)。
2. **引擎 har 声明的 API 版本**(API 24)高于可获得的 SDK,需要下调到 21。
3. **官方 SDK 压缩包里的 `toolchains` 是 aarch64**,在 x86_64 主机上无法运行
   (`restool` 会报 `Syntax error`),需要换成 `linux-x64` 版本。
4. **ArkTS 声明树**:SDK 里自带的 `ets-loader/declarations/` 是旧版 API 18 的
   内容,直接编译会报十几个 `Cannot find name 'BusinessError'` /
   `Property 'isCapsLockOn' does not exist`。需要用官方 API 21 的
   `{api,component,kits}` 覆盖,并**保留** loader 独有的
   `global.d.ts` / `ability_component.d.ts` / `featureability.d.ts`
   (否则所有用到 `console` / `setTimeout` 的文件都会编译失败)。
5. **两个高版本 API 的符号**:引擎用到的 `CompetitionStrategy`(API 24)与
   `Window.isInFreeWindowMode()`(API 22)在 API 21 的声明树里不存在。
   两者在引擎里都有运行时保护(`sdkApiVersion >= 24` / `>= 22`),
   因此在声明树里回补这两个符号即可安全编译。
6. **SDK 文件权限**:解压后的 SDK 大量文件丢失可执行位,
   `es2abc` / `restool` 会报 `Permission denied`。
7. **`llvm-strip` 架构**:SDK 只带 aarch64 交叉版 `llvm-strip`,
   x86-64 主机上要用宿主 LLVM 替换。
