# leleby Verification Ontology Specification v0.2

**文档版本：** v0.2 — Semantic Verification Alignment Release（语义验证对齐版）

**文档类型：** 模块规范（Module Ontology Specification）

**文档状态：** ⚠️ **候选冻结（Candidate Freeze）** — 核心结构与职责已明确，待实践验证后正式冻结

**依赖架构：** leleby Semantic Infrastructure Architecture Specification v1.2

**对齐模块：**
- `lbo-core` Core Ontology Specification v1.2（提供 `SemanticTarget`、`EvaluationContext`、`Assessment`、`ObligationLevel`）
- `lreq` Requirement Ontology Specification v1.1（提供 `Requirement` 和 `SemanticTarget`）
- `lcon` Constraint Ontology Specification v1.1（提供 `Constraint`）
- `lbo-meas` Measurement Ontology Specification v0.2（提供 `MeasurementResult`）
- `lbo-spec` Specification Framework Ontology Specification v1.1（提供 `SpecificationItem`）

**命名空间：** `https://ontology.leleby.org/verification/`

**推荐前缀：** `lver`

**目标受众：** 本体工程师、质量工程师、测试工程师、合规工程师、AI Agent 开发者


## 目录

1. 引言
   1.1 目的
   1.2 在 leleby 架构中的位置
   1.3 与 Requirement / Specification / Measurement / Compliance / Decision 的边界
   1.4 v0.2 与 v0.1 的核心差异

2. 设计原则

3. 核心概念模型
   3.1 六元验证模型（v0.2 更新）
   3.2 核心关系链（v0.2 更新）

4. 类规范
   4.1 Verification（验证活动）
   4.2 VerificationMethod（验证方法）
   4.3 TestMethod（测试方法——引用外部）
   4.4 VerificationRule（验证规则）
   4.5 RangeVerificationRule（范围规则）
   4.6 ToleranceVerificationRule（公差规则）
   4.7 EnumerationVerificationRule（枚举规则）
   4.8 BooleanVerificationRule（布尔规则）
   4.9 ProbabilityVerificationRule（概率规则）
   4.10 LogicalVerificationRule（逻辑规则）
   4.11 StatisticalVerificationRule（统计规则）
   4.12 VerificationResult（验证结果）
   4.13 VerificationEvidence（验证证据）
   4.14 TestReport（测试报告）
   4.15 Certificate（证书）
   4.16 SamplingPlan（抽样计划）
   4.17 VerificationCondition（验证条件）

5. 对象属性（v0.2 更新）

6. 数据属性

7. 与 Requirement / Specification / Measurement / Compliance 的连接（v0.2 更新）
   7.1 完整的规范语义链路
   7.2 关系示例

8. 外部标准对齐

9. SHACL 验证约束（v0.2 更新）

10. 完整示例（v0.2 更新）

11. 与 Compliance Ontology 的接口

12. 核心类汇总

13. 冻结声明

14. 版本变更记录


## 1. 引言

### 1.1 目的

leleby Verification Ontology 是 leleby 语义基础设施中**验证执行层**的核心模块。它定义了针对单项要求、单项规格、单项事实进行可追溯的符合性验证的语义模型。

本规范回答以下核心问题：

- 验证什么目标？（`SemanticTarget`——特性/功能/接口/关系）
- 依据什么约束？（`Constraint`）
- 用什么方法验证？（`VerificationMethod`）
- 输入什么数据？（`MeasurementResult`）
- 执行什么规则？（`VerificationRule`）
- 得到什么结果？（`VerificationResult`）

**核心定位：** Verification Ontology 负责对**单项要求**进行可追溯的验证，产生**单项验证结果**（PASS/FAIL/INCONCLUSIVE）。它不负责最终的整体合格/不合格决策（该职责属于 Decision Ontology）。

### 1.2 在 leleby 架构中的位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Verification Ontology 在架构中的位置                    │
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Standard Ontology（标准体系）                                       ║ │
│  ║  定义：Standard → Edition → Clause → RequirementBinding              ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Requirement Ontology（需要什么）                                    ║ │
│  ║  定义：Authority + Scope + SemanticTarget + Condition + Constraint   ║ │
│  ║         + Obligation                                                 ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Specification Framework Ontology（如何描述）                        ║ │
│  ║  定义：产品/服务/能力的结构化规格表达                                ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Measurement Ontology（事实数据）                                    ║ │
│  ║  定义：ObservableEntity → MeasurementObservation → MeasurementResult ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    │  提供测量结果                         │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Verification Ontology（如何验证）—— 本模块                         ║ │
│  ║  定义：验证方法、验证规则、验证结果                                  ║ │
│  ║  输出：单项验证结果（VerificationResult）                            ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Compliance Ontology（符合性评估）                                   ║ │
│  ║  定义：单项验证结果的聚合、产品-标准符合性判断                       ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗ │
│  ║  Decision Ontology（如何决策）                                       ║ │
│  ║  定义：综合验证结果，形成最终决策和行动                              ║ │
│  ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 与 Requirement / Specification / Measurement / Compliance / Decision 的边界

| 维度 | Requirement | Specification | Measurement | Verification | Compliance | Decision |
|---|---|---|---|---|---|---|
| 核心问题 | 应该满足什么？ | 声明了什么？ | 测得什么？ | 是否被证明？ | 整体符合吗？ | 综合后做什么？ |
| 输出 | 约束 + 义务 | 属性值 | 测量结果 | 单项验证结果 | 符合性声明 | 最终决策 + 行动 |
| 示例 | “温度 ≥ -40℃” | “温度范围：-40~70℃” | “测得：-42℃” | “-42 ≥ -40 → PASS” | “产品符合 IEC 标准” | “98/100 通过 → 接收” |
| 职责归属 | Requirement | Specification | Measurement | **Verification** | Compliance | Decision |

