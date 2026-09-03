# leleby Evidence Ontology Specification v0.1

**文档版本：** v0.1 — Core Design Edition（核心设计版）

**文档类型：** 模块本体规范（Module Ontology Specification）

**文档状态：** ⚠️ **候选冻结（Candidate Freeze）** — 核心概念与顶层结构已稳定，待实践验证后正式冻结

**依赖架构：** leleby Ontology Architecture Specification v0.9

**依赖模块：** Core Ontology Specification v0.1 | Measurement Ontology Specification v0.1

**对齐模块：** Requirement Ontology | Specification Ontology | Verification Ontology | Compliance Ontology | Decision Ontology | Capability Ontology | Product Ontology

**命名空间：** `https://ontology.leleby.org/v0.9/evidence/`

**推荐前缀：** `levd`

**目标受众：** 本体工程师、AI Agent 开发者、企业数据架构师、合规与质量管理人员


## 1. 引言

### 1.1 目的

leleby Evidence Ontology 是 leleby 语义基础设施中的**可信语义支撑层（Information Trust Layer）**。它定义了：

- 什么是语义声明（Claim）
- 什么是证据（Evidence）
- 证据如何支撑声明
- 证据的类型、来源、有效期和可信度
- 证据之间的引用和派生关系

**核心定位：**

> Evidence Ontology 描述的是“某个语义声明由什么可追溯信息支持”的通用可信信息基础层。它解决的是 AI Agent 如何判断一个企业、产品、需求、规格、符合性声明是否具有可信依据的问题。

### 1.2 在 leleby 架构中的位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Evidence Ontology 在架构中的位置                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 4: Decision & Action                                        │   │
│  │  决策层：基于带 Evidence 的 Compliance 做决策                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                        │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 3: Verification & Compliance                                │   │
│  │  验证与符合性层：Verification 使用 Evidence 支撑判断结果            │   │
│  │  Compliance Declaration 需要 Evidence 支撑                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                        │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 2: Requirement & Specification                              │   │
│  │  需求与规格层：Requirement Source 需要 Evidence 支撑               │   │
│  │  Specification Claim 需要 Evidence 支撑                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                        │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 1: Enterprise & Product & Capability                        │   │
│  │  企业语义层：Product / Capability 声明需要 Evidence 支撑           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                        │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 0: Evidence Ontology                                        │   │
│  │  证据层：Claim ↔ Evidence 关系，证据类型/来源/有效期/可信度        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Core Foundation & Measurement                                     │   │
│  │  基础层：Entity / InformationEntity / QuantityValue               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 核心职责边界

| Evidence Ontology 支撑 | Evidence Ontology 不负责 |
|------------------------|--------------------------|
| ✅ 需求来源的可追溯性 | ❌ 判断证据的真实性（由 Verification 负责） |
| ✅ 规格声明的依据 | ❌ 证据的自动验证（由 Verification 负责） |
| ✅ 产品/能力声明的可信度 | ❌ 文件管理（证据载体管理由外部系统负责） |
| ✅ 验证结果的可信度 | ❌ 证据存储（由数据存储层负责） |
| ✅ 符合性声明的可信度 | ❌ 认证过程（由 Certification Process 负责） |

**核心原则：** Evidence 只表达“什么证据支持什么声明”，不判断证据真伪。真实性评价属于 Verification / Certification 流程。

### 1.4 本规范的边界

**本规范包含：**

| 模块 | 说明 |
|------|------|
| Claim | 需要被支持的语义声明 |
| Evidence | 支持声明的可追溯信息实体 |
| EvidenceArtifact | 证据的物理/数字载体 |
| EvidenceType | 证据类型（测试报告/认证/声明等） |
| EvidenceSource | 证据来源（机构/组织） |
| EvidenceContext | 证据产生的上下文 |
| EvidenceValidity | 证据的有效期和状态 |
| EvidenceConfidence | 证据的可信等级（基于来源类型） |
| EvidenceRelationship | 证据之间的关系 |

**本规范不包含：**

| 内容 | 归属 |
|------|------|
| 证据的自动验证逻辑 | Verification Ontology |
| 证据存储管理 | 数据存储层 |
| 文件管理模型 | 扩展模块 |


