# leleby Decision Ontology Specification v0.2

**文档版本：** v0.2 — Semantic Decision Alignment Release（语义决策对齐版）

**文档类型：** 模块规范（Module Ontology Specification）

**文档状态：** ⚠️ **候选冻结（Candidate Freeze）** — 核心结构与职责已明确，待实践验证后正式冻结

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.2

**对齐模块：**
- `llb` Foundation Vocabulary Specification v1.1（提供 `Entity`、`Concept`、`Statement`、`Agent` 等纯元概念）
- `lbo-core` Core Ontology Specification v1.2（提供 `EvaluationContext`）
- `lreq` Requirement Ontology Specification v1.1（提供 `Requirement`）
- `lver` Verification Ontology Specification v0.2（提供 `VerificationResult`）
- `lcomp` Compliance Ontology Specification v0.2（提供 `ComplianceAssertion`、`ComplianceAssessment`）
- `lbo-meas` Measurement Ontology Specification v0.2（提供 `MeasurementResult`）

**命名空间：** `https://ontology.leleby.org/decision/`

**推荐前缀：** `ldec`

**目标受众：** 本体工程师、质量工程师、生产管理人员、AI Agent 开发者


## 目录

1. 引言
   1.1 目的
   1.2 在 leleby 架构中的位置（v0.2 更新）
   1.3 与 Compliance / Verification / Requirement 的边界（v0.2 更新）
   1.4 v0.2 与 v0.1 的核心差异
   1.5 DMN 兼容性说明

2. 设计原则（v0.2 更新）

3. 核心概念模型
   3.1 总体架构（v0.2 更新）
   3.2 核心关系链（v0.2 更新）

4. 类规范
   4.1 Decision（决策活动）
   4.2 DecisionInput（决策输入——v0.2 重构）
   4.3 ComplianceInput（符合性输入——v0.2 新增）
   4.4 BusinessInput（业务输入——v0.2 新增）
   4.5 RiskInput（风险输入——v0.2 新增）
   4.6 DecisionRule（决策规则——v0.2 增强）
   4.7 DecisionOutcome（决策结果——v0.2 增强）
   4.8 DecisionTable（决策表）
   4.9 InputClause / OutputClause / TableRule（决策表组件）
   4.10 SamplingAcceptanceDecision（抽样接受决策——v0.2 重构）
   4.11 ActionReference（行动引用——v0.2 新增）
   4.12 OutcomeStatus（结果状态——v0.2 新增）

5. 对象属性（v0.2 更新）

6. 数据属性

7. 与 Compliance / Verification 的连接（v0.2 更新）
   7.1 完整决策链路（v0.2 更新）
   7.2 连接示例（v0.2 更新）

8. DMN 兼容性设计

9. 推理规则（v0.2 新增）

10. SHACL 验证约束（v0.2 更新）

11. 完整示例（v0.2 更新）

12. 核心类汇总

13. 冻结声明

14. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Decision Ontology 是 leleby 语义基础设施中**决策推理与行动触发层**的核心模块。它定义了如何基于符合性评估结果、业务规则、风险策略和组织策略，对一个对象、事件或过程进行最终判断，并触发后续行动。

Decision Ontology 是 leleby 语义推理链的**行动决策环节**：

```
Requirement（需要什么）
      │
      ▼
Verification（是否满足）
      │
      ▼
Compliance（是否符合）
      │
      ▼
Decision（如何行动）
      │
      ▼
Action（做什么）
```

### 1.2 在 leleby 架构中的位置（v0.2 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Decision Ontology 在架构中的位置（v0.2）                │
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Compliance Ontology                                                 ║ │
│  ║  输出：ComplianceAssessment（整体符合性汇总）                         ║ │
│  ║  输出：ComplianceAssertion（单项符合性断言）                          ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    │  提供符合性结论                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Decision Ontology（本模块）                                         ║ │
│  ║  输入：ComplianceAssessment + 业务规则 + 风险策略                     ║ │
│  ║  处理：决策表匹配、规则引擎、综合判断                                ║ │
│  ║  输出：DecisionOutcome + ActionReference                             ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    │  驱动执行                             │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Action / Execution Layer                                            ║ │
│  ║  放行 / 返工 / 报废 / 通知 / 记录                                    ║ │
│  ║  （具体执行由 Workflow/Execution Ontology 负责）                     ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 与 Compliance / Verification / Requirement 的边界（v0.2 更新）

| 维度 | Requirement | Verification | Compliance | **Decision** |
|------|-------------|--------------|------------|--------------|
| 核心问题 | 应该满足什么？ | 是否被事实证明？ | 是否符合？ | **如何行动？** |
| 输入 | 利益相关者期望 | 观测/测量数据 | VerificationResult | **ComplianceAssessment** |
| 输出 | 约束 + 义务 | 单项验证结果 | 符合性断言/评估 | **决策结果 + 行动引用** |
| 示例 | "温度 ≥ -40℃" | "温度测试 PASS" | "产品符合温度要求" | **"批次接收 → 放行"** |
| 变化驱动 | 需求变更 | 方法变更 | 规则变更 | **策略/业务规则变更** |

**核心边界声明（v0.2 更新）：**

| Decision Ontology 包含 | Decision Ontology 不包含 |
|----------------------|-------------------------|
| ✅ 综合符合性判断 | ❌ 产品属性要求（归 Requirement） |
| ✅ 判定规则（IF-THEN） | ❌ 检测方法（归 Verification） |
| ✅ 决策表（DMN 风格） | ❌ 测量数据（归 Measurement） |
| ✅ 抽样判定（Ac/Re） | ❌ 抽样计划定义（归 Verification） |
| ✅ 行动引用 | ❌ 行动执行细节（归 Workflow/Execution） |
| ✅ 风险等级判定 | ❌ 风险分析过程 |
| ✅ 业务决策（采购/放行/返工） | ❌ 符合性判断（归 Compliance） |

**核心原则（v0.2 更新）：**

> **Decision 不产生 Compliance。Decision 使用 Compliance 结果做出行动决策。**
>
> - Compliance 回答"是否符合要求"（语义结论）
> - Decision 回答"接下来做什么"（行动决策）

### 1.4 v0.2 与 v0.1 的核心差异

