# Saber · HarmonyOS / OpenHarmony 适配

这个目录是 **Saber 的鸿蒙适配全部内容** 的家:代码、构建脚本、工具链、用户说明书,
全都在这里。

设计目标只有一条:**上游 Saber 的代码保持原样,我们的改动单独成目录**,
以后要合并回上游主干时,冲突面最小、随时可以一键退回。

---

## 0. 三十秒速览

```bash
# Linux / macOS
bash harmony/toolchain/env.sh          # 导出 FLUTTER_ROOT / OHOS_SDK_HOME / PATH ...
bash harmony/scripts/build_ohos.sh      # 一条命令出包(默认 release)

# Windows
. .\harmony\toolchain\env.ps1
powershell -File harmony\scripts\build_ohos.ps1
```

产物:`build/ohos/hap/entry-default-signed.hap`

装到平板:

```bash
hdc install -r build/ohos/hap/entry-default-signed.hap
hdc shell aa start -a EntryAbility -b com.sabernotes.saber
```

- 完整指南:[harmony/docs/ohos.md](docs/ohos.md)(环境准备 / 签名 / 构建 / 装机 / 排障)
- Windows 本机专版:[harmony/docs/BUILD-LOCAL.md](docs/BUILD-LOCAL.md)
- **用户使用说明书**:[harmony/docs/manual/Saber-鸿蒙版使用手册.md](docs/manual/Saber-鸿蒙版使用手册.md)
- 合并回上游的策略:[harmony/docs/ohos-upstream.md](docs/ohos-upstream.md)

---

## 1. 目录结构

```
harmony/
├── README.md                    ← 本文件
├── .gitignore                   ← 本目录的本地产物
│
├── docs/                        ← 文档
│   ├── ohos.md                  完整适配指南(环境/签名/构建/装机/排障)
│   ├── ohos-upstream.md         怎么把这套东西合并回上游主干
│   ├── BUILD-LOCAL.md           Windows 本机构建(不需要 Linux 构建机)
│   └── manual/                  用户使用说明书
│       ├── Saber-鸿蒙版使用手册.md
│       ├── img/                 15 张真机标注图
│       ├── shots/               31 张原始截图(配图的输入素材)
│       └── tools/               生成配图的脚本(跨平台)
│
├── packages/                    ← 鸿蒙专用的 Dart 包
│   ├── file_picker_ohos/        file_picker 的鸿蒙实现(导入/插照片/另存为/选目录)
│   └── stow_secure/             stow_secure 的鸿蒙实现(Nextcloud 凭据存储)
│
├── patches/
│   ├── ohos/                    构建前对 pub cache 的修补(见其 README.md)
│   └── upstream/                ★ 对上游文件的改动,一共 6 个补丁
│
├── scripts/                     ← 构建入口
│   ├── build_ohos.sh            Linux / macOS
│   ├── build_ohos.ps1           Windows
│   ├── apply_upstream_patches.sh   打/撤上游补丁
│   └── apply_upstream_patches.ps1
│
└── toolchain/                   ← 主机侧工具链(SDK 修补、AOT、签名、装机)
    ├── common.sh                公共路径解析(所有脚本都 source 它)
    ├── env.sh / env.ps1         环境变量
    ├── prepare_signing.sh       签名材料准备
    ├── setup_ohos_aot.sh        AOT 打通
    ├── install_on_device.sh     装到平板
    ├── dist/                    给终端用户的安装脚本
    └── windows/                 Windows 版的等价实现
```

仓库里还有**一个**目录留在外面:`ohos/`(鸿蒙工程骨架)。
这是 Flutter-OH 的硬性要求 —— `flutter_tools` 里写死了工程根目录:

```dart
// flutter/packages/flutter_tools/lib/src/project.dart:1317
Directory get editableHostAppDirectory => parent.directory.childDirectory('ohos');
```

