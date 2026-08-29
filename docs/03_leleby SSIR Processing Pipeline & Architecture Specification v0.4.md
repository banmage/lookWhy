# leleby SSIR Processing Pipeline & Architecture Specification v0.5

> **文档状态**：正式发布 | **版本**：0.5 | **日期**：2026-08-17
>
> **v0.4 主要修订**（基于 Data Model v0.4 和 JSON Schema v0.3 的对齐）：
> - **升级 Round-trip 比较为四层**：Identity/Structural/Content/Semantic Equivalence，对齐 Data Model v0.4 §7.6
> - **新增 CriticalLossChecker 子模块**：执行 12 项 Critical Information Loss 检查（Data Model v0.4 §7.3）
> - **Rendering Service 升级为 Normative Rendering Service**：明确 ALLOWED_NORMALIZATIONS / FORBIDDEN_CHANGES 边界
> - **QualityAssessment 增加 `renderingProfile` 字段**：对齐 JSON Schema v0.3
> - **新增 §5.9 CriticalLossChecker 模块定义**
> - **更新 §8 Acceptance Criteria**：增加 Critical Gate 和 Normative Rendering Gate
> - **更新 §4.1 数据流图**：反映四层比较 + Critical Loss Check
> - **更新 §3.2 Preservation Contract**：明确 ALLOWED_NORMALIZATIONS 与 FORBIDDEN_CHANGES


## 1. Scope

本规范定义 leleby SSIR（Standard Structured Information Representation）的处理流水线与系统架构，涵盖从源文档输入到 SSIR 生成、验证、存储、渲染和往返测试的完整技术路径。

本规范适用于 Phase 1 开发，即 **SSIR Round-trip Digitalization Engine** 的工程实现。

**Phase 1 的核心链路**：

> **当前 M1 实现链路覆盖范围**：`用户原始 Markdown → CSM Validator/Normalizer → Canonical CSM Markdown → Markdown AST → Extraction IR → SSIR → CSM Renderer → Render.md CSM Markdown → CSMParser → Verify → Four-layer Comparator → Round-trip Report`；`Canonical` 是完成基础纠错后的回环起点，原始输入的修复项进入转换报告。Turtle 是从 SSIR JSON 派生的可选导出。下文的 PDF/MinerU/OCR/DOCX 链路是 M2 的预留架构，不得在 M1 启动时强制安装或调用。
>
> M1 必须保存 Markdown 源文件和行/列/AST 溯源；无 PDF 输入时，`pdfPageIndex`、`bbox` 等字段保持缺省，不得用虚拟值填充。

```
Source Document → Ingestion → Extraction → Extraction IR → SSIR Builder → SSIR → Validation → Repository → Normative Rendering → DOCX/PDF → Re-extraction → Round-trip Verification
```

**Phase 1 边界**：
- **包含**：文档数字化、结构化表示、溯源、规范性渲染、往返验证
- **不包含**：leleby Ontology、Compliance、Requirement Graph 推理等 Semantic Layer 功能
- **M1 的可执行终点是 SSIR JSON 与 Markdown Round-trip Report；DOCX/PDF 渲染仍留待 M2**


## 2. System Architecture Overview

### 2.1 四层架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Application Layer                                 │
│         API Server  │  Worker  │  CLI  │  Document Workbench               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Service Layer                                    │
│                                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │Ingestion │ │Extraction│ │  SSIR    │ │Validation│ │Normative │        │
│  │ Service  │ │ Service  │ │ Builder  │ │ Service  │ │Rendering │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
│                                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │Semantic  │ │  Round-  │ │  Search  │ │ Critical │                     │
│  │Enrichment│ │   trip   │ │  Engine  │ │  Loss    │                     │
│  │ (L4)     │ │ Verifier │ │          │ │ Checker  │                     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Data Layer                                       │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    PostgreSQL / MinIO / Redis                        │  │
│  │                                                                      │  │
│  │  ssir_document │ source_file │ processing_run │ quality_assessment  │  │
│  │  ─────────────────────────────────────────────────────────────────   │  │
│  │  Object Storage: PDF │ OCR assets │ Figures │ SSIR JSON             │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Infrastructure Layer                                │
│                                                                             │
│  Docker │ Docker Compose │ MinIO │ Redis │ Celery Broker                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Pipeline vs Enrichment Pipeline

| Pipeline | 模块 | Preservation Level | Round-trip 必要条件 |
|----------|------|-------------------|-------------------|
| **Core Pipeline** | Ingestion → Extraction → CanonicalText → Structure → Content → Provenance → Validation | L0-L3 | **是** |
| **Normative Rendering Pipeline** | SSIR → Rendering IR → DOCX/PDF (with Profile) | L3 → 渲染文档 | **是** |
| **Enrichment Pipeline** | Reference → Entity → Relation | L4 | **否**（Phase 1 可选） |

**架构原则**：L0-L3 不依赖任何 L4 能力。L4 是可选的增强层，不能阻塞 Round-trip。

### 2.3 Round-trip 核心定义

SSIR Round-trip Digitalization Engine 的验证目标为：

```
源文档 → SSIR → 渲染文档 → Verify

验证目标：SSIR ≈ Verify（SSIR Semantic Equivalence — 四层比较）
而非：源文档 ≈ 渲染文档（文档外观等价）
```

其中：
- `源文档`：原始输入文档
- `SSIR`：从 源文档 提取的信息基准状态
- `渲染文档`：从 SSIR 渲染生成的规范化文档（**Normative Rendering**，依据 GB/T 1.1-2020 等 Rendering Profile）
- `Verify`：从 渲染文档 再次提取的恢复状态

**关键原则**：传统文档是可变的表现层（Document Representation），SSIR 才是需要保持稳定的信息层（Information Representation）。因此 `源文档` 与 `渲染文档` 的差异不必然表示 Round-trip 失败。


## 3. Preservation Levels & Contract

### 3.1 Preservation Levels

