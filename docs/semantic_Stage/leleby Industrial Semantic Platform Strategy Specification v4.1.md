# leleby Industrial Semantic Platform Strategy Specification v4.1

**leleby 工业语义平台战略规划**

| 项目 | 内容 |
|------|------|
| 文档版本 | v4.1 |
| 编制日期 | 2026年8月 |
| 文档性质 | 本文件为 leleby 平台体系的**顶层战略与架构约束文件**，适用于2026—2030年发展周期。它同时约束长期愿景、中期能力与近期MVP，是后续架构设计、本体开发和项目迭代的根本依据。 |
| 前序版本 | v2.0（Industrial Semantic Foundation & Standard Application Platform）；v3.1.1（leleby Strategy — 工业语义基础设施架构版）；v4.0（战略整合基线版） |
| 整合说明 | 本文件以 v2.0 的平台分层架构为骨架，以 v3.1.1 的战略定位、生态愿景和 Ontology 体系为内容填充，合并两个前序版本形成统一战略基线。v4.1 在 v4.0 基础上新增品牌体系澄清、语义资产交换层、工业分类框架及生态价值链章节。 |


## 1. 引言

### 1.1 编写目的

本文件为 leleby 平台体系的**顶层战略与架构约束文件**，旨在明确：

- leleby 的长期战略定位与核心使命
- 工业语义平台与各应用平台的层级关系
- 核心语义原则与 Ontology 架构
- 第一阶段（Standard Application Platform）的 MVP 范围与功能
- 与 lookWhy 平台的生态协同关系
- 长期演化路线

本文件是后续架构设计、本体开发和项目迭代的根本依据。

### 1.2 项目名称

| 层级 | 名称 | 说明 |
|------|------|------|
| **基础平台名称** | leleby Industrial Semantic Platform | 长期存在的工业语义基础设施 |
| **第一阶段应用平台名称** | leleby Standard Application Platform | 标准语义建模 + 产品合规验证闭环 |

### 1.3 与前序版本的关系

| 前序版本 | 核心贡献 | 在本文件中的处理 |
|---------|---------|-----------------|
| **v2.0（Industrial Semantic Foundation & Standard Application Platform）** | 平台分层架构（基础平台 + 应用平台）；Standard Application Platform MVP 范围 | 作为本文件的**架构骨架**，完整保留 |
| **v3.1.1（leleby Strategy — 工业语义基础设施架构版）** | 战略愿景、商业定位、Ontology 体系、Namespace Architecture | 作为本文件的**战略与本体内容**，融入各章节 |
| **v4.0（战略整合基线版）** | 完成 v2.0 与 v3.1.1 的首次整合 | 作为本文件的**整合基础** |

两个前序版本（v2.0 与 v3.1.1）在本文件发布后**不再单独维护**，所有后续修订均以本文件为准。

### 1.4 与生态战略及其他文档的关系

本文件是 leleby & lookWhy 工业知识与语义生态战略规划的下游文档：

```
leleby & lookWhy 工业知识与语义生态战略规划
                （生态顶层战略）
                      │
      ┌───────────────┴───────────────┐
      │                               │
leleby Industrial Semantic   lookWhy 战略与需求说明书
   Platform Strategy v4.1           （v1.1 企业知识资产生产）
      │
      ├── Ontology Architecture Specification
      ├── Standard Application Platform Specification
      └── Semantic Package Specification
```

本文件定义的 leleby 平台定位、边界与共享基础设施，与生态战略文件第3章（两个系统的总体关系）和第4章（核心边界原则）保持一致。

### 1.5 "leleby"品牌与平台体系关系澄清

"leleby"是工业语义生态体系的**品牌名称**，其下包含多个层次的平台产品：

```
leleby（品牌 / 生态体系）
    │
    ├── leleby Industrial Semantic Platform
    │   （长期基础平台 / 语义基础设施）
    │
    ├── leleby Standard Application Platform
    │   （第一阶段应用平台 / 标准语义与合规验证）
    │
    └── Future Application Platforms
        （产品工程平台 / 制造平台 / 供应链平台等）
```

**核心关系**：

| 概念 | 含义 | 定位 |
|------|------|------|
| **leleby** | 品牌名称与生态体系标识 | 对外品牌、商业实体、生态体系 |
| **Industrial Semantic Platform** | 长期语义基础设施 | 内部架构概念，非独立产品 |
| **Standard Application Platform** | 第一阶段应用平台 | 当前MVP阶段的产品形态 |
| **Future Applications** | 未来扩展应用 | 基于同一基础设施的后续产品 |

在对外沟通中，"leleby"指代整个生态体系；在内部架构讨论中，须区分基础设施层与应用平台层。


## 2. 平台体系定位

### 2.1 核心定位

leleby 的愿景是：**构建面向 AI 时代的企业商业语义网络，让企业、产品、能力、标准和要求成为机器可理解的商业对象，支撑 AI Agent 完成从要求理解、产品发现、规范验证、商务判断到交易决策的完整推理闭环。**

leleby builds the semantic infrastructure for AI-driven B2B discovery, matching and transaction — enabling AI systems to understand enterprise capabilities, product specifications, standards conformance, commercial policies, and procurement requirements.

**核心定位**：leleby 是面向 AI 驱动 B2B 供需匹配和自动交易的商业语义基础设施。它用机器可理解、可验证的方式表达商业世界的完整语义链——从外部法规/标准输入，到企业工程设计转化，到产品规格定义，到实物验证，再到采购需求匹配——使 AI 系统能够完成可追溯、可解释的商业推理。

### 2.2 平台体系层级

leleby 采用**基础平台 + 应用平台**的两级体系架构：

```
┌─────────────────────────────────────────────────────────────┐
│           leleby Industrial Semantic Platform              │
│              （长期基础平台 / 父级战略）                      │
│  定位：面向AI时代的工业语义基础设施，管理本体、知识图谱、       │
│        推理引擎、语义包运行时环境                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 承载
                              ▼
┌─────────────────────────────────────────────────────────────┐
│        leleby Standard Application Platform                │
│           （第一阶段应用平台 / 子级战略）                    │
│  定位：标准语义建模 + 产品合规验证闭环                       │
│  范围：Standard → Requirement → Verification → Compliance  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 未来扩展
                              ▼
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        Product Platform  Manufacturing   Supply Chain
         （第二阶段）     Platform（第三）  Platform（第四）
```

**核心关系**：

- **leleby Industrial Semantic Platform**：长期存在的底层基础设施，提供本体、知识图谱、推理引擎、语义包运行环境等基础能力
- **leleby Standard Application Platform**：基于语义平台构建的第一个垂直应用，聚焦标准语义化与合规管理
- 未来所有新增应用（产品工程、制造、供应链等）均生长在同一语义基础设施之上，确保知识资产统一积累

### 2.3 包含与不包含

| 维度 | 内容 |
|------|------|
| **包含（语义事实层）** | 标准/法规语义、工程设计规范、产品规格、BOM、企业能力、验证事实、符合性、采购要求、商务规则 |
| **不包含（留给AI Agent）** | 最终采购决策、排序算法、商业谈判、UI 界面、固定价值判断 |
| **核心原则** | leleby 负责建立商业世界的完整语义事实层和可推理关系，AI Agent 基于事实层完成商业决策 |

### 2.4 Semantic Asset Exchange Layer（语义资产交换层）

leleby 作为工业语义生态的核心枢纽，须提供标准化的**语义资产交换层**，支持与 lookWhy 及其他外部系统进行受控数据交换。

#### 2.4.1 交换层的战略定位

```
                    ┌─────────────────────────────────────┐
                    │        知识资产生态系统              │
                    │  （lookWhy / 企业系统 / 行业平台）    │
                    └───────────────────┬─────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────┐
                    │      Semantic Asset Exchange Layer  │
                    │         （语义资产交换层）           │
                    │  - 协议适配  - 权限判断              │
                    │  - 格式转换  - 脱敏校验              │
                    └───────────────────┬─────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────┐
                    │         leleby 语义平台             │
                    │  （本体 / 语义包 / 推理引擎）        │
                    └─────────────────────────────────────┘
```

#### 2.4.2 交换层承担的核心职责

| 职责 | 说明 |
|------|------|
| **协议适配** | 支持 MCP、RESTful API、文件交换等多种接入协议 |
| **权限判断** | 校验调用方身份与授权范围，确保数据安全 |
| **脱敏校验** | 对从 lookWhy 等系统流入的数据进行脱敏检查 |
| **格式转换** | 在 leleby 内部语义格式与外部系统格式间转换 |
| **审计留痕** | 记录所有跨系统数据交换操作 |

#### 2.4.3 支持的交换场景

| 数据来源 | 目标 | 数据类型 | 说明 |
|---------|------|---------|------|
| lookWhy | leleby | Level 3 公开语义资产（产品语义卡） | 主要数据流，需脱敏审批 |
| leleby | 外部AI Agent | 标准语义、产品语义、合规信息 | 通过MCP协议提供 |
| leleby | 标准组织 | 分类框架、行业语义包 | 双向交换 |
| leleby | 企业系统 | 标准化语义资产包 | 按需导出 |


