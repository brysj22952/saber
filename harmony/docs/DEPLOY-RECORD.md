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