| Level | 名称 | 内容 | 负责模块 |
|-------|------|------|----------|
| **L0** | Metadata Only | 文档身份与元数据 | SSIR Builder |
| **L1** | Structural | L0 + 章节/条款/附录逻辑结构 | SSIR Builder |
| **L2** | Content Complete | L1 + 正文、表格、图、公式、列表、注、脚注 | SSIR Builder |
| **L3** | Traceable | L2 + SourceAnchor、TextSpan、完整溯源 | SSIR Builder + Provenance |
| **L4** | Semantic Enriched | L3 + Reference、Entity、Relation | Semantic Enrichment Service |

**Phase 1 Round-trip Ready 的最低要求：L3**

### 3.2 Preservation Contract / Loss Budget

#### MUST PRESERVE（必须保留）

| 类别 | 内容 |
|------|------|
| Identity | 文档标识符、标题、发布日期、发布机构、标准号 |
| Structure | 章节层级、条款编号、附录结构 |
| Text | 规范性正文、术语定义、范围、要求条款 |
| Tables | 行、列、合并单元格、表头、表注 |
| Figures | 图片本身（asset）、图题 |
| Formulas | rawText（原始表示）、公式编号 |
| Lists | 层级、标记（marker）、文本 |
| Notes | 注、示例、警示 |
| References | rawTarget（原始引用文本） |
| Ordering | 所有内容元素的原始顺序 |
| Provenance | 每个核心对象的 SourceAnchor |

#### ALLOWED_NORMALIZATIONS（允许规范化 — Data Model v0.4 §7.3）

| 类别 | 说明 |
|------|------|
| whitespace_normalization | 空格规范化 |
| line_break_unification | 换行统一 |
| punctuation_normalization | 标点规范化 |
| number_format_normalization | 数字格式规范化 |
| unit_abbreviation_normalization | 单位缩写规范化 |
| reference_separator_normalization | 引用分隔符规范化 |

#### FORBIDDEN_CHANGES（绝对禁止修改 — Data Model v0.4 §7.3）

| 类别 | 说明 |
|------|------|
| normative_verb_change | 应 → 宜 |
| prohibition_change | 不得 → 不应 |
| numeric_value_change | 90 → 80 |
| unit_change | MPa → kPa |
| comparison_operator_change | ≥ → > |
| clause_identifier_change | 5.2.1 → 5.2 |
| table_cell_content_change | 表格单元格内容改变 |
| formula_raw_change | 公式原始表示改变 |
| reference_raw_change | 引用原始文本改变 |
| scope_change | 范围改变 |
| applicability_change | 适用性改变 |
| mandatory_condition_change | 强制条件改变 |

#### MAY NORMALIZE（允许规范化 — 排版层面）

| 类别 | 说明 |
|------|------|
| Pagination | PDF 分页不要求保留 |
| Font metrics | 字体、字号、行距不要求保留 |
| Rendering coordinates | bbox 坐标在渲染后可能变化 |
| Page layout | 页眉/页脚位置可变化 |

#### MUST NOT CHANGE（绝对禁止修改 — 语义层面）

| 类别 | 说明 |
|------|------|
| Normative wording | 规范性语句的措辞（应/应当/必须/不得/不应/禁止） |
| Numbers | 数值、百分比、范围 |
| Units | 单位符号 |
| Symbols | 化学符号、数学符号 |
| Clause identifiers | 条款编号（如 5.2.1） |
| Table cell content | 表格单元格的文本内容 |
| Formula raw representation | 公式的原始文本表示 |
| Reference rawTarget | 引用的原始文本 |


## 4. Core Data Flow

### 4.1 Overall Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CORE PIPELINE (L0 → L3)                          │
│                                                                             │
│  ┌──────────────────┐                                                      │
│  │   Source File    │  (PDF / Scanned PDF / DOCX)                         │
│  └────────┬─────────┘                                                      │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────┐                                                      │
│  │   Ingestion      │  → DocumentSourceProfile, SourceFile, ProcessingRun │
│  └────────┬─────────┘                                                      │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────┐                                                      │
│  │   Extraction     │  → MinerU / DOCX Parser / OCR                      │
│  └────────┬─────────┘                                                      │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────┐                                                      │
│  │  Extraction IR   │  → Parser-neutral intermediate representation       │
│  └────────┬─────────┘                                                      │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────┐                                                      │
│  │ CanonicalText    │  → 权威文本层 + TextSpan                           │
│  └────────┬─────────┘                                                      │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────┐                                                      │
│  │  Structure       │  → 章节/条款/附录逻辑树                            │
│  └────────┬─────────┘                                                      │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────┐                                                      │
│  │  Content         │  → Paragraph/List/Table/Figure/Formula/Note/...    │
│  └────────┬─────────┘                                                      │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────┐                                                      │
│  │  Provenance      │  → SourceAnchor / TextSpan                         │
│  └────────┬─────────┘                                                      │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────┐                                                      │
│  │    SSIR L3       │  → Round-trip Ready                                │
│  └────────┬─────────┘                                                      │
│           │                                                                │
│           ├──────────────────┬──────────────────────┬────────────────────┐  │
│           ▼                  ▼                      ▼                    ▼  │
│  ┌──────────────────┐ ┌──────────────┐ ┌──────────────────────┐ ┌───────┐│
│  │   Validation     │ │  Normative   │ │  Semantic            │ │Critical││
│  │   (L3 Gate)      │ │  Rendering   │ │  Enrichment (L4)     │ │ Loss  ││
│  │                  │ │  (with       │ └──────────────────────┘ │Checker││
│  │  Quality:        │ │   Profile)   │                         │       ││
│  │  renderingProfile│ └──────┬───────┘                         └───────┘│
│  └────────┬─────────┘        │                                           │
│           ▼                  ▼                                           │
│  ┌──────────────────┐ ┌──────────────┐                                   │
│  │   Repository     │ │Rendering IR  │                                   │
│  │  (含 versioning  │ └──────┬───────┘                                   │
│  │   + profile)     │        │                                           │
│  └──────────────────┘        ▼                                           │
│                        ┌──────────────┐                                   │
│                        │  DOCX / PDF  │                                   │
│                        │   (渲染文档)     │                                   │
│                        └──────┬───────┘                                   │
│                               ▼                                           │
│                        ┌──────────────┐                                   │
│                        │Re-extraction │                                   │
│                        └──────┬───────┘                                   │
│                               ▼                                           │
│                        ┌──────────────┐                                   │
│                        │   Verify      │                                   │
│                        └──────┬───────┘                                   │
│                               ▼                                           │
│                        ┌──────────────────────────────────────────────┐  │
│                        │         Round-trip Verification              │  │
│                        │                                              │  │
│                        │  ┌────────────────────────────────────────┐ │  │
│                        │  │  Four-layer SSIR ≈ Verify Compare     │ │  │
│                        │  │                                        │ │  │
│                        │  │ Level 1: Identity (STRICT)            │ │  │
│                        │  │ Level 2: Structural (STRICT)          │ │  │
│                        │  │ Level 3: Content (NORMALIZED)         │ │  │
│                        │  │ Level 4: Semantic (STRICT)            │ │  │
│                        │  └────────────────────────────────────────┘ │  │
│                        │                    │                       │  │
│                        │                    ▼                       │  │
│                        │  ┌────────────────────────────────────────┐ │  │
│                        │  │  Critical Information Loss Check      │ │  │
│                        │  │  (12项 — Data Model v0.4 §7.3)       │ │  │
│                        │  └────────────────────────────────────────┘ │  │
│                        │                    │                       │  │
│                        │                    ▼                       │  │
│                        │  ┌────────────────────────────────────────┐ │  │
│                        │  │  Rendering Fidelity Test (独立)       │ │  │
│                        │  └────────────────────────────────────────┘ │  │
│                        └──────────────────────────────────────────────┘  │
│                               │                                           │
│                               ▼                                           │
│                        ┌──────────────┐                                   │
│                        │Round-trip    │                                   │
│                        │  Report      │                                   │
│                        └──────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Canonical Content Principle

