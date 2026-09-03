# leleby Measurement Ontology Specification v0.4

**文档版本：** v0.4 — Foundation Alignment Edition（Foundation 对齐版）

**文档类型：** 模块规范（Module Ontology Specification）

**文档状态：** ⚠️ **核心对齐版（Core Aligned）** — 已同步至 leleby 核心语义模型（Requirement v1.2 / Product v0.4 / Constraint v1.2 / Foundation v1.1），待实例验证后进入正式冻结

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.2

**依赖模块：**
- `llb` Foundation Vocabulary Specification v1.1（提供 `Entity`、`Concept`、`Statement`、`Event` 等纯元概念）
- `lbo-core` Core Ontology Specification v1.2（提供 `Characteristic`、`SemanticTarget`、`EvaluationContext`、`Assessment`）
- `lcon` Constraint Ontology Specification v1.2（提供 `Constraint`、`ConstraintEvaluation`）
- `lreq` Requirement Ontology Specification v1.2（提供 `SemanticTarget` 概念对齐）
- `lprod` Product Ontology Specification v0.4（提供 `ProductRelationship` 等目标）
- `qudt` QUDT（提供 `QuantityValue`、`Unit`、`QuantityKind`——量值表达的基础）

**命名空间：** `https://ontology.leleby.org/measurement/`

**推荐前缀：** `lbo-meas`

**目标受众：** 本体架构师、测试工程师、计量工程师、AI Agent 开发者


## 目录

1. 引言
   1.1 目的
   1.2 核心定位
   1.3 v0.4 与 v0.3 的核心差异
   1.4 设计原则
   1.5 与 Foundation Vocabulary 的边界（v0.4 新增）

2. 命名空间声明
3. 核心概念模型
   3.1 测量顶层模型
   3.2 测量闭环模型
   3.3 测量在 leleby 架构中的位置

4. 类规范
   4.1 ObservableEntity（可观测实体）
   4.2 Quantity（量值抽象 — v0.4 新增，从 Foundation 迁移）
   4.3 MeasurableTarget（可测量目标）
   4.4 CharacteristicTarget（特性目标）
   4.5 FunctionTarget（功能目标）
   4.6 InterfaceTarget（接口目标）
   4.7 RelationshipTarget（关系目标）
   4.8 MeasurementQuantity（测量量）
   4.9 MeasurementObservation（测量观测）
   4.10 MeasurementResult（测量结果）
   4.11 MeasurementValue（测量值）
   4.12 ScalarValue（标量值）
   4.13 IntervalValue（区间值）
   4.14 RangeValue（范围值）
   4.15 DistributionValue（分布值）
   4.16 StatisticalValue（统计值）
   4.17 MeasurementUncertainty（测量不确定度）
   4.18 MeasurementStatus（测量状态）
   4.19 MeasurementContext（测量上下文）
   4.20 MeasurementMethodApplication（测量方法应用）
   4.21 MeasurementCapability（可测性）

5. 对象属性（v0.4 更新）
6. 数据属性（v0.4 更新）
7. 与 QUDT 的集成（v0.4 更新）
8. 与外部标准的对齐
   8.1 QUDT
   8.2 SOSA/SSN
   8.3 VIM
9. 与其他模块的接口（v0.4 更新）
   9.1 与 Core Ontology 的接口
   9.2 与 Foundation Vocabulary 的接口（v0.4 新增）
   9.3 与 Requirement Ontology 的接口
   9.4 与 Constraint Ontology 的接口
   9.5 与 Specification Framework 的接口
   9.6 与 Verification Ontology 的接口
   9.7 接口总图
10. 推理规则
11. SHACL 验证约束（v0.4 更新）
12. 完整示例（v0.4 更新）
13. 核心类汇总
14. 冻结声明
15. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Measurement Ontology 是 leleby 语义基础设施中**测量事实表达**的核心模块。它定义了工业测量活动的语义模型，使测量数据成为机器可理解、可推理的事实证据。

本规范回答以下核心问题：

- **什么被测量？** —— ObservableEntity（产品、零件、材料、环境）
- **测量什么目标？** —— MeasurableTarget（特性、功能、接口、关系等）
- **在什么条件下测量？** —— MeasurementContext（环境、工况、时间）
- **用什么方法？** —— MeasurementMethodApplication
- **测到什么结果？** —— MeasurementResult（数值、范围、不确定性、状态）

本规范是 leleby Measurement Ontology 的 v0.4 版本。

### 1.2 核心定位

> **Measurement Ontology 描述的是“一个对象的某个可测量目标，在特定条件下，被某种方法测量后，得到什么具有语义的事实数据”。**

**核心表述：**

```
MeasurementObservation =
    ObservableEntity（被测量的对象）
  + MeasurableTarget（被测量的目标——特性/功能/接口/关系）
  + MeasurementContext（测量条件）
  + MeasurementMethod（测量方法）
  + MeasurementResult（测量结果）
```

**关键定位声明：**

> **Measurement 不是“值”。Measurement 是产生事实的完整过程。** `MeasurementObservation` 代表一次测量活动，`MeasurementResult` 代表该活动产生的事实数据。两者必须区分。

### 1.3 v0.4 与 v0.3 的核心差异

| 问题 | v0.3 状态 | v0.4 修正 |
|---|---|---|
| **量值表达** | 依赖 `llb:Quantity`（Foundation） | **接收从 Foundation v1.1 迁移的 `Quantity` 类**，在本模块中定义为 `lbo-meas:Quantity` |
| **量值属性** | 依赖 `llb:hasNumericValue`、`llb:hasUnit` | **接收属性迁移**，在本模块中定义为 `lbo-meas:hasNumericValue`、`lbo-meas:hasUnit` |
| **MeasurementQuantity 父类** | `llb:Quantity`（在 Foundation v1.1 中已移除） | **改为 `llb:Concept`**，因为 `llb:Quantity` 已迁移至本模块 |
| **QUDT 集成** | 基础引用 | **强化说明**：量值表达以 QUDT 为基础，`lbo-meas:Quantity` 与 `qudt:QuantityValue` 互补使用 |
| **Foundation 边界** | 未明确 | **新增章节**，明确 Measurement Ontology 与 Foundation Vocabulary 的协作关系 |
| **SHACL 约束** | 无 `Quantity` 约束 | **新增 `QuantityShape`**，验证数值和单位的完整性 |

### 1.4 设计原则

**原则一：观测与事实分离**

> **MeasurementObservation（观测活动）** 与 **MeasurementResult（结果事实）** 必须分离。观测是过程，结果是事实。

**原则二：值与事实分离**

> `MeasurementResult` 不是单纯的值。它包含值、单位、不确定性、状态、条件等完整语义。

**原则三：可测性是关系，不是继承**

> `MeasurableTarget` 通过 `hasMeasurementCapability` 关联 `MeasurementQuantity`，而非通过子类化。这保持 Core Ontology 的稳定性，同时支持测量语义的扩展。

**原则四：测量目标是泛化的**

> 测量目标不限于 `Characteristic`。功能（Function）、接口（Interface）、关系（Relationship）等工程语义元素同样可以被观测或测量。`MeasurableTarget` 是 `lreq:SemanticTarget` 中可被观测的子集。

**原则五：测量结果是事实，不是判断**

> `MeasurementResult` 只记录“测得什么”，不判断“是否合格”。符合性判断由 `ConstraintEvaluation` 和 `ComplianceAssessment` 负责。

**原则六：与 QUDT 深度集成**

