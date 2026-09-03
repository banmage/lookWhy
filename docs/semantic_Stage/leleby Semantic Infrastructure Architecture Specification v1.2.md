# leleby Semantic Infrastructure Architecture Specification v1.2

**文档版本：** v1.2 — Architecture Clarification Release（架构澄清版）

**文档类型：** 架构规范（Architecture Specification）

**文档状态：** ✅ **正式冻结（Frozen）** — 核心架构原则已冻结，后续仅允许模块内部扩展和领域层新增

**目标受众：** 本体架构师、领域本体设计师、企业数据架构师、AI Agent 开发者、标准工程师

**发布日期：** 2026-08-04


## 目录

1. 引言
   1.1 背景
   1.2 本规范的核心定位
   1.3 核心回答的问题
   1.4 核心架构声明
   1.5 v1.2 与 v1.1 的核心差异

2. 设计原则
   2.1 实体优先于分类
   2.2 要求与能力分离
   2.3 结构（Structure）与角色（Role）分离
   2.4 产品递归组合原则
   2.5 验证与推理分离
   2.6 标准中立
   2.7 工业语义闭环原则
   2.8 评价上下文原则（EvaluationContext）
   2.9 分类即断言原则
   2.10 四层资产分离原则
   2.11 Demand 与 Requirement 分离原则（v1.2 新增）

3. Namespace Architecture（命名空间架构）
   3.1 命名空间设计原则
   3.2 四层命名空间定义
   3.3 命名空间间关系
   3.4 命名空间使用约束

4. 语义资产架构
   4.1 架构总览
   4.2 四层语义资产模型与 Namespace 映射
   4.3 各层稳定性承诺

5. Foundation Vocabulary（llb — 语义基础层）
   5.1 定位
   5.2 核心基础类定义
   5.3 关键约束

6. Upper Industrial Ontology（lbo — 上层工业本体）
   6.1 定位
   6.2 核心工业类定义
   6.3 六元要求语义框架（v1.2 更新）
   6.4 EvaluationContext（跨模块共享核心概念）

7. Core Ontology（lbo — 核心工业本体）
   7.1 定位
   7.2 核心类定义
   7.3 Core Ontology 与其他层的关系

8. Domain Ontology Architecture（领域本体架构）
   8.1 领域本体设计原则
   8.2 领域本体示例
   8.3 分类即断言原则的贯彻

9. Semantic Package Architecture（语义包架构）
   9.1 定义
   9.2 标准语义包与 Ontology 的本质区别
   9.3 语义包清单模型（Package Manifest）
   9.4 标准语义包结构

10. Standard Ontology（标准本体）
    10.1 定位
    10.2 Standard Document vs Standard Edition
    10.3 核心概念
    10.4 标准属性
    10.5 标准条款与要求的关系

11. Demand Ontology 边界说明（v1.2 新增）
    11.1 Demand 与 Requirement 的分离
    11.2 Demand Ontology 预留接口

12. Constraint & Reasoning Layer（约束与推理层）
    12.1 四层执行架构
    12.2 各层职责与输入输出
    12.3 Constraint Ontology 定位
    12.4 各类约束定义

13. Compliance Model（符合性模型）
    13.1 Compliance 三级模型
    13.2 ComplianceDeclaration 法律属性

14. PPM as Industrial Validation Platform（PPM 作为工业验证平台）
    14.1 PPM 的战略定位
    14.2 PPM 与 leleby 语义架构的关系
    14.3 PPM 在 leleby 战略目标体系中的位置

15. 核心语义闭环链路（v1.2 更新）

16. 冻结声明（v1.2 更新）
    16.1 冻结范围
    16.2 冻结分级
    16.3 冻结后允许
    16.4 冻结后禁止

17. 下一步工作计划（v1.2 更新）

18. 版本变更记录


## 1. 引言

### 1.1 背景

leleby Semantic Infrastructure Architecture Specification 经过 v0.1 至 v0.9 的演进，以及 v1.0-rc1 和 v1.1 的发布，已形成了完整的架构体系。v1.2 在 v1.1 基础上完成了架构澄清，核心变更包括：

1. **将 Requirement 六元模型中的 `Characteristic` 升级为 `SemanticTarget`**，与 Requirement Ontology v1.1 保持一致
2. **在架构中明确 Demand 与 Requirement 的边界**，增加 Demand Ontology 的预留接口
3. **更新核心语义闭环链路图**，增加 Demand 作为商业入口
4. **调整冻结声明**：冻结“六元语义框架”而非具体字段，冻结“架构原则”而非具体类模型
5. **同步更新模块版本状态**，反映各模块的最新版本

### 1.2 本规范的核心定位

> **本规范是 leleby 语义基础设施体系的“架构总纲”。**

它描述整个 leleby 语义体系的：

- **本质与定位**（是什么、不是什么）
- **设计原则**（为什么这样设计）
- **命名空间架构**（llb / lbo / lbs / llc 的职责与关系）
- **语义资产架构**（四层资产模型）
- **模块关系**（模块之间如何协作）
- **冻结声明**（什么可以变、什么不能变）

**各子 Ontology 的详细类/属性定义，在独立的模块规范中定义。**

### 1.3 核心回答的问题

leleby 语义基础设施不仅回答：

> "企业有什么？"

还回答：

> "企业提供的产品是否满足某个要求？"
>
> "在什么条件下满足？"
>
> "根据什么标准验证？"
>
> "如何判断？"
>
> "判断之后采取什么行动？"

**v1.2 新增：** leleby 还回答：

> "客户需要什么（Demand）？"
>
> "商务需求如何转化为技术要求（Requirement）？"

### 1.4 核心架构声明

> **leleby 不是通过建立一个统一知识图谱来理解工业世界，而是通过稳定的 Foundation Vocabulary、可扩展的 Ontology、版本化的 Semantic Package 和可推理的 Commercial Instance Data，共同构建工业世界的数字语义基础设施。**

leleby 的语义基础设施由四个层次构成：

| 层次 | Namespace | 内容 | 稳定性 |
|---|---|---|---|
| **Foundation Vocabulary（基础词汇层）** | `llb:` | 元概念、标识、版本、文档等基础语义（**不含任何 Ontology 类**） | 永久冻结 |
| **Ontology（本体层）** | `lbo:` | 工业世界的核心类和关系定义（Upper + Core + Domain + Application） | 分级冻结 |
| **Semantic Package（语义包层）** | `lbs:` | 规范/标准/行业模型的语义化实例（版本化知识封装） | 版本化演进 |
| **Commercial Instance（商业实例层）** | `llc:` | 企业、产品、测量、交易的具体实例 | 动态更新 |

