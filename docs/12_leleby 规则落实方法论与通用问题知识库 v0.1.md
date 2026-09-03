# 12. leleby 规则落实方法论与通用问题知识库 v0.1

> 状态：生效（v0.1，2026-08-31）
> 适用：lookWhy / leleby SSIR Engine 的全部开发、维护与验证活动
> 目的：本文档**独立于任何 AI 工具（Hermes skill 等）**，沉淀本项目的规则化
> 方法论与通用问题解决记录，保证知识离开特定 harness 后仍可正确执行。
> 关联文档：03（流水线架构）、11（规则目录布局）、PROJECT.md（开发说明）。

---

## 1. 规则落实方法论（元规则）

### 1.1 两条基本原则

1. **标准有规定的 → 落实到具体规则的执行与验证。**
   凡 GB/T 1.1-2020（或具体标准）有明确条款的问题，必须：
   - 在需求规则 `rules/base/GB_T_1.1-2020/requirements.yaml` 中落实规则
     （规则 ID `GBT-*`，`source` 字段标注标准原文章节号以便追溯）；
   - 在解析/渲染代码中**执行**该规则（源码注释 `规则对应: GBT-XXX` 映射）；
   - 在 `src/leleby_ssir/compliance.py` 中实现**机器验证**，并配回归测试。

2. **标准没有具体规定的 → 经过确认且具有通用性的问题，补充到通用规则。**
   工程实践类问题（工具链缺陷、OCR 损坏特征、格式宽容处理等）若通过
   **通用性确认**，则写入 `rules/base/GB_T_1.1-2020/extraction-rules.yaml`
   （规则 ID `GEN-*`，`gbt11-ref` 字段标注对应标准章节，标准无对应处标"—"）。

### 1.2 通用性确认标准（什么问题值得入 GEN-* 规则）

只有**全部**满足才写入通用规则：

- **根因通用**：根因是工具链/格式/文本层的通用缺陷，不是单份文件的特例；
- **修复通用**：修复逻辑不依赖具体标准的专有文本（如不写死"某某标准第 X 条"）；
- **可复现**：同类问题预期在其他标准 PDF 上复现（语料库已有多份文件命中
  或根因分析可推得必然复现）。

不满足者（单份文件特例）只记入对应报告的 issue，不入规则。

### 1.3 问题 → 规则 → 执行 → 验证闭环

```
发现缺陷（流水线失败 / 渲染错 / roundtrip 差异 / 合规发现）
  → 定位根因（区分三层：源 PDF 文本层损坏 / MinerU 工具缺陷 / 本引擎缺陷）
  → 查标准原文：requirements.yaml 有对应 GBT-* 条款吗？
       ├─ 有 → 细化该规则条款（标注 source 章节）
       │        解析/渲染代码实现（源码注释 规则对应: GBT-XXX）
       │        compliance.py 增加机器检查（新 code 值）
       │        tests 增加回归用例
       └─ 无 → 按 §1.2 做通用性确认
                 ├─ 通过 → extraction-rules.yaml 新增 GEN-XXX（gbt11-ref 标 "—"）
                 └─ 不通过 → 报告 issue 记录，不入规则
  → 验证：unittest 全绿 + 流水线重跑（exit 0 + roundtrip passed）
           + 渲染产物抽查（字体/字号/位置按 PDF 内部对象验证，非视觉比对）
  → 知识沉淀：本文档 §3 追加问题解决记录（现象/根因/修复/规则化/验证）
```

### 1.4 规则文件与执行/验证层

| 层 | 文件 | 内容 | 执行者 |
|---|---|---|---|
| 需求规则 | `rules/base/GB_T_1.1-2020/requirements.yaml` | GBT-*，标准有明文规定的要求（内容/结构/排版） | — |
| 通用规则 | `rules/base/GB_T_1.1-2020/extraction-rules.yaml` | GEN-*，工程实践规则（stage: extract/merge/normalize/build/render/verify） | — |
| 规则执行 | `src/leleby_ssir/`（parser.py、pdf_renderer.py、builder.py、mineru_html.py、csm_renderer.py 等） | 每条处理逻辑以注释 `规则对应: XXX` 映射规则 ID | 流水线 |
| 规则验证 | `src/leleby_ssir/compliance.py` | 机器检查 GBT-*/GEN-*，结果写入 parse-report.json 的 `compliance` 字段（appliedRuleSets / findingCount / findings / passed） | parse 阶段 |
| 回归保障 | `tests/test_compliance.py`、`tests/test_pdf_renderer.py`、`tests/test_csm_to_ssir.py`、`tests/test_pdf_extractor.py` | 每个修复至少一个回归用例 | `python -m unittest discover` |

---

## 2. 问题 → 规则映射总表（2026-08-31 集中审计）

本表是本会话（GB_T_1.1-2020 渲染修复 + GB_T_43726-2024 OCR 重抽）全部问题
的规则化结果，也是 §1 方法论的实例。