> 所有量值表达使用 QUDT 的 `QuantityValue`、`Unit`、`QuantityKind`，不重新定义单位或量纲。
>
> **v0.4 补充：** Foundation Vocabulary v1.1 已将 `llb:Quantity` 类迁移至 Measurement Ontology。本模块中的 `lbo-meas:Quantity` 类继承自 `llb:Entity`，作为量值的抽象表达。具体的数值+单位组合通过 QUDT 的 `qudt:QuantityValue` 表达。`lbo-meas:Quantity` 与 `qudt:QuantityValue` 的关系是：前者是 leleby 的量值抽象概念，后者是其 QUDT 兼容的具体表达形式。

**原则七：测量结果是证据，不是验证结论**

> `MeasurementResult` 是 `VerificationAssessment` 的**证据输入**，而非验证结果本身。验证活动引用测量结果作为支持证据。

### 1.5 与 Foundation Vocabulary 的边界（v0.4 新增）

> **Measurement Ontology 是 Foundation Vocabulary 中量值相关概念（`llb:Quantity`）的继承者和扩展者。**
>
> Foundation Vocabulary v1.1 将 `llb:Quantity` 类及 `llb:hasQuantity`、`llb:hasNumericValue`、`llb:hasUnit` 属性迁移至 Measurement Ontology，由 Measurement Ontology 全权负责量值的语义表达。
>
> 因此：
>
> - Foundation Vocabulary 不再包含任何量值相关类
> - Measurement Ontology 通过 `lbo-meas:Quantity` 类继承 `llb:Entity`（而非 `llb:Quantity`，因为 `llb:Quantity` 已迁移至本模块）
> - 所有量值表达以 QUDT 的 `qudt:QuantityValue` 作为基础类型
>
> 这种设计使 Foundation 层保持“纯元概念”定位，同时使 Measurement Ontology 拥有完整的量值语义控制权。


## 2. 命名空间声明

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix llb: <https://ontology.leleby.org/foundation/> .
@prefix lbo-core: <https://ontology.leleby.org/core/> .
@prefix lbo-meas: <https://ontology.leleby.org/measurement/> .
@prefix lreq: <https://ontology.leleby.org/requirement/> .
@prefix lcon: <https://ontology.leleby.org/constraint/> .
@prefix lprod: <https://ontology.leleby.org/product/> .
@prefix qudt: <http://qudt.org/schema/qudt/> .

<https://ontology.leleby.org/measurement/>
    rdf:type owl:Ontology ;
    owl:versionInfo "0.4" ;
    owl:imports <https://ontology.leleby.org/foundation/> ;
    owl:imports <https://ontology.leleby.org/core/> ;
    owl:imports <https://ontology.leleby.org/requirement/> ;
    owl:imports <http://qudt.org/schema/qudt/> ;
    rdfs:label "leleby Measurement Ontology" ;
    rdfs:comment "leleby 测量事实表达模块，定义测量活动、测量结果及其语义" .
```


## 3. 核心概念模型

### 3.1 测量顶层模型

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Measurement 核心结构（v0.4）                            │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    MeasurementObservation（测量观测）               │   │
│  │  一次完整的测量活动                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│     ┌──────────────┬───────────────┼───────────────┬──────────────┐       │
│     │              │               │               │              │       │
│     ▼              ▼               ▼               ▼              ▼       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Observable│  │Measurable│  │Context   │  │Method    │  │Result    │   │
│  │Entity    │  │Target    │  │          │  │Application│  │          │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                     │                                                     │
│        ┌────────────┼────────────┐                                        │
│        │            │            │                                        │
│        ▼            ▼            ▼                                        │
│  Characteristic  Function    Interface   Relationship                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    MeasurementResult（测量结果）                    │   │
│  │  测量活动产生的事实                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                    ┌───────────────┼───────────────┐                    │
│                    │               │               │                    │
│                    ▼               ▼               ▼                    │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │
│  │   MeasurementValue  │  │  Uncer-         │  │  MeasurementStatus  │   │
│  │   （测量值）         │  │  tainty        │  │  （测量状态）        │   │
│  │   - ScalarValue     │  │  （不确定度）   │  │  - Valid            │   │
│  │   - IntervalValue   │  │                 │  │  - Invalid          │   │
│  │   - RangeValue      │  │                 │  │  - Estimated        │   │
│  │   - Distribution    │  │                 │  │  - Calculated       │   │
│  │   - Statistical     │  │                 │  │  - Observed         │   │
│  └─────────────────────┘  └─────────────────┘  └─────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 测量闭环模型

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    测量在 leleby 推理链中的位置（v0.4）                      │
│                                                                             │
│  Requirement（要求——来自 lreq）                                             │
│       │                                                                     │
│       │  lreq:hasTargetElement → lreq:SemanticTarget                       │
│       │                     │                                              │
│       │                     │ 可被测量的子集                                │
│       ▼                     ▼                                              │
│  MeasurableTarget（可测量目标——来自 lbo-meas）                             │
│       │                                                                     │
│       │  lbo-meas:hasMeasurementCapability                                 │
│       ▼                                                                     │
│  MeasurementQuantity（测量量）                                               │
│       │                                                                     │
│       │  定义测量方法                                                       │
│       ▼                                                                     │
│  MeasurementObservation（测量观测）                                         │
│       │                                                                     │
│       │  产生                                                               │
│       ▼                                                                     │
│  MeasurementResult（测量结果）                                              │
│       │                                                                     │
│       │  作为证据输入                                                       │
│       ▼                                                                     │
│  ConstraintEvaluation / VerificationAssessment（约束评估/验证评估）         │
│       │                                                                     │
│       │  产生                                                               │
│       ▼                                                                     │
│  ComplianceAssessment（合规评估）                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 测量在 leleby 架构中的位置

```
                    leleby Semantic Infrastructure


                            llb Foundation
                                 |
                                 |
                        lbo-core Core Ontology
                                 |
        ----------------------------------------------------
        |              |              |              |
   Requirement    Specification  Measurement    Constraint
   Ontology       Framework      Ontology       Ontology
   (lreq:)        (lbo-spec:)    (lbo-meas:)    (lcon:)
        |              |              |              |
        ----------------------------------------------------
                                 |
                                 |
                      Compliance Reasoning
```


## 4. 类规范

### 4.1 ObservableEntity（可观测实体）

```turtle
lbo-meas:ObservableEntity
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "ObservableEntity" ;
    rdfs:comment "可以被测量的实体，如产品、零件、材料、环境等" .
```

**用途：** 表示任何可以被测量活动观测的对象。产品、零件、材料、环境条件等均可作为观测实体。

**示例：**
- `lbo-core:Product` 的实例
- `lbo-core:ProductInstance` 的实例
- `lbo-core:Process` 的实例

### 4.2 Quantity（量值抽象 — v0.4 新增，从 Foundation 迁移）

```turtle
lbo-meas:Quantity
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "Quantity" ;
    rdfs:comment "量的抽象表达，用于表达数值与单位的组合。此类从 Foundation Vocabulary v1.1 迁移至此，由 Measurement Ontology 全权负责量值语义" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:hasNumericValue` | `lbo-meas:Quantity` | `xsd:double` | 量的数值 | 1 |
| `lbo-meas:hasUnit` | `lbo-meas:Quantity` | `qudt:Unit` | 量的单位（来自 QUDT） | 1 |
| `lbo-meas:hasQuantityKind` | `lbo-meas:Quantity` | `qudt:QuantityKind` | 量的量纲（来自 QUDT） | 0..1 |

**说明：** 此类与 QUDT 的 `qudt:QuantityValue` 互补。`lbo-meas:Quantity` 是 leleby 语义体系内的量值抽象，而 `qudt:QuantityValue` 是 QUDT 标准中的具体量值表达。推荐使用 QUDT 表达具体量值，使用 `lbo-meas:Quantity` 表达量值概念或与 leleby 其他模块交互。

### 4.3 MeasurableTarget（可测量目标）

```turtle
lbo-meas:MeasurableTarget
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "MeasurableTarget" ;
    rdfs:comment "可测量目标的抽象基类。表示测量活动具体观测的对象——可以是特性、功能、接口或关系。与 lreq:SemanticTarget 保持概念对齐，但仅包含可被观测的子集" .
