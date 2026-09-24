# 标准元素与结构清单（识别 · 结构化 · 渲染）v0.1

依据：`rules/base/GB_T_1.1-2020/requirements.yaml`（GBT-E/H/C/N/X/P/L/FM/B 共 75 条）、
`rules/base/GB_T_1.1-2020/extraction-rules.yaml`（GEN-001—GEN-122 共 66 条）、
`src/leleby_ssir/ssir.schema.json`、`src/leleby_ssir/parser.py`、`src/leleby_ssir/builder.py`、
`docs/07`（canonical 语法）、`docs/12`（问题→规则知识库），以及 `out/mineru/*/03_ssir/*.ssir.json`
与 `corpus/golden/*` 的实测。

---

## 0. 本文定位与决策记录

### 0.1 决策（2026-09-22，用户裁定）

- **回环验证功能全面取消，从最初设计上取消。** canonical ↔ SSIR ↔ render.md ↔ verify
  这条链不再是交付口径的一部分：`render.md` 不再承担"能被解析器读回"的职责，
  CSM 语法只在 **canonical（唯一人工可编辑基线）** 一侧存在。
- `render.md` 的新定位：**SSIR JSON → 标准 markdown 的只读投影**——一份不依赖任何
  引擎私有标记、可被通用 markdown 解释器直接显示、视觉结构接近 `render.pdf` 的文件。
- 交付口径收窄为三条：**① 元数据抽取正确；② 全部元素与结构被识别并结构化进 JSON；
  ③ 从 JSON 正确渲染 PDF（以及作为投影的标准 markdown）**。
- 验证职责随之转移（替代回环）：元数据正确性校验、结构完整性与归属校验
  （一一对应、编号连续性、锚点可定位）、渲染端零推断断言、PDF 产物校验。

### 0.2 本文用途

对"需要**先识别其性质**、再按 GB/T 1.1 的格式渲染"的元素与结构做一次全量清点：
标出标准要求、现有规则、现有 JSON 落点、缺口。它是后续三件事的共同底稿——
schema 字段增补、parser/builder 结构化改造、标准 markdown 输出规范。

### 0.3 现状判读约定

- **已实现**：规则落地且有回归夹具、跨语料验证；
- **部分实现**：抽取/解析能命中，但落到 JSON 的信息不足以支撑"不猜"的渲染或本体消费；
- **缺**：没有规则、没有字段，靠渲染端启发式或根本没有处理。

---

## 1. 标准的包含关系（骨架）

GB/T 1.1-2020 表3 给出要素的类别、构成与允许的表述形式；本引擎的元素模型必须与之一一对应。

```
文件（标准）
├── 层次（7.1—7.5）        部分 → 章 → 条 → 段 → 列项
├── 要素（表3，14 项，有规定次序）
│   ├── 资料性要素：封面 / 目次 / 前言 / 引言 / 规范性引用文件 / 参考文献 / 索引
│   └── 规范性要素：范围 / 术语和定义 / 符号和缩略语 / 分类和编码·系统构成 /
│                   总体原则和（或）总体要求 / 核心技术要素 / 其他技术要素
├── 表述形式（9.1—9.13）   条文 / 附加信息 / 通用内容 / 引用与提示 / 附录 /
│                          图 / 表 / 数学公式 / 示例 / 注 / 脚注
└── 附加信息              注、脚注、示例、图注、表注、来源、指明附录
```

要素与其**允许的表述形式**（表3，规则的 source 逐条对应）：

