# leleby Compliance Ontology Specification v0.2

**文档版本：** v0.2 — Semantic Judgment Alignment Release（语义判断对齐版）

**文档类型：** 模块规范（Module Ontology Specification）

**文档状态：** ⚠️ **候选冻结（Candidate Freeze）** — 核心概念与顶层结构已稳定，待实践验证后正式冻结

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.2

**依赖模块：**
- `llb` Foundation Vocabulary Specification v1.1（提供 `Entity`、`Concept`、`Statement`、`Agent` 等纯元概念）
- `lbo-core` Core Ontology Specification v1.2（提供 `SemanticTarget`、`EvaluationContext`、`Assessment`）
- `lreq` Requirement Ontology Specification v1.1（提供 `Requirement`）
- `lcon` Constraint Ontology Specification v1.1（提供 `Constraint`）
- `lbo-meas` Measurement Ontology Specification v0.2（提供 `MeasurementResult`）
- `lver` Verification Ontology Specification v0.2（提供 `VerificationResult`）
- `lbo-spec` Specification Framework Ontology Specification v1.1（提供 `SpecificationItem`）
- `lprod` Product Ontology Specification v0.4（提供 `Product`）
- `ldec` Decision Ontology Specification（待定，提供 `DecisionResult`）

**命名空间：** `https://ontology.leleby.org/compliance/`

**推荐前缀：** `lcomp`

**目标受众：** 本体工程师、合规管理人员、质量管理人员、AI Agent 开发者


## 目录

1. 引言
   1.1 目的
   1.2 在 leleby 架构中的位置（v0.2 更新）
   1.3 核心职责边界（v0.2 更新）
   1.4 v0.2 与 v0.1 的核心差异
   1.5 设计原则

2. 命名空间声明

3. 核心概念模型
   3.1 三级符合性模型（v0.2 重构）
   3.2 核心关系链（v0.2 更新）

4. 类规范
   4.1 ComplianceAssertion（单项符合性断言——v0.2 重构）
   4.2 ComplianceAssessment（整体符合性评估——v0.2 重构）
   4.3 ComplianceDeclaration（对外符合性声明——v0.2 增强）
   4.4 ComplianceStatus（符合性状态）
   4.5 DeclarationStatus（声明状态——v0.2 新增）
   4.6 DeclarationType（声明类型——v0.2 新增）
   4.7 ComplianceMatrix（符合性矩阵）

5. 对象属性（v0.2 更新）

6. 数据属性

7. 与其他模块的连接（v0.2 更新）
   7.1 与 Requirement Ontology 的连接
   7.2 与 Verification Ontology 的连接
   7.3 与 Decision Ontology 的连接（v0.2 更新）
   7.4 与 Measurement Ontology 的连接
   7.5 与 Specification Framework 的连接
   7.6 与 Product Ontology 的连接
   7.7 接口总图

8. 完整推理链路（v0.2 更新）

9. 推理规则（v0.2 更新）

10. SHACL 验证约束（v0.2 更新）

11. 完整示例（v0.2 更新）

12. 核心类汇总

13. 冻结声明

14. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Compliance Ontology 是 leleby 语义基础设施中的**语义判断层（Semantic Judgment Layer）**。它定义了：

- 产品、服务、能力或组织满足某项要求的符合性语义表达
- 符合性的结构化断言（Compliance Assertion）
- 符合性状态和聚合评估
- 面向外部的符合性声明

**核心定位：**

> Compliance Ontology 定义的是“一个对象在什么要求、什么验证依据下，被判断为符合或不符合”的语义结论。它是 leleby 规范语义闭环的最终输出层，供 AI Agent、合规审查、商业决策等系统消费。

### 1.2 在 leleby 架构中的位置（v0.2 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Compliance Ontology 在架构中的位置（v0.2）              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 6: Decision & Action                                        │   │
│  │  决策与行动层：使用 Compliance 结果，做出最终决策和行动              │   │
│  │  DecisionResult ──uses──> ComplianceAssessment                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                        │
│                                    │  usedBy（决策使用符合性结果）           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 5: Compliance Ontology（本模块）                            │   │
│  │  符合性层：Semantic Judgment Layer                                  │   │
│  │  ComplianceAssertion / ComplianceAssessment / ComplianceDeclaration │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                        │
│                                    │  basedOn（基于验证结果）                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 4: Verification Ontology                                    │   │
│  │  验证层：单项验证结果                                                │   │
│  │  VerificationResult                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                        │
│                                    │  providesData（提供事实数据）           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 3: Measurement Ontology                                     │   │
│  │  事实层：测量结果                                                    │   │
│  │  MeasurementResult                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                        │
│                                    │  defines（定义要求）                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 2: Requirement & Constraint                                 │   │
│  │  需求与约束层：Requirement / Constraint                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                        │
│                                    │  subjectOf（被评价对象）                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Layer 1: Product & Capability                                     │   │
│  │  业务对象层：Product / Capability / Organization                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  关键关系：                                                                  │
│  - Compliance 不依赖 Decision（反向：Decision 使用 Compliance）             │
│  - Compliance 基于 Verification（而非直接基于 Measurement）                 │
│  - Compliance 产出供 AI Agent 和商业决策系统消费                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 核心职责边界（v0.2 更新）

| Compliance Ontology 包含 | Compliance Ontology 不包含 |
|-------------------------|---------------------------|
| ✅ 符合性断言（Compliance Assertion） | ❌ 需求定义（归 Requirement Ontology） |
| ✅ 符合性状态 | ❌ 规格定义（归 Specification Framework） |
| ✅ 符合性聚合评估 | ❌ 验证执行（归 Verification Ontology） |
| ✅ 符合性证据引用 | ❌ 测量事实（归 Measurement Ontology） |
| ✅ 对外符合性声明 | ❌ 决策规则（归 Decision Ontology） |
| ✅ 符合性追溯 | ❌ 最终行动决策（归 Decision Ontology） |
| ✅ 语义目标符合性 | ❌ 商业判断（归 Decision Ontology） |

**核心原则（v0.2 更新）：**

> **Compliance 是“结论层”，不是“计算层”。**
>
> - Verification 判断“单项要求是否满足”（计算层）
> - Compliance 表达“语义符合性结论”（结论层）
> - Decision 使用 Compliance 结果进行“综合行动判断”（决策层）

### 1.4 v0.2 与 v0.1 的核心差异