> **CanonicalText SHALL be the authoritative textual representation of preserved source text. StructuralNode and ContentElement SHOULD reference CanonicalText through TextSpan rather than independently duplicating canonical textual content, except where the SSIR schema explicitly requires object-local raw content (e.g., `rawTarget` for references, `rawText` for formulas).**

| 对象 | 文本存储方式 |
|------|-------------|
| CanonicalText | 权威全文 |
| TextSpan | 引用 CanonicalText + start/end |
| ContentElement | 引用 TextSpan（或本地 `textContent` 作为备选） |
| TableCell | 本地 `text` 或 `richText` |
| ListItem | 本地 `text` 或 `richText` |
| Reference | `rawTarget` 必须本地保存（不可改写） |
| Formula | `rawText` 必须本地保存（不可改写） |


## 5. Module Definitions

### 5.1 P1: Document Ingestion Service

**职责**：接收源文件，识别文件类型，建立 SourceFile 对象。

**输入**：
- 文件流（PDF/DOCX）
- 可选：用户提供的元数据覆盖

**输出**：
- `DocumentSourceProfile`
- `SourceFile` 对象（符合 SSIR 模型）
- `ProcessingRun`（初始）

**子模块**：

| 子模块 | 职责 | 输出 |
|--------|------|------|
| DocumentDetector | 识别 MIME、文件类型、页数、文本层质量 | DocumentSourceProfile |
| SourceFileBuilder | 计算 hash、提取元数据、建立 SourceFile | SourceFile |
| ProcessingRunInitializer | 创建初始 ProcessingRun | ProcessingRun |

**DocumentSourceProfile 结构**：

```json
{
  "fileType": "pdf" | "docx",
  "pdfType": "text" | "scanned" | "hybrid",
  "pageCount": 128,
  "hasTextLayer": false,
  "textLayerQuality": "none" | "partial" | "full",
  "ocrRequired": true,
  "ocrCoverage": 0.95,
  "pages": [
    {
      "pageIndex": 0,
      "sourceMode": "text" | "ocr" | "mixed"
    }
  ],
  "language": "zh-CN",
  "isEncrypted": false,
  "isCorrupted": false
}
```

### 5.2 P2: Document Extraction Service

**职责**：使用解析器将源文件转换为 Extraction IR。

**输入**：
- `SourceFile` + `ProcessingRun`
- 文件存储路径

**输出**：
- `ExtractionIR`

**子模块**：

| 子模块 | 职责 | 输出 |
|--------|------|------|
| PDFExtractor | MinerU 适配器 | 原始解析结果 |
| DOCXExtractor | python-docx 解析器 | 原始解析结果 |
| OCRPipeline | 扫描 PDF OCR 处理 | OCR 文本 + bbox + 置信度 |
| LayoutAnalyzer | 页面布局分析 | 区块、阅读顺序 |
| ReadingOrderResolver | 确定内容阅读顺序 | 有序的区块列表 |

**Extraction IR 结构**（Parser-neutral）：

```json
{
  "sourceFileId": "src:...",
  "processingRunId": "run:...",
  "pages": [
    {
      "pageIndex": 0,
      "pageLabel": "1",
      "blocks": [
        {
          "blockId": "block-001",
          "type": "text" | "heading" | "table" | "figure" | "formula" | "list" | "note",
          "bbox": [100, 120, 800, 160],
          "text": "...",
          "readingOrder": 0,
          "confidence": 0.99,
          "children": [],
          "sourceMethod": "native_text" | "ocr" | "docx"
        }
      ]
    }
  ]
}
```

**关键原则**：
- Extraction IR 是 **parser-neutral**，不是 SSIR 的低级版本
- 禁止将 MinerU 数据结构直接作为 SSIR
- 每个 block 必须记录 `sourceMethod`

### 5.3 P3: SSIR Builder Service (Core)

**职责**：将 Extraction IR 转换为符合 SSIR v0.4 的完整文档（L0-L3）。

**输入**：
- `ExtractionIR`
- `SourceFile` + `ProcessingRun`

**输出**：
- `SSIRDocument`（L0-L3）

**子模块**：

