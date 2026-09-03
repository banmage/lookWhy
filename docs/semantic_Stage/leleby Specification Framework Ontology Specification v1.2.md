# leleby Specification Framework Ontology Specification v1.2

**文档版本：** v1.2 — Semantic Target Enhancement Release（语义目标增强版）

**文档类型：** 模块规范（Module Ontology Specification）

**文档状态：** ✅ **核心冻结（Core Frozen）** — 规格框架核心模型已冻结，仅允许在指定扩展点进行模块内部扩展。

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.1

**依赖模块：**
- `llb` Foundation Vocabulary Specification v1.0
- `lbo-core` Core Ontology Specification v1.1
- `lbo-req` Requirement Ontology Specification v0.4
- `lbo-meas` Measurement Ontology Specification（待定）

**命名空间：** `https://ontology.leleby.org/specification/`

**推荐前缀：** `lspec`

**目标受众：** 本体架构师、产品数据架构师、PLM/ERP 系统集成商、AI Agent 开发者、标准工程师


## 目录

1. 引言
   1.1 目的
   1.2 核心定位
   1.3 与 Standard Ontology 的关系
   1.4 与 Requirement Ontology 的关系
   1.5 设计原则
   1.6 与其他模块的关系
   1.7 v1.2 修订说明（新增）
2. 命名空间声明
3. 核心概念模型
   3.1 顶层概念模型
   3.2 规格表达模型（v1.2 增强）
   3.3 值与条件模型
4. 类规范
   4.1 Specification
   4.2 SpecificationType
   4.3 SpecificationItem（v1.2 增强）
   4.4 SpecificationTarget（v1.2 新增）
   4.5 CharacteristicTarget（v1.2 新增）
   4.6 FunctionTarget（v1.2 新增）
   4.7 InterfaceTarget（v1.2 新增）
   4.8 StructureTarget（v1.2 新增）
   4.9 RelationshipTarget（v1.2 新增）
   4.10 ProcessTarget（v1.2 新增）
   4.11 Characteristic（引用 Core Ontology）
   4.12 ValueExpression
   4.13 SimpleValueExpression
   4.14 RangeValueExpression
   4.15 ToleranceValueExpression
   4.16 EnumerationValueExpression
   4.17 BooleanValueExpression
   4.18 ProbabilityValueExpression
   4.19 StringValueExpression
   4.20 ConditionalValueExpression
   4.21 SpecificationCondition
   4.22 SpecificationTemplate
   4.23 SpecificationProfile
   4.24 SpecificationSchema
5. 对象属性
   5.1 规格结构与组成属性
   5.2 目标与值属性（v1.2 增强）
   5.3 条件属性
   5.4 与外部模块的连接属性
6. 数据属性
7. 与 Requirement Ontology 的接口（v1.2 增强）
8. 与 Standard Ontology 的接口
9. 与 Product Ontology 的接口（v1.2 新增）
10. 外部标准对齐
11. SHACL 验证约束（v1.2 更新）
12. 完整示例（v1.2 更新）
13. 冻结声明
14. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Specification Framework Ontology 是 leleby 语义基础设施中**规格表达层**的核心模块。它定义了产品、服务、能力、组件等实体的结构化规格信息表达框架，使其能够被 AI Agent 理解、比较、验证和推理。

**核心目标：**
- 将企业产品信息（官网、手册、PDF）转换为机器可理解的规格语义
- 支持产品能力匹配与智能选型
- 支持 Requirement → Specification → Verification 推理链
- 支持 Standard → Requirement → Specification 合规推理
- 支持产品规格的版本化管理和差异比较
- **支持描述功能、接口、结构关系等非特性类工程语义对象（v1.2 新增）**

### 1.2 核心定位

> **Specification Framework Ontology 定义“规格如何表达”，而非“规格应该是什么”。**

| 模块 | 回答的问题 |
|---|---|
| **Standard Ontology** | 规范体系要求什么？ |
| **Requirement Ontology** | 要求的语义结构是什么？ |
| **Specification Framework Ontology** | 对象的规格如何表达？ |
| **Product Specification** | 这个具体产品的规格是什么？（实例层） |

### 1.3 与 Standard Ontology 的关系

**Specification Framework Ontology 与 Standard Ontology 是上下游关系，而非竞争或替代关系。**

```
Standard Ontology
        │
        │  定义规范体系（Standard / Clause / NormativeRequirement）
        ▼
Requirement Ontology
        │
        │  定义要求语义（六元模型）
        ▼
Specification Framework Ontology  ← 本模块
        │
        │  定义规格表达框架（SpecificationItem / ValueExpression）
        ▼
Product Specification（实例层）
        │
        │  描述具体产品
        ▼
lprod: ProductInstance
```

**关键区别：**

| 维度 | Standard Ontology | Specification Framework Ontology |
|---|---|---|
| 核心对象 | Standard / Clause / NormativeRequirement | Specification / SpecificationItem / ValueExpression |
| 表达内容 | 规范体系要求什么 | 对象的规格如何描述 |
| 来源 | 标准组织（IEC/ISO/GB） | 企业/产品数据 |
| 方向 | 外部要求 → 内部 | 内部表达 → 外部 |

### 1.4 与 Requirement Ontology 的关系

> **Requirement 定义“需要什么”，Specification 描述“实际是什么”。** 两者通过 `satisfies` / `evaluatedAgainst` 连接。

### 1.5 设计原则

**原则一：规格是信息实体，独立于被描述对象**
`Specification` 作为 `llb:InformationEntity`，可独立于产品进行版本化、复用和引用。

**原则二：规格项是核心表达单元**
每个规格项（`SpecificationItem`）表达“一个语义目标 + 一个值表达 + 可选条件”的三元组。

**原则三：值表达必须可计算**
所有值表达（`ValueExpression`）必须支持机器比较和计算，避免使用“高亮度”等不可量化描述。

