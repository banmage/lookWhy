# leleby Product Ontology Specification v0.4

**文档版本：** v0.4 — Relationship Enhancement Release（关系增强版）

**文档类型：** 模块本体规范（Module Ontology Specification）

**文档状态：** ✅ **核心冻结（Core Frozen）** — 模块职责、核心类与顶层关系已稳定，后续仅允许模块内部扩展，禁止修改跨模块边界

**依赖架构：** leleby Ontology Architecture Specification v0.7

**对齐模块：** Requirement Ontology Specification v0.2

**命名空间：** `https://ontology.leleby.org/v0.7/product/`

**推荐前缀：** `lprod`

**目标受众：** 本体工程师、产品数据架构师、PLM/ERP 系统集成商、AI Agent 开发者


## 目录

1. 引言
   1.1 目的
   1.2 v0.4 核心定位
   1.3 v0.4 与 v0.3 的关系
   1.4 与 leleby Ontology Architecture v0.7 的对齐
   1.5 本规范的边界
2. 设计原则（v0.4 更新）
3. 核心概念模型
   3.1 Product（产品）
   3.2 ProductType（产品类型）
   3.3 ProductModel（产品型号）
   3.4 ProductInstance（产品实例）
   3.5 三元模型关系图
4. Product Identity Model（身份模型）
5. Product Composition Model（组成模型 v0.4 重构）
   5.1 设计思想：关系是一等工程实体
   5.2 快捷关系：hasPart / hasConstituent
   5.3 ProductRelationship 基类
   5.4 PartRelationship
   5.5 InterfaceRelationship
   5.6 CompatibilityRelationship
   5.7 DependencyRelationship
   5.8 AssemblyRelationship
   5.9 关系实体化 vs RDF-star 使用规则（v0.4 新增）
6. Product Capability Model（能力模型）
7. Product Specification Reference Model（规格引用模型）
8. Product Configuration Model（配置模型）
9. Product Relationship Model（产品间关系—广义）
10. Product Offering Model（商业化提供模型）
11. Product Lifecycle Model（生命周期模型）
12. 产品分类与外部映射
13. 与其他 Ontology 的边界与关系（v0.4 更新）
    13.1 与 Requirement Ontology 的接口（v0.4 新增）
14. SHACL 验证约束（v0.4 更新）
15. 完整示例：云达照明（v0.4 更新）
16. 核心类汇总
17. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Product Ontology 是 leleby 语义基础设施中**产品实体层（Product Entity Layer）**的核心模块。它定义了工业世界中“产品”的本质语义——企业提供什么、产品如何被识别、如何分类、如何组成、具有什么能力、以及如何被商业化提供。

本规范是 leleby Product Ontology 的正式冻结版本 v0.4。

### 1.2 v0.4 核心定位

> **Product Ontology defines what an enterprise provides, how products are identified, classified, configured, composed, what capabilities they provide, and how they relate to each other as engineering entities. Product relationships — especially part relationships — are first-class engineering entities that carry semantics such as role, cardinality, connection, importance, replaceability, and assembly method.**

**中文：**
> Product Ontology 描述企业提供什么产品、产品如何分类和识别、由什么组成、具有什么能力、如何被商业化提供，以及产品之间如何作为工程实体相互关联。产品关系——尤其是部件关系——是一等工程实体，承载角色、数量、连接方式、重要性、可替换性和装配方式等语义。

### 1.3 v0.4 与 v0.3 的关系

v0.4 **不是推倒重来**，而是在 v0.3 基础上进行**关系模型增强**：

| 维度 | v0.3（产品实体层模型） | v0.4（关系增强版） |
|------|----------------------|-------------------|
| 结构表达 | ProductStructureAssertion | ProductRelationship 基类体系 |
| 部件关系 | 固定断言结构 | PartRelationship 承载角色、数量、连接、重要性、可替换性 |
| 接口关系 | 无 | 新增 InterfaceRelationship |
| 依赖关系 | 隐含 | 新增 DependencyRelationship |
| 装配关系 | 无 | 新增 AssemblyRelationship |
| hasPart | 主关系 | 降级为快捷关系（语义简化版） |
| RDF-star | 未涉及 | 明确使用规则 |
| 与Requirement接口 | 无 | 明确 Requirement 可约束 Relationship |

### 1.4 与 leleby Ontology Architecture v0.7 的对齐

Product Ontology v0.4 完全遵循 v0.7 架构中定义的**语义闭环链路**：

```
Enterprise → Product → Specification → Verification → Compliance → Decision → Action
```

Product Ontology 负责 **Enterprise → Product** 以及 **Product → Specification** 的连接，不承担后续链路的职责。

### 1.5 本规范的边界

**本规范包含：**

| 模块 | 说明 |
|------|------|
| Product Concept Model | 产品的核心类定义（Product / ProductType / ProductModel / ProductInstance） |
| Product Classification Model | 产品分类与外部体系映射 |
| Product Identity Model | 产品标识符（SKU / Model / GTIN / Serial Number） |
| Product Composition Model | **产品结构关系（PartRelationship / InterfaceRelationship / DependencyRelationship / AssemblyRelationship）** |
| Product Capability Model | 产品提供的能力（providesCapability） |
| Product Specification Reference Model | 产品与规格的描述关系（describedBy） |
| Product Configuration Model | 产品配置（选配项、变体） |
| Product Lifecycle Model | 产品生命周期状态（仅状态引用） |
| Product Relationship Model | 产品间关系（变体、兼容） |
| Product Offering Model | 产品的商业化表达（销售状态、市场区域） |

