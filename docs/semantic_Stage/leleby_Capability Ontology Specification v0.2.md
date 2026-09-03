# leleby Capability Ontology Specification v0.2

**文档版本：** v0.2 — Capability Model Alignment Edition（能力模型对齐版）

**文档类型：** 模块本体规范（Module Ontology Specification）

**文档状态：** ⚠️ **候选冻结（Candidate Freeze）** — 核心概念与顶层结构已稳定，待实践验证后正式冻结

**依赖架构：** leleby Ontology Architecture Specification v0.9

**依赖模块：** Core Ontology Specification v0.1 | Product Ontology Specification v0.3 | Requirement Ontology Specification v0.3

**对齐模块：** Specification Ontology | Verification Ontology | Measurement Ontology | Evidence Ontology | Compliance Ontology | Decision Ontology

**命名空间：** `https://ontology.leleby.org/v0.9/capability/`

**推荐前缀：** `lcap`

**目标受众：** 本体工程师、企业语义建模工程师、AI Agent 开发者、PLM/ERP/CRM 系统集成商、企业架构师


## 1. 引言

### 1.1 目的

leleby Capability Ontology 是 leleby 语义基础设施中的**能力语义层（Capability Semantic Layer）**。它定义了：

- 企业、组织、产品、服务或系统能够执行某种功能、提供某种价值的语义表达
- 能力与需求的对齐关系
- 能力与产品的实现关系
- 能力之间的组成和依赖关系
- 能力的参数化表达（基于 NIST 制造能力模型）
- 能力的企业架构分层（基于 Enterprise Capability Model）

**核心定位：**

> Capability Ontology 是连接企业商业能力、产品能力和客户需求的语义桥梁。如果 Requirement 是“市场需要什么”，Capability 就是“企业能够提供什么”；Product 是“哪个具体对象实现这种能力”；Specification 是“如何用参数描述这种能力”。

### 1.2 v0.2 升级说明

v0.2 基于 v0.1 进行了全面升级，融入了以下外部资源的核心思想：

| 资源 | 核心贡献 | 融入方式 |
|------|----------|----------|
| **NIST Model-Based Manufacturing Capability Definition** | 能力是动态的、可测量的、可控制的；能力需在不同抽象层次描述以支持不同决策上下文；能力需通过参数、约束、资源表达 | 新增 `CapabilityParameter`、`CapabilityConstraint`、`CapabilityResource`；强化 `Capability` 的“动态可测量”语义 |
| **Enterprise Capability Model（Creately）** | 能力是组织“做什么”的稳定抽象，独立于“如何做、谁做、在哪做”；能力分层组织（Level 1–3）；能力需以业务友好语言表达 | 新增 `CapabilityHierarchy`；引入“企业能力层”与“产品能力层”分离；强化 `Capability` 的业务语义 |
| **SAP Enterprise Architecture Framework** | 能力是企业架构中的稳定抽象层；能力与流程、应用、技术分层映射；能力支持战略对齐和投资决策 | 新增 `CapabilityStatus`（Active/Deprecated/Planned）；增加能力生命周期和治理语义 |
| **BFO（Basic Formal Ontology）** | Capability 是 Disposition 的特殊类型——一种潜在倾向，在特定条件下通过过程实现；Capability 介于 Function 和 Disposition 之间 | 强化 `Capability` 作为 `Disposition` 子类的哲学基础；明确 Capability 与 Function 的关系 |

**核心升级点：**

1. **Capability 哲学基础强化**：明确 Capability 是 BFO Disposition 的特殊化——一种可由 Agent 拥有的潜在倾向
2. **能力参数化模型**：新增 `CapabilityParameter`，支持类似 NIST 的制造能力参数表达
3. **企业架构分层**：区分“企业能力层”与“产品能力层”，支持企业 AI 商业名片
4. **能力生命周期**：新增能力状态（Active / Deprecated / Planned），支持能力治理
5. **能力层次结构**：支持能力的分层组织（Level 1–3 或更深）

### 1.3 Capability 与 BFO Disposition 的关系（v0.2 明确）

在 BFO（Basic Formal Ontology）中，**Disposition** 被定义为：

> 一种在特定条件下通过特定过程实现的潜在倾向。

**Capability 是 Disposition 的特殊化**：与一般 Disposition 不同，Capability 要求存在一个 Agent（组织、系统或个人）对该能力的实现具有利益。与 Function 不同，Capability 的实现不是其存在的主要理由。

因此，leleby 中：

