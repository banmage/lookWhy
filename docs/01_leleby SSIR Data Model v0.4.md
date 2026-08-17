# leleby SSIR Data Model v0.4 — Core Object Model

> **文档状态**：正式发布 | **版本**：0.4 | **日期**：2026-08-15
>
> **v0.4 主要修订**（基于 v0.3 的 Round-trip 语义增强，不推翻核心对象模型）：
> - **重新定义 Round-trip 闭环**：明确 `Std₀ → SSIR₁ → Std₁ → SSIR₂` 为 Round-trip 核心链路，验证目标为 `SSIR₁ ≈ SSIR₂`，而非 `Std₀ ≈ Std₁`
> - **新增 §3 术语**：`Round-trip Equivalence`、`Normative Rendering`
> - **§4 设计原则**：将原第 12 条拆分为第 12 条（Completeness）和第 13 条（Equivalence）
> - **§7 Round-trip Requirements**：完全重写，包含 Source Fidelity、Normative Rendering、Re-extraction、SSIR Equivalence、Rendering Conformance 五个子节
> - **§7.6 Equivalence Classification Table**：明确哪些字段必须等价、哪些允许变化、哪些可忽略
> - **§10 Preservation Levels**：新增与 Round-trip 关系的说明
> - **§2 Normative References**：新增 GB/T 1.1-2020 引用


## 1. Scope

本文件定义 leleby SSIR（Standard Structured Information Representation）的核心对象模型。

SSIR 是 leleby 对已发布标准、法规及其他规范性文件进行结构化数字化后的规范化中间表示。SSIR 以源文件为中心，忠实保存文件的身份与元数据、文档逻辑结构、内容表达要素、表格/图/公式等具体内容、文档间关系、内部与外部引用、实体提及、关系提及，以及从结构化结果到源文件的完整溯源信息。

**SSIR 的本质是“树 + 图 + 溯源”**：
- **树**：文档的逻辑结构（章、条、款、项、附录）
- **图**：引用图、实体关系图、文档关系图
- **溯源**：每个结构化对象到源文件（PDF 页面/区域/文本区间）的完整定位

**SSIR 不负责**：建立行业知识本体、跨标准知识融合、合规推理、直接表达 leleby Requirement/Product/Verification/Compliance 等领域知识对象。

**SSIR 支持双向转换**：
- **正向**：源文档 → SSIR（结构化提取）
- **逆向**：SSIR → 传统格式文档（Markdown/HTML/DOCX 等），完整复现全部元素和内容


## 2. Normative References

下列文件对于本文件的应用是必不可少的。凡是注日期的引用文件，仅注日期的版本适用于本文件。凡是不注日期的引用文件，其最新版本（包括所有的修改单）适用于本文件。

- GB/T 22373-2021 标准文献元数据
- GB/T 42093.1-2022 标准文档结构化 元模型 第1部分：全文
- GB/T 47462-2026 数字标准 标准信息模型架构
- GB/T 46917.1 标准语义知识库 第1部分：标准内容语义化表达通用要求
- GB/T 1.1-2020 标准化工作导则 第1部分：标准化文件的结构和起草规则


## 3. Terms and Definitions

下列术语和定义适用于本文件。

| 术语 | 定义 |
|------|------|
| **SSIR** | Standard Structured Information Representation。leleby 对已发布标准、法规及其他规范性文件进行结构化数字化后的规范化中间表示 |
| **Structural Node** | 结构节点。标准文档逻辑层次结构中的节点，如 Document、Block、Section、Clause、Annex 等 |
| **Content Element** | 内容元素。挂载于结构节点下的内容表达单元，包括段落、列表、表格、图、公式、注、脚注等 |
| **Entity Mention** | 实体提及。从标准文本中识别出的实体名称或术语的原始出现，不绑定 Ontology Class |
| **Relation Mention** | 关系提及。从标准文本中识别出的实体间语义关系的原始出现 |
| **Reference** | 引用。标准文档中的规范性或资料性引用，目标可以是内部条款或外部文献 |
| **Document Relationship** | 文档关系。标准文档之间的事实关系（代替、修改、补充、等效、采纳等） |
| **Source Anchor** | 源锚点。SSIR 对象到源文件（PDF 等）的定位信息 |
| **Text Span** | 文本区间。SSIR 规范化文本流中的字符位置区间 |
| **Processing Run** | 处理运行记录。一次从源文件提取/处理生成 SSIR 的过程记录 |
| **Canonical Text** | 规范文本。SSIR 中用于检索和文本定位的统一规范化全文 |
| **Round-trip Completeness** | SSIR 是否保存了足以重新构造源文档全部逻辑结构、内容元素和信息的能力 |
| **Round-trip Equivalence** | SSIR 经 `SSIR → 渲染 → 重新提取` 循环后，其结构、内容和语义是否保持等价的性质 |
| **Normative Rendering** | 从 SSIR 生成传统文档时，依据指定 Rendering Profile 对格式、编号、标点等进行规范化的过程 |


## 4. Design Principles

SSIR 数据模型遵循以下设计原则：

| 编号 | 原则 | 说明 |
|------|------|------|
| 1 | **Source Fidelity（源文件保真）** | 尽可能忠实保存源文件内容，不擅自改写原文 |
| 2 | **Structural Preservation（结构保持）** | 不破坏原始文档逻辑层级 |
| 3 | **Orthogonal Modeling（正交建模）** | 逻辑结构、内容表达形式、语义类型三个维度分离 |
| 4 | **Traceability（可追溯）** | 每一个重要对象均可追溯到源文件的具体位置 |
| 5 | **Provenance（来源记录）** | 所有自动处理结果记录处理来源（工具、版本、时间等） |
| 6 | **Semantic Neutrality（语义中立）** | SSIR 不强制绑定行业本体或领域知识模型 |
| 7 | **Extensibility（可扩展）** | 支持标准、法规、企业规范等不同文件类型 |
| 8 | **Machine Readability（机器可读）** | SSIR 必须可以被机器直接处理 |
| 9 | **Human Verifiability（人工可验证）** | 人可以借助 SSIR 回到原文件进行审核 |
| 10 | **Serialization Independence（序列化无关）** | SSIR 数据模型与 JSON/XML/RDF 等具体序列化格式解耦 |
| 11 | **Graph Awareness（图感知）** | SSIR 不是单一树，而是树 + 引用图 + 关系图 + 溯源图的组合 |
| 12 | **Round-trip Completeness（往返完整性）** | SSIR 必须保存足以重新构造源规范文件全部逻辑结构、内容元素、文本内容、表格数据、图、公式、列表、注、脚注、引用、附录及其顺序关系的信息。反向生成的文档不要求完全复现源文件的版式、字体、分页和视觉细节，但不得丢失原文件中任何具有文档语义或内容意义的元素 |
| 13 | **Round-trip Equivalence（往返等价性）** | SSIR 经 `SSIR → 传统文档渲染 → 重新提取` 循环后，其结构、内容和语义应保持等价。Round-trip 的判定应以 `SSIR₁ ≈ SSIR₂` 为核心依据，而非以源文档与重建文档的字节级、字符级或版式级一致为依据 |

