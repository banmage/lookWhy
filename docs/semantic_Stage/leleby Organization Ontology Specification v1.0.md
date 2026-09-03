# leleby Organization Ontology Specification v1.0

**文档版本：** v1.0 — Enterprise Semantic Identity Edition（企业语义身份版）

**文档类型：** 模块规范（Module Ontology Specification）

**文档状态：** ✅ **正式冻结（Frozen）** — 组织核心模型已冻结，仅允许模块内部扩展

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.1

**依赖模块：**
- `llb` Foundation Vocabulary Specification v1.0
- `lbo-core` Core Ontology Specification v1.0

**命名空间：** `https://ontology.leleby.org/organization/`

**推荐前缀：** `lorg`

**目标受众：** 本体架构师、企业数据架构师、AI Agent 开发者、商业智能工程师


## 目录

1. 引言
   1.1 目的
   1.2 核心定位
   1.3 设计原则
   1.4 与其他模块的关系

2. 命名空间声明

3. 核心概念模型
   3.1 组织四维模型
   3.2 组织类型与状态模型
   3.3 组织角色与能力模型
   3.4 组织关系模型

4. 类规范
   4.1 Organization
   4.2 LegalEntity
   4.3 OrganizationalUnit
   4.4 VirtualOrganization
   4.5 OrganizationStatus
   4.6 OrganizationType
   4.7 OrganizationRole
   4.8 OrganizationRoleAssignment
   4.9 OrganizationRelationship
   4.10 OwnershipRelationship
   4.11 ControlRelationship
   4.12 PartnershipRelationship
   4.13 OrganizationLifecycleEvent
   4.14 OrganizationLocation

5. 对象属性
   5.1 身份与归属属性
   5.2 状态与生命周期属性
   5.3 角色与能力属性
   5.4 关系属性
   5.5 位置与资源属性

6. 数据属性

7. 推理规则
   7.1 角色继承规则
   7.2 能力推断规则
   7.3 控制传递规则

8. SHACL 验证约束

9. 与外部标准的对齐

10. 完整示例

11. 冻结声明

12. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Organization Ontology 是 leleby 语义基础设施中**企业语义身份（Enterprise Semantic Identity）**的核心模块。它定义了描述商业组织主体的语义模型，支撑企业 AI 商业名片、供应链主体识别、企业能力搜索和组织关系推理。

本规范回答以下核心问题：

- 一个企业是谁？（身份）
- 企业当前处于什么状态？（状态）
- 企业承担什么商业角色？（角色）
- 企业与其他组织有什么关系？（关系）
- 企业拥有和提供什么能力？（能力）
- 企业如何参与产品、过程、标准符合性和商业活动？（参与）

本规范是 leleby Organization Ontology 的正式冻结版本 v1.0。

### 1.2 核心定位

> **Organization Ontology 是 leleby 企业 AI 商业名片的主体模型，而非传统的企业主数据模型（MDM）。**

它与 Core Ontology 的关系：

```
llb: Foundation Vocabulary（基础词汇）
    │
    └── lbo-core: Core Ontology（核心工业概念）
            │
            └── lbo-organization: Organization Ontology（组织模型）
                    │
                    ├── LegalEntity（法律实体）
                    ├── OrganizationalUnit（内部组织）
                    └── VirtualOrganization（虚拟组织）
```

**Organization Ontology 不重新定义：**
- `Entity`、`Identifier`、`Document`、`Statement`、`Agent`（来自 `llb:`）
- `Product`、`Capability`、`Process`、`Resource`、`Requirement`、`Assessment`（来自 `lbo-core:`）

**Organization Ontology 负责：**
- `Organization` 的身份、状态、角色、关系
- `LegalEntity`、`OrganizationalUnit`、`VirtualOrganization`
- 组织生命周期事件
- 组织角色分配（RoleAssignment）

### 1.3 设计原则

**原则一：组织是持续存在的实体，而非分类标签**

`Organization` 是持久的社会经济实体。组织类型（如 `PublicCompany`、`Manufacturer`）是状态/角色，而非身份本身。

**原则二：身份、状态、角色、关系四维分离**

