# leleby Foundation Vocabulary Specification v1.1

**文档版本：** v1.1 — Refinement Release（精炼版）

**文档类型：** 模块规范（Module Specification）

**文档状态：** ✅ **正式冻结（Frozen）** — 基础词汇层已冻结，仅允许后向兼容的扩展

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.2

**依赖模块：** 无（本模块是 leleby 所有语义模块的底层基础，不依赖任何其他模块）

**命名空间：** `https://ontology.leleby.org/foundation/`

**推荐前缀：** `llb`

**目标受众：** 本体架构师、领域本体设计师、企业数据架构师、AI Agent 开发者


## 目录

1. 引言
   1.1 目的
   1.2 v1.1 核心定位
   1.3 设计原则
   1.4 与其他模块的关系

2. 命名空间声明

3. 核心类定义
   3.1 Entity（语义对象）
   3.2 Concept（概念）
   3.3 Agent（行为主体）
   3.4 Identifier（标识符）
   3.5 Version（版本）
   3.6 Document（文档）
   3.7 Event（事件）
   3.8 Statement（声明）
   3.9 Time（时间）
   3.10 Location（位置）
   3.11 IdentifiableEntity（可标识实体）

4. 核心属性与关系
   4.1 标识与版本属性
   4.2 时间与空间属性
   4.3 文档与声明属性
   4.4 版本演进属性

5. 与上层 Ontology 的接口

6. SHACL 验证约束

7. 冻结声明
   7.1 冻结范围
   7.2 冻结后允许
   7.3 冻结后禁止

8. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Foundation Vocabulary 是 leleby 语义基础设施的**最底层基础模块**。它定义了所有上层 Ontology 所依赖的**纯元概念（Pure Meta-Concept）**——即最基本的语义构件，用于构建更复杂的工业领域概念。

**本模块的核心职责：**

- 提供所有语义表达所需的基础元概念
- 定义跨所有模块共享的通用属性与关系
- **不包含任何工业领域语义（如 Product、Motor、Specification 等）**
- **不包含任何 BFO 式物理/对象/过程的 Ontology 分类（如 PhysicalEntity、Object、Process、Continuant、Occurrent）**
- **不包含测量量值（Quantity）**——Quantity 属于 Measurement Ontology
- **不包含测量单位（Unit）**——Unit 属于 Measurement Ontology
- **不包含组织概念（Organization）**——Organization 属于 Organization Ontology

本规范是 leleby Foundation Vocabulary 的正式冻结版本 v1.1。

### 1.2 v1.1 核心定位

> **Foundation Vocabulary 是 leleby 语义基础设施的基础词汇层（Foundation Vocabulary Layer），而不是基础本体层（Foundation Ontology Layer）。**

| 维度 | Foundation Vocabulary | Foundation Ontology（❌ 不存在于 leleby） |
|---|---|---|
| 内容 | 纯元概念（Entity、Concept、Agent、Identifier、Version、Document、Statement） | BFO 式类（PhysicalEntity、Object、Process、Continuant、Occurrent） |
| 职责 | 提供构建语义所需的最基本构件 | 提供世界的分类框架 |
| 是否包含 Ontology 语义 | ❌ 不包含 | ✅ 包含 |

**关键声明：**

> `llb:` 命名空间中的所有类都**不包含任何 Ontology 语义**。它们是最基础的概念构件——类似于编程语言中的原始类型（Primitive Types），而非领域模型中的类（Domain Classes）。

**类比：**

| 编程语言 | leleby Foundation Vocabulary |
|---|---|
| `int`、`string`、`bool` | `Entity`、`Concept`、`Statement` |
| `class User`、`class Order` | `lbo:Product`、`lbo:Organization` |

### 1.3 设计原则

**原则一：纯元概念原则**

`llb:` 中的每个类都应是“概念的概念”——即描述其他概念所需的最基本构件。它们不应携带任何特定领域的语义含义。

**原则二：最小化原则**

Foundation Vocabulary 应尽可能小。只有那些被多个上层 Ontology 共享的最基础概念才应纳入本模块。

**原则三：冻结兼容性原则**

`llb:` 命名空间一旦冻结，**不允许破坏性变更**。新增概念必须保持与现有类的后向兼容。对现有类的语义修改必须经过架构委员会严格评审。

**原则四：不包含物理/对象/过程分类原则**

`llb:` 不包含 `PhysicalEntity`、`Object`、`Process`、`Continuant`、`Occurrent` 等 BFO 式类。这些类属于 `lbo:UpperIndustrialOntology`，而非基础词汇层。

**原则五：不包含领域概念原则**

`llb:` 不包含 `Organization`、`Quantity`、`Unit` 等具有领域色彩的类。这些类属于对应的领域模块。