**原则四：条件与值分离**
规格值通常在特定条件下成立（如“在 25℃ 环境下，功率为 100W”）。条件作为独立的 `SpecificationCondition` 表达。

**原则五：与 Standard Ontology 职责分离**
本模块不定义标准相关的概念（Standard、Clause、NormativeRequirement）。这些属于 `lbo-standard:StandardOntology`。

**原则六：与 Requirement Ontology 职责分离**
本模块不定义要求的约束语义。`Constraint` 属于 `lbo-constraint:ConstraintOntology`。

**原则七：规格目标通用化（v1.2 新增）**
规格可以描述任何工程语义元素，包括特性（Characteristic）、功能（Function）、接口（Interface）、结构关系（Structure）、产品关系（Relationship）和过程要素（Process），而不仅限于物理参数。

### 1.6 与其他模块的关系

```
llb: Foundation Vocabulary（基础词汇）
    │
    └── lbo-core: Core Ontology（核心工业概念）
            │
            └── lbo-spec: Specification Framework Ontology（本模块）
                    │
                    ├── 引用 → lbo-core:Characteristic
                    ├── 引用 → lbo-req:Requirement（通过 satisfiedBy）
                    ├── 引用 → lbo-std:Standard（通过 conformsToStandard）
                    ├── 引用 → lprod:ProductRelationship（通过 RelationshipTarget）
                    └── 引用 → lbo-meas:QuantityValue
```

### 1.7 v1.2 修订说明（新增）

v1.2 在 v1.1 的基础上，针对规格目标的语义范围进行了增强：

1. **引入 `SpecificationTarget` 抽象类**：作为规格目标的统一基类。
2. **新增目标子类**：`CharacteristicTarget`、`FunctionTarget`、`InterfaceTarget`、`StructureTarget`、`RelationshipTarget`、`ProcessTarget`。
3. **扩展 `SpecificationItem`**：将 `specifiesCharacteristic` 扩展为更通用的 `specifies`，支持指向任何 `SpecificationTarget`。
4. **保留向后兼容**：`specifiesCharacteristic` 作为 `specifies` 的子属性继续保留。
5. **新增与 Product Ontology 的接口**：明确 `RelationshipTarget` 可指向 `lprod:ProductRelationship`。
6. **更新示例**：展示功能、接口、结构关系等非特性规格。


## 2. 命名空间声明

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix llb: <https://ontology.leleby.org/foundation/> .
@prefix lbo-core: <https://ontology.leleby.org/core/> .
@prefix lbo-req: <https://ontology.leleby.org/requirement/> .
@prefix lbo-std: <https://ontology.leleby.org/standard/> .
@prefix lprod: <https://ontology.leleby.org/product/> .
@prefix lspec: <https://ontology.leleby.org/specification/> .

<https://ontology.leleby.org/specification/>
    rdf:type owl:Ontology ;
    owl:versionInfo "1.2" ;
    owl:imports <https://ontology.leleby.org/foundation/> ;
    owl:imports <https://ontology.leleby.org/core/> ;
    rdfs:label "leleby Specification Framework Ontology" ;
    rdfs:comment "leleby 规格表达框架，定义产品/服务/能力规格的结构化表达模型" .
```


## 3. 核心概念模型

### 3.1 顶层概念模型

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Specification Framework 核心结构                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Specification（规格书）                          │   │
│  │  一个版本化的信息实体，包含多个规格项                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │  contains                             │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SpecificationItem（规格项）                      │   │
│  │  一个规格目标（SpecificationTarget）+ 一个值表达（ValueExpression）  │   │
│  │  + 可选条件（Condition）                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                    ┌───────────────┼───────────────┐                    │
│                    │               │               │                    │
│                    ▼               ▼               ▼                    │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │ SpecificationTarget │  │  ValueExpression │  │   Condition     │    │
│  │   （规格目标）       │  │  （值的表达）    │  │  （生效条件）     │    │
│  └─────────────────────┘  └─────────────────┘  └─────────────────┘    │
│          │                                                               │
│          ├── CharacteristicTarget（特性）                               │
│          ├── FunctionTarget（功能）                                     │
│          ├── InterfaceTarget（接口）                                    │
│          ├── StructureTarget（结构）                                    │
│          ├── RelationshipTarget（关系）——可指向 ProductRelationship     │
│          └── ProcessTarget（过程）                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 规格表达模型（v1.2 增强）

```
Specification（规格书）
    │
    ├── hasSpecificationType → SpecificationType
    │
    ├── hasSpecificationItem → SpecificationItem（1..*）
    │       │
    │       ├── specifies → SpecificationTarget（1）
    │       │       │
    │       │       ├── CharacteristicTarget → lbo-core:Characteristic
    │       │       ├── FunctionTarget → lcap:Function / lprod:ProductFeature
    │       │       ├── InterfaceTarget → lprod:Interface
    │       │       ├── StructureTarget → lprod:Structure
    │       │       ├── RelationshipTarget → lprod:ProductRelationship
    │       │       └── ProcessTarget → lprod:Process
    │       │
    │       ├── hasValueExpression → ValueExpression
    │       └── underCondition → SpecificationCondition（可选）
    │
    ├── conformsToTemplate → SpecificationTemplate（可选）
    │
    └── hasProfile → SpecificationProfile（可选）
