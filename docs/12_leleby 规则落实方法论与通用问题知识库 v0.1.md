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

---

## 4. 历史通用问题速查（2026-08 早期，均有规则映射）

| 日期 | 问题 | 修复 | 规则 |
|---|---|---|---|
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
| GEN-031 | normalize | must | 层次编号规范化（点分链 ≤5 层）；掉点可安全拆点则修复（CSM-OCR-002），否则不猜测 |
| GEN-032 | normalize | should | 表格单位陈述折进 table.unit；题注折叠防双题注 |
| GEN-070 | render | must | 只能注册 TrueType 轮廓字体；CFF 必须报错并给替代建议 |
| GEN-071 | render | must | 排版参数一律来自渲染 profile，源码无硬编码中文排版常数 |
| GEN-090 | verify | must | 合成 PDF 机器验证（文本层抽取查封面字段/孤立单字行/页数） |
| GEN-091 | verify | must | 字体字号验证基于 PDF 内部对象（span 级 font/size），非视觉比对 |
| GEN-092 | extract | should | 文本层质量预检（孤立 "4."/"2." 行 ≥30 或截断标准号 ≥3 → 强制 OCR；方法不一致失效 parts + 删盘重抽） |
| GEN-093 | build | must | 文后/前置要素（目次/前言/引言/参考文献/索引）是文档级要素，不得并入附录示例 |

### 5.2 需求规则（requirements.yaml，GBT-*）

| ID | source | 摘要（本知识库相关更新） |
|---|---|---|
| GBT-H03 | 7.3.1、7.3.2 | 条号点分编号；**父号加点前缀校验**（4.2.1 挂于 4.2 之下） |
| GBT-B07 | 10.4.2、9.8.4、附录F 37-40 | 表题之上居中；**单位陈述在表题之下右上方小五号宋体紧贴表格** |
| GBT-B08 | 9.8.2.1、9.7.2.1 | 题注必须形如"表X 题名"/"图X 图题"（编号必备、题名可省略） |
| GBT-C06 | 8.6.1—8.6.3 | 规范性引用文件为第 2 章；**每个引用条目应含标准文件编号与名称** |
| GBT-X04 | 9.12.1、9.12.2 | 脚注**由标记与解释成对组成**；图表脚注小写拉丁字母 a) b) 上标，标记与解释行均小写，逐图逐表编号 |
| GBT-X02 | 9.8.1.3—9.8.4 | 表编号/表题/表头/合并单元格 |
| GBT-X05 | 9.10.1—9.10.4 | 示例引导语与编号 |
| GBT-C18 | 表脚注（08-27 并入 X04） | 表脚注上角标 |

### 5.3 报告 issue 码（parser 修复记录）

| 码 | 含义 | 处理 |
|---|---|---|
| CSM-OCR-001 | 列表 marker 字形混淆（1)/l)、0)/O)） | 多数派上下文纠正（normalize 层），无法确认不纠正 |
| CSM-OCR-002 | 条号掉点 | 编号连续性可唯一拆点时修复（_repair_clause_numbers），否则保守跳过记 issue |
| CSM-OCR-003 | 术语中英文间隙 | U+200B → U+3000 + 白色汉字填充 |

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
- issue 码按序分配（当前 CSM-OCR 已占用 001-006；002 为条号掉点修复）。
- 本文档修改历史：
  - v0.1（2026-08-31）：初版，沉淀规则落实方法论（§1）、本会话问题→规则
    映射（§2）、详细记录（§3）、历史速查（§4）、规则速查（§5）、验证手册（§6）。