- **身份**：组织本身（LegalEntity、OrganizationalUnit）
- **状态**：组织在特定时期的分类（OrganizationStatus）
- **角色**：组织在特定上下文中承担的功能（RoleAssignment）
- **关系**：组织之间的关联（Ownership、Control、Partnership）

**原则三：角色是时间绑定的分配，而非固定属性**

角色（如 Manufacturer、Supplier）通过 `RoleAssignment` 表达，支持 `validFrom`/`validUntil`。

**原则四：组织类型是状态，不是子类**

不采用 `PublicCompany`、`Subsidiary` 作为 `Organization` 的子类，而是通过 `OrganizationType` 作为状态属性。

**原则五：与 Core Ontology 边界清晰**

`Organization` 继承自 `lbo-core:Organization`（Core Ontology 中的组织基类），不直接继承 `llb:Agent`。Core Ontology 提供组织的最基本定义，Organization Ontology 提供企业语义身份的完整建模。

### 1.4 与其他模块的关系

```
llb: Foundation Vocabulary（基础词汇）
    │
    └── lbo-core: Core Ontology
            │
            ├── lbo-core:Organization（组织基类）
            │       │
            │       └── lorg:Organization（本模块扩展）
            │
            ├── lbo-core:Capability（能力）
            │       └── 被 lorg:Organization 引用
            │
            └── lbo-core:Process（过程）
                    └── 被 lorg:Organization 引用
```

**Organization Ontology 不依赖：**
- `lbo-product:Product Ontology`
- `lbo-compliance:Compliance Ontology`
- `lbo-resource:Resource Ontology`

这些模块通过 `lbo-core:` 的接口与 Organization 交互。


## 2. 命名空间声明

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix llb: <https://ontology.leleby.org/foundation/> .
@prefix lbo-core: <https://ontology.leleby.org/core/> .
@prefix lorg: <https://ontology.leleby.org/organization/> .

<https://ontology.leleby.org/organization/>
    rdf:type owl:Ontology ;
    owl:versionInfo "1.0" ;
    owl:imports <https://ontology.leleby.org/foundation/> ;
    owl:imports <https://ontology.leleby.org/core/> ;
    rdfs:label "leleby Organization Ontology" ;
    rdfs:comment "leleby 组织语义模型，用于企业语义身份、供应链主体识别和组织关系推理" .
```


## 3. 核心概念模型

### 3.1 组织四维模型

```text
                        Organization
                             |
        ┌────────────────────┼────────────────────┐
        |                    |                    |
   Identity              Status              Relationship
   （是谁）             （什么状态）            （什么关系）
        |                    |                    |
   LegalEntity       OrganizationStatus    Ownership
   OrganizationalUnit OrganizationType     Control
   VirtualOrganization                    Partnership
        |                    |
        └────────┬───────────┘
                 |
                Role
              （做什么）
                 |
        OrganizationRoleAssignment
```

### 3.2 组织类型与状态模型

```text
Organization
    |
    +-- hasStatus (时间绑定)
    |
    OrganizationStatus
        |
        +-- hasType (OrganizationType)
        +-- validFrom
        +-- validUntil
        +-- source
        +-- confidence
```

OrganizationType 采用 SKOS Concept Scheme 管理，支持多维度分类。

### 3.3 组织角色与能力模型

```text
Organization
    |
    +-- hasRoleAssignment (时间绑定)
    |
    OrganizationRoleAssignment
        |
        +-- role (OrganizationRole)
        +-- validFrom / validUntil
        +-- context (e.g., "Outdoor Lighting")
        +-- scope (e.g., "Global")
        +-- evidence (llb:Document)
    |
    +-- providesCapability (直接引用 lbo-core:Capability)
    |
    lbo-core:Capability
```

### 3.4 组织关系模型

```text
Organization --→ OwnershipRelationship
                     |
                     +-- owns (Organization)
                     +-- ownershipPercentage
                     +-- validPeriod

Organization --→ ControlRelationship
                     |
                     +-- controls (Organization)
                     +-- controlType
                     +-- validPeriod

Organization --→ PartnershipRelationship
                     |
                     +-- partner (Organization)
                     +-- partnershipType
                     +-- validPeriod
