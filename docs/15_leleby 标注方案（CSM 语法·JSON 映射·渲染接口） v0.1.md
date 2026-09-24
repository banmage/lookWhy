# leleby 标注方案（CSM 语法 · JSON 映射 · 渲染接口）v0.1

> 状态：草案，待评审 | 日期：2026-09-22
> 上位裁定：**回环验证功能取消（从最初设计上取消）**；交付口径 = 元数据正确 + 元素与结构全部
> 识别并结构化进 JSON + 从 JSON 正确渲染 PDF 与标准 markdown。
> 输入依据：`docs/07`（CSM 语法 v1.1）、`docs/12`（问题→规则知识库，75 条）、
> `docs/14`（元素与结构清单）、`rules/base/GB_T_1.1-2020/{requirements,extraction-rules}.yaml`、
> `src/leleby_ssir/ssir.schema.json`、`corpus/golden/csm/*.canonical.md`、`out/mineru/*`。

---

> 补充（2026-09-23）：本方案的**输入契约**已落定——抽取阶段产出 `01_extract/<ID>.layout.json`
> （通道清单与体积实测见 `docs/16` §2.3，读取点迁移表见 §3，落地记录见 §14.6）；
> 标注/解析/渲染只读 canonical 与 SSIR，源 PDF 在 MinerU 之后不再读取。
> 另：`metadata.json`（GBT-M01—M14）尚未实现，仍按 `docs/16` §2.4 的口径执行。

## 0. 决策与总原则

### 0.1 七条总原则

| # | 原则 | 依据（教训来源） |
| P1 | **两套格式分离**：`canonical CSM`（面向机器，允许非 markdown 语法的块级指令）与 `render.md`（面向阅读，只用 CommonMark+GFM 子集）由 **SSIR JSON 单向派生**，二者之间不存在往返 | 本次用户裁定；render.md 里残留 CSM 指令导致阅读器无法解析 |
| P2 | **一个结构一种写法**；同一字符序列不得有两种解释 | `$^{a}$` 既当角注又当数学上标；`>` 同时承载注/示例/警示/引文 |
| P3 | **判据单源**：每种结构的识别判据只有一份实现（`parser.py`），builder/渲染端只消费解析结果 | docs/12 §3.60「术语行判据在 parser 与 builder 各写一份」 |
| P4 | **排版不进 CSM**：字隙、字号、行距、缩进、列宽一律由渲染 profile 与渲染层决定 | GBT-B04/B12 的固定字隙、GEN-071/074/075 |
| P5 | **归属与锚点显式**：渲染与本体需要的关联必须在 JSON 有字段；判不出来就报 issue，不猜 | §0.3；渲染端 `_is_figure_note_shape`、`_recover_table_note_markers` 的存在就是反例 |
| P6 | **显式声明优先于几何推断**：版式类信息（框、并列、页起止）以手工声明为正式通道，几何识别只作补全 | docs/12 §3.32、§3.36 |
| P7 | **幂等**：写侧生成与读侧判据同规；任何回放工具重复执行逐字节稳定 | CSM-TABLE-004（写侧二次转义）；GEN-114 回放 |

### 0.2 本方案要解决的三个"同形歧义"

| 歧义 | 现状 | 本方案 |
| `$^{a}$` | 表内角注与数学/单位上标同形（GEN-119 合并写法换来的代价） | 角注改用 `[foot:a]`；`$^{…}$` 只表示数学上下标 |
| `> 注：…` / `> 示例：…` / `> 警示：…` / 引用 | 四种块共用 blockquote，靠前缀文字判型 | 保留写法（标准要求印出这些词），但**判型唯一由前缀正则决定**并落 JSON `noteKind`；无前缀的 `>` 一律 `quote` |
| `—— 条目` | 列项破折号与版式对齐线/破折号连接号同形 | 列项组由 `<!-- ssir:list -->` 显式声明括起，组内的 `——` 才是 marker |

---

## 1. 分层与数据流

```
源 PDF ──MinerU──▶ raw ──normalize──▶ canonical CSM ──parse──▶ SSIR JSON ──┬─▶ render.pdf
（人工 curation 也直接产出 canonical）                    （唯一真值）      ├─▶ render.md（标准 markdown 投影）
                                                                            ├─▶ metadata.json（本体阶段输入）
                                                                            └─▶ 校验报告（结构/注/引用/合规）
```

- **CSM 是输入语法，不是交付物**：它只保证"可确定性解析、可人工最小编辑、幂等"。
- **SSIR JSON 是唯一真值**：渲染端、markdown 投影、本体阶段都只读 JSON。
- **回环链（render.md → parse → verify）取消**：不再有任何"从渲染产物回读"的路径。

---

## 2. 语法总表

### 2.1 行内标记（inline，出现在文本流或单元格内）