## 2. 设计原则

### 2.1 声明与证据分离原则

> **Claim（声明）和 Evidence（证据）是独立的概念。** Claim 是语义陈述，Evidence 是支持该陈述的信息资源。两者通过 `supports` 关系连接，而非合并。

### 2.2 证据不等于载体原则

> **Evidence 是语义实体，EvidenceArtifact 是载体。** 同一份 PDF 可以包含多个证据；同一个证据可以以多种载体形式存在。

### 2.3 来源可追溯原则

> **每个 Evidence 必须能够追溯到其来源（Source）。** 来源包括产生证据的组织、个人或系统。

### 2.4 有效性可表达原则

> **Evidence 可以有有效期。** 过期证据不应被用于支撑新的声明。

### 2.5 可信度不判断真实性原则

> **Evidence Ontology 只表达“来源类型”和“可信等级”，不判断“是否真实”。** 真实性评价属于 Verification / Certification 流程。


## 3. 核心概念模型

### 3.1 六层证据模型

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Evidence 六层模型                                       │
│                                                                             │
│  Layer 1: Claim（声明）                                                    │
│  需要被支持的语义陈述                                                     │
│  示例："产品 YD-GK-200W 具有 IP66 防护等级"                                │
│                                                                             │
│  Layer 2: Evidence（证据）                                                │
│  支持声明的可追溯信息实体                                                  │
│  示例："IEC 60529 测试报告 #123"                                           │
│                                                                             │
│  Layer 3: EvidenceArtifact（证据载体）                                    │
│  证据的物理/数字载体                                                       │
│  示例："报告 PDF 文件"                                                     │
│                                                                             │
│  Layer 4: EvidenceSource（证据来源）                                      │
│  产生证据的机构/组织/系统                                                  │
│  示例："SGS 实验室"                                                        │
│                                                                             │
│  Layer 5: EvidenceContext（证据上下文）                                   │
│  证据产生的条件/环境/时间                                                  │
│  示例："2026-07-15 在 SGS 上海实验室完成测试"                              │
│                                                                             │
│  Layer 6: EvidenceConfidence（可信等级）                                  │
│  基于来源类型的可信度评级                                                  │
│  示例："ThirdPartyVerified"                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心关系链

```
Claim（语义声明）
    │
    │  supportedBy（被支持）
    ▼
Evidence（证据实体）
    │
    ├── hasArtifact（有载体）
    │       ▼
    │   EvidenceArtifact（载体）
    │
    ├── generatedBy（产生自）
    │       ▼
    │   EvidenceSource（来源）
    │
    ├── hasContext（有上下文）
    │       ▼
    │   EvidenceContext（上下文）
    │
    ├── hasType（有类型）
    │       ▼
    │   EvidenceType（类型）
    │
    ├── hasValidity（有有效期）
    │       ▼
    │   EvidenceValidity（有效期）
    │
    └── hasConfidence（有可信等级）
            ▼
        EvidenceConfidence（可信等级）
```


## 4. 核心类定义

### 4.1 Claim（声明）

```
leleby-evidence:Claim
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Assertion ;
    rdfs:label "Claim" ;
    rdfs:comment "一个需要被支持、验证或证明的语义陈述。" .
```

**语义说明：** Claim 是语义层面的陈述，它可以是关于产品、能力、需求、规格、符合性的任何断言。Claim 本身不一定是真的——它需要被 Evidence 支撑才能获得可信度。

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `levd:claimIdentifier` | levd:Claim | xsd:string | 声明编号 | 0..1 |
| `levd:claimText` | levd:Claim | xsd:string | 声明文本 | 1 |
| `levd:claimType` | levd:Claim | levd:ClaimType | 声明类型 | 0..1 |
| `levd:claimDate` | levd:Claim | xsd:dateTime | 声明日期 | 0..1 |
| `levd:claimStatus` | levd:Claim | levd:ClaimStatus | 声明状态 | 0..1 |

**ClaimType 枚举：**