**重要声明：** Verification Ontology 不负责：

- 抽样接收准则（AQL、Ac/Re）的综合判定
- 综合批判定（放行/返工/报废）
- 整体合格/不合格判断
- 产品是否符合标准的声明（属于 Compliance）
- 商业决策和行动映射

上述内容分别属于 Compliance Ontology 和 Decision Ontology。

### 1.4 v0.2 与 v0.1 的核心差异

| 问题 | v0.1 状态 | v0.2 修正 |
|---|---|---|
| **验证目标** | `VerificationTarget`（独立类） | **改为 `lbo-core:SemanticTarget`**，与 Requirement/Measurement/Constraint 统一 |
| **观测事实** | `Observation`（独立定义） | **引用 `lbo-meas:MeasurementResult`**，不再重复定义 |
| **符合性断言** | `ConformanceAssertion` 在 Verification 中定义 | **移除**，由 Compliance Ontology 负责 |
| **验证方法** | 在 Verification 中完整定义 | **改为引用外部 Method Ontology**，保持模块边界 |
| **验证上下文** | 未明确 | **新增 `underContext` → `lbo-core:EvaluationContext`** |
| **评估目标** | 间接 | **新增 `evaluatesTarget` → `SemanticTarget`** |


## 2. 设计原则

### 2.1 基于证据原则（Evidence-based）

> **验证必须基于可观测的事实数据，而非仅依赖声明或文档。** 验证的核心是对照测量结果与约束要求进行判断。

**错误：**
```
产品规格书 IP66 → 直接判定符合
```

**正确：**
```
产品规格书 IP66 + 测试报告（IP66通过） → 验证通过
```

### 2.2 针对语义目标原则（SemanticTarget-oriented）

> **验证针对的是特定的语义目标（`SemanticTarget`——特性、功能、接口、关系）及其约束（`Constraint`），而非笼统的对象。** 每个 Verification 实例对应一个 `(SemanticTarget + Constraint)` 组合。

### 2.3 单项验证原则（Single-item Focus）

> **每个 Verification 产生一个单项验证结果（Verification Result），描述“单一要求是否满足”。** 综合判断由 Compliance 和 Decision 负责。

### 2.4 验证与决策分离原则

> **Verification 只产生 PASS / FAIL / INCONCLUSIVE 等状态，不产生“接收 / 拒收 / 放行”等商业决策。** 决策层使用验证结果集进行综合判断。

### 2.5 跨模块引用原则（Cross-module Reference）

> **Verification Ontology 不重新定义其他模块已有概念。** 目标引用 `SemanticTarget`，事实数据引用 `MeasurementResult`，约束引用 `Constraint`，符合性声明由 Compliance Ontology 负责。

### 2.6 方法与结果可追溯原则

> **验证方法和验证结果必须可追溯，支持溯源、审核和复现。**


## 3. 核心概念模型

### 3.1 六元验证模型（v0.2 更新）

Verification Ontology 的核心结构由六个要素构成，其中目标、事实数据、约束均引用外部模块：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Verification 六元模型（v0.2）                            │
│                                                                             │
│  1. Verification Target（验证目标）                                        │
│     对什么语义目标进行验证？                                                │
│     来源：lbo-core:SemanticTarget（特性/功能/接口/关系）                   │
│                                                                             │
│  2. Constraint（约束依据）                                                 │
│     依据什么约束进行判断？                                                  │
│     来源：lcon:Constraint（RangeConstraint / ToleranceConstraint / ...）   │
│                                                                             │
│  3. Measurement Result（测量事实）                                         │
│     输入什么测量数据？                                                      │
│     来源：lbo-meas:MeasurementResult（测量值 + 不确定度 + 状态）           │
│                                                                             │
│  4. Verification Method（验证方法）                                        │
│     用什么方法验证？                                                        │
│     引用：lbo-method:Method（外部 Method Ontology）                        │
│                                                                             │
│  5. Verification Rule（验证规则）                                          │
│     用什么规则判断？                                                        │
│     定义：lver:VerificationRule（范围/枚举/公差/逻辑）                     │
│                                                                             │
│  6. Verification Result（验证结果）                                        │
│     得到什么结论？                                                          │
│     定义：lver:VerificationResult（PASS / FAIL / INCONCLUSIVE）           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心关系链（v0.2 更新）

```
Requirement（需求约束——来自 lreq）
    │
    │  provides SemanticTarget + Constraint
    ▼
Verification（验证活动）
    │
    ├── evaluatesTarget ──→ lbo-core:SemanticTarget（验证的目标）
    ├── evaluatesConstraint ──→ lcon:Constraint（依据的约束）
    ├── usesMeasurementResult ──→ lbo-meas:MeasurementResult（输入的事实数据）
    ├── usesMethod ──→ lbo-method:Method（验证方法）
    ├── usesRule ──→ lver:VerificationRule（判断规则）
    ├── underContext ──→ lbo-core:EvaluationContext（验证条件）
    └── produces ──→ lver:VerificationResult（验证结果）
```


## 4. 类规范

### 4.1 Verification（验证活动）

```turtle
lver:Verification
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Process ;
    rdfs:label "Verification" ;
    rdfs:comment "一次具体的验证活动，对某项要求进行事实证明，产生单项验证结果" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lver:verificationIdentifier` | lver:Verification | xsd:string | 验证编号 | 1 |
| `lver:verificationDate` | lver:Verification | xsd:dateTime | 验证日期 | 0..1 |
| `lver:performedBy` | lver:Verification | llb:Agent | 执行者 | 0..1 |
| `lver:verificationDescription` | lver:Verification | xsd:string | 描述 | 0..1 |