| 子模块 | 职责 | 输出 |
|--------|------|------|
| CanonicalTextBuilder | 生成权威全文 + TextSpan | CanonicalText |
| MetadataExtractor | 提取文档元数据 | DocumentMetadata |
| StructureBuilder | 构建逻辑结构树 | StructuralNode (root) |
| ContentBuilder | 构建内容元素 | ContentElement[] |
| TableBuilder | 构建表格对象 | Table[] |
| FigureBuilder | 构建图片对象 | Figure[] |
| FormulaBuilder | 构建公式对象 | Formula[] |
| ListBuilder | 构建列表对象 | ListItem[] |
| FootnoteBuilder | 构建脚注 | ContentElement[] |
| UnknownContentHandler | 处理未识别内容 | UnknownContent[] |
| ProvenanceBuilder | 建立源定位 | SourceAnchor[] |

**SSIR Builder 不负责 L4**。Reference/Entity/Relation 由独立的 Semantic Enrichment Service 处理。

**Builder 内部数据流**：

```
Extraction IR
      │
      ├──────────────────────────────────────┐
      │                                      │
      ▼                                      ▼
CanonicalTextBuilder                 StructureBuilder
      │                                      │
      ▼                                      │
CanonicalText + TextSpan                     │
      │                                      │
      └──────────────┬───────────────────────┘
                     ▼
              ContentBuilder
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
    Table        Figure        Formula
    Builder      Builder       Builder
       │             │             │
       └─────────────┼─────────────┘
                     ▼
              ProvenanceBuilder
                     │
                     ▼
                 SSIR L3
```

### 5.4 P4: Semantic Enrichment Service (L4 — Optional)

**职责**：在 L3 SSIR 基础上进行语义增强，生成 L4 SSIR。

**输入**：
- `SSIRDocument`（L3）

**输出**：
- `SSIRDocument`（L4）

**子模块**：

| 子模块 | 职责 | 输出 |
|--------|------|------|
| ReferenceExtractor | 识别引用关系 | Reference[] |
| EntityExtractor | 识别实体提及 | EntityMention[] |
| RelationExtractor | 识别关系提及 | RelationMention[] |

**关键原则**：
- L4 是 **可选增强层**，不能阻塞 Round-trip
- L4 的提取失败不应导致 L3 SSIR 无法通过验证
- L4 结果必须保留 `confidence` 和 `resolutionStatus`

### 5.5 P5: SSIR Validation Service

**职责**：验证 SSIR 文档的完整性和正确性。

**输入**：
- `SSIRDocument`

**输出**：
- `QualityAssessment`（**含 `renderingProfile` 字段**）
- `ValidationReport`

**验证层级**：

| 层级 | 验证内容 | 失败处理 |
|------|----------|----------|
| Schema | JSON Schema 合规性（v0.3） | FATAL |
| Structural | 根节点唯一、parent 存在、sortOrder 连续 | ERROR |
| Referential | tableRef/figureRef/formulaRef 存在 | ERROR |
| Provenance | 核心对象有 SourceAnchor | ERROR（L3 要求） |
| Content | 文本长度、表格完整性 | WARN |
| Preservation | 达到 L2/L3 | WARN |
| RenderingProfile | renderingProfile 字段有效 | WARN |

**Validation Status 定义**：

| 状态 | 说明 |
|------|------|
| FATAL | 无法继续处理，必须人工干预 |
| ERROR | 违反核心契约，不通过验证 |
| WARN | 存在质量问题，但可通过 |
| INFO | 信息性提示 |

**QualityAssessment 结构**（含 renderingProfile）：

```json
{
  "id": "...",
  "documentId": "...",
  "runId": "...",
  "renderingProfile": "GB_T_1.1-2020",  // 新增 — 对齐 JSON Schema v0.3
  "overallStatus": "complete" | "partial" | "extractionFailed" | "requiresReview" | "approved" | "rejected",
  "dimensions": {
    "textExtraction": {
      "status": "PASS" | "WARN" | "FAIL",
      "confidence": 0.95,
      "details": {}
    },
    "structureRecognition": {
      "status": "PASS",
      "confidence": 0.98,
      "details": {}
    },
    "tableExtraction": {
      "status": "WARN",
      "confidence": 0.78,
      "details": {"unresolvedTables": ["table-003"]}
    },
    "figurePreservation": {
      "status": "PASS",
      "confidence": 1.0,
      "details": {}
    },
    "formulaPreservation": {
      "status": "PASS",
      "confidence": 1.0,
      "details": {}
    },
    "provenanceCoverage": {
      "status": "PASS",
      "coverage": 0.99,
      "details": {}
    },
    "renderingProfileValidation": {
      "status": "PASS",
      "details": {"profile": "GB_T_1.1-2020"}
    }
  },
  "assessedAt": "..."
}
```

### 5.6 P6: SSIR Repository

**职责**：存储和检索 SSIR 文档，支持版本化。

**存储结构**：

```
PostgreSQL Tables:
├── ssir_document
│   ├── id (PK)
│   ├── document_version (integer)
│   ├── schema_version (string)           -- v0.4
│   ├── content_hash (string)
│   ├── parent_version (string)
│   ├── created_by_processing_run (FK)
│   ├── preservation_level
│   ├── rendering_profile (string)        -- 新增
│   ├── created_at
│   └── updated_at
│
├── source_file
│   ├── id (PK)
│   ├── document_id (FK)
│   ├── file_name
│   ├── file_hash
│   ├── mime_type
│   └── page_count
│
├── processing_run
│   ├── id (PK)
│   ├── document_id (FK)
│   ├── source_file_id (FK)
│   ├── pipeline_version (string)
│   ├── ssir_version (string)
│   ├── extractor (string)
│   ├── extractor_version (string)
│   ├── ocr_engine
│   ├── ocr_version
│   ├── ocr_model
│   ├── layout_analyzer_version
│   ├── reading_order_version
│   ├── configuration_hash (string)
│   ├── input_hash (string)
│   ├── timestamp
│   └── output_summary
│
├── quality_assessment
│   ├── id (PK)
│   ├── document_id (FK)
│   ├── overall_status
│   ├── dimensions (JSONB)
│   ├── rendering_profile (string)        -- 新增
│   └── assessed_at
│
└── metadata_index
    ├── document_id (FK)
    ├── key
    ├── value
    └── (GIN index for search)

Object Storage:
├── originals/{document_id}/{version}/source.pdf
├── assets/{document_id}/{version}/figures/
├── assets/{document_id}/{version}/tables/
├── ssir/{document_id}/{version}/ssir.json
├── rendered/{document_id}/{version}/document.docx
└── rendered/{document_id}/{version}/document.pdf
```

