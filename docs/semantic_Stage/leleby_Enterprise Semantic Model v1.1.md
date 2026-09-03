# leleby Enterprise Semantic Model v1.1

**文档版本：** v1.1 — 架构对齐版（Architecture Alignment Edition）

**文档类型：** 企业语义模型规范（Enterprise Semantic Model Specification）

**文档状态：** ✅ **核心冻结（Core Frozen）** — 允许实例化填充，禁止修改核心类与关系结构

**依赖架构：** leleby Ontology Architecture Specification v0.9（架构冻结版）

**依赖模块：**
- Core Ontology Specification v0.1
- Product Ontology Specification v0.3
- Capability Ontology Specification v0.2
- Process Ontology Specification v0.1
- Requirement Ontology Specification v0.3
- Specification Ontology Specification v1.0
- Measurement Ontology Specification v0.1
- Evidence Ontology Specification v0.1
- Verification Ontology Specification v0.1
- Compliance Ontology Specification v0.1
- Decision Ontology Specification v0.1

**目标受众：** 企业数据架构师、AI Agent 开发者、ERP/PIM 系统集成商、语义数据工程师

**版本说明：** v1.1 基于 v1.0 进行架构对齐升级，核心改进包括：
- 依赖本体从 v0.1 升级至 v0.9 架构体系
- 同步各模块规范的核心关系命名（`providesCapability` / `realizesCapability`）
- 增加 ProductType / ProductModel / ProductInstance 三层结构
- 增加 Verification、Decision、Process、Measurement 模块引用
- Compliance 模型升级为三级结构（Assertion / Assessment / Declaration）
- 完善 Evidence 和 Measurement 模型


## 1. 引言

### 1.1 目的

leleby Enterprise Semantic Model（ESM）是 leleby 体系中**面向商业化的核心应用层模型**。它定义了**一个具体企业应该如何被表达为 AI 可以理解、查询、验证和决策的语义数据对象**。

如果说 leleby Ontology 定义了“商业世界长什么样”，那么 ESM 定义了“**你家企业在 AI 眼里长什么样**”。

### 1.2 与 leleby Ontology 的关系

| 维度 | leleby Ontology | leleby ESM |
|------|-----------------|------------|
| **层次** | 基础设施层（模块规范） | 应用层（数据模板） |
| **内容** | 类定义、属性定义、关系定义 | 企业实例数据的结构规范 |
| **稳定性** | 极高（Architecture v0.9 冻结） | 较高（v1.1 冻结，可扩展） |
| **角色** | 提供语义词汇表 | 提供数据组织框架 |
| **使用方式** | 实例化类的定义 | 填充具体数据值 |
| **类比** | 英语字典 + 语法 | 商务信函模板 |

**关系图：**

```
leleby Ontology Architecture v0.9          leleby ESM v1.1
     │                                            │
     │  provides vocabulary                       │  defines structure
     │  (15+ 模块规范)                            │
     ▼                                            ▼
┌──────────────────────────┐              ┌─────────────────────────────┐
│ Core Ontology            │              │ ESM Enterprise Package     │
│ Product Ontology         │   ──使用──→   │   - Identity               │
│ Capability Ontology      │              │   - Capabilities           │
│ Process Ontology         │              │   - Products               │
│ Requirement Ontology     │              │   - Services               │
│ Specification Ontology   │              │   - Compliance             │
│ Measurement Ontology     │              │   - Verification           │
│ Evidence Ontology        │              │   - Decision               │
│ Verification Ontology    │              │   - Achievements           │
│ Compliance Ontology      │              │   - Restrictions           │
│ Decision Ontology        │              │   - Sustainability         │
└──────────────────────────┘              └─────────────────────────────┘
```

### 1.3 ESM 的核心定位

**ESM 不是一个企业信息数据库，也不是一个企业主页，而是：**

> **企业面向 AI 世界的语义化数字身份（Semantic Identity + Capability Representation + Verifiable Trust + Decision-Ready Facts）**

它让 AI Agent 能够：

- **找到**企业（精确语义发现，非关键词搜索）
- **理解**企业（能力、过程、产品、服务）
- **验证**企业（符合性事实、检测证据、来源可信度）
- **比较**企业（能力空间、超额能力、可持续性）
- **决策**企业（基于验证结果和业务规则的综合判断）
- **交易**企业（语义驱动的商业交互）

### 1.4 语义闭环中的 ESM

ESM 是企业数据在 leleby 语义闭环中的**入口和载体**：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    leleby 语义闭环中的 ESM                                  │
│                                                                             │
│  ESM 企业语义数据包                                                         │
│  （企业身份 + 能力 + 产品 + 过程 + 规格 + 测量 + 证据）                    │
│                                    │                                        │
│                                    ▼                                        │
│  Requirement → Specification → Verification → Compliance → Decision        │
│                                                                             │
│  输出：                                                                     │
│  - 企业能力匹配结果                                                         │
│  - 产品符合性断言                                                           │
│  - 采购决策建议                                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 2. 核心原则

ESM 遵循以下核心设计原则：

### 2.1 外部语义原则

> **ESM 只描述企业面向外部的商业语义，不涉及企业内部组织架构、人事管理、财务核算等内部运营细节。**

### 2.2 事实不固化原则