| 概念 | 归属 |
|---|---|
| `Organization` | `lbo:OrganizationOntology` |
| `Quantity`、`Unit`、`Dimension`、`QuantityKind` | `lbo:MeasurementOntology` |

### 1.4 与其他模块的关系

```
llb: Foundation Vocabulary（本模块）
    │
    │  被继承/扩展
    ▼
lbo: Upper Industrial Ontology
    │
    │  被继承/扩展
    ▼
lbo: Core Ontology
    │
    │  被继承/扩展
    ▼
lbo: Domain Ontology
    │
    │  被实例化
    ▼
lbs: Semantic Package
    │
    │  被实例化
    ▼
llc: Commercial Instance
```

**继承方向：**

- `lbo:` 可继承 `llb:`（如 `lbo:Product rdfs:subClassOf llb:Entity`）
- `llb:` **不可**继承 `lbo:`
- 所有上层模块最终都依赖于 `llb:`


## 2. 命名空间声明

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix llb: <https://ontology.leleby.org/foundation/> .

<https://ontology.leleby.org/foundation/>
    rdf:type owl:Ontology ;
    owl:versionInfo "1.1" ;
    rdfs:label "leleby Foundation Vocabulary" ;
    rdfs:comment "leleby 语义基础设施的基础词汇层，提供所有上层 Ontology 依赖的纯元概念" .
```


## 3. 核心类定义

### 3.1 Entity（语义对象）

语义对象的基础抽象类。用于表示具有独立语义身份的对象。

```turtle
llb:Entity
    rdf:type owl:Class ;
    rdfs:label "Entity" ;
    rdfs:comment "语义对象的基础抽象类。它不是 owl:Thing 的替代，而是 leleby 语义建模中的推荐抽象基类。Entity 代表 leleby 知识模型中任何具有语义可标识性的资源——包括物理实体、抽象概念、信息对象和事件" .
```

**定位声明：**

> `llb:Entity` 不是 `owl:Thing` 的替代。`owl:Thing` 是所有 OWL 个体的内置根类。`llb:Entity` 是 leleby 语义建模中**推荐使用的抽象基类**，用于那些需要表达语义身份的对象。数据类型（如 `xsd:string`、`xsd:integer`）和字面量（Literals）不属于 `llb:Entity`。

**Entity 的跨领域覆盖：**

| 类型 | 示例 |
|---|---|
| 物理实体 | 产品、零件、设备 |
| 抽象概念 | 能力、分类、特征 |
| 信息对象 | 文档、声明、规格 |
| 事件 | 测量活动、生产事件 |

**用途：** 所有上层 Ontology 中的实体类最终都继承自 `llb:Entity`。

**示例：**
- `lbo:Product rdfs:subClassOf llb:Entity`
- `lbo:Measurement rdfs:subClassOf llb:Entity`

### 3.2 Concept（概念）

概念的顶级抽象，用于表达抽象概念。

```turtle
llb:Concept
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "Concept" ;
    rdfs:comment "概念的顶级抽象，用于表达非物理的抽象概念，如能力、分类、特征、类型等" .
```

**用途：** 用于表达能力、分类、特征等抽象概念。

**注意：** `Constraint` 不属于 `llb:Concept`。Constraint 是独立的规范规则实体，在 `lbo-constraint:ConstraintOntology` 中定义。

**示例：**
- `lbo:Capability rdfs:subClassOf llb:Concept`
- `lbo:Classification rdfs:subClassOf llb:Concept`

### 3.3 Agent（行为主体）

有意图的行为主体。

```turtle
llb:Agent
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "Agent" ;
    rdfs:comment "有意图的行为主体，如人、组织、系统、AI Agent" .
```

**用途：** 用于表达具有行为能力的实体。

**示例：**
- `lbo:Person rdfs:subClassOf llb:Agent`
- `lbo:Organization rdfs:subClassOf llb:Agent`（定义在 Organization Ontology 中）

### 3.4 Identifier（标识符）

标识符，用于唯一标识实体。

```turtle
llb:Identifier
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "Identifier" ;
    rdfs:comment "标识符，用于唯一标识实体" .
```

**用途：** 用于为实体分配唯一标识。

**示例：**
- 产品编号：`llb:Identifier`
- 标准编号：`llb:Identifier`

### 3.5 Version（版本）

版本标识，用于表达版本信息。

```turtle
llb:Version
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "Version" ;
    rdfs:comment "版本标识，用于表达版本信息" .
```

**用途：** 用于语义包、标准、规范的版本管理。

### 3.6 Document（文档）

文档的抽象，用于表达承载信息的文件。

```turtle
llb:Document
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "Document" ;
    rdfs:comment "文档的抽象，用于表达承载信息的文件" .