| 标记 | 语义 | 出现位置 | JSON |
| `[foot:1]` | **页脚注**引用点（label `1`…，全文连续，落页脚） | 正文句末 | `notes[]{type:footnote, label, anchorKind:page, ownerRef}` |
| `[foot:a]` | **图表脚注**引用点（label `a`…，逐表/逐图编号） | 表内单元格 / 图内 | `notes[]{type:footnote, label, anchorKind:tableCell\|figurePart, ownerRef}` |
| `[foot:a、c]` | 同格多角标（保留源角标字符序列） | 同上 | `labels: ["a","c"]` |
| `$^{…}$` `$_{…}$` | **纯数学/单位**上下标（不再承载注） | 任意 | `textContent` 原样 |
| `$…$` | 行内公式（LaTeX） | 任意 | `textContent`；表格单元格按 GEN-097 归一 |
| `**…**` `*…*` `***…***` | 黑体 / 斜体 / 粗斜体（成对星号簇，未成对按字面） | 任意 | `richText/TextSpan{fontStyle}` |
| `[来源：GB/T 20000.1—2014,5.2]` | 术语条目来源（**保留标准原文方括号写法**，不是链接） | 术语条目末 | `TermSource{raw, targetRef?}` |
| `<br>` | 单元格内强制换行（仅表格单元格） | 表格 | `TableCell.text` 内换行 |

**不采用** `[note:…]` 作为行内标记：GB/T 1.1 的「注」（GBT-X03）**没有引用点**——它是排在属主之后的独立块；
引入行内引用点会把"注"与"脚注"（GBT-X04，标记与解释成对）两族混同。注块的机器识别用块级声明（§3.9）。

### 2.2 块级指令（block directives，独占一行，前后必须有空行）

| 指令 | 状态 | 语义 | JSON |
| `<!-- ssir:table id= header-rows= unit= -->` | 保留 | 表开始 | `Table` |
| `<!-- ssir:table-merge table= row= column= rowspan= colspan= -->` | 保留（**位置固定到表格行之后、空行分隔**） | 合并单元格 | `TableCell{rowspan,colspan}` |
| `<!-- ssir:figure id= asset-status= caption= -->` | 保留 | 图 | `Figure` |
| `<!-- ssir:formula id= asset-ref= -->` | 保留 | 公式 | `Formula` |
| `<!--ssir:foot:LABEL owner= scope=-->…<!--ssir:/foot-->` | **扩展**（原有无属性形态兼容） | 脚注注文定义（页/表/图同型） | `notes[]{type:footnote, text, ownerRef, scope}` |
| `<!-- ssir:list kind= level= terminator= intro= -->` | **启用**（docs/07 §6.2 已声明但解析器未实现） | 列项组开始 | `list[]` + `ListGroup` |
| `<!-- ssir:note kind= label= owner= -->` | **新增**（可选声明） | 注块归属（注文紧随其后） | `notes[]{type:note, ownerRef}` |
| `<!-- ssir:toc -->` … `<!-- ssir:/toc -->` | **新增** | 目次区块 | `TocEntry[]` |
| `<!-- ssir:formula-vars formula= -->` | **新增** | 式中变量解释组 | `Formula.explanationGroup` |
| `<!-- ssir:figure-legend figure= -->` | **新增** | 图中标引序号说明（"图中：1——…"） | `Figure.legend[]` |
| `<!-- ssir:figure-sub figure= label= -->` | **新增** | 分图题注分条 | `Figure.subCaptions[]{label,text}` |
| `<!-- ssir:box style=frame\|shaded -->` … `<!-- ssir:/box -->` | 保留 | 显式框 | `box/boxStyle` |
| `<!-- ssir:columns widths= -->` / `column` / `/columns` | 保留 | 并列组 | `sideBySide*` |
| `<!-- ssir:unknown type-hint= -->` + 围栏块 | 保留 | 原样块 | `UnknownContent` |
| `<!-- ssir:block id= -->` | 保留（可省） | 稳定块 ID | `sourceAnchors` |

### 2.3 结构语法（纯文本形态，保留）

| 结构 | 写法 |
| 文件名称 | `# <title>`（唯一 H1，与 front matter `title` 一致） |
| 章 / 条 | `## 1 范围` / `### 4.1 环境条件`（编号+空格+标题；无标题条可只写编号） |
| 附录 | `## 附录 A（规范性） 标题`；附录内 `### A.1 标题` |
| 段 | 普通段落 |
| 表 | `**表N 表题**` + GFM 表（列数一致，`\|` 转义，空单元格一字线） |
| 图 | `![图N 图题](assets/…)`；缺资产 → 指令 `asset-status="missing"` + `**图N 图题**` 题注段 |
| 公式 | `$$ … $$` + 独立行 `式(N)` |
| 注块 | `> 注：…` / `> 注1：…`（块内首行前缀即判据） |
| 示例 / 警示 | `> 示例N：…` / `> 警示：…` |
| 引文 | `> …`（无前缀） |
| 术语条目 | 编号行 + 术语行 + 定义段（见 §3.5） |
| 式中解释行 | `变量——解释；`（末项句号；字隙由渲染层实现，CSM 不写空格） |