> **ESM 只提供事实层，不固化价值判断。** 价格优先、性能优先、绿色优先、安全优先，都由 AI Agent 根据客户需求自行判断。

### 2.3 分类中立原则

> **ESM 不强制绑定任何单一分类体系。** 产品可以同时拥有 GS1、HS Code、eCl@ss、Amazon、Alibaba 等多体系分类断言。

### 2.4 证据适度原则

> **ESM 的核心是表达“观测事实”（Observation）和“符合性断言”（Compliance Assertion），而非成为认证系统。** Evidence 是来源标注，用于置信度推理。

### 2.5 AI 原生原则

> **ESM 的最终输出（JSON-LD / RDF）必须能够被 AI Agent 直接消费、推理和决策。**

### 2.6 闭环完整原则（v1.1 新增）

> **ESM 必须覆盖从需求到决策的完整语义闭环：Requirement → Specification → Verification → Compliance → Decision。**


## 3. ESM 总体架构

leleby Enterprise Semantic Model 由以下十二大模块构成（v1.1 新增 Verification 和 Decision 模块）：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    leleby Enterprise Semantic Package                       │
│                    （企业语义数据包）                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 1:  Enterprise Identity Model（企业身份模型）                        │
│  回答：你是谁？（法律/商业/联系方式）                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 2:  External Relationship Model（外部关系模型）                      │
│  回答：你和谁有关系？（母子公司/品牌/合作/供应链）                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 3:  Enterprise Capability Model（企业能力模型）—— 核心               │
│  回答：你能做什么？（通过什么过程产生什么结果）                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 4:  Product Semantic Model（产品语义模型）—— v1.1 三层结构            │
│  回答：你制造什么产品？（类型/型号/实例/结构/属性）                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 5:  Service Semantic Model（服务语义模型）                           │
│  回答：你提供什么服务？（服务类型/服务能力/SLA）                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 6:  Process Semantic Model（过程语义模型）—— v1.1 新增               │
│  回答：你如何实现能力？（制造过程/检验过程/交付过程）                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 7:  Specification & Measurement Model（规格与测量模型）—— v1.1 增强   │
│  回答：产品/过程如何被描述和量化？（规格项 + 量值 + 条件）                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 8:  Verification Model（验证模型）—— v1.1 新增                       │
│  回答：产品/能力是否被验证？（验证方法 + 观测事实 + 验证结果）                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 9:  Compliance Model（符合性模型）—— v1.1 三级结构                   │
│  回答：你满足什么标准？（单项符合性 + 综合评价 + 对外声明）                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 10: Decision & Action Model（决策与行动模型）—— v1.1 新增            │
│  回答：基于验证结果做什么决策？（决策规则 + 决策结果 + 行动）                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 11: Achievement & Evidence Model（业绩与证据模型）                    │
│  回答：你做过什么？有什么证明？（项目/案例/专利/证书/测试报告）               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  模块 12: Restriction & Sustainability Model（限制与可持续模型）           │
│  回答：什么情况下不能/不允许？环境/社会/治理表现如何？                        │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 4. 模块 1：Enterprise Identity Model（企业身份模型）

### 4.1 核心实体

基于 Core Ontology Specification v0.1：

```
leleby:Enterprise
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Organization .
```

### 4.2 属性定义

| 属性 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `leleby:legalName` | xsd:string | 法定注册名称 | "某某照明科技有限公司" |
| `leleby:tradeName` | xsd:string | 商号/品牌名称 | "Yunda Lighting" |
| `leleby:hasIdentifier` | leleby:Identifier | 统一标识符 | 注册号/LEI |
| `leleby:establishedDate` | xsd:date | 成立日期 | "2008-06-15" |
| `leleby:registeredAddress` | leleby:Address | 注册地址 | ... |
| `leleby:operatingAddress` | leleby:Address | 经营地址 | ... |
| `leleby:website` | xsd:anyURI | 官方网站 | "https://www.yunda.com" |
| `leleby:primaryIndustry` | leleby:IndustryCode | 主要行业 | "C3871" |
| `leleby:employeeCount` | xsd:integer | 员工人数 | 500 |
| `leleby:operatingStatus` | leleby:OperatingStatus | 经营状态 | Active / Inactive |

### 4.3 联系人信息

| 属性 | 类型 | 说明 |
|------|------|------|
| `leleby:hasContactPoint` | leleby:ContactPoint | 联系点 |
| `leleby:email` | xsd:string | 邮箱 |
| `leleby:phone` | xsd:string | 电话 |
| `leleby:contactPerson` | xsd:string | 联系人姓名 |

### 4.4 经营状态枚举

| 值 | 说明 |
|----|------|
| `leleby:Active` | 正常经营 |
| `leleby:Inactive` | 停业 |
| `leleby:Bankruptcy` | 破产 |
| `leleby:Acquired` | 已被收购 |
| `leleby:Merged` | 已合并 |


## 5. 模块 2：External Relationship Model（外部关系模型）

### 5.1 核心思想

企业不是孤岛。ESM 表达企业参与外部经济活动的关系网络。

**注意：** 不包含内部组织架构（部门/员工/岗位）。

### 5.2 关系类型