**原则 12 的补充说明**：
- Semantic extraction failure shall never cause source content loss（语义识别失败不应导致内容丢失）
- 即使实体识别、关系识别、语义分类全部失败，SSIR 仍然必须能够反向生成包含全部元素和内容的文档

**原则 12 与 13 的关系**：
- **Completeness（完整性）** 回答：SSIR 有没有保存足够的信息？
- **Equivalence（等价性）** 回答：保存的信息经过 `SSIR → Std → SSIR` 循环后有没有发生实质性变化？
- 两者共同构成 Round-trip 质量的两个正交维度。


## 5. SSIR Conceptual Model

SSIR 的对象世界由以下核心概念及其关系构成：

```
                              SSIRDocument
                                   │
       ┌───────────┬───────────────┼───────────────┬───────────┬──────────────┐
       ▼           ▼               ▼               ▼           ▼              ▼
   Metadata    SourceFiles   ProcessingRuns   Document     Quality    CanonicalText
                  │                         Relationships  Assessment      │
                  │                              │                         │
                  ▼                              ▼                         ▼
           StructuralTree                   ReferenceGraph           TextSpan
                  │                              │
                  ▼                              ▼
           StructuralNode                 ┌──────┴──────┐
                  │                       │             ▼
                  ▼                       ▼      Document
           ContentElement            Relationship
                  │
       ┌──────────┼──────────┬───────────┐
       ▼          ▼          ▼           ▼
    Text/List   Table     Figure      Formula
       │          │          │           │
       ▼          ▼          ▼           ▼
    ListItem  TableRow   (asset)     (rawText)
       │          │
       ▼          ▼
   (marker)   TableCell
                  │
              (richText)
                  │
       ┌──────────┴───────────┐
       ▼                      ▼
   EntityMention        RelationMention
       │                      │
       └──────────────────────┼──────────────┐
                              ▼              ▼
                    SourceAnchor +     UnknownContent
                    TextSpan         (fallback)
                              │
                              ▼
                         SourceFile
```

**核心实体分类**：

| 类别 | 实体 |
|------|------|
| **文档层** | SSIRDocument, DocumentMetadata, SourceFile, CanonicalText |
| **结构层** | StructuralNode |
| **内容层** | ContentElement, Table, TableRow, TableCell, Figure, Formula, ListItem, UnknownContent |
| **引用/关系层** | Reference, DocumentRelationship |
| **语义提及层** | EntityMention, RelationMention |
| **溯源层** | SourceAnchor, TextSpan |
| **处理/质量层** | ProcessingRun, QualityAssessment |


## 6. Core Object Model

### 6.1 SSIRDocument

SSIRDocument 是 SSIR 的根对象，代表一份标准/法规文件的结构化表示。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | SSIR 文档唯一标识符 |
| ssirVersion | M | String | SSIR 数据模型版本号，如 "0.4" |
| documentType | M | Enum | 文档类型：standard \| regulation \| specification \| enterpriseStandard \| contract \| testReport \| other |
| metadata | M | DocumentMetadata | 文档元数据 |
| sourceFiles | M | Array[SourceFile] | 源文件列表（至少一个） |
| canonicalText | O | CanonicalText | 规范全文文本 |
| structuralRoot | M | StructuralNode | 结构树的根节点 |
| references | O | Array[Reference] | 文档中的引用 |
| documentRelationships | O | Array[DocumentRelationship] | 文档间关系 |
| entityMentions | O | Array[EntityMention] | 实体提及列表 |
| relationMentions | O | Array[RelationMention] | 关系提及列表 |
| processingRuns | M | Array[ProcessingRun] | 处理运行记录（至少一个） |
| qualityAssessments | O | Array[QualityAssessment] | 质量评估记录 |
| preservationLevel | O | Enum | 保存等级（见 §10 Preservation Levels） |
| createdAt | M | DateTime | 创建时间 |
| updatedAt | O | DateTime | 更新时间 |

**id 规则**：`ssir:{文档标识符}`，如 `ssir:GBT-22373-2021`。

**约束**：
- `sourceFiles` 至少包含一个元素。
- `processingRuns` 至少包含一个元素。
- `structuralRoot` 必须为非空结构树。


### 6.2 DocumentMetadata

DocumentMetadata 承载文档元数据。采用“通用元数据 + 类型专用元数据”模式。

#### 6.2.1 CommonMetadata（通用元数据）

所有文档类型通用。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| documentIdentifier | M | String | 文档唯一标识符（标准号/文件编号/合同号等） |
| title | M | String | 文档标题 |
| titleEn | O | String | 英文标题 |
| language | O | String | 正文语种（GB/T 4880.1 代码） |
| publicationDate | O | String | 发布日期（YYYY-MM-DD） |
| effectiveDate | O | String | 生效/实施日期（YYYY-MM-DD） |
| issuer | O | String | 发布/颁发机构 |
| status | O | String | 文档状态（现行/废止/草案等） |
| version | O | String | 版本号 |

#### 6.2.2 StandardMetadata（标准专用元数据）

当 `documentType = standard` 时使用。

| 属性 | 约束 | 类型 | 说明 | 对应 GB/T 22373 |
|------|------|------|------|-----------------|
| standardNumber | C | String | 标准编号 | 3100 |
| chineseTitle | C | String | 中文标准名称 | 7298 |
| englishTitle | C | String | 英文标准名称 | 7302 |
| originalTitle | O | String | 原文标准名称 | 7301 |
| publishingBody | O | String | 发布机构 | 4102 |
| publishingBodyCode | O | String | 发布机构代码 | 4104 |
| ccs | O | String | 中国标准分类号 | 4825 |
| ics | O | String | 国际标准分类号 | 4826 |
| drafters | O | Array[String] | 起草单位 | 4209 |
| proposer | O | String | 提出单位 | 4870 |
| mirrorBody | O | String | 归口单位 | 4871 |
| adoption | O | String | 一致性程度 | 4800 |