### 2.4 与本轮用户提案的差异

| 用户提案 | 本方案 | 理由 |
| 正文注/表注/图注用 `[note:1]` 行内标记 | 注块用 `> 注N：…` + 可选 `<!-- ssir:note -->` 归属声明 | 注（GBT-X03）在源文件里**没有引用点**，加行内标记等于凭空造锚点（违 §0.1/§0.3）；行内 `[note:…]` 会把注族与脚注族混同 |
| 图表角标沿用 `$^{a}$` | 图表角标改用 `[foot:a]`，`$^{…}$` 归数学 | 二者语法同形无法判据区分（GB/T 语料中单字母上标也出现在数学里） |
| 脚注 `[foot:a]` + 定义指令对 | 保留，并把"图表脚注"一并纳入同一语法（靠 `owner`/`scope` 区分锚点） | GBT-X04 里页脚注与图表脚注**同为脚注族**，区别只在锚点与编号作用域 |
| 通用上下标保留 `$^{a}$` | 保留，但仅限数学/单位语义 | 与上一条配套：语义边界一旦划清，判据就不再依赖上下文猜测 |

---

## 3. 逐元素标注规格

图例：**保留**＝不改；**扩展**＝兼容旧写法新增属性；**替换**＝旧写法退役（报 issue + 回放迁移）；**新增**＝新语法。

### 3.1 元数据（front matter）

| 项 | 现写法 | 新写法 | JSON |
| 标识/标题/日期/机构/分类号/一致性 | front matter 现有字段 | 保留 | `metadata.common/standard` |
| 归口单位 / 技术委员会 | 无 | 新增 `technical-committees: ["SAC/TC286"]`（同时必须出现在正文"前言"中，docs/07 §4 既有要求） | `standard.technicalCommittees[]` |
| 标准状态 | 无 | 新增 `standard-status: published\|revised\|withdrawn` | `standard.status` |
| 关键词 / 技术领域 | 无 | 新增 `keywords: [...]` | `standard.keywords[]` |
| 国际对应关系 | 无（只有一致性标识） | 新增 `international-relation: {type: equivalent\|modified\|not-equivalent, document: "ISO/IEC Directives, Part 2"}` | `standard.internationalRelation` |
| 发布/实施日期、机构、起草单位 | 有 front matter | **同时保留正文要素中的出现**（不变） | 同前 |

### 3.2 标题与层次

| 项 | 现写法 | 新写法 | 判据（单源） | JSON |
| 文件名称 | `# title` | 保留 | H1 唯一 | `documentType` + `title` |
| 章/条 | `#{2..6} 编号 标题` | 保留 | `HEADING_RE` + `_bare_heading_candidates`（GEN-117：编号后可为空白或直接接标题文字） | `StructuralNode{nodeType, number, title, level}` |
| 附录 | `## 附录 A（规范性） 标题` | 保留；**新增显式作用域属性**（可选）：`<!-- ssir:annex letter="A" status="normative" -->` | `ANNEX_HEADING_RE` | `annex` 节点 + `annexScope{letter, status}` |
| 部分（第 N 部分） | 标题字符串 | 保留 | `_PART_TITLE_RE` | `standard.partNumber` |

### 3.3 段落

保留普通段落；`**…**`/`*…*` 语义见 §3.14。同一段落内换行按软换行归一（docs/07 §3.3 不变）。

### 3.4 列项组（本轮重点之一）

**现写法**（两种并存，判据靠幸存 marker 猜）：

```markdown
a） 海拔：不超过 1000 m；
b） 环境温度：-20℃～+60℃；
```

**新写法**（组显式声明 + 条目逐行原样）：

```markdown
电机在下列条件下应能正常工作：

<!-- ssir:list kind="alpha" level="1" terminator="period" intro="ssir:.../content/…" -->
a） 海拔：不超过 1000 m；
b） 环境温度：-20℃～+60℃；
c） 相对湿度：5%～95%（无凝露）。
```

规则：

- `kind`（第一层次）：`dash`（`——`）/ `alpha`（`a）`）；第二层次 `dot`（`·`）/ `numeric`（`1）`）——
  与 GBT-B04、GBT-H06 一一对应；`level` 取 1|2（GB/T 1.1 对列项细分不宜超过两层）。
- 条目行 = **原 marker + 文本 + 终止符**：marker 原样保留（不归一为 `-`），终止符保留在行尾；
  `terminator` 属性声明末项终止符（GB/T H06：末项以句号结束），解析时校验，不符报 issue。
- `intro`（可省）：引语段落 id；缺省绑定**紧邻前一块**，并把绑定结果写入 JSON（`introRef`）与报告。
- 组内**不得有空行**（空行会打断组）；需要保留的分条用 `level="2"` 的嵌套组表达。
- 与 markdown 列表的关系：GFM 无法保留 `a）`/`——` 等 marker，故 CSM 一律用本指令，
  与 docs/07 §6.2 既有规定一致（该规定此前只在文档里，解析器未实现 `ssir:list`）。