| 值 | 说明 | 示例 |
|----|------|------|
| `levd:ProductClaim` | 产品声明 | "产品防护等级 IP66" |
| `levd:CapabilityClaim` | 能力声明 | "企业具备精密加工能力" |
| `levd:RequirementClaim` | 需求声明 | "IEC 标准要求温度范围 -20~70℃" |
| `levd:SpecificationClaim` | 规格声明 | "产品功率 200W" |
| `levd:ComplianceClaim` | 符合性声明 | "产品符合 IEC 60598" |
| `levd:QualityClaim` | 质量声明 | "产品寿命 ≥ 50000h" |
| `levd:PerformanceClaim` | 性能声明 | "光效 ≥ 150 lm/W" |

**ClaimStatus 枚举：**

| 值 | 说明 |
|----|------|
| `levd:Proposed` | 已提议（待验证） |
| `levd:Verified` | 已验证（有证据支撑） |
| `levd:Rejected` | 已驳回（证据不足或矛盾） |
| `levd:Expired` | 已过期 |

**示例：**

```
levd:Claim_IP66_001
    a levd:Claim ;
    levd:claimIdentifier "CLAIM-IP66-001" ;
    levd:claimText "YD-GK-200W LED 灯具具有 IP66 防护等级" ;
    levd:claimType levd:ProductClaim ;
    levd:claimDate "2026-07-28T10:00:00Z"^^xsd:dateTime .
```

### 4.2 Evidence（证据）

```
leleby-evidence:Evidence
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity ;
    rdfs:label "Evidence" ;
    rdfs:comment "支撑、验证或证明某个语义声明的可追溯信息资源。" .
```

**语义说明：** Evidence 是证据的核心语义实体。它是可追溯的、有来源的信息资源，用于支持某个 Claim。

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `levd:evidenceIdentifier` | levd:Evidence | xsd:string | 证据编号 | 1 |
| `levd:evidenceName` | levd:Evidence | xsd:string | 证据名称 | 1 |
| `levd:evidenceDescription` | levd:Evidence | xsd:string | 证据描述 | 0..1 |
| `levd:createdAt` | levd:Evidence | xsd:dateTime | 创建时间 | 0..1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `levd:supportsClaim` | levd:Evidence | levd:Claim | 支持的声明 | 1..n |
| `levd:hasArtifact` | levd:Evidence | levd:EvidenceArtifact | 证据载体 | 0..n |
| `levd:generatedBy` | levd:Evidence | levd:EvidenceSource | 产生来源 | 0..1 |
| `levd:hasType` | levd:Evidence | levd:EvidenceType | 证据类型 | 1 |
| `levd:hasContext` | levd:Evidence | levd:EvidenceContext | 证据上下文 | 0..1 |
| `levd:hasValidity` | levd:Evidence | levd:EvidenceValidity | 有效期 | 0..1 |
| `levd:hasConfidence` | levd:Evidence | levd:EvidenceConfidence | 可信等级 | 0..1 |

**示例：**

```
levd:Evidence_TestReport_123
    a levd:Evidence ;
    levd:evidenceIdentifier "EVID-TR-123" ;
    levd:evidenceName "IEC 60529 防护等级测试报告" ;
    levd:evidenceDescription "SGS 出具的 IP66 防护等级测试报告" ;
    levd:supportsClaim levd:Claim_IP66_001 ;
    levd:hasType levd:TestReportEvidence ;
    levd:generatedBy levd:Source_SGS .
```

### 4.3 EvidenceArtifact（证据载体）

```
leleby-evidence:EvidenceArtifact
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity ;
    rdfs:label "EvidenceArtifact" ;
    rdfs:comment "证据的物理或数字载体，如 PDF 文件、图片、视频、数据库记录等。" .
```

**语义说明：** EvidenceArtifact 是证据的具体载体形式。一个 Evidence 可以有多个载体（如 PDF 和 XML 格式），一个载体可以承载多个 Evidence。

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `levd:artifactIdentifier` | levd:EvidenceArtifact | xsd:string | 载体编号 | 1 |
| `levd:artifactName` | levd:EvidenceArtifact | xsd:string | 载体名称 | 1 |
| `levd:artifactType` | levd:EvidenceArtifact | levd:ArtifactType | 载体类型 | 1 |
| `levd:artifactLocation` | levd:EvidenceArtifact | xsd:anyURI | 载体位置（URL/路径） | 0..1 |
| `levd:artifactHash` | levd:EvidenceArtifact | xsd:string | 文件哈希值 | 0..1 |
| `levd:artifactSize` | levd:EvidenceArtifact | xsd:integer | 文件大小（字节） | 0..1 |