```
leleby:Disposition（BFO 对齐）
    │
    │  subClassOf（特殊化）
    ▼
leleby:Capability（leleby 定义）
    │
    │  requires
    ▼
leleby:Agent（拥有能力的实体）
```

**BFO 对齐：**
> `lcap:Capability` `skos:closeMatch` `bfo:Disposition`（特殊化关系）

### 1.4 在 leleby 架构中的位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Capability Ontology 在架构中的位置                      │
│                                                                             │
│  Requirement Ontology                                                       │
│  （市场/客户/标准需要什么能力）                                             │
│         │                                                                  │
│         │  requiresCapability                                              │
│         ▼                                                                  │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Capability Ontology                                                  ║ │
│  ║  （企业/产品能够提供什么能力）                                         ║ │
│  ║  企业能力层（Enterprise Capability Model）                            ║ │
│  ║  产品能力层（Product Capability Model）                               ║ │
│  ║  能力参数层（NIST Manufacturing Capability Parameters）               ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│         │                                                                  │
│         │  realizedBy / providesCapability                                 │
│         ▼                                                                  │
│  Product Ontology                                                          │
│  （哪个产品实现这种能力）                                                  │
│         │                                                                  │
│         │  describedBy                                                     │
│         ▼                                                                  │
│  Specification Ontology                                                    │
│  （能力如何用参数描述）                                                    │
│         │                                                                  │
│         │  verifiedBy                                                      │
│         ▼                                                                  │
│  Verification & Measurement & Evidence                                    │
│  （能力是否被验证）                                                        │
│         │                                                                  │
│         ▼                                                                  │
│  Compliance & Decision                                                     │
│  （能力是否满足需求）                                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 2. 设计原则

### 2.1 能力是潜在倾向原则（v0.2 强化）

> **Capability 是 BFO Disposition 的特殊化——一种可由 Agent 拥有的潜在倾向**。它不是行为本身，而是在特定条件下通过过程实现的潜在能力。

**BFO 对齐：**
> Capability 继承自 Disposition，在特定条件下通过过程实现。

### 2.2 能力独立于实现原则

> **同一种能力可以由不同的产品、技术路线或服务方式实现。**

### 2.3 能力必须可验证原则

> **能力必须能够通过测量、测试或评估被验证。** 不可验证的能力对 AI 没有语义价值。

### 2.4 能力有上下文原则

> **能力不是绝对存在的。** 能力总是在特定条件、环境或上下文中才有效。

### 2.5 能力可组合原则

> **复杂能力可以由多个简单能力组合而成。**

### 2.6 能力是企业架构的稳定层原则（v0.2 新增）

> **能力是企业“做什么”的稳定抽象，独立于“如何做、谁做、在哪做”**。即使流程、系统、人员发生变化，能力依然保持稳定。

### 2.7 能力可分层原则（v0.2 新增）

> **能力应在不同抽象层次上描述，以支持不同的决策上下文**。从高层业务能力到详细技术能力，形成层次结构。

### 2.8 能力可参数化原则（v0.2 新增）

> **能力应通过可测量的参数（Parameters）进行量化表达**，以支持 AI 的能力比较和匹配。


## 3. 核心概念模型

### 3.1 能力六要素模型（v0.2 扩展）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Capability 六要素模型（v0.2）                           │
│                                                                             │
│  1. Function（功能）                                                       │
│  能力执行什么功能？                                                        │
│  示例："提供照明"                                                          │
│                                                                             │
│  2. Parameter（参数）—— v0.2 强化                                          │
│  能力的量化参数是什么？                                                    │
│  示例："温度范围：-40℃ ~ 70℃；精度：±0.01mm"                            │
│                                                                             │
│  3. Constraint（约束）—— v0.2 强化                                          │
│  能力的边界限制是什么？                                                    │
│  示例："材料：铝合金；工件尺寸 ≤ 500mm"                                   │
│                                                                             │
│  4. Condition（条件）                                                      │
│  能力在什么条件下有效？                                                    │
│  示例："-40℃ ~ 70℃ 环境"                                                  │
│                                                                             │
│  5. Resource（资源）—— v0.2 新增                                           │
│  能力需要什么资源支撑？                                                    │
│  示例："CNC 机床；熟练操作工"                                              │
│                                                                             │
│  6. Level（等级）                                                          │
│  能力的成熟度或等级是什么？                                                │
│  示例："Level 3: Mass Production"                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心关系链（v0.2 强化）