| 要素 | 规则 ID | 性质 | 必备性 | 允许的表述形式 |
| 封面 | GBT-E01 | 资料性 | 必备 | 标明文件信息 |
| 目次 | GBT-E02 | 资料性 | 可选 | 列表（自动生成） |
| 前言 | GBT-E03 | 资料性 | 必备 | 条文、注、脚注、指明附录 |
| 引言 | GBT-E04 | 资料性 | 可选 | 条文、图、表、公式、注、脚注、指明附录 |
| 范围 | GBT-E05 | 规范性 | 必备 | 条文、表、注、脚注 |
| 规范性引用文件 | GBT-E06 | 资料性 | 必备/可选 | 清单、注、脚注 |
| 术语和定义 | GBT-E07 | 规范性 | 必备/可选 | 条文、图、公式、示例、注、引用、提示 |
| 符号和缩略语 | GBT-E08 | 规范性 | 可选 | 条文、图、表、公式、示例、注、脚注、引用、提示、指明附录 |
| 分类和编码/系统构成 | GBT-E09 | 规范性 | 可选 | （表3 未列） |
| 总体原则和/或总体要求 | GBT-E10 | 规范性 | 可选 | （表3 未列） |
| 核心技术要素 | GBT-E11 | 规范性 | 必备 | （表3 未列，8.11） |
| 其他技术要素 | GBT-E12 | 规范性 | 可选 | （表3 未列，8.12） |
| 参考文献 | GBT-E13 | 资料性 | 可选 | 清单、脚注 |
| 索引 | GBT-E14 | 资料性 | 可选 | 列表（自动生成） |

**注意**：`requirements.yaml` 中要素编写规则只有 **GBT-C01—C09**（8.1—9.6）；
`标准要素完整清单.md` 里标注的 GBT-C10—C14（8.10—8.14：总体原则/核心技术要素/
其他技术要素/参考文献/索引）**在规则包中不存在**，需核对后补齐或改正清单。

---

## 2. 元素总表

### 2.1 A 组：标准元数据与封面

| 元素 | 标准依据 | 规则 ID | 现有 JSON 落点 | 现状 |
| 文件编号（含年份） | 8.1、10.3.1.4 | GEN-012、GBT-L02 | `metadata.standard.standardNumber`、`common.documentIdentifier` | 已实现 |
| 标准名称（中文） | 8.1、10.3.1.2 | GEN-016、016A、GBT-L04 | `common.title`、`standard.chineseTitle` | 已实现 |
| 英文译名 | 8.1、附录F 序号08 | GEN-016、GBT-L05 | `common.titleEn` | 已实现（GB_T_51711-2014 缺，见 §7） |
| 发布机构 | 8.1、附录F 序号14 | GEN-014、GBT-L08、L09 | `common.issuer` | 已实现（映射表有限） |
| 发布日期 | 8.1、附录F 序号13 | GEN-013、GBT-L07 | `common.publicationDate` | 已实现 |
| 实施日期 | 8.1 | GEN-013、GBT-L07 | `common.effectiveDate` | 已实现 |
| ICS 号 | 10.3.1.5 | GEN-011、GEN-101、GBT-L01 | `standard.ics` | 已实现 |
| CCS 号 | 10.3.1.5 | GEN-011、GEN-101、GBT-L01 | `standard.ccs` | 已实现 |
| 被代替文件编号 | 8.1、10.3.1.4 | GEN-015、GBT-L02 | `standard.replaces` | 已实现（源无则空） |
| 一致性程度标识 | 10.3.1.3 | GEN-017、GBT-L06 | `common.conformityStatement` | 已实现 |
| 封面横幅 / 类别字样 | 表3、图E.5 | GEN-016A、GBT-L03 | （仅用于识别，不入 JSON） | 已实现 |
| 封面徽标 | 附录E 图E.5 | GEN-018 | `metadata.standard.logo`（渲染用） | 已实现 |
| 归口单位 / 技术委员会 | 前言写作（8.3） | **缺** | **无字段** | **缺** |
| 标准状态（发布/修订/废止） | GBT 22373 元数据 | **缺** | **无字段** | **缺** |
| 技术领域 / 关键词 | GBT 22373 元数据 | **缺** | **无字段** | **缺** |
| 国际对应关系（等同/修改/非等效） | 9.5、10.3.1.3 | 部分（GEN-017 只覆盖一致性标识） | **无字段** | **缺** |

`metadata.DocumentRelationship` 系列类型（replaces/amends/equivalentTo…）已在 schema
定义，但只用于 `standard.replaces` 一个字段。

### 2.2 B 组：文档级要素与层次