```
leleby:OrganizationRelationship
    rdf:type owl:Class ;
    rdfs:label "OrganizationRelationship" .
```

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `leleby:hasRelationship` | leleby:Enterprise | leleby:OrganizationRelationship | 拥有外部关系 |
| `leleby:relatedOrganization` | leleby:OrganizationRelationship | leleby:Organization | 关联组织 |
| `leleby:relationshipType` | leleby:OrganizationRelationship | leleby:RelationshipType | 关系类型 |

### 5.3 预定义关系类型

| 类型 | 说明 |
|------|------|
| `leleby:ParentCompany` | 母公司 |
| `leleby:Subsidiary` | 子公司 |
| `leleby:JointVenture` | 合资企业 |
| `leleby:StrategicPartner` | 战略合作伙伴 |
| `leleby:Supplier` | 供应商 |
| `leleby:Customer` | 客户 |
| `leleby:Distributor` | 分销商 |
| `leleby:CertificationBody` | 认证机构关系 |
| `leleby:IndustryAssociation` | 行业协会成员 |


## 6. 模块 3：Enterprise Capability Model（企业能力模型）

### 6.1 核心模型（v1.1 更新）

基于 Capability Ontology Specification v0.2：

> **Capability** 是 BFO Disposition 的特殊化——一种可由 Agent 拥有的潜在倾向，能够在特定条件下通过资源、过程或产品实现某种功能或价值。

```
Enterprise
    │
    └── providesCapability ──→ Capability（v1.1：providesCapability）
                              │
                              │ realizedBy
                              ▼
                          Process
                              │
                              │ produces
                              ▼
                          Output
                              │
                    ┌─────────┴──────────┐
                    │                    │
                Product              Service
```

**v1.1 关系变更：** `hasCapability` → `providesCapability`

### 6.2 能力结构

```
leleby:EnterpriseCapability
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Capability .

属性:
    ├── leleby:capabilityIdentifier   xsd:string       能力标识符
    ├── leleby:capabilityName         xsd:string       能力名称
    ├── leleby:capabilityDescription  xsd:string       能力描述
    ├── leleby:hasCapabilityType      leleby:CapabilityType  能力类型
    ├── leleby:hasCapabilityLevel     leleby:CapabilityLevel  能力等级
    ├── leleby:realizedBy             leleby:Process   实现过程
    ├── leleby:hasParameter           leleby:CapabilityParameter  能力参数
    ├── leleby:hasConstraint          leleby:CapabilityConstraint  能力约束
    └── leleby:requiresResource       leleby:CapabilityResource  所需资源
```

### 6.3 能力分类

| 能力类型 | 说明 |
|----------|------|
| `leleby:ManufacturingCapability` | 制造能力 |
| `leleby:EngineeringCapability` | 工程能力 |
| `leleby:TestingCapability` | 检测能力 |
| `leleby:ServiceCapability` | 服务能力 |
| `leleby:BusinessCapability` | 商业能力 |
| `leleby:EnvironmentalCapability` | 环境适应能力 |

### 6.4 示例

```ttl
leleby:YundaLighting
    leleby:providesCapability
        leleby:OutdoorLightingManufacturingCapability .

leleby:OutdoorLightingManufacturingCapability
    a leleby:EnterpriseCapability ;
    leleby:capabilityIdentifier "CAP-YUNDA-001" ;
    leleby:capabilityName "户外照明制造能力" ;
    leleby:capabilityDescription "设计、制造和测试户外 LED 照明产品" ;
    leleby:hasCapabilityType leleby:ManufacturingCapability ;
    leleby:hasCapabilityLevel leleby:Level4_GlobalSupply ;
    leleby:realizedBy leleby:LightingManufacturingProcess .
```


## 7. 模块 4：Product Semantic Model（产品语义模型 v1.1 重构）

### 7.1 核心结构（v1.1 三层模型）

基于 Product Ontology Specification v0.3，产品采用三层结构：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Product 三层模型                                        │
│                                                                             │
│  ProductType（产品类型）                                                   │
│  例如：户外 LED 灯具类别                                                    │
│                                                                             │
│  ProductModel（产品型号）                                                  │
│  例如：YD-GK-200W                                                          │
│                                                                             │
│  ProductInstance（产品个体）                                               │
│  例如：SN: 202607001                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 核心结构

```
ProductModel
    │
    ├── hasProductType ──→ ProductType（类型）
    │
    ├── hasInstance ──→ ProductInstance（实例）
    │
    ├── providesCapability ──→ ProductCapability（能力）
    │
    ├── describedBy ──→ ProductSpecification（规格）
    │
    ├── hasPart ──→ Product（递归结构）
    │
    ├── hasConfiguration ──→ ProductConfiguration（配置）
    │
    ├── hasOffering ──→ ProductOffering（商业化提供）
    │
    └── hasClassificationAssertion ──→ ClassificationAssertion（分类）
```

### 7.3 产品基本信息（ProductModel）

| 属性 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `leleby:hasProductName` | xsd:string | 产品名称 | "LED 户外工矿灯" |
| `leleby:hasModelNumber` | xsd:string | 型号 | "YD-GK-200W" |
| `leleby:hasProductSeries` | xsd:string | 系列名称 | "GK 系列" |
| `leleby:hasProductDescription` | xsd:string | 产品描述 | ... |
| `leleby:productStatus` | leleby:ProductStatus | 产品状态 | Active/Discontinued/ComingSoon |
| `leleby:releaseDate` | xsd:date | 上市日期 | "2024-03-01" |