```
Requirement（需求）
    │
    │  requiresCapability
    ▼
Capability（能力）
    │
    ├── hasFunction（功能）
    ├── hasParameter（参数）—— v0.2 新增
    ├── hasConstraint（约束）—— v0.2 强化
    ├── applicableUnder（条件）
    ├── requiresResource（资源）—— v0.2 新增
    ├── hasLevel（等级）
    ├── hasCapabilityStatus（状态）—— v0.2 新增
    │
    │  realizedBy（被实现）
    ▼
Product / Service（产品/服务）
    │
    │  describedBy
    ▼
Specification（规格）
```


## 4. 核心类定义

### 4.1 Capability（能力）

```
leleby-capability:Capability
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Disposition ;
    rdfs:label "Capability" ;
    rdfs:comment "一种可由 Agent 拥有的潜在倾向（BFO Disposition 的特殊化），能够在特定条件下通过资源、过程或产品实现某种功能或价值。" .
```

**v0.2 语义强化：**

Capability 是 **BFO Disposition 的特殊化**——一种可由 Agent（组织、系统或个人）拥有的潜在倾向，在特定条件下通过特定过程实现。

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `lcap:capabilityIdentifier` | lcap:Capability | xsd:string | 能力标识符 | 1 |
| `lcap:capabilityName` | lcap:Capability | xsd:string | 能力名称（业务友好语言） | 1 |
| `lcap:capabilityDescription` | lcap:Capability | xsd:string | 能力描述 | 0..1 |
| `lcap:hasCapabilityType` | lcap:Capability | lcap:CapabilityType | 能力类型 | 0..1 |
| `lcap:hasCapabilityLevel` | lcap:Capability | lcap:CapabilityLevel | 能力等级 | 0..1 |
| `lcap:hasCapabilityStatus` | lcap:Capability | lcap:CapabilityStatus | 能力状态（v0.2 新增） | 0..1 |
| `lcap:capabilityOwner` | lcap:Capability | leleby:Agent | 能力拥有者 | 0..1 |

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `lcap:hasFunction` | lcap:Capability | lcap:Function | 执行的功能 | 0..1 |
| `lcap:hasParameter` | lcap:Capability | lcap:CapabilityParameter | 能力的量化参数（v0.2 新增） | 0..n |
| `lcap:hasConstraint` | lcap:Capability | lcap:CapabilityConstraint | 能力的约束限制（v0.2 强化） | 0..n |
| `lcap:applicableUnder` | lcap:Capability | leleby:Condition | 适用的条件 | 0..n |
| `lcap:requiresResource` | lcap:Capability | lcap:CapabilityResource | 所需资源（v0.2 新增） | 0..n |
| `lcap:realizedBy` | lcap:Capability | leleby:Product | 被产品实现 | 0..n |
| `lcap:providedBy` | lcap:Capability | leleby:Organization | 由组织提供 | 0..n |
| `lcap:verifiedBy` | lcap:Capability | lver:VerificationResult | 被验证 | 0..n |
| `lcap:satisfiesRequirement` | lcap:Capability | lreq:Requirement | 满足的需求 | 0..n |
| `lcap:hasSubCapability` | lcap:Capability | lcap:Capability | 子能力（层次结构） | 0..n |

### 4.2 CapabilityType（能力类型）

```
leleby-capability:CapabilityType
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity ;
    rdfs:label "CapabilityType" ;
    rdfs:comment "能力的分类类型。" .
```

**预定义类型（v0.2 扩展）：**

| 类型 | 说明 | 示例 |
|------|------|------|
| `lcap:EnterpriseCapability` | 企业级能力（战略层） | "全球供应能力"、"研发能力" |
| `lcap:BusinessCapability` | 业务能力（运营层） | "客户管理能力"、"订单处理能力" |
| `lcap:FunctionalCapability` | 功能能力 | "提供照明"、"提供通信" |
| `lcap:PerformanceCapability` | 性能能力 | "高效率"、"长寿命" |
| `lcap:TechnicalCapability` | 技术能力 | "IP防护"、"热管理" |
| `lcap:EnvironmentalCapability` | 环境适应能力 | "低温运行"、"盐雾耐受" |
| `lcap:ManufacturingCapability` | 制造能力 | "批量生产"、"精密加工" |
| `lcap:ServiceCapability` | 服务能力 | "安装服务"、"远程监控" |
| `lcap:OrganizationalCapability` | 组织能力 | "研发能力"、"质量控制" |

### 4.3 CapabilityStatus（能力状态）— v0.2 新增

```
leleby-capability:CapabilityStatus
    rdf:type owl:Class ;
    rdfs:label "CapabilityStatus" ;
    rdfs:comment "能力的生命周期状态，支持能力治理。" .
```

**预定义状态：**

