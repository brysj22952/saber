# Saber 鸿蒙版 · 真机部署记录

> 2026-11-09 首次成功部署到 HUAWEI MatePad Edge

## 代码位置

| 项 | 值 |
|---|---|
| 上游仓库 | https://github.com/saber-notes/saber |
| 你的 fork | https://github.com/brysj22952/saber |
| 适配分支 | `feature/ohos-harmonyos` |
| 我们的改动 | `harmony/`(全部适配内容)+ `ohos/`(Flutter-OH 要求的工程骨架) |
| 指南 | [`harmony/docs/ohos.md`](ohos.md)(完整说明)、[`harmony/toolchain/README.md`](../toolchain/README.md)(工具链) |
| 上游合并策略 | [`harmony/docs/ohos-upstream.md`](ohos-upstream.md) |

## 设备

| 项 | 值 |
|---|---|
| 型号 | `QXS-W20` |
| 名称 | HUAWEI MatePad Edge |
| 系统 | HarmonyOS `7.0.0.111(SP16C00E111R6P5)` |
| API | `26` |
| 连接 | 无线调试,`hdc tconn <设备IP>:<端口>`(端口每次重开都变) |

> 设备 UDID、AGC 项目 ID / APP ID 之类的标识**不写在这里** —— 它们属于你的
> 账号与设备,仓库是公开的。具体值看本地的 `ohos/signing/`(已 gitignore)。

## AGC 资源

| 项 | 值 |
|---|---|
| 应用名称 | Saber |
| 包名 | `com.sabernotes.saber` |
| 调试证书 | `saber_debug_2026`(由本地 `app.csr` 签发) |
| 调试 Profile | `saber_debug_profile` |

签名材料(password 与 alias 由 `harmony/toolchain/prepare_signing.py` 的默认值决定):

```
ohos/signing/
├── app.p12          本地生成的密钥库
├── app.csr          证书签名请求
├── app.cer          AGC 下载的证书链(root→CA→leaf)
├── app-cert.pem     重排成 leaf→CA→leaf…(certpath 用)
├── app.p7b          AGC 下载的调试 Profile
└── material/        密码加解密用的密钥材料
```

> 整个 `ohos/signing/` 目录在 `.gitignore` 里 —— 泄露等于任何人都能冒充你的应用签名。

## 验证结果

```
$ hdc install -r entry-default-signed.hap
install bundle successfully.

$ hdc shell aa start -a EntryAbility -b com.sabernotes.saber
start ability successfully.
```

界面渲染正常,点击「+」能展开「导入笔记 / 新建笔记」,新建笔记能打开
完整的手写编辑器工具栏,无 Dart 异常、无崩溃。

## 复现命令

```bash
# 1. 连设备(无线调试,端口看平板屏幕)
hdc tconn <设备IP>:<端口>
hdc list targets -v          # 应为 Connected

# 2. 构建(需要 ohos/signing/ 下的 AGC 材料)
bash harmony/scripts/build_ohos.sh
# 或者用顶层入口:bash harmony/toolchain/saber-harmony.sh build

# 3. 安装 + 启动
bash harmony/toolchain/install_on_device.sh
```

---

## 2026-11-09 后续:release(AOT)构建打通

最初只有 debug 包,手写明显"不跟手"。排查后发现是 debug JIT + 交互期
掉帧(约每 100ms 一次 `ReportJANKEvent`);渲染后端本身没问题
(Impeller + Vulkan 正常工作)。

### 结果对比

| 指标 | debug | release |
|---|---|---|
| 包体积 | 246 MB | 39 MB |
| 交互掉帧 | 每 100ms 一次 JANK | **0** |
| 冷启后稳定性 | 正常 | 正常 |

### 打通过程(详见 [`harmony/docs/ohos.md`](ohos.md) §4.9)

Linux 主机上 release 构建默认不可用,四层障碍逐个绕过:

1. frontend_server 的 `--target-os` 白名单无 `ohos`
   → 补丁:传 `linux`
2. 传 `linux` 导致 `Platform.isLinux` 被常量折叠为 true
   → 补丁:框架加 `FLUTTER_OHOS_AOT_BUILD` 开关
3. 插件注册表同样先判 `isLinux`
   → 补丁:ohos 分支提到最前
4. 缺 kernel 138 的 linux `gen_snapshot`
   → 用 `3.47.4-ohos-1.0.4` 的 Windows 版 + Wine

一条命令装好全部前置:`bash harmony/toolchain/setup_ohos_aot.sh`

### 坑:白屏的两级递进

- 第一级:`MissingPlatformDirectoryException`
  → 插件注册成了 `path_provider_linux`
- 第二级:`MissingPluginException ... window_manager`
  → `main.dart` 的 `Platform.isLinux` 判断成立,调了桌面插件

两个都修掉之后才正常渲染。

### 剩余已知问题

- PDFium(鸿蒙无对应二进制),在后台 worker 中被捕获,不影响主流程;
  代价是鸿蒙版**不支持 PDF 预览/导入**。
- 导入的笔记在首页没有缩略图 —— 预览图是旁挂文件 `<笔记>.sbn2.p`,
  只在编辑器保存时生成,打开笔记随便画一笔保存一下就有了(上游既有行为)。

---

## 2026-11-12 后续:Windows 本机构建打通

原先只能在 Seoul 那台 Linux 机器上构建,现在本机(Win11 ARM 虚机)也能出包,
详见 [`harmony/docs/BUILD-LOCAL.md`](BUILD-LOCAL.md)。

| | Linux(Seoul) | Windows(本机) |
|---|---|---|
| AOT 快照器 | Windows 版 + Wine | 原生 exe(SDK 自己拉) |
| 构建耗时 | 约 20 分钟 | 约 10 分钟 |
| 产物 | 39 MB | 37.9 MB |

---

## 2026-11-14 后续:目录重组 + 重构

- 全部适配内容收进 `harmony/`,上游源码保持原样(见 [`harmony/README.md`](../README.md))
- 5 处对上游的改动改成了补丁(`harmony/patches/upstream/`),便于以后合并回上游
- 消除了 bash / Python 双实现,逻辑只剩一份

---

## 2026-11-15 后续:装到第二台设备(手机)