| 问题 | v0.1 状态 | v0.2 修正 |
|---|---|---|
| **Compliance 与 Decision 的关系** | Compliance 由 Decision 产生 | **反向：Decision 使用 Compliance 结果** |
| **ComplianceAssertion 语义** | `evaluatesRequirement`（评估需求） | **改为 `conformsToRequirement`（满足需求）** |
| **Specification 关系** | `evaluatesSpecification` | **删除**（Specification 不直接参与 Compliance） |
| **SemanticTarget 支持** | 无 | **新增 `hasTarget` → `SemanticTarget`** |
| **ComplianceAssessment 职责** | 做出合格/不合格判断 | **只做聚合统计，不判断合格/不合格** |
| **ComplianceLevel** | 定义 High/Medium/Low | **删除，标记为行业扩展** |
| **ComplianceStatus** | 包含 Expired、Suspended | **拆分：Expired/Suspended 归 DeclarationStatus** |
| **ComplianceMatrix** | 在 Core 中 | **标记为 Application 层概念** |
| **SHACL 约束** | 基础 | **更新以反映新语义** |

### 1.5 设计原则

**原则一：符合性是语义断言原则**

> **符合性不是事实本身，而是基于验证证据产生的语义结论。** 每个 Compliance 断言都带有完整的来源追溯。

**原则二：事实与判断分离原则**

> **leleby 必须区分 Measurement Fact（事实）、Verification Result（验证）和 Compliance Judgment（符合性）。** 三者不能混合。

| 层次 | 概念 | 示例 |
|------|------|------|
| 事实层 | Measurement | 实测温度：-35℃ |
| 验证层 | Verification Result | 温度要求验证通过 |
| 符合性层 | Compliance Assertion | 产品符合温度要求 |

**原则三：符合性有上下文原则**

> **任何符合性必须包含完整的上下文：符合谁？满足什么？依据什么？什么时候？什么条件？**

**原则四：可追溯原则**

> **每个 Compliance 断言必须能够追溯到其依据：需求、验证结果、证据。**

**原则五：三级符合性模型原则**

> **Compliance 分为三个层级：**
> 1. **ComplianceAssertion**：单项符合性断言（基本单元）
> 2. **ComplianceAssessment**：聚合评估（统计汇总）
> 3. **ComplianceDeclaration**：对外符合性声明（正式输出）

**原则六：Compliance 与 Decision 分离原则（v0.2 新增）**

> **Compliance 表达“是否符合”，Decision 表达“采取什么行动”。** Compliance 不依赖 Decision，Decision 可以引用 Compliance。两者职责清晰分离。


## 2. 命名空间声明

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix llb: <https://ontology.leleby.org/foundation/> .
@prefix lbo-core: <https://ontology.leleby.org/core/> .
@prefix lreq: <https://ontology.leleby.org/requirement/> .
@prefix lcon: <https://ontology.leleby.org/constraint/> .
@prefix lbo-meas: <https://ontology.leleby.org/measurement/> .
@prefix lver: <https://ontology.leleby.org/verification/> .
@prefix lbo-spec: <https://ontology.leleby.org/specification/> .
@prefix lprod: <https://ontology.leleby.org/product/> .
@prefix ldec: <https://ontology.leleby.org/decision/> .
@prefix lcomp: <https://ontology.leleby.org/compliance/> .

<https://ontology.leleby.org/compliance/>
    rdf:type owl:Ontology ;
    owl:versionInfo "0.2" ;
    owl:imports <https://ontology.leleby.org/foundation/> ;
    owl:imports <https://ontology.leleby.org/core/> ;
    owl:imports <https://ontology.leleby.org/requirement/> ;
    owl:imports <https://ontology.leleby.org/verification/> ;
    rdfs:label "leleby Compliance Ontology" ;
    rdfs:comment "leleby 语义基础设施的语义判断层，定义符合性断言、评估和声明" .
```


## 3. 核心概念模型

### 3.1 三级符合性模型（v0.2 重构）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Compliance 三级模型（v0.2 重构）                         │
│                                                                             │
│  Level 1: ComplianceAssertion（单项符合性断言）                             │
│  ────────────────────────────────────────────────────────────────────────   │
│  描述：一个对象对一项要求的单项符合性语义结论                               │
│  来源：VerificationResult + Evidence                                       │
│  语义：Subject conformsTo Requirement（满足/不满足）                       │
│  示例："产品 A 的温度要求 → 符合"                                          │
│  基数：1 项 Requirement → 1 项 ComplianceAssertion                         │
│                                                                             │
│                                    │                                        │
│                                    │  aggregatedBy（聚合）                  │
│                                    ▼                                        │
│  Level 2: ComplianceAssessment（整体符合性评估）                           │
│  ────────────────────────────────────────────────────────────────────────   │
│  描述：多个 ComplianceAssertion 的统计汇总                                  │
│  来源：多个 ComplianceAssertion                                             │
│  功能：统计通过/失败数量，计算符合率                                       │
│  示例："产品 A：120/125 项通过"                                             │
│  注意：**不做最终合格/不合格判断**（该判断归 Decision）                     │
│                                                                             │
│                                    │                                        │
│                                    │  declaredAs（声明为）                  │
│                                    ▼                                        │
│  Level 3: ComplianceDeclaration（对外符合性声明）                          │
│  ────────────────────────────────────────────────────────────────────────   │
│  描述：面向外部利益相关者的符合性正式声明                                   │
│  来源：ComplianceAssessment + 组织声明规则                                  │
│  示例："产品 A 符合 IEC 60598 标准"                                        │
│  基数：1 个产品 → 1 项 ComplianceDeclaration                               │
│  法律属性：issuedBy、declarationType、declarationStatus                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心关系链（v0.2 更新）

```
Requirement（需求——来自 lreq）
    │
    │  defines constraint target
    ▼
Verification（验证——来自 lver）
    │
    │  produces
    ▼
VerificationResult（验证结果）
    │
    │  provides evidence for
    ▼
ComplianceAssertion（单项符合性断言）← 本模块
    │
    │  conformsTo Requirement
    │  hasSubject Product
    │  hasStatus Compliant/NonCompliant
    │
    │  aggregatedBy
    ▼
ComplianceAssessment（聚合评估）
    │
    │  aggregates assertions
    │  calculates: passedCount / totalCount / complianceRate
    │  **不判断合格/不合格**
    │
    │  declaredAs
    ▼
ComplianceDeclaration（对外声明）
    │
    │  declaresProduct
    │  declaresStandard
    │  issuedBy Organization
    │
    ▼
Decision（决策——来自 ldec）
    │
    │  uses ComplianceAssessment
    │  makes final decision
    ▼