| 值 | 说明 |
|----|------|
| `lcap:Active` | 当前有效 |
| `lcap:Deprecated` | 已废弃（不再推荐使用） |
| `lcap:Planned` | 规划中（尚未实现） |
| `lcap:InDevelopment` | 开发中 |
| `lcap:Suspended` | 暂停 |

### 4.4 Function（功能）

```
leleby-capability:Function
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity ;
    rdfs:label "Function" ;
    rdfs:comment "能力执行的功能。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lcap:functionIdentifier` | lcap:Function | xsd:string | 功能标识符 |
| `lcap:functionName` | lcap:Function | xsd:string | 功能名称 |
| `lcap:functionDescription` | lcap:Function | xsd:string | 功能描述 |

### 4.5 CapabilityParameter（能力参数）— v0.2 新增

```
leleby-capability:CapabilityParameter
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity ;
    rdfs:label "CapabilityParameter" ;
    rdfs:comment "能力的量化参数，支持能力的精确表达和比较（参考 NIST 制造能力模型）。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `lcap:parameterName` | lcap:CapabilityParameter | xsd:string | 参数名称 | 1 |
| `lcap:parameterValue` | lcap:CapabilityParameter | leleby:QuantityValue | 参数值 | 1 |
| `lcap:parameterType` | lcap:CapabilityParameter | lcap:ParameterType | 参数类型 | 0..1 |
| `lcap:parameterDescription` | lcap:CapabilityParameter | xsd:string | 参数描述 | 0..1 |

**ParameterType 枚举：**

| 值 | 说明 |
|----|------|
| `lcap:Range` | 范围参数（如：-40℃ ~ 70℃） |
| `lcap:Minimum` | 最小值参数（如：精度 ≥ 0.01mm） |
| `lcap:Maximum` | 最大值参数（如：功率 ≤ 200W） |
| `lcap:Typical` | 典型值参数（如：光效 150 lm/W） |
| `lcap:Statistical` | 统计参数（如：均值、标准差） |

### 4.6 CapabilityConstraint（能力约束）— v0.2 强化

```
leleby-capability:CapabilityConstraint
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Constraint ;
    rdfs:label "CapabilityConstraint" ;
    rdfs:comment "能力的边界限制（参考 NIST 制造能力模型中的约束表达）。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lcap:constraintType` | lcap:CapabilityConstraint | lcap:ConstraintType | 约束类型 |
| `lcap:constraintValue` | lcap:CapabilityConstraint | leleby:QuantityValue | 约束值 |
| `lcap:constraintDescription` | lcap:CapabilityConstraint | xsd:string | 约束描述 |

**ConstraintType 枚举：**

| 值 | 说明 |
|----|------|
| `lcap:MaterialConstraint` | 材料约束（如：仅限铝合金） |
| `lcap:SizeConstraint` | 尺寸约束（如：工件 ≤ 500mm） |
| `lcap:QuantityConstraint` | 数量约束（如：批量 ≥ 1000） |
| `lcap:AccuracyConstraint` | 精度约束（如：公差 ±0.01mm） |
| `lcap:GeographicConstraint` | 地理约束（如：仅限亚洲） |
| `lcap:RegulatoryConstraint` | 法规约束（如：符合 RoHS） |

### 4.7 CapabilityResource（能力资源）— v0.2 新增

```
leleby-capability:CapabilityResource
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity ;
    rdfs:label "CapabilityResource" ;
    rdfs:comment "能力所需的资源（参考 NIST 制造能力模型中的资源依赖）。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lcap:resourceIdentifier` | lcap:CapabilityResource | xsd:string | 资源标识符 |
| `lcap:resourceName` | lcap:CapabilityResource | xsd:string | 资源名称 |
| `lcap:resourceType` | lcap:CapabilityResource | lcap:ResourceType | 资源类型 |
| `lcap:resourceQuantity` | lcap:CapabilityResource | leleby:QuantityValue | 资源数量 |

**ResourceType 枚举：**

| 值 | 说明 |
|----|------|
| `lcap:Equipment` | 设备 |
| `lcap:Tool` | 工具 |
| `lcap:Material` | 材料 |
| `lcap:Personnel` | 人员 |
| `lcap:Software` | 软件 |
| `lcap:Facility` | 设施 |
| `lcap:Information` | 信息 |

### 4.8 CapabilityLevel（能力等级）

```
leleby-capability:CapabilityLevel
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity ;
    rdfs:label "CapabilityLevel" ;
    rdfs:comment "能力的成熟度或等级。" .
```

**预定义等级（制造能力示例）：**