```


## 4. 类规范

### 4.1 Organization

```turtle
lorg:Organization
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Organization ;
    rdfs:label "Organization" ;
    rdfs:comment "一个商业或社会经济组织，具有身份、状态、角色、关系和能力。本类继承自 lbo-core:Organization，并在其基础上扩展企业语义身份所需的关系和属性" .
```

**继承链：**
- `llb:Entity` ← `lbo-core:Organization` ← `lorg:Organization`

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lorg:hasLegalName` | 法定名称 | 0..1 |
| `lorg:hasTradeName` | 商号/品牌名称 | 0..1 |
| `lorg:hasDescription` | 企业描述 | 0..1 |
| `lorg:hasWebsite` | 官网 URL | 0..1 |
| `lorg:hasLogo` | 标识 URL | 0..1 |

### 4.2 LegalEntity

```turtle
lorg:LegalEntity
    rdf:type owl:Class ;
    rdfs:subClassOf lorg:Organization ;
    rdfs:label "LegalEntity" ;
    rdfs:comment "具有独立法律权利和义务的组织实体，如有限公司、股份公司等" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lorg:legalName` | 法定名称（必填） | 1 |
| `lorg:registrationNumber` | 注册号 | 0..1 |
| `lorg:jurisdiction` | 注册司法区域 | 1 |
| `lorg:incorporationDate` | 成立日期 | 0..1 |
| `lorg:legalForm` | 公司形式（如 "Ltd"、"AG"） | 0..1 |

### 4.3 OrganizationalUnit

```turtle
lorg:OrganizationalUnit
    rdf:type owl:Class ;
    rdfs:subClassOf lorg:Organization ;
    rdfs:label "OrganizationalUnit" ;
    rdfs:comment "组织内部不具有独立法律身份的业务单元，如部门、事业部、工厂等" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lorg:unitName` | 单元名称 | 1 |
| `lorg:unitType` | 单元类型（Department/Division/BusinessUnit/Laboratory/FactoryOrganization） | 0..1 |
| `lorg:partOf` | 所属组织 | 1 |

### 4.4 VirtualOrganization

```turtle
lorg:VirtualOrganization
    rdf:type owl:Class ;
    rdfs:subClassOf lorg:Organization ;
    rdfs:label "VirtualOrganization" ;
    rdfs:comment "不具有独立法律实体身份但具有组织行为的虚拟组织，如行业协会、联盟、项目联合体等" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lorg:hasMember` | 成员组织 | 0..* |
| `lorg:formationDate` | 成立日期 | 0..1 |
| `lorg:dissolutionDate` | 解散日期 | 0..1 |

### 4.5 OrganizationStatus

```turtle
lorg:OrganizationStatus
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "OrganizationStatus" ;
    rdfs:comment "组织在特定时间段内的状态描述，包含组织类型、法律形式等分类信息" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lorg:hasType` | 组织类型（引用 OrganizationType） | 1 |
| `lorg:validFrom` | 状态开始时间 | 1 |
| `lorg:validUntil` | 状态结束时间 | 0..1 |
| `lorg:source` | 来源 | 0..1 |
| `lorg:confidence` | 可信度（0-1） | 0..1 |

### 4.6 OrganizationType

```turtle
lorg:OrganizationType
    rdf:type owl:Class ;
    rdfs:subClassOf skos:Concept ;
    rdfs:label "OrganizationType" ;
    rdfs:comment "组织类型的概念，采用 SKOS 管理，支持多维度分类" .
```

**预定义类型（示例）：**

| 类型 | 说明 |
|---|---|
| `lorg:IndependentEnterprise` | 独立企业 |
| `lorg:EnterpriseGroup` | 企业集团 |
| `lorg:HoldingCompany` | 控股公司 |
| `lorg:Subsidiary` | 子公司 |
| `lorg:JointVenture` | 合资企业 |
| `lorg:PublicCompany` | 上市公司 |
| `lorg:PrivateCompany` | 私营公司 |
| `lorg:GovernmentOrganization` | 政府组织 |
| `lorg:NonProfitOrganization` | 非营利组织 |

### 4.7 OrganizationRole

```turtle
lorg:OrganizationRole
    rdf:type owl:Class ;
    rdfs:subClassOf skos:Concept ;
    rdfs:label "OrganizationRole" ;
    rdfs:comment "组织在商业活动中承担的角色概念" .
```

**预定义角色（示例）：**

