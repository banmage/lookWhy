# leleby SSIR Round-trip & Conformance Test Specification v0.3

> **文档状态**：正式发布 | **版本**：0.3 | **日期**：2026-08-15
>
> **v0.3 主要修订**（基于 Data Model v0.4 和 JSON Schema v0.3 的对齐）：
> - **更新 §2 Normative References**：增加 JSON Schema Specification v0.3 引用
> - **更新 §4 Conformance Model**：增加 Normative Rendering 支持声明和 FORBIDDEN_CHANGES 合规性要求
> - **更新 §5 SSIR Equivalence Model**：增加 Critical Information Loss 检查项清单（12 项）
> - **更新 §6 Information Preservation Contract**：明确 ALLOWED_NORMALIZATIONS 与 FORBIDDEN_CHANGES 边界
> - **新增 §10 Normative Rendering Conformance Test**：重命名并增强，增加 Profile 验证和 Negative Test
> - **更新 §14 Schema Conformance Test**：增加 v0.3 新字段（ssirVersion: "0.4"、NormativeRenderingProfile、QualityAssessment.renderingProfile）验证
> - **更新 §8 Golden Dataset**：增加 Normative Rendering 测试文档要求
> - **更新 §22 Test Cases Catalog**：新增 Normative Rendering 测试用例（NR-001～NR-004、RT-009）

> **当前 M1 测试范围**：只验收 `CSM Markdown → SSIR JSON`。CSM 语法/结构/内容/产品标准质量提示、JSON Schema、Markdown 溯源和确定性输出属于 M1；PDF、MinerU、OCR、DOCX、Normative Rendering 和 Round-trip 测试暂列 M2，不得阻塞 M1。
>
> M1 的权威测试输入为 `examples/csm/Q_PMRZ_9-2024.csm.md` 与 `examples/csm/Q_TQDZ_004-2026.csm.md`；模板文件只用于输入契约测试，不直接作为 Golden SSIR。


## 1. Scope

本规范定义了 leleby SSIR（Standard Structured Information Representation）Round-trip Digitalization Engine 的测试策略、测试方法、一致性要求与验收标准。

本规范适用于 Phase 1 开发中的以下测试活动：

- Schema Conformance Test
- Unit Test
- Integration Test
- Extraction Fidelity Test
- Normative Rendering Conformance Test
- Round-trip Preservation Test
- Normalization Stability Test
- E2E Acceptance Test
- Regression Test
- Negative & Robustness Test
- Performance Test

**本规范的核心目标**：验证 SSIR 处理引擎是否满足 **Round-trip Preservation** 原则——即 SSIR 经传统文档渲染、规范化及再次提取后，其核心信息、结构和语义应保持不变。

**Round-trip 核心定义**：

```
Std₀ → SSIR₁ → Std₁ → SSIR₂

验证目标：SSIR₁ ≈ SSIR₂（SSIR Semantic Equivalence）
而非：Std₀ ≈ Std₁（文档外观等价）
```

其中：
- `Std₀`：原始源文档
- `SSIR₁`：从 Std₀ 提取的信息基准状态
- `Std₁`：从 SSIR₁ 渲染生成的规范化文档（**Normative Rendering**，依据 GB/T 1.1-2020 等 Rendering Profile）
- `SSIR₂`：从 Std₁ 再次提取的恢复状态

**关键原则**：传统文档是可变的表现层（Document Representation），SSIR 才是需要保持稳定的信息层（Information Representation）。因此 `Std₀` 与 `Std₁` 的差异不必然表示 Round-trip 失败。


## 2. Normative References

| 文档 | 说明 |
|------|------|
| leleby SSIR Data Model v0.4 | SSIR 核心数据模型定义 |
| leleby SSIR JSON Schema Specification v0.3 | SSIR JSON 序列化与验证规范 |
| leleby SSIR Processing Pipeline & Architecture Specification v0.3 | 处理流水线与系统架构 |
| GB/T 1.1-2020 | 标准化工作导则 第1部分：标准化文件的结构和起草规则 |


## 3. Terms and Definitions

| 术语 | 定义 |
|------|------|
| **Golden Dataset** | 一组预先选定的、具有已知特征的标准文档集合，用于验证系统的正确性 |
| **Golden SSIR** | 从 Golden Dataset 中提取的、经过人工审核确认为正确的 SSIR 实例。既是 Extraction 的 Expected，也是 Round-trip 的 Reference State |
| **Round-trip Preservation** | SSIR 经传统文档渲染、规范化及再次提取后，其核心信息、结构和语义应保持不变的属性 |
| **Round-trip Completeness** | SSIR₁ 中的信息元素在 SSIR₂ 中被成功恢复的程度 |
| **SSIR Semantic Equivalence** | 两个 SSIR 实例在身份、结构、内容、关系层面等价，忽略非语义差异（如 ID、时间戳、坐标） |
| **Extraction Fidelity** | Std₀ → SSIR₁ 的正确程度 |
| **Normative Rendering Conformance** | SSIR₁ → Std₁ 是否符合目标规范（如 GB/T 1.1-2020），且遵循 ALLOWED_NORMALIZATIONS / FORBIDDEN_CHANGES 边界 |
| **Normalization Stability** | 系统在多次 `SSIR → 渲染 → 提取` 循环后是否收敛到稳定状态 |
| **Normalization Fixed Point** | 系统达到稳定状态，后续循环不再产生变化 |
| **Critical Information Loss** | 规范性要求、禁止性条款、强制条件、数值、单位、比较符、引用目标等关键信息的丢失或改变 |
| **SSIR Comparator** | 比较两个 SSIR 实例，判断其在语义上是否等价的模块 |
| **ALLOWED_NORMALIZATIONS** | 渲染过程中允许的规范化操作列表（Data Model v0.4 §7.3） |
| **FORBIDDEN_CHANGES** | 渲染过程中绝对禁止的语义变化列表（Data Model v0.4 §7.3） |


