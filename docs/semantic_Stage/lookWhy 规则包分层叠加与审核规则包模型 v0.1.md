# lookWhy 规则包分层叠加与审核规则包模型 v0.1

> 状态：设计草案（2026-09-02，用户提出"领域产品审核规则包继承叠加"构想后起草）。
> 结论先行：**构想合理，予以采纳**。它与既有规划一致（rules/README 已计划 base + industry + tenant profile 三层叠加；docs/12 规则落实方法论），也镜像现实世界的合规继承（企标采标国标 → 继承其规则；领域技术标准 → 决定产品指标体系）。但要工程化，必须钉死四个语义：**① 每层可溯源到已批准文件；② 层间冲突裁决策略（含不可放松的国家底线）；③ 适用性过滤（不加载无关数据）；④ 审查运行的可复现快照（当时用了哪些规则）**。本文把它们落成数据模型与流程。
> 配套：本文是《lookWhy 规则层分类与分阶段审查设计 v0.1》的**分层轴扩展**（分类 = 形式/技术纵轴；分层 = 通用→具体横轴；两者正交）。审查主流程见《lookWhy 知识图谱阶段规划与存储选型建议 v0.1》。

---

## 1. 术语与模型总览

| 术语 | 定义 |
|---|---|
| 规则包（rule package） | 由**一份已批准文件**派生的一组规则制品，目录 rules/base/<ID>/ 或 rules/industries/<code>/、rules/tenants/<tid>/；内含 requirements.yaml / extraction-rules.yaml / audit.yaml / source.*（溯源三件套） |
| 层（layer） | 叠加序中的一个规则包实例（包 ID + 版本钉 pin） |
| 审核规则包（audit profile） | **面向某领域/产品/文件类型的组合规则声明**：按序引用若干层 + 声明审查对象范围 + 冲突裁决策略。profile 本身也是版本化、可审批的"规则制品"（但它不直接派生自单一文件，而是对已批准包的选择/钉版/加企业专属层） |
| 有效规则集（effective rule set） | 引擎按 profile + 审查对象元数据材料化（materialize）后的最终规则集合，每条规则携带 `layerPath`（来自哪层的哪条） |
| 审查运行快照（review snapshot） | 一次审查实际生效的 profile 版本 + 各层钉版 + 有效规则集哈希；findings 全部挂在该快照下 |

```
无刷永磁电机企标（审查对象）
        │  按 subject 元数据命中 profile
        ▼
┌─ 审核规则包 prof.brushless-pm-ent（叠加序：通用→具体）───────────┐
│ L1 base/GB_T_1.1-2020         形式·起草规则（国家底线）        │
│ L2 base/GB_3100-2026(待建)    形式·量/单位（国家底线）         │
│ L3 base/GB_T_1.1-2020/audit   形式·通用逻辑(GEN-STRUCT；不含流水线GEN-*) │
│ L4 ent/<企业>/标准模板v3       形式·企业标准模板规则             │
│ L5 industry/motor/旋转电机    技术·指标类别/范围(源自GB_T_755类) │
│ L6 industry/motor/小功率电动机 技术·小功率专项(按subject命中才载) │
└──────────────────────────────────────────────┬──────────────┘
                                               ▼
                      材料化 → 有效规则集（逐条带 layerPath）
                               │
     形式审查阶段只载 L1-L4（formal）｜技术要求审查阶段载 L4-L6（technical）
```

---

## 2. 分层模型

### 2.1 层类别（规则包存放位置对齐 rules/README 与 docs/11）

| 层类别 | 目录 | 内容 | 示例 |
|---|---|---|---|
| base（全局基础） | rules/base/<ID>/ | 法定起草/表达规则与通用逻辑；所有 profile 默认底座的候选 | GB_T_1.1-2020、GB_3100-2026、GB_T_20001.10-2014、（建议）通用逻辑独立包 generic-audit |
| industry（行业/专业域） | rules/industries/<code>/approved/ | 某技术域或产品类通用要求（由相应标准提升注册） | motor/旋转电机（GB_T_755-2025 类）、motor/小功率电动机、（未来）lighting/… |
| tenant（企业） | rules/tenants/<tid>/（企业私域） | 企业自身模板与产品专属要求；密级受控（lookWhy §8.2） | 企业标准模板、无刷永磁电机企标自身（注册后） |
| profile（审核规则包） | rules/profiles/ | 组合声明，非新规则源 | prof.brushless-pm-ent |