**关系（v0.2 更新）：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lver:evaluatesTarget` | lver:Verification | **`lbo-core:SemanticTarget`** | **验证的目标（v0.2 新增）** | 1 |
| `lver:evaluatesConstraint` | lver:Verification | **`lcon:Constraint`** | **依据的约束（v0.2 新增）** | 1 |
| `lver:usesMeasurementResult` | lver:Verification | **`lbo-meas:MeasurementResult`** | **使用的测量结果（v0.2 新增）** | 1 |
| `lver:usesMethod` | lver:Verification | `lbo-method:Method` | 使用的方法 | 0..1 |
| `lver:usesRule` | lver:Verification | `lver:VerificationRule` | 使用的验证规则 | 1 |
| `lver:underContext` | lver:Verification | **`lbo-core:EvaluationContext`** | **验证条件（v0.2 新增）** | 0..1 |
| `lver:producesResult` | lver:Verification | `lver:VerificationResult` | 产生的验证结果 | 1 |
| `lver:hasEvidence` | lver:Verification | `lver:VerificationEvidence` | 有证据支撑 | 0..* |
| `lver:usesSamplingPlan` | lver:Verification | `lver:SamplingPlan` | 使用抽样计划 | 0..1 |

### 4.2 VerificationMethod（验证方法）

```turtle
lver:VerificationMethod
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "VerificationMethod" ;
    rdfs:comment "验证方法的抽象基类。具体方法定义在 Method Ontology 中，本模块仅引用" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lver:methodIdentifier` | lver:VerificationMethod | xsd:string | 方法标识 |
| `lver:methodName` | lver:VerificationMethod | xsd:string | 方法名称 |
| `lver:methodDescription` | lver:VerificationMethod | xsd:string | 方法描述 |

**子类（作为外部 Method Ontology 的引用点）：**

| 子类 | 说明 | 示例 |
|---|---|---|
| `lver:TestMethod` | 测试方法 | IEC 60068-2-1 低温测试 |
| `lver:InspectionMethod` | 检验方法 | 视觉检查、尺寸测量 |
| `lver:AnalysisMethod` | 分析方法 | 光谱分析、化学分析 |
| `lver:SimulationMethod` | 模拟方法 | 有限元分析、仿真 |
| `lver:ReviewMethod` | 审核方法 | 文件审查、设计评审 |
| `lver:CalculationMethod` | 计算方法 | 强度计算、热计算 |

### 4.3 TestMethod（测试方法——引用外部）

```turtle
lver:TestMethod
    rdf:type owl:Class ;
    rdfs:subClassOf lver:VerificationMethod ;
    rdfs:label "TestMethod" ;
    rdfs:comment "具体的测试方法。完整定义在 Method Ontology 中，本模块仅标识引用" .
```

**属性（简化为引用标识）：**

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lver:standardReference` | lver:TestMethod | xsd:string | 依据标准编号 |
| `lver:procedureDescription` | lver:TestMethod | xsd:string | 过程描述（简要） |

> **v0.2 说明：** TestMethod 的完整定义（设备、条件、步骤、验收准则等）属于 Method Ontology。Verification Ontology 仅保留对方法的引用标识。

### 4.4 VerificationRule（验证规则）

```turtle
lver:VerificationRule
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "VerificationRule" ;
    rdfs:comment "用于判断测量值是否符合约束的规则。VerificationRule 是 Constraint 的可执行对应物" .
```

**核心属性：**

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lver:ruleIdentifier` | lver:VerificationRule | xsd:string | 规则标识 |
| `lver:ruleDescription` | lver:VerificationRule | xsd:string | 规则描述 |
| `lver:ruleExpression` | lver:VerificationRule | xsd:string | 规则表达式（如 SPARQL 或逻辑表达式） |
| `lver:mapsToConstraint` | lver:VerificationRule | `lcon:Constraint` | 对应的约束类型 |

**子类：**

| 子类 | 说明 | 适用约束类型 |
|---|---|---|
| `lver:RangeVerificationRule` | 范围包含规则 | RangeConstraint |
| `lver:ToleranceVerificationRule` | 公差判断规则 | ToleranceConstraint |
| `lver:EnumerationVerificationRule` | 枚举匹配规则 | EnumerationConstraint |
| `lver:BooleanVerificationRule` | 布尔判断规则 | BooleanConstraint |
| `lver:ProbabilityVerificationRule` | 概率判断规则 | ProbabilityConstraint |
| `lver:LogicalVerificationRule` | 逻辑组合规则 | LogicalConstraint |
| `lver:StatisticalVerificationRule` | 统计判断规则 | 适用批量数据 |

### 4.5 RangeVerificationRule（范围规则）

```turtle
lver:RangeVerificationRule
    rdf:type owl:Class ;
    rdfs:subClassOf lver:VerificationRule ;
    rdfs:label "RangeVerificationRule" ;
    rdfs:comment "范围包含规则：检查测量值是否在指定范围内" .
```

**规则逻辑：**

```
IF minValue ≤ measurementValue ≤ maxValue THEN PASS ELSE FAIL
```

### 4.6 ToleranceVerificationRule（公差规则）

```turtle
lver:ToleranceVerificationRule
    rdf:type owl:Class ;
    rdfs:subClassOf lver:VerificationRule ;
    rdfs:label "ToleranceVerificationRule" ;
    rdfs:comment "公差判断规则：检查测量值是否在标称值 ± 公差范围内" .