## 3. 战略目标体系

leleby 的战略目标分为四个层次，从基础设施到商业应用逐层构建：

| 层次 | 目标 | 核心交付 |
|---|---|---|
| **L0: 基础设施层** | 建立工业商业语义基础设施 | Foundation Vocabulary + Core/Domain Ontology + Specification Meta Model |
| **L1: 供给侧语义资产** | 建立企业、产品、商务的语义化表达 | Enterprise Semantic Identity + Product Semantic Model + Business Capability Model |
| **L2: 要求侧语义资产** | 建立采购要求的语义化表达 | Procurement Requirement Ontology + Procurement Intent Pool |
| **L3: 智能商业应用** | 构建AI驱动的商业应用 | AI Matching + AI Procurement + Automated Transaction |

### 3.1 L0：工业语义基础设施层（Foundation）

**目标**：建立面向工业商业世界的开放语义基础设施，为所有上层应用提供语义底座。

| 序号 | 目标 | 说明 |
|---|---|---|
| 0.1 | Foundation Vocabulary | 定义元概念、标识、版本、文档、事件等基础语义 |
| 0.2 | Core Industrial Ontology | 定义 Product, Specification, Requirement, Capability, Measurement, Compliance 等核心工业类 |
| 0.3 | Domain Ontology | 定义电机、照明、电池等领域扩展本体 |
| 0.4 | Standard Semantic Package 体系 | 建立国际标准、国家标准、行业标准、企业标准、产品规范的语义化表达体系 |
| 0.5 | Specification Meta Model Ontology | 描述规范结构、约束表达、接口定义、能力描述与验证方法之间关系的元模型 |
| 0.6 | Version Governance 体系 | Git式标准版本管理、标准生命周期治理、适用性状态管理 |
| 0.7 | Compliance Reasoning 体系 | 合规推理框架、多标准并存处理、条款级引用与推理链可追溯 |

### 3.2 L1：供给侧语义资产层（Supply-Side Semantic Assets）

**目标**：将供给侧企业、产品、商务能力转化为机器可理解、可推理的语义数据。

| 序号 | 目标 | 说明 |
|---|---|---|
| 1.1 | Enterprise Semantic Identity | 企业AI商业名片——包含企业身份、能力、设备、认证、业绩的完整语义表达 |
| 1.2 | Product Semantic Identity | 产品AI商业名片——包含产品身份、BOM结构、技术规范、合规声明的完整语义表达 |
| 1.3 | Business Capability Model | 生产、服务、商务、物流、支付、售后等企业能力的语义模型 |
| 1.4 | Negative Constraint Model | 不支持、禁止、例外等负面约束的语义表达 |

### 3.3 L2：要求侧语义资产层（Demand-Side Semantic Assets）

**目标**：将采购要求转化为机器可理解、可推理的语义数据。

| 序号 | 目标 | 说明 |
|---|---|---|
| 2.1 | Procurement Requirement Ontology | 采购要求的完整语义模型，包含技术要求、商业要求、合规要求、偏好要求 |
| 2.2 | Procurement Intent Pool | 需方采购意图的结构化语义数据池，支持AI Agent查询和匹配 |
| 2.3 | Demand Constraint Model | 范围/枚举/逻辑/优先级/偏好的约束表达模型（must/should/may） |

### 3.4 L3：智能商业应用层（AI Business Applications）

**目标**：基于语义基础设施和语义资产，构建AI驱动的商业应用。

| 序号 | 目标 | 说明 |
|---|---|---|
| 3.1 | AI 供需匹配 | 基于要求约束和产品规格的智能匹配 |
| 3.2 | AI 智能采购 | 自动生成采购要求、智能选型、供应商发现 |
| 3.3 | Automated Transaction | 交易就绪判断、自动询价、自动交易触发 |


## 4. 核心语义原则

### 4.1 从文件驱动到知识驱动

**传统工业体系**（文件驱动）：
```
标准文件 → 人工理解 → 工程设计 → 人工验证
```

**leleby体系**（知识驱动）：
```
标准语义知识 → 计算机理解 → 智能辅助设计 → 自动符合性验证
```

### 4.2 标准不是文档，而是可计算知识

传统标准等同于PDF文件，leleby将标准解构为可计算的知识单元：

```
Standard（标准）
  └── Edition（版本）
        └── Scope（适用范围）
        └── Content Unit（内容单元）
              └── Normative Statement（规范性声明）
                    └── Requirement（要求）
                          └── Constraint（约束条件）
                          └── Binding Level（强制性等级）
                          └── Verification Method（验证方法）
                                └── Compliance Rule（合规判定规则）
```

### 4.3 多层约束语义模型（L1-L5）

在工业现实中，以下概念虽然中文都可能被称作"要求"，但语义本质完全不同：

| 概念 | 语义本质 | 来源 | 示例 |
|---|---|---|---|
| 法规（Regulation） | 法律强制约束 | 立法/监管机构 | CE, RoHS, REACH |
| 标准（Standard） | 推荐/强制技术规范 | 标准组织（IEC, ISO, GB） | IEC 60598 |
| 企业设计规范（Enterprise Standard） | 工程转化后的内部设计要求 | 企业研发/工程部门 | 设计裕度+20% |
| 产品规格（Product Specification） | 产品"是什么"的事实描述 | 产品定义/制造文件 | IP66, -40~60℃ |
| 测试结果（Test Result） | 特定实例的测量事实 | 检测/质控过程 | 样品A实测IP67 |
| 采购需求（Procurement Demand） | 客户"想要什么"的条件 | 采购方/项目方 | 需要IP≥65, 数量5000 |

**leleby 多层约束语义模型（L1-L5）** ：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     L1: 外部知识层（External Knowledge）                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │   法规        │  │   强制标准    │  │   自愿标准    │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
│                           │ 外部约束输入                                   │
│                           ▼                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                     L2: 工程与设计层（Engineering & Design）                │
│  企业设计规范 / 工程标准（吸收L1输入，结合企业工艺能力、成本、质量目标转化）   │
│                           │ 设计输出                                       │
│                           ▼                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                     L3: 产品定义层（Product Definition）                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │  产品型号规格  │  │    BOM结构    │  │  制造工艺    │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
│                           │ 产品定义事实                                   │
│                           ▼                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                     L4: 实物与验证层（Instance & Verification）             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │  产品实例     │──│   测量数据    │──│  符合性声明   │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
│  ⚠️ 测量数据是"事实"，不是"规格"。同一型号不同批次测量值可能不同。          │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     L5: 要求与商业层（Demand & Commerce）                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │  采购技术要求  │  │  商务合同条件  │  │  交付/物流   │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
│  采购需求通过约束匹配（Constraint Matching）连接 L3 产品规格和 L4 验证事实。  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 核心推理链路

**合规推理**：
L1（法规/标准） → L2（工程转化） → L4（验证事实） → 符合性判断

**匹配推理**：
L5（采购约束） → L3（产品规格） + L4（验证事实） + L1（标准引用） → 匹配结论

### 4.5 所有知识采用语义模型管理

系统核心并非传统数据库，而是 **leleby Semantic Model**。数据库仅是底层实现手段。

- 第一阶段：Neo4j（通过抽象层）
- 未来支持：GraphDB、Stardog、Amazon Neptune、NebulaGraph


## 5. Namespace Architecture（命名空间架构）

### 5.1 命名空间设计原则

leleby 的命名空间架构遵循以下原则：

1. **职责分离**——每个命名空间承担唯一的语义职责，互不重叠
2. **llb不包含Ontology语义**——`llb:` 仅提供基础词汇和元模型框架，不定义工业领域的概念类
3. **所有Ontology归属lbo**——`lbo:` 是唯一的Ontology命名空间，包含所有工业类和属性定义
4. **lbs是实例化应用**——`lbs:` 是基于Ontology的语义包，是Ontology的实例化应用
5. **商业与本体分离**——`llc:` 商业实例数据与语义定义分离
6. **继承方向单一**——`lbo` 可继承 `llb`，`llb` 不能依赖 `lbo`；`lbs` 可引用 `lbo` 和 `llb`

### 5.2 四层命名空间定义

| 命名空间 | 前缀 | 用途 | 示例 |
|---|---|---|---|
| **Foundation Namespace** | `llb` | leleby基础词汇定义（元概念、标识、版本、文档、事件等，不含工业Ontology） | `llb:Entity`, `llb:Identifier`, `llb:Version`, `llb:Document`, `llb:Statement`, `llb:Concept` |
| **Ontology Namespace** | `lbo` | leleby核心工业本体和领域本体（所有工业类、属性、关系的定义） | `lbo:Product`, `lbo:Specification`, `lbo:Requirement`, `lbo:Capability`, `lbo:Motor`, `lbo:Lighting`, `lbo:Measurement`, `lbo:TestMethod` |
| **Specification Namespace** | `lbs` | 标准语义包（具体标准、规范的语义表达，是Ontology的实例化应用） | `lbs:IEC-60034-1-2025`, `lbs:PPM-RM-001-v1.0`, `lbs:GB-18613-2020` |
| **Commercial Namespace** | `llc` | 商业实例数据（企业、产品、交易、测量数据） | `llc:yunda-lighting`, `llc:product-001`, `llc:measurement-001` |