```

### 3.3 值与条件模型

```
ValueExpression（值表达抽象）
    │
    ├── SimpleValueExpression（单一值）
    │       └── hasQuantityValue → QuantityValue
    │
    ├── RangeValueExpression（范围值）
    │       ├── minValue → QuantityValue
    │       └── maxValue → QuantityValue
    │
    ├── ToleranceValueExpression（公差值）
    │       ├── nominalValue → QuantityValue
    │       ├── upperTolerance → QuantityValue
    │       └── lowerTolerance → QuantityValue
    │
    ├── EnumerationValueExpression（枚举值）
    │       └── allowedValues → rdfs:Literal[]
    │
    ├── BooleanValueExpression（布尔值）
    │       └── booleanValue → xsd:boolean
    │
    ├── ProbabilityValueExpression（概率值）
    │       ├── targetValue → QuantityValue
    │       └── confidenceLevel → xsd:double
    │
    ├── StringValueExpression（字符串值）
    │       └── stringValue → xsd:string
    │
    └── ConditionalValueExpression（条件值）
            ├── condition → SpecificationCondition
            └── thenValue → ValueExpression
```


## 4. 类规范

### 4.1 Specification

```turtle
lspec:Specification
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Document ;
    rdfs:label "Specification" ;
    rdfs:comment "规格书，描述对象特征、能力或参数集合的版本化信息实体" .
```

**属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lspec:specificationId` | 规格编号 | 1 |
| `lspec:specificationName` | 规格名称 | 1 |
| `lspec:specificationVersion` | 版本号 | 1 |
| `lspec:specificationStatus` | 状态（Draft/Released/Obsolete/UnderReview） | 0..1 |
| `lspec:createdDate` | 创建日期 | 0..1 |
| `lspec:modifiedDate` | 修改日期 | 0..1 |
| `lspec:validFrom` | 生效日期 | 0..1 |
| `lspec:validUntil` | 失效日期 | 0..1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:hasSpecificationItem` | lspec:Specification | lspec:SpecificationItem | 包含的规格项 | 1..* |
| `lspec:hasSpecificationType` | lspec:Specification | lspec:SpecificationType | 规格类型 | 0..1 |
| `lspec:conformsToTemplate` | lspec:Specification | lspec:SpecificationTemplate | 遵循的模板 | 0..1 |
| `lspec:hasProfile` | lspec:Specification | lspec:SpecificationProfile | 规格画像 | 0..1 |
| `lspec:supersedes` | lspec:Specification | lspec:Specification | 替代的旧规格 | 0..1 |
| `lspec:supersededBy` | lspec:Specification | lspec:Specification | 被新规格替代 | 0..1 |

### 4.2 SpecificationType

```turtle
lspec:SpecificationType
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "SpecificationType" ;
    rdfs:comment "规格的类型分类" .
```

**预定义类型：**

| 类型 | 说明 |
|---|---|
| `lspec:ProductSpecification` | 产品规格 |
| `lspec:ServiceSpecification` | 服务规格 |
| `lspec:CapabilitySpecification` | 能力规格 |
| `lspec:ComponentSpecification` | 组件规格 |
| `lspec:InterfaceSpecification` | 接口规格 |
| `lspec:MaterialSpecification` | 材料规格 |
| `lspec:ProcessSpecification` | 过程规格 |
| `lspec:QualitySpecification` | 质量规格 |
| `lspec:RelationshipSpecification` | 关系规格（v1.2 新增） |
| `lspec:FunctionSpecification` | 功能规格（v1.2 新增） |

### 4.3 SpecificationItem（v1.2 增强）

**这是 Specification Framework Ontology 的核心类。**

```turtle
lspec:SpecificationItem
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "SpecificationItem" ;
    rdfs:comment "单个规格项，描述一个规格目标（特性/功能/接口/关系等）在特定条件下的值表达" .
```

**属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lspec:itemIdentifier` | 项标识符 | 0..1 |
| `lspec:itemName` | 项名称 | 1 |
| `lspec:itemDescription` | 项描述 | 0..1 |
| `lspec:itemPriority` | 优先级（Critical/High/Medium/Low） | 0..1 |

**关系（v1.2 增强）：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:specifies` | lspec:SpecificationItem | **`lspec:SpecificationTarget`** | **规格目标（v1.2 新增，统一入口）** | 1 |
| `lspec:specifiesCharacteristic` | lspec:SpecificationItem | lbo-core:Characteristic | **描述的特性（v1.2 保留，作为 specifies 的子属性，向后兼容）** | 0..1 |
| `lspec:hasValueExpression` | lspec:SpecificationItem | lspec:ValueExpression | 值的表达 | 1 |
| `lspec:underCondition` | lspec:SpecificationItem | lspec:SpecificationCondition | 生效条件 | 0..1 |
| `lspec:hasUnit` | lspec:SpecificationItem | llb:Unit | 单位（快捷方式） | 0..1 |

### 4.4 SpecificationTarget（v1.2 新增）

```turtle
lspec:SpecificationTarget
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "SpecificationTarget" ;
    rdfs:comment "规格目标的抽象基类，表示规格描述的对象是哪个工程语义元素" .