```

**规则逻辑：**

```
IF nominal - lowerTolerance ≤ measurementValue ≤ nominal + upperTolerance THEN PASS ELSE FAIL
```

### 4.7 EnumerationVerificationRule（枚举规则）

```turtle
lver:EnumerationVerificationRule
    rdf:type owl:Class ;
    rdfs:subClassOf lver:VerificationRule ;
    rdfs:label "EnumerationVerificationRule" ;
    rdfs:comment "枚举匹配规则：检查测量值是否在允许值列表中" .
```

**规则逻辑：**

```
IF measurementValue IN allowedValues THEN PASS ELSE FAIL
```

### 4.8 BooleanVerificationRule（布尔规则）

```turtle
lver:BooleanVerificationRule
    rdf:type owl:Class ;
    rdfs:subClassOf lver:VerificationRule ;
    rdfs:label "BooleanVerificationRule" ;
    rdfs:comment "布尔判断规则：检查布尔值是否等于期望值" .
```

### 4.9 ProbabilityVerificationRule（概率规则）

```turtle
lver:ProbabilityVerificationRule
    rdf:type owl:Class ;
    rdfs:subClassOf lver:VerificationRule ;
    rdfs:label "ProbabilityVerificationRule" ;
    rdfs:comment "概率判断规则：检查统计量是否满足概率约束" .
```

### 4.10 LogicalVerificationRule（逻辑规则）

```turtle
lver:LogicalVerificationRule
    rdf:type owl:Class ;
    rdfs:subClassOf lver:VerificationRule ;
    rdfs:label "LogicalVerificationRule" ;
    rdfs:comment "逻辑组合规则：组合多个子规则的判断结果" .
```

**子类：**

| 子类 | 说明 |
|---|---|
| `lver:AndVerificationRule` | AND 组合 |
| `lver:OrVerificationRule` | OR 组合 |
| `lver:NotVerificationRule` | NOT 组合 |

### 4.11 StatisticalVerificationRule（统计规则）

```turtle
lver:StatisticalVerificationRule
    rdf:type owl:Class ;
    rdfs:subClassOf lver:VerificationRule ;
    rdfs:label "StatisticalVerificationRule" ;
    rdfs:comment "统计判断规则：基于多组数据统计结果进行判断" .
```

### 4.12 VerificationResult（验证结果）

```turtle
lver:VerificationResult
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:Assessment ;
    rdfs:label "VerificationResult" ;
    rdfs:comment "单项验证活动的输出结果。它表示一次验证是否通过，不表示整体合规状态" .
```

**状态枚举：**

| 值 | 说明 |
|---|---|
| `lver:PASS` | 符合要求 |
| `lver:FAIL` | 不符合要求 |
| `lver:INCONCLUSIVE` | 无法确定（数据不足或方法失效） |
| `lver:NOT_APPLICABLE` | 不适用 |
| `lver:UNKNOWN` | 未知 |

> **v0.2 说明：** VerificationResult 是单项验证结果。整体符合性（如“产品符合标准”）属于 Compliance Ontology 的 `ConformanceAssertion`。

**属性：**

| 属性 | 域 | 值域 | 说明 | 基数 |
|---|---|---|---|---|
| `lver:resultStatus` | lver:VerificationResult | lver:VerificationStatus | 结果状态 | 1 |
| `lver:confidence` | lver:VerificationResult | xsd:double | 置信度 [0,1] | 0..1 |
| `lver:message` | lver:VerificationResult | xsd:string | 结果描述 | 0..1 |
| `lver:generatedByRule` | lver:VerificationResult | lver:VerificationRule | 由哪条规则生成 | 1 |
| `lver:basedOnMeasurement` | lver:VerificationResult | `lbo-meas:MeasurementResult` | 基于哪个测量结果 | 1 |

### 4.13 VerificationEvidence（验证证据）

```turtle
lver:VerificationEvidence
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Document ;
    rdfs:label "VerificationEvidence" ;
    rdfs:comment "验证所依据的证据文件或记录" .
```

**子类：**

| 子类 | 说明 |
|---|---|
| `lver:TestReport` | 测试报告 |
| `lver:Certificate` | 证书 |
| `lver:MeasurementRecord` | 测量记录 |
| `lver:InspectionRecord` | 检验记录 |
| `lver:SimulationResult` | 仿真结果 |
| `lver:ImageEvidence` | 图片证据 |

**关系：**

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lver:supportedBy` | lver:Verification | lver:VerificationEvidence | 验证有证据支撑 |
| `lver:evidenceIdentifier` | lver:VerificationEvidence | xsd:string | 证据标识 |
| `lver:evidenceURI` | lver:VerificationEvidence | xsd:anyURI | 证据链接 |

### 4.14 TestReport（测试报告）

```turtle
lver:TestReport
    rdf:type owl:Class ;
    rdfs:subClassOf lver:VerificationEvidence ;
    rdfs:label "TestReport" ;
    rdfs:comment "测试报告，包含测试结果、测试条件、测试人员等信息" .
```

### 4.15 Certificate（证书）

```turtle
lver:Certificate
    rdf:type owl:Class ;
    rdfs:subClassOf lver:VerificationEvidence ;
    rdfs:label "Certificate" ;
    rdfs:comment "认证/符合性证书" .
```

### 4.16 SamplingPlan（抽样计划）

```turtle
lver:SamplingPlan
    rdf:type owl:Class ;
    rdfs:subClassOf llb:Concept ;
    rdfs:label "SamplingPlan" ;
    rdfs:comment "验证的抽样计划，用于批量验证的样本设计" .
```

