# leleby SSIR Engine — Golden Dataset Specification v0.1

> **文档状态**：正式发布 | **版本**：0.1 | **日期**：2026-08-15
>
> **前置依赖**：
> 1. leleby SSIR Data Model v0.4
> 2. leleby SSIR JSON Schema Specification v0.3
> 3. leleby SSIR Processing Pipeline & Architecture Specification v0.4
> 4. leleby SSIR Round-trip & Conformance Test Specification v0.3
> 5. leleby SSIR Engine — AI Coding Implementation Specification v0.4
>
> **目标读者**：AI Coding Agent / 开发团队 / QA 团队 / 数据集制作人员

> **当前 M1 数据集边界**：M1 使用 CSM Markdown 作为唯一输入，Golden Dataset 的主类别为 `Dataset M-CSM`。现有 PDF/OCR 类 Dataset A/B/C 及 Normative Rendering Dataset E 保留为 M2 及以后使用；M1 不要求准备 PDF、MinerU 输出或 OCR 资产。
>
> M1 的权威输入为 `examples/csm/` 下的 CSM 文件；其期望输出为人工审核后的 SSIR JSON（建议存放于 `fixtures/golden/csm/`），而不是把系统首次生成的 JSON 自动视为 Golden。


## 1. Scope

本规范定义了 leleby SSIR Engine Phase 1 开发中使用的 **Golden Dataset**（黄金数据集）的完整规范，包括：

- 数据集的结构和分类
- 每个数据集的文档清单和特征描述
- Golden SSIR 的格式和制作流程
- 数据集的质量要求
- 数据集的版本管理和维护规则

**Golden Dataset 的核心用途**：

1. **验证 Extraction Fidelity**：作为 Golden Test 的输入，验证 `Std₀ → SSIR₁` 的正确性
2. **验证 Round-trip Preservation**：作为 Round-trip Test 的基准输入
3. **验证 Normative Rendering**：Dataset E 专门用于验证 Rendering Conformance
4. **回归防护**：防止系统修改导致已有功能退化


## 2. Golden Dataset 设计原则

### 2.1 核心原则

| 编号 | 原则 | 说明 |
|------|------|------|
| 1 | **代表性** | 覆盖真实标准文档中出现的所有关键特征 |
| 2 | **稳定性** | 一经确定，非必要不修改；修改需经过评审 |
| 3 | **可追溯性** | 每个 Golden SSIR 标记对应的源文档、版本和创建时间 |
| 4 | **版本管理** | 随系统版本演进，旧版本保留 |
| 5 | **独立性** | Golden 的权威来源是**人工审核 + 独立确认**，不是系统自动生成的 |
| 6 | **可执行性** | 每个 Golden 用例必须能够被自动化测试框架直接执行 |

### 2.2 独立性原则（Golden ≠ 系统输出）

> **Golden Dataset 的权威来源不是系统本身，而是人工审核后的规范基准。**

制作流程：

```
Source Document
       ↓
系统提取（当前稳定版）  ← 辅助工具，不是权威来源
       ↓
SSIR Candidate
       ↓
双人独立审核              ← 人工确认，建立权威
       ↓
审核记录（差异项 + 判定）
       ↓
系统修正（如有）
       ↓
重新提取（如需要）
       ↓
Golden SSIR（冻结版本）   ← 权威基准
```


## 3. Dataset Classification

### 3.1 数据集分类总览

| 数据集 | 名称 | 特征 | 文档数 | 用途 | 优先级 |
|--------|------|------|--------|------|--------|
| **Dataset A** | 普通文本 PDF | 结构清晰，表格简单，正文为主 | ≥ 5 | 基础功能验证 | P0 |
| **Dataset B** | 复杂标准 | 含复杂表格、图、公式、多层列表、附录、引用 | ≥ 3 | 核心能力验证 | P0 |
| **Dataset C** | 扫描 PDF | OCR、低质量文字、混合排版 | ≥ 2 | OCR 鲁棒性验证 | P1 |
| **Dataset D** | 回归测试 | 历史 Bug 修复案例 | 持续增加 | 回归防护 | P0 |
| **Dataset E** | Normative Rendering | 需编号/标点规范化的文档，含规范性动词 | ≥ 1 | Normative Rendering 验证 | P0 |

### 3.2 优先级说明