**约束**：
- `documentType = standard` 时，`standardNumber` 必选。
- `chineseTitle`、`englishTitle`、`originalTitle` 至少存在一个。


### 6.3 SourceFile

SourceFile 表示被解析的具体源文件（包括 CSM Markdown、PDF 等），独立于 SSIRDocument 的逻辑身份。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 源文件唯一标识符 |
| fileName | M | String | 文件名 |
| filePath | O | String | 存储路径 |
| fileHash | M | String | 文件哈希值（SHA-256 推荐） |
| fileSize | O | Integer | 文件大小（字节） |
| mimeType | M | String | MIME 类型，如 "text/markdown"、"application/pdf" |
| pageCount | O | Integer | 总页数 |
| metadata | O | Object | 文件元数据（创建时间、修改时间等） |

**id 规则**：`src:{hash前16位}`，如 `src:a1b2c3d4e5f67890`。


### 6.4 StructuralNode

StructuralNode 是标准文档逻辑结构树中的节点。**仅表达逻辑层次，不承载具体内容**。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 节点唯一标识符 |
| logicalId | M | String | 人类可读的逻辑标识符 |
| nodeType | M | Enum | 节点类型（见枚举 9.1） |
| level | O | Integer | 层级深度（章=1，条=2，款=3，项=4） |
| number | O | String | 编号字符串，如 "5"、"5.2"、"5.2.1"、"a" |
| title | O | String | 章节标题文本 |
| children | O | Array[StructuralNode] | 子节点列表 |
| contentElements | O | Array[ContentElement] | 挂载的内容元素（按 `sortOrder` 排序） |
| sourceAnchors | M | Array[SourceAnchor] | 源定位信息（至少一个） |
| sortOrder | M | Integer | 同层级内的排序序号 |

**nodeType 枚举（仅逻辑结构）**：
- `document` — 文档根节点
- `documentBlock` — 文档分块（cover/toc/foreword/introduction/mainBody/annex/reference/index）
- `section` — 章
- `clause` — 条
- `subClause` — 款
- `item` — 项
- `subItem` — 子项
- `annex` — 附录（规范性/资料性）
- `annexSection` — 附录内的章/条

**id 规则**：`{documentId}/{logicalId}`，如 `ssir:GBT-22373-2021/clause-5.2`。

**logicalId 规则**：
- 章/条/款/项：`clause-{number}`，如 `clause-5.2`
- 附录：`annex-{letter}`，如 `annex-A`
- 分块：`block-{blockType}`，如 `block-foreword`

**约束**：
- `nodeType` 为 `document` 的节点必须且只能有一个，作为结构树根节点。
- `sortOrder` 在同一父节点下必须连续且不重复。
- `sourceAnchors` 至少有一个元素。


### 6.5 ContentElement

ContentElement 是挂载于 StructuralNode 下的内容表达单元。**承载可见内容，独立于逻辑结构**。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 内容元素唯一标识符 |
| presentationType | M | Enum | 内容表达形式（见枚举 9.2） |
| parentNodeId | M | String | 所属 StructuralNode 的 id |
| semanticTypes | O | Array[Enum] | 内容要素语义类型（见枚举 9.3），可多标签 |
| normativeStatus | O | Enum | 规范性状态（见枚举 9.4） |
| sortOrder | M | Integer | 在父节点内的排序序号 |
| sourceAnchors | M | Array[SourceAnchor] | 源定位信息（至少一个） |
| textContent | O | String | 纯文本内容（适用于 paragraph/heading/note/example/quote） |
| richText | O | Array[RichTextSpan] | 富文本片段（含样式标记） |
| listItems | O | Array[ListItem] | 列表项（仅 presentationType=list） |
| tableRef | O | String | 关联 Table 对象的 id（仅 presentationType=table） |
| figureRef | O | String | 关联 Figure 对象的 id（仅 presentationType=figure） |
| formulaRef | O | String | 关联 Formula 对象的 id（仅 presentationType=formula） |
| unknownRef | O | String | 关联 UnknownContent 对象的 id（仅 presentationType=other） |

**presentationType 枚举（内容表达形式）**：
- `paragraph` — 普通段落
- `heading` — 标题
- `list` — 列表
- `table` — 表格（关联 Table 对象）
- `figure` — 图（关联 Figure 对象）
- `formula` — 公式（关联 Formula 对象）
- `note` — 注
- `example` — 示例
- `warning` — 警示
- `quote` — 引用文本
- `footnote` — 脚注
- `other` — 未知类型（关联 UnknownContent 对象，保底机制）

**ListItem**：

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 列表项 ID |
| text | O | String | 列表项文本 |
| richText | O | Array[RichTextSpan] | 富文本内容 |
| marker | O | String | 列表项标记，如 "a)"、"1)"、"•" |
| markerType | O | Enum | 标记类型：lowerAlpha \| upperAlpha \| numeric \| roman \| bullet \| dash \| other |
| subItems | O | Array[ListItem] | 子列表项（递归） |
| sourceAnchor | O | SourceAnchor | 源定位 |
| sortOrder | M | Integer | 在列表内的排序序号 |

**RichTextSpan**：

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| text | M | String | 文本片段 |
| bold | O | Boolean | 是否加粗 |
| italic | O | Boolean | 是否斜体 |
| subscript | O | Boolean | 是否下标 |
| superscript | O | Boolean | 是否上标 |
| underline | O | Boolean | 是否下划线 |
| style | O | String | 其他样式 |

**id 规则**：`{documentId}/content/{序号}`，如 `ssir:GBT-22373-2021/content/c-001`。

**约束**：
- 每个 ContentElement 必须属于且仅属于一个 StructuralNode。
- `presentationType=table` 时，`tableRef` 必须非空。
- `presentationType=figure` 时，`figureRef` 必须非空。
- `presentationType=formula` 时，`formulaRef` 必须非空。
- `presentationType=other` 时，`unknownRef` 必须非空。
- `semanticTypes` 可为空（如纯资料性注释）。


### 6.6 Table / TableRow / TableCell

Table 是表格内容的独立结构化表示。

#### 6.6.1 Table

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 表格唯一标识符 |
| number | O | String | 表编号，如 "表1"、"Table 1" |
| caption | O | String | 表标题 |
| rowCount | M | Integer | 总行数 |
| colCount | M | Integer | 总列数 |
| rows | M | Array[TableRow] | 行数组 |
| tableNote | O | Array[String] | 表注 |
| sourceAnchors | M | Array[SourceAnchor] | 源定位信息 |
| crossPage | O | Boolean | 是否跨页 |
| preservationStatus | O | Enum | preserved \| partiallyPreserved \| notPreserved |