以上四层共同构成 leleby 的**四层语义基础设施模型**。

### 1.5 v1.2 与 v1.1 的核心差异

| 问题 | v1.1 状态 | v1.2 修正 |
|---|---|---|
| Requirement 六元模型第三元 | `Characteristic` | **升级为 `SemanticTarget`**（特性/功能/接口/关系/结构/过程/服务） |
| Demand 与 Requirement 边界 | 未明确 | **新增 Demand Ontology 边界说明章节** |
| 核心闭环链路 | 始于 Requirement | **增加 Demand 作为商业入口** |
| 冻结范围 | 冻结具体类模型 | **调整为冻结“架构原则”和“语义框架”** |
| 模块版本状态 | 部分模块版本过时 | **同步更新至最新版本** |


## 2. 设计原则

### 2.1 实体优先于分类

**原则：** 实体的身份和关系先于其所属的分类体系。

- 一个 Product 首先是 `lbo:Product`（具有身份、结构、能力），然后才拥有各种分类标签
- 分类是断言（Assertion），不是实体的固有属性

### 2.2 要求与能力分离

**原则：** 要求（Requirement）定义"需要什么"，能力（Capability）定义"能提供什么"，两者通过符合性（Compliance）连接。

### 2.3 结构（Structure）与角色（Role）分离

**原则：** 一个实体在不同上下文中扮演不同角色，角色不改变实体的本质结构。

### 2.4 产品递归组合原则

> **产品之间可以通过结构关系形成递归组合，系统、子系统、组件、零件、材料均不是 Product 的固有分类，而是在特定上下文中的结构角色。**

### 2.5 验证与推理分离

**原则：** SHACL 验证数据结构；OWL 推理概念关系；规则引擎执行符合性判断。

| 层次 | 技术 | 职责 |
|---|---|---|
| 结构推理 | OWL 2 | 分类、传递、关系 |
| 数据验证 | SHACL | 完整性、格式、基数 |
| 规则推理 | Rule Engine | 数值、条件、逻辑 |
| 决策推理 | Decision Engine | 多因素综合判断、行动映射 |

### 2.6 标准中立

**原则：** leleby 不绑定任何单一标准体系。外部标准通过语义映射（Mapping）连接，不导入外部 namespace。

### 2.7 工业语义闭环原则

> **leleby 的核心运行逻辑是 Demand → Requirement → Specification → Verification → Compliance → Decision → Action 的完整推理闭环（v1.2 更新）。**

### 2.8 评价上下文原则（EvaluationContext）

> **同一属性在不同条件下可能有不同的要求、规格和验证结果。EvaluationContext 是跨模块共享的核心概念，用于表达环境、工况、检验阶段、市场区域、生命周期阶段等评价条件。**

### 2.9 分类即断言原则

> **分类（Classification）不是实体的固有属性，而是可计算的断言（Assertion）。** 同一实体可根据不同维度（技术、结构、应用、功率等）被赋予多个分类，分类通过条件函数（BooleanExpression）计算得出。

### 2.10 四层资产分离原则

> **Foundation Vocabulary、Ontology、Semantic Package、Commercial Instance 四个层次必须保持清晰的职责边界，不允许跨层混合。** 每一层只依赖其下层，不反向依赖。

### 2.11 Demand 与 Requirement 分离原则（v1.2 新增）

> **Demand（商务需求）与 Requirement（技术要求）是两个不同层级的概念，必须分离。** Demand 表达客户/市场的商业期望（交货期、数量、价格、支付方式），Requirement 表达技术性的约束性期望（性能、安全、接口、可靠性）。Demand 可通过转换规则派生出 Requirement，但二者语义不同，属于不同的 Ontology 模块。


## 3. Namespace Architecture（命名空间架构）

### 3.1 命名空间设计原则

leleby 的命名空间架构遵循以下原则：

1. **职责分离**——每个命名空间承担唯一的语义职责，互不重叠
2. **llb 不包含任何 Ontology 语义**——`llb:` 仅提供纯元概念（Entity、Identifier、Version、Document 等），**不包含 PhysicalEntity、Object、Process 等 BFO 式类**
3. **所有 Ontology 归属 lbo**——`lbo:` 是唯一的 Ontology 命名空间，包含所有工业类和属性定义
4. **lbs 是实例化应用**——`lbs:` 是基于 Ontology 的语义包，是 Ontology 的实例化应用
5. **商业与本体分离**——`llc:` 商业实例数据与语义定义分离
6. **继承方向单一**——`lbo` 可继承 `llb`，`llb` 不能依赖 `lbo`；`lbs` 可引用 `lbo` 和 `llb`

### 3.2 四层命名空间定义

| 命名空间 | 前缀 | 用途 | 示例 |
|---|---|---|---|
| **Foundation Namespace** | `llb` | leleby 基础词汇定义（纯元概念：Entity、Identifier、Version、Document、Statement、Concept、Agent、Event） | `llb:Entity`, `llb:Identifier`, `llb:Version`, `llb:Document`, `llb:Statement`, `llb:Concept`, `llb:Agent` |
| **Ontology Namespace** | `lbo` | leleby 核心工业本体和领域本体（**所有**工业类、属性、关系的定义） | `lbo:Product`, `lbo:Specification`, `lbo:Requirement`, `lbo:Capability`, `lbo:Motor`, `lbo:Lighting`, `lbo:Measurement`, `lbo:TestMethod` |
| **Specification Namespace** | `lbs` | 标准语义包（具体标准、规范的语义表达，是 Ontology 的实例化应用） | `lbs:IEC-60034-1-2025`, `lbs:PPM-RM-001-v1.0`, `lbs:GB-18613-2020` |
| **Commercial Namespace** | `llc` | 商业实例数据（企业、产品、交易、测量数据） | `llc:yunda-lighting`, `llc:product-001`, `llc:measurement-001` |

### 3.3 命名空间间关系