| 等级 | 说明 |
|------|------|
| `lcap:Level1_Prototype` | 样机/原型能力 |
| `lcap:Level2_Pilot` | 小批量试产 |
| `lcap:Level3_MassProduction` | 批量生产 |
| `lcap:Level4_GlobalSupply` | 全球供应 |

**预定义等级（技术能力示例）：**

| 等级 | 说明 |
|------|------|
| `lcap:Level1_Basic` | 基础能力 |
| `lcap:Level2_Intermediate` | 中级能力 |
| `lcap:Level3_Advanced` | 高级能力 |
| `lcap:Level4_Expert` | 专家级能力 |


## 5. Capability 分类与层次结构（v0.2 新增）

### 5.1 设计思想

基于 Enterprise Capability Model，能力应在不同抽象层次上组织。leleby 区分两个主要层次：

| 层次 | 说明 | 示例 |
|------|------|------|
| **企业能力层** | 组织层面的战略能力，独立于具体实现 | "全球供应链管理"、"产品创新" |
| **产品能力层** | 产品层面的具体能力，可被产品实现 | "低温运行能力"、"IP66防护" |

### 5.2 能力层次关系

```
Enterprise Capability（企业能力层）
    │
    │  hasSubCapability
    ▼
Business Capability（业务能力层）
    │
    │  hasSubCapability
    ▼
Product Capability（产品能力层）
    │
    │  hasSubCapability
    ▼
Technical Capability（技术能力层）
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lcap:hasSubCapability` | lcap:Capability | lcap:Capability | 子能力（支持递归层次结构） |
| `lcap:capabilityLevel` | lcap:Capability | xsd:integer | 能力层级（1-4） |

### 5.3 示例：企业能力层次

```
Yunda Lighting Enterprise Capability（企业层）
    │
    ├── Product Development Capability（业务层）
    │   ├── Optical Design Capability（产品层）
    │   └── Thermal Management Capability（产品层）
    │
    ├── Manufacturing Capability（业务层）
    │   ├── CNC Machining Capability（产品层）
    │   │   └── 5-axis Machining Capability（技术层）
    │   └── Assembly Capability（产品层）
    │
    └── Supply Chain Capability（业务层）
        └── Global Logistics Capability（产品层）
```


## 6. Capability 参数化模型（v0.2 新增）

### 6.1 设计思想

基于 NIST 的 Model-Based Manufacturing Capability Definition，制造能力需要被定义、测量和控制。这要求能力通过可量化的参数表达。

### 6.2 参数化结构

```
Capability（能力）
    │
    │  hasParameter（0..n）
    ▼
CapabilityParameter（能力参数）
    │
    ├── parameterName（参数名称）
    ├── parameterValue（参数值：QuantityValue）
    ├── parameterType（参数类型：Range/Min/Max/Typical/Statistical）
    └── parameterDescription（参数描述）
```

### 6.3 示例：精密加工能力参数化

```
lcap:PrecisionMachiningCapability
    a lcap:ManufacturingCapability ;
    lcap:hasParameter [
        a lcap:CapabilityParameter ;
        lcap:parameterName "加工精度" ;
        lcap:parameterValue [
            leleby:hasNumericValue "0.005"^^xsd:double ;
            leleby:hasUnit leleby:Millimeter
        ] ;
        lcap:parameterType lcap:Typical
    ] ;
    lcap:hasParameter [
        a lcap:CapabilityParameter ;
        lcap:parameterName "最大工件尺寸" ;
        lcap:parameterValue [
            leleby:hasNumericValue "500"^^xsd:double ;
            leleby:hasUnit leleby:Millimeter
        ] ;
        lcap:parameterType lcap:Maximum
    ] .
```


## 7. Capability 资源模型（v0.2 新增）

### 7.1 设计思想

基于 NIST 制造能力模型，能力需要资源支撑（设备、工具、材料、人员等）。leleby 通过 `requiresResource` 关系表达这种依赖。

### 7.2 资源模型结构

```
Capability（能力）
    │
    │  requiresResource（0..n）
    ▼
CapabilityResource（能力资源）
    │
    ├── resourceIdentifier（资源标识符）
    ├── resourceName（资源名称）
    ├── resourceType（资源类型：Equipment/Tool/Material/Personnel/Software/Facility/Information）
    └── resourceQuantity（资源数量）
```

### 7.3 示例：制造能力与资源

