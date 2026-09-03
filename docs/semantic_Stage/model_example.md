# leleby Standard Ontology Model — 经典核心版 v1.2-EXT

## 1. 核心设计原则
- **标准是知识体系，不是文件**：区分 `Standard`（体系）与 `StandardEdition`（版本）。
- **条款与要求解耦**：`StandardClause` 仅负责结构，`RequirementBinding` 负责将条款与 `lbo-req:Requirement` 绑定。
- **约束独立表达**：要求通过 `Constraint` 结构化（不依赖自然语言）。
- **验证闭环**：从约束到测量规格，再到验证结果，形成完整合规链路。
- **作用于类型**：标准作用于 `ProductType` / `ProcessType`，而非具体实例。

---

## 2. 命名空间（Namespace）

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix llb: <https://ontology.leleby.org/foundation/> .
@prefix lbo-core: <https://ontology.leleby.org/core/> .
@prefix lbo-req: <https://ontology.leleby.org/requirement/> .
@prefix lbo-spec: <https://ontology.leleby.org/specification/> .
@prefix lstd: <https://ontology.leleby.org/standard/> .
```

---

## 3. 核心类模型（Class Model）

### 3.1 标准体系层（完全遵循 v1.2）

| 类（Class） | 描述 | 关键属性 |
| :--- | :--- | :--- |
| **`lstd:Standard`** | 标准体系（如 IEC 60034） | `standardId`, `standardTitle` |
| **`lstd:StandardFamily`** | 标准族（如 IEC 60000 系列） | `familyId`, `familyName` |
| **`lstd:StandardEdition`** | 具体版本（如 2025 版） | `edition`, `effectiveDate`, `status` (Published/Superseded) |
| **`lstd:StandardOrganization`** | 发布机构（如 IEC, GB） | 继承 `lbo-core:Organization` |
| **`lstd:StandardClause`** | 条款/章节 | `clauseNumber`, `clauseTitle`, `clauseText` |
| **`lstd:RequirementBinding`** | **条款与要求的桥梁（核心创新）** | `referencesRequirement` (指向 lbo-req), `hasObligationLevel` (来自 Core), `derivedFromClause` |

### 3.2 标准关系层（完全遵循 v1.2）

| 类（Class） | 描述 |
| :--- | :--- |
| **`lstd:AdoptionRelationship`** | 采纳关系（等同/修改采用） |
| **`lstd:EquivalenceRelationship`** | 等效关系 |
| **`lstd:DeviationRelationship`** | 偏差关系 |
| **`lstd:ReplacementRelationship`** | 替代关系（跨体系） |

### 3.3 **补全层：要求语义与约束层**（连接 `lbo-req`）

| 类（Class） | 描述 | 关键属性 |
| :--- | :--- | :--- |
| **`lbo-req:Requirement`** | 要求定义（引用自 Requirement Ontology） | — |
| **`lstd:Constraint`** | **结构化约束（机器可读）** | `constrainsCharacteristic`, `hasOperator`, `hasValueSpecification` |
| **`lstd:Characteristic`** | **可测量的技术特性（替代容易混淆的 Property）** | 如：Noise, Efficiency, Torque |

### 3.4 **补全层：测量与验证层**（实例评估闭环）

| 类（Class） | 描述 | 关键属性 |
| :--- | :--- | :--- |
| **`lstd:MeasurementSpec`** | 测量规格（如何测） | `hasProcedure`, `usesDevice`, `hasCondition` |
| **`lstd:MeasurementResult`** | 实测结果 | `hasNumericValue`, `hasUnit` |
| **`lstd:Verification`** | 验证动作（比较结果与约束） | `verifiesConstraint`, `hasMeasurementResult` |
| **`lstd:VerificationOutcome`** | 验证结论 | `PASS` / `FAIL` |

### 3.5 **补全层：适用范围层**

| 类（Class） | 描述 | 关键属性 |
| :--- | :--- | :--- |
| **`lstd:StandardScope`** | 标准适用范围 | `scopeText`, `appliesToProductType`, `appliesToProcessType` |

---

## 4. 核心对象属性（Object Properties）

### 4.1 结构与组成（v1.2）
- `lstd:hasEdition` — Standard → Edition
- `lstd:containsClause` — Edition → Clause
- `lstd:hasParentClause` / `lstd:hasChildClause` — Clause 层级
- `lstd:definesBinding` — Clause → RequirementBinding

### 4.2 绑定与外部引用（v1.2）
- `lstd:referencesRequirement` — Binding → `lbo-req:Requirement`
- `lstd:hasObligationLevel` — Binding → `lbo-core:ObligationLevel` (Mandatory/Recommended/Optional)
- `lstd:derivedFromClause` — Binding → Clause

### 4.3 标准关系（v1.2）
- `lstd:hasRelationship` — Standard → (Adoption/Equivalence/Deviation/Replacement)
- `lstd:supersedes` / `lstd:supersededBy` — Edition → Edition

### 4.4 **约束与测量链路（补全）**
- `lstd:hasConstraint` — Requirement → Constraint
- `lstd:constrainsCharacteristic` — Constraint → Characteristic
- `lstd:hasOperator` — Constraint → Operator (<=, >=, ==, Range, Enum)
- `lstd:hasValueSpecification` — Constraint → (xsd:decimal / xsd:string / Range / List)
- `lstd:requiresMeasurement` — Constraint → MeasurementSpec
- `lstd:hasVerification` — Constraint → Verification (反向：Verification → verifiesConstraint)

### 4.5 **适用范围（补全）**
- `lstd:hasScope` — Standard → StandardScope
- `lstd:appliesToProductType` — Scope → `lbo-core:ProductType` (非具体实例)

---

## 5. 完整端到端实例（IEC 60034-1 电机噪声标准）

```turtle
### 1. 标准体系与版本
lstd:IEC_60034_1
    a lstd:Standard ;
    lstd:standardId "IEC 60034-1" ;
    lstd:standardTitle "Rotating electrical machines - Rating and performance" ;
    lstd:issuedBy lstd:IEC .