**本规范不包含：**

| 内容 | 归属 |
|------|------|
| 要求定义 | Requirement Ontology |
| 验证方法 / 测试方法 | Verification Ontology |
| 符合性判断 | Compliance Ontology |
| 决策规则 / 行动映射 | Decision Ontology |
| 产品规格的详细属性 | Specification Ontology |


## 2. 设计原则（v0.4 更新）

### 2.1 产品实体原则

> **Product 是企业向市场提供的具有商业身份的实体对象。** 它既是工程技术对象（具有结构、能力），也是商业对象（具有价格、市场、销售状态）。

### 2.2 产品三元模型原则

> **产品类型（ProductType）、产品型号（ProductModel）和产品实例（ProductInstance）是三种不同的抽象层次，不应混淆。**

| 层次 | 概念 | 示例 |
|------|------|------|
| 类型层 | ProductType | “户外 LED 灯具” |
| 型号层 | ProductModel | “YD-GK-200W” |
| 实例层 | ProductInstance | “SN: 202607001” |

### 2.3 产品与规格分离原则

> **Product 本身不承载规格内容，而是通过 `describedBy` 引用 Specification Ontology 中的 ProductSpecification 信息实体。**

### 2.4 能力提供原则

> **Product 提供能力（providesCapability），而非“满足要求”。**

### 2.5 产品与要求间接连接原则

> **Product 不直接连接 Requirement。** 通过 Capability 或 Specification 建立间接连接。

### 2.6 关系是一等工程实体原则（v0.4 核心）

> **Product 之间的工程关系——尤其是部件关系——是一等实体（first-class entity），而非产品的属性或简单的三元组。** 关系承载角色、数量、连接方式、重要性、可替换性、装配方式等工程语义，应被显式建模为独立的 `ProductRelationship` 及其子类。

### 2.7 递归组合原则

> **Product 之间可以通过结构关系形成递归组合。** `hasPart` 快捷关系支持递归组合。


## 3. 核心概念模型

### 3.1 Product（产品）

```
leleby-product:Product
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Continuant ;
    rdfs:label "Product" ;
    rdfs:comment "产品是企业向市场提供的具有商业身份的实体对象。"
```

**语义说明：**

Product 是 **Continuant**（持续存在物），在时间中保持身份不变。它既是：
- **工程对象**：具有结构、组件、能力
- **商业对象**：具有价格、市场区域、销售状态

**核心属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `lprod:hasProductName` | lprod:Product | xsd:string | 产品名称 | 1 |
| `lprod:hasProductDescription` | lprod:Product | xsd:string | 产品描述 | 0..1 |
| `lprod:productStatus` | lprod:Product | lprod:ProductStatus | 产品状态 | 0..1 |

### 3.2 ProductType（产品类型）

```
leleby-product:ProductType
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Continuant ;
    rdfs:label "ProductType" ;
    rdfs:comment "产品类别/类型，如'户外LED灯具'、'工业机器人'" .
```

### 3.3 ProductModel（产品型号）

```
leleby-product:ProductModel
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Continuant ;
    rdfs:label "ProductModel" ;
    rdfs:comment "产品型号，如'YD-GK-200W'，代表一个可销售的产品规格定义" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:hasModelNumber` | lprod:ProductModel | xsd:string | 型号编号 |
| `lprod:releaseDate` | lprod:ProductModel | xsd:date | 上市日期 |
| `lprod:hasSeries` | lprod:ProductModel | xsd:string | 产品系列 |

### 3.4 ProductInstance（产品实例）

```
leleby-product:ProductInstance
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Continuant ;
    rdfs:label "ProductInstance" ;
    rdfs:comment "具体的产品个体，可被追踪（如 SN: 202607001）" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:hasSerialNumber` | lprod:ProductInstance | xsd:string | 序列号 |
| `lprod:manufacturedDate` | lprod:ProductInstance | xsd:date | 生产日期 |
| `lprod:batchNumber` | lprod:ProductInstance | xsd:string | 批次号 |