| 元素 | 标准依据 | 规则 ID | 现有 JSON 落点 | 现状 |
| 封面 / 封底 | GBT-E01、L10 | GBT-C01、GEN-018 | 渲染期由 profile 绘制，不入结构树 | 已实现 |
| 目次 | GBT-E02、C02、FM1 | GEN-093、GEN-030 | `structuralRoot` 下 documentBlock + `list` | 部分实现（条目/页码未结构化） |
| 前言 | GBT-E03、C03、FM2 | GBT-C03、GEN-093 | section 节点 | 已实现（"提出/归口/起草单位"未结构化） |
| 引言 | GBT-E04、C04、FM2 | GBT-C04 | section 节点 | 已实现 |
| 正文与要素章 | GBT-E05—E12 | GBT-C05—C09、GEN-093 | clause 节点树 | 已实现 |
| 参考文献 | GBT-E13、C13 缺、FM5 | GEN-099 | section + `ref_text` 块 → 段落 | 部分实现（条目未结构化） |
| 索引 | GBT-E14、FM5 | GEN-099、GEN-030 | section + `index` 块 → 段落 | 部分实现 |
| 部分（分部分文件） | GBT-H01 | **缺**（规则包内无分部专项规则） | 仅标题字符串（`_PART_TITLE_RE` 识别"第 N 部分"） | **缺** |
| 章 | GBT-H02、B02 | GEN-031、GEN-117 | `nodeType: clause` | 已实现 |
| 条 / 分条 | GBT-H03、H04 | GEN-031、GEN-035、GEN-117 | `nodeType: clause/subClause` | 已实现 |
| 段 | GBT-H05、B03 | GBT-B03 | `paragraph` 内容元素 | 已实现 |
| 列项 | GBT-H06、B04 | CSM-OCR-016、GEN-099 | `list` 内容元素 + `listItems[]` | 部分实现（引语/终止符未结构化，见 §4） |

### 2.3 C 组：表述形式

| 元素 | 标准依据 | 规则 ID | 现有 JSON 落点 | 现状 |
| 条文 | 9.1、10.2 | GBT-B03、GEN-108 | `paragraph`（含 `richText`） | 已实现 |
| 图 | GBT-X01、B06 | GEN-032/033/096/098/100/112/113 | `figures[]` + `figure` 内容元素 | 部分实现（分图/图脚注/标引序号未结构化） |
| 表 | GBT-X02、B07、B13 | GEN-032/033/080/094/094B/103/110/114/115/120/121 | `tables[]` + `table` 内容元素 | 部分实现（注/角标未结构化，见 §3.7） |
| 数学公式 | GBT-X06、B09 | GEN-102/105/106/109、CSM-OCR-017 | `formulas[]` + `formula` 内容元素 | 部分实现（式中解释组未结构化） |
| 示例 | GBT-X05、B11 | GBT-B11、CSM-STRUCT-006 | `example` 内容元素 + `box/boxStyle` | 已实现 |
| 注（条文注/图注/表注） | GBT-X03、B10 | GBT-X03、GEN-080 | `note` 内容元素 | **部分实现：不区分族、无属主、无锚点** |
| 脚注 | GBT-X04、B10 | GEN-118（条文脚注）、GEN-119（角标） | `footnote` + `footnoteMarker/footnoteAnchorRef` | 部分实现（图表脚注未结构化） |
| 引用与提示 | 9.5.4、9.5.5 | **缺** | **无**（schema 有 `Reference` 定义但无产出） | **缺** |
| 指明附录 | 9.6.3 | **缺** | **无** | **缺** |
| 清单（规范性引用文件/参考文献/符号） | GBT-C06、C08、FM3 | GEN-099、GBT-C06 | `paragraph` 序列 | 部分实现（条目未结构化） |
| 来源（术语条目） | GBT-C07 | **缺**（仅 builder 注释提到"定义段判定时排除来源行"） | **无**（`[来源：…]` 作为正文段落） | 部分实现 |
| 提示语（重要提示） | GBT-B01 | GBT-B01 | 封面区段（渲染期） | 已实现 |

### 2.4 D 组：版式与渲染（渲染端，不影响 JSON 结构）