**属性：**

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lver:sampleSize` | lver:SamplingPlan | xsd:integer | 样本数量 |
| `lver:samplingMethod` | lver:SamplingPlan | xsd:string | 抽样方法（随机/分层/系统） |
| `lver:confidenceLevel` | lver:SamplingPlan | xsd:double | 置信水平 |
| `lver:acceptanceNumber` | lver:SamplingPlan | xsd:integer | 接受数（Ac） |
| `lver:rejectionNumber` | lver:SamplingPlan | xsd:integer | 拒收数（Re） |

**说明：** SamplingPlan 定义抽样方案，但最终的 Ac/Re 判断属于 Decision Ontology。Verification Ontology 仅记录抽样计划和样本观测结果。

### 4.17 VerificationCondition（验证条件）

```turtle
lver:VerificationCondition
    rdf:type owl:Class ;
    rdfs:subClassOf lbo-core:EvaluationContext ;
    rdfs:label "VerificationCondition" ;
    rdfs:comment "验证活动的条件上下文。继承自 Core Ontology 的 EvaluationContext" .
```


## 5. 对象属性（v0.2 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| **`lver:evaluatesTarget`** | lver:Verification | **`lbo-core:SemanticTarget`** | **验证的目标（v0.2 新增）** |
| **`lver:evaluatesConstraint`** | lver:Verification | **`lcon:Constraint`** | **依据的约束（v0.2 新增）** |
| **`lver:usesMeasurementResult`** | lver:Verification | **`lbo-meas:MeasurementResult`** | **使用的测量结果（v0.2 新增）** |
| `lver:usesMethod` | lver:Verification | `lbo-method:Method` | 使用的方法 |
| `lver:usesRule` | lver:Verification | lver:VerificationRule | 使用的验证规则 |
| `lver:underContext` | lver:Verification | **`lbo-core:EvaluationContext`** | **验证条件（v0.2 新增）** |
| `lver:producesResult` | lver:Verification | lver:VerificationResult | 产生的验证结果 |
| `lver:hasEvidence` | lver:Verification | lver:VerificationEvidence | 有证据支撑 |
| `lver:usesSamplingPlan` | lver:Verification | lver:SamplingPlan | 使用抽样计划 |
| `lver:mapsToConstraint` | lver:VerificationRule | `lcon:Constraint` | 对应的约束 |
| `lver:generatedByRule` | lver:VerificationResult | lver:VerificationRule | 由哪条规则生成 |
| `lver:basedOnMeasurement` | lver:VerificationResult | `lbo-meas:MeasurementResult` | 基于哪个测量结果 |
| `lver:supportedBy` | lver:Verification | lver:VerificationEvidence | 有证据支撑 |
| `lver:standardReference` | lver:TestMethod | xsd:string | 依据标准编号 |


## 6. 数据属性

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| `lver:verificationIdentifier` | lver:Verification | xsd:string | 验证编号 |
| `lver:verificationDate` | lver:Verification | xsd:dateTime | 验证日期 |
| `lver:verificationDescription` | lver:Verification | xsd:string | 描述 |
| `lver:methodIdentifier` | lver:VerificationMethod | xsd:string | 方法标识 |
| `lver:methodName` | lver:VerificationMethod | xsd:string | 方法名称 |
| `lver:methodDescription` | lver:VerificationMethod | xsd:string | 方法描述 |
| `lver:ruleIdentifier` | lver:VerificationRule | xsd:string | 规则标识 |
| `lver:ruleDescription` | lver:VerificationRule | xsd:string | 规则描述 |
| `lver:ruleExpression` | lver:VerificationRule | xsd:string | 规则表达式 |
| `lver:resultStatus` | lver:VerificationResult | lver:VerificationStatus | 结果状态 |
| `lver:confidence` | lver:VerificationResult | xsd:double | 置信度 |
| `lver:message` | lver:VerificationResult | xsd:string | 结果描述 |
| `lver:evidenceIdentifier` | lver:VerificationEvidence | xsd:string | 证据标识 |
| `lver:evidenceURI` | lver:VerificationEvidence | xsd:anyURI | 证据链接 |
| `lver:sampleSize` | lver:SamplingPlan | xsd:integer | 样本数量 |
| `lver:samplingMethod` | lver:SamplingPlan | xsd:string | 抽样方法 |
| `lver:acceptanceNumber` | lver:SamplingPlan | xsd:integer | 接受数 |
| `lver:rejectionNumber` | lver:SamplingPlan | xsd:integer | 拒收数 |


## 7. 与 Requirement / Specification / Measurement / Compliance 的连接（v0.2 更新）

### 7.1 完整的规范语义链路

```
Standard Ontology
    │
    │  Standard → Edition → Clause → RequirementBinding
    ▼
Requirement（需求约束——来自 lreq）
    │
    │  hasTargetElement → SemanticTarget
    │  hasConstraint → Constraint
    ▼
SemanticTarget + Constraint
    │
    │  被 Verification 引用
    ▼
Verification（验证活动）
    │
    │  evaluatesTarget → SemanticTarget
    │  evaluatesConstraint → Constraint
    │  usesMeasurementResult → MeasurementResult
    │  usesRule → VerificationRule
    │  producesResult → VerificationResult
    ▼
VerificationResult（单项结果）
    │
    │  PASS / FAIL / INCONCLUSIVE
    ▼
Compliance Ontology
    │
    │  聚合多项 VerificationResult
    │  产生 ConformanceAssertion
    ▼
Decision Ontology
    │
    │  综合判断
    │  产生最终决策和行动
```

### 7.2 关系示例（v0.2 更新）

```ttl
# 需求
lreq:REQ_Temp_001
    a lreq:Requirement ;
    lreq:hasRequirementIdentifier "REQ-TEMP-001" ;
    lreq:hasTargetElement lreq:Target_Temp ;
    lreq:hasConstraint lcon:Constraint_Temp_Neg40 .