- **关键不变量**：L1-L5 每一层的内容规则都**派生自已批准文件**（包内 source.csm.md/source.ssir.json + conversion-report 即证据）；profile 只做"选择+钉版+声明范围与裁决"，不夹带无出处的新规则。企业若有专属规则，必须先落为企业已批准文件的规则包（tenant 层），再被 profile 引用。

### 2.2 叠加语义

- 顺序即优先级倾向：**后叠加层（更具体）默认优先，但受裁决策略约束**（见 §3）——不是简单"具体层赢"。
- 同一审查对象命中多个 profile 时：取**最具体且已批准**的 profile（如"小功率电动机企标 profile"优于"旋转电机企标 profile"），再按需回退叠加通用 profile；profile 之间也可显式 `extends`。
- 材料化输出：有效规则集 = 各层规则按 `layerPath` 合并；规则 ID 全局唯一稳定（如 `GBT-E03`、`P10-R02`、`MOT-R-012`、`TPL-FMT-004`），允许同 ID 在多层出现（下层是"被覆盖/被加严"对象），引擎只输出裁决后版本并在快照中记录覆盖链。

---

## 3. 冲突裁决（必须显式化，否则叠加不可审计）

### 3.1 冲突类型与默认策略（v0.1 更新：技术条款按强制/推荐分级）

**裁决前置（2026-09-02 决策）**：技术要求类条款先分 **强制性要求（mandatory，标准用"应"）** 与 **推荐性要求（recommended，标准用"宜"）** 两级；只有**强制性要求的放宽**需要偏差登记，推荐性放宽/未覆盖只记**备注/提示**。

| 冲突类型 | 示例 | 默认策略 | 依据 |
|---|---|---|---|
| 国家底线（legal floor） | 企标模板要求文件不带封面 vs GB/T 1.1 要求封面必备 | **不可覆盖**；profile 把相关包声明进 `legal-floor`，engine 拒绝任何层放松 | 法定强制性、GB/T 1.1 等编写规则底线 |
| 强制条款·放宽（mandatory relax） | 5171.1"电压偏差±5%时应能连续运行"，企标改为 ±10% | **需偏差登记**（register-required）：登记裁定人/依据/证据锚点/有效期限，随 profile 版本携带 | 强制性要求不可静默放松 |
| 强制条款·加严/一致（mandatory tighten/equal） | 企标要求 ≤40dB（域包 ≤45dB）或一致 | **通过**，无需登记 | 就高不就低 |
| 强制条款·未覆盖（mandatory gap） | 域包要求某强制指标，企标无对应条款 | **提示/警告**：建议企标声明覆盖或走偏差登记 | 覆盖完整性 |
| 推荐条款·放宽/未覆盖（recommended relax/gap） | 5171.1"宜提供三效率点数据"，企标未提供 | **备注/提示即可**，不要求登记 | 推荐性要求可选择性执行 |
| 形态选择（format choice） | 企业模板规定封面机构行排版细节 | **具体层可替换**（企业模板 > 通用细节），需类型匹配（同属 file-format 子类） | 企业模板是已批准文件，对其文件形态有自决权 |
| 同层矛盾 | 同一域包内两条规则冲突 | 数据错误：材料化时报错，包作者修复 | 规则质量治理 |

### 3.2 裁决所需规则元数据（registry/包级扩展）

每条有效规则需携带（继承自包 meta，可条目级覆盖）：

```yaml
# 规则条目扩展草案（叠加模型所需字段）
conflict-class: legal-floor | tighten | format-choice | data-error   # 默认按包 meta
review-category: formal | technical          # 分类文档定义（纵轴）
review-stage: form | technical               # 阶段门控
obligation: mandatory | recommended          # 技术条款：强制(应)/推荐(宜)；form 类多为 mandatory
authority-level: national | industry | enterprise | template   # 溯源层级（裁决参考）
source: "7.3.1"                              # 包内标准章节（已存在）
source-file: rules/base/GB_T_1.1-2020/source.csm.md   # 溯源到已批准文件
```

偏离（deviation）登记：技术类"放宽"与企业模板替换国家底线的例外，一律走**偏差台账**（同分类文档 §5.2 的豁免登记），记录裁定人/依据/证据锚点/有效期限，纳入 profile 版本；下一次审查自动携带已批准的 deviations，不重复人工判定。

---

## 4. 审核规则包（profile）声明示例 —— 无刷永磁电机企业标准

