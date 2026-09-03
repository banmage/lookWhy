# leleby Standard Ontology Specification v1.5

**文档版本：** v1.5 — Document Semantic Alignment Release（文档语义对齐版）

**文档类型：** 模块规范（Module Ontology Specification）

**文档状态：** ✅ **核心模型冻结（Core Model Frozen）** — 核心类与属性已冻结，允许在指定扩展点进行模块内部扩展。

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.2

**依赖模块：**
- `llb` Foundation Vocabulary Specification v1.0
- `lbo-core` Core Ontology Specification v1.2（提供 `ObligationLevel`、`SemanticTarget`）
- `lbo-req` Requirement Ontology Specification v1.2（提供 `Requirement` 和 `SemanticTarget`）
- `lbo-spec` Specification Framework Ontology Specification v1.2
- `lcon` Constraint Ontology Specification v1.2（通过 Requirement 间接引用）

**命名空间：** `https://ontology.leleby.org/standard/`

**推荐前缀：** `lstd`

**目标受众：** 本体架构师、标准工程师、合规工程师、AI Agent 开发者


## 目录

1. 引言
   1.1 目的
   1.2 核心定位
   1.3 与其他模块的关系
   1.4 与 Normative Semantic Package 的关系
   1.5 设计原则
   1.6 v1.5 修订说明（新增）
2. 命名空间声明
3. 核心概念模型
   3.1 标准体系顶层模型（v1.5 更新）
   3.2 标准内容单元模型（v1.5 新增）
   3.3 标准条款与要求绑定模型（v1.5 增强）
   3.4 标准关系模型（v1.5 增强）
   3.5 完整推理链路（v1.5 增强）
   3.6 标准语义完整性模型（v1.5 增强）
4. 类规范
   4.1 Standard
   4.2 StandardFamily
   4.3 StandardEdition（v1.5 增强）
   4.4 StandardOrganization
   4.5 StandardContentUnit（v1.5 新增）
   4.6 StandardClause（v1.5 调整）
   4.7 TableUnit（v1.5 新增）
   4.8 FigureUnit（v1.5 新增）
   4.9 DefinitionUnit（v1.5 新增）
   4.10 NoteUnit（v1.5 新增）
   4.11 ExampleUnit（v1.5 新增）
   4.12 AnnexUnit（v1.5 新增）
   4.13 NormativeStatement（v1.5 增强）
   4.14 RequirementBinding（v1.5 增强）
   4.15 StandardRelationship
   4.16 AdoptionRelationship
   4.17 EquivalenceRelationship
   4.18 DeviationRelationship
   4.19 HarmonizationRelationship
   4.20 ReplacementRelationship
   4.21 ReferencingRelationship（v1.5 增强）
   4.22 ComplementaryRelationship
   4.23 Jurisdiction
   4.24 StandardScope
   4.25 StandardStatus
   4.26 StandardSemanticStatus（v1.5 增强）
5. 对象属性
   5.1 标准结构与组成属性（v1.5 更新）
   5.2 内容单元属性（v1.5 新增）
   5.3 条款与要求绑定属性（v1.5 增强）
   5.4 标准关系属性（v1.5 增强）
   5.5 与外部模块的连接属性
   5.6 语义完整性属性（v1.5 增强）
6. 数据属性
7. 推理规则
   7.1 要求继承规则
   7.2 要求绑定传播规则
   7.3 版本替代规则
   7.4 采纳传播规则
   7.5 符合性推理规则
   7.6 引用传播规则（v1.5 增强）
   7.7 内容单元到语义层的推理规则（v1.5 新增）
8. 与 Normative Semantic Package 的接口（v1.5 增强）
9. 与 Specification Framework Ontology 的接口
10. 与 Requirement Ontology 的接口（v1.5 增强）
11. 与 Constraint Ontology 的接口
12. 与 GB/T 46917 的对齐（v1.5 新增）
13. 外部标准对齐
14. SHACL 验证约束（v1.5 增强）
15. 完整示例（v1.5 更新）
16. 冻结声明
17. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Standard Ontology 是 leleby 语义基础设施中**规范知识体系**的核心模块。它定义了工业标准作为规范知识体系时所需要的概念、关系和语义模型，使标准能够被 AI 系统理解、推理和应用于合规验证。

**核心目标：**
- 定义“标准是什么”的语义模型（标准体系、版本、内容单元、要求）
- 支持 Standard → ContentUnit → Requirement → Constraint → Specification → Measurement → Compliance 完整推理链
- 支持标准的版本管理和生命周期表达
- 支持标准之间的采纳、等效、偏差、替代、引用、互补等关系
- **支持标准文档内容单元的细粒度语义化表达（v1.5 新增）**
- 为 Normative Semantic Package 提供概念层基础

### 1.2 核心定位

> **Standard Ontology 定义“规范体系要求什么”，而非“具体标准文件如何封装”。**

| 模块 | 回答的问题 | 层级 |
|---|---|---|
| **Standard Ontology** | 规范体系要求什么？标准体系的结构是什么？ | 概念层（`lbo-standard`） |
| **Requirement Ontology** | 要求的语义结构是什么？要求约束什么目标要素？ | 概念层（`lbo-req`） |
| **Constraint Ontology** | 约束如何表达和评估？ | 概念层（`lcon`） |
| **Specification Framework Ontology** | 规格如何表达？ | 框架层（`lbo-spec`） |
| **Normative Semantic Package** | 某个具体标准文件如何语义化封装？ | 实例封装层（`lbs`） |

### 1.3 与其他模块的关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Standard Ontology 在架构中的位置                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Core Ontology（lbo-core v1.2）                  │   │
│  │              Organization / Product / Capability / Process          │   │
│  │              ObligationLevel（强制程度）                            │   │
│  │              SemanticTarget（语义目标——v1.2 新增）                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Standard Ontology（lstd）—— 本模块              │   │
│  │              Standard / StandardEdition / StandardContentUnit       │   │
│  │              StandardClause / TableUnit / FigureUnit / ...          │   │
│  │              RequirementBinding（引用 lbo-req:Requirement）         │   │
│  │              StandardRelationship（含引用/互补）                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                    ┌───────────────┼───────────────┐                    │
│                    │               │               │                    │
│                    ▼               ▼               ▼                    │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │
│  │  Requirement        │  │  Constraint     │  │  Normative          │   │
│  │  Ontology           │  │  Ontology       │  │  Semantic Package   │   │
│  │  （要求语义）        │  │  （约束评估）    │  │  （实例封装）       │   │
│  └─────────────────────┘  └─────────────────┘  └─────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Specification Framework Ontology                 │   │
│  │                    （规格表达）                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Measurement Ontology + Compliance Reasoning     │   │
│  │                    （测量事实 + 合规判断）                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.4 与 Normative Semantic Package 的关系

**Standard Ontology 与 Normative Semantic Package 是上下游关系。**

| 维度 | Standard Ontology | Normative Semantic Package |
|---|---|---|
| **职责** | 定义“标准是什么”的概念模型 | 封装“某个具体标准”的语义实例 |
| **层级** | 概念层（Ontology） | 实例封装层（Semantic Package） |
| **内容** | Standard、Clause、ContentUnit、RequirementBinding 的类定义 | IEC 60034-1:2025 的具体实例 |
| **稳定性** | 长期稳定 | 版本化演进 |

**关系链路：**

```
Standard Ontology（概念定义）
        │
        │  被实例化
        ▼
Normative Semantic Package（具体标准封装）
        │
        │  包含
        ▼
Requirement Instances（要求实例——引用 lbo-req:Requirement）
        │
        │  被引用
        ▼
Specification Framework（规格表达）
```

### 1.5 设计原则

**原则一：标准是知识体系，不是文件**
标准首先是概念体系（Standard），其次才是文件（Document）。标准编号与具体版本分离。

**原则二：内容单元是结构基础，要求是语义单元（v1.5 增强）**
标准的内容单元（Clause、Table、Figure、Definition、Note、Example、Annex）组织标准结构，要求（Requirement）表达规范内容。两者通过 `RequirementBinding` 连接。

**原则三：要求不重新定义**
标准中的要求直接引用 `lbo-req:Requirement`，不创建 `StandardRequirement` 子类。强制程度（ObligationLevel）来自 `lbo-core:ObligationLevel`。

**原则四：标准关系是一等公民**
标准之间的关系（采纳、等效、偏差、替代、引用、互补）需要显式建模。

**原则五：与 Normative Semantic Package 职责分离**
Standard Ontology 不定义包的封装格式。Package Manifest、文件结构等属于 Normative Semantic Package。

**原则六：可计算适用范围**
标准的适用范围（Scope）应支持机器可计算的匹配，而非仅人类可读文本。

**原则七：要求约束目标要素**
要求（Requirement）的直接约束目标是标准化对象主体（Subject）所拥有的语义要素（Semantic Target），包括特性、功能、接口、结构关系、材料属性或过程要素等，而非主体本身。主体通过要素的 `hostedBy` 关系间接关联。

**原则八：引用语义显式化**
标准之间的引用关系必须显式区分引用类型（规范性引用、信息性引用、方法引用、定义引用等），以支持正确的语义传播和推理。同时需要显式标记引用依赖的解析状态（v1.5 新增）。

**原则九：语义完整性可度量**
标准语义包的完整性状态应被显式标记，特别是当标准引用的外部规范未被建模时，应能记录和报告这种不完整状态。

**原则十：文档层与语义层分离（v1.5 新增）**
标准文档的内容单元（条款、表格、图、定义、注、示例、附录）属于文档层，表达规范的结构组织；要求、约束、语义目标属于语义层，表达规范的知识内容。两者通过绑定关系连接，职责清晰、互不混淆。

### 1.6 v1.5 修订说明（新增）

v1.5 是 v1.4 的文档语义增强版本，基于对 GB/T 46917.1-2026《标准内容语义化表达通用要求》和标准 PDF 自动抽取实际需求的分析，重点解决了以下问题：