### 5.7 P7: Normative Rendering Service

**职责**：从 SSIR 生成规范性传统格式文档（`SSIR → 渲染文档`），遵循 ALLOWED_NORMALIZATIONS 规则，禁止 FORBIDDEN_CHANGES。

**输入**：
- `SSIRDocument`（L3）
- `NormativeRenderingProfile`（枚举：GB_T_1.1-2020, iso-iec, custom）

**输出**：
- `RenderingIR`
- DOCX/HTML/PDF（`渲染文档`）
- `QualityAssessment.renderingProfile` 填充

**Normative Rendering Pipeline**：

```
SSIRDocument (L3)
      │
      ▼
Rendering IR Builder
      │
      ├── Semantic Rendering Rules
      │   ├── section → heading
      │   ├── clause → numbered clause
      │   ├── table → table
      │   ├── figure → figure
      │   └── formula → formula
      │
      ├── ALLOWED_NORMALIZATIONS 应用
      │   ├── whitespace_normalization
      │   ├── line_break_unification
      │   ├── punctuation_normalization
      │   ├── number_format_normalization
      │   ├── unit_abbreviation_normalization
      │   └── reference_separator_normalization
      │
      ├── FORBIDDEN_CHANGES 检查（由 CriticalLossChecker 独立执行）
      │   └── 任何违规 → 渲染失败 + 报告
      │
      └── Presentation Rules
          ├── font / size / spacing
          ├── margins / page setup
          ├── numbering format
          ├── table style
          ├── figure caption
          └── header / footer / page number
      │
      ▼
Rendering IR
      │
      ▼
DOCX Renderer / PDF Converter
      │
      ▼
Rendered Document (渲染文档)
```

**RenderingProfile 结构**（对齐 JSON Schema v0.3 NormativeRenderingProfile）：

```json
{
  "profileName": "GB_T_1.1-2020",
  "profileType": "GB_T_1.1-2020",  // NormativeRenderingProfile 枚举
  "semanticRules": {
    "section": {"rendersAs": "heading1"},
    "clause": {"rendersAs": "heading2"},
    "subClause": {"rendersAs": "heading3"},
    "item": {"rendersAs": "paragraph", "indent": true},
    "annex": {"rendersAs": "heading1", "prefix": "附录"},
    "table": {"rendersAs": "table", "captionPosition": "above"},
    "figure": {"rendersAs": "figure", "captionPosition": "below"},
    "formula": {"rendersAs": "formula", "numberPosition": "right"}
  },
  "allowedNormalizations": [
    "whitespace_normalization",
    "line_break_unification",
    "punctuation_normalization",
    "number_format_normalization",
    "unit_abbreviation_normalization",
    "reference_separator_normalization"
  ],
  "presentationRules": {
    "font": {"heading1": "宋体, 16pt, bold", "paragraph": "宋体, 12pt"},
    "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
    "pageSize": "A4",
    "tableStyle": "GB/T 1.1 Table Style",
    "figureCaption": {"format": "图{number} {text}"},
    "formulaNumber": {"format": "({number})"}
  }
}
```

### 5.8 P8: Round-trip Verification Service

**职责**：验证 SSIR 的往返完整性。验证目标为 `SSIR ≈ Verify`（四层比较 + Critical Loss Check）。

**输入**：
- `SSIRDocument`（L3）- 作为 `SSIR`
- `SourceFile` - 作为 `源文档`
- `NormativeRenderingProfile` - 渲染使用的 Profile

**输出**：
- `RoundTripReport`

**Round-trip Pipeline**：

```
                    ┌───────────────┐
                    │     源文档      │ 
                    └───────┬───────┘
                            │
                     Extraction
                            │
                            ▼
                    ┌───────────────┐
                    │    SSIR      │  ← Round-trip Reference State 
                    └───────┬───────┘
                            │
                  ┌─────────┴─────────┐
                  │                   │
                  ▼                   ▼
         ┌─────────────────┐ ┌─────────────────┐
         │ Rendering       │ │ Critical Loss   │
         │ Fidelity Test   │ │ Check (12项)    │
         │ (独立)          │ │ (SSIR 基准)    │ 
         └─────────────────┘ └─────────────────┘
                  │                   │
                  └─────────┬─────────┘
                            │
                  Normative Rendering
                  (GB/T 1.1-2020 Profile)
                            │
                            ▼
                    ┌───────────────┐
                    │     渲染文档      │  ← 规范化输出
                    └───────┬───────┘
                            │
                     Re-Extraction
                            │
                            ▼
                    ┌───────────────┐
                    │    Verify      │  ← 恢复状态
                    └───────┬───────┘
                            │
                            ▼
                  ┌─────────────────────────────┐
                  │    Four-layer Comparison    │
                  │    SSIR ≈ Verify            │
                  │                             │
                  │ Level 1: Identity (STRICT)  │
                  │ Level 2: Structural (STRICT)│
                  │ Level 3: Content (NORMALIZED)│
                  │ Level 4: Semantic (STRICT)  │
                  └─────────────────────────────┘
                            │
                            ▼
                  ┌─────────────────────────────┐
                  │    Critical Information     │
                  │    Loss Check (12项)        │
                  │    SSIR vs Verify           │
                  └─────────────────────────────┘
                            │
                            ▼
                  ┌─────────────────────────────┐
                  │    Round-trip Report        │
                  └─────────────────────────────┘
```