```

**设计说明：**

> `MeasurableTarget` 是 `lreq:SemanticTarget` 中**可被观测/测量**的子集。不是所有 `SemanticTarget` 都能被传统意义上的“测量”覆盖（例如，某些结构关系更适合“检查”而非“测量”）。但测量模块负责定义所有可通过观测获取事实证据的目标类型。

**MeasurableTarget 类型体系：**

```
MeasurableTarget
    ├── CharacteristicTarget（特性目标）
    │       └── targetCharacteristic → lbo-core:Characteristic
    ├── FunctionTarget（功能目标）
    │       └── targetFunction → lcap:Function / lprod:ProductFeature
    ├── InterfaceTarget（接口目标）
    │       └── targetInterface → lprod:Interface
    └── RelationshipTarget（关系目标）
            └── targetRelationship → lprod:ProductRelationship
```

### 4.4 CharacteristicTarget（特性目标）

```turtle
lbo-meas:CharacteristicTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-meas:MeasurableTarget ;
    rdfs:label "CharacteristicTarget" ;
    rdfs:comment "特性类测量目标，指向 lbo-core:Characteristic" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:targetCharacteristic` | CharacteristicTarget | `lbo-core:Characteristic` | 目标特性 | 1 |

### 4.5 FunctionTarget（功能目标）

```turtle
lbo-meas:FunctionTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-meas:MeasurableTarget ;
    rdfs:label "FunctionTarget" ;
    rdfs:comment "功能类测量目标，指向产品功能或能力" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:targetFunction` | FunctionTarget | `lcap:Function` / `lprod:ProductFeature` | 目标功能 | 1 |

### 4.6 InterfaceTarget（接口目标）

```turtle
lbo-meas:InterfaceTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-meas:MeasurableTarget ;
    rdfs:label "InterfaceTarget" ;
    rdfs:comment "接口类测量目标，指向产品接口" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:targetInterface` | InterfaceTarget | `lprod:Interface` | 目标接口 | 1 |

### 4.7 RelationshipTarget（关系目标）

```turtle
lbo-meas:RelationshipTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-meas:MeasurableTarget ;
    rdfs:label "RelationshipTarget" ;
    rdfs:comment "关系类测量目标，指向产品关系（如 PartRelationship）。可用于表达对关系属性的观测，如连接强度、间隙尺寸等" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:targetRelationship` | RelationshipTarget | `lprod:ProductRelationship` | 目标产品关系 | 1 |
| `lbo-meas:targetRelationshipType` | RelationshipTarget | rdfs:Class | 目标关系类型 | 0..1 |

### 4.8 MeasurementQuantity（测量量）

```turtle
lbo-meas:MeasurementQuantity
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "MeasurementQuantity" ;
    rdfs:comment "测量量的概念定义，包含量纲、单位、测量方法等信息。对齐 QUDT 的 QuantityKind。注意：此类是'关于测量量的概念'，而非量值本身（量值由 lbo-meas:Quantity 表达）" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:quantityName` | MeasurementQuantity | xsd:string | 量名称 | 1 |
| `lbo-meas:quantitySymbol` | MeasurementQuantity | xsd:string | 量符号 | 0..1 |
| `lbo-meas:hasQuantityKind` | MeasurementQuantity | `qudt:QuantityKind` | 量纲（来自 QUDT） | 1 |
| `lbo-meas:hasDefaultUnit` | MeasurementQuantity | `qudt:Unit` | 默认单位 | 0..1 |

### 4.9 MeasurementObservation（测量观测）

```turtle
lbo-meas:MeasurementObservation
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Event ;
    rdfs:label "MeasurementObservation" ;
    rdfs:comment "一次完整的测量观测活动，包含测量对象、测量目标、上下文、方法和结果" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo-meas:observationId` | 观测唯一标识符 | 0..1 |
| `lbo-meas:observationName` | 观测名称 | 0..1 |
| `lbo-meas:observationTime` | 观测时间 | 0..1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:hasSubject` | MeasurementObservation | `lbo-meas:ObservableEntity` | 被测量的实体 | 1 |
| `lbo-meas:observes` | MeasurementObservation | **`lbo-meas:MeasurableTarget`** | 被测量的目标 | 1 |
| `lbo-meas:hasContext` | MeasurementObservation | `lbo-core:EvaluationContext` | 测量条件 | 0..1 |
| `lbo-meas:usesMethod` | MeasurementObservation | `lbo-meas:MeasurementMethodApplication` | 使用的测量方法 | 0..1 |
| `lbo-meas:produces` | MeasurementObservation | `lbo-meas:MeasurementResult` | 产生的测量结果 | 1 |

### 4.10 MeasurementResult（测量结果）

```turtle
lbo-meas:MeasurementResult
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "MeasurementResult" ;
    rdfs:comment "测量活动产生的结果事实，包含值、单位、不确定性、状态" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo-meas:hasValue` | 测量值 | 1 |
| `lbo-meas:hasUnit` | 测量单位 | 0..1 |
| `lbo-meas:hasUncertainty` | 测量不确定度 | 0..1 |
| `lbo-meas:hasStatus` | 测量状态 | 0..1 |
| `lbo-meas:isValid` | 是否有效（快捷属性） | 0..1 |

### 4.11 MeasurementValue（测量值）

```turtle
lbo-meas:MeasurementValue
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "MeasurementValue" ;
    rdfs:comment "测量值的抽象基类，支持多种值表达形式" .
```

**子类：**

| 子类 | 说明 | 示例 |
|---|---|---|
| `lbo-meas:ScalarValue` | 标量值 | 25.0℃ |
| `lbo-meas:IntervalValue` | 区间值 | 69.8~70.2℃ |
| `lbo-meas:RangeValue` | 范围值 | -40~70℃ |
| `lbo-meas:DistributionValue` | 分布值 | 正态分布(μ=25, σ=0.5) |
| `lbo-meas:StatisticalValue` | 统计值 | 平均值、最大值、最小值 |

### 4.12 ScalarValue（标量值）

```turtle
lbo-meas:ScalarValue
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-meas:MeasurementValue ;
    rdfs:label "ScalarValue" ;
    rdfs:comment "单一数值表达" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:scalarValue` | ScalarValue | `qudt:QuantityValue` | 量值（使用 QUDT） | 1 |

### 4.13 IntervalValue（区间值）

```turtle
lbo-meas:IntervalValue
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-meas:MeasurementValue ;
    rdfs:label "IntervalValue" ;
    rdfs:comment "测量结果的区间表达，如 69.8~70.2℃" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:lowerBound` | IntervalValue | `qudt:QuantityValue` | 下限值 | 1 |
| `lbo-meas:upperBound` | IntervalValue | `qudt:QuantityValue` | 上限值 | 1 |
| `lbo-meas:includeLower` | IntervalValue | xsd:boolean | 是否包含下限（默认 true） | 0..1 |
| `lbo-meas:includeUpper` | IntervalValue | xsd:boolean | 是否包含上限（默认 true） | 0..1 |

### 4.14 RangeValue（范围值）

```turtle
lbo-meas:RangeValue
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-meas:MeasurementValue ;
    rdfs:label "RangeValue" ;
    rdfs:comment "属性的允许范围，如 -40~70℃（用于规格定义）" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:minValue` | RangeValue | `qudt:QuantityValue` | 最小值 | 0..1 |