| 项 | 值 |
|---|---|
| 设备 | HUAWEI Pura X Max 典藏版(`HOP-AL10`) |
| 系统 | OpenHarmony 7.0.0.111(SP12C00E111R4P4),API 26 |
| 连接 | 无线调试,`192.168.1.40:45059`(端口每次重开都变) |
| 签名 | 沿用平板那套 AGC 调试证书,只是把 Profile 的设备白名单扩到两台 |

> 设备 UDID 属于你的设备,不入库 —— 用 `hdc shell bm get --udid` 现取。

### 踩到的坑:profile 的设备白名单

首次安装报:

```
code:9568423  the device is unauthorized,
make sure the UDID of your device is configured in the signing profile
```

调试 Profile 里的 `debug-info.device-ids` 只绑了平板那一台。
鸿蒙强制验签,**没有旁路**:`hdc install` 没有 `--no-check-signature`,
设备端 `bm install` 也没有跳过校验的开关。

解法 —— 不用重新申请证书,直接改现有 Profile 的设备白名单:

1. AGC「ID、证书和Profile → 设备」→ 添加设备(UDID + 设备类型)
2. AGC「Profile」→ `saber_debug_profile` → **编辑设备** → 勾选新设备 → 确认修改
   (提示 *profile内容已更新,请重新下载并更新软件包*)
3. 同一行「下载」→ 新的 `app.p7b`(白名单变成两台)
4. `hap-sign-tool sign-app` 重签 hvigor 留下的未签名包(秒级,不用重新构建)
5. `hdc install -r` + `aa start`

完整步骤见 [`harmony/docs/ohos.md`](../docs/ohos.md) §4.5.1。

### 结果

```
install bundle successfully.
start ability successfully.
```

界面正常渲染(首页「最近笔记」+「欢迎使用 Saber」),
日志里 `FilePickerPlugin` / `SharedPreferencesOhosPlugin` / `PathProviderPlugin`
等鸿蒙插件都注册成功,无 Dart 异常。

![Saber 运行在 Pura X Max 上](manual/shots/17-harmonyos-phone-home.jpeg)


---

## 2026-11-15 后续:上架华为应用市场 · 阶段 0–1(环境自检 + 发布证书/Profile)

按 [`harmony/docs/RELEASE-TO-APPGALLERY.md`](RELEASE-TO-APPGALLERY.md) 执行。

### 阶段 0 · 环境自检

| 项 | 结果 |
|---|---|
| 仓库 | `feature/ohos-harmonyos`,与 `fork/feature/ohos-harmonyos` 同步 |
| Flutter-OH SDK | `/root/hzq/saber-ohos/flutter` |
| OpenHarmony SDK | `/root/hzq/saber-ohos/ohos-sdk-root/ohos-sdk` |
| DevEco 命令行工具 | `/root/hzq/saber-ohos/deveco-tools/command-line-tools` |
| 构建产物 | `build/ohos/hap/entry-default-signed.hap`(上一次是 debug 包,阶段 2 会用发布材料重出) |
| 浏览器 CDP | `127.0.0.1:9333` 活着,AGC 控制台已登录华为账号 |

### 阶段 1 · 发布证书 + 发布 Profile

| 项 | 值 |
|---|---|
| 发布证书 | `saber_release_2026`(发布证书,有效期至 2029-11-15) |
| 发布 Profile | `saber_release_profile`(发布类型,无设备白名单) |
| 本地落点 | `ohos/signing/app-release.cer`、`ohos/signing/app-release.p7b`(都在 `.gitignore` 里) |

**复用了原来的密钥对**,没有重新生成 CSR/密钥 —— 重新生成会让已签发的证书全部作废。
校验方式:

- `app-release.cer` 是三张证书组成的链(root → CA → leaf),
  **leaf 的公钥指纹与 `app.csr` 里的一致** ⇒ 证书确实签给了我们这把钥匙;
- `app-release.p7b` 解出来 `type == release`、`bundle-name == com.sabernotes.saber`、
  `distribution-certificate` 的公钥指纹与上面那张 leaf 一致;
- `devices` 字段为空 —— 发布 Profile 没有设备白名单,符合预期。

### 新增工具:`harmony/toolchain/agc/agc_upload.py`

上架流程要在控制台上传 CSR / 证书链,`agc_console.py` 里没有「选文件」的能力,
所以新加了一个薄脚本(复用 `agc_console.py` 的 CDP 客户端,不改它的既有逻辑):

```bash
python3 harmony/toolchain/agc/agc_upload.py ohos/signing/app.csr --scope iframe --index 0
```

**踩到的坑**:nodeId 必须用 `DOM.querySelector` 现查。
`DOM.getDocument(depth=-1, pierce=True)` 返回的 nodeId 是「过期」的,
直接拿去 `DOM.setFileInputFiles` 会报 `Could not find node with given id`;
用 querySelector 查出来的 nodeId 才能用,而且浏览器会自动派发 change 事件。


---

## 2026-11-15 后续:上架华为应用市场 · 阶段 2–4(发布包重建 + 上架材料 + 上传)

接着上一节(阶段 0–1)往下做。本节只写**结论和坑**,不写任何签名材料和 AGC 标识。

### 阶段 2 · 用发布材料重新构建

**结论**:商店要的是 **`.app` 包**(整包),不是 `.hap`。而且 `.app` **不能靠把 `.hap` 改名得到** ——
改名的包 AGC 直接拒收,报 `amp.appPackage.996 软件包解析失败`。

正确做法是让 hvigor 走 `assembleApp` 任务,由 Flutter 工具链生成 `pack.info` + 内层 HAP 并整体签名:

```bash
flutter build app --release --build-name=1.0.0 --build-number=1000000 \
  --dart-define=FLUTTER_OHOS_AOT_BUILD=true
```

产物:`ohos/build/outputs/default/ohos-default-signed.app`(约 17MB)。
zip 内部结构 = `pack.info` + `entry-default.hap`(约 39MB),`pack.info` 里:

| 字段 | 值 |
|---|---|
| bundleName | `com.sabernotes.saber` |
| bundleType | `app` |
| version | code `1000000` / name `1.0.0` |
| modules[0].deviceType | `default` / `tablet` / `2in1` |
| apiVersion | compatible `21`,target `21`,releaseType `Release` |
| packages[0].name | `entry-default`(与内层 HAP 文件名一致 ✓) |

**验收(签名)**:用 `hap-sign-tool.jar verify-app` 解出包内 profile,`type == release`,
且与 `ohos/signing/app-release.p7b` **逐字节一致**;`devices` 字段为空(无设备白名单)✓。

