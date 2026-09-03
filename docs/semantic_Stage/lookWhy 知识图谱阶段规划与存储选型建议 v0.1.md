# lookWhy 标准知识图谱（KG）阶段规划与存储选型建议 v0.1

> 状态：规划草案（待评审冻结）
> 范围：本文回答三个问题 —— ① "所有标准元素与数据以知识图谱管理、可追溯原文条款号"的下一步如何开展；② 是否需要双数据库（SQLite+Neo4j / PostgreSQL+Neo4j）；③ 每个标准文档以独立 JSON/TTL 文件导入导出 Neo4j 的可行性。
> 依据：docs/semantic_Stage/*（leleby 生态战略 v4.1、lookWhy 战略 v1.1、Standard Ontology v1.5、Normative Semantic Package v0.3、架构总结 txt）、docs/00-12（SSIR 引擎）、src/leleby_ssir/ssir.schema.json 与 out/mineru/ 真实产物。
> 结论先行：双库方向正确但应拆成"文件真源 + 图谱投影 + 关系操作库"三层；MVP 关系库用 SQLite（SQLAlchemy 抽象），多用户时换 PostgreSQL；每文档独立 JSON 导入导出 = 正确粒度，TTL 是生态交换格式而非 Neo4j 原生存储格式。
> 
> 修订 v0.1（2026-09-02，决策已确认）：① MVP 单人工作站 → 关系库 SQLite 起步，PostgreSQL 仅在多用户部署时引入；② JSON（SSIR/文件层）为唯一真源，Neo4j 仅作"检索收敛后的图数据展示"，不承担主查询职责；③ 新增 Track R：规则层按 形式要求(formal)/技术要求(technical) 两分法分类，支撑分阶段合规审查与纠错 —— 详见配套文档《lookWhy 规则层分类与分阶段审查设计 v0.1.md》。

---

## 1. 现状盘点（已具备的资产，勿重复建设）

### 1.1 文档级文件资产（out/mineru/<ID>/，per-doc 单阶段目录）

每个标准当前已产出结构化中间物，是未来知识图谱的"原子库存"：

- `03_ssir/<ID>.ssir.json`：整本文档的结构化表示，**元素级稳定 URI** 已内建：
  - 结构树 structuralRoot：`document` → `documentBlock`（目次/前言/引言等）、`section`（章，带 `number`）、`clause`/`subClause`（条，带 `number`，如 id `ssir:GB-T-1.1-2020/clause-3.1-007`）、`annex`（附录）、`item`；
  - 每个节点：`id`、`nodeType`、`title`、`number`（条款号/附录号）、`level`、`logicalId`、`sortOrder`、`contentElements`、`sourceAnchors`；
  - 内容元素 contentElement：`id`、`parentNodeId`、`presentationType`（paragraph/…）、`semanticTypes`（实测已有 `termDefinition`、`scope`）、`textContent`、`sourceAnchors`；
  - sourceAnchor：`anchorType=markdown`、`markdownNodePath`、`markdownStartLine/EndLine`、`sourceFileId` —— 即**原文锚点已经逐元素存在**；
  - 文档级数组：`tables`、`figures`、`formulas`（表格/图/公式集中管理，元素按需引用）；
  - metadata.standard：`standardNumber`、`chineseTitle`、`ics`、`ccs`、`replaces`、发布日期等。
- `02_canonical/<ID>.canonical.md`：与 SSIR 一一对应的人类可读真源。
- `00_source/*.pdf|docx`、`04_render/*.render.pdf|docx`、`05_verify/verify.json`：原文与渲染回环。
- `assets/` + `manifest.json`：图元等资源。

推论：**图谱节点不需要"重新发明 ID"** —— SSIR URI（`ssir:<DOC-ID>/…`）就是天然稳定主键，条款号（node.number）就是追溯键。

### 1.2 生态/本体/战略资产（docs/semantic_Stage/）

- lookWhy 战略 v1.1：§4.6 知识分类是视图、知识图谱是本底；§5.2 四层知识模型；§8 数据治理（所有权 8.1、密级 8.2、谱系 8.4、审计 8.6）；§9 四阶段路线图。
- leleby 生态战略 v4.1：§20.1 技术栈表 = Neo4j（抽象层）+ PostgreSQL + MinIO；§20.2 图存储抽象层（应用层不绑 Cypher，内部 AST，未来 GraphDB/Stardog/Neptune）；§21.1 Ontology First，"严禁根据 Neo4j Schema 反推业务 Ontology"。
- Standard Ontology v1.5：标准结构类已定义齐备 —— Standard / StandardFamily / StandardEdition / StandardClause / StandardContentUnit / TableUnit / FigureUnit / DefinitionUnit / NoteUnit / ExampleUnit / AnnexUnit / NormativeStatement / RequirementBinding / StandardScope / StandardStatus，以及标准间关系：ReferencingRelationship / ReplacementRelationship / AdoptionRelationship / EquivalenceRelationship / DeviationRelationship / HarmonizationRelationship / ComplementaryRelationship。
- Normative Semantic Package v0.3：每份标准 = 独立语义包（.ttl 多文件：manifest/metadata/ontology-context/clauses/requirements/constraints/testmethods/dependencies/mappings/validation）；要求独立语义对象，来源追溯 `derivedFromNormativeSource → NormativeSource（Clause/Annex/…）`；SHACL 验证。
- 架构总结 txt：核心原则 8"知识图谱表示当前状态，版本系统保存历史演化"；标准版本 Git 式治理；标准之间 Adoption/Equivalence/Deviation/Scope 关系。

### 1.3 已固化且必须遵守的原则（直接引用，不重定义）

1. 应用层不得直接依赖 Neo4j 专有语法；图查询走语义服务层 + 适配器（生态 v4.1 §20.2）。
2. Ontology First：先定本体/数据契约，再映射存储；严禁从图库 Schema 反推。
3. 分类是视图/标签，图谱是本底；视图不存储数据。
4. 标准作为独立、版本化、可追溯的语义包存在；每条语义可追溯具体条款（NSP §3.4）。
5. 版本管理 Git 思想：当前状态入图，历史演化由文件/版本体系保存（txt 原则 8）。
6. 语义包不定义新 Ontology，全部类和关系来自 llb/lbo（NSP §3.6）。

---

## 2. 目标信息架构：三层模型（本规划的关键决策）

```
┌────────────────────────────────────────────────────────────────┐
│ ③ 关系操作库（SQLite→PostgreSQL，SQLAlchemy 抽象）             │
│    用户/角色/权限、审核流、审计日志、设计上下文与产品绑定、      │
│    分类视图标签索引、全文检索（FTS/tsvector）                    │
├────────────────────────────────────────────────────────────────┤
│ ② 图谱投影（Neo4j，语义服务层 + 适配器）—— 可整体重建            │
│    标准元素网络：Clause/ContentUnit/Table/Figure/Term/Ref...     │
│    跨文档引用边、replaces 边、谱系边、证据链边                   │
│    = "当前状态"，只承载查询/遍历/可视化/推理                     │
├────────────────────────────────────────────────────────────────┤
│ ① 文档真源（文件层，已存在）—— 唯一 System of Record            │
│    storage/tenants/<租户>/<ID>/ 或 out/mineru/<ID>/：            │
│    source.(pdf|docx) + canonical.md + ssir.json + assets/        │
│    + 校验报告；git 式版本管理、diff、审计                        │
└────────────────────────────────────────────────────────────────┘
```

### 2.1 第一层：文档真源 = 每份标准的独立文件（已实现，保持为唯一权威）

- SSIR JSON 是**无损文档表示**（含 LaTeX、上标、锚点、表图公式全要素），比任何图模型表达力都强；图模型是其**视图/投影**。
- 文件天生支持：多租户隔离（docs/11）、版本管理（Git 思想）、diff/回环验证、企业数据所有权与随时导出（lookWhy §8.1）、跨实例迁移（§6.8.4 .knw）。
- **推论：任何数据库（含 Neo4j）都可以从 ① 重新构建** —— 图谱不是系统记录，一致性/备份/迁移问题大幅简化。

### 2.2 第二层：图谱投影 = 面向展示与探索的派生视图（v0.1 角色收敛）

- **（已决策）Neo4j 定位为"检索收敛后的图数据展示"**：查询/筛选/收敛由 ①文件层 + ③关系库（SQLite FTS/JSON 检索、结构过滤）承担；命中子图以 kg.json 切片装载进 Neo4j 做图展示与探索。Neo4j 不是主查询引擎，也不是记录系统。
- 由 ① 经映射器构建；标签（Node Label）与边类型由 Standard Ontology v1.5 / NSP 语义模型决定（见 §3），**不由 Neo4j 决定**。
- 展示能力：条款树浏览、单文档/跨文档引用网络、换版影响子图（沿 references/replaces 多跳）、谱系链（derivedFrom）、证据链、KG 可视化；推理/约束检查留在语义服务层。
- 可整体删除重建（重建 = 批量重跑映射器），故无需为它设计复杂增量同步；装载切片的粒度=文档版本（§5）。

### 2.3 第三层：关系操作库 = 业务事务数据

- 与"标准元素"无关但与"平台运营"有关的数据：用户/角色/权限、知识审核流状态、审计日志、设计上下文（型号↔标准版本绑定）、分类视图标签、检索。
- 选型见 §4.3：MVP 用 SQLite，产品化多用户切 PostgreSQL —— 必须在代码层抽象（SQLAlchemy/异步驱动），避免迁移重写。

### 2.4 回答"是否需要两种数据库"

**结论：需要，但准确说法是"关系操作库 + 图库投影 + 文件真源"三层，且图库不是必须第一天就上。**

- 双库的真实理由不是"数据太多"，而是**访问模式不同**：
  - 图谱模式（多跳遍历、跨文档引用、影响分析、证据链）→ 图引擎；
  - 事务/审计/权限/全文 → 关系引擎。
- 若只做单文档浏览/树查询，SQLite(JSONB 递归 CTE) 就够了，Neo4j 属过度建设。你们的战略目标（跨标准引用网络、换版影响、合规证据链、与 leleby 共享语义层）天然是图遍历 —— 因此双库值得投入，但按 §6 的阶段 2 再引入 Neo4j，先把契约与映射器做扎实。

---

## 3. 图谱数据契约（"标准元素" → 节点/边）

> 本节是《SSIR→KG 映射规范》的骨架，正式化前需评审（§8）。

### 3.1 URI 策略

- 节点主键直接复用 SSIR 稳定 URI：`ssir:<DOC-ID>/document`、`…/section-3-006`、`…/clause-3.1-007`、`…/content/c-0421`、`…/table/t-0002`、`…/figure/f-0001`、`…/anchor/a-0011`。
- 追加语义层节点时以派生命名空间生成（如 `lreq:GB-T-1.1-2020/req-0001`），并在属性里记 `derivedFromElement` 指向 SSIR URI —— 保证"从图谱可一路退回文件元素/条款/原文锚点"。

### 3.2 节点类型映射（SSIR / SSIR 语义 ↔ Standard Ontology v1.5 ↔ Neo4j Label）

| SSIR 对象 | 本体类（lbo/lstd 语义） | Neo4j Label（投影建议） | 关键属性（来自 SSIR） |
|---|---|---|---|
| SSIRDocument | Standard / StandardEdition | StandardDocument | standardNumber, chineseTitle, ics, ccs, replaces, dates |
| structuralRoot(document) | StandardContentUnit(根) | DocumentRoot | — |
| documentBlock(封面/目次/前言/引言/参考文献/索引) | StandardContentUnit | DocumentBlock | title, blockKind(cover/toc/foreword/…) |
| section / clause / subClause | StandardClause | Clause | **number（追溯键）**, title, level, sortOrder |
| annex | AnnexUnit | Annex | annexLetter(A/B/…), normative/informative, title |
| item（列项条目） | StandardContentUnit | ContentUnit | kind=listItem |
| contentElement(paragraph/…) | StandardContentUnit | ContentUnit | kind=presentationType, text |
| contentElement(semanticTypes=[termDefinition]) | DefinitionUnit | Term | term, englishTerm, definition, 归属 3.x 条款 |
| 表格（tables 数组元素） | TableUnit | Table | tableNumber/caption, row/column 几何、合并 |
| 图（figures 数组元素） | FigureUnit | Figure | figureNumber/caption, assetRef |
| 公式（formulas 数组元素） | Formula | Formula | latex/平拍文本 |
| （未来）要求语句 | NormativeStatement/Requirement(lreq) | Requirement | 条款类型(要求/指示/推荐/允许/陈述)、应/宜/可 语气 |

实现提示：§3.2 的"kind/类型"全部可先从 SSIR 现字段派生（nodeType/presentationType/semanticTypes/title 形态），**不需要先跑 NLP**；语义提升（真正把句子抽成 Requirement/Constraint）放阶段 3，规则先行（应/不应/宜/可 + GB/T 1.1 附录 C 条款类型词表），复用 rules/base/GB_T_1.1-2020/requirements.yaml 与 compliance 已沉淀的判定逻辑。

### 3.3 关系（边）类型

| 边 | 起→止 | 来源 | 用途 |
|---|---|---|---|
| HAS_CHILD / PARENT_OF | 结构树父子 | structuralRoot.children | 树遍历（目录式导航） |
| CONTAINS_ELEMENT | Clause→ContentUnit/Term/Table/Figure | parentNodeId | 元素归条款 |
| TERM_DEFINED_IN | Term→Clause | 归属条款 | 术语库/跨文档术语对齐 |
| CITES / REFERENCES | Doc→Doc（条款级可带 referencingClause） | 第 2 章引用清单 + 正文"见…" | 规范性引用网络、换版影响 |
| REPLACES | Edition→Edition | metadata.standard.replaces | 版本链（2008→2024 双版本验证） |
| CROSS_REFERENCES | Clause→Clause | "见 4.3.4" 类内部引用 | 条款内联引用 |
| HAS_ANCHOR | 一切元素→Anchor/原文位置 | sourceAnchors | 追溯（跳原文） |
| （未来）DERIVED_FROM | Requirement→Clause(NormativeSource) | 语义提升 | 合规证据链头 |
| （未来）APPLIES_TO / BINDS | 标准条款→产品型号 | 设计上下文 | 型号适用与换版 |

引用边实现提示：SSIR 现无顶层 references 数组（第 2 章引用以段落/列项文本存在），需在映射器中做**规则化提取**——直接复用 compliance.py 的 `_STANDARD_NUMBER_RE`（已覆盖 30+ 前缀）与 GBT-C06 的引用条目识别逻辑，产出 `references` 边 + `standardNumber` 属性，作为跨文档图的第一批"真边"。

### 3.4 可追溯性设计（核心需求，写死进契约）

每个图谱节点必须携带（源自 SSIR，映射器透传，禁止丢弃）：

```
{ ssirId, nodeType/number(条款号或 null), clausePath("3.1.2"/"B.2"/null),
  anchor: { markdownStartLine, markdownNodePath, sourceFileId },
  artifactPath: "storage/tenants/<t>/<ID>/03_ssir/<ID>.ssir.json" }
```

验收标准：任取图谱任意节点，两步之内可得到 (文档 ID, 条款号, canonical.md 行号, 源 PDF)；据此可实现"点击图谱节点 → 定位原文"。

### 3.5 图谱内容边界（分阶段，避免一步到位）

- 现在（阶段 0-2）：结构树 + 内容单元 + 术语（termDefinition）+ 表格/图/公式 + 跨文档引用 + 版本替换关系。**全部可从 SSIR 无损派生，零语义猜测。**
- 阶段 3：Requirement/Constraint 语义提升（规则先、AI 后、人工审核入库，符合 lookWhy §6.1.4 双轨 + §8.3 质量治理）。
- 阶段 4：跨规范映射（mappings.ttl）、证据链、企业/产品实例层（llc）留待 leleby 协同。

---

## 4. 存储选型细化

### 4.1 图谱库：Neo4j（社区版起步，容器化）—— 展示层

- **（已决策）只做展示层**：应用先经 ①文件层/③SQLite 检索收敛出目标文档/子图（kg.json 切片），再装载进 Neo4j 供图浏览与探索；跨文档遍历查询仍在语义服务层以"按切片装载"方式提供，不把全库查询压给 Neo4j。
- 符合生态 v4.1 §20.1 既定选型与抽象层约束；语料规模（百级文档 × 万级元素）远未到性能瓶颈。
- 部署：docker compose 单实例 + 卷；开发机即可跑。
- 交互：官方 Python driver + 语义服务层封装（仓库内 src/ 新增包，禁止业务代码裸写 Cypher）。
- 备份/恢复：图谱可随时重建，备份策略 = "定期导出 + 真源在文件层"即可，无需企业级图库运维。

### 4.2 关系库：SQLite 起步，PostgreSQL 产品化

| 维度 | SQLite（MVP/dev） | PostgreSQL（产品化触发条件） |
|---|---|---|
| 并发用户 | 单人/少量（工程师+知识管理员） | 多用户同时编辑/审批/检索 |
| 事务与锁 | 单写者，够用 | 多写并发、行级锁 |
| 全文检索 | FTS5（中文需分词插件） | tsvector + zhparser/pg_trgm |
| JSON 载荷 | JSON1 可用 | JSONB 更强 |
| 权限/审计 | 应用层实现 | 行级安全(RLS)可选 |
| 运维 | 零运维（文件） | 服务部署/备份 |

| **决策规则（2026-09-02 已确认）**：MVP 为**单人工作站** → SQLite 起步（零运维、快迭代）；**暂不评估并发**。产品化出现多用户部署需求时切 PostgreSQL，差异用 SQLAlchemy（或等价）抽象封住，切换成本≈配置+少量方言差异。**任何时刻只保留一种关系库，不并行维护两套。**

### 4.3 何时可以"只有一个库"（诚实边界）

- 若近期只做"单标准浏览 + 少量交叉引用"，可先只上 SQLite/Postgres：JSONB 存元素 + 递归 CTE 走条款树 + 引用表做引用网络，Neo4j 延后到确需多跳遍历/可视化规模时再引。本规划不反对这条保守路径；§6 阶段 2 即为 Neo4j 的"引入闸门"（届时用真实查询清单验证收益）。

### 4.4 硬约束

- 业务数据模型（图谱契约）先冻结，Neo4j Schema/索引后配（生态 v4.1 §21.1）。
- 语义服务层只暴露业务查询 API；Neo4jAdapter 为第一实现，GraphDB/Stardog 等为未来实现（§20.2 AST 思路可简化：阶段 2 先以"服务函数 + 参数化 Cypher 集中在 adapter"形式落地，不急于抽象出 AST）。

---

## 5. 每份标准文档独立导入/导出设计（JSON / TTL）

### 5.1 原子单位 = "文档版本"（一个标准的一个版本）

与文件层（out/mineru/<ID>/）、命名规范（naming_specification.txt）、NSP 最小包原则完全同构：

```
导入单位 = <租户>/<ID>/03_ssir/<ID>.ssir.json（或其导出的 <ID>.kg.json）
导出单位 = <ID>.kg.json（图切片）或 <ID>.semantic.ttl（语义包）
```

### 5.2 JSON 通道（第一优先，工具/图库交换格式）

- 格式：`<ID>.kg.json` —— 平台内部图谱交换格式：`{ document, nodes:[…], edges:[…] }`，节点/边字段即 §3 契约；用 JSON Schema 校验（复用 tests/ 验证文化，schema 放 src/leleby_ssir/kg.schema.json）。
- 导入 Neo4j：`MERGE` 按 SSIR URI 幂等写入（每文档一个事务，可选 label `Doc:<ID>` 便于按文档清理）；删除语义 = `DELETE` 该文档 slice 下全部节点 + 其出边（cross-doc 引用边按两端存在性维护）。
- 导出：从 Neo4j 或直接由 SSIR JSON 重新生成（推荐后者 —— 导出永远从真源出，图谱只负责查询）。真源无损 ⇒ JSON 通道可完整保留 LaTeX/上标/锚点等一切字段。
- JSON 与 JSON-LD 同构：给文档级加 `@context` 即可对齐 leleby 的 JSON-LD 生态（PPM/ESM 文档已用 JSON-LD），成本极低，作为阶段 4 备选。

### 5.3 TTL 通道（生态交换格式，第二优先）

- 对应 NSP v0.3 的每标准语义包：clauses.ttl / requirements.ttl / …（或单文件 <ID>.ttl），命名空间 llb/lbo/lbs，SHACL validation.ttl 校验。
- 由 rdflib 从 SSIR JSON（或 kg.json）生成；语义提升完成前只导出结构层（StandardDocument/StandardClause/ContentUnit 三元组 + 追溯属性），不冒充 Requirement 抽取结果。
- **Neo4j 不是 RDF 存储**：TTL 不做 Neo4j 原生导入主通道。三条可选路线，按你们语义优先程度选：
  1. （推荐，阶段 4）TTL 仅作对外交换产物，由文件层生成；Neo4j 内部始终吃 kg.json/SSIR。职责单一、无双向映射漂移。
  2. 若未来"图谱权威格式就是 RDF"，应换 triplestore（GraphDB/Stardog —— 恰在生态 v4.1 未来清单里），Neo4j 只作中间投影。
  3. 坚持"Neo4j 直吃 TTL"：引入 n10s（neosemantics）插件做 RDF↔属性图映射 —— 可行但引入 vendor 专用映射层，与"适配器解耦"原则张力大，**不建议作为首选**。

### 5.4 结论

- "每标准独立 JSON/TTL 导入导出"方向正确且与全部既有规范同构 —— 落地为：**JSON = 工具/库内交换格式（先做，全要素无损）；TTL = leleby 生态语义包导出格式（后做，语义提升后更有价值）**。
- 补一条约束：图谱导出永远以文件真源为唯一出点，保证"导出 = 真源的可复现视图"，杜绝图库与文件不一致。

---

## 6. 分阶段路线图（下一步怎么开展）

> 各阶段独立可交付、可验收；与 lookWhy 战略 §9 对齐（MVP 资产形成 → 谱系合规 → 流通）。

### 阶段 0：契约冻结与样例验证（约 1-2 周，可与 1 并行）

任务：
1. 选 3-5 份代表语料（建议：GB_T_1.1-2020 起草规则型、GB_T_43726-2024 技术要求型、GB_T_23132-2008 与 -2024 双版本替换型、T_ZZB_2224-2021 团体标准型、Q_* 企标型各一）。
2. 将本文 §3 扩展为正式《SSIR→KG 映射规范 v0.1》（节点/边/属性/追溯字段逐条列出，含 null 语义与边界 case：无编号 documentBlock、跨页续表、附录内条款号等）。
3. 为样例文档各生成一份 `<ID>.kg.json`，人工抽查条款号/锚点正确性。
4. 建立 kg.schema.json + 校验单测。

产出：映射规范 + 5 份样例 kg.json + schema + 测试。验收：任取样例中任意内容元素，能输出(条款号, md 行号)；规范冻结。

### 阶段 1：单文档图谱工具链（2-3 周，无需任何新数据库）

任务：
1. src/leleby_ssir 新增 kg 子模块（或独立包 leleby_kg）：`ssir kg build --input <ID>.ssir.json --output <ID>.kg.json`、`ssir kg show/query`、`ssir kg validate`。
2. 本地（内存/SQLite）查询 API：按条款号取元素、按语义类型取术语、树导航；CLI + 简单 HTML/图谱可视化（复用现有渲染栈或轻量前端）实现"点节点→跳原文段"。
3. 第 2 章引用清单规则提取（复用 compliance 正则）→ 文档内/文档间引用边原型。

产出：命令行工具 + schema 校验 + 单文档可视化 + 引用边 v0。验收：单文档一切查询不依赖 Neo4j 可跑；人工核对 GB_T_23132 引用边无漏。

### 阶段 2：Neo4j 联调 + 跨文档网络（2-3 周）—— "要不要双库"在此设闸门

任务：
1. docker compose 起 Neo4j（社区版）；语义服务层（kg-api）封装 Node/Edge CRUD 与查询函数，业务代码零裸 Cypher。
2. 批量 loader：corpus 全量（out/mineru/ 现有 ~15+ 份）→ MERGE 入库；`kg import <ID>` / `kg remove <ID>` / `kg rebuild --all`（重建 = 清库重灌，验证 ① 文件真源可恢复性）。
3. 参考查询清单（作为 Neo4j 价值验收，缺一不可）：
   - Q1 引用网络：某标准被哪些现行标准规范性引用（跨文档 1 跳）；
   - Q2 换版影响：GB/T 23132-2024 发布后，沿 REPLACES + CITES 传播，列出受影响文档与条款；
   - Q3 追溯：任意 Requirement/Term 节点 → 文档、条款号、md 行、PDF 页；
   - Q4 术语对齐：跨文档同名术语（term 归一）聚类。
4. 备份脚本：kg export --all（真源重生成）+ Neo4j 定期 dump。

产出：Neo4j 实例 + loader/语义服务 + Q1-Q4 演示脚本 + 重建演练记录。验收：Q1-Q4 全部跑通；`kg rebuild --all` 后结果与重建前逐节点一致。

### 阶段 3：语义提升与运营库（4-6 周）

任务：
1. 规则化语义提升 v1：GB/T 1.1 附录 C 条款类型词表（要求/指示/推荐/允许/陈述 + 应/不应/宜/可/可以/能够…）+ 术语定义 + 表格数值 → lreq:Requirement / lcon:Constraint 实例，`derivedFromNormativeSource` 指回条款（NSP v0.3 语义），落 `<ID>.semantic.json` 扩展文件（仍以文件为真源，图谱只加投影）。
2. 关系库上线：SQLite（多用户后换 PostgreSQL）；表：用户/权限/审计/审核流/设计上下文绑定/分类标签；全文检索。
3. 合规证据链原型：标准条款 → 验证计划 → 测试数据 → 结论（边入图）。
4. （Track R 并行，见配套文档）技术要素完备性审查 B1 与指标范围对标 B2 试点，接入 rules/base/registry.yaml 分类注册。

产出：semantic.json 生成器 + 审核入库流 + 运营库 + 证据链 demo。验收：对 GB_T_43726 抽取的 Requirement 人工抽查准确率基线（先定可接受阈值），每条可追溯。

### 阶段 4：生态交换与流通（3-4 周）

任务：
1. TTL 语义包导出（rdflib）：结构层先行 → 语义提升后含 Requirement；SHACL validation 自检；对齐 NSP v0.3 文件结构。
2. Level 1/3 输出 API（MCP/HTTP）+ 脱敏校验钩子 + 审计（lookWhy §6.8）。
3. 分类视图标签与图谱节点解耦的最终验证（视图只读标签，不动边）。
4. 与 leleby 共享语义层同步流程（本体版本订阅）。

---

## 7. 立即执行清单（本周可启动）

1. 你确认 3-5 份代表语料与选型偏好（§8 决策项 1-3）。
2. 我按 §3 骨架起草《SSIR→KG 映射规范 v0.1》并落库 docs/。
3. 实现 `kg.json` 导出器 + schema + 单测（阶段 0/1 的 2-4 项），先在 1-2 份语料上跑通。
4. （并行评估）Neo4j 容器化与 kg-api 层设计，准备阶段 2 闸门。
5. 规则层两分法落地（Track R 并行）：评审《规则层分类与分阶段审查设计 v0.1》的 registry 草案并实现 R0（规则源分类注册 + 引擎按审查阶段过滤），与 KG 阶段 0 同步推进；领域产品审核规则包的分层叠加/裁决/快照语义见《规则包分层叠加与审核规则包模型 v0.1.md》（R0b 材料化引擎）。

---

## 8. 未决问题（需你决策）

1. ~~部署形态~~ **已决策（2026-09-02）**：MVP 单人工作站 → SQLite 起步；PostgreSQL 仅多用户部署时引入。
2. ~~图谱权威格式~~ **已决策（2026-09-02）**：JSON（SSIR/文件）为唯一真源；Neo4j 仅作检索收敛后的图数据展示；TTL 为生态导出格式（阶段 4）。
3. **Neo4j 引入时机**：按本规划阶段 2（先契约后引擎）还是现在就并行搭环境？
4. **语义提升分工**：阶段 3 的 Requirement 抽取先做规则版（无 LLM 依赖、可测），还是直接上 AI 双轨（大模型抽取 + 人工审核）？
5. **版本治理载体**：文件真源的版本管理用 git 仓库（storage/tenants 入 git）还是对象存储 + 独立版本服务？（影响 docs/11 后续演进）
6. 首版可视化前端形态：仓库内轻量 HTML/JS 即可，还是要独立前端工程（React + Cytoscape/D3，对应生态 v4.1 §20.1）？
7. **规则层（Track R）决策项**：形式/技术两分法的子类划分、首批 technical 规则源范围、纠错自动修复边界等 —— 见配套文档《规则层分类与分阶段审查设计 v0.1》§8。

---

## 附：本文引用文档索引

- docs/semantic_Stage/lookWhy_strategy_and_requirement_v1.1.md（§4.6、§6.8、§8、§9）
- docs/semantic_Stage/leleby Industrial Semantic Platform Strategy Specification v4.1.md（§20.1/20.2/21.1）
- docs/semantic_Stage/leleby Standard Ontology Specification v1.5.md（§3.2/3.3/4.x 类与关系）
- docs/semantic_Stage/leleby Normative Semantic Package Specification v0.3.md（§3.4/4.3/17.x）
- docs/semantic_Stage/leleby 项目整体架构与语义基础设施设计总结（讨论最终结论版）.txt
- docs/11_leleby Multi-tenant Storage & Rules Layout Specification v0.1.md
- out/mineru/<ID>/03_ssir/<ID>.ssir.json（SSIR 元素 ID/条款号/锚点实证）
- src/leleby_ssir/ssir.schema.json、naming_specification.txt
