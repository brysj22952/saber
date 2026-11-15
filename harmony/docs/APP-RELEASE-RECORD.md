# Saber 鸿蒙版 · 华为应用市场上架记录

> 这是**上架专用**的简表,只记「哪一次提交、什么结果、怎么处理的」。
> 过程细节(坑、命令、截图脚本)在 [`DEPLOY-RECORD.md`](DEPLOY-RECORD.md) 里。

---

## 版本 1.0.0

| 项 | 值 |
|---|---|
| 应用名 | Saber |
| 包名 | `com.sabernotes.saber` |
| 版本 | versionName `1.0.0` / versionCode `1000000` |
| targetSdkVersion | `6.0.1(21)` |
| 设备类型 | 手机 / 平板 / 2in1 |
| 上架包 | `ohos-default-signed.app`(16.53 MB) |
| 签名 | 发布证书 + 发布 Profile(`type=release`,无设备白名单) |
| 分类 | 应用 → 工具;主标签 备忘录,附加标签 笔记 |
| 年龄分级 | 中国区 3+ / 巴西 所有年龄段 / 其他区域 3+ |
| 隐私政策 | https://brysj22952.github.io/saber/privacy-policy.html |
| 发布国家或地区 | 所有国家或地区(200 个) |
| 软件包加密 | 加密 |
| 负责人 | 胡中强(手机号已验证,邮箱 `13025424320@qq.com`) |
| 许可 | GPL-3.0,应用介绍中已声明开源并给出官方/本项目仓库地址 |

### 提交时间线

| 时间 | 事件 |
|---|---|
| 2026-11-15 17:15 | 上传 `ohos-default-signed.app`,合法性 **已达标** |
| 2026-11-15 18:0x | 版本表单全部填毕,点「提交审核」→「确认提交」 |
| 2026-11-15 18:0x | 状态变为 **预审中**(AGC 预审约 30–40 分钟,通过后自动转正式审核) |

### 审核结论

> 状态:**等待预审结果**(轮询中)

- 预审结果:
- 检测报告(如被打回):
- 正式审核结果:

### 下一版要做的事

- [ ] 预审通过后确认状态变为「审核中」→「已上架」
- [ ] 审核通过后把应用市场上架页链接补进本表
- [ ] 若被打回:按检测报告修 → 重新构建 → 重新提交,并在此追加一行

### 商店页文案

见 [`store-listing.md`](store-listing.md)(提交时填的就是这份文案 ✓)。

---

## 若被打回(预审不通过 / 审核驳回)的处理流程

1. 打开 AGC → 应用管理 → Saber → 版本/升级 → 点「检测报告」或「审核意见」,**先把报告原文贴进本表**。
2. 按报告逐条修,常见对应关系:

   | 报告里常见的说法 | 怎么处理 |
   |---|---|
   | 「隐私政策 URL 无法访问 / 与应用功能不符」 | 改 `harmony/docs/privacy-policy.html`,推 gh-pages 后重填隐私政策网址 |
   | 「权限说明与实际申请不符」 | 实际只申请 `ohos.permission.INTERNET`(已核对提交包内 `module.json` ✓),照实写 |
   | 「截图含个人信息 / 尺寸不符」 | 用 `harmony/toolchain/capture_store_screenshots.py` 重拍(严格 16:9) |
   | 「分类 / 年龄分级不符」 | 改应用分类标签、重填年龄分级问卷 |
   | 「功能与描述不符 / 崩溃」 | 重新构建 `.app` 并**重新上传新版本**(versionCode 递增)再提交 |

3. 需要改包时:改代码 → `flutter build app --release --build-name=<x> --build-number=<N+1>
   --dart-define=FLUTTER_OHOS_AOT_BUILD=true` → AGC 软件包管理上传新 `.app` → 版本页「去选择」选新包 → 提交审核。
4. 每一轮结论都追加到本表,并在 [`DEPLOY-RECORD.md`](DEPLOY-RECORD.md) 里补一节细节。

## 查状态

```bash
python3 harmony/toolchain/agc/agc_version_status.py
# 状态: 预审中 / 审核中 / 已上架 ...
```