**ArtifactType 枚举：**

| 值 | 说明 |
|----|------|
| `levd:PDF` | PDF 文件 |
| `levd:XML` | XML 文件 |
| `levd:RDF` | RDF 文件 |
| `levd:JSON` | JSON 文件 |
| `levd:Image` | 图片文件 |
| `levd:Video` | 视频文件 |
| `levd:DatabaseRecord` | 数据库记录 |
| `levd:URLReference` | URL 引用 |
| `levd:PhysicalDocument` | 物理文档 |

### 4.4 EvidenceSource（证据来源）

```
leleby-evidence:EvidenceSource
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Agent ;
    rdfs:label "EvidenceSource" ;
    rdfs:comment "产生证据的机构、组织、个人或系统。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `levd:sourceIdentifier` | levd:EvidenceSource | xsd:string | 来源编号 | 1 |
| `levd:sourceName` | levd:EvidenceSource | xsd:string | 来源名称 | 1 |
| `levd:sourceType` | levd:EvidenceSource | levd:SourceType | 来源类型 | 1 |
| `levd:sourceDescription` | levd:EvidenceSource | xsd:string | 来源描述 | 0..1 |

**SourceType 枚举：**

| 值 | 说明 |
|----|------|
| `levd:AccreditedLab` | 认可实验室（如 SGS、TÜV） |
| `levd:CertificationBody` | 认证机构（如 UL、CE） |
| `levd:RegulatoryAgency` | 监管机构 |
| `levd:Manufacturer` | 制造商 |
| `levd:Customer` | 客户 |
| `levd:IndustryAssociation` | 行业协会 |
| `levd:ResearchInstitute` | 研究机构 |
| `levd:InternalSystem` | 内部系统 |
| `levd:ThirdPartyProvider` | 第三方服务提供商 |

### 4.5 EvidenceType（证据类型）

```
leleby-evidence:EvidenceType
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity ;
    rdfs:label "EvidenceType" ;
    rdfs:comment "证据的分类类型。" .
```

**预定义类型：**

| 值 | 说明 | 示例 |
|----|------|------|
| `levd:CertificationEvidence` | 认证证据 | CE 证书、UL 证书 |
| `levd:TestReportEvidence` | 测试报告证据 | IEC 测试报告 |
| `levd:InspectionEvidence` | 检验证据 | 来料检验记录 |
| `levd:MeasurementEvidence` | 测量证据 | 尺寸测量数据 |
| `levd:SpecificationDocumentEvidence` | 规格文档证据 | 产品规格书 |
| `levd:RegulatoryEvidence` | 法规证据 | 法规文件 |
| `levd:StandardEvidence` | 标准证据 | 标准文档 |
| `levd:CustomerEvidence` | 客户证据 | 客户验收单 |
| `levd:OrganizationEvidence` | 组织证据 | 企业资质证明 |
| `levd:DeclarationEvidence` | 声明证据 | 企业自声明 |
| `levd:HistoricalEvidence` | 历史证据 | 历史项目记录 |
| `levd:ExpertEvidence` | 专家证据 | 专家意见 |

### 4.6 EvidenceContext（证据上下文）

```
leleby-evidence:EvidenceContext
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:EvaluationContext ;
    rdfs:label "EvidenceContext" ;
    rdfs:comment "证据产生的条件、环境、时间等上下文信息。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `levd:contextDate` | levd:EvidenceContext | xsd:dateTime | 证据产生时间 |
| `levd:contextLocation` | levd:EvidenceContext | leleby:Location | 证据产生地点 |
| `levd:contextCondition` | levd:EvidenceContext | xsd:string | 产生条件描述 |
| `levd:contextMethod` | levd:EvidenceContext | xsd:string | 产生方法引用 |

### 4.7 EvidenceValidity（证据有效期）