```

**用途：** 用于表达标准文件、报告、证书等。

**示例：**
- `lbo:NormativeDocument rdfs:subClassOf llb:Document`
- `lbo:TestMethod rdfs:subClassOf llb:Document`

### 3.7 Event（事件）

事件的抽象，用于表达发生的事件。

```turtle
llb:Event
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "Event" ;
    rdfs:comment "事件的抽象，用于表达发生的事件" .
```

**用途：** 用于表达测试事件、生产事件等。

**示例：**
- `lbo:Measurement rdfs:subClassOf llb:Event`

### 3.8 Statement（声明）

声明的抽象，用于表达断言、声明、主张等。

```turtle
llb:Statement
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "Statement" ;
    rdfs:comment "声明的抽象，用于表达断言、声明、主张等。它代表信息的表达形式，而不是事实本身。Statement 是一种信息实体，不等同于命题真值" .
```

**用途：** 用于表达需求、规格、符合性声明等。

**示例：**
- `lbo:Requirement rdfs:subClassOf llb:Statement`
- `lbo:Specification rdfs:subClassOf llb:Statement`
- `lbo:ComplianceStatement rdfs:subClassOf llb:Statement`

### 3.9 Time（时间）

时间相关概念。

```turtle
llb:Time
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "Time" ;
    rdfs:comment "时间相关概念，用于表达时间点、时间段等" .
```

**用途：** 用于表达时间点、时间段、时间区间等。

### 3.10 Location（位置）

位置相关概念。

```turtle
llb:Location
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "Location" ;
    rdfs:comment "位置相关概念，用于表达地理区域、坐标、地址等" .
```

**用途：** 用于表达地理区域、坐标、工厂位置、测试地点等。

### 3.11 IdentifiableEntity（可标识实体）

具有标识符的实体。

```turtle
llb:IdentifiableEntity
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Entity ;
    rdfs:label "IdentifiableEntity" ;
    rdfs:comment "具有标识符的实体，适用于需要被唯一标识的实体子集。并非所有 Entity 都需要标识符" .
```

**用途：** 用于表达那些必须有标识符的实体（如产品、文档、标准等），而非所有 Entity 都需要标识符。


## 4. 核心属性与关系

### 4.1 标识与版本属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `llb:hasIdentifier` | `llb:IdentifiableEntity` | `llb:Identifier` | 可标识实体拥有的标识符 |
| `llb:hasVersion` | `llb:Entity` | `llb:Version` | 实体拥有的版本 |
| `llb:versionNumber` | `llb:Version` | `xsd:string` | 版本号（如 "1.0.0"） |
| `llb:releasedAt` | `llb:Version` | `xsd:dateTime` | 版本发布日期 |
| `llb:previousVersion` | `llb:Version` | `llb:Version` | 前一版本 |

### 4.2 时间与空间属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `llb:createdAt` | `llb:Entity` | `xsd:dateTime` | 创建时间 |
| `llb:modifiedAt` | `llb:Entity` | `xsd:dateTime` | 修改时间 |
| `llb:hasTime` | `llb:Entity` | `llb:Time` | 关联的时间 |
| `llb:hasLocation` | `llb:Entity` | `llb:Location` | 关联的位置 |

### 4.3 文档与声明属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `llb:hasDocument` | `llb:Entity` | `llb:Document` | 关联的文档 |
| `llb:hasStatement` | `llb:Entity` | `llb:Statement` | 关联的声明 |
| `llb:hasAgent` | `llb:Entity` | `llb:Agent` | 关联的行为主体 |

### 4.4 版本演进属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `llb:supersedes` | `llb:Entity` | `llb:Entity` | 替代的旧实体 |
| `llb:supersededBy` | `llb:Entity` | `llb:Entity` | 被新实体替代 |


## 5. 与上层 Ontology 的接口

Foundation Vocabulary 为上层 Ontology 提供以下继承接口：

| 上层模块 | 继承自 `llb:` | 说明 |
|---|---|---|
| `lbo:UpperIndustrialOntology` | `llb:Entity` | 工业实体的顶层抽象 |
| `lbo:Product` | `llb:Entity` | 产品继承自 Entity（非 PhysicalEntity） |
| `lbo:Specification` | `llb:Statement` | 规格继承自 Statement |
| `lbo:Requirement` | `llb:Statement` | 需求继承自 Statement |
| `lbo:Capability` | `llb:Concept` | 能力继承自 Concept |
| `lbo:Organization` | `llb:Agent` | 组织继承自 Agent（定义在 Organization Ontology） |
| `lbo:NormativeDocument` | `llb:Document` | 规范文档继承自 Document |
| `lbo:Measurement` | `llb:Event` | 测量继承自 Event |
| `lbo:ComplianceStatement` | `llb:Statement` | 符合性声明继承自 Statement |
| `lbo:QuantityValue` | `llb:Entity` | 量值继承自 Entity（定义在 Measurement Ontology） |
| `lbo:Unit` | `llb:Entity` | 计量单位继承自 Entity（定义在 Measurement Ontology） |

**v1.1 说明：**

> `Quantity` 及相关的量值表达（`hasQuantity`、`hasNumericValue`、`hasUnit`）已从 Foundation Vocabulary 中移除，归属 `lbo:MeasurementOntology`。Foundation 层不再承载任何测量相关的语义定义，保持其“纯元概念”定位。

**关键约束：**

> `llb:` 中的所有类都是**抽象元概念**，不应被直接实例化。它们的作用是为上层 Ontology 提供继承基础。所有具体实例应使用上层 Ontology 中的类（如 `lbo:Product`、`lbo:Organization`）。


## 6. SHACL 验证约束

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix llb: <https://ontology.leleby.org/foundation/> .

# IdentifiableEntity 必须有标识符
llb:IdentifiableEntityShape
    a sh:NodeShape ;
    sh:targetClass llb:IdentifiableEntity ;
    sh:property [
        sh:path llb:hasIdentifier ;
        sh:minCount 1 ;
        sh:message "IdentifiableEntity 必须有标识符"
    ] .

# Document 必须有标识符
llb:DocumentShape
    a sh:NodeShape ;
    sh:targetClass llb:Document ;
    sh:property [
        sh:path llb:hasIdentifier ;
        sh:minCount 1 ;
        sh:message "Document 必须有标识符"
    ] .

# Statement 必须有内容或标签
llb:StatementShape
    a sh:NodeShape ;
    sh:targetClass llb:Statement ;
    sh:property [
        sh:path rdfs:label ;
        sh:minCount 1 ;
        sh:message "Statement 必须有标签"
    ] .

# Version 必须有版本号
llb:VersionShape
    a sh:NodeShape ;
    sh:targetClass llb:Version ;
    sh:property [
        sh:path llb:versionNumber ;
        sh:minCount 1 ;
        sh:message "Version 必须有版本号"
    ] .
```