| `lbo-meas:maxValue` | RangeValue | `qudt:QuantityValue` | 最大值 | 0..1 |

### 4.15 DistributionValue（分布值）

```turtle
lbo-meas:DistributionValue
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-meas:MeasurementValue ;
    rdfs:label "DistributionValue" ;
    rdfs:comment "分布值，如正态分布" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:distributionType` | DistributionValue | lbo-meas:DistributionType | 分布类型 | 1 |
| `lbo-meas:parameters` | DistributionValue | rdfs:Literal | 分布参数 | 0..* |

**DistributionType 枚举：**

| 值 | 说明 |
|---|---|
| `lbo-meas:NormalDistribution` | 正态分布 |
| `lbo-meas:UniformDistribution` | 均匀分布 |
| `lbo-meas:LogNormalDistribution` | 对数正态分布 |

### 4.16 StatisticalValue（统计值）

```turtle
lbo-meas:StatisticalValue
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-meas:MeasurementValue ;
    rdfs:label "StatisticalValue" ;
    rdfs:comment "统计值，如平均值、最大值、最小值" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:statisticalType` | StatisticalValue | lbo-meas:StatisticalType | 统计类型 | 1 |
| `lbo-meas:statisticalValue` | StatisticalValue | `qudt:QuantityValue` | 统计值 | 1 |
| `lbo-meas:sampleSize` | StatisticalValue | xsd:integer | 样本量 | 0..1 |

**StatisticalType 枚举：**

| 值 | 说明 |
|---|---|
| `lbo-meas:Mean` | 平均值 |
| `lbo-meas:Median` | 中位数 |
| `lbo-meas:StandardDeviation` | 标准差 |
| `lbo-meas:Maximum` | 最大值 |
| `lbo-meas:Minimum` | 最小值 |
| `lbo-meas:P95` | 95% 分位数 |

### 4.17 MeasurementUncertainty（测量不确定度）

```turtle
lbo-meas:MeasurementUncertainty
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "MeasurementUncertainty" ;
    rdfs:comment "测量不确定度，描述测量结果的质量" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo-meas:uncertaintyValue` | 不确定度值（± 后数值） | 1 |
| `lbo-meas:uncertaintyUnit` | 单位 | 1 |
| `lbo-meas:uncertaintyType` | 不确定度类型 | 0..1 |
| `lbo-meas:coverageFactor` | 包含因子 k | 0..1 |
| `lbo-meas:confidenceLevel` | 置信度 | 0..1 |

**UncertaintyType 枚举：**

| 值 | 说明 |
|---|---|
| `lbo-meas:StandardUncertainty` | 标准不确定度（k=1） |
| `lbo-meas:ExpandedUncertainty` | 扩展不确定度（k>1） |
| `lbo-meas:TypeA` | A 类不确定度（统计方法） |
| `lbo-meas:TypeB` | B 类不确定度（非统计方法） |

### 4.18 MeasurementStatus（测量状态）

```turtle
lbo-meas:MeasurementStatus
    rdf:type owl:Class ;
    rdfs:label "MeasurementStatus" ;
    rdfs:comment "测量结果的有效性状态" .
```

**预定义状态：**

| 值 | 说明 |
|---|---|
| `lbo-meas:Valid` | 有效测量结果 |
| `lbo-meas:Invalid` | 无效测量结果 |
| `lbo-meas:Estimated` | 估计值 |
| `lbo-meas:Calculated` | 计算值 |
| `lbo-meas:Observed` | 观测值 |

### 4.19 MeasurementContext（测量上下文）

```turtle
lbo-meas:MeasurementContext
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:EvaluationContext ;
    rdfs:label "MeasurementContext" ;
    rdfs:comment "测量活动的上下文环境。继承自 Core Ontology 的 EvaluationContext" .
```

### 4.20 MeasurementMethodApplication（测量方法应用）

```turtle
lbo-meas:MeasurementMethodApplication
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "MeasurementMethodApplication" ;
    rdfs:comment "测量方法在特定测量活动中的应用。引用定义在 Method Ontology 中的方法，不重新定义方法本身" .
```

| 属性 | 说明 | 基数 |
|---|---|---|
| `lbo-meas:methodId` | 方法标识符 | 0..1 |
| `lbo-meas:methodName` | 方法名称 | 1 |
| `lbo-meas:methodDescription` | 方法描述 | 0..1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:referencesMethod` | MeasurementMethodApplication | `lbo-method:TestMethod` | 引用的测试方法 | 0..1 |
| `lbo-meas:hasVersion` | MeasurementMethodApplication | xsd:string | 方法版本 | 0..1 |

### 4.21 MeasurementCapability（可测性）

```turtle
lbo-meas:MeasurementCapability
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "MeasurementCapability" ;
    rdfs:comment "可测量目标与测量量之间的可测性关系。表示某个 MeasurableTarget 可以通过某个 MeasurementQuantity 被测量" .
```

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lbo-meas:measurementSubject` | MeasurementCapability | **`lbo-meas:MeasurableTarget`** | 可被测量的目标 | 1 |
| `lbo-meas:measurementQuantity` | MeasurementCapability | `lbo-meas:MeasurementQuantity` | 对应的测量量 | 1 |
| `lbo-meas:measurementMethod` | MeasurementCapability | `lbo-meas:MeasurementMethodApplication` | 推荐测量方法 | 0..1 |


## 5. 对象属性（v0.4 更新）

### 5.1 观测结构与组成属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-meas:hasSubject` | `lbo-meas:MeasurementObservation` | `lbo-meas:ObservableEntity` | 被测量的实体 |
| `lbo-meas:observes` | `lbo-meas:MeasurementObservation` | **`lbo-meas:MeasurableTarget`** | 被测量的目标 |
| `lbo-meas:hasContext` | `lbo-meas:MeasurementObservation` | `lbo-core:EvaluationContext` | 测量条件 |
| `lbo-meas:usesMethod` | `lbo-meas:MeasurementObservation` | `lbo-meas:MeasurementMethodApplication` | 使用的测量方法 |
| `lbo-meas:produces` | `lbo-meas:MeasurementObservation` | `lbo-meas:MeasurementResult` | 产生的测量结果 |

### 5.2 值与结果属性（v0.4 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-meas:hasValue` | `lbo-meas:MeasurementResult` | `lbo-meas:MeasurementValue` | 测量值 |
| `lbo-meas:hasUnit` | `lbo-meas:MeasurementResult` | `qudt:Unit` | 测量单位 |
| `lbo-meas:hasUncertainty` | `lbo-meas:MeasurementResult` | `lbo-meas:MeasurementUncertainty` | 不确定度 |
| `lbo-meas:hasStatus` | `lbo-meas:MeasurementResult` | `lbo-meas:MeasurementStatus` | 测量状态 |
| `lbo-meas:hasNumericValue` | **`lbo-meas:Quantity`** | `xsd:double` | **量值数值（v0.4 新增，从 Foundation 迁移）** |
| `lbo-meas:hasUnit` | **`lbo-meas:Quantity`** | `qudt:Unit` | **量值单位（v0.4 新增，从 Foundation 迁移）** |
| `lbo-meas:hasQuantityKind` | **`lbo-meas:Quantity`** | `qudt:QuantityKind` | **量值量纲（v0.4 新增，从 Foundation 迁移）** |
| `lbo-meas:scalarValue` | `lbo-meas:ScalarValue` | `qudt:QuantityValue` | 标量值 |
| `lbo-meas:lowerBound` | `lbo-meas:IntervalValue` | `qudt:QuantityValue` | 区间下限 |
| `lbo-meas:upperBound` | `lbo-meas:IntervalValue` | `qudt:QuantityValue` | 区间上限 |
| `lbo-meas:minValue` | `lbo-meas:RangeValue` | `qudt:QuantityValue` | 范围最小值 |
| `lbo-meas:maxValue` | `lbo-meas:RangeValue` | `qudt:QuantityValue` | 范围最大值 |
| `lbo-meas:statisticalValue` | `lbo-meas:StatisticalValue` | `qudt:QuantityValue` | 统计值 |