```
llb:（Foundation Vocabulary - 纯元概念，不含 Ontology）
    │
    │  提供元概念（Entity, Identifier, Version, Document, Statement, Concept, Agent）
    │
    ▼
lbo:（Ontology - 所有工业本体定义）
    │
    │  继承 llb 元概念，定义工业领域类（Product, Specification, Motor, etc.）
    │
    ├── 继承: lbo:Product rdfs:subClassOf llb:Entity（非 PhysicalEntity）
    │
    │  实例化为标准语义包
    │
    ▼
lbs:（Semantic Package - 标准/规范的语义实例）
    │
    │  引用 lbo 定义的类和属性，表达具体规范内容
    │
    │  实例化为商业数据
    │
    ▼
llc:（Commercial Data - 企业/产品/交易实例）
    │
    │  引用 lbs 标准包和 lbo 本体，表达具体商业事实
    │
    ▼
    （AI Agent 查询与推理）
```

### 3.4 命名空间使用约束

| 约束 | 说明 |
|---|---|
| **llb 不定义 Ontology 类** | `llb:` 不包含 `PhysicalEntity`、`Object`、`Process` 等类；不包含 `Product`、`Motor`、`Requirement` 等工业概念 |
| **继承方向不可逆** | `lbo` 可继承 `llb`，但 `llb` 不可继承 `lbo` |
| **lbs 不定义新类** | `lbs:` 不定义新的 OWL 类；所有类来自 `lbo:` 或 `llb:` |
| **llc 不定义语义** | `llc:` 不定义任何类和属性；仅包含实例数据 |


## 4. 语义资产架构

### 4.1 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AI Agent 应用层                                       │
│         采购推荐  │  供应商发现  │  合规检查  │  询价触发  │  交易判断      │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ HTTP / JSON-LD / MCP
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                      商业实例层 (llc:)                                     │
│              企业AI名片  │  产品实例  │  测量数据  │  采购需求              │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ 实例化/引用
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                      语义包层 (lbs:)                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │  标准语义包        │  │  产品标准语义包    │  │  PPM标准语义包    │        │
│  │  IEC.xxx.ttl     │  │  GB.xxx.ttl      │  │  PPM-RM-001.ttl │        │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘        │
│  （lbs 引用 lbo 定义的类和属性，表达具体规范内容）                           │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ 引用/实例化
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                      本体层 (lbo:)                                         │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  Upper Industrial Ontology  │  Core Ontology                      │   │
│  │  （顶层工业抽象类）          │  （核心工业类）                      │   │
│  ├────────────────────────────────────────────────────────────────────┤   │
│  │  Domain Ontology  │  Application Ontology                         │   │
│  │  （领域扩展）      │  （应用层扩展，如 PPM 扩展）                  │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│  （lbo 继承 llb 元概念，定义工业领域的所有类和属性）                        │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ 继承/扩展
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                      基础词汇层 (llb:)                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  Entity │ Identifier │ Version │ Document │ Statement             │   │
│  │  Concept │ Agent │ Event │ Time │ Location │ Quantity │ Unit     │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│  （llb 仅提供纯元概念，不包含任何工业领域类或物理类）                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 四层语义基础设施模型与 Namespace 映射

| 层级 | 层级类型 | Namespace | 稳定性 | 治理方式 |
|---|---|---|---|---|
| **Foundation Vocabulary** | 基础词汇层 | `llb:` | 永久冻结 | 核心团队冻结，不可变更 |
| **Ontology** | 本体层 | `lbo:` | 分级冻结 | 详见第16章 |
| **Semantic Package** | 语义包层 | `lbs:` | 版本化演进 | 版本管理，可追溯变更 |
| **Instance Data** | 商业实例层 | `llc:` | 动态更新 | 数据治理，可审计 |

### 4.3 各层稳定性承诺

| 层级 | 稳定性承诺 | 变更流程 |
|---|---|---|
| `llb:` Foundation Vocabulary | **永久冻结** | 不允许任何变更 |
| `lbo:` Upper + Core | **绝对冻结**（Level 0） | 仅允许勘误修正 |
| `lbo:` Domain | **稳定**（Level 1） | 需架构委员会批准 |
| `lbo:` Application | **可演进**（Level 2） | 模块维护者自主更新 |
| `lbs:` Semantic Package | **版本化** | Git式版本管理 |
| `llc:` Commercial Instance | **动态** | 数据治理流程 |


## 5. Foundation Vocabulary（llb — 语义基础层）

### 5.1 定位

`llb:` 是 leleby 的 **Foundation Namespace**，提供所有语义表达所需的纯元概念和框架。**它不包含任何 Ontology 类（如 PhysicalEntity、Object、Process），也不包含任何工业领域类。**

`llb:` 的设计参考了 BFO（Basic Formal Ontology）和 DOLCE 的上层架构思想，但**仅取其元概念层级，不引入物理/对象/过程的 Ontology 分类**。

### 5.2 核心基础类（llb）定义

| 类 | 定义 | 说明 |
|---|---|---|
| `llb:Entity` | 所有实体的顶级抽象 | 唯一根类 |
| `llb:Concept` | 概念的顶级抽象 | 用于抽象概念的表达 |
| `llb:Agent` | 行为主体（人、组织、系统） | 有意图的实体 |
| `llb:Organization` | 组织实体（企业、机构、标准组织） | Agent 的子类 |
| `llb:Identifier` | 标识符（ID、URI、编码） | 信息实体 |
| `llb:Version` | 版本标识 | 信息实体 |
| `llb:Document` | 文档（标准文件、报告、证书） | 信息实体 |
| `llb:Event` | 事件（测试事件、生产事件） | 发生物 |
| `llb:Statement` | 声明（断言、声明、主张） | 信息实体 |
| `llb:Time` | 时间相关概念 | — |
| `llb:Location` | 位置相关概念 | — |
| `llb:Quantity` | 量的抽象（数值、单位） | — |
| `llb:Unit` | 计量单位 | — |

### 5.3 关键约束

`llb:` 中的所有类都**不包含任何 Ontology 语义**：

- ❌ **不包含** `PhysicalEntity`、`Object`、`Process`、`Continuant`、`Occurrent`
- ❌ **不包含** `Product`、`Specification`、`Requirement`、`Capability`
- ✅ **仅包含** 纯元概念：Entity、Concept、Agent、Identifier、Version、Document、Event、Statement、Time、Location、Quantity、Unit


## 6. Upper Industrial Ontology（lbo — 上层工业本体）

### 6.1 定位

`lbo:UpperIndustrialOntology` 是 leleby 的 **上层工业本体**，定义了工业世界中最基础的抽象概念。它是所有工业 Ontology 的根。