1. **标准内容单元泛化**：新增 `StandardContentUnit` 抽象类，将 `StandardClause` 降为子类，新增 `TableUnit`、`FigureUnit`、`DefinitionUnit`、`NoteUnit`、`ExampleUnit`、`AnnexUnit` 等，对齐 GB/T 46917 的“标准内容语义化表达单元”概念。
2. **规范性陈述与要求的分层**：明确 `NormativeStatement` 是标准文本中的规范性表达（文档层），`Requirement` 是语义化后的规范要求实体（语义层），两者通过 `RequirementBinding` 连接。
3. **引用依赖状态管理**：在 `ReferencingRelationship` 中新增 `hasDependencyStatus`，表达引用关系是否已解析、部分解析或未解析。
4. **语义完整性状态扩展**：扩展 `StandardSemanticStatus`，增加 `PartialSemanticModel`、`MissingMeasurementModel`、`MissingConstraintModel`、`PendingReview` 等细粒度状态。
5. **增强 SHACL 验证约束**：增加对 `RequirementBinding.referencesRequirement`、`Requirement.hasSemanticTarget`、`NormativeStatement.hasObligationLevel` 的验证。
6. **明确语义包多版本关系**：在 `hasNormativePackage` 中增加版本管理说明。


## 2. 命名空间声明

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix llb: <https://ontology.leleby.org/foundation/> .
@prefix lbo-core: <https://ontology.leleby.org/core/> .
@prefix lbo-req: <https://ontology.leleby.org/requirement/> .
@prefix lbo-spec: <https://ontology.leleby.org/specification/> .
@prefix lcon: <https://ontology.leleby.org/constraint/> .
@prefix lstd: <https://ontology.leleby.org/standard/> .

<https://ontology.leleby.org/standard/>
    rdf:type owl:Ontology ;
    owl:versionInfo "1.5" ;
    owl:imports <https://ontology.leleby.org/foundation/> ;
    owl:imports <https://ontology.leleby.org/core/> ;
    owl:imports <https://ontology.leleby.org/requirement/> ;
    rdfs:label "leleby Standard Ontology" ;
    rdfs:comment "leleby 标准知识体系语义模型，定义标准、内容单元、条款、要求绑定及其关系的概念模型" .
```


## 3. 核心概念模型

### 3.1 标准体系顶层模型（v1.5 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    标准体系顶层模型（v1.5）                                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Standard（标准体系）                            │   │
│  │  - standardId: "IEC 60034"                                        │   │
│  │  - standardTitle: "Rotating electrical machines"                  │   │
│  │  - belongsToFamily → StandardFamily: "IEC 60000 Series"          │   │
│  │  - hasScope → StandardScope（结构化适用范围）                     │   │
│  │  - hasSemanticStatus → StandardSemanticStatus（v1.5 增强）        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │  hasEdition                           │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    StandardEdition（标准版本）                     │   │
│  │  - edition: "2025"                                                │   │
│  │  - effectiveDate: "2026-02-01"                                    │   │
│  │  - status: "published"                                            │   │
│  │  - supersedes → StandardEdition: "2017"                          │   │
│  │  - hasSemanticPackageVersion → 多个语义包版本（v1.5 增强）         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │  containsContentUnit                  │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    StandardContentUnit（内容单元——v1.5 新增）      │   │
│  │  标准文档中可独立识别的内容单元                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│    ┌───────────────┬───────────────┼───────────────┬───────────────┐       │
│    │               │               │               │               │       │
│    ▼               ▼               ▼               ▼               ▼       │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │ Clauses │  │ Tables  │  │ Figures │  │Defini-  │  │ Annexes │         │
│  │ （条款） │  │ （表格） │  │ （图）   │  │tions    │  │ （附录） │         │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RequirementBinding（要求绑定）                  │   │
│  │  - referencesRequirement → lbo-req:Requirement                   │   │
│  │  - hasObligationLevel → lbo-core:ObligationLevel                 │   │
│  │  - bindingType → lstd:BindingType（扩展）                        │   │
│  │  - derivedFromNormativeSource → NormativeStatement / ContentUnit  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 标准内容单元模型（v1.5 新增）

GB/T 46917.1-2026 将标准内容语义化表达单元分为**通用语义化表达单元**和**专用语义化表达单元**。标准内容不仅仅是条款，还包括表格、图、定义、注、示例、附录等多种内容类型。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    标准内容单元模型（v1.5 新增）                            │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    StandardContentUnit（内容单元）                  │   │
│  │  抽象基类：标准文档中可独立识别的、具有结构意义的内容单元           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│    ┌───────────┬───────────┬───────┴───────┬───────────┬───────────┐      │
│    │           │           │               │           │           │      │
│    ▼           ▼           ▼               ▼           ▼           ▼      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐│
│  │Standard │ │ Table   │ │ Figure  │ │Defini-  │ │ Note    │ │ Example ││
│  │Clause   │ │ Unit    │ │ Unit    │ │tion Unit│ │ Unit    │ │ Unit    ││
│  │（条款）  │ │（表格）  │ │（图）    │ │（定义）  │ │（注）    │ │（示例）  ││
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘│
│                                    │                                        │
│                                    │  nestedContent                         │
│                                    ▼                                        │
│                    ┌─────────────────────────────┐                        │
│                    │  AnnexUnit（附录）           │                        │
│                    │  可包含条款、表格、图、定义等 │                        │
│                    └─────────────────────────────┘                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 标准条款与要求绑定模型（v1.5 增强）

```
StandardEdition
    │
    └── containsContentUnit → StandardContentUnit（1..*）
            │
            ├── StandardClause（条款）
            │       ├── hasParentClause → StandardClause（0..1）
            │       ├── hasChildClause → StandardClause（0..*）
            │       └── contains → NormativeStatement（0..*）
            │
            ├── TableUnit（表格）
            │       ├── tableNumber → xsd:string
            │       ├── tableTitle → xsd:string
            │       └── tableContent → xsd:string（结构化）
            │
            ├── FigureUnit（图）
            │       ├── figureNumber → xsd:string
            │       ├── figureTitle → xsd:string
            │       └── figureContent → xsd:string
            │
            ├── DefinitionUnit（定义）
            │       ├── term → xsd:string
            │       └── definition → xsd:string
            │
            ├── NoteUnit（注）
            │       └── noteText → xsd:string
            │
            ├── ExampleUnit（示例）
            │       └── exampleText → xsd:string
            │
            └── AnnexUnit（附录）
                    ├── annexNumber → xsd:string
                    ├── annexTitle → xsd:string
                    └── containsContentUnit → StandardContentUnit（0..*）
            │
            └── definesBinding / isSourceFor → RequirementBinding（0..*）
                    │
                    ├── referencesRequirement → lbo-req:Requirement（1）
                    │       │
                    │       └── hasSemanticTarget → lbo-req:SemanticTarget（1..*）
                    │
                    ├── hasObligationLevel → lbo-core:ObligationLevel（1）
                    │
                    ├── bindingType → lstd:BindingType
                    │
                    └── derivedFromNormativeSource → lstd:NormativeStatement / lstd:StandardContentUnit（0..*）
```

### 3.4 标准关系模型（v1.5 增强）

```
Standard
    │
    └── hasRelationship → StandardRelationship（0..*）
            │
            ├── AdoptionRelationship（采纳）
            ├── EquivalenceRelationship（等效）
            ├── DeviationRelationship（偏差）
            ├── HarmonizationRelationship（协调）
            ├── ReplacementRelationship（替代）
            ├── ReferencingRelationship（引用——v1.5 增强）
            │       │
            │       ├── hasReferenceType → lstd:ReferenceType
            │       └── hasDependencyStatus → lstd:DependencyStatus（v1.5 新增）
            │
            └── ComplementaryRelationship（互补）
```

### 3.5 完整推理链路（v1.5 增强）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Standard Ontology 完整推理链路（v1.5）                   │
│                                                                             │
│  Standard（标准体系）                                                       │
│       │                                                                     │
│       │  lstd:hasEdition                                                    │
│       ▼                                                                     │
│  StandardEdition（标准版本）                                                │
│       │                                                                     │
│       │  lstd:containsContentUnit                                           │
│       ▼                                                                     │
│  StandardContentUnit（内容单元——v1.5 新增）                                 │
│       │                                                                     │
│       │  lstd:contains → lstd:NormativeStatement                           │
│       ▼                                                                     │
│  NormativeStatement（规范性陈述——文档层）                                   │
│       │                                                                     │
│       │  lstd:derivesBinding / lstd:isSourceFor                            │
│       ▼                                                                     │
│  RequirementBinding（要求绑定）                                             │
│       │                                                                     │
│       │  lstd:referencesRequirement                                         │
│       ▼                                                                     │
│  lbo-req:Requirement（要求——语义层）                                        │
│       │                                                                     │
│       │  lbo-req:hasSemanticTarget                                          │
│       ▼                                                                     │
│  lbo-req:SemanticTarget（语义目标）                                         │
│       │                                                                     │
│       │  lbo-req:hostedBy                                                   │
│       ▼                                                                     │
│  lbo-core:Product / Part / Process / Software / Interface（标准化对象主体） │
│       │                                                                     │
│       │  lbo-req:hasConstraint                                              │
│       ▼                                                                     │
│  lcon:Constraint（约束）                                                    │
│       │                                                                     │
│       │  被 Specification 引用                                              │
│       ▼                                                                     │
│  lbo-spec:Specification（规格）                                             │
│       │                                                                     │
│       │  被 Measurement 验证                                                │
│       ▼                                                                     │
│  lbo-meas:MeasurementResult（测量结果）                                     │
│       │                                                                     │
│       │  被 ComplianceAssessment 评估                                       │
│       ▼                                                                     │
│  lbo-core:ComplianceAssessment（合规评估）                                  │
│                                                                             │
│  完整推理链：                                                               │
│  标准 → 版本 → 内容单元（文档层）→ 规范性陈述 → 要求绑定 →                  │
│  要求（语义层）→ 语义目标 → 宿主对象 → 约束 → 规格 → 测量 → 合规            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.6 标准语义完整性模型（v1.5 增强）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    标准语义完整性模型（v1.5 增强）                          │
│                                                                             │
│  在标准语义化过程中，一个标准可能引用其他标准或规范，也可能包含需要        │
│  进一步语义化但尚未完成的内容。此模型用于标记和追溯这种状态。              │
│                                                                             │
│  Standard / StandardEdition                                                 │
│       │                                                                     │
│       │  lstd:hasSemanticStatus                                             │
│       ▼                                                                     │
│  StandardSemanticStatus（语义完整性状态——v1.5 扩展）                        │
│       │                                                                     │
│       ├── lstd:Complete（完整）                                             │
│       │   所有引用和依赖均已建模。                                          │
│       │                                                                     │
│       ├── lstd:IncompleteExternalDependency（外部依赖不完整）               │
│       │   引用的外部标准或规范未被建模。                                    │
│       │                                                                     │
│       ├── lstd:PartialSemanticModel（部分语义模型——v1.5 新增）             │
│       │   标准核心内容已建模，但部分内容（如注、示例、附录）未完成。        │
│       │                                                                     │
│       ├── lstd:MissingMeasurementModel（缺少测量模型——v1.5 新增）          │
│       │   标准包含测量/试验方法要求，但未关联 Measurement Ontology。         │
│       │                                                                     │
│       ├── lstd:MissingConstraintModel（缺少约束模型——v1.5 新增）           │
│       │   标准包含技术指标，但未转换为 Constraint。                          │
│       │                                                                     │
│       ├── lstd:PendingReview（待审核——v1.5 新增）                          │
│       │   语义化已完成，但尚未经过人工审核确认。                            │
│       │                                                                     │
│       └── lstd:UnresolvedReference（未解析引用）                            │
│            标准包含引用，但引用目标无法解析或未知。                          │
│                                                                             │
│  lstd:hasUnresolvedDependency（未解析依赖）                                 │
│       │                                                                     │
│       ▼                                                                     │
│  lstd:UnresolvedDependency                                                  │
│       │                                                                     │
│       ├── lstd:targetReferenceId: "IEC 60034-1:2025"                       │
│       ├── lstd:referencingClause: "5.3"                                    │
│       └── lstd:unresolvedReason: "Standard not modeled"                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 4. 类规范

### 4.1 Standard

```turtle
lstd:Standard
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "Standard" ;
    rdfs:comment "标准的抽象标识，代表一个标准体系（如 IEC 60034），不包含具体版本" .