### 5.3 可测性属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-meas:measurementSubject` | `lbo-meas:MeasurementCapability` | **`lbo-meas:MeasurableTarget`** | 可被测量的目标 |
| `lbo-meas:measurementQuantity` | `lbo-meas:MeasurementCapability` | `lbo-meas:MeasurementQuantity` | 对应的测量量 |
| `lbo-meas:measurementMethod` | `lbo-meas:MeasurementCapability` | `lbo-meas:MeasurementMethodApplication` | 推荐测量方法 |

### 5.4 上下文与方法属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-meas:referencesMethod` | `lbo-meas:MeasurementMethodApplication` | `lbo-method:TestMethod` | 引用的测试方法 |
| `lbo-meas:hasVersion` | `lbo-meas:MeasurementMethodApplication` | xsd:string | 方法版本 |

### 5.5 评估与证据属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-meas:isInputOf` | `lbo-meas:MeasurementResult` | `lbo-core:Assessment` | 测量结果是某评估活动的输入 |
| `lbo-meas:isEvidenceFor` | `lbo-meas:MeasurementResult` | `lbo-core:VerificationAssessment` | 测量结果是某验证活动的证据 |


## 6. 数据属性（v0.4 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-meas:observationId` | `lbo-meas:MeasurementObservation` | xsd:string | 观测标识符 |
| `lbo-meas:observationName` | `lbo-meas:MeasurementObservation` | xsd:string | 观测名称 |
| `lbo-meas:observationTime` | `lbo-meas:MeasurementObservation` | xsd:dateTime | 观测时间 |
| `lbo-meas:quantityName` | `lbo-meas:MeasurementQuantity` | xsd:string | 量名称 |
| `lbo-meas:quantitySymbol` | `lbo-meas:MeasurementQuantity` | xsd:string | 量符号 |
| `lbo-meas:uncertaintyValue` | `lbo-meas:MeasurementUncertainty` | xsd:double | 不确定度值 |
| `lbo-meas:coverageFactor` | `lbo-meas:MeasurementUncertainty` | xsd:double | 包含因子 |
| `lbo-meas:confidenceLevel` | `lbo-meas:MeasurementUncertainty` | xsd:double | 置信度 |
| `lbo-meas:isValid` | `lbo-meas:MeasurementResult` | xsd:boolean | 结果有效标志 |
| `lbo-meas:includeLower` | `lbo-meas:IntervalValue` | xsd:boolean | 包含下限 |
| `lbo-meas:includeUpper` | `lbo-meas:IntervalValue` | xsd:boolean | 包含上限 |
| **`lbo-meas:hasNumericValue`** | **`lbo-meas:Quantity`** | **xsd:double** | **量的数值（v0.4 新增，从 Foundation 迁移）** |


## 7. 与 QUDT 的集成（v0.4 更新）

**核心原则：** leleby Measurement Ontology 的量值表达以 QUDT 为基础，同时拥有从 Foundation Vocabulary 迁移而来的 `lbo-meas:Quantity` 类作为 leleby 内部量值抽象。

| QUDT 概念 | leleby Measurement 使用方式 |
|---|---|
| `qudt:QuantityValue` | 所有数值表达（标量、区间、范围、统计值）的基础类型 |
| `qudt:Unit` | 所有测量值的单位（同时也是 `lbo-meas:hasUnit` 的值域） |
| `qudt:QuantityKind` | 测量量（MeasurementQuantity）和量值（Quantity）的量纲定义来源 |
| `qudt:SI` | 国际单位制参考 |

**与 Foundation Vocabulary 的协作：**

Foundation Vocabulary v1.1 已将 `llb:Quantity` 类及 `llb:hasQuantity`、`llb:hasNumericValue`、`llb:hasUnit` 属性迁移至 Measurement Ontology：

| Foundation v1.0 中的概念 | Measurement v0.4 中的对应 |
|---|---|
| `llb:Quantity` | `lbo-meas:Quantity`（继承自 `llb:Entity`） |
| `llb:hasNumericValue` | `lbo-meas:hasNumericValue` |
| `llb:hasUnit` | `lbo-meas:hasUnit` |

**集成约束：**

> leleby Measurement Ontology 不重新定义单位或量纲结构。具体量值表达优先使用 QUDT 的 `qudt:QuantityValue`，`lbo-meas:Quantity` 作为 leleby 内部量值抽象与 QUDT 互补使用。这确保了与外部标准体系的对齐和互操作性。


## 8. 与外部标准的对齐

### 8.1 QUDT

| QUDT 概念 | leleby 映射 |
|---|---|
| `qudt:QuantityValue` | `lbo-meas:ScalarValue` 的值类型 |
| `qudt:Unit` | `lbo-meas:hasUnit` 的值域 |
| `qudt:QuantityKind` | `lbo-meas:MeasurementQuantity` 的 `hasQuantityKind` |

### 8.2 SOSA/SSN

| SOSA/SSN 概念 | leleby 映射 |
|---|---|
| `sosa:Observation` | `lbo-meas:MeasurementObservation` |
| `sosa:hasResult` | `lbo-meas:produces` |
| `sosa:observedProperty` | `lbo-meas:observes`（指向 MeasurableTarget） |
| `sosa:phenomenonTime` | `lbo-meas:observationTime` |

### 8.3 VIM（国际计量学词汇）

| VIM 概念 | leleby 映射 |
|---|---|
| `measurement` | `lbo-meas:MeasurementObservation` |
| `measurand` | `lbo-meas:observes` → `lbo-meas:MeasurableTarget` |
| `measurement result` | `lbo-meas:MeasurementResult` |
| `measurement uncertainty` | `lbo-meas:MeasurementUncertainty` |
| `coverage factor` | `lbo-meas:coverageFactor` |
| `confidence level` | `lbo-meas:confidenceLevel` |


## 9. 与其他模块的接口（v0.4 更新）

### 9.1 与 Core Ontology 的接口

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-meas:observes` | MeasurementObservation | `lbo-meas:MeasurableTarget` | 测量的目标 |
| `lbo-meas:hasContext` | MeasurementObservation | `lbo-core:EvaluationContext` | 测量条件 |

### 9.2 与 Foundation Vocabulary 的接口（v0.4 新增）

| Foundation 概念 | Measurement 对应 | 说明 |
|---|---|---|
| `llb:Entity` | `lbo-meas:Quantity` 的父类 | 量值继承自 Entity |
| `llb:Event` | `lbo-meas:MeasurementObservation` 的父类 | 观测活动继承自 Event |
| `llb:Statement` | `lbo-meas:MeasurementResult` 的父类 | 结果事实继承自 Statement |
| `llb:Concept` | `lbo-meas:MeasurementValue` 的父类 | 值抽象继承自 Concept |

> **注意：** Foundation v1.1 已移除 `llb:Quantity`，该概念已迁移至 Measurement Ontology 作为 `lbo-meas:Quantity`。所有量值相关的表达现在由 Measurement Ontology 和 QUDT 共同承担。

### 9.3 与 Requirement Ontology 的接口

> **`lbo-meas:MeasurableTarget` 与 `lreq:SemanticTarget` 保持概念对齐。**

```turtle
# SemanticTarget 中可被测量的子集映射为 MeasurableTarget
# 这不是 OWL 层面的子类关系（避免模块耦合），而是语义对齐
```

**对齐映射：**

| Requirement Ontology | Measurement Ontology | 说明 |
|---|---|---|
| `lreq:CharacteristicTarget` | `lbo-meas:CharacteristicTarget` | 特性目标 |
| `lreq:FunctionTarget` | `lbo-meas:FunctionTarget` | 功能目标 |
| `lreq:InterfaceTarget` | `lbo-meas:InterfaceTarget` | 接口目标 |
| `lreq:RelationshipTarget` | `lbo-meas:RelationshipTarget` | 关系目标 |
| `lreq:StructureTarget` | — | 结构目标（通常通过检查而非测量） |
| `lreq:ProcessTarget` | — | 过程目标（通常通过观察而非测量） |

### 9.4 与 Constraint Ontology 的接口

**核心调整：** `MeasurementResult` 不直接连接 `Constraint`。测量结果是 `ConstraintEvaluation` 的输入。

```turtle
# 测量结果是 ConstraintEvaluation 的输入（在 Core Ontology 中定义）
lbo-core:hasInput
    rdf:type owl:ObjectProperty ;
    rdfs:domain lbo-core:Assessment ;
    rdfs:range lbo-meas:MeasurementResult ;
    rdfs:label "hasInput" ;
    rdfs:comment "评估活动使用测量结果作为输入" .