### 3.5 三元模型关系图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    产品三元模型（v0.4 保留）                                │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │                        ProductType                               │    │
│  │                   （产品类别，如“户外LED灯具”）                  │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    │  hasProductType                       │
│                                    ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │                        ProductModel                              │    │
│  │                   （产品型号，如“YD-GK-200W”）                   │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    │  hasInstance                          │
│                                    ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │                       ProductInstance                            │    │
│  │                   （产品个体，如“SN: 202607001”）                │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**关键关系：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:hasProductType` | lprod:ProductModel | lprod:ProductType | 型号属于某类型 |
| `lprod:hasModel` | lprod:Product | lprod:ProductModel | 实体有关联的型号 |
| `lprod:hasInstance` | lprod:ProductModel | lprod:ProductInstance | 型号有实例 |
| `lprod:instanceOfModel` | lprod:ProductInstance | lprod:ProductModel | 实例属于某型号 |


## 4. Product Identity Model（身份模型）

### 4.1 ProductIdentifier

```
leleby-product:ProductIdentifier
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Identifier ;
    rdfs:label "ProductIdentifier" ;
    rdfs:comment "产品标识符，统一表达各种产品身份体系" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:identifierType` | lprod:ProductIdentifier | lprod:IdentifierType | 标识符类型 |
| `lprod:identifierValue` | lprod:ProductIdentifier | xsd:string | 标识符值 |
| `lprod:issuedBy` | lprod:ProductIdentifier | leleby:Organization | 签发机构 |

**IdentifierType 枚举：**

| 值 | 说明 |
|----|------|
| `lprod:SKU` | 库存单位 |
| `lprod:ModelNumber` | 型号编号 |
| `lprod:SerialNumber` | 序列号 |
| `lprod:GTIN` | 全球贸易项目代码 |
| `lprod:InternalCode` | 内部编码 |
| `lprod:PartNumber` | 零件编号 |
| `lprod:SupplierCode` | 供应商代码 |


## 5. Product Composition Model（组成模型 v0.4 重构）

### 5.1 设计思想：关系是一等工程实体

v0.4 的核心变化：产品之间的关系——尤其是部件关系——被提升为**一等工程实体（first-class engineering entity）**。

**为什么需要关系实体化？**

在工业工程中，产品之间的关系不仅仅是“A 包含 B”，而是包含丰富的工程语义：

| 语义维度 | 示例 |
|----------|------|
| **角色** | 工作轮胎 vs 备用轮胎 |
| **数量** | 4 个 vs 1 个 |
| **连接方式** | 焊接、螺栓连接、压装 |
| **重要性** | 关键件 vs 一般件 |
| **可替换性** | 可现场更换 vs 工厂替换 |
| **装配方式** | 先装后焊 vs 单独装配 |
| **生命周期关系** | 同步更新 vs 独立更换 |
| **方位/位置** | 左侧、右侧、顶部 |

如果仅使用简单的 `hasPart` 属性（甚至是加了 RDF-star 标注的三元组），这些语义无法被完整表达，也无法被 Requirement、Constraint、Specification 直接引用。

**解决方案：**

- **简单关系**（仅表达存在性）：使用 `hasPart` / `hasConstituent` 快捷关系，可采用 RDF-star 标注。
- **工程语义关系**（需表达角色、数量、连接等）：使用 `PartRelationship` 等实体化关系。

### 5.2 快捷关系：hasPart / hasConstituent（保留，重新定位）

```
lprod:hasPart
    rdf:type owl:ObjectProperty ;
    rdfs:domain lprod:Product ;
    rdfs:range lprod:Product ;
    rdfs:label "hasPart" ;
    rdfs:comment "产品包含离散部件（快捷关系，用于简化表达）。详细信息应使用 PartRelationship 实体。" .
```

```
lprod:hasConstituent
    rdf:type owl:ObjectProperty ;
    rdfs:domain lprod:Product ;
    rdfs:range lprod:Product ;
    rdfs:label "hasConstituent" ;
    rdfs:comment "产品的物质组成（快捷关系），与 hasPart 完全独立。详细信息应使用 ConstituentRelationship 实体。" .
```

**使用规则：**

- `hasPart` / `hasConstituent` 仅用于表达“存在性”关系，不携带工程语义。
- 当需要表达角色、数量、连接方式、重要性等工程语义时，**必须**使用 `PartRelationship` 或 `ConstituentRelationship` 实体。
- 快捷关系与实体化关系可共存：快捷关系提供快速查询路径，实体化关系提供详细语义。

### 5.3 ProductRelationship 基类

```
lprod:ProductRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Relationship ;
    rdfs:label "ProductRelationship" ;
    rdfs:comment "产品关系的抽象基类。所有产品间工程关系均应继承自此，表达关系是一等工程实体。" .
```

**通用属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `lprod:subjectProduct` | lprod:ProductRelationship | lprod:Product | 关系主体 | 1 |
| `lprod:objectProduct` | lprod:ProductRelationship | lprod:Product | 关系客体 | 1 |
| `lprod:relationshipType` | lprod:ProductRelationship | lprod:RelationshipType | 关系类型 | 1 |
| `lprod:relationshipName` | lprod:ProductRelationship | xsd:string | 关系名称 | 0..1 |
| `lprod:relationshipDescription` | lprod:ProductRelationship | xsd:string | 关系描述 | 0..1 |

**RelationshipType 枚举：**

| 值 | 说明 |
|----|------|
| `lprod:PartRelationshipType` | 部件关系 |
| `lprod:InterfaceRelationshipType` | 接口关系 |
| `lprod:CompatibilityRelationshipType` | 兼容关系 |
| `lprod:DependencyRelationshipType` | 依赖关系 |
| `lprod:AssemblyRelationshipType` | 装配关系 |
| `lprod:ConstituentRelationshipType` | 物质组成关系 |

### 5.4 PartRelationship（部件关系）

```
lprod:PartRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lprod:ProductRelationship ;
    rdfs:label "PartRelationship" ;
    rdfs:comment "产品与其组成部件之间的工程关系，承载角色、数量、连接方式、重要性、可替换性等工程语义。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `lprod:part` | lprod:PartRelationship | lprod:Product | 部件（同 objectProduct） | 1 |
| `lprod:partRole` | lprod:PartRelationship | lprod:PartRole | **部件角色（v0.4 新增）** | 0..1 |
| `lprod:cardinality` | lprod:PartRelationship | xsd:integer | **数量（v0.4 新增）** | 0..1 |
| `lprod:minCardinality` | lprod:PartRelationship | xsd:integer | **最少数量（v0.4 新增）** | 0..1 |
| `lprod:maxCardinality` | lprod:PartRelationship | xsd:integer | **最多数量（v0.4 新增）** | 0..1 |
| `lprod:cardinalityUnit` | lprod:PartRelationship | leleby:Unit | 数量单位 | 0..1 |
| `lprod:connectionType` | lprod:PartRelationship | lprod:ConnectionType | 连接方式 | 0..1 |
| `lprod:importanceLevel` | lprod:PartRelationship | lprod:ImportanceLevel | **重要性（v0.4 新增）** | 0..1 |
| `lprod:replaceability` | lprod:PartRelationship | lprod:Replaceability | **可替换性（v0.4 新增）** | 0..1 |
| `lprod:assemblyMethod` | lprod:PartRelationship | lprod:AssemblyMethod | **装配方式（v0.4 新增）** | 0..1 |
| `lprod:lifecycleRelation` | lprod:PartRelationship | xsd:string | 生命周期关系描述 | 0..1 |
| `lprod:position` | lprod:PartRelationship | xsd:string | 方位/位置描述 | 0..1 |
| `lprod:isCritical` | lprod:PartRelationship | xsd:boolean | **是否为关键件（v0.4 新增）** | 0..1 |