```

### 4.5 CharacteristicTarget（v1.2 新增）

```turtle
lspec:CharacteristicTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:SpecificationTarget ;
    rdfs:label "CharacteristicTarget" ;
    rdfs:comment "特性类规格目标，指向 lbo-core:Characteristic" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:targetCharacteristic` | lspec:CharacteristicTarget | lbo-core:Characteristic | 目标特性 | 1 |

### 4.6 FunctionTarget（v1.2 新增）

```turtle
lspec:FunctionTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:SpecificationTarget ;
    rdfs:label "FunctionTarget" ;
    rdfs:comment "功能类规格目标，指向产品功能或能力" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:targetFunction` | lspec:FunctionTarget | lcap:Function / lprod:ProductFeature | 目标功能 | 1 |

### 4.7 InterfaceTarget（v1.2 新增）

```turtle
lspec:InterfaceTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:SpecificationTarget ;
    rdfs:label "InterfaceTarget" ;
    rdfs:comment "接口类规格目标，指向产品接口" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:targetInterface` | lspec:InterfaceTarget | lprod:Interface | 目标接口 | 1 |

### 4.8 StructureTarget（v1.2 新增）

```turtle
lspec:StructureTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:SpecificationTarget ;
    rdfs:label "StructureTarget" ;
    rdfs:comment "结构类规格目标，指向产品的结构元素" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:targetStructure` | lspec:StructureTarget | lprod:Structure | 目标结构 | 1 |

### 4.9 RelationshipTarget（v1.2 新增）

```turtle
lspec:RelationshipTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:SpecificationTarget ;
    rdfs:label "RelationshipTarget" ;
    rdfs:comment "关系类规格目标，指向产品关系（如 PartRelationship）" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:targetRelationship` | lspec:RelationshipTarget | **`lprod:ProductRelationship`** | **目标产品关系（v1.2 新增）** | 1 |

### 4.10 ProcessTarget（v1.2 新增）

```turtle
lspec:ProcessTarget
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:SpecificationTarget ;
    rdfs:label "ProcessTarget" ;
    rdfs:comment "过程类规格目标，指向生产过程或操作" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:targetProcess` | lspec:ProcessTarget | lprod:Process | 目标过程 | 1 |

### 4.11 Characteristic（引用 Core Ontology）

**Characteristic 定义在 `lbo-core:CoreOntology` 中。本模块通过 `lspec:specifiesCharacteristic` 引用，不重新定义。**

| 预定义特性（来自 Core） | 类型 | 说明 |
|---|---|---|
| `lbo-core:OperatingTemperature` | PhysicalProperty | 工作温度 |
| `lbo-core:StorageTemperature` | PhysicalProperty | 存储温度 |
| `lbo-core:Mass` | PhysicalProperty | 质量 |
| `lbo-core:Length` | PhysicalProperty | 长度 |
| `lbo-core:Diameter` | PhysicalProperty | 直径 |
| `lbo-core:PowerConsumption` | PhysicalProperty | 功耗 |
| `lbo-core:Voltage` | PhysicalProperty | 电压 |
| `lbo-core:Current` | PhysicalProperty | 电流 |
| `lbo-core:LuminousFlux` | PhysicalProperty | 光通量 |
| `lbo-core:ColorTemperature` | PhysicalProperty | 色温 |
| `lbo-core:ProtectionLevel` | QualityCharacteristic | 防护等级 |
| `lbo-core:Reliability` | QualityCharacteristic | 可靠性 |
| `lbo-core:Lifetime` | QualityCharacteristic | 寿命 |

### 4.12 ValueExpression

```turtle
lspec:ValueExpression
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "ValueExpression" ;
    rdfs:comment "值的表达方式的抽象基类" .
```

### 4.13 SimpleValueExpression

```turtle
lspec:SimpleValueExpression
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:ValueExpression ;
    rdfs:label "SimpleValueExpression" ;
    rdfs:comment "单一数值或量值表达" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:hasQuantityValue` | lspec:SimpleValueExpression | lbo-meas:QuantityValue | 量值 | 1 |

### 4.14 RangeValueExpression

```turtle
lspec:RangeValueExpression
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:ValueExpression ;
    rdfs:label "RangeValueExpression" ;
    rdfs:comment "范围值表达" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:minValue` | lspec:RangeValueExpression | lbo-meas:QuantityValue | 最小值 | 0..1 |
| `lspec:maxValue` | lspec:RangeValueExpression | lbo-meas:QuantityValue | 最大值 | 0..1 |

**约束：** 至少有一个 `minValue` 或 `maxValue`。

### 4.15 ToleranceValueExpression

```turtle
lspec:ToleranceValueExpression
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:ValueExpression ;
    rdfs:label "ToleranceValueExpression" ;
    rdfs:comment "公差值表达，如 15.0 ± 0.02" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:nominalValue` | lspec:ToleranceValueExpression | lbo-meas:QuantityValue | 标称值 | 1 |
| `lspec:upperTolerance` | lspec:ToleranceValueExpression | lbo-meas:QuantityValue | 上公差 | 0..1 |
| `lspec:lowerTolerance` | lspec:ToleranceValueExpression | lbo-meas:QuantityValue | 下公差 | 0..1 |

### 4.16 EnumerationValueExpression

```turtle
lspec:EnumerationValueExpression
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:ValueExpression ;
    rdfs:label "EnumerationValueExpression" ;
    rdfs:comment "枚举值表达" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:allowedValues` | lspec:EnumerationValueExpression | rdfs:Literal | 允许值列表 | 1 |

### 4.17 BooleanValueExpression

```turtle
lspec:BooleanValueExpression
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:ValueExpression ;
    rdfs:label "BooleanValueExpression" ;
    rdfs:comment "布尔值表达" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:booleanValue` | lspec:BooleanValueExpression | xsd:boolean | 布尔值 | 1 |

### 4.18 ProbabilityValueExpression

```turtle
lspec:ProbabilityValueExpression
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:ValueExpression ;
    rdfs:label "ProbabilityValueExpression" ;
    rdfs:comment "概率/统计值表达，如 L70 ≥ 50000h @ 90%" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:targetValue` | lspec:ProbabilityValueExpression | lbo-meas:QuantityValue | 目标值 | 1 |
| `lspec:confidenceLevel` | lspec:ProbabilityValueExpression | xsd:double | 置信度（0-1） | 0..1 |
| `lspec:statisticalQuantity` | lspec:ProbabilityValueExpression | xsd:string | 统计量类型（MTBF/L10/L70） | 0..1 |

### 4.19 StringValueExpression

```turtle
lspec:StringValueExpression
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:ValueExpression ;
    rdfs:label "StringValueExpression" ;
    rdfs:comment "字符串值表达" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:stringValue` | lspec:StringValueExpression | xsd:string | 字符串值 | 1 |

### 4.20 ConditionalValueExpression

```turtle
lspec:ConditionalValueExpression
    rdf:type owl:Class ;
    rdfs:subClassOf lspec:ValueExpression ;
    rdfs:label "ConditionalValueExpression" ;
    rdfs:comment "带条件的值表达：IF condition THEN value" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:condition` | lspec:ConditionalValueExpression | lspec:SpecificationCondition | 条件 | 1 |
| `lspec:thenValue` | lspec:ConditionalValueExpression | lspec:ValueExpression | 条件满足时的值 | 1 |

### 4.21 SpecificationCondition

```turtle
lspec:SpecificationCondition
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "SpecificationCondition" ;
    rdfs:comment "规格值生效的条件" .