### 阶段 3 · 上架材料

| 材料 | 落地情况 |
|---|---|
| 应用图标 | `assets/icon/icon.png`(1024×1024 RGBA PNG,35KB)✓ |
| 应用截图 | `harmony/docs/store-screenshots/{home,fabmenu,editor,whiteboard}.png`,4 张 **2353×1324(严格 16:9)** ✓ |
| 截图生成 | 新增 `harmony/toolchain/capture_store_screenshots.py`(见下)✓ |
| 隐私政策 | `harmony/docs/privacy-policy.html` → `https://brysj22952.github.io/saber/privacy-policy.html`(HTTP 200)✓ |
| 商店文案 | 新增 `harmony/docs/store-listing.md`(简介/介绍/权限说明/开源声明/更新说明)✓ |
| 应用分类 | 应用 → **工具**,主标签 **备忘录**,附加标签 笔记 ✓ |
| 年龄分级 | 中国区 3+ / 巴西 所有年龄段 / 其他区域 3+(问卷全选「否」推导得出)✓ |

**截图尺寸硬约束**:3~10 张、**宽高比必须 16:9**、长边 ≥1920。
第一版拍成 2090×1324(比例 1.58)被拒,报「图片尺寸不符合要求,请重新上传」,
改成把应用窗口调到内容区正好 16:9 再截,才通过。

**新增工具:`harmony/toolchain/capture_store_screenshots.py`**
用 `hdc` + `uitest` 在平板上自动拍 4 张商店图(首页 / 新建菜单 / 编辑器两笔 / 白板),
脚本会先把浮动窗口宽度调成 `(高-70)*16/9`(标题栏 70px),再逐张截图、校验前台窗口、
最后用 PIL 裁成精确 16:9。截图前会清空笔记区,保证画面里**没有任何个人笔记**。

### 阶段 4 · 上传 + 提交审核

| 项 | 状态 |
|---|---|
| 上传 `.app` | ✓「ohos-default-signed.app 上传成功」 |
| 版本行 | `1.0.0（1000000）`,合法性 **已达标** ✓ |
| 版本表单 | 应用介绍/一句话简介/隐私政策网址/隐私权利/是否涉及个人信息收集=否/AI 服务=不涉及/APP 类型=单机/主办单位=个人+与账号主体一致/上架时间=审核通过立即上架/4 张截图/年龄分级/应用负责人(手机+短信验证+邮箱+姓名) —— 全部填好 ✓ |
| **提交审核** | ✓ **已提交**,版本状态 = **预审中**(2026-11-15) |

提交时的「发布信息确认」弹窗回顾:软件版本号 `1.0.0(1000000)`、默认语言 简体中文、
发布国家或地区「所有国家或地区」(200 个)、软件包加密 = 加密 ✓。

提交后版本页顶部变成「**1.0.0 新版本 - 预审中**」,并提示:
*「预审:正式审核前的自动化检测阶段,预审通过后会自动提交至应用市场审核团队;
预审时长通常会在 30-40 分钟左右」*——即预审不通过 = 提交失败,要看检测报告。

### 阶段 5 · 轮询审核(进行中)

```bash
# 每次查状态
python3 harmony/toolchain/agc/agc_version_status.py
```

**2026-11-15 18:09:预审通过**。版本历史记录里的时间线:
`准备提交 → 预审中(18:07) → **正在审核**(18:09)`,即已进应用市场审核团队队列 ✓。

AGC 给的两条提示:
* 「如果不通过,您的应用发布申请会在几小时内自动驳回,您可以马上启动问题修复」;
* 「请您关注 APP 个人信息保护合规性检测结果,并及时进行整改」(异步检测,结果在控制台消息中心)。

接下来等华为侧人工审核(通常 1–7 个工作日)。状态变化时用上面那条命令查,
并把结论写进 [`APP-RELEASE-RECORD.md`](APP-RELEASE-RECORD.md)。

### 等待审核期间的补充验证

- **提交包与商店文案一致**:解开 `ohos-default-signed.app` → 内层 HAP 的 `module.json`,
  `requestPermissions` 只有 `ohos.permission.INTERNET` 一项 ✓,
  与商店「权限说明」文案逐条对得上 ✓(权限说明与实际不符是最常见的驳回理由之一)。
- **商店素材合规**:4 张截图全部 2353×1324、严格 16:9、PNG ✓,满足「3~10 张 / 长边≥1920 / 比例 16:9」。
- **隐私政策线上与仓库一致**:`gh-pages` 分支里的 `privacy-policy.html` 与
  `https://brysj22952.github.io/saber/privacy-policy.html` 的 md5 相同 ✓,
  审核员看到的就是审过的那一份 ✓。
- **签名材料确实没进仓库**(用 git 反查):
  `git ls-files ohos/signing/` 输出为空 ✓,`.p12/.cer/.p7b/.csr` 全部命中 `ohos/.gitignore` 的 `/signing/` 规则 ✓;
  发布证书有效期到 2049 年 ✓(以后签新版本不受影响)。
- **真机冒烟**(审核期间在平板上跑了一次,只启动自己的 App,没动别的应用):
  `aa start -a EntryAbility -b com.sabernotes.saber` → 「start ability successfully」,
  进程存活 ✓,`XComFlutterEngine` 正常起来 ✓,hilog 里**没有 FATAL/崩溃** ✓
  (只有 `FeatureManager get config failed`、`APP_NAP not in system exemption list` 这类常规告警;
  后者是因为 App 没在前台 ✓)。
  > 注:平板上装的是**调试包**(与提交包的 Dart 代码一致,只差 AOT 与签名);
  > **不要**在有个人笔记的设备上装发布包 —— 调试包与发布包签名不同,同包名只能先卸载,
  > 卸载会连带删掉本地笔记 ✓。

### 这一阶段踩到的坑(AGC 控制台是 Vue SPA,只能靠 CDP 驱动)

1. **`.app` 不能改名**:`.hap` 改名成 `.app` → `996 软件包解析失败`。见阶段 2 ✓。
2. **应用信息页有「手机 / PC/2in1」两个设备页签**,图标、名称、分类、标签**两个页签都要填**。
   只填手机页签时,版本页顶部会一直挂「您的应用信息页面还有必填信息未填写」✓。