## 4. Conformance Model

### 4.1 Conformance Classes

| Conformance Class | 支持的 SSIR Level | Normative Rendering 支持 | 描述 |
|-------------------|-------------------|--------------------------|------|
| **Core** | L0-L3 | 必须支持 GB/T 1.1-2020 | 支持完整的 Core Pipeline（Metadata → Structure → Content → Provenance），通过所有 P0 测试，支持 Round-trip Preservation，且 Normative Rendering 不违反 FORBIDDEN_CHANGES |
| **Full** | L0-L4 | 必须支持 GB/T 1.1-2020 + 可扩展 | Core + 支持 Semantic Enrichment（Reference/Entity/Relation），通过所有 P0+P1 测试 |
| **Extended** | L0-L4+ | 支持多种 Profile | Full + 支持额外文档类型（法规/企业标准/合同/测试报告等）和更多 Rendering Profiles，通过所有测试用例 |

### 4.2 声明规则

> 一个实现应声明其支持的 **SSIR Preservation Level**、**Conformance Class** 以及 **Normative Rendering Profiles**。测试规范验证声明是否属实。

### 4.3 FORBIDDEN_CHANGES 合规性声明

任何宣称 Core Conformant 或更高的实现，必须声明其 Normative Rendering 实现**不会**执行 Data Model v0.4 §7.3 中定义的任何 FORBIDDEN_CHANGES。

### 4.4 映射关系

| 测试类别 | 验证的能力 | 对应 Conformance |
|----------|-----------|------------------|
| Schema Conformance | JSON Schema 合规性（含 v0.3 新字段） | 所有等级 |
| Extraction Fidelity | Std₀ → SSIR₁ | 所有等级 |
| Normative Rendering Conformance | SSIR₁ → Std₁（含 ALLOWED_NORMALIZATIONS / FORBIDDEN_CHANGES） | Core 及以上 |
| Round-trip Preservation | SSIR₁ ≈ SSIR₂ | Core 及以上 |
| Normalization Stability | 系统收敛性 | Core 及以上 |
| Semantic Enrichment | L4 能力 | Full 及以上 |


## 5. SSIR Equivalence Model

> **SSIR Semantic Equivalence** 是两个 SSIR 实例在语义上等价的正式定义。

### 5.1 Identity Equivalence

| 检查项 | 方法 | 允许差异 |
|--------|------|----------|
| documentIdentifier | exact | 无 |
| title | exact | 无 |
| titleEn | exact | 无 |
| publicationDate | exact | 无 |
| effectiveDate | exact | 无 |
| issuer | exact | 无 |
| standardNumber | exact | 无 |
| CCS/ICS | exact | 无 |

### 5.2 Structural Equivalence

| 检查项 | 方法 | 允许差异 |
|--------|------|----------|
| 节点数量 | count | 无 |
| 节点类型 | exact | 无 |
| 父子关系 | exact | 无 |
| 层级深度 | exact | 无 |
| 编号 | exact | 无 |
| 逻辑顺序 | exact | 无 |

### 5.3 Content Equivalence

| 检查项 | 方法 | 允许差异 |
|--------|------|----------|
| Paragraph | 规范化文本比较 | 空格/换行 |
| Heading | 规范化文本比较 | 空格/换行 |
| Table | 结构 + 单元格内容 | 空格/换行 |
| Figure | 数量 + 编号 + 图题 | 空格/换行 |
| Formula | 数量 + 编号 + rawText | 空格/换行 |
| List | 层级 + marker + 文本 | 标记样式变体 |
| Note/Example/Warning | 规范化文本比较 | 空格/换行 |

### 5.4 Relationship Equivalence

| 检查项 | 方法 | 允许差异 |
|--------|------|----------|
| Reference | 数量 + rawTarget | 无 |
| DocumentRelationship | 数量 + relationType + target | 无 |

### 5.5 Critical Information Loss — 检查项清单（Data Model v0.4 §7.3）

Round-trip 测试必须执行以下 12 项 Critical Information Loss 检查。任何一项检查发现变化，Round-trip 直接 **FAIL**。

| 编号 | 检查项 | 说明 | 示例 |
|------|--------|------|------|
| C1 | Normative Wording | 规范性动词不得改变 | "应" → "宜" = FAIL |
| C2 | Prohibitions | 禁止性表述不得改变 | "不得" → "不应" = FAIL |
| C3 | Mandatory Conditions | 强制条件不得改变 | "在...条件下" 被删除 = FAIL |
| C4 | Numerical Values | 数值不得改变 | 90 → 80 = FAIL |
| C5 | Units | 单位不得改变 | MPa → kPa = FAIL |
| C6 | Comparison Operators | 比较符不得改变 | ≥ → > = FAIL |
| C7 | Clause Identifiers | 条款编号不得改变 | 5.2.1 → 5.2 = FAIL |
| C8 | Table Cell Content | 表格单元格内容不得改变 | 任何内容变化 = FAIL |
| C9 | Formula Raw Representation | 公式原始表示不得改变 | 任何变化 = FAIL |
| C10 | Reference Raw Target | 引用原始文本不得改变 | 任何变化 = FAIL |
| C11 | Scope | 范围声明不得改变 | 任何变化 = FAIL |
| C12 | Applicability | 适用性声明不得改变 | 任何变化 = FAIL |

### 5.6 Normalization Rules

比较前必须应用以下归一化：

