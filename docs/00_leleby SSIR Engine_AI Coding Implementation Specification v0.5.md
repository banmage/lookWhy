# leleby SSIR Engine — AI Coding Implementation Specification v0.6

> **文档状态**：正式发布 | **版本**：0.6 | **日期**：2026-08-17
>
> **前置文档**：
> 1. leleby SSIR Data Model v0.4
> 2. leleby SSIR JSON Schema Specification v0.3
> 3. leleby SSIR Processing Pipeline & Architecture Specification v0.4
> 4. leleby SSIR Round-trip & Conformance Test Specification v0.3
> 5. leleby SSIR Engine — Golden Dataset Specification v0.1
> 6. leleby SSIR Engine — API Contract & Interface Specification v0.1
>
> **目标读者**：AI Coding Agent / 开发团队
>
> **核心指令**：本规范是 Phase 1 开发的唯一编码依据。所有代码实现必须严格遵循本规范的定义，不得偏离。

> **当前迭代边界（M1：CSM Markdown Round-trip）**：本项目接收用户 Markdown，先进行宽容校验和无语义损失的基础纠错并冻结为 `Canonical`，再执行 `Canonical → SSIR → Render.md → Verify` 回环验证。原始输入不是回环比较基准，修复项必须记录在转换报告。PDF/DOCX 接入、MinerU、OCR 和“PDF → CSM”属于后续 M2，不得成为 M1 的运行时依赖或验收条件。
>
> - M1 回环输入：已纠错的 `corpus/golden/csm/*.canonical.md`（Canonical）；用户 Markdown 必须先经过 CSM 校验/纠错阶段。`corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md` 定义该阶段的目标格式。
> - M1 主输出：符合 JSON Schema v0.3 的 `.ssir.json`；Turtle（`.ttl`）仅作为从已验证 SSIR JSON 派生的可选导出，不得替代 JSON 作为权威交换格式。
> - M1 溯源：`source.mode=user-markdown`、`mimeType=text/markdown`、SHA-256，以及 Markdown 行/列和 AST block 定位；不得伪造 PDF 页码或 bbox。
> - M1 回环：确定性 CSM Renderer 输出 `Render.md`，使用同一 CSMParser 重提取 `Verify`，并比较身份、结构、内容、语义视图及关键损失；来源锚点、运行记录和质量评估不参与等价比较。
> - M1 不实现：PDF 上传/解析、MinerU/OCR、DOCX 解析、规范性 DOCX/PDF 渲染、PDF/DOCX 视觉保真、L4 语义推理。
> - 本框中的约束优先于本文件后文仍保留的完整 Phase 1 任务清单；后文任务作为 M2+ 路线图保留。

M1 的可执行模块契约和验收标准见 `docs/08_leleby CSM-to-SSIR Implementation Specification v0.1.md`。
>
> **v0.5 主要修订**（基于 API Contract & Interface Specification v0.1 的同步）：
> - **新增 §5 内部接口契约**：定义所有核心模块的 Python 抽象类/协议接口
> - **增强 §6 Task 9（Storage & API）**：增加完整的 API 实现指令，包括路由、请求/响应模型、依赖注入、错误处理
> - **新增 §6 Task 10（API Integration Testing）**：增加 API 集成测试任务
> - **更新目录结构**：增加 `apps/api/models/` 下的请求/响应模型文件
> - **更新 §1.4 管线图**：增加 API 层在整体架构中的位置
> - **更新 §8 Acceptance Criteria**：增加 API Conformance Gate
> - **更新前置文档列表**：增加 API Contract & Interface Specification


## 1. Implementation Overview

### 1.1 项目代号
`leleby-ssir-engine`

### 1.2 核心目标（Phase 1）
开发一个 **SSIR Round-trip Digitalization Engine**，能够：
- 将传统规范文档（PDF/扫描 PDF/DOCX）转换为符合 SSIR v0.4 的结构化 JSON（`源文档 → SSIR`）
- 从 SSIR 按规范化规则生成符合 GB/T 1.1-2020 起草规则的标准文档（`SSIR → 渲染文档`，即 **Normative Rendering**）
- 从渲染文档重新提取生成 Verify（`渲染文档 → Verify`）
- 验证 SSIR 与 Verify 的语义等价性（`SSIR ≈ Verify`，即 **Round-trip Equivalence**），执行四层比较 + 12 项 Critical Information Loss Check
- 通过 REST API 提供所有功能的访问接口
- 通过 Round-trip 测试验证信息完整性

### 1.3 必须实现的三层中间表示

| 层 | 名称 | 用途 |
|----|------|------|
| L1 | **Extraction IR** | 解析器（MinerU/DOCX）输出的规范化中间格式，与具体解析器解耦 |
| L2 | **SSIR** | 标准的结构化数字表示，符合 v0.4 数据模型 |
| L3 | **Rendering IR** | SSIR 转换为排版指令的中间格式，与具体输出格式解耦 |

### 1.4 必须实现的管线（含 API 层）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API Layer                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  POST /documents → POST /{id}/process → GET /{id}/ssir              │  │
│  │  POST /{id}/render → POST /{id}/roundtrip → GET /{id}/quality       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                      │
│                                      ▼                                      │
│                              Celery Tasks                                   │
│                                      │                                      │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Core Pipeline (L0 → L3)                            │
│                                                                             │
│  源文档                                                                      │ 
│    │                                                                       │
│    ▼                                                                       │
│  Ingestion → Extraction → Extraction IR → CanonicalText → Structure       │
│  → Content → Provenance → Validation → SSIR                              │ 
│                                                                             │
│  SSIR                                                                     │ 
│    │                                                                       │
│    ▼                                                                       │
│  Normative Rendering (GB/T 1.1-2020 Profile)                              │
│  (ALLOWED_NORMALIZATIONS / FORBIDDEN_CHANGES enforced)                    │
│    │                                                                       │
│    ▼                                                                       │
│  渲染文档                                                                      │
│    │                                                                       │
│    ▼                                                                       │
│  Re-Ingestion → Re-Extraction → Verify                                     │
│    │                                                                       │
│    ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    Round-trip Verification                          │  │
│  │  Four-layer Comparison (SSIR ≈ Verify)                             │  │
│  │  Critical Loss Check (12项)                                        │  │
│  │  Rendering Fidelity Test (独立)                                    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│    │                                                                       │
│    ▼                                                                       │
│  RoundTripReport                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.5 SSIR Semantic Round-trip Property（核心公理）

对于输入标准文档 `源文档`，第一次转换得到 `SSIR`，再依据适用的标准起草规则生成规范化标准文档 `渲染文档`（Normative Rendering），然后重新转换得到 `Verify`。

Engine 应保证：

> **SSIR ≈ Verify**（SSIR Semantic Equivalence — 四层比较）

其中等价关系允许预先定义的表示规范化、排版变化、文档标识变化和物理版面变化，但不得允许未经授权的结构、规范性内容、数值、关系或引用语义变化（FORBIDDEN_CHANGES）。

因此，Round-trip 的主要验证对象**不是** `源文档` 与 `渲染文档` 的字面一致性，而是 `SSIR` 与 `Verify` 的信息和语义等价性。

**四个验证概念的关系**（来自 Data Model v0.4 §7.8）：

| 概念 | 链路 | 回答的问题 |
|------|------|-----------|
| **Source Fidelity** | `源文档 → SSIR` | 有没有正确提取？ |
| **Rendering Conformance** | `SSIR → 渲染文档` | 输出是否符合规范且不违反 FORBIDDEN_CHANGES？ |
| **Round-trip Completeness** | `SSIR → 渲染文档` | 有没有保存足够的信息重建？ |
| **Round-trip Equivalence** | `SSIR → 渲染文档 → Verify` | 重建后信息是否仍然等价？ |

**Phase 1 必须同时验证以上四个概念。**


## 2. Technology Stack (Fixed)

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 语言 | Python | 3.11+ | 主开发语言 |
| API | FastAPI | 0.100+ | REST API |
| 异步任务 | Celery | 5.3+ | 长时间处理任务 |
| Broker | Redis | 7.0+ | Celery 消息代理 |
| 数据库 | PostgreSQL | 15+ | 元数据存储 |
| ORM | SQLAlchemy | 2.0+ | 数据库访问 |
| 对象存储 | MinIO | RELEASE.2024 | 文件/资产存储 |
| Schema | Pydantic | **2.5+** | 数据验证 + 模型定义（**使用 v2 API**） |
| PDF 解析 | MinerU | 最新稳定版 | PDF 结构化提取 |
| PDF 基础 | PyMuPDF | 1.23+ | PDF 元数据/页面操作 |
| DOCX | python-docx | 1.1+ | DOCX 读写 |
| 测试 | pytest | 7.4+ | 测试框架 |
| 容器 | Docker / Compose | 24.0+ / 2.23+ | 环境编排 |


## 3. Directory & File Structure (Mandatory)

AI Coding Agent **必须**生成以下完整的目录结构（含文件用途注释）：

