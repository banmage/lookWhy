# leleby Requirement Ontology Specification v1.2

**文档版本：** v1.2 — Final Clarification Release（最终澄清版）

**文档类型：** 模块规范（Module Ontology Specification）

**文档状态：** ✅ **正式冻结（Frozen）** — 六元语义框架已正式冻结，仅允许在指定扩展点进行模块内部扩展。

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.2

**依赖模块：**
- `llb` Foundation Vocabulary Specification v1.0
- `lbo-core` Core Ontology Specification v1.1
- `lbo-constraint` Constraint Ontology Specification v1.2
- `lbo-meas` Measurement Ontology Specification（待定）
- `lprod` Product Ontology Specification v0.4

**对齐模块：** Standard Ontology Specification v1.3 | Specification Framework Ontology Specification v1.2 | Verification Ontology Specification

**命名空间：** `https://ontology.leleby.org/requirement/`

**推荐前缀：** `lreq`

**目标受众：** 本体架构师、需求工程师、标准工程师、AI Agent 开发者


## 目录

1. 引言
   1.1 目的
   1.2 核心定位
   1.3 v1.2 与 v1.1 的核心差异
   1.4 核心模型声明

2. 设计原则
   2.1 要求语义原则（六元模型）
   2.2 来源权威原则
   2.3 约束独立原则
   2.4 条件上下文共享原则
   2.5 强制程度统一原则
   2.6 模块边界原则
   2.7 目标通用化原则

3. 核心概念模型
   3.1 Requirement（要求）
   3.2 六元核心模型（v1.2 澄清）
   3.3 六元关系定义

4. Requirement Source Model（要求来源模型）
   4.1 设计思想
   4.2 RequirementAuthority（提出者）
   4.3 RequirementSource（来源引用）
   4.4 Authority/Source/Requirement 关系
   4.5 示例：完整来源追溯

5. Requirement Target Model（要求目标模型）
   5.1 设计思想
   5.2 TargetScope（适用范围）
   5.3 预定义范围
   5.4 SemanticTarget（语义目标）
   5.5 CharacteristicTarget
   5.6 FunctionTarget
   5.7 InterfaceTarget
   5.8 RelationshipTarget（v1.2 增强）
   5.9 PartRelationshipTarget（v1.2 新增）
   5.10 StructureTarget
   5.11 ProcessTarget
   5.12 ServiceTarget

6. Requirement Aspect Model（要求多维分类）
   6.1 RequirementAspect
   6.2 预定义 Aspect
   6.3 示例

7. Condition Context Model（条件上下文模型）
   7.1 设计思想
   7.2 EvaluationContext（引用 Core Ontology）
   7.3 ConditionSet
   7.4 ConditionExpression（引用 Core Ontology）

8. Obligation Model（强制程度模型 — 引用 Core）
   8.1 设计思想
   8.2 lbo-core:ObligationLevel
   8.3 预定义级别

9. Requirement Relationship Model（要求关系模型 — v1.2 澄清）
   9.1 关系类型
   9.2 RequirementRelationship
   9.3 与标准引用关系的区别（v1.2 新增）

10. Demand Ontology 边界说明

11. RDF-star Support（RDF-star 预留 — v1.2 澄清）

12. 与 Constraint Ontology 的接口（v1.2 澄清）

13. 与其他模块的接口
    13.1 与 Core Ontology 的接口
    13.2 与 Standard Ontology 的接口
    13.3 与 Specification Framework Ontology 的接口
    13.4 与 Product Ontology 的接口
    13.5 接口总图

14. 推理规则
    14.1 权威传递规则
    14.2 范围推理规则
    14.3 目标元素推理规则
    14.4 约束满足推理规则

15. SHACL 验证约束（v1.2 更新）

16. 完整示例（v1.2 更新）

17. 核心类汇总

18. 冻结声明

19. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Requirement Ontology 是 leleby 语义基础设施中**约束性要求语义表达**的核心模块。它定义了工业标准、客户合同、企业内部规范等外部要求如何被结构化为机器可理解、可推理的语义模型。

本规范是 leleby Requirement Ontology 的正式冻结版本 v1.2。

### 1.2 核心定位

> **Requirement Ontology 定义了“某个权威来源（Authority），针对某个目标对象范围（Scope），在特定条件（Condition）下，对其某个工程语义目标元素（SemanticTarget——可以是特性、功能、接口、关系、结构、过程或服务），提出必须满足的约束（Constraint），并指定强制程度（Obligation）”的完整语义表达。**

**核心表述（六元模型）：**

```
Requirement =
    Authority（谁提出的——通过 Source 推理获得）
  + Scope（适用于什么范围——产品类型/市场/生命周期/环境）
  + SemanticTarget（要求什么目标元素——特性/功能/接口/关系/结构/过程/服务）
  + Condition（在什么条件下有效）
  + Constraint（必须满足什么约束——引用外部 Constraint Ontology 实例）
  + Obligation（强制/推荐/可选）
```

**术语说明（v1.1 明确，v1.2 保留）：**

| 英文 | 中文 | 说明 |
|---|---|---|
| **Requirement** | **要求** | 技术性、规范性的约束性期望（Standard / Technical / Normative） |
| **Demand** | **需求** | 商务性、市场性的需要（Customer / Market / Commercial），如交货期、数量、支付方式。**Demand 不属于 Requirement Ontology**，预留 Demand Ontology 定义 |

### 1.3 v1.2 与 v1.1 的核心差异

| 维度 | v1.1 | v1.2 |
|---|---|---|
| **Constraint 定位** | 隐含为 Requirement 的组成部分 | **明确为外部独立 Ontology 实体的引用**，增加澄清说明 |
| **RelationshipTarget** | 基础关系目标 | **增强**：增加 cardinality、connectionType、importanceLevel、role、replaceability 等工程语义属性 |
| **PartRelationshipTarget** | 不存在 | **新增**：作为 RelationshipTarget 的子类，专门用于部件数量/角色/连接方式等结构约束 |
| **RDF-star 用途** | 未明确 | **澄清**：RDF-star 用于元数据标注（如来源、置信度、证据），而非核心关系表达 |
| **RequirementRelationship** | 存在，但边界模糊 | **明确**：与标准引用关系（Standard Ontology）区分，仅用于 Requirement 之间的派生/细化/冲突等关系 |

### 1.4 核心模型声明

> **Requirement 不定义 Constraint、Condition 或 Obligation 的具体类型。** 这些概念分别属于 Constraint Ontology 和 Core Ontology，Requirement 仅引用它们。这确保了跨模块的一致性和可组合性。
>
> **特别澄清（v1.2）：** Constraint 是独立的 Ontology 实体，位于 `lbo-constraint:ConstraintOntology`。Requirement 通过 `lreq:hasConstraint` 属性引用 Constraint 实例，而非在 Requirement 内部定义或嵌入 Constraint。这种引用关系确保 Constraint 可在 Specification、Verification、Decision 等多个模块中独立复用。


## 2. 设计原则

### 2.1 要求语义原则（六元模型）

> **Requirement 不是自由文本，也不是管理对象，而是“约束性期望”的语义表达。** 其核心语义由六元组构成：

```
Requirement = Authority + Scope + SemanticTarget + Condition + Constraint + Obligation
```

### 2.2 来源权威原则

> **Authority 通过 Source 推理获得，而非直接作为 Requirement 的属性。** 一个 Requirement 可能来自多个来源（如 IEC 标准被 EN 采纳），Authority 应通过来源链推理得出。

