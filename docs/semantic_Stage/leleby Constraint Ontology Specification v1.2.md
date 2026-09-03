# leleby Constraint Ontology Specification v1.2

**文档版本：** v1.2 — Semantic Target Enhancement Release（语义目标增强版）

**文档类型：** 模块规范（Module Ontology Specification）

**文档状态：** ✅ **核心冻结（Core Frozen）** — 约束核心模型已冻结，仅允许在指定扩展点进行模块内部扩展。

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.1

**依赖模块：**
- `llb` Foundation Vocabulary Specification v1.0
- `lbo-core` Core Ontology Specification v1.1（提供 `Characteristic`、`ObligationLevel`）
- `lbo-meas` Measurement Ontology Specification（待定，引用其 `MeasurementResult`）
- `lprod` Product Ontology Specification v0.4（引用其 `ProductRelationship`）
- `lcap` Capability Ontology Specification（引用其 `Function`）

**命名空间：** `https://ontology.leleby.org/constraint/`

**推荐前缀：** `lcon`

**目标受众：** 本体架构师、推理引擎开发者、合规工程师、AI Agent 开发者


## 目录

1. 引言
   1.1 目的
   1.2 核心定位
   1.3 v1.2 与 v1.1 的核心差异
   1.4 设计原则
   1.5 与其他模块的关系
   1.6 v1.2 修订说明（新增）
2. 命名空间声明
3. 核心概念模型
   3.1 约束顶层模型（v1.2 更新）
   3.2 约束目标体系（v1.2 新增）
   3.3 约束类型体系
   3.4 约束评估模型
4. 类规范
   4.1 Constraint（v1.2 增强）
   4.2 ConstraintTarget（v1.2 新增）
   4.3 CharacteristicTarget（v1.2 新增）
   4.4 FunctionTarget（v1.2 新增）
   4.5 InterfaceTarget（v1.2 新增）
   4.6 RelationshipTarget（v1.2 新增）
   4.7 StructureTarget（v1.2 新增）
   4.8 ProcessTarget（v1.2 新增）
   4.9 ConstraintExpression
   4.10 ComparisonExpression
   4.11 LogicalExpression
   4.12 AtomicConstraint
   4.13 ValueConstraint
   4.14 RangeConstraint
   4.15 ToleranceConstraint
   4.16 EnumerationConstraint
   4.17 LogicalConstraint
   4.18 AndConstraint
   4.19 OrConstraint
   4.20 NotConstraint
   4.21 ConditionalConstraint
   4.22 DependencyConstraint
   4.23 StatisticalConstraint
   4.24 TemporalConstraint
5. 对象属性
   5.1 约束目标属性（v1.2 更新）
   5.2 约束结构与组成属性
   5.3 值与范围属性
   5.4 逻辑与条件属性
   5.5 评估与验证属性
6. 数据属性
7. 约束评估模型
8. 推理规则
   8.1 范围包含规则
   8.2 公差判断规则
   8.3 枚举匹配规则
   8.4 逻辑组合规则
   8.5 条件满足规则
   8.6 统计约束规则
   8.7 关系约束规则（v1.2 新增）
9. SHACL 验证约束（v1.2 更新）
10. 与 QUDT 的集成
11. 与其他模块的接口（v1.2 更新）
    11.1 与 Core Ontology 的接口
    11.2 与 Requirement Ontology 的接口
    11.3 与 Specification Framework Ontology 的接口（v1.2 更新）
    11.4 与 Product Ontology 的接口（v1.2 新增）
    11.5 与 Measurement Ontology 的接口
    11.6 与 Standard Ontology 的接口
    11.7 接口总图
12. 完整示例（v1.2 更新）
13. 核心类汇总
14. 冻结声明
15. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Constraint Ontology 是 leleby 语义基础设施中**约束表达与评估**的核心模块。它定义了用于描述对象、规格、测量结果、要求之间符合关系的限制条件、判断规则和逻辑表达模型。

本规范是 leleby Constraint Ontology 的正式冻结版本 v1.2。

### 1.2 核心定位

> **Constraint 是 leleby 语义基础设施的“判断引擎”。它连接 Requirement（要求）、Specification（规格）、Measurement（测量）和 Standard（标准），使 AI 能够判断一个事实是否满足一个要求。**

**核心表述：**

```
Constraint =
    Constrains（约束什么工程语义目标）
  + Expression（如何表达约束）
  + Priority（强制程度）
```

> **Constraint 不是 Requirement 的子概念。Requirement 通过 `lbo-core:hasConstraint` 引用 Constraint。Constraint 独立存在于语义层，被多个模块共享和复用。**

**Constraint 作为 Rule/Concept 的定位（v1.1 确认）：**

> Constraint 是**可计算的规则/概念**，而非普通陈述。因此 Constraint 继承自 `llb:Concept`（或 `llb:Rule`），而非 `llb:Statement`。这反映了它在推理系统中的角色——它是被评估的对象，而非事实性陈述。

### 1.3 v1.2 与 v1.1 的核心差异

| 问题 | v1.1 状态 | v1.2 修正 |
|---|---|---|
| 约束目标 | `appliesTo` → `lbo-core:Characteristic` | **扩展为 `constrains` → `ConstraintTarget`，支持特性/功能/接口/关系/结构/过程** |
| 目标体系 | 仅有 Characteristic | **新增 `ConstraintTarget` 抽象类及 6 个子类** |
| 与 Product Ontology 接口 | 无 | **新增 `RelationshipTarget` 指向 `lprod:ProductRelationship`** |
| 结构约束支持 | 不支持 | **新增结构约束示例（PartRelationship cardinality）** |
| 向后兼容性 | N/A | **保留 `appliesTo` 作为 `constrains` 的子属性** |
| SHACL 约束 | 要求 `appliesTo` | **更新为支持 `constrains` 或 `appliesTo`** |

### 1.4 设计原则

**原则一：约束独立原则**

`Constraint` 不是 `Requirement` 的附属概念。它是独立的一等对象，可被 Requirement、Specification、Standard、Verification 等多个模块引用。

**原则二：约束可计算原则**

所有 Constraint 必须支持机器可执行的评估（Evaluation）。Constraint 的语义必须能被规则引擎解析，产生明确的结果（PASS / FAIL / UNKNOWN）。

**原则三：约束是 Concept，不是 Statement**

Constraint 是**可计算的规则/条件**，而非事实性陈述。它继承自 `llb:Concept`，反映其在推理系统中的角色。

**原则四：约束与值分离原则**

Constraint 不是值。`RangeConstraint` 不是“温度 ≤ 70℃”这个值，而是“温度必须满足 ≤ 70℃ 这个条件”的规则。值属于 `MeasurementResult`，条件属于 `Constraint`。

**原则五：约束目标通用化原则（v1.2 新增）**

Constraint 可以约束任何工程语义元素，包括特性（Characteristic）、功能（Function）、接口（Interface）、结构关系（Structure）、产品关系（Relationship）和过程要素（Process），而不仅限于物理参数。

**原则六：继承与复用原则**

约束可在不同上下文中复用。例如，`RangeConstraint(-40, 70)` 可同时被 IEC 标准要求和产品规格引用。

**原则七：表达式可执行原则**

`ConstraintExpression` 必须支持机器可执行的形式，能够被规则引擎直接解析和评估。

### 1.5 与其他模块的关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Constraint Ontology 在架构中的位置                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Core Ontology（lbo-core v1.1）                  │   │
│  │              Characteristic / ObligationLevel                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │ 引用                                   │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Constraint Ontology（lcon）—— 本模块            │   │
│  │              Constraint / RangeConstraint / LogicalConstraint       │   │
│  │              ToleranceConstraint / StatisticalConstraint            │   │
│  │              ConstraintTarget / CharacteristicTarget /              │   │
│  │              RelationshipTarget / FunctionTarget / ...              │   │
│  │              ComparisonExpression / LogicalExpression               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                    ┌───────────────┼───────────────┐                    │
│                    │               │               │                    │
│                    ▼               ▼               ▼                    │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │
│  │  Requirement        │  │  Specification  │  │  Product            │   │
│  │  Ontology           │  │  Framework      │  │  Ontology           │   │
│  │  （要求引用约束）    │  │  （规格引用约束） │  │  （关系被约束）      │   │
│  └─────────────────────┘  └─────────────────┘  └─────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Measurement Ontology                            │   │
│  │                    （测量值被约束评估）                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**关键依赖：**