**这些类由 `llb:` 元概念派生，但加入了工业语义维度。**

### 6.2 核心工业类定义

| 类 | 定义 | 继承自 |
|---|---|---|
| `lbo:IndustrialEntity` | 工业实体的顶级抽象 | `llb:Entity` |
| `lbo:Product` | 产品或产品系列 | `lbo:IndustrialEntity` |
| `lbo:ProductInstance` | 产品具体实例（批次/个体） | `lbo:IndustrialEntity` |
| `lbo:Specification` | 产品技术规格的事实描述 | `llb:Statement` |
| `lbo:Capability` | 产品在特定条件下实现某种功能的潜在倾向 | `llb:Concept` |
| `lbo:Requirement` | 必须满足的约束性期望（技术要求） | `llb:Statement` |
| `lbo:Demand` | 客户/市场的商业期望（商务需求）—— **v1.2 新增** | `llb:Statement` |
| `lbo:Constraint` | 可计算的约束表达 | `llb:Concept` |
| `lbo:Measurement` | 测量活动及其结果 | `llb:Event` + `llb:Statement` |
| `lbo:TestMethod` | 测试方法定义 | `llb:Document` |
| `lbo:TestResult` | 测试结果 | `llb:Statement` |
| `lbo:SamplingPlan` | 抽样方案 | `llb:Concept` |
| `lbo:ComplianceStatement` | 符合性声明 | `llb:Statement` |
| `lbo:Classification` | 分类/分级方法 | `llb:Concept` |
| `lbo:Standard` | 标准文件 | `llb:Document` |
| `lbo:StandardClause` | 标准条款 | `llb:Statement` |
| `lbo:Regulation` | 法规文件 | `llb:Document` |
| `lbo:BOMStructure` | 物料清单结构 | `llb:Concept` |
| `lbo:BOMComponent` | BOM 组件 | `lbo:IndustrialEntity` |
| `lbo:Organization` | 企业/组织 | `llb:Organization` |
| `lbo:EvaluationContext` | 评价上下文 | `llb:Concept` |

### 6.3 六元要求语义框架（v1.2 更新）

> **Requirement 是 leleby 语义基础设施中表达“约束性期望”的核心语义单元。** 其核心语义由六元组构成，v1.2 将第三元从 `Characteristic` 升级为 `SemanticTarget`：

```
Requirement =
    Authority（谁提出的——通过 Source 推理获得）
  + Scope（适用于什么范围——产品类型/市场/生命周期/环境）
  + SemanticTarget（要求什么目标元素——特性/功能/接口/关系/结构/过程/服务）
  + Condition（在什么条件下有效）
  + Constraint（必须满足什么约束）
  + Obligation（强制/推荐/可选）
```

**SemanticTarget 类型体系（v1.2 引入架构层）：**

```
SemanticTarget
    ├── CharacteristicTarget（特性——指向 lbo-core:Characteristic）
    ├── FunctionTarget（功能——指向 lcap:Function / lprod:ProductFeature）
    ├── InterfaceTarget（接口——指向 lprod:Interface）
    ├── RelationshipTarget（关系——指向 lprod:ProductRelationship）
    ├── StructureTarget（结构——指向 lprod:Structure）
    ├── ProcessTarget（过程——指向 lprod:Process）
    └── ServiceTarget（服务——指向 lprod:Service）
```

**为什么升级？**

| 维度 | v1.1（Characteristic） | v1.2（SemanticTarget） |
|---|---|---|
| 约束目标 | 仅物理特性 | 特性/功能/接口/关系/结构/过程/服务 |
| 示例 | "效率 ≥ 90%" | "电机必须具有过载保护功能"、"车辆必须具有4个工作轮胎" |
| 与 Product Ontology 对齐 | 弱 | 强（RelationshipTarget → ProductRelationship） |

### 6.4 EvaluationContext（跨模块共享核心概念）

`lbo:EvaluationContext` 是本架构的核心创新概念之一，**必须被提升为 Upper Industrial Ontology 的核心对象**。

```
lbo:EvaluationContext
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "EvaluationContext" ;
    rdfs:comment "评价上下文，表达环境、工况、检验阶段、市场区域、生命周期阶段等评价条件" .
```

**用途：** 同一属性在不同条件下可能有不同的要求、规格和验证结果。

**应用于：**

| 模块 | 使用方式 |
|---|---|
| Requirement | `underContext` —— 要求在什么条件下生效 |
| Specification | `specifiedForContext` —— 规格适用于什么条件 |
| Verification | `executedInContext` —— 验证在什么条件下执行 |
| Compliance | `assessedInContext` —— 符合性在什么上下文中判定 |
| Decision | `appliesInContext` —— 决策适用于什么条件 |

**Context 子类（示例）：**

```
EvaluationContext
    ├── EnvironmentalContext（环境条件）
    │   ├── TemperatureRange
    │   ├── HumidityRange
    │   └── AltitudeRange
    ├── OperatingContext（工况条件）
    │   ├── LoadCondition
    │   ├── ModeCondition
    │   └── SpeedCondition
    ├── InspectionStageContext（检验阶段）
    │   ├── IncomingInspection
    │   ├── InProcessInspection
    │   └── FinalInspection
    ├── MarketContext（市场区域）
    │   ├── EU
    │   ├── US
    │   └── Asia
    └── LifecycleContext（生命周期阶段）
        ├── ManufacturingPhase
        ├── OperationPhase
        └── EndOfLifePhase
```


## 7. Core Ontology（lbo — 核心工业本体）

### 7.1 定位

`lbo:CoreOntology` 是 leleby 的 **核心工业本体**，定义了所有工业领域共享的核心概念和关系。它建立在 Upper Industrial Ontology 之上，是 Domain Ontology 和 Application Ontology 的基础。

### 7.2 核心类定义

Core Ontology 继承了 Upper Industrial Ontology 中定义的所有类，并进一步细化和约束：

- `lbo:Product` —— 产品或产品系列
- `lbo:ProductInstance` —— 产品具体实例
- `lbo:Specification` —— 产品/过程/服务的规格描述
- `lbo:Capability` —— 能力
- `lbo:Requirement` —— 要求（技术性约束期望）
- `lbo:Demand` —— 商务需求（v1.2 新增）
- `lbo:Constraint` —— 约束
- `lbo:Measurement` —— 测量
- `lbo:TestMethod` —— 测试方法
- `lbo:ComplianceStatement` —— 符合性声明
- `lbo:EvaluationContext` —— 评价上下文
- `lbo:SemanticTarget` —— 语义目标（v1.2 新增）