### 2.3 约束独立原则

> **Constraint 不是 Requirement 的专属概念。** Specification 需要约束，Verification 需要约束，Measurement 需要约束。因此 Constraint 应属于 `lbo-constraint:ConstraintOntology`，Requirement 通过 `hasConstraint` 引用。**Constraint 是外部独立实体，Requirement 仅持有对它的引用。**

### 2.4 条件上下文共享原则

> **Condition 不是 Requirement 的专属概念。** Specification 需要条件，Verification 需要条件，Decision 需要条件。因此 Condition 应属于 `lbo-core:EvaluationContext`，Requirement 通过 `underContext` 引用。

### 2.5 强制程度统一原则

> **Obligation 不是 Requirement 的专属概念。** 标准有强制程度，客户要求有优先级。因此 Obligation 应属于 `lbo-core:ObligationLevel`，跨模块共享。

### 2.6 模块边界原则

> **Requirement 不定义验证方法、不产生验证结果、不做符合性判定、不做决策。** Requirement 是“输入”，验证和决策由 Verification 和 Decision Ontology 负责。

### 2.7 目标通用化原则

> **Requirement 的目标不限于物理特性（Characteristic）。** Requirement 可以约束功能（Function）、接口（Interface）、产品关系（ProductRelationship）、结构元素（Structure）、过程要素（Process）和服务（Service）。因此，Requirement 的第三元应使用 `SemanticTarget` 而非 `Characteristic`。


## 3. 核心概念模型

### 3.1 Requirement（要求）

```turtle
lreq:Requirement
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "Requirement" ;
    rdfs:comment "要求是某个权威来源针对某个目标范围，在特定条件下，对其工程语义目标元素提出的约束性期望" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lreq:hasRequirementIdentifier` | 要求唯一标识符 | 1 |
| `lreq:hasRequirementName` | 要求名称/标题 | 1 |
| `lreq:hasRequirementText` | 要求原文（用于人类阅读） | 0..1 |
| `lreq:hasVersion` | 版本号 | 0..1 |
| `lreq:createdDate` | 创建日期 | 0..1 |

### 3.2 六元核心模型（v1.2 澄清）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Requirement 六元核心模型（v1.2 冻结）                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  第1元：Authority（谁提出的？）                                    │   │
│  │  值域：通过 derivedFrom → Source → issuedBy 推理获得               │   │
│  │  示例：IEC TC2                                                    │   │
│  │  注：hasAuthority 是推理属性，权威来源是 Source                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  第2元：Scope（适用于什么范围？）                                  │   │
│  │  值域：TargetScope（对象类型 / 市场 / 生命周期 / 环境）            │   │
│  │  示例：OutdoorLuminaire, EU Market, Operation Phase                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  第3元：SemanticTarget（要求什么目标元素？）                       │   │
│  │  值域：lreq:SemanticTarget                                         │   │
│  │  子类：CharacteristicTarget / FunctionTarget / InterfaceTarget /   │   │
│  │        RelationshipTarget / PartRelationshipTarget /               │   │
│  │        StructureTarget / ProcessTarget / ServiceTarget             │   │
│  │  示例：Efficiency（特性）/ OverloadProtection（功能）/             │   │
│  │        WorkingWheelRelationship（关系）/ TireCount（部件关系）     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  第4元：Condition（在什么条件下有效？）                           │   │
│  │  值域：lbo-core:EvaluationContext                                  │   │
│  │  示例：SaltFogEnvironment AND Altitude > 3000m                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  第5元：Constraint（必须满足什么约束？）                          │   │
│  │  值域：lbo-constraint:Constraint（外部独立 Ontology 实体）         │   │
│  │  示例：RangeConstraint [-20℃, 70℃]                                │   │
│  │  注：Constraint 不是 Requirement 的组成部分，而是独立实体引用      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  第6元：Obligation（强制/推荐/可选？）                             │   │
│  │  值域：lbo-core:ObligationLevel                                    │   │
│  │  示例：Mandatory                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 六元关系定义

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lreq:hasScope` | lreq:Requirement | `lreq:TargetScope` | 适用范围 | 1 |
| `lreq:targets` | lreq:Requirement | `lreq:TargetScope` | 已弃用，建议使用 hasScope，保留向后兼容 | 0..1 |
| `lreq:hasTargetElement` | lreq:Requirement | **`lreq:SemanticTarget`** | 真正被约束的目标元素 | 1 |
| `lreq:requiresCharacteristic` | lreq:Requirement | `lbo-core:Characteristic` | 已弃用（v1.1），请使用 hasTargetElement → CharacteristicTarget | 0..1 |
| `lreq:underContext` | lreq:Requirement | `lbo-core:EvaluationContext` | 在什么条件下有效 | 0..* |
| `lreq:hasConstraint` | lreq:Requirement | **`lbo-constraint:Constraint`** | **必须满足的约束（引用外部 Constraint Ontology 实例，v1.2 澄清）** | 1 |
| `lreq:hasObligation` | lreq:Requirement | `lbo-core:ObligationLevel` | 强制程度 | 1 |


## 4. Requirement Source Model（要求来源模型）

### 4.1 设计思想

**明确区分 Authority（谁提出的）和 Source（具体从哪里引用的）。** Authority 通过 Source 推理获得，而非直接作为 Requirement 的属性。

| 概念 | 说明 | 示例 |
|---|---|---|
| Authority | 要求的提出者/发布者 | "IEC 组织" |
| Source | 承载要求的具体文件及条款 | "IEC 60598:2025 Clause 8.4.2" |

**推理链路：**

```
Requirement
    │
    │  lreq:derivedFrom
    ▼
RequirementSource
    │
    │  lreq:issuedBy
    ▼
RequirementAuthority
```

### 4.2 RequirementAuthority（提出者）

```turtle
lreq:RequirementAuthority
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Agent ;
    rdfs:label "RequirementAuthority" ;
    rdfs:comment "要求的提出者/发布者，如 IEC、ISO、客户公司等" .
```

**子类：**

| 子类 | 说明 |
|---|---|
| `lreq:StandardAuthority` | 标准发布组织（如 IEC） |
| `lreq:RegulatoryAuthority` | 监管机构（如 EU Commission） |
| `lreq:CustomerAuthority` | 客户 |
| `lreq:InternalAuthority` | 企业内部（如工程部门） |

### 4.3 RequirementSource（来源引用）

```turtle
lreq:RequirementSource
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Document ;
    rdfs:label "RequirementSource" ;
    rdfs:comment "承载要求的具体来源文件及条款，支持条款级追溯" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lreq:sourceIdentifier` | 来源标识符（如 "IEC 60598"） | 1 |
| `lreq:sourceName` | 来源名称 | 0..1 |
| `lreq:clauseReference` | 条款级引用（如 "Clause 8.4.2"） | 0..1 |
| `lreq:hasVersion` | 来源文件的版本（如 "2025"） | 0..1 |
| `lreq:effectiveDate` | 生效日期 | 0..1 |
| `lreq:hasJurisdiction` | 适用司法管辖区 | 0..1 |

### 4.4 Authority/Source/Requirement 关系

```
RequirementAuthority（IEC TC2）
    │
    │  lreq:issuedBy（发布）
    ▼
RequirementSource（IEC 60598:2025）
    │
    │  lreq:hasClause（包含）
    ▼
StandardClause（Clause 8.4.2）
    │
    │  lreq:defines（定义）
    ▼
Requirement（REQ-001）