```yaml
# rules/profiles/brushless-pm-ent.yaml（草案）
profile:
  id: prof.brushless-pm-ent-review
  version: "1.1.0"
  status: approved                 # draft → candidate → approved（审批流，同 rules 生命周期）
  title: 无刷永磁电机企业标准 编制与审查规则包
  subject:                         # 适用性过滤的声明（不加载无关数据的依据）
    document-types: [enterprise-standard, product-standard]
    products: [brushless-pm-motor, small-power-motor]
    ics: [29.160.30]
    doc-classes: [Q_, T_]          # 企标/团标代号族
  layers:                          # 通用 → 具体
    - {package: base/GB_T_1.1-2020,            role: formal-floor}
    - {package: base/GB_3100-2026,             role: formal-floor, note: 单位检查;1993版按目标文档年代切换}
    - {package: base/GB_T_1.1-2020#audit,      role: formal-generic, load-policy: {ignore-gen: true}}
    - {package: tenants/<tid>/std-template-v3, role: formal-template}      # 企业自身标准模板规则
    - {package: industries/motor/rotating,     role: technical-baseline}  # 旋转电机规则包(源:GB_T_755类)
    - {package: industries/motor/small-power,  role: technical-optional}  # 小功率专项,subject命中才载
  resolution:
    conflict: most-specific-wins
    legal-floor: [base/GB_T_1.1-2020, base/GB_3100-2026]
    obligation: {mandatory: {relax: register-required, tighten: pass, gap: warn},
                 recommended: {relax: note, tighten: pass, gap: note}}
    deviation: register-required   # 仅强制性放宽触发登记；推荐性放宽记备注
  pins: {lock: true}               # 每层钉包版本 → 快照可复现
  review-stages: [form, technical] # 与分类文档阶段门控一致
```

### 4.2 profile 生命周期与行业共享审批（2026-09-02 决策）

- profile 归属两档：`private`（tenant 企业私域，企业自建自审）与 `industry-shared`（行业共享，任何被授权用户可引用）。
- 共享审批流：企业提交行业共享（private → industry-candidate）→ **需经批准方进入 industry-shared**（状态 industry-approved）；**系统管理员可直接新增/批准 industry-shared profile**（如 leleby/行业生态维护的公共 profile）。
- 存放建议：private 在 rules/tenants/<tid>/profiles/，industry-shared 在 rules/profiles/ 或 rules/industries/<code>/profiles/approved/；状态机 draft → approved（企业内）→ industry-candidate → industry-approved。
- profile 版本化：共享后企业 fork 出的私有分支仍可继续演进；升级共享版走同审批流；引用方按钉版（pins）不受影响。

使用效果（对应你的三个诉求）：
1. **不加载无关数据**：subject 元数据（文件类型/产品/ICS/代号族）→ 命中 profile → 阶段门控（形式审查只载 formal 层 L1-L4；技术要求审查载 technical 层 L4-L6）→ 规则条目再按 `applies-to`/结构条件过滤；新用户做照明类审查时根本不加载电机 profile。
2. **合规性继承**：文档声明采标/引用（adopts/references）或产品域归属后，引擎自动把对应层的继承规则并入有效集；企标继承国标底线，域包继承旋转电机通用指标，企标只声明"加严/专项"即可。
3. **审查与纠错**：findings 每条带 `ruleId + layerPath + source-file`，可一路点回"哪层的哪条规则、源自哪份已批准文件哪一条款"；纠错回路沿用分类文档 §5.2。

---

## 5. 合规性继承的图语义（与 KG 主线衔接）

- 层/包关系在图中建模：`RuleSource(package) --derivedFrom--> ApprovedFile`；`Profile --layers(N)--> Package@version`；`Profile --appliesTo--> SubjectType/Product`。
- 文档级继承：`SubjectDoc --adopts--> Standard` / `SubjectDoc --coveredBy--> ProductDomain` → 引擎经图可达性收集应继承的 profile；标准换版时 profile 钉版触发"受影响 profile/审查运行"提醒（版本生命周期沿用 lookWhy §6.4）。
- 审查结果：`ReviewRun --snapshot--> EffectiveRuleSet`、`Finding --violates--> Rule`、`Finding --at--> Clause`；支持"该 domain 全部审查中最常违反的层/规则"类分析。
- 反推查询：任意有效规则 → 其 `layerPath` → 包 → 已批准文件条款锚点（闭环可审计）。

---

## 6. 与现有制品/前序设计的落点

