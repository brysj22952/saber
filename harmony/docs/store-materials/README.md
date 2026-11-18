# 上传材料(审核附件 / 授权书)

这两个文件是审核报告里「应用资质 1:缺《Saber官方授权书》」对应的材料,
**要传到两个互不相干的槽位**:

| 控制台位置 | 收什么格式 | 传哪个文件 |
|---|---|---|
| 版本页 →「审核附件」 | zip | `saber-open-source-audit.zip` |
| 版本信息 →「版权信息」→「授权书及其他材料」 | **只收 JPG / JPEG / BMP / PDF** | `开源说明与授权依据.pdf` |

> ⚠️ 「授权书及其他材料」那个槽**不收 zip**。第 3 轮就是因为把材料做成 zip
> 只传进了「审核附件」,这个槽一直空着 —— 1.0.2 因此很可能在「应用资质」上
> 再次被打回。zip 里已经带了同一份 PDF,两边内容一致。

## 怎么重新生成

三个文件都由一个脚本生成,不要手工改:

```bash
python3 harmony/toolchain/make_audit_zip.py --output /tmp/saber-open-source-audit.zip
```

然后把 zip 里的两个 PDF 解出来放到本目录(审核员看的是 PDF 本身):

```bash
cd harmony/docs/store-materials
unzip -o /tmp/saber-open-source-audit.zip '*.pdf'
```

改过 `harmony/toolchain/make_audit_zip.py` 里的 `README_TEMPLATE` 之后,
**一定要重新生成并把新的 PDF 一起提交**,否则目录里的 PDF 与 zip 里的会不一致。

## 内容

* `开源说明与授权依据.pdf`(2 页,整图嵌入,1240×1754 @150dpi)
  —— 应用性质、源码地址、GPL-3.0 授权依据、与上游的差异、
  **名称与图标的独立性**、上游版权声明原文、构建说明、隐私与数据处理、联系方式;
* `GPL-3.0-LICENSE.pdf`(11 页,文本型)—— 上游采用的 GPL-3.0 全文;
* `saber-open-source-audit.zip` —— 上面两个 PDF + `LICENSE`(纯文本)+
  `README-OpenSource.txt`(同 PDF 的文字版)。