| 元素 | 规则 ID | 现状 |
| 幅面/页面格式 | GBT-P01—P06 | 已实现（profile 驱动，GEN-071） |
| 封面布局 10 项 | GBT-L01—L10 | 已实现 |
| 目次/前言/术语/参考文献版式 | GBT-FM1—FM5 | 已实现 |
| 正文版式（章条/段/列项/附录/图/表/公式/注/示例） | GBT-B01—B13 | 已实现 |
| 字体字号矩阵 | 附录F 表F.1、GEN-070/071 | 已实现（TrueType 约束） |
| 列宽分配与宽表横排 | GEN-103/110/111/120/121 | 已实现 |
| 转页接排（续表/续图） | GBT-B13、GEN-115 | 已实现 |
| 上标还原与单位字隙 | GBT-B12、GEN-104/116/122 | 已实现 |
| 公式与希腊字形 | GEN-102/105/106/109/122 | 已实现 |

### 2.5 E 组：附加与特殊块

| 元素 | 规则 ID | 现有 JSON 落点 | 现状 |
| 显式文档框（示例框等） | CSM-STRUCT-006、GBT-B11、docs/07 §6.8 | `box` / `boxStyle`（节点与内容元素） | 已实现 |
| 并列组（两栏对照） | GEN-095、CSM-STRUCT-008、docs/07 §6.9 | `sideBySideGroup/Column/Widths` | 已实现 |
| 原样块（树状/伪代码/版式片段） | GEN-052/GEN-107、docs/07 §6.10 | `unknownContents[]` + `unknown` | 已实现 |
| 行内强调（黑体/斜体语义） | GEN-108 | `richText`/`TextSpan` | 已实现 |
| 未知/未覆盖内容 | GEN-052 | `unknownContents[]` | 已实现 |
| 实体与关系（本体层） | — | schema 有 `EntityMention/RelationMention/Reference` **定义**，SSIR **无产出** | **缺**（下一阶段） |

---

## 3. 结构模式清单（我们实际识别和处理的书写形态）

本节回答用户提出的问题："我们实际识别和处理的结构有哪些"。每条给出**形态 → 判据 →
代码位置 → JSON 表达 → 缺口**。

### 3.1 层次编号与标题

- 形态：`# 编号 标题`；编号为点分阿拉伯数字链（条）或 `附录 A（规范性）标题`。
- 判据：`HEADING_RE`；编号确认不依赖编号与标题之间的空格（**GEN-117**，
  `parser._bare_heading_candidates`）；裸条号标题提升（GEN-035，`_promoted_bare_headings`）；
  编号掉点修复（GEN-031，`_clause_digit_placements`）；H1 收敛（GEN-034）；
  附录标题三行合并（GEN-030 `_recover_annex_headings`）。
- JSON：`StructuralNode{nodeType, number, title, level}`，`annex` 节点带 `（规范性）` 状态。
- 缺口：无。

### 3.2 冒号引导的列项组（引语 + 条目序列 + 终止符）

- 形态：引语段以 `：` 收尾，其后为若干条目；条目以 marker 起首，**条目间以「；」收尾、
  末项以「。」收尾**；第二层次条目以 `·` 或 `1)` 起首。
- 判据：`parser._repair_colon_led_lists`（CSM-OCR-016），
  `colon_intro = re.compile(r"[:：]\s*$")`；条目终止符 `_FORMULA_ITEM_END_RE` 同族判据。
- JSON：`list` 内容元素 → `listItems[{marker, markerType, text, subItems}]`；
  **引语是独立的 `paragraph` 元素**（与 list 无结构关联）。
- 缺口：① 引语与列表组无关联字段（`introRef`）；② 条目终止符（；/。）不入 JSON；
  ③ 层次深度只有一层 `subItems`；④ "一个列项组被 OCR 拆成多段"只在 parser 内修，
  修完后没有可核验的"组完整性"信息落到 JSON。

### 3.3 列项 marker 族

- 形态（GBT-B04）：第一层次 `——`（破折号）或 `a）`（字母编号）；第二层次 `·`（间隔号）
  或 `1）`（数字编号）。渲染时破折号/字母空两个汉字起排、回行对齐第 5 汉字位；
  第二层次空四个汉字、回行对齐第 7 汉字位。
- 判据：`UNORDERED_ITEM_RE`（`-—–`、`*+`、`●•·○`）、`NUMBERED_ITEM_RE`
  （`^([A-Za-z]+[)）]|\d+[)）])`）、`_marker_family`（dash/dot/letter/number）。