推理结果：
Requirement → hasAuthority → IEC TC2
```

**关系属性：**

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lreq:issuedBy` | lreq:RequirementSource | lreq:RequirementAuthority | 来源文件由某权威发布 |
| `lreq:hasClause` | lreq:RequirementSource | lreq:StandardClause | 包含的条款 |
| `lreq:derivedFrom` | lreq:Requirement | lreq:RequirementSource | 要求源自某来源 |
| `lreq:derivedFromClause` | lreq:Requirement | lreq:StandardClause | 要求源自某具体条款 |
| `lreq:hasAuthority` | lreq:Requirement | lreq:RequirementAuthority | **推理属性**：通过 derivedFrom → Source → issuedBy 推理获得 |

### 4.5 示例：完整来源追溯

```turtle
# 权威
lreq:IEC_TC34
    a lreq:StandardAuthority ;
    llb:hasName "International Electrotechnical Commission - TC34" .

# 来源文件及条款
lreq:IEC60598_Source
    a lreq:RequirementSource ;
    lreq:sourceIdentifier "IEC 60598" ;
    lreq:sourceName "Luminaires - General requirements" ;
    lreq:hasVersion "2025" .

lreq:IEC60598_Clause_8_4_2
    a lreq:StandardClause ;
    lreq:clauseIdentifier "8.4.2" ;
    lreq:clauseText "Outdoor luminaires shall operate between -40℃ and 70℃." .

# 来源发布权威
lreq:IEC60598_Source
    lreq:issuedBy lreq:IEC_TC34 .

# 要求：完整追溯
lreq:REQ_Temp_001
    a lreq:Requirement ;
    lreq:hasRequirementIdentifier "REQ-TEMP-001" ;
    lreq:hasRequirementName "户外灯具工作温度要求" ;
    lreq:derivedFrom lreq:IEC60598_Source ;
    lreq:derivedFromClause lreq:IEC60598_Clause_8_4_2 .

# 推理结果：
# lreq:REQ_Temp_001 → lreq:hasAuthority → lreq:IEC_TC34
```


## 5. Requirement Target Model（要求目标模型）

### 5.1 设计思想

**明确区分“适用范围”（Scope）和“真正被约束的目标元素”（SemanticTarget）。**

| 概念 | 说明 | 示例 |
|---|---|---|
| **Scope（适用范围）** | 这个要求适用于什么范围的对象 | "户外灯具"、"EU 市场"、"运行阶段" |
| **SemanticTarget（语义目标）** | 这个要求具体约束什么元素 | "效率"（特性）、"过载保护"（功能）、"CAN接口"（接口）、"工作轮胎关系"（关系） |

### 5.2 TargetScope（适用范围）

```turtle
lreq:TargetScope
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "TargetScope" ;
    rdfs:comment "要求适用的目标对象范围，包含多个维度" .
```

**核心属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lreq:hasObjectScope` | lreq:TargetScope | rdfs:Class | 适用的对象类型（Ontology 类） | 0..1 |
| `lreq:hasMarketScope` | lreq:TargetScope | lreq:MarketScope | 市场范围 | 0..1 |
| `lreq:hasLifecycleScope` | lreq:TargetScope | lreq:LifecycleScope | 生命周期阶段 | 0..1 |
| `lreq:hasEnvironmentScope` | lreq:TargetScope | lreq:EnvironmentScope | 环境范围 | 0..1 |

### 5.3 预定义范围

**MarketScope：**

| 值 | 说明 |
|---|---|
| `lreq:Global` | 全球 |
| `lreq:EU` | 欧盟 |
| `lreq:US` | 美国 |
| `lreq:China` | 中国 |
| `lreq:Japan` | 日本 |

**LifecycleScope：**

| 值 | 说明 |
|---|---|
| `lreq:DesignPhase` | 设计阶段 |
| `lreq:ManufacturingPhase` | 制造阶段 |
| `lreq:OperationPhase` | 运行阶段 |
| `lreq:EndOfLifePhase` | 报废阶段 |

**EnvironmentScope：**

| 值 | 说明 |
|---|---|
| `lreq:MarineEnvironment` | 海洋环境 |
| `lreq:IndustrialEnvironment` | 工业环境 |
| `lreq:OutdoorEnvironment` | 户外环境 |
| `lreq:IndoorEnvironment` | 室内环境 |

### 5.4 SemanticTarget（语义目标）

```turtle
lreq:SemanticTarget
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "SemanticTarget" ;
    rdfs:comment "要求真正约束的目标元素的抽象基类。表示要求的约束对象是特性、功能、接口、关系、结构、过程还是服务" .
```

**SemanticTarget 类型体系（v1.2 更新）：**

```
SemanticTarget
    ├── CharacteristicTarget（特性）
    │       └── targetCharacteristic → lbo-core:Characteristic
    ├── FunctionTarget（功能）
    │       └── targetFunction → lcap:Function / lprod:ProductFeature
    ├── InterfaceTarget（接口）
    │       └── targetInterface → lprod:Interface
    ├── RelationshipTarget（关系——v1.2 增强）
    │       └── targetRelationship → lprod:ProductRelationship
    │       └── （可约束 cardinality / connectionType / importanceLevel / role / replaceability）
    ├── PartRelationshipTarget（部件关系——v1.2 新增）
    │       └── targetPartRelationship → lprod:PartRelationship
    │       └── （专门用于结构约束：数量/角色/连接方式/重要性/可替换性）
    ├── StructureTarget（结构）
    │       └── targetStructure → lprod:Structure
    ├── ProcessTarget（过程）
    │       └── targetProcess → lprod:Process
    └── ServiceTarget（服务）
            └── targetService → lprod:Service
```

### 5.5 CharacteristicTarget

```turtle
lreq:CharacteristicTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lreq:SemanticTarget ;
    rdfs:label "CharacteristicTarget" ;
    rdfs:comment "特性类目标，指向 lbo-core:Characteristic" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lreq:targetCharacteristic` | lreq:CharacteristicTarget | `lbo-core:Characteristic` | 目标特性 | 1 |

### 5.6 FunctionTarget

```turtle
lreq:FunctionTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lreq:SemanticTarget ;
    rdfs:label "FunctionTarget" ;
    rdfs:comment "功能类目标，指向产品功能或能力" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lreq:targetFunction` | lreq:FunctionTarget | `lcap:Function` / `lprod:ProductFeature` | 目标功能 | 1 |

### 5.7 InterfaceTarget

```turtle
lreq:InterfaceTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lreq:SemanticTarget ;
    rdfs:label "InterfaceTarget" ;
    rdfs:comment "接口类目标，指向产品接口" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lreq:targetInterface` | lreq:InterfaceTarget | `lprod:Interface` | 目标接口 | 1 |

### 5.8 RelationshipTarget（v1.2 增强）

```turtle
lreq:RelationshipTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lreq:SemanticTarget ;
    rdfs:label "RelationshipTarget" ;
    rdfs:comment "关系类目标，指向产品关系（如 ProductRelationship）。可约束关系的类型、角色、数量、连接方式、重要性、可替换性等属性。" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lreq:targetRelationship` | lreq:RelationshipTarget | `lprod:ProductRelationship` | 目标产品关系 | 1 |
| `lreq:targetRelationshipType` | lreq:RelationshipTarget | rdfs:Class | 目标关系类型（如 PartRelationship） | 0..1 |
| `lreq:requiredCardinality` | lreq:RelationshipTarget | xsd:integer | **要求的数量（v1.2 增强）** | 0..1 |
| `lreq:requiredRole` | lreq:RelationshipTarget | lprod:PartRole | **要求的角色（v1.2 增强）** | 0..1 |
| `lreq:requiredConnectionType` | lreq:RelationshipTarget | lprod:ConnectionType | **要求的连接方式（v1.2 新增）** | 0..1 |
| `lreq:requiredImportanceLevel` | lreq:RelationshipTarget | lprod:ImportanceLevel | **要求的重要性级别（v1.2 新增）** | 0..1 |
| `lreq:requiredReplaceability` | lreq:RelationshipTarget | lprod:Replaceability | **要求的可替换性（v1.2 新增）** | 0..1 |

### 5.9 PartRelationshipTarget（v1.2 新增）

```turtle
lreq:PartRelationshipTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lreq:RelationshipTarget ;
    rdfs:label "PartRelationshipTarget" ;
    rdfs:comment "部件关系类目标，专门用于约束产品与部件之间的结构关系。用于表达'必须具有X个Y部件'、'Y部件必须采用Z连接方式'等结构要求。" .