**四层比较的验证规则**：

#### Level 1: Identity Equivalence（STRICT）

| 维度 | 比较内容 | 允许差异 |
|------|----------|----------|
| Identity | 标准号、标题、日期、发布机构 | 无 |

#### Level 2: Structural Equivalence（STRICT）

| 维度 | 比较内容 | 允许差异 |
|------|----------|----------|
| Structure | 节点数量、层级、编号 | 无 |

#### Level 3: Content Equivalence（NORMALIZED）

| 维度 | 比较内容 | 允许差异 |
|------|----------|----------|
| Content | 文本内容（归一化后） | ALLOWED_NORMALIZATIONS |
| Tables | 行列数、单元格内容 | 无 |
| Figures | 数量、图题 | 无 |
| Formulas | 数量、rawText | 无 |
| Lists | 数量、层级、标记 | 标记样式变体 |
| References | 数量、rawTarget | 无 |
| Ordering | 内容元素顺序 | 无 |

#### Level 4: Semantic Equivalence（STRICT）

| 维度 | 比较内容 | 允许差异 |
|------|----------|----------|
| Semantics | Requirement, Scope, Definition, etc. | 无 |

### 5.9 CriticalLossChecker Module（新增）

**职责**：执行 Data Model v0.4 §7.3 定义的 12 项 Critical Information Loss 检查。

**输入**：
- `SSIR`（基准状态）
- `Verify`（恢复状态）

**输出**：
- `CriticalLossResult`（包含所有检查项状态和违规列表）

**12 项检查清单**：

| 编号 | 检查项 | 说明 |
|------|--------|------|
| C1 | Normative Wording | 规范性动词不得改变（应 → 宜） |
| C2 | Prohibitions | 禁止性表述不得改变（不得 → 不应） |
| C3 | Mandatory Conditions | 强制条件不得改变 |
| C4 | Numerical Values | 数值不得改变（90 → 80） |
| C5 | Units | 单位不得改变（MPa → kPa） |
| C6 | Comparison Operators | 比较符不得改变（≥ → >） |
| C7 | Clause Identifiers | 条款编号不得改变（5.2.1 → 5.2） |
| C8 | Table Cell Content | 表格单元格内容不得改变 |
| C9 | Formula Raw Representation | 公式原始表示不得改变 |
| C10 | Reference Raw Target | 引用原始文本不得改变 |
| C11 | Scope | 范围声明不得改变 |
| C12 | Applicability | 适用性声明不得改变 |

**CriticalLossResult 结构**：

```json
{
  "status": "PASS" | "FAIL",
  "violations": [
    {
      "type": "normative_wording",
      "description": "规范性动词变化: '应' → '宜'",
      "location": "clause-5.2",
      "expected": "应",
      "actual": "宜"
    }
  ],
  "checks": {
    "normative_wording": "PASS",
    "prohibition": "PASS",
    "mandatory_condition": "PASS",
    "numerical_value": "PASS",
    "unit": "PASS",
    "comparison_operator": "PASS",
    "clause_identifier": "PASS",
    "table_cell": "PASS",
    "formula_raw": "PASS",
    "reference_raw": "PASS",
    "scope": "PASS",
    "applicability": "PASS"
  }
}
```

**关键原则**：任何一项检查发现变化 → Round-trip 直接 **FAIL**。

### 5.10 Rendering Fidelity Test（独立）

**职责**：独立测试渲染器的保真度（`SSIR → DOCX/PDF → SSIR'`），与 Round-trip Equivalence 分离。

**测试链路**：

```
SSIR
  │
  ▼
Normative Rendering
  │
  ▼
DOCX/PDF
  │
  ▼
Re-Extraction
  │
  ▼
SSIR'
  │
  ▼
Compare SSIR ≈ SSIR'
```

**关键原则**：
- 这是**独立的测试**，与 Round-trip Equivalence 并行
- 测试渲染器是否能够重新提取而不发生不可接受的信息损失
- 失败不直接导致 Round-trip FAIL，但会生成 WARN 报告

### 5.11 UnknownContent 增强

UnknownContent 是保底机制，确保无法识别的内容不被丢弃。

```json
{
  "id": "ssir:.../unknown/u-001",
  "rawContent": "...",
  "contentTypeHint": "decorative-box",
  "originalBlockType": "graphic",
  "reason": "unsupported_layout",
  "confidence": 0.42,
  "sourceAnchors": [...]
}
```

**字段说明**：
- `originalBlockType`：提取器识别的原始类型
- `reason`：无法识别的具体原因
- `confidence`：识别置信度


## 6. Infrastructure & Technology Stack

| 模块 | 技术 | 版本 |
|------|------|------|
| 主语言 | Python | 3.11+ |
| API 框架 | FastAPI | 0.100+ |
| 异步任务 | Celery | 5.3+ |
| 任务 Broker | Redis | 7.0+ |
| 数据库 | PostgreSQL | 15+ |
| ORM | SQLAlchemy | 2.0+ |
| 对象存储 | MinIO | RELEASE.2024 |
| PDF 解析 | MinerU | 最新稳定版 |
| PDF 基础处理 | PyMuPDF | 1.23+ |
| DOCX 处理 | python-docx | 1.1+ |
| OCR | MinerU 内置 + 可插拔 | - |
| Schema 验证 | Pydantic + JSON Schema | 2.5+ |
| 测试 | pytest | 7.4+ |
| 容器 | Docker | 24.0+ |
| 编排 | Docker Compose | 2.23+ |


## 7. Project Structure