### 5.3 命名空间间关系

```
llb:（Foundation Vocabulary - 不含Ontology语义）
    │  提供基础元概念（Entity, Identifier, Version, Document, Statement）
    ▼
lbo:（Ontology - 所有工业本体定义）
    │  扩展llb基础概念，定义工业领域类（Product, Specification, Motor, etc.）
    ├── 继承: lbo:Product rdfs:subClassOf llb:PhysicalEntity
    │  实例化为标准语义包
    ▼
lbs:（Semantic Package - 标准/规范的语义实例）
    │  引用lbo定义的类和属性，表达具体规范内容
    │  实例化为商业数据
    ▼
llc:（Commercial Data - 企业/产品/交易实例）
    │  引用lbs标准包和lbo本体，表达具体商业事实
    ▼
    （AI Agent查询与推理）
```

### 5.4 命名空间使用约束

| 约束 | 说明 |
|---|---|
| **llb不定义工业类** | `llb:` 不包含 `Product`、`Motor`、`Requirement` 等工业概念类；这些类属于 `lbo:` |
| **继承方向不可逆** | `lbo` 可继承 `llb`（如 `lbo:Product rdfs:subClassOf llb:PhysicalEntity`），但 `llb` 不可继承 `lbo` |
| **lbs不定义新类** | `lbs:` 不定义新的OWL类；所有类来自 `lbo:` 或 `llb:` |
| **llc不定义语义** | `llc:` 不定义任何类和属性；仅包含实例数据 |
| **lbs与llc的引用关系** | `llc:` 实例可引用 `lbs:` 标准语义包中的规范定义 |


## 6. Industrial Classification Framework（工业分类框架）

工业分类框架是 leleby 与 lookWhy 之间最大的公共基础之一。两个系统不采用单一分类树，而是采用**多维度工业分类框架**，各维度之间相互独立、可组合查询。

### 6.1 分类维度的战略价值

分类框架是工业语义基础设施的核心组成部分。通过将传统单树分类拆解为多维度独立分类，系统能够：

- 避免单一分类树无法表达知识多维属性的困境
- 支持跨维度的组合查询（如"船用 + BLDC + 防水"）
- 为AI采购和工程推理提供精确的语义匹配基础
- 兼容现有国家标准和国际标准分类体系

### 6.2 分类维度总览

| 维度 | 回答的问题 | 参考依据 | 主要使用者 |
|------|-----------|----------|-----------|
| **行业分类** | 谁在生产/谁在使用 | GB/T 4754、ISIC、NACE | leleby |
| **产品分类** | 是什么产品 | 产品本体、IEC 61360 | leleby、lookWhy |
| **技术分类** | 用什么技术实现 | 行业技术分类体系 | lookWhy、leleby |
| **应用领域分类** | 用在哪里 | 行业应用分类 | leleby |
| **功能能力分类** | 能做什么 | 功能本体 | leleby |
| **知识领域分类** | 属于什么知识领域 | GB/T 23703.7 | lookWhy |

### 6.3 行业分类（Industry Classification）

**回答的问题**：谁在生产？谁在使用？

**依据标准**：
- 中国：GB/T 4754-2017《国民经济行业分类》
- 国际：ISIC Rev.4（国际标准行业分类）
- 欧洲：NACE Rev.2（欧盟经济活动统计分类）

**示例**：
```
制造业（C）
  └── 铁路、船舶、航空航天和其他运输设备制造业（37）
        └── 船舶及相关装置制造（373）
```

**使用场景**：
- leleby：企业行业归属、供应商行业过滤
- lookWhy：知识资产的行业上下文标记

### 6.4 产品分类（Product Classification）

**回答的问题**：是什么产品？

**依据参考**：
- IEC 61360 标准数据元素类型及相关分类方案
- 产品本体（Product Ontology）
- 企业自定义扩展

**示例**：
```
Product
  └── Electric Motor
        └── DC Motor
              └── Brushless DC Motor (BLDC)
                    └── BLDC Motor Module
```

**使用场景**：
- leleby：产品目录、搜索与匹配
- lookWhy：产品知识关联

### 6.5 技术分类（Technology Classification）

**回答的问题**：用什么技术实现？

**示例**：
```
Technology
  └── Electric Drive
        └── Brushless DC
              ├── Permanent Magnet
              ├── Sensorless Control
              └── Field-Oriented Control
```

**使用场景**：
- lookWhy：技术知识关联、专利分类
- leleby：技术能力标签

### 6.6 应用领域分类（Application Domain Classification）

**回答的问题**：用在哪里？

**示例**：
```
Application Domain
  └── Marine Equipment
        ├── Ship Ventilation System
        ├── Ship Pump System
        ├── Ship Propulsion Auxiliary
        └── Ship Control System
```

**使用场景**：
- leleby：采购场景匹配
- lookWhy：应用经验关联

### 6.7 功能能力分类（Function / Capability Classification）

**回答的问题**：能做什么？

**示例**：
```
Capability
  └── Rotary Motion
        ├── Continuous Rotation
        ├── Positioning
        └── Speed Control
  └── Fluid Driving
        ├── Pumping
        ├── Fan Driving
        └── Compressing
```

**使用场景**：
- leleby：AI采购匹配的核心维度
- lookWhy：产品能力知识关联

### 6.8 知识领域分类（Knowledge Domain Classification）

**回答的问题**：属于什么知识领域？

**依据参考**：GB/T 23703.7-2014《知识管理 第7部分：知识分类通用要求》

**使用场景**：lookWhy 知识管理视图、导航维度

### 6.9 分类框架的语义表达

所有分类维度在知识图谱中表达为**独立的语义关系**，而非单一树状分类：

```
BLDC Motor Module
  ├── hasIndustry → Manufacturing / Electrical Machinery
  ├── hasProductType → BLDC Motor
  ├── hasTechnology → Brushless DC / Sensorless Control
  ├── hasApplication → Marine Ventilation System
  ├── hasCapability → Rotary Motion / Speed Control
  └── hasKnowledgeDomain → Motor Design / Electrical Engineering
```

一个实体可同时拥有多个维度的分类标签，各维度之间相互独立、可组合查询。

### 6.10 分类框架的治理

分类框架由生态技术委员会统一维护，leleby 与 lookWhy 共同使用：

| 治理事项 | 负责方 | 说明 |
|---------|--------|------|
| 分类维度定义 | 生态技术委员会 | 新增或删除分类维度 |
| 分类节点增删改 | 生态技术委员会评审 | 企业可根据需要申请扩展 |
| 分类与标准映射 | 生态技术委员会 | 维护与GB/T 4754等标准的映射关系 |
| 版本发布 | 生态技术委员会 | 分类框架版本与本体版本同步发布 |

### 6.11 分类框架在各平台中的使用方式

| 平台 | 使用方式 | 重点维度 |
|------|---------|----------|
| **leleby** | 产品发现、采购匹配、AI搜索 | 行业、产品、应用、功能 |
| **lookWhy** | 知识导航、分类视图、检索过滤 | 知识领域、产品、技术 |
| **生态共享层** | 跨平台语义对齐、数据交换 | 全部维度 |


## 7. 语义基础设施架构