**PartRole 枚举（v0.4 新增）：**

| 值 | 说明 |
|----|------|
| `lprod:WorkingPart` | 工作件 |
| `lprod:SparePart` | 备用件 |
| `lprod:ReplacementPart` | 替换件 |
| `lprod:OptionalPart` | 选配件 |
| `lprod:StandardPart` | 标准件 |
| `lprod:CustomPart` | 定制件 |
| `lprod:ConsumablePart` | 耗材件 |

**ConnectionType 枚举（v0.4 扩展）：**

| 值 | 说明 |
|----|------|
| `lprod:Welded` | 焊接 |
| `lprod:Bolted` | 螺栓连接 |
| `lprod:Adhesive` | 粘接 |
| `lprod:Electrical` | 电气连接 |
| `lprod:Communication` | 通信连接 |
| `lprod:SnapFit` | 卡扣 |
| `lprod:PressFit` | 压装 |
| `lprod:Threaded` | 螺纹连接 |
| `lprod:Riveted` | 铆接 |
| `lprod:Soldered` | 焊接（电子） |
| `lprod:MechanicalInterlock` | 机械互锁 |
| `lprod:Optical` | 光学连接 |
| `lprod:Fluid` | 流体连接 |

**ImportanceLevel 枚举（v0.4 新增）：**

| 值 | 说明 |
|----|------|
| `lprod:Critical` | 关键件：失效会导致系统失效或安全事故 |
| `lprod:Important` | 重要件：失效会影响性能或寿命 |
| `lprod:Standard` | 一般件：标准部件 |
| `lprod:Optional` | 可选件：不影响基本功能 |

**Replaceability 枚举（v0.4 新增）：**

| 值 | 说明 |
|----|------|
| `lprod:FieldReplaceable` | 现场可更换 |
| `lprod:FactoryReplaceable` | 工厂替换 |
| `lprod:NonReplaceable` | 不可更换 |
| `lprod:Upgradable` | 可升级 |

**AssemblyMethod 枚举（v0.4 新增）：**

| 值 | 说明 |
|----|------|
| `lprod:Sequential` | 顺序装配 |
| `lprod:Parallel` | 并行装配 |
| `lprod:SubAssembly` | 子装配体 |
| `lprod:FinalAssembly` | 总装 |
| `lprod:Modular` | 模块化装配 |

### 5.5 InterfaceRelationship（接口关系）

```
lprod:InterfaceRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lprod:ProductRelationship ;
    rdfs:label "InterfaceRelationship" ;
    rdfs:comment "产品之间的接口关系，表达两个产品之间通过某种接口进行连接或交互。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:interfaceType` | lprod:InterfaceRelationship | lprod:InterfaceType | 接口类型 |
| `lprod:interfaceProtocol` | lprod:InterfaceRelationship | xsd:string | 协议/标准 |
| `lprod:interfaceSpecification` | lprod:InterfaceRelationship | xsd:string | 接口规格描述 |

**InterfaceType 枚举：**

| 值 | 说明 |
|----|------|
| `lprod:MechanicalInterface` | 机械接口 |
| `lprod:ElectricalInterface` | 电气接口 |
| `lprod:CommunicationInterface` | 通信接口 |
| `lprod:OpticalInterface` | 光学接口 |
| `lprod:FluidInterface` | 流体接口 |
| `lprod:ThermalInterface` | 热接口 |

### 5.6 CompatibilityRelationship（兼容关系）

```
lprod:CompatibilityRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lprod:ProductRelationship ;
    rdfs:label "CompatibilityRelationship" ;
    rdfs:comment "产品兼容关系" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:compatibilityType` | lprod:CompatibilityRelationship | lprod:CompatibilityType | 兼容类型 |
| `lprod:isMutual` | lprod:CompatibilityRelationship | xsd:boolean | 是否相互兼容 |

**CompatibilityType 枚举：**

| 值 | 说明 |
|----|------|
| `lprod:ElectricalCompatible` | 电气兼容 |
| `lprod:MechanicalCompatible` | 机械兼容 |
| `lprod:CommunicationCompatible` | 通信兼容 |
| `lprod:SoftwareCompatible` | 软件兼容 |
| `lprod:Interchangeable` | 可互换 |

### 5.7 DependencyRelationship（依赖关系）

```
lprod:DependencyRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lprod:ProductRelationship ;
    rdfs:label "DependencyRelationship" ;
    rdfs:comment "产品之间的依赖关系，表达一个产品的存在或功能依赖于另一个产品。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:dependencyType` | lprod:DependencyRelationship | lprod:DependencyType | 依赖类型 |
| `lprod:isHardDependency` | lprod:DependencyRelationship | xsd:boolean | 是否为硬依赖 |

**DependencyType 枚举：**