- JSON：`listItems[].marker` + `markerType`（schema 枚举 `lowerAlpha/upperAlpha/numeric/
  roman/bullet/dash/other`）。
- 缺口：`markerType` 的判定与 `_marker_family` 不是同一判据（前者在 builder，后者在 parser），
  存在两处口径；层次（第一层/第二层）没有显式字段，渲染端按 marker 族反推。

### 3.4 术语条目

- 形态（GBT-C07、GBT-FM4）：条目编号（`3.1.1`）顶格单独占一行 → 术语 + 空一个汉字 +
  英文对应词 → 定义（空两个汉字起排，回行顶格）→ 依次可加符号、图/公式、示例、注、来源。
- 判据：`TERM_ENTRY_LINE_RE`、`_TERM_ENTRY_GAP_RE`、`term_entry_pair`、
  `_repair_term_entry_headings`。
- JSON：`StructuralNode{nodeType: item/subItem, term, englishTerm}` + 内容元素。
- 缺口：定义/符号/"来源"三者没有各自的结构字段（来源行 `[来源：…]` 现在只是正文段落）。

### 3.5 式中变量解释组（公式的解释）

- 形态（GBT-B09、GBT-X06 10.4.3）：公式下方「式中：」独占一行 → 每条为
  **变量 + 破折号 + 解释 + （；末项。）**；破折号各行对齐。
- 判据：`FORMULA_VAR_INTRO_RE = ^式中[:：]$`、`FORMULA_VAR_ITEM_RE`（head/dash/text）、
  `_normalise_formula_variable_group`、`_repair_formula_variable_lines`。
- JSON 实态（GB_T_30819-2024 6.4 实测）：`formula` 内容元素之后是**一串互不关联的
  `paragraph`**——`式中：` 一段，`$ \overline{η}$ ─ 传动效率；` 一段，……
- 缺口：**解释组不是结构化对象**：哪个公式、哪几个变量、什么量纲/单位，本体拿不到；
  渲染端只能按"公式后面连续的段落"推断。建议 `Formula.variableExplanations[]`
  （`{symbol, definition, unit, terminator}`）。

### 3.6 图的解释 / 标引序号说明

- 形态（GB/T 1.1 9.7.4.2）：图中标引序号与说明——`图中：` 引出，`1——…；2——…。`
- 现状：**全仓库无处理**（`grep 标引 / 图中：` 在 parser/pdf_renderer/rules 中 0 命中）。
- 缺口：规则、语法、JSON 字段、渲染全部缺。与 §3.5 同属"解释组"，可共用对象模型。

### 3.7 表的注与表脚注（当前"注"问题最集中的地方）

- 形态（GBT-X03、GBT-X04）：
  - **表的注**：`注：` / `注1：`，位于表内下方、**表脚注之上**；
  - **表脚注**：小写拉丁字母上标 `a)`、`b)`，**逐表单独编号**，位于表内最下方，
    由标记与解释成对组成。
- 现状：
  - 角标只活在单元格文本里的 `$^{a}$`（GEN-119；实测 GB_T_10401-2023 表11
    `径向间隙$^{a、c}$`、GB_T_1.1-2020 表3 表头/末行）；
  - 注文形态有两种：① 被抽成表内合并末行单元格（GB/T 1.1 表3 的
    `$^{a}$章编号和标题的设置是必备的…`）；② 抽取层 `table_footnote` 内层块排成表后普通文本行；
  - schema 有 `Table.tableNote: string[]`，**语料 9 份全部为空数组**；
  - 表注的渲染依赖 GEN-080（单长格跨列合并）与渲染端启发式。
- 缺口（**本轮重点**）：
  1. 没有"注的族"（表的注 vs 表脚注 vs 图注 vs 图脚注 vs 条文注）字段；
  2. 角标 `a` 与注文之间**没有锚点关系**（哪一格、哪一行、哪条注）；
  3. `$^{a}$` 与数学上标语法同形，无判据区分（GEN-119 合并了写法，代价在此）；
  4. 逐表编号作用域未登记（多表共存时 `a` 会撞车）。

### 3.8 条文脚注