Action（行动）
```


## 4. 类规范

### 4.1 ComplianceAssertion（单项符合性断言——v0.2 重构）

```
lcomp:ComplianceAssertion
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Assessment ;
    rdfs:label "ComplianceAssertion" ;
    rdfs:comment "一个对象对一项要求的单项符合性语义断言。表达'Subject 符合/不符合 Requirement'的事实结论。" .
```

**语义说明（v0.2 更新）：**

> ComplianceAssertion 是最基本的符合性单元。它表达的是**语义事实结论**——"某个对象（Subject）在给定上下文（Context）中，基于验证证据（VerificationResult），对某项要求（Requirement）的符合性判断"。
>
> **关键语义转换（v0.2）：**
> - ❌ v0.1："产品评估需求"（evaluatesRequirement）
> - ✅ v0.2："产品满足需求"（conformsToRequirement）

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcomp:assertionIdentifier` | lcomp:ComplianceAssertion | xsd:string | 断言编号 | 1 |
| `lcomp:assertionDate` | lcomp:ComplianceAssertion | xsd:dateTime | 断言日期 | 0..1 |
| `lcomp:assertionDescription` | lcomp:ComplianceAssertion | xsd:string | 断言描述 | 0..1 |

**关系（v0.2 更新）：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcomp:hasSubject` | lcomp:ComplianceAssertion | `llb:Entity` | 被评价对象（Product/Organization/Process） | 1 |
| **`lcomp:hasTarget`** | lcomp:ComplianceAssertion | **`lbo-core:SemanticTarget`** | **被评价的语义目标（v0.2 新增）** | 0..1 |
| **`lcomp:conformsToRequirement`** | lcomp:ComplianceAssertion | **`lreq:Requirement`** | **满足的需求（v0.2 重构）** | 1 |
| `lcomp:basedOnVerification` | lcomp:ComplianceAssertion | `lver:VerificationResult` | 基于的验证结果 | 1 |
| `lcomp:supportedByEvidence` | lcomp:ComplianceAssertion | `llb:Document` | 支撑的证据 | 0..* |
| `lcomp:hasComplianceStatus` | lcomp:ComplianceAssertion | `lcomp:ComplianceStatus` | 符合性状态 | 1 |
| `lcomp:assertedInContext` | lcomp:ComplianceAssertion | `lbo-core:EvaluationContext` | 断言上下文 | 0..1 |

**v0.2 删除的属性：**
- ❌ `lcomp:evaluatesRequirement`（替换为 `conformsToRequirement`）
- ❌ `lcomp:evaluatesSpecification`（删除，Compliance 不直接涉及 Specification）
- ❌ `lcomp:determinedByDecision`（删除，Compliance 不依赖 Decision）

**示例（v0.2 更新）：**

```turtle
lcomp:CA_Temp_001
    a lcomp:ComplianceAssertion ;
    lcomp:assertionIdentifier "CA-TEMP-001" ;
    lcomp:assertionDate "2026-07-28T14:30:00Z"^^xsd:dateTime ;
    lcomp:assertionDescription "产品 A 的温度要求符合性" ;
    lcomp:hasSubject lprod:YD_GK_200W ;
    lcomp:hasTarget lreq:Target_Temp ;
    lcomp:conformsToRequirement lreq:REQ_Temp_001 ;
    lcomp:basedOnVerification lver:Result_Temp_001 ;
    lcomp:hasComplianceStatus lcomp:Compliant ;
    lcomp:assertedInContext lcore:Context_25C_Ambient .
```

### 4.2 ComplianceAssessment（整体符合性评估——v0.2 重构）

```
lcomp:ComplianceAssessment
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Assessment ;
    rdfs:label "ComplianceAssessment" ;
    rdfs:comment "多个 ComplianceAssertion 的聚合汇总。提供统计数据，但**不做最终合格/不合格判断**。" .
```

**语义说明（v0.2 重构）：**

> ComplianceAssessment 是对多个单项符合性断言的统计汇总。它回答"多少项通过了？多少项失败了？符合率是多少？"等问题。
>
> **v0.2 核心变化：**
> - ❌ 不再做出"合格/不合格"判断
> - ✅ 只提供统计数据
> - ✅ 判断权交给 Decision Ontology

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcomp:assessmentIdentifier` | lcomp:ComplianceAssessment | xsd:string | 评估编号 | 1 |
| `lcomp:assessmentName` | lcomp:ComplianceAssessment | xsd:string | 评估名称 | 1 |
| `lcomp:assessmentDate` | lcomp:ComplianceAssessment | xsd:dateTime | 评估日期 | 0..1 |
| `lcomp:totalRequirementCount` | lcomp:ComplianceAssessment | xsd:integer | 总要求数 | 1 |
| `lcomp:passedCount` | lcomp:ComplianceAssessment | xsd:integer | 通过数 | 1 |
| `lcomp:failedCount` | lcomp:ComplianceAssessment | xsd:integer | 失败数 | 1 |
| `lcomp:inconclusiveCount` | lcomp:ComplianceAssessment | xsd:integer | 不确定数 | 0..1 |
| `lcomp:complianceRate` | lcomp:ComplianceAssessment | xsd:double | 符合率（%） | 0..1 |

**关系（v0.2 重构）：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcomp:aggregatesAssertions` | lcomp:ComplianceAssessment | lcomp:ComplianceAssertion | 聚合的断言 | 1..* |
| `lcomp:hasSubject` | lcomp:ComplianceAssessment | `llb:Entity` | 被评估对象 | 1 |

**v0.2 删除的属性：**
- ❌ `lcomp:hasOverallStatus`（判断归 Decision）
- ❌ `lcomp:assessmentResult`（判断归 Decision）
- ❌ `lcomp:basedOnAssessmentRule`（规则归 Decision）

**示例（v0.2 更新）：**

```turtle
lcomp:CA_Batch_001
    a lcomp:ComplianceAssessment ;
    lcomp:assessmentIdentifier "CA-BATCH-001" ;
    lcomp:assessmentName "批次 20260701 符合性汇总" ;
    lcomp:hasSubject lprod:Batch_202607 ;
    lcomp:aggregatesAssertions lcomp:CA_Temp_001 ;
    lcomp:aggregatesAssertions lcomp:CA_IP_001 ;
    lcomp:aggregatesAssertions lcomp:CA_Life_001 ;
    lcomp:totalRequirementCount "3"^^xsd:integer ;
    lcomp:passedCount "2"^^xsd:integer ;
    lcomp:failedCount "1"^^xsd:integer ;
    lcomp:complianceRate "66.7"^^xsd:double .
    # 注意：没有 overallStatus！判断由 Decision 做出