- `lbo-core:Characteristic`：约束适用的特性（来自 Core v1.1）
- `lbo-core:ObligationLevel`：约束的强制程度（来自 Core v1.1）
- `lprod:ProductRelationship`：产品关系（来自 Product Ontology v0.4）
- `lcap:Function`：功能（来自 Capability Ontology）
- `lbo-meas:MeasurementResult`：被评估的测量值

### 1.6 v1.2 修订说明（新增）

v1.2 在 v1.1 的基础上，针对约束目标的语义范围进行了增强：

1. **引入 `ConstraintTarget` 抽象类**：作为约束目标的统一基类。
2. **新增目标子类**：`CharacteristicTarget`、`FunctionTarget`、`InterfaceTarget`、`RelationshipTarget`、`StructureTarget`、`ProcessTarget`。
3. **扩展 `Constraint`**：将 `appliesTo`（指向 Characteristic）扩展为更通用的 `constrains`，支持指向任何 `ConstraintTarget`。
4. **保留向后兼容**：`appliesTo` 作为 `constrains` 的子属性继续保留。
5. **新增与 Product Ontology 的接口**：明确 `RelationshipTarget` 可指向 `lprod:ProductRelationship`，支持结构约束（如“4个工作轮胎”）。
6. **新增结构约束推理规则**：规则 10 支持关系属性约束。
7. **更新示例**：展示特性、功能、接口、关系等不同类型目标的约束。


## 2. 命名空间声明

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix llb: <https://ontology.leleby.org/foundation/> .
@prefix lbo-core: <https://ontology.leleby.org/core/> .
@prefix lbo-meas: <https://ontology.leleby.org/measurement/> .
@prefix lprod: <https://ontology.leleby.org/product/> .
@prefix lcap: <https://ontology.leleby.org/capability/> .
@prefix lcon: <https://ontology.leleby.org/constraint/> .

<https://ontology.leleby.org/constraint/>
    rdf:type owl:Ontology ;
    owl:versionInfo "1.2" ;
    owl:imports <https://ontology.leleby.org/foundation/> ;
    owl:imports <https://ontology.leleby.org/core/> ;
    rdfs:label "leleby Constraint Ontology" ;
    rdfs:comment "leleby 约束表达与评估模型，定义约束的语义结构、类型体系和评估机制" .
```


## 3. 核心概念模型

### 3.1 约束顶层模型（v1.2 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Constraint 核心结构（v1.2）                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Constraint（约束）                              │   │
│  │  对工程语义目标的限制条件                                          │   │
│  │  继承自 llb:Concept（可计算规则/概念）                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                    ┌───────────────┼───────────────┐                    │
│                    │               │               │                    │
│                    ▼               ▼               ▼                    │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │
│  │   constrains        │  │  hasExpression   │  │  hasPriority        │   │
│  │   （约束目标）       │  │  （约束表达式）    │  │  （强制程度）        │   │
│  └─────────────────────┘  └─────────────────┘  └─────────────────────┘   │
│          │                                                                  │
│          ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ConstraintTarget（约束目标）                     │   │
│  │  （v1.2 新增——统一入口）                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│          │                                                                  │
│          ├── CharacteristicTarget（特性）——指向 lbo-core:Characteristic    │
│          ├── FunctionTarget（功能）——指向 lcap:Function                    │
│          ├── InterfaceTarget（接口）——指向 lprod:Interface                 │
│          ├── RelationshipTarget（关系）——指向 lprod:ProductRelationship    │
│          ├── StructureTarget（结构）——指向 lprod:Structure                 │
│          └── ProcessTarget（过程）——指向 lprod:Process                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 约束目标体系（v1.2 新增）

```
llb:Concept（来自 Foundation Vocabulary）
    │
    └── lcon:ConstraintTarget（约束目标抽象）
            │
            ├── lcon:CharacteristicTarget
            │       └── targetCharacteristic → lbo-core:Characteristic
            │
            ├── lcon:FunctionTarget
            │       └── targetFunction → lcap:Function
            │
            ├── lcon:InterfaceTarget
            │       └── targetInterface → lprod:Interface
            │
            ├── lcon:RelationshipTarget
            │       └── targetRelationship → lprod:ProductRelationship
            │
            ├── lcon:StructureTarget
            │       └── targetStructure → lprod:Structure
            │
            └── lcon:ProcessTarget
                    └── targetProcess → lprod:Process
```

### 3.3 约束类型体系（v1.1 保留）

```
llb:Concept（来自 Foundation Vocabulary）
    │
    └── lcon:Constraint（约束抽象）
            │
            ├── lcon:AtomicConstraint（原子约束）
            │       ├── lcon:ValueConstraint（值约束）
            │       ├── lcon:RangeConstraint（范围约束）
            │       ├── lcon:ToleranceConstraint（公差约束）
            │       ├── lcon:EnumerationConstraint（枚举约束）
            │       ├── lcon:StatisticalConstraint（统计约束）
            │       └── lcon:TemporalConstraint（时间约束）
            │
            ├── lcon:LogicalConstraint（逻辑约束）
            │       ├── lcon:AndConstraint（与约束）
            │       ├── lcon:OrConstraint（或约束）
            │       └── lcon:NotConstraint（非约束）
            │
            └── lcon:ConditionalConstraint（条件约束）
                    ├── lcon:DependencyConstraint（依赖约束）
                    └── lcon:ImplicationConstraint（蕴含约束）

llb:Concept（来自 Foundation Vocabulary）
    │
    └── lcon:ConstraintExpression（约束表达式）
            ├── lcon:ComparisonExpression（比较表达式）
            │       ├── hasOperator: ComparisonOperator
            │       ├── hasLeftOperand: ConstraintExpression
            │       └── hasRightOperand: ConstraintExpression
            └── lcon:LogicalExpression（逻辑表达式）
                    ├── hasOperator: LogicalOperator
                    └── hasOperands: ConstraintExpression[]
```

### 3.4 约束评估模型（v1.1 保留）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    约束评估模型（v1.1）                                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Input: MeasurementResult / SpecificationValue /                   │   │
│  │         RelationshipInstance / StructureInstance                   │   │
│  │  （输入：测量值 / 规格值 / 关系实例 / 结构实例）                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Evaluation Engine（评估引擎）                                    │   │
│  │  - 解析 ConstraintExpression（ComparisonExpression /               │   │
│  │    LogicalExpression）                                             │   │
│  │  - 获取 Constraint 约束的目标（ConstraintTarget）                  │   │
│  │  - 比较输入值与约束条件                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Output: EvaluationResult（评估结果）                              │   │
│  │  - PASS / FAIL / UNKNOWN                                          │   │
│  │  - 证据链                                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 4. 类规范

### 4.1 Constraint（v1.2 增强）

```turtle
lcon:Constraint
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "Constraint" ;
    rdfs:comment "对工程语义目标的限制条件，描述允许值空间或允许状态。约束是可计算、可评估的独立语义对象。继承自 llb:Concept（而非 Statement），体现约束的规则/概念属性" .
```

**属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lcon:constraintId` | 约束唯一标识符 | 0..1 |
| `lcon:constraintName` | 约束名称 | 1 |
| `lcon:constraintDescription` | 约束描述 | 0..1 |
| `lcon:constraintVersion` | 版本号 | 0..1 |

**关系（v1.2 增强）：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:constrains` | lcon:Constraint | **`lcon:ConstraintTarget`** | **约束目标（v1.2 新增，统一入口）** | 1 |
| `lcon:appliesTo` | lcon:Constraint | `lbo-core:Characteristic` | **适用的特性（v1.2 保留，作为 constrains 的子属性，向后兼容）** | 0..1 |
| `lcon:hasExpression` | lcon:Constraint | `lcon:ConstraintExpression` | 约束表达式 | 1 |
| `lcon:hasPriority` | lcon:Constraint | `lbo-core:ObligationLevel` | 强制程度（来自 Core） | 0..1 |

### 4.2 ConstraintTarget（v1.2 新增）

```turtle
lcon:ConstraintTarget
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "ConstraintTarget" ;
    rdfs:comment "约束目标的抽象基类，表示约束作用于哪个工程语义元素" .