1. **registry.yaml（分类文档 §4.1）扩展为"包注册 + profile 注册"双区**：`rule-sources:`（每包一条：类别/阶段/溯源/适用）与新增 `profiles:`（声明式组合）。schema 新建 `rules/schemas/rule-source-registry.schema.json`、`rules/schemas/audit-profile.schema.json`。
2. **目录/生命周期**：profile 存 rules/profiles/，状态机 draft→candidate→approved（对齐 industries 的 pending/approved 语义）；企业 profile 属 tenant 私域，审批与脱敏受 lookWhy §8 约束。
3. **包粒度重构候选（R0 不做，标注 future）**：把 GB_T_1.1-2020 包内通用 audit（id: general-standard-audit）拆为独立 `base/generic-audit` 包，便于被所有 profile 叠加而不携带 1.1 专有要求；GB_3100-2026 建包（源 ssir.json 已存在 → 提炼 requirements）作为量/单位层。
4. **引擎最小改动路径**：先实现"registry 加载 → subject 匹配 → 顺序材料化（不去重）→ 按裁决输出 + 覆盖链记录"，跑通形式审查再扩展 technical 层；现有 compliance/audit 执行器不动，只换规则集的供给方式。
5. **审查快照**：材料化完成即算 effective-set 哈希（含 profile 版本 + pins）写入 review-run 记录，findings 引用之 —— 历史审查可完全复现。

---

## 7. 分步落地（接 Track R，见分类文档 §6）

| 步骤 | 内容 | 验收 |
|---|---|---|
| R0a | registry 双区（rule-sources + profiles）+ schema；现有 base 包注册 | schema 校验过；profile 样例可解析 |
| R0b | 材料化引擎 v0：subject 匹配 → 顺序叠加 → legal-floor 校验 → 覆盖链记录 → effective-set 哈希 | 无刷永磁电机企标 profile 样例材料化结果人工可读、含 layerPath |
| R1 | 形式审查跑 profile（L1-L4） | 与现有 parse-report compliance 结果一致 + 覆盖链可见 |
| R2 | 首个 technical 层落地：旋转电机（或小功率）域包建包 + technical 审查试点 | 指标类别/范围 findings 出报告、可溯源到域包文件条款 |
| R3 | 继承/换版联动（adopts → 自动并入；钉版 → 受影响提醒）+ 图谱 Finding/ReviewRun 节点 | 换版影响清单正确 |

profile 样例语料：建议以一份真实"无刷永磁电机企标"（Q_* 语料或自建草案）端到端走 R0b-R2，作为 Track R 演示。

---

## 8. 未决问题（需决策）

1. **层数与粒度**：base 之下是否再分"起草规则 / 量单位 / 通用逻辑"为独立包（推荐拆，便于按阶段只载所需）；industry 层按"旋转电机→小功率→具体产品"还是"产品标准一刀切"？
2. ~~裁决默认值~~ **已决策（2026-09-02）**：技术条款分强制性(应)/推荐性(宜)；仅强制性放宽需偏差登记，推荐性放宽/未覆盖记备注或提示；加严一律通过。
3. ~~profile 归属与审批~~ **已决策（2026-09-02）**：profile 可行业共享；企业 profile 需批准后才能进入行业共享；系统管理员可直接新增行业共享 profile。落地验证见《验证报告 Q_YYJD 分层规则包 v0.1》。
4. **钉版策略**：profile 默认 `lock: true`（审查可复现）还是跟随最新 approved 包（自动享受新规则）？建议 lock + 显式升级动作。
5. **企业模板层示例**：企业标准模板目前无规则包样例，是否先以 Q_HKF/Q_TQDZ/Q_XKBZ 语料反推模板规则建 tenant 包？

---

## 附：关键引用

- rules/README.md（base + industry + tenant 三层叠加的既有规划；规则生命周期）
- docs/11_leleby Multi-tenant Storage & Rules Layout Specification v0.1.md（租户布局）
- docs/semantic_Stage/lookWhy 规则层分类与分阶段审查设计 v0.1.md（形式/技术纵轴、registry 草案、纠错回路）
- docs/semantic_Stage/lookWhy 知识图谱阶段规划与存储选型建议 v0.1.md（KG 主线、阶段与 Track R）
- docs/semantic_Stage/lookWhy_strategy_and_requirement_v1.1.md（§6.4 标准生命周期、§8 治理）
- docs/12_leleby 规则落实方法论与通用问题知识库 v0.1.md（§1 元规则与闭环）