| # | 问题现象 | 根因 | 修复位置 | 规则 ID | 验证 |
|---|---|---|---|---|---|
| 1 | 快捷模式传 `GB_T_1.1-2020` 报 "file not found (looked for …GB_T_1.pdf)" | `Path.with_suffix(".pdf")` 把标准号中 `.1-2020` 当后缀替换 | `tools/mineru_full_standard.py` L1194-1199 整体拼 `f"{args.file}.pdf"` | GEN-001（不猜测文件名，输入须存在） | 各形态解析：GB_T_1.1-2020 / 带.pdf / T_ZZB_2224-2021 / DB11_T_1000.1-2020 / 子路径 |
| 2 | 渲染 LayoutError：Flowable 含 PageBreak，tallest row 72000pt | 文后要素被标 exampleContent 且 PageBreak 被打包进示例箱表格 | `builder.py` `_mark_annex_examples` 遇文档级标题退出附录模式；`pdf_renderer.py` `_strip_pagebreaks` 示例箱入表前剔除 PageBreak（两处打包点） | GEN-093（文后/前置要素是文档级要素） | 81 页渲染成功、零警告；回归测试 test_back_matter_after_last_annex_not_marked_example_content |
| 3 | 条号掉点：4.2.1→421、7.4.2→742、5.10→510 | 源 PDF 文本层损坏，MinerU auto 抽取逐行丢点 | `parser.py` `_repair_clause_numbers`（编号连续性约束拆点，无法安全恢复不猜测记 issue CSM-OCR-002） | GEN-031 更新；GBT-H03 新增父号前缀校验（clause-prefix-mismatch） | 4/4.1/4.2/4.2.1/4.2.2 全部正确；compliance 对损坏输入命中 |
| 4 | 第 2 章规范性引用标准号丢失（"/ — 环境试验 第 部分:…"） | 文本层损坏，拉丁/数字整段丢弃 | `--method ocr` 强制整本重抽；`mineru_full_standard.py` 新增 `_detect_broken_text_layer` 自动检测损坏特征 | GEN-092（文本层质量预检强制 OCR）；GBT-C06 新增引用条目标准号检查（reference-item-number） | OCR 重抽后 GB/T 2423.16—2022 等全部恢复；compliance 对缺编号条目命中 |
| 5 | 表题注被抽成 directive 前普通段落 → 渲染双题注「表4 题名」+「表4」 | normalize 未把题注并入 table block | `parser.py` 段落形态题注折叠（与 heading-shaped 同走 pending_table_caption，合并时校验 caption-number 一致防误并） | GEN-032 更新（题注折叠 + 防双题注）；GBT-B08（题注形如"表X 题名"） | 表4 caption 带题名、正文残留段落消失、其余表不受影响 |
| 6 | "单位为毫米/毫安"单位行位置/样式不符 | 单位陈述未按规定渲染 | `parser.py` 单位行折进 `table.unit` 属性；`pdf_renderer.py` 渲染小五号(9pt)右对齐紧贴表格 | GEN-032 更新；GBT-B07（单位陈述位于表题之下右上方小五号宋体） | 各表题注 y 615→631.9 等（单位行在题注下 16.9pt），x≈526.9 贴版心右缘 |
| 7 | 表内 A/B/C 相（相位字母）被误上标 | `_table_cell_superscripts` 把大写行首字母当脚注标记 | 只上标**小写**行首标记（排除单位与 ")"） | GBT-X04（图表脚注用小写拉丁字母上标） | 表6 A/B/C 相 9pt 单 span 不上标 |
| 8 | 正文/图脚注标记未上标（脚注成对要求） | 脚注标记与解释行渲染为普通文本 | `pdf_renderer.py` 重构 `_footnote_superscripts` 接入正文段落分支；标记规则：行首"a 说明"/"a说明"、句末标点后（含 \n 合并段）标记、全角小写；**不做**汉字后半角小写（防误伤"转速n，"/"a)中所述"） | GBT-X04 更新（标记与解释成对、均小写）；compliance 新增解释行标记大写检查（footnote-marker-lowercase） | 附录E 图脚注 a/b 8.5pt 上标+10.5pt 正文；正文段落含合并段用例通过 |
| 9 | 渲染 LayoutError：tallest row 16,777,221pt（≈2^24），示例箱表格 cell 含 KeepTogether | 图+图题被 `_append_content` 包成 reportlab `KeepTogether`，其 `wrap()` 恒返回 0xffffff（强制拆分哨兵）；示例箱单列表格每 flowable 一行 → 该行 ~16.7M pt 超帧高 | `pdf_renderer.py` `_example_box` 展开 KeepTogether 内容（每子 flowable 单独成行，子内容 PageBreak 剔除） | 工程规则（无标准对应；渲染器 API 限制） | GB_T_20001.6-2017 渲染 14 页零警告、图1/图2 进框；回归测试 ExampleBoxKeepTogetherTests 3 例 |
| 10 | 章条标题被抽成裸段落（无 ## 前缀，QB_T_2946 第 3 章），GBT-H03 误报"缺失 3"、GBT-C06 把标题当引用条目 | MinerU 把章条标题压成普通段落（编号+标题同段） | `parser.py` 裸条号标题提升：祖先链 + 父已提升子级跟随的级联，无确认标题不提升（记录 CSM-STRUCT-001） | GEN-035 新增 | QB_T_2946 3/3.1/3.1.1 恢复标题；parse-report 0 findings（修复前 2 类误报）；单测 3 例 |
| 11 | 章条标题层级全压成同一层 ##（语料 90%+ 层级错，GB_T_1.1 176 个中 166 个） | MinerU 抽取不保留标题层级 | `parser.py` `_repair_heading_levels`：按编号段数提升（章 1 段→##、条 2 段→###…），只提升不降低，文本不变 | GEN-031 更新（记录 CSM-OCR-006） | roundtrip 三侧一致；单测含编号后无空格形态、千分位"1 000 kV"不误升 |
| 12 | 引用条目标准号误报缺号（QB_T_2946 20 条引用全报"缺少标准文件编号"） | `_STANDARD_NUMBER_RE` 前缀只列到 QB，QB/T、HG/T、FZ/T、Q/ 等 20+ 前缀漏识别 | `compliance.py` 前缀扩展 30+ 常见国家/行业/团体/企业代号（长前缀优先，Q/、T/ 代号后允许空白） | GBT-C06 更新 | QB_T_2946 引用不再误报；真缺号（"3 产品分类…"、"/ — 数据元…"）仍正确报；单测 4 例 |
| 13 | 文本层健康但 MinerU 丢拉丁整段（GB_T_15835："GB/T 1.1—2009"→"/ — "，raw 5 处） | MinerU 文本抽取按字体编码丢拉丁/数字，GEN-092 预检的损坏特征覆盖不到 | `mineru_full_standard.py` `_latin_loss_check`：抽取后对比文本层与 raw 标准号提及数（文本层 ≥5 且 raw 不足一半），命中强制 OCR 重抽（复用 previous_method 失效逻辑） | GEN-092 更新 | GB_T_15835 命中（文本层 18→raw 6）；GB_T_1.1/QB_T_2946/T_ZZB_2224/GB_3102.1 不误报；单测三态 |
| 14 | 渲染 LayoutError：示例箱表格 cell 含嵌套示例箱表格（36 行 x 1194pt 撞 688pt 帧高） | 示例文档自身章节树（5→5.1→5.4.1）也是 exampleContent 兄弟，`_append_node` 递归分组再包一层 `_example_box` → Table 套 Table 无法跨页拆分 | `pdf_renderer.py` `_append_node` 对 exampleContent 节点 children 扁平化逐节点追加（不产生嵌套框） | 工程规则（无标准对应；reportlab Table 单元格内 Table 不能拆分） | GB_T_20001.6-2017 渲染 15 页零警告；示例全文（5/5.1/5.4.1/追溯方法…）入框；回归测试 NestedExampleContentTests |
| 15 | 渲染图过大：图2 等按原图比例显示（GB_T_23132-2024 图1 42x76pt 被放大到 126x212pt、图2 卷曲判定图 455x248pt） | ① `_stamp_figure_source_sizes` 用 `ssir_path.parent / ref` 解析 assetRef，而资产在文档根 `assets/`（SSIR 在 03_ssir/ 子目录）→ 所有图都拿不到尺寸；② MinerU 裁剪图以 2-3x 像素密度导出，渲染端按 72dpi 固有尺寸放大；③ 图2 判定图被拆成 a)/b) 子图块，宽高比与整图矩形不符无法匹配 | `tools/mineru_full_standard.py` `_stamp_figure_source_sizes` 重写：祖先目录解析资产；矩形贪心匹配（每矩形只分配一次，防两相似图抢同一矩形）；封面徽标矩形（第 1 页高 <100pt）不参与匹配；无匹配子图回退**文档像素密度**（已匹配 px/pt 中位数，扫描型默认 200/72≈2.78）；表中图同样打标写入 `table.cellImageSizes`；`pdf_renderer.py` 表单元格图按原尺寸（上限单元格宽、不放大）渲染 | GEN-076（渲染图与原图尺寸相当）；GBT-X02 更新（表中图按原尺寸显示） | GB_T_23132-2024 图1 41.6x76.1、图3 169.8x102.5 与源矩形一致；图2 a/b 192.8x87.6/169.8x92.8；表2 六张图中图全部按原尺寸入格；roundtrip 0、15 页零警告；回归测试 FigureSourceSizeStampTests |
| 16 | 表2 中的图没有全部正常显示：旋转式行 试验区域分割 示意图被渲染成两表之间的大幅独立图 | MinerU 跨页表格把某行单元格内的图排在 `<table>` 元素之外，读取顺序上前表 → 裸图 → 续表（题注带"续"） | `parser.py` `_repair_stray_table_images`（CSM-TABLE-002）：前表最后一行既有含图单元格又有不含图单元格时，裸图折回第一个不含图且非首格的单元格并删除游离 figure 块（条件全满足才归位，纯文本行不归位） | 工程规则（GBT-X02 表中图；跨页续表折回） | GB_T_23132-2024 表2 旋转式行 试验区域分割 单元格出现 89e2bc42 图（96.4pt）；roundtrip 0；回归测试 2 例（归位/不误归位） |
| 17 | 表2 行内文字错列 + 说明文字位置颠倒（往复式行 试验区域分割 说明被放到插入角度列；各行第2列 文字在图上方） | MinerU 表格单元格分配：① 某行某列"图+文字"被拆开，文字误归到后一列（该列其它行都是纯图）；② 格内文字排在图标记之前 → 渲染 文字在上图在下，与原文"图在上、说明文字在下"相反 | `parser.py` `_repair_table_image_layout`（CSM-TABLE-003）：B. 列错位启发式——数据行≥2、该列文字仅此一行且是图列、前一格是纯图格 → 文字移回前一列图后，原格只留图（保守条件全满足才移动）；A. 格内顺序仅作为 B 的配套——B 触发的表（含同 caption-number 跨页续表）才统一为图前文字后，其余表严格按提取顺序渲染 | 工程规则（**非通用版式**：图与文字的上下关系是各表原文自行安排，渲染按数据顺序复现；"上图下文字"只是 GB_T_23132 表2 的原文布局） | GB_T_23132-2024 表2 三行第2列全部"图在上文字在下"、第3列纯图；无列错位证据的表保持提取顺序（回归测试验证不重排）；roundtrip 0、15 页零警告；回归测试 3 例 |
| 18 | 表格列宽一律等分（GB_3100-2026 表4 四列各 113.75pt），「与SI单位的关系」列长公式被迫换行 | 渲染端 `_append_table` 用 `455/col_count` 等宽分配，未按内容安排列宽 | `pdf_renderer.py` 新增 `_table_column_widths`（通用规则：列宽 ∝ 列内容自然宽度——CJK≈1em、拉丁≈0.55em、colspan 摊分、通栏注行/单长格不参与、图片按原宽；按比例充满版心宽 455pt，保底 24pt）+ `_cell_text_natural_width`（LaTeX 先经 `_latex_to_text` 拍平再估算，防命令噪声撑大需求）；`_render_cell` 图片按跨列总宽缩放 | GBT-B07 执行侧扩展（表版式：按内容分配列宽、尽量利用版面宽度） | GB_3100-2026 表4 列宽 [51.9,51.9,51.9,299.4]（关系列 ~60%，源 PDF [65.6,65.6,65.5,281.9] 关系列 59% 吻合）；长公式单行完整；4 份语料文档（GB_T_1.1/20001.6/T_ZZB_2224/Q_TQDZ）重渲染无 LayoutError；回归测试 TableColumnWidthTests 4 例 |
| 19 | 无标题条文被误升为标题（GB_T_1.1-2020 附录 B.2.2「这里描述的标记体系适用于下列各类文件。」、9.9.3.1 首句、GB_T_23132-2008 8.1.2；GB_T_20001.5-2017 竟有 8 处句子体标题） | MinerU 把「编号 + 整句条文内容、以句号收尾」的条文抽成标题行；真正的条标题从不以 。！？ 收尾 | `parser.py` `_demote_sentence_headed_clauses`（CSM-OCR-009）：编号开头（章条/附录条）+ 句末标点收尾的标题降级为正文段落，H1 除外 | CSM-OCR-009（parser 修复记录；工程规则，无 GEN 拆分） | 全语料 22 份 canonical 重 parse 命中 12 处全部为真实句子体标题；csm 手写夹具 0 命中；GB_T_1.1 目次不再出现 B.2.2 跳号行；回归测试 2 例（含无编号句子标题不误降） |
| 20 | 编号条文在页边界被断成两个 markdown 段落（GB_T_1.1-2020 9.4.2.2「……与"应"一起」+「使用表示要求……」；GB_T_20001.10 6.7.2.2「警示/用语」、20001.4 6.8.5「半成/品」、QB_T_2946 8.1.1「型/号」等） | MinerU 页边界断行处第一段无任何标点收尾，空行续接的（，、）规则覆盖不到 | `parser.py` `_merge_split_clause_paragraphs`（CSM-OCR-010）：相邻段落块级合并——首段以编号条文形态开头且不以句末/连接标点收尾、次段汉字开头非编号/示例/注/表/图、两侧均非术语行形态（中文 U+3000 拉丁） | CSM-OCR-010（parser 修复记录） | 全语料 22 份 canonical 命中 8 处全部为真实页断续文；GB_T_1.1 9.4.2.2 渲染为连续单段；回归测试 5 例（完整句不并、示例/注/新条文不并、术语行+定义不粘、链式） |

---

## 3. 详细问题解决记录

### 3.1 点分标准号被 Path.with_suffix 截断（GEN-001）