| 角色 | 说明 |
|---|---|
| `lorg:Manufacturer` | 制造商 |
| `lorg:Supplier` | 供应商 |
| `lorg:Distributor` | 分销商 |
| `lorg:ServiceProvider` | 服务提供商 |
| `lorg:BrandOwner` | 品牌拥有者 |
| `lorg:TechnologyProvider` | 技术提供商 |
| `lorg:CertificationBody` | 认证机构 |
| `lorg:TestingLaboratory` | 测试实验室 |
| `lorg:ResearchInstitute` | 研究机构 |

### 4.8 OrganizationRoleAssignment

```turtle
lorg:OrganizationRoleAssignment
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "OrganizationRoleAssignment" ;
    rdfs:comment "组织在特定时间范围和上下文中承担的角色分配" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lorg:hasRole` | 承担的角色 | 1 |
| `lorg:validFrom` | 角色开始时间 | 0..1 |
| `lorg:validUntil` | 角色结束时间 | 0..1 |
| `lorg:context` | 上下文（如行业、产品线） | 0..1 |
| `lorg:scope` | 范围（如 "Global"、"Regional"） | 0..1 |
| `lorg:evidence` | 证据文档 | 0..1 |

### 4.9 OrganizationRelationship

```turtle
lorg:OrganizationRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Statement ;
    rdfs:label "OrganizationRelationship" ;
    rdfs:comment "两个组织之间关系的抽象基类" .
```

### 4.10 OwnershipRelationship

```turtle
lorg:OwnershipRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lorg:OrganizationRelationship ;
    rdfs:label "OwnershipRelationship" ;
    rdfs:comment "所有权关系" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lorg:owner` | 所有者 | 1 |
| `lorg:ownedEntity` | 被拥有实体 | 1 |
| `lorg:ownershipPercentage` | 持股比例 | 0..1 |
| `lorg:validPeriod` | 有效期间 | 0..1 |

### 4.11 ControlRelationship

```turtle
lorg:ControlRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lorg:OrganizationRelationship ;
    rdfs:label "ControlRelationship" ;
    rdfs:comment "控制关系（区别于所有权）" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lorg:controller` | 控制方 | 1 |
| `lorg:controlledEntity` | 被控制实体 | 1 |
| `lorg:controlType` | 控制类型（Operational/Financial/Strategic） | 0..1 |
| `lorg:validPeriod` | 有效期间 | 0..1 |

### 4.12 PartnershipRelationship

```turtle
lorg:PartnershipRelationship
    rdf:type owl:Class ;
    rdfs:subClassOf lorg:OrganizationRelationship ;
    rdfs:label "PartnershipRelationship" ;
    rdfs:comment "合作关系" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lorg:partnerA` | 合作方A | 1 |
| `lorg:partnerB` | 合作方B | 1 |
| `lorg:partnershipType` | 合作类型（Strategic/JointVenture/Technology） | 0..1 |
| `lorg:validPeriod` | 有效期间 | 0..1 |

### 4.13 OrganizationLifecycleEvent

```turtle
lorg:OrganizationLifecycleEvent
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Event ;
    rdfs:label "OrganizationLifecycleEvent" ;
    rdfs:comment "组织生命周期中的重要事件" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lorg:eventType` | 事件类型（Creation/Merger/Acquisition/SpinOff/Transformation/Liquidation） | 1 |
| `lorg:eventDate` | 事件日期 | 1 |
| `lorg:source` | 来源 | 0..1 |
| `lorg:affectedOrganization` | 受影响组织 | 1 |

### 4.14 OrganizationLocation

```turtle
lorg:OrganizationLocation
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Location ;
    rdfs:label "OrganizationLocation" ;
    rdfs:comment "组织的位置/场所" .
```

**核心属性：**

| 属性 | 说明 | 基数 |
|---|---|---|
| `lorg:locationType` | 类型（Headquarters/ManufacturingSite/Office/Warehouse/Laboratory） | 0..1 |
| `lorg:address` | 地址 | 0..1 |
| `lorg:country` | 国家 | 0..1 |
| `lorg:region` | 地区 | 0..1 |
| `lorg:geoCoordinate` | 地理坐标 | 0..1 |


## 5. 对象属性