| 值 | 说明 |
|----|------|
| `lprod:FunctionalDependency` | 功能依赖 |
| `lprod:StructuralDependency` | 结构依赖 |
| `lprod:OperationalDependency` | 操作依赖 |
| `lprod:SupplyDependency` | 供应依赖 |

### 5.8 AssemblyRelationship（装配关系）

```
lprod:AssemblyRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lprod:ProductRelationship ;
    rdfs:label "AssemblyRelationship" ;
    rdfs:comment "产品装配关系，表达多个部件如何组装成产品。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:assemblySequence` | lprod:AssemblyRelationship | xsd:integer | 装配顺序号 |
| `lprod:assemblyMethod` | lprod:AssemblyRelationship | lprod:AssemblyMethod | 装配方式 |
| `lprod:tolerance` | lprod:AssemblyRelationship | xsd:string | 公差要求 |
| `lprod:requiredTools` | lprod:AssemblyRelationship | xsd:string | 所需工具 |

### 5.9 关系实体化 vs RDF-star 使用规则（v0.4 新增）

在 leleby Product Ontology 中，产品关系的表达有两种模式：

| 模式 | 适用场景 | 示例 |
|------|----------|------|
| **RDF-star 注解** | 简单关系，仅需表达存在性或少量属性 | `<<Car hasPart Wheel>> :confidence 0.95 .` |
| **关系实体化** | 需要表达角色、数量、连接方式、重要性等工程语义 | `:WorkingWheelInstallation a lprod:PartRelationship .` |

**决策规则：**

1. **仅需表达“A 包含 B”**：使用 `hasPart` / `hasConstituent` 快捷关系，可选用 RDF-star 添加简单注解。
2. **需要表达数量、角色、连接方式、重要性、可替换性、装配方式、生命周期关系中的任意一项**：**必须**使用 `PartRelationship` 等实体化关系。
3. **该关系可能被 Requirement 或 Constraint 引用**：**必须**使用实体化关系。
4. **该关系用于 BOM 或工程配置管理**：**必须**使用实体化关系。

**示例对比：**

```
# 简单表达（RDF-star）
<<lprod:Car lprod:hasPart lprod:Wheel>>
    :confidence 0.95 .

# 工程语义表达（实体化）
lprod:Car_Wheel_Installation
    a lprod:PartRelationship ;
    lprod:subjectProduct lprod:Car ;
    lprod:part lprod:Wheel ;
    lprod:partRole lprod:WorkingPart ;
    lprod:cardinality 4 ;
    lprod:connectionType lprod:Bolted ;
    lprod:importanceLevel lprod:Critical ;
    lprod:replaceability lprod:FieldReplaceable .
```


## 6. Product Capability Model（能力模型）

### 6.1 设计思想

v0.3 的关键调整在 v0.4 中保留：
- **关系重命名**：从 `hasCapability` 改为 **`providesCapability`**
- **语义明确**：产品“提供”能力，而非“拥有”能力
- **能力实现**：能力通过产品特征（Feature）实现

### 6.2 关系定义

```
lprod:providesCapability
    rdf:type owl:ObjectProperty ;
    rdfs:domain lprod:Product ;
    rdfs:range lcap:Capability ;
    rdfs:label "providesCapability" ;
    rdfs:comment "产品提供的能力（反向关系：Capability isProvidedBy Product）" .
```

### 6.3 Capability Realization（能力实现）

```
lprod:ProductFeature
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Continuant ;
    rdfs:label "ProductFeature" ;
    rdfs:comment "产品的特征，是能力的实现载体" .
```

**关系：**

```
leleby:Capability
    rdf:type owl:Class ;
    rdfs:label "Capability" ;
    rdfs:comment "能力由产品特征实现" .

lcap:realizedBy
    rdf:type owl:ObjectProperty ;
    rdfs:domain lcap:Capability ;
    rdfs:range lprod:ProductFeature ;
    rdfs:label "realizedBy" .
```


## 7. Product Specification Reference Model（规格引用模型）

### 7.1 设计思想

v0.3 的核心调整在 v0.4 中保留：Product 与 Specification 的关系从“拥有”（hasSpecification）改为“被描述”（describedBy）。

### 7.2 关系定义

```
lprod:describedBy
    rdf:type owl:ObjectProperty ;
    rdfs:domain lprod:Product ;
    rdfs:range lspec:ProductSpecification ;
    rdfs:label "describedBy" ;
    rdfs:comment "产品被某产品规格描述（反向：Specification describes Product）" .
```


## 8. Product Configuration Model（配置模型）

### 8.1 ProductConfiguration

```
leleby-product:ProductConfiguration
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Continuant ;
    rdfs:label "ProductConfiguration" ;
    rdfs:comment "产品配置，代表一个可销售的产品配置变体" .
```

**关系：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:hasConfiguration` | lprod:ProductModel | lprod:ProductConfiguration | 型号有配置 |
| `lprod:includesOption` | lprod:ProductConfiguration | lprod:ProductFeature | 配置包含选配特征 |
| `lprod:configurationName` | lprod:ProductConfiguration | xsd:string | 配置名称 |
| `lprod:configurationCode` | lprod:ProductConfiguration | xsd:string | 配置代码 |


## 9. Product Relationship Model（产品间关系—广义）

### 9.1 ProductVariant（产品变体）

```
leleby-product:ProductVariant
    rdf:type owl:Class ;
    rdfs:subClassOf lprod:ProductModel ;
    rdfs:label "ProductVariant" ;
    rdfs:comment "产品变体，从基础产品派生" .
