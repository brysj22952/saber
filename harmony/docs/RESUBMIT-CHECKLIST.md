# 重提版本清单(被打回时照着做)

> 场景:1.0.2(1000002)被审核打回 → 用 **1.0.3(1000003)** 重提。
> 1.0.3 的包已经用**发布签名**打好并验收通过(10/10),
> 位置 `build/ohos/app/ohos-default-signed.app`。
> 逐条做完再提交,顺序不能乱。

## 0. 先看状态

```bash
tail -20 /tmp/agc_poll.log          # 轮询日志;出现「不通过」就是终态
```

## 1. 确认包还在、还是发布签名

```bash
cd /root/hzq/saber-ohos/saber
python3 harmony/toolchain/verify_app_package.py     # 期望:10 项通过 / 0 失败
```

如果包不在了,重新构建(**注意签名切换**):

```bash
source /root/hzq/saber-ohos/env.sh
cp ohos/signing/app.p7b /root/hzq/saber-ohos/.signing-backup/app.p7b.debug-$(date +%Y%m%d-%H%M)
cp ohos/signing/app-release.p7b ohos/signing/app.p7b        # ← 换成发布 Profile
APP_VERSION_NAME=1.0.3 APP_VERSION_CODE=1000003 bash harmony/scripts/build_ohos.sh --app
cp /root/hzq/saber-ohos/.signing-backup/app.p7b.debug-<时间戳> ohos/signing/app.p7b   # ← 换回调试
```

## 2. 上传包

AGC 控制台 →「应用管理」→ 选应用 →「版本管理」→「软件包管理」→「上传软件包」
→ 选 `build/ohos/app/ohos-default-signed.app`。

## 3. 版本页:先选包,再改文案(顺序反了会被重置)

「版本信息」页 → 点「去选择」→ 选刚上传的 1.0.3 → **确认**。

> ⚠️ 离开页面时「发布版本」会被重置回「去选择」。所以顺序必须是:
> **先选包 → 再传附件 → 再改文案/截图 → 最后提交**。

## 4. 两个附件槽都要传(第 3 轮踩过的坑)

| 槽位 | 路径 | 传这个 |
|---|---|---|
| 审核附件 | 版本页 → 审核附件 | `harmony/docs/store-materials/saber-open-source-audit.zip`(567,960 字节) |
| 授权书及其他材料 | 版本信息 → 版权信息 → 授权书及其他材料 | `harmony/docs/store-materials/开源说明与授权依据.pdf`(586,661 字节) |

> 「授权书及其他材料」**只收 JPG/JPEG/BMP/PDF,不收 zip**。1.0.2 就是因为
> 只传了 zip 那一侧,这个槽空着,很可能在「应用资质」上再被打回。

## 5. 版本信息文案(照抄 `harmony/docs/store-listing.md`)

* 应用介绍:`store-listing.md` §2
* 版本更新说明:§5 的 **1.0.3** 一段
* 权限说明:§3
* 分类/年龄分级/隐私政策网址/支持设备:§6 表格(**平板保持关掉**,
  勾上会多出设备页签并触发「必填信息未填写」把提交卡住)

## 6. 提交

「提交审核」→ 弹窗「确认提交」。

**不要**点「撤销审核」/「保存草稿」,那两个会把发布版本状态重置掉。

## 7. 复核(提交后读回控制台)

* 版本号 = 1.0.3 / 1000003
* 审核附件与授权书两个槽都显示已上传
* 应用名 = 赛博手写笔记
* 隐私政策网址 = https://brysj22952.github.io/saber/privacy-policy.html
* 状态变成「正在等待审核」

## 8. 记录

把这一轮的结论追加到 `harmony/docs/APP-RELEASE-RECORD.md` 与
`harmony/docs/DEPLOY-RECORD.md`(两篇都要写),并重启轮询:

```bash
nohup env AGC_POLL_INTERVAL=300 bash harmony/toolchain/agc/agc_poll_review.sh >/dev/null 2>&1 &
tail -f /tmp/agc_poll.log
```

> 轮询器**只能有一个实例** —— 两个进程会抢同一个浏览器标签页,互相把页面导航坏。
