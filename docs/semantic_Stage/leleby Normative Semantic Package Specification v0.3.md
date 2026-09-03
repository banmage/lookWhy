# leleby Normative Semantic Package Specification v0.3

**文档版本：** v0.3 — Semantic Alignment Edition（语义对齐版）

**文档类型：** 语义资产规范（Semantic Asset Specification）

**文档状态：** ⚠️ **语义对齐版（Semantically Aligned）** — 已同步至 leleby 核心 Ontology 最新语义模型（Requirement v1.1 / Constraint v1.2 / Product v0.4 / Standard v1.3），待实例验证后冻结

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.2

**命名空间：** `https://spec.leleby.org/lsp/`

**推荐前缀：** `lsp`（leleby Semantic Package）


## 目录

1. 引言
   1.1 背景
   1.2 核心定义
   1.3 v0.3 与 v0.2 的核心差异
   1.4 关键定位声明

2. 目的与范围
   2.1 解决的核心问题
   2.2 核心能力

3. 设计原则
   3.1 规范身份优先原则
   3.2 语义内容分离原则
   3.3 版本不可变原则
   3.4 语义提取可追溯原则
   3.5 最小包原则
   3.6 Ontology 引用原则
   3.7 规范文件与版本分离原则
   3.8 跨规范可映射原则
   3.9 语义完整性可度量原则（v0.3 新增）
   3.10 要求是独立语义对象原则（v0.3 新增）

4. 语义包架构
   4.1 顶层分类体系
   4.2 架构总览
   4.3 文件结构
   4.4 文件内容说明

5. Package Manifest 模型
   5.1 核心类定义
   5.2 Manifest 属性
   5.3 PackageStatus
   5.4 SemanticCompletenessStatus（v0.3 新增）
   5.5 示例

6. 规范文件表示模型
   6.1 NormativeDocument
   6.2 NormativeEdition
   6.3 属性与关系
   6.4 示例

7. 条款语义模型（v0.3 调整）
   7.1 NormativeClause
   7.2 属性
   7.3 Clause-Requirement 关系（v0.3 调整）
   7.4 语义提取状态（v0.3 新增）
   7.5 示例

8. 要求语义模型（v0.3 升级）
   8.1 六元要求模型（v0.3 更新）
   8.2 SemanticTarget 类型体系
   8.3 要求提取映射
   8.4 要求作为独立语义对象（v0.3 新增）
   8.5 示例

9. 约束表示模型（v0.3 升级）
   9.1 约束类型体系
   9.2 ConditionalConstraint
   9.3 LogicalConstraint
   9.4 Constraint Target 同步（v0.3 新增）
   9.5 示例

10. 测试方法表示模型
    10.1 核心结构
    10.2 示例

11. 引用与依赖管理
    11.1 依赖属性
    11.2 未解析依赖处理（v0.3 新增）
    11.3 示例

12. 采纳、映射与偏差模型
    12.1 设计思想
    12.2 核心概念
    12.3 跨规范关系
    12.4 示例

13. 版本与生命周期管理
    13.1 版本标识
    13.2 生命周期状态

14. Git 式治理模型
    14.1 映射关系
    14.2 语义差异模型

15. SHACL 验证层（v0.3 调整）
    15.1 设计思想
    15.2 验证文件结构
    15.3 来源追溯验证（v0.3 调整）

16. 发布与分发
    16.1 Package URL
    16.2 Package Content Types

17. 完整示例（v0.3 更新）
    17.1 文件列表
    17.2 manifest.ttl
    17.3 metadata.ttl
    17.4 ontology-context.ttl
    17.5 clauses.ttl
    17.6 requirements.ttl
    17.7 constraints.ttl
    17.8 validation.ttl

18. 版本变更记录


## 1. 引言

### 1.1 背景

工业世界的运行依赖于海量的标准、规范、法规和行业惯例。这些文档目前主要以 PDF、Word、HTML 等人类可读格式存在，**机器无法直接理解、推理和比较**。

随着 AI 驱动的智能制造、自动采购和合规验证的兴起，工业界需要一种**机器可读、可版本管理、可推理的规范语义表达格式**。

leleby Normative Semantic Package Specification 正是为此而生。

### 1.2 核心定义

> **leleby Normative Semantic Package（规范语义包）是对具有规范效力的文件（含标准、规范、法规、行业惯例、企业技术规范等）进行结构化、语义化和版本化封装后的语义资产。**

它是连接现实世界规范文件与 leleby 语义基础设施的桥梁：

```
现实规范文件（PDF/Word/HTML）
        │
        │ 语义提取（Semantic Extraction）
        ▼
leleby Normative Semantic Package（.ttl + manifest）
        │
        │ 加载
        ▼
leleby 语义基础设施（Ontology + Knowledge Graph）
        │
        ▼
AI 推理 / 自动采购 / 合规判断 / 智能选型
```

### 1.3 v0.3 与 v0.2 的核心差异

| 维度 | v0.2 | v0.3 |
|---|---|---|
| **Requirement 第三元** | `requiresCharacteristic` → `lbo:Characteristic` | **升级为 `hasTargetElement` → `lreq:SemanticTarget`**（支持特性/功能/接口/关系/结构/过程/服务） |
| **Clause-Requirement 关系** | `defines`（条款拥有要求） | **调整为 `references` / `establishesBinding`**（要求是独立语义对象） |
| **语义完整性** | 未定义 | **新增 `SemanticCompletenessStatus` 及 `unresolvedDependency`** |
| **来源追溯** | `derivedFromClause` | **扩展为 `derivedFromNormativeSource`**（支持 Clause/Annex/TechnicalNote/EnterpriseDefinition） |
| **Constraint 目标** | 隐含指向 Characteristic | **显式对齐 `lcon:ConstraintTarget`（含 RelationshipTarget）** |
| **requirements.ttl 定位** | 未明确 | **明确声明：存储 Requirement 实例，非 Ontology 定义** |
| **提取状态** | 未定义 | **新增 `semanticExtractionStatus`** |
| **依赖架构** | v1.1 | **升级至 v1.2**（含 Demand 边界） |

### 1.4 关键定位声明

> **Normative Semantic Package 不是 Ontology，而是 Ontology 的实例化应用。**
>
> - `lbo:` 定义"规范是什么"（概念层）
> - `lsp:NormativeSemanticPackage` 定义"某个具体规范如何被语义化发布"（资产/实例层）

**语义包的四层分类：**

```
leleby Normative Semantic Package
    │
    ├── Standard Package（标准包——IEC/ISO/GB 等）
    │
    ├── Regulation Package（法规包——EU/CFR 等）
    │
    ├── Industry Practice Package（行业惯例包）
    │
    └── Enterprise Specification Package（企业规范包——PPM 等）
```


## 2. 目的与范围

### 2.1 解决的核心问题

