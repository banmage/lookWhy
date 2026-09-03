# leleby Core Ontology Specification v1.3

**文档版本：** v1.3 — Semantic Role Refinement Release（语义角色精炼版）

**文档类型：** 模块规范（Module Ontology Specification）

**文档状态：** ✅ **正式冻结（Frozen）** — 核心工业概念模型已正式冻结，仅允许模块内部扩展

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.2

**依赖模块：**
- `llb` Foundation Vocabulary Specification v1.0
- `lcon` Constraint Ontology Specification v1.2（通过引用关系依赖）

**命名空间：** `https://ontology.leleby.org/core/`

**推荐前缀：** `lbo-core`

**目标受众：** 本体架构师、领域本体设计师、企业数据架构师、AI Agent 开发者


## 目录

1. 引言
   1.1 目的
   1.2 v1.3 核心定位
   1.3 v1.3 与 v1.2 的核心差异
   1.4 设计原则
   1.5 与其他模块的关系
   1.6 与 Foundation Vocabulary 的边界

2. 命名空间声明
3. 核心概念模型
   3.1 顶层概念模型（v1.3 更新）
   3.2 产品与组织模型
   3.3 规范与验证模型（v1.3 更新）
   3.4 能力与过程模型
   3.5 约束与评估模型（v1.3 更新）
   3.6 语义目标角色模型（v1.3 重构）

4. 类规范
   4.1 IndustrialEntity（工业实体）
   4.2 Organization（组织）
   4.3 Product（产品）
   4.4 ProductType（产品类型）
   4.5 ProductInstance（产品实例）
   4.6 Capability（能力）
   4.7 Function（功能）
   4.8 Process（过程）
   4.9 Resource（资源）
   4.10 Specification（规范——抽象类）
   4.11 Requirement（需求——抽象类）
   4.12 Characteristic（特性）
   4.13 SemanticTarget（语义目标——v1.3 重构）
   4.14 Function（作为 SemanticTarget 的子类——v1.3 新增）
   4.15 Interface（接口——v1.3 新增）
   4.16 Structure（结构——v1.3 新增）
   4.17 Relationship（关系——v1.3 新增）
   4.18 Process（作为 SemanticTarget 的子类——v1.3 新增）
   4.19 ObligationLevel（强制程度）
   4.20 Assessment（评估——抽象类）
   4.21 ConstraintEvaluation（约束评估）
   4.22 VerificationAssessment（验证评估）
   4.23 ComplianceAssessment（合规评估）

5. 对象属性（v1.3 更新）
   5.1 身份与归属属性
   5.2 结构与组成属性（v1.3 更新）
   5.3 生命周期属性
   5.4 能力与功能属性
   5.5 规范与符合性属性（v1.3 更新）
   5.6 评估与验证属性（v1.3 更新）
   5.7 语义目标角色属性（v1.3 新增）

6. 数据属性
7. 推理规则（v1.3 更新）
   7.1 符合性传递规则
   7.2 能力推断规则
   7.3 需求满足规则
   7.4 评估聚合规则
   7.5 语义目标角色推理规则（v1.3 新增）
   7.6 评估目标推理规则（v1.3 新增）

8. SHACL 验证约束（v1.3 更新）
9. RDF/OWL 表示（v1.3 更新）
10. 完整示例（v1.3 更新）
11. 冻结声明
12. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Core Ontology 是 leleby 语义基础设施的**核心工业世界模型层**。它定义了工业世界中最基本的通用概念及其相互关系，是所有工业领域本体的共同基础。

**本模块的核心职责：**

- 定义跨所有工业领域共享的核心概念（Product、Organization、Capability、Process、Specification、Requirement、Characteristic、**SemanticTarget** 等）
- 建立这些核心概念之间的基本关系
- **不进入具体行业领域**（如 Motor、Luminaire、Battery 属于 Domain Ontology）
- **不重复 Foundation Vocabulary**（如 Entity、Identifier、Document 已在 llb 中定义）
- **不定义 Constraint 的具体类型**（属于 Constraint Ontology）

本规范是 leleby Core Ontology 的正式冻结版本 v1.3。

### 1.2 v1.3 核心定位

> **Core Ontology 是 leleby 语义体系从"语言基础"进入"工业世界模型"的第一层。v1.3 将 SemanticTarget 精炼为跨模块的"语义角色"体系——任何工业元素（特性、功能、接口、结构、关系、过程）在被 Requirement、Specification、Measurement、Constraint 引用时，均扮演"目标角色"。这种设计消除了不必要的 Wrapper 类，使跨模块引用更加自然和简洁。**

| 层次 | 模块 | 回答的问题 |
|---|---|---|
| 基础层 | `llb` Foundation Vocabulary | 如何表达语义？ |
| **世界模型层** | **`lbo-core` Core Ontology** | **工业世界中最基本的对象和关系是什么？** |
| 领域扩展层 | `lbo-domain` Domain Ontology | 特定行业有哪些具体概念？ |
| 规范实例层 | `lbs` Semantic Package | 某个具体标准如何表达？ |
| 商业实例层 | `llc` Commercial Instance | 某个具体企业/产品是什么？ |

### 1.3 v1.3 与 v1.2 的核心差异

| 问题 | v1.2 状态 | v1.3 修正 |
|---|---|---|
| **SemanticTarget 设计** | 类型继承体系（6 个 Wrapper 子类） | **角色扮演体系**，删除 Wrapper 类，直接让工业元素扮演目标角色 |
| **CharacteristicTarget** | 存在，指向 Characteristic | **删除**，Characteristic 直接作为 SemanticTarget 的子类 |
| **FunctionTarget** | 存在，指向 Function | **删除**，Function 直接作为 SemanticTarget 的子类 |
| **InterfaceTarget** | 存在，指向 Interface | **删除**，Interface 直接作为 SemanticTarget 的子类 |
| **StructureTarget** | 存在，指向 Structure | **删除**，Structure 直接作为 SemanticTarget 的子类 |
| **RelationshipTarget** | 存在，指向 Relationship | **删除**，Relationship 直接作为 SemanticTarget 的子类 |
| **ProcessTarget** | 存在，指向 Process | **删除**，Process 直接作为 SemanticTarget 的子类 |
| **反向属性** | 无 | **新增 `isTargetOf`**，表达元素被谁作为目标引用 |
| **Specification 接口** | 有 `specifiesTarget` | **移除**，通过 Requirement 间接指向目标 |
| **Assessment 接口** | 无 | **新增 `evaluatesTarget`**，支持评估语义目标 |

### 1.4 设计原则

**原则一：不重复 Foundation Vocabulary**

`lbo-core:` 不重新定义 `llb:` 中已有的类（Entity、Identifier、Document、Statement、Quantity 等）。Core Ontology 直接继承并使用这些基础概念。

**原则二：不进入行业领域**