| 问题 | v0.1 状态 | v0.2 修正 |
|---|---|---|
| **Decision 输入** | 主要是 `VerificationResult` | **增加 `ComplianceAssessment` 和 `ComplianceAssertion` 作为核心输入** |
| **Decision 与 Compliance 关系** | Decision 产生 Compliance（隐含） | **Decision 使用 Compliance 结果**（明确反向） |
| **DecisionCondition** | 独立定义 | **合并到 `lbo-core:EvaluationContext`**，不再独立定义 |
| **DecisionInput** | 单一类型 | **重构为子类体系**（ComplianceInput、BusinessInput、RiskInput） |
| **SamplingDecision** | 核心类，包含抽样计划 | **重命名为 `SamplingAcceptanceDecision`**，仅负责 Ac/Re 判断，抽样计划归属 Verification |
| **Action** | 完整的行动类体系 | **降级为 `ActionReference`**，仅做行动引用 |
| **DecisionOutcome** | 基础状态 | **增强状态模型**，新增 `OutcomeStatus` 枚举 |
| **DMN 兼容** | 基础映射 | **保留并增强** |

### 1.5 DMN 兼容性说明

Decision Ontology 的设计与 **OMG DMN（Decision Model and Notation）** 标准保持概念对齐。支持：

- DMN Decision Table 结构的 RDF 表达
- FEEL 表达式的基础映射
- 与 DMN 引擎的双向转换能力

**对齐方式：** 通过 Mapping Ontology 建立 `skos:closeMatch` 关系。


## 2. 设计原则（v0.2 更新）

### 2.1 基于符合性原则（Compliance-based Decision）

> **Decision 必须基于 Compliance 结论，而非直接基于 VerificationResult 或原始数据。** 决策的输入是"已经完成的符合性判断"，而非"验证结果原始值"。

**错误（v0.1 隐含）：**
```
Decision 直接读取 VerificationResult: TemperatureRequirement = PASS
```

**正确（v0.2）：**
```
Decision 读取 ComplianceAssessment: Product 符合 125/128 项要求
```

### 2.2 综合判断原则（Aggregative Decision）

> **Decision 负责聚合 Compliance 结果，形成整体行动判断。** 单项符合性由 Compliance 表达，综合行动决策由 Decision 完成。

### 2.3 规则与数据分离原则（Rule-Data Separation）

> **决策规则（DecisionRule）与决策执行（Decision）分离。** 规则可独立版本化、复用和变更，不影响已产生的决策记录。

### 2.4 可追溯原则（Traceability）

> **每个 Decision 必须可追溯到其输入（ComplianceAssessment）、规则（DecisionRule）和输出（DecisionOutcome + ActionReference）。**

### 2.5 行动引用原则（Action Reference）

> **Decision 的最终输出是"决策结果 + 行动引用"。** Decision 不定义行动的执行细节，仅引用需要在其他层执行的行动。

### 2.6 上下文敏感原则（Context-sensitive）

> **Decision 在特定上下文中执行。** 同一套 Compliance 结果在不同上下文（市场、客户、风险偏好）下可能产生不同的决策结果。


## 3. 核心概念模型

### 3.1 总体架构（v0.2 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Decision 核心概念模型（v0.2）                            │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Decision                                        │   │
│  │  一次决策活动（如：批次接收决策）                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         │                          │                          │            │
│         ▼                          ▼                          ▼            │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐ │
│  │  DecisionInput  │    │  DecisionRule   │    │  DecisionOutcome        │ │
│  │  （输入事实集）   │    │  （判定规则）    │    │  （判定结果）            │ │
│  │  ├─Compliance   │    │                 │    │                         │ │
│  │  ├─Business     │    │                 │    │                         │ │
│  │  └─Risk         │    │                 │    │                         │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────┘ │
│         │                          │                          │            │
│         │                          │                          │            │
│         ▼                          ▼                          ▼            │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐ │
│  │Compliance       │    │ DecisionTable  │    │   ActionReference       │ │
│  │Assessment       │    │  （决策表）      │    │  （触发行动引用）         │ │
│  │（来自 Compliance） │    │                 │    │                         │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    EvaluationContext（来自 Core）                   │   │
│  │  决策执行的上下文环境                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心关系链（v0.2 更新）

```
ComplianceAssessment（符合性评估——来自 Compliance Ontology）
    │
    │  usedAsInput
    ▼
DecisionInput（决策输入）
    │
    │  evaluatedBy
    ▼
DecisionRule（决策规则）
    │
    │  produces
    ▼
DecisionOutcome（决策结果）
    │
    │  triggers
    ▼
ActionReference（行动引用）
```


## 4. 类规范

### 4.1 Decision（决策活动）

```
ldec:Decision
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Process ;
    rdfs:label "Decision" ;
    rdfs:comment "一次决策活动，基于符合性评估和业务规则产生行动决策" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `ldec:decisionIdentifier` | ldec:Decision | xsd:string | 决策编号 | 1 |
| `ldec:decisionName` | ldec:Decision | xsd:string | 决策名称 | 1 |
| `ldec:decisionDescription` | ldec:Decision | xsd:string | 决策描述 | 0..1 |
| `ldec:executedAt` | ldec:Decision | xsd:dateTime | 执行时间 | 0..1 |
| `ldec:executedBy` | ldec:Decision | llb:Agent | 执行主体 | 0..1 |
| `ldec:decisionStatus` | ldec:Decision | ldec:DecisionStatus | 决策状态 | 0..1 |

**关系（v0.2 更新）：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| **`ldec:usesComplianceAssessment`** | ldec:Decision | **`lcomp:ComplianceAssessment`** | **使用的符合性评估（v0.2 新增）** | 1 |
| **`ldec:usesComplianceAssertion`** | ldec:Decision | **`lcomp:ComplianceAssertion`** | **使用的符合性断言（v0.2 新增）** | 0..* |
| `ldec:usesInput` | ldec:Decision | `ldec:DecisionInput` | 使用的输入 | 0..* |
| `ldec:usesRule` | ldec:Decision | `ldec:DecisionRule` | 使用的规则 | 1 |
| `ldec:hasOutcome` | ldec:Decision | `ldec:DecisionOutcome` | 产生的结果 | 1 |
| **`ldec:underContext`** | ldec:Decision | **`lbo-core:EvaluationContext`** | **决策上下文（v0.2 新增）** | 0..1 |

**DecisionStatus 枚举（v0.2 更新）：**

| 值 | 说明 |
|----|------|
| `ldec:Planned` | 计划中 |
| `ldec:InProgress` | 执行中 |
| `ldec:Completed` | 已完成 |
| `ldec:Overridden` | 被覆盖（人工干预） |
| `ldec:Deferred` | 延迟 |

### 4.2 DecisionInput（决策输入——v0.2 重构）

```
ldec:DecisionInput
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "DecisionInput" ;
    rdfs:comment "决策输入数据的抽象基类。具体的输入类型通过子类表达。" .