JSON：`ContentElement{presentationType:list, listRef}` + `ListGroup{kind, level, introRef, terminator, items[{marker, markerType, text, terminator, subItems}]}`。

### 3.5 术语条目与来源（本轮重点之二）

**现写法**（两种抽取形态并存，判据在 parser 与 builder 各一份，见 docs/12 §3.60）：

```markdown
3.1.1                       ← 裸编号段落形态

标准化文件　standardizing document

通过标准化活动制定的文件。

[来源：GB/T 20000.1—2014,5.2]

#### 3.1.2 标准 standard   ← 标题形态（术语与英文挤在标题里）
```

**新写法**（编号行与术语行分离，术语/英文拆成字段）：

```markdown
#### 3.1.1
标准化文件　standardizing document

通过标准化活动制定的文件。

[来源：GB/T 20000.1—2014,5.2]
```

规则：

- 条目编号**独占一行、单独成块**（GBT-FM4：条目编号顶格单独占一行），标题深度 = 该条目所属层次；
- 紧随其后的首个段落 = **术语行**：`术语 + 一个全角空格 + 英文对应词`（英文可缺）；
- 之后依次：定义段 → 符号段 → 图/公式 → 示例 → 注 → 来源行；
- `[来源：…]` 必须是**独立段落**且位于条目末尾（新增告警：出现在条目中部时按 CSM-OCR-007 报出）。

JSON：`StructuralNode{nodeType: item, term, englishTerm}` + `ContentElement{definition}` + `TermSource{raw, targetRef}`。

### 3.6 表

| 项 | 写法 | 变更 |
| 表开始/题注/表体/单位/续表 | `<!-- ssir:table … -->` + `**表N 题题**` + GFM 表；`unit` 属性；续表由渲染层按 GBT-B13 生成 | 保留 |
| 表头行数 | `header-rows` = 表头区几何跨度（GEN-114） | 保留 |
| 合并单元格 | `<!-- ssir:table-merge … -->` | **位置收紧**：必须紧跟表格最后一行之后、**前后各一空行**（现写法紧贴表行，会被 GFM 解析器吞成表格数据行） |
| 单元格换行/竖线/空位 | `<br>` / `\|` / 一字线 `—` | 保留（CSM-TABLE-004：写侧与读侧同一转义判据） |
| 表内角标 | `径向间隙$^{a、c}$` | **替换**为 `径向间隙[foot:a、c]` |
| 表脚注注文 | 表内合并末行单元格 或 表后文本行 | **替换**为定义指令：`<!--ssir:foot:a owner="tbl-003" scope="table"-->径向间隙指……<!--ssir:/foot-->` |
| 表注（`注：`） | 表后的 `> 注：…` 块 | 保留；可选 `<!-- ssir:note kind="table" label="1" owner="tbl-003" -->` 声明归属 |
| 表内图 | 图块折进单元格 | 保留 |

### 3.7 图

| 项 | 写法 | 变更 |
| 题注 / 资产 / 源尺寸 | `![图N 图题](assets/…)` + `<!-- ssir:figure -->` | 保留 |
| 缺资产 | `<!-- ssir:figure asset-status="missing" -->` + **题注段 `**图N 图题**`** | **替换**（现为 `> [图N …（图片占位）]`，方括号在标准 markdown 里按字面显示） |
| 单位陈述 | 图指令前的独立单位行（GEN-032 扩展） | 保留 |
| 分图题注 | 折进 caption/altText | **扩展**：分图题注写独立行 `a）分图题名`，由 `<!-- ssir:figure-sub -->` 分条 | 
| 图脚注 | 图后文本行 | **替换**为 `[foot:a]` + 定义指令（同表） |
| 图中标引序号说明 | 无处理 | **新增** `<!-- ssir:figure-legend figure="fig-001" -->` + `1——…；2——…。` | 
| 续图 | 渲染层按 GBT-B13 生成 | 保留 |

### 3.8 公式与式中解释组（本轮重点之三）

| 项 | 现写法 | 新写法 | JSON |
| 公式 | `<!-- ssir:formula -->` + `$$ … $$` | 保留 | `Formula{latex, assetRef, number}` |
| 编号行 | `式(N)` 独立行 | 保留 | `Formula.number` |
| 式中变量解释 | 「式中：」段 + 若干互不关联的段落 | **组显式声明**：`<!-- ssir:formula-vars formula="fm-001" -->` 后跟各解释行 `变量——解释；`（末项句号） | `Formula.explanationGroup{introRef, items[{symbol, definition, unit, terminator}]}` |