```
leleby-evidence:EvidenceValidity
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity ;
    rdfs:label "EvidenceValidity" ;
    rdfs:comment "证据的有效期和状态。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `levd:validFrom` | levd:EvidenceValidity | xsd:dateTime | 有效期起始 | 0..1 |
| `levd:validUntil` | levd:EvidenceValidity | xsd:dateTime | 有效期结束 | 0..1 |
| `levd:validityStatus` | levd:EvidenceValidity | levd:ValidityStatus | 有效性状态 | 1 |

**ValidityStatus 枚举：**

| 值 | 说明 |
|----|------|
| `levd:Valid` | 有效 |
| `levd:Expired` | 已过期 |
| `levd:Suspended` | 已暂停（待重新验证） |
| `levd:Revoked` | 已撤销 |

### 4.8 EvidenceConfidence（可信等级）

```
leleby-evidence:EvidenceConfidence
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity ;
    rdfs:label "EvidenceConfidence" ;
    rdfs:comment "基于来源类型的证据可信等级。" .
```

**语义说明：** EvidenceConfidence 表达的是“基于来源类型”的可信度，而非“真实性判断”。它帮助 AI Agent 评估证据的权重。

**预定义等级：**

| 值 | 说明 | 权重建议 |
|----|------|----------|
| `levd:Official` | 官方机构出具 | 0.95 |
| `levd:ThirdPartyVerified` | 第三方独立验证 | 0.90 |
| `levd:AccreditedLab` | 认可实验室出具 | 0.85 |
| `levd:IndustryStandard` | 行业标准引用 | 0.80 |
| `levd:ManufacturerDeclared` | 制造商声明 | 0.60 |
| `levd:CustomerProvided` | 客户提供 | 0.50 |
| `levd:CommunityProvided` | 社区/公开信息 | 0.40 |
| `levd:InternalSystem` | 内部系统记录 | 0.70 |

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `levd:confidenceLevel` | levd:EvidenceConfidence | xsd:double | 可信度值 [0,1] |
| `levd:confidenceLabel` | levd:EvidenceConfidence | xsd:string | 可信度标签 |
| `levd:confidenceBasis` | levd:EvidenceConfidence | xsd:string | 可信度依据 |

### 4.9 EvidenceRelationship（证据关系）

```
leleby-evidence:EvidenceRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity ;
    rdfs:label "EvidenceRelationship" ;
    rdfs:comment "证据之间的关系。" .
```

**关系类型：**

| 值 | 说明 |
|----|------|
| `levd:DerivedFrom` | 派生自（证据由另一个证据派生） |
| `levd:References` | 引用（证据引用另一个证据） |
| `levd:Supersedes` | 替代（新证据替代旧证据） |
| `levd:Supports` | 支持（证据支持另一个证据） |
| `levd:Contradicts` | 矛盾（证据与另一个证据矛盾） |
| `levd:Amends` | 修正（证据修正另一个证据） |

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `levd:sourceEvidence` | levd:EvidenceRelationship | levd:Evidence | 源证据 |
| `levd:targetEvidence` | levd:EvidenceRelationship | levd:Evidence | 目标证据 |
| `levd:relationshipType` | levd:EvidenceRelationship | levd:RelationshipType | 关系类型 |


## 5. 与其他模块的连接

### 5.1 与 Requirement Ontology 的连接

```
Requirement（需求）
    │
    │  derivedFrom
    ▼
RequirementSource（需求来源）
    │
    │  supportedBy
    ▼
Evidence（证据）
    │
    └── 例如：标准文档、法规文件、客户规格书
```

### 5.2 与 Specification Ontology 的连接

```
SpecificationItem（规格项）
    │
    │  （规格项本身是一个 Claim）
    ▼
Claim（声明）
    │
    │  supportedBy
    ▼
Evidence（证据）
    │
    └── 例如：产品手册、技术图纸、测试报告
```

### 5.3 与 Product / Capability Ontology 的连接

```
Product / Capability（产品/能力）
    │
    │  （能力声明是一个 Claim）
    ▼
Claim（声明）
    │
    │  supportedBy
    ▼
Evidence（证据）
    │
    └── 例如：设备清单、人员资质、认证证书
```

### 5.4 与 Verification Ontology 的连接

```
VerificationActivity（验证活动）
    │
    │  uses
    ▼