| 问题 | 现状 | leleby 方案 |
|---|---|---|
| 规范不可计算 | PDF 中的要求需要人工阅读和解释 | 语义化表达为机器可推理的 RDF 三元组 |
| 规范版本混乱 | 新旧版本并存，差异不清晰 | Git 式版本管理，差异可追溯 |
| 规范追溯困难 | 产品符合某规范，但无法证明 | 每条 Requirement 可追溯到具体条款 |
| 规范依赖不透明 | 规范 A 引用规范 B，但关系未建模 | 显式依赖声明，版本固定或浮动 |
| 跨规范映射困难 | 同一要求在 IEC 和 GB 中表达不同 | 通过 Adoption/Mapping 层建立等价关系 |
| **语义完整性不可知（v0.3 新增）** | 引用的规范未语义化，但无标记 | **显式标记 `IncompleteDependency` 状态** |
| **要求不属于单一条款（v0.3 新增）** | 同一要求可被多个规范引用 | **Requirement 作为独立语义对象，可被多个 Clause 引用** |

### 2.2 核心能力

**2.2.1 规范知识图谱化**

将规范文件转化为可查询、可推理的知识图谱：

```
NormativeDocument
    │
    ├── contains → Clause
    │       │
    │       └── references / establishesBinding → Requirement（v0.3 调整）
    │               │
    │               ├── hasTargetElement → SemanticTarget（v0.3 升级）
    │               ├── hasConstraint → Constraint（含 ConstraintTarget）
    │               └── verifiedBy → TestMethod
    │
    ├── references → NormativeDocument（依赖关系）
    │
    └── hasEdition → Edition（版本关系）
```

**2.2.2 AI 合规推理**

使 AI 能够判断产品是否符合规范：

```
Product Specification（产品规格）
        │
        │ 与 Requirement 对比
        ▼
Compliance Judgment（符合性判断）
        │
        └── 输出：符合 / 不符合 / 部分符合
```

**2.2.3 规范版本管理**

支持多个版本并存，并明确版本间关系：

```
IEC 60034-1:2012
        │
        ├── supersededBy → IEC 60034-1:2025
        │
IEC 60034-1:2025
        │
        └── supersedes → IEC 60034-1:2012
```

**2.2.4 跨规范映射与对齐**

支持不同规范体系之间的语义映射：

```
IEC 60034-1:2025
        │
        └── hasAdoption → GB/T 755-2025
                └── deviation: +10℃ temperature
```


## 3. 设计原则

### 3.1 规范身份优先原则

**原则：** 规范首先是一个法律/行政文件，必须保留其完整的文档身份信息。

### 3.2 语义内容分离原则

**原则：** 规范的文档层与语义层分离，但通过引用保持关联。

### 3.3 版本不可变原则

**原则：** 语义包发布后，其内容不可修改。任何变更需发布新版本。

### 3.4 语义提取可追溯原则

**原则：** 每条语义（Requirement、Constraint、TestMethod）必须可追溯到原始文档的具体来源。

### 3.5 最小包原则

**原则：** 一个语义包应只包含一个独立规范的内容。规范间的引用通过 `dependsOn` 声明。

### 3.6 Ontology 引用原则

**原则：** 语义包不定义新的 Ontology 类。所有类和关系来自 `llb:` 和 `lbo:` 命名空间。`requirements.ttl` 存储的是 `lreq:Requirement` 的实例，而非定义。

### 3.7 规范文件与版本分离原则

**原则：** 规范的核心身份（NormativeDocument）与其版本（Edition）分离。

### 3.8 跨规范可映射原则

**原则：** 不同规范体系之间的内容应可建立映射关系。

### 3.9 语义完整性可度量原则（v0.3 新增）

**原则：** 语义包的完整性状态必须显式标记。当包引用的外部规范尚未被语义化时，不能假称完整，必须标记为 `IncompleteDependency` 并记录未解析的依赖项。

### 3.10 要求是独立语义对象原则（v0.3 新增）

**原则：** Requirement 不是 Clause 的私有属性，而是独立的语义对象。同一个 Requirement 可被多个 Clause、多个规范引用。Clause 通过 `references` 或 `establishesBinding` 与 Requirement 关联，而非 `defines`。


## 4. 语义包架构

### 4.1 顶层分类体系

```turtle
lsp:NormativeSemanticPackage
    rdf:type owl:Class ;
    rdfs:subClassOf llb:InformationEntity ;
    rdfs:label "NormativeSemanticPackage" ;
    rdfs:comment "规范语义包的顶层抽象" .

lsp:StandardPackage
    rdfs:subClassOf lsp:NormativeSemanticPackage ;
    rdfs:label "StandardPackage" ;
    rdfs:comment "标准语义包（IEC/ISO/GB 等）" .

lsp:RegulationPackage
    rdfs:subClassOf lsp:NormativeSemanticPackage ;
    rdfs:label "RegulationPackage" ;
    rdfs:comment "法规语义包（EU/CFR 等）" .

lsp:IndustryPracticePackage
    rdfs:subClassOf lsp:NormativeSemanticPackage ;
    rdfs:label "IndustryPracticePackage" ;
    rdfs:comment "行业惯例语义包" .

lsp:EnterpriseSpecificationPackage
    rdfs:subClassOf lsp:NormativeSemanticPackage ;
    rdfs:label "EnterpriseSpecificationPackage" ;
    rdfs:comment "企业规范语义包（PPM 等）" .
```

### 4.2 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Normative Semantic Package                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Package Manifest（清单文件）                                       │   │
│  │  - packageId, version, status, packageType                         │   │
│  │  - issuedBy, approvedBy, effectiveDate                             │   │
│  │  - ontologyDependencies                                            │   │
│  │  - dependsOn（规范依赖）                                            │   │
│  │  - semanticCompletenessStatus（v0.3 新增）                        │   │
│  │  - unresolvedDependencies（v0.3 新增）                            │   │
│  │  - changeLog                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Ontology Context                                                   │   │
│  │  - owl:imports 声明                                               │   │
│  │  - 命名空间绑定                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Document Metadata（文档元数据）                                    │   │
│  │  - documentId, edition, title                                      │   │
│  │  - issuingBody, approvalDate, effectiveDate, withdrawDate          │   │
│  │  - jurisdiction, status, officialFile                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Semantic Content（语义内容）                                      │   │
│  │  ├── Clauses（条款结构——含提取状态）                               │   │
│  │  ├── Requirements（要求实例——使用 SemanticTarget）                 │   │
│  │  ├── Constraints（约束实例——含 ConstraintTarget）                  │   │
│  │  └── Test Methods（测试方法引用）                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Cross-Normative Relations（跨规范关系）                           │   │
│  │  - adopts / adoptedFrom                                            │   │
│  │  - deviatesFrom                                                    │   │
│  │  - equivalentTo / partiallyEquivalentTo                            │   │
│  │  - harmonizedWith                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  SHACL Validation                                                  │   │
│  │  - 节点形状定义                                                    │   │
│  │  - 完整性约束（含来源追溯验证）                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 文件结构