```

### 4.3 CharacteristicTarget（v1.2 新增）

```turtle
lcon:CharacteristicTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:ConstraintTarget ;
    rdfs:label "CharacteristicTarget" ;
    rdfs:comment "特性类约束目标，指向 lbo-core:Characteristic" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:targetCharacteristic` | lcon:CharacteristicTarget | `lbo-core:Characteristic` | 目标特性 | 1 |

### 4.4 FunctionTarget（v1.2 新增）

```turtle
lcon:FunctionTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:ConstraintTarget ;
    rdfs:label "FunctionTarget" ;
    rdfs:comment "功能类约束目标，指向产品功能或能力" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:targetFunction` | lcon:FunctionTarget | `lcap:Function` / `lprod:ProductFeature` | 目标功能 | 1 |

### 4.5 InterfaceTarget（v1.2 新增）

```turtle
lcon:InterfaceTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:ConstraintTarget ;
    rdfs:label "InterfaceTarget" ;
    rdfs:comment "接口类约束目标，指向产品接口" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:targetInterface` | lcon:InterfaceTarget | `lprod:Interface` | 目标接口 | 1 |

### 4.6 RelationshipTarget（v1.2 新增）

```turtle
lcon:RelationshipTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:ConstraintTarget ;
    rdfs:label "RelationshipTarget" ;
    rdfs:comment "关系类约束目标，指向产品关系（如 PartRelationship）" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:targetRelationship` | lcon:RelationshipTarget | **`lprod:ProductRelationship`** | **目标产品关系（v1.2 新增）** | 1 |

**用途示例：** 约束 `PartRelationship` 的 `cardinality`、`connectionType`、`importanceLevel`、`partRole` 等属性。

### 4.7 StructureTarget（v1.2 新增）

```turtle
lcon:StructureTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:ConstraintTarget ;
    rdfs:label "StructureTarget" ;
    rdfs:comment "结构类约束目标，指向产品的结构元素" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:targetStructure` | lcon:StructureTarget | `lprod:Structure` | 目标结构 | 1 |

### 4.8 ProcessTarget（v1.2 新增）

```turtle
lcon:ProcessTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:ConstraintTarget ;
    rdfs:label "ProcessTarget" ;
    rdfs:comment "过程类约束目标，指向生产过程或操作" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:targetProcess` | lcon:ProcessTarget | `lprod:Process` | 目标过程 | 1 |

### 4.9 ConstraintExpression

```turtle
lcon:ConstraintExpression
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "ConstraintExpression" ;
    rdfs:comment "约束的可计算表达形式，是约束评估的输入。作为抽象基类，由 ComparisonExpression 和 LogicalExpression 具体实现" .
```

### 4.10 ComparisonExpression

```turtle
lcon:ComparisonExpression
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:ConstraintExpression ;
    rdfs:label "ComparisonExpression" ;
    rdfs:comment "比较表达式：比较两个操作数，产生布尔结果" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:hasOperator` | lcon:ComparisonExpression | lcon:ComparisonOperator | 比较操作符 | 1 |
| `lcon:hasLeftOperand` | lcon:ComparisonExpression | lcon:ConstraintExpression | 左操作数 | 1 |
| `lcon:hasRightOperand` | lcon:ComparisonExpression | lcon:ConstraintExpression | 右操作数 | 1 |

**ComparisonOperator 枚举：**

| 值 | 说明 | 示例 |
|---|---|---|
| `lcon:Equals` | 等于 | `x = 5` |
| `lcon:NotEquals` | 不等于 | `x ≠ 5` |
| `lcon:GreaterThan` | 大于 | `x > 5` |
| `lcon:GreaterThanOrEqual` | 大于等于 | `x ≥ 5` |
| `lcon:LessThan` | 小于 | `x < 5` |
| `lcon:LessThanOrEqual` | 小于等于 | `x ≤ 5` |
| `lcon:Contains` | 包含 | `x ∈ {a, b, c}` |
| `lcon:MatchesPattern` | 模式匹配 | `x matches ".*\.pdf"` |

### 4.11 LogicalExpression

```turtle
lcon:LogicalExpression
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:ConstraintExpression ;
    rdfs:label "LogicalExpression" ;
    rdfs:comment "逻辑表达式：组合多个子表达式" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:hasOperator` | lcon:LogicalExpression | lcon:LogicalOperator | 逻辑操作符 | 1 |
| `lcon:hasOperands` | lcon:LogicalExpression | lcon:ConstraintExpression | 操作数列表 | 2..* |

**LogicalOperator 枚举：**

| 值 | 说明 |
|---|---|
| `lcon:AND` | 与（所有子表达式必须为真） |
| `lcon:OR` | 或（至少一个子表达式为真） |
| `lcon:NOT` | 非（子表达式必须为假） |

### 4.12 AtomicConstraint

```turtle
lcon:AtomicConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:Constraint ;
    rdfs:label "AtomicConstraint" ;
    rdfs:comment "原子约束，不可再分的基本约束" .
```

### 4.13 ValueConstraint

```turtle
lcon:ValueConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:AtomicConstraint ;
    rdfs:label "ValueConstraint" ;
    rdfs:comment "固定值约束：属性值必须等于指定值" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:expectedValue` | lcon:ValueConstraint | `lbo-meas:QuantityValue` | 期望值 | 1 |

### 4.14 RangeConstraint

```turtle
lcon:RangeConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:AtomicConstraint ;
    rdfs:label "RangeConstraint" ;
    rdfs:comment "范围约束：属性值必须在指定范围内" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:minValue` | lcon:RangeConstraint | `lbo-meas:QuantityValue` | 最小值 | 0..1 |
| `lcon:maxValue` | lcon:RangeConstraint | `lbo-meas:QuantityValue` | 最大值 | 0..1 |
| `lcon:minInclusive` | lcon:RangeConstraint | xsd:boolean | 是否包含最小值（默认 true） | 0..1 |
| `lcon:maxInclusive` | lcon:RangeConstraint | xsd:boolean | 是否包含最大值（默认 true） | 0..1 |

**约束：** 至少有一个 `minValue` 或 `maxValue`。

**示例：** `-40℃ ≤ T ≤ 70℃`

### 4.15 ToleranceConstraint

```turtle
lcon:ToleranceConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:AtomicConstraint ;
    rdfs:label "ToleranceConstraint" ;
    rdfs:comment "公差约束：标称值 ± 公差" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:nominalValue` | lcon:ToleranceConstraint | `lbo-meas:QuantityValue` | 标称值 | 1 |
| `lcon:tolerancePositive` | lcon:ToleranceConstraint | `lbo-meas:QuantityValue` | 正公差 | 0..1 |
| `lcon:toleranceNegative` | lcon:ToleranceConstraint | `lbo-meas:QuantityValue` | 负公差 | 0..1 |
| `lcon:symmetricTolerance` | lcon:ToleranceConstraint | `lbo-meas:QuantityValue` | 对称公差（快捷方式） | 0..1 |

**约束：** 至少有一个 `tolerancePositive` + `toleranceNegative` 或 `symmetricTolerance`。

**示例：** `15.00 ± 0.02 mm`

### 4.16 EnumerationConstraint

```turtle
lcon:EnumerationConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:AtomicConstraint ;
    rdfs:label "EnumerationConstraint" ;
    rdfs:comment "枚举约束：属性值必须在预定义列表中" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:allowedValues` | lcon:EnumerationConstraint | rdfs:Literal | 允许值列表 | 1..* |

**示例：** `IP65`, `IP66`, `IP67`

### 4.17 LogicalConstraint

```turtle
lcon:LogicalConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:Constraint ;
    rdfs:label "LogicalConstraint" ;
    rdfs:comment "逻辑约束：多个约束的逻辑组合" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:operands` | lcon:LogicalConstraint | lcon:Constraint | 操作数列表 | 2..* |

### 4.18 AndConstraint

```turtle
lcon:AndConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:LogicalConstraint ;
    rdfs:label "AndConstraint" ;
    rdfs:comment "与约束：所有子约束必须同时满足" .
```

**示例：** `Temperature ≥ -20℃ AND Humidity ≤ 90%`

### 4.19 OrConstraint

```turtle
lcon:OrConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:LogicalConstraint ;
    rdfs:label "OrConstraint" ;
    rdfs:comment "或约束：至少一个子约束满足" .