```

**属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:standardId` | 标准编号（如 "IEC 60034"） | 1 |
| `lstd:standardTitle` | 标准名称 | 1 |
| `lstd:standardAbbreviation` | 标准缩写 | 0..1 |
| `lstd:standardDescription` | 标准描述 | 0..1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:issuedBy` | lstd:Standard | lstd:StandardOrganization | 发布机构 | 1 |
| `lstd:hasEdition` | lstd:Standard | lstd:StandardEdition | 拥有的版本 | 1..* |
| `lstd:hasRelationship` | lstd:Standard | lstd:StandardRelationship | 标准间关系 | 0..* |
| `lstd:hasJurisdiction` | lstd:Standard | lstd:Jurisdiction | 适用司法管辖区 | 0..1 |
| `lstd:belongsToFamily` | lstd:Standard | lstd:StandardFamily | 所属标准族 | 0..1 |
| `lstd:hasScope` | lstd:Standard | lstd:StandardScope | 适用范围 | 0..1 |
| `lstd:hasSemanticStatus` | lstd:Standard | lstd:StandardSemanticStatus | 语义完整性状态（v1.5 增强） | 0..1 |

### 4.2 StandardFamily

```turtle
lstd:StandardFamily
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "StandardFamily" ;
    rdfs:comment "标准族，如 IEC 60000 系列、ISO 9000 系列" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:familyId` | 族标识 | 1 |
| `lstd:familyName` | 族名称 | 1 |
| `lstd:familyDescription` | 族描述 | 0..1 |

### 4.3 StandardEdition（v1.5 增强）

```turtle
lstd:StandardEdition
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Document ;
    rdfs:label "StandardEdition" ;
    rdfs:comment "标准的具体版本，包含版本号、发布日期、实施日期等" .
```

**属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:edition` | 版本标识（如 "2025"） | 1 |
| `lstd:editionTitle` | 版本名称（如 "Edition 4.0"） | 0..1 |
| `lstd:approvalDate` | 批准日期 | 0..1 |
| `lstd:effectiveDate` | 实施日期 | 1 |
| `lstd:withdrawDate` | 废止日期 | 0..1 |
| `lstd:status` | 版本状态 | 1 |
| `lstd:officialFile` | 官方文件 URL | 0..1 |
| `lstd:pageCount` | 页数 | 0..1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:containsContentUnit` | lstd:StandardEdition | **`lstd:StandardContentUnit`** | **包含的内容单元（v1.5 新增，替代 containsClause）** | 1..* |
| `lstd:containsClause` | lstd:StandardEdition | lstd:StandardClause | 包含的条款（v1.5 保留，作为 containsContentUnit 的子属性，向后兼容） | 0..* |
| `lstd:supersedes` | lstd:StandardEdition | lstd:StandardEdition | 替代的旧版本 | 0..1 |
| `lstd:supersededBy` | lstd:StandardEdition | lstd:StandardEdition | 被新版本替代 | 0..1 |
| `lstd:revises` | lstd:StandardEdition | lstd:StandardEdition | 修订的旧版本 | 0..1 |
| `lstd:revisedFrom` | lstd:StandardEdition | lstd:StandardEdition | 被修订的版本 | 0..1 |
| `lstd:hasAdoption` | lstd:StandardEdition | lstd:AdoptionRelationship | 采纳关系 | 0..* |
| `lstd:hasSemanticStatus` | lstd:StandardEdition | lstd:StandardSemanticStatus | 语义完整性状态（v1.5 增强） | 0..1 |
| `lstd:hasSemanticPackageVersion` | lstd:StandardEdition | `lsp:SemanticPackage` | **语义包版本（v1.5 增强——支持多版本）** | 0..* |

### 4.4 StandardOrganization

```turtle
lstd:StandardOrganization
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Organization ;
    rdfs:label "StandardOrganization" ;
    rdfs:comment "标准发布机构，如 IEC、ISO、GB 等" .
```

### 4.5 StandardContentUnit（v1.5 新增）

```turtle
lstd:StandardContentUnit
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "StandardContentUnit" ;
    rdfs:comment "标准内容单元的抽象基类。代表标准文档中可独立识别的内容单元——如条款、表格、图、定义、注、示例、附录等。对齐 GB/T 46917.1-2026 中'标准内容语义化表达单元'的概念" .
```

**属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:contentUnitId` | 内容单元唯一标识符 | 0..1 |
| `lstd:contentUnitType` | 内容单元类型（clause/table/figure/definition/note/example/annex） | 1 |
| `lstd:contentUnitOrder` | 在文档中的顺序号 | 0..1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:hasParentUnit` | lstd:StandardContentUnit | lstd:StandardContentUnit | 父内容单元 | 0..1 |
| `lstd:hasChildUnit` | lstd:StandardContentUnit | lstd:StandardContentUnit | 子内容单元 | 0..* |
| `lstd:containsNormativeStatement` | lstd:StandardContentUnit | lstd:NormativeStatement | 包含的规范性陈述 | 0..* |
| `lstd:isSourceFor` | lstd:StandardContentUnit | lstd:RequirementBinding | 作为来源的要求绑定 | 0..* |
| `lstd:hasExtractionStatus` | lstd:StandardContentUnit | lstd:ExtractionStatus | 语义提取状态 | 0..1 |

### 4.6 StandardClause（v1.5 调整）

```turtle
lstd:StandardClause
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardContentUnit ;
    rdfs:label "StandardClause" ;
    rdfs:comment "标准的条款/章节，是标准内容的基本结构组织单元，同时作为要求的来源追溯节点" .
```

**属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:clauseNumber` | 条款编号（如 "5.6.3"） | 1 |
| `lstd:clauseTitle` | 条款标题 | 0..1 |
| `lstd:clauseText` | 条款原文 | 1 |
| `lstd:clauseType` | 条款类型 | 0..1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:hasParentClause` | lstd:StandardClause | lstd:StandardClause | 父条款（v1.5 保留，建议使用 hasParentUnit） | 0..1 |
| `lstd:hasChildClause` | lstd:StandardClause | lstd:StandardClause | 子条款（v1.5 保留，建议使用 hasChildUnit） | 0..* |
| `lstd:definesBinding` | lstd:StandardClause | lstd:RequirementBinding | 定义的要求绑定（来源方视角） | 0..* |
| `lstd:isSourceFor` | lstd:StandardClause | lstd:RequirementBinding | 作为来源的要求绑定（要求方视角） | 0..* |

### 4.7 TableUnit（v1.5 新增）

```turtle
lstd:TableUnit
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardContentUnit ;
    rdfs:label "TableUnit" ;
    rdfs:comment "标准文档中的表格内容单元" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:tableNumber` | 表格编号（如 "Table 8"） | 0..1 |
| `lstd:tableTitle` | 表格标题 | 0..1 |
| `lstd:tableContent` | 表格内容（结构化 JSON/XML 表示） | 1 |
| `lstd:tableColumnHeaders` | 列头 | 0..* |
| `lstd:tableRowHeaders` | 行头 | 0..* |

### 4.8 FigureUnit（v1.5 新增）

```turtle
lstd:FigureUnit
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardContentUnit ;
    rdfs:label "FigureUnit" ;
    rdfs:comment "标准文档中的图内容单元" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:figureNumber` | 图编号（如 "Figure 1"） | 0..1 |
| `lstd:figureTitle` | 图标题 | 0..1 |
| `lstd:figureCaption` | 图说明 | 0..1 |
| `lstd:figureContent` | 图内容（base64 编码或 URL） | 0..1 |
| `lstd:figureDescription` | 图的文字描述 | 0..1 |

### 4.9 DefinitionUnit（v1.5 新增）

```turtle
lstd:DefinitionUnit
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardContentUnit ;
    rdfs:label "DefinitionUnit" ;
    rdfs:comment "标准文档中的术语定义单元" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:term` | 术语 | 1 |
| `lstd:definition` | 定义文本 | 1 |
| `lstd:termSource` | 术语来源 | 0..1 |
| `lstd:termAbbreviation` | 缩略语 | 0..1 |

### 4.10 NoteUnit（v1.5 新增）

```turtle
lstd:NoteUnit
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardContentUnit ;
    rdfs:label "NoteUnit" ;
    rdfs:comment "标准文档中的注内容单元" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:noteNumber` | 注编号 | 0..1 |
| `lstd:noteText` | 注文本 | 1 |
| `lstd:noteType` | 注类型（一般注/警告注/特别注） | 0..1 |

### 4.11 ExampleUnit（v1.5 新增）

```turtle
lstd:ExampleUnit
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardContentUnit ;
    rdfs:label "ExampleUnit" ;
    rdfs:comment "标准文档中的示例单元" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:exampleNumber` | 示例编号 | 0..1 |
| `lstd:exampleText` | 示例文本 | 1 |

### 4.12 AnnexUnit（v1.5 新增）

```turtle
lstd:AnnexUnit
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardContentUnit ;
    rdfs:label "AnnexUnit" ;
    rdfs:comment "标准文档中的附录单元，可包含条款、表格、图等多种内容" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:annexNumber` | 附录编号 | 1 |
| `lstd:annexTitle` | 附录标题 | 1 |
| `lstd:annexType` | 附录类型（规范性/资料性） | 1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:containsContentUnit` | lstd:AnnexUnit | lstd:StandardContentUnit | 附录包含的内容单元 | 0..* |

