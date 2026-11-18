# 上传材料(审核附件 / 授权书)

这两个文件是审核报告里「应用资质 1:缺《Saber官方授权书》」对应的材料,
**要传到两个互不相干的槽位**:

| 控制台位置 | 收什么格式 | 传哪个文件 |
|---|---|---|
| 版本页 →「审核附件」 | zip(任意内容) | `saber-open-source-audit.zip` |
| 版本信息 →「版权信息」→「授权书及其他材料」 | **zip**(≤200M,压缩包内是 JPG/JPEG/BMP 图片与 PDF) | `授权材料.zip` |

> 第 8 轮在控制台上核对过原文:「授权书及其他材料:上传 —— 请上传 zip 格式文件,
> 不能超过 200M。**压缩包内支持包含 JPG、JPEG、BMP 格式图片和 PDF 格式的文件**,
> 文件夹层级最多三层,累计不超过 200 个文件。」
> 也就是说这个槽**收 zip**,只是压缩包里的文件要限制成图片与 PDF;
> 所以单独准备了一个 `授权材料.zip`,里面只有那两份 PDF(不带 .txt / LICENSE,
> 免得格式不合)。
>
> ⚠️ 1.0.2 的这个槽**是空的**(审核期间该字段被禁用,改不了),
> 所以它很可能在「应用资质」上再被打回 —— 重提 1.0.3 时两个槽都要传。

## 怎么重新生成

三个文件都由一个脚本生成,不要手工改:

```bash
python3 harmony/toolchain/make_audit_zip.py --output /tmp/saber-open-source-audit.zip
```

然后把 zip 里的两个 PDF 解出来放到本目录(审核员看的是 PDF 本身):

```bash
cd harmony/docs/store-materials
unzip -o /tmp/saber-open-source-audit.zip '*.pdf'
# 「授权书及其他材料」那个槽只收图片与 PDF,单独打一个只含 PDF 的包
zip -j 授权材料.zip 开源说明与授权依据.pdf GPL-3.0-LICENSE.pdf
```

改过 `harmony/toolchain/make_audit_zip.py` 里的 `README_TEMPLATE` 之后,
**一定要重新生成并把新的 PDF 一起提交**,否则目录里的 PDF 与 zip 里的会不一致。

## 内容

* `开源说明与授权依据.pdf`(2 页,整图嵌入,1240×1754 @150dpi)
  —— 应用性质、源码地址、GPL-3.0 授权依据、与上游的差异、
  **名称与图标的独立性**、上游版权声明原文、构建说明、隐私与数据处理、联系方式;
* `GPL-3.0-LICENSE.pdf`(11 页,文本型)—— 上游采用的 GPL-3.0 全文;
* `saber-open-source-audit.zip` —— 上面两个 PDF + `LICENSE`(纯文本)+
  `README-OpenSource.txt`(同 PDF 的文字版);传到「审核附件」槽 ✓;
* `授权材料.zip` —— 只含上面两个 PDF;传到「授权书及其他材料」槽 ✓
  (那个槽的压缩包内容限图片与 PDF)。