- **现象**：`.venv/bin/python tools/mineru_full_standard.py GB_T_1.1-2020`
  报 `file not found under corpus/golden/: 'GB_T_1.1-2020' (looked for …/GB_T_1.pdf)`。
- **根因**：快捷模式用 `Path(args.file).with_suffix(".pdf")` 补扩展名，
  Path 把"最后一个点"当后缀——`GB_T_1.1-2020` 的 `.1-2020` 被替换成 `.pdf`。
  凡点分标准号（DB11_T_1000.1-2020、GB_T_20001.5-2017）不带 .pdf 传参都会中招。
- **修复**：`tools/mineru_full_standard.py` L1194-1199 弃用 with_suffix，
  改为 `candidate = ROOT / "corpus" / "golden" / f"{args.file}.pdf"`。
- **规则化**：GEN-001（输入必须是存在的 PDF 文件，不合法立即报错，不得猜测文件名）。
- **验证**：GB_T_1.1-2020 / 带.pdf / T_ZZB_2224-2021 / DB11_T_1000.1-2020 / 子路径
  各形态均正确解析。

### 3.2 文后要素误标示例内容 → 渲染 LayoutError（GEN-093）

- **现象**：GB_T_1.1-2020 渲染崩溃
  `reportlab.platypus.doctemplate.LayoutError`（Table 32 rows，含 PageBreak，
  tallest row ≈72000pt）。
- **根因**（双重）：
  1. 扁平树（MinerU 全 `##` 抽取）中 `builder._mark_annex_examples` 的
     `in_annex` 状态在最后一个附录后不退出 → 参考文献、索引、索引字母块
     （B/D/Z）被标 `exampleContent`；
  2. 渲染器把连续 exampleContent 兄弟打包成单列 `_example_box` 表格，
     「参考文献另起一面」的 PageBreak 落在表格内（PageBreak 占满整帧高度）。
- **修复**（双保险）：
  - `builder.py`：扁平树 sweep 遇文档级要素标题（参考文献/索引/目次/前言/引言）
    即退出附录模式；
  - `pdf_renderer.py`：新增 `_strip_pagebreaks`，示例箱入表前剔除 PageBreak，
    接入模块级 `_append_nodes` 与 `make_story` 内联循环两处打包点。
- **规则化**：GEN-093（build stage，must）——目次、前言、引言、参考文献、
  索引是文档级要素；扁平树中最后一个附录之后的这些要素不得被并入附录示例内容。
- **验证**：81 页渲染成功、render-report 零警告；p75 参考文献正常段落、
  p76+ 索引带字母组+点线；回归测试
  `test_back_matter_after_last_annex_not_marked_example_content`。

### 3.3 条号掉点自动修复（GEN-031 / GBT-H03 / CSM-OCR-002）

- **现象**：GB_T_43726-2024 raw 中 `## 742 C组检验`、`## 7421 通则`、
  `## 421 型号结构`（源 PDF 文本层孤立 `4.`/`2.` 分行，MinerU 逐行丢点不一致，
  7.4.2.2 又带点）。
- **根因**：文本层损坏型 PDF，auto 抽取丢点丢数字；与 GBT_23132-2024、
  GB_T_20001.4/20001.10、GB_T_755-2025 同类。
- **修复**（两层）：
  1. 工具 `--method ocr` 强制整本重抽；
  2. `parser.py` 新增 `_repair_clause_numbers`（issue 码 **CSM-OCR-002**，
     001/003-006 已占用）作安全网：用编号连续性约束把纯数字串重新拆点
     （章级连续 1,2,3…；条级 = 父号前缀 + 连续兄弟/子条 .1）。
     无法唯一合法拆点时不猜测（留给 GBT-H03 记录）。
- **规则化**：GEN-031 更新（层次编号规范化 + 掉点修复 + 保守原则）；
  compliance GBT-H03 新增**父号前缀校验**（子条号必须以父号+点为前缀，
  code=clause-prefix-mismatch，7.3.1/7.3.2）。
- **验证**：4/4.1/4.2/4.2.1/4.2.2、5.36.1、6.26.1、7.4.2/7.4.2.1/7.4.2.2
  全部正确。注意该修复是**严格连续**的：中间缺号（夹具漏章）会中断整段修复，
  属保守设计（防臆测）。
- **坑**：修复连续性依赖真实连续编号序列；测试夹具必须真实（补全 2/3/6 章、
  5.2-5.8 后算法才生效）。

### 3.4 文本层质量预检强制 OCR（GEN-092）

- **现象**：文本层损坏型 PDF 用 auto 抽取得到丢行丢点丢标准号的坏 raw。
- **根因**：MinerU 文本抽取对特定字体编码处理不当（拉丁/数字整段丢失、
  条号拆行），不是 PDF 物理损坏；pymupdf 读同一文本层却正常。