```
IEC-60034-1-2025-Package/
    │
    ├── manifest.ttl           # Package Manifest（含完整性状态）
    ├── metadata.ttl           # 文档元数据
    ├── ontology-context.ttl   # Ontology 上下文
    ├── clauses.ttl            # 条款结构（含提取状态）
    ├── requirements.ttl       # 要求实例（使用 SemanticTarget）
    ├── constraints.ttl        # 约束实例（含 ConstraintTarget）
    ├── testmethods.ttl        # 测试方法引用
    ├── dependencies.ttl       # 依赖与引用
    ├── mappings.ttl           # 跨规范映射
    ├── validation.ttl         # SHACL 验证规则
    ├── changelog.md           # 变更日志（人类可读）
    └── original/
        └── IEC-60034-1-2025.pdf  # 原始规范文件
```

### 4.4 文件内容说明

| 文件 | 内容 | 必选 |
|---|---|---|
| `manifest.ttl` | 包清单（packageId, version, status, completeness, dependencies） | ✅ 必选 |
| `metadata.ttl` | 文档元数据（issuer, dates, jurisdiction） | ✅ 必选 |
| `ontology-context.ttl` | Ontology 导入声明（owl:imports） | ✅ 必选 |
| `clauses.ttl` | 条款层级结构及提取状态 | ✅ 必选 |
| `requirements.ttl` | **Requirement 实例（使用 SemanticTarget）** | ✅ 必选 |
| `constraints.ttl` | **Constraint 实例（含 ConstraintTarget）** | ✅ 必选 |
| `testmethods.ttl` | 测试方法引用 | 条件必选 |
| `dependencies.ttl` | 依赖与引用 | 条件必选 |
| `mappings.ttl` | 跨规范映射 | 可选 |
| `validation.ttl` | SHACL 验证规则 | ✅ 必选 |
| `changelog.md` | 变更日志 | ✅ 必选 |


## 5. Package Manifest 模型

### 5.1 核心类定义

```turtle
lsp:NormativeSemanticPackage
    rdf:type owl:Class ;
    rdfs:subClassOf llb:InformationEntity ;
    rdfs:label "NormativeSemanticPackage" ;
    rdfs:comment "规范语义包的顶级实体" .
```

### 5.2 Manifest 属性

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lsp:packageId` | lsp:NormativeSemanticPackage | xsd:string | 包唯一标识 | 1 |
| `lsp:packageType` | lsp:NormativeSemanticPackage | lsp:PackageType | 包类型 | 1 |
| `lsp:version` | lsp:NormativeSemanticPackage | xsd:string | 语义包版本 | 1 |
| `lsp:status` | lsp:NormativeSemanticPackage | lsp:PackageStatus | 包状态 | 1 |
| `lsp:releaseDate` | lsp:NormativeSemanticPackage | xsd:date | 语义包发布日期 | 1 |
| `lsp:basedOnDocument` | lsp:NormativeSemanticPackage | lbo:NormativeEdition | 基于的规范版本 | 1 |
| `lsp:requiresOntology` | lsp:NormativeSemanticPackage | owl:Ontology | 依赖的 Ontology | 0..* |
| `lsp:dependsOn` | lsp:NormativeSemanticPackage | lsp:NormativeSemanticPackage | 依赖的其他语义包 | 0..* |
| `lsp:hasManifest` | lsp:NormativeSemanticPackage | lsp:PackageManifest | 关联的清单 | 1 |
| `lsp:hasCompletenessStatus` | lsp:NormativeSemanticPackage | **`lsp:SemanticCompletenessStatus`** | **语义完整性状态（v0.3 新增）** | 1 |
| `lsp:hasUnresolvedDependency` | lsp:NormativeSemanticPackage | **`lsp:UnresolvedDependency`** | **未解析的依赖项（v0.3 新增）** | 0..* |

### 5.3 PackageType

| 值 | 说明 |
|---|---|
| `lsp:Standard` | 标准（IEC/ISO/GB 等） |
| `lsp:Regulation` | 法规（EU/CFR 等） |
| `lsp:IndustryPractice` | 行业惯例 |
| `lsp:EnterpriseSpec` | 企业规范（PPM 等） |

### 5.4 PackageStatus

| 值 | 说明 |
|---|---|
| `lsp:Draft` | 草案中 |
| `lsp:Review` | 审核中 |
| `lsp:Approved` | 已批准 |
| `lsp:Published` | 已发布 |
| `lsp:Superseded` | 已被替代 |
| `lsp:Withdrawn` | 已废止 |

### 5.5 SemanticCompletenessStatus（v0.3 新增）

```turtle
lsp:SemanticCompletenessStatus
    rdf:type owl:Class ;
    rdfs:label "SemanticCompletenessStatus" ;
    rdfs:comment "语义包的完整性状态，用于标记包的语义化完成度和依赖解析状态" .
```

| 值 | 说明 |
|---|---|
| `lsp:Complete` | **完整**：所有引用和依赖均已建模 |
| `lsp:Partial` | **部分**：包本身部分内容已建模，部分未建模 |
| `lsp:IncompleteDependency` | **依赖不完整**：引用的外部规范未被语义化，导致包不完整 |
| `lsp:PendingExtraction` | **待提取**：包内容尚未完全从原始文档提取 |

```turtle
lsp:UnresolvedDependency
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "UnresolvedDependency" ;
    rdfs:comment "未解析的依赖项，记录语义包中未能解析的引用" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lsp:targetReferenceId` | 被引用的规范标识（如 "IEC 60034-1:2025"） | 1 |
| `lsp:referencingClause` | 发起引用的条款号 | 0..1 |
| `lsp:unresolvedReason` | 未解析原因 | 0..1 |
| `lsp:resolvedAt` | 解析时间戳 | 0..1 |

### 5.6 示例

```turtle
@prefix lsp: <https://spec.leleby.org/lsp/> .
@prefix ppm: <https://spec.leleby.org/ppm/> .

ppm:Package
    a lsp:EnterpriseSpecificationPackage ;
    lsp:packageId "PPM-RM-001-v1.0" ;
    lsp:packageType lsp:EnterpriseSpec ;
    lsp:version "1.0.0" ;
    lsp:status lsp:Published ;
    lsp:releaseDate "2026-07-31"^^xsd:date ;
    lsp:basedOnDocument ppm:PPM-RM-001-2026 ;
    lsp:requiresOntology lreq:RequirementOntology ;
    lsp:requiresOntology lbo:ConstraintOntology ;
    lsp:requiresOntology lbo:TestMethodOntology ;
    lsp:hasCompletenessStatus lsp:Complete .