# 目标（SemanticTarget）
lreq:Target_Temp
    a lreq:CharacteristicTarget ;
    lreq:targetCharacteristic lbo-core:OperatingTemperature .

# 约束（Constraint）
lcon:Constraint_Temp_Neg40
    a lcon:RangeConstraint ;
    lcon:minValue [ -40℃ ] .

# 测量结果（来自 Measurement Ontology）
lbo-meas:Meas_Temp_001
    a lbo-meas:MeasurementResult ;
    lbo-meas:hasValue [ -42℃ ] .

# 验证规则
lver:RangeRule_Temp_001
    a lver:RangeVerificationRule ;
    lver:ruleIdentifier "RULE-TEMP-001" ;
    lver:ruleDescription "Check temperature >= -40℃" ;
    lver:mapsToConstraint lcon:Constraint_Temp_Neg40 .

# 验证活动（v0.2：使用新的关系）
lver:Verification_Temp_001
    a lver:Verification ;
    lver:verificationIdentifier "VER-TEMP-001" ;
    lver:verificationDate "2026-07-28"^^xsd:date ;
    lver:evaluatesTarget lreq:Target_Temp ;
    lver:evaluatesConstraint lcon:Constraint_Temp_Neg40 ;
    lver:usesMeasurementResult lbo-meas:Meas_Temp_001 ;
    lver:usesMethod lver:Method_IEC60068 ;
    lver:usesRule lver:RangeRule_Temp_001 ;
    lver:underContext lver:Condition_Outdoor ;
    lver:producesResult [
        a lver:VerificationResult ;
        lver:resultStatus lver:PASS ;
        lver:confidence "0.95"^^xsd:double ;
        lver:generatedByRule lver:RangeRule_Temp_001 ;
        lver:basedOnMeasurement lbo-meas:Meas_Temp_001
    ] .
```


## 8. 外部标准对齐

| 外部体系 | 对齐方式 | 说明 |
|---|---|---|
| ISO/IEC 17025 | `skos:closeMatch` | 实验室能力通用要求 |
| ISO 9001 | `skos:relatedMatch` | 质量体系验证要求 |
| VIM（国际计量词汇） | `skos:closeMatch` | 计量术语对齐 |
| QUDT | `skos:closeMatch` | 量和单位 |
| SHACL | — | 用于规则表达 |
| IEC 标准 | `skos:relatedMatch` | 具体测试方法引用 |


## 9. SHACL 验证约束（v0.2 更新）

### 9.1 Verification 基础约束（v0.2 更新）

```turtle
lver:VerificationShape
    a sh:NodeShape ;
    sh:targetClass lver:Verification ;
    sh:property [
        sh:path lver:verificationIdentifier ;
        sh:minCount 1 ;
        sh:message "Verification must have an identifier" ;
    ] ;
    sh:property [
        sh:path lver:evaluatesTarget ;
        sh:minCount 1 ;
        sh:message "Verification must evaluate a SemanticTarget" ;
    ] ;
    sh:property [
        sh:path lver:evaluatesConstraint ;
        sh:minCount 1 ;
        sh:message "Verification must evaluate a Constraint" ;
    ] ;
    sh:property [
        sh:path lver:usesMeasurementResult ;
        sh:minCount 1 ;
        sh:message "Verification must use a MeasurementResult" ;
    ] ;
    sh:property [
        sh:path lver:usesRule ;
        sh:minCount 1 ;
        sh:message "Verification must use a VerificationRule" ;
    ] ;
    sh:property [
        sh:path lver:producesResult ;
        sh:minCount 1 ;
        sh:message "Verification must produce a result" ;
    ] .
```

### 9.2 VerificationResult 约束（v0.2 更新）

```turtle
lver:VerificationResultShape
    a sh:NodeShape ;
    sh:targetClass lver:VerificationResult ;
    sh:property [
        sh:path lver:resultStatus ;
        sh:minCount 1 ;
        sh:in (
            lver:PASS
            lver:FAIL
            lver:INCONCLUSIVE
            lver:NOT_APPLICABLE
            lver:UNKNOWN
        ) ;
        sh:message "Result status must be one of predefined values" ;
    ] ;
    sh:property [
        sh:path lver:generatedByRule ;
        sh:minCount 1 ;
        sh:message "VerificationResult must be generated by a rule" ;
    ] ;
    sh:property [
        sh:path lver:basedOnMeasurement ;
        sh:minCount 1 ;
        sh:message "VerificationResult must be based on a measurement" ;
    ] .
```

### 9.3 VerificationRule 约束

```turtle
lver:VerificationRuleShape
    a sh:NodeShape ;
    sh:targetClass lver:VerificationRule ;
    sh:property [
        sh:path lver:ruleIdentifier ;
        sh:minCount 1 ;
        sh:message "VerificationRule must have a rule identifier" ;
    ] ;
    sh:property [
        sh:path lver:mapsToConstraint ;
        sh:minCount 1 ;
        sh:message "VerificationRule must map to a Constraint" ;
    ] .
```


## 10. 完整示例（v0.2 更新）

### 10.1 示例一：温度验证（单项 PASS）

```ttl
# 需求：工作温度 ≥ -40℃
lreq:REQ_Temp_001
    a lreq:Requirement ;
    lreq:hasRequirementIdentifier "REQ-TEMP-001" ;
    lreq:hasTargetElement [
        a lreq:CharacteristicTarget ;
        lreq:targetCharacteristic lbo-core:OperatingTemperature
    ] ;
    lreq:hasConstraint [
        a lcon:RangeConstraint ;
        lcon:minValue [
            qudt:value "-40"^^xsd:double ;
            qudt:unit qudt:DEG_C
        ]
    ] .