| 规则 | 说明 | 对应 ALLOWED_NORMALIZATIONS |
|------|------|------------------------------|
| Whitespace | 多个空格 → 单个空格，去除行首/行尾空格 | whitespace_normalization |
| Line breaks | 统一为 `\n` | line_break_unification |
| Unicode | NFC 规范化 | — |
| Dashes | `—` 与 `-` 可归一化（非标识符上下文） | punctuation_normalization |
| Quotation marks | 统一为 `"`（非特殊上下文） | punctuation_normalization |
| Number format | 数字格式可规范化 | number_format_normalization |
| Unit abbreviation | 单位缩写可规范化 | unit_abbreviation_normalization |
| Reference separator | 引用分隔符可规范化 | reference_separator_normalization |

**重要限制**：归一化不适用于：
- 标准编号中的连字符
- 公式中的符号
- 数值和单位（除非是格式规范化）
- 标识符
- 引用目标
- 规范性动词（受 FORBIDDEN_CHANGES 保护）

### 5.7 Non-preservable Properties

以下属性在 Equivalence 比较中**不要求**保持一致：

- 所有 `id` 字段
- `createdAt` / `updatedAt` / `timestamp`
- `processingRuns` 中的 `id`、`timestamp`、`durationSeconds`
- `sourceAnchors` 中的 `pdfPageIndex`、`bbox`、`sourceBlockId`
- `sourceFiles` 中的 `filePath`/`storageUri`
- `qualityAssessments`（重新评估结果不同）
- `preservationLevel`（由比较结果重新判定）
- 渲染后的页码、分页、字体、字号、行距
- 任何派生/计算字段


## 6. Information Preservation Contract

> 本 Contract 定义 SSIR 转换周期中各元素的保存要求。

### 6.1 Preservation Classes

| 类别 | 定义 | 失败处理 |
|------|------|----------|
| **CRITICAL** | 信息丢失或改变将导致标准语义失效 | Round-trip 直接 FAIL |
| **REQUIRED** | 信息应完整保留，可接受规范化差异 | Round-trip 可能 WARN 或 FAIL |
| **OPTIONAL** | 信息鼓励保留但不强制 | 不影响 Conformance |
| **NON-PRESERVABLE** | 信息必然变化，不比较 | 忽略差异 |

### 6.2 Critical Information（零损失要求）

见 §5.5 的 12 项检查清单。

**规则**：任何 CRITICAL 信息的丢失或改变 → Round-trip 直接 **FAIL**，不被总体 Match Rate 抵消。

### 6.3 Required Information（对应 ALLOWED_NORMALIZATIONS）

| 类别 | 允许差异 | 对应规范化规则 |
|------|----------|----------------|
| 结构节点 | 无 | — |
| 段落文本 | 空格/换行 | whitespace_normalization, line_break_unification |
| 列表标记 | 样式变体 | — |
| 图题/表题 | 空格/换行 | whitespace_normalization |
| 资料性注释 | 空格/换行 | whitespace_normalization |
| 标点 | 规范化 | punctuation_normalization |
| 数字格式 | 格式变化 | number_format_normalization |
| 单位表示 | 缩写变化 | unit_abbreviation_normalization |
| 引用分隔符 | 格式变化 | reference_separator_normalization |

### 6.4 MUST NOT CHANGE（对应 FORBIDDEN_CHANGES）

Data Model v0.4 §7.3 定义的 12 项绝对禁止变化：

| 编号 | 禁止变化 |
|------|----------|
| F1 | normative_verb_change（应 → 宜） |
| F2 | prohibition_change（不得 → 不应） |
| F3 | numeric_value_change（90 → 80） |
| F4 | unit_change（MPa → kPa） |
| F5 | comparison_operator_change（≥ → >） |
| F6 | clause_identifier_change（5.2.1 → 5.2） |
| F7 | table_cell_content_change |
| F8 | formula_raw_change |
| F9 | reference_raw_change |
| F10 | scope_change |
| F11 | applicability_change |
| F12 | mandatory_condition_change |

### 6.5 Optional Information

- 特定格式的页眉/页脚
- 原始 PDF 的分页信息（渲染后必变）
- 字体样式细节
- 缩进数值

### 6.6 Non-preservable Information

- 所有 `id` 值
- `createdAt` / `updatedAt`
- `processingRun` 的 `timestamp`、`id`
- `sourceAnchor` 的 `bbox`、`pdfPageIndex`、`sourceBlockId`
- `sourceFile` 的 `filePath`/`storageUri`
- 任何派生字段


## 7. Testing Strategy

### 7.1 Test Pyramid

```
                    ┌─────────────────────┐
                    │   E2E / Round-trip  │  ← 验收级
                    │    (少而全)          │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │   Integration Tests │  ← 集成级
                    │   (模块间接口)       │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │    Unit Tests       │  ← 单元级
                    │    (按能力覆盖)      │
                    └─────────────────────┘
```

### 7.2 Test Layers

| 层 | 测试类型 | 职责 |
|----|----------|------|
| L1 | Schema Conformance | JSON Schema 合规性（含 v0.3 新字段） |
| L2 | Unit Test | 核心处理组件正确性 |
| L3 | Integration Test | 模块间接口正确性 |
| L4 | Extraction Fidelity | Std₀ → SSIR₁ 正确性 |
| L5 | Normative Rendering Conformance | SSIR₁ → Std₁ 合规性（含 ALLOWED_NORMALIZATIONS / FORBIDDEN_CHANGES） |
| L6 | Round-trip Preservation | SSIR₁ ≈ SSIR₂ |
| L7 | Normalization Stability | 系统收敛性 |
| L8 | E2E Acceptance | 完整业务路径 |
| L9 | Regression | 无退化 |
| L10 | Negative/Robustness | 错误输入处理 |