### 4.13 NormativeStatement（v1.5 增强）

```turtle
lstd:NormativeStatement
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "NormativeStatement" ;
    rdfs:comment "标准文本中的规范性陈述（文档层）。表达标准原文中的规范性内容，如'shall'、'should'、'may'等引导的句子。与语义层的 Requirement 通过 RequirementBinding 连接" .
```

**属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:statementText` | 陈述文本（原文） | 1 |
| `lstd:statementType` | 陈述类型（shall/should/may/informative） | 1 |
| `lstd:hasObligationLevel` | **强制程度（v1.5 新增，映射到 Core）** | 0..1 |
| `lstd:statementPosition` | 在文档中的位置（条款号/段落号） | 0..1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:derivesBinding` | lstd:NormativeStatement | lstd:RequirementBinding | 产生的要求绑定 | 0..* |
| `lstd:isSourceFor` | lstd:NormativeStatement | lstd:RequirementBinding | 作为来源的要求绑定 | 0..* |

**语义分层说明（v1.5 新增）：**

| 层次 | 概念 | 说明 |
|---|---|---|
| **文档层** | `NormativeStatement` | 标准文本中的规范性表达（"电机效率不得低于90%"） |
| **绑定层** | `RequirementBinding` | 连接文档层与语义层 |
| **语义层** | `Requirement` | 语义化后的规范要求实体（Target: Efficiency, Constraint: ≥90%） |

### 4.14 RequirementBinding（v1.5 增强）

```turtle
lstd:RequirementBinding
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "RequirementBinding" ;
    rdfs:comment "标准条款/内容单元与要求之间的绑定关系。引用 lbo-req:Requirement 并记录来源和强制程度，不重新定义要求本身" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:referencesRequirement` | lstd:RequirementBinding | `lbo-req:Requirement` | 引用的要求定义 | 1 |
| `lstd:hasObligationLevel` | lstd:RequirementBinding | **`lbo-core:ObligationLevel`** | 强制程度（来自 Core Ontology） | 1 |
| `lstd:bindingType` | lstd:RequirementBinding | **`lstd:BindingType`** | 绑定类型 | 0..1 |
| `lstd:derivedFromClause` | lstd:RequirementBinding | `lstd:StandardClause` | 来源条款（0..*，v1.5 保留） | 0..* |
| `lstd:derivedFromContentUnit` | lstd:RequirementBinding | **`lstd:StandardContentUnit`** | **来源内容单元（v1.5 新增，支持从非条款内容单元派生）** | 0..* |
| `lstd:derivedFromNormativeSource` | lstd:RequirementBinding | **`lstd:NormativeStatement` / `lstd:StandardContentUnit`** | **来源规范性来源（v1.5 新增，统一入口）** | 0..* |

**BindingType 枚举（v1.4 保留）：**

| 值 | 说明 |
|---|---|
| `lstd:DirectRequirement` | 条款直接定义的要求（shall） |
| `lstd:InheritedRequirement` | 从父标准或上级条款继承的要求 |
| `lstd:AdoptedRequirement` | 通过采纳关系获得的要求 |
| `lstd:ExtendedRequirement` | 在引用基础上提出更严格或额外要求 |
| `lstd:ReferencedRequirement` | 条款引用的外部要求（如 "according to ISO xxx"） |
| `lstd:InformativeBinding` | 信息性条款（非强制性） |
| `lstd:RecommendationBinding` | 推荐性要求（should） |

### 4.15 StandardRelationship

```turtle
lstd:StandardRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "StandardRelationship" ;
    rdfs:comment "标准之间关系的抽象基类" .
```

### 4.16 AdoptionRelationship

```turtle
lstd:AdoptionRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardRelationship ;
    rdfs:label "AdoptionRelationship" ;
    rdfs:comment "采纳关系：一个标准采纳另一个标准的内容" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:sourceStandard` | lstd:AdoptionRelationship | lstd:Standard | 采纳方 | 1 |
| `lstd:targetStandard` | lstd:AdoptionRelationship | lstd:Standard | 被采纳方 | 1 |
| `lstd:adoptionType` | lstd:AdoptionRelationship | lstd:AdoptionType | 采纳类型 | 1 |
| `lstd:hasDeviation` | lstd:AdoptionRelationship | lstd:Deviation | 偏差描述 | 0..1 |

**AdoptionType：**

| 值 | 说明 |
|---|---|
| `lstd:Identical` | 等同采用 |
| `lstd:Modified` | 修改采用 |
| `lstd:Equivalent` | 等效采用 |
| `lstd:NonEquivalent` | 非等效采用 |

### 4.17 EquivalenceRelationship

```turtle
lstd:EquivalenceRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardRelationship ;
    rdfs:label "EquivalenceRelationship" ;
    rdfs:comment "等效关系：两个标准内容等效" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:standardA` | lstd:EquivalenceRelationship | lstd:Standard | 标准A | 1 |
| `lstd:standardB` | lstd:EquivalenceRelationship | lstd:Standard | 标准B | 1 |
| `lstd:equivalenceType` | lstd:EquivalenceRelationship | lstd:EquivalenceType | 等效类型 | 1 |

**EquivalenceType：**

| 值 | 说明 |
|---|---|
| `lstd:FullEquivalent` | 完全等效 |
| `lstd:PartialEquivalent` | 部分等效 |
| `lstd:TechnicalEquivalent` | 技术等效 |

### 4.18 DeviationRelationship

```turtle
lstd:DeviationRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardRelationship ;
    rdfs:label "DeviationRelationship" ;
    rdfs:comment "偏差关系：一个标准偏离另一个标准的要求" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:sourceStandard` | lstd:DeviationRelationship | lstd:Standard | 偏差方 | 1 |
| `lstd:targetStandard` | lstd:DeviationRelationship | lstd:Standard | 被偏差方 | 1 |
| `lstd:deviationDescription` | lstd:DeviationRelationship | xsd:string | 偏差描述 | 1 |
| `lstd:affectedClauses` | lstd:DeviationRelationship | xsd:string | 受影响的条款 | 0..1 |

### 4.19 HarmonizationRelationship

```turtle
lstd:HarmonizationRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardRelationship ;
    rdfs:label "HarmonizationRelationship" ;
    rdfs:comment "协调关系：多个标准之间经过协调一致" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:standards` | lstd:HarmonizationRelationship | lstd:Standard | 协调的标准列表 | 1..* |
| `lstd:harmonizationScope` | lstd:HarmonizationRelationship | xsd:string | 协调范围 | 0..1 |

### 4.20 ReplacementRelationship

```turtle
lstd:ReplacementRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardRelationship ;
    rdfs:label "ReplacementRelationship" ;
    rdfs:comment "替代关系：一个标准替代另一个标准（跨体系）" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:replacedStandard` | lstd:ReplacementRelationship | lstd:Standard | 被替代的标准 | 1 |
| `lstd:replacingStandard` | lstd:ReplacementRelationship | lstd:Standard | 替代的标准 | 1 |
| `lstd:replacementReason` | lstd:ReplacementRelationship | xsd:string | 替代原因 | 0..1 |

### 4.21 ReferencingRelationship（v1.5 增强）

```turtle
lstd:ReferencingRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardRelationship ;
    rdfs:label "ReferencingRelationship" ;
    rdfs:comment "引用关系：一个标准引用另一个标准的内容作为参考" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:referencingStandard` | lstd:ReferencingRelationship | lstd:Standard | 引用方 | 1 |
| `lstd:referencedStandard` | lstd:ReferencingRelationship | lstd:Standard | 被引用方 | 1 |
| `lstd:hasReferenceType` | lstd:ReferencingRelationship | **`lstd:ReferenceType`** | 引用类型 | 1 |
| `lstd:hasDependencyStatus` | lstd:ReferencingRelationship | **`lstd:DependencyStatus`** | **依赖解析状态（v1.5 新增）** | 1 |
| `lstd:referenceClause` | lstd:ReferencingRelationship | xsd:string | 引用的具体条款 | 0..1 |
| `lstd:isNormativeDependency` | lstd:ReferencingRelationship | xsd:boolean | 是否为规范性依赖 | 0..1 |

**ReferenceType（v1.4 保留）：**

| 值 | 说明 | 推理行为 |
|---|---|---|
| `lstd:MandatoryReference` | 强制性引用：被引用内容必须遵守 | 要求必须传播 |
| `lstd:NormativeReference` | 规范性引用：被引用内容是规范的一部分 | 要求应根据引用上下文传播 |
| `lstd:InformativeReference` | 信息性引用：仅供参考 | 要求不传播，仅提供背景信息 |
| `lstd:MethodReference` | 方法引用：引用测试方法或程序 | 要求传播受限，仅传播方法类约束 |
| `lstd:DefinitionReference` | 定义引用：引用术语或定义 | 不传播要求，传播术语定义 |
| `lstd:BibliographicReference` | 文献引用 | 要求不传播 |

**DependencyStatus（v1.5 新增）：**

| 值 | 说明 |
|---|---|
| `lstd:Resolved` | 已解析：被引用的标准已完全语义化 |
| `lstd:Partial` | 部分解析：被引用的标准部分语义化 |
| `lstd:Unresolved` | 未解析：被引用的标准未被语义化 |
| `lstd:Obsolete` | 已过时：被引用的标准已废止，应使用更新版本 |
| `lstd:Unknown` | 未知：被引用的标准不存在或无法识别 |

### 4.22 ComplementaryRelationship