```markdown
<!-- ssir:formula id="fm-001" -->
$$
\overline{η} = \dfrac{\overline{P}_{2}}{\overline{P}_{1}}
$$
式(1)

<!-- ssir:formula-vars formula="fm-001" -->
$\overline{η}$——传动效率；

$\overline{P}_{1}$——输入端功率算术平均值，单位为千瓦（kW）。
```

- 解析判据仍复用 `FORMULA_VAR_ITEM_RE`（变量 + 破折号 + 解释），但**组边界由指令确定**，
  不再"从公式往后吸收连续段落"；解释行内的单位陈述（`单位为…`）解析为 `unit` 字段。

### 3.9 注与脚注（本轮重点之四）

族谱（严格按 GB/T 1.1 的两族划分）：

```
注（GBT-X03）           块级、无引用点、标签形如「注：」「注1：」
├── 条文的注            排在相关条款/段之后
├── 表的注              排在表内下方、表脚注之上
├── 图的注              排在图中注说明/图脚注之上、图题之上
├── 术语条目的注         条目末尾
└── 示例的注             示例框内

脚注（GBT-X04）         标记与解释成对
├── 条文脚注  [foot:1]    全文连续编号，落"引用所在页"页脚
└── 图表脚注  [foot:a]    逐图/逐表单独编号，落图题之上/表内最下方
```

| 项 | 写法 | JSON |
| 注块 | `> 注：…` / `> 注1：…`（前缀即判据，`NOTE_LEAD_RE`） | `notes[]{type:note, kind, label, text, ownerRef, placement}` |
| 注块归属 | 默认按位置（父节点 + 相邻表/图）；**跨页、被抽取打散、多候选时**必须写 `<!-- ssir:note kind= owner= label= -->` | 同上；`ownerRef` 未确定时记 issue，不猜 |
| 页脚注引用点 | `[foot:1]` | `notes[]{type:footnote, label:"1", anchorKind:page, ownerRef:条款}` |
| 图表脚注引用点 | `[foot:a]`（在单元格/图元内） | `notes[]{type:footnote, label:"a", anchorKind:tableCell\|figurePart, anchors[{tableRef,row,col}\|{figureRef,part}]}` |
| 脚注注文 | `<!--ssir:foot:LABEL owner= scope=-->注文<!--ssir:/foot-->`（独立块，紧随引用所在块之后） | `notes[].text` |
| 编号作用域 | `scope`：`document`（页脚注）/ `table` / `figure`（图表脚注） | `scope` + 渲染端校验连续性 |

**不变更的部分**：条文脚注的现写法（`[foot:N]` + 指令对，GEN-118）完全保留，只增加可选 `owner/scope` 属性。

### 3.10 示例、警示、引文

| 项 | 写法 | 变更 |
| 示例 | `> 示例：…` / `> 示例N：…`；线框用 `ssir:box` | 保留 |
| 警示 | `> 警示：…` | 保留（前缀判据已存在） |
| 引文 | `> …`（无前缀词） | 保留；**新增校验**：`>` 块首无「注/示例/警示」前缀时按引文处理并在报告登记（避免判型漂移） |
| 示例的结构位置 | 附录示例由 `_mark_annex_examples` 标记 | **扩展**：示例节点带 `exampleIndex`（示例N 的 N） |

### 3.11 框、并列组、原样块

全部保留（`ssir:box` / `ssir:columns` / `ssir:unknown`）。新增两条约束：
① 三类指令**前后必须有空行**；② 渲染端不再用"连续 exampleContent 相邻兄弟"启发式推断框边界（docs/12 §3.35 的旧通道），只认显式声明。

### 3.12 清单与目次

| 项 | 现写法 | 新写法 | JSON |
| 规范性引用文件清单 | 连续段落行 | 保留写法；解析为清单条目（文件编号 + 名称 + 括号信息） | `checklists[].entries[{raw, standardNumber, title}]` |
| 参考文献 | 连续段落行（`ref_text` 块，GEN-099） | 保留写法；解析为条目 | `bibliography[].entries[{raw, targetRef?}]` |
| 索引 | 连续段落行 | 保留 | `index[].entries[{term, refs[]}]` |
| 目次 | 段落行 `条目……页码` | `<!-- ssir:toc -->` … `<!-- ssir:/toc -->` 括起 | `TocEntry[]{kind, title, number, pageLabel?, targetRef?}` |

目次页码在渲染时由渲染层按实际分页回填（现渲染端已有预检通道），CSM 里的页码视为**源文件的页码**，
不得与渲染页码混淆（JSON 分开存 `sourcePageLabel` 与 `renderPage`）。

### 3.13 引用与提示（识别，不标注）

正文中的「见 9.5.4」「见表1」「按 GB/T 4942.1」等**不新增语法**——它们是原文，标注会破坏原文。
由 parser 在解析时识别并产出 `Reference[]`（schema 已有定义）：