```

**子类（v0.2 新增）：**

| 子类 | 说明 | 来源 |
|------|------|------|
| **`ldec:ComplianceInput`** | **符合性输入** | **Compliance Ontology（v0.2 新增）** |
| **`ldec:BusinessInput`** | **业务输入** | 外部业务系统（v0.2 新增） |
| **`ldec:RiskInput`** | **风险输入** | 外部风险模型（v0.2 新增） |
| `ldec:VerificationInput` | 验证输入（保留，向后兼容） | Verification Ontology |
| `ldec:HistoricalInput` | 历史输入 | 外部系统 |

### 4.3 ComplianceInput（符合性输入——v0.2 新增）

```
ldec:ComplianceInput
    rdf:type owl:Class ;
    rdfs:subClassOf ldec:DecisionInput ;
    rdfs:label "ComplianceInput" ;
    rdfs:comment "基于符合性评估的决策输入，是 Decision 的核心输入类型" .
```

**关系：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `ldec:referencesComplianceAssessment` | ldec:ComplianceInput | `lcomp:ComplianceAssessment` | 引用的符合性评估 | 1 |
| `ldec:referencesComplianceAssertion` | ldec:ComplianceInput | `lcomp:ComplianceAssertion` | 引用的符合性断言 | 0..* |

### 4.4 BusinessInput（业务输入——v0.2 新增）

```
ldec:BusinessInput
    rdf:type owl:Class ;
    rdfs:subClassOf ldec:DecisionInput ;
    rdfs:label "BusinessInput" ;
    rdfs:comment "业务决策输入，如成本、交期、客户优先级等" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `ldec:cost` | ldec:BusinessInput | xsd:double | 成本 | 0..1 |
| `ldec:deliveryTime` | ldec:BusinessInput | xsd:dateTime | 交付时间 | 0..1 |
| `ldec:customerPriority` | ldec:BusinessInput | xsd:string | 客户优先级 | 0..1 |
| `ldec:inventoryLevel` | ldec:BusinessInput | xsd:integer | 库存水平 | 0..1 |

### 4.5 RiskInput（风险输入——v0.2 新增）

```
ldec:RiskInput
    rdf:type owl:Class ;
    rdfs:subClassOf ldec:DecisionInput ;
    rdfs:label "RiskInput" ;
    rdfs:comment "风险决策输入，如风险等级、风险偏好等" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `ldec:riskLevel` | ldec:RiskInput | ldec:RiskLevel | 风险等级 | 0..1 |
| `ldec:riskTolerance` | ldec:RiskInput | xsd:double | 风险容忍度 | 0..1 |
| `ldec:riskDescription` | ldec:RiskInput | xsd:string | 风险描述 | 0..1 |

**RiskLevel 枚举（v0.2 新增）：**

| 值 | 说明 |
|----|------|
| `ldec:Low` | 低风险 |
| `ldec:Medium` | 中等风险 |
| `ldec:High` | 高风险 |
| `ldec:Critical` | 关键风险 |

### 4.6 DecisionRule（决策规则——v0.2 增强）

```
ldec:DecisionRule
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "DecisionRule" ;
    rdfs:comment "将输入条件映射为决策结果的规则" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|------|----|------|------|------|
| `ldec:ruleIdentifier` | ldec:DecisionRule | xsd:string | 规则编号 | 1 |
| `ldec:ruleName` | ldec:DecisionRule | xsd:string | 规则名称 | 1 |
| `ldec:ruleDescription` | ldec:DecisionRule | xsd:string | 规则描述 | 0..1 |
| `ldec:rulePriority` | ldec:DecisionRule | xsd:integer | 规则优先级 | 0..1 |
| `ldec:ruleVersion` | ldec:DecisionRule | xsd:string | 规则版本 | 0..1 |
| `ldec:effectiveFrom` | ldec:DecisionRule | xsd:dateTime | 生效起始时间 | 0..1 |
| `ldec:effectiveTo` | ldec:DecisionRule | xsd:dateTime | 生效结束时间 | 0..1 |
| **`ldec:ruleSource`** | ldec:DecisionRule | **xsd:string** | **规则来源（政策/法规/合同/标准——v0.2 新增）** | 0..1 |

**关系（v0.2 增强）：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| **`ldec:hasConditionExpression`** | ldec:DecisionRule | **xsd:string** | **规则条件表达式（v0.2 新增）** | 1 |
| `ldec:producesOutcome` | ldec:DecisionRule | `ldec:DecisionOutcome` | 规则产生的结果 | 1 |
| **`ldec:derivedFromPolicy`** | ldec:DecisionRule | **llb:Document** | **规则来源政策文件（v0.2 新增）** | 0..1 |

**v0.2 说明：**

> `ldec:DecisionCondition` 类已被移除。决策条件应通过 `ldec:hasConditionExpression` 直接表达，或通过 `ldec:underContext` 引用 `lbo-core:EvaluationContext`。这简化了模型并消除了与 Core 的重复。

### 4.7 DecisionOutcome（决策结果——v0.2 增强）

```
ldec:DecisionOutcome
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Assessment ;
    rdfs:label "DecisionOutcome" ;
    rdfs:comment "决策产生的最终行动决定" .
```

**结果状态枚举（v0.2 增强）：**

| 值 | 说明 | 适用场景 |
|----|------|----------|
| `ldec:Accept` | 接受 | 批次放行、产品接收 |
| `ldec:Reject` | 拒绝 | 批次拒收、产品退回 |
| `ldec:ConditionalAccept` | 有条件接受 | 附带条件放行 |
| `ldec:NeedReview` | 需评审 | 无法自动判定 |
| `ldec:Escalate` | 升级处理 | 需要更高权限决策 |
| `ldec:Defer` | 延迟决策 | 等待更多信息 |
| **`ldec:Approve`** | **批准（v0.2 新增）** | **设计批准、流程批准** |
| **`ldec:RejectWithRemediation`** | **有条件拒绝（v0.2 新增）** | **需整改后重新提交** |

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `ldec:outcomeStatus` | ldec:DecisionOutcome | `ldec:OutcomeStatus` | 结果状态 | 1 |
| `ldec:outcomeMessage` | ldec:DecisionOutcome | xsd:string | 结果描述 | 0..1 |
| `ldec:outcomeConfidence` | ldec:DecisionOutcome | xsd:double | 置信度 | 0..1 |
| `ldec:outcomeTimestamp` | ldec:DecisionOutcome | xsd:dateTime | 结果时间 | 0..1 |

**关系（v0.2 更新）：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| **`ldec:triggersActionReference`** | ldec:DecisionOutcome | **`ldec:ActionReference`** | **触发的行动引用（v0.2 新增）** | 0..1 |

### 4.8 DecisionTable（决策表）