所以 `ohos/` 必须在 `<工程根>/ohos/`,挪不动。除此之外的所有东西都在 `harmony/` 里。

---

## 2. 改动了什么

### 2.1 上游文件:**源码一个字节都没改**

仓库里上游 Saber 的**源码**保持原样。对它们的改动全部变成了**补丁**,
放在 `harmony/patches/upstream/`,构建时自动打上:

```bash
bash harmony/scripts/apply_upstream_patches.sh            # 打(幂等)
bash harmony/scripts/apply_upstream_patches.sh --reverse  # 撤,回到纯上游
bash harmony/scripts/apply_upstream_patches.sh --check    # 只看状态
```

| 补丁 | 上游文件 | 为什么必须改 | 改了什么 |
|---|---|---|---|
| `0001-pubspec-add-file-picker-ohos` | `pubspec.yaml` | `file_picker` 没有鸿蒙实现,导入/插照片/另存为全都用不了 | 加一条 `file_picker_ohos` 依赖(path 指向 `harmony/packages/file_picker_ohos`)。**必须写在 `dependencies` 而不是 `dependency_overrides`** —— `flutter_tools` 只从「应用声明的依赖」出发遍历依赖图来发现插件 |
| `0002-lib-add-is-open-harmony` | `lib/data/is_open_harmony.dart` | 需要一个「当前是不是鸿蒙」的判断 | **新增文件**(上游没有这个文件)。比较 `defaultTargetPlatform.name == 'ohos'`,这样 Android / 桌面端编译不会因为 `TargetPlatform.ohos` 这个上游不存在的成员而失败 |
| `0003-lib-file-manager-datadir-recovery` | `lib/data/file_manager/file_manager.dart` | 鸿蒙上「自定义数据目录」的授权只在本次会话内有效 | 应用启动时检查该目录是否还能读,读不到就回退到默认目录。没有这个兜底的话,重启后每篇笔记都会变成 `PathAccessException`,连设置里的入口都点不开 |
| `0004-lib-toolbar-save-icon` | `lib/components/toolbar/toolbar.dart` | `share_plus` 没有鸿蒙实现,那个按钮实际是「另存为」 | 鸿蒙上换用「另存为」图标,免得界面上看着像能分享 |
| `0005-lib-settings-hide-open-folder` | `lib/pages/home/settings.dart` | 两个设置项在鸿蒙上用不了 | ①隐藏「打开 Saber 文件夹」:`dart:io` 的 `Platform.isLinux` 在鸿蒙上为真(鸿蒙是 Linux 内核),但系统里没有 `xdg-open`;②隐藏「自定义数据目录」:授权不持久,搬走就再也搬不回来 |

**唯一直接改动的上游文件是 `.gitignore`** —— 加了两行,只忽略我们自己的产物
(`/pubspec_overrides.yaml` 与 `/saber-ohos-kit/`)。之所以不做成补丁:这两条规则
必须在文件**存在之前**就生效,否则一次 `git add -A` 就可能把根目录的
`pubspec_overrides.yaml` 提交上去 —— 那会让上游 CI(以及任何克隆了这个仓库的人)
都被迫拉取 gitcode 上的鸿蒙分支插件。

> **为什么用补丁而不是直接改文件?**
> `git diff <上游基线>` 只会看到**新增**和上面那两行 `.gitignore`,
> 不会看到「把上游改坏的地方」;
> 合并上游主干时,冲突面只剩这 5 个补丁;想退回纯上游,一条命令。
>
> 打完补丁后工作树里那 5 个文件会显示为 modified —— 这是正常的,
> 它们不会被提交进仓库(仓库里存的是补丁)。

### 2.2 新增内容(全部在 `harmony/` 与 `ohos/` 里)