### 7.4 产品个体（ProductInstance）

| 属性 | 类型 | 说明 |
|------|------|------|
| `leleby:hasSerialNumber` | xsd:string | 序列号 |
| `leleby:manufacturedDate` | xsd:date | 生产日期 |
| `leleby:batchNumber` | xsd:string | 批次号 |
| `leleby:hasLifecycleState` | leleby:LifecycleState | 生命周期状态 |

### 7.5 产品结构

```
leleby:ProductStructureAssertion
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Assertion .

属性:
    ├── leleby:subjectProduct      leleby:Product    主体产品
    ├── leleby:relationType        leleby:StructureRelationType  关系类型
    ├── leleby:objectProduct       leleby:Product    客体产品
    ├── leleby:partQuantity        xsd:integer       数量
    ├── leleby:quantityUnit        leleby:Unit       单位
    └── leleby:connectionType      leleby:ConnectionType  连接类型
```

**连接类型：** `Welded` / `Bolted` / `Adhesive` / `Electrical` / `Communication` / `SnapFit` / `PressFit` / `Threaded`

### 7.6 产品能力（v1.1 更新）

```
ProductModel
    leleby:providesCapability ──→ ProductCapability
```

**v1.1 关系变更：** `hasCapability` → `providesCapability`

### 7.7 产品分类（多分类投影）

```ttl
leleby:ProductModel
    leleby:hasClassificationAssertion
        leleby:Classification001 .

leleby:Classification001
    a leleby:ClassificationAssertion ;
    leleby:classificationSystem leleby:GS1System ;
    leleby:classCode "31401234" ;
    leleby:className "Lighting Equipment" ;
    leleby:mappingType leleby:exactMatch ;
    leleby:confidence "0.95"^^xsd:double .
```


## 8. 模块 5：Service Semantic Model（服务语义模型）

### 8.1 核心思想

服务不是产品的子类。服务是**通过服务过程实现的能力输出**。

基于 Specification Ontology v1.0 和 Process Ontology v0.1：

```
Enterprise
    │
    └── providesService ──→ Service
                              │
                              │ realizedBy
                              ▼
                        ServiceProcess
                              │
                              ├── hasServiceCapability
                              └── hasSLA
```

### 8.2 服务类型

| 类型 | 说明 |
|------|------|
| `leleby:InstallationService` | 安装服务 |
| `leleby:MaintenanceService` | 维护服务 |
| `leleby:RepairService` | 维修服务 |
| `leleby:TrainingService` | 培训服务 |
| `leleby:ConsultingService` | 咨询服务 |
| `leleby:DesignService` | 设计服务 |
| `leleby:TestingService` | 检测服务 |
| `leleby:SoftwareAsAService` | SaaS 服务 |
| `leleby:WarrantyService` | 保修服务 |


## 9. 模块 6：Process Semantic Model（过程语义模型）—— v1.1 新增

### 9.1 核心思想

基于 Process Ontology Specification v0.1：

> **Process** 是一组相互关联的活动，将输入转换为输出，实现一种或多种能力。过程在时间中展开，具有时间部分。

### 9.2 过程结构

```
leleby:Process
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Occurrent .

属性:
    ├── leleby:processIdentifier   xsd:string      过程标识符
    ├── leleby:processName         xsd:string      过程名称
    ├── leleby:processDescription  xsd:string      过程描述
    ├── leleby:processType         leleby:ProcessType  过程类型
    ├── leleby:hasActivity         leleby:Activity  包含的活动
    ├── leleby:hasInput            leleby:ProcessInput  过程输入
    ├── leleby:hasOutput           leleby:ProcessOutput  过程输出
    ├── leleby:requiresResource    leleby:Resource  所需资源
    ├── leleby:hasParameter        leleby:ProcessParameter  过程参数
    └── leleby:realizesCapability  leleby:Capability  实现的能力
```

### 9.3 过程类型

| 类型 | 说明 |
|------|------|
| `leleby:BusinessProcess` | 业务流程 |
| `leleby:ManufacturingProcess` | 制造过程 |
| `leleby:InspectionProcess` | 检验过程 |
| `leleby:MaintenanceProcess` | 维护过程 |
| `leleby:ServiceProcess` | 服务过程 |
| `leleby:LifecycleProcess` | 生命周期过程 |


## 10. 模块 7：Specification & Measurement Model（规格与测量模型）—— v1.1 增强

### 10.1 规格模型

基于 Specification Ontology Specification v1.0：

```
leleby:ProductSpecification
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Specification .

属性:
    ├── leleby:hasSpecificationIdentifier   xsd:string  规格编号
    ├── leleby:hasSpecificationName         xsd:string  规格名称
    ├── leleby:hasVersion                   xsd:string  版本号
    ├── leleby:hasSpecificationItem         leleby:SpecificationItem  规格项
    └── leleby:hasSpecificationStatus       leleby:SpecificationStatus  规格状态
```

### 10.2 规格项