```
ldec:DecisionTable
    rdf:type owl:Class ;
    rdfs:subClassOf ldec:DecisionRule ;
    rdfs:label "DecisionTable" ;
    rdfs:comment "决策表，用于表达多条件组合的决策规则（DMN 风格）" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `ldec:hasInputClause` | ldec:DecisionTable | ldec:InputClause | 输入子句列表 |
| `ldec:hasOutputClause` | ldec:DecisionTable | ldec:OutputClause | 输出子句列表 |
| `ldec:hasTableRule` | ldec:DecisionTable | ldec:TableRule | 表格规则行 |
| `ldec:hitPolicy` | ldec:DecisionTable | ldec:HitPolicy | 命中策略 |

**HitPolicy 枚举（参考 DMN）：**

| 值 | 说明 |
|----|------|
| `ldec:Unique` | 唯一匹配 |
| `ldec:First` | 第一个匹配 |
| `ldec:Priority` | 按优先级匹配 |
| `ldec:Any` | 任意匹配 |
| `ldec:Collect` | 收集所有匹配 |
| `ldec:RuleOrder` | 规则顺序 |

### 4.9 InputClause / OutputClause / TableRule（决策表组件）

```
ldec:InputClause
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "InputClause" ;
    rdfs:comment "决策表的输入列定义" .
```

```
ldec:OutputClause
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "OutputClause" ;
    rdfs:comment "决策表的输出列定义" .
```

```
ldec:TableRule
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "TableRule" ;
    rdfs:comment "决策表的单行规则" .
```

### 4.10 SamplingAcceptanceDecision（抽样接受决策——v0.2 重构）

```
ldec:SamplingAcceptanceDecision
    rdf:type owl:Class ;
    rdfs:subClassOf ldec:Decision ;
    rdfs:label "SamplingAcceptanceDecision" ;
    rdfs:comment "基于抽样检验的批接受决策。抽样计划（SamplingPlan）由 Verification Ontology 定义，本类仅负责 Ac/Re 判断。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|------|----|------|------|
| `ldec:defectCount` | ldec:SamplingAcceptanceDecision | xsd:integer | 缺陷数量 |
| `ldec:acceptanceNumber` | ldec:SamplingAcceptanceDecision | xsd:integer | 接受数（Ac） |
| `ldec:rejectionNumber` | ldec:SamplingAcceptanceDecision | xsd:integer | 拒收数（Re） |

**v0.2 说明：**

> `sampleSize` 属性已移除，由 Verification Ontology 的 `SamplingPlan` 管理。`SamplingAcceptanceDecision` 仅负责决策逻辑，不负责抽样计划定义。

### 4.11 ActionReference（行动引用——v0.2 新增）

```
ldec:ActionReference
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "ActionReference" ;
    rdfs:comment "对需要执行的具体行动的引用。Decision 不定义行动的执行细节，仅标识需要触发的行动类型和参数。" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `ldec:actionType` | ldec:ActionReference | ldec:ActionType | 行动类型 | 1 |
| `ldec:actionTarget` | ldec:ActionReference | llb:Entity | 行动目标对象 | 0..1 |
| `ldec:actionParameter` | ldec:ActionReference | xsd:string | 行动参数 | 0..1 |
| `ldec:actionPriority` | ldec:ActionReference | ldec:ActionPriority | 行动优先级 | 0..1 |

**ActionType 枚举（v0.2 保留）：**

| 值 | 说明 |
|----|------|
| `ldec:Release` | 放行 |
| `ldec:Rework` | 返工 |
| `ldec:Scrap` | 报废 |
| `ldec:Block` | 隔离 |
| `ldec:Return` | 退货 |
| `ldec:Notify` | 通知 |
| `ldec:Record` | 记录 |
| `ldec:Review` | 评审 |
| `ldec:Escalate` | 升级 |

**ActionPriority 枚举（v0.2 新增）：**

| 值 | 说明 |
|----|------|
| `ldec:Urgent` | 紧急 |
| `ldec:High` | 高 |
| `ldec:Medium` | 中 |
| `ldec:Low` | 低 |

### 4.12 OutcomeStatus（结果状态——v0.2 新增）

```
ldec:OutcomeStatus
    rdf:type owl:Class ;
    rdfs:label "OutcomeStatus" ;
    rdfs:comment "决策结果状态枚举。" .