Core Ontology 只定义跨行业共享的通用概念。Motor、Luminaire、Battery、Pump 等属于 Domain Ontology。

**原则三：不定义 Constraint 具体类型**

Constraint 的具体类型（RangeConstraint、ToleranceConstraint 等）属于 `lbo-constraint:ConstraintOntology`。Core Ontology 仅通过 `lcon:Constraint` 引用。

**原则四：Requirement 和 Specification 是抽象类**

Core Ontology 中的 `Requirement` 和 `Specification` 是工业世界的抽象概念，具体语义由 `lbo-req:RequirementOntology` 和 `lbo-spec:SpecificationFrameworkOntology` 扩展。

**原则五：评估体系统一**

Core Ontology 建立统一的评估体系（Assessment），ConstraintEvaluation、VerificationAssessment、ComplianceAssessment 均继承自 Assessment。

**原则六：语义目标是角色，而非类型（v1.3 重构）**

`SemanticTarget` 不是一种新的实体类型，而是任何工业元素（特性、功能、接口、结构、关系、过程）在被 Requirement、Specification、Measurement、Constraint 引用时所扮演的**语义角色**。一个元素可以同时是多个模块的目标。

**原则七：稳定性优先**

Core Ontology 一旦冻结，应保持长期稳定。行业特定的扩展应在 Domain Ontology 层进行。

### 1.5 与其他模块的关系

```
llb: Foundation Vocabulary（基础词汇层）
    │
    │  继承/扩展
    ▼
lbo-core: Core Ontology（世界模型层 — 本模块）
    │
    │  提供 SemanticTarget 角色体系给所有模块（v1.3 重构）
    │  提供 ObligationLevel 给所有模块
    │  引用 Constraint Ontology（lcon:Constraint）
    │
    │  继承/扩展
    ▼
┌───────────────────────────────────────────────────────────────┐
│  Domain Modules（领域模块）                                 │
│  ├── lbo-req: Requirement Ontology（扩展 Requirement）        │
│  ├── lbo-spec: Specification Framework（扩展 Specification） │
│  ├── lbo-meas: Measurement Ontology（引用 SemanticTarget）   │
│  ├── lprod: Product Ontology（引用 SemanticTarget）          │
│  └── ...                                                    │
└───────────────────────────────────────────────────────────────┘
    │
    │  实例化
    ▼
lbs: Semantic Package（规范实例层）
    │
    │  实例化
    ▼
llc: Commercial Instance（商业实例层）
```

### 1.6 与 Foundation Vocabulary 的边界

| 概念 | 归属 | 理由 |
|---|---|---|
| `Entity`、`Identifier`、`Document`、`Statement`、`Quantity`、`Agent` | `llb:` | 纯元概念，无工业语义 |
| **`IndustrialEntity`、`Organization`、`Product`、`Capability`、`Process`、`Specification`、`Requirement`、`Characteristic`、`SemanticTarget`、`ObligationLevel`、`Assessment`** | **`lbo-core:`** | **具有工业语义的核心概念** |
| `Motor`、`Luminaire`、`Battery`、`Pump` | `lbo-domain:` | 具体行业领域概念 |
| `RangeConstraint`、`ToleranceConstraint`、`LogicalConstraint` | `lbo-constraint:` | 约束具体类型，独立模块 |


## 2. 命名空间声明

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix llb: <https://ontology.leleby.org/foundation/> .
@prefix lbo-core: <https://ontology.leleby.org/core/> .
@prefix lcon: <https://ontology.leleby.org/constraint/> .

<https://ontology.leleby.org/core/>
    rdf:type owl:Ontology ;
    owl:versionInfo "1.3" ;
    owl:imports <https://ontology.leleby.org/foundation/> ;
    rdfs:label "leleby Core Ontology" ;
    rdfs:comment "leleby 语义基础设施的核心工业世界模型层，定义跨行业共享的基本工业概念，包含 SemanticTarget 跨模块共享目标角色体系" .
```


## 3. 核心概念模型

### 3.1 顶层概念模型（v1.3 更新）

```
llb:Entity（来自 Foundation Vocabulary）
    │
    └── lbo-core:IndustrialEntity（工业实体）
            │
            ├── lbo-core:Organization（组织）
            │
            ├── lbo-core:Product（产品）
            │       ├── lbo-core:ProductType（产品类型）
            │       └── lbo-core:ProductInstance（产品实例）
            │
            ├── lbo-core:Process（过程） ← 同时是 SemanticTarget 的子类
            │
            └── lbo-core:Resource（资源）

llb:Concept（来自 Foundation Vocabulary）
    │
    ├── lbo-core:SemanticTarget（语义目标——v1.3 重构）
    │       │
    │       ├── lbo-core:Characteristic（特性）← 直接作为 SemanticTarget 子类
    │       ├── lbo-core:Function（功能）← 同时是 SemanticTarget 子类
    │       ├── lbo-core:Interface（接口）← v1.3 新增
    │       ├── lbo-core:Structure（结构）← v1.3 新增
    │       ├── lbo-core:Relationship（关系）← v1.3 新增
    │       └── lbo-core:Process（过程）← 多重继承
    │
    ├── lbo-core:Capability（能力）
    │
    └── lbo-core:ObligationLevel（强制程度）

llb:Statement（来自 Foundation Vocabulary）
    │
    ├── lbo-core:Specification（规范——抽象类）
    │
    ├── lbo-core:Requirement（需求——抽象类）
    │
    └── lbo-core:Assessment（评估——抽象类）
            │
            ├── lbo-core:ConstraintEvaluation（约束评估）
            │
            └── lbo-core:VerificationAssessment（验证评估）
                    │
                    └── lbo-core:ComplianceAssessment（合规评估）
```

### 3.2 产品与组织模型

```
Organization（组织）
    │
    ├── hasCapability → Capability（组织能力）
    │
    ├── manufactures → Product（制造的产品）
    │
    └── performs → Process（执行的过程）

Product（产品）
    │
    ├── hasProductType → ProductType（产品类型）
    │
    ├── hasInstance → ProductInstance（产品实例）
    │
    ├── providesFunction → Function（提供的功能）
    │
    ├── hasSpecification → Specification（产品规范）
    │
    ├── manufacturedBy → Organization（制造者）
    │
    └── conformsTo → Specification（符合的规范）
```

### 3.3 规范与验证模型（v1.3 更新）

```
Specification（规范——抽象类）
    │
    ├── definesRequirement → Requirement（定义的需求）
    │
    └── appliesTo → IndustrialEntity（适用的对象）

Requirement（需求——抽象类）
    │
    ├── 具体目标由 lreq:hasTargetElement → SemanticTarget 管理（在 Requirement Ontology 中定义）
    │
    └── hasConstraint → lcon:Constraint（约束——来自 Constraint Ontology）