```
leleby-ssir-engine/
│
├── apps/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 应用入口
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── documents.py        # POST /documents, GET /documents, DELETE /documents/{id}
│   │   │   ├── processing.py       # POST /documents/{id}/process, GET /documents/{id}/status
│   │   │   ├── rendering.py        # POST /documents/{id}/render, GET /documents/{id}/render/status
│   │   │   ├── roundtrip.py        # POST /documents/{id}/roundtrip, GET /documents/{id}/roundtrip/result
│   │   │   ├── quality.py          # GET /documents/{id}/quality
│   │   │   └── health.py           # GET /health, GET /ready
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── requests.py         # API 请求模型 (Pydantic)
│   │   │   └── responses.py        # API 响应模型 (Pydantic)
│   │   └── dependencies/
│   │       ├── __init__.py
│   │       ├── auth.py             # 认证依赖（Phase 1 简化）
│   │       └── storage.py          # 存储依赖
│   │
│   └── worker/
│       ├── __init__.py
│       ├── main.py                 # Celery worker 入口
│       ├── celery_config.py        # Celery 配置
│       └── tasks/
│           ├── __init__.py
│           ├── extraction.py       # 提取任务
│           ├── rendering.py        # 规范性渲染任务
│           └── roundtrip.py        # 往返测试任务
│
├── packages/
│   ├── core/                       # 核心数据模型（Pydantic v2）
│   │   ├── __init__.py
│   │   ├── ssir.py                 # SSIR 所有 Pydantic 模型 (v0.4)
│   │   ├── extraction_ir.py        # Extraction IR 模型
│   │   ├── rendering_ir.py         # Rendering IR 模型
│   │   ├── enums.py                # 所有枚举定义（含新增枚举）
│   │   ├── equivalence.py          # SSIR Equivalence Model (四层)
│   │   ├── roundtrip.py            # RoundTripReport
│   │   ├── transformation.py       # ALLOWED_NORMALIZATIONS / FORBIDDEN_CHANGES
│   │   └── schema/                 # JSON Schema
│   │       └── ssir.schema.json    # JSON Schema v0.3
│   │
│   ├── ingestion/                  # 文档接入服务
│   │   ├── __init__.py
│   │   ├── detector.py             # DocumentDetector
│   │   ├── source_file.py          # SourceFileBuilder
│   │   └── profiles.py             # DocumentSourceProfile
│   │
│   ├── extraction/                 # 文档提取服务
│   │   ├── __init__.py
│   │   ├── adapter.py              # 解析器适配器基类
│   │   ├── mineru_adapter.py       # MinerU 适配器
│   │   ├── docx_adapter.py         # python-docx 适配器
│   │   ├── ocr_pipeline.py         # OCR 处理
│   │   ├── layout_analyzer.py      # 布局分析
│   │   └── reading_order.py        # 阅读顺序解析
│   │
│   ├── canonical_text/             # 权威文本构建
│   │   ├── __init__.py
│   │   ├── builder.py              # CanonicalTextBuilder
│   │   ├── normalizer.py           # 文本规范化
│   │   └── text_span.py            # TextSpan 生成
│   │
│   ├── ssir_builder/               # SSIR 构建器（L0-L3）
│   │   ├── __init__.py
│   │   ├── builder.py              # SSIRBuilder 主入口
│   │   ├── metadata.py             # MetadataExtractor
│   │   ├── structure.py            # StructureBuilder
│   │   ├── content.py              # ContentBuilder
│   │   ├── table.py                # TableBuilder
│   │   ├── figure.py               # FigureBuilder
│   │   ├── formula.py              # FormulaBuilder
│   │   ├── list.py                 # ListBuilder
│   │   ├── provenance.py           # ProvenanceBuilder
│   │   └── unknown.py              # UnknownContentHandler
│   │
│   ├── semantic_enrichment/        # L4 - 独立于 SSIR Builder
│   │   ├── __init__.py
│   │   ├── reference.py            # ReferenceExtractor
│   │   ├── entity.py               # EntityExtractor
│   │   └── relation.py             # RelationExtractor
│   │
│   ├── validator/                  # 验证服务
│   │   ├── __init__.py
│   │   ├── schema.py               # JSON Schema 验证 (v0.3)
│   │   ├── structural.py           # 结构验证
│   │   ├── content.py              # 内容验证
│   │   ├── provenance.py           # 溯源验证
│   │   └── quality.py              # QualityAssessment 生成 (含 renderingProfile)
│   │
│   ├── rendering/                  # 规范性渲染服务
│   │   ├── __init__.py
│   │   ├── renderer.py             # 主渲染器入口
│   │   ├── profile.py              # NormativeRenderingProfile 基类
│   │   ├── gb_t_1_1_profile.py     # GB/T 1.1-2020 Normative Rendering Profile
│   │   ├── docx_renderer.py        # DOCX 渲染器
│   │   └── pdf_converter.py        # DOCX → PDF 转换
│   │
│   ├── roundtrip/                  # 往返测试服务
│   │   ├── __init__.py
│   │   ├── verifier.py             # Round-trip 主验证器
│   │   ├── comparator.py           # 四层比较器
│   │   ├── critical_check.py       # Critical Information Loss Check (12项)
│   │   ├── report.py               # RoundTripReport 生成
│   │   └── fidelity.py             # Rendering Fidelity Test (独立)
│   │
│   └── storage/                    # 存储服务
│       ├── __init__.py
│       ├── repository.py           # 数据仓库接口
│       ├── postgres.py             # PostgreSQL 实现（含版本化）
│       └── object_storage.py       # MinIO 实现
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # pytest 配置/fixtures
│   ├── unit/                       # 单元测试
│   │   ├── test_canonical_text.py
│   │   ├── test_structure.py
│   │   ├── test_table.py
│   │   ├── test_critical_check.py
│   │   └── ...
│   ├── integration/                # 集成测试
│   │   ├── test_extraction_ir_to_ssir.py
│   │   ├── test_ssir_to_rendering.py
│   │   └── ...
│   ├── api/                        # API 测试
│   │   ├── test_documents.py
│   │   ├── test_processing.py
│   │   ├── test_rendering.py
│   │   └── test_roundtrip.py
│   ├── golden/                     # Golden Test
│   │   ├── test_golden.py
│   │   └── goldens/
│   └── roundtrip/                  # Round-trip Test
│       ├── test_roundtrip.py
│       └── fixtures/
│
├── fixtures/
│   ├── golden/                     # Golden Dataset
│   │   ├── dataset-A/
│   │   ├── dataset-B/
│   │   ├── dataset-C/
│   │   ├── dataset-D/
│   │   └── dataset-E/
│   ├── sample/                     # 开发用样例
│   └── generated/                  # 测试生成的文件
│
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   └── docker-compose.yml
│
├── scripts/
│   ├── init_db.py
│   ├── run_golden_tests.py
│   └── run_roundtrip.py
│
├── config.yaml                     # 主配置文件
├── pyproject.toml                  # 项目依赖
├── pytest.ini                      # pytest 配置
├── README.md
└── .env.example
```


## 4. Pydantic Models (Core Data Contracts)

### 4.1 SSIR 核心模型（必须精确实现 — Data Model v0.4）

所有模型必须定义在 `packages/core/ssir.py` 中，严格遵循 SSIR v0.4 数据模型。**必须使用 Pydantic v2 API**（`@field_validator`、`Field(min_length=...)`、`pattern=` 等）。