#### 6.6.2 TableRow

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 行唯一标识符 |
| rowIndex | M | Integer | 行索引（从 0 开始） |
| cells | M | Array[TableCell] | 单元格数组 |
| isHeader | O | Boolean | 是否为表头行 |

#### 6.6.3 TableCell

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 单元格唯一标识符 |
| rowIndex | M | Integer | 行索引（从 0 开始） |
| colIndex | M | Integer | 列索引（从 0 开始） |
| text | O | String | 单元格纯文本内容 |
| richText | O | Array[RichTextSpan] | 单元格富文本内容 |
| colspan | O | Integer | 跨列数，默认 1 |
| rowspan | O | Integer | 跨行数，默认 1 |
| isHeader | O | Boolean | 是否为表头单元格 |
| sourceAnchor | O | SourceAnchor | 单元格级源定位 |

**id 规则**：
- Table: `{documentId}/table/{序号}`，如 `ssir:GBT-22373-2021/table/t-001`
- TableRow: `{tableId}/row/{rowIndex}`
- TableCell: `{tableId}/cell/{rowIndex}-{colIndex}`

**约束**：
- 每行的 `cells` 数量应与 `colCount` 一致（考虑 colspan 后）。
- `rowCount` 必须等于 `rows` 数组长度。


### 6.7 Figure

Figure 是图片内容的独立结构化表示。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 图唯一标识符 |
| number | O | String | 图编号，如 "图1"、"Figure 1" |
| caption | O | String | 图题/图注 |
| assetRef | O | String | 图片资产引用（文件路径/URL/Base64 等） |
| altText | O | String | 替代文本 |
| sourceAnchors | M | Array[SourceAnchor] | 源定位信息 |
| preservationStatus | O | Enum | preserved \| partiallyPreserved \| notPreserved |

**id 规则**：`{documentId}/figure/{序号}`，如 `ssir:GBT-22373-2021/figure/f-001`。


### 6.8 Formula

Formula 是公式内容的独立结构化表示。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 公式唯一标识符 |
| number | O | String | 公式编号，如 "(1)" |
| rawText | M | String | 原始文本表示 |
| latex | O | String | LaTeX 表示（如可获取） |
| sourceAnchors | M | Array[SourceAnchor] | 源定位信息 |
| preservationStatus | O | Enum | preserved \| partiallyPreserved \| notPreserved |

**id 规则**：`{documentId}/formula/{序号}`，如 `ssir:GBT-22373-2021/formula/fm-001`。

**约束**：
- `rawText` 必须非空，作为保底内容。
- `latex` 可选，作为增强表示。


### 6.9 UnknownContent

UnknownContent 是保底机制，用于保存无法被现有 PresentationType 覆盖的内容。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 未知内容唯一标识符 |
| rawContent | M | String | 原始内容 |
| contentTypeHint | O | String | 内容类型提示 |
| sourceAnchors | M | Array[SourceAnchor] | 源定位信息 |

**id 规则**：`{documentId}/unknown/{序号}`。

**设计原则**：**无法理解 ≠ 可以丢弃**。UnknownContent 确保所有源内容在 SSIR 中都有归宿。


### 6.10 CanonicalText

CanonicalText 是 SSIR 的规范化全文文本，为 TextSpan 提供统一的文本坐标系。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 规范文本唯一标识符 |
| text | M | String | 规范化全文 |
| normalizationPolicy | O | String | 规范化策略说明（如 "去除多余空白"、"保留原文"等） |
| sourceElementRefs | O | Array[String] | 组成此规范文本的 ContentElement id 列表 |
| version | O | String | 版本号 |

**id 规则**：`{documentId}/canonical`，如 `ssir:GBT-22373-2021/canonical`。

**约束**：
- 每个 SSIRDocument 最多有一个 CanonicalText。
- `text` 应包含文档中所有文本内容，按文档顺序拼接。


### 6.11 TextSpan

TextSpan 表示 SSIR 规范化文本流中的字符位置区间，用于 NLP/检索场景。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 文本区间唯一标识符 |
| canonicalTextId | M | String | 所属 CanonicalText 的 id |
| startChar | M | Integer | 起始字符位置（从 0 开始） |
| endChar | M | Integer | 结束字符位置（开区间） |
| text | M | String | 区间文本内容 |
| sourceAnchor | O | SourceAnchor | 对应的源定位 |

**id 规则**：`{documentId}/span/{序号}`。

**约束**：
- `startChar` <= `endChar`。
- `text` 必须与 CanonicalText 中对应区间的文本一致。


### 6.12 SourceAnchor

SourceAnchor 提供 SSIR 对象到源文件的具体定位信息。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 锚点唯一标识符 |
| sourceFileId | M | String | 关联的 SourceFile id |
| anchorType | M | Enum | 定位类型（见枚举 9.5） |
| pdfPageIndex | O | Integer | PDF 页码（从 1 开始） |
| documentPageLabel | O | String | 标准印刷页码（如 "14"） |
| bbox | O | Array[Float] | 边界框 [x, y, width, height]（归一化坐标 0-1） |
| textSpanRef | O | String | 关联的 TextSpan id |
| textQuote | O | String | 原始文字片段（用于验证） |
| sourceBlockId | O | String | 解析器输出的 block id |
| markdownStartLine | O | Integer | Markdown 起始行（从 1 开始；`anchorType=markdown` 时必填） |
| markdownStartColumn | O | Integer | Markdown 起始列（从 1 开始） |
| markdownEndLine | O | Integer | Markdown 结束行（含；`anchorType=markdown` 时必填） |
| markdownEndColumn | O | Integer | Markdown 结束列（含） |
| markdownNodePath | O | String | Markdown AST 节点路径或 CSM block ID |
| assetRef | O | String | 图片/表格等资源的资产引用 |
| extractionRegion | O | String | 提取区域描述 |

**id 规则**：`{documentId}/anchor/{序号}`。

**约束**：
- `sourceFileId` 必须引用有效的 SourceFile。
- `anchorType` 必须为枚举值。
- `bbox` 数组必须包含 4 个元素。


### 6.13 EntityMention