```

### 4.20 NotConstraint

```turtle
lcon:NotConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:LogicalConstraint ;
    rdfs:label "NotConstraint" ;
    rdfs:comment "非约束：子约束必须不满足" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:operand` | lcon:NotConstraint | lcon:Constraint | 操作数 | 1 |

### 4.21 ConditionalConstraint

```turtle
lcon:ConditionalConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:Constraint ;
    rdfs:label "ConditionalConstraint" ;
    rdfs:comment "条件约束：IF condition THEN constraint" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:condition` | lcon:ConditionalConstraint | lcon:Constraint | 触发条件 | 1 |
| `lcon:thenConstraint` | lcon:ConditionalConstraint | lcon:Constraint | 条件满足时的约束 | 1 |
| `lcon:elseConstraint` | lcon:ConditionalConstraint | lcon:Constraint | 条件不满足时的约束 | 0..1 |

**示例：** `IF altitude > 3000m THEN temperature_range = [-10℃, 50℃]`

### 4.22 DependencyConstraint

```turtle
lcon:DependencyConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:ConditionalConstraint ;
    rdfs:label "DependencyConstraint" ;
    rdfs:comment "依赖约束：一个约束的满足依赖于另一个约束" .
```

### 4.23 StatisticalConstraint

```turtle
lcon:StatisticalConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:AtomicConstraint ;
    rdfs:label "StatisticalConstraint" ;
    rdfs:comment "统计约束：可靠性/寿命等统计量约束" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:statisticalQuantity` | lcon:StatisticalConstraint | xsd:string | 统计量类型（MTBF/L10/L70） | 1 |
| `lcon:targetValue` | lcon:StatisticalConstraint | `lbo-meas:QuantityValue` | 目标值 | 1 |
| `lcon:confidenceLevel` | lcon:StatisticalConstraint | xsd:double | 置信度（0-1） | 0..1 |
| `lcon:testDuration` | lcon:StatisticalConstraint | `lbo-meas:QuantityValue` | 测试持续时间 | 0..1 |

**示例：** `L70 ≥ 50000h @ 90% 置信度`

### 4.24 TemporalConstraint

```turtle
lcon:TemporalConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf lcon:AtomicConstraint ;
    rdfs:label "TemporalConstraint" ;
    rdfs:comment "时间约束：时间相关约束" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:temporalOperator` | lcon:TemporalConstraint | lcon:TemporalOperator | 时间操作符 | 1 |
| `lcon:temporalValue` | lcon:TemporalConstraint | `lbo-meas:QuantityValue` / xsd:date | 时间值 | 1 |

**TemporalOperator 枚举：**

| 值 | 说明 |
|---|---|
| `lcon:Before` | 在...之前 |
| `lcon:After` | 在...之后 |
| `lcon:During` | 在...期间 |
| `lcon:DurationGreaterThan` | 持续时间大于 |
| `lcon:DurationLessThan` | 持续时间小于 |
| `lcon:EffectiveFrom` | 从...开始生效 |
| `lcon:EffectiveUntil` | 直到...生效 |


## 5. 对象属性

### 5.1 约束目标属性（v1.2 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lcon:constrains` | lcon:Constraint | **`lcon:ConstraintTarget`** | **约束目标（v1.2 新增，统一入口）** |
| `lcon:appliesTo` | lcon:Constraint | `lbo-core:Characteristic` | 适用的特性（v1.2 保留，作为 constrains 的子属性，向后兼容） |
| `lcon:targetCharacteristic` | lcon:CharacteristicTarget | `lbo-core:Characteristic` | 目标特性 |
| `lcon:targetFunction` | lcon:FunctionTarget | `lcap:Function` | 目标功能 |
| `lcon:targetInterface` | lcon:InterfaceTarget | `lprod:Interface` | 目标接口 |
| `lcon:targetRelationship` | lcon:RelationshipTarget | `lprod:ProductRelationship` | 目标产品关系 |
| `lcon:targetStructure` | lcon:StructureTarget | `lprod:Structure` | 目标结构 |
| `lcon:targetProcess` | lcon:ProcessTarget | `lprod:Process` | 目标过程 |

### 5.2 约束结构与组成属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lcon:hasExpression` | lcon:Constraint | `lcon:ConstraintExpression` | 约束表达式 |
| `lcon:hasPriority` | lcon:Constraint | `lbo-core:ObligationLevel` | 强制程度 |

### 5.3 值与范围属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lcon:expectedValue` | lcon:ValueConstraint | `lbo-meas:QuantityValue` | 期望值 |
| `lcon:minValue` | lcon:RangeConstraint | `lbo-meas:QuantityValue` | 最小值 |
| `lcon:maxValue` | lcon:RangeConstraint | `lbo-meas:QuantityValue` | 最大值 |
| `lcon:nominalValue` | lcon:ToleranceConstraint | `lbo-meas:QuantityValue` | 标称值 |
| `lcon:tolerancePositive` | lcon:ToleranceConstraint | `lbo-meas:QuantityValue` | 正公差 |
| `lcon:toleranceNegative` | lcon:ToleranceConstraint | `lbo-meas:QuantityValue` | 负公差 |
| `lcon:symmetricTolerance` | lcon:ToleranceConstraint | `lbo-meas:QuantityValue` | 对称公差 |
| `lcon:allowedValues` | lcon:EnumerationConstraint | rdfs:Literal | 允许值 |
| `lcon:statisticalQuantity` | lcon:StatisticalConstraint | xsd:string | 统计量类型 |
| `lcon:targetValue` | lcon:StatisticalConstraint | `lbo-meas:QuantityValue` | 目标值 |
| `lcon:confidenceLevel` | lcon:StatisticalConstraint | xsd:double | 置信度 |

### 5.4 逻辑与条件属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lcon:operands` | lcon:LogicalConstraint | lcon:Constraint | 操作数列表 |
| `lcon:operand` | lcon:NotConstraint | lcon:Constraint | 操作数 |
| `lcon:condition` | lcon:ConditionalConstraint | lcon:Constraint | 触发条件 |
| `lcon:thenConstraint` | lcon:ConditionalConstraint | lcon:Constraint | 条件满足时的约束 |
| `lcon:elseConstraint` | lcon:ConditionalConstraint | lcon:Constraint | 条件不满足时的约束 |
| `lcon:hasOperator` | lcon:ComparisonExpression / lcon:LogicalExpression | lcon:ComparisonOperator / lcon:LogicalOperator | 操作符 |
| `lcon:hasLeftOperand` | lcon:ComparisonExpression | lcon:ConstraintExpression | 左操作数 |
| `lcon:hasRightOperand` | lcon:ComparisonExpression | lcon:ConstraintExpression | 右操作数 |
| `lcon:hasOperands` | lcon:LogicalExpression | lcon:ConstraintExpression | 操作数列表 |

### 5.5 评估与验证属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lcon:evaluates` | lcon:ConstraintEvaluation | lcon:Constraint | 评估的约束 |
| `lcon:hasEvaluationResult` | lcon:ConstraintEvaluation | lcon:EvaluationResult | 评估结果 |
| `lcon:subjectValue` | lcon:ConstraintEvaluation | `lbo-meas:MeasurementResult` | 被评估的值 |
| `lcon:subjectRelationship` | lcon:ConstraintEvaluation | `lprod:ProductRelationship` | **被评估的关系（v1.2 新增）** |
| `lcon:subjectTarget` | lcon:ConstraintEvaluation | `lcon:ConstraintTarget` | **被评估的目标（v1.2 新增）** |


## 6. 数据属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lcon:constraintId` | lcon:Constraint | xsd:string | 约束标识符 |
| `lcon:constraintName` | lcon:Constraint | xsd:string | 约束名称 |
| `lcon:constraintVersion` | lcon:Constraint | xsd:string | 版本号 |
| `lcon:minInclusive` | lcon:RangeConstraint | xsd:boolean | 是否包含最小值 |
| `lcon:maxInclusive` | lcon:RangeConstraint | xsd:boolean | 是否包含最大值 |
| `lcon:confidenceLevel` | lcon:StatisticalConstraint | xsd:double | 置信度 |
| `lcon:statisticalQuantity` | lcon:StatisticalConstraint | xsd:string | 统计量类型 |