```python
# packages/core/ssir.py
from typing import Optional, List, Union, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ValidationInfo
from .enums import *


class SSIRDocument(BaseModel):
    """SSIR 文档根对象 — Data Model v0.4"""
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+$")
    ssirVersion: str = Field(default="0.4")
    documentType: DocumentType
    metadata: "DocumentMetadata"
    sourceFiles: List["SourceFile"] = Field(..., min_length=1)
    canonicalText: Optional["CanonicalText"] = None
    structuralRoot: "StructuralNode"
    tables: List["Table"] = Field(default_factory=list)
    figures: List["Figure"] = Field(default_factory=list)
    formulas: List["Formula"] = Field(default_factory=list)
    unknownContents: List["UnknownContent"] = Field(default_factory=list)
    references: List["Reference"] = Field(default_factory=list)
    documentRelationships: List["DocumentRelationship"] = Field(default_factory=list)
    entityMentions: List["EntityMention"] = Field(default_factory=list)
    relationMentions: List["RelationMention"] = Field(default_factory=list)
    processingRuns: List["ProcessingRun"] = Field(..., min_length=1)
    qualityAssessments: List["QualityAssessment"] = Field(default_factory=list)
    preservationLevel: Optional[PreservationLevel] = None
    createdAt: datetime
    updatedAt: Optional[datetime] = None

    @field_validator("structuralRoot")
    @classmethod
    def validate_root_type(cls, v: "StructuralNode") -> "StructuralNode":
        if v.nodeType != StructuralNodeType.DOCUMENT:
            raise ValueError("structuralRoot must be nodeType 'document'")
        return v


class DocumentMetadata(BaseModel):
    common: "CommonMetadata"
    standard: Optional["StandardMetadata"] = None

    @field_validator("standard")
    @classmethod
    def validate_standard_metadata(cls, v: Optional["StandardMetadata"], info: ValidationInfo) -> Optional["StandardMetadata"]:
        common = info.data.get("common")
        if common and common.documentType == DocumentType.STANDARD:
            if v is None:
                raise ValueError("standard metadata required when documentType=standard")
        return v


class CommonMetadata(BaseModel):
    documentIdentifier: str
    title: str
    titleEn: Optional[str] = None
    language: Optional[str] = None
    publicationDate: Optional[str] = None
    effectiveDate: Optional[str] = None
    issuer: Optional[str] = None
    status: Optional[str] = None
    version: Optional[str] = None


class StandardMetadata(BaseModel):
    standardNumber: str
    chineseTitle: Optional[str] = None
    englishTitle: Optional[str] = None
    originalTitle: Optional[str] = None
    publishingBody: Optional[str] = None
    publishingBodyCode: Optional[str] = None
    ccs: Optional[str] = None
    ics: Optional[str] = None
    drafters: List[str] = Field(default_factory=list)
    proposer: Optional[str] = None
    mirrorBody: Optional[str] = None
    adoption: Optional[str] = None


class FileHash(BaseModel):
    algorithm: str = Field(..., pattern=r"^(SHA-256|SHA-512|MD5|SHA-1)$")
    value: str


class SourceFile(BaseModel):
    id: str = Field(..., pattern=r"^src:[A-Fa-f0-9]{16,}$")
    fileName: str
    storageUri: Optional[str] = Field(None, pattern=r"^[a-zA-Z][a-zA-Z0-9+.-]+://.*$")
    fileHash: FileHash
    fileSize: Optional[int] = Field(None, ge=0)
    mimeType: str
    pageCount: Optional[int] = Field(None, ge=0)
    metadata: Optional[dict] = None


class CanonicalText(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/canonical$")
    text: str
    normalizationPolicy: Optional[NormalizationPolicy] = None
    sourceElementRefs: List[str] = Field(default_factory=list)
    version: Optional[str] = None


class StructuralNode(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/[A-Za-z0-9._-]+$")
    logicalId: str
    nodeType: StructuralNodeType
    level: Optional[int] = None
    number: Optional[str] = None
    title: Optional[str] = None
    children: List["StructuralNode"] = Field(default_factory=list)
    contentElements: List["ContentElement"] = Field(default_factory=list)
    sourceAnchors: List["SourceAnchor"] = Field(default_factory=list)
    sortOrder: int

    @field_validator("sourceAnchors")
    @classmethod
    def validate_source_anchors(cls, v: List["SourceAnchor"], info: ValidationInfo) -> List["SourceAnchor"]:
        node_type = info.data.get("nodeType")
        if node_type != StructuralNodeType.DOCUMENT and len(v) == 0:
            raise ValueError("sourceAnchors must have at least 1 element for non-document nodes")
        return v


class ContentElement(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/content/[A-Za-z0-9_-]+$")
    presentationType: PresentationType
    parentNodeId: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/[A-Za-z0-9._-]+$")
    semanticTypes: List[SemanticType] = Field(default_factory=list)
    normativeStatus: Optional[NormativeStatus] = None
    sortOrder: int
    sourceAnchors: List["SourceAnchor"] = Field(..., min_length=1)
    textContent: Optional[str] = None
    richText: List["RichTextSpan"] = Field(default_factory=list)
    listItems: List["ListItem"] = Field(default_factory=list)
    tableRef: Optional[str] = Field(None, pattern=r"^ssir:[A-Za-z0-9._:/-]+/table/[A-Za-z0-9_-]+$")
    figureRef: Optional[str] = Field(None, pattern=r"^ssir:[A-Za-z0-9._:/-]+/figure/[A-Za-z0-9_-]+$")
    formulaRef: Optional[str] = Field(None, pattern=r"^ssir:[A-Za-z0-9._:/-]+/formula/[A-Za-z0-9_-]+$")
    unknownRef: Optional[str] = Field(None, pattern=r"^ssir:[A-Za-z0-9._:/-]+/unknown/[A-Za-z0-9_-]+$")

    @field_validator("tableRef")
    @classmethod
    def validate_table_ref(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if info.data.get("presentationType") == PresentationType.TABLE and v is None:
            raise ValueError("tableRef required when presentationType=table")
        return v
    # 类似 validators for figureRef, formulaRef, unknownRef...


class Table(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/table/[A-Za-z0-9_-]+$")
    number: Optional[str] = None
    caption: Optional[str] = None
    rowCount: int = Field(..., ge=0)
    colCount: int = Field(..., ge=0)
    rows: List["TableRow"]
    tableNote: List[str] = Field(default_factory=list)
    sourceAnchors: List["SourceAnchor"] = Field(..., min_length=1)
    crossPage: Optional[bool] = None
    preservationStatus: Optional[PreservationStatus] = None


class TableRow(BaseModel):
    id: str = Field(..., pattern=r"^[A-Za-z0-9_-]+$")
    rowIndex: int = Field(..., ge=0)
    cells: List["TableCell"]
    isHeader: Optional[bool] = None


class TableCell(BaseModel):
    id: str = Field(..., pattern=r"^[A-Za-z0-9_-]+$")
    rowIndex: int = Field(..., ge=0)
    colIndex: int = Field(..., ge=0)
    text: Optional[str] = None
    richText: List["RichTextSpan"] = Field(default_factory=list)
    colspan: int = Field(default=1, ge=1)
    rowspan: int = Field(default=1, ge=1)
    isHeader: Optional[bool] = None
    sourceAnchor: Optional["SourceAnchor"] = None


class Figure(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/figure/[A-Za-z0-9_-]+$")
    number: Optional[str] = None
    caption: Optional[str] = None
    assetRef: Optional[str] = None
    altText: Optional[str] = None
    sourceAnchors: List["SourceAnchor"] = Field(..., min_length=1)
    preservationStatus: Optional[PreservationStatus] = None


class Formula(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/formula/[A-Za-z0-9_-]+$")
    number: Optional[str] = None
    rawText: str
    latex: Optional[str] = None
    sourceAnchors: List["SourceAnchor"] = Field(..., min_length=1)
    preservationStatus: Optional[PreservationStatus] = None


class UnknownContent(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/unknown/[A-Za-z0-9_-]+$")
    rawContent: str
    contentTypeHint: Optional[str] = None
    sourceAnchors: List["SourceAnchor"] = Field(..., min_length=1)


class ListItem(BaseModel):
    id: str = Field(..., pattern=r"^[A-Za-z0-9_-]+$")
    text: Optional[str] = None
    richText: List["RichTextSpan"] = Field(default_factory=list)
    marker: Optional[str] = None
    markerType: Optional[MarkerType] = None
    subItems: List["ListItem"] = Field(default_factory=list)
    sourceAnchor: Optional["SourceAnchor"] = None
    sortOrder: int


class RichTextSpan(BaseModel):
    text: str
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    subscript: Optional[bool] = None
    superscript: Optional[bool] = None
    underline: Optional[bool] = None
    style: Optional[str] = None


class TextSpan(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/span/[A-Za-z0-9_-]+$")
    canonicalTextId: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/canonical$")
    startChar: int = Field(..., ge=0)
    endChar: int = Field(..., ge=1)
    text: str
    sourceAnchor: Optional["SourceAnchor"] = None

    @field_validator("endChar")
    @classmethod
    def validate_char_bounds(cls, v: int, info: ValidationInfo) -> int:
        start = info.data.get("startChar")
        if start is not None and v <= start:
            raise ValueError("endChar must be greater than startChar")
        return v


class SourceAnchor(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/anchor/[A-Za-z0-9_-]+$")
    sourceFileId: str = Field(..., pattern=r"^src:[A-Fa-f0-9]{16,}$")
    anchorType: AnchorType
    pdfPageIndex: Optional[int] = Field(None, ge=0)
    documentPageLabel: Optional[str] = None
    bbox: Optional[List[float]] = Field(None, min_length=4, max_length=4,
                                        description="[x1,y1,x2,y2], PDF Point coordinate system")
    textSpanRef: Optional[str] = Field(None, pattern=r"^ssir:[A-Za-z0-9._:/-]+/span/[A-Za-z0-9_-]+$")
    textQuote: Optional[str] = None
    sourceBlockId: Optional[str] = None
    assetRef: Optional[str] = None
    extractionRegion: Optional[str] = None


class EntityMention(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/mention/[A-Za-z0-9_-]+$")
    surfaceForm: str
    normalizedForm: Optional[str] = None
    mentionType: EntityMentionType
    parentNodeId: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/[A-Za-z0-9._-]+$")
    sourceElementId: Optional[str] = Field(None, pattern=r"^ssir:[A-Za-z0-9._:/-]+/content/[A-Za-z0-9_-]+$")
    textSpan: TextSpan
    context: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    candidateMappings: List["CandidateMapping"] = Field(default_factory=list)


class CandidateMapping(BaseModel):
    ontology: str
    conceptId: str
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    status: Optional[str] = Field(None, pattern=r"^(candidate|confirmed|rejected)$")


class RelationMention(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/relation/[A-Za-z0-9_-]+$")
    relationType: RelationMentionType
    sourceId: str
    targetId: Optional[str] = None
    targetMentionText: Optional[str] = None
    parentNodeId: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/[A-Za-z0-9._-]+$")
    sourceElementId: Optional[str] = Field(None, pattern=r"^ssir:[A-Za-z0-9._:/-]+/content/[A-Za-z0-9_-]+$")
    textSpan: TextSpan
    evidence: Optional[str] = None
    resolutionStatus: Optional[ResolutionStatus] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

    @field_validator("targetId", "targetMentionText")
    @classmethod
    def validate_target(cls, target_id: Optional[str], info: ValidationInfo) -> Optional[str]:
        # targetId and targetMentionText at least one provided
        # This validator runs for each field; check both via info.data
        if info.field_name == "targetId":
            mention_text = info.data.get("targetMentionText")
            if target_id is None and mention_text is None:
                raise ValueError("Either targetId or targetMentionText must be provided")
        return target_id


class Reference(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/reference/[A-Za-z0-9_-]+$")
    sourceNodeId: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/[A-Za-z0-9._-]+$")
    referenceType: ReferenceType
    targetType: ReferenceTargetType
    rawTarget: str
    resolvedDocumentId: Optional[str] = None
    resolvedVersion: Optional[str] = None
    resolvedClause: Optional[str] = None
    citedText: Optional[str] = None
    textSpan: TextSpan
    resolutionStatus: Optional[ResolutionStatus] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class DocumentRelationship(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/docrel/[A-Za-z0-9_-]+$")
    sourceDocumentId: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+$")
    relationType: DocumentRelationshipType
    targetDocumentId: str
    targetVersion: Optional[str] = None
    validity: Optional[str] = None
    sourceAnchor: Optional[SourceAnchor] = None
    evidence: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class ProcessingRun(BaseModel):
    id: str = Field(..., pattern=r"^ssir:processing/run/[0-9]{8}-[0-9]+$")
    sourceFileId: str = Field(..., pattern=r"^src:[A-Fa-f0-9]{16,}$")
    runType: RunType
    tool: str
    toolVersion: str
    ocrUsed: Optional[bool] = None
    ocrEngine: Optional[str] = None
    model: Optional[str] = None
    modelVersion: Optional[str] = None
    timestamp: datetime
    configuration: Optional[dict] = None
    durationSeconds: Optional[float] = Field(None, ge=0)
    outputSummary: Optional[dict] = None


class QualityAssessment(BaseModel):
    id: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+/qa/[A-Za-z0-9_-]+$")
    documentId: str = Field(..., pattern=r"^ssir:[A-Za-z0-9._:/-]+$")
    runId: Optional[str] = Field(None, pattern=r"^ssir:processing/run/[0-9]{8}-[0-9]+$")
    renderingProfile: Optional[NormativeRenderingProfile] = None  # 新增 — JSON Schema v0.3
    overallStatus: OverallStatus
    structureConfidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    tableConfidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    figureConfidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    formulaConfidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    ocrConfidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    entityConfidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    relationConfidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    referenceConfidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    missingPages: List[int] = Field(default_factory=list)
    unresolvedTables: List[str] = Field(default_factory=list)
    unresolvedFigures: List[str] = Field(default_factory=list)
    unresolvedFormulas: List[str] = Field(default_factory=list)
    unresolvedReferences: List[str] = Field(default_factory=list)
    humanReviewStatus: Optional[HumanReviewStatus] = None
    comments: Optional[str] = None
    assessedAt: datetime
```

### 4.2 SSIR Equivalence Model（核心新增 — 四层比较）

定义在 `packages/core/equivalence.py`：

```python
# packages/core/equivalence.py
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class EquivalenceStatus(str, Enum):
    """单维度等价状态"""
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NOT_APPLICABLE = "N/A"


class ComparisonLevel(str, Enum):
    """比较严格程度 — Data Model v0.4 §7.6"""
    STRICT = "strict"          # 必须完全一致
    NORMALIZED = "normalized"  # 允许规范化差异
    IGNORED = "ignored"        # 不比较


class CriticalLossType(str, Enum):
    """关键信息丢失类型 — Data Model v0.4 §7.3 语义保护边界"""
    NORMATIVE_WORDING = "normative_wording"
    PROHIBITION = "prohibition"
    MANDATORY_CONDITION = "mandatory_condition"
    NUMERICAL_VALUE = "numerical_value"
    UNIT = "unit"
    COMPARISON_OPERATOR = "comparison_operator"
    CLAUSE_IDENTIFIER = "clause_identifier"
    TABLE_CELL_CONTENT = "table_cell_content"
    FORMULA_RAW = "formula_raw"
    REFERENCE_RAW = "reference_raw"
    SCOPE = "scope"
    APPLICABILITY = "applicability"


class CriticalLossItem(BaseModel):
    type: CriticalLossType
    description: str
    location: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None


class EquivalenceDimension(BaseModel):
    """单维度等价结果"""
    status: EquivalenceStatus
    matched: Optional[int] = None
    total: Optional[int] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class SSIREquivalenceResult(BaseModel):
    """SSIR 四层等价性结果 — Data Model v0.4 §7.5/7.6"""
    # Level 1: Identity Equivalence (STRICT)
    identity: EquivalenceDimension
    # Level 2: Structural Equivalence (STRICT)
    structure: EquivalenceDimension
    # Level 3: Content Equivalence (NORMALIZED)
    content: EquivalenceDimension
    # Level 4: Semantic Equivalence (STRICT)
    semantics: Optional[EquivalenceDimension] = None

    # Critical Information Loss Check
    criticalLosses: List[CriticalLossItem] = Field(default_factory=list)
    hasCriticalLoss: bool = False

    # Overall
    overallStatus: EquivalenceStatus

    # Normalization tracking
    expectedNormalizations: List[str] = Field(default_factory=list)
    semanticMutations: List[str] = Field(default_factory=list)

    def is_roundtrip_valid(self) -> bool:
        """判断是否通过 Round-trip 验证 — Data Model v0.4 §7.5"""
        if self.hasCriticalLoss:
            return False
        if self.overallStatus == EquivalenceStatus.FAIL:
            return False
        if self.identity.status == EquivalenceStatus.FAIL:
            return False
        if self.structure.status == EquivalenceStatus.FAIL:
            return False
        if self.content.status == EquivalenceStatus.FAIL:
            return False
        return True
```