### 7.3 四柱测试体系

| 测试支柱 | 链路 | 核心问题 |
|----------|------|----------|
| **Extraction Fidelity Test** | `Std₀ → SSIR₁` | 是否正确理解原文？ |
| **Normative Rendering Conformance Test** | `SSIR₁ → Std₁` | 输出是否符合规范且不违反 FORBIDDEN_CHANGES？ |
| **Round-trip Preservation Test** | `SSIR₁ → Std₁ → SSIR₂` | 信息是否丢失？ |
| **Normalization Stability Test** | `SSIR₁ → Std₁ → SSIR₂ → Std₂ → SSIR₃` | 系统是否收敛稳定？ |


## 8. Golden Dataset

### 8.1 设计原则

1. **代表性**：覆盖真实标准文档中出现的所有关键特征
2. **稳定性**：一经确定，非必要不修改；修改需经过评审
3. **可追溯性**：每个 Golden SSIR 标记对应的源文档、版本和创建时间
4. **版本管理**：随系统版本演进，旧版本保留
5. **Golden 独立性**：Golden 的权威来源不是系统本身，而是**人工审核 + 独立确认**
6. **Normative Rendering 覆盖**：至少包含一份需要编号规范化、标点规范化、包含规范性动词的标准文档

### 8.2 Golden 制作流程

```
Source Document
       ↓
系统提取（当前稳定版）
       ↓
SSIR Candidate
       ↓
双人审核（独立进行）
       ↓
审核记录（差异项 + 判定）
       ↓
系统修正（如有）
       ↓
重新提取（如需要）
       ↓
Golden SSIR（冻结版本）
```

**关键原则**：`Golden SSIR` 是**人工确认的正确 SSIR**，不是"系统认为正确的答案"。

### 8.3 数据集分类

| 数据集 | 特征 | 最少文档数 | 用途 |
|--------|------|------------|------|
| **Dataset A** | 普通文本 PDF，结构清晰，表格简单 | ≥ 3 | 基础功能验证 |
| **Dataset B** | 含复杂表格、图、公式、多层列表、附录、引用 | ≥ 3 | 核心能力验证 |
| **Dataset C** | 扫描 PDF、OCR、低质量文字 | ≥ 2 | OCR 鲁棒性验证 |
| **Dataset D** | 历史 Bug 修复案例 | 持续增加 | 回归防护 |
| **Dataset E** | 需 Normative Rendering 验证的文档（含不规范的编号/标点/规范性动词） | ≥ 1 | Normative Rendering 验证 |

### 8.4 Feature Coverage Matrix

| Feature | A | B | C | D | E | 说明 |
|---------|---|---|---|---|---|------|
| Metadata | ✓ | ✓ | ✓ | ✓ | ✓ | |
| Multi-level Structure | ✓ | ✓ | ✓ | ✓ | ✓ | 章/条/款/项 |
| Table | ✓ | ✓ | | ✓ | | |
| Merged Cell | | ✓ | | ✓ | | |
| Cross-page Table | | ✓ | | | | |
| Figure | | ✓ | | ✓ | | |
| Formula | | ✓ | | ✓ | | rawText 非空 |
| List | ✓ | ✓ | ✓ | ✓ | | 含 nested |
| Normative Reference | ✓ | ✓ | | ✓ | | |
| Internal Reference | ✓ | ✓ | | ✓ | | |
| Appendix | | ✓ | | | | |
| Note | | ✓ | | | | |
| Example | | ✓ | | | | |
| Warning | | ✓ | | | | |
| OCR | | | ✓ | | | |
| **Normative Rendering Test** | | | | | ✓ | 编号/标点规范化 |
| **FORBIDDEN_CHANGES Test** | | | | | ✓ | 规范性动词不变 |

### 8.5 Golden Dataset 存储结构

```
fixtures/golden/
│
├── dataset-A-text-pdf/
│   ├── GBT-xxx-20xx.pdf
│   ├── GBT-xxx-20xx.golden.ssir.json
│   ├── GBT-xxx-20xx.manifest.yaml
│   └── GBT-xxx-20xx.review.log
│
├── dataset-B-complex/
├── dataset-C-scanned/
├── dataset-D-regression/
│
└── dataset-E-normative-rendering/
    ├── GBT-yyy-20xx.pdf          # 含不规范编号/标点/规范性动词
    ├── GBT-yyy-20xx.golden.ssir.json
    ├── GBT-yyy-20xx.rendering.expected.docx  # 预期渲染结果
    ├── GBT-yyy-20xx.rendering.profile.yaml   # Rendering Profile 配置
    └── GBT-yyy-20xx.manifest.yaml
```


## 9. Extraction Fidelity Test

### 9.1 定义

验证 `Std₀ → SSIR₁` 的正确性。

### 9.2 测试方法

```
Std₀
  ↓
Extraction Pipeline
  ↓
SSIR₁
  ↓
Compare with Golden SSIR
  ↓
Extraction Fidelity Report
```

### 9.3 验证维度

| 维度 | 验证内容 | 方法 |
|------|----------|------|
| Metadata | 所有元数据字段 | exact match |
| Structure | 节点数量、层级、编号 | exact match |
| Content | 所有内容元素 | normalized match |
| Table | 行/列/单元格/合并 | exact match |
| Figure | 数量/编号/图题 | existence + normalized |
| Formula | 数量/编号/rawText | exact match |
| List | 层级/marker/文本 | normalized match |
| Provenance | SourceAnchor 存在性 | existence check |

### 9.4 通过标准

| 数据集 | 阈值 |
|--------|------|
| Dataset A | 100% |
| Dataset B | ≥ 98% |
| Dataset C | ≥ 95% |
| Dataset D | 100%（已修复 Bug 不重现） |
| Dataset E | 100% |