```

**预定义状态：**

| 值 | 说明 |
|----|------|
| `ldec:Accept` | 接受 |
| `ldec:Reject` | 拒绝 |
| `ldec:ConditionalAccept` | 有条件接受 |
| `ldec:NeedReview` | 需评审 |
| `ldec:Escalate` | 升级处理 |
| `ldec:Defer` | 延迟决策 |
| `ldec:Approve` | 批准 |
| `ldec:RejectWithRemediation` | 有条件拒绝 |


## 5. 对象属性（v0.2 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| **`ldec:usesComplianceAssessment`** | `ldec:Decision` | **`lcomp:ComplianceAssessment`** | **使用的符合性评估（v0.2 新增）** |
| **`ldec:usesComplianceAssertion`** | `ldec:Decision` | **`lcomp:ComplianceAssertion`** | **使用的符合性断言（v0.2 新增）** |
| `ldec:usesInput` | `ldec:Decision` | `ldec:DecisionInput` | 使用的输入 |
| **`ldec:usesVerificationResult`** | `ldec:Decision` | `lver:VerificationResult` | **使用的验证结果（v0.2 保留，向后兼容）** |
| `ldec:usesRule` | `ldec:Decision` | `ldec:DecisionRule` | 使用的规则 |
| `ldec:hasOutcome` | `ldec:Decision` | `ldec:DecisionOutcome` | 产生的结果 |
| **`ldec:triggersActionReference`** | `ldec:DecisionOutcome` | **`ldec:ActionReference`** | **触发的行动引用（v0.2 新增）** |
| **`ldec:underContext`** | `ldec:Decision` | **`lbo-core:EvaluationContext`** | **决策上下文（v0.2 新增）** |
| `ldec:hasConditionExpression` | `ldec:DecisionRule` | xsd:string | 规则条件表达式 |
| `ldec:producesOutcome` | `ldec:DecisionRule` | `ldec:DecisionOutcome` | 规则产生结果 |
| **`ldec:derivedFromPolicy`** | `ldec:DecisionRule` | **llb:Document** | **规则来源政策文件（v0.2 新增）** |
| `ldec:referencesComplianceAssessment` | `ldec:ComplianceInput` | `lcomp:ComplianceAssessment` | 引用的符合性评估 |
| `ldec:hasInputClause` | `ldec:DecisionTable` | `ldec:InputClause` | 有输入列 |
| `ldec:hasOutputClause` | `ldec:DecisionTable` | `ldec:OutputClause` | 有输出列 |
| `ldec:hasTableRule` | `ldec:DecisionTable` | `ldec:TableRule` | 有规则行 |


## 6. 数据属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `ldec:decisionIdentifier` | `ldec:Decision` | xsd:string | 决策编号 |
| `ldec:decisionName` | `ldec:Decision` | xsd:string | 决策名称 |
| `ldec:decisionDescription` | `ldec:Decision` | xsd:string | 决策描述 |
| `ldec:executedAt` | `ldec:Decision` | xsd:dateTime | 执行时间 |
| `ldec:ruleIdentifier` | `ldec:DecisionRule` | xsd:string | 规则编号 |
| `ldec:ruleName` | `ldec:DecisionRule` | xsd:string | 规则名称 |
| `ldec:ruleDescription` | `ldec:DecisionRule` | xsd:string | 规则描述 |
| `ldec:rulePriority` | `ldec:DecisionRule` | xsd:integer | 规则优先级 |
| `ldec:ruleVersion` | `ldec:DecisionRule` | xsd:string | 规则版本 |
| `ldec:ruleSource` | `ldec:DecisionRule` | xsd:string | 规则来源 |
| `ldec:hasConditionExpression` | `ldec:DecisionRule` | xsd:string | 条件表达式 |
| `ldec:outcomeStatus` | `ldec:DecisionOutcome` | `ldec:OutcomeStatus` | 结果状态 |
| `ldec:outcomeMessage` | `ldec:DecisionOutcome` | xsd:string | 结果描述 |
| `ldec:outcomeConfidence` | `ldec:DecisionOutcome` | xsd:double | 置信度 |
| `ldec:defectCount` | `ldec:SamplingAcceptanceDecision` | xsd:integer | 缺陷数量 |
| `ldec:acceptanceNumber` | `ldec:SamplingAcceptanceDecision` | xsd:integer | 接受数 |
| `ldec:rejectionNumber` | `ldec:SamplingAcceptanceDecision` | xsd:integer | 拒收数 |
| `ldec:actionType` | `ldec:ActionReference` | `ldec:ActionType` | 行动类型 |
| `ldec:actionParameter` | `ldec:ActionReference` | xsd:string | 行动参数 |


## 7. 与 Compliance / Verification 的连接（v0.2 更新）

### 7.1 完整决策链路（v0.2 更新）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    完整决策链路（v0.2）                                     │
│                                                                             │
│  Requirement A  ──┐                                                         │
│  （温度 ≥ -40℃）  │                                                         │
│                   │                                                         │
│  Requirement B  ──┤                                                         │
│  （IP ≥ IP65）    │                                                         │
│                   ├──Verification──▶ VerificationResult A（PASS）          │
│  Requirement C  ──┤                   VerificationResult B（PASS）          │
│  （寿命 ≥ 50000h）│                   VerificationResult C（FAIL）           │
│                   │                                                         │
│                   └──────────┬──────────────┘                              │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Compliance Assertions（单项符合性）                                 │   │
│  │  CA_Temp: Compliant                                                │   │
│  │  CA_IP: Compliant                                                  │   │
│  │  CA_Life: NonCompliant                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Compliance Assessment（整体符合性）                                 │   │
│  │  totalRequirementCount: 3                                          │   │
│  │  passedCount: 2                                                    │   │
│  │  failedCount: 1                                                    │   │
│  │  complianceRate: 66.7%                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Decision Input                                                    │   │
│  │  ComplianceAssessment + BusinessRule + RiskContext                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Decision Rule: CriticalFailure_count = 0 AND PASS_count >= 2      │   │
│  │  → Accept                                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Decision Outcome: Accept + ActionReference: Release               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 连接示例（v0.2 更新）

```turtle
# === 1. 验证结果（来自 Verification Ontology） ===
lver:Result_Temp_001
    a lver:VerificationResult ;
    lver:resultStatus lver:PASS .

lver:Result_IP_001
    a lver:VerificationResult ;
    lver:resultStatus lver:PASS .

lver:Result_Life_001
    a lver:VerificationResult ;
    lver:resultStatus lver:FAIL .

# === 2. 符合性断言（来自 Compliance Ontology） ===
lcomp:CA_Temp
    a lcomp:ComplianceAssertion ;
    lcomp:hasSubject lprod:Product_A ;
    lcomp:conformsToRequirement lreq:REQ_Temp ;
    lcomp:hasComplianceStatus lcomp:Compliant ;
    lcomp:basedOnVerification lver:Result_Temp_001 .

lcomp:CA_IP
    a lcomp:ComplianceAssertion ;
    lcomp:hasSubject lprod:Product_A ;
    lcomp:conformsToRequirement lreq:REQ_IP ;
    lcomp:hasComplianceStatus lcomp:Compliant ;
    lcomp:basedOnVerification lver:Result_IP_001 .

lcomp:CA_Life
    a lcomp:ComplianceAssertion ;
    lcomp:hasSubject lprod:Product_A ;
    lcomp:conformsToRequirement lreq:REQ_Life ;
    lcomp:hasComplianceStatus lcomp:NonCompliant ;
    lcomp:basedOnVerification lver:Result_Life_001 .

# === 3. 符合性评估（来自 Compliance Ontology） ===
lcomp:CA_Batch_001
    a lcomp:ComplianceAssessment ;
    lcomp:assessmentIdentifier "CA-BATCH-001" ;
    lcomp:assessmentName "批次符合性汇总" ;
    lcomp:aggregatesAssertions lcomp:CA_Temp ;
    lcomp:aggregatesAssertions lcomp:CA_IP ;
    lcomp:aggregatesAssertions lcomp:CA_Life ;
    lcomp:totalRequirementCount "3"^^xsd:integer ;
    lcomp:passedCount "2"^^xsd:integer ;
    lcomp:failedCount "1"^^xsd:integer ;
    lcomp:complianceRate "66.7"^^xsd:double .

# === 4. 决策规则（v0.2：使用条件表达式，而非独立 Condition 类） ===
ldec:Rule_BatchAccept_001
    a ldec:DecisionRule ;
    ldec:ruleIdentifier "RULE-BATCH-001" ;
    ldec:ruleName "批次接收规则" ;
    ldec:hasConditionExpression "passedCount >= 2 AND failedCount = 0" ;
    ldec:producesOutcome ldec:Outcome_Accept .

ldec:Rule_BatchReview_001
    a ldec:DecisionRule ;
    ldec:ruleIdentifier "RULE-BATCH-002" ;
    ldec:ruleName "批次评审规则" ;
    ldec:hasConditionExpression "failedCount >= 1 AND failedCount <= 2" ;
    ldec:producesOutcome ldec:Outcome_NeedReview .

