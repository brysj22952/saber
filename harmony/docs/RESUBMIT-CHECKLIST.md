# 重提版本清单(被打回时照着做)

> 场景:1.0.2(1000002)被审核打回 → 用 **1.0.3(1000003)** 重提。
> 1.0.3 的包已经用**发布签名**打好并验收通过(10/10),
> 位置 `build/ohos/app/ohos-default-signed.app`。
> 逐条做完再提交,顺序不能乱。

## ⚠️ 先看这里:**两套口径,客服口径优先**(2026-11-20 更新)

1.0.2 已于 **2026-11-18 21:05:42** 被驳回(审核未通过,3 个问题:
应用功能 2 个「暂不影响上架」的建议项 + 应用资质 1 个阻塞项)。
**2026-11-20 华为客服(互动中心工单)答复:不用再提交授权书** ✓ ——
但客服自己也留了口子:「以后续提审的结果为准」,所以备用口径要留着 ✓。

| | 口径 ①**客服口径(优先,默认走这条)** | 口径 ② 备用(仅当又被要求授权书时) |
|---|---|---|
| 应用名称 | **保持「赛博手写笔记」不变** ✓ | 同 ① |
| 商店图标 | **保持当前图标不变** ✓ | 同 ① |
| 「授权书及其他材料」槽 | **留空,不传** ✓ | **传** `harmony/docs/store-materials/授权材料.zip`(624,909 字节)✓ |
| 「审核附件」槽 | **仍然传** `saber-open-source-audit.zip`(639,543 字节)✓ | 同 ① |
| 备注栏 | **必填**,原样写客服给的那句(见下)✓ | 同 ① |
| 其余步骤 | 第 0~9 节,完全一样 ✓ | 同 ① |

**① 备注栏要写的内容 —— 照抄客服原话,一个字都别改**:

```
已通过互动中心工单号：461323199043685201反馈，当前名称及图标与Saber不一致，已沟通。
```

> 客服原话(逐字):「请保持当前名称及图标重新提审,同时请在备注栏中备注
> "已通过互动中心工单号:461323199043685201反馈,当前名称及图标与Saber不一致,已沟通。",
> 便于审核人员知悉,以后续提审的结果为准。」
> ⚠️ 客服原话用的是**全角冒号「：」**与**全角逗号「，」** —— 照抄即可 ✓;
> ⚠️ **不要再改名、不要再换图标** ✗✗(1.0.1→1.0.2 那次改名换图标就是为了消「知识产权」那条,
> 客服已认定「最新上传的版本已经修改图标及名称」,现在**保持不动**才是对的 ✓)。

> 客服答复的完整来龙去脉见
> [`APP-RELEASE-RECORD.md`](APP-RELEASE-RECORD.md) 第 15 轮 ✓。

## 0. 先看状态

```bash
tail -20 /tmp/agc_poll.log          # 轮询日志;出现「不通过」就是终态
```

轮询器一旦看到「不通过」,会**自动把审核报告抓下来**(第 12 轮加的 ✓):
报告正文在报告页里的 amp iframe 中,6 条问题分在 4 个 tab 上,
脚本会逐个 tab 点开再读,所以拿到的是**全部 6 条** ✓。

```bash
ls -l /tmp/agc_audit_report_*.txt   # 被打回时会有这个文件
cat /tmp/agc_audit_report_1.0.2.txt
```

> 报告页是新的标签页,`--raw` 之类的方式只能看到当前那个 tab 的一条,
> 6 条问题会看不全 —— 用 `python3 harmony/toolchain/agc/agc_audit_report.py --out <文件>` 重抓。

## 1. 确认包还在、还是发布签名

```bash
cd /root/hzq/saber-ohos/saber
python3 harmony/toolchain/verify_app_package.py     # 期望:10 项通过 / 0 失败
md5sum build/ohos/app/ohos-default-signed.app       # 期望:0094975e96179b44f0cff396702ce025
```

> 上面那个 md5 是**第 12 轮重打的那个包**(24 个语言包改名之后重打的 ✓,
> 10/10 通过 ✓,AOT 里查得到新名字、查不到旧的 "Welcome to Saber" ✓)。
> 另有一份副本在 `/root/hzq/saber-ohos/release-artifacts/` ✓。