```


## 6. 规范文件表示模型

### 6.1 NormativeDocument（规范文件）

```turtle
lbo:NormativeDocument
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Document ;
    rdfs:label "NormativeDocument" ;
    rdfs:comment "规范的抽象标识，不包含具体版本" .
```

### 6.2 NormativeEdition（规范版本）

```turtle
lbo:NormativeEdition
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Document ;
    rdfs:label "NormativeEdition" ;
    rdfs:comment "规范的具体版本" .
```

### 6.3 属性与关系

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo:documentId` | lbo:NormativeDocument | xsd:string | 规范编号 | 1 |
| `lbo:documentTitle` | lbo:NormativeDocument | xsd:string | 规范名称 | 1 |
| `lbo:documentType` | lbo:NormativeDocument | lsp:PackageType | 规范类型 | 1 |
| `lbo:edition` | lbo:NormativeEdition | xsd:string | 版本标识 | 1 |
| `lbo:issuingBody` | lbo:NormativeEdition | lbo:Organization | 发布机构 | 1 |
| `lbo:approvalDate` | lbo:NormativeEdition | xsd:date | 批准日期 | 1 |
| `lbo:effectiveDate` | lbo:NormativeEdition | xsd:date | 实施日期 | 1 |
| `lbo:withdrawDate` | lbo:NormativeEdition | xsd:date | 废止日期 | 0..1 |
| `lbo:jurisdiction` | lbo:NormativeEdition | lbo:Jurisdiction | 适用区域 | 0..1 |
| `lbo:status` | lbo:NormativeEdition | lbo:NormativeStatus | 规范状态 | 1 |
| `lbo:supersedes` | lbo:NormativeEdition | lbo:NormativeEdition | 替代的旧版本 | 0..1 |
| `lbo:supersededBy` | lbo:NormativeEdition | lbo:NormativeEdition | 被新版本替代 | 0..1 |

### 6.4 示例

```turtle
ppm:PPM-RM-001
    a lbo:NormativeDocument ;
    lbo:documentId "PPM-RM-001" ;
    lbo:documentTitle "Rotary Motion Module Specification" ;
    lbo:documentType lsp:EnterpriseSpec .

ppm:PPM-RM-001-2026
    a lbo:NormativeEdition ;
    lbo:edition "2026" ;
    lbo:issuingBody ppm:PPM_Committee ;
    lbo:approvalDate "2026-07-30"^^xsd:date ;
    lbo:effectiveDate "2026-08-01"^^xsd:date .
```


## 7. 条款语义模型（v0.3 调整）

### 7.1 NormativeClause

```turtle
lbo:NormativeClause
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "NormativeClause" ;
    rdfs:comment "规范的条款/章节，是标准文档的结构组织单元，同时作为要求的来源追溯节点" .
```

### 7.2 属性

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo:clauseNumber` | lbo:NormativeClause | xsd:string | 条款编号 | 1 |
| `lbo:clauseTitle` | lbo:NormativeClause | xsd:string | 条款标题 | 0..1 |
| `lbo:clauseText` | lbo:NormativeClause | xsd:string | 条款原文 | 1 |
| `lbo:hasParentClause` | lbo:NormativeClause | lbo:NormativeClause | 父条款 | 0..1 |
| `lbo:hasChildClause` | lbo:NormativeClause | lbo:NormativeClause | 子条款 | 0..* |
| **`lsp:semanticExtractionStatus`** | lbo:NormativeClause | **`lsp:ExtractionStatus`** | **语义提取状态（v0.3 新增）** | 0..1 |

### 7.3 Clause-Requirement 关系（v0.3 调整）

**v0.3 核心变更：** Clause 不“拥有”Requirement。Requirement 是独立的语义对象，Clause 通过以下方式与 Requirement 关联：

| 关系 | 说明 | 方向 |
|---|---|---|
| `lbo:referencesRequirement` | 条款引用某要求（推荐） | Clause → Requirement |
| `lbo:establishesBinding` | 条款建立与某要求的绑定（等同于 defines 的弱化版） | Clause → Requirement |
| `lsp:isSourceFor` | 条款作为某要求的来源（反向关系） | Clause → Requirement |

> **注意：** `lbo:defines` 关系在 v0.3 中被弱化，不再作为 Clause 与 Requirement 的主要关系。这反映了“Requirement 是独立语义对象，可被多个 Clause/规范引用”的设计原则。

```turtle
# 推荐使用
lbo:referencesRequirement
    rdf:type owl:ObjectProperty ;
    rdfs:domain lbo:NormativeClause ;
    rdfs:range lreq:Requirement ;
    rdfs:label "referencesRequirement" ;
    rdfs:comment "条款引用的要求（要求是独立对象）" .

# 保留用于向后兼容，但语义调整为“建立绑定”
lbo:establishesBinding
    rdf:type owl:ObjectProperty ;
    rdfs:domain lbo:NormativeClause ;
    rdfs:range lreq:Requirement ;
    rdfs:label "establishesBinding" ;
    rdfs:comment "条款与要求建立绑定关系（弱化版 defines）" .
```

### 7.4 语义提取状态（v0.3 新增）

```turtle
lsp:ExtractionStatus
    rdf:type owl:Class ;
    rdfs:label "ExtractionStatus" ;
    rdfs:comment "条款的语义提取状态" .
```

| 值 | 说明 |
|---|---|
| `lsp:NotExtracted` | 未提取 |
| `lsp:PartiallyExtracted` | 部分提取 |
| `lsp:Extracted` | 已提取 |
| `lsp:Reviewed` | 已审核 |

### 7.5 示例

```turtle
ppm:Clause_4_1
    a lbo:NormativeClause ;
    lbo:clauseNumber "4.1" ;
    lbo:clauseTitle "RM42-General" ;
    lbo:clauseText "The RM42-General capability class covers 50-300W power range..." ;
    lsp:semanticExtractionStatus lsp:Extracted ;
    lbo:referencesRequirement ppm:R_Power_001 ;
    lbo:referencesRequirement ppm:R_Efficiency_001 .
```


## 8. 要求语义模型（v0.3 升级）

### 8.1 六元要求模型（v0.3 更新）

**v0.3 核心变更：** 第三元从 `Characteristic` 升级为 `SemanticTarget`。

每个 Requirement 应尽可能包含以下六个维度的语义：

```
Requirement =
    Authority（谁提出的——通过 Source 推理获得）
  + Scope（适用于什么范围——产品类型/市场/生命周期/环境）
  + SemanticTarget（要求什么目标元素——特性/功能/接口/关系/结构/过程/服务）
  + Condition（在什么条件下有效）
  + Constraint（必须满足什么约束——含 ConstraintTarget）
  + Obligation（强制/推荐/可选）