### 5.1 身份与归属属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lorg:hasIdentifier` | `lorg:Organization` | `llb:Identifier` | 组织标识符 |
| `lorg:hasLegalName` | `lorg:Organization` | `xsd:string` | 法定名称 |
| `lorg:hasTradeName` | `lorg:Organization` | `xsd:string` | 商号 |
| `lorg:hasDescription` | `lorg:Organization` | `xsd:string` | 描述 |
| `lorg:hasWebsite` | `lorg:Organization` | `xsd:anyURI` | 官网 |
| `lorg:hasLogo` | `lorg:Organization` | `xsd:anyURI` | 标识 |

### 5.2 状态与生命周期属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lorg:hasStatus` | `lorg:Organization` | `lorg:OrganizationStatus` | 组织当前/历史状态 |
| `lorg:hasType` | `lorg:OrganizationStatus` | `lorg:OrganizationType` | 状态包含的类型 |
| `lorg:hasLifecycleEvent` | `lorg:Organization` | `lorg:OrganizationLifecycleEvent` | 生命周期事件 |

### 5.3 角色与能力属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lorg:hasRoleAssignment` | `lorg:Organization` | `lorg:OrganizationRoleAssignment` | 角色分配 |
| `lorg:hasRole` | `lorg:OrganizationRoleAssignment` | `lorg:OrganizationRole` | 具体角色 |
| `lorg:providesCapability` | `lorg:Organization` | `lbo-core:Capability` | 提供的能力（直接引用 Core） |

### 5.4 关系属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lorg:hasRelationship` | `lorg:Organization` | `lorg:OrganizationRelationship` | 组织间关系 |
| `lorg:owns` | `lorg:Organization` | `lorg:Organization` | 所有权关系 |
| `lorg:controls` | `lorg:Organization` | `lorg:Organization` | 控制关系 |
| `lorg:hasPartner` | `lorg:Organization` | `lorg:Organization` | 合作关系 |
| `lorg:partOf` | `lorg:OrganizationalUnit` | `lorg:Organization` | 所属组织 |

### 5.5 位置与资源属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lorg:hasLocation` | `lorg:Organization` | `lorg:OrganizationLocation` | 组织位置 |
| `lorg:ownsResource` | `lorg:Organization` | `lbo-core:Resource` | 拥有的资源 |


## 6. 数据属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lorg:legalName` | `lorg:LegalEntity` | `xsd:string` | 法定名称 |
| `lorg:registrationNumber` | `lorg:LegalEntity` | `xsd:string` | 注册号 |
| `lorg:jurisdiction` | `lorg:LegalEntity` | `xsd:string` | 管辖区域 |
| `lorg:incorporationDate` | `lorg:LegalEntity` | `xsd:date` | 成立日期 |
| `lorg:legalForm` | `lorg:LegalEntity` | `xsd:string` | 法律形式 |
| `lorg:validFrom` | `lorg:OrganizationStatus` | `xsd:date` | 状态开始 |
| `lorg:validUntil` | `lorg:OrganizationStatus` | `xsd:date` | 状态结束 |
| `lorg:confidence` | `lorg:OrganizationStatus` | `xsd:double` | 可信度 |
| `lorg:ownershipPercentage` | `lorg:OwnershipRelationship` | `xsd:double` | 持股比例 |
| `lorg:eventType` | `lorg:OrganizationLifecycleEvent` | `xsd:string` | 事件类型 |


## 7. 推理规则

### 7.1 角色继承规则

**规则1：组织单元继承其所属组织的角色能力**

```
IF OrganizationalUnit partOf Organization
AND Organization hasRoleAssignment RoleAssignment
THEN OrganizationalUnit hasRoleAssignment RoleAssignment
```

### 7.2 能力推断规则

**规则2：组织制造产品 ⇒ 具有制造能力**

```
IF Organization manufactures Product (from Core)
THEN Organization providesCapability ManufacturingCapability
```

**规则3：组织执行某过程 ⇒ 具有相应能力**

```
IF Organization performs Process (from Core)
THEN Organization providesCapability Capability
```

### 7.3 控制传递规则

**规则4：控制关系传递**

```
IF Organization A controls Organization B
AND Organization B controls Organization C
THEN Organization A controls Organization C
```