Evidence（证据）
    │
    │  supports
    ▼
VerificationResult（验证结果）
```

### 5.5 与 Compliance Ontology 的连接

```
ComplianceDeclaration（符合性声明）
    │
    │  supportedBy
    ▼
Evidence（证据）
    │
    └── 例如：认证证书、审核记录、第三方评估报告
```

### 5.6 与 Measurement Ontology 的连接

```
MeasurementObservation（测量观察）
    │
    │  produces
    ▼
MeasurementResult（测量结果）
    │
    │  includedIn
    ▼
Evidence（证据）
    │
    └── 例如：测试报告包含测量数据
```


## 6. PROV-O 对齐（证据溯源）

### 6.1 设计思想

leleby Evidence Ontology 与 **W3C PROV-O（Provenance Ontology）** 保持概念对齐，以支持证据溯源。

**PROV-O 核心概念：**
- `prov:Entity`：可被描述的事物
- `prov:Activity`：产生或使用事物的事件
- `prov:Agent`：活动的参与者
- `prov:wasGeneratedBy`：实体由活动产生
- `prov:wasAttributedTo`：实体归属于代理

### 6.2 映射关系

| leleby 概念 | PROV-O 概念 | 映射类型 |
|------------|-------------|----------|
| `levd:Evidence` | `prov:Entity` | `skos:closeMatch` |
| `levd:EvidenceSource` | `prov:Agent` | `skos:closeMatch` |
| `levd:EvidenceContext` | `prov:Activity` | `skos:closeMatch` |
| `levd:generatedBy` | `prov:wasGeneratedBy` | `skos:closeMatch` |
| `levd:supportsClaim` | — | 无直接对应 |

**对齐示例：**

```
levd:Evidence
    skos:closeMatch prov:Entity .

levd:generatedBy
    skos:closeMatch prov:wasGeneratedBy .
```


## 7. 外部标准对齐

| 外部体系 | 对齐方式 | 说明 |
|----------|----------|------|
| W3C PROV-O | `skos:closeMatch` | 证据溯源 |
| schema.org | `skos:relatedMatch` | DigitalDocument / Certification |
| DC Terms | `skos:relatedMatch` | 元数据（creator / issued / valid） |
| ISO 9001 | `skos:relatedMatch` | 证据与记录管理概念 |


## 8. SHACL 验证约束

### 8.1 Evidence 基础约束

```turtle
levd:EvidenceShape
    a sh:NodeShape ;
    sh:targetClass levd:Evidence ;
    sh:property [
        sh:path levd:evidenceIdentifier ;
        sh:minCount 1 ;
        sh:message "Evidence must have an identifier" ;
    ] ;
    sh:property [
        sh:path levd:evidenceName ;
        sh:minCount 1 ;
        sh:message "Evidence must have a name" ;
    ] ;
    sh:property [
        sh:path levd:supportsClaim ;
        sh:minCount 1 ;
        sh:message "Evidence must support at least one claim" ;
    ] ;
    sh:property [
        sh:path levd:hasType ;
        sh:minCount 1 ;
        sh:message "Evidence must have a type" ;
    ] .
```

### 8.2 Claim 约束

```turtle
levd:ClaimShape
    a sh:NodeShape ;
    sh:targetClass levd:Claim ;
    sh:property [
        sh:path levd:claimText ;
        sh:minCount 1 ;
        sh:message "Claim must have text" ;
    ] .
```

### 8.3 EvidenceArtifact 约束

```turtle
levd:EvidenceArtifactShape
    a sh:NodeShape ;
    sh:targetClass levd:EvidenceArtifact ;
    sh:property [
        sh:path levd:artifactIdentifier ;
        sh:minCount 1 ;
        sh:message "Artifact must have an identifier" ;
    ] ;
    sh:property [
        sh:path levd:artifactType ;
        sh:minCount 1 ;
        sh:message "Artifact must have a type" ;
    ] .