```turtle
lstd:ComplementaryRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lstd:StandardRelationship ;
    rdfs:label "ComplementaryRelationship" ;
    rdfs:comment "互补关系：多个标准共同适用，互为补充" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lstd:complementaryStandards` | lstd:ComplementaryRelationship | lstd:Standard | 互补标准列表 | 2..* |
| `lstd:complementaryScope` | lstd:ComplementaryRelationship | xsd:string | 互补范围描述 | 0..1 |

### 4.23 Jurisdiction

```turtle
lstd:Jurisdiction
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "Jurisdiction" ;
    rdfs:comment "法律管辖权/适用区域" .
```

### 4.24 StandardScope

```turtle
lstd:StandardScope
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "StandardScope" ;
    rdfs:comment "标准的适用范围描述，支持结构化表达和可计算匹配" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:scopeText` | 适用范围文本（人类可读） | 1 |
| `lstd:appliesToProductType` | 适用的产品类型 | 0..* |
| `lstd:appliesToIndustry` | 适用的行业 | 0..* |
| `lstd:appliesToMarket` | 适用的市场区域 | 0..* |
| `lstd:appliesToJurisdiction` | 适用的司法管辖区 | 0..* |
| `lstd:appliesToLifecycleStage` | 适用的生命周期阶段 | 0..* |

### 4.25 StandardStatus

```turtle
lstd:StandardStatus
    rdf:type owl:Class ;
    rdfs:label "StandardStatus" ;
    rdfs:comment "标准版本的状态" .
```

| 值 | 说明 |
|---|---|
| `lstd:Draft` | 草案 |
| `lstd:Published` | 已发布 |
| `lstd:Superseded` | 已被替代 |
| `lstd:Withdrawn` | 已废止 |
| `lstd:UnderReview` | 审查中 |

### 4.26 StandardSemanticStatus（v1.5 增强）

```turtle
lstd:StandardSemanticStatus
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "StandardSemanticStatus" ;
    rdfs:comment "标准语义包的完整性状态，用于标记标准在语义化过程中的完成度" .
```

| 值 | 说明 |
|---|---|
| `lstd:Complete` | 完整：所有引用和依赖均已建模 |
| `lstd:IncompleteExternalDependency` | 外部依赖不完整：引用的外部标准或规范未被建模 |
| **`lstd:PartialSemanticModel`** | **部分语义模型（v1.5 新增）：标准核心内容已建模，但部分内容（如注、示例、附录）未完成** |
| **`lstd:MissingMeasurementModel`** | **缺少测量模型（v1.5 新增）：标准包含测量/试验方法要求，但未关联 Measurement Ontology** |
| **`lstd:MissingConstraintModel`** | **缺少约束模型（v1.5 新增）：标准包含技术指标，但未转换为 Constraint** |
| **`lstd:PendingReview`** | **待审核（v1.5 新增）：语义化已完成，但尚未经过人工审核确认** |
| `lstd:UnresolvedReference` | 未解析引用：标准包含引用，但引用目标无法解析或未知 |

```turtle
lstd:UnresolvedDependency
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "UnresolvedDependency" ;
    rdfs:comment "未解析的依赖项，记录标准语义化过程中未能解析的引用" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lstd:targetReferenceId` | 被引用的标准标识（如 "IEC 60034-1:2025"） | 1 |
| `lstd:referencingClause` | 发起引用的条款号 | 0..1 |
| `lstd:unresolvedReason` | 未解析原因 | 0..1 |
| `lstd:resolvedAt` | 解析时间戳 | 0..1 |


## 5. 对象属性

### 5.1 标准结构与组成属性（v1.5 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lstd:issuedBy` | lstd:Standard | lstd:StandardOrganization | 发布机构 |
| `lstd:hasEdition` | lstd:Standard | lstd:StandardEdition | 拥有的版本 |
| `lstd:containsContentUnit` | lstd:StandardEdition | **`lstd:StandardContentUnit`** | **包含的内容单元（v1.5 新增）** |
| `lstd:containsClause` | lstd:StandardEdition | lstd:StandardClause | 包含的条款（v1.5 保留，向后兼容） |
| `lstd:belongsToFamily` | lstd:Standard | lstd:StandardFamily | 所属标准族 |
| `lstd:hasScope` | lstd:Standard | lstd:StandardScope | 适用范围 |
| `lstd:hasSemanticPackageVersion` | lstd:StandardEdition | `lsp:SemanticPackage` | 语义包版本（v1.5 增强） |

### 5.2 内容单元属性（v1.5 新增）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lstd:hasParentUnit` | lstd:StandardContentUnit | lstd:StandardContentUnit | 父内容单元 |
| `lstd:hasChildUnit` | lstd:StandardContentUnit | lstd:StandardContentUnit | 子内容单元 |
| `lstd:containsNormativeStatement` | lstd:StandardContentUnit | lstd:NormativeStatement | 包含的规范性陈述 |
| `lstd:hasExtractionStatus` | lstd:StandardContentUnit | lstd:ExtractionStatus | 语义提取状态 |

### 5.3 条款与要求绑定属性（v1.5 增强）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lstd:definesBinding` | lstd:StandardClause | lstd:RequirementBinding | 定义的要求绑定（来源方视角） |
| `lstd:isSourceFor` | lstd:StandardClause / lstd:StandardContentUnit | lstd:RequirementBinding | 作为来源的要求绑定（要求方视角） |
| `lstd:referencesRequirement` | lstd:RequirementBinding | `lbo-req:Requirement` | 引用的要求定义 |
| `lstd:hasObligationLevel` | lstd:RequirementBinding / lstd:NormativeStatement | **`lbo-core:ObligationLevel`** | 强制程度 |
| `lstd:bindingType` | lstd:RequirementBinding | **`lstd:BindingType`** | 绑定类型 |
| `lstd:derivedFromClause` | lstd:RequirementBinding | lstd:StandardClause | 来源条款（0..*） |
| `lstd:derivedFromContentUnit` | lstd:RequirementBinding | **`lstd:StandardContentUnit`** | **来源内容单元（v1.5 新增）** |
| `lstd:derivedFromNormativeSource` | lstd:RequirementBinding | **`lstd:NormativeStatement` / `lstd:StandardContentUnit`** | **来源规范性来源（v1.5 新增）** |
| `lstd:derivesBinding` | lstd:NormativeStatement | lstd:RequirementBinding | 产生的要求绑定（v1.5 新增） |

### 5.4 标准关系属性（v1.5 增强）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lstd:hasRelationship` | lstd:Standard | lstd:StandardRelationship | 标准间关系 |
| `lstd:sourceStandard` | lstd:AdoptionRelationship / lstd:DeviationRelationship | lstd:Standard | 源标准 |
| `lstd:targetStandard` | lstd:AdoptionRelationship / lstd:DeviationRelationship | lstd:Standard | 目标标准 |
| `lstd:standardA` | lstd:EquivalenceRelationship | lstd:Standard | 标准A |
| `lstd:standardB` | lstd:EquivalenceRelationship | lstd:Standard | 标准B |
| `lstd:replacedStandard` | lstd:ReplacementRelationship | lstd:Standard | 被替代标准 |
| `lstd:replacingStandard` | lstd:ReplacementRelationship | lstd:Standard | 替代标准 |
| `lstd:referencingStandard` | lstd:ReferencingRelationship | lstd:Standard | 引用方 |
| `lstd:referencedStandard` | lstd:ReferencingRelationship | lstd:Standard | 被引用方 |
| `lstd:hasReferenceType` | lstd:ReferencingRelationship | **`lstd:ReferenceType`** | 引用类型 |
| **`lstd:hasDependencyStatus`** | **lstd:ReferencingRelationship** | **`lstd:DependencyStatus`** | **依赖解析状态（v1.5 新增）** |
| `lstd:complementaryStandards` | lstd:ComplementaryRelationship | lstd:Standard | 互补标准列表 |
| `lstd:hasDeviation` | lstd:AdoptionRelationship | lstd:Deviation | 偏差描述 |
| `lstd:supersedes` | lstd:StandardEdition | lstd:StandardEdition | 替代旧版本 |
| `lstd:supersededBy` | lstd:StandardEdition | lstd:StandardEdition | 被新版本替代 |
| `lstd:revises` | lstd:StandardEdition | lstd:StandardEdition | 修订的旧版本 |
| `lstd:revisedFrom` | lstd:StandardEdition | lstd:StandardEdition | 被修订的版本 |

### 5.5 与外部模块的连接属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lstd:hasNormativePackage` | lstd:StandardEdition | lsp:NormativeSemanticPackage | 对应的语义包（v1.5 增强——支持多版本） |

### 5.6 语义完整性属性（v1.5 增强）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lstd:hasSemanticStatus` | lstd:Standard / lstd:StandardEdition | lstd:StandardSemanticStatus | 语义完整性状态（v1.5 增强） |
| `lstd:hasUnresolvedDependency` | lstd:Standard / lstd:StandardEdition | lstd:UnresolvedDependency | 未解析依赖项 |