### 7.1 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AI Agent 应用层                                       │
│         采购推荐  │  供应商发现  │  合规检查  │  询价触发  │  交易判断      │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ HTTP / JSON-LD / MCP
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                      商业实例数据层 (llc:)                                  │
│              企业AI名片  │  产品实例  │  测量数据  │  采购要求              │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ 实例化/引用
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                      语义包层 (lbs:)                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │  标准语义包        │  │  产品标准语义包    │  │  PPM标准语义包    │        │
│  │  IEC.xxx.ttl     │  │  GB.xxx.ttl      │  │  PPM-RM-001.ttl │        │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘        │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ 引用/实例化
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                      本体层 (lbo:)                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │  核心工业本体      │  │  电机本体        │  │  照明本体        │        │
│  │  Product,         │  │  Motor,          │  │  Lighting,       │        │
│  │  Specification,   │  │  BLDCMotor,      │  │  Luminaire       │        │
│  │  Requirement,     │  │  PMSMMotor       │  │                  │        │
│  │  Capability,      │  └──────────────────┘  └──────────────────┘        │
│  │  Measurement...   │                                                   │
│  └──────────────────┘                                                     │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ 继承/扩展
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                      基础词汇层 (llb:)                                     │
│  Entity │ Identifier │ Version │ Document │ Event │ Statement             │
│  Agent │ Organization │ Time │ Location │ Quantity │ Unit                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 知识体系三层结构

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Application Knowledge Layer（应用知识层）          │
│  - Requirement（要求）  - Verification（验证）              │
│  - Compliance（合规）   - Design Rule（设计规则）           │
│  - Evidence（证据链）                                      │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Industrial Domain Knowledge Layer（领域知识层）    │
│  - Industry Knowledge（行业知识）                           │
│  - Standard Knowledge（标准知识）                           │
│  - Product Knowledge（产品知识）                            │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Semantic Foundation Layer（语义基础层）            │
│  - Foundation Ontology（基础本体）                          │
│  - Upper Ontology Mapping（上层本体映射）                   │
│  - Units / Time / Organization / Location                   │
└─────────────────────────────────────────────────────────────┘
```

### 7.3 三层语义资产模型与Namespace映射

| 层级 | 资产类型 | Namespace | 稳定性 | 治理方式 |
|---|---|---|---|---|
| **Foundation Vocabulary** | 元概念、标识、版本、文档等基础语义 | `llb:` | 永久冻结 | 核心团队冻结，不可变更 |
| **Ontology** | 工业类和属性的定义 | `lbo:` | 长期稳定，可扩展 | 核心团队冻结，社区扩展受限 |
| **Semantic Package** | 标准规范、产品标准的语义表达 | `lbs:` | 版本化演进 | 版本管理，可追溯变更 |
| **Instance Data** | 企业、产品、测量、交易的实例 | `llc:` | 动态更新 | 数据治理，可审计 |

### 7.4 与AI Agent的分工边界

| 职责 | leleby提供 | AI Agent实现 |
|---|---|---|
| **事实层** | 标准语义、产品规格、合规声明、测量数据 | — |
| **推理能力** | 约束满足推理、合规推理、匹配推理 | 基于推理结果的商业决策 |
| **知识表示** | OWL/RDF语义模型 | 查询和推理引擎 |
| **商业判断** | — | 供应商评分、采购决策、谈判策略 |
| **用户交互** | — | UI界面、对话体验、推荐展示 |


## 8. Core Ontology Model（核心本体模型）

### 8.1 Foundation Vocabulary（llb — 语义基础层）

`llb:` 是 leleby 的 **Foundation Namespace**，提供所有语义表达所需的基础元概念和框架。它不包含任何工业领域Ontology语义。

**核心基础类（llb）定义**：

| 类 | 定义 |
|---|---|
| `llb:Entity` | 所有实体的顶级抽象 |
| `llb:Concept` | 概念的顶级抽象（用于抽象概念的表达） |
| `llb:PhysicalEntity` | 物理实体的抽象（产品、设备、材料等） |
| `llb:Agent` | 行为主体（人、组织、系统） |
| `llb:Organization` | 组织实体（企业、机构、标准组织） |
| `llb:Identifier` | 标识符（ID、URI、编码） |
| `llb:Version` | 版本标识 |
| `llb:Document` | 文档（标准文件、报告、证书） |
| `llb:Event` | 事件（测试事件、生产事件） |
| `llb:Statement` | 声明（断言、声明、主张） |
| `llb:Time` | 时间相关概念 |
| `llb:Location` | 位置相关概念 |
| `llb:Quantity` | 量的抽象（数值、单位） |
| `llb:Unit` | 计量单位 |

**关键约束**：`llb:` 中的所有类都不包含工业领域语义。例如，`Product` 不属于 `llb:`，而是属于 `lbo:`。

### 8.2 Core Industrial Ontology（lbo — 核心工业本体）

`lbo:` 是 leleby 的 **Ontology Namespace**，所有工业领域的类和属性定义均属于此命名空间。`lbo:` 继承并扩展 `llb:` 的基础概念。

**核心工业类（lbo）定义**：

| 类 | 定义 | 继承自 |
|---|---|---|
| `lbo:Product` | 产品或产品系列 | `llb:PhysicalEntity` |
| `lbo:ProductInstance` | 产品具体实例（批次/个体） | `llb:PhysicalEntity` |
| `lbo:ProductSpecification` | 产品技术规格的事实描述 | `llb:Statement` |
| `lbo:Capability` | 产品在特定条件下实现某种功能的潜在倾向 | `llb:Concept` |
| `lbo:Requirement` | 必须满足的约束条件 | `llb:Statement` |
| `lbo:Measurement` | 测量活动及其结果 | `llb:Event` + `llb:Statement` |
| `lbo:TestMethod` | 测试方法定义 | `llb:Document` |
| `lbo:TestResult` | 测试结果 | `llb:Statement` |
| `lbo:SamplingPlan` | 抽样方案 | `llb:Concept` |
| `lbo:ComplianceStatement` | 符合性声明 | `llb:Statement` |
| `lbo:Classification` | 分类/分级方法 | `llb:Concept` |
| `lbo:StandardDocument` | 标准文件 | `llb:Document` |
| `lbo:Regulation` | 法规文件 | `llb:Document` |
| `lbo:BOMStructure` | 物料清单结构 | `llb:Concept` |
| `lbo:BOMComponent` | BOM组件 | `llb:PhysicalEntity` |

### 8.3 Classification Ontology（分类本体）

分类是工业语义中最重要的基础能力之一。分类不是固定的树形结构，而是可计算的布尔表达式条件函数模型。

**核心模型**：

```
ClassificationMethod
    │
    ├── hasClassificationDimension → Dimension
    ├── hasExpression → BooleanExpression
    └── hasEvaluationRule → EvaluationRule
```

**工业分类示例**：

| 分类 | 条件表达式 | 说明 |
|---|---|---|
| 高速电机 | RPM > 10000 | 按转速分类 |
| 户外适用 | IP >= 54 AND operatingTemp >= -20℃ | 按环境适应性分类 |
| IE4能效 | efficiency >= 93% @ rated_load | 按能效等级分类 |

### 8.4 核心语义关系体系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  关系体系                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Regulation / Standard                                                      │
│       ├── defines → NormativeConstraint                                    │
│       └── isInputTo → DesignRequirement (in Enterprise Engineering)        │
│                                                                             │
│  DesignRequirement                                                          │
│       └── resultsIn → ProductSpecification (L3 产品事实)                   │
│                                                                             │
│  Product                                                                   │
│       ├── hasSpecification → ProductSpecification                          │
│       ├── hasInstance → ProductInstance                                    │
│       └── hasCapability → Capability                                       │
│                                                                             │
│  ProductInstance                                                            │
│       └── hasMeasurement → MeasurementResult (L4 事实)                     │
│                                                                             │
│  ProcurementRequirement (L5)                                                │
│       ├── hasConstraint → DemandConstraint                                 │
│       └── matches → ProductSpecification (via Reasoning)                   │
│                                                                             │
│  ComplianceStatement (L4)                                                   │
│       ├── subject → Product / ProductInstance                              │
│       ├── against → Standard / Regulation                                  │
│       ├── basedOn → VerificationResult                                     │
│       └── applicableTo → Jurisdiction / Market                             │
│                                                                             │
│  TransactionReadiness                                                        │
│       ├── requires → TechnicalMatch (L3 ↔ L5)                             │
│       ├── requires → CompliancePass (L1 ↔ L4)                             │
│       └── requires → CommercialPolicyMatch (L5)                            │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 9. Domain Ontology Model（领域本体模型）

### 9.1 领域本体设计原则

1. **单一职责**——每个领域本体专注于一个工业领域（电机、照明、电池等）
2. **继承基础**——所有领域本体继承 `lbo:` 核心工业类，同时依赖 `llb:` 基础语义
3. **最小化扩展**——只在必要时扩展核心类，避免过度设计
4. **可组合**——多个领域本体可共存，交叉引用

**继承关系示例**：

```
llb:PhysicalEntity （基础词汇层）
    │
    └── lbo:Product （核心工业本体）
            │
            └── lbo:Motor （电机领域本体）
                    │
                    ├── lbo:BLDCMotor （产品类型）
                    └── lbo:PMSMMotor （产品类型）
```

### 9.2 Product Ontology（产品本体）

产品本体遵循**产品主体优先原则**：

> **Product Ontology首先描述产品是什么、由什么组成；技术路线、材料路线、制造路线既是分类维度，也可以是产品类型属性，两者共存以满足不同场景要求。**

**双表达建模方式**：

在产品本体中，技术分类和产品类型可以同时存在，以覆盖不同的使用场景：

| 场景 | 表达方式 | 用途 |
|---|---|---|
| AI智能选型 | `MotorTechnology = "BLDC"`（分类维度） | 按技术条件筛选 |
| 供应商目录 | `lbo:BLDCMotor`（产品类型） | 商业产品查询 |

```
lbo:ElectricMotor
    │
    ├── hasTechnologyAttribute → MotorTechnologyCategory （分类维度）
    │       ├── BLDC
    │       ├── PMSM
    │       ├── Induction
    │       └── SwitchedReluctance
    │
    └── hasProductType → MotorProductType （产品类型）
            ├── lbo:BLDCMotor
            ├── lbo:PMSMMotor
            └── lbo:InductionMotor