```
leleby-ssir-engine/
│
├── apps/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   └── models/
│   └── worker/
│       ├── main.py
│       ├── celery_config.py
│       └── tasks/
│
├── packages/
│   ├── core/
│   │   ├── ssir.py                    # SSIR v0.4
│   │   ├── extraction_ir.py
│   │   ├── rendering_ir.py
│   │   ├── enums.py                   # 含 NormativeRenderingProfile
│   │   ├── equivalence.py             # 四层 Equivalence Model
│   │   ├── roundtrip.py               # RoundTripReport
│   │   └── transformation.py          # ALLOWED_NORMALIZATIONS / FORBIDDEN_CHANGES
│   │
│   ├── ingestion/
│   ├── extraction/
│   ├── canonical_text/
│   ├── ssir_builder/
│   │   ├── metadata.py
│   │   ├── structure.py
│   │   ├── content.py
│   │   ├── table.py
│   │   ├── figure.py
│   │   ├── formula.py
│   │   ├── provenance.py
│   │   └── unknown.py
│   │
│   ├── semantic_enrichment/           # L4 - 独立于 SSIR Builder
│   │   ├── reference.py
│   │   ├── entity.py
│   │   └── relation.py
│   │
│   ├── validator/
│   │   ├── schema.py
│   │   ├── structural.py
│   │   ├── content.py
│   │   ├── provenance.py
│   │   └── quality.py                # 含 renderingProfile
│   │
│   ├── rendering/
│   │   ├── __init__.py
│   │   ├── renderer.py
│   │   ├── profile.py                 # NormativeRenderingProfile
│   │   ├── gb_t_1_1_profile.py        # GB/T 1.1-2020
│   │   ├── docx_renderer.py
│   │   └── pdf_converter.py
│   │
│   ├── roundtrip/
│   │   ├── __init__.py
│   │   ├── verifier.py                # 主验证器
│   │   ├── comparator.py              # 四层比较器
│   │   ├── critical_check.py          # 12项 Critical Loss Check
│   │   ├── report.py                  # RoundTripReport
│   │   └── fidelity.py                # Rendering Fidelity Test
│   │
│   └── storage/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── golden/
│   └── roundtrip/
│
├── fixtures/
│   ├── golden/
│   └── sample/
│
├── docker/
├── scripts/
├── config.yaml
└── pyproject.toml
```


## 8. Acceptance Criteria (Phase 1)

Phase 1 必须通过的验收标准：

| Gate | 名称 | 要求 | Data Model v0.4 依据 |
|------|------|------|---------------------|
| **G1** | Schema Gate | 100% required schema tests PASS（含 v0.3 新字段） | §6 |
| **G2** | Extraction Gate | Core Golden Dataset PASS | §7.2 Source Fidelity |
| **G3** | Structural Gate | 100% critical structure preserved | §7.6 |
| **G4** | Content Gate | ≥ 99% content preserved（归一化后） | §7.6 |
| **G5** | Critical Gate | **0 critical information loss**（12 项检查全通过） | §7.3 |
| **G6** | Normative Rendering Gate | ALLOWED_NORMALIZATIONS 正确应用，FORBIDDEN_CHANGES 0 违规 | §7.3 |
| **G7** | Round-trip Gate | All P0 Round-trip PASS（四层比较全通过） | §7.5 |
| **G8** | Regression Gate | 0 regression in frozen Golden Dataset | — |

**详细说明**：

| 指标 | 目标值 | 说明 | Data Model v0.4 依据 |
|------|--------|------|---------------------|
| Identity Equivalence | 100% | 标准号、标题、日期等 | §7.6 STRICT |
| Structural Equivalence | 100% | 章节/条款/项完整 | §7.6 STRICT |
| Content Equivalence | ≥ 99% | 归一化后内容一致 | §7.6 NORMALIZED |
| Table Recall | 100% | 表格行/列/单元格完整 | §7.6 STRICT |
| Figure Preservation | 100% | 所有图元素存在 | §7.6 STRICT |
| Formula Preservation | 100% | 所有公式 rawText 非空 | §7.6 STRICT |
| Reference Preservation | 100% | 原始引用文本保留 | §7.6 STRICT |
| Critical Information Loss | **0** | 12 项检查全通过 | §7.3 |
| Semantic Equivalence | 100% | Requirement/Scope/Definition 不变 | §7.6 STRICT |
| Rendering Profile | 正确填充 | QualityAssessment.renderingProfile | JSON Schema v0.3 |
| Source Traceability | 100% | 核心对象有 SourceAnchor | §7.2 |


## 9. Sprint Breakdown

### Sprint 0 — Contract Freeze

**目标**：冻结所有核心契约。

**任务**：
1. 确认 SSIR v0.4 数据模型
2. 完成 JSON Schema v0.3
3. 定义 SSIR Preservation Contract（含 ALLOWED_NORMALIZATIONS / FORBIDDEN_CHANGES）
4. 定义 Extraction IR Contract
5. 定义 CanonicalText / TextSpan Contract
6. 定义 Round-trip Equivalence Contract（四层比较）
7. 定义 12 项 Critical Loss Check
8. 准备 Golden Dataset（≥ 10 个文档，含 Normative Rendering 测试文档）

**验收标准**：
- 所有 Contract 文档完成评审
- Golden Dataset 覆盖所有特征类型

### Sprint 1 — Ingestion & Extraction

**目标**：完成 Ingestion 和 Extraction，输出 Extraction IR。

**任务**：
1. 实现 DocumentDetector（含 textLayerQuality）
2. 实现 SourceFileBuilder
3. 实现 MinerU Adapter（支持文本/扫描/混合 PDF）
4. 实现 DOCX Adapter
5. 实现 OCR Pipeline
6. 实现 LayoutAnalyzer
7. 实现 ReadingOrderResolver
8. 实现 Extraction IR 模型

**验收标准**：
- 文本 PDF → Extraction IR 100% 完成
- 扫描 PDF → Extraction IR 完成
- DOCX → Extraction IR 完成
- Extraction IR 包含 page、block、bbox、text、reading_order、sourceMethod

### Sprint 2 — CanonicalText + Structure

**目标**：实现 CanonicalText 和结构构建，输出 SSIR Level 1。

**任务**：
1. 实现 CanonicalTextBuilder
2. 实现 TextSpan 生成
3. 实现 MetadataExtractor
4. 实现 StructureBuilder（章节编号解析、层级建立）
5. 实现 DocumentBlock 识别

**验收标准**：
- CanonicalText 正确生成
- TextSpan 正确定位
- 结构树正确反映文档层级
- SSIR Level 1 验证通过

