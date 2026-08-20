# 初始标准文件审核规则

本目录保存标准文件审核的第一批规则制品。

## 制品

- `general-standard-audit.yaml`：第一份通用审核准则，覆盖标准文件的基本元数据、结构、编号、内部引用和未识别内容保留。规则结果只产生审核发现，不阻断 CSM/SSIR 转换。
- `schemas/audit-rule-set.schema.json`：通用审核准则的 Draft-07 Schema。
- `profiles/standard-initial.yaml`：一般标准文件的组合审核配置，加载通用准则，并声明 GB/T 1.1-2020 为必需的规范性依据。
- `profiles/product-standard-initial.yaml`：产品标准的组合审核配置，继承 GB/T 1.1-2020，并叠加适用的 GB/T 20001.10-2014。
- `sources/GBT 1.1-2020.csm.md`：GB/T 1.1-2020 的 CSM 规则源副本，保留原文并补充 CSM/来源元数据。
- `sources/GBT 1.1-2020.ssir.json`：由 CSM 规则源生成、通过 SSIR Schema 的权威 SSIR 文件。
- `sources/GBT 1.1-2020.conversion-report.json`：转换诊断和来源哈希记录。
- `sources/GBT 20001.10-2014.csm.md`：GB/T 20001.10-2014 的 CSM 规则源副本。
- `sources/GBT 20001.10-2014.ssir.json`：由 CSM 规则源生成、通过 SSIR Schema 的权威 SSIR 文件。
- `sources/GBT 20001.10-2014.conversion-report.json`：转换诊断和来源哈希记录。

## 当前状态

GB/T 1.1 和 GB/T 20001.10 的 SSIR 是规则文档的事实层和规范性依据，不等于已经完成的逐条 Requirement Catalog。后续应从两个 SSIR 编译或人工校核 `AuditRule`，并为每条规则补充来源条款、适用条件、检查算子、证据要求和人工复核状态。产品标准配置中的继承顺序是：通用准则 -> GB/T 1.1 -> GB/T 20001.10。

排版、字号、空格、行距等规则暂不进入通用审核准则；未来应从 GB/T 1.1 单独生成 `RenderingManifest`，供 SSIR 到 DOCX/PDF 的渲染阶段使用。

## 验证

```text
PYTHONPATH=src python3 -m leleby_ssir csm parse \
  --input 'rules/sources/GBT 1.1-2020.csm.md' \
  --output 'rules/sources/GBT 1.1-2020.ssir.json' \
  --format json

PYTHONPATH=src python3 -m leleby_ssir csm roundtrip \
  --input 'rules/sources/GBT 1.1-2020.csm.md' \
  --std1-output out/GBT-1.1-2020.std1.csm.md
```