```

### 9.3 Measurement Ontology（测量本体）

| 类 | 定义 |
|---|---|
| `lbo:Measurement` | 测量活动 |
| `lbo:MeasuredProperty` | 被测量的属性（温度、功率、效率等） |
| `lbo:MeasurementValue` | 测量值（含数值、单位、精度） |
| `lbo:MeasurementCondition` | 测量条件（环境温度、湿度、负载等） |
| `lbo:MeasurementDevice` | 测量设备（型号、精度、校准） |

### 9.4 Test Method Ontology（测试方法本体）

| 类 | 定义 |
|---|---|
| `lbo:TestMethod` | 测试方法（步骤、设备、判定准则） |
| `lbo:TestSetup` | 测试布置（接线、安装、附件） |
| `lbo:TestProcedure` | 测试步骤序列 |
| `lbo:TestCriteria` | 判定准则（通过/不通过条件） |
| `lbo:TestResult` | 测试结果（含对标准的符合性判断） |

### 9.5 Sampling Ontology（抽样本体）

| 类 | 定义 |
|---|---|
| `lbo:SamplingPlan` | 抽样方案（批量、抽样数、接收数、拒收数） |
| `lbo:SampleSize` | 样本量 |
| `lbo:AcceptanceCriteria` | 接受准则（合格判定数） |
| `lbo:InspectionLevel` | 检验水平（一般I、II、III，特殊S-1至S-4） |


## 10. Standard Semantic Package Model（标准语义包模型）

### 10.1 标准语义包定义

**Standard Semantic Package（标准语义包）** 是 leleby 的核心创新之一。

> **标准语义包是对某一权威规则体系（IEC、GB、ISO等标准或PPM等企业/行业规范）的完整语义化表达。它不是Ontology（本体），而是Ontology的实例化应用——使用 `lbo:` 和 `llb:` 定义的类和关系，表达具体标准的内容。**

**Standard Package 与 Ontology 的本质区别**：

| 维度 | Ontology（lbo） | Standard Package（lbs） |
|---|---|---|
| 定义内容 | 世界有什么东西（类、属性、关系） | 某个规则体系如何约束世界（具体规范） |
| 示例 | `lbo:Product`, `lbo:Motor` | `lbs:IEC-60034-1-2025`, `lbs:PPM-RM-001-v1.0` |
| 稳定性 | 长期稳定，可扩展 | 版本化演进 |
| 创建方式 | 本体工程师定义 | 标准分析师从标准文本提取 |

### 10.2 标准文件元数据（Standard Document Identity）

标准语义包必须包含标准文件的完整元数据，以支持法律追溯和合规审计：

```
StandardDocument
    │
    ├── standardId: "IEC-60034-1"
    ├── title: "Rotating electrical machines - Part 1: Rating and performance"
    ├── issuingBody: "IEC"
    ├── officialFile: "https://.../IEC-60034-1-2025.pdf"
    ├── approvedBy: "IEC TC2"
    ├── approvalDate: "2025-12-15"
    ├── effectiveDate: "2026-02-01"
    ├── jurisdiction: "International" | "China" | "EU" | "US"
    ├── adoption: "GB/T 755-2025" (如适用)
    └── status: "published" | "superseded" | "withdrawn"
```

### 10.3 标准语义包结构

每个标准语义包包含以下模块：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Standard Semantic Package                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  Metadata                                                                  │
│  ├── standardId, version, title, issuingBody, issuingDate                │
│  ├── officialFile, approvalDate, effectiveDate, jurisdiction             │
│  ├── adoption, status                                                    │
│  └── previousVersion, changeHistory                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Normative Content                                                        │
│  ├── classifications → 定义的标准分类体系                                 │
│  ├── requirements → 各项要求的具体定义（引用 lbo:Requirement）            │
│  ├── testMethods → 引用的测试方法（引用 lbo:TestMethod）                  │
│  ├── evaluationRules → 判定规则                                           │
│  └── references → 引用的其他标准                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  Clause Mapping                                                           │
│  ├── requirement-001 → derivedFrom Clause 5.6                            │
│  ├── requirement-002 → derivedFrom Clause 6.3.2                          │
│  └── ...                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  Change History                                                           │
│  ├── previousVersion: "IEC-60034-1-2017"                                 │
│  ├── changes: [变更说明列表]                                              │
│  └── effectiveDate: "2026-02-01"                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.4 Specification Meta Model Ontology

**Specification Meta Model Ontology（规格元模型本体）** 是 `lbo:` 命名空间中的核心本体之一。

它**不是**存放具体规范内容的地方，而是**描述规范结构、约束表达、接口定义、能力描述与验证方法之间关系的元模型**。

| 概念 | 定义 | 归属 |
|---|---|---|
| **Specification Meta Model Ontology** | 描述"一个规范包含什么元素、这些元素之间是什么关系"的元模型 | `lbo:`（Ontology） |
| **Standard Semantic Package** | 基于元模型定义的某个具体规范的内容 | `lbs:`（Semantic Package） |

**元模型核心类（lbo:）** ：

```
SpecificationMetaModel
    │
    ├── hasComponent → SpecificationElement
    │       ├── RequirementElement
    │       ├── InterfaceElement
    │       ├── CapabilityElement
    │       └── VerificationElement
    ├── hasConstraintModel → ConstraintExpression
    └── hasRelationship → ElementRelation
```


## 11. Product Semantic Model（产品语义模型）

### 11.1 产品身份与规格

**产品身份**：

| 属性 | 说明 |
|---|---|
| `productId` | 产品唯一标识 |
| `productName` | 产品名称 |
| `productSeries` | 产品系列 |
| `manufacturer` | 制造商（引用 `llc:Enterprise`） |
| `classification` | 分类（引用 Classification） |
| `technologyType` | 技术类型（如 BLDC, PMSM） |

**产品规格**：

规格是**事实描述**，不是要求。

| 属性 | 说明 |
|---|---|
| `specName` | 规格名称 |
| `specValue` | 规格值 |
| `unit` | 单位 |
| `condition` | 测量/有效条件 |
| `tolerance` | 公差范围 |
| `confidenceLevel` | 置信水平 |
| `derivedFrom` | 来源标准条款引用 |

### 11.2 产品能力

能力是产品在特定条件下实现某种功能的潜在倾向。

```
Capability
    │
    ├── capabilityType: "RotaryMotion"
    ├── performanceMatrix: [
    │     { speed: 1000RPM, torque: 0.5Nm, efficiency: 0.85 },
    │     { speed: 3000RPM, torque: 0.8Nm, efficiency: 0.88 }
    │   ]
    ├── condition: "S1 continuous duty, ambient 25℃"
    └── classification: "IE4" (通过 Classification 条件函数判定)
```

### 11.3 BOM结构

BOM（物料清单）是产品结构的语义表达：

```
Product
    │
    ├── hasBOM → BOMStructure
    │       ├── hasComponent → Component (层级1)
    │       │       ├── quantity: 2
    │       │       ├── material: "Copper"
    │       │       └── hasComponent → SubComponent (层级2)
    │       └── hasComponent → Component (层级1)
    │               └── quantity: 1
    └── hasAssembly → AssemblyProcess
```


## 12. Requirement & Constraint Model（要求与约束模型）

### 12.1 要求分类体系

leleby 区分不同来源和性质的要求：

```
Requirement
    │
    ├── NormativeRequirement（来自法规/标准）
    │   ├── RegulatoryRequirement（法规要求）
    │   └── StandardRequirement（标准要求）
    │
    ├── EngineeringRequirement（工程设计转化）
    │   ├── DesignMarginRequirement（设计裕度）
    │   └── ManufacturingCapabilityRequirement（制造能力要求）
    │
    ├── SpecificationRequirement（产品规格事实——此为L3定义）
    │   └── ProductSpecification（产品规格事实）
    │
    └── DemandRequirement（采购要求——L5）
        ├── TechnicalConstraint（技术约束）
        ├── CommercialConstraint（商务约束）
        └── DeliveryConstraint（交付约束）
```

### 12.2 约束表达模型

要求以可计算约束的形式表达：

```
Constraint
    │
    ├── constraintType: "Range" | "Enumeration" | "Logic" | "Comparison"
    ├── expression:
    │   Range: { min: 0.5, max: 5.0, unit: "Nm" }
    │   Enumeration: { values: ["IP54", "IP65", "IP66"] }
    │   Logic: { operator: "AND", operands: [Constraint1, Constraint2] }
    │   Comparison: { operator: ">=", value: 50000, unit: "hours" }
    ├── condition: { applicableWhen: "rated_load" }
    └── derivedFrom: StandardClause 引用