EntityMention 记录从标准文本中识别出的实体名称或术语的原始出现。**仅记录“文档中出现了什么”，不绑定 Ontology Class**。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 实体提及唯一标识符 |
| surfaceForm | M | String | 原始表面形式，如 "电动机" |
| normalizedForm | O | String | 规范化形式 |
| mentionType | M | Enum | 提及类型（见枚举 9.6） |
| parentNodeId | M | String | 所属 StructuralNode 的 id |
| sourceElementId | O | String | 所属 ContentElement/TableCell/ListItem 的 id（精确定位） |
| textSpan | M | TextSpan | 文本区间定位 |
| context | O | String | 上下文片段 |
| confidence | O | Float | 识别置信度 0-1 |
| candidateMappings | O | Array[CandidateMapping] | 候选 Ontology 映射（转换层信息） |

**CandidateMapping**：

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| ontology | O | String | 目标 Ontology 名称 |
| conceptId | O | String | 目标概念 ID |
| confidence | O | Float | 映射置信度 0-1 |
| status | O | Enum | candidate \| confirmed \| rejected |

**id 规则**：`{documentId}/mention/{序号}`，如 `ssir:GBT-22373-2021/mention/m-001`。


### 6.14 RelationMention

RelationMention 记录从标准文本中识别出的实体间语义关系的原始出现。**不表达文档级引用关系（引用由 Reference 处理）**。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 关系提及唯一标识符 |
| relationType | M | Enum | 关系类型（见枚举 9.7） |
| sourceId | M | String | 关系源对象 id（SSIRObjectRef 格式） |
| targetId | O | String | 关系目标对象 id（SSIRObjectRef 格式，可空） |
| targetMentionText | O | String | 目标对象文本（当 targetId 为空时使用） |
| parentNodeId | M | String | 所属 StructuralNode 的 id |
| sourceElementId | O | String | 所属 ContentElement/TableCell/ListItem 的 id |
| textSpan | M | TextSpan | 文本区间定位 |
| evidence | O | String | 关系证据文本 |
| resolutionStatus | O | Enum | resolved \| unresolved \| partiallyResolved |
| confidence | O | Float | 识别置信度 0-1 |

**SSIRObjectRef 格式**：`{objectType}:{id}`，如 `entity:mention-001`、`table:table-001/cell/0-1`。

**id 规则**：`{documentId}/relation/{序号}`。

**约束**：
- `targetId` 和 `targetMentionText` 至少存在一个。
- `relationType` 不得包含 `references`（引用关系由 Reference 对象处理）。


### 6.15 Reference

Reference 记录标准文档中的引用关系。**Reference 是一等对象，独立于 RelationMention**。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 引用唯一标识符 |
| sourceNodeId | M | String | 引用来源节点 id |
| referenceType | M | Enum | 引用类型（见枚举 9.8） |
| targetType | M | Enum | 目标类型（见枚举 9.9） |
| rawTarget | M | String | 原始引用文本，如 "GB/T 42093.1-2022" |
| resolvedDocumentId | O | String | 解析后的文档标识符 |
| resolvedVersion | O | String | 解析后的版本 |
| resolvedClause | O | String | 引用的具体条款，如 "6.3" |
| citedText | O | String | 被引用的原文片段 |
| textSpan | M | TextSpan | 文本区间定位 |
| resolutionStatus | O | Enum | resolved \| unresolved \| partiallyResolved |
| confidence | O | Float | 识别置信度 0-1 |

**id 规则**：`{documentId}/reference/{序号}`。

**约束**：
- `rawTarget` 保留原文，不可改写。
- `resolvedDocumentId`、`resolvedVersion`、`resolvedClause` 为解析结果，允许为空。


### 6.16 DocumentRelationship

DocumentRelationship 记录标准文档之间的事实关系。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 关系唯一标识符 |
| sourceDocumentId | M | String | 源文档 SSIR id |
| relationType | M | Enum | 关系类型（见枚举 9.10） |
| targetDocumentId | M | String | 目标文档标识符 |
| targetVersion | O | String | 目标文档版本 |
| validity | O | String | 有效性说明 |
| sourceAnchor | O | SourceAnchor | 声明此关系的原文位置 |
| evidence | O | String | 证据描述 |
| confidence | O | Float | 识别置信度 0-1 |

**id 规则**：`{documentId}/docrel/{序号}`。

**约束**：
- `relationType` 与 `Reference` 中的引用类型有明确区分：DocumentRelationship 表达文档级事实关系（代替、修改、补充等），Reference 表达条款级引用。


### 6.17 ProcessingRun

ProcessingRun 记录一次从源文件提取/处理生成 SSIR 的过程。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 处理运行唯一标识符 |
| sourceFileId | M | String | 关联的 SourceFile id |
| runType | M | Enum | extraction \| classification \| entityRecognition \| relationExtraction \| referenceResolution \| humanReview \| other |
| tool | M | String | 工具名称，如 "MinerU" |
| toolVersion | M | String | 工具版本号 |
| ocrUsed | O | Boolean | 是否使用 OCR |
| ocrEngine | O | String | OCR 引擎名称 |
| model | O | String | 使用的模型名称 |
| modelVersion | O | String | 模型版本 |
| timestamp | M | DateTime | 处理时间戳 |
| configuration | O | Object | 处理配置参数 |
| durationSeconds | O | Float | 处理耗时（秒） |
| outputSummary | O | Object | 输出统计（节点数、表格数、提及数等） |

**id 规则**：`ssir:processing/run/{YYYYMMDD}-{序号}`。


### 6.18 QualityAssessment

QualityAssessment 记录 SSIR 的质量评估结果。

| 属性 | 约束 | 类型 | 说明 |
|------|------|------|------|
| id | M | String | 评估唯一标识符 |
| documentId | M | String | 关联的 SSIRDocument id |
| runId | O | String | 关联的 ProcessingRun id |
| overallStatus | M | Enum | complete \| partial \| extractionFailed \| requiresReview \| approved \| rejected |
| structureConfidence | O | Float | 结构识别置信度 0-1 |
| tableConfidence | O | Float | 表格识别置信度 0-1 |
| figureConfidence | O | Float | 图识别置信度 0-1 |
| formulaConfidence | O | Float | 公式识别置信度 0-1 |
| ocrConfidence | O | Float | OCR 置信度 0-1 |
| entityConfidence | O | Float | 实体识别置信度 0-1 |
| relationConfidence | O | Float | 关系识别置信度 0-1 |
| referenceConfidence | O | Float | 引用解析置信度 0-1 |
| missingPages | O | Array[Integer] | 缺失页码列表 |
| unresolvedTables | O | Array[String] | 未解析表格列表 |
| unresolvedFigures | O | Array[String] | 未解析图列表 |
| unresolvedFormulas | O | Array[String] | 未解析公式列表 |
| unresolvedReferences | O | Array[String] | 未解析引用列表 |
| humanReviewStatus | O | Enum | unreviewed \| machineReviewed \| humanReviewed \| approved \| rejected |
| comments | O | String | 评估备注 |
| assessedAt | M | DateTime | 评估时间 |