Assessment（评估——抽象类）
    │
    ├── assesses → IndustrialEntity（评估的对象）
    │
    ├── evaluatesTarget → SemanticTarget（评估的目标——v1.3 新增）
    │
    └── produces → llb:Statement（产生的声明）

ConstraintEvaluation（约束评估）
    │
    ├── evaluatesConstraint → lcon:Constraint（评估的约束）
    │
    ├── subjectValue → lbo-meas:MeasurementResult（被评估的值）
    │
    └── result → EvaluationResult（PASS/FAIL/UNKNOWN）

VerificationAssessment（验证评估）
    │
    ├── basedOn → Requirement（基于的需求）
    │
    └── hasEvidence → llb:Document（证据文件）

ComplianceAssessment（合规评估）
    │
    ├── assesses → Product / ProductInstance（评估的产品）
    │
    ├── basedOn → Specification（基于的规范）
    │
    ├── result → ComplianceStatus（COMPLIANT/NON_COMPLIANT）
    │
    └── hasEvidence → llb:Document（证据文件）
```

### 3.4 能力与过程模型

```
Capability（能力）
    │
    ├── hasCapabilityType → CapabilityType（能力类型）
    │
    └── realizedBy → Process（通过过程实现）

Process（过程）
    │
    ├── hasInput → Resource（输入资源）
    │
    ├── hasOutput → Product（输出产品）
    │
    ├── performedBy → Organization（执行者）
    │
    └── realizesCapability → Capability（实现的能力）

Resource（资源）
    │
    ├── Material（材料）
    ├── Equipment（设备）
    ├── Energy（能源）
    └── Information（信息）
```

### 3.5 约束与评估模型（v1.3 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    v1.3 约束与评估模型                                      │
│                                                                             │
│  Core Ontology 不定义 Constraint 的具体类型。                              │
│  Constraint 由 lbo-constraint:ConstraintOntology 独立定义。               │
│  Core 通过 lcon:Constraint 引用。                                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Assessment（评估——抽象类）                      │   │
│  │  - assesses → IndustrialEntity（评估对象主体）                     │   │
│  │  - evaluatesTarget → SemanticTarget（评估目标——v1.3 新增）        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                    ┌───────────────┼───────────────┐                    │
│                    │               │               │                    │
│                    ▼               ▼               ▼                    │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │
│  │  Constraint         │  │  Verification   │  │  Compliance         │   │
│  │  Evaluation         │  │  Assessment     │  │  Assessment         │   │
│  │  （约束评估）        │  │  （验证评估）    │  │  （合规评估）        │   │
│  │  PASS/FAIL/UNKNOWN  │  │  （验证执行）    │  │  COMPLIANT/         │   │
│  │                     │  │                 │  │  NON_COMPLIANT      │   │
│  └─────────────────────┘  └─────────────────┘  └─────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  lcon:Constraint（来自 Constraint Ontology）                       │   │
│  │  被 Requirement 引用，被 ConstraintEvaluation 评估                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.6 语义目标角色模型（v1.3 重构）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SemanticTarget 角色模型（v1.3 重构）                     │
│                                                                             │
│  SemanticTarget 是 Core 层的共享"语义角色"，而非"类型体系"。                │
│  任何工业元素（特性、功能、接口、结构、关系、过程）在被 Requirement、        │
│  Specification、Measurement、Constraint 引用时，均扮演"目标角色"。          │
│                                                                             │
│  核心设计原则：                                                             │
│  1. SemanticTarget 是角色（Role），不是类型（Type）                        │
│  2. 元素本身直接继承 SemanticTarget，无需额外 Wrapper 类                   │
│  3. 一个元素可同时被多个模块作为目标引用                                   │
│  4. 通过 isTargetOf 反向追踪引用者                                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SemanticTarget（语义目标角色）                   │   │
│  │  被 Requirement / Specification / Measurement / Constraint 引用的  │   │
│  │  工程语义元素所扮演的角色                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│     ┌──────────────┬───────────────┼───────────────┬──────────────┐       │
│     │              │               │               │              │       │
│     ▼              ▼               ▼               ▼              ▼       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Character │  │ Function │  │ Interface│  │Structure │  │Relation  │   │
│  │-istic    │  │          │  │          │  │          │  │ship      │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│       │             │             │             │             │           │
│       ▼             ▼             ▼             ▼             ▼           │
│  可被测量      可被要求      可被规格化      可被约束      可被评估        │
│                                                                             │
│  注：Process 同时是工业实体和语义目标（多重继承）                           │
│                                                                             │
│  跨模块统一引用方式：                                                       │
│  - Requirement Ontology: lreq:hasTargetElement → lbo-core:SemanticTarget   │
│  - Specification Framework: lspec:specifies → lbo-core:SemanticTarget      │
│  - Measurement Ontology: lbo-meas:observes → lbo-core:SemanticTarget       │
│  - Constraint Ontology: lcon:constrains → lbo-core:SemanticTarget          │
│  - Assessment: lbo-core:evaluatesTarget → lbo-core:SemanticTarget          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 4. 类规范

### 4.1 IndustrialEntity（工业实体）

```turtle
lbo-core:IndustrialEntity
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "IndustrialEntity" ;
    rdfs:comment "参与工业活动、供应链、制造系统或商业交互的实体。这是所有工业概念的顶层抽象类" .
```

### 4.2 Organization（组织）

```turtle
lbo-core:Organization
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Agent ;
    rdfs:label "Organization" ;
    rdfs:comment "具有独立法律或运营身份的工业组织，如企业、标准机构、监管机构等" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo-core:hasLegalName` | 法定名称 | 1 |
| `lbo-core:hasTradeName` | 商号/品牌名称 | 0..1 |
| `lbo-core:hasTaxId` | 税务登记号 | 0..1 |
| `lbo-core:hasOrganizationType` | 组织类型 | 0..1 |

**OrganizationType 枚举：**

| 值 | 说明 |
|---|---|
| `lbo-core:Manufacturer` | 制造商 |
| `lbo-core:Supplier` | 供应商 |
| `lbo-core:StandardBody` | 标准机构 |
| `lbo-core:Regulator` | 监管机构 |
| `lbo-core:Customer` | 客户 |
| `lbo-core:Distributor` | 分销商 |

### 4.3 Product（产品）

```turtle
lbo-core:Product
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:IndustrialEntity ;
    rdfs:label "Product" ;
    rdfs:comment "经过设计、制造或交付以提供特定功能或能力的工业实体" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo-core:hasProductName` | 产品名称 | 1 |
| `lbo-core:hasProductCode` | 产品代码/型号 | 0..1 |
| `lbo-core:hasProductCategory` | 产品类别 | 0..1 |

### 4.4 ProductType（产品类型）

```turtle
lbo-core:ProductType
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Product ;
    rdfs:label "ProductType" ;
    rdfs:comment "产品的类型/型号定义，代表一类产品的共同特征" .