```

### 12.3 法规与强制性等级

**Binding Level（约束等级）** 枚举：

| 等级 | 含义 | 示例 |
|------|------|------|
| **Mandatory** | 强制遵守，法律法规要求 | GB强制性标准 |
| **Recommended** | 推荐采用，最佳实践 | ISO推荐标准 |
| **Contractual** | 合同约定，按协议执行 | 客户指定标准 |
| **EnterpriseInternal** | 企业内部规定 | 企业标准 |

该属性是合规判定和AI辅助决策的关键输入。


## 13. Measurement & Verification Model（测量与验证模型）

### 13.1 测量本体

测量结果是**事实**，不是规格定义。

```
MeasurementResult
    │
    ├── subject → ProductInstance
    ├── measuredProperty → "Power"
    ├── value: 250.3
    ├── unit: "W"
    ├── condition: { load: "rated", ambientTemp: 25℃ }
    ├── device: { model: "PowerMeter-3000", calibration: "2026-01-15" }
    ├── uncertainty: ±2.5W (k=2)
    ├── derivedFrom: TestMethod 引用
    └── timestamp: "2026-06-01T14:30:00Z"
```

### 13.2 合规证据链

升级为**可追溯证据链（Traceable Evidence Chain）**：

```
Requirement（标准要求）
  │
  ▼
Verification Plan（验证计划）
  ├── testMethod: TestMethod
  ├── sampleSize: int
  ├── acceptanceCriteria: Criteria
  │
  ▼
Test Execution（测试执行）
  ├── testDate: date
  ├── operator: Person
  ├── equipment: TestEquipment（含校准信息）
  ├── environmentalConditions: Condition
  │
  ▼
Measurement Data（测量数据）
  ├── rawData: DataSet
  ├── observedValue: Value
  ├── uncertainty: float
  │
  ▼
Evaluation Rule（评价规则）
  ├── ruleExpression: Rule（如"Efficiency ≥ 92%"）
  ├── logic: （Pass | Fail | Inconclusive）
  │
  ▼
Compliance Result（合规结果）
  ├── result: （Pass | Fail | NotApplicable | Conditional）
  └── complianceStatus: string
  │
  ▼
Evidence Package（证据包）
  ├── evidenceId: string
  ├── testReport: Document（测试报告）
  ├── rawDataFile: File（原始数据文件）
  ├── equipmentCalibrationCert: Document（校准证书）
  ├── operatorQualification: Document（人员资质）
  ├── timestamp: datetime
  └── digitalSignature: string（数字签名，防篡改）
```

**设计原则**：合规结论不等于一个简单的"PASS"，而是一份**可审计、可追溯、可重现**的证据档案。未来AI审核和监管检查均依赖于完整的证据链。

### 13.3 符合性声明

```
ComplianceStatement
    │
    ├── subject → Product / ProductInstance
    ├── against → Standard / Regulation
    ├── applicableScope → Market / Jurisdiction
    ├── result: "compliant" | "non-compliant" | "partially-compliant"
    ├── basedOn → VerificationResult[]
    ├── evidence → TestReport[]
    ├── derivedFrom → StandardClause[]（条款级引用）
    └── issuedBy → VerifyingBody
```


## 14. Version Governance Model（版本治理模型）

### 14.1 标准生命周期治理

```
标准生命周期：
    Draft（草案）
        │
        ▼
    Proposed（提案）
        │
        ▼
    Approved（批准）
        │
        ▼
    Published（发布）  ← 正式语义包上线
        │
        ▼
    Amended（修订）  ← 小规模修正
        │
        ▼
    Superseded（替代）  ← 新版本发布
        │
        ▼
    Withdrawn（废止）  ← 不再使用
```

### 14.2 Git式标准治理模型

leleby 将标准语义包的管理类比 Git 版本控制系统：

| Git 概念 | leleby 对应 | 说明 |
|---|---|---|
| Repository | Standard Repository | 标准语义包的存储仓库 |
| Commit | Semantic Change | 对标准语义包的变更提交 |
| Tag | Official Version | 正式发布的版本标签 |
| Branch | Adoption Context | 不同采用场景的变异分支 |
| Diff | Requirement Change | 版本间要求的差异 |
| Signature | Approval | 标准发布批准的签名记录 |

**标准语义包版本标识**：

```
格式：{standardId}-v{major}.{minor}.{patch}

示例：
  IEC-60034-1-v1.0.0  → 首次发布
  IEC-60034-1-v1.1.0  → 新增要求（minor变更）
  IEC-60034-1-v1.0.1  → 勘误修正（patch变更）
  IEC-60034-1-v2.0.0  → 重大重构（major变更）
```

### 14.3 标准适用性状态（Applicability）

标准虽然被替代，但仍可适用于特定产品生命周期内的场景：

```
StandardApplicability
    │
    ├── standard: "IEC-60034-1-2017"
    ├── appliesTo: [
    │     { productModel: "Product-A", lifecyclePhase: "production" },
    │     { market: "China", status: "still_valid" }
    │   ]
    ├── validDuring: { start: "2017-06-01", end: null }
    └── status: "applicable" | "not_applicable" | "conditional"
```

**示例**：即使 IEC 60034-1:2025 已发布，2017 版仍适用于特定存量产品的合规声明。


## 15. Compliance Reasoning Model（合规推理模型）

### 15.1 条款级引用与推理链可追溯性

每个符合性判断必须支持完整的推理链追溯，且每个要求必须关联到原始标准的具体条款：

```
Requirement-001
    │
    ├── derivedFrom: IEC-60034-1-2025-Clause-5.6
    └── text: "Rated voltage shall be specified by the manufacturer"

────────────────────────────────────────────────────────────

ComplianceStatement#2026-001
    │
    ├── conclusion: compliant
    ├── requirementRef: [Requirement-001, Requirement-002]
    ├── clauseRefs: [
    │     "IEC-60034-1-2025-Clause-5.6",
    │     "IEC-60034-1-2025-Clause-7.3"
    │   ]
    ├── reasoningTrace: [
    │     { step: 1, source: "IEC-60034-1-2025-Clause-5.6", action: "提取要求" },
    │     { step: 2, source: "llc:product-001#Specification-Voltage", action: "匹配规格" },
    │     { step: 3, source: "llc:product-001#Measurement-Voltage", action: "验证事实" },
    │     { step: 4, action: "约束满足判断", result: "通过" }
    │   ]
    └── evidence: [TestReport-2026-001, CalibrationCertificate-2026-001]
```

### 15.2 多标准并存处理

产品可同时符合多个标准，每个标准对应独立的 ComplianceStatement：

```
Product: llc:product-001
    │
    ├── hasCompliance → ComplianceStatement (against: IEC 60598)
    │       ├── result: compliant
    │       ├── applicableMarket: "EU"
    │       ├── derivedFrom: [IEC-60598-Clause-5.3, IEC-60598-Clause-7.1]
    │       └── evidence: [TestReport-IEC-2026-001]
    │
    ├── hasCompliance → ComplianceStatement (against: GB 7000)
    │       ├── result: compliant
    │       ├── applicableMarket: "China"
    │       ├── derivedFrom: [GB-7000-Clause-5.2]
    │       └── evidence: [TestReport-GB-2026-001]
    │
    └── hasCompliance → ComplianceStatement (against: PPM-MOT-001)
            ├── result: compliant
            ├── applicableScope: "PPM Certified"
            ├── derivedFrom: [PPM-MOT-001-Clause-4.1]
            └── evidence: [TestReport-PPM-2026-001]
```


## 16. Commercial Semantic Layer（商业语义层）

### 16.1 Procurement Requirement（采购要求）

采购要求是L5层核心概念，包含技术、商务、交付三个维度的约束：

```
ProcurementRequirement
    │
    ├── requirementId: "PROC-2026-001"
    ├── technicalConstraints: [
    │     { property: "Power", min: 200, max: 300, unit: "W" },
    │     { property: "IP", min: 54 },
    │     { property: "OperatingTemp", min: -20, max: 40, unit: "℃" }
    │   ]
    ├── commercialConstraints: [
    │     { property: "UnitPrice", max: 50, unit: "USD" },
    │     { property: "PaymentTerms", values: ["T/T", "L/C"] }
    │   ]
    ├── deliveryConstraints: [
    │     { property: "LeadTime", max: 30, unit: "days" },
    │     { property: "Quantity", value: 5000 }
    │   ]
    └── targetMarket: "EU"
```

### 16.2 Transaction Readiness（交易就绪）

交易就绪状态是技术匹配、合规满足、商务规则满足的联合判断：

```
TransactionReadiness
    │
    ├── procurementRequirement → { id: "PROC-2026-001" }
    ├── technicalMatch: {
    │     status: "fully_matched",
    │     matchedProducts: ["llc:product-001", "llc:product-002"],
    │     evidence: [匹配推理链]
    │   }
    ├── compliancePass: {
    │     status: "passed",
    │     applicableStandards: ["IEC-60034-1-2025", "PPM-MOT-001"],
    │     evidence: [合规推理链]
    │   }
    ├── commercialPolicyMatch: {
    │     status: "satisfied",
    │     paymentTerms: "T/T accepted",
    │     deliveryTerms: "FOB acceptable"
    │   }
    └── readiness: "ready" | "partial" | "not_ready"
