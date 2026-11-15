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

---

## 阶段 0–5 总结(2026-11-15)

| 项 | 结论 |
|---|---|
| 是否上架成功 | **尚未上架** —— 1.0.0 已于 2026-11-15 18:07 提交,18:09 预审通过,当前 **正在等待审核**(华为侧人工审核) |
| 审核结论 | 预审(自动化检测)**通过** ✓;正式审核待出结果 |
| 提交物 | `ohos-default-signed.app`(16.53 MB,发布证书 + 发布 Profile,targetSdk 6.0.1(21)) |
| 商店素材 | 图标 1024×1024 ✓ / 4 张 2353×1324 严格 16:9 截图 ✓ / 隐私政策 GitHub Pages ✓ / 分类「工具」+ 标签「备忘录」✓ / 年龄分级 中国区 3+·巴西 AL·其他区域 3+ ✓ |
| 开源声明 | 应用介绍里已写明:开源项目、为 HarmonyOS 设备编译适配、官方仓库 `saber-notes/saber` + 本项目仓库 `brysj22952/saber` ✓,许可 GPL-3.0 ✓ |
| 下一步 | ① 等审核结果(轮询脚本 `harmony/toolchain/agc/agc_poll_review.sh`,最长约 7 天);<br>② 若被驳回 → 按检测报告修 → 重新构建 `.app`(versionCode 递增)→ 重新提交;<br>③ **2027-01-01 前把 targetSdkVersion 升到 `26.0.0`** —— 控制台已提示,从 2027 年起 API 26 才会强制;<br>④ 清理控制台里那个遗留的 `saber-release.app`(不通过(996));<br>⑤ 上架后在应用市场搜「Saber」核对商店页与截图展示 ✓ |