3. **年龄分级是问卷,不是表格**:面板里的分级表格一开始永远是空的(它只展示**已填过**的评级)。
   正确路径是「设置」→「填写问卷」→ 11 道题逐题作答 → 「验证」→「提交」→ 再答「是否仅面向儿童=否」。
   任一道题选了「否」都会展开子问题,子问题不答就卡在红标 ✓。
4. **el-cascader(应用分类)不吃 JS 合成事件**:`el.click()` / `dispatchEvent` 都弹不出下拉,
   必须用 CDP `Input.dispatchMouseEvent` 发**真实鼠标事件**,且坐标要用**顶层文档坐标**
   (`iframeRect.left + 元素在 iframe 内的 x`)✓。
5. **上传文件后 DOM 会重建**,旧的 nodeId 立刻失效 ⇒ 每传一张图/图标都要重新
   `DOM.querySelectorAll` 取 nodeId,否则文件会落到错误的槽位或直接丢失 ✓。
6. **「保存草稿」会清空「发布版本」里选好的包** ⇒ 提交审核前必须**最后再选一次**包,中间不要存草稿 ✓。
7. **选包后「发布版本」那一栏仍显示「去选择」按钮**(v-if 占位是空的),这是**假象**:
   表单里其实已经选好了 —— 点「提交审核」后弹出的「发布信息确认」里会显示
   `软件版本号:1.0.0(1000000)` ✓。不要被这个按钮骗去反复选包 ✓。
8. **版本选取弹窗里没有 radio 列**,点「文件名称」那一格才会选中(下方会展开该包的
   包名/默认名/SHA256 等详情),再点「确认选取」✓。
9. **版本在审核中时「去选择」按钮是禁用的**(选不了包)—— 也就是说审核期间不会误改包 ✓;
   同理「保存草稿」也别再点,会把已提交的版本数据搅乱 ✓。
10. **软件包管理里会躺着之前上传失败的包**:`saber-release.app`(2026-11-15 16:50,
   合法性「不通过(996)」)—— 那次是把 `.hap` 改名成 `.app` 的失败尝试。
    它不影响上架(状态是「不可选」),下次需要清理时在控制台删掉即可 ✓。
11. **Python 侧 CDP 小坑**:`Runtime.evaluate` 不带 `contextId` 会落在**顶层文档**而不是 iframe,
   取 iframe 里的元素要显式传 `contextId`;`Runtime.evaluate` 想要 DOM 节点引用要 `returnByValue=False` ✓。
12. **iframe 路由切换后隔离世界会被重建**,`agc_console.Frame` 里缓存的 `ctx` 失效,
   `Runtime.evaluate` 会静默返回空 —— 切页面后要**重新建一个 `Frame`** 再读 ✓。
13. **`agc_console.py` 连的是 `/json/list` 的第一个标签页**。控制台里若同时开着别的应用页面,
    轮询脚本会读到**别的应用**的状态 —— 所以 `agc_version_status.py` 里加了
    「页面上必须出现 `com.sabernotes.saber` 才作数」的校验 ✓。
14. **控制台会话久了会被重定向到「华为 APIs 使用协议」页**(iframe 里不再是业务页),
    这时点侧边栏「版本/升级」是点不动的。`agc_version_status.py` 的兜底是
    `Page.reload` —— SPA 会按 hash 回到原来的路由 ✓(实测 3 次重试 + 重载即可恢复 ✓)。

---

## 阶段 0–5 总结(2026-11-15)

| 项 | 结论 |
|---|---|
| 是否上架成功 | **尚未上架** —— 1.0.0 提交后于 2026-11-16 15:23 **被驳回**;整改后 **1.0.1 (1000001)** 于 2026-11-16 20:39 重新提交,当前 **预审中** ✓ |
| 审核结论 | 第 1 轮 ❌ 未通过(8 条意见,已逐条整改);第 2 轮预审中,待人工审核 |
| 提交物 | `saber-harmony-1.0.1.app`(16.54 MB,发布证书 + 发布 Profile,targetSdk 6.0.1(21),versionCode 1000001) |
| 商店素材 | 图标 1024×1024 **不透明** ✓ / 4 张 2353×1324 严格 16:9 截图 ✓ / 隐私政策 GitHub Pages ✓ / 分类「工具」+ 标签「备忘录」✓ / 年龄分级 中国区 3+·巴西 AL·其他区域 3+ ✓ |
| 开源声明 | 应用介绍里已写明:开源项目、为 HarmonyOS 设备编译适配、官方仓库 `saber-notes/saber` + 本项目仓库 `brysj22952/saber` ✓,许可 GPL-3.0 ✓ |
| 下一步 | ① 等审核结果(轮询脚本 `harmony/toolchain/agc/agc_poll_review.sh`,最长约 7 天);<br>② 若再被驳回 → 按检测报告修 → 重新构建 `.app`(versionCode 递增)→ 重新提交;<br>③ **2027-01-01 前把 targetSdkVersion 升到 `26.0.0`** —— 控制台已提示,从 2027 年起 API 26 才会强制;<br>④ 清理控制台里那个遗留的 `saber-release.app`(不通过(996));<br>⑤ 上架后在应用市场搜「**Saber 手写笔记**」核对商店页与截图展示 ✓ |

---

## 2026-11-16 后续:第 1 轮审核被驳回 → 整改 → 1.0.1 重新提交(2026-11-16 20:36)

### 时间线

| 时间 | 事件 |
|---|---|
| 11-16 15:23 | 第 1 轮审核出报告:**未通过**(8 条意见,5 阻断 + 3 建议),详见 `APP-RELEASE-RECORD.md` |
| 11-16 19:50–20:25 | 三条排查并行做完(PDF 导入 / .sba 预览、版本号 + 图标 + deviceTypes、隐私明示同意),逐条定位根因 |
| 11-16 20:25 | 代码整改完成:10 个新上游补丁(0006–0015)+ 版本号单一来源 + 新图标 |
| 11-16 20:30 | `bash harmony/scripts/build_ohos.sh --release --app` 出 **`1.0.1 (1000001)`** 的 `.app`(17 MB) |
| 11-16 20:36 | 控制台上传新包 → 软件包管理显示 **已达标** ✓ |
| 11-16 20:39 | 版本页「去选择」选中新包 → 「提交审核」→「确认提交」✓ → 状态 **1.0.1 预审中** ✓ |