```
lcap:CNCMachiningCapability
    a lcap:ManufacturingCapability ;
    lcap:requiresResource [
        a lcap:CapabilityResource ;
        lcap:resourceIdentifier "RES-CNC-001" ;
        lcap:resourceName "5轴CNC加工中心" ;
        lcap:resourceType lcap:Equipment ;
        lcap:resourceQuantity [
            leleby:hasNumericValue "5"^^xsd:double ;
            leleby:hasUnit leleby:Unit
        ]
    ] ;
    lcap:requiresResource [
        a lcap:CapabilityResource ;
        lcap:resourceIdentifier "RES-OP-001" ;
        lcap:resourceName "CNC操作员" ;
        lcap:resourceType lcap:Personnel ;
        lcap:resourceQuantity [
            leleby:hasNumericValue "10"^^xsd:double ;
            leleby:hasUnit leleby:Unit
        ]
    ] .
```


## 8. Capability Ontology 与其他模块的连接

### 8.1 连接关系总表（v0.2 扩展）

| 源模块 | 目标模块 | 关系 | 说明 |
|--------|----------|------|------|
| Requirement | Capability | `requiresCapability` | 需求要求能力 |
| Capability | Requirement | `satisfiesRequirement` | 能力满足需求 |
| Product | Capability | `providesCapability` | 产品提供能力 |
| Capability | Product | `realizedBy` | 能力被产品实现 |
| Capability | Specification | `hasSpecification` | 能力有规格描述 |
| Capability | Verification | `verifiedBy` | 能力被验证 |
| Capability | Evidence | `supportedBy` | 能力有证据支撑 |
| Capability | Compliance | `compliesWith` | 能力符合要求 |
| Capability | Capability | `hasSubCapability` | 能力层次结构（v0.2 新增） |
| Capability | Resource | `requiresResource` | 能力需要资源（v0.2 新增） |

### 8.2 完整语义闭环（v0.2）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    leleby 能力语义闭环（v0.2）                              │
│                                                                             │
│  1. 需求层（Requirement Ontology）                                         │
│     "市场需要什么能力？"                                                   │
│          │                                                                  │
│          │  requiresCapability                                              │
│          ▼                                                                  │
│  2. 能力层（Capability Ontology）                                          │
│     "企业/产品提供什么能力？"                                               │
│     ├── 企业能力层（战略/业务能力）                                        │
│     ├── 产品能力层（产品实现的能力）                                        │
│     ├── 能力参数（NIST 可测量参数）                                        │
│     └── 能力资源（所需资源）                                                │
│          │                                                                  │
│          │  realizedBy / providesCapability                                 │
│          ▼                                                                  │
│  3. 产品层（Product Ontology）                                             │
│     "哪个产品实现这种能力？"                                                │
│          │                                                                  │
│          │  describedBy                                                     │
│          ▼                                                                  │
│  4. 规格层（Specification Ontology）                                       │
│     "能力如何用参数描述？"                                                  │
│          │                                                                  │
│          │  verifiedBy                                                      │
│          ▼                                                                  │
│  5. 验证层（Verification + Measurement + Evidence）                        │
│     "能力是否被验证？"                                                      │
│          │                                                                  │
│          ▼                                                                  │
│  6. 符合性层（Compliance Ontology）                                        │
│     "能力是否满足需求？"                                                    │
│          │                                                                  │
│          ▼                                                                  │
│  7. 决策层（Decision Ontology）                                            │
│     "基于能力匹配做什么决策？"                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 9. SHACL 验证约束

### 9.1 Capability 基础约束（v0.2 扩展）

```turtle
lcap:CapabilityShape
    a sh:NodeShape ;
    sh:targetClass lcap:Capability ;
    sh:property [
        sh:path lcap:capabilityIdentifier ;
        sh:minCount 1 ;
        sh:message "Capability must have an identifier" ;
    ] ;
    sh:property [
        sh:path lcap:capabilityName ;
        sh:minCount 1 ;
        sh:message "Capability must have a name" ;
    ] ;
    sh:property [
        sh:path lcap:hasFunction ;
        sh:minCount 1 ;
        sh:message "Capability should have at least one function" ;
    ] ;
    sh:property [
        sh:path lcap:hasCapabilityStatus ;
        sh:minCount 0 ;
        sh:message "Capability status is recommended for enterprise capabilities" ;
    ] .
```

### 9.2 CapabilityParameter 约束（v0.2 新增）

```turtle
lcap:CapabilityParameterShape
    a sh:NodeShape ;
    sh:targetClass lcap:CapabilityParameter ;
    sh:property [
        sh:path lcap:parameterName ;
        sh:minCount 1 ;
        sh:message "CapabilityParameter must have a name" ;
    ] ;
    sh:property [
        sh:path lcap:parameterValue ;
        sh:minCount 1 ;
        sh:message "CapabilityParameter must have a value" ;
    ] .
```