### 7.3 Core Ontology 与其他层的关系

```
lbo:UpperIndustrialOntology
    │
    └── lbo:CoreOntology（基础工业概念）
            │
            ├── lbo:DomainOntology（领域扩展：Motor, Lighting, Battery, Pump）
            │       │
            │       └── lbo:ApplicationOntology（应用层扩展：PPM Extension）
            │
            └── lbo:FrameworkOntology（框架扩展：Specification Framework, 等）
```


## 8. Domain Ontology Architecture（领域本体架构）

### 8.1 领域本体设计原则

1. **单一职责**——每个领域本体专注于一个工业领域（电机、照明、电池等）
2. **继承基础**——所有领域本体继承 `lbo:CoreOntology` 核心类
3. **分类即断言**——技术路线、材料路线等使用 `hasClassification` 断言，而非子类化
4. **可组合**——多个领域本体可共存，交叉引用

### 8.2 领域本体示例

**正确的建模方式（贯彻分类即断言原则）：**

```
lbo:Motor
    │
    ├── hasTechnology → TechnologyValue
    │       ├── "BLDC"
    │       ├── "PMSM"
    │       ├── "Induction"
    │       └── "SwitchedReluctance"
    │
    ├── hasStructure → StructureValue
    │       ├── "InnerRotor"
    │       └── "OuterRotor"
    │
    ├── hasApplication → ApplicationValue
    │       ├── "IndustrialDrive"
    │       ├── "Automotive"
    │       └── "Consumer"
    │
    └── hasPowerClass → PowerClassValue
            ├── "Micro"（< 100W）
            ├── "Standard"（100W - 1kW）
            └── "Power"（> 1kW）
```

**❌ 不推荐（旧方式）：**

```
lbo:Motor
    │
    ├── lbo:BLDCMotor  ← 不推荐：将技术路线固化为子类
    └── lbo:PMSMMotor  ← 不推荐
```

### 8.3 分类即断言原则的贯彻

分类断言使用 `lbo:Classification` 模型：

```
ClassificationAssertion
    │
    ├── subject → Motor（被分类的对象）
    │
    ├── dimension → TechnologyDimension（分类维度）
    │
    ├── value → "BLDC"（分类值）
    │
    └── method → ClassificationMethod（分类方法，可选）
```


## 9. Semantic Package Architecture（语义包架构）

### 9.1 定义

**Semantic Package（语义包）** 是 leleby 的核心知识封装机制。

**语义包是对某一权威规则体系（IEC、GB、ISO 等标准、PPM 等企业/行业规范、法规、行业惯例等）的完整语义化表达。它不是 Ontology（本体），而是 Ontology 的实例化应用——使用 `lbo:` 和 `llb:` 定义的类和关系，表达具体规范/标准的内容。**

**Standard Semantic Package（标准语义包）** 是 Semantic Package 的首个重要应用类型，专门用于 IEC、GB、ISO 等标准的语义化表达。其他应用类型包括：
- **Regulation Package**（法规语义包）
- **Industry Practice Package**（行业惯例语义包）
- **Enterprise Specification Package**（企业规范语义包，如 PPM）

### 9.2 Semantic Package 与 Ontology 的本质区别

| 维度 | Ontology（lbo） | Standard Package（lbs） |
|---|---|---|
| 定义内容 | 世界有什么东西（类、属性、关系） | 某个规则体系如何约束世界（具体规范） |
| 示例 | `lbo:Product`, `lbo:Motor` | `lbs:IEC-60034-1-2025`, `lbs:PPM-RM-001-v1.0` |
| 稳定性 | 分级冻结 | 版本化演进 |
| 创建方式 | 本体工程师定义 | 标准分析师从标准文本提取 |

### 9.3 语义包清单模型（Package Manifest）

每个标准语义包必须包含一个 `Package Manifest`：

```
lbs:SemanticPackage
    │
    └── hasManifest → lbs:PackageManifest

lbs:PackageManifest
    │
    ├── packageId: "IEC-60034-1-2025"（唯一标识）
    │
    ├── packageType: "Standard" | "Regulation" | "IndustryPractice" | "ProductStandard"
    │
    ├── version: "1.0.0"
    │
    ├── releaseDate: "2026-07-31"
    │
    ├── status: "published" | "draft" | "superseded" | "withdrawn"
    │
    ├── issuedBy: lreq:IEC_TC2（引用 Authority）
    │
    ├── approvedBy: "IEC TC2"（批准机构）
    │
    ├── approvalDate: "2025-12-15"
    │
    ├── effectiveDate: "2026-02-01"
    │
    ├── jurisdiction: "International"
    │
    ├── hasArtifact: [文件列表]
    │
    ├── hasDependency: [依赖的其他 Semantic Package]
    │
    └── hasChangeLog: [变更记录]
```

### 9.4 标准语义包结构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Standard Semantic Package                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  Package Manifest                                                          │
│  ├── packageId, version, releaseDate, status                              │
│  ├── issuedBy, approvedBy, approvalDate, effectiveDate                   │
│  ├── jurisdiction                                                         │
│  ├── hasArtifact, hasDependency, hasChangeLog                            │
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
└─────────────────────────────────────────────────────────────────────────────┘
```


## 10. Standard Ontology（标准本体）

### 10.1 定位

标准是工业世界的**一等对象**。`Standard Ontology` 独立定义标准的完整语义，特别区分**标准文件（Document）** 和**标准版本（Edition）**，以支持法律追溯和版本管理。

### 10.2 Standard Document vs Standard Edition

| 概念 | 说明 | 示例 |
|---|---|---|
| **Standard Document** | 标准文件的抽象标识，不包含具体版本 | "IEC 60034" |
| **Standard Edition** | 标准的特定版本/发布 | "IEC 60034:2025" |

**关系：**

```
StandardDocument（IEC 60034）
    │
    ├── hasEdition → StandardEdition（IEC 60034:2025）
    │       ├── hasVersion: "2025"
    │       ├── effectiveDate: "2026-02-01"
    │       ├── status: "published"
    │       └── supersedes → StandardEdition（IEC 60034:2017）
    │
    └── hasEdition → StandardEdition（IEC 60034:2017）
            ├── hasVersion: "2017"
            ├── status: "superseded"
            └── supersededBy → StandardEdition（IEC 60034:2025）