```

### 16.3 Negative Constraint Model（负面约束模型）

商业世界中，负面约束（Negative Constraints）与正面要求同等重要。

```
NegativeConstraint
    │
    ├── PaymentException（支付例外）
    │   ├── unsupportedPaymentMethods: ["Cash", "Cheque"]
    │   └── unsupportedCurrencies: ["USD", "EUR"]
    │
    ├── DeliveryException（交付例外）
    │   ├── restrictedRegions: ["Region A", "Region B"]
    │   ├── exportControl: ["Dual-use items", "Military goods"]
    │   └── legalRestrictions: ["EU Export Regulation"]
    │
    ├── ServiceException（服务例外）
    │   ├── unsupportedRegions: ["Country X"]
    │   └── warrantyExclusions: ["Consumables", "Damage from misuse"]
    │
    └── ComplianceException（合规例外）
        ├── standardsNotMet: ["IEC-xxxx"]
        └── marketsNotCompliant: ["Market Y"]
```


## 17. PPM as Industrial Validation Platform（PPM作为工业验证平台）

### 17.1 PPM的战略定位

PPM（Perfect Product Manufacture）是 leleby 工业语义基础设施的**下属验证平台与行业落地载体**。

PPM不是独立品牌或独立公司，而是 leleby 工业语义基础设施在制造领域的**首个Semantic Standard Package实践和验证平台**——通过语义标准定义高价值工业功能部件、建立验证体系和制造能力认证网络，验证 leleby 多层约束语义模型和标准语义包框架在真实工业场景中的完整闭环。

**PPM在leleby战略目标体系中的位置**：

| 层次 | PPM的贡献 |
|---|---|
| **L0: 基础设施层** | 验证 Specification Meta Model Ontology 在真实工业标准制定中的有效性 |
| **L1: 供给侧语义资产** | 建立 PPM Certified Manufacturer 的 Enterprise Semantic Identity + Product Semantic Model 行业标准 |
| **L2: 需求侧语义资产** | 提供工业采购要求的标准语义参考模型 |
| **L3: 智能商业应用** | 验证从标准语义→产品语义→制造商匹配→交易就绪的完整AI商业闭环 |

### 17.2 PPM标准语义包示例

```
Package: PPM-RM-001-v1.0.ttl

Metadata:
  standardId: PPM-RM-001
  version: 1.0
  title: Rotary Motion Module - General Industrial Power Class
  issuingBody: PPM
  issuingDate: 2026-07-30
  effectiveDate: 2026-08-01

Capability Class: RM42-General
  ├── definition: 通用工业动力能力族，覆盖50-300W功率范围
  ├── performanceConstraints: [
  │     { property: "Power", min: 50, max: 300, unit: "W" },
  │     { property: "Speed", min: 1000, max: 15000, unit: "RPM" },
  │     { property: "Efficiency", min: 85, unit: "%", condition: "rated_load" }
  │   ]
  ├── interfaceRequirements: [
  │     { type: "Mechanical", standard: "RM-Flange-42" },
  │     { type: "Electrical", standard: "RM-Elec-24V-48V" },
  │     { type: "Control", standard: "RM-Ctrl-FOC" }
  │   ]
  ├── manufacturingWindow: {
  │     statorOD: 42,
  │     stackLength: { min: 15, max: 40 },
  │     wireDiameter: { min: 0.3, max: 0.8 }
  │   }
  ├── testMethods: [
  │     { ref: "PPM-TEST-RM-001", name: "Efficiency Test" },
  │     { ref: "PPM-TEST-RM-002", name: "Noise Test" }
  │   ]
  └── certificationRequirements: [
  │     { level: "Certified", criteria: "pass_initial_audit" },
  │     { level: "Gold", criteria: "合格率≥99.8%持续24个月" }
  │   ]

References:
  conformsTo: [GB/T 755-2025, GB/T 4772.1-2025, GB/T 43726-2024]

ClauseMapping:
  requirement-001: derivedFrom PPM-RM-001-Clause-4.1
  requirement-002: derivedFrom PPM-RM-001-Clause-5.2
```


## 18. 与 lookWhy 的生态协同关系

### 18.1 生态全景

leleby 与 lookWhy 是两个**独立平行**的产品线，而非上下级子系统：

```
                    Industrial Semantic Ecosystem

                    工业语义基础设施层
         ┌─────────────────────────────────────┐
         │                                     │
    ┌────┴────┐                         ┌──────┴─────┐
    │ lookWhy  │                         │  leleby    │
    │工业知识资产 │                         │ 工业语义   │
    │生产平台   │                         │ 交换与应用 │
    └────┬────┘                         └──────┬─────┘
         │                                     │
    企业内部闭环                         企业外部价值释放
    回答"Why"                           回答"What"
    为什么这样设计                       有什么产品能力
```

### 18.2 数据流向

企业内部研发制造过程 → lookWhy（沉淀为私有知识资产）→ 抽象与脱敏（仅提取产品规格、符合性标准、认证信息）→ 授权审批 → 发布至 leleby。

### 18.3 共享基础设施

两个平台共享**公共工业语义层**（如基础物理单位、标准本体、要求模型、测量模型），但各自维护独立的实例图谱。该公共语义层由生态技术委员会统一治理，独立于任一平台存在。

### 18.4 核心约束

leleby **不接收** lookWhy 中的工艺参数、设计原因、供应商信息、失效模式等核心机密。所有从 lookWhy 进入 leleby 的数据须经过授权审批与脱敏校验。


## 19. 安全与治理

### 19.1 数据安全

- 企业知识资产隔离（多租户）
- 敏感数据加密存储
- 传输层TLS加密
- 数字签名防篡改（证据链完整性）

### 19.2 权限模型

基于RBAC + 知识对象级ACL：

- 标准查看/标注/审核/发布权限分离
- 企业知识库私有与共享控制
- 操作审计日志记录

### 19.3 知识质量治理

- AI抽取结果需人工确认方可发布
- 定期知识审核与过期清理
- 冲突检测与解决机制
- 质量度量指标（完整性、准确性、时效性）


## 20. 技术架构规划

### 20.1 第一阶段技术栈

| 层级 | 技术选型 | 用途 |
|------|---------|------|
| **后端** | Python + FastAPI | 业务逻辑与API服务 |
| **图数据库** | Neo4j（通过抽象层） | 存储本体、标准、产品、合规等关系数据 |
| **对象存储** | MinIO / S3兼容 | 保存PDF、图片、原始测试数据、证据文件 |
| **关系数据库** | PostgreSQL | 用户、权限、审核记录、工作流状态 |
| **前端** | React + D3.js / Cytoscape | 知识图谱可视化、标注工作台、合规矩阵展示 |
| **推理引擎** | 基于Python规则引擎（逐步演进） | 执行符合性判断和约束检查 |

### 20.2 图存储抽象层

**原则**：应用层不得直接依赖Neo4j的专有查询语法。

```
Application（应用层）
        │
        ▼
Semantic Service Layer（语义服务层）
  - 提供标准化的图查询API
  - 屏蔽底层图数据库差异
        │
        ▼
Graph Storage Adapter（图存储适配器）
  - Neo4jAdapter（第一阶段）
  - GraphDBAdapter（未来）
  - StardogAdapter（未来）
        │
        ▼