```

**典型用途：**

| 约束类型 | 示例 |
|---|---|
| 数量约束 | "汽车必须具有4个工作轮胎" |
| 角色约束 | "必须具有备用轮胎" |
| 连接方式约束 | "电池必须采用螺栓固定" |
| 重要性约束 | "制动系统部件为关键件" |
| 可替换性约束 | "过滤器必须可现场更换" |

**示例：**

```turtle
# 要求：汽车必须具有4个工作轮胎
lreq:Target_WorkingWheel
    a lreq:PartRelationshipTarget ;
    lreq:targetRelationshipType lprod:PartRelationship ;
    lreq:requiredRole lprod:WorkingPart ;
    lreq:requiredCardinality 4 ;
    lreq:requiredConnectionType lprod:Bolted .
```

### 5.10 StructureTarget

```turtle
lreq:StructureTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lreq:SemanticTarget ;
    rdfs:label "StructureTarget" ;
    rdfs:comment "结构类目标，指向产品的结构元素" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lreq:targetStructure` | lreq:StructureTarget | `lprod:Structure` | 目标结构 | 1 |

### 5.11 ProcessTarget

```turtle
lreq:ProcessTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lreq:SemanticTarget ;
    rdfs:label "ProcessTarget" ;
    rdfs:comment "过程类目标，指向生产过程或操作" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lreq:targetProcess` | lreq:ProcessTarget | `lprod:Process` | 目标过程 | 1 |

### 5.12 ServiceTarget

```turtle
lreq:ServiceTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lreq:SemanticTarget ;
    rdfs:label "ServiceTarget" ;
    rdfs:comment "服务类目标，指向产品服务" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lreq:targetService` | lreq:ServiceTarget | `lprod:Service` | 目标服务 | 1 |


## 6. Requirement Aspect Model（要求多维分类）

### 6.1 RequirementAspect

```turtle
lreq:RequirementAspect
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "RequirementAspect" ;
    rdfs:comment "要求的维度标签，支持多维分类" .
```

### 6.2 预定义 Aspect

| 方面 | 说明 |
|---|---|
| `lreq:FunctionalAspect` | 功能方面 |
| `lreq:PerformanceAspect` | 性能方面 |
| `lreq:QualityAspect` | 质量方面 |
| `lreq:SafetyAspect` | 安全方面 |
| `lreq:EnvironmentalAspect` | 环境方面 |
| `lreq:RegulatoryAspect` | 法规方面 |
| `lreq:InterfaceAspect` | 接口方面 |
| `lreq:CommercialAspect` | 商业方面 |
| `lreq:ReliabilityAspect` | 可靠性方面 |

### 6.3 示例

```turtle
lreq:REQ_IP_001
    a lreq:Requirement ;
    lreq:hasAspect lreq:SafetyAspect ;
    lreq:hasAspect lreq:EnvironmentalAspect .
```


## 7. Condition Context Model（条件上下文模型）

### 7.1 设计思想

**Condition 概念迁移至 Core Ontology 的 `EvaluationContext`。** Requirement 通过 `lreq:underContext` 引用 `lbo-core:EvaluationContext`，不再独立定义 Condition 类。

### 7.2 EvaluationContext（引用 Core Ontology）

`lbo-core:EvaluationContext` 在 Core Ontology 中定义。Requirement 通过 `lreq:underContext` 引用。

### 7.3 ConditionSet

对于需要组合条件的场景，使用 `lreq:ConditionSet`：

```turtle
lreq:ConditionSet
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:EvaluationContext ;
    rdfs:label "ConditionSet" ;
    rdfs:comment "条件的逻辑组合" .
```

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lreq:logicalOperator` | lreq:ConditionSet | lreq:LogicalOperator | 逻辑操作符 |
| `lreq:containsCondition` | lreq:ConditionSet | lbo-core:EvaluationContext | 包含的条件 |

### 7.4 示例

```turtle
# 条件组合：盐雾环境 AND 海拔 > 3000m
lreq:ConditionSet_SaltHighAltitude
    a lreq:ConditionSet ;
    lreq:logicalOperator lreq:AND ;
    lreq:containsCondition [
        a lbo-core:EnvironmentalContext ;
        lbo-core:environmentType "SaltFog"
    ] ;
    lreq:containsCondition [
        a lbo-core:EnvironmentalContext ;
        lbo-core:altitude "3000"^^xsd:double ;
        lbo-core:altitudeUnit llb:Metre
    ] .

# Requirement 引用条件
lreq:REQ_Corrosion_001
    a lreq:Requirement ;
    lreq:underContext lreq:ConditionSet_SaltHighAltitude .
```


## 8. Obligation Model（强制程度模型 — 引用 Core）

### 8.1 设计思想

**ObligationLevel 迁移至 Core Ontology，跨模块共享。**

### 8.2 lbo-core:ObligationLevel

`lbo-core:ObligationLevel` 在 Core Ontology 中定义。Requirement 通过 `lreq:hasObligation` 引用。

### 8.3 预定义级别

| 值 | 说明 | 对应 ISO 术语 |
|---|---|---|
| `lbo-core:Mandatory` | 强制 | "shall" |
| `lbo-core:ConditionalMandatory` | 条件强制 | "shall" under certain conditions |
| `lbo-core:Required` | 要求 | "should" |
| `lbo-core:Recommended` | 推荐 | "recommended" |
| `lbo-core:Optional` | 可选 | "may" |
| `lbo-core:Informative` | 参考 | "informative" |

### 8.4 示例

```turtle
lreq:REQ_Temp_001
    a lreq:Requirement ;
    lreq:hasObligation lbo-core:Mandatory .
```


## 9. Requirement Relationship Model（要求关系模型 — v1.2 澄清）

### 9.1 关系类型

| 关系 | 说明 |
|---|---|
| `lreq:derives` | 派生关系 |
| `lreq:refines` | 细化关系 |
| `lreq:supersedes` | 替代关系 |
| `lreq:conflictsWith` | 冲突关系 |
| `lreq:dependsOn` | 依赖关系 |
| `lreq:tracesTo` | 追溯关系 |
| `lreq:hasSubRequirement` | 子要求 |

### 9.2 RequirementRelationship