### 这次踩到的坑(补进上面的经验清单)

15. **版本页里会同时留着旧版本**(1.0.0 准备提交 / 1.0.1 预审中)。
    `agc_version_status.py` 原来用整页文本正则找状态,**会读到旧版本** ✗ →
    改成读顶层文档侧栏的版本列表,取**版本号最大的那条** ✓。
16. **`DOM.setFileInputFiles` 的 nodeId 会失效**:上传对话框每次重新渲染都会重建 DOM,
    `DOM.requestNode` 拿到的 nodeId 紧接着就「Could not find node with given id」。
    **直接传 `objectId` 最稳** ✓(`DOM.setFileInputFiles` 接受 objectId ✓)。
17. **上传对话框必须先选「使用场景」再选文件** —— 顺序反了会提示「请先选择使用场景」✓。
    另外 AGC 里**同名文件不会覆盖旧包**:新包换个名字(`saber-harmony-1.0.1.app`)上传更保险 ✓。
18. **应用信息页的改动不点「保存」就等于没改**:改完名称/图标直接切页签或刷新,改动会丢 ✗。
    两个设备页签(手机 / PC/2in1)各有一份图标,要分别上传 ✓;「保存」按钮在有改动时才可用 ✓。
19. **版本页的「保存草稿」慎用** —— 它会把已选取的软件包清掉 ✗;改完直接「提交审核」即可 ✓。
20. **上游的 golden 测试在这台机器上跑不了**:仓库用的 Flutter SDK 是 OHOS 专用版,
    `flutter test` 会以 `Abi._os: ohos` 去编译 FFI 代码,`flutter_tester` 直接崩
    (`Type IntPtr has no mapping for ABI ... ohos/arm`)。
    所以 `test/goldens/login_page_*.png` **这次没能重新生成** ——
    登录页的界面变了(多了隐私复选框),golden 与上游不一致,
    要在有桌面版 Flutter SDK 的机器上跑 `flutter test --update-goldens` 才能补上 ✓。
    (不影响鸿蒙构建与上架 ✓ —— 商店截图是另外用真机截的 ✓。)
21. **`ohos/build-profile.json5` 是「模板」文件**:仓库里存的是空口令版本,
    `prepare_signing.sh` 构建时会往里写本地密钥库的加密口令 ✗。
    这个文件是**被 git 跟踪的**(`git add -A` 会把口令一起提交 ✗✗),
    每次提交前要 `git checkout -- ohos/build-profile.json5` 还原 ✓。
    同理 `ohos/signing/` 下的 `.p12/.cer/.p7b/.csr` 已被 `.gitignore` 挡住 ✓。

### 这一轮的整改清单(对照审核 8 条)

| 审核意见 | 改法 | 落在哪 |
|---|---|---|
| 图标透明 / 与终端不一致 | 新画不透明图标(1024×1024 RGB),商店与包内同一张 | `harmony/assets/app-icon-1024.png` + `ohos/**/media/*.png` |
| 名称雷同 | 「Saber」→「**Saber 手写笔记**」(商店两个页签 + 包内 `app_name`/`EntryAbility_label` + Dart 标题) | `ohos/**/element/string.json`、`lib/main.dart` 等 |
| 主题类型灰屏 | 鸿蒙上隐藏「主题类型」设置项 | 补丁 `0005` |
| 导入 PDF 无响应 | 静默 `return` → 明确 SnackBar 提示 | 补丁 `0006` |
| .sba 无预览 | 导出时把缩略图打进压缩包,导入时还原 | 补丁 `0007` + `0003` |
| 版本号显示错 | `--build-name/--build-number` 与 `--dart-define=APP_VERSION_*` 同源 | 补丁 `0010` + `harmony/scripts/build_ohos.sh` |
| deviceTypes 越界 | `["default","tablet","2in1"]` → `["phone","tablet","2in1"]` | `ohos/entry/src/main/module.json5` |
| 隐私政策未明示同意 | 登录页加默认未勾选的复选框 + 「不同意并退出」,未勾选时登录按钮置灰 | 补丁 `0011` |

### 顺带修的

- 应用内「隐私政策」链接:鸿蒙版改指 **与商店提交同一份** `brysj22952.github.io/saber/privacy-policy.html`
  (原来指向上游 `saber.adil.hanney.org` ✗ —— 审核员从应用内点进去会和商店页对不上 ✗)。
- 版本号收敛成单一来源:`harmony/scripts/build_ohos.sh` 里 `APP_VERSION_NAME`/`APP_VERSION_CODE`
  一处定义,同时喂给包元数据和设置页 ✓,以后不会再漂 ✓。

### 平板(MatePad Edge,10.0.0.4)上的应用被卸掉了 —— 需要时再装回去

- 这次为了做真机冒烟测试,先 `hdc uninstall` 掉了平板上原来那个 **1.37.1/137010** 的调试包,
  想装新的 **1.0.1/1000001** 验证界面,**没装上** ✗:
  - release profile(AGC 发布证书)包:`code:9568322 not trusted app source` —— 发布包本来就不给旁加载 ✗
  - 换成 AGC 的 **调试 profile**(`saber_debug_profile`,白名单里有 2 台设备)重新打的 debug 包:
    同样报 9568322 ✗ —— 平板的 UDID 很可能不在那个 profile 的白名单里(设备重置过?)✗
- **2026-11-16 23:32 已解决并装回平板** ✓:根因是证书链用错(见上面的「证书链用错了」一节),
  修好后 `hdc install` 报 `install bundle successfully` ✓,启动器里应用名已是
  「**Saber 手写笔记**」 ✓。
- 剩下的事:平板有**锁屏密码**,`aa start` 会被系统拒绝(错误码 10106102,
  developer 模式下无法用 hdc 自动解锁),所以界面级自检要等明天解锁后跑:
  ```bash
  python3 harmony/toolchain/verify_device_ui.py --connect
  ```
  它会检查:新名称 ✓ / 版本号 1.0.1+1000001 ✓ / 「主题类型」已隐藏 ✓ /
  登录页的隐私复选框 ✓ / 未勾选时登录按钮禁用 ✓。
- 另外两条路(备选):
  1. 用 `harmony/toolchain/agc/` 从控制台把平板的 UDID 加进调试 profile 的设备列表,
     重新下载 profile 再 `bash harmony/scripts/build_ohos.sh --debug` 打 debug 包安装 ✓;
  2. 或者用「我的应用市场 → 调试」把刚提交的 1.0.1 装到设备上(走 AGC 的可信来源通道 ✓)。