```

### 4.3 ComplianceDeclaration（对外符合性声明——v0.2 增强）

```
lcomp:ComplianceDeclaration
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "ComplianceDeclaration" ;
    rdfs:comment "面向外部利益相关者的符合性正式声明，具有法律效力。" .
```

**语义说明（v0.2 增强）：**

> ComplianceDeclaration 是对外发布的正式符合性声明，如"产品符合 IEC 60598 标准"。它是 Compliance 的最终输出形式，供 AI Agent、采购系统、监管机构等外部系统消费。

**属性（v0.2 新增法律属性）：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcomp:declarationIdentifier` | lcomp:ComplianceDeclaration | xsd:string | 声明编号 | 1 |
| `lcomp:declarationName` | lcomp:ComplianceDeclaration | xsd:string | 声明名称 | 1 |
| `lcomp:declarationDate` | lcomp:ComplianceDeclaration | xsd:dateTime | 声明日期 | 1 |
| `lcomp:declarationScope` | lcomp:ComplianceDeclaration | xsd:string | 声明范围 | 0..1 |
| `lcomp:declarationStatus` | lcomp:ComplianceDeclaration | `lcomp:DeclarationStatus` | 声明状态 | 1 |
| `lcomp:declarationType` | lcomp:ComplianceDeclaration | **`lcomp:DeclarationType`** | **声明类型（v0.2 新增）** | 1 |
| `lcomp:legalResponsibility` | lcomp:ComplianceDeclaration | xsd:string | **法律责任声明（v0.2 新增）** | 0..1 |
| `lcomp:validFrom` | lcomp:ComplianceDeclaration | xsd:date | **生效日期（v0.2 新增）** | 0..1 |
| `lcomp:validUntil` | lcomp:ComplianceDeclaration | xsd:date | **失效日期（v0.2 新增）** | 0..1 |

**关系（v0.2 增强）：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcomp:declaresAssessment` | lcomp:ComplianceDeclaration | lcomp:ComplianceAssessment | 声明的评估 | 1 |
| `lcomp:declaresProduct` | lcomp:ComplianceDeclaration | `lprod:Product` / `lprod:ProductType` | 声明的产品 | 1 |
| `lcomp:declaresStandard` | lcomp:ComplianceDeclaration | `lreq:RequirementSource` | 声明的标准/法规 | 0..1 |
| `lcomp:issuedBy` | lcomp:ComplianceDeclaration | `llb:Agent` | **签发者（v0.2 增强，范围扩大为 Agent）** | 1 |
| `lcomp:hasComplianceStatus` | lcomp:ComplianceDeclaration | `lcomp:ComplianceStatus` | 声明的符合性状态 | 1 |

**示例（v0.2 更新）：**

```turtle
lcomp:CD_IEC60598_001
    a lcomp:ComplianceDeclaration ;
    lcomp:declarationIdentifier "CD-IEC-2026-001" ;
    lcomp:declarationName "YD-GK-200W IEC 60598 符合性声明" ;
    lcomp:declarationDate "2026-07-28T15:00:00Z"^^xsd:dateTime ;
    lcomp:declarationStatus lcomp:Active ;
    lcomp:declarationType lcomp:SelfDeclaration ;
    lcomp:legalResponsibility "本声明基于真实测试数据" ;
    lcomp:validFrom "2026-07-28"^^xsd:date ;
    lcomp:validUntil "2027-07-28"^^xsd:date ;
    lcomp:declaresProduct lprod:YD_GK_200W ;
    lcomp:declaresStandard lreq:IEC60598_Source ;
    lcomp:declaresAssessment lcomp:CA_Batch_001 ;
    lcomp:hasComplianceStatus lcomp:Compliant ;
    lcomp:issuedBy leleby:YundaLighting .
```

### 4.4 ComplianceStatus（符合性状态）

```
lcomp:ComplianceStatus
    rdf:type owl:Class ;
    rdfs:label "ComplianceStatus" ;
    rdfs:comment "符合性状态枚举。" .
```

**预定义状态（v0.2 精简）：**

| 值 | 说明 | 适用层级 |
|----|------|----------|
| `lcomp:Compliant` | 符合 | Assertion / Declaration |
| `lcomp:NonCompliant` | 不符合 | Assertion / Declaration |
| `lcomp:PartiallyCompliant` | 部分符合 | Declaration |
| `lcomp:ConditionallyCompliant` | 条件符合 | Declaration |
| `lcomp:Unknown` | 未知 | Assertion |
| `lcomp:NotApplicable` | 不适用 | Assertion |

**v0.2 删除的状态（移至 DeclarationStatus）：**
- `lcomp:Expired` → 移至 `lcomp:DeclarationStatus.Expired`
- `lcomp:Suspended` → 移至 `lcomp:DeclarationStatus.Suspended`

### 4.5 DeclarationStatus（声明状态——v0.2 新增）

```
lcomp:DeclarationStatus
    rdf:type owl:Class ;
    rdfs:label "DeclarationStatus" ;
    rdfs:comment "声明生命周期状态枚举。" .
```

**预定义状态：**

| 值 | 说明 |
|----|------|
| `lcomp:Active` | 有效（当前有效） |
| `lcomp:Expired` | 已过期（从 ComplianceStatus 移入） |
| `lcomp:Suspended` | 已暂停（从 ComplianceStatus 移入） |
| `lcomp:Withdrawn` | 已撤回 |
| `lcomp:Draft` | 草案 |

### 4.6 DeclarationType（声明类型——v0.2 新增）

```
lcomp:DeclarationType
    rdf:type owl:Class ;
    rdfs:label "DeclarationType" ;
    rdfs:comment "声明类型枚举。" .
```

**预定义类型：**

| 值 | 说明 |
|----|------|
| `lcomp:SelfDeclaration` | 自我声明（企业自行声明） |
| `lcomp:ThirdPartyCertification` | 第三方认证（由认证机构颁发） |
| `lcomp:RegulatoryDeclaration` | 法规声明（针对法规要求） |
| `lcomp:ContractualDeclaration` | 合同声明（合同约定的符合性） |

### 4.7 ComplianceMatrix（符合性矩阵）

```
lcomp:ComplianceMatrix
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "ComplianceMatrix" ;
    rdfs:comment "符合性矩阵，展示多个对象对多个要求的符合性结果。属于 Application 层概念，用于数据可视化。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcomp:matrixName` | lcomp:ComplianceMatrix | xsd:string | 矩阵名称 | 1 |