- 形态（GEN-118，已定案）：正文引用点 `[foot:1]`；注文写指令对
  `<!--ssir:foot:1-->…<!--ssir:/foot-->`，独立成行、紧随引用段，渲染到**引用所在页**页脚。
- JSON：`ContentElement{footnoteMarker, footnoteAnchorRef}` + `presentationType: footnote`。
- 现状：已实现（builder.py:298-309），是全仓库**唯一**把"标记↔属主"落到 JSON 的一类。
- 缺口：锚点类型只隐含"页"，没有显式的 anchor 种类；脚注的"被注释对象"只到条款级，
  不到句/段级。

### 3.9 示例与框

- 形态（GBT-X05、GBT-B11）：`示例：` / `示例1：`；线框内示例用 `ssir:box` 显式声明
  （docs/07 §6.8）。
- JSON：`example` 内容元素 + `box/boxStyle`；附录示例由 `_mark_annex_examples` 标记。
- 现状：已实现。
- 缺口：示例如内嵌注/脚注时的归属（与 §3.7 同族问题）。

### 3.10 附录结构

- 形态（GBT-C09、GBT-B05）：`附录 A`、`（规范性）/（资料性）`、标题各占一行居中；
  附录内条/图/表/公式编号加附录字母（`A.1`、`图A.1`、`表A.1`、`式(A.1)`）；
  附录中不设"范围/规范性引用文件/术语和定义"。
- JSON：`nodeType: annex` / `annexSection`；附录内编号作用域由 parser 在标题重组时确定。
- 现状：已实现（GEN-030、CSM-OCR-017 的附录内公式编号作用域切换）。
- 缺口：附录编号作用域没有显式字段（渲染/本体需要从 title 字符串再解析一次）。

### 3.11 规范性引用文件清单

- 形态（GBT-C06、GBT-FM3）：引导语 + 文件清单；清单**不加序号**，各文件空两个汉字起排、
  回行顶格；条目含文件编号 + 名称；无引用时写"本文件没有规范性引用文件。"。
- JSON：`paragraph` 序列（无结构）。
- 缺口：清单条目应是**引用关系**（schema `Reference` 已定义 `targetType:
  externalStandard` 等），当前完全没产出。本体阶段必需。

### 3.12 参考文献 / 索引条目

- 形态（GBT-FM5、GEN-099）：`ref_text` / `index` 块按"一行一条记录"处理。
- JSON：`paragraph` 序列。
- 缺口：同上，条目未结构化。

### 3.13 目次条目

- 形态（GBT-C02、GBT-FM1）：项 + `……` + 页码；不列术语条目编号和术语。
- JSON：documentBlock + `list`（GEN-093）。
- 缺口：条目与页码不分离（渲染端按 `……` 切）。

### 3.14 表结构细节

- 表头行数（GEN-114，按首行起点最大 rowspan）、合并单元格（`rowspan/colspan`）、
  空位一字线（GBT-X02/GEN-094A）、单位陈述（GEN-032）、续表（GEN-115，重复表头+单位+「（续）」）、
  列宽下界（GEN-103/120/121）、隐藏行表 hybrid 二遍（GEN-094）。
- JSON：`Table{number, caption, unit, rows[].cells[]{text, colspan, rowspan, isHeader}}`。
- 现状：已实现。
- 缺口：单元格的"注角标锚点"（§3.7）；表内 `$^{a}$` 与单位字母的歧义由 GEN-104 兜底。

### 3.15 图结构细节

- 题注（图下居中）、单位陈述（右上）、分图 `a) b)` 题注（GEN-112/113）、
  资产与源尺寸（GEN-096/098/100）、续图（GBT-B13）。
- JSON：`Figure{number, caption, unit, assetRef, sourceWidth/Height, altText, preservationStatus}`。
- 缺口：**图脚注/图中标引说明无字段**（`Figure` 只有 caption/unit）；分图题注无结构（
  现在被折进 caption/altText 文本）。

### 3.16 公式细节

- 居中、编号右端对齐与 `……` 引导线、编号作用域（正文连续 / 附录内重启，CSM-OCR-017）、
  含 CJK 公式用图资产（GEN-102）、显示尺寸与 dfrac（GEN-105/109）、
  行内公式斜体与上划线（GEN-116/122）。