## 7. 约束评估模型

### 7.1 评估执行架构

| 层次 | 技术 | 职责 |
|---|---|---|
| **约束语义** | Constraint Ontology | 定义约束“是什么” |
| **约束验证** | SHACL | 验证数据结构完整性 |
| **约束评估** | 规则引擎 | 执行约束评估计算（解析 ComparisonExpression / LogicalExpression） |
| **决策推理** | 决策引擎 | 多因素综合判断 |

### 7.2 评估结果模型

```turtle
lcon:ConstraintEvaluation
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Assessment ;
    rdfs:label "ConstraintEvaluation" ;
    rdfs:comment "约束评估活动及其结果。继承自 lbo-core:Assessment" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lcon:evaluates` | lcon:ConstraintEvaluation | lcon:Constraint | 评估的约束 | 1 |
| `lcon:subjectValue` | lcon:ConstraintEvaluation | `lbo-meas:MeasurementResult` | 被评估的值 | 0..1 |
| `lcon:subjectRelationship` | lcon:ConstraintEvaluation | `lprod:ProductRelationship` | 被评估的关系（v1.2 新增） | 0..1 |
| `lcon:subjectTarget` | lcon:ConstraintEvaluation | `lcon:ConstraintTarget` | 被评估的目标（v1.2 新增） | 0..1 |
| `lcon:hasEvaluationResult` | lcon:ConstraintEvaluation | lcon:EvaluationResult | 评估结果 | 1 |
| `lcon:evidence` | lcon:ConstraintEvaluation | llb:Document | 证据引用 | 0..1 |

**EvaluationResult 枚举：**

| 值 | 说明 |
|---|---|
| `lcon:PASS` | 通过 |
| `lcon:FAIL` | 不通过 |
| `lcon:UNKNOWN` | 未评估/无法判定 |

> **注意：** `EvaluationResult`（PASS/FAIL/UNKNOWN）与 `ComplianceStatus`（COMPLIANT/NON_COMPLIANT/PARTIAL）是两个不同层级的概念。前者属于 Constraint Ontology，用于单个约束的评估；后者属于 Core Ontology（`lbo-core:ComplianceAssessment`），用于整体合规判断。


## 8. 推理规则

### 8.1 范围包含规则

**规则1：值在范围内则通过**

```
IF MeasurementResult V hasValue x
AND Constraint C is RangeConstraint with min ≤ x ≤ max
AND C constrains CharacteristicTarget targeting the same characteristic as V
THEN C evaluates PASS on V
```

**规则2：区间包含则满足**

```
IF RangeConstraint C_req requires value in [a, b]
AND Specification has range [c, d]
AND [a, b] ⊆ [c, d]
THEN Specification satisfies C_req
```

### 8.2 公差判断规则

**规则3：公差满足规则**

```
IF ToleranceConstraint T has nominal n, tolerance ±t
AND MeasurementResult V has value x
AND n - t ≤ x ≤ n + t
THEN T evaluates PASS on V
```

### 8.3 枚举匹配规则

**规则4：枚举匹配规则**

```
IF EnumerationConstraint E has allowedValues [v1, v2, ...]
AND MeasurementResult V has value x
AND x IN [v1, v2, ...]
THEN E evaluates PASS on V
```

### 8.4 逻辑组合规则

**规则5：AND 组合规则**

```
IF AndConstraint A has operands [C1, C2, ...]
AND all Ci evaluate PASS
THEN A evaluates PASS
```

**规则6：OR 组合规则**

```
IF OrConstraint O has operands [C1, C2, ...]
AND any Ci evaluates PASS
THEN O evaluates PASS
```

**规则7：NOT 组合规则**

```
IF NotConstraint N has operand C
AND C evaluates FAIL
THEN N evaluates PASS
```

### 8.5 条件满足规则

**规则8：条件约束规则**

```
IF ConditionalConstraint CC has condition Cc and thenConstraint Ct
AND Cc evaluates PASS
THEN Ct must evaluate PASS
```

### 8.6 统计约束规则

**规则9：统计约束规则**

```
IF StatisticalConstraint S has target T, confidence Cf
AND TestResult shows value V with confidence Cv
AND V ≥ T AND Cv ≥ Cf
THEN S evaluates PASS
```

### 8.7 关系约束规则（v1.2 新增）

**规则10：关系属性约束规则**

```
IF PartRelationship R has property P (e.g., cardinality = 4, role = WorkingPart)
AND Constraint C constrains RelationshipTarget targeting R's relationship type
AND C hasExpression requiring specific property value
AND R's property matches the requirement
THEN C evaluates PASS on R
```

**规则10a：关系数量约束**

```
IF Vehicle V hasPartRelationship R of type WorkingWheelInstallation
AND R hasCardinality 4
AND Constraint C requires cardinality = 4 for WorkingWheelInstallation
THEN C evaluates PASS on V
```

**规则10b：关系角色约束**

```
IF PartRelationship R hasPartRole lprod:WorkingPart
AND Constraint C requires role = WorkingPart
THEN C evaluates PASS on R
```


## 9. SHACL 验证约束（v1.2 更新）

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix lcon: <https://ontology.leleby.org/constraint/> .

# Constraint 必须有 constrains 或 appliesTo，以及 hasExpression
lcon:ConstraintShape
    a sh:NodeShape ;
    sh:targetClass lcon:Constraint ;
    sh:or (
        [
            sh:property [
                sh:path lcon:constrains ;
                sh:minCount 1 ;
                sh:message "Constraint must specify a constraint target via constrains"
            ]
        ]
        [
            sh:property [
                sh:path lcon:appliesTo ;
                sh:minCount 1 ;
                sh:message "Constraint must specify a characteristic via appliesTo (deprecated but supported)"
            ]
        ]
    ) ;
    sh:property [
        sh:path lcon:hasExpression ;
        sh:minCount 1 ;
        sh:message "Constraint must have an expression"
    ] .

# RangeConstraint 必须有 min 或 max
lcon:RangeConstraintShape
    a sh:NodeShape ;
    sh:targetClass lcon:RangeConstraint ;
    sh:or (
        [ sh:path lcon:minValue ; sh:minCount 1 ]
        [ sh:path lcon:maxValue ; sh:minCount 1 ]
    ) ;
    sh:message "RangeConstraint must have at least one of minValue or maxValue" .

# ToleranceConstraint 必须有 nominal 和至少一个公差
lcon:ToleranceConstraintShape
    a sh:NodeShape ;
    sh:targetClass lcon:ToleranceConstraint ;
    sh:property [
        sh:path lcon:nominalValue ;
        sh:minCount 1 ;
        sh:message "ToleranceConstraint must have a nominal value"
    ] ;
    sh:or (
        [ sh:path lcon:symmetricTolerance ; sh:minCount 1 ]
        [ sh:and (
            [ sh:path lcon:tolerancePositive ; sh:minCount 1 ]
            [ sh:path lcon:toleranceNegative ; sh:minCount 1 ]
        ) ]
    ) ;
    sh:message "ToleranceConstraint must have tolerance specification" .

# LogicalConstraint 必须有至少两个 operands
lcon:LogicalConstraintShape
    a sh:NodeShape ;
    sh:targetClass lcon:LogicalConstraint ;
    sh:property [
        sh:path lcon:operands ;
        sh:minCount 2 ;
        sh:message "LogicalConstraint must have at least two operands"
    ] .

# ConditionalConstraint 必须有 condition 和 thenConstraint
lcon:ConditionalConstraintShape
    a sh:NodeShape ;
    sh:targetClass lcon:ConditionalConstraint ;
    sh:property [
        sh:path lcon:condition ;
        sh:minCount 1 ;
        sh:message "ConditionalConstraint must have a condition"
    ] ;
    sh:property [
        sh:path lcon:thenConstraint ;
        sh:minCount 1 ;
        sh:message "ConditionalConstraint must have a thenConstraint"
    ] .