```turtle
lreq:RequirementRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "RequirementRelationship" .
```

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lreq:sourceRequirement` | lreq:RequirementRelationship | lreq:Requirement | 源要求 |
| `lreq:targetRequirement` | lreq:RequirementRelationship | lreq:Requirement | 目标要求 |
| `lreq:relationshipType` | lreq:RequirementRelationship | lreq:RelationshipType | 关系类型 |

### 9.3 与标准引用关系的区别（v1.2 新增）

> **重要澄清：** `RequirementRelationship`（本模块）与标准引用关系（Standard Ontology / Normative Semantic Package）是两个不同层次的概念。

| 维度 | RequirementRelationship（本模块） | 标准引用关系（Standard Ontology） |
|---|---|---|
| **范围** | Requirement 实例之间的关系 | 标准/规范文件之间的关系 |
| **示例** | "REQ-001 refines REQ-002" | "IEC 60034-1 references IEC 60034-5" |
| **表达方式** | `lreq:refines` / `lreq:derives` | `lstd:ReferencingRelationship` / `lstd:AdoptionRelationship` |
| **Ontology** | Requirement Ontology（本模块） | Standard Ontology |

**使用约束：**

- ❌ **不要**使用 `RequirementRelationship` 表达标准之间的引用关系（应使用 Standard Ontology）
- ✅ **应当**使用 `RequirementRelationship` 表达 Requirement 实例之间的派生、细化、冲突等关系


## 10. Demand Ontology 边界说明

**重要：** `Requirement`（要求）与 `Demand`（需求）是两个不同层级的概念。

| 维度 | Requirement（要求） | Demand（需求） |
|---|---|---|
| **性质** | 技术性、规范性、约束性 | 商务性、市场性、期望性 |
| **来源** | 标准、法规、技术规范 | 客户、市场、采购合同 |
| **示例** | "电机效率 ≥ 90%" | "交货日期 2026-10-01"、"采购数量 500 台" |
| **约束对象** | 产品特性、功能、接口、结构关系 | 交付条件、商务条款、服务范围 |
| **所属 Ontology** | **Requirement Ontology（本模块）** | **预留 Demand Ontology（待定义）** |

**接口预留：**

```
Demand（商务需求）
    │
    │  mayDerive（可能派生出）
    ▼
Requirement（技术要求）
```

Demand 的具体语义结构（交付日期、数量、支付方式、合同条款等）将在后续的 **Demand Ontology Specification** 中定义。本模块不负责商务需求的定义。


## 11. RDF-star Support（RDF-star 预留 — v1.2 澄清）

### 11.1 设计思想

RDF-star 在 leleby Requirement Ontology 中的定位是：**为已有断言附加元数据，而非表达核心语义关系。**

### 11.2 适用场景（v1.2 澄清）

| 适用场景 | 示例 |
|---|---|
| **来源追溯** | `<<lreq:REQ-001 lreq:derivedFrom lreq:Clause-5-6>>` + 置信度、提取时间 |
| **置信度标注** | `<<lreq:REQ-001 lreq:targets lreq:Target-Wheel>>` + 置信度 0.95 |
| **证据关联** | `<<lreq:REQ-001 lreq:hasConstraint lcon:C-001>>` + 测试报告引用 |
| **审计元数据** | `<<lreq:REQ-001 lreq:hasObligation lbo:Mandatory>>` + 审核人、审核日期 |

### 11.3 不适用场景（v1.2 澄清）

> **RDF-star 不应用于表达 Requirement 的核心语义关系。** 核心关系（如 `hasTargetElement`、`hasConstraint`、`hasScope`）应使用标准的 OWL 对象属性表达，而非 RDF-star 注解。

❌ **错误示例：**

```turtle
# 不要用 RDF-star 表达核心关系
<<lreq:REQ-001 lreq:hasTargetElement lreq:Target-Temp>>
    :source "IEC 60598" .
```

✅ **正确示例：**

```turtle
# 核心关系使用标准 OWL 属性
lreq:REQ-001
    lreq:hasTargetElement lreq:Target-Temp ;
    lreq:hasConstraint lcon:C-001 .

# RDF-star 仅用于附加元数据
<<lreq:REQ-001 lreq:hasConstraint lcon:C-001>>
    :confidence 0.95 ;
    :verifiedBy lreq:TestReport-2026-001 .
```

### 11.4 SHACL 与 RDF-star 的关系

> **SHACL 负责验证数据结构（完整性、格式、基数）。RDF-star 负责为断言附加条件化信息。两者互不替代。**


## 12. 与 Constraint Ontology 的接口（v1.2 澄清）

### 12.1 设计思想

> **Constraint 是独立的 Ontology 实体，位于 `lbo-constraint:ConstraintOntology`。Requirement 通过 `lreq:hasConstraint` 引用 Constraint 实例。** 这种引用关系确保 Constraint 可在 Specification、Verification、Decision 等多个模块中独立复用。

### 12.2 关系定义

```turtle
lreq:hasConstraint
    rdf:type owl:ObjectProperty ;
    rdfs:domain lreq:Requirement ;
    rdfs:range lbo-constraint:Constraint ;
    rdfs:label "hasConstraint" ;
    rdfs:comment "要求引用的约束定义。Constraint 是外部独立实体，非 Requirement 组成部分。" .
```

### 12.3 Constraint 与 SemanticTarget 的对齐

Constraint 的 `constrains` 属性指向 `lbo-constraint:ConstraintTarget`，与 Requirement 的 `hasTargetElement` 指向 `lreq:SemanticTarget` 需保持语义一致：

```
Requirement
    │
    │  hasTargetElement → lreq:SemanticTarget
    │                     （例如：PartRelationshipTarget → PartRelationship）
    │
    │  hasConstraint → lbo-constraint:Constraint
    │                     │
    │                     │  constrains → lbo-constraint:ConstraintTarget
    │                     │                （例如：RelationshipTarget → PartRelationship）
    ▼
语义对齐：Requirement 的 SemanticTarget 应与其引用的 Constraint 的 ConstraintTarget 指向同一类工程元素。
```


## 13. 与其他模块的接口

### 13.1 与 Core Ontology 的接口

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lreq:hasTargetElement` | lreq:Requirement | `lreq:SemanticTarget` | v1.1 新增 |
| `lreq:targetCharacteristic` | lreq:CharacteristicTarget | `lbo-core:Characteristic` | 来自 Core Ontology |
| `lreq:underContext` | lreq:Requirement | `lbo-core:EvaluationContext` | 来自 Core Ontology |
| `lreq:hasObligation` | lreq:Requirement | `lbo-core:ObligationLevel` | 来自 Core Ontology |

### 13.2 与 Standard Ontology 的接口

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lreq:derivedFromClause` | lreq:Requirement | `lstd:StandardClause` | 来自标准条款 |
| `lreq:hasAuthority` | lreq:Requirement | `lreq:RequirementAuthority` | 通过 Source 推理 |

### 13.3 与 Specification Framework Ontology 的接口

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-spec:satisfies` | lbo-spec:Specification | lreq:Requirement | 规格满足要求 |
| `lbo-spec:evaluatedAgainst` | lbo-spec:Specification | lreq:Requirement | 规格被要求评估 |