```

### 4.5 ProductInstance（产品实例）

```turtle
lbo-core:ProductInstance
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Product ;
    rdfs:label "ProductInstance" ;
    rdfs:comment "产品的具体个体实例，具有唯一序列号或批次号" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo-core:hasSerialNumber` | 序列号 | 0..1 |
| `lbo-core:hasBatchNumber` | 批次号 | 0..1 |
| `lbo-core:manufacturedDate` | 生产日期 | 0..1 |

### 4.6 Capability（能力）

```turtle
lbo-core:Capability
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "Capability" ;
    rdfs:comment "实体执行特定活动或提供特定功能的潜在能力" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo-core:hasCapabilityName` | 能力名称 | 1 |
| `lbo-core:hasCapabilityLevel` | 能力等级 | 0..1 |
| `lbo-core:hasCapabilityType` | 能力类型 | 0..1 |

### 4.7 Function（功能）

```turtle
lbo-core:Function
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:SemanticTarget ;  -- v1.3：直接作为 SemanticTarget 子类
    rdfs:label "Function" ;
    rdfs:comment "产品/系统在特定条件下能够执行的行为或任务。同时作为 SemanticTarget 的角色体现" .
```

### 4.8 Process（过程）

```turtle
lbo-core:Process
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:IndustrialEntity , lbo-core:SemanticTarget ;  -- v1.3：多重继承
    rdfs:label "Process" ;
    rdfs:comment "将输入转化为输出的活动序列，消耗资源并产生价值。既是工业实体，也可作为语义目标" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo-core:hasProcessName` | 过程名称 | 1 |
| `lbo-core:hasProcessType` | 过程类型 | 0..1 |

### 4.9 Resource（资源）

```turtle
lbo-core:Resource
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:IndustrialEntity ;
    rdfs:label "Resource" ;
    rdfs:comment "工业活动中消耗或使用的物质、能量或信息" .
```

**子类：**

| 子类 | 说明 |
|---|---|
| `lbo-core:Material` | 材料 |
| `lbo-core:Equipment` | 设备 |
| `lbo-core:Energy` | 能源 |
| `lbo-core:Information` | 信息 |

### 4.10 Specification（规范——抽象类）

```turtle
lbo-core:Specification
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "Specification" ;
    rdfs:comment "规范（抽象类），描述产品、过程或服务应满足的技术要求。具体语义由 lbo-spec:SpecificationFrameworkOntology 扩展" .
```

**v1.3 说明：**

> Specification 不直接指向 SemanticTarget。Specification 通过 `definesRequirement` 定义 Requirement，由 Requirement 的 `lreq:hasTargetElement` 指向 SemanticTarget。这种间接引用确保了规范层与目标层的清晰分离。

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-core:definesRequirement` | Specification | `lbo-core:Requirement` | 定义的需求 | 1..* |
| `lbo-core:appliesTo` | Specification | `lbo-core:IndustrialEntity` | 适用的对象 | 0..1 |

### 4.11 Requirement（需求——抽象类）

```turtle
lbo-core:Requirement
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "Requirement" ;
    rdfs:comment "需求（抽象类），产品、过程或服务必须满足的约束性期望。具体语义由 lbo-req:RequirementOntology 扩展" .
```

**v1.3 重要说明：**

> `lbo-core:Requirement` 是 Core Ontology 中的**抽象类**，不直接实例化。具体需求类型由 `lbo-req:RequirementOntology` 定义。
>
> **v1.2 已移除 `appliesTo` 属性：** Requirement 的具体约束目标不由 Core 层的 `appliesTo`（指向 `IndustrialEntity`）管理，而由 Requirement Ontology 的 `lreq:hasTargetElement`（指向 `SemanticTarget`）管理。这反映了 Requirement 不直接约束产品主体，而是约束产品所拥有的语义目标元素（特性、功能、接口、关系、结构、过程等）的设计原则。

**保留的关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-core:hasConstraint` | Requirement | `lcon:Constraint` | 约束（来自 Constraint Ontology） | 1..* |

### 4.12 Characteristic（特性）

```turtle
lbo-core:Characteristic
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:SemanticTarget ;  -- v1.3：直接作为 SemanticTarget 子类
    rdfs:label "Characteristic" ;
    rdfs:comment "实体可测量的属性或质量特征，如温度、功率、效率等。它是连接 Requirement、Specification、Measurement、Constraint 的桥梁。作为 SemanticTarget 的角色体现" .
```

**子类：**

| 子类 | 说明 | 示例 |
|---|---|---|
| `lbo-core:PhysicalCharacteristic` | 物理特性 | 温度、尺寸、质量 |
| `lbo-core:FunctionalCharacteristic` | 功能特性 | 旋转运动、照明 |
| `lbo-core:PerformanceCharacteristic` | 性能特性 | 效率、功率、速度 |
| `lbo-core:EnvironmentalCharacteristic` | 环境特性 | 防护等级、工作温度范围 |
| `lbo-core:QualityCharacteristic` | 质量特性 | 可靠性、寿命、精度 |

**v1.3 定位：**

> Characteristic 是 `SemanticTarget` 的直接子类。Requirement 通过 `hasTargetElement` → `Characteristic` 直接指向特性，无需经过 `CharacteristicTarget` Wrapper 类。

### 4.13 SemanticTarget（语义目标 — v1.3 重构）

```turtle
lbo-core:SemanticTarget
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "SemanticTarget" ;
    rdfs:comment "语义目标的抽象基类。表示被 Requirement、Specification、Measurement、Constraint、Assessment 引用的工程语义元素所扮演的角色。任何工业元素（特性、功能、接口、结构、关系、过程）在被引用时均可扮演此角色" .