| 优先级 | 定义 | Phase 1 要求 |
|--------|------|--------------|
| **P0** | 核心能力，必须通过 | 所有 P0 用例必须 100% 通过 |
| **P1** | 重要能力，强烈建议 | ≥ 95% 通过 |
| **P2** | 增强能力，可选 | 不强制 |


## 4. Dataset A — 普通文本 PDF

### 4.1 特征要求

| 特征 | 要求 |
|------|------|
| 文件类型 | 可搜索 PDF（含文本层） |
| 结构 | 章、条、款、项清晰 |
| 表格 | 至少包含 1 个简单表格 |
| 列表 | 至少包含 1 个简单列表 |
| 引用 | 至少包含 1 个内部引用或外部标准引用 |
| 页数 | 10-50 页 |
| 语言 | 中文（优先）或英文 |

### 4.2 文档清单

| 序号 | 文档标识 | 标准号 | 说明 | 优先级 |
|------|----------|--------|------|--------|
| A-01 | GBT-42093.1-2022 | GB/T 42093.1-2022 | 标准文档结构化 元模型 第1部分：全文（已提供） | P0 |
| A-02 | GBT-22373-2021 | GB/T 22373-2021 | 标准文献元数据（已提供） | P0 |
| A-03 | GBT-1.1-2020 | GB/T 1.1-2020 | 标准化工作导则 第1部分（已提供） | P0 |
| A-04 | GBT-47462-2026 | GB/T 47462-2026 | 数字标准 标准信息模型架构（已提供） | P1 |
| A-05 | GBT-YYYYY-20XX | 待补充 | 简单标准（含列表和引用） | P1 |

### 4.3 文件结构

```
fixtures/golden/dataset-A-text-pdf/
│
├── GBT-42093.1-2022/
│   ├── source.pdf                         # 源文档
│   ├── expected.ssir.json                 # Golden SSIR
│   ├── expected.ssir.schema.json          # Schema 验证文件
│   ├── manifest.yaml                      # 数据集描述
│   └── review.log                         # 审核记录
│
├── GBT-22373-2021/
│   └── ...
│
├── GBT-1.1-2020/
│   └── ...
│
├── GBT-47462-2026/
│   └── ...
│
└── manifest.yaml                          # Dataset A 总清单
```


## 5. Dataset B — 复杂标准

### 5.1 特征要求

| 特征 | 要求 |
|------|------|
| 文件类型 | 可搜索 PDF（含文本层） |
| 结构 | 深层嵌套（章/条/款/项 ≥ 4 层） |
| 表格 | 至少包含 2 个表格，其中至少 1 个含合并单元格 |
| 图 | 至少包含 1 个图 |
| 公式 | 至少包含 1 个数学公式 |
| 列表 | 含多层嵌套列表 |
| 附录 | 至少包含 1 个规范性附录或资料性附录 |
| 引用 | 含内部引用和外部标准引用 |
| 注/示例/警示 | 至少包含 1 个注或示例 |
| 页数 | 30-100 页 |

### 5.2 文档清单

| 序号 | 文档标识 | 标准号 | 说明 | 优先级 |
|------|----------|--------|------|--------|
| B-01 | GBT-xxx-complex-01 | 待确定 | 含复杂表格和图的标准 | P0 |
| B-02 | GBT-xxx-complex-02 | 待确定 | 含公式和多层列表的标准 | P0 |
| B-03 | GBT-xxx-complex-03 | 待确定 | 含附录和大量引用的标准 | P1 |

### 5.3 文件结构

```
fixtures/golden/dataset-B-complex/
│
├── GBT-xxx-complex-01/
│   ├── source.pdf
│   ├── expected.ssir.json
│   ├── expected.ssir.schema.json
│   ├── manifest.yaml
│   └── review.log
│
├── ...
│
└── manifest.yaml
```


## 6. Dataset C — 扫描 PDF

### 6.1 特征要求

| 特征 | 要求 |
|------|------|
| 文件类型 | 扫描 PDF（无文本层，或文本层质量差） |
| OCR 需求 | 必须使用 OCR |
| 表格 | 至少包含 1 个表格（OCR 识别挑战） |
| 文字质量 | 包含部分低质量文字或模糊区域 |
| 页数 | 10-50 页 |

### 6.2 文档清单

| 序号 | 文档标识 | 标准号 | 说明 | 优先级 |
|------|----------|--------|------|--------|
| C-01 | GBT-xxx-scanned-01 | 待确定 | 扫描标准样例 | P1 |
| C-02 | GBT-xxx-scanned-02 | 待确定 | 含表格的扫描标准 | P1 |