### 4.3 RoundTripReport（核心新增）

定义在 `packages/core/roundtrip.py`：

```python
# packages/core/roundtrip.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from .equivalence import SSIREquivalenceResult, EquivalenceStatus


class RenderingFidelityResult(BaseModel):
    """Rendering Fidelity Test 结果 — 独立于 Round-trip Equivalence"""
    status: EquivalenceStatus
    matched: int
    total: int
    details: dict = Field(default_factory=dict)


class RoundTripReport(BaseModel):
    """Round-trip 完整报告 — Data Model v0.4 §7.1-7.8"""
    reportId: str
    timestamp: datetime
    documentId: str

    # 三阶段标识 (Canonical → SSIR → Render.md → Verify)
    ssirId: str
    renderMdId: Optional[str] = None
    verifyId: Optional[str] = None
    renderingProfile: Optional[str] = None  # 使用的 Rendering Profile

    # 核心等价性结果 (SSIR ≈ Verify)
    equivalence: SSIREquivalenceResult

    # Rendering Fidelity (独立测试)
    renderingFidelity: Optional[RenderingFidelityResult] = None

    # 汇总
    overallStatus: EquivalenceStatus

    # 元数据
    extractionRunId: Optional[str] = None
    renderingRunId: Optional[str] = None
    reExtractionRunId: Optional[str] = None

    def is_roundtrip_valid(self) -> bool:
        return self.equivalence.is_roundtrip_valid()

    def has_critical_loss(self) -> bool:
        return self.equivalence.hasCriticalLoss
```

### 4.4 Allowed Transformation / Semantic Mutation

定义在 `packages/core/transformation.py`：

```python
# packages/core/transformation.py
from enum import Enum


class TransformationType(str, Enum):
    """转换差异分类 — Data Model v0.4 §7.3"""
    EQUIVALENT = "equivalent"
    EXPECTED_NORMALIZATION = "expected_normalization"
    DERIVED_CHANGE = "derived_change"
    CONTENT_LOSS = "content_loss"
    SEMANTIC_CHANGE = "semantic_change"
    STRUCTURAL_CHANGE = "structural_change"
    UNRESOLVED = "unresolved"


# 允许的规范化规则 — Data Model v0.4 §7.3
ALLOWED_NORMALIZATIONS = [
    "whitespace_normalization",          # 空格规范化
    "line_break_unification",            # 换行统一
    "punctuation_normalization",         # 标点规范化
    "number_format_normalization",       # 数字格式
    "unit_abbreviation_normalization",   # 单位缩写
    "reference_separator_normalization", # 引用分隔符
]

# 绝对禁止的变化 — Data Model v0.4 §7.3 语义保护边界
FORBIDDEN_CHANGES = [
    "normative_verb_change",      # 应 → 宜
    "prohibition_change",         # 不得 → 不应
    "numeric_value_change",       # 90 → 80
    "unit_change",                # MPa → kPa
    "comparison_operator_change", # ≥ → >
    "clause_identifier_change",   # 5.2.1 → 5.2
    "scope_change",               # 范围改变
    "applicability_change",       # 适用性改变
]
```

### 4.5 Extraction IR 模型

定义在 `packages/core/extraction_ir.py`：

```python
# packages/core/extraction_ir.py
from typing import Optional, List, Literal, Tuple
from pydantic import BaseModel, Field
from .enums import SourceMethod


class ExtractionBlock(BaseModel):
    blockId: str
    type: Literal["text", "heading", "table", "figure", "formula", "list", "note"]
    bbox: Tuple[float, float, float, float] = Field(..., description="[x1,y1,x2,y2], PDF Point coordinates")
    text: Optional[str] = None
    children: List["ExtractionBlock"] = Field(default_factory=list)
    readingOrder: int
    confidence: float = Field(..., ge=0.0, le=1.0)
    pageIndex: int
    sourceMethod: SourceMethod  # 必须记录: native_text / ocr / docx
    tableData: Optional[dict] = None  # 表格结构化数据（MinerU 输出）
    imageRef: Optional[str] = None
    formulaRaw: Optional[str] = None


class ExtractionPage(BaseModel):
    pageIndex: int
    pageLabel: str
    blocks: List[ExtractionBlock] = Field(default_factory=list)


class ExtractionIR(BaseModel):
    sourceFileId: str
    processingRunId: str
    pages: List[ExtractionPage] = Field(default_factory=list)
    metadata: Optional[dict] = None
    extractionConfidence: float = Field(..., ge=0.0, le=1.0)
    ocrUsed: bool = False
    ocrEngine: Optional[str] = None
```

### 4.6 Rendering IR 模型

定义在 `packages/core/rendering_ir.py`：

```python
# packages/core/rendering_ir.py
from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field


class RenderingStyle(BaseModel):
    fontName: str = "宋体"
    fontSize: int = 12
    bold: bool = False
    italic: bool = False
    alignment: Literal["left", "center", "right", "justify"] = "left"
    spaceBefore: Optional[int] = None
    spaceAfter: Optional[int] = None


class RenderingNode(BaseModel):
    type: Literal["section", "clause", "paragraph", "table", "figure", "formula", "list"]
    number: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    children: List["RenderingNode"] = Field(default_factory=list)
    style: Optional[RenderingStyle] = None
    tableData: Optional[dict] = None
    figureRef: Optional[str] = None
    formulaText: Optional[str] = None
    listItems: Optional[List[dict]] = None


class RenderingIR(BaseModel):
    documentId: str
    profile: str  # "GB_T_1.1-2020"
    nodes: List[RenderingNode]
    styles: Dict[str, RenderingStyle]
    pageSetup: Optional[dict] = None
    metadata: Optional[dict] = None
```

### 4.7 枚举定义（必须完整实现）

定义在 `packages/core/enums.py`：

```python
# packages/core/enums.py
from enum import Enum


class DocumentType(str, Enum):
    STANDARD = "standard"
    REGULATION = "regulation"
    SPECIFICATION = "specification"
    ENTERPRISE_STANDARD = "enterpriseStandard"
    CONTRACT = "contract"
    TEST_REPORT = "testReport"
    OTHER = "other"


class StructuralNodeType(str, Enum):
    DOCUMENT = "document"
    DOCUMENT_BLOCK = "documentBlock"
    SECTION = "section"
    CLAUSE = "clause"
    SUB_CLAUSE = "subClause"
    ITEM = "item"
    SUB_ITEM = "subItem"
    ANNEX = "annex"
    ANNEX_SECTION = "annexSection"


class PresentationType(str, Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    FORMULA = "formula"
    NOTE = "note"
    EXAMPLE = "example"
    WARNING = "warning"
    QUOTE = "quote"
    FOOTNOTE = "footnote"
    OTHER = "other"


class SemanticType(str, Enum):
    SCOPE = "scope"
    NORMATIVE_REFERENCE = "normativeReference"
    TERM_DEFINITION = "termDefinition"
    SYMBOL_DEFINITION = "symbolDefinition"
    CLASSIFICATION = "classification"
    REQUIREMENT = "requirement"
    TEST_METHOD = "testMethod"
    INSPECTION_RULE = "inspectionRule"
    MARKING_REQUIREMENT = "markingRequirement"
    PACKAGING_TRANSPORT_STORAGE = "packagingTransportStorage"
    EXAMPLE = "example"
    WARNING = "warning"
    NOTE = "note"
    APPENDIX_EXPLANATION = "appendixExplanation"
    BIBLIOGRAPHIC_REFERENCE = "bibliographicReference"


class NormativeStatus(str, Enum):
    NORMATIVE = "normative"
    INFORMATIVE = "informative"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "notApplicable"


class AnchorType(str, Enum):
    PAGE = "page"
    BBOX = "bbox"
    TEXT_SPAN = "textSpan"
    BLOCK = "block"
    TABLE_CELL = "tableCell"
    FIGURE_REGION = "figureRegion"


class EntityMentionType(str, Enum):
    DOCUMENT_CONCEPT = "documentConcept"
    PRODUCT = "product"
    MATERIAL = "material"
    ORGANIZATION = "organization"
    STANDARD = "standard"
    REGULATION = "regulation"
    PROCESS = "process"
    EQUIPMENT = "equipment"
    PARAMETER = "parameter"
    UNIT = "unit"
    VALUE = "value"
    TIME = "time"
    LOCATION = "location"
    IDENTIFIER = "identifier"
    OTHER = "other"


class RelationMentionType(str, Enum):
    DEFINES = "defines"
    HAS_PROPERTY = "hasProperty"
    APPLIES_TO = "appliesTo"
    MEASURES = "measures"
    REQUIRES = "requires"
    CONSTRAINS = "constrains"
    EQUIVALENT_TO = "equivalentTo"


class ReferenceType(str, Enum):
    NORMATIVE = "normative"
    INFORMATIVE = "informative"
    MANDATORY = "mandatory"
    CONDITIONAL = "conditional"


class ReferenceTargetType(str, Enum):
    INTERNAL_CLAUSE = "internalClause"
    INTERNAL_ANNEX = "internalAnnex"
    INTERNAL_TABLE = "internalTable"
    INTERNAL_FIGURE = "internalFigure"
    EXTERNAL_STANDARD = "externalStandard"
    EXTERNAL_REGULATION = "externalRegulation"
    EXTERNAL_DOCUMENT = "externalDocument"
    EXTERNAL_TECHNICAL_SPECIFICATION = "externalTechnicalSpecification"


class DocumentRelationshipType(str, Enum):
    REPLACES = "replaces"
    REPLACED_BY = "replacedBy"
    AMENDS = "amends"
    AMENDED_BY = "amendedBy"
    SUPPLEMENTS = "supplements"
    SUPPLEMENTED_BY = "supplementedBy"
    EQUIVALENT_TO = "equivalentTo"
    ADOPTS = "adopts"
    ADOPTED_BY = "adoptedBy"
    REFERENCES = "references"
    REFERENCED_BY = "referencedBy"


class MarkerType(str, Enum):
    LOWER_ALPHA = "lowerAlpha"
    UPPER_ALPHA = "upperAlpha"
    NUMERIC = "numeric"
    ROMAN = "roman"
    BULLET = "bullet"
    DASH = "dash"
    OTHER = "other"


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    PARTIALLY_RESOLVED = "partiallyResolved"


class RunType(str, Enum):
    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"
    ENTITY_RECOGNITION = "entityRecognition"
    RELATION_EXTRACTION = "relationExtraction"
    REFERENCE_RESOLUTION = "referenceResolution"
    HUMAN_REVIEW = "humanReview"
    OTHER = "other"


class OverallStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    EXTRACTION_FAILED = "extractionFailed"
    REQUIRES_REVIEW = "requiresReview"
    APPROVED = "approved"
    REJECTED = "rejected"


class HumanReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    MACHINE_REVIEWED = "machineReviewed"
    HUMAN_REVIEWED = "humanReviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class PreservationLevel(str, Enum):
    LEVEL_0 = "Level0"
    LEVEL_1 = "Level1"
    LEVEL_2 = "Level2"
    LEVEL_3 = "Level3"
    LEVEL_4 = "Level4"


class PreservationStatus(str, Enum):
    PRESERVED = "preserved"
    PARTIALLY_PRESERVED = "partiallyPreserved"
    NOT_PRESERVED = "notPreserved"


class NormativeRenderingProfile(str, Enum):
    """规范性渲染配置文件 — 新增于 JSON Schema v0.3 / Data Model v0.4 §7.3"""
    GB_T_1_1_2020 = "GB_T_1.1-2020"
    ISO_IEC_DIRECTIVES_PART_2 = "iso-iec-directives-part-2"
    CUSTOM = "custom"


class EquivalenceStatus(str, Enum):
    """单维度等价状态 — 用于 SSIR Equivalence Model"""
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NOT_APPLICABLE = "N/A"


class ComparisonLevel(str, Enum):
    """比较严格程度 — Data Model v0.4 §7.6"""
    STRICT = "strict"
    NORMALIZED = "normalized"
    IGNORED = "ignored"


class CriticalLossType(str, Enum):
    """关键信息丢失类型 — Data Model v0.4 §7.3 语义保护边界"""
    NORMATIVE_WORDING = "normative_wording"
    PROHIBITION = "prohibition"
    MANDATORY_CONDITION = "mandatory_condition"
    NUMERICAL_VALUE = "numerical_value"
    UNIT = "unit"
    COMPARISON_OPERATOR = "comparison_operator"
    CLAUSE_IDENTIFIER = "clause_identifier"
    TABLE_CELL_CONTENT = "table_cell_content"
    FORMULA_RAW = "formula_raw"
    REFERENCE_RAW = "reference_raw"
    SCOPE = "scope"
    APPLICABILITY = "applicability"


class TransformationType(str, Enum):
    """转换差异分类 — Data Model v0.4 §7.3"""
    EQUIVALENT = "equivalent"
    EXPECTED_NORMALIZATION = "expected_normalization"
    DERIVED_CHANGE = "derived_change"
    CONTENT_LOSS = "content_loss"
    SEMANTIC_CHANGE = "semantic_change"
    STRUCTURAL_CHANGE = "structural_change"
    UNRESOLVED = "unresolved"


class SourceMethod(str, Enum):
    """提取来源方法 — Extraction IR"""
    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    DOCX = "docx"


class NormalizationPolicy(str, Enum):
    """CanonicalText 规范化策略"""
    SSIR_CANONICAL_TEXT_V1 = "ssir-canonical-text-v1"


class RenderingProfileType(str, Enum):
    """渲染配置文件类型 — Rendering IR"""
    GB_T_1_1_2020 = "GB_T_1.1-2020"
    ISO_IEC = "iso-iec"
    CUSTOM = "custom"
```