```

**属性定义（v0.3 更新）：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| **`lreq:hasTargetElement`** | lreq:Requirement | **`lreq:SemanticTarget`** | **要求的目标元素（v0.3 升级）** | 1 |
| `lreq:hasScope` | lreq:Requirement | `lreq:TargetScope` | 适用范围 | 1 |
| `lreq:hasConstraint` | lreq:Requirement | `lbo:Constraint` | 约束（含 ConstraintTarget） | 1 |
| `lreq:underContext` | lreq:Requirement | `lbo:EvaluationContext` | 生效条件 | 0..* |
| `lreq:hasObligation` | lreq:Requirement | `lbo:ObligationLevel` | 强制程度 | 1 |
| `lreq:derivedFromSource` | lreq:Requirement | **`lsp:NormativeSource`** | **来源（v0.3 扩展）** | 1..* |
| `lreq:hasAuthority` | lreq:Requirement | `lreq:RequirementAuthority` | 来源权威（推理属性） | 0..1 |

### 8.2 SemanticTarget 类型体系（v0.3 升级）

```turtle
lreq:SemanticTarget
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "SemanticTarget" ;
    rdfs:comment "要求真正约束的目标元素的抽象基类" .
```

**SemanticTarget 类型体系：**

```
SemanticTarget
    ├── lreq:CharacteristicTarget（特性）
    │       └── targetCharacteristic → lbo-core:Characteristic
    ├── lreq:FunctionTarget（功能）
    │       └── targetFunction → lcap:Function / lprod:ProductFeature
    ├── lreq:InterfaceTarget（接口）
    │       └── targetInterface → lprod:Interface
    ├── lreq:RelationshipTarget（关系）
    │       └── targetRelationship → lprod:ProductRelationship
    ├── lreq:StructureTarget（结构）
    │       └── targetStructure → lprod:Structure
    ├── lreq:ProcessTarget（过程）
    │       └── targetProcess → lprod:Process
    └── lreq:ServiceTarget（服务）
            └── targetService → lprod:Service
```

**使用示例（v0.3 升级）：**

```turtle
# 特性目标（v0.2 的 requiresCharacteristic 升级）
ppm:Target_Power
    a lreq:CharacteristicTarget ;
    lreq:targetCharacteristic lbo:Power .

# 功能目标（v0.3 新增）
ppm:Target_OverloadProtection
    a lreq:FunctionTarget ;
    lreq:targetFunction ppm:OverloadProtectionFeature .

# 关系目标（v0.3 新增——支持结构约束，如“4个工作轮胎”）
ppm:Target_WorkingWheel
    a lreq:RelationshipTarget ;
    lreq:targetRelationshipType lprod:PartRelationship ;
    lreq:requiredRole lprod:WorkingPart ;
    lreq:requiredCardinality 4 .
```

### 8.3 要求提取映射

| 规范文本要素 | leleby 概念 |
|---|---|
| "shall" / "must" | `lbo:Mandatory` |
| "should" | `lbo:Required` |
| "may" | `lbo:Optional` |
| 数值范围（如 "-20℃ to 70℃"） | `lbo:RangeConstraint` |
| 带条件的数值（如 "when at rated load"） | `lbo:ConditionalConstraint` |
| 允许值列表（如 "IP65, IP66"） | `lbo:EnumerationConstraint` |
| 功能要求（如 "shall have overload protection"） | `lreq:FunctionTarget` |
| 结构要求（如 "shall have 4 working wheels"） | `lreq:RelationshipTarget` |

### 8.4 要求作为独立语义对象（v0.3 新增）

> **Normative Semantic Package 中的 `requirements.ttl` 存储的是 `lreq:Requirement` 的实例，而非 Ontology 定义。**
>
> - Requirement 的定义在 `lbo:RequirementOntology` 中
> - Package 中的 Requirement 是遵循该 Ontology 的实例化个体
> - 同一个 Requirement 实例可被多个 Clause 引用

```turtle
# 正确：Package 中实例化 Requirement
ppm:R_Power_001
    a lreq:Requirement ;  # 引用 Ontology 中的类
    lreq:hasRequirementIdentifier "R-POWER-001" ;
    lreq:hasTargetElement ppm:Target_Power ;
    ...

# 错误：Package 中不应定义新的 Requirement 子类
# ppm:MyRequirement rdfs:subClassOf lreq:Requirement .  # ❌ 禁止
```

### 8.5 示例（v0.3 升级）

```turtle
# 适用范围
ppm:Scope_RM42
    a lreq:TargetScope ;
    lreq:hasObjectScope ppm:RM42-General .

# 特性目标
ppm:Target_Power
    a lreq:CharacteristicTarget ;
    lreq:targetCharacteristic lbo:Power .

# 约束
ppm:C_Power_Range
    a lbo:RangeConstraint ;
    lbo:minValue [ llb:hasNumericValue "50"^^xsd:double ; llb:hasUnit llb:Watt ] ;
    lbo:maxValue [ llb:hasNumericValue "300"^^xsd:double ; llb:hasUnit llb:Watt ] .

# 要求实例（v0.3：使用 hasTargetElement）
ppm:R_Power_001
    a lreq:Requirement ;
    lreq:hasRequirementIdentifier "R-POWER-001" ;
    lreq:hasRequirementName "RM42-General 功率范围要求" ;
    lreq:hasScope ppm:Scope_RM42 ;
    lreq:hasTargetElement ppm:Target_Power ;  # v0.3 升级
    lreq:hasConstraint ppm:C_Power_Range ;
    lreq:underCondition ppm:NormalOperation ;
    lreq:hasObligation lbo:Mandatory ;
    lreq:derivedFromSource ppm:Clause_4_1 .  # v0.3 扩展
```


## 9. 约束表示模型（v0.3 升级）

### 9.1 约束类型体系

```
lbo:Constraint
    │
    ├── lbo:ValueConstraint（值约束）
    │       ├── lbo:RangeConstraint（范围）
    │       ├── lbo:ToleranceConstraint（公差）
    │       ├── lbo:EnumerationConstraint（枚举）
    │       ├── lbo:ExactConstraint（精确）
    │       └── lbo:ComparisonConstraint（比较）
    │
    ├── lbo:ConditionalConstraint（条件约束）
    │       └── IF condition THEN constraint
    │
    ├── lbo:LogicalConstraint（逻辑约束）
    │       ├── lbo:AndConstraint
    │       ├── lbo:OrConstraint
    │       └── lbo:NotConstraint
    │
    ├── lbo:StatisticalConstraint（统计约束）
    │
    ├── lbo:TemporalConstraint（时间约束）
    │
    └── lbo:GeographicConstraint（地理约束）
```

### 9.2 ConditionalConstraint

```turtle
lbo:ConditionalConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lbo:Constraint ;
    rdfs:label "ConditionalConstraint" ;
    rdfs:comment "带条件的约束：IF condition THEN constraint" .
```

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo:condition` | lbo:ConditionalConstraint | lreq:ConditionExpression | 触发条件 |
| `lbo:thenConstraint` | lbo:ConditionalConstraint | lbo:Constraint | 条件满足时的约束 |
| `lbo:elseConstraint` | lbo:ConditionalConstraint | lbo:Constraint | 条件不满足时的约束（可选） |

