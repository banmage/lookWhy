# 11. leleby 多租户存储与规则目录规范 v0.1

> 状态：设计稿（已落地第一阶段目录迁移）
> 适用：lookWhy / leleby SSIR Engine 及未来的多租户应用系统
> 关联文档：03（流水线架构）、06（API 契约）

## 1. 设计原则

1. **规则与数据分离**：`rules/` 是系统加载的"程序"（业务规则、本体），`corpus/` 是平台基准语料，`storage/` 是用户上传的运行时"数据"。三者生命周期与管辖角色不同。
2. **租户隔离**：企业数据全部位于 `storage/tenants/{tenant_id}/` 之下；跨租户访问由应用层强制拒绝。企业不可见平台级 `rules/`、`config/`、`corpus/` 的写接口。
3. **状态可追溯**：行业规则带"上传→转换→待批→批准/驳回"生命周期，用子目录表达状态。
4. **规则三层叠加**：企业执行扫描转换时，生效规则 = base（通用）+ industry（所属行业，仅 approved）+ tenant profile（企业编排规则）。后层覆盖前层的同 ID 规则。

## 2. 目录布局

```
lookwhy/
├── src/leleby_ssir/              # 核心引擎
├── tools/                        # 运维脚本
├── config/                       # 引擎配置（非业务规则）
│   ├── rendering/                # 渲染 profile（gb-t-1-1-2020.yaml）
│   └── pipeline/                 # 审核组合配置（audit-profile-*.yaml）
├── rules/                        # ★ 规则库
│   ├── base/{standard-id}/       # 通用规则包（场景 a）
│   │   ├── requirements.yaml     # 结构化规则要求（GBT-xxx + source 章节追溯）
│   │   ├── extraction-rules.yaml # 抽取/合成通用规则（GEN-xxx + gbt11-ref）
│   │   ├── audit.yaml            # 审核准则
│   │   └── source.{csm.md,ssir.json,parse-report.json}
│   ├── industries/{code}/        # 行业规则（场景 b）
│   │   ├── pending/  approved/  rejected/
│   ├── ontology/                 # 本体文件（分类树、术语库）
│   └── schemas/                  # 规则文件自身 Schema（audit-rule-set.schema.json 等）
├── corpus/
│   ├── reference-standards/      # 参考标准全文（只读）
│   └── golden/                   # 黄金样本、CSM 模板、批量回环输入（csm/）
├── storage/tenants/{tenant_id}/  # ★ 租户运行时存储（gitignore）
│   ├── uploads/{yyyy}/{mm}/{batch_id}/   # 原始上传
│   ├── work/                     # MinerU parts、assets、content_list 等中间产物
│   ├── outputs/                  # csm/canonical/render.md/ssir.json/verify.json/pdf/各类报告
│   └── profile/                  # 本企业编排格式规则（审核通过后生效）
└── docs/                         # 项目文档（本文档所在）
```

## 3. 与业务场景的对应

| 场景 | 角色 | 落点 | 生效方式 |
|---|---|---|---|
| a) 上传通用规则/本体 | 平台管理员 | `rules/base/{standard-id}/`、`rules/ontology/` | 识别校验通过后注册加载，全局生效 |
| b) 上传行业规则 | 行业管理员 | `rules/industries/{code}/pending/` → 转换校验 → 平台管理员批准 → `approved/`（驳回 `rejected/`） | 仅 `approved/` 被规则引擎加载 |
| c) 上传企业文件 | 企业用户 | `storage/tenants/{tid}/uploads/...`；企业编排格式经审核放 `profile/` | 三层合并后扫描转换为本企业 SSIR |

## 4. 支持的原始文件格式

`uploads/` 接受：`pdf_img`（扫描 PDF）、`pdf_txt`（文本 PDF）、`docx`、`rtf`、`txt`、`markdown`，以及符合规范的 `SSIR_md`（CSM）与 `SSIR_Json`。格式由应用层按扩展名 + 内容嗅探判定，并记录进批次清单。

## 5. 迁移对照表（v0.5 仓库 → 本方案）

| 旧路径 | 新路径 |
|---|---|
| `rules/generic-extraction-rules.yaml` | `rules/base/gbt-1-1-2020/extraction-rules.yaml` |
| `rules/gbt-1-1-2020-requirements.yaml` | `rules/base/gbt-1-1-2020/requirements.yaml` |
| `rules/general-standard-audit.yaml` | `rules/base/gbt-1-1-2020/audit.yaml` |
| `rules/sources/GBT 1.1-2020.*` | `rules/base/gbt-1-1-2020/source.*` |
| `rules/sources/GBT 20001.10-2014.*` | `rules/base/gbt-20001.10-2014/source.*` |
| `rules/rendering/gb-t-1-1-2020.yaml` | `config/rendering/gb-t-1-1-2020.yaml` |
| `rules/profiles/*.yaml` | `config/pipeline/audit-profile-*.yaml` |
| `examples/*` | `corpus/golden/*` |
| `examples/csm/*` | `corpus/golden/csm/*` |
| `standards/*` | `corpus/reference-standards/*` |
| `out/mineru/*`（开发产物） | `storage/tenants/{tid}/{work,outputs}/` |

代码引用同步：`pdf_renderer.DEFAULT_PROFILE` 指向 `config/rendering/`；审核 profile 内 `source:` 已更新；测试样例路径指向 `corpus/golden/`。

## 6. 待实现项

- [ ] `src/leleby_ssir/rules_engine.py`：三层规则装载与合并器。
- [ ] 行业规则的 pending→approved 状态机（可由应用 DB 驱动，目录仅作归档视图）。
- [ ] `rules/schemas/industry-rule.schema.json`、`ontology.schema.json`。
- [ ] 上传批次清单（batch manifest）：记录原始文件名、格式嗅探结果、sha256、提交者。