## 5. Internal Interface Contract（新增）

> **本节定义所有核心模块的 Python 抽象类/协议接口。所有实现必须遵循这些接口定义。**

### 5.1 Ingestion Service Interface

```python
# packages/ingestion/interface.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from packages.core.ssir import SourceFile, ProcessingRun
from packages.ingestion.profiles import DocumentSourceProfile


class IngestionService(ABC):
    """文档接入服务接口"""

    @abstractmethod
    def detect(self, file_path: Path) -> DocumentSourceProfile:
        """检测文件类型和质量"""
        pass

    @abstractmethod
    def create_source_file(self, file_path: Path, metadata: Optional[dict] = None) -> SourceFile:
        """创建 SourceFile 对象"""
        pass

    @abstractmethod
    def create_processing_run(self, source_file_id: str) -> ProcessingRun:
        """创建 ProcessingRun 对象"""
        pass

    @abstractmethod
    def store_file(self, source_file: SourceFile, file_path: Path) -> str:
        """存储源文件到对象存储，返回 storageUri"""
        pass
```

### 5.2 Extraction Service Interface

```python
# packages/extraction/interface.py
from abc import ABC, abstractmethod
from pathlib import Path
from packages.core.extraction_ir import ExtractionIR
from packages.core.ssir import SourceFile


class ExtractionAdapter(ABC):
    """解析器适配器接口"""

    @abstractmethod
    def extract(self, source_file: SourceFile, file_path: Path) -> ExtractionIR:
        """提取文档内容，返回 Extraction IR"""
        pass

    @abstractmethod
    def supports(self, mime_type: str) -> bool:
        """判断是否支持该 MIME 类型"""
        pass


class OCRPipeline(ABC):
    """OCR 管道接口"""

    @abstractmethod
    def process(self, file_path: Path, pages: Optional[list] = None) -> ExtractionIR:
        """对扫描 PDF 执行 OCR"""
        pass

    @abstractmethod
    def get_confidence(self) -> float:
        """获取 OCR 置信度"""
        pass
```

### 5.3 SSIR Builder Interface

```python
# packages/ssir_builder/interface.py
from abc import ABC, abstractmethod
from packages.core.extraction_ir import ExtractionIR
from packages.core.ssir import SSIRDocument, SourceFile, ProcessingRun, CanonicalText


class SSIRBuilder(ABC):
    """SSIR 构建器接口"""

    @abstractmethod
    def build(
        self,
        extraction_ir: ExtractionIR,
        source_file: SourceFile,
        processing_run: ProcessingRun
    ) -> SSIRDocument:
        """从 Extraction IR 构建 SSIR 文档（L0-L3）"""
        pass

    @abstractmethod
    def build_canonical_text(self, extraction_ir: ExtractionIR) -> CanonicalText:
        """构建权威文本"""
        pass

    @abstractmethod
    def build_structure(self, extraction_ir: ExtractionIR) -> "StructuralNode":
        """构建结构树"""
        pass

    @abstractmethod
    def build_content(self, extraction_ir: ExtractionIR) -> list:
        """构建内容元素"""
        pass

    @abstractmethod
    def build_provenance(self, ssir: SSIRDocument) -> None:
        """建立溯源信息"""
        pass
```

### 5.4 Validation Service Interface

```python
# packages/validator/interface.py
from abc import ABC, abstractmethod
from packages.core.ssir import SSIRDocument, QualityAssessment
from packages.validator.types import ValidationReport


class ValidationService(ABC):
    """验证服务接口"""

    @abstractmethod
    def validate_schema(self, ssir: SSIRDocument) -> ValidationReport:
        """Schema 验证"""
        pass

    @abstractmethod
    def validate_structural(self, ssir: SSIRDocument) -> ValidationReport:
        """结构验证"""
        pass

    @abstractmethod
    def validate_content(self, ssir: SSIRDocument) -> ValidationReport:
        """内容验证"""
        pass

    @abstractmethod
    def validate_provenance(self, ssir: SSIRDocument) -> ValidationReport:
        """溯源验证"""
        pass

    @abstractmethod
    def assess_quality(self, ssir: SSIRDocument, rendering_profile: Optional[str] = None) -> QualityAssessment:
        """生成质量评估（含 renderingProfile）"""
        pass
```

### 5.5 Normative Rendering Service Interface

```python
# packages/rendering/interface.py
from abc import ABC, abstractmethod
from packages.core.ssir import SSIRDocument
from packages.core.rendering_ir import RenderingIR
from packages.rendering.profile import NormativeRenderingProfile


class RenderingService(ABC):
    """规范性渲染服务接口"""

    @abstractmethod
    def render(
        self,
        ssir: SSIRDocument,
        profile: NormativeRenderingProfile,
        options: Optional[dict] = None
    ) -> RenderingIR:
        """从 SSIR 生成 Rendering IR"""
        pass

    @abstractmethod
    def to_docx(self, rendering_ir: RenderingIR) -> bytes:
        """Rendering IR → DOCX"""
        pass

    @abstractmethod
    def to_pdf(self, rendering_ir: RenderingIR) -> bytes:
        """Rendering IR → PDF"""
        pass

    @abstractmethod
    def to_html(self, rendering_ir: RenderingIR) -> str:
        """Rendering IR → HTML"""
        pass

    @abstractmethod
    def get_profile(self, name: str) -> NormativeRenderingProfile:
        """获取指定的渲染配置"""
        pass
```

### 5.6 Round-trip Verification Service Interface

```python
# packages/roundtrip/interface.py
from abc import ABC, abstractmethod
from pathlib import Path
from packages.core.ssir import SSIRDocument
from packages.core.equivalence import SSIREquivalenceResult
from packages.core.roundtrip import RoundTripReport
from packages.roundtrip.critical_check import CriticalLossResult
from packages.rendering.profile import NormativeRenderingProfile


class RoundtripVerifier(ABC):
    """往返测试验证器接口"""

    @abstractmethod
    def verify(
        self,
        canonical: Path,
        profile: NormativeRenderingProfile,
        options: Optional[dict] = None
    ) -> RoundTripReport:
        """执行完整的往返测试"""
        pass

    @abstractmethod
    def compare_ssir(self, ssir: SSIRDocument, verify: SSIRDocument) -> SSIREquivalenceResult:
        """四层比较两个 SSIR"""
        pass

    @abstractmethod
    def check_critical_loss(self, ssir: SSIRDocument, verify: SSIRDocument) -> CriticalLossResult:
        """执行 12 项 Critical Loss 检查"""
        pass

    @abstractmethod
    def test_rendering_fidelity(
        self,
        ssir: SSIRDocument,
        profile: NormativeRenderingProfile
    ) -> dict:
        """独立的 Rendering Fidelity 测试"""
        pass
```

### 5.7 Repository Interface