### 9.3 LogicalConstraint

```turtle
lbo:LogicalConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lbo:Constraint ;
    rdfs:label "LogicalConstraint" ;
    rdfs:comment "逻辑组合约束" .

lbo:AndConstraint
    rdfs:subClassOf lbo:LogicalConstraint .

lbo:OrConstraint
    rdfs:subClassOf lbo:LogicalConstraint .

lbo:NotConstraint
    rdfs:subClassOf lbo:LogicalConstraint .
```

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo:operands` | lbo:LogicalConstraint | lbo:Constraint | 操作数列表 |

### 9.4 Constraint Target 同步（v0.3 新增）

**v0.3 核心变更：** Constraint 的目标与 Requirement 的 `SemanticTarget` 对齐，通过 `lcon:constrains` 指向 `lcon:ConstraintTarget`。

```
lbo:Constraint
    │
    └── lcon:constrains → lcon:ConstraintTarget
            │
            ├── lcon:CharacteristicTarget → lbo-core:Characteristic
            ├── lcon:FunctionTarget → lcap:Function
            ├── lcon:InterfaceTarget → lprod:Interface
            ├── lcon:RelationshipTarget → lprod:ProductRelationship
            ├── lcon:StructureTarget → lprod:Structure
            └── lcon:ProcessTarget → lprod:Process
```

**语义对齐要求：**

> Requirement 的 `hasTargetElement`（指向 `lreq:SemanticTarget`）与其引用的 Constraint 的 `constrains`（指向 `lcon:ConstraintTarget`）应指向同一类工程元素。

### 9.5 示例

```turtle
# 特性约束
ppm:C_Power_Range
    a lbo:RangeConstraint ;
    lbo:minValue [ llb:hasNumericValue "50"^^xsd:double ; llb:hasUnit llb:Watt ] ;
    lbo:maxValue [ llb:hasNumericValue "300"^^xsd:double ; llb:hasUnit llb:Watt ] .

# 条件约束
ppm:C_Temp_Altitude
    a lbo:ConditionalConstraint ;
    lbo:condition [
        a lreq:ConditionExpression ;
        lreq:hasProperty lbo:Altitude ;
        lreq:hasOperator lreq:GreaterThan ;
        lreq:hasValue "3000"^^xsd:double
    ] ;
    lbo:thenConstraint ppm:C_Temp_HighAltitude ;
    lbo:elseConstraint ppm:C_Temp_Normal .

# 逻辑约束
ppm:C_Env_And
    a lbo:AndConstraint ;
    lbo:operands (ppm:C_Temp_Range ppm:C_Humidity_Range) .
```


## 10. 测试方法表示模型

### 10.1 核心结构

测试方法默认引用自 `lbo:TestMethod`（Core Ontology），而非在 Package 中定义新类。

```turtle
lbo:TestMethod
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Document ;
    rdfs:label "TestMethod" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo:testMethodId` | 测试方法标识 | 1 |
| `lbo:testMethodName` | 测试方法名称 | 1 |
| `lbo:testProcedure` | 测试步骤 | 1 |
| `lbo:testEquipment` | 测试设备要求 | 0..* |
| `lbo:testCondition` | 测试条件 | 0..* |
| `lbo:acceptanceCriteria` | 接收准则 | 1 |

### 10.2 示例

```turtle
ppm:Test_Power_001
    a lbo:TestMethod ;
    lbo:testMethodId "POWER-001" ;
    lbo:testMethodName "功率测试方法" ;
    lbo:testProcedure "1. 将被测电机连接至功率分析仪..." ;
    lbo:testCondition "环境温度 25±2℃, 额定负载" ;
    lbo:acceptanceCriteria "实测功率在 50W-300W 范围内" .
```


## 11. 引用与依赖管理

### 11.1 依赖属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lsp:dependsOn` | lsp:NormativeSemanticPackage | lsp:NormativeSemanticPackage | 依赖的其他语义包 |
| `lsp:referenceVersion` | lsp:PackageDependency | xsd:string | 特定版本（固定依赖） |
| `lsp:referenceLatest` | lsp:PackageDependency | xsd:boolean | 是否跟随最新版本 |

### 11.2 未解析依赖处理（v0.3 新增）

当 Package 依赖的外部规范尚未被语义化时：

```turtle
ppm:Package
    lsp:hasCompletenessStatus lsp:IncompleteDependency ;
    lsp:hasUnresolvedDependency [
        a lsp:UnresolvedDependency ;
        lsp:targetReferenceId "IEC 60034-1:2025" ;
        lsp:referencingClause "4.3" ;
        lsp:unresolvedReason "Referenced standard not yet modeled in knowledge base"
    ] .
```

### 11.3 示例

```turtle
ppm:Package
    lsp:dependsOn [
        a lsp:PackageDependency ;
        lsp:package iec:IEC60034_5_2021 ;
        lsp:referenceVersion "1.0.0"
    ] .
```


## 12. 采纳、映射与偏差模型

### 12.1 设计思想

规范之间的关系不仅是"引用"，还包括"采纳"、"等同"、"偏差"、"协调"等。这些关系对跨规范合规推理至关重要。

### 12.2 核心概念

```turtle
lbo:CrossNormativeRelation
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "CrossNormativeRelation" .
```

| 关系类型 | 说明 |
|---|---|
| `lbo:adopts` | 采纳某规范（含偏差） |
| `lbo:adoptedFrom` | 被某规范采纳 |
| `lbo:equivalentTo` | 完全等效 |
| `lbo:partiallyEquivalentTo` | 部分等效 |
| `lbo:deviatesFrom` | 偏离某规范 |
| `lbo:harmonizedWith` | 与某规范协调一致 |

### 12.3 跨规范关系属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo:sourceNormative` | lbo:CrossNormativeRelation | lbo:NormativeEdition | 源规范 |
| `lbo:targetNormative` | lbo:CrossNormativeRelation | lbo:NormativeEdition | 目标规范 |
| `lbo:relationType` | lbo:CrossNormativeRelation | lbo:CrossNormativeRelationType | 关系类型 |
| `lbo:hasDeviation` | lbo:CrossNormativeRelation | lbo:Deviation | 偏差描述 |
| `lbo:scope` | lbo:CrossNormativeRelation | xsd:string | 适用范围 |

### 12.4 示例

```turtle
lsp:GB_T_755_2025
    a lbo:CrossNormativeRelation ;
    lbo:sourceNormative gb:GB_T_755_2025 ;
    lbo:targetNormative iec:IEC60034_1_2025 ;
    lbo:relationType lbo:adopts ;
    lbo:hasDeviation [
        a lbo:Deviation ;
        lbo:deviationDescription "温度限值提高10℃以适应中国南方气候" ;
        lbo:affectedClauses ("8.4.2" "8.4.3")
    ] ;
    lbo:scope "中国国内市场" .
```