### 6.3 文件结构

```
fixtures/golden/dataset-C-scanned/
│
├── GBT-xxx-scanned-01/
│   ├── source.pdf
│   ├── expected.ssir.json
│   ├── expected.ssir.schema.json
│   ├── manifest.yaml
│   ├── review.log
│   └── ocr.config.yaml                    # OCR 配置
│
└── manifest.yaml
```


## 7. Dataset D — 回归测试

### 7.1 特征要求

| 特征 | 要求 |
|------|------|
| 来源 | 历史 Bug 修复案例 |
| 特征 | 每个用例对应一个已修复的特定缺陷 |
| 状态 | 持续增加，随 Bug 修复而扩展 |

### 7.2 文档清单

| 序号 | 文档标识 | 关联 Issue | 说明 | 优先级 |
|------|----------|------------|------|--------|
| D-01 | BUG-001 | 待确定 | 表格合并单元格识别失败 | P0 |
| D-02 | BUG-002 | 待确定 | 多层列表标记识别错误 | P0 |
| D-03 | BUG-003 | 待确定 | 跨页表格处理失败 | P1 |
| D-04 | BUG-004 | 待确定 | 公式 rawText 丢失 | P0 |

### 7.3 文件结构

```
fixtures/golden/dataset-D-regression/
│
├── BUG-001/
│   ├── source.pdf
│   ├── expected.ssir.json
│   ├── manifest.yaml
│   └── bug-context.yaml                   # Bug 描述和修复信息
│
└── manifest.yaml
```


## 8. Dataset E — Normative Rendering

### 8.1 特征要求

| 特征 | 要求 |
|------|------|
| 文件类型 | 可搜索 PDF |
| 编号不规范 | 至少包含 1 处需要编号规范化的章节 |
| 标点不规范 | 至少包含 1 处需要标点规范化的文本 |
| 规范性动词 | 至少包含 1 个"应"、"应当"、"必须"等规范性动词 |
| 禁止性表述 | 至少包含 1 个"不得"、"不应"等禁止性表述 |
| 结构 | 包含需要 GB/T 1.1 规范化的结构 |

### 8.2 文档清单

| 序号 | 文档标识 | 标准号 | 说明 | 优先级 |
|------|----------|--------|------|--------|
| E-01 | GBT-xxx-rendering-01 | 待确定 | 含不规范编号和标点的标准 | P0 |

### 8.3 文件结构

```
fixtures/golden/dataset-E-normative-rendering/
│
├── GBT-xxx-rendering-01/
│   ├── source.pdf                         # 含不规范内容的源文档
│   ├── expected.ssir.json                 # Golden SSIR
│   ├── expected.rendering.docx            # 预期渲染结果（GB/T 1.1 样式）
│   ├── expected.rendering.pdf             # 预期渲染结果（PDF）
│   ├── rendering.profile.yaml             # Rendering Profile 配置
│   ├── manifest.yaml
│   └── review.log
│
└── manifest.yaml
```


## 9. Golden SSIR 规范

### 9.1 文件格式

Golden SSIR 必须：
- 符合 JSON Schema v0.3（`ssir.schema.json`）
- 使用 `ssirVersion: "0.4"`
- 包含完整的 `sourceAnchors`（Level 3 要求）
- 包含所有内容元素（Level 2 要求）
- 包含完整的元数据（Level 0 要求）
- 包含完整的结构树（Level 1 要求）

### 9.2 文件命名

```
expected.ssir.json          # 标准命名
expected.ssir.schema.json   # Schema 验证文件
```

### 9.3 Golden SSIR 制作流程

```
Step 1: 选择源文档
        ↓
Step 2: 使用当前稳定版系统提取 SSIR（辅助）
        ↓
Step 3: SSIR Candidate 生成
        ↓
Step 4: 审核员 A 独立审核（标记差异项）
        ↓
Step 5: 审核员 B 独立审核（标记差异项）
        ↓
Step 6: 差异项合并讨论
        ↓
Step 7: 如果是系统缺陷 → 修正系统，返回 Step 2
        ↓
Step 8: 如果是人工判定 → 记录判定结果
        ↓
Step 9: 双方确认 → Golden SSIR 冻结
        ↓
Step 10: 提交版本管理
```

### 9.4 审核检查清单