```python
# packages/storage/interface.py
from abc import ABC, abstractmethod
from typing import Optional, List
from packages.core.ssir import SSIRDocument, SourceFile, ProcessingRun, QualityAssessment


class Repository(ABC):
    """数据仓库接口"""

    # Document operations
    @abstractmethod
    def save_document(self, document: SSIRDocument) -> str:
        """保存 SSIR 文档（含版本化）"""
        pass

    @abstractmethod
    def get_document(self, document_id: str, version: Optional[int] = None) -> Optional[SSIRDocument]:
        """获取 SSIR 文档"""
        pass

    @abstractmethod
    def list_documents(self, limit: int = 20, offset: int = 0, **filters) -> List[SSIRDocument]:
        """列出 SSIR 文档"""
        pass

    @abstractmethod
    def delete_document(self, document_id: str, force: bool = False) -> bool:
        """删除 SSIR 文档"""
        pass

    @abstractmethod
    def get_document_status(self, document_id: str) -> str:
        """获取文档处理状态"""
        pass

    # SourceFile operations
    @abstractmethod
    def save_source_file(self, source_file: SourceFile) -> str:
        pass

    @abstractmethod
    def get_source_file(self, source_file_id: str) -> Optional[SourceFile]:
        pass

    # ProcessingRun operations
    @abstractmethod
    def save_processing_run(self, run: ProcessingRun) -> str:
        pass

    @abstractmethod
    def get_processing_run(self, run_id: str) -> Optional[ProcessingRun]:
        pass

    # QualityAssessment operations
    @abstractmethod
    def save_quality_assessment(self, qa: QualityAssessment) -> str:
        pass

    @abstractmethod
    def get_quality_assessment(self, document_id: str, version: Optional[int] = None) -> Optional[QualityAssessment]:
        pass


class ObjectStorage(ABC):
    """对象存储接口"""

    @abstractmethod
    def upload(self, key: str, data: bytes, content_type: str) -> str:
        """上传文件，返回 URI"""
        pass

    @abstractmethod
    def download(self, key: str) -> bytes:
        """下载文件"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除文件"""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查文件是否存在"""
        pass

    @abstractmethod
    def get_uri(self, key: str) -> str:
        """获取文件 URI"""
        pass
```


## 6. Implementation Tasks (Sprint by Sprint)

### Task 0: Core Model & Setup (Day 1-2)

**产出**：所有 Pydantic 模型、JSON Schema v0.3、config.yaml、pyproject.toml

**AI 编码指令**：

1. 初始化项目，创建上述完整目录结构
2. 编写 `pyproject.toml` 包含所有依赖（**Pydantic >=2.5**）
3. 实现 `packages/core/enums.py` 所有枚举（**含所有新增枚举**）
4. 实现 `packages/core/ssir.py` 中的所有 Pydantic 模型（**Data Model v0.4**）：
   - 使用 `@field_validator` 而非 `@validator`（Pydantic v2）
   - 使用 `Field(min_length=...)` 而非 `min_items`
   - 使用 `pattern=` 参数进行 ID 格式验证
   - 所有模型必须通过 `mypy --strict` 检查
5. 实现 `packages/core/extraction_ir.py` 和 `rendering_ir.py`
6. 实现 `packages/core/equivalence.py`（**四层 SSIR Equivalence Model**）
7. 实现 `packages/core/transformation.py`（**ALLOWED_NORMALIZATIONS + FORBIDDEN_CHANGES**）
8. 实现 `packages/core/roundtrip.py`（**RoundTripReport**）
9. 将 JSON Schema v0.3 输出为 `packages/core/schema/ssir.schema.json`
10. 编写 `config.yaml`
11. **确保所有模型通过 `mypy --strict` 检查**
12. 为所有模型编写初步单元测试
13. 实现 `packages/core/interface.py`（所有抽象接口定义）

### Task 1: Ingestion Service (Day 2-3)

**产出**：DocumentDetector, SourceFileBuilder, ProcessingRunInitializer

**AI 编码指令**：

1. 实现 `packages/ingestion/detector.py`：
   - 识别文件 MIME 类型（使用 `magic` 或 `mimetypes`）
   - 判断 PDF 是否扫描（使用 PyMuPDF 检测文本层）
   - 判断 PDF 类型：`text` / `scanned` / `hybrid`
   - 输出 `DocumentSourceProfile`（含 `textLayerQuality`、`pages` 逐页分类、`ocrRequired`、`ocrCoverage`）
   - 检测文件是否加密或损坏
2. 实现 `packages/ingestion/source_file.py`：
   - 计算 SHA-256 hash（含 algorithm + value）
   - 提取文件大小、页数
   - 生成 `SourceFile` 对象
3. 实现 `packages/ingestion/profiles.py`：定义 `DocumentSourceProfile` Pydantic 模型
4. 实现 `packages/ingestion/processing_run.py`：创建初始 `ProcessingRun` 对象

### Task 2: Extraction Service — MinerU Adapter (Day 3-5)

**产出**：MinerUAdapter, OCRPipeline, ExtractionIR

**AI 编码指令**：

1. 实现 `packages/extraction/adapter.py`：解析器适配器抽象基类，定义 `extract()` 方法签名
2. 实现 `packages/extraction/mineru_adapter.py`：
   - 调用 MinerU CLI（`magic-pdf`）
   - 解析 MinerU 输出的 JSON/Markdown
   - 提取 page、block、bbox、text、table、image、formula
   - 记录 `sourceMethod`（`native_text` / `ocr`）
   - 转换为 `ExtractionIR`
   - 必须处理：文本PDF、扫描PDF、混合PDF
   - 保留 OCR 置信度
   - **禁止将 MinerU 数据结构直接作为 SSIR**
3. 实现 `packages/extraction/docx_adapter.py`：
   - 使用 `python-docx` 解析 DOCX
   - 提取段落、表格、图片
   - 转换为 `ExtractionIR`
4. 实现 `packages/extraction/ocr_pipeline.py`：
   - 对扫描 PDF 触发 OCR
   - 配置 OCR 引擎（PaddleOCR / Tesseract）
   - 输出 bbox + 文本 + 置信度
   - 记录 OCR 引擎和版本到 ProcessingRun
5. 实现 `packages/extraction/layout_analyzer.py`：
   - 分析页面布局（单栏/双栏）
   - 识别页眉、页脚、页码
   - 识别标题层级
6. 实现 `packages/extraction/reading_order.py`：
   - 确定阅读顺序（基于 bbox y/x 坐标）
   - 处理双栏布局的阅读顺序

### Task 3: CanonicalText & Structure Builder (Day 5-7)

**产出**：CanonicalTextBuilder, StructureBuilder, MetadataExtractor

**AI 编码指令**：

1. 实现 `packages/canonical_text/builder.py`：
   - 按阅读顺序提取所有文本
   - 规范化文本（去除多余空白，保留原文）
   - 生成 `CanonicalText` 对象
   - 遵循 `ssir-canonical-text-v1` 规范化策略
2. 实现 `packages/canonical_text/text_span.py`：
   - 为每个内容片段生成 `TextSpan`
   - 记录 `startChar`/`endChar` 与 CanonicalText 的映射
   - 确保 `startChar < endChar`
3. 实现 `packages/canonical_text/normalizer.py`：
   - 实现文本规范化规则（空格、换行、Unicode NFC）
4. 实现 `packages/ssir_builder/metadata.py`：
   - 从 Extraction IR 提取元数据
   - 识别标准号、标题、日期、发布机构
   - 使用规则（正则表达式），**不使用 LLM**
5. 实现 `packages/ssir_builder/structure.py`：
   - 识别章节编号（`1`, `2.1`, `2.1.1`, `a)`, `1)`）
   - 建立 `StructuralNode` 树
   - 分配 `logicalId`、`level`、`sortOrder`
   - **禁止使用 LLM 解析编号** — 必须使用确定性规则

### Task 4: Content Builder (Day 7-10)

**产出**：所有 ContentElement 构建器

**AI 编码指令**：

1. 实现 `packages/ssir_builder/content.py`：
   - 将 Extraction IR 的 block 分类为 `presentationType`
   - 生成 `ContentElement` 对象
   - 关联到父 StructuralNode
   - 保留 `sortOrder` 以维护原始顺序
2. 实现 `packages/ssir_builder/table.py`：
   - 处理 MinerU 表格输出
   - 构建 `Table`、`TableRow`、`TableCell`
   - 处理合并单元格（`rowspan`/`colspan`）
   - 识别表头行（`isHeader`）
   - 记录 `crossPage`
   - 保存 `tableNote`
   - 处理单元格内富文本（`richText`）
3. 实现 `packages/ssir_builder/figure.py`：
   - 提取图编号和标题
   - 保存 `assetRef`（图片文件路径/URL）
   - 生成 `Figure` 对象
4. 实现 `packages/ssir_builder/formula.py`：
   - 提取公式编号
   - 保存 `rawText`（OCR 文本）— **必须非空**
   - 如果有 LaTeX 则保存 `latex`
   - 生成 `Formula` 对象
5. 实现 `packages/ssir_builder/list.py`：
   - 识别列表结构
   - 提取 `marker` 和 `markerType`
   - 构建嵌套 `ListItem`
6. 实现 `packages/ssir_builder/unknown.py`：
   - 所有无法分类的内容 → `UnknownContent`
   - **绝不丢弃任何内容**
   - 保留 `rawContent` 和 `SourceAnchor`

### Task 5: Provenance Builder (Day 10-11)

**产出**：SourceAnchor 建立

**AI 编码指令**：

1. 实现 `packages/ssir_builder/provenance.py`：
   - 为每个 `StructuralNode` 建立 `SourceAnchor`
   - 为每个 `ContentElement` 建立 `SourceAnchor`
   - 为每个 `Table`/`Figure`/`Formula` 建立 `SourceAnchor`
   - 为每个 `EntityMention`/`RelationMention` 建立 `SourceAnchor`
   - 记录 `pdfPageIndex`、`bbox`、`textSpanRef`、`textQuote`
   - 确保 `SourceAnchor` 包含 `pdfPageIndex`
   - 确保 `TextSpan` 关联 `CanonicalText`

### Task 6: Validator (Day 11-12)

**产出**：所有验证器 + QualityAssessment

**AI 编码指令**：

1. 实现 `packages/validator/schema.py`：
   - 使用 `jsonschema` 库验证 JSON Schema v0.3
   - 验证 `ssirVersion` 为 `"0.3"` 或 `"0.4"`
   - 验证新增字段：`NormativeRenderingProfile`、`QualityAssessment.renderingProfile`
2. 实现 `packages/validator/structural.py`：
   - 验证根节点唯一性（`nodeType: document`）
   - 验证 parent 引用存在
   - 验证 `sortOrder` 连续性
   - 验证层级深度合法性
3. 实现 `packages/validator/content.py`：
   - 验证 `tableRef`/`figureRef`/`formulaRef`/`unknownRef` 存在性
   - 验证内容不丢失
   - 验证表格行列数与实际 rows/cells 匹配