```

**跨模块引用（v1.3 统一）：**

| 模块 | 使用方式 |
|---|---|
| Requirement Ontology | `lreq:hasTargetElement → lbo-core:SemanticTarget` |
| Specification Framework | `lspec:specifies → lbo-core:SemanticTarget` |
| Measurement Ontology | `lbo-meas:observes → lbo-core:SemanticTarget` |
| Constraint Ontology | `lcon:constrains → lbo-core:SemanticTarget` |
| Core Assessment | `lbo-core:evaluatesTarget → lbo-core:SemanticTarget` |

### 4.14 Interface（接口 — v1.3 新增）

```turtle
lbo-core:Interface
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:SemanticTarget ;
    rdfs:label "Interface" ;
    rdfs:comment "产品/系统与外部交互的边界点，如电气接口、通信接口、机械接口等。作为 SemanticTarget 的角色体现" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo-core:interfaceType` | 接口类型（电气/通信/机械/光学/流体） | 1 |
| `lbo-core:interfaceProtocol` | 接口协议/标准 | 0..1 |

### 4.15 Structure（结构 — v1.3 新增）

```turtle
lbo-core:Structure
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:SemanticTarget ;
    rdfs:label "Structure" ;
    rdfs:comment "产品的结构元素，如框架、外壳、支架等。作为 SemanticTarget 的角色体现" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo-core:structureType` | 结构类型 | 0..1 |
| `lbo-core:structureMaterial` | 结构材料 | 0..1 |

### 4.16 Relationship（关系 — v1.3 新增）

```turtle
lbo-core:Relationship
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:SemanticTarget ;
    rdfs:label "Relationship" ;
    rdfs:comment "产品之间的工程关系，如部件关系、连接关系、装配关系、兼容关系等。作为 SemanticTarget 的角色体现。详细语义由 Product Ontology 的 ProductRelationship 定义" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-core:relationshipType` | Relationship | rdfs:Class | 关系类型 | 0..1 |

### 4.17 Process（作为 SemanticTarget 的子类 — v1.3 新增）

已在 4.8 中定义，此处不再重复。

### 4.18 ObligationLevel（强制程度）

```turtle
lbo-core:ObligationLevel
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "ObligationLevel" ;
    rdfs:comment "强制程度，跨模块共享。被 Requirement、Standard、Constraint 等模块统一引用" .
```

**预定义级别：**

| 值 | 说明 | 对应 ISO 术语 |
|---|---|---|
| `lbo-core:Mandatory` | 强制 | "shall" |
| `lbo-core:ConditionalMandatory` | 条件强制 | "shall" under certain conditions |
| `lbo-core:Required` | 要求 | "should" |
| `lbo-core:Recommended` | 推荐 | "recommended" |
| `lbo-core:Optional` | 可选 | "may" |
| `lbo-core:Informative` | 参考 | "informative" |

### 4.19 Assessment（评估——抽象类）

```turtle
lbo-core:Assessment
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "Assessment" ;
    rdfs:comment "评估（抽象类），对实体进行评估的活动及其结果。评估结果分为约束评估、验证评估、合规评估三个层级" .
```

**v1.3 新增关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-core:evaluatesTarget` | Assessment | `lbo-core:SemanticTarget` | **评估的目标（v1.3 新增）** | 0..* |

### 4.20 ConstraintEvaluation（约束评估）

```turtle
lbo-core:ConstraintEvaluation
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Assessment ;
    rdfs:label "ConstraintEvaluation" ;
    rdfs:comment "约束评估：判断一个值是否满足指定的约束" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-core:evaluatesConstraint` | ConstraintEvaluation | `lcon:Constraint` | 评估的约束 | 1 |
| `lbo-core:subjectValue` | ConstraintEvaluation | `lbo-meas:MeasurementResult` | 被评估的值 | 1 |
| `lbo-core:evaluationResult` | ConstraintEvaluation | `lbo-core:EvaluationResult` | 评估结果 | 1 |

### 4.21 VerificationAssessment（验证评估）

```turtle
lbo-core:VerificationAssessment
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Assessment ;
    rdfs:label "VerificationAssessment" ;
    rdfs:comment "验证评估：通过测试、检验等方法验证产品是否符合需求" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-core:basedOn` | VerificationAssessment | `lbo-core:Requirement` | 基于的需求 | 1 |
| `lbo-core:hasEvidence` | VerificationAssessment | `llb:Document` | 证据文件 | 0..* |

### 4.22 ComplianceAssessment（合规评估）

```turtle
lbo-core:ComplianceAssessment
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:VerificationAssessment ;
    rdfs:label "ComplianceAssessment" ;
    rdfs:comment "合规评估：判断产品是否符合特定规范或标准的评估" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-core:assesses` | ComplianceAssessment | `lbo-core:Product` / `lbo-core:ProductInstance` | 评估的产品 | 1 |
| `lbo-core:basedOn` | ComplianceAssessment | `lbo-core:Specification` | 基于的规范 | 1 |
| `lbo-core:complianceResult` | ComplianceAssessment | `lbo-core:ComplianceStatus` | 合规结果 | 1 |
| `lbo-core:hasEvidence` | ComplianceAssessment | `llb:Document` | 证据文件 | 0..* |
| `lbo-core:hasIssuer` | ComplianceAssessment | `lbo-core:Organization` | 评估发布者 | 0..1 |


## 5. 对象属性（v1.3 更新）

### 5.1 身份与归属属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-core:hasIdentifier` | `lbo-core:IndustrialEntity` | `llb:Identifier` | 实体拥有的标识符 |
| `lbo-core:hasName` | `lbo-core:IndustrialEntity` | `xsd:string` | 实体名称 |
| `lbo-core:belongsTo` | `lbo-core:IndustrialEntity` | `lbo-core:Organization` | 属于某组织 |

### 5.2 结构与组成属性（v1.3 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-core:hasPart` | `lbo-core:Product` | `lbo-core:Product` | **简化关系**：产品包含的部件。详细部件关系语义（数量、角色、连接方式等）由 Product Ontology 的 `PartRelationship` 定义。此属性仅表达"存在包含关系"，不携带工程语义。 |
| `lbo-core:partOf` | `lbo-core:Product` | `lbo-core:Product` | 属于某个产品 |
| `lbo-core:hasProductType` | `lbo-core:Product` | `lbo-core:ProductType` | 产品类型 |
| `lbo-core:hasInstance` | `lbo-core:ProductType` | `lbo-core:ProductInstance` | 产品实例 |
| `lbo-core:hasBOM` | `lbo-core:Product` | `lbo-core:BOMStructure` | BOM 结构 |

### 5.3 生命周期属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-core:manufacturedBy` | `lbo-core:Product` | `lbo-core:Organization` | 制造者 |
| `lbo-core:designedBy` | `lbo-core:Product` | `lbo-core:Organization` | 设计者 |
| `lbo-core:suppliedBy` | `lbo-core:Product` | `lbo-core:Organization` | 供应商 |
| `lbo-core:performedBy` | `lbo-core:Process` | `lbo-core:Organization` | 执行者 |

### 5.4 能力与功能属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-core:hasCapability` | `lbo-core:Organization` / `lbo-core:Product` | `lbo-core:Capability` | 拥有的能力 |
| `lbo-core:providesFunction` | `lbo-core:Product` | `lbo-core:Function` | 提供的功能 |
| `lbo-core:realizesCapability` | `lbo-core:Process` | `lbo-core:Capability` | 实现的能力 |
| `lbo-core:hasInput` | `lbo-core:Process` | `lbo-core:Resource` | 输入资源 |
| `lbo-core:hasOutput` | `lbo-core:Process` | `lbo-core:Product` | 输出产品 |