```

### 10.3 核心概念

| 概念 | 说明 |
|---|---|
| `lbo:StandardDocument` | 标准的抽象标识（不含版本） |
| `lbo:StandardEdition` | 标准的特定版本 |
| `lbo:StandardClause` | 标准条款 |
| `lbo:Regulation` | 法规文件 |
| `lbo:IndustryPractice` | 行业惯例 |
| `lbo:Guideline` | 指南 |
| `lbo:BestPractice` | 最佳实践 |

### 10.4 标准属性

```
StandardDocument
    │
    ├── standardId: "IEC-60034"
    │
    ├── title: "Rotating electrical machines"
    │
    ├── issuingBody: "IEC"
    │
    └── hasEdition → StandardEdition

StandardEdition
    │
    ├── version: "2025"
    │
    ├── officialFile: "https://.../IEC-60034-1-2025.pdf"
    │
    ├── approvedBy: "IEC TC2"
    │
    ├── approvalDate: "2025-12-15"
    │
    ├── effectiveDate: "2026-02-01"
    │
    ├── withdrawDate: null（如已废止则填写）
    │
    ├── jurisdiction: "International"
    │
    ├── status: "published" | "superseded" | "withdrawn"
    │
    ├── supersedes → StandardEdition（前一版本）
    │
    ├── supersededBy → StandardEdition（后一版本，如适用）
    │
    └── hasClause → StandardClause
```

### 10.5 标准条款与要求的关系

```
StandardEdition
    │
    └── hasClause → StandardClause
            │
            └── defines → Requirement
                    │
                    └── derivedFrom: StandardClause
```


## 11. Demand Ontology 边界说明（v1.2 新增）

### 11.1 Demand 与 Requirement 的分离

**重要：** `Demand`（商务需求）与 `Requirement`（技术要求）是两个不同层级的概念，必须分离。

| 维度 | Demand（商务需求） | Requirement（技术要求） |
|---|---|---|
| **性质** | 商务性、市场性、期望性 | 技术性、规范性、约束性 |
| **来源** | 客户、市场、采购合同 | 标准、法规、技术规范 |
| **示例** | "交货日期 2026-10-01"、"采购数量 500 台" | "电机效率 ≥ 90%"、"防护等级 IP66" |
| **约束对象** | 交付条件、商务条款、服务范围 | 产品特性、功能、接口、结构关系 |
| **所属 Ontology** | **预留 Demand Ontology（待定义）** | **Requirement Ontology（已冻结）** |

### 11.2 Demand Ontology 预留接口

Demand 的具体语义结构（交付日期、数量、支付方式、合同条款等）将在后续的 **Demand Ontology Specification** 中定义。本架构为 Demand 预留以下接口：

```
Demand（商务需求）
    │
    ├── hasDemandIdentifier → xsd:string
    │
    ├── hasDemandName → xsd:string
    │
    ├── hasDemandText → xsd:string（原始需求文本）
    │
    ├── fromParty → Organization（提出方，如客户）
    │
    ├── toParty → Organization（接收方，如供应商）
    │
    ├── hasDeliveryDate → xsd:date（期望交货期）
    │
    ├── hasQuantity → Quantity（采购数量）
    │
    ├── hasPaymentTerms → PaymentTerm（支付条款）
    │
    ├── hasContractReference → Document（合同引用）
    │
    └── mayDerive → Requirement[]（派生的技术要求）
```

**Demand → Requirement 转换链路：**

```
Demand（商务需求）
    │
    │  商务需求分析
    │  合同条款解析
    ▼
Technical Requirement Set（技术要求集合）
    │
    │  derivedFromDemand
    │  derivedFromContract
    ▼
Requirement Ontology（技术要求语义表达）
```

**重要约束：**

> Demand Ontology 不属于 Requirement Ontology。Demand 和 Requirement 是两个独立的 Ontology 模块，分别归入 `lbo:DemandOntology` 和 `lbo:RequirementOntology`。Requirement 不定义商务需求，Demand 不定义技术要求。


## 12. Constraint & Reasoning Layer（约束与推理层）

### 12.1 四层执行架构

| 层次 | 技术 | 职责 | 输出 |
|---|---|---|---|
| **概念建模** | OWL 2 | 定义类、属性、关系 | Ontology |
| **结构验证** | SHACL | 验证数据完整性、格式、基数 | 验证报告 |
| **约束语义** | Constraint Ontology | 表达约束是什么（范围/枚举/逻辑/比较） | 约束实例 |
| **规则推理** | Rule Engine | 执行数值计算、条件判断 | VerificationCompliance |
| **决策推理** | Decision Engine | 多因素综合判断、行动映射 | DecisionResult + Action |

### 12.2 各层职责与输入输出

| 层次 | 输入 | 输出 | 归属 |
|---|---|---|---|
| OWL 推理 | RDF 三元组 | 推断的三元组 | OWL 引擎 |
| SHACL 验证 | RDF 数据 | 完整性报告 | SHACL 引擎 |
| 规则推理 | Requirement + Specification + Measurement | VerificationCompliance | 规则引擎 |
| 决策推理 | VerificationCompliance + EvaluationCompliance | DecisionResult + Action | 决策引擎 |

### 12.3 Constraint Ontology 定位

**Constraint Ontology 不是 SHACL，也不是 Rule Engine。** 它定义的是"约束的语义模型"，即"约束是什么"，而不是"如何验证"或"如何计算"。

- **Constraint Ontology**：定义 `RangeConstraint`、`EnumerationConstraint`、`ComparisonConstraint` 等类型的结构
- **SHACL**：验证数据是否符合这些约束的结构要求
- **Rule Engine**：计算约束是否被满足（如 `minValue ≤ 实测值 ≤ maxValue`）

### 12.4 各类约束定义

| 约束类型 | 说明 | 示例 |
|---|---|---|
| `lbo:RangeConstraint` | 范围约束 | [-20, 70] |
| `lbo:ToleranceConstraint` | 公差约束 | 15.0 ± 0.02 |
| `lbo:EnumerationConstraint` | 枚举约束 | {IP65, IP66, IP67} |
| `lbo:ExactConstraint` | 精确约束 | = 24V |
| `lbo:ComparisonConstraint` | 比较约束 | ≥ 85% |
| `lbo:StatisticalConstraint` | 统计约束 | MTBF ≥ 50000h @ 90% |
| `lbo:DependencyConstraint` | 依赖约束 | IF A THEN B |
| `lbo:TemporalConstraint` | 时间约束 | 在 2028 年后 |
| `lbo:GeographicConstraint` | 地理约束 | 仅限欧洲 |


## 13. Compliance Model（符合性模型）

### 13.1 Compliance 三级模型

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Compliance 三级模型                                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Level 1: VerificationCompliance（单项符合性）                      │   │
│  │  描述：单项要求是否满足                                              │   │
│  │  来源：Verification Result                                          │   │
│  │  示例："温度要求 -40℃ PASS"                                        │   │
│  │  责任：Verification Ontology                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │  aggregatedBy                         │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Level 2: EvaluationCompliance（综合评价）                          │   │
│  │  描述：多个单项符合性的综合评估                                      │   │
│  │  来源：多个 VerificationCompliance + 评估规则                       │   │
│  │  示例："98/100 项要求通过 → 产品合格"                              │   │
│  │  责任：Compliance Ontology（综合评估）                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │  declaredAs                           │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Level 3: ComplianceDeclaration（对外声明）                         │   │
│  │  描述：面向外部利益相关者的符合性断言                                │   │
│  │  来源：EvaluationCompliance                                         │   │
│  │  示例："产品 X 符合 IEC 60598 标准"                                │   │
│  │  责任：Compliance Ontology（声明层）                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 ComplianceDeclaration 法律属性

ComplianceDeclaration 不仅是一个技术断言，**更是一个法律声明**。必须包含以下属性：

```
ComplianceDeclaration
    │
    ├── declaredBy → Organization（声明发布者——企业/机构）
    │
    ├── issuedDate → xsd:dateTime（声明发布日期）
    │
    ├── legalResponsibility → xsd:string（法律责任声明，如"本声明基于真实测试数据"）
    │
    ├── subject → Product / ProductInstance（声明对象）
    │
    ├── against → Standard / Regulation（声明依据的标准/法规）
    │
    ├── applicableScope → Market / Jurisdiction（声明适用范围）
    │
    ├── result: "compliant" | "non-compliant" | "partially-compliant"
    │
    ├── basedOn → VerificationResult[]（依据的验证结果）
    │
    └── evidence → TestReport[]（证据文件）