```

### 8.4 EvidenceSource 约束

```turtle
levd:EvidenceSourceShape
    a sh:NodeShape ;
    sh:targetClass levd:EvidenceSource ;
    sh:property [
        sh:path levd:sourceIdentifier ;
        sh:minCount 1 ;
        sh:message "Source must have an identifier" ;
    ] ;
    sh:property [
        sh:path levd:sourceName ;
        sh:minCount 1 ;
        sh:message "Source must have a name" ;
    ] .
```

### 8.5 EvidenceValidity 约束

```turtle
levd:EvidenceValidityShape
    a sh:NodeShape ;
    sh:targetClass levd:EvidenceValidity ;
    sh:property [
        sh:path levd:validityStatus ;
        sh:minCount 1 ;
        sh:in (
            levd:Valid
            levd:Expired
            levd:Suspended
            levd:Revoked
        ) ;
        sh:message "Validity status must be one of predefined values" ;
    ] .
```


## 9. 完整示例

### 9.1 示例一：产品能力声明 + 测试报告证据

```ttl
# 1. 声明
levd:Claim_IP66
    a levd:Claim ;
    levd:claimIdentifier "CLAIM-IP66-001" ;
    levd:claimText "YD-GK-200W LED 灯具具有 IP66 防护等级" ;
    levd:claimType levd:ProductClaim ;
    levd:claimStatus levd:Verified .

# 2. 证据来源
levd:Source_SGS
    a levd:EvidenceSource ;
    levd:sourceIdentifier "SRC-SGS" ;
    levd:sourceName "SGS 上海实验室" ;
    levd:sourceType levd:AccreditedLab .

# 3. 证据
levd:Evidence_TestReport_IP66
    a levd:Evidence ;
    levd:evidenceIdentifier "EVID-TR-IP66-001" ;
    levd:evidenceName "IEC 60529 IP 测试报告" ;
    levd:evidenceDescription "SGS 出具的 IP66 防护等级测试报告" ;
    levd:supportsClaim levd:Claim_IP66 ;
    levd:hasType levd:TestReportEvidence ;
    levd:generatedBy levd:Source_SGS ;
    levd:hasValidity [
        a levd:EvidenceValidity ;
        levd:validFrom "2026-01-15T00:00:00Z"^^xsd:dateTime ;
        levd:validUntil "2031-01-14T23:59:59Z"^^xsd:dateTime ;
        levd:validityStatus levd:Valid
    ] ;
    levd:hasConfidence [
        a levd:EvidenceConfidence ;
        levd:confidenceLevel "0.90"^^xsd:double ;
        levd:confidenceLabel "第三方认可实验室验证" ;
        levd:confidenceBasis "SGS 是 IEC 认可实验室"
    ] ;
    levd:hasArtifact [
        a levd:EvidenceArtifact ;
        levd:artifactIdentifier "ART-PDF-IP66-001" ;
        levd:artifactName "IP66 测试报告 PDF" ;
        levd:artifactType levd:PDF ;
        levd:artifactLocation "https://storage.leleby.com/reports/ip66-test-001.pdf" ;
        levd:artifactHash "sha256:abc123..." ;
        levd:artifactSize "2457600"^^xsd:integer
    ] .
```

### 9.2 示例二：标准需求 + 标准证据

```ttl
# 1. 需求声明
levd:Claim_IEC_Temp
    a levd:Claim ;
    levd:claimIdentifier "CLAIM-IEC-TEMP-001" ;
    levd:claimText "IEC 60598 要求户外灯具工作温度范围为 -20℃ ~ 70℃" ;
    levd:claimType levd:RequirementClaim .

# 2. 来源
levd:Source_IEC
    a levd:EvidenceSource ;
    levd:sourceIdentifier "SRC-IEC" ;
    levd:sourceName "国际电工委员会" ;
    levd:sourceType levd:IndustryStandard .

# 3. 证据
levd:Evidence_IEC_Standard
    a levd:Evidence ;
    levd:evidenceIdentifier "EVID-IEC-60598" ;
    levd:evidenceName "IEC 60598 标准" ;
    levd:evidenceDescription "IEC 60598:2021 灯具通用要求与测试" ;
    levd:supportsClaim levd:Claim_IEC_Temp ;
    levd:hasType levd:StandardEvidence ;
    levd:generatedBy levd:Source_IEC ;
    levd:hasArtifact [
        a levd:EvidenceArtifact ;
        levd:artifactIdentifier "ART-IEC-60598" ;
        levd:artifactName "IEC 60598 PDF" ;
        levd:artifactType levd:PDF ;
        levd:artifactLocation "https://storage.leleby.com/standards/iec-60598-2021.pdf"
    ] .