### 5.5 规范与符合性属性（v1.3 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-core:hasSpecification` | `lbo-core:Product` | `lbo-core:Specification` | 产品规范 |
| `lbo-core:definesRequirement` | `lbo-core:Specification` | `lbo-core:Requirement` | 定义的需求 |
| `lbo-core:appliesTo` | `lbo-core:Specification` / `lbo-core:ComplianceAssessment` | `lbo-core:IndustrialEntity` | 适用主体范围 |
| `lbo-core:hasConstraint` | `lbo-core:Requirement` | `lcon:Constraint` | 约束（来自 Constraint Ontology） |
| `lbo-core:conformsTo` | `lbo-core:Product` | `lbo-core:Specification` | 符合的规范 |
| `lbo-core:satisfies` | `lbo-core:Product` / `lbo-core:ProductInstance` | `lbo-core:Requirement` | 满足的需求 |

### 5.6 评估与验证属性（v1.3 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-core:assesses` | `lbo-core:ComplianceAssessment` | `lbo-core:Product` / `lbo-core:ProductInstance` | 评估的产品 |
| **`lbo-core:evaluatesTarget`** | **`lbo-core:Assessment`** | **`lbo-core:SemanticTarget`** | **评估的目标（v1.3 新增）** |
| `lbo-core:basedOn` | `lbo-core:VerificationAssessment` / `lbo-core:ComplianceAssessment` | `lbo-core:Requirement` / `lbo-core:Specification` | 基于的需求或规范 |
| `lbo-core:producesStatement` | `lbo-core:Assessment` | `llb:Statement` | 产生的声明 |
| `lbo-core:hasEvidence` | `lbo-core:VerificationAssessment` / `lbo-core:ComplianceAssessment` | `llb:Document` | 证据文件 |
| `lbo-core:evaluatesConstraint` | `lbo-core:ConstraintEvaluation` | `lcon:Constraint` | 评估的约束 |
| `lbo-core:subjectValue` | `lbo-core:ConstraintEvaluation` | `lbo-meas:MeasurementResult` | 被评估的值 |

### 5.7 语义目标角色属性（v1.3 新增）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| **`lbo-core:isTargetOf`** | **`lbo-core:SemanticTarget`** | **`llb:Statement`** | **反向属性：该语义目标被谁作为目标引用（Requirement / Specification / Measurement / Constraint / Assessment）** |


## 6. 数据属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-core:hasLegalName` | `lbo-core:Organization` | `xsd:string` | 法定名称 |
| `lbo-core:hasTradeName` | `lbo-core:Organization` | `xsd:string` | 商号 |
| `lbo-core:hasProductName` | `lbo-core:Product` | `xsd:string` | 产品名称 |
| `lbo-core:hasSerialNumber` | `lbo-core:ProductInstance` | `xsd:string` | 序列号 |
| `lbo-core:hasBatchNumber` | `lbo-core:ProductInstance` | `xsd:string` | 批次号 |
| `lbo-core:hasRequirementText` | `lbo-core:Requirement` | `xsd:string` | 需求原文（抽象类属性，由子模块使用） |
| `lbo-core:complianceResult` | `lbo-core:ComplianceAssessment` | `lbo-core:ComplianceStatus` | 合规结果 |
| `lbo-core:evaluationResult` | `lbo-core:ConstraintEvaluation` | `lbo-core:EvaluationResult` | 约束评估结果 |
| `lbo-core:interfaceType` | `lbo-core:Interface` | `xsd:string` | 接口类型 |
| `lbo-core:structureType` | `lbo-core:Structure` | `xsd:string` | 结构类型 |
| `lbo-core:relationshipType` | `lbo-core:Relationship` | `xsd:string` | 关系类型 |


## 7. 推理规则（v1.3 更新）

### 7.1 符合性传递规则

**规则1：如果产品符合某规范，且该规范定义了需求，则产品满足该需求。**

```
IF Product conformsTo Specification
AND Specification definesRequirement Requirement
THEN Product satisfies Requirement
```

**规则2：如果产品类型符合某规范，则该类型的所有实例也符合该规范。**

```
IF ProductType conformsTo Specification
AND ProductType hasInstance ProductInstance
THEN ProductInstance conformsTo Specification
```

### 7.2 能力推断规则

**规则3：如果组织制造某产品，则组织具有制造该产品的能力。**

```
IF Organization manufactures Product
THEN Organization hasCapability ManufacturingCapability
```

**规则4：如果产品提供某功能，则该产品具有相应的能力。**

```
IF Product providesFunction Function
THEN Product hasCapability Capability
```

### 7.3 需求满足规则

**规则5：如果产品满足某需求的所有约束，则产品满足该需求。**

```
IF Product hasMeasurement Result
AND Requirement hasConstraint Constraint
AND Result satisfies Constraint
THEN Product satisfies Requirement
```

### 7.4 评估聚合规则

**规则6：如果所有约束评估均为 PASS，则验证评估为通过。**

```
IF VerificationAssessment is basedOn Requirement R
AND R hasConstraint C1...Cn
AND all ConstraintEvaluation on C1...Cn result PASS
THEN VerificationAssessment result PASS
```

**规则7：如果验证评估通过，且规范所有需求均满足，则合规评估为 COMPLIANT。**

```
IF ComplianceAssessment assesses Product P
AND P satisfies all Requirements in Specification S
THEN ComplianceAssessment result COMPLIANT
```

### 7.5 语义目标角色推理规则（v1.3 新增）

**规则8：SemanticTarget 角色传播规则**

```
IF Characteristic C is a lbo-core:Characteristic
AND C is a subclass of lbo-core:SemanticTarget
THEN C can be used as a target of Requirement / Measurement / Constraint / Assessment
```

**规则9：SemanticTarget 反向追踪规则**

```
IF Requirement R hasTargetElement SemanticTarget ST
THEN ST isTargetOf R
```

**规则10：跨模块语义目标一致性规则**

```
IF lreq:Requirement R hasTargetElement lbo-core:SemanticTarget ST
AND lbo-meas:MeasurementObservation M observes lbo-core:SemanticTarget ST
AND lcon:Constraint C constrains lbo-core:SemanticTarget ST
THEN R, M, and C refer to the same engineering element
```

### 7.6 评估目标推理规则（v1.3 新增）

**规则11：评估目标与需求目标对齐规则**

```
IF Assessment A evaluatesTarget SemanticTarget ST
AND Requirement R hasTargetElement ST
THEN A provides evidence for R
```

**规则12：约束评估目标推理规则**

```
IF ConstraintEvaluation CE evaluatesConstraint C
AND C constrains SemanticTarget ST
THEN CE evaluatesTarget ST
```


## 8. SHACL 验证约束（v1.3 更新）

### 8.1 Organization 约束

```turtle
lbo-core:OrganizationShape
    a sh:NodeShape ;
    sh:targetClass lbo-core:Organization ;
    sh:property [
        sh:path lbo-core:hasLegalName ;
        sh:minCount 1 ;
        sh:message "Organization 必须有法定名称"
    ] .
```

### 8.2 Product 约束