```

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lspec:conditionName` | lspec:SpecificationCondition | xsd:string | 条件名称 | 0..1 |
| `lspec:conditionDescription` | lspec:SpecificationCondition | xsd:string | 条件描述 | 0..1 |
| `lspec:hasConditionExpression` | lspec:SpecificationCondition | lspec:ConditionExpression | 可执行条件表达 | 0..1 |

### 4.22 SpecificationTemplate

```turtle
lspec:SpecificationTemplate
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Document ;
    rdfs:label "SpecificationTemplate" ;
    rdfs:comment "规格模板，定义某类对象应包含的规格项结构" .
```

**关系：**

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lspec:definesSpecificationItem` | lspec:SpecificationTemplate | lspec:SpecificationItem | 模板定义的规格项 |
| `lspec:templateName` | lspec:SpecificationTemplate | xsd:string | 模板名称 |
| `lspec:appliesToClass` | lspec:SpecificationTemplate | rdfs:Class | 适用的 Ontology 类 |

### 4.23 SpecificationProfile

```turtle
lspec:SpecificationProfile
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "SpecificationProfile" ;
    rdfs:comment "规格画像，用于规格的比较和匹配" .
```

**用途：** 规格画像为 AI 选型提供可比较的特征集合。

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lspec:hasKeyCharacteristics` | lspec:SpecificationProfile | lbo-core:Characteristic | 关键特性列表 |
| `lspec:profileName` | lspec:SpecificationProfile | xsd:string | 画像名称 |

### 4.24 SpecificationSchema

```turtle
lspec:SpecificationSchema
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Document ;
    rdfs:label "SpecificationSchema" ;
    rdfs:comment "规格模式，定义规格的结构约束规则" .
```

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lspec:requiresCharacteristic` | lspec:SpecificationSchema | lbo-core:Characteristic | 必须包含的特性 |
| `lspec:optionalCharacteristic` | lspec:SpecificationSchema | lbo-core:Characteristic | 可选特性 |


## 5. 对象属性

### 5.1 规格结构与组成属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lspec:hasSpecificationItem` | lspec:Specification | lspec:SpecificationItem | 包含规格项 |
| `lspec:hasSpecificationType` | lspec:Specification | lspec:SpecificationType | 规格类型 |
| `lspec:conformsToTemplate` | lspec:Specification | lspec:SpecificationTemplate | 遵循模板 |
| `lspec:hasProfile` | lspec:Specification | lspec:SpecificationProfile | 规格画像 |
| `lspec:definesSpecificationItem` | lspec:SpecificationTemplate | lspec:SpecificationItem | 模板定义项 |
| `lspec:appliesToClass` | lspec:SpecificationTemplate | rdfs:Class | 适用类 |

### 5.2 目标与值属性（v1.2 增强）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lspec:specifies` | lspec:SpecificationItem | **`lspec:SpecificationTarget`** | **规格目标（v1.2 新增，统一入口）** |
| `lspec:specifiesCharacteristic` | lspec:SpecificationItem | lbo-core:Characteristic | 描述的特性（v1.2 保留为子属性，向后兼容） |
| `lspec:hasValueExpression` | lspec:SpecificationItem | lspec:ValueExpression | 值的表达 |
| `lspec:hasQuantityValue` | lspec:SimpleValueExpression | lbo-meas:QuantityValue | 量值 |
| `lspec:hasUnit` | lspec:SpecificationItem | llb:Unit | 单位（快捷） |
| `lspec:nominalValue` | lspec:ToleranceValueExpression | lbo-meas:QuantityValue | 标称值 |
| `lspec:upperTolerance` | lspec:ToleranceValueExpression | lbo-meas:QuantityValue | 上公差 |
| `lspec:lowerTolerance` | lspec:ToleranceValueExpression | lbo-meas:QuantityValue | 下公差 |
| `lspec:minValue` | lspec:RangeValueExpression | lbo-meas:QuantityValue | 最小值 |
| `lspec:maxValue` | lspec:RangeValueExpression | lbo-meas:QuantityValue | 最大值 |
| `lspec:allowedValues` | lspec:EnumerationValueExpression | rdfs:Literal | 允许值 |
| `lspec:booleanValue` | lspec:BooleanValueExpression | xsd:boolean | 布尔值 |
| `lspec:targetValue` | lspec:ProbabilityValueExpression | lbo-meas:QuantityValue | 目标值 |
| `lspec:confidenceLevel` | lspec:ProbabilityValueExpression | xsd:double | 置信度 |
| `lspec:stringValue` | lspec:StringValueExpression | xsd:string | 字符串值 |

### 5.3 条件属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lspec:underCondition` | lspec:SpecificationItem | lspec:SpecificationCondition | 生效条件 |
| `lspec:condition` | lspec:ConditionalValueExpression | lspec:SpecificationCondition | 条件 |
| `lspec:thenValue` | lspec:ConditionalValueExpression | lspec:ValueExpression | 条件满足时的值 |