## 10. Normative Rendering Conformance Test

### 10.1 定义

验证 `SSIR₁ → Std₁` 是否符合目标规范（GB/T 1.1-2020），且遵循 **ALLOWED_NORMALIZATIONS** / **FORBIDDEN_CHANGES** 边界。

### 10.2 测试方法

```
SSIR₁ (Golden)
  ↓
Normative Rendering Pipeline
  (with specified Rendering Profile)
  ↓
Std₁ (DOCX/PDF)
  ↓
Manual + Automated Inspection
  ↓
Normative Rendering Conformance Report
```

### 10.3 验证维度（GB/T 1.1-2020）

| 维度 | 验证内容 |
|------|----------|
| Structure | 章节编号格式、层级 |
| Headings | 标题样式、编号 |
| Tables | 表题位置、表头、表注 |
| Figures | 图题位置、编号 |
| Formulas | 公式编号位置 |
| References | 引用格式 |
| Page Layout | 页边距、页码 |

### 10.4 ALLOWED_NORMALIZATIONS 验证

| 规范化操作 | 验证方法 | 预期 |
|------------|----------|------|
| 编号格式规范化 | 比较 Std₁ 编号格式 | 符合 GB/T 1.1 |
| 标点规范化 | 检查标点 | 符合规范 |
| 空格规范化 | 检查空格 | 符合规范 |
| 数字格式规范化 | 检查数字格式 | 符合规范 |
| 单位缩写规范化 | 检查单位 | 符合规范 |
| 引用分隔符规范化 | 检查引用格式 | 符合规范 |

### 10.5 FORBIDDEN_CHANGES 验证（Negative Test）

| 禁止变化 | 验证方法 | 预期 |
|----------|----------|------|
| normative_verb_change | 比较 SSIR₁ 与 Std₁ 的规范性动词 | 无变化 |
| prohibition_change | 比较禁止性表述 | 无变化 |
| numeric_value_change | 比较数值 | 无变化 |
| unit_change | 比较单位 | 无变化 |
| comparison_operator_change | 比较比较符 | 无变化 |
| clause_identifier_change | 比较条款编号 | 无变化 |
| table_cell_content_change | 比较表格单元格 | 无变化 |
| formula_raw_change | 比较公式 | 无变化 |
| reference_raw_change | 比较引用 | 无变化 |
| scope_change | 比较范围 | 无变化 |
| applicability_change | 比较适用性 | 无变化 |
| mandatory_condition_change | 比较强制条件 | 无变化 |

### 10.6 Rendering Profile 验证

| 验证项 | 方法 | 预期 |
|--------|------|------|
| Profile 选择 | 检查 QualityAssessment.renderingProfile | 与指定 Profile 一致 |
| Profile 合规 | 验证 Std₁ 符合 Profile 规则 | 全部符合 |

### 10.7 通过标准

- 所有 P0 文档的 Normative Rendering 输出符合 GB/T 1.1-2020 基本结构要求
- 无结构层级丢失
- 无编号格式错误
- **0 项 FORBIDDEN_CHANGES 违规**
- `QualityAssessment.renderingProfile` 字段正确填充


## 11. Round-trip Preservation Test

### 11.1 定义

验证 `SSIR₁ → Std₁ → SSIR₂` 后 `SSIR₁ ≈ SSIR₂`。

### 11.2 测试方法

```
                    ┌───────────────┐
                    │     Std₀      │
                    └───────┬───────┘
                            │
                     Extraction
                            │
                            ▼
                    ┌───────────────┐
                    │    SSIR₁      │  ← Round-trip Reference State
                    └───────┬───────┘
                            │
                  Normative Rendering
                  (GB/T 1.1-2020 Profile)
                            │
                            ▼
                    ┌───────────────┐
                    │     Std₁      │  ← 规范化输出
                    └───────┬───────┘
                            │
                     Re-Extraction
                            │
                            ▼
                    ┌───────────────┐
                    │    SSIR₂      │  ← 恢复状态
                    └───────┬───────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ SSIR₁ vs SSIR₂   │
                  │ Four-layer       │
                  │ Compare          │
                  └──────────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ Critical Loss    │
                  │ Check (12项)     │
                  └──────────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ Round-trip       │
                  │ Report           │
                  └──────────────────┘
```

### 11.3 Comparator 设计

SSIR Comparator 执行四层比较：

#### Layer 1: Identity View (STRICT)

| 比较项 | 方法 | 允许差异 |
|--------|------|----------|
| 所有 Identity 字段 | exact | 无 |

#### Layer 2: Structural View (STRICT)

| 比较项 | 方法 | 允许差异 |
|--------|------|----------|
| 结构树 | 递归比较 | 无 |

#### Layer 3: Content View (NORMALIZED)

| 比较项 | 方法 | 允许差异 |
|--------|------|----------|
| 内容元素 | 按 sortOrder 逐项比较 | ALLOWED_NORMALIZATIONS |

#### Layer 4: Semantic View (STRICT)

| 比较项 | 方法 | 允许差异 |
|--------|------|----------|
| Requirement | 结构化比较 | 无 |
| Scope | 文本比较 | 无 |
| Definition | 文本比较 | 无 |

### 11.4 Critical Information Loss Check

在比较前，必须执行 Data Model v0.4 §7.3 定义的 12 项 Critical Information Loss 检查（见 §5.5）。

```
如果任何 CRITICAL 信息丢失或改变 → Round-trip FAIL
```

### 11.5 通过标准