### 9.3 CapabilityResource 约束（v0.2 新增）

```turtle
lcap:CapabilityResourceShape
    a sh:NodeShape ;
    sh:targetClass lcap:CapabilityResource ;
    sh:property [
        sh:path lcap:resourceIdentifier ;
        sh:minCount 1 ;
        sh:message "CapabilityResource must have an identifier" ;
    ] ;
    sh:property [
        sh:path lcap:resourceName ;
        sh:minCount 1 ;
        sh:message "CapabilityResource must have a name" ;
    ] ;
    sh:property [
        sh:path lcap:resourceType ;
        sh:minCount 1 ;
        sh:message "CapabilityResource must have a type" ;
    ] .
```


## 10. 完整示例：云达照明能力模型（v0.2）

### 10.1 企业能力层（战略能力）

```ttl
# 企业
leleby:YundaLighting
    a leleby:Enterprise ;
    leleby:legalName "云达照明科技有限公司" .

# 企业战略能力
lcap:Yunda_EnterpriseCapability
    a lcap:EnterpriseCapability ;
    lcap:capabilityIdentifier "CAP-ENT-001" ;
    lcap:capabilityName "户外照明全价值链能力" ;
    lcap:capabilityDescription "从设计、制造到全球供应的完整户外照明能力" ;
    lcap:hasCapabilityStatus lcap:Active ;
    lcap:providedBy leleby:YundaLighting ;
    lcap:hasSubCapability lcap:Yunda_DesignCapability ;
    lcap:hasSubCapability lcap:Yunda_ManufacturingCapability ;
    lcap:hasSubCapability lcap:Yunda_SupplyChainCapability .
```

### 10.2 业务能力层

```ttl
# 制造能力（业务层）
lcap:Yunda_ManufacturingCapability
    a lcap:BusinessCapability ;
    lcap:capabilityIdentifier "CAP-BIZ-001" ;
    lcap:capabilityName "户外照明制造能力" ;
    lcap:capabilityDescription "设计、制造和测试户外 LED 照明产品" ;
    lcap:hasCapabilityType lcap:ManufacturingCapability ;
    lcap:hasCapabilityLevel lcap:Level4_GlobalSupply ;
    lcap:providedBy leleby:YundaLighting ;
    lcap:hasSubCapability lcap:Yunda_CNCMachiningCapability ;
    lcap:hasSubCapability lcap:Yunda_AssemblyCapability ;
    lcap:hasSubCapability lcap:Yunda_TestingCapability .
```

### 10.3 产品能力层（含参数、约束、资源）

```ttl
# 低温运行能力（产品层）
lcap:Yunda_ColdOperationCapability
    a lcap:EnvironmentalCapability ;
    lcap:capabilityIdentifier "CAP-PROD-001" ;
    lcap:capabilityName "低温运行能力" ;
    lcap:capabilityDescription "产品在 -40℃ 环境下正常工作" ;
    lcap:hasCapabilityType lcap:EnvironmentalCapability ;
    lcap:hasCapabilityStatus lcap:Active ;
    lcap:providedBy leleby:YundaLighting ;
    lcap:hasParameter [
        a lcap:CapabilityParameter ;
        lcap:parameterName "最低工作温度" ;
        lcap:parameterValue [
            leleby:hasNumericValue "-40"^^xsd:double ;
            leleby:hasUnit leleby:DegreeCelsius
        ] ;
        lcap:parameterType lcap:Minimum
    ] ;
    lcap:hasConstraint [
        a lcap:CapabilityConstraint ;
        lcap:constraintType lcap:SizeConstraint ;
        lcap:constraintValue [
            leleby:hasNumericValue "500"^^xsd:double ;
            leleby:hasUnit leleby:Millimeter
        ] ;
        lcap:constraintDescription "适用于尺寸 ≤ 500mm 的灯具"
    ] ;
    lcap:requiresResource [
        a lcap:CapabilityResource ;
        lcap:resourceIdentifier "RES-TEST-001" ;
        lcap:resourceName "高低温测试箱" ;
        lcap:resourceType lcap:Equipment
    ] .
```

### 10.4 产品实现能力

```ttl
# 产品型号
lprod:YD_GK_200W
    a lprod:ProductModel ;
    lprod:hasProductName "LED 户外工矿灯" ;
    lprod:hasModelNumber "YD-GK-200W" .

# 产品提供能力
lprod:YD_GK_200W
    lprod:providesCapability lcap:Yunda_ColdOperationCapability ;
    lprod:providesCapability lcap:Yunda_OutdoorLightingCapability .

# 能力被产品实现（反向）
lcap:Yunda_ColdOperationCapability
    lcap:realizedBy lprod:YD_GK_200W .
```