- 商店截图(`harmony/docs/store-screenshots/`)已经拍好 ✓,不受影响 ✓。

### 2026-11-16 深夜:真机装不上的根因 = 证书链用错了(不是设备类型、也不是签名)

排查过程:

1. 先怀疑「设备不在调试 Profile 白名单」→ 读 `saber_debug_profile` 的 `debug-info.device-ids`,
   **平板的 UDID 就在里面** ✓ → 白名单没问题。
2. 平板 UDID 用 `hdc shell bm get --udid` 读到(文档 §4.5.1 里记的方法 ✓),
   设备自报 `const.product.devicetype = tablet`。
3. 再看签名材料,把「证书」和「公钥」分开看 —— 之前一直把 `.cer` 文件里的
   **第一张**(根 CA)当成了这张证书本身,得把叶子(最后一张)单独拎出来比:
   | 东西 | 叶子证书的公钥 md5 前 10 位 |
   |---|---|
   | `app.p12` 私钥对应的证书 | `5b7d1f894f` |
   | 调试 Profile 引用的证书(…Development) | `5b7d1f894f` |
   | 发布 Profile 引用的证书(…Release) | `5b7d1f894f` |
   | 控制台另一张自动签名证书 | `4a7cb3b249` |
   → 公钥都是同一把 ✓,**但 Development 和 Release 是两张不同的证书** ✗ ✗。
4. 原来的 `build_chain()` 直接拿 `app.cer` 当证书链,而 `app.cer` 的叶子是
   **Release 证书** ✗ —— 调试 Profile 要的是 Development 证书 ✗ ✗。
   设备是拿 Profile 指定的那张证书去核对包里的证书链,对不上 →
   `code:9568322 not trusted app source` ✗。

修法:

* `harmony/toolchain/prepare_signing.py` 改成:**按公钥比对**,
  profile 引用的证书与 `app.p12` 是同一把钥匙时,以 profile 里那张证书为叶子,
  再拼上 `app.cer` 里的两级华为 CA(顺序跟 AGC 导出的 `.cer` 一致:根→中间→叶子,
  hvigor 才认)✓。
* `harmony/scripts/build_ohos.sh` 加了一道保险:构建前检查 Profile 类型,
  `--app`(上架包)配上调试 Profile 直接报错停下 ✓。
* 只重签(秒级,不用重新构建):用 `hap-sign-tool sign-app` 签
  `ohos/entry/build/default/outputs/default/entry-default-unsigned.hap` ✓
  (`verify-app` 验过:包里的 profile 与 `ohos/signing/app.p7b` 的 md5 完全一致 ✓)。

### 2026-11-17 06:32 真机界面自检:7/7 全部通过

平板解锁后跑 `python3 harmony/toolchain/verify_device_ui.py --connect` ✓,
逐项结果:

| 检查项 | 结果 | 实测到的界面文字 |
|---|---|---|
| 应用标题显示新名称 | ✅ | `Saber 手写笔记` |
| 版本号是 1.0.1 | ✅ | 设置页 `v1.0.1 (1000001)` |
| 版本号是 1000001 | ✅ | 同上 |
| 「主题类型」已隐藏 | ✅ | 设置页只有「应用主题/系统·浅色·深色」 |
| 登录页有隐私复选框 | ✅ | `我已阅读并同意《隐私政策》` |
| 有「不同意并退出」 | ✅ | 登录页左下角 |
| 未勾选时登录按钮禁用 | ✅ | 「使用 Saber 登录」「使用 Nextcloud 登录」均为 disabled |

即第 1 轮审核意见里与界面相关的 3 项(改应用名、版本号显示错误、隐私政策勾选框)
在真机上都已经落实 ✓。

### 明天(设备解锁后)要做的事

1. 平板解锁后跑 `python3 harmony/toolchain/verify_device_ui.py --connect` ✓。
2. 审核状态:轮询器每 5 分钟查一次(`/tmp/agc_poll.log` ✓),
   1.0.1 当前是「正在等待审核」 ✓。
3. 若被驳回,按审核报告逐条整改 → 版本号 +1 → 重新构建 `.app` → 上传 → 提交。

### 控制台里把平板的设备类型改成「平板」

* AGC「开发者管理 → 设备」里 MatePad Edge 那条原本登记成「**手机**」✗,
  已删掉重加为「**MatePad Edge / 平板**」✓(先要在 Profile 里解除关联才能删 ✓)。
* 调试 Profile 的白名单随之调整过一轮:先摘掉平板 → 删设备行 → 以「平板」重新添加 →
  再在 Profile「编辑设备」里勾回去 → 重新下载 Profile ✓(现在白名单是手机 + 平板两台 ✓)。

### 当前状态

- 版本:**1.0.1 (1000001)**,状态 **预审中**(2026-11-16 20:39 提交 ✓)
- 轮询:`harmony/toolchain/agc/agc_poll_review.sh`(5 分钟一次,最长约 7 天),日志 `/tmp/agc_poll.log`
- 遗留:控制台里那个 `saber-release.app`(不通过 996)还没删 ✓

## 2026-11-17 晚:第 2 轮审核被打回 → 改名换图标 → **1.0.2 重新提交成功(预审中)**

> 这一段的详细对照表在 [`APP-RELEASE-RECORD.md`](APP-RELEASE-RECORD.md) 的「第 2 轮审核结论 / 第 3 轮整改」两节,
> 这里只记**过程与坑**。

### 这一晚做了什么

1. **改名 + 换图标(针对第 2 轮的阻塞 1/2/3)**
   * 应用名:`Saber 手写笔记` → **`赛博手写笔记`**(Dart 标题、启动页、AppScope/entry 的 string.json 一起改,
     改了 `harmony/patches/upstream/0008/0009/0012–0015` 五个补丁)。
   * 图标:重写 `harmony/toolchain/make_app_icon.py`,生成**「赛博」主题**的 **1024×1024 RGB 无 alpha** 图标;
     `harmony/assets/app-icon-1024.png`、`ohos/AppScope/.../app_icon.png`、`ohos/entry/.../icon.png` 三处同源。
   * 控制台端:应用信息页的 **手机 / 平板 / PC·2in1** 三个页签的图标全部换成新图标,
     并逐个下载 CDN 上的图校验 md5 ✓(不能只看缩略图)。
