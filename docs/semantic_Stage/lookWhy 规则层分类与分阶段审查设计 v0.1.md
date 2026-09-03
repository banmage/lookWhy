# lookWhy 规则层分类与分阶段审查设计 v0.1

> 状态：设计草案（配套《lookWhy 知识图谱阶段规划与存储选型建议》）；2026-09-02 由用户提出"基础规则文档两分法"后起草。
> 核心命题：规则（含规则源文档与规则条目）从层面划分为 **形式要求（formal）** 与 **技术要求（technical）** 两大类，支撑"先形式审查、后技术要求审查"的分阶段合规审查与纠错闭环。
> 依据：rules/README.md、rules/base/GB_T_1.1-2020/{requirements,extraction-rules,audit}.yaml、rules/base/GB_T_20001.10-2014/*、rules/schemas/audit-rule-set.schema.json、docs/12 规则落实方法论、docs/semantic_Stage/lookWhy 知识图谱阶段规划与存储选型建议 v0.1。

---

## 1. 术语

| 术语 | 定义 |
|---|---|
| 规则源文档 | 被注册为审查依据的标准/规范文档（如 GB/T 1.1-2020、GB/T 20001.10-2014，未来含 PPM 能力单元标准） |
| 规则包 | rules/base/<ID>/ 目录，含 requirements.yaml / extraction-rules.yaml / audit.yaml / source.* 三件套 |
| 规则条目 | 规则包内的单条规则（GBT-* / P10-* / GEN-* / P10-GEN-* / P10-AUD-* / GEN-STRUCT-*） |
| 审查对象 | 被审查的文档（如企业标准草案、团体标准送审稿、待入库的标准知识资产） |
| 审查阶段 | 对审查对象顺序执行的审查关口：形式审查 → 技术要求审查 →（未来）产品/证据合规 |
| 纠错 | 对审查发现的违规项给出修复建议/自动修复并回归验证的闭环 |

---

## 2. 规则两分法（用户定义，v0.1 冻结）

### 2.1 类别定义

| 类别 | 主要覆盖 | 用途 | 典型规则源 |
|---|---|---|---|
| **形式要求（formal）** | 文件格式/版式（如 GB/T 1.1 的封面、目次、字号字体）、内容结构（要素、章条层次、编号、内部引用）、计量单位与量值表达 | **形式审查**：文档"写得对不对"（结构与表达合规），以结构/排版检查为主，机器可自动判定与部分自动修复 | GB_T_1.1-2020（起草规则）；GB_T_20001.4/5/6/10（各类标准编写规则）；GB_3100/3101/3102.*（量与单位）；GB_T_15835（数字用法）等 |
| **技术要求（technical）** | 技术指标类别（有哪些指标）、分类（产品/型式分类与命名）、产品构成（组成/结构单元）、技术指标范围（量值上下限/公差/条件） | **技术要求审查**：文档"技术内容是否完整、可验证、合标"（指标体系与量值审查），需结构化要求抽取与对标，多为人工/规则+AI 辅助判定 | 具体产品/技术要求类标准（如 GB_T_43726-2024、GB_T_23132-2024、T_ZZB_2224-2021）；企业自建 PPM 能力单元标准 |

### 2.2 初始子类划分（建议，待确认）

- formal 子类（沿用用户口径，可再扩展）：
  - `file-format` 文件格式/版式：封面、目次、字号字体、行距、边框线等（GB_T_1.1 第 10 章、附录 E/F）
  - `content-structure` 内容结构：要素与顺序（GB_T_1.1 表 3）、章条层次与编号、列项、注/示例/脚注、参考文献与索引结构
  - `units-measurement` 计量单位与量值表达：法定计量单位、单位符号、数字与量值写法（GB_3100/3101/3102、GB_T_15835）
- technical 子类（用户四类原样保留）：
  - `indicator-category` 技术指标类别：应给出哪些指标类别（性能/安全/环境/寿命…）及定义
  - `classification` 分类：产品分类、型式命名与代号规则
  - `product-composition` 产品构成：组成/结构/部件及接口
  - `indicator-range` 技术指标范围：指标量值、上下限、公差、适用条件

### 2.3 归类原则（边界 case 处理）

1. 判类看"规则约束的对象"：约束**文档表达**（怎么写）→ formal；约束**技术内容**（指标/分类/构成/量值是什么）→ technical。
2. 同一条规则若横跨两类（如"技术指标必须给出单位"）——约束对象是表达 → 归 formal（units-measurement）；"技术指标值必须在 X~Y 之间" → technical（indicator-range）。
3. GB_T_1.1-2020 与 GB_T_20001.x 属编写规则，整体注册为 formal；其中涉及技术内容撰写形态的章节（如 GB_T_20001.10 的"要求"章撰写、GB_T_20001.5 的特性值表述）是"技术内容的**形式**要求"，仍归 formal，但标记子类 `technical-content-form`（未来可细分），避免与 technical 类混淆——**technical 类只约束具体技术对象，不约束撰写形态**。
4. 语料/待审文档 ≠ 规则源：corpus/golden/ 与 out/mineru/ 下的大多数技术标准是**审查对象或知识资产**；只有当其被注册为某类审查依据时才进入 rules/（base 或 industries）成为规则源。规则包 = 注册动作的产物。

---

## 3. 现状规则制品映射（v0.1 初排，待你确认）

### 3.1 现有规则包与编号族的归类

| 规则制品 | 位置 | 建议类别 | 说明 |
|---|---|---|---|
| GBT-* 内容/结构/排版要求（GBT-E01…E14、GBT-H01…、GBT-C/X/B/…族） | rules/base/GB_T_1.1-2020/requirements.yaml | formal | 全部来自 GB/T 1.1-2020（起草规则） |
| P10-E*/R*/L* 产品标准专项要求 | rules/base/GB_T_20001.10-2014/requirements.yaml | formal | 产品标准"怎么写"的差异要求（5.2—5.8） |
| P10-GEN-*（要求章无编号小节标题、试验方法编号镜像、定量指标单位保留…） | rules/base/GB_T_20001.10-2014/extraction-rules.yaml | formal | 抽取/合成规则，约束表达层 |
| GEN-* 流水线通用规则（extract/merge/normalize/build/render/verify） | rules/base/GB_T_1.1-2020/extraction-rules.yaml | formal（工具类） | 属引擎工程规则，不参与业务审查；审查流程需显式排除 |
| GEN-STRUCT-*、P10-AUD-* 审核准则 | rules/base/*/audit.yaml | formal | audit 面向结构/元数据/编号/引用保留 |
| （未来）技术类规则源 requirements | rules/base/<技术标准ID>/ 或 rules/industries/<code>/ | technical | 待首个技术规则源注册验证 |

### 3.2 语料库标准初始分类（作规则源潜力盘点，非注册承诺）

| 角色 | 文档 |
|---|---|
| formal 规则源（建议注册） | GB_T_1.1-2020、GB_T_20001.4-2015、GB_T_20001.5-2017、GB_T_20001.6-2017、GB_T_20001.10-2014、GB_3100-1993/-2026、GB_3101-1993、GB_3102.1~.5-1993、GB_T_15835-2011、DB11_T_1000.1-2020（地方标准编写细则，若纳入规则体系） |
| technical 规则源（按需注册，先试点 1-2 份） | GB_T_43726-2024（洗衣机电动机，指标类别+范围齐全）、GB_T_23132-2024（含 2008/2024 双版本对标）、GB_T_755-2025、T_ZZB_2224-2021、企业 Q_* 标准（注册为企业私有规则源） |
| 暂作审查对象/知识资产 | 其余 corpus/out 语料 |

> 注：GB_3100/3101/3102 是"计量单位"规则的自然载体，正式注册后单位/量值表达检查不再靠零散正则补丁，而是按注册规则源驱动。

---

## 4. 规则分类的落点设计（文件级）

> 原则：**不推倒现有三件套**，采用"规则源注册表 + 规则条目可选标注"两层扩展；schema 变更向后兼容。

### 4.1 新增：规则源注册表 rules/base/registry.yaml（草案）

每份注册为规则源的标准一行；审查引擎按此表决定"哪个阶段、对什么对象、加载哪些规则集"。

```yaml
# rules/base/registry.yaml（草案字段）
schema-version: "0.1"
rule-sources:
  - id: GB_T_1.1-2020            # = 规则包目录名
    title: 标准化工作导则 第1部分：标准化文件的结构和起草规则
    review-category: formal      # formal | technical
    formal-sub: [content-structure, file-format]   # 见 2.2
    review-stage: form           # 主要服务阶段：form | technical
    applies-to:                  # 适用审查对象（缺省=全部标准化文件）
      document-types: [standard]
      doc-classes: [GB_T, GB_Z, JB_T, DB_T, T_, Q_]
    rule-sets: [requirements.yaml, extraction-rules.yaml, audit.yaml]
    load-policy: {ignore-gen: true}      # 审查时跳过 GEN-* 流水线工程规则
    status: approved
  - id: GB_T_43726-2024          # 未来 technical 示例（草案字段示意）
    title: 家用和类似用途电器电动机 …
    review-category: technical
    technical-sub: [indicator-category, indicator-range]
    review-stage: technical
    applies-to:
      document-types: [standard, enterprise-standard]
      products: [washing-machine-motor]
    rule-sets: [requirements.yaml, audit.yaml]
    status: candidate
```

字段约定（沿用 audit.yaml 的 kebab-case 风格）：`review-category` 必填；`formal-sub`/`technical-sub` 可多值；`review-stage` 决定默认挂载的审查阶段；`applies-to` 支持文档类型/代号族/产品类三档；`load-policy.ignore-gen` 供审查引擎剔除流水线工程规则。Schema 校验文件新建 `rules/schemas/rule-source-registry.schema.json`。
> **分层叠加扩展（2026-09-02）**：本 registry 将扩展为"包注册 rule-sources + 审核规则包 profiles"双区，支持 base/industry/tenant 分层叠加与领域产品 profile（如无刷永磁电机企标 = 基础包 + 企业模板 + 旋转电机/小功率域包），冲突裁决与快照语义见《lookWhy 规则包分层叠加与审核规则包模型 v0.1.md》。

### 4.2 规则条目级可选标注（细粒度覆盖）

- requirements.yaml / extraction-rules.yaml：`meta.review-category` 给出包默认值；单条规则如需偏离，加可选键 `review-category`/`review-stage`（无则继承包级）。
- audit.yaml：规则条目已含自由 `category`（structure/metadata/…），新增可选 `review-stage`（form|technical，默认 form）+ 受控 `category` 建议值枚举（与 2.2 子类对齐），扩展 audit-rule-set.schema.json 时保持 old 文件无新键也可加载（键 optional + additionalProperties 兼容）。
- 若实施中发现 requirements.yaml 内部混类严重（如某组同时含要素顺序与技术要求撰写），可先只做包级分类 + 少量条目覆盖，不强制逐条标注（MVP 成本控制）。

### 4.3 分类视图与图谱的衔接（预告，详见 KG 规划文档）

- 注册表本身可落图：RuleSource 节点带 reviewCategory/子类，边 `providesRuleSet`、`appliesTo(SubjectType)`。
- 审查结果落图：Finding/Issue 节点绑 `belongsToClause`（审查对象条款）+ `violates(Rule)`，纠错记录绑状态 —— 支持"某规则族在全部文档上的违规分布"类查询。

---

## 5. 分阶段合规审查与纠错闭环

### 5.1 审查流程（两阶段，顺序执行）

```
审查对象文档（SSIR 就绪）
   │
   ▼
┌──────────────────────────────────────────────┐
│ 阶段 A 形式审查（formal rule sets 全量加载） │
│   · 文件格式/版式、内容结构、计量单位表达     │
│   · 引擎：compliance.py 扩展（结构化规则）    │
│   · 输出：findings（ruleId/severity/条款锚点）│
└──────────────────────────────────────────────┘
   │ 未通过 → 纠错回路（5.2）
   ▼
┌──────────────────────────────────────────────┐
│ 阶段 B 技术要求审查（technical rule sets）   │
│   B1 技术要素完备性（规则可判）：             │
│       指标类别/分类/产品构成/指标范围是否齐备、│
│       有单位、可验证（P10-R*/P10-AUD-* 扩展） │
│   B2 指标范围对标（需语义提升，阶段3+）：      │
│       技术规则源指标库 vs 审查对象条款量值比对 │
│   · 输出：findings + 对标差异报告             │
└──────────────────────────────────────────────┘
   │
   ▼