```
leleby:SpecificationItem
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity .

属性:
    ├── leleby:specifiesCharacteristic   leleby:Characteristic  描述的特性
    ├── leleby:hasValueExpression        leleby:ValueExpression  值的表达
    └── leleby:underCondition            leleby:Condition  生效条件
```

### 10.3 值表达模型

| 类型 | 说明 | 示例 |
|------|------|------|
| `leleby:SimpleValueExpression` | 单一数值 | 100W |
| `leleby:RangeValueExpression` | 范围值 | -40℃ ~ 70℃ |
| `leleby:ToleranceValueExpression` | 公差值 | 15.00 ±0.02mm |
| `leleby:EnumerationValueExpression` | 枚举值 | IP65, IP66, IP67 |
| `leleby:BooleanValueExpression` | 布尔值 | TRUE |

### 10.4 测量模型

基于 Measurement Ontology Specification v0.1：

```
leleby:MeasurementObservation
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Observation .

属性:
    ├── leleby:hasSubject        leleby:ObservableEntity  测量对象
    ├── leleby:observes          leleby:ObservableCharacteristic  测量特性
    ├── leleby:hasResult         leleby:MeasurementResult  测量结果
    ├── leleby:hasContext        leleby:MeasurementContext  测量上下文
    ├── leleby:usesMethod        leleby:MeasurementMethodReference  测量方法
    └── leleby:hasSample         leleby:MeasurementSample  测量样本
```

```
leleby:MeasurementResult
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity .

属性:
    ├── leleby:hasValue          leleby:MeasurementValue  测量值
    ├── leleby:hasUnit           leleby:Unit  单位
    ├── leleby:hasUncertainty    leleby:MeasurementUncertainty  不确定度
    └── leleby:confidenceLevel   xsd:double  置信度
```


## 11. 模块 8：Verification Model（验证模型）—— v1.1 新增

### 11.1 核心思想

基于 Verification Ontology Specification v0.1：

> **Verification** 负责对单项要求、单项规格、单项事实进行可追溯的符合性验证，并产生 Verification Result。**不负责最终的整体合格/不合格决策**。

### 11.2 验证结构

```
leleby:Verification
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Process .

属性:
    ├── leleby:hasVerificationIdentifier   xsd:string  验证编号
    ├── leleby:verificationDate            xsd:dateTime  验证日期
    ├── leleby:targets                     leleby:VerificationTarget  验证目标
    ├── leleby:usesMethod                  leleby:VerificationMethod  验证方法
    ├── leleby:hasObservation              leleby:Observation  观测事实
    ├── leleby:evaluatedBy                 leleby:VerificationRule  验证规则
    └── leleby:hasResult                   leleby:VerificationResult  验证结果
```

### 11.3 验证结果状态

| 值 | 说明 |
|----|------|
| `leleby:PASS` | 通过 |
| `leleby:FAIL` | 未通过 |
| `leleby:INCONCLUSIVE` | 无法确定 |
| `leleby:NOT_APPLICABLE` | 不适用 |

### 11.4 示例

```ttl
leleby:Verification_Temp_001
    a leleby:Verification ;
    leleby:hasVerificationIdentifier "VER-TEMP-001" ;
    leleby:verificationDate "2026-07-28"^^xsd:date ;
    leleby:targets leleby:ProductYD001 ;
    leleby:usesMethod leleby:Method_IEC60068 ;
    leleby:hasObservation leleby:Obs_Temp_001 ;
    leleby:evaluatedBy leleby:RangeRule_Temp ;
    leleby:hasResult [
        a leleby:VerificationResult ;
        leleby:hasResultStatus leleby:PASS ;
        leleby:hasConfidence "0.95"^^xsd:double
    ] .
```


## 12. 模块 9：Compliance Model（符合性模型）—— v1.1 三级结构

### 12.1 核心思想

基于 Compliance Ontology Specification v0.1：

> **Compliance 不是单一概念，而是三个层级的符合性表达体系：**

| 层级 | 概念 | 说明 |
|------|------|------|
| Level 1 | `ComplianceAssertion` | 单项符合性断言（Verification 的直接输出） |
| Level 2 | `ComplianceAssessment` | 综合评价（多个断言的聚合） |
| Level 3 | `ComplianceDeclaration` | 对外声明（面向外部利益相关者） |

### 12.2 三级结构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Compliance 三级模型（v1.1）                              │
│                                                                             │
│  Level 1: ComplianceAssertion（单项符合性）                                 │
│  描述：单项要求是否满足                                                    │
│  来源：Verification Result                                                │
│  示例："温度要求 PASS"                                                    │
│                                                                             │
│                                    │                                        │
│                                    │  aggregatedBy                         │
│                                    ▼                                        │
│  Level 2: ComplianceAssessment（综合评价）                                 │
│  描述：多个单项符合性的综合评估                                            │
│  来源：多个 ComplianceAssertion + 评估规则                                 │
│  示例："98/100 项要求通过 → 产品合格"                                    │
│                                                                             │
│                                    │                                        │
│                                    │  declaredAs                           │
│                                    ▼                                        │
│  Level 3: ComplianceDeclaration（对外声明）                                │
│  描述：面向外部利益相关者的符合性正式声明                                  │
│  来源：ComplianceAssessment                                               │
│  示例："产品符合 IEC 60598 标准"                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 符合性状态