### 5.4 与外部模块的连接属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lspec:satisfies` | lspec:Specification | lbo-req:Requirement | 规格满足的要求 |
| `lspec:evaluatedAgainst` | lspec:Specification | lbo-req:Requirement | 规格被要求评估 |
| `lspec:conformsToStandard` | lspec:Specification | lbo-std:Standard | 规格符合的标准 |
| `lspec:describedBy` | lbo-core:Product | lspec:Specification | 产品被规格描述 |
| `lspec:hasVerificationTarget` | lspec:SpecificationItem | lbo-ver:VerificationActivity | 提供验证目标 |


## 6. 数据属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lspec:specificationId` | lspec:Specification | xsd:string | 规格编号 |
| `lspec:specificationName` | lspec:Specification | xsd:string | 规格名称 |
| `lspec:specificationVersion` | lspec:Specification | xsd:string | 版本号 |
| `lspec:specificationStatus` | lspec:Specification | lspec:SpecificationStatus | 状态 |
| `lspec:validFrom` | lspec:Specification | xsd:date | 生效日期 |
| `lspec:validUntil` | lspec:Specification | xsd:date | 失效日期 |
| `lspec:itemIdentifier` | lspec:SpecificationItem | xsd:string | 项标识符 |
| `lspec:itemName` | lspec:SpecificationItem | xsd:string | 项名称 |
| `lspec:itemDescription` | lspec:SpecificationItem | xsd:string | 项描述 |
| `lspec:itemPriority` | lspec:SpecificationItem | lspec:ItemPriority | 优先级 |
| `lspec:templateName` | lspec:SpecificationTemplate | xsd:string | 模板名称 |
| `lspec:profileName` | lspec:SpecificationProfile | xsd:string | 画像名称 |


## 7. 与 Requirement Ontology 的接口（v1.2 增强）

### 7.1 关系定义

```turtle
# Specification 满足 Requirement
lspec:satisfies
    rdf:type owl:ObjectProperty ;
    rdfs:domain lspec:Specification ;
    rdfs:range lbo-req:Requirement ;
    rdfs:label "satisfies" ;
    rdfs:comment "规格满足某个要求" .

# Specification 被 Requirement 评估
lspec:evaluatedAgainst
    rdf:type owl:ObjectProperty ;
    rdfs:domain lspec:Specification ;
    rdfs:range lbo-req:Requirement ;
    rdfs:label "evaluatedAgainst" ;
    rdfs:comment "规格被某个要求评估" .
```

### 7.2 完整推理链（v1.2 更新）

```
Requirement（要求）
    │
    │  defines what is needed
    │  （要求约束的可以是 Characteristic / Function / Interface / Relationship）
    ▼
Specification（规格）
    │
    │  describes actual values / states
    │  （SpecificationItem 通过 SpecificationTarget 指向对应的工程元素）
    ▼
Verification（验证）
    │
    │  compares target vs observed
    ▼
VerificationResult（验证结果）
    │
    │  supports
    ▼
ComplianceAssessment（合规评估）
```


## 8. 与 Standard Ontology 的接口

### 8.1 关系定义

```turtle
# Specification 符合 Standard
lspec:conformsToStandard
    rdf:type owl:ObjectProperty ;
    rdfs:domain lspec:Specification ;
    rdfs:range lbo-std:Standard ;
    rdfs:label "conformsToStandard" ;
    rdfs:comment "规格符合某个标准" .
```

### 8.2 Standard → Specification 链路

```
Standard Ontology（标准体系）
    │
    │  defines
    ▼
Requirement Ontology（要求语义）
    │
    │  requires
    ▼
Specification Framework Ontology（规格表达）
    │
    │  describes
    ▼
Product Specification（产品规格实例）
```


## 9. 与 Product Ontology 的接口（v1.2 新增）

v1.2 新增了与 Product Ontology v0.4 的明确接口，特别是支持 `RelationshipTarget` 指向 `lprod:ProductRelationship`。

### 9.1 关系定义

```turtle
# Specification 描述 Product
lspec:describes
    rdf:type owl:ObjectProperty ;
    rdfs:domain lspec:Specification ;
    rdfs:range lprod:Product ;
    rdfs:label "describes" ;
    rdfs:comment "规格描述了某个产品" .

# 反向关系：Product 被 Specification 描述（在 Product Ontology 中定义）
lprod:describedBy
    rdf:type owl:ObjectProperty ;
    rdfs:domain lprod:Product ;
    rdfs:range lspec:Specification ;
    rdfs:label "describedBy" .
```

### 9.2 规格目标与产品元素的映射

```
lspec:SpecificationItem
    │
    │  specifies
    ▼
lspec:SpecificationTarget
    │
    ├── CharacteristicTarget → lbo-core:Characteristic → (hostedBy) → lprod:Product
    ├── FunctionTarget → lcap:Function → (hostedBy) → lprod:Product
    ├── InterfaceTarget → lprod:Interface → (hostedBy) → lprod:Product
    ├── StructureTarget → lprod:Structure → (hostedBy) → lprod:Product
    ├── RelationshipTarget → lprod:ProductRelationship → (subjectProduct/objectProduct) → lprod:Product
    └── ProcessTarget → lprod:Process → (partOf) → lprod:Product
```


## 10. 外部标准对齐

| 外部体系 | 对齐方式 | 说明 |
|---|---|---|
| schema.org | `skos:closeMatch` | schema:PropertyValue / schema:QuantitativeValue |
| QUDT | `skos:closeMatch` | qudt:QuantityValue / qudt:Unit |
| GS1 | `skos:relatedMatch` | 产品属性映射 |
| eCl@ss | `skos:relatedMatch` | 产品分类属性映射 |
| IEC CDD | `skos:closeMatch` | 工程属性字典 |


## 11. SHACL 验证约束（v1.2 更新）

### 11.1 Specification 约束