# ComparisonExpression 必须有 operator 和两个 operands
lcon:ComparisonExpressionShape
    a sh:NodeShape ;
    sh:targetClass lcon:ComparisonExpression ;
    sh:property [
        sh:path lcon:hasOperator ;
        sh:minCount 1 ;
        sh:message "ComparisonExpression must have an operator"
    ] ;
    sh:property [
        sh:path lcon:hasLeftOperand ;
        sh:minCount 1 ;
        sh:message "ComparisonExpression must have a left operand"
    ] ;
    sh:property [
        sh:path lcon:hasRightOperand ;
        sh:minCount 1 ;
        sh:message "ComparisonExpression must have a right operand"
    ] .

# ConstraintTarget 约束（v1.2 新增）
lcon:ConstraintTargetShape
    a sh:NodeShape ;
    sh:targetClass lcon:ConstraintTarget ;
    sh:closed false ;
    sh:message "ConstraintTarget can be specialized to specific target types" .

# CharacteristicTarget 必须有 targetCharacteristic
lcon:CharacteristicTargetShape
    a sh:NodeShape ;
    sh:targetClass lcon:CharacteristicTarget ;
    sh:property [
        sh:path lcon:targetCharacteristic ;
        sh:minCount 1 ;
        sh:message "CharacteristicTarget must have a target characteristic"
    ] .

# RelationshipTarget 必须有 targetRelationship
lcon:RelationshipTargetShape
    a sh:NodeShape ;
    sh:targetClass lcon:RelationshipTarget ;
    sh:property [
        sh:path lcon:targetRelationship ;
        sh:minCount 1 ;
        sh:message "RelationshipTarget must have a target relationship"
    ] .

# ConstraintEvaluation 必须有 evaluates、subject 和 result
lcon:ConstraintEvaluationShape
    a sh:NodeShape ;
    sh:targetClass lcon:ConstraintEvaluation ;
    sh:property [
        sh:path lcon:evaluates ;
        sh:minCount 1 ;
        sh:message "ConstraintEvaluation must specify the constraint"
    ] ;
    sh:or (
        [
            sh:property [
                sh:path lcon:subjectValue ;
                sh:minCount 1 ;
                sh:message "ConstraintEvaluation must have a subject value"
            ]
        ]
        [
            sh:property [
                sh:path lcon:subjectRelationship ;
                sh:minCount 1 ;
                sh:message "ConstraintEvaluation must have a subject relationship"
            ]
        ]
        [
            sh:property [
                sh:path lcon:subjectTarget ;
                sh:minCount 1 ;
                sh:message "ConstraintEvaluation must have a subject target"
            ]
        ]
    ) ;
    sh:property [
        sh:path lcon:hasEvaluationResult ;
        sh:minCount 1 ;
        sh:message "ConstraintEvaluation must have an evaluation result"
    ] .
```


## 10. 与 QUDT 的集成

| QUDT 概念 | leleby Constraint 使用方式 |
|---|---|
| `qudt:QuantityValue` | 作为 `RangeConstraint.minValue` / `maxValue` / `nominalValue` 等的值类型 |
| `qudt:Unit` | 量值的单位 |
| `qudt:Dimension` | 量值的量纲（通过 `constrains` 的 ConstraintTarget 间接关联） |

**集成约束：**

> Constraint 不重新定义量值结构。所有数值表达引用 `lbo-meas:QuantityValue`（对齐 QUDT）。


## 11. 与其他模块的接口（v1.2 更新）

### 11.1 与 Core Ontology 的接口

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lcon:constrains` | lcon:Constraint | `lcon:ConstraintTarget` | v1.2 新增，统一入口 |
| `lcon:appliesTo` | lcon:Constraint | `lbo-core:Characteristic` | v1.2 保留，向后兼容 |
| `lcon:hasPriority` | lcon:Constraint | `lbo-core:ObligationLevel` | 来自 Core v1.1 |

### 11.2 与 Requirement Ontology 的接口

```turtle
# Requirement 引用 Constraint（在 Core Ontology 中定义）
lbo-core:hasConstraint
    rdf:type owl:ObjectProperty ;
    rdfs:domain lbo-core:Requirement ;
    rdfs:range lcon:Constraint .
```

### 11.3 与 Specification Framework Ontology 的接口（v1.2 更新）

```turtle
# SpecificationItem 引用 Constraint（在 Specification Framework 中定义）
lspec:hasConstraint
    rdf:type owl:ObjectProperty ;
    rdfs:domain lspec:SpecificationItem ;
    rdfs:range lcon:Constraint .

# Constraint 评估 Specification（v1.2 新增方向）
lcon:constrainsSpecification
    rdf:type owl:ObjectProperty ;
    rdfs:domain lcon:Constraint ;
    rdfs:range lspec:SpecificationItem ;
    rdfs:label "constrainsSpecification" ;
    rdfs:comment "约束评估某个规格项" .
```

### 11.4 与 Product Ontology 的接口（v1.2 新增）

```turtle
# RelationshipTarget 指向 ProductRelationship
lcon:targetRelationship
    rdf:type owl:ObjectProperty ;
    rdfs:domain lcon:RelationshipTarget ;
    rdfs:range lprod:ProductRelationship ;
    rdfs:label "targetRelationship" ;
    rdfs:comment "约束目标指向的产品关系" .

# ConstraintEvaluation 评估 ProductRelationship
lcon:subjectRelationship
    rdf:type owl:ObjectProperty ;
    rdfs:domain lcon:ConstraintEvaluation ;
    rdfs:range lprod:ProductRelationship ;
    rdfs:label "subjectRelationship" ;
    rdfs:comment "被评估的产品关系" .
```

### 11.5 与 Measurement Ontology 的接口

```turtle
# Measurement 被 Constraint 评估
lcon:subjectValue
    rdf:type owl:ObjectProperty ;
    rdfs:domain lcon:ConstraintEvaluation ;
    rdfs:range lbo-meas:MeasurementResult .
```

### 11.6 与 Standard Ontology 的接口

Standard 不直接引用 Constraint。标准通过 `RequirementBinding` 引用要求，要求引用 Constraint：

```
Standard
    │
    └── StandardClause
            │
            └── definesBinding → RequirementBinding
                    │
                    └── referencesRequirement → lbo-core:Requirement
                            │
                            └── lbo-core:hasConstraint → lcon:Constraint
```

### 11.7 接口总图（v1.2 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Constraint Ontology 与其他模块的接口（v1.2）             │
│                                                                             │
│  lbo-core: Core Ontology v1.1                                               │
│  ├── Characteristic（被 lcon:CharacteristicTarget 引用）                   │
│  └── ObligationLevel（被 lcon:hasPriority 引用）                           │
│         │                                                                  │
│         │  被引用                                                          │
│         ▼                                                                  │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║                       Constraint Ontology (lcon:)                    ║ │
│  ║  Constraint (subClassOf llb:Concept)                                 ║ │
│  ║  ConstraintTarget (CharacteristicTarget / FunctionTarget /           ║ │
│  ║    RelationshipTarget / InterfaceTarget / StructureTarget /          ║ │
│  ║    ProcessTarget)                                                    ║ │
│  ║  ConstraintExpression (ComparisonExpression / LogicalExpression)     ║ │
│  ║  RangeConstraint / ToleranceConstraint / ...                        ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│         │                                                                  │
│         │  被引用 / 被评估                                                  │
│         ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  引用方                                                             │   │
│  │  ├── lbo-core:Requirement（通过 lbo-core:hasConstraint）            │   │
│  │  ├── lspec:SpecificationItem（通过 lspec:hasConstraint）            │   │
│  │  ├── lstd:StandardClause（通过 Requirement → Constraint 链路）     │   │
│  │  ├── lbo-meas:MeasurementResult（通过 ConstraintEvaluation）       │   │
│  │  └── lprod:ProductRelationship（通过 RelationshipTarget）  ←v1.2新增│   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 12. 完整示例（v1.2 更新）

### 12.1 温度范围约束（使用 ComparisonExpression）

**要求：** 户外灯具工作温度必须在 -40℃ 至 70℃ 之间。