| 状态 | 说明 |
|----|------|
| `leleby:Compliant` | 符合 |
| `leleby:NonCompliant` | 不符合 |
| `leleby:PartiallyCompliant` | 部分符合 |
| `leleby:ConditionallyCompliant` | 条件符合 |
| `leleby:Unknown` | 未知 |
| `leleby:NotApplicable` | 不适用 |

### 12.4 符合性级别

| 级别 | 说明 |
|----|------|
| `leleby:Full` | 完全符合 |
| `leleby:High` | 高度符合（≥ 95%） |
| `leleby:Medium` | 中等符合（≥ 80%） |
| `leleby:Low` | 低度符合（≥ 60%） |

### 12.5 示例

```ttl
# Level 1: 单项符合性
leleby:CA_Temp_001
    a leleby:ComplianceAssertion ;
    leleby:hasSubject leleby:ProductYD001 ;
    leleby:evaluatesRequirement leleby:REQ_Temp_001 ;
    leleby:basedOnVerification leleby:Verification_Temp_001 ;
    leleby:hasComplianceStatus leleby:Compliant .

# Level 2: 综合评价
leleby:CA_Product_001
    a leleby:ComplianceAssessment ;
    leleby:assessmentName "产品 YD001 整体符合性评估" ;
    leleby:aggregatesAssertions leleby:CA_Temp_001 ;
    leleby:aggregatesAssertions leleby:CA_IP_001 ;
    leleby:totalRequirementCount "3"^^xsd:integer ;
    leleby:passedCount "3"^^xsd:integer ;
    leleby:hasOverallStatus leleby:Compliant .

# Level 3: 对外声明
leleby:CD_IEC60598_001
    a leleby:ComplianceDeclaration ;
    leleby:declarationName "YD001 IEC 60598 符合性声明" ;
    leleby:declaresProduct leleby:ProductYD001 ;
    leleby:declaresAssessment leleby:CA_Product_001 ;
    leleby:declarationStatus leleby:Active .
```


## 13. 模块 10：Decision & Action Model（决策与行动模型）—— v1.1 新增

### 13.1 核心思想

基于 Decision Ontology Specification v0.1：

> **Decision** 处理“多个事实、多项验证结果如何形成业务判断”。

### 13.2 决策结构

```
leleby:Decision
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:Process .

属性:
    ├── leleby:hasDecisionIdentifier   xsd:string  决策编号
    ├── leleby:decisionName            xsd:string  决策名称
    ├── leleby:usesInput               leleby:DecisionInput  决策输入
    ├── leleby:usesRule                leleby:DecisionRule  决策规则
    └── leleby:hasOutcome              leleby:DecisionOutcome  决策结果
```

### 13.3 决策结果

| 结果 | 说明 |
|----|------|
| `leleby:Accept` | 接受 |
| `leleby:Reject` | 拒绝 |
| `leleby:ConditionalAccept` | 有条件接受 |
| `leleby:NeedReview` | 需评审 |
| `leleby:Escalate` | 升级处理 |
| `leleby:Defer` | 延迟决策 |

### 13.4 行动类型

| 行动 | 说明 |
|----|------|
| `leleby:Release` | 放行 |
| `leleby:Rework` | 返工 |
| `leleby:Repair` | 维修 |
| `leleby:Scrap` | 报废 |
| `leleby:Hold` | 隔离 |
| `leleby:Notify` | 通知 |


## 14. 模块 11：Achievement & Evidence Model（业绩与证据模型）

### 14.1 项目/交付成果

```
leleby:Project
    rdf:type owl:Class .

属性:
    ├── leleby:projectName         xsd:string  项目名称
    ├── leleby:projectDescription  xsd:string  项目描述
    ├── leleby:clientIndustry      xsd:string  客户行业
    ├── leleby:projectLocation     leleby:Location  项目地点
    ├── leleby:startDate           xsd:date  开始日期
    ├── leleby:completionDate      xsd:date  完成日期
    ├── leleby:productUsed         leleby:Product  使用的产品
    └── leleby:quantity            xsd:integer  数量
```

### 14.2 证据模型

基于 Evidence Ontology Specification v0.1：

```
leleby:Evidence
    rdf:type owl:Class ;
    rdfs:subClassOf leleby:InformationEntity .

属性:
    ├── leleby:evidenceIdentifier   xsd:string  证据编号
    ├── leleby:evidenceName         xsd:string  证据名称
    ├── leleby:supportsClaim        leleby:Claim  支持的声明
    ├── leleby:hasType              leleby:EvidenceType  证据类型
    ├── leleby:generatedBy          leleby:EvidenceSource  产生来源
    ├── leleby:hasValidity          leleby:EvidenceValidity  有效期
    └── leleby:hasConfidence        leleby:EvidenceConfidence  可信等级
```

### 14.3 证据类型

| 类型 | 说明 |
|----|------|
| `leleby:CertificationEvidence` | 认证证据 |
| `leleby:TestReportEvidence` | 测试报告证据 |
| `leleby:InspectionEvidence` | 检验证据 |
| `leleby:MeasurementEvidence` | 测量证据 |
| `leleby:SpecificationDocumentEvidence` | 规格文档证据 |
| `leleby:StandardEvidence` | 标准证据 |
| `leleby:DeclarationEvidence` | 声明证据 |