```


## 14. PPM as Industrial Validation Platform（PPM 作为工业验证平台）

### 14.1 PPM 的战略定位

PPM（Perfect Product Manufacture）是 leleby 语义基础设施的**工业验证案例与行业落地实践**。

PPM 不是独立品牌或独立公司，而是 leleby 语义基础设施在制造领域的**首个 Enterprise Specification Package 实践和验证案例**——通过语义标准定义高价值工业功能部件、建立验证体系和制造能力认证网络，验证 leleby 多层语义模型和语义包框架在真实工业场景中的完整闭环。

### 14.2 PPM 与 leleby 语义架构的关系

```
leleby 语义基础设施
    │
    ├── Foundation Vocabulary（llb:）→ Entity, Identifier, Version, Document
    │
    ├── Upper Industrial Ontology（lbo:）→ Product, Specification, Requirement, Capability
    │
    ├── Core Ontology（lbo:）→ 核心工业概念
    │
    ├── Specification Framework Ontology（lbo:）→ 规范结构、约束表达、验证方法关系
    │
    ├── Standard Ontology（lbo:）→ 标准、法规、条款
    │
    ├── Standard Semantic Package（lbs:）→ PPM-RM-001-v1.0.ttl
    │
    └── Commercial Instance（llc:）→ PPM Certified Manufacturer, PPM Module Instance