```turtle
# 约束目标
lcon:Target_OperatingTemp
    a lcon:CharacteristicTarget ;
    lcon:targetCharacteristic lbo-core:OperatingTemperature .

# 使用 ComparisonExpression 表达范围
lcon:Expression_Temp_GE_Neg40
    a lcon:ComparisonExpression ;
    lcon:hasOperator lcon:GreaterThanOrEqual ;
    lcon:hasLeftOperand [
        a lcon:VariableExpression ;
        lcon:variableName "temperature" ;
        lcon:referencesCharacteristic lbo-core:OperatingTemperature
    ] ;
    lcon:hasRightOperand [
        a lcon:ConstantExpression ;
        lcon:constantValue [
            llb:hasNumericValue "-40"^^xsd:double ;
            llb:hasUnit llb:DegreeCelsius
        ]
    ] .

lcon:Expression_Temp_LE_70
    a lcon:ComparisonExpression ;
    lcon:hasOperator lcon:LessThanOrEqual ;
    lcon:hasLeftOperand lcon:Variable_Temp ;
    lcon:hasRightOperand [
        a lcon:ConstantExpression ;
        lcon:constantValue [
            llb:hasNumericValue "70"^^xsd:double ;
            llb:hasUnit llb:DegreeCelsius
        ]
    ] .

lcon:Expression_Temp_AND
    a lcon:LogicalExpression ;
    lcon:hasOperator lcon:AND ;
    lcon:hasOperands (
        lcon:Expression_Temp_GE_Neg40
        lcon:Expression_Temp_LE_70
    ) .

# 范围约束（使用 LogicalExpression 组合比较表达式）
lcon:Constraint_OutdoorTemp
    a lcon:RangeConstraint ;  # 保留 RangeConstraint 作为快捷方式
    lcon:constraintName "户外灯具工作温度范围" ;
    lcon:constrains lcon:Target_OperatingTemp ;  # v1.2: 使用 constrains
    lcon:minValue [
        a lbo-meas:QuantityValue ;
        llb:hasNumericValue "-40"^^xsd:double ;
        llb:hasUnit llb:DegreeCelsius
    ] ;
    lcon:maxValue [
        a lbo-meas:QuantityValue ;
        llb:hasNumericValue "70"^^xsd:double ;
        llb:hasUnit llb:DegreeCelsius
    ] .

# Requirement 引用约束
lreq:REQ_IEC_001
    a lbo-core:Requirement ;
    lreq:hasRequirementIdentifier "REQ-IEC-001" ;
    lreq:hasRequirementName "IEC 60598 户外灯具工作温度要求" ;
    lbo-core:hasConstraint lcon:Constraint_OutdoorTemp ;
    lbo-core:hasObligation lbo-core:Mandatory .
```

### 12.2 功能约束（v1.2 新增）

**要求：** 电机必须具备过载保护功能。

```turtle
# 约束目标：功能
lcon:Target_OverloadProtection
    a lcon:FunctionTarget ;
    lcon:targetFunction lprod:OverloadProtectionFeature .

# 功能存在性约束
lcon:Constraint_OverloadProtection
    a lcon:ValueConstraint ;
    lcon:constraintName "过载保护功能要求" ;
    lcon:constrains lcon:Target_OverloadProtection ;
    lcon:expectedValue [
        a lbo-meas:QuantityValue ;
        llb:hasNumericValue "true"^^xsd:boolean
    ] .
```

### 12.3 结构约束：车辆轮胎（v1.2 新增）

**要求：** 汽车必须具有4个工作轮胎。

```turtle
# PartRelationship 实例（在 Product Ontology 中定义）
lprod:Vehicle_Wheel_Installation
    a lprod:PartRelationship ;
    lprod:subjectProduct lprod:Vehicle ;
    lprod:part lprod:Wheel ;
    lprod:partRole lprod:WorkingPart ;
    lprod:cardinality 4 ;
    lprod:connectionType lprod:Bolted .

# 约束目标：PartRelationship
lcon:Target_WorkingWheel
    a lcon:RelationshipTarget ;
    lcon:targetRelationship lprod:PartRelationship ;
    lcon:targetRelationshipType lprod:WorkingPart .

# 数量约束
lcon:Constraint_WorkingWheel_Count
    a lcon:ValueConstraint ;
    lcon:constraintName "工作轮胎数量要求" ;
    lcon:constrains lcon:Target_WorkingWheel ;
    lcon:expectedValue [
        a lbo-meas:QuantityValue ;
        llb:hasNumericValue "4"^^xsd:integer ;
        llb:hasUnit llb:Each
    ] .

# 角色约束
lcon:Constraint_WorkingWheel_Role
    a lcon:EnumerationConstraint ;
    lcon:constraintName "工作轮胎角色要求" ;
    lcon:constrains lcon:Target_WorkingWheel ;
    lcon:allowedValues ( lprod:WorkingPart ) .
```

### 12.4 公差约束

**规格：** 电机轴径 15.0 ± 0.02 mm。

```turtle
lcon:Target_ShaftDiameter
    a lcon:CharacteristicTarget ;
    lcon:targetCharacteristic lbo-core:Diameter .

lcon:Constraint_ShaftDiameter
    a lcon:ToleranceConstraint ;
    lcon:constraintName "电机轴径公差" ;
    lcon:constrains lcon:Target_ShaftDiameter ;
    lcon:nominalValue [
        a lbo-meas:QuantityValue ;
        llb:hasNumericValue "15.0"^^xsd:double ;
        llb:hasUnit llb:Millimetre
    ] ;
    lcon:symmetricTolerance [
        a lbo-meas:QuantityValue ;
        llb:hasNumericValue "0.02"^^xsd:double ;
        llb:hasUnit llb:Millimetre
    ] .
```

### 12.5 逻辑约束

**要求：** 设备在温度低于 -20℃ 或高于 60℃ 时不得工作。

```turtle
lcon:Target_OperatingTemp
    a lcon:CharacteristicTarget ;
    lcon:targetCharacteristic lbo-core:OperatingTemperature .

lcon:Constraint_LowTemp
    a lcon:RangeConstraint ;
    lcon:constrains lcon:Target_OperatingTemp ;
    lcon:maxValue [
        llb:hasNumericValue "-20"^^xsd:double ;
        llb:hasUnit llb:DegreeCelsius
    ] .

lcon:Constraint_HighTemp
    a lcon:RangeConstraint ;
    lcon:constrains lcon:Target_OperatingTemp ;
    lcon:minValue [
        llb:hasNumericValue "60"^^xsd:double ;
        llb:hasUnit llb:DegreeCelsius
    ] .

lcon:Constraint_TempOr
    a lcon:OrConstraint ;
    lcon:constrains lcon:Target_OperatingTemp ;
    lcon:operands (
        lcon:Constraint_LowTemp
        lcon:Constraint_HighTemp
    ) .
```

### 12.6 条件约束

**要求：** 当海拔超过 3000m 时，工作温度范围调整为 -10℃ 至 50℃。

```turtle
lcon:Target_Altitude
    a lcon:CharacteristicTarget ;
    lcon:targetCharacteristic lbo-core:Altitude .

lcon:Target_OperatingTemp
    a lcon:CharacteristicTarget ;
    lcon:targetCharacteristic lbo-core:OperatingTemperature .

lcon:Constraint_AltitudeCondition
    a lcon:RangeConstraint ;
    lcon:constrains lcon:Target_Altitude ;
    lcon:minValue [
        llb:hasNumericValue "3000"^^xsd:double ;
        llb:hasUnit llb:Metre
    ] .

lcon:Constraint_HighAltitudeTemp
    a lcon:RangeConstraint ;
    lcon:constrains lcon:Target_OperatingTemp ;
    lcon:minValue [
        llb:hasNumericValue "-10"^^xsd:double ;
        llb:hasUnit llb:DegreeCelsius
    ] ;
    lcon:maxValue [
        llb:hasNumericValue "50"^^xsd:double ;
        llb:hasUnit llb:DegreeCelsius
    ] .

lcon:Constraint_TempAltitudeDependency
    a lcon:DependencyConstraint ;
    lcon:condition lcon:Constraint_AltitudeCondition ;
    lcon:thenConstraint lcon:Constraint_HighAltitudeTemp .
```

### 12.7 约束评估示例