### 13.4 与 Product Ontology 的接口

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lreq:targetRelationship` | lreq:RelationshipTarget | `lprod:ProductRelationship` | 要求约束产品关系 |
| `lreq:targetPartRelationship` | lreq:PartRelationshipTarget | `lprod:PartRelationship` | 要求约束部件关系 |
| `lreq:targetStructure` | lreq:StructureTarget | `lprod:Structure` | 要求约束结构元素 |
| `lreq:targetFunction` | lreq:FunctionTarget | `lprod:ProductFeature` | 要求约束功能 |
| `lreq:targetInterface` | lreq:InterfaceTarget | `lprod:Interface` | 要求约束接口 |
| `lreq:targetProcess` | lreq:ProcessTarget | `lprod:Process` | 要求约束过程 |

### 13.5 接口总图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Requirement Ontology 与其他模块的接口（v1.2 冻结）       │
│                                                                             │
│  lbo-core: Core Ontology                                                    │
│  ├── Characteristic（特性——通过 CharacteristicTarget 引用）                │
│  ├── EvaluationContext（条件上下文）                                       │
│  └── ObligationLevel（强制程度）                                           │
│         │                                                                  │
│         │  被引用                                                          │
│         ▼                                                                  │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║                       Requirement Ontology (lreq:)                   ║ │
│  ║  Requirement                                                         ║ │
│  ║  ├── hasScope → TargetScope（适用范围）                              ║ │
│  ║  ├── hasTargetElement → SemanticTarget（约束目标）                   ║ │
│  ║  │       ├── CharacteristicTarget → lbo-core:Characteristic          ║ │
│  ║  │       ├── FunctionTarget → lcap:Function                         ║ │
│  ║  │       ├── InterfaceTarget → lprod:Interface                     ║ │
│  ║  │       ├── RelationshipTarget → lprod:ProductRelationship        ║ │
│  ║  │       ├── PartRelationshipTarget → lprod:PartRelationship       ║ │
│  ║  │       ├── StructureTarget → lprod:Structure                     ║ │
│  ║  │       ├── ProcessTarget → lprod:Process                         ║ │
│  ║  │       └── ServiceTarget → lprod:Service                         ║ │
│  ║  ├── underContext → lbo-core:EvaluationContext                      ║ │
│  ║  ├── hasConstraint → lbo-constraint:Constraint（外部独立实体）      ║ │
│  ║  └── hasObligation → lbo-core:ObligationLevel                       ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│         │                                                                  │
│         │  被引用 / 被满足                                                  │
│         ▼                                                                  │
│  lbo-constraint: Constraint Ontology（独立模块）                           │
│  └── RangeConstraint / ToleranceConstraint / ...                          │
│         │                                                                  │
│         │  被评估                                                          │
│         ▼                                                                  │
│  lbo-spec: Specification Framework Ontology                                │
│  └── Specification satisfies/evaluatedAgainst Requirement                 │
│         │                                                                  │
│         │  被约束                                                          │
│         ▼                                                                  │
│  lprod: Product Ontology                                                   │
│  └── ProductRelationship / Structure / Interface / Process                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 14. 推理规则

### 14.1 权威传递规则

**规则1：Requirement 通过 Source 继承 Authority**

```
IF Requirement R derivedFrom Source S
AND Source S issuedBy Authority A
THEN R hasAuthority A
```

### 14.2 范围推理规则

**规则2：子类继承父类的要求**

```
IF Requirement R hasScope Scope S
AND S hasObjectScope Class C
AND Product P isSubClassOf Class C
THEN Requirement R appliesTo Product P
```

**规则3：目标范围的组合推理**

```
IF Requirement R hasScope Scope S
AND S hasObjectScope Class C
AND C hasSubClass SubC
THEN Requirement R appliesTo SubC
```

### 14.3 目标元素推理规则

**规则4：Requirement 通过 SemanticTarget 定位约束对象**

```
IF Requirement R hasTargetElement SemanticTarget T
AND T is CharacteristicTarget targeting Characteristic C
AND Product P hasCharacteristic C
THEN R constrains P's characteristic C
```

**规则5：Requirement 通过 PartRelationshipTarget 定位结构约束**

```
IF Requirement R hasTargetElement PartRelationshipTarget PT
AND PT requires cardinality = 4
AND PT requires role = WorkingPart
AND Product P hasPartRelationship R with cardinality 4 and role WorkingPart
THEN R is satisfied by P
```

### 14.4 约束满足推理规则

**规则6：要求满足判定**

```
IF Specification S hasValue V
AND Requirement R hasConstraint C
AND V satisfies C
AND R hasObligation Mandatory
THEN S satisfies R
```

**规则7：强制要求验证规则**

```
IF Requirement R hasObligation Mandatory
AND Product P does not satisfy R
THEN P is non-compliant
```


## 15. SHACL 验证约束（v1.2 更新）

### 15.1 Requirement 六元约束

```turtle
lreq:RequirementShape
    a sh:NodeShape ;
    sh:targetClass lreq:Requirement ;
    sh:property [
        sh:path lreq:hasRequirementIdentifier ;
        sh:minCount 1 ;
        sh:message "Requirement must have an identifier" ;
    ] ;
    sh:property [
        sh:path lreq:hasRequirementName ;
        sh:minCount 1 ;
        sh:message "Requirement must have a name" ;
    ] ;
    sh:property [
        sh:path lreq:hasScope ;
        sh:minCount 1 ;
        sh:message "Requirement must have a scope" ;
    ] ;
    sh:property [
        sh:path lreq:hasTargetElement ;
        sh:minCount 1 ;
        sh:message "Requirement must have a target element (SemanticTarget)" ;
    ] ;
    sh:property [
        sh:path lreq:hasConstraint ;
        sh:minCount 1 ;
        sh:message "Requirement must have a constraint (from Constraint Ontology)" ;
    ] ;
    sh:property [
        sh:path lreq:hasObligation ;
        sh:minCount 1 ;
        sh:message "Requirement must have an obligation level" ;
    ] ;
    sh:or (
        [ sh:path lreq:derivedFrom ; sh:minCount 1 ]
        [ sh:path lreq:derivedFromClause ; sh:minCount 1 ]
    ) ;
    sh:message "Requirement must have a source reference" .
```

### 15.2 SemanticTarget 约束（v1.2 更新）

```turtle
# CharacteristicTarget 必须有 targetCharacteristic
lreq:CharacteristicTargetShape
    a sh:NodeShape ;
    sh:targetClass lreq:CharacteristicTarget ;
    sh:property [
        sh:path lreq:targetCharacteristic ;
        sh:minCount 1 ;
        sh:message "CharacteristicTarget must have a target characteristic" ;
    ] .

# RelationshipTarget 必须有 targetRelationship 或 targetRelationshipType
lreq:RelationshipTargetShape
    a sh:NodeShape ;
    sh:targetClass lreq:RelationshipTarget ;
    sh:or (
        [ sh:path lreq:targetRelationship ; sh:minCount 1 ]
        [ sh:path lreq:targetRelationshipType ; sh:minCount 1 ]
    ) ;
    sh:message "RelationshipTarget must have a target relationship or relationship type" .

# PartRelationshipTarget 必须有 targetRelationshipType
lreq:PartRelationshipTargetShape
    a sh:NodeShape ;
    sh:targetClass lreq:PartRelationshipTarget ;
    sh:property [
        sh:path lreq:targetRelationshipType ;
        sh:minCount 1 ;
        sh:message "PartRelationshipTarget must have a target relationship type" ;
    ] .
```

### 15.3 TargetScope 约束

```turtle
lreq:TargetScopeShape
    a sh:NodeShape ;
    sh:targetClass lreq:TargetScope ;
    sh:or (
        [ sh:path lreq:hasObjectScope ; sh:minCount 1 ]
        [ sh:path lreq:hasMarketScope ; sh:minCount 1 ]
        [ sh:path lreq:hasLifecycleScope ; sh:minCount 1 ]
        [ sh:path lreq:hasEnvironmentScope ; sh:minCount 1 ]
    ) ;
    sh:message "TargetScope must have at least one scope dimension" .