```

### 14.3 PPM 在 leleby 战略目标体系中的位置

| 层次 | PPM 的贡献 |
|---|---|
| **L0: 基础设施层** | 验证 Specification Framework Ontology 在真实工业标准制定中的有效性；建立标准语义包从定义→版本管理→验证的完整生命周期 |
| **L1: 供给侧语义资产** | 建立 PPM Certified Manufacturer 的 Enterprise Semantic Identity + Product Semantic Model 行业标准 |
| **L2: 需求侧语义资产** | 提供工业采购需求的标准语义参考模型 |
| **L3: 智能商业应用** | 验证从标准语义→产品语义→制造商匹配→交易就绪的完整 AI 商业闭环 |


## 15. 核心语义闭环链路（v1.2 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    leleby 语义闭环链路（v1.2 更新）                         │
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Step 0: 商业入口层（Demand Ontology — v1.2 新增）                   ║ │
│  ║  Customer Demand / Purchase Order / Contract / Market Requirement    ║ │
│  ║  示例："客户需要 500 台 BLDC 电机，10月交货"                         ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    │  derivesTechnicalRequirement          │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Step 1: 标准层（Standard Ontology + Semantic Package）              ║ │
│  ║  Regulation / Standard / Industry Practice / Contract                ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    │  defines                              │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Step 2: 要求层（Requirement Ontology）                              ║ │
│  ║  六元模型：Authority + Scope + SemanticTarget + Condition +          ║ │
│  ║          Constraint + Obligation（v1.2 更新）                        ║ │
│  ║  + EvaluationContext                                                 ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    │  evaluatedAgainst                      │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Step 3: 规范层（Specification Framework Ontology）                   ║ │
│  ║  定义"如何被描述"：ProductSpecification / ProcessSpecification /      ║ │
│  ║  EvaluationSpecification                                               ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    │  verifiedBy / providesInput           │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Step 4: 验证层（Verification Ontology）                              ║ │
│  ║  定义"如何证明满足"：TestMethod / Observation / VerificationResult   ║ │
│  ║  Measurement 是跨模块基础事实层                                        ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    │  supports                              │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Step 5: 符合性层（Compliance Ontology）—— 三级分层                   ║ │
│  ║  5.1 VerificationCompliance（单项符合性）                             ║ │
│  ║  5.2 EvaluationCompliance（综合评价）                                 ║ │
│  ║  5.3 ComplianceDeclaration（对外声明——含法律属性）                   ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    │  informs                              │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Step 6: 决策层（Decision Ontology）                                  ║ │
│  ║  DecisionDefinition / DecisionRule / DecisionResult → Action         ║ │
│  ║  Decision 在 EvaluationContext 中执行                                 ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                                                             │
│  完整闭环：Demand → Requirement → Specification → Verification →           │
│            Compliance → Decision → Action                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## 16. 冻结声明（v1.2 更新）

### 16.1 冻结范围

v1.2 确认后，以下内容进入**冻结状态**：

- ✅ 四层命名空间架构（llb / lbo / lbs / llc）
- ✅ llb 与 lbo 的职责边界（llb 不含任何 Ontology 语义）
- ✅ lbo 内部四层结构（Upper / Core / Domain / Application）
- ✅ EvaluationContext 作为 Core Ontology 核心对象
- ✅ **Requirement 六元语义框架**（Authority + Scope + SemanticTarget + Condition + Constraint + Obligation）
- ✅ **SemanticTarget 作为第三元**（冻结“框架”，不冻结“具体类型”）
- ✅ Demand 与 Requirement 分离原则
- ✅ 分类即断言原则
- ✅ 模块划分与职责边界
- ✅ 核心推理链路（Demand → Requirement → Specification → Verification → Compliance → Decision → Action）
- ✅ 四层执行架构（OWL / SHACL / Rule Engine / Decision Engine）
- ✅ Semantic Package Manifest 模型

### 16.2 冻结分级

| 级别 | 范围 | 变更规则 |
|---|---|---|
| **Level 0（绝对冻结）** | Namespace 架构、llb 内容、Upper Industrial Ontology、Core 核心类、推理链路 | 不允许任何变更 |
| **Level 1（稳定）** | Domain Ontology 核心类、SemanticTarget 框架 | 需架构委员会 2/3 多数批准 |
| **Level 2（可演进）** | Application Ontology、领域扩展、SemanticTarget 具体子类型 | 模块维护者自主更新，需向后兼容 |

### 16.3 冻结后允许

- ✅ 模块内部的类和属性扩展
- ✅ 行业 Domain Extension（Level 2）
- ✅ Mapping 增强
- ✅ 新增辅助模块（如 Market Ontology、SupplyChain Ontology、Demand Ontology）
- ✅ 新增领域扩展模块（如 Lighting Extension、Automotive Extension）
- ✅ 新增 Application Ontology（如 PPM Extension）
- ✅ **新增 SemanticTarget 子类型**（扩展点）

### 16.4 冻结后禁止

- ❌ **改变核心语义边界**（如 Requirement 的定义、六元框架）
- ❌ **改变核心推理链**（如 Verification → Compliance → Decision 的顺序）
- ❌ **改变模块核心职责**（如 Verification 承担决策职责）
- ❌ **删除或合并核心模块**
- ❌ **改变命名空间职责边界**（如将 Ontology 放入 llb）
- ❌ **在 llb 中添加任何 Ontology 类**（如 PhysicalEntity）
- ❌ **将 SemanticTarget 回退为仅支持 Characteristic**
- ❌ **将 Demand 混入 Requirement Ontology**


## 17. 下一步工作计划（v1.2 更新）

### 已完成模块规范（v1.2 同步）

| 序号 | 模块规范 | 状态 | 版本 |
|---|---|---|---|
| 0 | leleby Semantic Infrastructure Architecture Specification | ✅ 正式冻结 | v1.2（本文档） |
| 1 | leleby Requirement Ontology Specification | ✅ 核心冻结 | v1.1 |
| 2 | leleby Product Ontology Specification | ✅ 核心冻结 | v0.4 |
| 3 | leleby Standard Ontology Specification | ✅ 核心冻结 | v1.3 |
| 4 | leleby Constraint Ontology Specification | ✅ 核心冻结 | v1.2 |
| 5 | leleby Specification Framework Ontology Specification | ✅ 核心冻结 | v1.2 |
| 6 | leleby Verification Ontology Specification | ✅ 候选冻结 | v0.1 |
| 7 | leleby Decision Ontology Specification | ✅ 候选冻结 | v0.1 |

### 待开发模块规范（按优先级）

#### Phase 0：基础层（P0，最高优先级）

1. **Foundation Vocabulary Specification v1.0** —— llb 命名空间完整定义
2. **Core Ontology Specification v1.0** —— 包含 EvaluationContext 和 SemanticTarget 完整定义
3. **Measurement Ontology Specification v1.0** —— 跨模块量值基础

#### Phase 1：支撑层（P0）

4. **Demand Ontology Specification v1.0** —— 商务需求语义定义（v1.2 新增）
5. **Compliance Ontology Specification v1.0** —— 三级分层设计 + 法律属性
6. **Evidence Ontology Specification v1.0**
7. **Classification Ontology Specification v1.0** —— 条件函数分类模型

#### Phase 2：框架层（P1）

8. **Semantic Package Architecture Specification v1.0** —— 含 Package Manifest

#### Phase 3：企业语义层（P1）

9. **Organization Ontology Specification v1.0**
10. **Capability Ontology Specification v1.0**
11. **Process Ontology Specification v1.0**

#### Phase 4：生态集成（P2）

12. **Mapping Ontology Specification v1.0**
13. **Method Ontology Specification v1.0**


## 18. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v0.1 - v0.8 | 2026-07-27 ~ 2026-07-28 | 初始版本至综合版本 |
| v0.9 | 2026-07-28 | 最终冻结候选版 |
| v1.0-rc1 | 2026-07-31 | 发布候选版：Semantic Infrastructure 定位；四层语义资产；llb/lbo/lbs/llc 架构 |
| v1.1 | 2026-07-31 | 架构冻结发布版：llb 纯化为 Foundation Vocabulary；四层 Ontology 层级；分类即断言原则；Package Manifest；Standard Document/Edition 区分；EvaluationContext 提升；三级冻结分级 |
| **v1.2** | **2026-08-04** | **架构澄清版**：1）Requirement 六元模型第三元从 `Characteristic` 升级为 `SemanticTarget`（特性/功能/接口/关系/结构/过程/服务）；2）新增 Demand Ontology 边界说明章节，明确 Demand 与 Requirement 分离；3）更新核心语义闭环链路图，增加 Demand 作为商业入口；4）冻结声明调整为冻结“六元语义框架”而非具体字段，冻结“架构原则”而非具体类模型；5）同步更新各模块版本状态（Requirement v1.1、Product v0.4、Standard v1.3、Constraint v1.2、Specification v1.2）；6）新增 Demand Ontology 到下一步工作计划 |


*— leleby Semantic Infrastructure Architecture Specification v1.2 — Architecture Clarification Release —*