```turtle
lbo-core:ProductShape
    a sh:NodeShape ;
    sh:targetClass lbo-core:Product ;
    sh:property [
        sh:path lbo-core:hasProductName ;
        sh:minCount 1 ;
        sh:message "Product 必须有产品名称"
    ] .
```

### 8.3 ProductInstance 约束

```turtle
lbo-core:ProductInstanceShape
    a sh:NodeShape ;
    sh:targetClass lbo-core:ProductInstance ;
    sh:or (
        [ sh:path lbo-core:hasSerialNumber ; sh:minCount 1 ]
        [ sh:path lbo-core:hasBatchNumber ; sh:minCount 1 ]
    ) ;
    sh:message "ProductInstance 必须有序列号或批次号" .
```

### 8.4 Specification 约束

```turtle
lbo-core:SpecificationShape
    a sh:NodeShape ;
    sh:targetClass lbo-core:Specification ;
    sh:property [
        sh:path lbo-core:definesRequirement ;
        sh:minCount 1 ;
        sh:message "Specification 必须定义至少一个 Requirement"
    ] .
```

### 8.5 Requirement 约束（v1.3 更新）

```turtle
lbo-core:RequirementShape
    a sh:NodeShape ;
    sh:targetClass lbo-core:Requirement ;
    sh:property [
        sh:path lbo-core:hasConstraint ;
        sh:minCount 1 ;
        sh:message "Requirement 必须引用至少一个 Constraint"
    ] ;
    sh:property [
        sh:path lbo-core:appliesTo ;
        sh:minCount 0 ;
        sh:message "Requirement 不再使用 appliesTo（具体目标由 Requirement Ontology 的 hasTargetElement 管理）"
    ] .
```

### 8.6 SemanticTarget 约束（v1.3 重构）

```turtle
# SemanticTarget 抽象类约束
lbo-core:SemanticTargetShape
    a sh:NodeShape ;
    sh:targetClass lbo-core:SemanticTarget ;
    sh:closed true ;
    sh:message "SemanticTarget 的子类应为 Characteristic、Function、Interface、Structure、Relationship、Process" .

# Characteristic 作为 SemanticTarget 子类
lbo-core:CharacteristicShape
    a sh:NodeShape ;
    sh:targetClass lbo-core:Characteristic ;
    sh:property [
        sh:path llb:hasName ;
        sh:minCount 1 ;
        sh:message "Characteristic 必须有名称"
    ] .

# Function 作为 SemanticTarget 子类（v1.3 新增）
lbo-core:FunctionShape
    a sh:NodeShape ;
    sh:targetClass lbo-core:Function ;
    sh:property [
        sh:path llb:hasName ;
        sh:minCount 1 ;
        sh:message "Function 必须有名称"
    ] .

# Interface 作为 SemanticTarget 子类（v1.3 新增）
lbo-core:InterfaceShape
    a sh:NodeShape ;
    sh:targetClass lbo-core:Interface ;
    sh:property [
        sh:path lbo-core:interfaceType ;
        sh:minCount 1 ;
        sh:message "Interface 必须有接口类型"
    ] .
```

### 8.7 ConstraintEvaluation 约束

```turtle
lbo-core:ConstraintEvaluationShape
    a sh:NodeShape ;
    sh:targetClass lbo-core:ConstraintEvaluation ;
    sh:property [
        sh:path lbo-core:evaluatesConstraint ;
        sh:minCount 1 ;
        sh:message "ConstraintEvaluation 必须指定评估的约束"
    ] ;
    sh:property [
        sh:path lbo-core:subjectValue ;
        sh:minCount 1 ;
        sh:message "ConstraintEvaluation 必须有被评估的值"
    ] ;
    sh:property [
        sh:path lbo-core:evaluationResult ;
        sh:minCount 1 ;
        sh:message "ConstraintEvaluation 必须有评估结果"
    ] .
```

### 8.8 Assessment 约束（v1.3 新增）

```turtle
lbo-core:AssessmentShape
    a sh:NodeShape ;
    sh:targetClass lbo-core:Assessment ;
    sh:or (
        [
            sh:property [
                sh:path lbo-core:assesses ;
                sh:minCount 1 ;
                sh:message "Assessment 必须评估至少一个对象"
            ]
        ]
        [
            sh:property [
                sh:path lbo-core:evaluatesTarget ;
                sh:minCount 1 ;
                sh:message "Assessment 必须评估至少一个目标"
            ]
        ]
    ) .
```


## 9. RDF/OWL 表示（v1.3 更新）

```turtle
@prefix lbo-core: <https://ontology.leleby.org/core/> .

# IndustrialEntity
lbo-core:IndustrialEntity
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity .

# Organization
lbo-core:Organization
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Agent .

# Product
lbo-core:Product
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:IndustrialEntity .

# SemanticTarget（v1.3 重构）
lbo-core:SemanticTarget
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept .

# Characteristic（直接作为 SemanticTarget 子类 — v1.3 重构）
lbo-core:Characteristic
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:SemanticTarget .

# Function（直接作为 SemanticTarget 子类 — v1.3 重构）
lbo-core:Function
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:SemanticTarget .

# Interface（v1.3 新增）
lbo-core:Interface
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:SemanticTarget .

# Structure（v1.3 新增）
lbo-core:Structure
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:SemanticTarget .

# Relationship（v1.3 新增）
lbo-core:Relationship
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:SemanticTarget .

# Process（多重继承 — v1.3 重构）
lbo-core:Process
    rdf:type owl:Class ;
    rdfs:subClassOf (
        lbo-core:IndustrialEntity
        lbo-core:SemanticTarget
    ) .

# ObligationLevel
lbo-core:ObligationLevel
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept .

# Assessment 抽象类
lbo-core:Assessment
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement .

# ConstraintEvaluation
lbo-core:ConstraintEvaluation
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Assessment .

# VerificationAssessment
lbo-core:VerificationAssessment
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Assessment .

# ComplianceAssessment
lbo-core:ComplianceAssessment
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:VerificationAssessment .

# 语义目标角色属性（v1.3 新增）
lbo-core:isTargetOf
    rdf:type owl:ObjectProperty ;
    rdfs:domain lbo-core:SemanticTarget ;
    rdfs:range llb:Statement ;
    rdfs:label "isTargetOf" ;
    rdfs:comment "反向属性：该语义目标被谁作为目标引用" .

# 评估目标属性（v1.3 新增）
lbo-core:evaluatesTarget
    rdf:type owl:ObjectProperty ;
    rdfs:domain lbo-core:Assessment ;
    rdfs:range lbo-core:SemanticTarget ;
    rdfs:label "evaluatesTarget" ;
    rdfs:comment "评估活动直接评估的语义目标" .
```


## 10. 完整示例（v1.3 更新）