# 测量结果（来自 Measurement Ontology）
lbo-meas:Meas_Temp_001
    a lbo-meas:MeasurementResult ;
    lbo-meas:hasValue [
        a lbo-meas:ScalarValue ;
        lbo-meas:scalarValue [
            a qudt:QuantityValue ;
            qudt:value "-42"^^xsd:double ;
            qudt:unit qudt:DEG_C
        ]
    ] .

# 验证规则
lver:RangeRule_Temp_001
    a lver:RangeVerificationRule ;
    lver:ruleIdentifier "RULE-TEMP-001" ;
    lver:ruleDescription "Check temperature >= -40℃" ;
    lver:mapsToConstraint lcon:Constraint_Temp_Neg40 .

# 验证活动
lver:Verification_Temp_001
    a lver:Verification ;
    lver:verificationIdentifier "VER-TEMP-001" ;
    lver:verificationDate "2026-07-28"^^xsd:date ;
    lver:evaluatesTarget lreq:Target_Temp ;
    lver:evaluatesConstraint lcon:Constraint_Temp_Neg40 ;
    lver:usesMeasurementResult lbo-meas:Meas_Temp_001 ;
    lver:usesMethod [
        a lver:TestMethod ;
        lver:methodName "Cold Test IEC 60068-2-1" ;
        lver:standardReference "IEC 60068-2-1"
    ] ;
    lver:usesRule lver:RangeRule_Temp_001 ;
    lver:producesResult [
        a lver:VerificationResult ;
        lver:resultStatus lver:PASS ;
        lver:confidence "0.95"^^xsd:double ;
        lver:message "Temperature -42℃ ≥ -40℃" ;
        lver:generatedByRule lver:RangeRule_Temp_001 ;
        lver:basedOnMeasurement lbo-meas:Meas_Temp_001
    ] .
```

### 10.2 示例二：尺寸公差验证（单项 FAIL）

```ttl
# 需求：直径 15±0.02mm
lreq:REQ_Dim_001
    a lreq:Requirement ;
    lreq:hasTargetElement [
        a lreq:CharacteristicTarget ;
        lreq:targetCharacteristic lbo-core:Diameter
    ] ;
    lreq:hasConstraint [
        a lcon:ToleranceConstraint ;
        lcon:nominalValue [ 15mm ] ;
        lcon:symmetricTolerance [ 0.02mm ]
    ] .

# 测量结果
lbo-meas:Meas_Dim_001
    a lbo-meas:MeasurementResult ;
    lbo-meas:hasValue [
        a lbo-meas:ScalarValue ;
        lbo-meas:scalarValue [
            qudt:value "14.96"^^xsd:double ;
            qudt:unit qudt:Millimetre
        ]
    ] .

# 验证规则
lver:ToleranceRule_Dim_001
    a lver:ToleranceVerificationRule ;
    lver:ruleIdentifier "RULE-DIM-001" ;
    lver:ruleDescription "Check 15±0.02mm" ;
    lver:mapsToConstraint lcon:Constraint_Dim_001 .

# 验证活动
lver:Verification_Dim_001
    a lver:Verification ;
    lver:verificationIdentifier "VER-DIM-001" ;
    lver:evaluatesTarget lreq:Target_Dim ;
    lver:evaluatesConstraint lcon:Constraint_Dim_001 ;
    lver:usesMeasurementResult lbo-meas:Meas_Dim_001 ;
    lver:usesRule lver:ToleranceRule_Dim_001 ;
    lver:producesResult [
        a lver:VerificationResult ;
        lver:resultStatus lver:FAIL ;
        lver:message "Measured 14.96mm outside tolerance 15.00±0.02mm" ;
        lver:generatedByRule lver:ToleranceRule_Dim_001 ;
        lver:basedOnMeasurement lbo-meas:Meas_Dim_001
    ] .
```


## 11. 与 Compliance Ontology 的接口

Verification Ontology 向 Compliance Ontology 提供的输入：

| 输入项 | 来源 | 说明 |
|---|---|---|
| 验证结果集 | `lver:VerificationResult` | 每个单项的 PASS/FAIL |
| 验证目标 | `lver:evaluatesTarget` | 验证的具体 SemanticTarget |
| 约束依据 | `lver:evaluatesConstraint` | 验证依据的 Constraint |
| 置信度 | `lver:confidence` | 每个结果的可信度 |

**接口关系（v0.2 更新）：**

```
lver:VerificationResult（单项验证结果）
    │
    │  provided to
    ▼
lcom:ComplianceAssessment（在 Compliance Ontology 中定义）
    │
    │  aggregates multiple VerificationResult
    ▼