**规则5：所有权传递**

```
IF Organization A owns Organization B
AND Organization B owns Organization C
THEN Organization A owns Organization C
```


## 8. SHACL 验证约束

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix lorg: <https://ontology.leleby.org/organization/> .

# Organization 必须有至少一个名称
lorg:OrganizationShape
    a sh:NodeShape ;
    sh:targetClass lorg:Organization ;
    sh:or (
        [ sh:path lorg:hasLegalName ; sh:minCount 1 ]
        [ sh:path lorg:hasTradeName ; sh:minCount 1 ]
    ) ;
    sh:message "Organization 必须有法定名称或商号" .

# LegalEntity 必须有法定名称和管辖区域
lorg:LegalEntityShape
    a sh:NodeShape ;
    sh:targetClass lorg:LegalEntity ;
    sh:property [
        sh:path lorg:legalName ;
        sh:minCount 1 ;
        sh:message "LegalEntity 必须有法定名称"
    ] ;
    sh:property [
        sh:path lorg:jurisdiction ;
        sh:minCount 1 ;
        sh:message "LegalEntity 必须有管辖区域"
    ] .

# OrganizationalUnit 必须有单元名称和所属组织
lorg:OrganizationalUnitShape
    a sh:NodeShape ;
    sh:targetClass lorg:OrganizationalUnit ;
    sh:property [
        sh:path lorg:unitName ;
        sh:minCount 1 ;
        sh:message "OrganizationalUnit 必须有单元名称"
    ] ;
    sh:property [
        sh:path lorg:partOf ;
        sh:minCount 1 ;
        sh:message "OrganizationalUnit 必须有所属组织"
    ] .

# OrganizationStatus 必须有类型和生效时间
lorg:OrganizationStatusShape
    a sh:NodeShape ;
    sh:targetClass lorg:OrganizationStatus ;
    sh:property [
        sh:path lorg:hasType ;
        sh:minCount 1 ;
        sh:message "OrganizationStatus 必须有类型"
    ] ;
    sh:property [
        sh:path lorg:validFrom ;
        sh:minCount 1 ;
        sh:message "OrganizationStatus 必须有生效时间"
    ] .

# RoleAssignment 必须有角色
lorg:RoleAssignmentShape
    a sh:NodeShape ;
    sh:targetClass lorg:OrganizationRoleAssignment ;
    sh:property [
        sh:path lorg:hasRole ;
        sh:minCount 1 ;
        sh:message "RoleAssignment 必须有角色"
    ] .
```


## 9. 与外部标准的对齐

### 9.1 W3C ORG Vocabulary

| W3C ORG | leleby Organization Ontology |
|---|---|
| `org:Organization` | `lorg:Organization` |
| `org:OrganizationalUnit` | `lorg:OrganizationalUnit` |
| `org:Role` | `lorg:OrganizationRole` |
| `org:Site` | `lorg:OrganizationLocation` |

### 9.2 schema.org

| schema.org | leleby Organization Ontology |
|---|---|
| `schema:Organization` | `lorg:Organization` |
| `schema:legalName` | `lorg:legalName` |
| `schema:logo` | `lorg:hasLogo` |
| `schema:url` | `lorg:hasWebsite` |

### 9.3 FIBO

FIBO 的 Party、Organization、LegalEntity 概念被参考，但 leleby 采用更轻量、面向 AI 推理的设计。


## 10. 完整示例

### 10.1 Yunda Lighting 企业语义身份

**组织身份：**

```turtle
llc:YundaLighting
    a lorg:LegalEntity ;
    lorg:legalName "Yunda Lighting Co., Ltd." ;
    lorg:tradeName "Yunda Lighting" ;
    lorg:jurisdiction "China" ;
    lorg:incorporationDate "2010-05-15"^^xsd:date ;
    lorg:legalForm "Ltd" ;
    lorg:hasWebsite "https://www.yundalighting.com"^^xsd:anyURI .
```

**组织状态：**

```turtle
llc:YundaLighting_Status_2025
    a lorg:OrganizationStatus ;
    lorg:hasType lorg:IndependentEnterprise ;
    lorg:validFrom "2025-01-01"^^xsd:date ;
    lorg:source "Annual Report 2025" ;
    lorg:confidence "0.95"^^xsd:double .