## 15. 模块 12：Restriction & Sustainability Model（限制与可持续模型）

### 15.1 限制模型

```
leleby:Restriction
    rdf:type owl:Class .

属性:
    ├── leleby:appliesToRestriction   leleby:Entity  限制目标
    ├── leleby:restrictionType        leleby:RestrictionType  限制类型
    ├── leleby:restrictionDescription xsd:string  限制描述
    ├── leleby:hasConstraint          leleby:Constraint  限制条件
    └── leleby:validPeriod            leleby:Interval  有效期
```

**限制类型：** `ExportRestriction` / `GeographicRestriction` / `TemporalRestriction` / `UsageRestriction` / `CustomerRestriction`

### 15.2 可持续模型

```
leleby:EnterpriseSustainability
    rdf:type owl:Class .

属性:
    ├── leleby:hasEnvironmentalManagement   xsd:boolean  环境管理体系
    ├── leleby:hasSafetyManagement          xsd:boolean  安全管理体系
    ├── leleby:hasSocialResponsibility      xsd:boolean  社会责任承诺
    ├── leleby:esgCertification             leleby:Certification  ESG 认证
    └── leleby:sustainabilityReport         xsd:anyURI  可持续发展报告
```

**产品级可持续：**

```
leleby:ProductSustainability
    rdf:type owl:Class .

属性:
    ├── leleby:carbonFootprint     leleby:MeasurementValue  碳足迹
    ├── leleby:recyclabilityRate   xsd:double  可回收率
    ├── leleby:repairabilityScore  xsd:double  可维修性评分
    └── leleby:energyConsumption   leleby:MeasurementValue  能耗
```


## 16. ESM 完整数据包结构（JSON-LD 模板 v1.1）

```json
{
  "@context": "https://esm.leleby.com/v1.1/context.jsonld",
  "@type": "EnterpriseSemanticPackage",
  "enterpriseId": "https://leleby.ai/ent/123456",

  "identity": {
    "legalName": "某某照明科技有限公司",
    "tradeName": "Yunda Lighting",
    "identifier": {
      "identifierType": "RegistrationNumber",
      "identifierValue": "91440101XXXX"
    },
    "establishedDate": "2008-06-15",
    "website": "https://www.yunda.com",
    "primaryIndustry": "C3871",
    "employeeCount": 500,
    "operatingStatus": "Active",
    "contactPoint": {
      "email": "info@yunda.com",
      "phone": "+86-755-12345678"
    }
  },

  "relationships": [
    {
      "relatedOrganization": "Yunda Group",
      "relationshipType": "Subsidiary"
    }
  ],

  "capabilities": [
    {
      "capabilityIdentifier": "CAP-YUNDA-001",
      "capabilityName": "户外照明制造能力",
      "capabilityDescription": "设计、制造和测试户外 LED 照明产品",
      "capabilityType": "ManufacturingCapability",
      "capabilityLevel": "Level4_GlobalSupply",
      "parameters": [
        {
          "parameterName": "年产能",
          "parameterValue": { "value": 500000, "unit": "pcs/year" }
        }
      ],
      "resources": [
        { "resourceName": "SMT 生产线", "resourceType": "Equipment" },
        { "resourceName": "组装线", "resourceType": "Equipment" }
      ]
    }
  ],

  "products": [
    {
      "productType": {
        "name": "户外 LED 灯具"
      },
      "productModel": {
        "modelNumber": "YD-GK-200W",
        "productName": "LED 户外工矿灯",
        "productStatus": "Active"
      },
      "productInstances": [
        {
          "serialNumber": "SN-2026-001",
          "manufacturedDate": "2026-07-15",
          "lifecycleState": "InStock"
        }
      ],
      "classificationAssertions": [
        { "system": "GS1", "code": "31401234", "confidence": 0.95 },
        { "system": "HS", "code": "9405.40", "confidence": 0.98 }
      ],
      "specifications": [
        {
          "specificationName": "YD-GK-200W 产品规格书",
          "version": "1.0",
          "items": [
            {
              "characteristic": "OperatingTemperature",
              "valueExpression": {
                "type": "RangeValueExpression",
                "minValue": { "value": -40, "unit": "°C" },
                "maxValue": { "value": 85, "unit": "°C" }
              },
              "condition": { "humidity": "<95%", "altitude": "<5000m" }
            }
          ]
        }
      ],
      "capabilities": [
        {
          "capabilityName": "低温运行能力",
          "parameters": [
            {
              "parameterName": "最低工作温度",
              "parameterValue": { "value": -40, "unit": "°C" }
            }
          ]
        }
      ],
      "restrictions": [
        {
          "type": "ExportRestriction",
          "description": "不可出口至美国",
          "validUntil": "2028-12-31"
        }
      ]
    }
  ],

  "processes": [
    {
      "processIdentifier": "PROC-MFG-001",
      "processName": "户外灯具制造过程",
      "processType": "ManufacturingProcess",
      "activities": ["SMT", "组装", "老化测试"],
      "inputs": ["LED芯片", "铝材", "电源"],
      "outputs": ["户外LED灯具"],
      "realizesCapability": "户外照明制造能力"
    }
  ],

  "verifications": [
    {
      "verificationIdentifier": "VER-TEMP-001",
      "verificationDate": "2026-07-28",
      "targets": "YD-GK-200W",
      "method": "IEC 60068-2-1 Cold Test",
      "observation": {
        "characteristic": "OperatingTemperature",
        "value": { "min": -45, "max": 75, "unit": "°C" }
      },
      "result": {
        "status": "PASS",
        "confidence": 0.95,
        "evidence": "SGS Test Report #123"
      }
    }
  ],

  "compliance": [
    {
      "type": "ComplianceAssertion",
      "subject": "YD-GK-200W",
      "requirement": "IEC 60598 Temperature Requirement",
      "basedOn": "VER-TEMP-001",
      "status": "Compliant"
    },
    {
      "type": "ComplianceAssessment",
      "assessmentName": "产品 YD-GK-200W 整体评估",
      "totalRequirementCount": 3,
      "passedCount": 3,
      "overallStatus": "Compliant"
    },
    {
      "type": "ComplianceDeclaration",
      "declarationName": "IEC 60598 符合性声明",
      "declaresProduct": "YD-GK-200W",
      "declaresAssessment": "产品 YD-GK-200W 整体评估",
      "declarationStatus": "Active"
    }
  ],

  "decisions": [
    {
      "decisionIdentifier": "DEC-BATCH-001",
      "decisionName": "批次接收决策",
      "input": "ComplianceAssessment: 产品 YD-GK-200W 整体评估",
      "rule": "所有要求通过 → 接受",
      "outcome": "Accept",
      "action": "Release"
    }
  ],

  "achievements": [
    {
      "projectName": "深圳宝安机场航站楼照明改造",
      "clientIndustry": "航空交通",
      "location": "深圳",
      "completionDate": "2024-12-01",
      "productUsed": "YD-GK-200W",
      "quantity": 5000
    }
  ],

  "evidence": [
    {
      "evidenceIdentifier": "EVID-SGS-001",
      "evidenceName": "SGS 温度测试报告",
      "evidenceType": "TestReportEvidence",
      "supports": "温度要求符合性",
      "confidence": 0.95,
      "source": "SGS",
      "validUntil": "2031-07-28"
    }
  ],

  "sustainability": {
    "enterprise": {
      "hasEnvironmentalManagement": true,
      "hasSafetyManagement": true
    },
    "products": [
      {
        "productId": "YD-GK-200W",
        "carbonFootprint": { "value": 2.5, "unit": "kg CO2 eq" },
        "recyclabilityRate": 85
      }
    ]
  },

  "mappings": [
    {
      "system": "GS1",
      "code": "31401234",
      "confidence": 0.95
    }
  ]
}
```


