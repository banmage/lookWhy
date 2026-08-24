# 规则库（rules/）

本目录保存系统可加载的业务规则制品。规则是系统的"程序"，与 `corpus/`（语料数据）和 `storage/`（租户运行时数据）严格分离。

## 目录结构

```
rules/
├── base/                          # 通用规则（平台管理员上传，批准即全局生效）
│   ├── gbt-1-1-2020/              # 一个标准一个规则包
│   │   ├── requirements.yaml      # GB/T 1.1-2020 结构化规则要求（内容/结构/排版，带 source 章节追溯）
│   │   ├── extraction-rules.yaml  # 通用抽取与合成规则（GEN-xxx，带 gbt11-ref 追溯字段）
│   │   ├── audit.yaml             # 通用审核准则
│   │   ├── source.csm.md          # 规则源标准 CSM 副本
│   │   ├── source.ssir.json       # 权威 SSIR 文件
│   │   └── source.conversion-report.json  # 转换诊断与来源哈希
│   └── gbt-20001.10-2014/         # 同构规则包（当前仅 source 三件套）
├── industries/                    # 行业规则（规划）：{industry_code}/{pending,approved,rejected}/
├── ontology/                      # 本体文件（规划）：分类树、术语库等平台级资源
└── schemas/                       # 规则文件自身的校验 Schema
    └── audit-rule-set.schema.json
```

## base/gbt-1-1-2020 制品说明

- `requirements.yaml`：从 GB/T 1.1-2020 原文整理的内容、结构与排版要求（GBT-xxx 编号），每条规则的 `source` 字段给出标准章节编号以便追溯。
- `extraction-rules.yaml`：PDF 抽取→CSM→SSIR→PDF 流水线的通用逻辑规则（GEN-xxx），有标准原文对应的条目带 `gbt11-ref` 追溯字段。
- `audit.yaml`：第一份通用审核准则，覆盖基本元数据、结构、编号、内部引用和未识别内容保留；只产生审核发现，不阻断转换。
- `source.*`：GB/T 1.1-2020 的 CSM 规则源副本、权威 SSIR 与转换报告。

GB/T 20001.10 的逐条 Requirement Catalog 后续应从其 SSIR 编译或人工校核，并补齐 requirements/extraction-rules/audit。

## 行业规则生命周期（规划）

行业管理员上传 → 落入 `industries/{code}/pending/` → 系统转换校验通过后由平台管理员批准移入 `approved/`（驳回进 `rejected/`）。规则引擎只从 `approved/` 加载。企业扫描转换时按 **base + industry(所属行业) + tenant profile** 三层合并叠加。

## 验证

```text
PYTHONPATH=src python3 -m leleby_ssir csm parse \
  --input 'rules/base/gbt-1-1-2020/source.csm.md' \
  --output 'rules/base/gbt-1-1-2020/source.ssir.json' \
  --format json
```