# === 5. 决策执行（v0.2：使用 usesComplianceAssessment） ===
ldec:Decision_Batch_001
    a ldec:Decision ;
    ldec:decisionIdentifier "DEC-BATCH-001" ;
    ldec:decisionName "20260701批次接收决策" ;
    ldec:executedAt "2026-07-28T14:30:00Z"^^xsd:dateTime ;
    ldec:usesComplianceAssessment lcomp:CA_Batch_001 ;
    ldec:usesRule ldec:Rule_BatchReview_001 ;
    ldec:underContext lcore:Context_FinalInspection ;
    ldec:hasOutcome ldec:Outcome_NeedReview .

# === 6. 决策结果（v0.2：触发 ActionReference） ===
ldec:Outcome_NeedReview
    a ldec:DecisionOutcome ;
    ldec:outcomeStatus ldec:NeedReview ;
    ldec:outcomeMessage "寿命测试未通过，需要评审" ;
    ldec:triggersActionReference [
        a ldec:ActionReference ;
        ldec:actionType ldec:Review ;
        ldec:actionPriority ldec:High ;
        ldec:actionTarget lprod:Product_A
    ] .
```


## 8. DMN 兼容性设计

### 8.1 DMN 概念映射

| DMN 概念 | leleby 概念 | 映射类型 |
|----------|-------------|----------|
| `Decision` | `ldec:Decision` | `skos:closeMatch` |
| `BusinessRule` | `ldec:DecisionRule` | `skos:closeMatch` |
| `InputData` | `ldec:DecisionInput` | `skos:closeMatch` |
| `DecisionTable` | `ldec:DecisionTable` | `skos:closeMatch` |
| `HitPolicy` | `ldec:HitPolicy` | `skos:closeMatch` |
| `Output` | `ldec:DecisionOutcome` | `skos:closeMatch` |
| `DRG`（决策需求图） | `ldec:usesRule` / `ldec:usesInput` | `skos:relatedMatch` |

### 8.2 DMN 决策表示例

```turtle
ldec:DefectDecisionTable
    a ldec:DecisionTable ;
    ldec:hasInputClause [
        a ldec:InputClause ;
        ldec:inputName "缺陷数量"
    ] ;
    ldec:hasInputClause [
        a ldec:InputClause ;
        ldec:inputName "严重等级"
    ] ;
    ldec:hasOutputClause [
        a ldec:OutputClause ;
        ldec:outputName "结论"
    ] ;
    ldec:hasOutputClause [
        a ldec:OutputClause ;
        ldec:outputName "建议行动"
    ] ;
    ldec:hitPolicy ldec:First .
```


## 9. 推理规则（v0.2 新增）

**规则 1：基于符合性评估的接受决策**

```
IF
    ComplianceAssessment CA has passedCount >= threshold
    AND
    ComplianceAssessment CA has failedCount = 0
THEN
    Decision D
        usesComplianceAssessment = CA
        usesRule = AcceptanceRule
        hasOutcome = Accept
```

**规则 2：基于符合性评估的评审决策**

```
IF
    ComplianceAssessment CA has failedCount >= 1
    AND
    ComplianceAssessment CA has failedCount <= reviewThreshold
THEN
    Decision D
        usesComplianceAssessment = CA
        usesRule = ReviewRule
        hasOutcome = NeedReview
```

**规则 3：基于符合性评估的拒收决策**

```
IF
    ComplianceAssessment CA has failedCount > rejectThreshold
THEN
    Decision D
        usesComplianceAssessment = CA
        usesRule = RejectRule
        hasOutcome = Reject
```

**规则 4：决策结果触发行动**

```
IF
    Decision D hasOutcome Accept
THEN
    DecisionOutcome triggers ActionReference of type Release
```


## 10. SHACL 验证约束（v0.2 更新）

### 10.1 Decision 约束（v0.2 更新）

```turtle
ldec:DecisionShape
    a sh:NodeShape ;
    sh:targetClass ldec:Decision ;
    sh:property [
        sh:path ldec:decisionIdentifier ;
        sh:minCount 1 ;
        sh:message "Decision must have an identifier" ;
    ] ;
    sh:property [
        sh:path ldec:decisionName ;
        sh:minCount 1 ;
        sh:message "Decision must have a name" ;
    ] ;
    sh:property [
        sh:path ldec:usesComplianceAssessment ;
        sh:minCount 1 ;
        sh:message "Decision must use a ComplianceAssessment" ;
    ] ;
    sh:property [
        sh:path ldec:usesRule ;
        sh:minCount 1 ;
        sh:message "Decision must use a rule" ;
    ] ;
    sh:property [
        sh:path ldec:hasOutcome ;
        sh:minCount 1 ;
        sh:message "Decision must have an outcome" ;
    ] ;
    sh:property [
        sh:path ldec:usesVerificationResult ;
        sh:minCount 0 ;
        sh:message "Decision should NOT directly use VerificationResult (use ComplianceAssessment instead)" ;
    ] .
```

### 10.2 DecisionRule 约束（v0.2 更新）

```turtle
ldec:DecisionRuleShape
    a sh:NodeShape ;
    sh:targetClass ldec:DecisionRule ;
    sh:property [
        sh:path ldec:ruleIdentifier ;
        sh:minCount 1 ;
        sh:message "DecisionRule must have an identifier" ;
    ] ;
    sh:property [
        sh:path ldec:hasConditionExpression ;
        sh:minCount 1 ;
        sh:message "DecisionRule must have a condition expression" ;
    ] ;
    sh:property [
        sh:path ldec:producesOutcome ;
        sh:minCount 1 ;
        sh:message "DecisionRule must produce an outcome" ;
    ] .
```

### 10.3 DecisionOutcome 约束（v0.2 更新）

```turtle
ldec:DecisionOutcomeShape
    a sh:NodeShape ;
    sh:targetClass ldec:DecisionOutcome ;
    sh:property [
        sh:path ldec:outcomeStatus ;
        sh:minCount 1 ;
        sh:in (
            ldec:Accept
            ldec:Reject
            ldec:ConditionalAccept
            ldec:NeedReview
            ldec:Escalate
            ldec:Defer
            ldec:Approve
            ldec:RejectWithRemediation
        ) ;
        sh:message "Outcome status must be one of predefined values" ;
    ] .