- **修复**：`mineru_full_standard.py` 新增 `_detect_broken_text_layer`——
  默认 `--method auto` 时先用 pymupdf 扫源 PDF 前 30 页文本层，命中典型
  损坏特征（孤立 `4.`/`2.` 行 ≥30，或截断标准号 `GB/T2423.` ≥3）就自动改
  `--method ocr`；显式 `--method` 尊重用户选择。已记录方法与当前方法不一致时，
  失效全部 parts **并删除磁盘 parts/** 与 pipeline-state.json 后重抽
  （防 "Markdown exists; state was repaired" 分支绕过重抽；
  注意 previous_method 必须在覆盖 state["parameters"] **之前**读取）。
- **规则化**：GEN-092（extract stage，should）。
- **验证**：语料库实测 GB_T_43726-2024、GB_T_23132-2024、GB_T_20001.4/20001.10、
  GB_T_755-2025 命中；健康文本层（GB_T_1.1-2020、5089 等）与无文本层扫描件
  （JB_T_14054、SJ_T_11859，auto 本就会 OCR）均不误报。

### 3.5 表题注折叠与单位行（GEN-032 / GBT-B07）

- **现象**：表题注「表4 安装配合面的同轴度」被抽成 table directive 前的
  普通段落（可隔"单位为毫米"行）→ 渲染双题注（「表4 题名」+「表4」）；
  单位陈述行位置/字号不符。
- **根因**：normalize 未把段落形态题注并入 table block；单位行未按规范渲染。
- **修复**：
  - `parser.py` 段落形态题注折叠：与 heading-shaped 同走
    `pending_table_caption`，lookahead 跳过空行/单位行，合并时校验
    caption-number 与 directive 编号一致防误并；合并点加编号匹配保护；
  - `parser.py` 独立成段的单位行折进 `table.unit` 属性（schema 已登记，
    additionalProperties:false 必须同步）；
  - `pdf_renderer.py` 单位行渲染为小五号(9pt)右对齐、位于题注之下紧贴表格。
- **规则化**：GEN-032 更新（单位陈述折叠 + 防双题注）；GBT-B07 更新
  （10.4.2：各栏单位相同时在表题之下右上方陈述单位，小五号宋体，紧贴表格）。
- **验证**：表3 题注 y 615.0→单位行 631.9、表4 79→95.9、表5 231→247.9、
  表8 457→473.9、表B.1 706.8→723.8（单位行在题注下约 16.9pt），
  x1≈526.9 贴版心右缘；无双题注。

### 3.6 脚注成对与小写上标（GBT-X04）

- **现象**：表格脚注/正文脚注标记未渲染为上角标；A/B/C 相相位字母被误上标。
- **根因**：`_table_cell_superscripts` 不区分大小写；正文段落无脚注标记处理。
- **修复**（`pdf_renderer.py`）：
  - `_footnote_superscripts`（正文/图脚注安全版，接入正文段落分支），
    触发位置：行首标记+空格+汉字、行首标记紧跟汉字（OCR 丢空格）、
    全角 ａ-ｚ、句末标点（。；）后接标记（含 \n，MinerU 合并段）；
    排除：公式变量行（字母+—破折号）、大写字母、列项引用（a)中所述）、
    变量（转速n，）；**刻意不做**"汉字后+半角小写单字母"（防误伤）。
  - `_table_cell_superscripts` 只上标**小写**行首标记（排除单位与 ")"），
    并在其上补表格半角规则。
  - 实现细节：哨兵 `\x00SUP\x00…\x00/SUP\x00` 由 `_markup` 转 `<super>`；
    渲染尺寸上标 8.5pt vs 正文 10.5pt；替换串中组引用写 `\1`（非 `\\1`）。
- **规则化**：GBT-X04 更新（9.12.1/9.12.2：脚注由标记与解释成对组成；
  条文脚注 1)、2)… 全文连续；图表脚注小写拉丁字母 a)、b) 上标，标记与
  解释行均小写，逐图逐表单独编号）；compliance GBT-X04 新增解释行标记
  大写检查（footnote-marker-lowercase）。
- **验证**：附录E 图脚注 p66 `a` 8.5pt 上标 + 10.5pt 正文、p67/p68 `a`+`b`
  均上标；正文段落合并段用例（`\n` 后标记）通过；A/B/C 相不上标。

### 3.7 第 2 章标准号完整性检查（GBT-C06）

- **现象**：规范性引用清单条目缺标准号（"/ — 环境试验 第 部分:…"）。
- **根因**：文本层损坏丢拉丁/数字整段（OCR 重抽后恢复）。
- **修复**：compliance.py `_STANDARD_NUMBER_RE` 允许 "GB/T 与编号间空格"
  （`\s*`，"GB/T 2423.16—2022" 不再误判缺编号）；新增引用条目标准号检查
  （code=reference-item-number，8.6.1—8.6.3：每个引用条目应含标准文件编号
  与文件名称；文本层损坏导致标准号丢失时提示复核）。
- **验证**：OCR 重抽后全部标准号恢复；单测用缺编号条目命中。

### 3.8 示例框内嵌图撑爆表格行 → 渲染 LayoutError（工程规则）

- **现象**：GB_T_20001.6-2017（规程标准，附录示例含图）渲染崩溃：
  `LayoutError: Flowable <Table … 51 rows x 1 cols(tallest row 16777221)> …
  cell(0,0) containing '<KeepTogether …> containing :<Image …>'
  (441.54 x 33555428), too large on page 12`。`04_render/` 只有 render.md、
  没有 render.pdf（渲染步骤异常退出）。
- **根因**：附录示例框（GBT-B11 `_example_box`）把每个 flowable 放进单列
  表格的一行以便跨页拆框；`_append_content` 的 figure 分支把「图+图题」包成
  reportlab `KeepTogether`。而 `KeepTogether.wrap()` **恒返回
  `W, 0xffffff`（16,777,215pt，强制拆分的哨兵高度）**——在普通文档流里由
  doctemplate 的 split 机制消化，但放进 Table 单元格后 Table.wrap 把它当真实
  行高，tallest row = 0xffffff + 6pt 单元格 padding = 16,777,221 ≈ 2^24，
  超帧高（688pt）→ LayoutError。GB_T_1.1-2020 的图在「示例：」题注节点里
  （不进框）所以不炸；20001.6 的图在普通 exampleContent 节（4.1 马铃薯脱毒
  试管苗繁育程序的构成）里，进框即炸。
- **修复**：`pdf_renderer.py` `_example_box` 展开 KeepTogether——遍历
  `_content`，每个子 flowable 单独成行（子内容里的 PageBreak 一并剔除，
  与 `_strip_pagebreaks` 同逻辑）。图与图题拆成相邻两行，跨页时可能分属
  两个框片段，与示例框按行跨页的设计一致。
- **规则化**：工程规则（无标准对应；reportlab API 限制——KeepTogether
  不能进表格单元格）。同类问题排查提示：**凡 Table 单元格内出现 wrap 返回
  哨兵高度的 flowable 都会撑爆行高**，PageBreak（≈72000pt）与 KeepTogether
  （0xffffff）是已知两类。
- **验证**：GB_T_20001.6-2017 全流程重跑——渲染 14 页、render-report 零警告、
  roundtrip 0（等价）；p12 图1（马铃薯脱毒试管苗繁育程序流程图）+ 图题、
  p13 图2 均入框；回归测试 tests/test_pdf_renderer.py::ExampleBoxKeepTogetherTests
  3 例（KeepTogether 展开为独立行 / 子内容 PageBreak 剔除 / 普通 flowable
  不受影响）。

### 3.9 裸条号标题提升与标题层级规范化（GEN-035 / GEN-031、CSM-OCR-006）

- **现象**：QB_T_2946-2020 raw 中第 3 章「3 产品分类和型号命名」及 3.1/3.1.1
  被 MinerU 抽成**裸段落**（无 `##` 前缀，编号+标题同段）→ parse-report
  GBT-H03 误报「章编号不连续：缺失 3」、GBT-C06 把「3 产品分类和型号命名」
  当规范性引用条目误报缺号。语料级检查还发现：MinerU 把章条标题全部压成
  同一层 `##`，几乎所有文档 90%+ 标题层级错（GB_T_1.1-2020 176 个标题中
  166 个层级不匹配编号段数）。
- **根因**：MinerU 版面引擎对章条标题的处理不稳定——要么压成裸段落，
  要么全部提升为同一层 `##`，不保留标题层级。
- **修复**（parser.py normalize 阶段，两个独立机制）：
  1. **裸标题提升**（`_bare_heading_candidates` / `_promoted_bare_headings`）：
     用「祖先链 + 父已提升子级跟随」的级联判定——某编号是已确认标题的
     祖先（如 3 是 3.1 的祖先）后提升为标题，其下子级跟随。**全文档无任何
     已确认标题时完全不提升**（保守，不猜）。记录 CSM-STRUCT-001 warning。
  2. **层级规范化**（`_repair_heading_levels`，issue 码 CSM-OCR-006）：
     按编号段数提升标题层级——章 1 段→`##`、条 2 段→`###`、子条 3 段→
     `####`…。**只提升不降低**：守护用户手写结构、避免与 CSM-OCR-002
     等其他修复冲突；文本不变，roundtrip 三侧一致。
- **规则化**：GEN-035 新增（裸条号标题提升）；GEN-031 更新（层级规范化）。
- **验证**：QB_T_2946-2020 parse-report 0 findings（修复前 GBT-H03/G06 两类
  误报全部消除）；canonical 中 3/3.1/3.1.1 恢复正确层级；单测覆盖裸提升、
  层级规范化（含编号后无空格形态、千分位「1 000 kV」不误升）。

### 3.10 引用标准号前缀扩展（GBT-C06）

- **现象**：QB_T_2946-2020（轻工行业标准）20 条规范性引用条目全部误报
  「缺少标准文件编号」。
- **根因**：`compliance._STANDARD_NUMBER_RE` 前缀只列到 GB/T、JB、QB 等
  少数代号，QB/T、HG/T、FZ/T、T/CAS、Q/ 等 20+ 常见国家/行业/团体/企业
  前缀全部漏识别 → 引用条目被当缺号。
- **修复**：前缀扩展 30+ 个（GB/T、GB/Z、GB、JB/T、JB、DBxx/T、QB/T、
  QB、SJ/T、DL/T、NY/T、HG/T、FZ/T、WS/T、YD/T、GA/T、CJ/T、JG/T、
  TB/T、SH/T、JC/T、EJ/T、MT/T、YY/T、YY、HJ/T、HJ、T/、Q/、ISO、IEC），
  **长前缀在前**（防 GB 吞掉 GB/T）；GB/T 等与编号间允许空格；Q/、T/
  代号后允许空白。
- **验证**：QB_T_2946-2020 引用条目不再误报；真缺号（「3 产品分类和型号
  命名」、「/ — 数据元…」）仍正确报缺；单测 4 例（行业前缀不误报 + 真
  缺号仍报）。

### 3.11 拉丁/数字丢失后验强制 OCR（GEN-092 扩展）

- **现象**：GB_T_15835-2011 文本层健康（pymupdf 读到 "GB/T1.1—2009"），
  但 MinerU auto 抽取丢拉丁整段——raw 里 5 处 "/ — "（标准号只留斜杠和
  连接号）。GEN-092 预检只在抽取**前**看文本层损坏特征，覆盖不到这类。
- **根因**：MinerU 文本抽取对特定字体编码处理不当（与 GBT_23132-2024
  同类），文本层本身无损坏特征。
- **修复**：`mineru_full_standard.py` 新增 `_latin_loss_check`（抽取**后**
  后验）：对比源 PDF 文本层与 raw 的标准号提及数——文本层 ≥5 且 raw 不足
  一半时判定丢失，main 流程 auto 模式下自动强制 OCR 重抽（复用
  previous_method 不一致时失效 parts 的既有逻辑，删除旧产物防续跑绕过）。
- **验证**：GB_T_15835-2011 命中（文本层 18 → raw 6）；GB_T_1.1-2020 /
  QB_T_2946 / T_ZZB_2224 / GB_3102.1 均不误报；单测三态（命中/健康/稀疏
  文本层不触发）。

### 3.12 嵌套示例内容扁平化 → 渲染 LayoutError（工程规则）

- **现象**：GB_T_20001.6-2017（规程标准附录「规程标准编写示例」）KeepTogether
  修复后仍崩溃：`LayoutError: Flowable <Table 4 rows x 1 cols(tallest row 792)>
  with cell(0,0) containing "<Table 36 rows x 1 cols(tallest row 90)>…5.1 田间选择"
  (441.54 x 1194), tallest cell 792, too large on page 14`。
- **根因**：示例文档自身是完整的迷你标准（5 繁育程序 → 5.1 田间选择 →
  5.4.1 茎尖培养基的制备），其章节树节点全部带 exampleContent 标记。
  `_append_node` 对 exampleContent 节点递归 `_append_nodes`，而后者把连续
  exampleContent 兄弟**分组再包一层 `_example_box`** → 外层示例箱表格的
  单元格里放了一个内层示例箱表格。reportlab Table 单元格内的表格**不能
  跨页拆分**，内层 36 行 / 1194pt 整表高度超过帧高（688pt）→ LayoutError。
- **修复**：`_append_node` 对 exampleContent 节点的 children 走**扁平化**
  分支——逐节点直接 `_append_node` 追加进当前框（示例内部标题用黑体顶格
  example-content 样式），不再经 `_append_nodes` 分组，不产生嵌套框。
- **规则化**：工程规则（无标准对应；reportlab Table-in-Table 不能拆分）。
  排查提示：凡示例内容含自身层级结构的（规程/指南类标准的示例文档），
  都会触发同类崩溃。
- **验证**：GB_T_20001.6-2017 全流程重跑——渲染 15 页、render-report 零
  警告、roundtrip 0；渲染 PDF 文本层抽查 9 个探针（示例：/技术规程/5 繁育
  /5.1/5.4.1/追溯方法/标记方法/过程记录）全部命中；回归测试
  NestedExampleContentTests（单框扁平、无嵌套 Table、标题齐全）。

### 3.13 渲染图过大 → 按原图尺寸打标（GEN-076 / GBT-X02 表中图）

- **现象**：GB_T_23132-2024 渲染的图太大——图1 尼龙丝摆放位置 原图
  41.6x76.1pt 被渲染成 126x212pt（约 3 倍），图2 卷曲判定图被拆成的
  a)/b) 两块各渲染成 455x206.8 / 455x248.5pt，图3 455x277.9pt；
  表2 单元格内六张示意图全部按单元格宽放大到 143.7pt（原图最窄仅
  87.5pt），且旋转式行 试验区域分割 示意图（89e2bc42）被渲染成
  265x273pt 的独立大图悬在两表之间。
- **根因**（三层）：
  1. `_stamp_figure_source_sizes`（finalize 阶段打标）用
     `ssir_path.parent / ref` 解析 assetRef，而资产实际在文档根
     `<docroot>/assets/images/`（SSIR 在 `03_ssir/` 子目录）——
     解析全部落空，没有任何图拿到 sourceWidth/sourceHeight，渲染端
     回退按 72dpi 固有像素尺寸输出；
  2. MinerU 裁剪图以 2.1-3x 像素密度导出（OCR 重渲染 ~200dpi），
     72dpi 固有尺寸 = 原图 2-3 倍；
  3. 图2 卷曲判定图被 OCR 拆成 a) 合格断面 / b) 不合格断面 两个无编号
     图块，宽高比与源 PDF 整图矩形（427.9x130.8）不符，宽高比匹配失败；
     表2 单元格内图不在 figures 注册表（是 cell 文本里的 `![](ref)`），
     原打标逻辑根本不扫。
- **修复**（`tools/mineru_full_standard.py` `_stamp_figure_source_sizes` 重写）：
  - **资产解析**：沿祖先目录向上找（同 `pdf_renderer._resolve_asset`）；
  - **矩形匹配**：`|Δaspect| < 0.12` 且像素密度 `[1.2, 4.0] px/pt`；
    全局贪心（最小 Δaspect 的候选-矩形对先占位），**每个源矩形只分配一次**，
    防两张相似方形图抢同一矩形（表2 旋转式 试验区域分割/插入角度）；
  - **封面徽标排除**：第 1 页高 < 100pt 的矩形不参与匹配（封面徽标/logo，
    非内容图；正文图不会出现在封面），否则宽高比接近的内容图会误配到
    GB_logo 113.7x56.9；
  - **密度回退**：无匹配的子图（图2 a/b 块）按**文档像素密度**取尺寸——
    已匹配资产的 px/pt 中位数（实测 2.74-2.77 ≈ 200dpi/72）；扫描型 PDF
    无任何匹配时默认 200/72 ≈ 2.78；
  - **表中图打标**：扫描 table cell 文本里的 `![](ref)`，同样匹配/回退，
    尺寸写入 `table["cellImageSizes"] = {ref: [w, h]}`（ssir.schema.json
    Table 增补该属性；渲染端 `_append_table`/`_render_cell` 按原尺寸、
    上限单元格宽、不放大渲染，保持图片自身宽高比不拉伸）。
- **表中图归位**（CSM-TABLE-002，parser `_repair_stray_table_images`）：
  MinerU 跨页表格把某行单元格内的图排在 `<table>` 元素外，读取顺序上
  表现为 前表 → 裸图 → 续表（题注带"续"）。全部条件满足才归位：
  前后都是表格、caption-number 相同且后表题注含"续"、前表最后一行既有
  含图单元格又有不含图单元格、游离块是单张裸图（无题注文本）→ 折回
  第一个不含图且非首格（行标题列）的单元格，删除游离 figure 块。
  纯文本行不归位（保守，防把独立图塞进表格）。
- **规则化**：GEN-076（渲染图与原图尺寸相当）；GBT-X02 更新（表中图按
  原尺寸显示）；工程规则 CSM-TABLE-002（跨页续表折回）。
- **验证**：GB_T_23132-2024 全流程重跑——图1 41.6x76.1、图3 169.8x102.5
  与源矩形完全一致；图2 a/b 192.8x87.6 / 169.8x92.8（接近原整图比例）；
  表2 六张图中图全部按原尺寸入格（旋转式 试验区域分割 89e2bc42 96.4pt
  归位到单元格）；roundtrip 0、15 页零警告；回归测试
  FigureSourceSizeStampTests（含徽标排除/密度回退/表中图打标/祖先目录
  解析）+ test_stray_figure_between_split_table_parts_folds_into_last_row
  + test_stray_figure_not_folded_when_no_image_cell_in_last_row。

### 3.14 表中图格内顺序与列错位（CSM-TABLE-003）

- **现象**：GB_T_23132-2024 表2 尺寸修复后，版式仍与原文不符——
  ① 往复式行 试验区域分割 列的说明文字"单片往复式取2个区域；双片往复式
  按照单片往…"被放在了 插入角度 列（第3列，该列其余行均为纯图）；
  ② 三行 第2列（试验区域分割）的说明文字都排在图的上方，而原文是
  **图在上、说明文字在下**（源 p11/p12 视觉实测：旋转式/往复式/修剪器
  三行第2列全是 上图下文字，第3列插入角度是纯图）。
- **根因**（MinerU 表格提取两个通用偏差）：
  1. **列错位**：某行某列是"图+文字"时，MinerU 的单元格切分可能把文字
     误归到后一列（往复式行：文字跟着 插入角度 的图进了第3列）；
  2. **格内顺序**：OCR 把说明文字排在图片标记之前（`文字 ![]()`），
     渲染端按文本顺序流式输出 → 文字在上图在下。
- **原则**（重要）：**"图在上、文字在下"不是通用版式要求**——图与说明
  文字的上下关系是各表原文自行安排的（GB_T_23132 表2 第2列恰好如此）。
  渲染端（pdf_renderer._render_cell）保持中立，按数据（cell 文本）顺序
  忠实复现：数据怎么排就怎么渲染。本修复只纠正**有明确证据**的错误。
- **修复**（`parser.py` `_repair_table_image_layout`，CSM-TABLE-003）：
  - B. **列错位移动**（有列间证据，保守启发式，全部满足才移动否则不猜）：
    数据行数 ≥ 2；当前格同时含图与文字；该列文字**仅此一行**
    （col_text_count == 1）且该列是图列；前一格是**纯图格**
    （无文字，文字落点明确）→ 把文字移到前一列图后，原格只留图。
    不满足任何一条都不动（如 修剪器行 第2列 文字+图 与多数行一致 → 不移动；
    单行表格无"其它行"参照 → 不移动）。
  - A. **格内顺序**（仅作为 B 的配套，不独立触发）：只有当该表（或与其
    同 caption-number 的跨页续表）发生了 B 时，才把相关表块的图文混合
    单元格统一重排为 图在前、文字在后——B 移动的文字以"图前文字后"落位，
    同表（含跨页两部分）其它图文混合单元格保持同向才一致。**未发生 B 的
    表不重排**，严格按提取顺序渲染（原文若为文字在上图在下，保持原样）。
  - 坑：`re.split` 带捕获组的正则会把捕获的 assetRef 也放进结果
    （格内重排时裸 ref 泄漏进文字），拆分必须用无捕获组版本。
- **规则化**：工程规则；issue 码 CSM-TABLE-003。**不写入 GBT-* 通用
  版式规则**——"上图下文字"只是 GB_T_23132 表2 的原文布局。
- **验证**：GB_T_23132-2024 重跑——roundtrip 0、15 页零警告；视觉核对
  （vision_analyze）渲染 p11/p12：三行第2列均为 图在上、文字在下，第3列
  纯图，与源页一致；回归测试 3 例（无证据不重排/列错位移动/不误伤）。

### 3.15 GB_3100-2026 六项排版修复（2026-09-02）

用户报告 GB_3100-2026 六类问题：3.7 术语解释不另起一行、<sup>/<sub> 字面
泄漏、4.2 七个常量挤成一行流、表1 注不分行且居中、表2 上角标丢失、表4
注到注11 落表格框外。解析层三修 + 渲染层五修：

- **解析层（parser.py，全部已回归）**
  - **Fix A 空行续接收窄**：原规则"不以 。！？ 结尾即续接"会把术语行
    （拉丁结尾）与空行后的定义并段、把 4.2 引导语与常量行并段。收窄为
    **仅 `，、` 结尾**续接（MinerU 误插空行处通常是逗号）；`；`/`：`/句号/
    拉丁结尾一律不续接。代价：词中插空行（"确\\n\\n立"）不再合并为一段
    （两段正文，内容不丢）——保守取舍。
  - **Fix B 裸列项分行**：`_is_bare_enumeration`——段落含 ≥2 行、≥2/3 行以
    句末标点（。；：;.）结尾、≥1 行以 `；` 收尾 → 按行拆成独立段落
    （4.2 七个定义常量逐条成段）。行尾 LaTeX `$` 先剥掉再判定。
  - **Fix G 表注跨页吸收**：`_absorb_table_note_spill`——表末注行（末行首格
    以 `注N：` 开头）后紧随的注块（注N：…）与未收尾续句段（表注行文本
    尚未以句末标点收尾时的普通段落）吸收回表末注行单元格，以 `<br>` 分行；
    遇新块（标题/条号段/新表格）停止；表注行已句号收尾时不吸收后续普通段
    （防误并）。
- **渲染层（pdf_renderer.py）**
  - **Fix C <sup>/<sub>**：`_markup` 在 escape() 前把 HTML 标签转
    `\x00SUP\x00`/`\x00SUB\x00` 哨兵，escape 后恢复为 reportlab
    `<super>`/`<sub>` 真上标/下标。**坑（再次命中）**：re.sub 替换串里
    `"\\x00SUP\\x00\\1"` 报 `bad escape \x`——`\x00` 必须写真实 NUL 转义、
    组引用写 `\\1`。
  - **Fix D 缺字形上标**：正文宋体 Noto Serif CJK SC **只有 ¹²³⁴，缺
    ⁰⁵⁶⁷⁸⁹⁻⁺ 字形**（fontTools 实测）——Unicode 上标直接渲染成 .notdef
    方框。`_markup` escape 后把缺字形字符（⁰⁵⁶⁷⁸⁹⁻⁺ⁱ）转
    `<super>普通字符</super>`，相邻上标合并为一个 run。
  - **Fix E 表格平拍上标**：`_table_cell_superscripts` 新增 5 条平拍指数
    还原规则（只作用于表格单元格，上下文受限不会误伤正文）：单位字母后
    `−/[-]数字`（s−1→s⁻¹）、`10[−-]数字`（10-2→10⁻²）、`10[1-9]\d{0,2}`
    （1030→10³⁰，100 不猜）、`10[²³¹]\d` 半上标混合（10²4→10²⁴，²³¹ 归一
    为数字进 <super>，防双重缩小）、单位字母后平印 2/3（N/m2→N/m²）。
  - **Fix F LaTeX 拍平**：`_latex_to_text` 对 `_`/`^` 输出 super/sub 哨兵
    （拍平会丢上标版式）；数字逐字空格收紧（"6 . 6 2 6"→"6.626"）；希腊
    字母后命令终止空格折叠（`\Delta V`→ΔV，同一量符号）；拉丁-拉丁乘积
    （J s）空格保留（原文有间隙）。
  - **Fix H 表注行拆条**：`_TABLE_NOTE_CELL_RE` + `_split_table_note_parts`
    ——表注行单元格按 `(?=注N：)` 拆成每条注独立段落，居左、首行空两格
    （table-note 样式，GBT-B09 表内居中例外）。**坑（2026-09-02 实测）**：
    尾部 `<br>` 哨兵（`\x00BR\x00` 三字符）只 `strip("\x00")` 会残留 "BR"
    字面文本（渲染成 Ⓡ-like 字符，表4 注7~注10 中招）——必须先整段
    `re.sub(r"(?:\x00BR\x00)+$", "", part)` 再 strip；行中 <br>（注6 续句）
    保留为 <br/>。
- **验证**：GB_3100-2026 重跑——roundtrip 0；vision 逐页核对 6 项全过
  （3.7 术语/定义分行、4.2 常量逐行、上标全正确无方框、表1/表3/表4 注
  独立成段居左缩进、表4 注1~11 在框内）；回归测试 12 例（parser 5 +
  renderer 7，含 BR 泄漏回归）。

### 3.16 表格列宽按内容分配、尽量利用版面宽度（2026-09-03）

- **问题**：渲染端 `_append_table` 列宽一律 `455/col_count` 等分——表4
  四列各 113.75pt，「与SI单位的关系」列（1 kn=1 n mile/h=（1852/3600）
  m/s、1 Da = 1 u ≈ 1.660 540×10⁻²⁷ kg 等长公式）被迫换行，窄列却大量
  留白。用户要求：**按内容安排列的宽度，尽量利用版面宽度**（通用规则）。
- **修复**（`pdf_renderer.py`）：
  - `_cell_text_natural_width(text, font_size)`：文本自然宽度估算——按行
    （<br>/哨兵/换行）拆分取最长行；CJK 及全角（U+2E80 起）≈1em、拉丁/
    数字 ≈0.55em、空白 ≈0.3em、其它 ≈0.5em；<sup>/<sub> 标签剥掉，哨兵
    字符剔除。
  - `_table_column_widths(...)`：每列需求 = 该列最宽单元格自然宽度；
    **colspan 内容按跨列数摊分**；**整行通栏的注行（colspan=全部）与 OCR
    丢 colspan 的单长格（渲染端 SPAN 全宽）不挤占单列需求**；图片按原版面
    宽度计；**估算前先把 `$...$` LaTeX 经 `_latex_to_text` 拍平**（否则
    命令噪声 `\mathrm { D a }` 把需求撑大——表4 道尔顿行实测 302pt→135pt）；
    按需求比例把版心宽 455pt 全部分配（列宽和恰等于版面宽），保底 24pt
    防空列退化。
  - `_append_table` 用 per-column 宽度构建 `colWidths`；`_render_cell` 的
    图片缩放按**跨列总宽**（colspan 单元格内图不再被单列宽低估）。
- **验证**：GB_3100-2026 表4 列宽 [51.9, 51.9, 51.9, 299.4]（关系列 ~60%；
    源 PDF 表4 列几何 [65.6, 65.6, 65.5, 281.9]，关系列 59%——高度吻合）；
  长公式单行完整显示、窄列舒适不换行、整表满版心宽；4 份语料文档
  （GB_T_1.1-2020 84 页、GB_T_20001.6-2017 15 页、T_ZZB_2224-2021 18 页、
  Q_TQDZ_004-2026 10 页）重渲染全部成功无 LayoutError；回归测试
  TableColumnWidthTests 4 例（CJK/拉丁加权、比例充满版心、通栏注行不撑爆、
  空列保底）。

### 3.17 句子体条文误升标题 + 页边界条文断段（CSM-OCR-009/010，2026-09-04）

背景：GB_T_1.1-2020 附录 B 的目次/树审计发现 B.2.2 被当作 ## 标题（附录
B.2 下出现伪二级结构、目次跳号），9.4.2.2 被断成两段渲染。早期会话曾用
「逐实例数据手术」直接改写 canonical（9.4.4.4/9.4.5.2/示例1 的公式语义、
B.2.2 降级、9.4.2.2 合并等 6 处），按用户原则（不得针对单文档做一次性
手术；先根因分析落为通用规则 + 回归夹具 + 跨语料验证）已全部回滚。本次
把其中可通用化的两处结构性缺陷落为 parser 修复，并在 canonical 上以
「规则实例化」方式重放（与 3.9 外科手术式更新同约定）：

- **CSM-OCR-009 句子体条文误升标题**（`_demote_sentence_headed_clauses`）：
  MinerU 把「编号 + 整句条文、以 。！？ 收尾」的无标题条文抽成标题行
  （GB_T_1.1-2020 附录 B.2.2「这里描述的标记体系适用于下列各类文件。」、
  9.9.3.1 首句「数学公式应以正确的数学形式表示。」；GB_T_23132-2008 8.1.2；
  GB_T_20001.5-2017 更甚——5.1~5.4 站控层句子、4.1.1/4.1.2 专利句等 8 处）。
  真标题从不以句末标点收尾 → 编号开头 + 句末标点 = 降级为正文段落
  （H1 除外）。修复后条文回到父节点 contentElement 流，不再产生伪结构
  节点/目次条目。
- **CSM-OCR-010 页边界条文断段**（`_merge_split_clause_paragraphs`）：
  MinerU 在页边界把无标题条文拦腰断成两个 markdown 段落（9.4.2.2
  「……不应该与"应"一起」+「使用表示要求……推荐。」；GB_T_20001.10-2014
  6.7.2.2 警示/用语、GB_T_20001.4-2015 6.8.5 半成/品、GB_T_20001.5-2017
  6.3.2.4、QB_T_2946-2020 8.1.1/8.2.2）。空行续接的（，、）收窄规则
  （见 3.15）覆盖不到无标点断点 → 块级合并：首段编号条文形态开头、无
  句末/连接标点收尾；次段汉字开头、非编号/示例/注/表/图开头；两侧均非
  术语行形态（中文 U+3000 拉丁）——防术语行与定义段被粘、防示例/注被吞。
- **坑**：
  - 修复必须放在 `read()` 的 repair 链（normalize 与 parse 共用），
    canonical 级回放只改实例行、不跑完整 normalize（raw 过期会毁内容，
    与 3.9 同）。
  - 术语章形态「3.1.1（空行）标准化文件　standardizing document（空行）
    定义段」：编号后无内容的孤立 "3.1.1" 行不满足「编号+内容」判定，
    天然免疫；术语行含 U+3000+拉丁由守卫排除——不加守卫会把术语行与其
    定义粘成一段（CSM-OCR-003 术语间隙修复反而制造误并）。
  - 测试断言勿用「一起使用表示要求」这类可能命中相邻条文（9.4.2.3）
    的子串，用行首编号定位段落。
- **验证**：全语料 22 份 canonical 重 parse——009 命中 12 处、010 命中 8 处，
  全部为真实句子体标题/页断续文，csm 手写夹具 0 命中；GB_T_1.1 canonical
  回放 3 处（B.2.2 降级、9.9.3.1 降级、9.4.2.2 合并）后重 parse 残留 0
  （幂等）、roundtrip passed、render 82 页 0 警告、正文 9.4.2.2 单段连续、
  目次不再出现 B.2.2 行；单测 6 例（含完整句不并、示例/注/新条文不并、
  无编号句子标题不降、术语行+定义不粘）。规则 ID 同步：§2 表 19/20、
  §5.3 CSM-OCR-009/010。

### 3.18 抽取层语义局限如实标注（2026-09-04，GB_T_1.1-2020）

审计识别的其余缺陷类经根因分析判定为**抽取层真值丢失**，无法以安全通用
规则恢复，按用户原则如实标注、不做人工改写掩盖（canonical 保留 OCR 原样）：

- **破折号/项目符号丢失**（引言三段引导句、5.2.3/8.5.2 引导列项、9.5.4.4.1
  子弹 2-5）：源 PDF 像素分析确认原稿各行均有破折号，MinerU/OCR 只保留首个
  marker（raw.md 起就缺失）。逐行补 marker 需「哪些行属于同一条目」的语义
  判断，且 OCR 真值本就不完整（行文本也常被截），未发现可安全通用的恢复
  规则 → 抽取局限。与既有 CSM-OCR-005/GBT-C12 只处理「整行文本健在、仅丢
  marker」形态不同，此处行内容本身残缺。
- **公式区 LaTeX 语义垃圾**（9.4.4.4 的 `\lrcorner`、9.4.5.2 引导句内的
  `\overline{\prime}\mathrm{J}`、示例1 的假分式 `\frac{\mu F}{8(80±2)\mu F(`、
  示例5 的 `\~`）：OCR 对公式区字形的误识别，真值只存在于印刷排版；
  P0-C 拍平器（`_latex_to_text` 花括号配平展开 + `\sim`/波浪号映射）已通用化
  消除命令噪声与泄漏（§3.15 同批），但**语义重写**（把假分式改写成
  「80 μF±2 μF 或（80±2）μF」）需要外部正本佐证，属逐实例人工改写——
  本次已按用户原则回滚（见 §3.17 背景）。
- **9.7.3 图3「表格泄漏」判定**：示例/图中"表"形态内容（转页接排标记
  「（第#页/共*页）」等）如何归框，涉及示例框渲染的通用形态判定，
  待后续专项判定（未解决，不标注为已修）。

---

## 4. 历史通用问题速查（2026-08 早期，均有规则映射）

| 日期 | 问题 | 修复 | 规则 |
|---|---|---|---|
| 09-01 | 标题行编号整体从文本层丢失（Q_TQDZ_004-2026 等企标："7.1 外观检查"→裸"外观检查"；章节号/条号 6.2.1、9.2.2 完好，唯独标题行编号缺失，pymupdf 逐字符确认，视觉层 OCR 可恢复 7.1-7.9/9.1-9.4） | `_detect_broken_text_layer` 新增信号：裸汉字短行（2-12 字）≥5 且其中 ≥50% 后跟长正文行（≥15 字，标题-正文版式）+ 存在带点条款行（≥5）→ 判定标题编号丢失，auto 自动强制 OCR。对语料 33 份实测：Q_TQDZ/Q_HKF/Q_XKBZ 命中，健康文档（T_ZZB_2224 表格型、Q_YYJD 无 x.y 体系、GB 系列）零误报 | GEN-092 扩展 |
| 08-31 | 示例框内嵌图渲染崩溃（KeepTogether.wrap 恒 0xffffff 撑爆表格行，tallest row ≈2^24） | `_example_box` 展开 KeepTogether 内容逐子成行（子内 PageBreak 剔除） | 工程规则（无标准对应） |
| 08-31 | 嵌套示例内容渲染崩溃（示例文档自身章节树 5→5.1→5.4.1 再包一层示例箱 → Table 套 Table 不能跨页拆分，36 行撞帧高） | `_append_node` 对 exampleContent 节点 children 扁平化逐节点追加，不产生嵌套框 | 工程规则（无标准对应） |
| 08-31 | 章条标题被抽成裸段落（QB_T_2946 第 3 章）→ GBT-H03 误报缺失、GBT-C06 误报引用缺号 | 祖先链 + 父已提升子级跟随的裸标题提升（无确认标题不提升，记录 CSM-STRUCT-001） | GEN-035 新增 |
| 08-31 | 标题层级全压成同一层 ##（语料 90%+ 层级错） | `_repair_heading_levels` 按编号段数提升（只提升不降低，文本不变） | GEN-031 更新（CSM-OCR-006） |
| 08-31 | 引用标准号前缀漏识别（QB/T、HG/T、FZ/T、Q/ 等 20+）→ 引用条目误报缺号 | `_STANDARD_NUMBER_RE` 扩展 30+ 前缀（长前缀优先，Q/、T/ 后允许空白） | GBT-C06 更新 |
| 08-31 | 文本层健康但 MinerU 丢拉丁整段（GB_T_15835 "GB/T1.1—2009"→"/ — "） | `_latin_loss_check` 抽取后对比文本层与 raw 标准号提及数，命中强制 OCR 重抽 | GEN-092 扩展 |
| 08-31 | 同一条款列表项符号不一致：破折号族混用（-、—、——、———，GB_T_1.1-2020 前言 8.3 与 GB_T_20001.4/5/6/10 前言清单均出现）；·/• 混读（GB_T_1.1-2020 前言 8.3 c) 子列表 "· 给出被代替…" 沦为独立段落、兄弟 • 被并入相邻字母列表） | `UNORDERED_ITEM_RE` 增补 ·/○ 为可解析项目符号、-—– 全破折号族；`_repair_list_markers` 符号族（破折号族+项目符号族）多数派统一（≥2 且严格多于其余，平手不猜）；渲染层 `_list_marker` 破折号族一律归一 —— | CSM-OCR-001 更新 |
| 08-27 | 文本层拉丁/数字整段丢失（GBT_23132-2024，"GB/T1.1—2020"→"/ — "） | 工具 `--method ocr` 整本重抽；`_cover_metadata` 用 PDF 文本层兜底机构名 | GEN-092 前身（后固化为 GEN-092） |
| 08-27 | 合并单元格表格错乱（rowspan 未展开，罩极异步电动机跑进第 1 列） | `mineru_html.py` 逐行维护 pending rowspan 占位，统一输出 ssir:table-merge 指令 | GBT-X02（表） |
| 08-27 | 封底横幅片段污染标题（OCR 拆成 "# 中华人民共和国"+ 国家标准） | `_demote_banner_fragments` + `_is_cover_banner_fragment` | GBT-C01 |
| 08-27 | 封面"代替GB/T23132—2008"无空格匹配不到 | `^代替\\s*(.+)$`（只扫封面块） | GEN-015 |
| 08-27 | 封面机构行带 `<sup>` 标签打断匹配 | 读 content_list 文本先 `re.sub(r"<[^>]+>", "", text)` | GBT-C01 / GEN-014 |
| 08-27 | 表脚注上角标丢失（单元格 ᵃ 只留脚注行） | `mineru_html._restore_table_footnote_markers` 补回标记 + `_table_cell_superscripts` 渲染上标 | GBT-C18（后并入 GBT-X04） |
| 08-27 | 编号连续性/字形混淆（4.O.1、GB/T 5O89；列表 1)/l) 混淆） | `_repair_list_markers`（CSM-OCR-001）；compliance GBT-H03/C14/C15/C16 | GBT-H03/C14/C15/C16、CSM-OCR-001 |
| 08-27 | 术语中英文间隔方框（U+200B 无字形） | parser 改插 U+3000；`_markup` 白色汉字填充 1em 间隙 | GEN-070 相关（字体能力） |
| 08-27 | 多位数条号落 body 样式（5.10 深度解析错） | `_heading_depth` 改 `\\d+(?:\\.\\d+)+` | GBT-B02 |
| 08-27 | 无标题条缩进（5.5.2承压零件…） | `_clause_leading_number()` 切 body-flush 顶格样式 | GBT-B02 |
| 08-27 | 行内公式 LaTeX 泄漏进 PDF | `_latex_to_text()` 渲染时压平为可读文本（CSM/SSIR 保留源） | 工程规则（无标准对应） |
| 08-26 | 合并单元格（colspan 跨列表头"功率因数cosφ"） | ssir:table-merge 指令 column/row 坐标统一 | GBT-X02 |
| 08-26 | 列项渲染/终结线（OCR 把 `——` 压成单破折号丢空格） | `UNORDERED_ITEM_RE` 允许 `-`/`—` 后无空格；`_EndLine` 终结线 | GBT-C12/C13、GBT-B04 |
| 08-25 | 目次块装饰图被丢弃 | `toc_story` 增 extra_contents 参数渲染 figure | GBT-X01（装饰图可不编号，should 属正常） |
| 08-25 | 表题注被提升为 H2 且位于 directive 前 | `TABLE_HEADING_CAPTION_RE` 折叠进 pending_table_caption | GEN-032 前身 |
| 08-25 | 发布/实施日期同行丢失（"2021-08-19 发布 2021-09-19 实施"） | `re.finditer` 同行全部日期对 | GEN-013 |
| 08-25 | 句末标点后条号分段（"……告知乘客。\n6.3.5.2为了确保…"） | `CLAUSE_SPLIT_RE` 零宽切分 | GBT-B02 |
| 08-25 | 段落空行续接（"……方法时，\n应指明仲裁方法。"） | 段落收集遇空行 lookahead 连接性标点 | 工程规则（无标准对应） |
| 08-25 | 示例线框（附录框式示例） | `_stamp_example_styles` 按源 PDF 矢量几何识别 frame/shaded；`_example_box` 按行拆分表格跨页 | GBT-B11、GBT-X05 |
| 08-25 | 示例标题提升（"示例 1："冒号后无内容） | `EX_HEADER_RE` 提升为 ## 标题 | GBT-X05 |
| 08-24 | 封面徽标反白（白徽章黑底 + smask） | `get_pixmap(clip=rect)` 应用软蒙版；固化 GB_logo.png 到 config/emblems/ | GEN-018 |
| 08-24 | 正文首页标题重复（正文首页标准名抽成 ##） | `build()` 跳过 text==metadata.title 的 level>=2 标题 | GBT-C01 |
| 08-24 | 列项误识别为标题（"c）定型和固化时间；"） | `_parse_body` 形如列项的标题降级为 list 块 | GBT-H06 |
| 08-24 | 段落中途硬换行（Markdown 行尾两空格 + `\n`→`<br/>`） | 段落收集 rstrip；`_markup` 把 `\n` 折叠为空格 | 工程规则（无标准对应） |
| 08-22 | 字体 OpenType/CFF 无法加载 | reportlab 只能 TrueType；黑体 wqy-zenhei、宋体思源宋体 CFF→TTF（`tools/prepare_serif_font.py`） | GEN-070 |
| 08-22 | 宋体全角标点居中（AR PL UMing 句号悬空） | 换用思源宋体 Noto Serif CJK SC（句号 ink 贴底） | GEN-070 相关 |

---

## 5. 规则 ID 速查（本知识库涉及）

### 5.1 通用规则（extraction-rules.yaml，GEN-*）

| ID | stage | priority | 摘要 |
|---|---|---|---|
| GEN-001 | extract | must | 输入必须是存在的 PDF；不合法立即报错，不猜测文件名 |
| GEN-012 | merge | must | 文件编号识别与规范化（含命名方案：斜杠转下划线、字母大写） |
| GEN-013 | merge | must | 发布/实施日期识别（同行多日期用 finditer） |
| GEN-015 | merge | must | 被代替文件编号（`^代替\\s*(.+)$`，只扫封面块） |
| GEN-018 | render | should | 封面徽标按标准前缀从 config/emblems/ 读固定文件 |
| GEN-030 | merge | must | 附录标题重组（编号行 + 性质行 + 标题行） |
| GEN-031 | normalize | must | 层次编号规范化（点分链 ≤5 层）；掉点可安全拆点则修复（CSM-OCR-002），否则不猜测；标题层级按编号段数提升（CSM-OCR-006，只提升不降低） |
| GEN-032 | normalize | should | 表格单位陈述折进 table.unit；题注折叠防双题注 |
| GEN-035 | normalize | should | 裸条号标题提升：祖先链 + 父已提升子级跟随级联（无确认标题不提升，记录 CSM-STRUCT-001） |
| GEN-070 | render | must | 只能注册 TrueType 轮廓字体；CFF 必须报错并给替代建议 |
| GEN-071 | render | must | 排版参数一律来自渲染 profile，源码无硬编码中文排版常数 |
| GEN-090 | verify | must | 合成 PDF 机器验证（文本层抽取查封面字段/孤立单字行/页数） |
| GEN-091 | verify | must | 字体字号验证基于 PDF 内部对象（span 级 font/size），非视觉比对 |
| GEN-092 | extract | should | 文本层质量预检（孤立 "4."/"2." 行 ≥30 或截断标准号 ≥3 → 强制 OCR；裸汉字短行+带点条款体系判标题编号丢失 → 强制 OCR，09-01 扩展；方法不一致失效 parts + 删盘重抽）；抽取后拉丁/数字丢失后验（文本层与 raw 标准号提及数对比，命中强制 OCR 重抽） |
| GEN-093 | build | must | 文后/前置要素（目次/前言/引言/参考文献/索引）是文档级要素，不得并入附录示例 |
| GEN-076 | render | should | 渲染图与原图尺寸相当：finalize 从源 PDF 版面矩形打标 sourceWidth/sourceHeight（祖先目录解析资产；矩形贪心匹配防抢；封面徽标矩形不参与；无匹配子图按文档像素密度回退，扫描型默认 200/72≈2.78）；表中图尺寸写入 table.cellImageSizes |

### 5.2 需求规则（requirements.yaml，GBT-*）

| ID | source | 摘要（本知识库相关更新） |
|---|---|---|
| GBT-H03 | 7.3.1、7.3.2 | 条号点分编号；**父号加点前缀校验**（4.2.1 挂于 4.2 之下） |
| GBT-B07 | 10.4.2、9.8.4、附录F 37-40 | 表题之上居中；**单位陈述在表题之下右上方小五号宋体紧贴表格** |
| GBT-B08 | 9.8.2.1、9.7.2.1 | 题注必须形如"表X 题名"/"图X 图题"（编号必备、题名可省略） |
| GBT-C06 | 8.6.1—8.6.3 | 规范性引用文件为第 2 章；**每个引用条目应含标准文件编号与名称** |
| GBT-X04 | 9.12.1、9.12.2 | 脚注**由标记与解释成对组成**；图表脚注小写拉丁字母 a) b) 上标，标记与解释行均小写，逐图逐表编号 |
| GBT-X02 | 9.8.1.3—9.8.4 | 表编号/表题/表头/合并单元格；**表中图按原尺寸显示（上限单元格宽、不放大）；跨页续表裸图折回（CSM-TABLE-002）** |
| GBT-X05 | 9.10.1—9.10.4 | 示例引导语与编号 |
| GBT-C18 | 表脚注（08-27 并入 X04） | 表脚注上角标 |

### 5.3 报告 issue 码（parser 修复记录）

| 码 | 含义 | 处理 |
|---|---|---|
| CSM-OCR-001 | 列表 marker 字形/符号混淆（1)/l)、0)/O)；破折号族 -/—/——/——— 混用；·/•/●/○ 混读） | 多数派上下文纠正（normalize 层）：符号型标记（破折号族+项目符号族）按同列表多数派统一（≥2 且严格多于其余，平手不猜，真嵌套列项不误伤）；字母/数字编号混淆同理。无法确认不纠正 |
| CSM-OCR-002 | 条号掉点 | 编号连续性可唯一拆点时修复（_repair_clause_numbers），否则保守跳过记 issue |
| CSM-OCR-003 | 术语中英文间隙 | U+200B → U+3000 + 白色汉字填充 |
| CSM-OCR-006 | 标题层级被压成同一层 | 按编号段数提升层级（_repair_heading_levels，只提升不降低），文本不变 |
| CSM-STRUCT-001 | 裸条号标题提升 | 祖先链 + 父已提升子级跟随的级联提升为标题（无确认标题不提升），记 warning |
| CSM-TABLE-002 | 跨页续表间的裸图 | 前表最后一行既有含图单元格又含不含图单元格时，裸图折回第一个不含图且非首格单元格并删除游离 figure 块（条件全满足才归位，纯文本行不归位） |
| CSM-TABLE-003 | 表中图格内顺序/列错位 | B. 列错位：该列文字仅此一行且是图列、前一格纯图 → 文字移回前一列图后（保守条件全满足才移动）；A. 格内顺序仅作为 B 的配套——B 触发的表（含同 caption-number 跨页续表）才统一为图前文字后，其余表保持提取顺序（不把"上图下文字"当通用版式） |
| CSM-OCR-009 | 无标题条文被误升为标题 | 编号开头（章条/附录条）+ 句末标点（。！？）收尾的 heading 降级为正文段落（_demote_sentence_headed_clauses；H1 除外）——真标题不以句末标点收尾 |
| CSM-OCR-010 | 编号条文在页边界被断成两段 | 相邻段落块级合并（_merge_split_clause_paragraphs）：首段编号条文形态开头且无句末/连接标点收尾 + 次段汉字开头非编号/示例/注/表/图 + 两侧均非术语行形态（中文 U+3000 拉丁） |

---

## 6. 验证手册（离开 harness 后照此执行）

```bash
cd /home/jlx/projects/lookWhy

# 1) 全量单测（含全部回归用例）
.venv/bin/python -m unittest discover

# 2) 快捷模式流水线（提取 → 规范化 → SSIR → 回环验证 → 渲染）
#    退出码：0 = 完成且回环等价；2 = 抽取/转换失败；3 = SSIR 与 Verify 不等价
.venv/bin/python tools/mineru_full_standard.py GB_T_1.1-2020
.venv/bin/python tools/mineru_full_standard.py GB_T_43726-2024.pdf

# 3) 合规结果检查（parse-report.json 的 compliance 字段）
#    compliance = {appliedRuleSets, findingCount, findings, passed}
#    finding 字段含 ruleId、message；规则是安全网：干净文档零发现属正常，
#    单测用损坏输入触发验证
cat out/mineru/GB_T_43726-2024/03_ssir/*.parse-report.json

# 4) 渲染产物抽查（字体/字号/位置基于 PDF 内部对象）
.venv/bin/python - <<'PY'
import fitz
doc = fitz.open("out/mineru/GB_T_43726-2024/04_render/GB_T_43726-2024.render.pdf")
for page in doc:
    for span in page.get_text("dict")["blocks"]:
        for line in span.get("lines", []):
            for s in line["spans"]:
                if "单位" in s["text"]:
                    print(f"p{page.number} '{s['text']}' size={s['size']:.1f} font={s['font']} x0={s['bbox'][0]:.1f}")
PY

# 5) 语料库批量回环
.venv/bin/python tools/verify_markdown_roundtrip.py \
  --examples-dir corpus/golden/csm --output-dir out/roundtrip
```

验证要点（对应 GEN-090/091）：
- 单位行 9pt（小五号）、右对齐（x1 贴版心右缘 ≈526.9）、位于题注之下约 16.9pt；
- 脚注标记 span 尺寸 8.5pt（上标）vs 正文 10.5pt，且字号小者带 super 语义；
- 合规安全网：干净文档 GBT-H03/C06/X04 零发现（43726、1.1 实测无发现）；
- roundtrip passed（roundtrip.json 状态）。

---

## 7. 维护约定

- 新增 GBT-*/GEN-* 规则必须同步：规则文件 + 源码注释映射 + compliance 检查
  （如有）+ 回归测试 + 本表；schema（ssir.schema.json）在新增字段时必须
  同步登记（additionalProperties: false）。