| 维度 | 阈值 |
|------|------|
| Identity | 100% |
| Structure | 100% |
| Content | ≥ 99%（归一化后） |
| Tables | 100% |
| Figures | 100%（存在性 + 图题） |
| Formulas | 100%（存在性 + rawText） |
| References | 100%（存在性 + rawTarget） |
| Ordering | 100% |
| Critical Information Loss | **0** |
| Rendering Profile | 正确填充 |
| Overall Status | **PASS**（所有维度 PASS） |

### 11.6 Round-trip Test 用例

| 用例 ID | 场景 | 优先级 | 预期 |
|---------|------|--------|------|
| RT-001 | 普通文本标准往返 | P0 | PASS |
| RT-002 | 含表格标准往返 | P0 | PASS |
| RT-003 | 含图/公式标准往返 | P1 | PASS |
| RT-004 | 含复杂表格（合并/跨页）往返 | P1 | PASS |
| RT-005 | 含多层列表往返 | P1 | PASS |
| RT-006 | 完整复杂标准往返 | P0 | PASS |
| RT-007 | 扫描 PDF 往返 | P2 | PASS |
| RT-008 | 含规范性引用和内部引用往返 | P1 | PASS |
| RT-009 | **含 Normative Rendering Profile 往返** | **P0** | **PASS** |


## 12. Normalization Stability Test

### 12.1 定义

验证系统在多次 `SSIR → 渲染 → 提取` 循环后是否收敛到稳定状态。

### 12.2 测试方法

```
Std₀
  ↓
SSIR₁
  ↓
Std₁
  ↓
SSIR₂
  ↓
Std₂
  ↓
SSIR₃
  ↓
...
```

验证：

```
SSIR₁ ≡ SSIR₂ ≡ SSIR₃ ≡ ... ≡ SSIRₙ
```

且：

```
Std₁ ≈ Std₂ ≈ Std₃ ≈ ... ≈ Stdₙ
```

### 12.3 Normalization Fixed Point

当满足以下条件时，系统达到 **Normalization Fixed Point（规范化固定点）**：

```
SSIRₙ₋₁ ≡ SSIRₙ
```

后续循环不再产生变化。

### 12.4 通过标准

- 系统在 3 次循环内达到 Normalization Fixed Point
- 固定点状态中无 Critical Information Loss


## 13. E2E Acceptance Test

### 13.1 定义

验证从用户输入一个标准文档到获得完整输出的完整业务路径。

### 13.2 测试方法

```
User Input (PDF/DOCX)
       ↓
API: POST /documents
       ↓
API: POST /documents/{id}/process (async)
       ↓
Worker: Extraction Pipeline
       ↓
Worker: Validation
       ↓
Worker: Quality Assessment (含 renderingProfile)
       ↓
API: GET /documents/{id}/ssir → SSIR JSON (v0.4)
       ↓
API: POST /documents/{id}/render (with Rendering Profile) → DOCX/PDF
       ↓
API: POST /documents/{id}/roundtrip → Report (含 Critical Loss Check)
```

### 13.3 验收标准

- API 返回正确的 HTTP 状态码
- SSIR 实例通过 Schema Validation（v0.3）
- QualityAssessment 状态非 FAIL
- QualityAssessment.renderingProfile 正确填充
- 输出文档可打开、可阅读
- Round-trip Report 可生成（含 Critical Loss Check 结果）
- 端到端耗时在可接受范围内


## 14. Schema Conformance Test

### 14.1 定义

验证 SSIR 实例是否符合 JSON Schema Specification v0.3。

### 14.2 v0.3 新增字段验证

| 新增字段 | 验证内容 | 测试类型 |
|----------|----------|----------|
| `ssirVersion` | 枚举值包含 `"0.4"` | Valid |
| `NormativeRenderingProfile` | 枚举值完整 | Valid |
| `QualityAssessment.renderingProfile` | 字段存在且值有效 | Valid |

### 14.3 测试类型

| 类型 | 输入 | 预期 |
|------|------|------|
| Valid | 完整有效的 SSIR（v0.4） | PASS |
| Valid with Profile | 含 renderingProfile 的 SSIR | PASS |
| Missing Required | 缺少必选字段 | REJECT |
| Invalid Enum | 枚举值违规 | REJECT |
| Invalid Pattern | ID 格式违规 | REJECT |
| Invalid Type | 字段类型错误 | REJECT |
| Invalid Reference | 引用不存在 | REJECT（Semantic Validator） |
| Boundary | 边界值（空数组、零值等） | PASS/REJECT 按规范 |
| Invalid ssirVersion | 版本号非 "0.3" 或 "0.4" | REJECT |
| Invalid renderingProfile | 非 NormativeRenderingProfile 枚举值 | REJECT |

### 14.4 通过标准

- 所有 Valid SSIR 通过验证
- 所有 Invalid SSIR 被正确拒绝
- 所有 v0.3 新增字段正确验证


## 15. Negative & Robustness Test

### 15.1 测试类型

| 用例 ID | 场景 | 输入 | 预期 |
|---------|------|------|------|
| NT-001 | 无效 SSIR | 缺少必选字段 | REJECT |
| NT-002 | 无效结构 | 根节点不是 document | REJECT |
| NT-003 | 无效引用 | tableRef 指向不存在的 Table | WARN/ERROR |
| NT-004 | 无效 TextSpan | startChar > endChar | WARN |
| NT-005 | 无效枚举 | 非标准枚举值 | REJECT |
| NT-006 | 空文档 | 无 contentElements | WARN |
| NT-007 | 超大文档 | 超过处理能力 | 优雅降级 |
| NT-008 | **FORBIDDEN_CHANGES 检测** | Rendering 违反 FORBIDDEN_CHANGES | **FAIL** |
| NT-009 | **无效 NormativeRenderingProfile** | 使用不支持的 Profile | REJECT/WARN |