lcom:ConformanceAssertion（产品符合标准）
```

> **v0.2 说明：** `ConformanceAssertion` 已从 Verification Ontology 移除，由 Compliance Ontology 负责。


## 12. 核心类汇总

### 12.1 Classes（v0.2 更新）

| 类名 | 父类 | 说明 |
|---|---|---|
| `lver:Verification` | `lbo-core:Process` | 验证活动 |
| `lver:VerificationMethod` | `llb:Concept` | 验证方法（抽象） |
| `lver:TestMethod` | `lver:VerificationMethod` | 测试方法（引用外部） |
| `lver:InspectionMethod` | `lver:VerificationMethod` | 检验方法 |
| `lver:AnalysisMethod` | `lver:VerificationMethod` | 分析方法 |
| `lver:SimulationMethod` | `lver:VerificationMethod` | 模拟方法 |
| `lver:ReviewMethod` | `lver:VerificationMethod` | 审核方法 |
| `lver:CalculationMethod` | `lver:VerificationMethod` | 计算方法 |
| `lver:VerificationRule` | `llb:Concept` | 验证规则（抽象） |
| `lver:RangeVerificationRule` | `lver:VerificationRule` | 范围规则 |
| `lver:ToleranceVerificationRule` | `lver:VerificationRule` | 公差规则 |
| `lver:EnumerationVerificationRule` | `lver:VerificationRule` | 枚举规则 |
| `lver:BooleanVerificationRule` | `lver:VerificationRule` | 布尔规则 |
| `lver:ProbabilityVerificationRule` | `lver:VerificationRule` | 概率规则 |
| `lver:LogicalVerificationRule` | `lver:VerificationRule` | 逻辑规则 |
| `lver:StatisticalVerificationRule` | `lver:VerificationRule` | 统计规则 |
| `lver:VerificationResult` | `lbo-core:Assessment` | 验证结果 |
| `lver:VerificationEvidence` | `llb:Document` | 证据（抽象） |
| `lver:TestReport` | `lver:VerificationEvidence` | 测试报告 |
| `lver:Certificate` | `lver:VerificationEvidence` | 证书 |
| `lver:MeasurementRecord` | `lver:VerificationEvidence` | 测量记录 |
| `lver:InspectionRecord` | `lver:VerificationEvidence` | 检验记录 |
| `lver:SimulationResult` | `lver:VerificationEvidence` | 仿真结果 |
| `lver:SamplingPlan` | `llb:Concept` | 抽样计划 |
| `lver:VerificationCondition` | `lbo-core:EvaluationContext` | 验证条件 |

### 12.2 Object Properties（v0.2 更新）

| 属性 | 域 | 值域 | 说明 |
|---|---|---|---|
| **`lver:evaluatesTarget`** | `lver:Verification` | **`lbo-core:SemanticTarget`** | **验证的目标（v0.2 新增）** |
| **`lver:evaluatesConstraint`** | `lver:Verification` | **`lcon:Constraint`** | **依据的约束（v0.2 新增）** |
| **`lver:usesMeasurementResult`** | `lver:Verification` | **`lbo-meas:MeasurementResult`** | **使用的测量结果（v0.2 新增）** |
| `lver:usesMethod` | `lver:Verification` | `lbo-method:Method` | 使用的方法 |
| `lver:usesRule` | `lver:Verification` | `lver:VerificationRule` | 使用的规则 |
| `lver:underContext` | `lver:Verification` | **`lbo-core:EvaluationContext`** | **验证条件（v0.2 新增）** |
| `lver:producesResult` | `lver:Verification` | `lver:VerificationResult` | 产生的结果 |
| `lver:hasEvidence` | `lver:Verification` | `lver:VerificationEvidence` | 有证据支撑 |
| `lver:usesSamplingPlan` | `lver:Verification` | `lver:SamplingPlan` | 使用抽样计划 |
| `lver:mapsToConstraint` | `lver:VerificationRule` | `lcon:Constraint` | 对应的约束 |
| `lver:generatedByRule` | `lver:VerificationResult` | `lver:VerificationRule` | 由规则生成 |
| `lver:basedOnMeasurement` | `lver:VerificationResult` | `lbo-meas:MeasurementResult` | 基于的测量 |
| `lver:supportedBy` | `lver:Verification` | `lver:VerificationEvidence` | 有证据支撑 |


## 13. 冻结声明

### 13.1 冻结范围

v0.2 确认后，以下内容进入**冻结状态**：

- ✅ 核心模型（Verification + VerificationResult + VerificationRule）
- ✅ **与 Core Ontology 的接口（evaluatesTarget → SemanticTarget）**
- ✅ **与 Constraint Ontology 的接口（evaluatesConstraint → Constraint）**
- ✅ **与 Measurement Ontology 的接口（usesMeasurementResult → MeasurementResult）**
- ✅ **与 EvaluationContext 的接口（underContext）**
- ✅ 验证规则类型体系（Range、Tolerance、Enumeration、Boolean、Probability、Logical、Statistical）
- ✅ 命名空间 `https://ontology.leleby.org/verification/`

### 13.2 冻结后允许

- ✅ 新增 VerificationRule 子类
- ✅ 新增 VerificationStatus 值
- ✅ 新增 VerificationMethod 子类
- ✅ 新增 Evidence 子类
- ✅ 新增推理规则

### 13.3 冻结后禁止

- ❌ **修改核心模型结构**（Verification/VerificationResult/VerificationRule）
- ❌ **修改与 Core / Constraint / Measurement 的接口**
- ❌ **将 ConformanceAssertion 放回 Verification Ontology**（属于 Compliance Ontology）
- ❌ **重新定义 Observation 或 Measurement 类**（必须引用 Measurement Ontology）
- ❌ **重新定义 SemanticTarget**（必须引用 Core Ontology）


## 14. 版本变更记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| **v0.1** | **2026-07-28** | **初始设计版**：定义 Verification 六元模型；核心类；明确与 Requirement/Specification/Decision 的边界；外部标准对齐；SHACL 验证；完整示例 |
| **v0.2** | **2026-08-04** | **语义验证对齐版**：1）删除 `VerificationTarget`，改为引用 `lbo-core:SemanticTarget`（新增 `evaluatesTarget`）；2）删除 `Observation`，改为引用 `lbo-meas:MeasurementResult`（新增 `usesMeasurementResult`）；3）移除 `ConformanceAssertion`（归属 Compliance Ontology）；4）新增 `evaluatesConstraint` → `lcon:Constraint`；5）新增 `underContext` → `lbo-core:EvaluationContext`；6）`TestMethod` 改为外部 Method Ontology 引用；7）更新 SHACL 验证约束；8）更新完整示例；9）冻结声明更新 |


*— leleby Verification Ontology Specification v0.2 — Semantic Verification Alignment Release —*