llc:YundaLighting
    lorg:hasStatus llc:YundaLighting_Status_2025 .
```

**组织角色：**

```turtle
llc:YundaLighting_Role_Manufacturer
    a lorg:OrganizationRoleAssignment ;
    lorg:hasRole lorg:Manufacturer ;
    lorg:context "Outdoor LED Lighting" ;
    lorg:validFrom "2010-05-15"^^xsd:date ;
    lorg:scope "Global" .

llc:YundaLighting
    lorg:hasRoleAssignment llc:YundaLighting_Role_Manufacturer .
```

**组织能力：**

```turtle
llc:YundaLighting_Capability
    a lbo-core:Capability ;
    lbo-core:hasCapabilityName "Outdoor LED Luminaire Manufacturing" ;
    lbo-core:hasCapabilityType lbo-core:ManufacturingCapability .

llc:YundaLighting
    lorg:providesCapability llc:YundaLighting_Capability .
```

**组织位置：**

```turtle
llc:YundaLighting_Location
    a lorg:OrganizationLocation ;
    lorg:locationType lorg:Headquarters ;
    lorg:address "No. 123, Lighting Road, Zhongshan, China" ;
    lorg:country "China" .

llc:YundaLighting
    lorg:hasLocation llc:YundaLighting_Location .
```

### 10.2 组织关系示例

```turtle
# 所有权关系
llc:SiemensAG
    a lorg:LegalEntity ;
    lorg:legalName "Siemens AG" .

llc:SiemensUSA
    a lorg:LegalEntity ;
    lorg:legalName "Siemens USA Inc." .

llc:Siemens_Owns_USA
    a lorg:OwnershipRelationship ;
    lorg:owner llc:SiemensAG ;
    lorg:ownedEntity llc:SiemensUSA ;
    lorg:ownershipPercentage "100.0"^^xsd:double .

llc:SiemensAG
    lorg:hasRelationship llc:Siemens_Owns_USA .
```


## 11. 冻结声明

### 11.1 冻结范围

v1.0 确认后，以下内容进入**冻结状态**：

- ✅ 所有核心类（Organization、LegalEntity、OrganizationalUnit、VirtualOrganization、OrganizationStatus、OrganizationType、OrganizationRole、OrganizationRoleAssignment、OrganizationRelationship、OwnershipRelationship、ControlRelationship、PartnershipRelationship、OrganizationLifecycleEvent、OrganizationLocation）
- ✅ 所有核心对象属性
- ✅ 命名空间 `https://ontology.leleby.org/organization/`
- ✅ 与 Core Ontology 的继承关系
- ✅ 核心推理规则

### 11.2 冻结后允许

- ✅ 新增组织类型（OrganizationType SKOS concepts）
- ✅ 新增角色类型（OrganizationRole SKOS concepts）
- ✅ 新增位置类型
- ✅ 新增生命周期事件类型
- ✅ 新增关系子类（如 SupplyRelationship）

### 11.3 冻结后禁止

- ❌ **修改或删除任何现有类**
- ❌ **修改或删除任何现有属性**
- ❌ **改变继承关系**
- ❌ **在 Organization Ontology 中定义产品、合规、资源等不属于组织模型的概念**
- ❌ **直接将 Organization 子类化到具体企业（如 YundaLighting）——企业实例属于 `llc:` 层**


## 12. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v0.1 | 2026-07-28 | 初始版本 |
| v0.2 | 2026-07-28 | 引入组织生命周期模型 |
| **v1.0** | **2026-07-31** | **企业语义身份版（正式冻结）**：1）继承关系调整为 `lbo-core:Organization`（而非直接 `llb:Agent`）；2）增加 `VirtualOrganization`；3）强化 `OrganizationRoleAssignment`（支持时间绑定和上下文）；4）移除 `OrganizationResource` 细分类，引用 `lbo-core:Resource`；5）移除 `OrganizationCertification`，由 Compliance Ontology 负责；6）Namespace 更新为 `https://ontology.leleby.org/organization/`；7）完善 SHACL 约束；8）增加推理规则；9）明确与 Core Ontology 的边界 |


*— leleby Organization Ontology Specification v1.0 — Enterprise Semantic Identity Edition —*