```

**关系：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:isVariantOf` | lprod:ProductVariant | lprod:ProductModel | 是某产品的变体 |
| `lprod:variantType` | lprod:ProductVariant | xsd:string | 变体类型（功率/颜色/功能） |


## 10. Product Offering Model（商业化提供模型）

### 10.1 ProductOffering

```
leleby-product:ProductOffering
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Continuant ;
    rdfs:label "ProductOffering" ;
    rdfs:comment "产品的商业化提供，表达销售状态、市场区域、服务范围" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:offeringName` | lprod:ProductOffering | xsd:string | 提供名称 |
| `lprod:marketRegion` | lprod:ProductOffering | xsd:string | 市场区域 |
| `lprod:salesStatus` | lprod:ProductOffering | lprod:SalesStatus | 销售状态 |
| `lprod:serviceScope` | lprod:ProductOffering | xsd:string | 服务范围 |

**SalesStatus 枚举：**

| 值 | 说明 |
|----|------|
| `lprod:Active` | 在售 |
| `lprod:Discontinued` | 停产 |
| `lprod:ComingSoon` | 即将上市 |
| `lprod:EndOfLife` | 生命周期结束 |
| `lprod:Seasonal` | 季节性 |

**关系：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:hasOffering` | lprod:ProductModel | lprod:ProductOffering | 型号有商业化提供 |


## 11. Product Lifecycle Model（生命周期模型）

### 11.1 定位说明

Product Lifecycle State 由 **Lifecycle Ontology** 定义。Product Ontology 仅引用状态，不定义状态本身。

**关系：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:hasLifecycleState` | lprod:ProductInstance | llife:LifecycleState | 产品实例的当前生命周期状态 |


## 12. 产品分类与外部映射

### 12.1 分类原则

Product 的分类不是固有属性，而是通过 `ClassificationAssertion` 连接到外部体系。

```
lprod:YD_GK_200W
    lmap:hasClassificationAssertion [
        a lmap:ClassificationAssertion ;
        lmap:classificationSystem lmap:GS1System ;
        lmap:classCode "31401234" ;
        lmap:className "Lighting Equipment" ;
        lmap:mappingType lmap:exactMatch
    ] .
```

### 12.2 支持的外部体系

| 体系 | 用途 |
|------|------|
| GS1 GPC | 商业产品分类 |
| HS Code | 海关贸易分类 |
| eCl@ss | 工业产品分类 |
| UNSPSC | 采购分类 |
| schema.org | Web 语义 |


## 13. 与其他 Ontology 的边界与关系（v0.4 更新）

### 13.1 关系总图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Product Ontology 与其他模块的关系（v0.4 冻结）          │
│                                                                             │
│  Enterprise Ontology                                                       │
│         │                                                                  │
│         │  provides / produces                                             │
│         ▼                                                                  │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║                       Product Ontology                                ║ │
│  ║  Product / ProductType / ProductModel / ProductInstance               ║ │
│  ║  providesCapability / describedBy / hasRelationship                   ║ │
│  ║  PartRelationship / InterfaceRelationship / ...                      ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│         │                    │                          │                │
│         │                    │                          │                │
│         ▼                    ▼                          ▼                │
│  Capability Ontology  Specification Ontology     （商业化视图）           │
│  （providesCapability） （describedBy）          ProductOffering          │
│         │                    │                          │                │
│         │                    │                          │                │
│         │                    ▼                          │                │
│         │           Verification Ontology               │                │
│         │           （验证产品规格是否满足要求）         │                │
│         │                    │                          │                │
│         │                    ▼                          │                │
│         │           Compliance Ontology                 │                │
│         │           （符合性判断）                       │                │
│         │                    │                          │                │
│         │                    ▼                          │                │
│         │           Decision Ontology                   │                │
│         │           （决策与行动）                       │                │
│         │                                                │                │
│         └────────────────────────────────────────────────┘                │
│                                                                             │
│  ════════ 边界明确：Product 不直接连接 Requirement、Compliance、Decision ════ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 跨模块关系汇总

| Product 侧 | 目标模块 | 目标概念 | 说明 |
|-----------|----------|----------|------|
| `Enterprise provides Product` | Enterprise | Enterprise | 企业提供产品 |
| `Product providesCapability` | Capability | Capability | 产品提供能力 |
| `Product describedBy` | Specification | ProductSpecification | 产品被规格描述 |
| `Product hasIdentifier` | Core | Identifier | 产品有标识符 |
| `Product hasLifecycleState` | Lifecycle | LifecycleState | 产品有生命周期状态 |
| `Product hasClassificationAssertion` | Mapping | ClassificationAssertion | 产品有分类断言 |

### 13.3 Product 不直接连接的内容（v0.4 强制声明）

| 被禁止的关系 | 原因 | 正确替代链路 |
|-------------|------|-------------|
| Product → Requirement | Product 不定义要求 | Requirement → Capability → Product 或 Requirement → Specification → Product |
| Product → Compliance | Product 不判断符合性 | Product → Specification → Verification → Compliance |
| Product → Decision | Product 不做决策 | Compliance → Decision → Action |

### 13.4 与 Requirement Ontology 的接口（v0.4 新增）

**重要：** Requirement 不直接约束 Product 本身，而是约束 Product 的**语义元素**，包括：

1. **ProductFeature**（产品特征）
2. **ProductRelationship**（产品关系，如 PartRelationship）
3. **ProductCapability**（产品能力）
4. **ProductSpecification**（产品规格）

**示例：标准要求“车辆必须具有四个工作轮胎”**