```turtle
lspec:SpecificationShape
    a sh:NodeShape ;
    sh:targetClass lspec:Specification ;
    sh:property [
        sh:path lspec:specificationId ;
        sh:minCount 1 ;
        sh:message "Specification must have an identifier"
    ] ;
    sh:property [
        sh:path lspec:specificationName ;
        sh:minCount 1 ;
        sh:message "Specification must have a name"
    ] ;
    sh:property [
        sh:path lspec:specificationVersion ;
        sh:minCount 1 ;
        sh:message "Specification must have a version"
    ] ;
    sh:property [
        sh:path lspec:hasSpecificationItem ;
        sh:minCount 1 ;
        sh:message "Specification must have at least one specification item"
    ] .
```

### 11.2 SpecificationItem 约束（v1.2 更新）

```turtle
lspec:SpecificationItemShape
    a sh:NodeShape ;
    sh:targetClass lspec:SpecificationItem ;
    sh:or (
        [
            sh:property [
                sh:path lspec:specifies ;
                sh:minCount 1 ;
                sh:message "SpecificationItem must specify a SpecificationTarget"
            ]
        ]
        [
            sh:property [
                sh:path lspec:specifiesCharacteristic ;
                sh:minCount 1 ;
                sh:message "SpecificationItem must specify a Characteristic"
            ]
        ]
    ) ;
    sh:property [
        sh:path lspec:hasValueExpression ;
        sh:minCount 1 ;
        sh:message "SpecificationItem must have a value expression"
    ] .
```

### 11.3 RangeValueExpression 约束

```turtle
lspec:RangeValueExpressionShape
    a sh:NodeShape ;
    sh:targetClass lspec:RangeValueExpression ;
    sh:or (
        [ sh:path lspec:minValue ; sh:minCount 1 ]
        [ sh:path lspec:maxValue ; sh:minCount 1 ]
    ) ;
    sh:message "RangeValueExpression must have at least one of minValue or maxValue" .
```

### 11.4 SimpleValueExpression 约束

```turtle
lspec:SimpleValueExpressionShape
    a sh:NodeShape ;
    sh:targetClass lspec:SimpleValueExpression ;
    sh:property [
        sh:path lspec:hasQuantityValue ;
        sh:minCount 1 ;
        sh:message "SimpleValueExpression must have a quantity value"
    ] .
```

### 11.5 SpecificationTarget 约束（v1.2 新增）

```turtle
lspec:SpecificationTargetShape
    a sh:NodeShape ;
    sh:targetClass lspec:SpecificationTarget ;
    sh:closed false ;
    sh:message "SpecificationTarget can be specialized to specific target types" .
```


## 12. 完整示例（v1.2 更新）

### 12.1 户外灯具完整规格（含非特性目标）

```ttl
# 规格定义
lspec:OutdoorLampSpec
    a lspec:Specification ;
    lspec:specificationId "YD-SPEC-001" ;
    lspec:specificationName "YD-GK-200W 产品规格书" ;
    lspec:specificationVersion "1.0" ;
    lspec:specificationStatus lspec:Released ;
    lspec:validFrom "2026-01-01"^^xsd:date ;
    lspec:hasSpecificationType lspec:ProductSpecification .

# --- 规格项1：特性目标（功率）---
lspec:SpecItem_Power
    a lspec:SpecificationItem ;
    lspec:itemName "额定功率" ;
    lspec:specifies [
        a lspec:CharacteristicTarget ;
        lspec:targetCharacteristic lbo-core:PowerConsumption
    ] ;
    lspec:hasValueExpression [
        a lspec:SimpleValueExpression ;
        lspec:hasQuantityValue [
            a lbo-meas:QuantityValue ;
            llb:hasNumericValue "200"^^xsd:double ;
            llb:hasUnit llb:Watt
        ]
    ] .

# --- 规格项2：特性目标（工作温度，范围值）---
lspec:SpecItem_Temperature
    a lspec:SpecificationItem ;
    lspec:itemName "工作温度" ;
    lspec:specifies [
        a lspec:CharacteristicTarget ;
        lspec:targetCharacteristic lbo-core:OperatingTemperature
    ] ;
    lspec:hasValueExpression [
        a lspec:RangeValueExpression ;
        lspec:minValue [
            a lbo-meas:QuantityValue ;
            llb:hasNumericValue "-40"^^xsd:double ;
            llb:hasUnit llb:DegreeCelsius
        ] ;
        lspec:maxValue [
            a lbo-meas:QuantityValue ;
            llb:hasNumericValue "70"^^xsd:double ;
            llb:hasUnit llb:DegreeCelsius
        ]
    ] .

# --- 规格项3：功能目标（过载保护）---（v1.2 新增）
lspec:SpecItem_OverloadProtection
    a lspec:SpecificationItem ;
    lspec:itemName "过载保护功能" ;
    lspec:specifies [
        a lspec:FunctionTarget ;
        lspec:targetFunction lprod:OverloadProtectionFeature
    ] ;
    lspec:hasValueExpression [
        a lspec:BooleanValueExpression ;
        lspec:booleanValue "true"^^xsd:boolean
    ] .

# --- 规格项4：接口目标（通信接口）---（v1.2 新增）
lspec:SpecItem_CommunicationInterface
    a lspec:SpecificationItem ;
    lspec:itemName "通信接口" ;
    lspec:specifies [
        a lspec:InterfaceTarget ;
        lspec:targetInterface lprod:CAN_Interface
    ] ;
    lspec:hasValueExpression [
        a lspec:SimpleValueExpression ;
        lspec:hasQuantityValue [
            a lbo-meas:QuantityValue ;
            llb:hasNumericValue "250"^^xsd:double ;
            llb:hasUnit llb:Kbps
        ]
    ] ;
    lspec:underCondition [
        a lspec:SpecificationCondition ;
        lspec:conditionName "通信启用" ;
        lspec:conditionDescription "当控制器启用 CAN 通信时"
    ] .

# --- 规格项5：关系目标（LED模块安装）---（v1.2 新增）
lspec:SpecItem_LEDModuleInstallation
    a lspec:SpecificationItem ;
    lspec:itemName "LED模块安装规格" ;
    lspec:specifies [
        a lspec:RelationshipTarget ;
        lspec:targetRelationship lprod:LEDModule_Installation
    ] ;
    lspec:hasValueExpression [
        a lspec:EnumerationValueExpression ;
        lspec:allowedValues ("Bolted" "Electrical")
    ] ;
    lspec:itemPriority lspec:Critical .

# 组装规格
lspec:OutdoorLampSpec
    lspec:hasSpecificationItem lspec:SpecItem_Power ;
    lspec:hasSpecificationItem lspec:SpecItem_Temperature ;
    lspec:hasSpecificationItem lspec:SpecItem_OverloadProtection ;
    lspec:hasSpecificationItem lspec:SpecItem_CommunicationInterface ;
    lspec:hasSpecificationItem lspec:SpecItem_LEDModuleInstallation .

# 产品与规格连接
lprod:YD_GK_200W
    lprod:describedBy lspec:OutdoorLampSpec .
```