| 检查项 | 方法 | 通过标准 |
|--------|------|----------|
| Metadata | 人工核对 | 所有字段正确 |
| Structure | 人工核对 + 自动化 | 章节数量、编号、层级正确 |
| Content | 人工核对 | 所有段落、列表、表格、图、公式存在 |
| Tables | 人工核对 | 行、列、合并单元格、表头、表注正确 |
| Figures | 人工核对 | 图编号、图题正确 |
| Formulas | 人工核对 | rawText 非空，编号正确 |
| References | 人工核对 | rawTarget 正确 |
| SourceAnchors | 自动化 | 所有核心对象有 SourceAnchor |
| Schema | 自动化 | 通过 JSON Schema v0.3 验证 |

### 9.5 审核记录格式

```yaml
# review.log
golden_ssir:
  document_id: "ssir:GBT-42093.1-2022"
  created_at: "2026-08-15T10:30:00Z"
  created_by: "reviewer-a"

reviewers:
  - name: "审核员A"
    review_date: "2026-08-15T10:00:00Z"
    findings:
      - "5.2 条款编号正确"
      - "表1 合并单元格正确"
    status: "approved"

  - name: "审核员B"
    review_date: "2026-08-15T11:00:00Z"
    findings:
      - "5.2 条款编号正确"
      - "表1 合并单元格正确"
    status: "approved"

system_iterations:
  - version: "v0.1.0"
    issues_found:
      - "表格合并单元格处理缺失"
    fixed: true

final_status: "frozen"
frozen_at: "2026-08-15T12:00:00Z"
```


## 10. Dataset Manifest 格式

### 10.1 总清单 (manifest.yaml)

```yaml
# fixtures/golden/manifest.yaml
dataset:
  name: "leleby SSIR Golden Dataset"
  version: "1.0"
  created_at: "2026-08-15"
  description: "用于 SSIR Engine Phase 1 的黄金数据集"

subsets:
  - name: "dataset-A-text-pdf"
    description: "普通文本 PDF，结构清晰，表格简单"
    priority: "P0"
    doc_count: 5
    required_pass_rate: 1.0

  - name: "dataset-B-complex"
    description: "含复杂表格、图、公式、多层列表、附录、引用"
    priority: "P0"
    doc_count: 3
    required_pass_rate: 0.98

  - name: "dataset-C-scanned"
    description: "扫描 PDF、OCR、低质量文字"
    priority: "P1"
    doc_count: 2
    required_pass_rate: 0.95

  - name: "dataset-D-regression"
    description: "历史 Bug 修复案例"
    priority: "P0"
    doc_count: "持续增加"
    required_pass_rate: 1.0

  - name: "dataset-E-normative-rendering"
    description: "Normative Rendering 验证文档"
    priority: "P0"
    doc_count: 1
    required_pass_rate: 1.0
```

### 10.2 子集清单 (subset/manifest.yaml)

```yaml
# fixtures/golden/dataset-A-text-pdf/manifest.yaml
subset:
  name: "dataset-A-text-pdf"
  version: "1.0"
  description: "普通文本 PDF"

documents:
  - id: "GBT-42093.1-2022"
    file: "GBT-42093.1-2022/source.pdf"
    expected: "GBT-42093.1-2022/expected.ssir.json"
    schema: "GBT-42093.1-2022/expected.ssir.schema.json"
    review_log: "GBT-42093.1-2022/review.log"
    features:
      - text_pdf
      - multi_section
      - references
      - tables
    expected_level: "Level3"
    priority: "P0"

  - id: "GBT-22373-2021"
    file: "GBT-22373-2021/source.pdf"
    expected: "GBT-22373-2021/expected.ssir.json"
    schema: "GBT-22373-2021/expected.ssir.schema.json"
    review_log: "GBT-22373-2021/review.log"
    features:
      - text_pdf
      - tables
      - metadata
    expected_level: "Level3"
    priority: "P0"

  # ... 更多文档
```


## 11. Feature Coverage Matrix

### 11.1 数据集特征覆盖