## 16. Regression Test

### 16.1 触发条件

- 代码合并到主分支
- 修改 Core Pipeline 逻辑
- 修改 SSIR Builder
- 修改 Normative Rendering 逻辑
- 修改 FORBIDDEN_CHANGES 检测逻辑
- 升级依赖库（MinerU、OCR 引擎等）
- 修改 Rendering Profile

### 16.2 回归类型

| 类型 | 定义 | 检测方法 |
|------|------|----------|
| **Functional Regression** | 功能退化 | Golden Test 结果变化 |
| **Semantic Regression** | 语义能力退化 | SSIR Semantic Compare 结果变化 |
| **Normative Regression** | Normative Rendering 退化 | FORBIDDEN_CHANGES 检测结果变化 |

### 16.3 回归防护

1. CI/CD Pipeline 中集成 Golden Test
2. 失败用例阻止合并
3. 每周生成 Regression Report
4. 建立 Test Failures Triage 流程


## 17. Conformance Gates

Phase 1 必须通过的 8 道 Gate：

| Gate | 名称 | 要求 | 对应 Data Model v0.4 |
|------|------|------|---------------------|
| **G1** | Schema Gate | 100% required schema tests PASS（含 v0.3 新字段） | §6 |
| **G2** | Extraction Gate | Core Golden Dataset PASS | §7.2 Source Fidelity |
| **G3** | Structural Gate | 100% critical structure preserved | §7.6 |
| **G4** | Content Gate | ≥ 99% content preserved | §7.6 |
| **G5** | Critical Gate | **0 critical information loss**（12 项检查全通过） | §7.3 |
| **G6** | Normative Rendering Gate | ALLOWED_NORMALIZATIONS 正确应用，FORBIDDEN_CHANGES 0 违规 | §7.3 |
| **G7** | Round-trip Gate | All P0 Round-trip PASS | §7.5 |
| **G8** | Regression Gate | 0 regression in frozen Golden Dataset | — |


## 18. Test Environment & Tools

| 组件 | 要求 |
|------|------|
| 操作系统 | Ubuntu 22.04 LTS 或 Docker 容器 |
| Python | 3.11+ |
| 内存 | ≥ 16 GB |
| 存储 | ≥ 50 GB 可用空间 |
| 网络 | 稳定网络连接 |

| 工具 | 用途 |
|------|------|
| pytest | 单元测试和集成测试框架 |
| pytest-cov | 测试覆盖率报告 |
| deepdiff | JSON/对象深度比较 |
| jsonschema | Schema 验证（v0.3） |
| junit-xml | 测试结果输出 |


## 19. Test Reporting

### 19.1 报告类型

| 报告类型 | 频率 | 受众 |
|----------|------|------|
| Unit Test Report | 每次提交 | 开发者 |
| Integration Test Report | 每次合并 | 开发者/QA |
| Golden Test Report | 每次发版 | QA/PM |
| Normative Rendering Report | 每次发版 | QA/PM |
| Round-trip Report | 每次发版 | QA/PM |
| Regression Report | 每周 | QA/开发负责人 |
| Conformance Report | 里程碑 | 项目负责人 |

### 19.2 Round-trip Report 格式（含 Critical Loss）

```json
{
  "reportId": "rt-20260815-001",
  "timestamp": "2026-08-15T14:30:00Z",
  "documentId": "ssir:GBT-42093.1-2022",
  "renderingProfile": "gb-t-1-1-2020",
  "cycle": 1,
  
  "summary": {
    "overallStatus": "PASS",
    "criticalLoss": false,
    "criticalCount": 0
  },
  
  "identityView": {
    "status": "PASS",
    "details": {}
  },
  
  "structuralView": {
    "status": "PASS",
    "nodes": {"matched": 45, "total": 45}
  },
  
  "contentView": {
    "status": "PASS",
    "elements": {"matched": 1430, "total": 1432},
    "matchRate": 0.9986
  },
  
  "semanticView": {
    "status": "PASS",
    "details": {}
  },
  
  "criticalCheck": {
    "status": "PASS",
    "violations": [],
    "checks": {
      "normative_wording": "PASS",
      "prohibition": "PASS",
      "numeric_value": "PASS",
      "unit": "PASS",
      "comparison_operator": "PASS",
      "clause_identifier": "PASS",
      "table_cell": "PASS",
      "formula_raw": "PASS",
      "reference_raw": "PASS",
      "scope": "PASS",
      "applicability": "PASS",
      "mandatory_condition": "PASS"
    }
  },
  
  "renderingProfileValidation": {
    "status": "PASS",
    "profile": "gb-t-1-1-2020"
  },
  
  "recommendations": []
}
```


## 20. Bug Classification & Triage

### 20.1 严重等级

| 等级 | 定义 | 示例 |
|------|------|------|
| **S0** | Critical Information Loss | 数值丢失、规范要求丢失、公式丢失、FORBIDDEN_CHANGES 违规 |
| **S1** | 核心能力失败 | Golden Test FAIL、结构树损坏、Rendering Profile 错误 |
| **S2** | 一般功能缺陷 | 列表标记错误、富文本丢失 |
| **S3** | 边缘问题 | 罕见格式、低概率 OCR 错误 |

### 20.2 优先级

| 优先级 | 定义 |
|--------|------|
| **P0** | 阻塞发版，必须修复 |
| **P1** | 高优先级，应在当前 Sprint 修复 |
| **P2** | 中优先级，可排入后续 Sprint |