- JSON：`Formula{number, rawText, latex, assetRef}`。
- 缺口：式中解释组（§3.5）。

### 3.17 并列组

- 形态：源版面同一水平带内 x 分离的 2—3 组内容（如"正确/不正确"对照）；显式声明
  `ssir:columns`（CSM-STRUCT-008）。
- JSON：`sideBySideGroup/sideBySideColumn/sideBySideWidths`。
- 现状：已实现。

### 3.18 原样块

- 形态：树状结构/伪代码/版式片段，用 `ssir:unknown` + 围栏代码块（docs/07 §6.10、GEN-107）。
- JSON：`unknownContents[]{rawContent, contentTypeHint}`。
- 现状：已实现。

### 3.19 行内标记

| 标记 | 语义 | 规则 | JSON |
| `**…**` / `*…*` | 黑体（必备要素）/ 斜体（资料性要素） | GEN-108 | `richText/TextSpan` |
| `$…$` | 行内公式（变量斜体 + 上划线） | GEN-116/122 | `textContent` 内的原始 LaTeX |
| `$^{a}$` | 上标（**角注与数学上标同形**） | GEN-119/104 | 同上（无锚点） |
| `$_{…}$` | 下标 | GEN-104 | 同上 |
| `[foot:N]` | 条文脚注引用点 | GEN-118 | `footnoteMarker` + `footnoteAnchorRef` |
| `[来源：…]` | 术语条目来源 | GBT-C07 | 无（正文段落） |

---

## 4. JSON 目标模型（本轮要补的字段）

原则：**一切"渲染端现在靠猜的东西"必须先在 JSON 里有字段**。以下为本轮建议增补，
命名需经确认后写入 `ssir.schema.json`（GEN-050：未登记键必须构建失败）。

### 4.1 注与脚注（共用一族，按标准分型）

```
Note {
  id, type: "footnote" | "note",        // GBT-X04 / GBT-X03
  ownerKind: "clause"|"table"|"figure"|"term"|"example"|"page",
  ownerRef,                             // 属主节点 id（表/图/条款）
  label,                                // "1" / "a" / "注1"
  numberingScope,                       // "document" | "table" | "figure" | "clause"
  text, sourceAnchors[],
  anchors: [ { kind: "cell"|"figurePart"|"inline"|"page",
               tableRef?, row?, col?, figureRef?, contentElementRef?, textRange? } ]
}
```

- `Table.notes[]` / `Figure.notes[]` 取代现无实产的 `Table.tableNote`；
- `ContentElement` 增 `noteKind` / `noteLabel` / `noteOwnerRef`（`presentationType: note`）；
- 单元格文本保留 `$^{a}$` 显示形态，同时登记 `TableCell.noteAnchors[{label, noteRef}]`；
- 判别"角注 vs 数学上标"的通用判据（可跨语料验证）：
  **单字母或字母串（可含顿号串 `a、c`）+ 该表/图节点下存在与标签同名的注文条目**；
  命中→登记为角注锚点；不命中→按普通上标；无法判定→报 issue（不猜，§0.3）。

### 4.2 列项组

- `list` 增 `introRef`（引语段落 id）/ `introText`；`listItems[]` 增
  `terminator`（"；"/"。"）与 `level`（第一层/第二层）。

### 4.3 解释组（公式/图）

- `Formula.explanationGroup { introRef, items: [{ symbol, definition, unit, terminator }] }`；
- `Figure.legend[]`（标引序号说明：`{index, text}`）与 `Figure.footnotes[]`（图脚注）。

### 4.4 引用与提示

- 产出 schema 已定义的 `Reference[]`（`internalClause/internalTable/internalFigure/
  externalStandard/…`），供 §3.11—3.13 的清单条目、正文"见 x.x""见表 N"使用。

### 4.5 附录与清单

- `StructuralNode.annexScope`（附录字母 + 编号作用域，显式字段）；
- 清单条目结构（规范性引用文件 / 参考文献 / 索引：`{label?, text, targetRef?}`）。

---

## 5. render.md 标准 markdown 输出规范（不复核回环）