2. **审核附件(针对阻塞 4)**:`harmony/toolchain/make_audit_zip.py` 生成 `saber-open-source-audit.zip`
   —— GPL-3.0 全文 + 一份《开源说明》,写明「上游 `saber-notes/saber` / 本项目 `brysj22952/saber` /
   分支 `feature/ohos-harmonyos`」「名称与图标已重做,与上游不同」。
   版权信息同时补上:**主办单位类型 = 个人**、**主办单位 = 与开发者账号主体一致**。
3. **商店介绍改成 383 字**,开头「赛博手写笔记 是一款专注手写的开源笔记应用…」,
   保留 GPL 开源声明与两个仓库地址(用户明确要求:商店描述里要写明是开源的、在鸿蒙设备上编译的)。
4. **商店截图重拍**:4 张 2353×1324(严格 16:9)—— 首页 / 新建菜单 / 编辑器 / 白板,
   截图脚本改用 `tap:newNote` 新建空白笔记再画两笔(`harmony/toolchain/capture_store_screenshots.py`),
   拍完用布局 dump 校验画面里只有应用自己的文字,**没有个人信息** ✓。
5. **上传 1.0.2 的包并提交**:`ohos/build/outputs/default/ohos-default-signed.app`(16.56 MB,发布签名),
   版本信息页 →「去选择」→ 选 1.0.2 → 提交审核 → 「发布信息确认」→ **确认提交** ✓。

### 真正卡住提交的那一下:「支持设备」里的「平板」

控制台横幅一直写「**您的 应用信息 页面还有必填信息未填写**」,可应用信息页该填的都填了,
点「提交审核」毫无反应(不弹框、不报错、状态还停在「准备提交」)。

* 排查路径:把版本页所有 `.el-form-item__error` 挖出来 → 只有两条提示
  (「软件包加密」是说明性提示,「上架时间」是历史脏数据),**都不是阻塞项** ✓;
  再回头看横幅 → 横幅说的确实是「**应用信息**」页。
* 逐项核对应用信息页的必填项(名称 / 三个页签的图标 / 分类 / 标签 / 语言 / 支持设备)—— 全有值 ✓。
* 最后靠**对比实验**定位:第 2 版(1.0.1)当时是 手机 + PC·2in1,能提交;
  这轮多勾了「平板」→ 页面多出「平板」页签 → 横幅出现 → 提交被拦。
  **把「平板」取消勾选并保存,横幅立刻消失,提交一次就过了** ✓。

> 所以「平板」这一项不是配置问题,是**控制台自己的校验 bug**:多一个设备页签就判必填未填。
> 本轮先按上一版的配置(手机 + PC·2in1)提交,平板形态等真机验证顺了再打开 ✓。

### 这一晚踩到的坑(补进上面的经验清单)

1. **AGC 的侧栏/路由会骗人**:`route_of()` 读出来的是 iframe 的 `location.hash`,
   而 SPA 在同一个 hash 上换子页面时 hash 不变 —— 必须再叠一层**页面内容校验**
   (版本页认「审核附件」、应用信息页认「应用名称」),否则会以为跳到了目标页却在别的页上操作。
2. **直接改 iframe 的 `location.hash` 做 SPA 跳转最稳**(同源),
   比点侧栏 + 等路由变化可靠得多 ✓。
3. **`Runtime.evaluate` 必须带 `contextId=f.ctx`**,否则求值落在顶层文档上,
   读出来的是控制台外壳的内容,看起来「像是有数据」其实完全不对 ✗。
4. **截图上传用 `DOM.setFileInputFiles`(objectId)**,不要用 nodeId;
   上传后**等 7 秒再取下一张**,否则会串位;并且要**上传后立刻比对 CDN 上新出现的图**
   —— 这次就因为「上传完刷新页面再看」而误判成没替换成功 ✗。
5. **版本页离开时会把「发布版本」重置** —— 改文案/截图与选包的顺序要对,
   否则提交上去的包不是你选的那个 ✗。
6. **浏览器标签页会越来越卡**:开新标签(`/json/new`)+ 关旧标签(`/json/close`),
   并且尽量用 SPA 跳转而不是整页 `Page.navigate` ✓。

### 当前状态(2026-11-17 23:32)

- 版本:**1.0.2 (1000002)**,状态 **正在等待审核**(23:24 提交,23:29 **预审通过** ✓)
- 预审(自动化检测)已过,现在等应用市场的人工审核(1–7 个工作日)✓
- 轮询:`harmony/toolchain/agc/agc_poll_review.sh`(5 分钟一次),日志 `/tmp/agc_poll.log`
  (已确认能识别到「版本: 1.0.2 / 状态: 正在等待审核」✓)
- 备用:后台已用**发布 Profile** 重打了一个 **1.0.3 (1000003)** 的 `.app`,
  万一 1.0.2 因包内图标(512×512 RGBA,alpha=254)被退回,直接上传它再提交即可 ✓
- 平板(MatePad Edge)上测试用的空白笔记已清空 ✓(应用停掉后删的 `*.sbn2` / `*.sbn2.p`)

## 2026-11-18:查清「包内图标的 alpha 通道」——上一版备用包其实没修好

> 起因:1.0.2 在人工审核队列里等着,上一轮留了个「万一 1.0.2 因包内图标被退回,
> 直接上传 1.0.3 备用包」的底。核对备用包时发现**它带着同一个毛病**,
> 也就是说:1.0.2 真要因为图标被退回,那个底是救不了命的。

### 现象

包里 `resources/base/media/{app_icon,icon}.png` 是 **512×512 RGBA**,
而且 **alpha 全场都是 254**(不是 255):

```python
im = Image.open(pkg_icon)
im.mode            # RGBA
im.getchannel('A').getextrema()   # (254, 254)  <- 每个像素都"还差一点"不透明
```

「上传的图标有透明背景」正是第 1、2 轮审核都判过的**阻塞项**。
商店侧早就改对了(`harmony/assets/app-icon-1024.png` 是 1024×1024 **RGB 无 alpha**),
但**包内**这一份一直被 SDK 改坏。

### 根因:restool 的 iconCheck 会把大图缩到 512,缩放过程会带出 alpha

* hvigor 的 `process-resource` 任务开着 `iconCheck`,restool 会把 media 里的
  应用图标**归一化到 512×512**(启动器规范尺寸);