```

**链路：**

```
MeasurementResult
    │
    │  isInputOf
    ▼
ConstraintEvaluation（在 Core Ontology 中）
    │
    │  evaluates
    ▼
Constraint
```

### 9.5 与 Specification Framework 的接口

```turtle
# SpecificationItem 提供验证目标，MeasurementResult 提供实测值
# 两者的比较在 Verification 中完成
```

**链路：**

```
SpecificationItem（目标值）
    │
    │  比较
    ▼
MeasurementResult（实测值）
```

### 9.6 与 Verification Ontology 的接口

**核心调整：** 测量结果是验证活动的**证据输入**，而非验证结果本身。

```turtle
# 测量结果是 VerificationAssessment 的证据（在 Core Ontology 中定义）
lbo-core:hasEvidence
    rdf:type owl:ObjectProperty ;
    rdfs:domain lbo-core:VerificationAssessment ;
    rdfs:range lbo-meas:MeasurementResult ;
    rdfs:label "hasEvidence" ;
    rdfs:comment "验证活动使用测量结果作为证据" .
```

**链路：**

```
VerificationAssessment（验证评估）
    │
    │  hasEvidence
    ▼
MeasurementResult（测量结果——事实证据）
```

### 9.7 接口总图（v0.4 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Measurement Ontology 与其他模块的接口（v0.4）            │
│                                                                             │
│  llb: Foundation Vocabulary                                                 │
│  └── 提供 Entity / Event / Statement / Concept 基础（v0.4 更新）            │
│         │                                                                  │
│         │  量值概念已从 Foundation 迁移至本模块                            │
│         ▼                                                                  │
│  lreq: Requirement Ontology                                                 │
│  └── SemanticTarget（概念对齐）                                            │
│         │                                                                  │
│         │  对齐                                                            │
│         ▼                                                                  │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║                       Measurement Ontology (lbo-meas:)              ║ │
│  ║  MeasurementObservation / MeasurementResult / MeasurementValue       ║ │
│  ║  Quantity（v0.4 新增，从 Foundation 迁移）                           ║ │
│  ║  MeasurableTarget                                                     ║ │
│  ║  ├── CharacteristicTarget → lbo-core:Characteristic                 ║ │
│  ║  ├── FunctionTarget → lcap:Function                                 ║ │
│  ║  ├── InterfaceTarget → lprod:Interface                              ║ │
│  ║  └── RelationshipTarget → lprod:ProductRelationship                 ║ │
│  ║  MeasurementQuantity / MeasurementUncertainty / MeasurementStatus   ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│         │                                                                  │
│         │  被引用（作为输入/证据）                                         │
│         ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  引用方                                                             │   │
│  │  ├── lbo-core:ConstraintEvaluation（使用 MeasurementResult 作为输入）│   │
│  │  ├── lbo-core:VerificationAssessment（使用 MeasurementResult 作为证据）│   │
│  │  └── lspec:SpecificationItem（比较目标值与实测值）                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 10. 推理规则

### 10.1 测量与约束评估规则

**规则1：测量结果作为约束评估输入**

```
IF MeasurementResult M hasValue V
AND ConstraintEvaluation CE hasInput M
AND Constraint C appliesTo Characteristic Ch
AND V satisfies C
THEN CE result PASS
```

**规则2：测量状态影响评估有效性**

```
IF MeasurementResult M hasStatus Invalid
THEN any ConstraintEvaluation using M as input is INVALID
```

### 10.2 测量与验证规则

**规则3：测量结果作为验证证据**

```
IF VerificationAssessment VA hasEvidence M
AND M is MeasurementResult
THEN VA is supported by evidence
```

**规则4：测量结果验证规格**

```
IF SpecificationItem S hasTargetValue T
AND MeasurementResult M hasValue V
AND V satisfies T
THEN VerificationAssessment VA using M as evidence is PASS
```


## 11. SHACL 验证约束（v0.4 更新）

### 11.1 Quantity 约束（v0.4 新增，从 Foundation 迁移）

```turtle
# Quantity 必须有数值和单位（从 Foundation 迁移）
lbo-meas:QuantityShape
    a sh:NodeShape ;
    sh:targetClass lbo-meas:Quantity ;
    sh:property [
        sh:path lbo-meas:hasNumericValue ;
        sh:datatype xsd:double ;
        sh:minCount 1 ;
        sh:message "Quantity 必须有数值"
    ] ;
    sh:property [
        sh:path lbo-meas:hasUnit ;
        sh:minCount 1 ;
        sh:message "Quantity 必须有单位"
    ] .
```

### 11.2 MeasurementObservation 约束

```turtle
lbo-meas:MeasurementObservationShape
    a sh:NodeShape ;
    sh:targetClass lbo-meas:MeasurementObservation ;
    sh:property [
        sh:path lbo-meas:hasSubject ;
        sh:minCount 1 ;
        sh:message "MeasurementObservation must have a subject"
    ] ;
    sh:property [
        sh:path lbo-meas:observes ;
        sh:minCount 1 ;
        sh:message "MeasurementObservation must observe a MeasurableTarget"
    ] ;
    sh:property [
        sh:path lbo-meas:produces ;
        sh:minCount 1 ;
        sh:message "MeasurementObservation must produce a result"
    ] .
```

### 11.3 MeasurementResult 约束

```turtle
lbo-meas:MeasurementResultShape
    a sh:NodeShape ;
    sh:targetClass lbo-meas:MeasurementResult ;
    sh:property [
        sh:path lbo-meas:hasValue ;
        sh:minCount 1 ;
        sh:message "MeasurementResult must have a value"
    ] ;
    sh:property [
        sh:path lbo-meas:hasUnit ;
        sh:minCount 1 ;
        sh:message "MeasurementResult must have a unit"
    ] .
```

### 11.4 IntervalValue 约束

```turtle
lbo-meas:IntervalValueShape
    a sh:NodeShape ;
    sh:targetClass lbo-meas:IntervalValue ;
    sh:property [
        sh:path lbo-meas:lowerBound ;
        sh:minCount 1 ;
        sh:message "IntervalValue must have a lower bound"
    ] ;
    sh:property [
        sh:path lbo-meas:upperBound ;
        sh:minCount 1 ;
        sh:message "IntervalValue must have an upper bound"
    ] ;
    sh:property [
        sh:path lbo-meas:lowerBound ;
        sh:lessThan lbo-meas:upperBound ;
        sh:message "lowerBound must be less than upperBound"
    ] .