### 10.1 场景：Yunda Lighting 产品与合规（使用 SemanticTarget 角色）

**组织：Yunda Lighting**

```turtle
llc:YundaLighting
    a lbo-core:Organization ;
    lbo-core:hasLegalName "Yunda Lighting Co., Ltd." ;
    lbo-core:hasOrganizationType lbo-core:Manufacturer .
```

**产品：**

```turtle
llc:OutdoorLuminaireX100
    a lbo-core:ProductType ;
    lbo-core:hasProductName "Outdoor LED Luminaire X100" .
```

**特性（直接作为 SemanticTarget 子类 — v1.3 重构）：**

```turtle
lbo-core:OperatingTemperature
    a lbo-core:PhysicalCharacteristic ;  -- Characteristic 是 SemanticTarget 子类
    llb:hasName "Operating Temperature" .
```

**规范与需求：**

```turtle
llc:LuminaireSpecification
    a lbo-core:Specification ;
    llb:hasIdentifier "SPEC-001" ;
    lbo-core:appliesTo llc:OutdoorLuminaireX100 .

llc:TempRequirement
    a lbo-core:Requirement ;
    llb:hasIdentifier "REQ-TEMP-001" ;
    lbo-core:hasConstraint lcon:Constraint_Temp .

llc:LuminaireSpecification
    lbo-core:definesRequirement llc:TempRequirement .

# 在 Requirement Ontology 中，通过 hasTargetElement 直接指向 OperatingTemperature
lreq:REQ_Temp_001
    a lreq:Requirement ;
    lreq:hasTargetElement lbo-core:OperatingTemperature .
```

**推理：**

```turtle
llc:OutdoorLuminaireX100
    lbo-core:conformsTo llc:LuminaireSpecification .

# 规则1 触发
llc:OutdoorLuminaireX100
    lbo-core:satisfies llc:TempRequirement .
```

### 10.2 语义目标跨模块统一示例（v1.3 重构）

```turtle
# 目标：OperatingTemperature（直接作为 SemanticTarget）
lbo-core:OperatingTemperature
    a lbo-core:PhysicalCharacteristic ;
    llb:hasName "Operating Temperature" .

# Requirement 指向目标
lreq:REQ_Temp_001
    a lreq:Requirement ;
    lreq:hasTargetElement lbo-core:OperatingTemperature .

# Measurement 观测目标
lbo-meas:Temp_Observation
    a lbo-meas:MeasurementObservation ;
    lbo-meas:observes lbo-core:OperatingTemperature .

# Constraint 约束目标
lcon:Constraint_Temp_Range
    a lcon:RangeConstraint ;
    lcon:constrains lbo-core:OperatingTemperature .

# Assessment 评估目标（v1.3 新增）
llc:Temp_Assessment
    a lbo-core:ConstraintEvaluation ;
    lbo-core:evaluatesTarget lbo-core:OperatingTemperature .

# 反向追踪：谁引用了 OperatingTemperature？
lbo-core:OperatingTemperature
    lbo-core:isTargetOf lreq:REQ_Temp_001 ;
    lbo-core:isTargetOf lbo-meas:Temp_Observation ;
    lbo-core:isTargetOf lcon:Constraint_Temp_Range .
```


## 11. 冻结声明

### 11.1 冻结范围

v1.3 确认后，以下内容进入**正式冻结状态**：

- ✅ 所有核心类（IndustrialEntity、Organization、Product、ProductType、ProductInstance、Capability、Function、Process、Resource、Specification、Requirement、Characteristic、**SemanticTarget 及其子类**、ObligationLevel、Assessment、ConstraintEvaluation、VerificationAssessment、ComplianceAssessment）
- ✅ 所有核心对象属性（含 v1.3 新增的 `evaluatesTarget`、`isTargetOf`）
- ✅ 命名空间 `https://ontology.leleby.org/core/`
- ✅ 与 Foundation Vocabulary 的继承接口
- ✅ 与 Constraint Ontology 的引用关系（`hasConstraint → lcon:Constraint`）
- ✅ **SemanticTarget 跨模块共享角色体系**（v1.3 重构）
- ✅ 核心推理规则（含 v1.3 新增的语义目标角色推理规则）

### 11.2 冻结后允许

- ✅ 新增子类（如 Product 的子类）
- ✅ 新增属性（如新的关系）
- ✅ 新增推理规则（不改变现有规则语义）
- ✅ 新增 Characteristic 子类
- ✅ 新增 OrganizationType 枚举值
- ✅ **新增 SemanticTarget 子类（扩展点——但任何新增子类都应遵循"角色而非类型"原则）**

### 11.3 冻结后禁止

- ❌ **修改或删除任何现有核心类**
- ❌ **修改或删除任何现有核心属性**
- ❌ **改变核心推理规则**
- ❌ **在 Core 中添加行业领域类**（如 Motor、Luminaire、Battery）
- ❌ **在 Core 中定义 Constraint 具体类型**（属于 Constraint Ontology）
- ❌ **将 Requirement 或 Specification 从抽象类改为具体类**
- ❌ **将 SemanticTarget 回退为包含 Wrapper 类的类型继承体系**
- ❌ **恢复 `specifiesTarget` 作为 Specification 的直接属性**（目标应通过 Requirement 间接引用）


## 12. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v1.0 | 2026-07-31 | 正式冻结版：定义核心工业世界模型 |
| v1.1 | 2026-07-31 | 跨模块一致性版：删除 Constraint；Requirement/Specification 明确为抽象类；重构 Assessment 体系；新增 ObligationLevel；新增 Characteristic 子类 |
| v1.2 | 2026-08-04 | 语义目标对齐版：新增 SemanticTarget 抽象类及 6 个 Wrapper 子类；移除 Requirement 的 appliesTo 属性；新增 specifiesTarget 属性 |
| **v1.3** | **2026-08-04** | **语义角色精炼版**：1）SemanticTarget 从"类型继承体系"重构为"角色扮演体系"，删除 `CharacteristicTarget`、`FunctionTarget`、`InterfaceTarget`、`StructureTarget`、`RelationshipTarget`、`ProcessTarget` 六个 Wrapper 类；2）`Characteristic`、`Function`、`Interface`、`Structure`、`Relationship`、`Process` 直接作为 `SemanticTarget` 的子类；3）新增 `Interface`、`Structure`、`Relationship` 三个新类；4）新增 `isTargetOf` 反向属性；5）新增 `evaluatesTarget` 属性（Assessment → SemanticTarget）；6）移除 Specification 的 `specifiesTarget` 属性；7）Process 实现多重继承（IndustrialEntity + SemanticTarget）；8）新增语义目标角色推理规则（规则 8-10）；9）新增评估目标推理规则（规则 11-12）；10）更新 SHACL 验证约束；11）更新冻结声明 |


*— leleby Core Ontology Specification v1.3 — Semantic Role Refinement Release —*