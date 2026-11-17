# Saber 鸿蒙版 · 上架华为应用市场(AppGallery Connect)

这份文档是**交给首尔那台云电脑上的 DSH 干活的说明书**。
它假设执行者只看得懂这个仓库、没读过我们之前的对话。

---

## 0. 开场提示词(可直接粘给首尔的 DSH)

> 读 `harmony/docs/RELEASE-TO-APPGALLERY.md`,按里面的阶段 0→5 执行「把 Saber 鸿蒙版
> 上架到华为应用市场」。所有操作前先跑阶段 0 的环境自检,每阶段结束按「验收标准」
> 自检并把结果写进 `harmony/docs/DEPLOY-RECORD.md` 的新一节。
> 注意文档里 §6「禁止事项」,尤其不要把签名材料写进仓库或对话里。

---

## 1. 背景

Saber 是一个 Flutter 写的**手写笔记**应用(上游 https://github.com/saber-notes/saber,5044 star)。
我们已经把它移植到 HarmonyOS NEXT,能装到真机、能在真机上手写、能导出、能同步 Nextcloud
(细节见 [`harmony/README.md`](../README.md))。

**当前状态**:调试包已装到两台真机(平板 + 手机)并正常运行。
**目标**:把应用提交到华为应用市场审核。

| 项 | 值 |
|---|---|
| 包名 | `com.sabernotes.saber` |
| 应用名 | Saber |
| 版本 | versionName `1.0.0` / versionCode `1000000` |
| targetSdkVersion | `6.0.1(21)` |
| deviceTypes | `default`(手机) / `tablet` / `2in1` |
| 仓库 | https://github.com/brysj22952/saber 分支 `feature/ohos-harmonyos` |
| 上游 | https://github.com/saber-notes/saber |
| 许可证 | **GPL-3.0**(硬约束,见 §4.3) |

> AGC 的 APP ID / 项目 ID / 设备 UDID 等标识**不要写进仓库**(仓库是公开的)。
> 需要时去控制台现取。

---

## 2. 执行环境

### 2.1 首尔那台云电脑

| 项 | 值 |
|---|---|
| 仓库 | `/root/hzq/saber-ohos/saber`(分支 `feature/ohos-harmonyos`) |
| Flutter-OH SDK | `/root/hzq/saber-ohos/flutter` |
| DevEco 命令行工具 | `/root/hzq/saber-ohos/deveco-tools/command-line-tools` |
| OpenHarmony SDK | `/root/hzq/saber-ohos/ohos-sdk-root/ohos-sdk` |
| GitHub 凭据 | `/root/.git-credentials`(Seoul 能直连 GitHub,Windows 不行) |
| 浏览器 | Chromium + `--remote-debugging-port=9333`,**已登录华为账号** |
| 控制台驱动 | `harmony/toolchain/agc/agc_console.py`(见该目录 README) |

### 2.2 构建(发布包)

```bash
cd /root/hzq/saber-ohos/saber
source harmony/toolchain/env.sh
bash harmony/scripts/build_ohos.sh --release
# 产物:build/ohos/hap/entry-default-signed.hap(约 37.9MB)
```

Windows 本机也可以构建(不需要 Linux 构建机):
`powershell -File harmony\scripts\build_ohos.ps1 -Mode release`,细节见
[`BUILD-LOCAL.md`](BUILD-LOCAL.md)。

### 2.3 浏览器/CDP

```bash
# 确认浏览器还活着、AGC 页面还在
curl -s http://127.0.0.1:9333/json/list | head -c 400
python3 harmony/toolchain/agc/agc_console.py top menus
```

> 浏览器 session 里的登录态是**这台机器的资产**,不要在别的机器上重新登录。

---

## 3. 现在是什么状态(别重复做)

已经完成的:

- ✅ 鸿蒙适配全部完成,真机可用(平板 + 手机各装了一个 release 包)
- ✅ 调试证书 + 调试 Profile 已申请,**当前签名材料就是调试版**
- ✅ AGC 里已有 Saber 应用,包名 `com.sabernotes.saber`
- ✅ 用户手册 + 15 张平板真机截图在 `harmony/docs/manual/`
- ✅ GitHub 上仓库是同步的(`feature/ohos-harmonyos`)

还没做的(就是下面的阶段):

- ❌ 发布证书 / 发布 Profile
- ❌ 上架材料(图标、截图、隐私政策、权限说明)
- ❌ 上传版本 / 提交审核

---

## 4. 三个已定的决策(照做,别再纠结)

### 4.1 targetSdkVersion 暂时保持 `6.0.1(21)`

AGC 控制台提示「自 2027 年 1 月 1 日起检测 targetSdkVersion,建议升级到 26.0.0」。
**决策:本次上架先用 21 过审**,把「升 API 26」放到上架之后的下一个版本做。

理由:升 API 26 需要 DevEco 命令行工具 6.1.x+(本机没有)、引擎 har 的 API 声明对齐
(`harmony/toolchain/patch_engine_har_api.py`)、`ohos/build-profile.json5` 三个版本字段一起改,
工作量接近重做一遍构建链,会拖慢本次上架。

> 但:**提交前再回控制台看一眼**那条提示有没有升级成「必须」。如果变成硬性要求,
> 立刻停下来汇报,别硬提交。

### 4.2 隐私政策 URL 用 GitHub Pages

商店页必须填一个**可公开访问的隐私政策 URL**。我们没有自己的域名,最省事的做法:

1. 在 fork 仓库里开一个 `gh-pages` 分支,放一个 `privacy-policy.html`
   (底稿:仓库根的 `privacy_policy.md`,但要补上鸿蒙版特有的内容:
   文件存储位置、Nextcloud 同步、收集哪些权限、不收集什么);
2. URL 形如 `https://brysj22952.github.io/saber/privacy-policy.html`;
3. **提交前一定要用无痕窗口打开这个 URL 验证能访问**,填进商店页。

> 上游的 `saber.adil.hanney.org/privacy-policy` 是上游作者的站点,可以用作参考,
> 但不要直接填别人的域名。

### 4.3 GPL-3.0:公开源码 + 商店页声明

Saber 是 GPL-3.0,**用它的代码构建的鸿蒙应用也必须以 GPL-3.0 开源**,
闭源上架属于违反许可证。所以:

- 商店页「开源许可」/「其他信息」里声明:本应用基于 Saber(GPL-3.0)修改,
  源码公开于 https://github.com/brysj22952/saber/tree/feature/ohos-harmonyos;
- 源码仓库**已经**包含完整构建链(`harmony/` 目录),满足 GPL 的「附带源码」要求;
- 应用内的「设置 → 关于」如果有位置,补一行 GPL 声明(可选)。

---

## 5. 阶段分解

每个阶段结束都跑一次「验收标准」,不达标不要进下一阶段。

### 阶段 0 · 环境自检(10 分钟)

```bash
cd /root/hzq/saber-ohos/saber
git status -sb                     # 期望:与 fork/feature/ohos-harmonyos 同步,工作树干净
git log --oneline -3
bash -c 'source harmony/toolchain/env.sh && echo $FLUTTER_ROOT && echo $OHOS_SDK_HOME'
ls -la build/ohos/hap/             # 期望:有 entry-default-signed.hap
python3 harmony/toolchain/agc/agc_console.py top menus   # 期望:列出左侧菜单
```

**验收**:五项都正常;浏览器页面停在 AGC 控制台且已登录。

### 阶段 1 · 发布证书 + 发布 Profile(30–60 分钟)

**为什么要新的**:调试 profile 带设备白名单、字段是 `development-certificate`,
**调试签名不能上架**。

1. 生成 CSR(复用现有密钥对,别重新生成 —— 重新生成会让已签发的证书全部作废):

   ```bash
   ls -la ohos/signing/app.csr ohos/signing/app.p12   # 确认这两个还在
   ```

2. AGC 控制台 →「ID、证书和Profile」→「证书」→「新建证书」→ 类型选**发布**
   → 上传 `ohos/signing/app.csr` → 下载 `.cer`(证书链)。

3. AGC 控制台 →「Profile」→「新建」→ 类型**发布**、证书选上一步的 `.cer`、
   包名 `com.sabernotes.saber` → 保存 → 下载 `.p7b`。

   > 发布 profile **没有设备白名单**,所以不用先加设备。

4. 把材料落到仓库外的本地目录(**不要提交进 git**):

   ```
   ohos/signing/app-release.cer   # 发布证书链
   ohos/signing/app-release.p7b   # 发布 profile
   ```

   > `ohos/signing/` 已经在 `.gitignore` 里(`ohos/.gitignore` 的 `/signing/`),
   > 但**仍然要检查 `git status` 里没有它们**再提交别的东西。

5. 校验 profile 与证书配套:

   ```bash
   openssl smime -verify -noverify -in ohos/signing/app-release.p7b -inform DER \
     | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['type']); print(d['bundle-info'].keys())"
   # 期望:type == release,且 bundle-info 里有 distribution-certificate
   ```

**验收**:`app-release.p7b` 的 `type` 是 `release`;包名是 `com.sabernotes.saber`;
`distribution-certificate` 与 `app-release.cer` 的叶子证书一致;
`git status` 里没有任何签名材料。

### 阶段 2 · 用发布材料重新构建(约 10–20 分钟)

发布签名和调试签名的差别只在 `ohos/build-profile.json5` 的 `signingConfigs`。
本仓库的 `harmony/toolchain/prepare_signing.py` 会优先用 `ohos/signing/app.*`
(调试那套),所以发布包要显式指定:

```bash
cd /root/hzq/saber-ohos/saber
source harmony/toolchain/env.sh

# 用发布材料改写 build-profile.json5
python3 harmony/toolchain/prepare_signing.py --password 123456 --alias saber-key
# ↑ 这一步默认会用 app.p12/app.p7b/app.cer
#    如果发布材料用了别的文件名,先改名成 app.cer / app.p7b(备份旧的),
#    或直接用 harmony/toolchain/use_agc_signing.sh

bash harmony/scripts/build_ohos.sh --release
```

构建完**核对签名**:

```bash
# 取出包里的 profile,和发布 profile 比对
java -jar "$DEVECO_SDK_ROOT/openharmony/toolchains/lib/hap-sign-tool.jar" verify-app \
  -inFile build/ohos/hap/entry-default-signed.hap \
  -outCertChain /tmp/chain.cer -outProfile /tmp/inside.p7b
python3 - <<'PY'
import json,subprocess
def load(p):
    out=subprocess.run(["openssl","smime","-verify","-noverify","-in",p,"-inform","DER"],
                       capture_output=True)
    return json.loads(out.stdout)
inner=load("/tmp/inside.p7b")
outer=load("ohos/signing/app.p7b")
print("包内 profile type:", inner["type"])
print("与外层 profile 一致:", inner == outer)
PY
```

**验收**:跑这个脚本,全绿才算过:

```bash
python3 harmony/toolchain/verify_app_package.py
```

它会检查:包内图标**没有 alpha 通道**(第 1、2 轮的阻塞项)、签名有效、
包内 profile 是 `release` 且与 `ohos/signing/app-release.p7b` 一致、
版本号/包名/应用名对不对。

> ⚠️ **签名在 `.app` 上,不在里面的 hap 上**:上架包是**整包签名**(app-level),
> 签名块在 `.app` 自己身上,里面的 `entry-default.hap` 不带签名。
> 所以要 `hap-sign-tool verify-app` 对 `.app` 跑,对 hap 跑会报
> `No Hap Signing Block before ZIP Central Directory` ✗。

> 顺带:把旧的调试包备份走,别覆盖掉还能装平板/手机的那个。

### 阶段 3 · 上架材料(1–2 小时)

| 材料 | 从哪来 | 要求 |
|---|---|---|
| 应用图标 | `harmony/assets/app-icon-1024.png` | 1024×1024 PNG,**无 alpha 通道**(华为要求不透明);由 `harmony/toolchain/make_app_icon.py` 生成。包内 `ohos/**/media/*.png` 是**同一张图缩到 512×512 的 RGB**(画面内容一致),**不要**再放 1024 进包内 —— 见 [DEPLOY-RECORD.md](DEPLOY-RECORD.md) §2026-11-18「包内图标的 alpha 通道」 |
| 手机截图 | **要补拍** | ≥3 张:首页、编辑器、新建笔记菜单。可以用 `hdc` 截图:`hdc shell snapshot_display -f /data/local/tmp/s.jpeg` + `hdc file recv` |
| 平板截图 | `harmony/docs/manual/img/*.png` | 已有 15 张(标注图),挑 3–5 张干净的 |
| 隐私政策 | 新写 + GitHub Pages | §4.2 |
| 应用介绍 | 新写 | 中文,200 字以内,突出「手写 / 笔型 / 无云端也能用 / 可选 Nextcloud 同步」 |
| 权限说明 | `ohos/entry/src/main/module.json5` | 实际只申请了 **`ohos.permission.INTERNET`**(用于可选的 Nextcloud 同步)—— 如实写,不要夸大 |
| 分类 / 年龄分级 | 按实际选 | 工具类,无 UGC(笔记是本地的) |

**隐私政策必须写清的要点**(鸿蒙版特有):

- 笔记与图片**默认只存在设备本地**;
- 同步功能走**用户自选的 Nextcloud 服务器**,笔记在上传前用随机密钥加密;
- 密钥与密码存设备的 `stow_secure`(鸿蒙实现);
- **只申请网络权限**(`ohos.permission.INTERNET`),仅在开启同步时使用;
- **不收集**任何个人信息 / 无广告 / 无统计 SDK;
- 卸载即删除全部本地数据。

> **关于崩溃上报(Sentry)**:上游 Saber 有 Sentry,默认 **opt-in**
> (`sentryConsent` 初值是 `unknown` → 不启用)。而在鸿蒙版上它**根本不会初始化** ——
> 因为 AOT 用 `--target-os=linux` 编译,`dart:io` 的 `Platform.isLinux` 被常量折叠成 true,
> 而上游的判据是 `isSentryAvailable => !Platform.isLinux`。
> 即:**鸿蒙版没有崩溃上报**。写政策时按「不采集崩溃日志」写,
> 但**先在真机设置页确认一下有没有 Sentry 相关开关**,以实际为准。
>
> 顺带提醒:同一个 `Platform.isLinux == true` 也让上游的 `isDesktop` 在鸿蒙上为真
> (见 `lib/data/prefs.dart`)。目前没造成可见问题,但上架后的用户反馈里如果出现
> 「桌面版才有的行为」,先查这里。

**验收**:每项材料齐备且能打开;隐私政策 URL 无痕窗口可访问;截图清晰无个人隐私信息。

### 阶段 4 · 上传 + 提交审核(30–60 分钟)

AGC 控制台 →「应用管理」→「Saber」→「版本管理」→ 新建版本:

1. 上传 `build/ohos/hap/entry-default-signed.hap`(或它产出的 `.app` 包);
2. 填版本号(建议 `1.0.0` / versionCode 递增)、更新说明;
3. 填 §3 的材料(隐私政策 URL、截图、简介、权限);
4. 勾选开源许可声明(GPL-3.0,§4.3);
5. 提交。

**常见卡点**:

- **要求 API 26** → 停,回 §4.1,汇报;
- **要求企业资质** → 确认账号类型;个人开发者一般可上架工具类应用;
- **要求 ICP / 备案** → 笔记类不涉及;
- **隐私政策 URL 不可访问** → 填之前务必无痕窗口验证。

**验收**:版本状态变成「审核中」。

### 阶段 5 · 轮询审核(1–7 个工作日)

Seoul 是云电脑,正好长跑:

```bash
# 每天查一次
python3 harmony/toolchain/agc/agc_console.py top click 应用管理
python3 harmony/toolchain/agc/agc_console.py iframe text | head -60
```

被驳回就按意见改 → 重新构建 → 重新提交,并把每一轮的结论写进
`harmony/docs/DEPLOY-RECORD.md`。

**验收**:版本状态变成「已上架 / 已发布」。

---

## 6. 禁止事项

1. **不要把签名材料写进仓库、提交进 git、贴进对话**:
   `ohos/signing/` 下的 `.p12` / `.p7b` / `.cer` / `.csr` / `material/` 全是私钥级材料,
   泄露 = 任何人都能冒充你的应用签名。`ohos/.gitignore` 已经忽略 `/signing/`,
   但**每次提交前都要 `git status` 确认**。
2. **不要直接改上游文件**。上游 Saber 的源码保持原样,任何改动都要写成
   `harmony/patches/upstream/*.patch`(见 `harmony/README.md` §2.1)。
3. **不要用调试 profile 上架**。
4. **不要把 AGC 的 APP ID / 项目 ID / 设备 UDID 写进仓库**。
5. **不要动 `harmony/patches/`、`harmony/toolchain/` 里的既有逻辑**,
   除非任务确实需要;需要改就写清楚为什么。
6. **不要在没有备份的情况下覆盖 `ohos/signing/` 里已有的材料**。

---

## 7. 排障速查

| 现象 | 原因 | 处理 |
|---|---|---|
| `code:9568257` / `fail to verify pkcs7 file` | 证书链不被设备信任(用了社区证书) | 装真机要用华为账号签发的材料 |
| `code:9568393` / `9568423` | Profile 没包含这台设备的 UDID | 见 [`ohos.md` §4.5.1](ohos.md) —— 调试包才需要;发布 profile 无白名单 |
| `00306004 Specification Limit Violation` | 引擎 har 声明的 API 24 超了当前 SDK | `python3 harmony/toolchain/patch_engine_har_api.py 21` |
| `ConstFinder failure: Invalid SDK hash` | 引擎快照的 SDK hash 跟主机对不上 | `harmony/toolchain/windows/align_const_finder.py` |
| `TargetPlatform is not exhaustively matched` | 依赖补丁没打上(或者打完又跑了 `pub get`) | 补丁步骤必须在 `pub get` **之后** |
| `spawn java ENOENT` | 找不到 JDK | `env.sh` / `env.ps1` 会自动找 |
| 构建脚本报 `NativeCommandError`、退出码 1,但日志里有 `√ Built` | flutter 往 stderr 写提示,PS 5.1 包装成错误 | **以 `√ Built` 为准**,构建其实是成功的 |
| `Wrong full snapshot version` | flutter_tools 快照与 dartvm 的 SDK hash 不一致 | 两个都恢复成同一份 |

---

## 8. 交付物

完成后仓库里应该多出:

| 文件 | 内容 |
|---|---|
| `harmony/docs/APP-RELEASE-RECORD.md` | 上架过程记录:版本号、审核轮次、结论 |
| `gh-pages` 分支 | 隐私政策网页 |
| `harmony/docs/DEPLOY-RECORD.md` | 追加一节,记录上架结果 |

以及一条总结:是否上架成功、审核结论、下一步(比如升 API 26)。