## 7. 冻结声明

### 7.1 冻结范围

v1.1 确认后，以下内容进入**冻结状态**：

- ✅ 所有核心类定义（Entity、Concept、Agent、Identifier、Version、Document、Event、Statement、Time、Location、IdentifiableEntity）
- ✅ 所有核心属性与关系
- ✅ 命名空间 `https://ontology.leleby.org/foundation/`
- ✅ 与上层 Ontology 的继承接口

### 7.2 冻结后允许

- ✅ 新增辅助属性（如扩展的元数据字段），需确保后向兼容
- ✅ 在 `llb:` 中新增**纯元概念**类，需满足以下条件：
  - 该概念被至少两个独立的上层模块需要
  - 不携带任何领域语义
  - 经架构委员会批准

### 7.3 冻结后禁止

- ❌ **修改或删除任何现有类的核心语义**
- ❌ **修改或删除任何现有属性**
- ❌ **修改类的继承层次（除非修复错误）**
- ❌ **在 `llb:` 中添加任何工业领域类**（如 Product、Motor、Specification）
- ❌ **在 `llb:` 中添加任何 BFO 式类**（如 PhysicalEntity、Object、Process、Continuant、Occurrent）
- ❌ **在 `llb:` 中添加组织（Organization）类**——归属 `lbo:OrganizationOntology`
- ❌ **在 `llb:` 中添加测量量值或单位（Quantity、Unit）类**——归属 `lbo:MeasurementOntology`
- ❌ **修改 Entity 为"绝对根类"的定位**——Entity 是 leleby 推荐抽象基类，不是 owl:Thing 的替代
- ❌ **引入破坏后向兼容的变更**


## 8. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v0.9 | 2026-07-31 | 候选冻结版：初始草案，供评审 |
| v1.0 | 2026-07-31 | 正式冻结版：Entity 定位调整；删除 Organization；删除 Unit；新增 IdentifiableEntity；SHACL 调整；新增版本演进属性；明确 Statement 定位 |
| **v1.1** | **2026-08-04** | **精炼版**：1）移除 `Quantity` 类（归属 `lbo:MeasurementOntology`）；2）移除 `hasQuantity`、`hasNumericValue`、`hasUnit` 属性；3）增强 `Entity` 定义，明确其跨领域语义可标识性；4）弱化 `Concept` 中对 Constraint 的描述，避免与 Constraint Ontology 边界模糊；5）删除 `QuantityShape` SHACL 约束；6）新增 `VersionShape` SHACL 约束；7）冻结声明从"永久不可变更"调整为"仅允许后向兼容扩展" |


*— leleby Foundation Vocabulary Specification v1.1 — Refinement Release —*