| `lcomp:matrixIdentifier` | lcomp:ComplianceMatrix | xsd:string | 矩阵编号 | 0..1 |
| `lcomp:matrixDate` | lcomp:ComplianceMatrix | xsd:dateTime | 矩阵生成日期 | 0..1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcomp:includesAssertion` | lcomp:ComplianceMatrix | lcomp:ComplianceAssertion | 包含的断言 | 1..* |


## 5. 对象属性（v0.2 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| **`lcomp:conformsToRequirement`** | `lcomp:ComplianceAssertion` | **`lreq:Requirement`** | **满足的需求（v0.2 重构）** |
| **`lcomp:hasTarget`** | `lcomp:ComplianceAssertion` | **`lbo-core:SemanticTarget`** | **被评价的语义目标（v0.2 新增）** |
| `lcomp:hasSubject` | `lcomp:ComplianceAssertion` / `lcomp:ComplianceAssessment` | `llb:Entity` | 被评价对象 |
| `lcomp:basedOnVerification` | `lcomp:ComplianceAssertion` | `lver:VerificationResult` | 基于的验证结果 |
| `lcomp:supportedByEvidence` | `lcomp:ComplianceAssertion` | `llb:Document` | 支撑的证据 |
| `lcomp:hasComplianceStatus` | `lcomp:ComplianceAssertion` / `lcomp:ComplianceDeclaration` | `lcomp:ComplianceStatus` | 符合性状态 |
| `lcomp:assertedInContext` | `lcomp:ComplianceAssertion` | `lbo-core:EvaluationContext` | 断言上下文 |
| `lcomp:aggregatesAssertions` | `lcomp:ComplianceAssessment` | `lcomp:ComplianceAssertion` | 聚合的断言 |
| `lcomp:declaresAssessment` | `lcomp:ComplianceDeclaration` | `lcomp:ComplianceAssessment` | 声明的评估 |
| `lcomp:declaresProduct` | `lcomp:ComplianceDeclaration` | `lprod:Product` / `lprod:ProductType` | 声明的产品 |
| `lcomp:declaresStandard` | `lcomp:ComplianceDeclaration` | `lreq:RequirementSource` | 声明的标准 |
| `lcomp:issuedBy` | `lcomp:ComplianceDeclaration` | `llb:Agent` | 签发者 |
| `lcomp:includesAssertion` | `lcomp:ComplianceMatrix` | `lcomp:ComplianceAssertion` | 包含的断言 |


## 6. 数据属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lcomp:assertionIdentifier` | `lcomp:ComplianceAssertion` | xsd:string | 断言编号 |
| `lcomp:assertionDate` | `lcomp:ComplianceAssertion` | xsd:dateTime | 断言日期 |
| `lcomp:assertionDescription` | `lcomp:ComplianceAssertion` | xsd:string | 断言描述 |
| `lcomp:assessmentIdentifier` | `lcomp:ComplianceAssessment` | xsd:string | 评估编号 |
| `lcomp:assessmentName` | `lcomp:ComplianceAssessment` | xsd:string | 评估名称 |
| `lcomp:assessmentDate` | `lcomp:ComplianceAssessment` | xsd:dateTime | 评估日期 |
| `lcomp:totalRequirementCount` | `lcomp:ComplianceAssessment` | xsd:integer | 总要求数 |
| `lcomp:passedCount` | `lcomp:ComplianceAssessment` | xsd:integer | 通过数 |
| `lcomp:failedCount` | `lcomp:ComplianceAssessment` | xsd:integer | 失败数 |
| `lcomp:inconclusiveCount` | `lcomp:ComplianceAssessment` | xsd:integer | 不确定数 |
| `lcomp:complianceRate` | `lcomp:ComplianceAssessment` | xsd:double | 符合率 |
| `lcomp:declarationIdentifier` | `lcomp:ComplianceDeclaration` | xsd:string | 声明编号 |
| `lcomp:declarationName` | `lcomp:ComplianceDeclaration` | xsd:string | 声明名称 |
| `lcomp:declarationDate` | `lcomp:ComplianceDeclaration` | xsd:dateTime | 声明日期 |
| `lcomp:declarationScope` | `lcomp:ComplianceDeclaration` | xsd:string | 声明范围 |
| `lcomp:legalResponsibility` | `lcomp:ComplianceDeclaration` | xsd:string | 法律责任声明 |
| `lcomp:validFrom` | `lcomp:ComplianceDeclaration` | xsd:date | 生效日期 |
| `lcomp:validUntil` | `lcomp:ComplianceDeclaration` | xsd:date | 失效日期 |
| `lcomp:matrixName` | `lcomp:ComplianceMatrix` | xsd:string | 矩阵名称 |
| `lcomp:matrixIdentifier` | `lcomp:ComplianceMatrix` | xsd:string | 矩阵编号 |
| `lcomp:matrixDate` | `lcomp:ComplianceMatrix` | xsd:dateTime | 矩阵日期 |


## 7. 与其他模块的连接（v0.2 更新）

### 7.1 与 Requirement Ontology 的连接

```
Requirement（需求）
    │
    │  isConformedToBy（反向：Compliance 断言满足需求）
    ▼
ComplianceAssertion
```

**关系：**

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lcomp:conformsToRequirement` | `lcomp:ComplianceAssertion` | `lreq:Requirement` | 满足的需求 |

### 7.2 与 Verification Ontology 的连接

```
VerificationResult（验证结果）
    │
    │  providesEvidenceFor（反向：Compliance 基于验证）
    ▼
ComplianceAssertion
```

**关系：**

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lcomp:basedOnVerification` | `lcomp:ComplianceAssertion` | `lver:VerificationResult` | 基于的验证结果 |

### 7.3 与 Decision Ontology 的连接（v0.2 更新）

**v0.2 核心变化：** Decision 使用 Compliance，而非 Compliance 由 Decision 产生。

```
ComplianceAssessment（符合性评估）
    │
    │  isUsedBy（反向：Decision 使用符合性结果）
    ▼
DecisionResult（决策结果——在 Decision Ontology 中定义）
```

**关系（在 Decision Ontology 中定义）：**

```turtle
ldec:usesCompliance
    rdf:type owl:ObjectProperty ;
    rdfs:domain ldec:DecisionResult ;
    rdfs:range lcomp:ComplianceAssessment ;
    rdfs:label "usesCompliance" ;
    rdfs:comment "决策使用符合性评估结果" .
```

### 7.4 与 Measurement Ontology 的连接

> Compliance 不直接连接 Measurement。测量结果通过 Verification 间接引用。