```

### 15.4 RequirementSource 约束

```turtle
lreq:RequirementSourceShape
    a sh:NodeShape ;
    sh:targetClass lreq:RequirementSource ;
    sh:property [
        sh:path lreq:sourceIdentifier ;
        sh:minCount 1 ;
        sh:message "RequirementSource must have a source identifier" ;
    ] ;
    sh:property [
        sh:path lreq:issuedBy ;
        sh:minCount 1 ;
        sh:message "RequirementSource must have an issuer" ;
    ] .
```


## 16. 完整示例（v1.2 更新）

### 16.1 IEC 标准要求 → leleby 表达（使用 SemanticTarget）

**原始要求：**

> IEC 60598:2025 Clause 8.4.2 要求户外灯具在 -40℃ 至 70℃ 环境下正常工作。

```turtle
# Authority
lreq:IEC_TC34
    a lreq:StandardAuthority ;
    llb:hasName "IEC TC34" .

# Source & Clause
lreq:IEC60598_Source
    a lreq:RequirementSource ;
    lreq:sourceIdentifier "IEC 60598" ;
    lreq:sourceName "Luminaires - General requirements" ;
    lreq:hasVersion "2025" .

lreq:IEC60598_Clause_8_4_2
    a lreq:StandardClause ;
    lreq:clauseIdentifier "8.4.2" ;
    lreq:clauseText "Outdoor luminaires shall operate between -40℃ and 70℃." .

lreq:IEC60598_Source
    lreq:issuedBy lreq:IEC_TC34 ;
    lreq:hasClause lreq:IEC60598_Clause_8_4_2 .

# Scope
lreq:Target_OutdoorLuminaire
    a lreq:TargetScope ;
    lreq:hasObjectScope lbo:OutdoorLuminaire .

# SemanticTarget（CharacteristicTarget）
lreq:Target_Temperature
    a lreq:CharacteristicTarget ;
    lreq:targetCharacteristic lbo:OperatingTemperature .

# Constraint（来自 Constraint Ontology）
lreq:Constraint_Temp_Neg40_70
    a lbo-constraint:RangeConstraint ;
    lbo-constraint:minValue [
        llb:hasNumericValue "-40"^^xsd:double ;
        llb:hasUnit llb:DegreeCelsius
    ] ;
    lbo-constraint:maxValue [
        llb:hasNumericValue "70"^^xsd:double ;
        llb:hasUnit llb:DegreeCelsius
    ] .

# Requirement
lreq:REQ_IEC_001
    a lreq:Requirement ;
    lreq:hasRequirementIdentifier "REQ-IEC-001" ;
    lreq:hasRequirementName "IEC 60598 户外灯具工作温度要求" ;
    lreq:hasRequirementText "户外灯具应能在-40℃至70℃环境下正常工作" ;
    lreq:derivedFrom lreq:IEC60598_Source ;
    lreq:derivedFromClause lreq:IEC60598_Clause_8_4_2 ;
    lreq:hasScope lreq:Target_OutdoorLuminaire ;
    lreq:hasTargetElement lreq:Target_Temperature ;
    lreq:underContext lreq:Condition_OutdoorOperation ;
    lreq:hasConstraint lreq:Constraint_Temp_Neg40_70 ;
    lreq:hasObligation lbo-core:Mandatory ;
    lreq:hasAspect lreq:PerformanceAspect ;
    lreq:hasAspect lreq:EnvironmentalAspect .

# 推理结果：lreq:REQ_IEC_001 → lreq:hasAuthority → lreq:IEC_TC34
```

### 16.2 结构要求：车辆轮胎（使用 PartRelationshipTarget — v1.2 新增）

**原始要求：** 汽车必须具有4个工作轮胎。

```turtle
# Scope
lreq:Target_Vehicle
    a lreq:TargetScope ;
    lreq:hasObjectScope lprod:Vehicle .

# SemanticTarget：PartRelationshipTarget（v1.2 新增）
lreq:Target_WorkingWheel
    a lreq:PartRelationshipTarget ;
    lreq:targetRelationshipType lprod:PartRelationship ;
    lreq:requiredRole lprod:WorkingPart ;
    lreq:requiredCardinality 4 ;
    lreq:requiredConnectionType lprod:Bolted .

# Constraint
lreq:Constraint_Wheel_Count
    a lbo-constraint:ValueConstraint ;
    lbo-constraint:expectedValue [
        llb:hasNumericValue "4"^^xsd:integer ;
        llb:hasUnit llb:Each
    ] .

# Requirement
lreq:REQ_Vehicle_Wheel_001
    a lreq:Requirement ;
    lreq:hasRequirementIdentifier "REQ-VEH-WHEEL-001" ;
    lreq:hasRequirementName "车辆工作轮胎数量要求" ;
    lreq:hasScope lreq:Target_Vehicle ;
    lreq:hasTargetElement lreq:Target_WorkingWheel ;
    lreq:hasConstraint lreq:Constraint_Wheel_Count ;
    lreq:hasObligation lbo-core:Mandatory .
```

### 16.3 功能要求：过载保护

**原始要求：** 电机必须提供过载保护功能。

```turtle
# Scope
lreq:Target_Motor
    a lreq:TargetScope ;
    lreq:hasObjectScope lprod:Motor .

# SemanticTarget：FunctionTarget
lreq:Target_OverloadProtection
    a lreq:FunctionTarget ;
    lreq:targetFunction lprod:OverloadProtectionFeature .

# Constraint
lreq:Constraint_Overload_Exists
    a lbo-constraint:ValueConstraint ;
    lbo-constraint:expectedValue [
        llb:hasNumericValue "true"^^xsd:boolean
    ] .

# Requirement
lreq:REQ_Motor_Overload_001
    a lreq:Requirement ;
    lreq:hasRequirementIdentifier "REQ-MOTOR-OL-001" ;
    lreq:hasRequirementName "电机过载保护功能要求" ;
    lreq:hasScope lreq:Target_Motor ;
    lreq:hasTargetElement lreq:Target_OverloadProtection ;
    lreq:hasConstraint lreq:Constraint_Overload_Exists ;
    lreq:hasObligation lbo-core:Mandatory .