```
# Requirement 指向 PartRelationship
lbo-req:REQ_WorkingWheel_004
    a lbo-req:Requirement ;
    rdfs:label "车辆必须具有四个工作轮胎" ;
    lbo-req:hasSemanticTarget lbo-req:Target_WorkingWheel .

lbo-req:Target_WorkingWheel
    a lbo-req:StructureRelationTarget ;
    lbo-req:targetRelationshipType lprod:PartRelationship ;
    lbo-req:requiredCardinality 4 ;
    lbo-req:requiredRole lprod:WorkingPart .
```

**关键：** Requirement 不直接说“Vehicle 必须有 4 个 Wheel”，而是说“Vehicle 与 Wheel 之间必须存在 4 个 WorkingPart 角色关系的实例”。


## 14. SHACL 验证约束（v0.4 更新）

### 14.1 Product 基础约束

```turtle
lprod:ProductShape
    a sh:NodeShape ;
    sh:targetClass lprod:Product ;
    sh:property [
        sh:path lprod:hasProductName ;
        sh:minCount 1 ;
        sh:message "Product must have a product name" ;
    ] .
```

### 14.2 ProductModel 约束

```turtle
lprod:ProductModelShape
    a sh:NodeShape ;
    sh:targetClass lprod:ProductModel ;
    sh:property [
        sh:path lprod:hasModelNumber ;
        sh:minCount 1 ;
        sh:message "ProductModel must have a model number" ;
    ] ;
    sh:property [
        sh:path lprod:hasProductType ;
        sh:minCount 1 ;
        sh:message "ProductModel must have a product type" ;
    ] .
```

### 14.3 PartRelationship 约束（v0.4 新增）

```turtle
lprod:PartRelationshipShape
    a sh:NodeShape ;
    sh:targetClass lprod:PartRelationship ;
    sh:property [
        sh:path lprod:subjectProduct ;
        sh:minCount 1 ;
        sh:message "PartRelationship must have a subject product" ;
    ] ;
    sh:property [
        sh:path lprod:part ;
        sh:minCount 1 ;
        sh:message "PartRelationship must have a part" ;
    ] ;
    sh:property [
        sh:path lprod:cardinality ;
        sh:minCount 0 ;
        sh:message "PartRelationship may have cardinality" ;
    ] ;
    sh:property [
        sh:path lprod:partRole ;
        sh:minCount 0 ;
        sh:message "PartRelationship may have a part role" ;
    ] .
```

### 14.4 ProductRelationship 基类约束（v0.4 新增）

```turtle
lprod:ProductRelationshipShape
    a sh:NodeShape ;
    sh:targetClass lprod:ProductRelationship ;
    sh:property [
        sh:path lprod:subjectProduct ;
        sh:minCount 1 ;
        sh:message "ProductRelationship must have a subject product" ;
    ] ;
    sh:property [
        sh:path lprod:objectProduct ;
        sh:minCount 1 ;
        sh:message "ProductRelationship must have an object product" ;
    ] ;
    sh:property [
        sh:path lprod:relationshipType ;
        sh:minCount 1 ;
        sh:message "ProductRelationship must have a relationship type" ;
    ] .
```


## 15. 完整示例：云达照明（v0.4 更新）

### 15.1 企业信息

```ttl
leleby:YundaLighting
    a leleby:Enterprise ;
    leleby:legalName "云达照明科技有限公司" .
```

### 15.2 产品类型与型号

```ttl
# 产品类型
lprod:OutdoorLampType
    a lprod:ProductType ;
    lprod:hasProductName "户外LED灯具" .

# 产品型号
lprod:YD_GK_200W
    a lprod:ProductModel ;
    lprod:hasProductName "LED 户外工矿灯" ;
    lprod:hasModelNumber "YD-GK-200W" ;
    lprod:hasProductType lprod:OutdoorLampType ;
    lprod:providedBy leleby:YundaLighting ;
    lprod:producedBy leleby:YundaLighting .
```

### 15.3 产品结构关系（v0.4 使用 PartRelationship）

```ttl
# 快捷关系（简单表达）
lprod:YD_GK_200W
    lprod:hasPart lprod:YD_LEDModule .

# 工程语义关系（实体化）
lprod:LEDModule_Installation
    a lprod:PartRelationship ;
    lprod:subjectProduct lprod:YD_GK_200W ;
    lprod:part lprod:YD_LEDModule ;
    lprod:partRole lprod:WorkingPart ;
    lprod:cardinality 4 ;
    lprod:connectionType lprod:Electrical ;
    lprod:importanceLevel lprod:Critical ;
    lprod:replaceability lprod:FieldReplaceable ;
    lprod:assemblyMethod lprod:Modular ;
    lprod:position "均匀分布在灯具底部" .
```

### 15.4 产品能力

```ttl
# 产品提供能力
lprod:YD_GK_200W
    lprod:providesCapability lcap:ColdTemperatureOperationCapability .

# 能力实现
lcap:ColdTemperatureOperationCapability
    a lcap:Capability ;
    lcap:realizedBy lprod:ThermalDesignFeature .
```

### 15.5 产品规格引用

```ttl
lprod:YD_GK_200W
    lprod:describedBy lspec:Spec_YD_GK_200W_v1 .
```

### 15.6 产品配置

```ttl
lprod:YD_GK_200W
    lprod:hasConfiguration lprod:Config_YD_200W .

lprod:Config_YD_200W
    a lprod:ProductConfiguration ;
    lprod:configurationName "200W标准配置" ;
    lprod:includesOption lprod:Feature_200W_Power .
```

### 15.7 商业化提供