lstd:IEC_60034_1_2025
    a lstd:StandardEdition ;
    lstd:edition "2025" ;
    lstd:effectiveDate "2026-02-01"^^xsd:date ;
    lstd:status lstd:Published ;
    lstd:containsClause lstd:Clause_8_4 .

### 2. 条款（原文保留）
lstd:Clause_8_4
    a lstd:StandardClause ;
    lstd:clauseNumber "8.4" ;
    lstd:clauseTitle "Noise limits" ;
    lstd:clauseText "The A-weighted sound power level shall not exceed 40 dB(A)." .

### 3. 要求绑定（连接语义要求）
lstd:Binding_Noise_40dB
    a lstd:RequirementBinding ;
    lstd:referencesRequirement lbo-req:REQ_Noise_Limit ;  # 引用已有要求
    lstd:hasObligationLevel lbo-core:Mandatory ;
    lstd:derivedFromClause lstd:Clause_8_4 .

lstd:Clause_8_4 lstd:definesBinding lstd:Binding_Noise_40dB .

### 4. 结构化约束（机器可读补全）
lbo-req:REQ_Noise_Limit
    a lbo-req:Requirement ;
    lstd:hasConstraint lstd:Constraint_Noise_40dB .

lstd:Constraint_Noise_40dB
    a lstd:Constraint ;
    lstd:constrainsCharacteristic lstd:Char_AcousticNoise ;
    lstd:hasOperator lstd:Operator_LE ;          # <=
    lstd:hasValueSpecification "40.0"^^xsd:decimal ;
    lstd:hasUnit "dB(A)" ;
    lstd:requiresMeasurement lstd:MeasSpec_Noise .

lstd:Char_AcousticNoise
    a lstd:Characteristic ;
    rdfs:label "A-weighted sound power level" .

### 5. 测量规格
lstd:MeasSpec_Noise
    a lstd:MeasurementSpec ;
    lstd:hasProcedure "Microphone placed at 1m distance, free-field conditions" ;
    lstd:usesDevice lstd:Device_SoundLevelMeter ;
    lstd:hasCondition lstd:Env_Anechoic .

### 6. 标准适用范围（作用于产品类型）
lstd:Scope_IEC_60034
    a lstd:StandardScope ;
    lstd:scopeText "适用于旋转电机" ;
    lstd:appliesToProductType lbo-core:MotorProductType .  # 非实例

lstd:IEC_60034_1 lstd:hasScope lstd:Scope_IEC_60034 .
```

---

## 6. 验证闭环（产品合规评估实例）

当一个具体电机 `Motor_001` 被测试时：

```turtle
### 测试结果
lstd:Result_Noise_38dB
    a lstd:MeasurementResult ;
    lstd:hasNumericValue "38.0"^^xsd:decimal ;
    lstd:hasUnit "dB(A)" .

### 验证
lstd:Verification_Noise_001
    a lstd:Verification ;
    lstd:verifiesConstraint lstd:Constraint_Noise_40dB ;
    lstd:hasMeasurementResult lstd:Result_Noise_38dB ;
    lstd:hasOutcome lstd:Outcome_Pass .

lstd:Outcome_Pass
    a lstd:VerificationOutcome ;
    rdfs:label "PASS" .
```

---

## 7. 模型总结评价（对照 V1.2 及评审意见）

| 维度 | 本模型实现情况 | 依据 |
| :--- | :--- | :--- |
| **标准身份与版本** | ✅ 完全保留 v1.2 设计 | `Standard` + `StandardEdition` |
| **条款结构与层级** | ✅ 完全保留 v1.2 设计 | `StandardClause` 及其父子关系 |
| **要求绑定解耦** | ✅ **最大亮点**，完全保留 | `RequirementBinding` 连接 Clause 与 `lbo-req:Requirement` |
| **强制程度** | ✅ 统一引用 Core | `lbo-core:ObligationLevel` |
| **标准间关系** | ✅ 完全保留 v1.2 设计 | 采纳/等效/偏差/替代 |
| **结构化约束** | ✅ **补全** | 新增 `Constraint`, `Characteristic`, `ValueSpecification` |
| **测量与验证闭环** | ✅ **补全** | 新增 `MeasurementSpec`, `Verification`, `Outcome` |
| **适用范围** | ✅ **修正并补全** | 作用于 `ProductType`，避免实例爆炸 |
| **PDF 解析友好** | ✅ 保留 `clauseText` 原文 | 支持原文与语义双轨并存 |

---

## 8. 最终架构定位

这个模型本质上是 **v1.2 标准体系层** 与 **实例合规评估层** 的完美缝合：

```
Standard Ontology v1.2 (标准体系层)
        │
        ├── Standard → Edition → Clause → RequirementBinding
        │
        └── StandardRelationship (采纳/等效...)
                    │
                    ▼
本文补全层 (语义约束与合规验证层)
        │
        ├── Requirement → Constraint (Characteristic + Operator + Value)
        │
        ├── MeasurementSpec (Procedure + Device + Condition)
        │
        └── Verification (Result → Outcome)
                    │
                    ▼
             ProductType 评估 (合规判定)
```

这个模型既**严格尊重了已冻结的 v1.2 规范**，又具备了**驱动 AI 合规验证引擎的全部可计算语义**，可直接作为 leleby 标准语义包的蓝图。