### Sprint 3 — Content Complete

**目标**：实现所有内容元素构建，输出 SSIR Level 2。

**任务**：
1. 实现 ContentBuilder（paragraph/heading/list/note/example/warning/quote/footnote）
2. 实现 TableBuilder（含 row/col/merged cells/tableNote/crossPage）
3. 实现 FigureBuilder（含 number/caption/assetRef）
4. 实现 FormulaBuilder（含 number/rawText/latex）
5. 实现 ListBuilder（含 marker/markerType/subItems）
6. 实现 UnknownContentHandler

**验收标准**：
- 所有内容元素正确分类和构建
- 表格完整（含合并单元格）
- 图、公式完整
- 未知内容进入 UnknownContent
- SSIR Level 2 验证通过

### Sprint 4 — Provenance

**目标**：建立所有对象的 SourceAnchor，输出 SSIR Level 3。

**任务**：
1. 实现 SourceAnchorBuilder
2. 为所有 StructuralNode 建立 SourceAnchor
3. 为所有 ContentElement 建立 SourceAnchor
4. 为所有 Table/Figure/Formula 建立 SourceAnchor
5. 为所有 EntityMention/RelationMention 建立 SourceAnchor
6. 实现 assetRef 管理

**验收标准**：
- 所有核心对象有 SourceAnchor
- SourceAnchor 包含 pdfPageIndex/bbox/textSpanRef
- assetRef 指向实际资源
- SSIR Level 3 验证通过
- **Round-trip Ready**

### Sprint 5 — Reference & Semantic Enrichment (Optional for L4)

**目标**：实现 Reference/Entity/Relation 提取，输出 SSIR Level 4。

**任务**：
1. 实现 ReferenceExtractor（规范性引用、内部引用、外部引用）
2. 实现 Reference 解析（rawTarget → resolvedDocumentId）
3. 实现 EntityExtractor（实体提及识别）
4. 实现 RelationExtractor（关系提及识别）
5. 实现 DocumentRelationship 提取

**验收标准**：
- 引用正确提取和解析
- EntityMention 正确识别
- RelationMention 正确识别
- **本 Sprint 不阻塞 Round-trip**

### Sprint 6 — Normative Rendering

**目标**：实现 SSIR → 传统文档规范性渲染。

**任务**：
1. 实现 Rendering IR 模型
2. 实现 NormativeRenderingProfile 枚举
3. 实现 GB/T 1.1-2020 Rendering Profile（含 ALLOWED_NORMALIZATIONS）
4. 实现 DOCX Renderer
5. 实现 PDF Converter
6. 实现 FORBIDDEN_CHANGES 检查集成

**验收标准**：
- SSIR → DOCX 完整
- SSIR → PDF 完整
- 生成的 DOCX 包含所有结构和内容
- 符合 GB/T 1.1 样式规范
- QualityAssessment.renderingProfile 正确填充
- 无 FORBIDDEN_CHANGES 违规

### Sprint 7 — Round-trip Verification

**目标**：实现四层比较 + Critical Loss Check 往返测试验证。

**任务**：
1. 实现 Source Coverage 报告
2. 实现 SSIR Comparator（四层比较）
3. 实现 CriticalLossChecker（12 项检查）
4. 实现 Round-trip Pipeline（`源文档 → SSIR → 渲染文档 → Verify`）
5. 实现 Rendering Fidelity Test（独立）
6. 实现 RoundTripReport 生成
7. 实现 Golden Test 套件（含 Normative Rendering 测试）

**验收标准**：
- Round-trip Pipeline 完整
- 比较维度覆盖 Identity/Structural/Content/Semantic 四层
- Critical Loss 12 项检查完整实现
- Rendering Fidelity Test 独立实现
- Golden Test 通过率 100%（Dataset A）/ ≥ 98%（Dataset B）
- Normative Rendering 测试通过


## 10. Version History

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 0.1 | 2026-08-15 | 初始版本 |
| 0.2 | 2026-08-15 | 新增 Preservation Levels & Contract；Reference/Entity/Relation 从 SSIR Builder 拆分；增强 SourceAnchor/ProcessingRun/QualityAssessment；版本化 Repository |
| 0.3 | 2026-08-15 | 调整 Round-trip 核心定义为 `SSIR ≈ Verify`；重构 Round-trip Verification Service 为三层比较；删除 matchRate 单一指标；新增 Critical Information Loss Check；验收指标与 v0.2 测试规范 Gate 体系对齐 |
| 0.4 | 2026-08-15 | 与 Data Model v0.4 和 JSON Schema v0.3 对齐；Round-trip 比较升级为四层（Identity/Structural/Content/Semantic）；新增 CriticalLossChecker 子模块（12 项检查）；Rendering Service 升级为 Normative Rendering Service；明确 ALLOWED_NORMALIZATIONS / FORBIDDEN_CHANGES 边界；QualityAssessment 增加 renderingProfile 字段；更新数据流图；更新 Acceptance Criteria（增加 Critical Gate 和 Normative Rendering Gate） |
| 0.5 | 2026-08-17 | 明确 M1 将原始 Markdown 基础纠错为 `Canonical` 后完成 `Canonical → SSIR → Render.md → Verify` 回环；CSM Renderer、重提取、四层比较与报告属于 M1，PDF/MinerU/OCR/DOCX 保持 M2 预留 |


## 11. Next Steps

1. **Review & Freeze**: 本规范与 Data Model v0.4、JSON Schema v0.3、Test Specification v0.3 联合评审并冻结
2. **实现 CriticalLossChecker**: 实现 12 项 Critical Loss 检测
3. **实现 Normative Rendering**: 实现 ALLOWED_NORMALIZATIONS 应用和 FORBIDDEN_CHANGES 检查
4. **实现四层 Comparator**: 升级比较器为四层比较
5. **编写 AI Coding Specification**: 将本规范转化为可执行的开发任务
6. **Sprint 0 启动**: 冻结所有契约，准备 Golden Dataset（含 Normative Rendering 测试文档）