- issue 码按序分配（当前 CSM-OCR 已占用 001-010；002 为条号掉点修复）。
- 本文档修改历史：
  - v0.1（2026-08-31）：初版，沉淀规则落实方法论（§1）、本会话问题→规则
    映射（§2）、详细记录（§3）、历史速查（§4）、规则速查（§5）、验证手册（§6）。
  - 2026-09-04 追加：§2 表 19/20、§3.17、§5.3 CSM-OCR-009/010——句子体
    条文误升标题降级与页边界条文断段合并（parser repair；GB_T_1.1-2020
    B.2.2/9.9.3.1/9.4.2.2 以规则实例化方式回放 canonical，早期逐实例手术
    已按用户原则回滚）。
  - 2026-08-31 追加：§2 表 9、§3.8、§4 08-31 行——示例框内嵌图
    KeepTogether 撑爆表格行（LayoutError）修复，工程规则无新规则 ID。
  - 2026-08-31 追加（第二轮）：§2 表 10-14、§3.9-3.12、§4 08-31 五行、
    §5.1 GEN-035/031/092 更新、§5.3 CSM-OCR-006/CSM-STRUCT-001——
    裸标题提升（GEN-035）、层级规范化（CSM-OCR-006）、引用前缀扩展
    （GBT-C06）、拉丁丢失后验（GEN-092）、嵌套示例内容扁平化（工程规则）。
    规则文件同步：extraction-rules.yaml（GEN-031/035/092）、
    requirements.yaml（GBT-C06）。
  - 2026-08-31 追加（第三轮）：§2 列表符号统一行、§5.3 CSM-OCR-001
    更新——破折号族混用（-/—/——/———）与 ·/•/●/○ 混读按同列表多数派
    统一（CSM-OCR-001），`UNORDERED_ITEM_RE` 增补 ·/○ 与全破折号族，
    `_list_marker` 破折号族渲染归一 ——（GBT-C12）。