```

### 9.3 示例三：企业能力声明 + 证据链

```ttl
# 1. 能力声明
levd:Claim_Capability_CNC
    a levd:Claim ;
    levd:claimIdentifier "CLAIM-CAP-CNC-001" ;
    levd:claimText "云达照明具备 CNC 精密加工能力" ;
    levd:claimType levd:CapabilityClaim .

# 2. 证据来源
levd:Source_Yunda
    a levd:EvidenceSource ;
    levd:sourceIdentifier "SRC-YUNDA" ;
    levd:sourceName "云达照明科技有限公司" ;
    levd:sourceType levd:Manufacturer .

# 3. 多个证据支持同一声明
levd:Evidence_CNC_Equipment
    a levd:Evidence ;
    levd:evidenceIdentifier "EVID-CNC-EQUIP" ;
    levd:evidenceName "CNC 设备清单" ;
    levd:supportsClaim levd:Claim_Capability_CNC ;
    levd:hasType levd:OrganizationEvidence ;
    levd:generatedBy levd:Source_Yunda .

levd:Evidence_CNC_Cert
    a levd:Evidence ;
    levd:evidenceIdentifier "EVID-CNC-CERT" ;
    levd:evidenceName "ISO 9001 证书" ;
    levd:supportsClaim levd:Claim_Capability_CNC ;
    levd:hasType levd:CertificationEvidence ;
    levd:generatedBy levd:Source_Yunda .
```


## 10. 核心类汇总

### 10.1 Classes

| 类名 | 父类 | 说明 |
|------|------|------|
| `levd:Claim` | leleby:Assertion | 语义声明 |
| `levd:Evidence` | leleby:InformationEntity | 证据实体 |
| `levd:EvidenceArtifact` | leleby:InformationEntity | 证据载体 |
| `levd:EvidenceSource` | leleby:Agent | 证据来源 |
| `levd:EvidenceType` | leleby:InformationEntity | 证据类型 |
| `levd:EvidenceContext` | leleby:EvaluationContext | 证据上下文 |
| `levd:EvidenceValidity` | leleby:InformationEntity | 证据有效期 |
| `levd:EvidenceConfidence` | leleby:InformationEntity | 可信等级 |
| `levd:EvidenceRelationship` | leleby:InformationEntity | 证据关系 |

### 10.2 Object Properties

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `levd:supportsClaim` | levd:Evidence | levd:Claim | 支持声明 |
| `levd:hasArtifact` | levd:Evidence | levd:EvidenceArtifact | 有载体 |
| `levd:generatedBy` | levd:Evidence | levd:EvidenceSource | 产生自 |
| `levd:hasType` | levd:Evidence | levd:EvidenceType | 有类型 |
| `levd:hasContext` | levd:Evidence | levd:EvidenceContext | 有上下文 |
| `levd:hasValidity` | levd:Evidence | levd:EvidenceValidity | 有有效期 |
| `levd:hasConfidence` | levd:Evidence | levd:EvidenceConfidence | 有可信等级 |
| `levd:sourceEvidence` | levd:EvidenceRelationship | levd:Evidence | 源证据 |
| `levd:targetEvidence` | levd:EvidenceRelationship | levd:Evidence | 目标证据 |
| `levd:relationshipType` | levd:EvidenceRelationship | levd:RelationshipType | 关系类型 |


## 11. 版本变更记录

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| **v0.1** | **2026-07-28** | **初始版本：定义 Claim / Evidence / EvidenceArtifact / EvidenceSource / EvidenceType / EvidenceContext / EvidenceValidity / EvidenceConfidence / EvidenceRelationship；明确与 Requirement / Specification / Product / Capability / Verification / Compliance / Measurement 的连接；PROV-O 对齐；外部标准对齐（PROV-O / schema.org / DC Terms）；SHACL 验证；完整示例** |


*— leleby Evidence Ontology Specification v0.1 — Core Design Edition —*