**id 规则**：`{documentId}/qa/{序号}`。


## 7. Round-trip Requirements

SSIR 必须支持从源文档到 SSIR、再从 SSIR 到传统文档表示的完整往返转换。

### 7.1 Round-trip Definition

SSIR Round-trip 由以下转换链构成：

```
Std₀ → SSIR₁ → Std₁ → SSIR₂
```

其中：
- `Std₀` = 原始源文档（PDF/扫描 PDF/DOCX 等）
- `SSIR₁` = 从 Std₀ 提取的 SSIR（信息基准状态）
- `Std₁` = 从 SSIR₁ 渲染生成的规范化传统文档
- `SSIR₂` = 从 Std₁ 再次提取的 SSIR（恢复状态）

**Round-trip 正确性的主要判定依据是 `SSIR₁ ≈ SSIR₂`（SSIR 语义等价性），而非 `Std₀ ≈ Std₁`（文档外观等价性）。**

**理由**：`Std₀` 和 `Std₁` 不要求形式完全相同。`Std₀` 可能存在排版不规范、标题层级格式不规范、标点/编号/空格等可规范化问题。`Std₁` 可能经过 Rendering Profile（如 GB/T 1.1-2020）的规范化处理而产生形式差异。因此 `Std₀ ≠ Std₁` 不必然表示 SSIR 转换失败。

### 7.2 Source Fidelity（源保真）

**阶段**：`Std₀ → SSIR₁`

**要求**：
- SSIR₁ 必须完整保存 Std₀ 中应被保存的原始信息，包括：
  - 文档身份与元数据
  - 逻辑层次结构（章、条、款、项、附录）
  - 章节编号与标题
  - 段落文本
  - 列表及其层级
  - 表格、行、单元格、合并单元格、表头、表注
  - 图、图题
  - 公式及其编号
  - 注、示例、警示
  - 脚注及其与正文的关联
  - 规范性/资料性标识
  - 内部引用与外部引用
  - 内容元素的顺序
  - 原始文本内容
  - 源文件定位信息（SourceAnchor）
- 任何无法识别的内容必须进入 `UnknownContent`，不得静默丢弃
- 此阶段**禁止**对原文进行语义改写、摘要或润色

### 7.3 Normative Rendering（规范化渲染）

**阶段**：`SSIR₁ → Std₁`

**要求**：
- Rendering Engine 可以依据指定的 Rendering Profile（如 GB/T 1.1-2020）对文档进行规范化、格式化和必要的表达形式调整
- 允许的规范化包括：
  - 编号格式规范化
  - 标题层级表达规范化
  - 空格、标点规范
  - 版式、字体、字号
  - 表格格式
  - 页眉页脚
  - 附录格式
- 规范化过程**不得引入实质性语义变化**

**语义保护边界**：
- 以下内容**绝对禁止**因规范化而改变：
  - 规范性动词（"应"、"应当"、"必须" → 不得改为 "宜"、"可"、"可以"）
  - 禁止性表述（"不得"、"不应"、"禁止"）
  - 数值、百分比、范围、公差
  - 单位符号
  - 比较运算符（≥、≤、>、<、=、≠）
  - 条款编号
  - 表格单元格内容
  - 公式原始表示
  - 引用原始文本（rawTarget）
  - 标准的适用范围声明
- 此类变更属于**语义变换（Semantic Mutation）**，不应由 Rendering Engine 擅自执行

### 7.4 Re-extraction（重新提取）

**阶段**：`Std₁ → SSIR₂`

**要求**：
- 从 Std₁ 提取 SSIR₂ 应使用与 SSIR₁ 相同的提取流程和 Schema
- SSIR₂ 的 `sourceFiles` 和 `processingRuns` 会与 SSIR₁ 不同（因为源文件变为 Std₁）
- SSIR₂ 的 `SourceAnchor`（页码、bbox、blockId）必然与 SSIR₁ 不同

### 7.5 SSIR Equivalence（SSIR 等价性）

**阶段**：`SSIR₁ ≈ SSIR₂` 比较

**要求**：
- Round-trip 正确性的核心判定依据是 SSIR₁ 与 SSIR₂ 的等价性
- 等价性比较应采用 **Canonical Comparison** 方法：
  - 对两个 SSIR 实例进行标准化的规范化处理（去除 ID、时间戳、processingRun 差异）
  - 比较 Identity、Structure、Content、Tables、Figures、Formulas、Lists、References 等维度
  - 区分 **STRICT**（必须一致）、**NORMALIZED**（允许规范化差异）、**IGNORED**（不比较）三类字段

### 7.6 Equivalence Classification

| SSIR 部分 | 比较策略 | 说明 |
|-----------|----------|------|
| 文档逻辑结构 | **STRICT** | 节点数量、类型、层级、父子关系必须一致 |
| 条款编号 | **STRICT** | 除非 Rendering Profile 明确定义了规范化映射 |
| 标题语义 | **STRICT** | 标题内容必须等价（允许空格规范化） |
| 正文内容 | **NORMALIZED** | 空格、换行、标点可规范化；语义不得改变 |
| 表格结构 | **STRICT** | 行列数、合并单元格结构必须一致 |
| 表格内容 | **STRICT** | 单元格文本必须等价（允许空格规范化） |
| 图编号/图题 | **STRICT** | 必须一致（允许空格规范化） |
| 图资产 | **NORMALIZED** | 图本身应存在，assetRef 可能变化 |
| 公式 | **STRICT** | rawText 必须一致 |
| 列表层级 | **STRICT** | 层级结构必须一致 |
| 列表标记 | **NORMALIZED** | 标记样式（如 a) vs a.）可在同类型内变化 |
| 引用关系 | **STRICT** | rawTarget 必须一致 |
| 规范性/资料性属性 | **STRICT** | 必须一致 |
| Entity/Relation | **NORMALIZED** | 允许重新计算，但不得产生冲突 |
| SourceAnchor | **IGNORED** | 页码、bbox、blockId 必然变化 |
| ProcessingRun | **IGNORED** | ID、timestamp 必然变化 |
| sourceFiles | **IGNORED** | 源文件不同，ID/hash 必然变化 |
| SSIR ID | **IGNORED** | 重新提取生成新 ID |
| createdAt/updatedAt | **IGNORED** | 时间戳必然变化 |
| qualityAssessments | **IGNORED** | 重新评估结果不同 |