```

### 11.5 MeasurementQuantity 约束（v0.4 新增）

```turtle
# MeasurementQuantity 必须有 quantityName 和 hasQuantityKind
lbo-meas:MeasurementQuantityShape
    a sh:NodeShape ;
    sh:targetClass lbo-meas:MeasurementQuantity ;
    sh:property [
        sh:path lbo-meas:quantityName ;
        sh:minCount 1 ;
        sh:message "MeasurementQuantity 必须有量名称"
    ] ;
    sh:property [
        sh:path lbo-meas:hasQuantityKind ;
        sh:minCount 1 ;
        sh:message "MeasurementQuantity 必须有量纲（qudt:QuantityKind）"
    ] .
```

### 11.6 MeasurableTarget 约束

```turtle
# CharacteristicTarget 必须有 targetCharacteristic
lbo-meas:CharacteristicTargetShape
    a sh:NodeShape ;
    sh:targetClass lbo-meas:CharacteristicTarget ;
    sh:property [
        sh:path lbo-meas:targetCharacteristic ;
        sh:minCount 1 ;
        sh:message "CharacteristicTarget must have a target characteristic"
    ] .

# FunctionTarget 必须有 targetFunction
lbo-meas:FunctionTargetShape
    a sh:NodeShape ;
    sh:targetClass lbo-meas:FunctionTarget ;
    sh:property [
        sh:path lbo-meas:targetFunction ;
        sh:minCount 1 ;
        sh:message "FunctionTarget must have a target function"
    ] .

# InterfaceTarget 必须有 targetInterface
lbo-meas:InterfaceTargetShape
    a sh:NodeShape ;
    sh:targetClass lbo-meas:InterfaceTarget ;
    sh:property [
        sh:path lbo-meas:targetInterface ;
        sh:minCount 1 ;
        sh:message "InterfaceTarget must have a target interface"
    ] .

# RelationshipTarget 必须有 targetRelationship 或 targetRelationshipType
lbo-meas:RelationshipTargetShape
    a sh:NodeShape ;
    sh:targetClass lbo-meas:RelationshipTarget ;
    sh:or (
        [ sh:path lbo-meas:targetRelationship ; sh:minCount 1 ]
        [ sh:path lbo-meas:targetRelationshipType ; sh:minCount 1 ]
    ) ;
    sh:message "RelationshipTarget must have a target relationship or relationship type" .
```


## 12. 完整示例（v0.4 更新）

### 12.1 LED 灯具温度测量（使用 CharacteristicTarget）

```turtle
# 可观测实体
llc:Lamp_X100_Instance_001
    a lbo-core:ProductInstance ;
    lbo-core:hasProductName "Outdoor LED Luminaire X100" ;
    lbo-core:hasSerialNumber "SN-2026-001" .

# 特性目标
lbo-meas:Target_OperatingTemp
    a lbo-meas:CharacteristicTarget ;
    lbo-meas:targetCharacteristic lbo-core:OperatingTemperature .

# 测量量
lbo-meas:TemperatureQuantity
    a lbo-meas:MeasurementQuantity ;
    lbo-meas:quantityName "Temperature" ;
    lbo-meas:quantitySymbol "T" ;
    lbo-meas:hasQuantityKind qudt:ThermodynamicTemperature ;
    lbo-meas:hasDefaultUnit qudt:DEG_C .

# 可测性关系
llc:Temp_Measurability
    a lbo-meas:MeasurementCapability ;
    lbo-meas:measurementSubject lbo-meas:Target_OperatingTemp ;
    lbo-meas:measurementQuantity lbo-meas:TemperatureQuantity ;
    lbo-meas:measurementMethod [
        a lbo-meas:MeasurementMethodApplication ;
        lbo-meas:methodName "Thermocouple measurement" ;
        lbo-meas:methodDescription "K-type thermocouple with digital thermometer"
    ] .

# 测量上下文
llc:Temp_Context
    a lbo-core:EnvironmentalContext ;
    lbo-core:temperature 25 ;
    lbo-core:temperatureUnit llb:DegreeCelsius .

# 测量观测
llc:Temp_Observation_001
    a lbo-meas:MeasurementObservation ;
    lbo-meas:observationId "OBS-TEMP-001" ;
    lbo-meas:observationTime "2026-07-31T10:30:00Z"^^xsd:dateTime ;
    lbo-meas:hasSubject llc:Lamp_X100_Instance_001 ;
    lbo-meas:observes lbo-meas:Target_OperatingTemp ;
    lbo-meas:hasContext llc:Temp_Context ;
    lbo-meas:usesMethod [
        a lbo-meas:MeasurementMethodApplication ;
        lbo-meas:methodName "Thermocouple measurement"
    ] .

# 测量结果（使用 QUDT 表达量值）
llc:Temp_Result_001
    a lbo-meas:MeasurementResult ;
    lbo-meas:hasValue [
        a lbo-meas:ScalarValue ;
        lbo-meas:scalarValue [
            a qudt:QuantityValue ;
            qudt:value 65.0 ;
            qudt:unit qudt:DEG_C
        ]
    ] ;
    lbo-meas:hasUnit qudt:DEG_C ;
    lbo-meas:hasUncertainty [
        a lbo-meas:MeasurementUncertainty ;
        lbo-meas:uncertaintyValue 1.5 ;
        lbo-meas:uncertaintyUnit qudt:DEG_C ;
        lbo-meas:uncertaintyType lbo-meas:ExpandedUncertainty ;
        lbo-meas:coverageFactor 2.0 ;
        lbo-meas:confidenceLevel 0.95
    ] ;
    lbo-meas:hasStatus lbo-meas:Valid .

# 观测产生结果
llc:Temp_Observation_001
    lbo-meas:produces llc:Temp_Result_001 .
```

### 12.2 使用 lbo-meas:Quantity 表达量值（v0.4 新增）

```turtle
# 使用从 Foundation 迁移的 Quantity 类表达量值
llc:Temp_Quantity
    a lbo-meas:Quantity ;
    lbo-meas:hasNumericValue 65.0 ;
    lbo-meas:hasUnit qudt:DEG_C ;
    lbo-meas:hasQuantityKind qudt:ThermodynamicTemperature .

# 在 MeasurementResult 中引用
llc:Temp_Result_002
    a lbo-meas:MeasurementResult ;
    lbo-meas:hasValue [
        a lbo-meas:ScalarValue ;
        lbo-meas:scalarValue [
            a qudt:QuantityValue ;
            qudt:value 65.0 ;
            qudt:unit qudt:DEG_C
        ]
    ] ;
    lbo-meas:hasUnit qudt:DEG_C .
```

### 12.3 与 Requirement 的对齐

```turtle
# Requirement（来自 Requirement Ontology）
lreq:REQ_Temp_001
    a lreq:Requirement ;
    lreq:hasRequirementIdentifier "REQ-TEMP-001" ;
    lreq:hasRequirementName "户外灯具工作温度要求" ;
    lreq:hasTargetElement [
        a lreq:CharacteristicTarget ;
        lreq:targetCharacteristic lbo-core:OperatingTemperature
    ] .

# Measurement Target 与 Requirement Target 概念对齐
# lbo-meas:Target_OperatingTemp 与 lreq:CharacteristicTarget 指向同一特性
```

### 12.4 与 Constraint 和 Verification 的接口

```turtle
# 测量结果作为 ConstraintEvaluation 的输入（在 Core 中定义）
llc:ConstraintEvaluation_Temp
    a lbo-core:ConstraintEvaluation ;
    lbo-core:hasInput llc:Temp_Result_001 ;
    lbo-core:evaluates lcon:Constraint_OutdoorTemp ;
    lbo-core:hasResult lbo-core:PASS .