| Feature | A | B | C | D | E | 说明 |
|---------|---|---|---|---|---|------|
| Metadata | ✓ | ✓ | ✓ | ✓ | ✓ | 文档身份和元数据 |
| Multi-level Structure | ✓ | ✓ | ✓ | ✓ | ✓ | 章/条/款/项 |
| Paragraph | ✓ | ✓ | ✓ | ✓ | ✓ | 普通段落 |
| Heading | ✓ | ✓ | ✓ | ✓ | ✓ | 标题 |
| Simple Table | ✓ | ✓ | | ✓ | | 无合并单元格 |
| Complex Table (merged) | | ✓ | | ✓ | | 含合并单元格 |
| Cross-page Table | | ✓ | | | | 跨页表格 |
| Figure | | ✓ | | ✓ | | 图 + 图题 |
| Formula | | ✓ | | ✓ | | 公式 + rawText |
| Simple List | ✓ | ✓ | ✓ | ✓ | | 单层列表 |
| Nested List | | ✓ | | ✓ | | 多层嵌套列表 |
| Normative Reference | ✓ | ✓ | | ✓ | | 规范性引用 |
| Internal Reference | ✓ | ✓ | | ✓ | | 内部引用 |
| Appendix | | ✓ | | | | 附录 |
| Note | | ✓ | | | | 注 |
| Example | | ✓ | | | | 示例 |
| Warning | | ✓ | | | | 警示 |
| OCR | | | ✓ | | | 扫描 PDF + OCR |
| **Normative Rendering** | | | | | ✓ | 编号/标点规范化 |
| **FORBIDDEN_CHANGES** | | | | | ✓ | 规范性动词不变 |

### 11.2 覆盖率要求

| 特征类别 | 覆盖率要求 |
|----------|-----------|
| 文档元数据 | 100%（所有文档） |
| 逻辑结构 | 100%（所有文档） |
| 内容类型 | ≥ 80%（所有文档类型合计） |
| 表格 | ≥ 60%（含复杂表格） |
| 引用 | ≥ 50%（含规范性引用） |
| 特殊元素 | ≥ 50%（图/公式/附录） |


## 12. Feature Coverage Matrix

### 12.1 数据集特征覆盖

| Feature | A | B | C | D | E | 说明 |
|---------|---|---|---|---|---|------|
| Metadata | ✓ | ✓ | ✓ | ✓ | ✓ | 文档身份和元数据 |
| Multi-level Structure | ✓ | ✓ | ✓ | ✓ | ✓ | 章/条/款/项 |
| Paragraph | ✓ | ✓ | ✓ | ✓ | ✓ | 普通段落 |
| Heading | ✓ | ✓ | ✓ | ✓ | ✓ | 标题 |
| Simple Table | ✓ | ✓ | | ✓ | | 无合并单元格 |
| Complex Table (merged) | | ✓ | | ✓ | | 含合并单元格 |
| Cross-page Table | | ✓ | | | | 跨页表格 |
| Figure | | ✓ | | ✓ | | 图 + 图题 |
| Formula | | ✓ | | ✓ | | 公式 + rawText |
| Simple List | ✓ | ✓ | ✓ | ✓ | | 单层列表 |
| Nested List | | ✓ | | ✓ | | 多层嵌套列表 |
| Normative Reference | ✓ | ✓ | | ✓ | | 规范性引用 |
| Internal Reference | ✓ | ✓ | | ✓ | | 内部引用 |
| Appendix | | ✓ | | | | 附录 |
| Note | | ✓ | | | | 注 |
| Example | | ✓ | | | | 示例 |
| Warning | | ✓ | | | | 警示 |
| OCR | | | ✓ | | | 扫描 PDF + OCR |
| **Normative Rendering** | | | | | ✓ | 编号/标点规范化 |
| **FORBIDDEN_CHANGES** | | | | | ✓ | 规范性动词不变 |

### 12.2 覆盖率要求

| 特征类别 | 覆盖率要求 |
|----------|-----------|
| 文档元数据 | 100%（所有文档） |
| 逻辑结构 | 100%（所有文档） |
| 内容类型 | ≥ 80%（所有文档类型合计） |
| 表格 | ≥ 60%（含复杂表格） |
| 引用 | ≥ 50%（含规范性引用） |
| 特殊元素 | ≥ 50%（图/公式/附录） |


## 13. Golden Dataset Quality Requirements

### 13.1 文档质量要求

| 要求 | 标准 |
|------|------|
| 源文档完整性 | 无缺页、无损坏 |
| 源文档清晰度 | 文字清晰可读（扫描 PDF 需 ≥ 300 DPI） |
| 文档来源 | 优先使用官方发布版本 |
| 文档版本 | 记录准确的版本信息 |

### 13.2 Golden SSIR 质量要求

| 要求 | 标准 |
|------|------|
| Schema 合规 | 100% 通过 JSON Schema v0.3 验证 |
| 结构完整性 | 100% 结构节点正确 |
| 内容完整性 | ≥ 99% 内容元素正确 |
| 溯源完整性 | 100% 核心对象有 SourceAnchor |
| 人工审核 | 至少 2 人独立审核，无分歧 |