```

### 10.4 ActionReference 约束（v0.2 新增）

```turtle
ldec:ActionReferenceShape
    a sh:NodeShape ;
    sh:targetClass ldec:ActionReference ;
    sh:property [
        sh:path ldec:actionType ;
        sh:minCount 1 ;
        sh:in (
            ldec:Release
            ldec:Rework
            ldec:Scrap
            ldec:Block
            ldec:Return
            ldec:Notify
            ldec:Record
            ldec:Review
            ldec:Escalate
        ) ;
        sh:message "Action type must be one of predefined values" ;
    ] .
```

### 10.5 SamplingAcceptanceDecision 约束（v0.2 更新）

```turtle
ldec:SamplingAcceptanceDecisionShape
    a sh:NodeShape ;
    sh:targetClass ldec:SamplingAcceptanceDecision ;
    sh:property [
        sh:path ldec:defectCount ;
        sh:minCount 1 ;
        sh:datatype xsd:integer ;
        sh:message "SamplingAcceptanceDecision must have a defect count" ;
    ] ;
    sh:property [
        sh:path ldec:acceptanceNumber ;
        sh:minCount 1 ;
        sh:datatype xsd:integer ;
        sh:message "SamplingAcceptanceDecision must have an acceptance number" ;
    ] ;
    sh:property [
        sh:path ldec:rejectionNumber ;
        sh:minCount 1 ;
        sh:datatype xsd:integer ;
        sh:message "SamplingAcceptanceDecision must have a rejection number" ;
    ] .
```


## 11. 完整示例（v0.2 更新）

### 11.1 示例一：批次接收决策（基于 ComplianceAssessment）

```turtle
# === 1. 符合性评估（来自 Compliance Ontology） ===
lcomp:CA_Batch_202607
    a lcomp:ComplianceAssessment ;
    lcomp:assessmentIdentifier "CA-BATCH-202607" ;
    lcomp:assessmentName "批次 202607 符合性汇总" ;
    lcomp:hasSubject lprod:Batch_202607 ;
    lcomp:aggregatesAssertions lcomp:CA_Temp_Batch ;
    lcomp:aggregatesAssertions lcomp:CA_IP_Batch ;
    lcomp:aggregatesAssertions lcomp:CA_Life_Batch ;
    lcomp:totalRequirementCount "3"^^xsd:integer ;
    lcomp:passedCount "2"^^xsd:integer ;
    lcomp:failedCount "1"^^xsd:integer ;
    lcomp:complianceRate "66.7"^^xsd:double .

# === 2. 决策规则 ===
ldec:Rule_BatchAccept_001
    a ldec:DecisionRule ;
    ldec:ruleIdentifier "RULE-BATCH-001" ;
    ldec:ruleName "批次接收规则" ;
    ldec:ruleDescription "所有关键要求均通过且非关键失败数≤1时接受" ;
    ldec:hasConditionExpression "failedCount = 0 AND passedCount >= 2" ;
    ldec:producesOutcome ldec:Outcome_Accept .
    ldec:derivedFromPolicy lcore:QualityPolicy_001 .

ldec:Rule_BatchReview_001
    a ldec:DecisionRule ;
    ldec:ruleIdentifier "RULE-BATCH-002" ;
    ldec:ruleName "批次评审规则" ;
    ldec:ruleDescription "有关键要求失败时进入评审" ;
    ldec:hasConditionExpression "failedCount >= 1" ;
    ldec:producesOutcome ldec:Outcome_NeedReview .

# === 3. 决策执行 ===
ldec:Decision_Batch_202607
    a ldec:Decision ;
    ldec:decisionIdentifier "DEC-BATCH-202607" ;
    ldec:decisionName "批次 202607 接收决策" ;
    ldec:executedAt "2026-07-28T14:30:00Z"^^xsd:dateTime ;
    ldec:usesComplianceAssessment lcomp:CA_Batch_202607 ;
    ldec:usesRule ldec:Rule_BatchReview_001 ;
    ldec:underContext lcore:Context_FinalInspection ;
    ldec:hasOutcome ldec:Outcome_NeedReview .

# === 4. 决策结果 ===
ldec:Outcome_NeedReview
    a ldec:DecisionOutcome ;
    ldec:outcomeStatus ldec:NeedReview ;
    ldec:outcomeMessage "寿命测试未通过，需要质量评审" ;
    ldec:outcomeConfidence "0.95"^^xsd:double ;
    ldec:triggersActionReference [
        a ldec:ActionReference ;
        ldec:actionType ldec:Review ;
        ldec:actionPriority ldec:High ;
        ldec:actionTarget lprod:Batch_202607 ;
        ldec:actionParameter "寿命测试失败，请评审"
    ] .
```

### 11.2 示例二：抽样接受决策（v0.2 重构）

```turtle
# 抽样计划（来自 Verification Ontology）
lver:SamplingPlan_001
    a lver:SamplingPlan ;
    lver:sampleSize "100"^^xsd:integer ;
    lver:samplingMethod "random" ;
    lver:confidenceLevel "95"^^xsd:double .

# 抽样验证结果
lver:SamplingResult_001
    a lver:VerificationResult ;
    lver:resultStatus lver:PASS ;
    lver:hasMessage "样本 100 个，缺陷 2 个" .

# 符合性断言
lcomp:CA_Sampling_001
    a lcomp:ComplianceAssertion ;
    lcomp:hasSubject lprod:Batch_202607 ;
    lcomp:conformsToRequirement lreq:REQ_Sampling ;
    lcomp:hasComplianceStatus lcomp:Compliant ;
    lcomp:basedOnVerification lver:SamplingResult_001 .

# 抽样接受决策（v0.2：仅负责 Ac/Re 判断）
ldec:SamplingDecision_001
    a ldec:SamplingAcceptanceDecision ;
    ldec:decisionIdentifier "DEC-SAMPLING-001" ;
    ldec:decisionName "批次抽样接受决策" ;
    ldec:usesComplianceAssessment lcomp:CA_Sampling_001 ;
    ldec:defectCount "2"^^xsd:integer ;
    ldec:acceptanceNumber "2"^^xsd:integer ;
    ldec:rejectionNumber "3"^^xsd:integer ;
    ldec:usesRule ldec:SamplingRule_Accept ;
    ldec:hasOutcome [
        a ldec:DecisionOutcome ;
        ldec:outcomeStatus ldec:Accept ;
        ldec:triggersActionReference [
            a ldec:ActionReference ;
            ldec:actionType ldec:Release ;
            ldec:actionTarget lprod:Batch_202607
        ]
    ] .

ldec:SamplingRule_Accept
    a ldec:DecisionRule ;
    ldec:ruleIdentifier "RULE-SAMPLING-001" ;
    ldec:ruleName "抽样接受规则" ;
    ldec:hasConditionExpression "defectCount <= acceptanceNumber" ;
    ldec:producesOutcome ldec:Outcome_Accept .