### 10.5 能力满足需求

```ttl
# 客户需求
lreq:Customer_REQ_Arctic_001
    a lreq:Requirement ;
    lreq:hasRequirementIdentifier "CUST-REQ-ARCTIC-001" ;
    lreq:hasRequirementName "北极项目低温照明需求" ;
    lreq:requiresCapability [
        a lreq:CapabilityRequirement ;
        lreq:capabilityType lcap:EnvironmentalCapability ;
        lreq:requiresCharacteristic leleby:OperatingTemperature ;
        lreq:hasConstraint [
            a leleby:RangeConstraint ;
            leleby:minValue [
                leleby:hasNumericValue "-40"^^xsd:double ;
                leleby:hasUnit leleby:DegreeCelsius
            ]
        ]
    ] .

# 能力满足需求
lcap:Yunda_ColdOperationCapability
    lcap:satisfiesRequirement lreq:Customer_REQ_Arctic_001 .
```


## 11. 核心类汇总

### 11.1 Classes

| 类名 | 父类 | 说明 |
|------|------|------|
| `lcap:Capability` | leleby:Disposition | 能力（BFO Disposition 特殊化） |
| `lcap:CapabilityType` | leleby:InformationEntity | 能力类型 |
| `lcap:CapabilityStatus` | — | 能力状态（v0.2 新增） |
| `lcap:Function` | leleby:InformationEntity | 功能 |
| `lcap:CapabilityParameter` | leleby:InformationEntity | 能力参数（v0.2 新增） |
| `lcap:CapabilityConstraint` | leleby:Constraint | 能力约束（v0.2 强化） |
| `lcap:CapabilityResource` | leleby:InformationEntity | 能力资源（v0.2 新增） |
| `lcap:CapabilityLevel` | leleby:InformationEntity | 能力等级 |
| `lcap:CompositeCapability` | lcap:Capability | 组合能力 |
| `lcap:CapabilityDependency` | leleby:InformationEntity | 能力依赖 |
| `lcap:CapabilityMaturity` | leleby:InformationEntity | 能力成熟度 |

### 11.2 Object Properties

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `lcap:hasCapabilityType` | lcap:Capability | lcap:CapabilityType | 能力类型 |
| `lcap:hasCapabilityStatus` | lcap:Capability | lcap:CapabilityStatus | 能力状态（v0.2 新增） |
| `lcap:hasCapabilityLevel` | lcap:Capability | lcap:CapabilityLevel | 能力等级 |
| `lcap:hasFunction` | lcap:Capability | lcap:Function | 执行功能 |
| `lcap:hasParameter` | lcap:Capability | lcap:CapabilityParameter | 能力参数（v0.2 新增） |
| `lcap:hasConstraint` | lcap:Capability | lcap:CapabilityConstraint | 能力约束（v0.2 强化） |
| `lcap:applicableUnder` | lcap:Capability | leleby:Condition | 适用条件 |
| `lcap:requiresResource` | lcap:Capability | lcap:CapabilityResource | 所需资源（v0.2 新增） |
| `lcap:realizedBy` | lcap:Capability | leleby:Product | 被产品实现 |
| `lcap:providedBy` | lcap:Capability | leleby:Organization | 由组织提供 |
| `lcap:verifiedBy` | lcap:Capability | lver:VerificationResult | 被验证 |
| `lcap:satisfiesRequirement` | lcap:Capability | lreq:Requirement | 满足需求 |
| `lcap:hasSubCapability` | lcap:Capability | lcap:Capability | 子能力（v0.2 新增） |


## 12. 版本变更记录

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v0.1 | 2026-07-28 | 初始版本：核心类与六要素模型 |
| **v0.2** | **2026-07-28** | **能力模型对齐版：1) 强化 Capability 作为 BFO Disposition 特殊化的哲学基础；2) 新增 CapabilityParameter 支持 NIST 制造能力参数化；3) 新增 CapabilityResource 表达能力资源依赖；4) 强化 CapabilityConstraint 支持能力边界表达；5) 新增 CapabilityStatus 支持能力生命周期治理；6) 新增 hasSubCapability 支持能力层次结构；7) 新增 EnterpriseCapability / BusinessCapability / ProductCapability 类型区分；8) 更新完整示例展示企业-业务-产品三层能力结构** |


*— leleby Capability Ontology Specification v0.2 — Capability Model Alignment Edition —*