```ttl
lprod:YD_GK_200W
    lprod:hasOffering lprod:Offering_YD_Global .

lprod:Offering_YD_Global
    a lprod:ProductOffering ;
    lprod:offeringName "全球销售" ;
    lprod:marketRegion "Global" ;
    lprod:salesStatus lprod:Active .
```

### 15.8 产品实例

```ttl
lprod:YD_GK_200W_SN2026001
    a lprod:ProductInstance ;
    lprod:instanceOfModel lprod:YD_GK_200W ;
    lprod:hasSerialNumber "SN-2026-001" ;
    lprod:manufacturedDate "2026-07-15"^^xsd:date .
```

### 15.9 Requirement 约束产品关系示例（v0.4 新增）

```ttl
# Requirement Ontology 中定义
lbo-req:REQ_WorkingWheel_004
    a lbo-req:Requirement ;
    rdfs:label "车辆必须具有四个工作轮胎" ;
    lbo-req:hasSemanticTarget lbo-req:Target_WorkingWheel .

lbo-req:Target_WorkingWheel
    a lbo-req:StructureRelationTarget ;
    lbo-req:targetRelationshipType lprod:PartRelationship ;
    lbo-req:requiredCardinality 4 ;
    lbo-req:requiredRole lprod:WorkingPart ;
    lbo-req:requiredConnectionType lprod:Bolted .
```


## 16. 核心类汇总

### 16.1 Classes

| 类名 | 父类 | 说明 |
|------|------|------|
| `lprod:Product` | leleby:Continuant | 产品抽象根类 |
| `lprod:ProductType` | leleby:Continuant | 产品类别 |
| `lprod:ProductModel` | leleby:Continuant | 产品型号 |
| `lprod:ProductInstance` | leleby:Continuant | 产品个体 |
| `lprod:ProductIdentifier` | leleby:Identifier | 产品标识符 |
| `lprod:ProductRelationship` | leleby:Relationship | **产品关系抽象基类（v0.4 新增）** |
| `lprod:PartRelationship` | lprod:ProductRelationship | **部件关系（v0.4 新增）** |
| `lprod:InterfaceRelationship` | lprod:ProductRelationship | **接口关系（v0.4 新增）** |
| `lprod:CompatibilityRelationship` | lprod:ProductRelationship | **兼容关系（v0.4 新增）** |
| `lprod:DependencyRelationship` | lprod:ProductRelationship | **依赖关系（v0.4 新增）** |
| `lprod:AssemblyRelationship` | lprod:ProductRelationship | **装配关系（v0.4 新增）** |
| `lprod:ProductFeature` | leleby:Continuant | 产品特征 |
| `lprod:ProductConfiguration` | leleby:Continuant | 产品配置 |
| `lprod:ProductVariant` | lprod:ProductModel | 产品变体 |
| `lprod:ProductOffering` | leleby:Continuant | 商业化提供 |

### 16.2 Object Properties

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lprod:hasProductType` | lprod:ProductModel | lprod:ProductType | 型号属于类型 |
| `lprod:hasModel` | lprod:Product | lprod:ProductModel | 有关联型号 |
| `lprod:hasInstance` | lprod:ProductModel | lprod:ProductInstance | 型号有实例 |
| `lprod:instanceOfModel` | lprod:ProductInstance | lprod:ProductModel | 实例属于型号 |
| `lprod:providesCapability` | lprod:Product | lcap:Capability | 提供能力 |
| `lprod:describedBy` | lprod:Product | lspec:ProductSpecification | 被规格描述 |
| `lprod:hasPart` | lprod:Product | lprod:Product | **包含部件（快捷关系）** |
| `lprod:hasConstituent` | lprod:Product | lprod:Product | **物质组成（快捷关系）** |
| `lprod:hasRelationship` | lprod:Product | lprod:ProductRelationship | **产品关系（v0.4 新增）** |
| `lprod:hasConfiguration` | lprod:ProductModel | lprod:ProductConfiguration | 有配置 |
| `lprod:hasOffering` | lprod:ProductModel | lprod:ProductOffering | 有商业化提供 |
| `lprod:isVariantOf` | lprod:ProductVariant | lprod:ProductModel | 是变体 |
| `lprod:providedBy` | lprod:Product | leleby:Organization | 由组织提供 |
| `lprod:producedBy` | lprod:Product | leleby:Organization | 由组织生产 |


## 17. 版本变更记录

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v0.1 | 2026-07-28 | 初始版本 |
| v0.2 | 2026-07-28 | 本体精炼版：三层模型、结构断言、Capability外置 |
| v0.3 | 2026-07-28 | 核心冻结版：三元模型；hasCapability → providesCapability；hasSpecification → describedBy；ProductConfiguration；ProductOffering；ProductFeature；边界声明 |
| **v0.4** | **2026-08-04** | **关系增强版：1) ProductStructureAssertion 升级为 ProductRelationship 基类体系；2) 新增 PartRelationship 承载角色、数量、连接、重要性、可替换性、装配方式等工程语义；3) 新增 InterfaceRelationship、CompatibilityRelationship、DependencyRelationship、AssemblyRelationship；4) hasPart 重新定位为快捷关系；5) 明确 RDF-star 使用规则；6) 新增与 Requirement Ontology 接口，支持 Requirement 约束 ProductRelationship；7) 扩展 ConnectionType、新增 ImportanceLevel、Replaceability、AssemblyMethod 枚举；8) 更新所有示例和 SHACL 约束** |


*— leleby Product Ontology Specification v0.4 — Relationship Enhancement Release —*