```

### 11.3 示例三：决策表（缺陷分级）

```turtle
ldec:DefectDecisionTable
    a ldec:DecisionTable ;
    ldec:ruleIdentifier "DT-DEFECT-001" ;
    ldec:ruleName "缺陷分级决策表" ;
    ldec:hasInputClause [
        a ldec:InputClause ;
        ldec:inputName "缺陷数量"
    ] ;
    ldec:hasInputClause [
        a ldec:InputClause ;
        ldec:inputName "缺陷严重程度"
    ] ;
    ldec:hasOutputClause [
        a ldec:OutputClause ;
        ldec:outputName "判定结论"
    ] ;
    ldec:hasOutputClause [
        a ldec:OutputClause ;
        ldec:outputName "建议行动"
    ] ;
    ldec:hitPolicy ldec:First .
```


## 12. 核心类汇总

### 12.1 Classes（v0.2 更新）

| 类名 | 父类 | 说明 |
|---|---|---|
| `ldec:Decision` | `llb:Process` | 决策活动 |
| **`ldec:DecisionInput`** | **`llb:Concept`** | **决策输入（抽象——v0.2 重构）** |
| **`ldec:ComplianceInput`** | **`ldec:DecisionInput`** | **符合性输入（v0.2 新增）** |
| **`ldec:BusinessInput`** | **`ldec:DecisionInput`** | **业务输入（v0.2 新增）** |
| **`ldec:RiskInput`** | **`ldec:DecisionInput`** | **风险输入（v0.2 新增）** |
| `ldec:VerificationInput` | `ldec:DecisionInput` | 验证输入（保留，向后兼容） |
| `ldec:DecisionRule` | `llb:Concept` | 决策规则（v0.2 增强） |
| `ldec:DecisionOutcome` | `lbo-core:Assessment` | 决策结果（v0.2 增强） |
| `ldec:DecisionTable` | `ldec:DecisionRule` | 决策表 |
| `ldec:InputClause` | `llb:Concept` | 输入子句 |
| `ldec:OutputClause` | `llb:Concept` | 输出子句 |
| `ldec:TableRule` | `llb:Concept` | 表格规则行 |
| **`ldec:SamplingAcceptanceDecision`** | **`ldec:Decision`** | **抽样接受决策（v0.2 重构）** |
| **`ldec:ActionReference`** | **`llb:Concept`** | **行动引用（v0.2 新增）** |
| `ldec:OutcomeStatus` | — | 结果状态枚举（v0.2 新增） |

### 12.2 Object Properties（v0.2 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| **`ldec:usesComplianceAssessment`** | `ldec:Decision` | `lcomp:ComplianceAssessment` | **使用的符合性评估（v0.2 新增）** |
| **`ldec:usesComplianceAssertion`** | `ldec:Decision` | `lcomp:ComplianceAssertion` | **使用的符合性断言（v0.2 新增）** |
| `ldec:usesInput` | `ldec:Decision` | `ldec:DecisionInput` | 使用的输入 |
| `ldec:usesVerificationResult` | `ldec:Decision` | `lver:VerificationResult` | 使用的验证结果（向后兼容） |
| `ldec:usesRule` | `ldec:Decision` | `ldec:DecisionRule` | 使用的规则 |
| `ldec:hasOutcome` | `ldec:Decision` | `ldec:DecisionOutcome` | 产生的结果 |
| **`ldec:triggersActionReference`** | `ldec:DecisionOutcome` | **`ldec:ActionReference`** | **触发的行动引用（v0.2 新增）** |
| **`ldec:underContext`** | `ldec:Decision` | **`lbo-core:EvaluationContext`** | **决策上下文（v0.2 新增）** |
| `ldec:hasConditionExpression` | `ldec:DecisionRule` | xsd:string | 规则条件表达式 |
| `ldec:producesOutcome` | `ldec:DecisionRule` | `ldec:DecisionOutcome` | 规则产生结果 |
| **`ldec:derivedFromPolicy`** | `ldec:DecisionRule` | **llb:Document** | **规则来源政策文件（v0.2 新增）** |


## 13. 冻结声明

### 13.1 冻结范围

v0.2 确认后，以下内容进入**冻结状态**：

- ✅ 核心模型（Decision + DecisionRule + DecisionOutcome）
- ✅ **Decision 与 Compliance 的接口（usesComplianceAssessment / usesComplianceAssertion）**
- ✅ **Decision 与 Core EvaluationContext 的接口（underContext）**
- ✅ **ActionReference 模型**
- ✅ **SamplingAcceptanceDecision（Ac/Re 判断）**
- ✅ 决策表（DecisionTable）体系
- ✅ 命名空间 `https://ontology.leleby.org/decision/`

### 13.2 冻结后允许

- ✅ 新增 DecisionInput 子类
- ✅ 新增 OutcomeStatus 值
- ✅ 新增 ActionType 值
- ✅ 新增 HitPolicy 值
- ✅ 新增推理规则

### 13.3 冻结后禁止

- ❌ **修改核心决策模型结构**（Decision/DecisionRule/DecisionOutcome）
- ❌ **修改 Decision 与 Compliance 的接口方向**
- ❌ **将 ActionReference 改回完整的 Action 类体系**
- ❌ **在 Decision 中重新定义 Condition**（必须使用 Core EvaluationContext 或条件表达式）
- ❌ **在 Decision 中直接读取 MeasurementResult**（必须经过 Verification/Compliance）


## 14. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| **v0.1** | **2026-07-28** | **初始设计版**：定义 Decision 六元模型；核心类；DMN 兼容性设计；SHACL 验证；完整示例 |
| **v0.2** | **2026-08-04** | **语义决策对齐版**：1）Decision 输入从 VerificationResult 扩展为 ComplianceAssessment（新增 `usesComplianceAssessment`、`usesComplianceAssertion`）；2）Decision 与 Compliance 关系明确为"Decision 使用 Compliance"；3）删除 `DecisionCondition` 类，改用 `hasConditionExpression` 和 `underContext`（引用 Core EvaluationContext）；4）DecisionInput 重构为子类体系（ComplianceInput、BusinessInput、RiskInput）；5）`SamplingDecision` 重命名为 `SamplingAcceptanceDecision`，移除 sampleSize；6）Action 降级为 `ActionReference`；7）新增 `OutcomeStatus` 枚举；8）新增 `derivedFromPolicy` 属性；9）新增推理规则；10）更新 SHACL 验证约束；11）更新完整示例 |


*— leleby Decision Ontology Specification v0.2 — Semantic Decision Alignment Release —*