## 21. CI/CD Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                     CI Pipeline                                 │
│                                                                 │
│  1. Code Commit                                                │
│         │                                                       │
│         ▼                                                       │
│  2. Lint & Type Check                                          │
│         │                                                       │
│         ▼                                                       │
│  3. Unit Tests (按能力覆盖)                                    │
│         │                                                       │
│         ▼                                                       │
│  4. Schema Conformance Tests (v0.3)                           │
│         │                                                       │
│         ▼                                                       │
│  5. Integration Tests                                          │
│         │                                                       │
│         ▼                                                       │
│  6. Golden Tests (Dataset A only, < 5min)                     │
│         │                                                       │
│         ▼                                                       │
│  7. Normative Rendering Tests (Dataset E)                     │
│         │                                                       │
│         ▼                                                       │
│  8. Build & Package                                            │
│         │                                                       │
│         ▼                                                       │
│  9. (Nightly) Full Golden + Round-trip + Critical Loss Check  │
└─────────────────────────────────────────────────────────────────┘
```


## 22. Test Cases Catalog

### 22.1 Unit Test

| 用例 ID | 模块 | 描述 | 优先级 |
|---------|------|------|--------|
| UT-001 | CanonicalText | 文本规范化正确性 | P0 |
| UT-002 | StructureBuilder | 章节编号解析 | P0 |
| UT-003 | StructureBuilder | 列表标记解析 | P1 |
| UT-004 | TableBuilder | 合并单元格处理 | P0 |
| UT-005 | TableBuilder | 跨页表格处理 | P1 |
| UT-006 | ReferenceExtractor | 内部引用解析 | P1 |
| UT-007 | SourceAnchor | bbox 坐标归一化 | P0 |
| UT-008 | **CriticalLossChecker** | **12 项 Critical Loss 检测** | **P0** |
| UT-009 | **NormativeRenderingProfile** | **Profile 选择验证** | **P1** |

### 22.2 Golden Test

| 用例 ID | Dataset | 文档 | 优先级 |
|---------|---------|------|--------|
| GT-001 | A | GBT-42093.1-2022 | P0 |
| GT-002 | A | GBT-22373-2021 | P0 |
| GT-003 | B | 含复杂表格标准 | P0 |
| GT-004 | B | 含图/公式标准 | P1 |
| GT-005 | C | 扫描标准样例 | P2 |
| GT-006 | **E** | **Normative Rendering 验证文档** | **P0** |

### 22.3 Round-trip Test

| 用例 ID | 场景 | 优先级 |
|---------|------|--------|
| RT-001 | 普通文本标准往返 | P0 |
| RT-002 | 含表格标准往返 | P0 |
| RT-003 | 完整复杂标准往返 | P0 |
| RT-004 | 含图/公式标准往返 | P1 |
| RT-005 | 扫描 PDF 往返 | P2 |
| RT-006 | 含 Normative Rendering 往返 | P0 |

### 22.4 Normative Rendering Test

| 用例 ID | 场景 | 优先级 |
|---------|------|--------|
| NR-001 | Normative Rendering: 编号规范化 | P0 |
| NR-002 | Normative Rendering: 标点/空格规范化 | P1 |
| NR-003 | Normative Rendering: FORBIDDEN_CHANGES 不被执行 | P0 |
| NR-004 | Normative Rendering Profile 选择与验证 | P1 |

### 22.5 Negative Test

| 用例 ID | 场景 | 优先级 |
|---------|------|--------|
| NT-001 | 无效 SSIR | P0 |
| NT-002 | 无效结构 | P1 |
| NT-003 | 无效引用 | P1 |
| NT-004 | 无效 TextSpan | P2 |
| NT-005 | 无效枚举 | P0 |
| NT-006 | 空文档 | P2 |
| NT-007 | 超大文档 | P2 |
| NT-008 | **FORBIDDEN_CHANGES 检测** | **P0** |
| NT-009 | **无效 NormativeRenderingProfile** | **P1** |


## 23. Version History

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 0.1 | 2026-08-15 | 初始版本 |
| 0.2 | 2026-08-15 | 确立 Round-trip 核心定义（Std₀→SSIR₁→Std₁→SSIR₂，验证 SSIR₁≈SSIR₂）；新增 Conformance Model；新增 SSIR Equivalence Model；新增 Information Preservation Contract；拆分为四柱测试体系；取消单一 Match Rate；新增 Critical Information Loss/Zero Critical Loss；新增 Schema Conformance & Negative Test；新增 Normalization Stability Test；重新设计 Conformance Gates（8 Gates） |
| 0.3 | 2026-08-15 | 与 Data Model v0.4 和 JSON Schema v0.3 对齐；§2 增加 JSON Schema v0.3 引用；§4 Conformance Model 增加 Normative Rendering 支持声明和 FORBIDDEN_CHANGES 合规性要求；§5 增加 Critical Information Loss 检查项清单（12 项）；§6 明确 ALLOWED_NORMALIZATIONS 与 FORBIDDEN_CHANGES 边界；§10 重命名为 Normative Rendering Conformance Test，增加 Profile 验证和 Negative Test；§14 增加 v0.3 新字段验证；§8 增加 Dataset E（Normative Rendering 测试文档）；§22 新增 NR-001～NR-004、RT-009 测试用例 |


## 24. Next Steps

1. **Review & Freeze**: 本规范与 Data Model v0.4、JSON Schema v0.3 联合评审并冻结
2. **实现 CriticalLossChecker**: 实现 12 项 Critical Loss 检测
3. **实现 Normative Rendering 测试框架**: 实现 ALLOWED_NORMALIZATIONS / FORBIDDEN_CHANGES 验证
4. **准备 Dataset E**: 收集 Normative Rendering 测试文档
5. **更新 AI Coding Specification**: 将本规范的变更同步到 AI Coding Implementation Specification