## 17. 附录 A：ESM 核心属性完整汇总

| 属性名 | 域 | 值域 | 说明 | 模块 |
|--------|----|------|------|------|
| `leleby:legalName` | Enterprise | xsd:string | 法定名称 | 1 |
| `leleby:providesCapability` | Enterprise | Capability | 提供能力（v1.1 更新） | 3 |
| `leleby:realizedBy` | Capability | Process | 过程实现 | 3 |
| `leleby:providesProduct` | Enterprise | Product | 提供产品 | 4 |
| `leleby:providesService` | Enterprise | Service | 提供服务 | 5 |
| `leleby:hasPart` | Product | Product | 包含部件 | 4 |
| `leleby:describedBy` | Product | ProductSpecification | 被规格描述（v1.1 更新） | 4,7 |
| `leleby:hasSpecificationItem` | Specification | SpecificationItem | 包含规格项 | 7 |
| `leleby:hasValueExpression` | SpecificationItem | ValueExpression | 值的表达 | 7 |
| `leleby:hasMeasurement` | Characteristic | Measurement | 测量 | 7 |
| `leleby:underCondition` | Measurement/Requirement | Condition | 条件 | 7 |
| `leleby:targets` | Verification | VerificationTarget | 验证目标 | 8 |
| `leleby:hasResult` | Verification | VerificationResult | 验证结果 | 8 |
| `leleby:hasComplianceStatus` | ComplianceAssertion | ComplianceStatus | 符合状态 | 9 |
| `leleby:hasOutcome` | Decision | DecisionOutcome | 决策结果 | 10 |
| `leleby:triggersAction` | DecisionOutcome | Action | 触发行动 | 10 |
| `leleby:supportsClaim` | Evidence | Claim | 支持声明 | 11 |
| `leleby:hasRestriction` | Product/Service | Restriction | 限制 | 12 |


## 18. 附录 B：版本变更记录

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v1.0 | 2026-07-27 | 初始冻结版：十大模块 |
| **v1.1** | **2026-07-29** | **架构对齐版：1) 依赖本体从 v0.1 升级至 v0.9 架构；2) 关系更新：hasCapability → providesCapability / realizesCapability；3) Product 模型增加 ProductType / ProductModel / ProductInstance 三层结构；4) 新增 Verification 模块；5) 新增 Decision 模块；6) 新增 Process 模块；7) Compliance 升级为三级结构（Assertion / Assessment / Declaration）；8) 完善 Measurement 和 Evidence 模型；9) 更新 JSON-LD 数据包模板；10) 增加完整的 ESM-AI 闭环说明** |


*— leleby Enterprise Semantic Model v1.1 文档结束 —*