4. 实现 `packages/validator/provenance.py`：
   - 检查核心对象是否有 `SourceAnchor`
   - 检查 `SourceAnchor.sourceFileId` 是否存在
5. 实现 `packages/validator/quality.py`：
   - 生成 `QualityAssessment`（**含 `renderingProfile`**）
   - 计算各维度置信度
   - 设置 `overallStatus`

### Task 7: Normative Rendering Service (Day 12-15)

**产出**：SSIR → DOCX/PDF **规范性渲染器**

**AI 编码指令**：

1. 实现 `packages/rendering/profile.py`：`RenderingProfile` 基类，定义 `semanticRules` 和 `presentationRules`
2. 实现 `packages/rendering/gb_t_1_1_profile.py`：
   - 定义 GB/T 1.1-2020 样式
   - 标题字体、字号、对齐
   - 表格样式、图样式、公式样式
   - 明确这是 **Normative Rendering**（Data Model v0.4 §7.3）
   - 实现允许的规范化规则（`ALLOWED_NORMALIZATIONS`）
   - **禁止实现** `FORBIDDEN_CHANGES` 中的任何变换
3. 实现 `packages/rendering/docx_renderer.py`：
   - 遍历 `StructuralNode` 和 `ContentElement`
   - 写入 DOCX 段落、标题、表格、图（作为图片）、公式（作为文本）
   - 应用 GB/T 1.1 样式
   - 生成 `RenderingIR`
4. 实现 `packages/rendering/pdf_converter.py`：
   - 使用 LibreOffice headless 或 python-docx → PDF 转换
   - 或使用 weasyprint
5. 确保 `QualityAssessment.renderingProfile` 被正确填充

### Task 8: Round-trip Verification Service (Day 15-17) ⚠️ **核心任务**

**产出**：SSIRComparator（四层比较）, RoundTripVerifier, CriticalLossChecker, RenderingFidelityTest

**AI 编码指令**：

#### 8.1 实现 `packages/roundtrip/comparator.py` — 四层比较

```python
class SSIRComparator:
    """SSIR 四层等价性比较器 — Data Model v0.4 §7.5/7.6"""

    def compare(self, ssir: SSIRDocument, verify: SSIRDocument) -> SSIREquivalenceResult:
        result = SSIREquivalenceResult()

        # Level 1: Identity Equivalence (STRICT)
        result.identity = self._compare_identity(ssir, verify)

        # Level 2: Structural Equivalence (STRICT)
        result.structure = self._compare_structure(ssir, verify)

        # Level 3: Content Equivalence (NORMALIZED)
        result.content = self._compare_content(ssir, verify)

        # Level 4: Semantic Equivalence (STRICT) — 如可用
        result.semantics = self._compare_semantics(ssir, verify)

        # Critical Information Loss Check
        critical_checker = CriticalLossChecker()
        result.criticalLosses = critical_checker.check(ssir, verify)
        result.hasCriticalLoss = len(result.criticalLosses) > 0

        # Track expected normalizations
        result.expectedNormalizations = self._detect_expected_normalizations(ssir, verify)

        # Overall status
        result.overallStatus = self._determine_overall_status(result)

        return result

    def _compare_identity(self, ssir: SSIRDocument, verify: SSIRDocument) -> EquivalenceDimension:
        """比较 Identity 字段 — STRICT 级别"""
        # 比较 standardNumber, title, dates, issuer, etc.
        pass

    def _compare_structure(self, ssir: SSIRDocument, verify: SSIRDocument) -> EquivalenceDimension:
        """比较结构树 — STRICT 级别"""
        # 递归比较节点、层级、编号 (Data Model v0.4 §7.6)
        pass

    def _compare_content(self, ssir: SSIRDocument, verify: SSIRDocument) -> EquivalenceDimension:
        """比较内容 — NORMALIZED 级别 (Data Model v0.4 §7.6)"""
        # 应用 ALLOWED_NORMALIZATIONS 后比较
        pass

    def _compare_semantics(self, ssir: SSIRDocument, verify: SSIRDocument) -> Optional[EquivalenceDimension]:
        """比较语义 — STRICT 级别 (Data Model v0.4 §7.6)"""
        # Requirement, Scope, Definition, etc.
        pass
```

#### 8.2 实现 `packages/roundtrip/critical_check.py` — 12 项 Critical Loss Check

```python
class CriticalLossChecker:
    """关键信息丢失检查器 — Data Model v0.4 §7.3 语义保护边界"""

    def check(self, ssir: SSIRDocument, verify: SSIRDocument) -> List[CriticalLossItem]:
        losses = []

        # 检查 12 项 Critical Information
        losses.extend(self._check_normative_wording(ssir, verify))
        losses.extend(self._check_prohibitions(ssir, verify))
        losses.extend(self._check_numerical_values(ssir, verify))
        losses.extend(self._check_units(ssir, verify))
        losses.extend(self._check_comparison_operators(ssir, verify))
        losses.extend(self._check_clause_identifiers(ssir, verify))
        losses.extend(self._check_table_cell_content(ssir, verify))
        losses.extend(self._check_formula_raw(ssir, verify))
        losses.extend(self._check_reference_raw(ssir, verify))
        losses.extend(self._check_scope(ssir, verify))
        losses.extend(self._check_applicability(ssir, verify))
        losses.extend(self._check_mandatory_conditions(ssir, verify))

        return losses
```

#### 8.3 实现 `packages/roundtrip/verifier.py`

```python
class RoundTripVerifier:
    """执行完整的 Round-trip 验证 — Data Model v0.4 §7.1"""

    def verify(
        self,
        canonical: Path,
        renderer: RenderingService,
        extractor: ExtractionAdapter,
        profile: NormativeRenderingProfile = NormativeRenderingProfile.GB_T_1_1_2020
    ) -> RoundTripReport:
        # Step 1: Canonical → SSIR (Source Fidelity)
        ssir = extractor.extract(canonical)

        # Step 2: SSIR → Render.md (Normative Rendering)
        render_md = renderer.render(ssir, profile=profile)

        # Step 3: Render.md → Verify (Re-extraction)
        verify = extractor.extract(render_md)

        # Step 4: Compare SSIR ≈ Verify (SSIR Equivalence — 四层比较)
        comparator = SSIRComparator()
        equivalence = comparator.compare(ssir, verify)

        # Step 5: Rendering Fidelity Test (独立)
        fidelity = self._test_rendering_fidelity(ssir, renderer, extractor)

        # Step 6: Generate Report
        return RoundTripReport(
            documentId=ssir.id,
            ssirId=ssir.id,
            renderMdId=render_md.id if hasattr(render_md, 'id') else None,
            verifyId=verify.id,
            renderingProfile=profile.value,
            equivalence=equivalence,
            renderingFidelity=fidelity,
            overallStatus=equivalence.overallStatus,
            extractionRunId=ssir.processingRuns[0].id if ssir.processingRuns else None
        )
```

#### 8.4 实现 `packages/roundtrip/report.py`：生成 JSON/HTML 报告

### Task 9: Storage & API Service (Day 17-19) ⚠️ **增强任务**

**产出**：Repository（PostgreSQL + 版本化）, ObjectStorage（MinIO）, FastAPI 完整实现

**AI 编码指令**：

#### 9.1 实现存储层

1. 实现 `packages/storage/postgres.py`：
   - 使用 SQLAlchemy 定义表（**含版本化模型**）
   - 表结构：
     - `ssir_document`（含 `document_version`、`schema_version`、`content_hash`、`parent_version`、`rendering_profile`、`status`）
     - `source_file`（含 `file_hash`、`mime_type`、`page_count`）
     - `processing_run`（含 `tool`、`tool_version`、`timestamp`、`output_summary`）
     - `quality_assessment`（含 `rendering_profile`、`dimensions` JSONB）
     - `metadata_index`（用于全文搜索）
   - 实现 CRUD 操作
   - 实现版本管理（`get_document(version=...)`）
   - 实现状态查询（`get_document_status`）

2. 实现 `packages/storage/object_storage.py`：
   - 使用 MinIO SDK
   - 上传/下载 PDF、图片、SSIR JSON
   - 实现 `upload`、`download`、`delete`、`exists`、`get_uri`

#### 9.2 实现 API 层

3. 实现 `apps/api/models/requests.py`：所有 API 请求 Pydantic 模型
   - `UploadDocumentRequest`
   - `ProcessDocumentRequest`
   - `RenderDocumentRequest`
   - `RoundtripRequest`

4. 实现 `apps/api/models/responses.py`：所有 API 响应 Pydantic 模型
   - `DocumentResponse`
   - `DocumentListResponse`
   - `StatusResponse`
   - `SSIRResponse`
   - `QualityResponse`
   - `RoundtripResponse`
   - `ErrorResponse`

5. 实现 `apps/api/routes/documents.py`：
   - `POST /documents` — 上传文档
   - `GET /documents` — 获取文档列表（支持分页、筛选、搜索）
   - `GET /documents/{id}` — 获取文档详情
   - `DELETE /documents/{id}` — 删除文档

6. 实现 `apps/api/routes/processing.py`：
   - `POST /documents/{id}/process` — 启动 SSIR 提取（触发 Celery 任务）
   - `GET /documents/{id}/status` — 获取处理状态
   - `POST /documents/{id}/cancel` — 取消处理

7. 实现 `apps/api/routes/rendering.py`：
   - `POST /documents/{id}/render` — 渲染传统文档（触发 Celery 任务）
   - `GET /documents/{id}/render/status` — 获取渲染状态

8. 实现 `apps/api/routes/roundtrip.py`：
   - `POST /documents/{id}/roundtrip` — 执行往返测试（触发 Celery 任务）
   - `GET /documents/{id}/roundtrip/result` — 获取往返测试结果

9. 实现 `apps/api/routes/quality.py`：
   - `GET /documents/{id}/quality` — 获取质量报告

10. 实现 `apps/api/routes/health.py`：
    - `GET /health` — 健康检查
    - `GET /ready` — 就绪检查

11. 实现 `apps/api/dependencies/storage.py`：
    - 依赖注入：`get_repository()`、`get_object_storage()`、`get_services()`

12. 实现 `apps/api/main.py`：
    - FastAPI 应用初始化
    - 注册路由
    - 配置 CORS
    - 配置异常处理器
    - 配置 OpenAPI 文档

13. **错误处理**：
    - 所有 API 必须返回符合 API Contract 的错误响应格式
    - 实现全局异常处理器
    - 错误码与 API Contract v0.1 保持一致

14. **异步任务集成**：
    - `POST /documents/{id}/process` → 触发 Celery 任务 `process_extraction`
    - `POST /documents/{id}/render` → 触发 Celery 任务 `render_document`
    - `POST /documents/{id}/roundtrip` → 触发 Celery 任务 `verify_roundtrip`
    - 返回 202 Accepted + task_id