## 6. 数据属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lstd:standardId` | lstd:Standard | xsd:string | 标准编号 |
| `lstd:standardTitle` | lstd:Standard | xsd:string | 标准名称 |
| `lstd:edition` | lstd:StandardEdition | xsd:string | 版本标识 |
| `lstd:approvalDate` | lstd:StandardEdition | xsd:date | 批准日期 |
| `lstd:effectiveDate` | lstd:StandardEdition | xsd:date | 实施日期 |
| `lstd:withdrawDate` | lstd:StandardEdition | xsd:date | 废止日期 |
| `lstd:status` | lstd:StandardEdition | lstd:StandardStatus | 版本状态 |
| `lstd:contentUnitId` | lstd:StandardContentUnit | xsd:string | 内容单元标识符（v1.5 新增） |
| `lstd:contentUnitType` | lstd:StandardContentUnit | xsd:string | 内容单元类型（v1.5 新增） |
| `lstd:clauseNumber` | lstd:StandardClause | xsd:string | 条款编号 |
| `lstd:clauseText` | lstd:StandardClause | xsd:string | 条款原文 |
| `lstd:tableNumber` | lstd:TableUnit | xsd:string | 表格编号（v1.5 新增） |
| `lstd:tableContent` | lstd:TableUnit | xsd:string | 表格内容（v1.5 新增） |
| `lstd:figureNumber` | lstd:FigureUnit | xsd:string | 图编号（v1.5 新增） |
| `lstd:term` | lstd:DefinitionUnit | xsd:string | 术语（v1.5 新增） |
| `lstd:definition` | lstd:DefinitionUnit | xsd:string | 定义文本（v1.5 新增） |
| `lstd:noteText` | lstd:NoteUnit | xsd:string | 注文本（v1.5 新增） |
| `lstd:exampleText` | lstd:ExampleUnit | xsd:string | 示例文本（v1.5 新增） |
| `lstd:annexNumber` | lstd:AnnexUnit | xsd:string | 附录编号（v1.5 新增） |
| `lstd:annexType` | lstd:AnnexUnit | xsd:string | 附录类型（v1.5 新增） |
| `lstd:adoptionType` | lstd:AdoptionRelationship | lstd:AdoptionType | 采纳类型 |
| `lstd:deviationDescription` | lstd:DeviationRelationship | xsd:string | 偏差描述 |
| `lstd:equivalenceType` | lstd:EquivalenceRelationship | lstd:EquivalenceType | 等效类型 |
| `lstd:scopeText` | lstd:StandardScope | xsd:string | 适用范围文本 |
| `lstd:appliesToProductType` | lstd:StandardScope | rdfs:Class | 适用产品类型 |
| `lstd:appliesToIndustry` | lstd:StandardScope | xsd:string | 适用行业 |
| `lstd:appliesToMarket` | lstd:StandardScope | xsd:string | 适用市场 |
| `lstd:appliesToJurisdiction` | lstd:StandardScope | xsd:string | 适用司法管辖区 |
| `lstd:appliesToLifecycleStage` | lstd:StandardScope | xsd:string | 适用生命周期阶段 |
| `lstd:bindingType` | lstd:RequirementBinding | lstd:BindingType | 绑定类型 |
| `lstd:hasReferenceType` | lstd:ReferencingRelationship | lstd:ReferenceType | 引用类型 |
| **`lstd:hasDependencyStatus`** | **lstd:ReferencingRelationship** | **`lstd:DependencyStatus`** | **依赖解析状态（v1.5 新增）** |
| `lstd:isNormativeDependency` | lstd:ReferencingRelationship | xsd:boolean | 是否为规范性依赖 |
| `lstd:targetReferenceId` | lstd:UnresolvedDependency | xsd:string | 被引用的标准标识 |
| `lstd:referencingClause` | lstd:UnresolvedDependency | xsd:string | 发起引用的条款号 |
| `lstd:unresolvedReason` | lstd:UnresolvedDependency | xsd:string | 未解析原因 |
| `lstd:resolvedAt` | lstd:UnresolvedDependency | xsd:dateTime | 解析时间戳 |


## 7. 推理规则

### 7.1 要求继承规则

**规则1：子条款继承父条款的要求绑定**

```
IF StandardClause A hasParentClause B
AND B definesBinding Rb
THEN A definesBinding Rb
```

### 7.2 要求绑定传播规则

**规则2：要求绑定的要求可被产品规格评估**

```
IF StandardContentUnit definesBinding Rb
AND Rb referencesRequirement R
THEN R is a requirement derived from the standard
```

### 7.3 版本替代规则

**规则3：新版本替代旧版本 ⇒ 旧版本的要求绑定不再有效**

```
IF StandardEdition A supersedes StandardEdition B
AND B definesBinding Rb
THEN Rb is not effective for products conforming to A
```

### 7.4 采纳传播规则

**规则4：标准采纳另一标准 ⇒ 采纳方继承被采纳方的要求绑定**

```
IF Standard A adopts Standard B
AND B definesBinding Rb
THEN A definesBinding Rb
```

**规则5：采纳关系传递**

```
IF Standard A adopts Standard B
AND Standard B adopts Standard C
THEN Standard A adopts Standard C
```

### 7.5 符合性推理规则

**规则6：产品规格满足标准的所有强制要求 ⇒ 产品符合标准**

```
IF Product P hasSpecification S
AND StandardEdition E definesBinding Rb1...Rbn
AND Rb hasObligationLevel lbo-core:Mandatory
AND S satisfies R（对应的要求）
AND VerificationResult confirms satisfaction
THEN lbo-core:ComplianceAssessment C confirms P conformsTo E
```

**规则7：合规评估结果 ⇒ 要求满足声明**

```
IF lbo-core:ComplianceAssessment C confirms Product P conformsTo StandardEdition E
AND E definesBinding Rb
AND Rb referencesRequirement R
THEN P hasAssessmentResultFor R（从合规评估中获得的要求满足结果）
```

> **推理方向说明：**
>
> 规则6 用于从规格和验证结果判断是否可声明符合标准。
>
> 规则7 不再从"符合标准"推导"满足要求"（避免循环推理），而是从合规评估结果推导出产品对特定要求的评估覆盖情况。即：规则7 是**声明解释规则（semantic interpretation）**，而非推理规则。它说明合规评估覆盖了哪些要求，但不产生新的满足事实。

### 7.6 引用传播规则（v1.5 增强）

**规则8：强制性引用 ⇒ 要求传播**

```
IF Standard A references Standard B with ReferenceType MandatoryReference
AND B definesBinding Rb
THEN A inherits Rb as a mandatory requirement
```

**规则8a：规范性引用 ⇒ 要求有条件传播**

```
IF Standard A references Standard B with ReferenceType NormativeReference
AND B definesBinding Rb
AND A's context matches B's scope
THEN A hasReferencedRequirement Rb
```

**规则8b：方法引用 ⇒ 仅传播方法约束**

```
IF Standard A references Standard B with ReferenceType MethodReference
AND B definesBinding Rb
AND Rb relates to a Method or TestProcedure
THEN A inherits Rb as a method constraint
```

**规则8c：定义引用 ⇒ 传播术语定义（v1.5 新增）**

```
IF Standard A references Standard B with ReferenceType DefinitionReference
AND B definesBinding Rb
AND Rb relates to a Definition
THEN A inherits Rb as a definition reference
```

**规则9：引用关系传递**

```
IF Standard A references Standard B with ReferenceType T1
AND Standard B references Standard C with ReferenceType T2
AND T1 is NormativeReference or MandatoryReference
AND T2 is NormativeReference or MandatoryReference
THEN Standard A references Standard C with ReferenceType T (where T = max(T1, T2))
```

**规则10：引用关系导致语义不完整**

```
IF Standard A references Standard B
AND Standard B hasSemanticStatus IncompleteExternalDependency
THEN Standard A hasSemanticStatus IncompleteExternalDependency
```

**规则10a：依赖状态传播（v1.5 新增）**

```
IF ReferencingRelationship R hasDependencyStatus Unresolved
THEN the referencing Standard hasSemanticStatus IncompleteExternalDependency
```

### 7.7 内容单元到语义层的推理规则（v1.5 新增）

**规则11：规范性陈述产生要求绑定**

```
IF NormativeStatement NS contains text with "shall" or "must" or "should"
AND NS is contained in StandardContentUnit U
THEN U definesBinding Rb
AND Rb referencesRequirement R
AND R is derived from NS
```

**规则12：表格单元产生结构化要求**

```
IF TableUnit T contains technical values
AND T is referenced by NormativeStatement NS
THEN T isSourceFor RequirementBinding Rb
AND Rb referencesRequirement R with CharacteristicTarget
```


## 8. 与 Normative Semantic Package 的接口（v1.5 增强）

```turtle
# Standard 与 Normative Semantic Package 的关系
lstd:hasNormativePackage
    rdf:type owl:ObjectProperty ;
    rdfs:domain lstd:StandardEdition ;
    rdfs:range lsp:NormativeSemanticPackage ;
    rdfs:label "hasNormativePackage" ;
    rdfs:comment "标准版本对应的语义包。同一标准可有多个语义包版本（如不同领域版本）" .

lstd:hasSemanticPackageVersion
    rdf:type owl:ObjectProperty ;
    rdfs:domain lstd:StandardEdition ;
    rdfs:range lsp:SemanticPackage ;
    rdfs:label "hasSemanticPackageVersion" ;
    rdfs:comment "标准版本拥有的语义包版本（v1.5 新增，支持多版本管理）" .
```

**接口链路：**

```
Standard Ontology（概念层）
    │
    │  lstd:hasSemanticPackageVersion / lstd:hasNormativePackage
    ▼
Normative Semantic Package（实例封装层）
    │
    │  lsp:basedOnDocument → lbo:NormativeEdition
    │
    ▼
Requirement Instances（要求实例，引用 lbo-req:Requirement）
```

**多版本说明（v1.5 新增）：**

同一个标准版本可有多个语义包版本，适用于：
- 不同领域（如 IEC 60034-1 有电机设计版、能效版）
- 不同语言版本（中文、英文）
- 不同完善程度（v1.0 基础版，v2.0 完整版）


## 9. 与 Specification Framework Ontology 的接口

**正确的链路：**

```
Standard
    │
    │  lstd:definesBinding
    ▼
RequirementBinding
    │
    │  referencesRequirement
    ▼
lbo-req:Requirement（要求语义）
    │
    │  lbo-req:hasConstraint
    ▼
lcon:Constraint（约束）
    │
    │  约束 Specification
    ▼
lbo-spec:Specification（规格表达）
    │
    │  lbo-spec:describedBy
    ▼
Product（产品）
```

**接口属性（在 Specification Framework Ontology 中定义）：**

```turtle
# Specification 满足 Requirement（来自 lbo-spec）
lbo-spec:satisfies
    rdf:type owl:ObjectProperty ;
    rdfs:domain lbo-spec:Specification ;
    rdfs:range lbo-req:Requirement .

# Specification 被 Requirement 评估（来自 lbo-spec）
lbo-spec:evaluatedAgainst
    rdf:type owl:ObjectProperty ;
    rdfs:domain lbo-spec:Specification ;
    rdfs:range lbo-req:Requirement .
```


## 10. 与 Requirement Ontology 的接口（v1.5 增强）

Standard Ontology 引用 `lbo-req:Requirement`，不重新定义它。

| Standard Ontology 概念 | 引用的 Requirement Ontology 概念 |
|---|---|
| `lstd:RequirementBinding.referencesRequirement` | `lbo-req:Requirement` |
| `lbo-req:Requirement.hasSemanticTarget` | `lbo-req:SemanticTarget` |

**关键语义映射（v1.5 明确）：**

