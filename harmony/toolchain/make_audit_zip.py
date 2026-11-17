#!/usr/bin/env python3
"""生成上传给华为应用市场审核的「授权书及其他材料」附件(审核附件)。

审核第 2 轮要求在版本信息页的「版权信息 / 审核附件」里提供软件权属依据。
本项目是 Saber(GPL-3.0)的 HarmonyOS 移植版本,无法提供上游的「官方授权书」,
但可以提供 **GPL-3.0 协议全文 + 一份开源说明** —— 这正是本项目合法的分发依据。

用法:
    python3 harmony/toolchain/make_audit_zip.py                # 输出到 /tmp/saber-open-source-audit.zip
    python3 harmony/toolchain/make_audit_zip.py -o /tmp/x.zip

产物(纯文本,不包含任何签名材料):
    LICENSE              上游 GPL-3.0 协议全文(取自仓库根目录的 LICENSE.md)
    README-OpenSource.txt  开源说明:上游地址 / 本项目地址 / 授权依据 / 与上游的差异
"""

import argparse
import os
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

UPSTREAM_URL = "https://github.com/saber-notes/saber"
OWN_REPO_URL = "https://github.com/brysj22952/saber"
OWN_BRANCH = "feature/ohos-harmonyos"

README_TEMPLATE = """赛博手写笔记 —— 开源说明与授权依据

一、应用性质
本应用(应用名称:赛博手写笔记;包名:com.sabernotes.saber)是开源项目 Saber
({upstream})的 HarmonyOS / 鸿蒙(OpenHarmony NEXT)移植版本,
基于 GPL-3.0 协议开源,源代码完整公开,遵循 GPL-3.0 的全部条款。

二、源码地址
1. 官方开源项目(Saber 上游本体,GPL-3.0):
   {upstream}
2. 本鸿蒙版本(含完整鸿蒙构建链、签名配置说明、补丁脚本):
   {own}
   分支:{branch}

三、授权依据
附件 LICENSE 为 Saber 上游项目采用的 GPL-3.0 完整协议文本。
GPL-3.0 第 4、5、6 条明确允许在保留版权声明与许可证的前提下,
复制、修改并以源程序形式分发本作品,以及分发由本作品衍生的程序。
本移植版本即依据该授权条款开发与发布,并在应用内与本说明中保留上游版权归属信息。

四、与上游的差异(避免混淆)
本移植版本已重新设计应用图标与应用名称(由原项目名改为「赛博手写笔记」),
界面与应用信息均已独立调整,不是上游官方发布的版本,上游项目维护者
不对本移植版本提供官方支持,相关问题请以本仓库 issue 为准。

五、构建说明
本移植版本在 HarmonyOS 设备 / 开发工具链上编译打包,构建脚本位于:
{own}(harmony/scripts/build_ohos.sh)
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="/tmp/saber-open-source-audit.zip")
    args = ap.parse_args()

    lic = os.path.join(REPO_ROOT, "LICENSE.md")
    if not os.path.exists(lic):
        lic = os.path.join(REPO_ROOT, "LICENSE")
    if not os.path.exists(lic):
        raise SystemExit("找不到 LICENSE / LICENSE.md,无法生成授权依据附件")

    readme = README_TEMPLATE.format(upstream=UPSTREAM_URL, own=OWN_REPO_URL, branch=OWN_BRANCH)

    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(lic, "LICENSE")
        z.writestr("README-OpenSource.txt", readme)

    print("已生成:", args.output, os.path.getsize(args.output), "字节")
    print("内容:", zipfile.ZipFile(args.output).namelist())


if __name__ == "__main__":
    main()