### 12.2 规格与要求的连接（v1.2 更新）

```ttl
# 要求：电机必须提供过载保护功能
lbo-req:REQ_OverloadProtection_001
    a lbo-req:Requirement ;
    rdfs:label "电机必须提供过载保护功能" ;
    lbo-req:hasSemanticTarget [
        a lbo-req:FunctionTarget ;
        lbo-req:targetFunction lprod:OverloadProtectionFeature
    ] .

# 规格满足要求
lspec:OutdoorLampSpec
    lspec:satisfies lbo-req:REQ_OverloadProtection_001 .

# 要求：车辆必须具有四个工作轮胎（结构关系）
lbo-req:REQ_WorkingWheel_004
    a lbo-req:Requirement ;
    rdfs:label "车辆必须具有四个工作轮胎" ;
    lbo-req:hasSemanticTarget [
        a lbo-req:StructureRelationTarget ;
        lbo-req:targetRelationshipType lprod:PartRelationship ;
        lbo-req:requiredCardinality 4 ;
        lbo-req:requiredRole lprod:WorkingPart
    ] .

# 规格描述车辆结构
lspec:VehicleStructureSpec
    a lspec:Specification ;
    lspec:specificationName "车辆结构规格" ;
    lspec:hasSpecificationItem lspec:SpecItem_WheelInstallation .

lspec:SpecItem_WheelInstallation
    a lspec:SpecificationItem ;
    lspec:itemName "工作轮胎安装" ;
    lspec:specifies [
        a lspec:RelationshipTarget ;
        lspec:targetRelationship lprod:Vehicle_Wheel_Installation
    ] ;
    lspec:hasValueExpression [
        a lspec:SimpleValueExpression ;
        lspec:hasQuantityValue [
            a lbo-meas:QuantityValue ;
            llb:hasNumericValue "4"^^xsd:integer ;
            llb:hasUnit llb:Each
        ]
    ] .

lspec:VehicleStructureSpec
    lspec:satisfies lbo-req:REQ_WorkingWheel_004 .
```


## 13. 冻结声明

### 13.1 冻结范围

v1.2 确认后，以下内容进入**核心冻结状态**：

- ✅ 所有核心类（Specification、SpecificationItem、ValueExpression 及其子类、SpecificationCondition、SpecificationTemplate、SpecificationProfile、SpecificationSchema）
- ✅ **所有核心对象属性（包括 v1.2 新增的 `specifies` 和 `SpecificationTarget` 体系）**
- ✅ 命名空间 `https://ontology.leleby.org/specification/`
- ✅ 与 Requirement Ontology / Standard Ontology / Product Ontology 的接口

### 13.2 扩展点（Reserved Extension Points）

以下内容允许在 v1.2 基础上进行模块内部扩展，无需变更核心冻结模型：

- ✅ **新增 SpecificationTarget 子类（扩展点）**
- ✅ 新增 ValueExpression 子类
- ✅ 新增 SpecificationType
- ✅ 新增 ItemPriority 枚举值
- ✅ 新增 SpecificationCondition 子类

### 13.3 冻结后禁止

- ❌ **修改或删除任何现有核心类**
- ❌ **修改或删除任何现有核心属性**
- ❌ **改变与 Requirement / Standard / Core / Product Ontology 的核心接口**
- ❌ **在 Specification Framework 中定义标准相关概念**（Standard、Clause、NormativeRequirement）
- ❌ **将 SpecificationTarget 回退为仅支持 Characteristic**


## 14. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v1.0 | 2026-07-28 | 初始冻结版（Specification Ontology） |
| v1.1 | 2026-07-31 | 框架重构版：明确与 Standard Ontology 的上下游关系；删除 Standard 来源相关概念；新增 SpecificationProfile、SpecificationSchema；新增 ConditionalValueExpression；增加 conformsToStandard 接口 |
| **v1.2** | **2026-08-04** | **语义目标增强版**：1）引入 `SpecificationTarget` 抽象类，作为规格目标的统一基类；2）新增 `CharacteristicTarget`、`FunctionTarget`、`InterfaceTarget`、`StructureTarget`、`RelationshipTarget`、`ProcessTarget` 六个子类；3）`SpecificationItem` 增加 `specifies` 属性，支持指向任何 `SpecificationTarget`；4）`specifiesCharacteristic` 作为 `specifies` 的子属性保留，确保向后兼容；5）新增与 Product Ontology v0.4 的接口，特别是 `RelationshipTarget` 可指向 `lprod:ProductRelationship`；6）新增功能、接口、关系规格的完整示例；7）更新 SHACL 约束；8）更新冻结声明，明确扩展点 |


*— leleby Specification Framework Ontology Specification v1.2 — Semantic Target Enhancement Release —*