### 7.7 Rendering Conformance（渲染合规性）

**独立维度**：与 Round-trip Equivalence 并行

**要求**：
- `Std₁` 应符合指定的 Rendering Profile（如 GB/T 1.1-2020）
- 这是对输出文档质量的独立评估
- 与 Round-trip Equivalence 是不同的验证维度

### 7.8 四个验证概念的总结

| 概念 | 链路 | 回答的问题 |
|------|------|-----------|
| **Source Fidelity** | `Std₀ → SSIR₁` | 有没有正确提取？ |
| **Rendering Conformance** | `SSIR₁ → Std₁` | 输出是否符合规范？ |
| **Round-trip Completeness** | `SSIR₁ → Std₁` | 有没有保存足够的信息重建？ |
| **Round-trip Equivalence** | `SSIR₁ → Std₁ → SSIR₂` | 重建后信息是否仍然等价？ |


## 8. Object Relationship Summary

| 源对象 | 关系 | 目标对象 | Cardinality |
|--------|------|----------|-------------|
| SSIRDocument | has | DocumentMetadata | 1 |
| SSIRDocument | has | SourceFile | 1..N |
| SSIRDocument | has | StructuralNode (root) | 1 |
| SSIRDocument | has | ProcessingRun | 1..N |
| SSIRDocument | has | QualityAssessment | 0..N |
| SSIRDocument | has | Reference | 0..N |
| SSIRDocument | has | DocumentRelationship | 0..N |
| SSIRDocument | has | EntityMention | 0..N |
| SSIRDocument | has | RelationMention | 0..N |
| SSIRDocument | has | CanonicalText | 0..1 |
| StructuralNode | contains | StructuralNode | 0..N |
| StructuralNode | contains | ContentElement | 0..N |
| ContentElement | references | Table / Figure / Formula / UnknownContent | 0..1 |
| StructuralNode | has | EntityMention | 0..N |
| StructuralNode | has | RelationMention | 0..N |
| StructuralNode | has | Reference | 0..N |
| EntityMention | has | TextSpan | 1 |
| RelationMention | has | TextSpan | 1 |
| Reference | has | TextSpan | 1 |
| TextSpan | references | CanonicalText | 1 |
| SourceAnchor | references | SourceFile | 1 |
| SourceAnchor | references | TextSpan | 0..1 |


## 9. Enumerations

### 9.1 StructuralNodeType（逻辑结构类型）

| 值 | 说明 |
|----|------|
| document | 文档根节点 |
| documentBlock | 文档分块（cover/toc/foreword/introduction/mainBody/annex/reference/index） |
| section | 章 |
| clause | 条 |
| subClause | 款 |
| item | 项 |
| subItem | 子项 |
| annex | 附录 |
| annexSection | 附录内的章/条 |

### 9.2 PresentationType（内容表达形式）

| 值 | 说明 |
|----|------|
| paragraph | 普通段落 |
| heading | 标题 |
| list | 列表 |
| table | 表格 |
| figure | 图 |
| formula | 公式 |
| note | 注 |
| example | 示例 |
| warning | 警示 |
| quote | 引用文本 |
| footnote | 脚注 |
| other | 未知类型（保底机制） |

### 9.3 SemanticType（内容要素语义类型）

依据 GB/T 42093.1-2022 内容要素元模型。

| 值 | 说明 | 所属类别 |
|----|------|----------|
| scope | 范围 | 说明类 |
| normativeReference | 规范性引用文件 | 说明类 |
| termDefinition | 术语定义 | 说明类 |
| symbolDefinition | 符号定义 | 说明类 |
| classification | 分类 | 说明类 |
| requirement | 要求 | 规范性技术要素 |
| testMethod | 试验方法 | 规范性技术要素 |
| inspectionRule | 检验规则 | 规范性技术要素 |
| markingRequirement | 标志要求 | 规范性技术要素 |
| packagingTransportStorage | 包装/运输/储存 | 规范性技术要素 |
| example | 示例 | 补充附属要素 |
| warning | 警示 | 补充附属要素 |
| note | 注释 | 补充附属要素 |
| appendixExplanation | 附录说明 | 补充附属要素 |
| bibliographicReference | 参考文献 | 补充附属要素 |

### 9.4 NormativeStatus（规范性状态）

| 值 | 说明 |
|----|------|
| normative | 规范性内容 |
| informative | 资料性内容 |
| unknown | 无法判断 |
| notApplicable | 不适用 |

### 9.5 AnchorType（锚点定位类型）

| 值 | 说明 |
|----|------|
| page | 仅页面级定位 |
| bbox | 边界框定位 |
| textSpan | 文本区间定位 |
| block | 解析器 block 定位 |
| tableCell | 表格单元格定位 |
| figureRegion | 图片区域定位 |
| markdown | CSM Markdown 行/列和 AST 节点定位；不包含 PDF 坐标 |

### 9.6 EntityMentionType（实体提及类型）

| 值 | 说明 |
|----|------|
| documentConcept | 文档概念 |
| product | 产品 |
| material | 材料 |
| organization | 组织/机构 |
| standard | 标准 |
| regulation | 法规 |
| process | 过程/工艺 |
| equipment | 设备 |
| parameter | 参数/指标 |
| unit | 单位 |
| value | 数值 |
| time | 时间 |
| location | 地点 |
| identifier | 标识符 |
| other | 其他 |

### 9.7 RelationMentionType（关系提及类型）

**不含引用关系（由 Reference 处理）**。

| 值 | 说明 |
|----|------|
| defines | 定义 |
| hasProperty | 具有属性 |
| appliesTo | 适用于 |
| measures | 测量 |
| requires | 要求 |
| constrains | 约束 |
| equivalentTo | 等效于（文本层面的等效） |

### 9.8 ReferenceType（引用类型）

| 值 | 说明 |
|----|------|
| normative | 规范性引用 |
| informative | 资料性引用 |
| mandatory | 强制性引用 |
| conditional | 条件性引用 |

### 9.9 ReferenceTargetType（引用目标类型）

| 值 | 说明 |
|----|------|
| internalClause | 内部条款 |
| internalAnnex | 内部附录 |
| internalTable | 内部表格 |
| internalFigure | 内部图 |
| externalStandard | 外部标准 |
| externalRegulation | 外部法规 |
| externalDocument | 外部文献 |
| externalTechnicalSpecification | 外部技术规范 |

### 9.10 DocumentRelationshipType（文档关系类型）