### Task 10: API Integration Testing (Day 19-20) 🆕

**产出**：API 集成测试

**AI 编码指令**：

1. 实现 `tests/api/test_documents.py`：
   - 测试 `POST /documents`（上传 PDF、DOCX、无效文件）
   - 测试 `GET /documents`（分页、筛选、搜索）
   - 测试 `GET /documents/{id}`（存在、不存在）
   - 测试 `DELETE /documents/{id}`（正常删除、强制删除）

2. 实现 `tests/api/test_processing.py`：
   - 测试 `POST /documents/{id}/process`（启动处理、重复处理）
   - 测试 `GET /documents/{id}/status`（状态查询）
   - 测试 `POST /documents/{id}/cancel`（取消处理）

3. 实现 `tests/api/test_rendering.py`：
   - 测试 `POST /documents/{id}/render`（DOCX、PDF、HTML）
   - 测试 `GET /documents/{id}/render/status`

4. 实现 `tests/api/test_roundtrip.py`：
   - 测试 `POST /documents/{id}/roundtrip`（启动测试）
   - 测试 `GET /documents/{id}/roundtrip/result`（获取结果）

5. 实现 `tests/api/test_health.py`：
   - 测试 `GET /health`
   - 测试 `GET /ready`

6. 实现 `tests/api/test_error_handling.py`：
   - 测试错误响应格式
   - 测试错误码

### Task 11: Testing（贯穿所有 Sprint）

**AI 编码指令**：

1. 为每个模块编写单元测试，覆盖所有核心功能
2. 编写集成测试（模块间接口）
3. 实现 Golden Test 框架（`tests/golden/test_golden.py`）
4. 实现 Round-trip Test 框架（`tests/roundtrip/test_roundtrip.py`）
5. 实现 Critical Loss 检测测试
6. 实现 Normative Rendering 测试（含 ALLOWED_NORMALIZATIONS 和 FORBIDDEN_CHANGES）
7. 确保测试覆盖率 ≥ 85%


## 7. Non-Negotiable Implementation Rules

AI Coding Agent **必须严格遵守**以下规则：

### Rule 1: SSIR 源保真优先（Data Model v0.4 §7.2）

- 所有原始文本必须在 SSIR 中有对应位置
- `textContent`、`rawText`、`rawTarget` 必须保存原文
- **绝不允许**改写、摘要、润色原始内容
- **SSIR 是源文档事实和语义的保存层**
- `渲染文档` 是基于 SSIR 生成的规范化表示，允许依据适用的标准起草规则进行：
  - 格式规范化
  - 标点规范化
  - 编号规范化
  - 排版规范化
  - 明确允许的表达规范化（`ALLOWED_NORMALIZATIONS`）
- **但不得改变 SSIR 所表达的规范性语义**（`FORBIDDEN_CHANGES`）

### Rule 2: 永不丢弃

- 无法识别的内容 → `UnknownContent`
- 无法解析的公式 → `rawText` 保留
- 无法解析的表格 → 保存原始内容到 UnknownContent
- **UnknownContent 必须保留 `rawContent` 和 `SourceAnchor`**
- **验收标准**：所有源内容必须可追踪到 SSIR；无法识别的内容必须进入 UnknownContent，不得静默丢弃
- **不是**要求 `UnknownContent` 为空

### Rule 3: 规则优先于 LLM

- 章节编号解析 → 确定性规则
- 元数据提取 → 正则表达式 + 规则
- 阅读顺序 → bbox 算法
- LLM **仅允许**用于：语义分类（SemanticType）、实体识别（Entity）、关系识别（Relation）— 且这些是 Level 4 enrichment，**不能阻塞 Level 2/3**

### Rule 4: 溯源完整性

- 每个 `StructuralNode`、`ContentElement`、`Table`、`Figure`、`Formula` 必须有 `SourceAnchor`
- `SourceAnchor` 必须包含 `pdfPageIndex`
- `TextSpan` 必须关联 `CanonicalText`

### Rule 5: 正交分离

- **不混淆**：`StructuralNode`（结构）vs `ContentElement`（内容）vs `semanticTypes`（语义）
- `StructuralNode` 不包含 `paragraph`、`list` 等内容类型
- `ContentElement` 不包含结构层级信息

### Rule 6: 引擎可替换性

- MinerU 只是适配器之一
- 未来可替换为 Docling、GROBID 等
- Extraction IR 作为解耦层，**禁止直接依赖 MinerU 数据结构**

### Rule 7: Round-trip 验证独立性（Data Model v0.4 §7.8）

- `RoundTripVerifier` 验证 `SSIR ≈ Verify`（Round-trip Equivalence — 四层比较）
- `RenderingFidelityTest` 独立验证 `SSIR → DOCX/PDF → SSIR'`（Rendering Fidelity）
- `CriticalLossChecker` 独立验证 Data Model v0.4 §7.3 语义保护边界（12 项）
- 三者不可混淆

### Rule 8: Normative Rendering 边界（Data Model v0.4 §7.3）

- 允许的规范化：`ALLOWED_NORMALIZATIONS`
- **绝对禁止**的变化：`FORBIDDEN_CHANGES`
- Rendering Engine **不得**改变规范性语义
- `QualityAssessment.renderingProfile` 必须正确填充

### Rule 9: API Contract 一致性（新增）

- 所有 API 端点必须遵循 API Contract & Interface Specification v0.1
- 请求/响应格式必须与 Contract 一致
- 错误码必须与 Contract 一致
- 所有异步操作必须返回 202 Accepted
- 所有接口必须实现抽象接口定义


## 8. Acceptance Criteria (Phase 1)

| Gate | 名称 | 要求 | 对应文档 |
|------|------|------|----------|
| **G1** | Schema Gate | 100% required schema tests PASS（含 v0.3 新字段） | JSON Schema v0.3 |
| **G2** | Extraction Gate | Core Golden Dataset PASS | Golden Dataset v0.1 |
| **G3** | Structural Gate | 100% critical structure preserved | Data Model v0.4 §7.6 |
| **G4** | Content Gate | ≥ 99% content preserved（归一化后） | Data Model v0.4 §7.6 |
| **G5** | Critical Gate | **0 critical information loss**（12 项检查全通过） | Data Model v0.4 §7.3 |
| **G6** | Normative Rendering Gate | ALLOWED_NORMALIZATIONS 正确应用，FORBIDDEN_CHANGES 0 违规 | Data Model v0.4 §7.3 |
| **G7** | Round-trip Gate | All P0 Round-trip PASS（四层比较全通过） | Data Model v0.4 §7.5 |
| **G8** | Regression Gate | 0 regression in frozen Golden Dataset | Golden Dataset v0.1 |
| **G9** | API Conformance Gate | **100% API Contract 端点实现，100% 错误码覆盖** | API Contract v0.1 |

**详细指标**：

| 指标 | 目标值 | 说明 | 依据 |
|------|--------|------|------|
| Identity | 100% | 标准号、标题、日期等 | Data Model v0.4 §7.6 STRICT |
| Structure | 100% | 章节/条款/项完整 | Data Model v0.4 §7.6 STRICT |
| Normative Content | 100% | 规范性要求不丢失 | Data Model v0.4 §7.3 |
| Table Structural Integrity | 100% | 行/列/合并单元格 | Data Model v0.4 §7.6 STRICT |
| Formula Preservation | 100% | rawText 非空 | Data Model v0.4 §7.6 STRICT |
| Reference Preservation | 100% | rawTarget 保留 | Data Model v0.4 §7.6 STRICT |
| Informative Text | ≥ 98% | 资料性内容 | Data Model v0.4 §7.6 NORMALIZED |
| Critical Information Loss | **0** | 无关键信息丢失 | Data Model v0.4 §7.3 |
| Rendering Profile | 正确填充 | QualityAssessment.renderingProfile | JSON Schema v0.3 |
| API Endpoints | 100% | 所有 Contract 端点实现 | API Contract v0.1 |
| API Error Codes | 100% | 所有错误码正确实现 | API Contract v0.1 |
| API Response Format | 100% | 统一响应格式 | API Contract v0.1 |


## 9. First Code to Generate

AI Coding Agent 现在可以开始编码。**第一个任务**：生成以下文件的完整实现：

1. `packages/core/enums.py` — 所有枚举定义（**含所有新增枚举**）
2. `packages/core/ssir.py` — 所有 SSIR Pydantic 模型（**Data Model v0.4**，使用 Pydantic v2 API）
3. `packages/core/equivalence.py` — **SSIR Equivalence Model（四层）**
4. `packages/core/roundtrip.py` — **RoundTripReport**
5. `packages/core/transformation.py` — **ALLOWED_NORMALIZATIONS + FORBIDDEN_CHANGES**
6. `packages/core/extraction_ir.py` — Extraction IR 模型
7. `packages/core/rendering_ir.py` — Rendering IR 模型
8. `packages/core/interface.py` — **所有抽象接口定义**

确保所有模型通过 `mypy --strict` 检查。

**生成后**，将进入 Sprint 1：Ingestion Service 实现。


## 10. Version History

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 0.1 | 2026-08-15 | 初始版本 |
| 0.2 | 2026-08-15 | 重新定义 Round-trip 为 `源文档 → SSIR → 渲染文档 → Verify`，验证 `SSIR ≈ Verify`；新增 SSIR Equivalence Model；新增 RoundTripReport；新增四层比较；新增 Critical Information Loss；修改 Rule 1/2；取消单一 matchRate；Pydantic v2 API 规范化 |
| 0.3 | 2026-08-15 | 与 Data Model v0.4 和 JSON Schema v0.3 对齐；`ssirVersion` 支持 `"0.4"`；新增 `NormativeRenderingProfile` 枚举；`QualityAssessment` 增加 `renderingProfile`；新增 `transformation.py`；更新 Task 8；更新 Rule 7/8；更新 Acceptance Criteria |
| 0.4 | 2026-08-15 | 恢复 v0.1 的详细 Task 实现指令；恢复 API Contract 完整 OpenAPI 定义；恢复目录结构文件用途注释；恢复枚举完整 Python 代码实现；恢复验收标准具体数值和 Dataset 分类 |
| 0.5 | 2026-08-16 | 新增 §5 内部接口契约；增强 Task 9（Storage & API）增加完整 API 实现指令；新增 Task 10（API Integration Testing）；更新目录结构增加 API 模型文件；更新 §1.4 管线图增加 API 层；更新 Acceptance Criteria 增加 API Conformance Gate（G9）；更新前置文档列表 |
| 0.6 | 2026-08-17 | 更新 M1 边界为 CSM Markdown Round-trip：原始 Markdown 先经基础纠错冻结为 `Canonical`，再执行 `Canonical → SSIR → Render.md → Verify`、四层比较和关键损失检查；DOCX/PDF 渲染与视觉保真仍属于 M2 |