```
MeasurementResult
    │
    │  verifiedBy（在 Verification 中）
    ▼
VerificationResult
    │
    │  basedOnVerification（在 Compliance 中）
    ▼
ComplianceAssertion
```

### 7.5 与 Specification Framework 的连接

> v0.2 删除 Compliance 与 Specification 的直接关系。Specification 是产品声明，Compliance 判断是否满足 Requirement。

### 7.6 与 Product Ontology 的连接

```
Product（产品）
    │
    │  hasComplianceAssertion（反向）
    ▼
ComplianceAssertion
```

### 7.7 接口总图（v0.2 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Compliance Ontology 与其他模块的接口（v0.2）            │
│                                                                             │
│  lreq: Requirement Ontology                                                 │
│  └── Requirement（被 lcomp:conformsToRequirement 引用）                    │
│         │                                                                  │
│         │  被满足                                                          │
│         ▼                                                                  │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║                       Compliance Ontology (lcomp:)                   ║ │
│  ║  ComplianceAssertion                                                  ║ │
│  ║  ├── conformsToRequirement → lreq:Requirement                        ║ │
│  ║  ├── hasTarget → lbo-core:SemanticTarget                             ║ │
│  ║  ├── basedOnVerification → lver:VerificationResult                  ║ │
│  ║  ├── hasSubject → llb:Entity                                        ║ │
│  ║  └── hasComplianceStatus → lcomp:ComplianceStatus                    ║ │
│  ║  ComplianceAssessment                                                 ║ │
│  ║  └── aggregatesAssertions → ComplianceAssertion                      ║ │
│  ║  ComplianceDeclaration                                                ║ │
│  ║  ├── declaresAssessment → ComplianceAssessment                       ║ │
│  ║  ├── declaresProduct → lprod:Product                                ║ │
│  ║  └── issuedBy → llb:Agent                                           ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│         │                                                                  │
│         │  被使用（Decision 使用 Compliance）                              │
│         ▼                                                                  │
│  ldec: Decision Ontology                                                   │
│  └── DecisionResult（usesCompliance → ComplianceAssessment）              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 8. 完整推理链路（v0.2 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Compliance 完整推理链路（v0.2）                          │
│                                                                             │
│  Step 1: Standard（标准体系——来自 Standard Ontology）                       │
│  定义：IEC 60598 标准                                                     │
│                                                                             │
│  Step 2: Requirement（需求——来自 Requirement Ontology）                     │
│  定义：工作温度 ≥ -40℃                                                    │
│                                                                             │
│  Step 3: Constraint（约束——来自 Constraint Ontology）                      │
│  定义：RangeConstraint [-40, 70]                                           │
│                                                                             │
│  Step 4: Measurement（测量——来自 Measurement Ontology）                    │
│  定义：实测温度 -42℃                                                      │
│                                                                             │
│  Step 5: Verification（验证——来自 Verification Ontology）                  │
│  定义：VerificationResult = PASS                                           │
│                                                                             │
│  Step 6: ComplianceAssertion（符合性断言——本模块 Level 1）                 │
│  定义：产品符合温度要求                                                    │
│                                                                             │
│  Step 7: ComplianceAssessment（符合性评估——本模块 Level 2）                │
│  定义：3 项要求，2 项通过，1 项失败                                        │
│                                                                             │
│  Step 8: ComplianceDeclaration（符合性声明——本模块 Level 3）               │
│  定义：产品符合 IEC 60598 标准                                             │
│                                                                             │
│  Step 9: Decision（决策——Decision Ontology）                              │
│  定义：使用 ComplianceAssessment，判断是否允许进入市场                      │
│                                                                             │
│  Step 10: Action（行动——Decision Ontology）                               │
│  定义：放行产品                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 9. 推理规则（v0.2 更新）

**规则 1：单项符合性判断**

```
IF
    VerificationResult = PASS
    AND
    VerificationResult is based on Requirement R
THEN
    ComplianceAssertion CA
        hasSubject = Product
        conformsToRequirement = R
        hasComplianceStatus = Compliant
```

**规则 2：单项不符合性判断**

```
IF
    VerificationResult = FAIL
    AND
    VerificationResult is based on Requirement R
THEN
    ComplianceAssertion CA
        hasSubject = Product
        conformsToRequirement = R
        hasComplianceStatus = NonCompliant
```

**规则 3：符合性聚合统计**

```
IF
    ComplianceAssertion CA1...CAn all have same Subject
    AND
    n = count(CA1...CAn)
    AND
    passed = count(CA where status = Compliant)
    AND
    failed = count(CA where status = NonCompliant)
THEN
    ComplianceAssessment CAgg
        aggregatesAssertions = CA1...CAn
        totalRequirementCount = n
        passedCount = passed
        failedCount = failed
        complianceRate = passed / n * 100
    # 注意：不做合格/不合格判断
```

**规则 4：符合性声明生成**

```
IF
    ComplianceAssessment CAgg has complianceRate >= threshold
    AND
    Product P is subject of CAgg
    AND
    Organization O is issuer
THEN
    ComplianceDeclaration CD
        declaresAssessment = CAgg
        declaresProduct = P
        issuedBy = O
        hasComplianceStatus = Compliant
    # threshold 由 Decision 规则确定
```


## 10. SHACL 验证约束（v0.2 更新）

### 10.1 ComplianceAssertion 约束（v0.2 更新）

```turtle
lcomp:ComplianceAssertionShape
    a sh:NodeShape ;
    sh:targetClass lcomp:ComplianceAssertion ;
    sh:property [
        sh:path lcomp:assertionIdentifier ;
        sh:minCount 1 ;
        sh:message "ComplianceAssertion must have an identifier" ;
    ] ;
    sh:property [
        sh:path lcomp:hasSubject ;
        sh:minCount 1 ;
        sh:message "ComplianceAssertion must have a subject" ;
    ] ;
    sh:property [
        sh:path lcomp:conformsToRequirement ;
        sh:minCount 1 ;
        sh:message "ComplianceAssertion must conform to a requirement" ;
    ] ;
    sh:property [
        sh:path lcomp:basedOnVerification ;
        sh:minCount 1 ;
        sh:message "ComplianceAssertion must be based on a verification result" ;
    ] ;
    sh:property [
        sh:path lcomp:hasComplianceStatus ;
        sh:minCount 1 ;
        sh:in (
            lcomp:Compliant
            lcomp:NonCompliant
            lcomp:PartiallyCompliant
            lcomp:ConditionallyCompliant
            lcomp:Unknown
            lcomp:NotApplicable
        ) ;
        sh:message "ComplianceStatus must be one of predefined values" ;
    ] .
```