如果包不在了,重新构建(**注意签名切换**):

```bash
cd /root/hzq/saber-ohos/saber
mkdir -p .signing-backup
TS=$(date +%Y%m%d-%H%M%S)
cp ohos/signing/app.p7b ".signing-backup/app.p7b.debug-$TS"
cp ohos/signing/app-release.p7b ohos/signing/app.p7b        # ← 换成发布 Profile
# 用 trap 保证**构建失败也会换回调试 Profile**(否则下次调试包就签不上了)
restore() { cp ".signing-backup/app.p7b.debug-$TS" ohos/signing/app.p7b; }
trap restore EXIT
source /root/hzq/saber-ohos/env.sh
APP_VERSION_NAME=1.0.3 APP_VERSION_CODE=1000003 bash harmony/scripts/build_ohos.sh --app
```

构建完核对两件事:

```bash
md5sum ohos/signing/app.p7b          # 期望 75fcf9472804a6c09d771bfe00699495(调试 Profile)
python3 harmony/toolchain/verify_app_package.py   # 期望:10 项通过 / 0 失败
```

> `.signing-backup/` 已在 `.gitignore` 里 ✓,签名材料永远不会进仓库 ✓。

## 2. 上传包

AGC 控制台 →「应用管理」→ 选应用 →「版本管理」→「软件包管理」→「上传软件包」
→ 选 `build/ohos/app/ohos-default-signed.app`。

也可以直接用脚本往那个文件选择框里塞文件(浏览器没法用 JS 模拟选文件,
只能走 CDP 的 `DOM.setFileInputFiles`):

```bash
python3 harmony/toolchain/agc/agc_upload.py \
    build/ohos/app/ohos-default-signed.app
```

> 页面结构变了就加上 `--index N`(第几个 `input[type=file]`)或 `--scope top` ✓。

## 3. 版本页:先选包,再改文案(顺序反了会被重置)

「版本信息」页 → 点「去选择」→ 选刚上传的 1.0.3 → **确认**。

> ⚠️ 离开页面时「发布版本」会被重置回「去选择」。所以顺序必须是:
> **先选包 → 再传附件 → 再改文案/截图 → 最后提交**。

## 4. 附件槽:按上面「两套口径」走(第 3 轮踩过的坑 + 第 15 轮客服口径)

**默认(口径 ①,客服口径):**

| 槽位 | 路径 | 传什么 |
|---|---|---|
| 审核附件 | 版本页 → 审核附件 | ✅ **传** `harmony/docs/store-materials/saber-open-source-audit.zip`(639,543 字节) |
| 授权书及其他材料 | 版本信息 → 版权信息 → 授权书及其他材料 | ⛔ **留空,不传**(客服:「可以不需要提供授权书」)✓ |

**备用(口径 ②,仅当下一轮审核又点名要授权书时):**

| 槽位 | 路径 | 传什么 |
|---|---|---|
| 审核附件 | 版本页 → 审核附件 | ✅ `harmony/docs/store-materials/saber-open-source-audit.zip`(639,543 字节) |
| 授权书及其他材料 | 版本信息 → 版权信息 → 授权书及其他材料 | ✅ **传** `harmony/docs/store-materials/授权材料.zip`(624,909 字节,内含两份 PDF) |

> 「授权书及其他材料」收的是 **zip**(≤200M),压缩包里的文件限 JPG/JPEG/BMP 与 PDF
> —— 控制台原文就是这么写的,第 8 轮核对过 ✓。
> 1.0.2 这个槽是空的(审核期间字段被禁用 ✗),第 3 轮审核就在「应用资质」上被打回 ✗;
> **但客服 2026-11-20 已明确说不用提供** ✓ → 默认按口径 ① 留空,
> 真的又被要求了再按口径 ② 补上 ✓。

## 4b. 顺手确认「应用截图和视频」还带着那四张图

版本表单里「应用截图和视频」是**必填**的(介绍截图)✗。新版本表单可能不继承
1.0.2 的截图 ✓,所以提交前逐个槽看一眼:

* 介绍截图 ×1(必填)、其它素材 ×3(选填)—— 总共 4 张 ✓
* 就是 `harmony/docs/store-screenshots/` 里的 home / fabmenu / editor / whiteboard ✓
* 4 张都是 2353×1324 的 16:9 ✓,重拍命令见
  `harmony/toolchain/capture_store_screenshots.py` ✓

## 5. 版本信息文案(照抄 `harmony/docs/store-listing.md`)

* 应用介绍:`store-listing.md` §2
* 版本更新说明:§5 的 **1.0.3** 一段
* 权限说明:§3
* 分类/年龄分级/隐私政策网址/支持设备:§6 表格(**平板保持关掉**,
  勾上会多出设备页签并触发「必填信息未填写」把提交卡住)

**别手抄** —— 三段文案都带中文标点,抄错一个字就是商店页上肉眼可见的瑕疵。
先把它抠出来,连同长度一起看:

```bash
python3 harmony/toolchain/agc/agc_listing_texts.py --check     # 只看长度
python3 harmony/toolchain/agc/agc_listing_texts.py             # 打印三段
python3 harmony/toolchain/agc/agc_listing_texts.py --write-dir /tmp/listing
```

> 长度(第 13 轮实测):应用介绍 383 字、权限说明 312 字、更新说明 334 字 ✓,
> 控制台的字段上限远大于这些 ✓。

## 6. 提交

「提交审核」→ 弹窗「确认提交」。

**不要**点「撤销审核」/「保存草稿」,那两个会把发布版本状态重置掉。

> **提交前必须检查备注栏**:把客服给的那句**原样**粘进去 ——
> `已通过互动中心工单号：461323199043685201反馈，当前名称及图标与Saber不一致，已沟通。`
> 这是客服明确要求的一步(「便于审核人员知悉」)✓,漏了可能被再次按「名称图标相似」打回 ✗。

## 7. 复核(提交后读回控制台)

* 版本号 = 1.0.3 / 1000003
* 审核附件显示已上传;「授权书及其他材料」按口径 ① **留空** / 按口径 ② **显示已上传**
* 备注栏 = `已通过互动中心工单号：461323199043685201反馈，当前名称及图标与Saber不一致，已沟通。`
* 应用名 = 赛博手写笔记(**没有**被改名)✓
* 应用图标 = 当前那张(**没有**被换掉)✓
* 隐私政策网址 = https://brysj22952.github.io/saber/privacy-policy.html
* 状态变成「正在等待审核」

## 8. 记录

把这一轮的结论追加到 `harmony/docs/APP-RELEASE-RECORD.md` 与
`harmony/docs/DEPLOY-RECORD.md`(两篇都要写),并重启轮询:

```bash
pkill -f "agc_poll_review[.]sh"        # 先确保没有旧实例
nohup env AGC_POLL_INTERVAL=300 bash harmony/toolchain/agc/agc_poll_review.sh >/dev/null 2>&1 &
sleep 45; tail -20 /tmp/agc_poll.log
```

> 轮询器**只能有一个实例** —— 两个进程会抢同一个浏览器标签页,互相把页面导航坏。

## 9. 上架后核对商店页(审核通过时再跑)

```bash
python3 harmony/toolchain/agc/agc_store_check.py \
    --app-id 6917621319756237551 --name 赛博手写笔记
```

逐项核对,结论写进 `/tmp/agc_store_check.json`:

| 项 | 判据 |
|---|---|
| 名称 | 详情页正文出现「赛博手写笔记」 |
| 图标 | 商店里的正方形图片与本地 1024 图标缩放后平均像素差 < 8.0 |
| 截图 | 双向集合比对:本地四张都能在商店宽图里对上(差 < 8.0),商店的宽图也都能对上本地某张 |
| 介绍 | 正文含介绍文案里的关键句(「完全离线可用」) |
| 隐私政策 | 页面里能找到**我们那个**政策网址(不是商店页脚自带的通用法律链接),且 HTTP 200 |

> 阈值 8.0 是本地实测标定的(同一张图重编码后差 0.03~0.44,不同截图差 10.7~23.0),
> 详见 `harmony/docs/APP-RELEASE-RECORD.md` 第 10 轮。

> 必须走 `/app/C<appId>` 详情页;搜索页会把搜索词回显在正文里,不能据此判断已上架。