Graph Database（具体实现）
```

所有图查询使用内部抽象语法树（AST），由适配器转换为目标数据库的查询语言（Cypher / SPARQL / Gremlin）。

### 20.3 数据存储策略

- **图数据库**：所有语义关系、知识图谱
- **对象存储**：非结构化文件（原始标准PDF、测试报告、证据文件）
- **关系数据库**：用户、权限、工作流、审计日志


## 21. 数据模型原则

### 21.1 Ontology First

**开发顺序**：
```
leleby Ontology → Semantic Model → Database Mapping → Application
```

**严禁**：根据Neo4j Schema反推业务Ontology。

### 21.2 数据库解耦

已通过第20.2节的图存储抽象层实现。


## 22. 第一阶段（MVP）：Standard Application Platform

### 22.1 MVP目标

验证完整闭环：

> **标准语义建模 → 产品要求生成 → 检测验证 → 合规判断 → 证据归档**

### 22.2 MVP功能范围

| 优先级 | 功能模块 | 说明 |
|--------|---------|------|
| ★★★★★ | **功能1：标准语义建模工作台** | **核心前置模块**。提供PDF/Word/HTML查看、条款定位、实体标注、Requirement抽取、Constraint定义、Test Method关联、Binding Level标注、人工审核与版本管理 |
| ★★★★★ | **功能2：标准语义知识库** | 存储和管理标准语义图谱，支持标准查询、版本追溯、引用关系展示、Scope自动匹配 |
| ★★★★★ | **功能3：符合性验证管理** | 支持验证计划制定、测试数据录入、评价规则执行、合规判定、证据包生成与归档 |
| ★★★★☆ | **功能4：产品标准生成** | 根据产品结构（如BLDC电机），自动加载相关标准要求，生成企业产品标准草案 |
| ★★★★☆ | **功能5：研发任务书生成** | 基于企业标准、引用标准和产品模型，生成产品需求规格书 |
| ★★★☆☆ | **功能6：设计符合性检查** | 输入设计参数，自动与标准要求比对 |
| ★★★☆☆ | **功能7：语义文档生成** | 从知识图谱生成Markdown/PDF/Word/JSON |

### 22.3 标准语义建模工作台详细功能

- **文档解析**：支持PDF/Word/HTML结构抽取（目录、条款、表格、图片）
- **智能辅助标注**：AI建议实体类型、关系、要求条款
- **人工确认界面**：标注审核、冲突解决、质量校验
- **约束条件定义**：以结构化方式录入数值范围、逻辑表达式
- **测试方法关联**：将标准条款与具体测试方法绑定
- **版本工作流**：Draft → Review → Published 状态管理
- **变更追踪**：记录每次修改的人员、时间和原因


## 23. 长期演化路线

| 阶段 | 目标 | 核心内容 |
|------|------|----------|
| **Phase 1（当前）** | 标准语义平台 | Standard → Requirement → Verification → Compliance → Evidence |
| **Phase 2** | 产品工程平台 | 增加产品知识、BOM、设计模型、参数化模板 |
| **Phase 3** | 制造知识平台 | 增加工艺路线、设备、质量控制计划 |
| **Phase 4** | AI工业工程助手 | 工程师 + AI助手 + 知识图谱 → 智能设计决策与合规自检 |

**后续工作建议**：

| 顺序 | 产出物 | 说明 |
|------|--------|------|
| 1 | **leleby 总体架构设计 v1.0** | 软件模块划分、服务边界、数据流、部署架构 |
| 2 | **leleby Ontology Specification v1.0** | 集成Standard、Requirement、Verification、Compliance、Evidence、Semantic Package的完整应用层本体 |
| 3 | **MVP 图存储 Schema Design（通过抽象层）** | 节点、关系、属性、查询模式 |
| 4 | **标准语义建模工作台原型设计** | UI/UX设计、标注交互流程 |
| 5 | **BLDC标准应用验证案例包开发** | 第一个完整闭环Demo与语义包交付物 |


## 24. 战略护城河

| 护城河 | 说明 |
|---|---|
| **四层命名空间架构** | llb/lbo/lbs/llc 职责分离，llb不含Ontology语义，lbo是唯一的工业本体命名空间 |
| **llb/lbo分离策略** | llb作为基础词汇永久冻结，lbo承载所有工业本体，两者分离确保语义基础不受工业演进影响 |
| **Ontology vs Package分离** | 本体（lbo）与标准语义包（lbs）分离，使标准和规范可独立演进而不破坏本体 |
| **Classification Ontology** | 条件函数分类模型支持无限扩展，无需修改本体即可新增分类维度 |
| **标准版本治理模型** | Git式标准管理使标准语义包可追溯、可差异比较、可审计 |
| **标准文件元数据与适用性** | 标准文件的法律元数据和适用性状态支持合规审计和存量产品管理 |
| **条款级引用** | 每个要求可追溯到标准的具体条款，支持AI合规推理和证据链追溯 |
| **标准语义包网络效应** | 积累的语义化标准包越多，新标准包的定义成本越低 |
| **PPM验证闭环** | 标准定义→制造验证→数据反馈的标准演进闭环 |


## 25. Ecosystem Value Model（生态价值链）

leleby 与 lookWhy 共同构成完整的工业知识价值链：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           生态价值链                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  企业研发制造过程                                                           │
│        │                                                                    │
│        ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  lookWhy                                                           │   │
│  │  企业知识资产化：设计经验、工艺参数、标准规范 → 结构化知识原子        │   │
│  │  价值：防止知识流失、提升复用效率、支撑合规追溯                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                    │
│        ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Semantic Asset Exchange Layer                                     │   │
│  │  知识资产抽象与脱敏：权限判断、脱敏校验、格式转换、资产打包          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                    │
│        ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  leleby                                                            │   │
│  │  工业语义资产流通：产品语义卡、能力标签、合规认证 → AI商业应用       │   │
│  │  价值：产品发现效率、采购匹配精度、供应链透明度                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                    │
│        ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  AI商业生态                                                         │   │
│  │  AI采购、供应链优化、智能合规检查、自动化交易                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 25.1 各环节价值说明

| 环节 | 平台 | 价值创造 |
|------|------|----------|
| **知识生产** | lookWhy | 企业核心智力资产系统化、结构化、可追溯 |
| **知识治理** | lookWhy | 权限管控、质量审核、谱系管理、标准生命周期 |
| **语义抽象** | 交换层 | 脱敏保护、授权输出、格式标准化 |
| **语义流通** | leleby | 产品可发现、能力可比较、合规可验证 |
| **商业应用** | AI生态 | 采购效率提升、供应链优化、交易自动化 |

### 25.2 网络效应

随着生态中企业和产品语义资产的持续积累，形成正向飞轮：

```
更多企业接入
        │
        ▼
更多产品语义资产
        │
        ▼
更精准的AI匹配
        │
        ▼
更高的采购效率
        │
        ▼
更多采购需求
        │
        ▼
更多企业接入（循环）
```


## 26. 术语表

| 术语 | 英文 | 定义 |
|---|---|---|
| 工业语义平台 | Industrial Semantic Platform | leleby 长期基础平台，提供本体、知识图谱、推理引擎等基础能力 |
| 标准应用平台 | Standard Application Platform | leleby 第一阶段应用平台，聚焦标准语义建模与合规验证 |
| 命名空间 | Namespace | leleby 的语义命名空间体系（llb/lbo/lbs/llc） |
| 基础词汇 | Foundation Vocabulary | `llb:` 命名空间内容，提供元概念和基础语义框架 |
| 本体 | Ontology | `lbo:` 命名空间内容，定义工业世界的类和关系 |
| 标准语义包 | Standard Semantic Package | `lbs:` 命名空间内容，对某一权威规则体系的完整语义化表达 |
| 规格元模型本体 | Specification Meta Model Ontology | 描述规范结构、约束表达、验证方法之间关系的元模型 |
| 语义资产交换层 | Semantic Asset Exchange Layer | leleby 与外部系统进行受控数据交换的标准化接口层 |
| 法规 | Regulation | 立法/监管机构发布的强制法律约束 |
| 标准 | Standard | 标准组织发布的技术规范 |
| 产品规格 | Specification | 产品技术指标的事实描述 |
| 测量结果 | Measurement Result | 测试获得的事实数据 |
| 合规声明 | Compliance Statement | 针对特定标准/市场的合规判断 |
| 采购要求 | Procurement Requirement | 客户采购期望 |
| 交易就绪 | Transaction Readiness | 技术匹配+合规满足+商务规则满足的联合状态 |
| 分类方法 | Classification Method | 基于条件函数的可计算分类模型 |
| Git式治理 | Git-style Governance | 将标准语义包类比Git仓库进行版本管理 |
| 标准适用性 | Applicability | 标准在特定产品/市场/生命周期阶段的适用状态 |
| 条款级引用 | Clause-level Reference | 要求到标准具体条款的可追溯引用 |


## 27. 版本历史

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| v0.1 | 2026-07 | 初始战略规划草稿 |
| v1.0 | 2026-08 | 整合为标准应用平台总体规划 |
| v2.0 | 2026-08 | 评审修订版：增加平台层级定位；知识体系三层架构；标准模型；合规证据链；标准语义建模工作台；图存储抽象层；Semantic Package战略；知识生命周期；安全与治理章节 |
| v3.0 | 2026-07 | 战略重构：定位为 B2B 供需智能匹配基础设施 |
| v3.1 | 2026-07 | 工业语义基础设施架构版：新增 Namespace Architecture；明确 Ontology 与 Semantic Package 分离；新增 Classification Ontology；引入 Git式标准治理模型 |
| v3.1.1 | 2026-07 | 命名空间与Ontology边界澄清版：重新定义llb为Foundation Vocabulary；将所有Ontology内容迁移至lbo；明确llb→lbo单向继承；增加BLDC双表达 |
| v4.0 | 2026-08 | 战略整合基线版：以 v2.0 的平台分层架构为骨架，以 v3.1.1 的战略定位、生态愿景和 Ontology 体系为内容填充，合并两个前序版本 |
| **v4.1** | **2026-08** | **生态增强版**：新增1.5节"leleby"品牌与平台体系关系澄清；新增2.4节Semantic Asset Exchange Layer；新增第6章Industrial Classification Framework（原第6章及之后章节编号顺延）；新增第25章Ecosystem Value Model；统一术语体系 |


*本文件为 leleby 平台体系的顶层战略与架构约束文件，后续架构设计、本体开发和项目迭代均须以此为依据。*