```


## 17. 核心类汇总

### 17.1 Classes

| 类名 | 父类 | 说明 |
|---|---|---|
| `lreq:Requirement` | llb:Statement | 要求 |
| `lreq:RequirementAuthority` | llb:Agent | 要求提出者 |
| `lreq:RequirementSource` | llb:Document | 来源文件 |
| `lreq:StandardClause` | llb:Statement | 标准条款 |
| `lreq:TargetScope` | llb:Concept | 适用范围（多维） |
| `lreq:SemanticTarget` | llb:Concept | 语义目标 |
| `lreq:CharacteristicTarget` | lreq:SemanticTarget | 特性目标 |
| `lreq:FunctionTarget` | lreq:SemanticTarget | 功能目标 |
| `lreq:InterfaceTarget` | lreq:SemanticTarget | 接口目标 |
| `lreq:RelationshipTarget` | lreq:SemanticTarget | 关系目标 |
| **`lreq:PartRelationshipTarget`** | **lreq:RelationshipTarget** | **部件关系目标（v1.2 新增）** |
| `lreq:StructureTarget` | lreq:SemanticTarget | 结构目标 |
| `lreq:ProcessTarget` | lreq:SemanticTarget | 过程目标 |
| `lreq:ServiceTarget` | lreq:SemanticTarget | 服务目标 |
| `lreq:ConditionSet` | lbo-core:EvaluationContext | 条件集 |
| `lreq:RequirementAspect` | llb:Concept | 多维分类维度 |
| `lreq:RequirementRelationship` | llb:Statement | 要求关系 |

**来自 Core Ontology：**

| 类名 | 说明 |
|---|---|
| `lbo-core:Characteristic` | 特性 |
| `lbo-core:EvaluationContext` | 评价上下文 |
| `lbo-core:ObligationLevel` | 强制程度 |

**来自 Constraint Ontology：**

| 类名 | 说明 |
|---|---|
| `lbo-constraint:Constraint` | 约束（外部独立实体） |

### 17.2 Object Properties（v1.2 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lreq:hasScope` | lreq:Requirement | `lreq:TargetScope` | 适用范围 |
| `lreq:targets` | lreq:Requirement | `lreq:TargetScope` | 已弃用，保留向后兼容 |
| `lreq:hasTargetElement` | lreq:Requirement | **`lreq:SemanticTarget`** | 目标元素 |
| `lreq:requiresCharacteristic` | lreq:Requirement | `lbo-core:Characteristic` | 已弃用（v1.1） |
| `lreq:underContext` | lreq:Requirement | `lbo-core:EvaluationContext` | 条件上下文 |
| `lreq:hasConstraint` | lreq:Requirement | `lbo-constraint:Constraint` | 约束（外部引用） |
| `lreq:hasObligation` | lreq:Requirement | `lbo-core:ObligationLevel` | 强制程度 |
| `lreq:hasAuthority` | lreq:Requirement | `lreq:RequirementAuthority` | 权威（推理属性） |
| `lreq:derivedFrom` | lreq:Requirement | `lreq:RequirementSource` | 来源文件 |
| `lreq:derivedFromClause` | lreq:Requirement | `lreq:StandardClause` | 来源条款 |
| `lreq:issuedBy` | lreq:RequirementSource | `lreq:RequirementAuthority` | 来源由某权威发布 |
| `lreq:hasClause` | lreq:RequirementSource | `lreq:StandardClause` | 来源包含某条款 |
| `lreq:hasAspect` | lreq:Requirement | `lreq:RequirementAspect` | 多维分类 |
| `lreq:targetCharacteristic` | lreq:CharacteristicTarget | `lbo-core:Characteristic` | 目标特性 |
| `lreq:targetFunction` | lreq:FunctionTarget | `lcap:Function` | 目标功能 |
| `lreq:targetInterface` | lreq:InterfaceTarget | `lprod:Interface` | 目标接口 |
| `lreq:targetRelationship` | lreq:RelationshipTarget | `lprod:ProductRelationship` | 目标关系 |
| **`lreq:targetPartRelationship`** | **lreq:PartRelationshipTarget** | **`lprod:PartRelationship`** | **目标部件关系（v1.2 新增）** |
| `lreq:targetStructure` | lreq:StructureTarget | `lprod:Structure` | 目标结构 |
| `lreq:targetProcess` | lreq:ProcessTarget | `lprod:Process` | 目标过程 |
| `lreq:targetService` | lreq:ServiceTarget | `lprod:Service` | 目标服务 |
| **`lreq:requiredConnectionType`** | **lreq:RelationshipTarget** | **`lprod:ConnectionType`** | **要求的连接方式（v1.2 新增）** |
| **`lreq:requiredImportanceLevel`** | **lreq:RelationshipTarget** | **`lprod:ImportanceLevel`** | **要求的重要性级别（v1.2 新增）** |
| **`lreq:requiredReplaceability`** | **lreq:RelationshipTarget** | **`lprod:Replaceability`** | **要求的可替换性（v1.2 新增）** |


## 18. 冻结声明

### 18.1 冻结范围

v1.2 确认后，以下内容进入**正式冻结状态**：

- ✅ **六元语义框架**（Authority + Scope + SemanticTarget + Condition + Constraint + Obligation）
- ✅ 所有核心类（Requirement、RequirementSource、TargetScope、RequirementAspect）
- ✅ **SemanticTarget 类型体系**（CharacteristicTarget、FunctionTarget、InterfaceTarget、RelationshipTarget、**PartRelationshipTarget**、StructureTarget、ProcessTarget、ServiceTarget）
- ✅ 所有核心对象属性（包括 v1.2 新增的 `targetPartRelationship`、`requiredConnectionType`、`requiredImportanceLevel`、`requiredReplaceability`）
- ✅ 与 Core Ontology 的接口（Characteristic、EvaluationContext、ObligationLevel）
- ✅ 与 Constraint Ontology 的接口（hasConstraint — 明确为外部引用）
- ✅ 与 Product Ontology 的接口（RelationshipTarget → ProductRelationship、PartRelationshipTarget → PartRelationship）
- ✅ 命名空间 `https://ontology.leleby.org/requirement/`

### 18.2 扩展点（Reserved Extension Points）

以下内容允许在 v1.2 基础上进行模块内部扩展，无需变更核心冻结模型：

- ✅ **新增 SemanticTarget 子类（扩展点）**
- ✅ 新增 Aspect 类型
- ✅ 新增 Scope 维度
- ✅ 新增 MarketScope / LifecycleScope / EnvironmentScope 值
- ✅ 新增关系类型
- ✅ 新增推理规则

### 18.3 冻结后禁止

- ❌ **修改六元核心模型**
- ❌ **修改或删除任何现有核心类**
- ❌ **修改或删除任何现有核心属性**
- ❌ **在 Requirement Ontology 中定义 Constraint 类型**（属于 Constraint Ontology）
- ❌ **在 Requirement Ontology 中定义 Condition 类型**（属于 Core Ontology）
- ❌ **在 Requirement Ontology 中定义 Obligation 类型**（属于 Core Ontology）
- ❌ **改变与 Core / Constraint / Standard / Specification / Product 的核心接口**
- ❌ **将 SemanticTarget 回退为仅支持 Characteristic**
- ❌ **将 Constraint 嵌入 Requirement 内部定义**（必须保持为外部引用）


## 19. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v0.1 | 2026-07-28 | 初始版本 |
| v0.2 | 2026-07-28 | 全面重构 |
| v0.3 | 2026-07-28 | 核心冻结版：五元模型 + ConditionSet |
| v0.4 | 2026-07-31 | 工业约束语义模型版：六元模型 + 8+ Constraint 类型 + Characteristic 迁移 |
| v1.0 | 2026-07-31 | 核心冻结发布版：Authority 推理；Constraint/Condition/Obligation 迁移至 Core；TargetScope 多维增强 |
| v1.1 | 2026-08-04 | 语义目标扩展版：术语“需求”改为“要求”；第三元从 Characteristic 升级为 SemanticTarget；新增 7 个子类；拆分 hasScope/hasTargetElement；新增 Demand 边界；新增 Product Ontology 接口 |
| **v1.2** | **2026-08-04** | **最终澄清版**：1）明确 Constraint 是外部独立 Ontology 实体，Requirement 仅持有引用；2）RelationshipTarget 增强，增加 requiredConnectionType、requiredImportanceLevel、requiredReplaceability 属性；3）新增 PartRelationshipTarget 子类，专门用于部件数量/角色/连接方式等结构约束；4）RDF-star 用途澄清：用于元数据标注而非核心关系；5）RequirementRelationship 与标准引用关系区分说明；6）更新 SHACL 验证约束；7）冻结声明更新，确认正式冻结 |


*— leleby Requirement Ontology Specification v1.2 — Final Clarification Release —*