| 目标 | `targetType` | 判据 |
| 内部条款/附录 | `internalClause`/`internalAnnex` | `见\s*\d+(\.\d+)*` / `见附录\s*[A-Z]` |
| 内部表/图/公式 | `internalTable`/`internalFigure`/`internalFormula` | `见表\s*[A-Z]?\d+` / `见图\s*…` / `见式\s*\(…\)` |
| 外部标准/法规/文件 | `externalStandard` 等 | 标准号正则（复用 GBT-C06 的代号前缀表） |

### 3.14 行内强调与上下标

| 项 | 写法 | 变更 |
| 黑体/斜体/粗斜体 | 成对星号簇（1/2/3），未成对按字面（GEN-108） | 保留 |
| 变量斜体（公式内） | LaTeX 语义 | 保留（渲染规则 GEN-116/122） |
| 数学上下标 | `$^{…}$` / `$_{…}$` | 保留，**语义收窄**：只表示数学/单位 |
| 注角标 | `[foot:a]` | **替换**（原 `$^{a}$`） |
| 单位字隙、量符号正斜体 | 不写进 CSM | 保留（GBT-B12 固定字隙，渲染层实现） |

---

## 4. JSON 映射总表

| 语法 | JSON（新增/修改字段加粗） |
| `#`/`## 1`/`### 1.1`/`## 附录 A（规范性）` | `StructuralNode{nodeType, number, title, level}`；**annexScope{letter,status,scope}** |
| `<!-- ssir:list … -->` + 条目行 | `ListGroup{kind,level,introRef,terminator}` + `listItems[]{marker,markerType,text,terminator,subItems}`（**terminator/intro 新增**） |
| 术语条目 | `StructuralNode{term,englishTerm}` + **definition 段** + `TermSource{raw,targetRef}` |
| `<!-- ssir:table -->` / `table-merge` | `Table{number,caption,unit,rows[]{cells{text,colspan,rowspan,isHeader}}}` |
| `[foot:a]` + `<!--ssir:foot:a …-->` | **notes[]{id,type,label,ownerRef,scope,anchorKind,anchors[],text[root],numberingScope}** |
| `> 注1：…` + 可选 `ssir:note` | **notes[]{type:note,kind,label,ownerRef,text,placement}** |
| `<!-- ssir:formula -->` + `式(N)` | `Formula{latex,assetRef,number}` + **explanationGroup**（PDF 渲染端与 markdown 投影端**同一实现**逐行 `symbol——definition`；投影端把条目粘回「式中：」引入行之后，GEN-126） |
| `<!-- ssir:figure -->` + 图片/题注 | `Figure{number,caption,unit,assetRef,sourceWidth,sourceHeight,preservationStatus}` + **legend[]/subCaptions[]/footnotes[]** |
| `<!-- ssir:figure-legend -->` | **Figure.legend[]{index,text}** |
| `<!-- ssir:toc -->` | **TocEntry[]{kind,title,number,sourcePageLabel,targetRef}** |
| 清单三段（引用文件/参考文献/索引） | **checklists[] / bibliography[] / index[]{entries[]}** |
| 正文引用文本 | **Reference[]{sourceNodeId,referenceType,targetType,rawTarget,resolvedClause?}** |
| `<!-- ssir:box/columns/unknown -->` | `box/boxStyle`、`sideBySide*`、`UnknownContent` |

---

## 5. 判据单源（P3 落地）

现状问题：术语行判据、marker 族判定、表格转义在 parser/builder/渲染端各有一份（docs/12 §3.60、§3.26）。

新方案要求：

1. 所有**结构判据**（标题、列项组、术语条目、注/脚注、表格/图/公式、清单条目、引用模式）
   只在 `parser.py` 实现一次，产出 `Block.kind` + `Block.data`；
2. `builder.py` 只做 `Block → SSIR` 的**字段搬运与注册**，不得再做文本形态判定；
3. 渲染端只读 SSIR 字段，不得读 `textContent` 做正则判型（例外白名单：公式/单位/字隙等排版必需的行内解析）。

---

## 6. 渲染接口与"零推断"清单

渲染端必须停止的启发式（迁移到解析/构建阶段，或删除）：

| 位置 | 现状 | 处置 |
| `pipeline._recover_table_note_markers` | 从源 PDF 文本层反推丢失的表格角标 | **迁移**到 normalize/parse 阶段（GEN-119 的回收通道），渲染阶段不再访问源 PDF |
| `pipeline._cell_note_letters` / `_plain_note_cell_text` | 按字母匹配单元格与注文 | **删除**，改读 `notes[].anchors` |
| `pdf_renderer._is_figure_note_shape` | 按 `^图\d+` 文本形状猜"这是图注" | **删除**，改读 `notes[].kind/ownerRef` |
| `pdf_renderer._is_table_caption_shape` | 按文本形状猜表题 | 同上（表题由 `Table.caption` 提供） |
| 渲染端按 `>` 前缀判注/示例/警示 | 已在 parser 判定 | 保留（parser 已落 `presentationType`） |
| `pdf_renderer._footnote_superscripts` 的行首字母猜测 | 按「字母 + 汉字」文本形状猜脚注标记（结构化注文行已改走 `_note_line_marker_supers`，判据为 `[foot:…]` 与 `notes[].anchorKind`） | 本次只更正标记**字面**（GEN-137：字母族不补右括号）；猜测通道仍保留，删除需先确认无段落形态的脚注定义到达渲染端 |