```
lstd:RequirementBinding
    │
    │  referencesRequirement
    ▼
lbo-req:Requirement
    │
    │  hasSemanticTarget (1..*)
    ▼
lbo-req:SemanticTarget
    │
    ├── 可为以下类型：
    │   ├── lbo-req:CharacteristicTarget (特性，如 Efficiency)
    │   ├── lbo-req:FunctionTarget (功能，如 OverloadProtection)
    │   ├── lbo-req:InterfaceTarget (接口，如 CAN Interface)
    │   ├── lbo-req:StructureRelationTarget (结构关系，如 hasPart)
    │   ├── lbo-req:MaterialPropertyTarget (材料属性)
    │   └── lbo-req:ProcessElementTarget (过程要素)
    │
    │  hostedBy (1)
    ▼
lbo-core:Product / Part / Process / Software / Interface
```

强制程度（`ObligationLevel`）来自 `lbo-core:ObligationLevel`，在 Core Ontology 中定义。


## 11. 与 Constraint Ontology 的接口

Standard Ontology 通过 Requirement Ontology 间接引用 Constraint Ontology：

```
Standard
    │
    └── StandardContentUnit
            │
            └── definesBinding → RequirementBinding
                    │
                    └── referencesRequirement → lbo-req:Requirement
                            │
                            └── lbo-req:hasConstraint → lcon:Constraint
```

**完整链路：**

```
Standard → ContentUnit → RequirementBinding → Requirement → Constraint → Specification → Measurement → Compliance
```


## 12. 与 GB/T 46917 的对齐（v1.5 新增）

GB/T 46917.1-2026《标准内容语义化表达通用要求》将标准内容语义化表达单元分为**通用语义化表达单元**和**专用语义化表达单元**。本 Ontology 的对齐关系如下：

| GB/T 46917 概念 | Standard Ontology 映射 | 说明 |
|---|---|---|
| 标准编号 | `lstd:standardId` | 通用单元 |
| 中文标准名称 | `lstd:standardTitle` | 通用单元 |
| 发布日期 | `lstd:approvalDate` | 通用单元 |
| 发布机构 | `lstd:issuedBy` → `lstd:StandardOrganization` | 通用单元 |
| 标准状态 | `lstd:status` | 通用单元 |
| 起草单位 | `lstd:StandardOrganization` | 通用单元 |
| 前言 | `lstd:StandardEdition` 的 `preface` 属性 | 通用单元 |
| 引言 | `lstd:StandardEdition` 的 `introduction` 属性 | 通用单元 |
| **条款（规范性要素）** | **`lstd:StandardClause`** | **专用单元** |
| **表格** | **`lstd:TableUnit`** | **专用单元（v1.5 新增）** |
| **图** | **`lstd:FigureUnit`** | **专用单元（v1.5 新增）** |
| **定义** | **`lstd:DefinitionUnit`** | **专用单元（v1.5 新增）** |
| **注** | **`lstd:NoteUnit`** | **专用单元（v1.5 新增）** |
| **示例** | **`lstd:ExampleUnit`** | **专用单元（v1.5 新增）** |
| **附录** | **`lstd:AnnexUnit`** | **专用单元（v1.5 新增）** |

**语义化表达规则对齐：**

1. **表达顺序性**：内容单元的层级关系通过 `hasParentUnit`/`hasChildUnit` 维护，顺序通过 `contentUnitOrder` 表达。
2. **语义完整性**：规范性陈述通过 `NormativeStatement` 表达，并通过 `RequirementBinding` 连接到语义层，确保完整语义覆盖。


## 13. 外部标准对齐

| 外部体系 | 对齐方式 | 说明 |
|---|---|---|
| W3C ORG | `skos:closeMatch` | org:Organization → lstd:StandardOrganization |
| SKOS | `skos:Concept` | 用于 StandardType、Jurisdiction 等枚举 |
| ISO 标准元数据 | `skos:closeMatch` | ISO 标准标识元数据映射 |
| **GB/T 46917** | **概念对齐** | **标准内容语义化表达单元（v1.5 新增）** |


## 14. SHACL 验证约束（v1.5 增强）

### 14.1 Standard 约束

```turtle
lstd:StandardShape
    a sh:NodeShape ;
    sh:targetClass lstd:Standard ;
    sh:property [
        sh:path lstd:standardId ;
        sh:minCount 1 ;
        sh:message "Standard must have an identifier"
    ] ;
    sh:property [
        sh:path lstd:standardTitle ;
        sh:minCount 1 ;
        sh:message "Standard must have a title"
    ] ;
    sh:property [
        sh:path lstd:issuedBy ;
        sh:minCount 1 ;
        sh:message "Standard must have an issuing organization"
    ] ;
    sh:property [
        sh:path lstd:hasEdition ;
        sh:minCount 1 ;
        sh:message "Standard must have at least one edition"
    ] .
```

### 14.2 StandardEdition 约束（v1.5 更新）

```turtle
lstd:StandardEditionShape
    a sh:NodeShape ;
    sh:targetClass lstd:StandardEdition ;
    sh:property [
        sh:path lstd:edition ;
        sh:minCount 1 ;
        sh:message "StandardEdition must have an edition identifier"
    ] ;
    sh:property [
        sh:path lstd:effectiveDate ;
        sh:minCount 1 ;
        sh:message "StandardEdition must have an effective date"
    ] ;
    sh:property [
        sh:path lstd:status ;
        sh:minCount 1 ;
        sh:message "StandardEdition must have a status"
    ] ;
    sh:property [
        sh:path lstd:containsContentUnit ;
        sh:minCount 1 ;
        sh:message "StandardEdition must contain at least one content unit"
    ] .
```

### 14.3 StandardContentUnit 约束（v1.5 新增）

```turtle
lstd:StandardContentUnitShape
    a sh:NodeShape ;
    sh:targetClass lstd:StandardContentUnit ;
    sh:property [
        sh:path lstd:contentUnitType ;
        sh:minCount 1 ;
        sh:message "StandardContentUnit must have a content unit type"
    ] .
```

### 14.4 RequirementBinding 约束（v1.5 增强）

```turtle
lstd:RequirementBindingShape
    a sh:NodeShape ;
    sh:targetClass lstd:RequirementBinding ;
    sh:property [
        sh:path lstd:referencesRequirement ;
        sh:minCount 1 ;
        sh:message "RequirementBinding must reference a requirement"
    ] ;
    sh:property [
        sh:path lstd:hasObligationLevel ;
        sh:minCount 1 ;
        sh:message "RequirementBinding must have an obligation level"
    ] ;
    sh:or (
        [
            sh:property [
                sh:path lstd:derivedFromNormativeSource ;
                sh:minCount 1 ;
                sh:message "RequirementBinding must be derived from a normative source"
            ]
        ]
        [
            sh:property [
                sh:path lstd:derivedFromClause ;
                sh:minCount 1 ;
                sh:message "RequirementBinding must be derived from a clause"
            ]
        ]
        [
            sh:property [
                sh:path lstd:derivedFromContentUnit ;
                sh:minCount 1 ;
                sh:message "RequirementBinding must be derived from a content unit"
            ]
        ]
        [
            sh:property [
                sh:path lstd:isSourceFor ;
                sh:minCount 1 ;
                sh:message "RequirementBinding must be associated with at least one content unit"
            ]
        ]
    ) .
```

### 14.5 ReferencingRelationship 约束（v1.5 增强）

```turtle
lstd:ReferencingRelationshipShape
    a sh:NodeShape ;
    sh:targetClass lstd:ReferencingRelationship ;
    sh:property [
        sh:path lstd:referencingStandard ;
        sh:minCount 1 ;
        sh:message "ReferencingRelationship must have a referencing standard"
    ] ;
    sh:property [
        sh:path lstd:referencedStandard ;
        sh:minCount 1 ;
        sh:message "ReferencingRelationship must have a referenced standard"
    ] ;
    sh:property [
        sh:path lstd:hasReferenceType ;
        sh:minCount 1 ;
        sh:message "ReferencingRelationship must have a reference type"
    ] ;
    sh:property [
        sh:path lstd:hasDependencyStatus ;
        sh:minCount 1 ;
        sh:message "ReferencingRelationship must have a dependency status"
    ] .
```

### 14.6 StandardSemanticStatus 约束（v1.5 增强）

```turtle
lstd:StandardSemanticStatusShape
    a sh:NodeShape ;
    sh:targetClass lstd:StandardSemanticStatus ;
    sh:in (
        lstd:Complete
        lstd:IncompleteExternalDependency
        lstd:PartialSemanticModel
        lstd:MissingMeasurementModel
        lstd:MissingConstraintModel
        lstd:PendingReview
        lstd:UnresolvedReference
    ) ;
    sh:message "StandardSemanticStatus must be one of the predefined values" .
```

### 14.7 NormativeStatement 约束（v1.5 新增）

```turtle
lstd:NormativeStatementShape
    a sh:NodeShape ;
    sh:targetClass lstd:NormativeStatement ;
    sh:property [
        sh:path lstd:statementText ;
        sh:minCount 1 ;
        sh:message "NormativeStatement must have statement text"
    ] ;
    sh:property [
        sh:path lstd:statementType ;
        sh:minCount 1 ;
        sh:message "NormativeStatement must have a statement type"
    ] .
```


## 15. 完整示例（v1.5 更新）

### 15.1 IEC 60034-1:2025 标准表达（含内容单元）