通过/有条件通过（记录结论与证据锚点）
```

- 阶段 A 不通过可阻断进入阶段 B（形式关）。
- 阶段 B 依赖：审查对象 SSIR + （B1）规则集的要素/单位/可验证性要求 + （B2）技术规则源的结构化要求库（lreq 六元：目标对象/特性/条件/约束/验证，对齐 Normative Semantic Package v0.3 的 SemanticTarget）。

### 5.2 纠错回路（问题→规则→执行→验证，沿 docs/12 §1.3 方法论）

```
findings（含 ruleId、severity、targetElement、message、修复建议）
   │
   ├─ 自动修复型（formal 结构类，可机器改）：建议 patch → 重跑 → 回归比对 findings
   ├─ 人工确认型（formal 排版/表述类、technical 完备性类）：给出建议 diff → 人工采纳/驳回
   └─ 对标判定型（technical B2）：输出差异报告 → 标准化工程师裁定（改文档 or 豁免登记）
       每类都记录：判定人、时间、依据、证据锚点（审计可追溯）
```

纠错产物：
- 修复/改稿建议以 diff 形式落在 canonical/SSIR 层（不直接改源 PDF），回归验证复用 roundtrip 工具链；
- 豁免/偏差登记进规则层（新 GEN-*/审计条目或偏差台账），防止同类问题重复人工判定 —— 与 docs/12 的"通用性确认 → GEN-*"机制同构。

### 5.3 状态机（审查对象生命周期）

`submitted → form-check → form-fixing(可循环) → form-pass → tech-check → tech-fixing(可循环) → approved / conditional-approve / rejected`
（未来叠加产品/证据合规阶段时在 tech 后扩展，不影响前两段。）

---

## 6. 与主路线图的衔接（Track R）

在主规划（KG 阶段规划 v0.1）的阶段之外并行一条 **Track R（规则层）**，节奏可独立：

| 步骤 | 内容 | 前置 | 验收 |
|---|---|---|---|
| R0（0.5-1 周） | registry.yaml 草案落地 + schema；现有 formal 规则源注册（GB_T_1.1-2020、GB_T_20001.10-2014）；语料分类盘点确认 | 本文 2.2/4.1 字段评审 | registry 通过 schema 校验；引擎可按 stage 过滤规则集 |
| R1（1-2 周） | 形式审查阶段引擎：compliance 按 registry 的 review-stage=form 加载执行；产出分阶段 findings 报告 | R0 | 对 GB_T_43726 等 3 份语料出形式审查报告；与既有 parse-report compliance 结果一致 |
| R2（2-3 周） | B1 技术要素完备性规则试点：以 GB_T_20001.10 P10-* 为主 + 首个 technical 规则源（建议 GB_T_43726-2024 指标类别/范围骨架）做 B1 检查 | R1 + 首个 technical 注册 | 对"洗衣机电动机企标草案"类审查对象能输出指标类别缺项/范围无单位类 findings |
| R3（阶段 3+） | B2 指标范围对标 + 语义提升（lreq 抽取）联调；纠错回路自动化 | KG 主规划阶段 3 | 对标差异报告含证据锚点；豁免登记可用 |

Track R 与 KG 主线共享：SSIR/条款锚点、compliance 引擎、audit schema、图谱 Finding 节点（主线阶段 2 后接入）。

---

## 7. 立即执行建议（本周）

1. 评审并确认 2.2 子类划分与 3.1/3.2 初始归类（尤其：GB_3100 系列是否作为 formal 规则源注册；首个 technical 规则源选 GB_T_43726-2024 还是 PPM 自建标准）。
2. 冻结 registry.yaml 字段草案（4.1）与 schema。
3. 实现 R0：registry + 按 stage 过滤的 compliance 加载器（小改动，纯增量）。

---

## 8. 未决问题（需决策）

1. 技术要求审查的两个层次是否都做：B1 完备性（规则可判，先做）与 B2 量值对标（需语义提升，后做）？优先级如何？
2. 首批 technical 规则源选哪些：公开技术标准（GB_T_43726-2024 / GB_T_23132-2024）还是企业自建（Q_* 企标 / PPM 能力单元）？注册后其要求库由谁维护（人工结构化 or AI 抽取+审核）？
3. 纠错自动修复边界：formal 结构类自动修；formal 排版/表述与技术类是否全部人工确认后落地？
4. 计量单位规则的载体：将 GB_3100/3101/3102（.1993 旧版与 2026 新版并存）都注册为 formal 规则源，单位检查按"目标文档发布年代"选版，是否可行？
5. 语料里大量技术标准默认角色是"审查对象/知识资产"而非规则源 —— 此默认是否成立（避免 rules/ 膨胀为 corpus 复制）？

---

## 附：关键引用

- rules/README.md（规则包结构与生命周期）
- rules/base/GB_T_1.1-2020/{requirements.yaml, extraction-rules.yaml, audit.yaml}
- rules/base/GB_T_20001.10-2014/{requirements,extraction-rules,audit}.yaml（P10-* 族）
- rules/schemas/audit-rule-set.schema.json
- docs/12_leleby 规则落实方法论与通用问题知识库 v0.1.md（§1 元规则）
- docs/semantic_Stage/lookWhy 知识图谱阶段规划与存储选型建议 v0.1.md（KG 主线）
- docs/semantic_Stage/lookWhy_strategy_and_requirement_v1.1.md（§6.5 合规追溯、§8.3 质量治理）
- docs/semantic_Stage/lookWhy 规则包分层叠加与审核规则包模型 v0.1.md（分层轴扩展：profile/裁决/快照）