输出必须落在 **CommonMark + GFM 表**可解析子集，且满足三条硬约束：
① 不含任何 `<!-- ssir:… -->` 指令或 HTML 注释；② 相邻块之间必须有空行；
③ 列表项必须使用合法 markdown marker（`-`、`1.`）或显式硬换行，不得依赖非标准 marker。

| 结构 | render.md 写法 |
| 元数据 | YAML frontmatter（保留；机器可读，供本体阶段直接取用） |
| 章条标题 | `#`…`######`（层级 = 结构层级 + 1） |
| 条文段 | 普通段落 |
| 列项 | GFM 列表；原 marker（`a）`、`——`）作为项内文本保留，或按选择改用 `- ` |
| 表 | GFM 管道表；题注独立成段（加粗）；合并单元格留空（GFM 不支持 rowspan/colspan） |
| 图 | 有资产：`![题注](assets/…)`；无资产：独立段落写「图 N 题名（图片占位）」 |
| 公式 | 围栏代码块（```text）+ 「式(N)」独立段落；不使用 `$$`（非标准） |
| 注 | 独立段落（`注：…` / `注1：…`），不与正文同段 |
| 表脚注/图脚注 | 独立段落（`a）注文`），紧随表/图 |
| 条文脚注 | 独立段落（`1) 注文`），紧随引用段 |
| 示例 | 引用块 `> 示例：…` |
| 并列组 | 并排放不下时按列顺序输出为连续块（markdown 无并列语义） |
| 原样块 | 围栏代码块 |
| 角标/上下标 | 保留 `$^{a}$`（视觉等效；markdown 无上标语法） |

---

## 6. 验证（替代回环）

| 层 | 校验项 | 归属 |
| 元数据 | M01—M10 逐字段对照源 PDF 封面文本层：存在性、格式、与 canonical 一致 | 新工具 + 规则 |
| 结构 | 编号连续性、附录作用域、列项组完整性（引语 + 条目 + 终止符） | 合规层 |
| 注 | 标记 ↔ 注文**双向一一对应**；孤标/悬空注报错；作用域内编号连续；锚点可定位 | 合规层（新增） |
| 引用 | 每个 `ref` 命中注册表；`internalClause` 目标存在 | 合规层（新增） |
| 渲染 | 渲染端零推断断言：字段缺失即报错，禁止回读源 PDF 或按形状猜 | 单测 |
| 产物 | 页数、关键字段、孤立单字行、字体字号（基于 PDF 内部对象） | 保留（GEN-090/091） |

---

## 7. 缺口清单与优先级

**P0（本轮）**
1. 注/脚注族结构化（§3.7、§3.8、§4.1）：字段 + 解析登记 + 一一对应校验；
2. 元数据 M01—M10 逐文档校验（对照源 PDF，判"真缺 vs 抽取缺陷"）；
3. render.md 标准 markdown 输出（§5），彻底去掉 ssir 指令与 HTML 注释；
4. 回环功能下线（CLI / roundtrip.py / 05_verify / verify_conversion / verify_markdown_roundtrip /
   依赖它的单测改为直接断言 SSIR）。

**P1**
5. 解释组结构化：式中变量解释（§3.5）、图的解释与标引序号（§3.6）；
6. 列项组引语与终止符（§4.2）；
7. 引用与提示 `Reference[]` 产出（§4.4）——本体阶段的前置。

**P2**
8. 清单条目结构化（规范性引用文件 / 参考文献 / 索引）；
9. 术语条目"来源/符号/定义"分字段；
10. 分图题注、附录编号作用域显式字段；
11. 元数据 M11—M14（归口单位/标准状态/关键词/国际对应关系）抽取规则。

**已记录的抽取局限（按 §0.3 如实保留，不做数据手术）**
- OCR 丢失的角标（GEN-119 的字母上标）不猜；
- `$^{a}$` 无法判定归属时按普通上标处理并记 issue；
- 源文件确无的元数据字段（如 `replaces`、一致性标识）保持空。

---

## 附：变更记录

- v0.1（2026-09-22）：首版。依据用户裁定"回环功能从最初设计上取消"，
  清点 GB/T 1.1-2020 元素与结构、现有规则与 JSON 落点、缺口与优先级。