```turtle
# 测量结果
llc:Measured_Temp_001
    a lbo-meas:MeasurementResult ;
    lbo-meas:hasValue 65.0 ;
    lbo-meas:hasUnit llb:DegreeCelsius .

# 约束评估
llc:Temp_Evaluation_001
    a lcon:ConstraintEvaluation ;
    lcon:evaluates lcon:Constraint_OutdoorTemp ;
    lcon:subjectValue llc:Measured_Temp_001 ;
    lcon:hasEvaluationResult lcon:FAIL .

# 结构关系评估（v1.2 新增）
lprod:Vehicle_Wheel_Evaluation
    a lcon:ConstraintEvaluation ;
    lcon:evaluates lcon:Constraint_WorkingWheel_Count ;
    lcon:subjectRelationship lprod:Vehicle_Wheel_Installation ;
    lcon:hasEvaluationResult lcon:PASS .
```


## 13. 核心类汇总

### 13.1 Classes

| 类名 | 父类 | 说明 |
|---|---|---|
| `lcon:Constraint` | llb:Concept | 约束抽象 |
| `lcon:ConstraintTarget` | llb:Concept | **约束目标抽象（v1.2 新增）** |
| `lcon:CharacteristicTarget` | lcon:ConstraintTarget | **特性目标（v1.2 新增）** |
| `lcon:FunctionTarget` | lcon:ConstraintTarget | **功能目标（v1.2 新增）** |
| `lcon:InterfaceTarget` | lcon:ConstraintTarget | **接口目标（v1.2 新增）** |
| `lcon:RelationshipTarget` | lcon:ConstraintTarget | **关系目标（v1.2 新增）** |
| `lcon:StructureTarget` | lcon:ConstraintTarget | **结构目标（v1.2 新增）** |
| `lcon:ProcessTarget` | lcon:ConstraintTarget | **过程目标（v1.2 新增）** |
| `lcon:ConstraintExpression` | llb:Concept | 约束表达式 |
| `lcon:ComparisonExpression` | lcon:ConstraintExpression | 比较表达式 |
| `lcon:LogicalExpression` | lcon:ConstraintExpression | 逻辑表达式 |
| `lcon:AtomicConstraint` | lcon:Constraint | 原子约束 |
| `lcon:ValueConstraint` | lcon:AtomicConstraint | 值约束 |
| `lcon:RangeConstraint` | lcon:AtomicConstraint | 范围约束 |
| `lcon:ToleranceConstraint` | lcon:AtomicConstraint | 公差约束 |
| `lcon:EnumerationConstraint` | lcon:AtomicConstraint | 枚举约束 |
| `lcon:StatisticalConstraint` | lcon:AtomicConstraint | 统计约束 |
| `lcon:TemporalConstraint` | lcon:AtomicConstraint | 时间约束 |
| `lcon:LogicalConstraint` | lcon:Constraint | 逻辑约束 |
| `lcon:AndConstraint` | lcon:LogicalConstraint | 与约束 |
| `lcon:OrConstraint` | lcon:LogicalConstraint | 或约束 |
| `lcon:NotConstraint` | lcon:LogicalConstraint | 非约束 |
| `lcon:ConditionalConstraint` | lcon:Constraint | 条件约束 |
| `lcon:DependencyConstraint` | lcon:ConditionalConstraint | 依赖约束 |
| `lcon:ConstraintEvaluation` | lbo-core:Assessment | 约束评估 |

### 13.2 Object Properties（v1.2 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lcon:constrains` | lcon:Constraint | `lcon:ConstraintTarget` | **约束目标（v1.2 新增）** |
| `lcon:appliesTo` | lcon:Constraint | `lbo-core:Characteristic` | 适用的特性（v1.2 保留，向后兼容） |
| `lcon:hasExpression` | lcon:Constraint | `lcon:ConstraintExpression` | 约束表达式 |
| `lcon:hasPriority` | lcon:Constraint | `lbo-core:ObligationLevel` | 强制程度 |
| `lcon:targetCharacteristic` | lcon:CharacteristicTarget | `lbo-core:Characteristic` | 目标特性 |
| `lcon:targetFunction` | lcon:FunctionTarget | `lcap:Function` | 目标功能 |
| `lcon:targetInterface` | lcon:InterfaceTarget | `lprod:Interface` | 目标接口 |
| `lcon:targetRelationship` | lcon:RelationshipTarget | `lprod:ProductRelationship` | 目标产品关系 |
| `lcon:hasOperator` | lcon:ComparisonExpression / lcon:LogicalExpression | lcon:ComparisonOperator / lcon:LogicalOperator | 操作符 |
| `lcon:hasLeftOperand` | lcon:ComparisonExpression | lcon:ConstraintExpression | 左操作数 |
| `lcon:hasRightOperand` | lcon:ComparisonExpression | lcon:ConstraintExpression | 右操作数 |
| `lcon:hasOperands` | lcon:LogicalExpression | lcon:ConstraintExpression | 操作数列表 |
| `lcon:operands` | lcon:LogicalConstraint | lcon:Constraint | 操作数列表 |
| `lcon:condition` | lcon:ConditionalConstraint | lcon:Constraint | 触发条件 |
| `lcon:thenConstraint` | lcon:ConditionalConstraint | lcon:Constraint | 条件满足时的约束 |
| `lcon:evaluates` | lcon:ConstraintEvaluation | lcon:Constraint | 评估的约束 |
| `lcon:hasEvaluationResult` | lcon:ConstraintEvaluation | lcon:EvaluationResult | 评估结果 |
| `lcon:subjectRelationship` | lcon:ConstraintEvaluation | `lprod:ProductRelationship` | **被评估的关系（v1.2 新增）** |
| `lcon:subjectTarget` | lcon:ConstraintEvaluation | `lcon:ConstraintTarget` | **被评估的目标（v1.2 新增）** |


## 14. 冻结声明

### 14.1 冻结范围

v1.2 确认后，以下内容进入**核心冻结状态**：

- ✅ 约束类型体系（Atomic、Logical、Conditional）
- ✅ 所有核心类（Constraint、RangeConstraint、ToleranceConstraint、LogicalConstraint 等）
- ✅ **所有核心对象属性（包括 v1.2 新增的 `constrains` 和 `ConstraintTarget` 体系）**
- ✅ 与 Core Ontology / Requirement / Specification / Measurement / Product 的接口
- ✅ 核心推理规则
- ✅ 命名空间 `https://ontology.leleby.org/constraint/`
- ✅ Constraint 继承自 `llb:Concept`
- ✅ ComparisonExpression 和 LogicalExpression 结构

### 14.2 扩展点（Reserved Extension Points）

以下内容允许在 v1.2 基础上进行模块内部扩展，无需变更核心冻结模型：

- ✅ **新增 ConstraintTarget 子类（扩展点）**
- ✅ 新增约束类型
- ✅ 新增 TemporalOperator 值
- ✅ 新增推理规则
- ✅ 新增 Expression 子类

### 14.3 冻结后禁止

- ❌ **修改或删除任何现有核心类**
- ❌ **修改或删除任何现有核心属性**
- ❌ **改变与 Requirement / Specification / Measurement / Standard / Product 的核心接口**
- ❌ **在 Constraint Ontology 中定义要求或规格相关概念**
- ❌ **将 Constraint 改回继承 llb:Statement**
- ❌ **将 ConstraintTarget 回退为仅支持 Characteristic**


## 15. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v1.0 | 2026-07-31 | 正式冻结版 |
| v1.1 | 2026-07-31 | 跨模块一致性版：Constraint 继承改为 `llb:Concept`；新增 ComparisonExpression 和 LogicalExpression；`appliesTo` 指向 `lbo-core:Characteristic`；EvaluationResult 改为 PASS/FAIL/UNKNOWN |
| **v1.2** | **2026-08-04** | **语义目标增强版**：1）引入 `ConstraintTarget` 抽象类，作为约束目标的统一基类；2）新增 `CharacteristicTarget`、`FunctionTarget`、`InterfaceTarget`、`RelationshipTarget`、`StructureTarget`、`ProcessTarget` 六个子类；3）`Constraint` 增加 `constrains` 属性，支持指向任何 `ConstraintTarget`；4）`appliesTo` 作为 `constrains` 的子属性保留，确保向后兼容；5）新增与 Product Ontology v0.4 的接口，`RelationshipTarget` 可指向 `lprod:ProductRelationship`；6）新增结构约束示例（车辆轮胎数量）；7）新增关系约束推理规则（规则 10、10a、10b）；8）更新 SHACL 约束；9）更新冻结声明，明确扩展点 |


*— leleby Constraint Ontology Specification v1.2 — Semantic Target Enhancement Release —*