### 10.2 ComplianceAssessment 约束（v0.2 更新）

```turtle
lcomp:ComplianceAssessmentShape
    a sh:NodeShape ;
    sh:targetClass lcomp:ComplianceAssessment ;
    sh:property [
        sh:path lcomp:assessmentIdentifier ;
        sh:minCount 1 ;
        sh:message "ComplianceAssessment must have an identifier" ;
    ] ;
    sh:property [
        sh:path lcomp:assessmentName ;
        sh:minCount 1 ;
        sh:message "ComplianceAssessment must have a name" ;
    ] ;
    sh:property [
        sh:path lcomp:aggregatesAssertions ;
        sh:minCount 1 ;
        sh:message "ComplianceAssessment must aggregate at least one assertion" ;
    ] ;
    sh:property [
        sh:path lcomp:totalRequirementCount ;
        sh:minCount 1 ;
        sh:message "ComplianceAssessment must have total requirement count" ;
    ] ;
    sh:property [
        sh:path lcomp:passedCount ;
        sh:minCount 0 ;
        sh:message "ComplianceAssessment may have passed count" ;
    ] ;
    sh:property [
        sh:path lcomp:failedCount ;
        sh:minCount 0 ;
        sh:message "ComplianceAssessment may have failed count" ;
    ] ;
    sh:property [
        sh:path lcomp:hasOverallStatus ;
        sh:minCount 0 ;
        sh:message "ComplianceAssessment must NOT have overall status (moved to Decision)" ;
    ] .
```

### 10.3 ComplianceDeclaration 约束（v0.2 更新）

```turtle
lcomp:ComplianceDeclarationShape
    a sh:NodeShape ;
    sh:targetClass lcomp:ComplianceDeclaration ;
    sh:property [
        sh:path lcomp:declarationIdentifier ;
        sh:minCount 1 ;
        sh:message "ComplianceDeclaration must have an identifier" ;
    ] ;
    sh:property [
        sh:path lcomp:declarationName ;
        sh:minCount 1 ;
        sh:message "ComplianceDeclaration must have a name" ;
    ] ;
    sh:property [
        sh:path lcomp:declaresProduct ;
        sh:minCount 1 ;
        sh:message "ComplianceDeclaration must declare a product" ;
    ] ;
    sh:property [
        sh:path lcomp:issuedBy ;
        sh:minCount 1 ;
        sh:message "ComplianceDeclaration must have an issuer" ;
    ] ;
    sh:property [
        sh:path lcomp:declarationType ;
        sh:minCount 1 ;
        sh:in (
            lcomp:SelfDeclaration
            lcomp:ThirdPartyCertification
            lcomp:RegulatoryDeclaration
            lcomp:ContractualDeclaration
        ) ;
        sh:message "DeclarationType must be one of predefined values" ;
    ] .
```


## 11. 完整示例（v0.2 更新）

### 11.1 示例一：产品单项符合性断言

```turtle
# 1. 需求
lreq:REQ_Temp_001
    a lreq:Requirement ;
    lreq:hasRequirementIdentifier "REQ-TEMP-001" ;
    lreq:hasRequirementName "工作温度要求" ;
    lreq:hasTargetElement [
        a lreq:CharacteristicTarget ;
        lreq:targetCharacteristic lbo-core:OperatingTemperature
    ] ;
    lreq:hasConstraint [
        a lcon:RangeConstraint ;
        lcon:minValue [ -40℃ ]
    ] .

# 2. 验证结果
lver:Result_Temp_001
    a lver:VerificationResult ;
    lver:resultStatus lver:PASS ;
    lver:confidence "0.95"^^xsd:double .

# 3. 符合性断言（v0.2：使用 conformsToRequirement）
lcomp:CA_Temp_001
    a lcomp:ComplianceAssertion ;
    lcomp:assertionIdentifier "CA-TEMP-001" ;
    lcomp:assertionDate "2026-07-28T14:30:00Z"^^xsd:dateTime ;
    lcomp:assertionDescription "产品 A 的温度要求符合性" ;
    lcomp:hasSubject lprod:YD_GK_200W ;
    lcomp:hasTarget lreq:Target_Temp ;
    lcomp:conformsToRequirement lreq:REQ_Temp_001 ;
    lcomp:basedOnVerification lver:Result_Temp_001 ;
    lcomp:hasComplianceStatus lcomp:Compliant ;
    lcomp:assertedInContext lcore:Context_25C_Ambient ;
    lcomp:supportedByEvidence [
        a llb:Document ;
        llb:hasIdentifier "EVID-SGS-001" ;
        rdfs:label "SGS 温度测试报告"
    ] .
```

### 11.2 示例二：批次整体符合性汇总（v0.2 更新——不做判断）

```turtle
# 1. 多个单项符合性断言
lcomp:CA_Temp_Batch
    a lcomp:ComplianceAssertion ;
    lcomp:hasSubject lprod:Batch_202607 ;
    lcomp:conformsToRequirement lreq:REQ_Temp_001 ;
    lcomp:hasComplianceStatus lcomp:Compliant .

lcomp:CA_IP_Batch
    a lcomp:ComplianceAssertion ;
    lcomp:hasSubject lprod:Batch_202607 ;
    lcomp:conformsToRequirement lreq:REQ_IP_001 ;
    lcomp:hasComplianceStatus lcomp:Compliant .

lcomp:CA_Life_Batch
    a lcomp:ComplianceAssertion ;
    lcomp:hasSubject lprod:Batch_202607 ;
    lcomp:conformsToRequirement lreq:REQ_Life_001 ;
    lcomp:hasComplianceStatus lcomp:NonCompliant .

# 2. 整体符合性汇总（v0.2：仅统计数据，不判断合格/不合格）
lcomp:CA_Batch_202607
    a lcomp:ComplianceAssessment ;
    lcomp:assessmentIdentifier "CA-BATCH-202607" ;
    lcomp:assessmentName "批次 202607 符合性汇总" ;
    lcomp:hasSubject lprod:Batch_202607 ;
    lcomp:aggregatesAssertions lcomp:CA_Temp_Batch ;
    lcomp:aggregatesAssertions lcomp:CA_IP_Batch ;
    lcomp:aggregatesAssertions lcomp:CA_Life_Batch ;
    lcomp:totalRequirementCount "3"^^xsd:integer ;
    lcomp:passedCount "2"^^xsd:integer ;
    lcomp:failedCount "1"^^xsd:integer ;
    lcomp:complianceRate "66.7"^^xsd:double .
    # 注意：没有 overallStatus！由 Decision 判断是否合格
```