### 13.3 审核通过标准

| 审核项 | 通过标准 |
|--------|----------|
| 双人审核一致性 | 无重大分歧 |
| 系统提取正确性 | 提取结果与源文档一致 |
| Schema 验证 | 全部通过 |
| 结构验证 | 全部通过 |
| 内容验证 | ≥ 99% 匹配 |


## 14. Version Management

### 14.1 版本号规则

Golden Dataset 使用语义化版本号：`MAJOR.MINOR.PATCH`

| 版本号类型 | 变更类型 | 示例 |
|-----------|----------|------|
| **MAJOR** | 数据集结构重大变更、文档增删 | 1.0.0 → 2.0.0 |
| **MINOR** | 新增文档、新增特征 | 1.0.0 → 1.1.0 |
| **PATCH** | Golden SSIR 修正（不改变特征） | 1.0.0 → 1.0.1 |

### 14.2 版本记录

每次数据集变更必须记录：

```yaml
# version-history.yaml
version_history:
  - version: "1.0.0"
    date: "2026-08-15"
    changes:
      - "初始版本"
      - "Dataset A: 5 个文档"
      - "Dataset B: 3 个文档"
      - "Dataset C: 2 个文档"
      - "Dataset D: 4 个 Bug 用例"
      - "Dataset E: 1 个文档"
    status: "frozen"

  - version: "1.1.0"
    date: "2026-09-01"
    changes:
      - "新增 Dataset A-05 (GBT-YYYYY-20XX)"
      - "修正 Dataset B-01 Golden SSIR 中表格合并单元格"
    status: "draft"
```

### 14.3 版本标签

在 Git 中使用标签管理：

```
git tag -a golden-v1.0.0 -m "Golden Dataset v1.0.0"
```


## 15. Test Execution

### 15.1 Golden Test 执行流程

```python
# tests/golden/test_golden.py
def test_golden_dataset():
    for doc in load_manifest():
        # 1. 提取 SSIR
        ssir = extractor.extract(doc.source_path)
        
        # 2. 加载 Golden SSIR
        golden = load_golden(doc.expected_path)
        
        # 3. 比较
        result = comparator.compare(ssir, golden)
        
        # 4. 断言
        assert result.identity.status == "PASS"
        assert result.structure.status == "PASS"
        assert result.content.match_rate >= doc.required_pass_rate
```

### 15.2 测试报告

Golden Test 执行后生成报告：

```json
{
  "test_run": "2026-08-15T14:30:00Z",
  "dataset": "dataset-A-text-pdf",
  "results": {
    "GBT-42093.1-2022": {
      "status": "PASS",
      "identity": "PASS",
      "structure": "PASS",
      "content": {"match_rate": 1.0, "total": 1520, "matched": 1520}
    },
    "GBT-22373-2021": {
      "status": "PASS",
      "identity": "PASS",
      "structure": "PASS",
      "content": {"match_rate": 1.0, "total": 840, "matched": 840}
    }
  },
  "overall_status": "PASS",
  "pass_rate": 1.0,
  "required_pass_rate": 1.0
}
```


## 16. Maintenance

### 16.1 年度审查

- 每年至少审查一次 Golden Dataset
- 检查文档是否仍可获取
- 检查文档是否有新版本
- 检查 Golden SSIR 是否仍符合最新规范

### 16.2 变更管理

任何 Golden Dataset 变更必须：
1. 创建变更请求（CR）
2. 经过评审
3. 更新版本号
4. 更新文档
5. 通知相关方

### 16.3 备份与归档

- 所有 Golden Dataset 必须纳入版本控制
- 源文档和 Golden SSIR 同步备份
- 历史版本保留至少 3 个 major 版本


## 17. Version History

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 0.1 | 2026-08-15 | 初始版本，定义 5 个数据集（A/B/C/D/E）的分类、结构、制作流程和质量要求 |


## 18. Next Steps

1. **Review & Freeze**: 本规范评审并冻结
2. **收集源文档**: 根据文档清单收集所有源文档
3. **制作 Golden SSIR**: 按照制作流程生成所有 Golden SSIR
4. **审核确认**: 双人独立审核所有 Golden SSIR
5. **版本标记**: 标记 Golden Dataset v1.0.0
6. **集成到 CI**: 将 Golden Test 集成到 CI Pipeline