# 测量结果作为 VerificationAssessment 的证据（在 Core 中定义）
llc:VerificationAssessment_Temp
    a lbo-core:VerificationAssessment ;
    lbo-core:hasEvidence llc:Temp_Result_001 ;
    lbo-core:verifies lspec:SpecItem_Temperature ;
    lbo-core:hasResult lbo-core:PASS .
```


## 13. 核心类汇总

### 13.1 Classes（v0.4 更新）

| 类名 | 父类 | 说明 |
|---|---|---|
| `lbo-meas:ObservableEntity` | llb:Entity | 可观测实体 |
| **`lbo-meas:Quantity`** | **llb:Entity** | **量值抽象（v0.4 新增，从 Foundation 迁移）** |
| `lbo-meas:MeasurableTarget` | llb:Concept | 可测量目标 |
| `lbo-meas:CharacteristicTarget` | MeasurableTarget | 特性目标 |
| `lbo-meas:FunctionTarget` | MeasurableTarget | 功能目标 |
| `lbo-meas:InterfaceTarget` | MeasurableTarget | 接口目标 |
| `lbo-meas:RelationshipTarget` | MeasurableTarget | 关系目标 |
| `lbo-meas:MeasurementQuantity` | llb:Concept | 测量量定义（概念） |
| `lbo-meas:MeasurementObservation` | llb:Event | 测量观测活动 |
| `lbo-meas:MeasurementResult` | llb:Statement | 测量结果 |
| `lbo-meas:MeasurementValue` | llb:Concept | 测量值抽象 |
| `lbo-meas:ScalarValue` | MeasurementValue | 标量值 |
| `lbo-meas:IntervalValue` | MeasurementValue | 区间值 |
| `lbo-meas:RangeValue` | MeasurementValue | 范围值 |
| `lbo-meas:DistributionValue` | MeasurementValue | 分布值 |
| `lbo-meas:StatisticalValue` | MeasurementValue | 统计值 |
| `lbo-meas:MeasurementUncertainty` | llb:Concept | 测量不确定度 |
| `lbo-meas:MeasurementStatus` | — | 测量状态 |
| `lbo-meas:MeasurementMethodApplication` | llb:Statement | 测量方法应用 |
| `lbo-meas:MeasurementCapability` | llb:Statement | 可测性关系 |

### 13.2 Object Properties（v0.4 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lbo-meas:hasSubject` | MeasurementObservation | ObservableEntity | 被测量实体 |
| `lbo-meas:observes` | MeasurementObservation | **MeasurableTarget** | 被测量目标 |
| `lbo-meas:hasContext` | MeasurementObservation | `lbo-core:EvaluationContext` | 测量条件 |
| `lbo-meas:usesMethod` | MeasurementObservation | MeasurementMethodApplication | 测量方法 |
| `lbo-meas:produces` | MeasurementObservation | MeasurementResult | 产生的结果 |
| `lbo-meas:hasValue` | MeasurementResult | MeasurementValue | 测量值 |
| `lbo-meas:hasUnit` | MeasurementResult | `qudt:Unit` | 单位 |
| `lbo-meas:hasUncertainty` | MeasurementResult | MeasurementUncertainty | 不确定度 |
| `lbo-meas:hasStatus` | MeasurementResult | MeasurementStatus | 测量状态 |
| `lbo-meas:hasNumericValue` | **`lbo-meas:Quantity`** | **xsd:double** | **量值数值（v0.4 新增）** |
| `lbo-meas:hasUnit` | **`lbo-meas:Quantity`** | **qudt:Unit** | **量值单位（v0.4 新增）** |
| `lbo-meas:hasQuantityKind` | **`lbo-meas:Quantity`** | **qudt:QuantityKind** | **量值量纲（v0.4 新增）** |
| `lbo-meas:measurementSubject` | MeasurementCapability | **MeasurableTarget** | 可测量目标 |
| `lbo-meas:measurementQuantity` | MeasurementCapability | MeasurementQuantity | 测量量 |
| `lbo-meas:isInputOf` | MeasurementResult | `lbo-core:Assessment` | 作为评估输入 |
| `lbo-meas:isEvidenceFor` | MeasurementResult | `lbo-core:VerificationAssessment` | 作为验证证据 |


## 14. 冻结声明

### 14.1 冻结范围

v0.4 确认后，以下内容进入**冻结状态**：

- ✅ 核心模型（Observation + Result + Value + Uncertainty + Status）
- ✅ **`lbo-meas:Quantity` 类（v0.4 新增，从 Foundation 迁移）**
- ✅ **MeasurableTarget 类型体系**（CharacteristicTarget、FunctionTarget、InterfaceTarget、RelationshipTarget）
- ✅ 与 Core Ontology 的接口（ObservableEntity、EvaluationContext）
- ✅ **与 Foundation Vocabulary 的接口（v0.4 新增）**
- ✅ **与 Requirement Ontology 的接口（MeasurableTarget ↔ SemanticTarget 对齐）**
- ✅ **与 Constraint 的接口（MeasurementResult 作为评估输入）**
- ✅ **与 Verification 的接口（MeasurementResult 作为证据）**
- ✅ 与 QUDT 的集成
- ✅ 命名空间 `https://ontology.leleby.org/measurement/`

### 14.2 冻结后允许

- ✅ 新增 MeasurementValue 子类
- ✅ 新增 DistributionType 值
- ✅ 新增 StatisticalType 值
- ✅ 新增 UncertaintyType 值
- ✅ 新增 MeasurementStatus 值
- ✅ **新增 MeasurableTarget 子类（扩展点）**

### 14.3 冻结后禁止

- ❌ **修改核心模型结构**（Observation/Result/Value/Uncertainty/Status/Quantity）
- ❌ **修改与 Core / Foundation / Requirement / Constraint / Verification 的接口**
- ❌ **重新定义单位或量值结构**（必须使用 QUDT）
- ❌ **将 MeasurableTarget 回退为仅支持 Characteristic**
- ❌ **将 Quantity 移回 Foundation Vocabulary**（量值语义由 Measurement Ontology 全权负责）


## 15. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v0.1 | 2026-07-31 | 初始版本 |
| v0.2 | 2026-07-31 | 细化候选版：命名空间调整为 `lbo-meas:`；新增 MeasurementStatus、IntervalValue；增强 MeasurementUncertainty；重构 MeasurementMethodApplication；新增 Constraint 接口 |
| v0.3 | 2026-08-04 | 语义目标对齐版：`observes` 从 Characteristic 升级为 MeasurableTarget；新增 MeasurableTarget 抽象类及 4 个子类；与 lreq:SemanticTarget 概念对齐；调整 Constraint/Verification 接口 |
| **v0.4** | **2026-08-04** | **Foundation 对齐版**：1）接收从 Foundation Vocabulary v1.1 迁移的 `llb:Quantity` 类，在 Measurement Ontology 中定义为 `lbo-meas:Quantity`；2）接收 `llb:hasNumericValue`、`llb:hasUnit` 属性，在本模块中定义为 `lbo-meas:hasNumericValue`、`lbo-meas:hasUnit`；3）`MeasurementQuantity` 父类从 `llb:Quantity` 改为 `llb:Concept`（因为 `llb:Quantity` 已迁移至本模块）；4）新增 `QuantityShape` SHACL 约束；5）新增 `MeasurementQuantityShape` SHACL 约束；6）更新 QUDT 集成章节，明确与 Foundation 的协作关系；7）新增“与 Foundation Vocabulary 的边界”章节；8）新增与 Foundation Vocabulary 的接口章节；9）更新依赖模块版本 |


*— leleby Measurement Ontology Specification v0.4 — Foundation Alignment Edition —*