### 11.3 示例三：对外符合性声明（v0.2 增强）

```turtle
lcomp:CD_IEC60598_2026
    a lcomp:ComplianceDeclaration ;
    lcomp:declarationIdentifier "CD-IEC-2026-001" ;
    lcomp:declarationName "YD-GK-200W IEC 60598 符合性声明" ;
    lcomp:declarationDate "2026-07-28T15:00:00Z"^^xsd:dateTime ;
    lcomp:declarationStatus lcomp:Active ;
    lcomp:declarationType lcomp:SelfDeclaration ;
    lcomp:legalResponsibility "本声明基于真实测试数据，企业对声明内容承担法律责任" ;
    lcomp:validFrom "2026-07-28"^^xsd:date ;
    lcomp:validUntil "2027-07-28"^^xsd:date ;
    lcomp:declaresProduct lprod:YD_GK_200W ;
    lcomp:declaresStandard lreq:IEC60598_Source ;
    lcomp:declaresAssessment lcomp:CA_Batch_202607 ;
    lcomp:hasComplianceStatus lcomp:Compliant ;
    lcomp:issuedBy leleby:YundaLighting .
```


## 12. 核心类汇总

### 12.1 Classes（v0.2 更新）

| 类名 | 父类 | 说明 |
|---|---|---|
| `lcomp:ComplianceAssertion` | `lbo-core:Assessment` | 单项符合性断言（v0.2 重构） |
| `lcomp:ComplianceAssessment` | `lbo-core:Assessment` | 整体符合性汇总（v0.2 重构，不做判断） |
| `lcomp:ComplianceDeclaration` | `llb:Statement` | 对外符合性声明（v0.2 增强） |
| `lcomp:ComplianceStatus` | — | 符合性状态枚举（v0.2 精简） |
| `lcomp:DeclarationStatus` | — | 声明生命周期状态（v0.2 新增） |
| `lcomp:DeclarationType` | — | 声明类型（v0.2 新增） |
| `lcomp:ComplianceMatrix` | `llb:Concept` | 符合性矩阵（Application 层） |

### 12.2 Object Properties（v0.2 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| **`lcomp:conformsToRequirement`** | `lcomp:ComplianceAssertion` | **`lreq:Requirement`** | **满足的需求（v0.2 重构）** |
| **`lcomp:hasTarget`** | `lcomp:ComplianceAssertion` | **`lbo-core:SemanticTarget`** | **语义目标（v0.2 新增）** |
| `lcomp:hasSubject` | `lcomp:ComplianceAssertion` / `lcomp:ComplianceAssessment` | `llb:Entity` | 被评价对象 |
| `lcomp:basedOnVerification` | `lcomp:ComplianceAssertion` | `lver:VerificationResult` | 基于的验证结果 |
| `lcomp:supportedByEvidence` | `lcomp:ComplianceAssertion` | `llb:Document` | 支撑的证据 |
| `lcomp:hasComplianceStatus` | `lcomp:ComplianceAssertion` / `lcomp:ComplianceDeclaration` | `lcomp:ComplianceStatus` | 符合性状态 |
| `lcomp:assertedInContext` | `lcomp:ComplianceAssertion` | `lbo-core:EvaluationContext` | 断言上下文 |
| `lcomp:aggregatesAssertions` | `lcomp:ComplianceAssessment` | `lcomp:ComplianceAssertion` | 聚合的断言 |
| `lcomp:declaresAssessment` | `lcomp:ComplianceDeclaration` | `lcomp:ComplianceAssessment` | 声明的评估 |
| `lcomp:declaresProduct` | `lcomp:ComplianceDeclaration` | `lprod:Product` | 声明的产品 |
| `lcomp:declaresStandard` | `lcomp:ComplianceDeclaration` | `lreq:RequirementSource` | 声明的标准 |
| `lcomp:issuedBy` | `lcomp:ComplianceDeclaration` | `llb:Agent` | 签发者 |


## 13. 冻结声明

### 13.1 冻结范围

v0.2 确认后，以下内容进入**冻结状态**：

- ✅ 三级符合性模型（Assertion + Assessment + Declaration）
- ✅ **Conformance 语义（conformsToRequirement）**
- ✅ **SemanticTarget 接口（hasTarget）**
- ✅ **Compliance 与 Decision 的分离关系**
- ✅ ComplianceStatus 核心状态
- ✅ DeclarationStatus 和 DeclarationType
- ✅ 与 Requirement/Verification 的接口
- ✅ 命名空间 `https://ontology.leleby.org/compliance/`

### 13.2 冻结后允许

- ✅ 新增 ComplianceStatus 值
- ✅ 新增 DeclarationStatus 值
- ✅ 新增 DeclarationType 值
- ✅ 新增推理规则
- ✅ **新增 ComplianceMatrix 子类（Application 层扩展）**

### 13.3 冻结后禁止

- ❌ **修改三级符合性模型结构**
- ❌ **修改 Conformance 语义（必须使用 conformsTo）**
- ❌ **将 Decision 关系改回"Decision 产生 Compliance"**（必须是"Decision 使用 Compliance"）
- ❌ **在 Compliance 中直接连接 Measurement**（必须通过 Verification）
- ❌ **在 Compliance 中重新定义 Specification 评价**
- ❌ **将 ComplianceLevel 加回 Core**（属于行业扩展）


## 14. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| **v0.1** | **2026-07-28** | **初始设计版**：定义 Compliance 三级模型；ComplianceAssertion / ComplianceAssessment / ComplianceDeclaration；ComplianceStatus / ComplianceLevel / ComplianceMatrix；完整推理链；与各模块的连接；SHACL 验证 |
| **v0.2** | **2026-08-04** | **语义判断对齐版**：1）Compliance 与 Decision 解耦——Decision 使用 Compliance，而非 Compliance 由 Decision 产生；2）`evaluatesRequirement` 改为 `conformsToRequirement`；3）删除 `evaluatesSpecification`；4）新增 `hasTarget` → `lbo-core:SemanticTarget`；5）ComplianceAssessment 改为仅做聚合统计，不判断合格/不合格；6）删除 ComplianceLevel（标记为行业扩展）；7）拆分 ComplianceStatus：Expired/Suspended 移至 DeclarationStatus；8）新增 DeclarationType 和 legalResponsibility；9）删除 `determinedByDecision` 属性；10）更新 SHACL 约束；11）更新完整示例 |


*— leleby Compliance Ontology Specification v0.2 — Semantic Judgment Alignment Release —*