新增断言（回归夹具）：渲染输入中缺 `notes[].ownerRef`、缺 `Table.caption` 等必填关联时**必须报错**，
不得回退到启发式——这是"渲染端零推断"的可测形式。

---

## 7. render.md 投影规范（P1 落地）

| 结构 | render.md 写法 |
| 元数据 | YAML front matter（机器可读；本体阶段直接消费） |
| 标题 | `#`…`######`（层级 = 结构层级 + 1） |
| 段落 | 普通段落 |
| 列项组 | GFM 列表：`- a） 海拔：…；`（marker 进项内文本，保持原文可见）；第二层次缩进一级 |
| 术语条目 | 独立小节：编号 + 术语行（加粗）+ 定义段 + 来源段 |
| 表 | `**表N 表题**` + GFM 表（合并单元格留空）；单位行紧随题注 |
| 图 | 有资产 `![图N 图题](assets/…)`；无资产 `**图N 图题（图片占位）**` |
| 公式 | 围栏代码块 ```text + `式(N)` 段落；式中解释组按 `变量——解释；` 逐行 |
| 注 | 引用块 `> 注1：…`（与源版式一致，且是合法 markdown） |
| 图表脚注 | 独立段落 `a）注文`，紧随表/图；**表脚注**（`notes[].anchorKind == tableCell`）例外——并入**表末通栏行**（多注 `<br>` 相连，GB/T 1.1 10.4.2.2/10.4.4.2，GEN-131），正文流里不再单独出现 |
| 页脚注 | 独立段落 `1) 注文`，紧随引用所在段 |
| 示例/警示 | 引用块 `> 示例：…` / `> 警示：…` |
| 并列组 | 列顺序输出为连续块（markdown 无并列语义），列间加分隔注释以外的空行；框线/分栏等 md 子集表达不了的形态另由 `render.html` 承载（GEN-130） |
| 原样块 | 围栏代码块 |
| 上下标 | 保留 `$^{…}$`（markdown 无上标语法） |
| 硬约束 | ① 零 `ssir` 指令、零 HTML 注释（除 front matter）；② 块间必须有空行；③ 只用合法 GFM 列表 marker。伴生产物 `render.html` **不受**此硬约束（它就是为承载 md 表达不了的结构而存在），但必须与 md 同源同判据 |

---

## 8. 校验规则与 issue 码

| 校验 | 内容 | 失败处理 |
| 注/脚注一一对应 | 每个 `[foot:L]` ↔ 恰好一条同 label 定义；无引用点的定义、无定义的引用点均报错 | 阻断渲染（新闸门，替代回环） |
| 编号作用域 | 页脚注 1..n 连续；图表脚注逐表/逐图 a,b,c 起编且连续 | 记 issue；不自动改号（§0.3） |
| 注归属 | `kind/ownerRef` 必须可确定；`ssir:note` 声明的 owner 必须存在且类型匹配 | 报错，不猜 |
| 锚点可定位 | `anchors[].row/col` 在表范围内；`figureRef/part` 存在 | 报错 |
| 列项组 | `intro` 存在且以 `：`/引语句式收尾；条目 marker 族与 `kind` 一致；末项终止符 = `terminator` | 记 issue |
| 术语条目 | 编号行独立；术语行紧随；来源行在条目末 | 记 issue（CSM-OCR-007 扩展） |
| 引用 | 每个 `Reference` 能解析到目标（内部）或标准号格式合法（外部） | 记 issue |
| 元数据 | M01—M10 逐字段对照源 PDF 封面文本层：存在性、格式、与 JSON 一致 | 记 issue + 报告 |

新 issue 码（待登记 docs/12 §5.3）：

| 码 | 含义 |
| CSM-STRUCT-010 | 图表角标使用已退役的 `$^{a}$` 注写法（提示改写 `[foot:a]`） |
| CSM-STRUCT-011 | 定义的 label 与引用点不匹配（缺定义/悬空定义） |
| CSM-STRUCT-012 | 注块归属不可确定（需写 `ssir:note` 声明） |
| CSM-STRUCT-013 | 列项组缺少 `ssir:list` 声明而按裸 marker 行解析（宽容继续并记 issue） |
| CSM-STRUCT-014 | `table-merge` 指令位置不合规（紧贴表行，存在被解析器吞行的风险） |

---

## 9. 迁移与回放

1. **迁移对象**：`corpus/golden/csm/*.canonical.md`（5 份手写基线）+ `out/*/*/02_canonical/*.canonical.md`（9 份抽取产物）。
2. **迁移方式**：按 §0.4（AGENTS.md）"先规则后数据"——先落解析/校验规则与新 issue 码，再用回放工具做
   **确定性实例回放**：`tools/replay_note_footnotes.py`（`$^{a}$` → `[foot:a]` + 定义指令）、
   `tools/replay_list_groups.py`（裸 marker 行 → `ssir:list` 声明）。
3. **回放判据**（每个工具必须同时满足）：
   - 只改**语法形态**，不改任何文本字符（角标字符、marker、终止符原样保留）；
   - 幂等：二次执行逐字节相同；
   - 命中归零：回放后重 parse，对应 issue 码命中数为 0；
   - 干净夹具零命中（不误伤数学上标：无同 label 注文的 `$^{a}$` 一律不动）；
   - 无法判定的实例**不猜**，列入人工清单。
4. **兼容期**：解析器对旧写法报 issue 但**宽容继续**（`$^{a}$` 仍按角标处理、裸 marker 行仍按列项处理），
   使旧产物在迁移完成前仍可渲染；迁移完成后由 `--strict` 关闭兼容。

---

## 10. 实施顺序与影响面

| 阶段 | 内容 | 影响文件 |
| P0-1 | schema 增补（notes/ListGroup/TocEntry/Reference/术语来源/元数据新字段） | `src/leleby_ssir/ssir.schema.json`、`docs/02` |
| P0-2 | 解析器新语法实现（`ssir:list`、`[foot:a]`、`ssir:note`、`ssir:formula-vars`、`ssir:toc`）+ 单源判据整理 | `parser.py`、`builder.py` |
| P0-3 | 校验层（注一一对应、作用域、锚点、引用） | `compliance.py`、报告 |
| P0-4 | 渲染端改造（读新字段、删除 4 处启发式、渲染闸门） | `pdf_renderer.py`、`pipeline.py` |
| P0-5 | render.md 标准 markdown 投影（新模块 `markdown_projection.py`，替代 `csm_renderer` 的 render.md 用途） | 新模块 + 构建流程 |
| P0-6 | 回环下线（CLI `ssir csm roundtrip`、`roundtrip.py`、`05_verify`、`verify_conversion` 回环部分、`verify_markdown_roundtrip.py`、依赖它的单测） | `cli.py`、`pipeline.py`、`service.py`、`tools/*`、`tests/*` |
| P1 | 回放工具 + 双层语料迁移 + 跨语料验证 | `tools/replay_*.py`、`corpus/`、`out/` |
| P1 | 元数据 M01—M10 校验程序 | 新工具 `tools/verify_metadata.py` |
| P2 | 解释组、图 legend、清单/目次/引用结构化 | parser/builder/schema |
| P2 | 元数据 M11—M14 抽取规则 | 规则包 + parser |

**注**：`csm_renderer.render_csm` 在回环下线后仍被单测用作"SSIR → CSM 写回"夹具；本方案要求把它降级为
**测试夹具专用**（不产出交付物），或随单测改造一并移除（详见 §11 待决项）。

---

## 11. 待决项（需用户裁定）

1. **`Table.notes` 与旧 `tableNote` 的关系**：新字段直接替换（旧字段标 deprecated 只读）还是保留双写？
2. **术语条目新写法**是否要求全量迁移（现两种形态并存），还是解析器继续宽容两种、新产物统一写新形态？
3. **`ssir:list` 是否强制**：宽容期允许裸 marker 行（记 issue），迁移完成后是否拒绝？
4. **`csm_renderer` 去留**：改为测试夹具，还是完全删除（单测改为直接断言 SSIR）？
5. **页脚注的锚点粒度**：是否需要细化到"句/段"（现在到条款级 `footnoteAnchorRef`）？

---

## 附：与 docs/12 知识点的对应（本方案为什么这样设计）

| docs/12 记录 | 对本方案的影响 |
| §3.22 / §3.30（表注标记两次改形） | 标记族反复改版说明"写法简洁"不能优先于"语义可判"；故本轮把脚注/注/上下标三者语义边界一次划清 |
| §3.60（术语行判据两份） | 促成 P3 判据单源 |
| §3.26（写侧二次转义） | 促成 P7 幂等与读写同规 |
| §3.32 / §3.36（框、并列改用显式声明） | 促成 P6 显式声明优先 |
| §3.54（图单位行折进图节点） | 属主绑定必须落 JSON 的正面案例 |
| §3.67 / §3.74（续表表头、回放被覆盖） | 回放必须幂等且可重复执行 |
| §3.71（脚注/角注改形） | 本条被本方案部分取代（图表脚注并入 `[foot:…]` 同族） |

---

## 附：变更记录

- v0.1（2026-09-22）：首版。基于用户裁定（回环取消）与"重新统筹策划标注方案"的要求，
  给出两套格式分离、七条总原则、语法总表、逐元素规格、JSON 映射、渲染零推断清单、校验与迁移方案。