```turtle
# 标准组织
lstd:IEC
    a lstd:StandardOrganization ;
    llb:hasName "International Electrotechnical Commission" .

# 标准体系
lstd:IEC_60034_1
    a lstd:Standard ;
    lstd:standardId "IEC 60034-1" ;
    lstd:standardTitle "Rotating electrical machines - Part 1: Rating and performance" ;
    lstd:issuedBy lstd:IEC ;
    lstd:hasSemanticStatus lstd:Complete .

# 标准版本
lstd:IEC_60034_1_2025
    a lstd:StandardEdition ;
    lstd:edition "2025" ;
    lstd:editionTitle "Edition 4.0" ;
    lstd:approvalDate "2025-12-15"^^xsd:date ;
    lstd:effectiveDate "2026-02-01"^^xsd:date ;
    lstd:status lstd:Published ;
    lstd:supersedes lstd:IEC_60034_1_2017 .

# 条款（StandardClause 作为 StandardContentUnit 的子类）
lstd:Clause_8_4
    a lstd:StandardClause ;
    lstd:contentUnitType "clause" ;
    lstd:clauseNumber "8.4" ;
    lstd:clauseTitle "Temperature rise limits" ;
    lstd:clauseText "The temperature rise of the windings shall not exceed the limits specified in Table 8." .

lstd:Clause_8_4_1
    a lstd:StandardClause ;
    lstd:contentUnitType "clause" ;
    lstd:clauseNumber "8.4.1" ;
    lstd:clauseTitle "Method of measurement" ;
    lstd:clauseText "Temperature shall be measured by the resistance method." ;
    lstd:hasParentUnit lstd:Clause_8_4 .

# 表格单元（v1.5 新增）
lstd:Table_8
    a lstd:TableUnit ;
    lstd:contentUnitType "table" ;
    lstd:tableNumber "Table 8" ;
    lstd:tableTitle "Temperature rise limits by insulation class" ;
    lstd:tableContent "{\"rows\": [{\"class\": \"A\", \"limit\": 60}, ...]}" .
    lstd:hasParentUnit lstd:Clause_8_4 .

# 规范性陈述（v1.5 增强）
lstd:NS_Temp_Rise
    a lstd:NormativeStatement ;
    lstd:statementText "The temperature rise of the windings shall not exceed the limits specified in Table 8." ;
    lstd:statementType lstd:Shall ;
    lstd:hasObligationLevel lbo-core:Mandatory .

# 标准版本包含内容单元
lstd:IEC_60034_1_2025
    lstd:containsContentUnit lstd:Clause_8_4 ;
    lstd:containsContentUnit lstd:Clause_8_4_1 ;
    lstd:containsContentUnit lstd:Table_8 .

# Clause 包含 NormativeStatement
lstd:Clause_8_4
    lstd:containsNormativeStatement lstd:NS_Temp_Rise .

# 要求绑定（引用 lbo-req:Requirement）
lstd:Binding_Temp_Rise
    a lstd:RequirementBinding ;
    lstd:referencesRequirement lbo-req:REQ_Temp_001 ;
    lstd:hasObligationLevel lbo-core:Mandatory ;
    lstd:bindingType lstd:DirectRequirement ;
    lstd:derivedFromNormativeSource lstd:NS_Temp_Rise ;
    lstd:derivedFromContentUnit lstd:Clause_8_4 .

# NormativeStatement 产生绑定（v1.5 新增）
lstd:NS_Temp_Rise
    lstd:derivesBinding lstd:Binding_Temp_Rise .
```

### 15.2 要求目标示例

```turtle
# 在 Requirement Ontology 中定义
lbo-req:REQ_Temp_001
    a lbo-req:Requirement ;
    rdfs:label "Temperature Rise Limit Requirement" ;
    lbo-req:hasSemanticTarget lbo-req:Target_Temp_001 .

lbo-req:Target_Temp_001
    a lbo-req:CharacteristicTarget ;
    rdfs:label "Winding Temperature Rise" ;
    lbo-req:targetCharacteristic lbo-core:TemperatureRise ;
    lbo-req:hostedBy lbo-core:BLDCMotor_Winding ;
    lbo-req:hasConstraint lcon:Constraint_Temp_001 .

lcon:Constraint_Temp_001
    a lcon:Constraint ;
    rdfs:label "Temperature Rise ≤ 40°C" ;
    lcon:hasValueConstraint "<=40"^^xsd:string ;
    lcon:unit "°C" .
```

### 15.3 标准关系示例（含依赖状态）

```turtle
# GB/T 755-2025 采纳 IEC 60034-1:2025
lstd:GB_T_755_2025
    a lstd:Standard ;
    lstd:standardId "GB/T 755-2025" ;
    lstd:standardTitle "旋转电机 定额与性能" ;
    lstd:issuedBy lstd:GB .

lstd:GB_T_755_Adopts_IEC
    a lstd:AdoptionRelationship ;
    lstd:sourceStandard lstd:GB_T_755_2025 ;
    lstd:targetStandard lstd:IEC_60034_1_2025 ;
    lstd:adoptionType lstd:Identical .

lstd:GB_T_755_2025
    lstd:hasRelationship lstd:GB_T_755_Adopts_IEC .

# 引用关系示例（v1.5：含 DependencyStatus）
lstd:ISO_9001_2025
    a lstd:Standard ;
    lstd:standardId "ISO 9001:2025" .

lstd:ISO_9001_References_9000
    a lstd:ReferencingRelationship ;
    lstd:referencingStandard lstd:ISO_9001_2025 ;
    lstd:referencedStandard lstd:ISO_9000_2015 ;
    lstd:hasReferenceType lstd:NormativeReference ;
    lstd:hasDependencyStatus lstd:Resolved ;
    lstd:isNormativeDependency "true"^^xsd:boolean .

lstd:ISO_9001_2025
    lstd:hasRelationship lstd:ISO_9001_References_9000 .
```

### 15.4 语义完整性状态示例（v1.5 增强）

```turtle
# 一个部分语义化的标准（v1.5 新增状态）
lstd:IEC_60598_2025
    a lstd:Standard ;
    lstd:standardId "IEC 60598-1:2025" ;
    lstd:standardTitle "Luminaires - Part 1: General requirements and tests" ;
    lstd:hasSemanticStatus lstd:PartialSemanticModel ;
    lstd:hasUnresolvedDependency lstd:Unresolved_IEC_62471 .

lstd:Unresolved_IEC_62471
    a lstd:UnresolvedDependency ;
    lstd:targetReferenceId "IEC 62471:2006" ;
    lstd:referencingClause "4.3" ;
    lstd:unresolvedReason "Referenced standard not yet modeled in knowledge base" .
```


## 16. 冻结声明

### 16.1 冻结范围

v1.5 确认后，以下内容进入**核心冻结状态**：

- ✅ 所有核心类（Standard、StandardFamily、StandardEdition、StandardOrganization、**StandardContentUnit 及其子类**、StandardClause、TableUnit、FigureUnit、DefinitionUnit、NoteUnit、ExampleUnit、AnnexUnit、NormativeStatement、RequirementBinding、StandardRelationship 及其所有核心子类）
- ✅ 所有核心对象属性（含 v1.5 新增的 `containsContentUnit`、`hasParentUnit`、`hasChildUnit`、`derivedFromNormativeSource`、`hasDependencyStatus` 等）
- ✅ 命名空间 `https://ontology.leleby.org/standard/`
- ✅ 与 Requirement Ontology、Specification Framework Ontology、Constraint Ontology、Normative Semantic Package 的核心接口
- ✅ **与 GB/T 46917 的概念对齐关系（v1.5 新增）**

### 16.2 扩展点（Reserved Extension Points）

以下内容允许在 v1.5 基础上进行模块内部扩展，无需变更核心冻结模型：

- ✅ 新增标准组织实例
- ✅ 新增管辖权值
- ✅ 新增标准关系子类
- ✅ 新增标准状态值
- ✅ **新增 BindingType 值（扩展点）**
- ✅ **新增 ReferenceType 值（扩展点）**
- ✅ **新增 DependencyStatus 值（扩展点）**
- ✅ **新增 StandardSemanticStatus 值（扩展点）**
- ✅ **新增 StandardContentUnit 子类（扩展点）**
- ✅ **新增 UnresolvedDependency 子类**
- ✅ **优化推理规则（不改变核心类与属性）**
- ✅ **完善接口描述（不改变核心类与属性）**

### 16.3 冻结后禁止

- ❌ **修改或删除任何现有核心类**
- ❌ **修改或删除任何现有核心属性**
- ❌ **改变与 Requirement Ontology / Specification Framework Ontology / Constraint Ontology 的核心接口**
- ❌ **在 Standard Ontology 中定义包的封装格式**（属于 Normative Semantic Package）
- ❌ **重新定义 Requirement**（必须引用 lbo-req:Requirement）
- ❌ **重新定义 ObligationLevel**（必须引用 lbo-core:ObligationLevel）
- ❌ **将 StandardContentUnit 回退为仅支持 Clause**


## 17. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v1.0 | 2026-07-31 | 初始冻结版（Standard Ontology） |
| v1.1 | 2026-07-31 | 架构重构版：删除 StandardRequirement，新增 RequirementBinding；新增 StandardElement、StandardFamily、StandardScope；新增 ReplacementRelationship；重写符合性推理规则 |
| v1.2 | 2026-07-31 | 跨模块统一版：将 `lreq:ObligationLevel` 引用替换为 `lbo-core:ObligationLevel`；统一强制程度语义来源 |
| v1.3 | 2026-07-31 | 最终冻结版：重构符合性推理规则；RequirementBinding 新增 bindingType；StandardScope 结构化增强；新增 ReferencingRelationship、ComplementaryRelationship；补充 Constraint Ontology 接口 |
| v1.4 | 2026-08-04 | 语义增强版：明确 Requirement 目标为 SemanticTarget；ReferenceType 细化；新增 StandardSemanticStatus 和 UnresolvedDependency；BindingType 扩展；derivedFromClause 扩展为 0..*；新增 isSourceFor 反向属性；新增引用传播规则 |
| **v1.5** | **2026-08-04** | **文档语义对齐版**：1）新增 `StandardContentUnit` 抽象类，作为标准文档所有内容单元的顶层抽象，对齐 GB/T 46917.1-2026；2）将 `StandardClause` 改为 `StandardContentUnit` 的子类，保持向后兼容；3）新增 `TableUnit`、`FigureUnit`、`DefinitionUnit`、`NoteUnit`、`ExampleUnit`、`AnnexUnit` 六个内容单元子类；4）明确 `NormativeStatement`（文档层）与 `Requirement`（语义层）的分层关系，新增 `derivesBinding` 属性；5）`ReferencingRelationship` 新增 `hasDependencyStatus` 属性，值为 Resolved/Partial/Unresolved/Obsolete/Unknown；6）扩展 `StandardSemanticStatus` 增加 `PartialSemanticModel`、`MissingMeasurementModel`、`MissingConstraintModel`、`PendingReview`；7）新增 `hasSemanticPackageVersion` 属性支持多版本语义包；8）新增与 GB/T 46917 的概念对齐章节；9）新增内容单元到语义层的推理规则（规则 11-12）；10）增强 SHACL 验证约束；11）更新完整示例 |


*— leleby Standard Ontology Specification v1.5 — Document Semantic Alignment Release —*