| 值 | 说明 |
|----|------|
| replaces | 代替 |
| replacedBy | 被代替 |
| amends | 修改 |
| amendedBy | 被修改 |
| supplements | 补充 |
| supplementedBy | 被补充 |
| equivalentTo | 等效 |
| adopts | 采纳 |
| adoptedBy | 被采纳 |
| references | 引用（文档级） |
| referencedBy | 被引用（文档级） |

### 9.11 MarkerType（列表标记类型）

| 值 | 说明 |
|----|------|
| lowerAlpha | 小写字母，如 a) b) c) |
| upperAlpha | 大写字母，如 A) B) C) |
| numeric | 数字，如 1) 2) 3) |
| roman | 罗马数字，如 i) ii) iii) |
| bullet | 项目符号，如 • |
| dash | 破折号，如 — |
| other | 其他 |


## 10. Preservation Levels

SSIR 定义以下保存等级，用于标识 SSIR 实例的完整程度：

| 等级 | 名称 | 包含内容 |
|------|------|----------|
| **Level 0** | Metadata Only | 仅文档元数据 |
| **Level 1** | Structural | 章/条/款/项逻辑结构 + 编号 + 标题 |
| **Level 2** | Content Complete | Level 1 + 正文、表格、图、公式、列表、注、脚注 |
| **Level 3** | Source Traceable | Level 2 + 源文件定位；CSM 输入使用 Markdown 行/列和 AST 节点，PDF 输入可增加页码、bbox、TextSpan 和源区块 |
| **Level 4** | Semantic Enriched | Level 3 + EntityMention、RelationMention、Reference、DocumentRelationship |

**说明**：
- **Level 2 + Level 3** 是满足 Round-trip Completeness 的最低要求
- Level 4 不是 Round-trip 的必要条件，而是语义增强层
- 语义识别失败不应导致等级下降，Level 2/3 的内容必须在任何情况下完整保存

**Preservation Level 与 Round-trip 的关系**：
- `Preservation Level` 回答：SSIR 保存了多少信息？（数据质量等级）
- `Round-trip Completeness` 回答：是否保存了重建所需的信息？（必要条件）
- `Round-trip Equivalence` 回答：重建再提取后是否保持等价？（验证结果）
- 三者是正交概念，不应混淆


## 11. SSIR → leleby Semantic Layer Mapping Contract

SSIR 与 leleby Semantic Layer 之间的转换遵循以下映射关系。

| SSIR 对象 | 映射目标 | 说明 |
|-----------|----------|------|
| StructuralNode | Semantic SourceReference | 保留结构上下文 |
| ContentElement (semanticTypes=requirement) | RequirementAssertionCandidate | 转换为语义化要求候选 |
| ContentElement (semanticTypes=termDefinition) | TermDefinitionCandidate | 转换为术语定义候选 |
| EntityMention | OntologyConceptCandidate | 解析为 Ontology Class 候选 |
| RelationMention | SemanticRelationCandidate | 解析为语义关系候选 |
| Reference | StandardReference | 解析为标准引用 |
| SourceAnchor + TextSpan | Evidence / Provenance | 作为语义事实的证据来源 |

**关键原则**：
- **语义依赖是单向的**：SSIR 不依赖任何 Ontology 定义，其有效性独立于 Semantic Layer
- **文档转换是双向的**：SSIR 本身支持源文档表示与 SSIR 之间的双向转换
- Semantic Layer 中产生的任何语义事实，都必须保留其 `SourceAnchor` 和 `TextSpan` 引用
- 映射结果中的 `confidence` 和 `resolutionStatus` 必须保留


## 12. Out of Scope

以下内容不属于 SSIR 核心数据模型：

| 类别 | 具体内容 |
|------|----------|
| 领域知识 | ProductClass、RequirementSubject、RequirementProperty、RequirementConstraint |
| 验证与合规 | VerificationMethod、TestResult、ComplianceStatus、ComplianceDecision |
| 知识表示 | OntologyClass、KnowledgeGraphEntity、InferenceResult |
| 公式语义 | Formula AST（v0.4 暂不建模） |
| 图语义 | Figure semantic description（v0.4 暂不建模） |
| 版式细节 | 精确字体、分页、页眉/页脚位置（作为纯排版信息处理） |
| 复杂脚注 | 脚注的完整双向关联（v0.4 暂仅记录为 ContentElement） |

上述内容属于 leleby Semantic Knowledge Layer 的范畴，通过 Semantic Mapping 从 SSIR 转换得到。


## 13. Relationship to National Standards

| 国家标准 | 对应 SSIR 模块 |
|----------|----------------|
| GB/T 22373-2021 标准文献元数据 | DocumentMetadata.StandardMetadata（§6.2） |
| GB/T 42093.1-2022 层次元模型 | StructuralNode（§6.4） |
| GB/T 42093.1-2022 要素表述形式元模型 | ContentElement + Table + Figure + Formula（§6.5-6.8） |
| GB/T 42093.1-2022 内容要素元模型 | SemanticType（枚举 9.3） |
| GB/T 47462-2026 结构信息单元 | StructuralNode + ContentElement |
| GB/T 47462-2026 标准管理壳 | DocumentMetadata + ProcessingRun |
| GB/T 1.1-2020 | Normative Rendering Profile（§7.3） |


## 14. Version History

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 0.1 | 2026-08-15 | 初始版本，定义 10 个核心对象 |
| 0.2 | 2026-08-15 | 结构/内容分离；新增 SourceFile/TextSpan/ProcessingRun/QualityAssessment/DocumentRelationship；Reference/RelationMention 职责分离；元数据通用化；表格模型增强；明确"树+图+溯源"架构 |
| 0.3 | 2026-08-15 | 新增 Round-trip Completeness 原则；新增 CanonicalText/Figure/Formula/UnknownContent；增强 TableCell（richText）和 ListItem（marker）；新增 Preservation Levels；修正 Mapping Contract 表述；EntityMention 增加 sourceElementId；RelationMention 支持 SSIRObjectRef；SourceAnchor 增加 assetRef |
| 0.4 | 2026-08-15 | 重新定义 Round-trip 闭环为 `Std₀ → SSIR₁ → Std₁ → SSIR₂`；新增 Round-trip Equivalence 概念；新增 §7 Round-trip Requirements（完全重写）；新增 Equivalence Classification Table；明确 Rendering Normalization 边界；区分 Preservation Level、Completeness、Equivalence 三个正交概念；新增 GB/T 1.1-2020 引用 |
| 0.4-M1 | 2026-08-17 | 增加 CSM Markdown SourceFile、Markdown SourceAnchor 及 M1 的 Markdown-only 溯源约束 |