## 13. 版本与生命周期管理

### 13.1 版本标识

语义包版本遵循语义化版本规范：

```
Major.Minor.Patch

- Major: 不兼容的语义变更
- Minor: 新增语义内容
- Patch: 勘误修正
```

### 13.2 生命周期状态

```
Draft（草案）
    │
    ▼
Review（审核）
    │
    ▼
Approved（批准）
    │
    ▼
Published（已发布）← 唯一对外可用的状态
    │
    ├── → Superseded（已被替代）
    │
    └── → Withdrawn（已废止）
```


## 14. Git 式治理模型

### 14.1 映射关系

| Git 概念 | leleby 对应 |
|---|---|
| Repository | Normative Repository（规范仓库） |
| Commit | Semantic Change（语义变更） |
| Tag | Official Version（正式版本） |
| Branch | Adoption Context（采用上下文） |
| Diff | Semantic Difference（语义差异） |
| Signature | Approval（批准签名） |

### 14.2 语义差异模型

```turtle
lsp:SemanticDiff
    rdf:type owl:Class ;
    rdfs:label "SemanticDiff" ;
    rdfs:comment "两个语义包版本之间的差异" .
```

| 属性 | 说明 |
|---|---|
| `lsp:fromPackage` | 源版本 |
| `lsp:toPackage` | 目标版本 |
| `lsp:diffType` | 差异类型（add/modify/delete） |
| `lsp:affectedEntity` | 影响的实体 |
| `lsp:changeDescription` | 变更描述 |
| `lsp:impact` | 变更影响（stricter/looser/neutral） |

**示例：**

```turtle
lsp:IEC_Temp_Diff
    a lsp:SemanticDiff ;
    lsp:fromPackage iec:IEC60034_1_2017 ;
    lsp:toPackage iec:IEC60034_1_2025 ;
    lsp:affectedEntity iec:R_Temp_001 ;
    lsp:diffType lsp:Modify ;
    lsp:changeDescription "温度限值从150℃降低至155℃" ;
    lsp:impact lsp:Stricter .
```


## 15. SHACL 验证层（v0.3 调整）

### 15.1 设计思想

每个语义包应包含 SHACL 验证规则，确保：

1. 包内数据的完整性（必填字段）
2. 数据格式正确性（数据类型、基数）
3. 语义约束（如 Requirement 必须有 `derivedFromSource`）

### 15.2 验证文件结构

`validation.ttl` 应包含：

```turtle
# Requirement 必须有关键属性（v0.3 升级）
lsp:RequirementShape
    a sh:NodeShape ;
    sh:targetClass lreq:Requirement ;
    sh:property [
        sh:path lreq:hasRequirementIdentifier ;
        sh:minCount 1 ;
        sh:message "每个 Requirement 必须有标识符"
    ] ;
    sh:property [
        sh:path lreq:hasTargetElement ;
        sh:minCount 1 ;
        sh:message "每个 Requirement 必须有目标元素（SemanticTarget）"
    ] ;
    sh:property [
        sh:path lreq:derivedFromSource ;
        sh:minCount 1 ;
        sh:message "每个 Requirement 必须追溯到具体来源（NormativeSource）"
    ] .

# Constraint 必须有值
lsp:ConstraintShape
    a sh:NodeShape ;
    sh:targetClass lbo:Constraint ;
    sh:or (
        [ sh:path lbo:minValue ; sh:minCount 1 ]
        [ sh:path lbo:maxValue ; sh:minCount 1 ]
        [ sh:path lbo:nominalValue ; sh:minCount 1 ]
        [ sh:path lbo:allowedValues ; sh:minCount 1 ]
        [ sh:path lbo:condition ; sh:minCount 1 ]
    ) ;
    sh:message "Constraint 必须有值定义" .
```

### 15.3 来源追溯验证（v0.3 调整）

**v0.3 核心变更：** `derivedFromClause` 改为更通用的 `derivedFromSource`，支持多种来源类型。

```turtle
lsp:NormativeSource
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "NormativeSource" ;
    rdfs:comment "要求的规范性来源的抽象基类，可以是 Clause、Annex、TechnicalNote 或 EnterpriseDefinition" .

lsp:ClauseSource
    rdfs:subClassOf lsp:NormativeSource ;
    rdfs:label "ClauseSource" ;
    rdfs:comment "条款来源" .

lsp:AnnexSource
    rdfs:subClassOf lsp:NormativeSource ;
    rdfs:label "AnnexSource" ;
    rdfs:comment "附录来源" .

lsp:TechnicalNoteSource
    rdfs:subClassOf lsp:NormativeSource ;
    rdfs:label "TechnicalNoteSource" ;
    rdfs:comment "技术注释来源" .

lsp:EnterpriseDefinitionSource
    rdfs:subClassOf lsp:NormativeSource ;
    rdfs:label "EnterpriseDefinitionSource" ;
    rdfs:comment "企业规范定义来源" .
```

```turtle
# 验证：Requirement 必须追溯到 NormativeSource
lsp:RequirementSourceTraceShape
    a sh:NodeShape ;
    sh:targetClass lreq:Requirement ;
    sh:property [
        sh:path lreq:derivedFromSource ;
        sh:minCount 1 ;
        sh:nodeKind sh:IRI ;
        sh:class lsp:NormativeSource ;
        sh:message "derivedFromSource 必须指向 NormativeSource 的实例"
    ] .
```


## 16. 发布与分发

### 16.1 Package URL

规范语义包通过标准 URL 发布：

```
https://spec.leleby.org/package/{type}/{documentId}/{edition}/

示例：
https://spec.leleby.org/package/standard/iec/IEC-60034-1/2025/
https://spec.leleby.org/package/enterprise/ppm/PPM-RM-001/v1.0/
```

### 16.2 Package Content Types

| 文件 | Content-Type | 说明 |
|---|---|---|
| `manifest.ttl` | text/turtle | 包清单（含完整性状态） |
| `metadata.ttl` | text/turtle | 元数据 |
| `ontology-context.ttl` | text/turtle | Ontology 上下文 |
| `clauses.ttl` | text/turtle | 条款（含提取状态） |
| `requirements.ttl` | text/turtle | 要求（使用 SemanticTarget） |
| `constraints.ttl` | text/turtle | 约束（含 ConstraintTarget） |
| `validation.ttl` | text/turtle | SHACL 验证 |


## 17. 完整示例（v0.3 更新）

### 17.1 文件列表

```
PPM-RM-001-v1.0-Package/
    ├── manifest.ttl
    ├── metadata.ttl
    ├── ontology-context.ttl
    ├── clauses.ttl
    ├── requirements.ttl
    ├── constraints.ttl
    ├── testmethods.ttl
    ├── dependencies.ttl
    ├── mappings.ttl
    ├── validation.ttl
    ├── changelog.md
    └── original/
        └── PPM-RM-001-v1.0.pdf
```