* 源图是 **1024** 时这一步要缩放,走 SDK 的图像转码器
  (`libimage_transcoder_shared.so`,`opt-compression.json` 里的 `extensionPath`),
  转码器输出的是 **RGBA、alpha=254** 的 PNG;
* 源图本来就是 **≤512** 时,restool **原样拷贝**,根本不转码 → 输出是干净的 RGB。

用 SDK 自带的 restool 直接跑一遍(不改任何工程文件)验证:

| 源图 | 包内产物 | 结论 |
|---|---|---|
| 1024×1024 RGB | 512×512 **RGBA**(alpha=254) | ✗ 带透明通道 |
| 512×512 RGB | 512×512 **RGB** | ✓ 无 alpha 通道 |

> 手动跑 restool 时要带上 SDK 的库路径,否则会报
> `Failed to load the library .../libimage_transcoder_shared.so, libjsoncpp.so: cannot open shared object file`:
>
> ```bash
> SDK=<deveco-tools>/command-line-tools/sdk/default
> LD_LIBRARY_PATH="$SDK/hms/toolchains/lib:$SDK/hms/previewer/common/bin:$SDK/openharmony/previewer/common/bin" \
>   $SDK/openharmony/toolchains/restool -l <resConfig.json>
> ```
>
> (工程构建里 hvigor 自己会设好这个路径,不用手工加。)

### 修法:包内图标改成 512×512 RGB,商店图标保持 1024

* `harmony/toolchain/make_app_icon.py` 现在产出两份:
  * `harmony/assets/app-icon-1024.png` → **1024×1024 RGB**,商店上传用(商店规格就是 1024);
  * `ohos/AppScope/resources/base/media/app_icon.png` 与
    `ohos/entry/src/main/resources/base/media/icon.png` → **512×512 RGB**,包内用;
* 两张是**同一张图**(同一段绘制代码),只是分辨率不同,画面内容完全一致 ——
  审核员在商店页和终端上看到的仍是同一个图标;
* 包内那份不再有 alpha 通道,「透明背景」这条就没了;
* 顺带把 1.0.1 时代的 **144×144** 也一并解决了(第 2 轮的建议项)。

### 顺带修的另一个坑:两个轮询器抢同一个浏览器标签页

`/tmp/agc_poll.sh`(11-15 起)与 `harmony/toolchain/agc/agc_poll_review.sh`(11-16 起)
**同时在跑**,两个都往 `/tmp/agc_poll.log` 追加,于是:

* 日志里两条计数交错(`第379次` / `第344次` 混在一起),没法看;
* 两个脚本都用 CDP 驱动**同一个浏览器标签页**去读版本页,互相把 iframe 导航掉,
  于是大量轮询结果是「跳过(页面上没有包名 com.sabernotes.saber,可能连到了别的标签页)」——
  **轮询等于白跑**,真出状态变化反而可能看不到。

处理:停掉 `/tmp/agc_poll.sh`,只留仓库里那个 `agc_poll_review.sh`(有文档、有退出条件)。
之后再要起轮询,先 `pgrep -f agc_poll` 确认没有别的在跑。

### 当前状态(2026-11-18 07:05)

- **1.0.2 (1000002)**:仍在**正在等待审核**(人工审核,1–7 个工作日);
  轮询正常,最近几次都是干净的「版本: 1.0.2 / 状态: 正在等待审核」✓
- **备用包 1.0.3 (1000003)**:已用**发布 Profile** + 修好的 512 图标重新构建完成 ✓
  (产物 `build/ohos/app/ohos-default-signed.app`,同时也在 `ohos/build/outputs/default/`),
  验收结果见下。
- 构建前把 `ohos/signing/app.p7b` 换成了发布 Profile(`app-release.p7b`),
  **构建完已经换回调试 Profile**(`type == debug`),否则装真机会报「Profile 类型不匹配」。

### 验收清单(备用包)—— 全部通过 ✓

新增了一个验收脚本,以后每个上架包都跑一遍:

```bash
python3 harmony/toolchain/verify_app_package.py
```

1.0.3 (1000003) 的实测结果:

```
=== build/ohos/app/ohos-default-signed.app (16.55 MB) ===
  ✅ resources/base/media/icon.png 512×512 RGB,无 alpha 通道
  ✅ resources/base/media/app_icon.png 512×512 RGB,无 alpha 通道
  ✅ 包名 com.sabernotes.saber
  ✅ 版本 versionName=1.0.3 versionCode=1000003
  ✅ 包内能找到应用名「赛博手写笔记」
  ✅ 签名校验通过(hap-sign-tool verify-app)
  ✅ 包内 profile 类型 = release(发布 Profile)
  ✅ 包内 profile 与 ohos/signing/app-release.p7b 完全一致
```

> **签名在 .app 上,不在里面的 hap 上** —— 上架包是**整包签名**(app-level),
> 签名块在 `.app` 自己身上,里面的 `entry-default.hap` 是不带签名的。
> 所以要对 `.app` 跑 `hap-sign-tool verify-app`;对里面的 hap 跑会报
> `No Hap Signing Block before ZIP Central Directory` ✗。

### 2026-11-18 补充:包内图标改成「商店图标的精确缩放」

上面那版修法是把 `draw_icon(512)`(重新画一遍 512)放进包内。这轮又收紧了一步:
包内那张现在是**商店那张 1024 原图的 LANCZOS 缩放**,即

```python
packaged = store_1024.resize((512, 512), Image.LANCZOS)
```

理由:审核员会拿**控制台/商店的图标**和**终端里装出来的图标**比。
「第 2 轮」的阻塞意见 1 就是「控制台图标 ≠ 终端安装后的图标」。
重新画一遍 512 虽然是同一段代码,但边缘抗锯齿与商店那张不完全相同
(实测最大通道差 70,集中在霓虹描边的高对比像素);
改成精确缩放后,**差异为 0**,两个图标是逐像素可验证的同一张 ✓。

另外这轮还做了「审核期间的商店页自查」(逐项见
[`APP-RELEASE-RECORD.md`](APP-RELEASE-RECORD.md) §2026-11-18),
并修掉一个自查时抓到的不一致:**隐私政策网页还自称「Saber」**,
而应用已改名「赛博手写笔记」——已改并推 gh-pages,线上生效 ✓。