| 类别 | 位置 | 说明 |
|---|---|---|
| 鸿蒙工程 | `ohos/` | `flutter create --platforms ohos` 生成的骨架,含签名配置 |
| 鸿蒙插件 | `harmony/packages/file_picker_ohos/` | `file_picker` 的鸿蒙实现:federated plugin(`implements: file_picker`),原生侧直接用鸿蒙的 `DocumentViewPicker` / `PhotoViewPicker` |
| 鸿蒙插件 | `harmony/packages/stow_secure/` | `stow_secure` 的鸿蒙实现(底层 `shared_preferences`),替代没有鸿蒙实现的 `flutter_secure_storage` |
| 依赖补丁 | `harmony/patches/ohos/` | 构建前改 pub cache:①给穷尽的 `TargetPlatform` switch 补 `ohos` 分支;②跳过 `super_native_extensions` 的 Rust 交叉编译;③跳过 `pdfium_dart` 的预编译 pdfium 下载;④`window_manager` 缺原生实现时静默降级;⑤`url_launcher_ohos` 没有内嵌浏览器页面时退回系统浏览器 |
| 工具链 | `harmony/toolchain/` | SDK 声明树同步、API 22/24 回补、引擎 HAR 的 API 版本对齐、AOT 打通、签名材料生成、装机 |
| 构建脚本 | `harmony/scripts/` | 一条命令出包(见下) |
| 文档 | `harmony/docs/` | 完整指南 + Windows 本机版 + **用户使用说明书** |
| 配图工具 | `harmony/docs/manual/tools/` | 生成说明书标注图的脚本,跨平台 |

### 2.3 刻意**没有**提交的东西

| 文件 | 原因 |
|---|---|
| `ohos/build-profile.json5` | 里面有 hvigor 用的**加密签名密码**(和你的密钥库绑定)。仓库里存的是空密码模板,构建时由 `prepare_signing` 写入 |
| `ohos/signing/` | 私钥 / 证书 / profile —— 你的签名身份,泄露等于任何人都能冒充你的应用 |
| 根目录 `pubspec_overrides.yaml` | 依赖覆盖的本地产物(本体在 `harmony/toolchain/pubspec_overrides.yaml`)。提交它会让**与鸿蒙无关的构建**也被迫拉取 gitcode 上的鸿蒙分支插件 |
| `pubspec.lock` | 同上 —— 仓库约定 committed lock 记录 **pub.dev 上游的解析结果**;本地的漂移是依赖覆盖工作流的产物 |
| `linux/ macos/ windows/` 下的生成文件 | 只有换行符差异,纯噪音 |

---

## 3. 怎么编译

### 3.1 需要什么