### 17.2 manifest.ttl（v0.3 更新）

```turtle
@prefix lsp: <https://spec.leleby.org/lsp/> .
@prefix ppm: <https://spec.leleby.org/ppm/> .

ppm:Package
    a lsp:EnterpriseSpecificationPackage ;
    lsp:packageId "PPM-RM-001-v1.0" ;
    lsp:packageType lsp:EnterpriseSpec ;
    lsp:version "1.0.0" ;
    lsp:status lsp:Published ;
    lsp:releaseDate "2026-07-31"^^xsd:date ;
    lsp:hasCompletenessStatus lsp:Complete .
```

### 17.3 metadata.ttl

```turtle
ppm:PPM-RM-001
    a lbo:NormativeDocument ;
    lbo:documentId "PPM-RM-001" ;
    lbo:documentTitle "Rotary Motion Module Specification" ;
    lbo:documentType lsp:EnterpriseSpec .

ppm:PPM-RM-001-2026
    a lbo:NormativeEdition ;
    lbo:edition "2026" ;
    lbo:issuingBody ppm:PPM_Committee ;
    lbo:approvalDate "2026-07-30"^^xsd:date ;
    lbo:effectiveDate "2026-08-01"^^xsd:date .
```

### 17.4 ontology-context.ttl

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .

<>
    owl:imports <https://ontology.leleby.org/core/> ;
    owl:imports <https://ontology.leleby.org/requirement/> ;
    owl:imports <https://ontology.leleby.org/constraint/> ;
    owl:imports <https://ontology.leleby.org/testmethod/> .
```

### 17.5 clauses.ttl（v0.3 更新）

```turtle
ppm:Clause_4_1
    a lbo:NormativeClause ;
    lbo:clauseNumber "4.1" ;
    lbo:clauseTitle "RM42-General" ;
    lbo:clauseText "The RM42-General capability class covers 50-300W power range..." ;
    lsp:semanticExtractionStatus lsp:Extracted ;
    lbo:referencesRequirement ppm:R_Power_001 ;
    lbo:referencesRequirement ppm:R_Efficiency_001 .
```

### 17.6 requirements.ttl（v0.3 升级）

```turtle
# Scope
ppm:Scope_RM42
    a lreq:TargetScope ;
    lreq:hasObjectScope ppm:RM42-General .

# SemanticTarget（v0.3：使用 CharacteristicTarget）
ppm:Target_Power
    a lreq:CharacteristicTarget ;
    lreq:targetCharacteristic lbo:Power .

# Requirement（v0.3：使用 hasTargetElement）
ppm:R_Power_001
    a lreq:Requirement ;
    lreq:hasRequirementIdentifier "R-POWER-001" ;
    lreq:hasRequirementName "RM42-General 功率范围要求" ;
    lreq:hasScope ppm:Scope_RM42 ;
    lreq:hasTargetElement ppm:Target_Power ;
    lreq:hasConstraint ppm:C_Power_Range ;
    lreq:underCondition ppm:NormalOperation ;
    lreq:hasObligation lbo:Mandatory ;
    lreq:hasAuthority ppm:PPM_Committee ;
    lreq:derivedFromSource ppm:Clause_4_1 .
```

### 17.7 constraints.ttl（v0.3 同步）

```turtle
ppm:C_Power_Range
    a lbo:RangeConstraint ;
    lbo:minValue [
        llb:hasNumericValue "50"^^xsd:double ;
        llb:hasUnit llb:Watt
    ] ;
    lbo:maxValue [
        llb:hasNumericValue "300"^^xsd:double ;
        llb:hasUnit llb:Watt
    ] .

# 条件约束
ppm:C_Temp_Altitude
    a lbo:ConditionalConstraint ;
    lbo:condition [
        a lreq:ConditionExpression ;
        lreq:hasProperty lbo:Altitude ;
        lreq:hasOperator lreq:GreaterThan ;
        lreq:hasValue "3000"^^xsd:double
    ] ;
    lbo:thenConstraint ppm:C_Temp_HighAltitude ;
    lbo:elseConstraint ppm:C_Temp_Normal .
```

### 17.8 validation.ttl（v0.3 更新）

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .

lsp:RequirementShape
    a sh:NodeShape ;
    sh:targetClass lreq:Requirement ;
    sh:property [
        sh:path lreq:hasRequirementIdentifier ;
        sh:minCount 1 ;
        sh:message "每个 Requirement 必须有标识符"
    ] ;
    sh:property [
        sh:path lreq:hasTargetElement ;
        sh:minCount 1 ;
        sh:message "每个 Requirement 必须有目标元素（SemanticTarget）"
    ] ;
    sh:property [
        sh:path lreq:derivedFromSource ;
        sh:minCount 1 ;
        sh:message "每个 Requirement 必须追溯到具体来源（NormativeSource）"
    ] .

lsp:ConstraintShape
    a sh:NodeShape ;
    sh:targetClass lbo:Constraint ;
    sh:or (
        [ sh:path lbo:minValue ; sh:minCount 1 ]
        [ sh:path lbo:maxValue ; sh:minCount 1 ]
        [ sh:path lbo:nominalValue ; sh:minCount 1 ]
        [ sh:path lbo:allowedValues ; sh:minCount 1 ]
        [ sh:path lbo:condition ; sh:minCount 1 ]
    ) ;
    sh:message "Constraint 必须有值定义" .
```


## 18. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v0.1 | 2026-07-31 | 初始版本 |
| v0.2 | 2026-07-31 | 架构增强版：命名空间调整；四层包类型；六元 Requirement 模型；ConditionalConstraint/LogicalConstraint；跨规范关系模型；SHACL Validation Layer；Semantic Diff |
| **v0.3** | **2026-08-04** | **语义对齐版**：1）Requirement 第三元从 `requiresCharacteristic` 升级为 `hasTargetElement` → `lreq:SemanticTarget`（支持特性/功能/接口/关系/结构/过程/服务）；2）Clause-Requirement 关系从 `defines` 调整为 `referencesRequirement` / `establishesBinding`（要求是独立语义对象）；3）新增 `SemanticCompletenessStatus` 及 `UnresolvedDependency`，支持语义完整性度量；4）来源追溯从 `derivedFromClause` 扩展为 `derivedFromSource` → `NormativeSource`（支持 Clause/Annex/TechnicalNote/EnterpriseDefinition）；5）Constraint 目标同步至 `lcon:ConstraintTarget`；6）明确 `requirements.ttl` 存储 Requirement 实例而非 Ontology 定义；7）新增条款 `semanticExtractionStatus`；8）依赖架构升级至 v1.2 |


*— leleby Normative Semantic Package Specification v0.3 — Semantic Alignment Edition —*