| 组件 | 版本 | 备注 |
|---|---|---|
| Flutter | [Flutter-OH](https://gitcode.com/oh-flutter/flutter_flutter) `3.47.9-ohos-1.0.0` | **不是官方 Flutter** —— 官方版没有 OHOS 平台支持 |
| 鸿蒙 SDK | HarmonyOS **6.0.1(API 21)** | DevEco command-line-tools 6.0.1.251 |
| 构建工具 | ohpm 5.1.3 + hvigor 5.18.5 | command-line-tools 自带 |
| JDK | 17 | 脚本会自动找 |

详细的目录布局、环境变量、SDK 下载:[harmony/docs/ohos.md](docs/ohos.md)。

### 3.2 Linux / macOS

```bash
source harmony/toolchain/env.sh          # 导出 FLUTTER_ROOT / OHOS_SDK_HOME / PATH
bash harmony/toolchain/saber-harmony.sh setup    # 准备 SDK(声明树同步 + API 回补 + AOT 打通)
bash harmony/scripts/build_ohos.sh                # 构建 release 包
bash harmony/scripts/build_ohos.sh --debug        # 首次建议 --debug,报错信息更全
```

### 3.3 Windows(本机,不需要 Linux 构建机)

```powershell
. .\harmony\toolchain\env.ps1
powershell -File harmony\scripts\build_ohos.ps1              # release
powershell -File harmony\scripts\build_ohos.ps1 -Mode debug
```

细节见 [harmony/docs/BUILD-LOCAL.md](docs/BUILD-LOCAL.md)。

### 3.4 构建脚本做了什么

`build_ohos.sh` / `build_ohos.ps1` 的六个步骤:

| 步骤 | 做什么 | 为什么是这个顺序 |
|---|---|---|
| 0 | 打上游补丁 | `pubspec.yaml` 的补丁必须在 `pub get` 之前,否则鸿蒙侧的文件选择器插件不会被注册 |
| 1 | 把 `pubspec_overrides.yaml` 复制到仓库根 | pub 只认根目录那份 |
| 2 | `flutter pub get` | |
| 3 | 打 pub cache 的依赖补丁 | **必须在 `pub get` 之后** —— pub get 会重新解压/替换 cache 里的包目录,顺序反了补丁就被覆盖 |
| 4 | 准备签名材料 + 写 `build-profile.json5` | |
| 5 | `flutter build hap --<mode> --dart-define=FLUTTER_OHOS_AOT_BUILD=true` | 这个 define 强制把 `defaultTargetPlatform` 判成 `ohos`(AOT 用 `--target-os=linux` 编译,否则 `Platform.isLinux` 会被折叠成 true,框架会把鸿蒙误判成桌面 Linux) |

Windows 侧第 0 步之前还会跑一次 `harmony/toolchain/windows/setup_sdk.ps1`,
把 SDK 侧的修补(引擎 HAR 的 API 版本、API 22/24 声明回补、`const_finder` 快照的
SDK hash 对齐)集中做完 —— 幂等,每次构建都跑,因为 `flutter precache` 会重新下载
引擎工件,把那些补丁冲掉。

---

## 4. 怎么部署到鸿蒙设备

### 4.1 无线调试(推荐)

```bash
hdc tconn <设备IP>:<无线调试端口>     # 第一次会提示授权,再连一次即可
hdc install -r build/ohos/hap/entry-default-signed.hap
hdc shell aa start -a EntryAbility -b com.sabernotes.saber
```

也可以直接用现成的脚本:

```bash
bash harmony/toolchain/install_on_device.sh      # Linux / macOS
harmony\toolchain\dist\install-harmony.bat        # Windows
```

### 4.2 签名

| 材料来源 | 能装到哪 |
|---|---|
| **AGC(华为账号)签发的调试 Profile** | ✅ 能装到 Profile 白名单里的 HarmonyOS 真机(如 MatePad Edge) |
| SDK 自带的 OpenHarmony 社区证书 | ❌ 只能装到 OpenHarmony 设备与 DevEco 模拟器;真机报 `code:9568257 (fail to verify pkcs7 file)` |

生成材料的脚本都在 `harmony/toolchain/` 下(`gen_csr.sh`、`make_signing_profile.py`、
`make_debug_profile.py`、`use_agc_signing.sh`),详见
[harmony/docs/ohos.md](docs/ohos.md](docs/ohos.md) §4。

### 4.3 已知限制

| 功能 | 状态 |
|---|---|
| 手写 / 笔型 / 背景纸样 / 分页笔记 | ✅ 可用 |
| 导入笔记(`.sba`)、插入照片、导出另存为、选择文件夹 | ✅ 可用(`harmony/packages/file_picker_ohos/`) |
| 导出 `.sba` | ✅ 可用 |
| 分享到其它应用 | ⚠️ 走的是「另存为」(系统保存对话框),`share_plus` 没有鸿蒙实现 |
| Nextcloud 同步 | ⚠️ 登录跳**系统浏览器**;应用内同步走 WebDAV,可用 |
| **PDF 预览 / 导入** | ❌ **不可用** —— `pdfium_dart` 的 build hook 在鸿蒙上没有对应产物,被我们的补丁跳过了 |
| 后台同步 | ❌ 不可用(鸿蒙的后台任务限制) |
| 导入的笔记在首页没有缩略图 | ⚠️ 预览图是旁挂文件 `<笔记>.sbn2.p`,只在**编辑器保存**时生成;导入的笔记打开随便画一笔保存一下就有了(上游既有行为,不是鸿蒙引入的) |

---

## 5. 怎么合并回上游主干

上游 Saber 的文件在仓库里是原样的,所以合并很直接:

```bash
git fetch upstream
git rebase upstream/main          # 或 git merge upstream/main
```

可能需要重放的只有 `harmony/patches/upstream/` 里那 5 个补丁
(上游改了对应的文件时,补丁会打不上,重新 `git apply` 解决一下即可)。

`.gitignore` 末尾那两行如果上游也改了同一处,手动合一下就行(都是纯忽略规则)。

如果想把鸿蒙适配整体从上游分支里摘掉:

```bash
git rm -r harmony ohos             # 删掉两个新增目录
git rm -f harmony/patches/upstream/*.patch   # 补丁也一并删掉
# 此时工作树与上游基线完全一致(除了 pubspec.lock 这个依赖覆盖的产物)
```

拆分策略、哪些东西适合做成上游 PR、哪些不适合,见
[harmony/docs/ohos-upstream.md](docs/ohos-upstream.md)。

---

## 6. 给上游提 PR 的建议

| 改动 | 适合提 PR 吗 |
|---|---|
| `0002` 新增 `is_open_harmony.dart` | ✅ 可以 —— 纯新增文件,零冲突 |
| `0003` `file_manager` 的目录失联兜底 | ✅ 可以 —— 逻辑本身与平台无关,只是目前只在鸿蒙上生效 |
| `0004` `0005` 的图标与设置项 | ⚠️ 需要上游接受「按平台隐藏某个设置项」这种写法 |
| `0001` `file_picker_ohos` 依赖 | ❌ 不适合 —— 依赖一个仓库内的 path 包,上游不会接受 |
| `.gitignore` 的两行 | ❌ 不适合(但也无害) |
| `harmony/toolchain/` 整包 | ❌ 不适合 —— 高度依赖具体机器的目录布局与 Flutter-OH fork,维护成本大 |
| `harmony/docs/manual/` 用户说明书 | ✅ 可以 —— 纯文档 |

---

## 7. 排障速查

| 症状 | 原因与解法 |
|---|---|
| 白屏 + `MissingPlatformDirectoryException` | release 构建缺 `--dart-define=FLUTTER_OHOS_AOT_BUILD=true`,`Platform.isLinux` 被折叠成 true,注册成了 Linux 桌面插件。用 `harmony/scripts/build_ohos.sh`(已内置) |
| `The type 'TargetPlatform' is not exhaustively matched ... 'TargetPlatform.ohos'` | 依赖补丁没打上,或者打完补丁又跑了 `pub get`。步骤 3 必须在步骤 2 之后 |
| `ConstFinder failure: Can't load Kernel binary: Invalid SDK hash.` | `const_finder` 快照是用引擎对应的 Dart SDK 构建的,和主机 SDK 的 SDK hash 对不上。`harmony/toolchain/windows/align_const_finder.py` 会对齐它(挂在 `setup_sdk.ps1` 第 5 步) |
| `spawn java ENOENT` | 找不到 JDK。`harmony/toolchain/env.sh` / `env.ps1` 会自动找,也可以自己设 `JAVA_HOME` |
| `No Hmos SDK found` | 命令行工具 + 独立 SDK 的混合布局下的探测告警,依赖其实已经解析成功。构建脚本会忽略它 |
| 装到真机报 `9568257` | 签名用的不是华为账号签发的材料,见 §4.2 |
| 装到真机报 `9568393` | Profile 和设备不匹配,重新生成带该设备 UDID 的 Profile |
| `git apply` 打不上补丁 | 上游改了对应的文件。`bash harmony/scripts/apply_upstream_patches.sh` 会告诉你哪个补丁冲突 |
