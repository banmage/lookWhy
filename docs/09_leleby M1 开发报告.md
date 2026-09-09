# leleby SSIR M1 开发报告

> **状态**：已完成的 Markdown -> SSIR 基线 + PDF/MinerU 适配器交付记录
>
> **日期**：2026-08-24
>
> **用途**：记录本阶段的需求演变、已完成工作、验证证据、关键决策、问题与限制，作为后续 PDF 渲染、lookWhy 本体和 PDF/扫描件识别开发的交接依据；同时同步当前已落地的 MinerU/PDF 抽取链路。

## 1. 结论与当前可用能力

本阶段已经交付可运行的 M1 核心链路。系统可接收用户 Markdown 标准文件，对可安全修复的问题执行宽容导入并写出 `Canonical`，将 Canonical 解析为通过 Schema 校验的 SSIR JSON（可选 TTL），并完成以下回环：

```text
原始 Markdown
  -> CSM 校验、质量诊断、无语义损失的基础纠错
  -> Canonical CSM Markdown
  -> SSIR1 JSON
  -> Render.md CSM Markdown
  -> SSIR2 JSON
  -> 四层等价比较 + Critical Information Loss 检查
```

这里的核心定义是：原始 Markdown 只是导入来源；`Canonical` 是纠错后冻结的回环基线；回环验收只比较 `SSIR1` 和 `SSIR2`，不要求 Canonical 和 Render.md 的字符级或视觉级一致。

M1 已通过仓库内全部测试。对 `corpus/golden/csm/` 的 5 份产品标准 Canonical 样例进行批量回环，结果为 5/5 通过；CSM 模板的“原始 Markdown -> Canonical -> SSIR1 -> Render.md -> SSIR2”完整链路也已通过。

与此并行，项目已补齐 PDF/MinerU 抽取能力：`ssir pdf extract` 能从任意国家标准 PDF 生成 CSM Markdown，优先调用本地 `mineru`/`magic-pdf` 命令，失败时自动回退到 PyMuPDF 文本层；`tools/mineru_full_standard.py` 执行可恢复的全量抽取、CSM 合并、规范化、SSIR 解析和回旋验证。一致性地说，当前仓库中 PDF 适配器已经不是未实现的规划，而是可运行的实际功能。

## 2. 需求演变与范围决策

### 2.1 初始目标

项目最初涉及从传统 PDF 标准中使用 MinerU 提取内容，再生成 SSIR 的设想。为便于分阶段交付，随后确认应先把 PDF 解析和结构化建模解耦：无论来源为 MinerU 还是用户上传，均先产生统一的 Markdown 中间格式，再由该格式解析 SSIR。

### 2.2 M1 的最终边界

本阶段的核心工作仍然以 CSM Markdown -> SSIR 为主线，但通过后续补丁已实际落地 PDF/MinerU 抽取链路，形成“用户 Markdown + PDF 输入”两条并行入口。当前工作范围为：

- 定义并完善 CSM Markdown 模板，参考 GB/T 1.1-2020 与 GB/T 20001.10-2014；
- 准备包含图、表、公式、列表、检验规则、附录等要素的产品标准 Markdown 样例；
- 解析 CSM 并构建 SSIR JSON，提供可选 TTL 投影；
- 对用户 Markdown 进行宽容校验、可修复问题记录和产品标准质量提示；
- 实现 `Canonical -> SSIR1 -> Render.md -> SSIR2` 回旋转换与一致性验证；
- 通过 `ssir pdf extract` / `tools/mineru_full_standard.py` 将 PDF 解析为 CSM Markdown，并生成 provenance sidecar；
- 更新开发规范和面向使用者的 README。

当前实现已经包含 PDF/DOCX 入口的先行能力（PDF 解析已具备实现与 CLI），但仍保留对复杂扫描件、表格/图像精确识别、人工质量复核和 PDF 版式渲染的后续增强边界。该边界避免在未冻结中间格式前将 PDF、排版和知识图谱三类复杂问题相互耦合。

### 2.3 Canonical 定义的修正

开发中曾将回环输入直接称为“用户 Markdown”，但这会混淆两个职责：用户输入可能有 BOM、CRLF、缺失机器元数据或可安全修复的表格格式问题；而回环需要稳定、可重复的输入基线。因此已统一采用：

| 对象 | 定义 | 是否进入回环等价比较 |
|---|---|---|
| 原始 Markdown | 用户上传的输入，保留原始哈希与诊断来源。 | 否 |
| Canonical | 原始输入经安全修复、UTF-8/LF 规范化后冻结的 CSM。 | 是，作为 SSIR1 来源 |
| SSIR1 | 从 Canonical 解析得到的 SSIR 基准。 | 是 |
| Render.md | 由 SSIR1 确定性生成的 CSM。 | 是，作为 SSIR2 来源 |
| SSIR2 | 从 Render.md 重新解析得到的 SSIR。 | 是 |

这一划分应在后续 PDF/MinerU 适配器中保持不变：PDF/MinerU 产生的是“原始 CSM”，经同一 CSM 校验/纠错后才成为 Canonical。

## 3. 已完成工作

### 3.1 规范与数据准备

已阅读并参考 `corpus/reference-standards/` 中的 GB/T 1.1-2020、GB/T 20001.10-2014 以及标准元数据、结构化、机器语言表达和数字标准信息模型相关标准。完成的文档工作包括：

- 建立 [CSM 格式规范](07_leleby%20Canonical%20SSIR%20Markdown%20Format%20Specification%20v0.1.md)，定义 YAML front matter、标题与条款层级、附录、表格、图、公式、列表、机器注释、宽容导入和产品标准配置；
- 建立并补充 [CSM 到 SSIR 实现规范](08_leleby%20CSM-to-SSIR%20Implementation%20Specification%20v0.1.md)，定义输入输出、映射、CLI、报告、验收与非目标；
- 更新处理流水线、回环测试和总开发规范，使其以 Markdown Canonical/Render.md 作为 M1 回环对象；
- 提供 CSM 模板及 5 份 `corpus/golden/csm/` 产品标准样例，覆盖企业标准、团体标准、技术参数表、图占位、公式、不同列表标记、试验方法、检验规则、包装和规范性/资料性附录。

GB/T 1.1 和 GB/T 20001.10 中的可选或条件适用组成部分（例如术语、引用文件、取样、试验方法、检验规则、附录等）不会被实现为输入的绝对前置条件。缺失时进入质量提示，而不会丢弃正文或中断默认转换。

### 3.2 CSM 解析与宽容导入

实现文件：`src/leleby_ssir/parser.py`、`report.py`、`csm_normalizer.py`。

已实现的处理包括：

- UTF-8 输入读取、BOM 移除、CRLF/CR 到 LF 的内存规范化和源文件哈希记录；
- YAML front matter、H1、章节与条款、附录、普通段落、引文、图、公式、GFM 表格、列表、代码围栏和 `ssir:` 指令解析；
- 缺失或不兼容的机器元数据补全，例如 `csm-version`、文档类型、标题、标识、标准号、语言、来源和扩展对象；
- 短表格行的尾部空单元格补齐；无法安全解释的额外单元格、未闭合围栏、非 UTF-8、无效 YAML、重复显式 ID 等作为硬错误；
- 对前言、范围、产品技术要求和标准号表达进行 GB/T 质量提示；
- `ConversionReport` 输出问题代码、严重度、行号、是否修复与修复动作；
- `ssir csm normalize` 将内存中的安全修复写为 Canonical，避免用未经纠错的用户输入作为回环基线。

安全原则：正文、标准编号原文、技术数值、单位、比较符、公式、引用文本和规范性动词不可自动改写。需要人工判断的错误只报告，不“智能纠正”。

### 3.3 SSIR 构建、Schema 与导出

实现文件：`builder.py`、`validation.py`、`ssir.schema.json`、`exporters.py`、`service.py`。

- CSM AST 被映射为 SSIR 文档元数据、结构树、内容元素、表、图、公式、未知内容、来源文件、Markdown SourceAnchor、处理运行和质量评估；
- 使用项目内 Draft-07 Schema 与引用完整性检查，JSON 通过验证后才写出；
- JSON 输出采用稳定排序和固定时间戳，便于可重复测试；
- 提供 Turtle RDF 投影，并写入对应 JSON 的 SHA-256；JSON 仍是权威格式；
- 图像缺失时保留图题和占位信息，标记为部分保留，而不是删除图对象；
- 支持表格合并元数据、公式原文及 `raw`/LaTeX 形式、列表 marker 类型和 UnknownContent。

### 3.4 Markdown 回环与验证程序

实现文件：`csm_renderer.py`、`roundtrip.py`、`tools/verify_markdown_roundtrip.py`。

- `csm_renderer.py` 从 SSIR1 生成确定性的 Render.md CSM；
- `roundtrip.py` 生成身份、结构、内容、语义四层的可比较视图，忽略 ID、锚点、文件哈希、处理运行和质量评估等派生信息；
- 关键损失检查覆盖规范性用语、禁止性表述、强制条件、数值、单位、比较符、条款编号、表格单元格、公式原文、引用目标、范围与适用性；
- CLI `ssir csm roundtrip` 写出单份 Render.md 与 JSON 报告；通过返回 0，不等价返回 3；
- 批量程序接受多个输入或一个样例目录，写出逐份 Render.md、逐份报告和 `roundtrip-summary.json`；
- 增加“应 -> 宜”和表格数值变化的变异测试，验证比较器确实能报出失败，而非仅验证成功路径。

### 3.5 使用者入口与文档

`README.md` 已改为中文，包含功能范围、安装、四类 CLI 命令、输入输出、目录、程序入口和后续工作说明。主要命令如下：

```text
ssir csm validate
ssir csm normalize
ssir csm parse
ssir csm roundtrip
PYTHONPATH=src python3 tools/verify_markdown_roundtrip.py
```

CLI 分发位于 `src/leleby_ssir/cli.py`，服务边界位于 `service.py`，`python -m leleby_ssir` 由 `__main__.py` 进入同一 CLI。

### 3.6 规则库与逐条合规验证

规则是系统的“程序”，与语料数据（`corpus/`）和租户运行时数据（`storage/`）严格分离。`rules/base/` 下按标准组织规则包，当前含两套：

- `GB_T_1.1-2020/`：`requirements.yaml`（GBT-xxx 内容/结构/排版要求，逐条带 `source` 章节追溯）、`extraction-rules.yaml`（GEN-xxx 通用抽取与合成规则）、`audit.yaml`、以及规则源标准 CSM/SSIR/转换报告三件套；
- `GB_T_20001.10-2014/`：产品标准专项规则包（P10-xxx），仅对产品标准类文件叠加。

实现文件：`src/leleby_ssir/compliance.py`、`rules/base/*`。

- `verify_compliance()` 按 GEN-* → GBT-* → P10-* 三层对解析后的 SSIR 逐条验证；`is_product_standard()` 依据 document-type 或标题/章节文本判定是否加载产品标准层；
- 每条发现携带规则 ID、规则集、优先级（must→error / should→warning）、检查名和人类可读消息，经 `compliance_issues()` 合并进转换报告（service.py 的 `parse_csm_with_report` 接线）；
- 封面必备信息（GBT-C01）缺失除记 finding 外，还驱动 PDF 渲染以 “××” 占位（“ICS ××”/“×× 发布”等）并在渲染报告记录对应规则 ID；
- 抽取与渲染程序的关键函数均带“规则对应”注释，把处理逻辑逐条映射到规则 ID（如 `_cover_metadata` → GEN-013~017/019、`_cover_story` → GBT-L01~L09/GBT-C01），便于后续逐条核对与追责。

## 4. 验证记录

### 4.1 自动化测试

执行命令：

```bash
PYTHONPATH=src python3 -m unittest discover -v
```

本阶段最后一次执行结果为 26 项测试全部通过。覆盖内容包括：

- 5 份产品标准样例的 CSM -> SSIR；
- 全部 CSM 样例和模板的 Markdown 回环；
- 原始 Markdown（BOM、CRLF、缺失机器元数据）-> Canonical 后的语义一致性；
- 表格、合并单元格、图、图占位、公式、列表和附录；
- 产品标准的可选章节不阻断转换；
- 可恢复问题的报告与不可恢复问题的拒绝；
- 确定性 JSON；
- TTL 输出；
- 规范性动词和表格数值的负向变异检出；
- 规则库三层合规验证（tests/test_compliance.py 6 项）：封面必备字段（GBT-C01）、要素顺序（GBT-E03/E05/C05）、附录性质标识（GBT-C09）、图表编号（GBT-X01/X02）、产品标准定量要求带单位（P10-R02），以及驼峰/连字符元数据键的归一化。

### 4.2 批量回环

执行命令：

```bash
PYTHONPATH=src python3 tools/verify_markdown_roundtrip.py \
  --examples-dir corpus/golden/csm \
  --output-dir out/roundtrip
```

最后一次批量结果：总计 5，成功 5，失败 0。另对 CSM 模板实际执行 `normalize` 后再 `roundtrip`，结果通过。

### 4.3 静态检查

执行 `git diff --check`，通过，未发现补丁空白错误。

## 5. 开发中遇到的主要问题与处理经验

### 5.1 不要将“原始输入”直接用作回环基准

问题：用户输入可包含机械格式缺陷；若直接称其为 Canonical，重复测试会受 BOM、换行、默认元数据和表格补齐影响，导致“纠错”和“信息回环”混为一谈。

处理：增加 `normalize` 命令和 `csm_normalizer.py`，并在全部文档中将 Canonical 定义为安全修复后的冻结 CSM。原始哈希与修复记录留在转换报告中。后续新增任何输入适配器时必须沿用这个边界。

### 5.2 GB/T 要求不能简单地全部变为硬错误

问题：GB/T 1.1 和 GB/T 20001.10 既有必备要素，也有按文件类型、对象和适用条件采用的要素。若将所有章节都作为必填，会拒绝大量可用的真实标准；若完全不检查，又无法提示明显问题。

处理：区分三类情况：不可解析或可能错绑内容的错误为硬错误；机器元数据和无语义损失格式问题自动修复；正文结构或产品标准质量问题仅生成警告。后续增加领域规则时，应默认先做“可定位的提示”，只有得到明确规范依据和可恢复策略后才提高为硬错误。

### 5.3 Markdown 表现限制需要显式补偿

问题：GFM 不能原生表示单元格合并、稳定对象 ID、图像缺失原因、复杂列表标记和公式原文格式。

处理：以 `<!-- ssir:... -->` 指令补充机器信息；表格合并使用 `ssir:table-merge`，公式、图、未知内容使用稳定 ID。以后 PDF/MinerU 适配器必须生成同一套指令，不能另造一种中间格式。

### 5.4 附录看似微小的空格也会造成结构损失

问题：首次渲染 Render.md 时在“附录 A”和“（规范性）”之间加入了空格，而解析器仅接受紧凑形式。这导致附录在 SSIR2 中成为普通章节，触发 C7 条款编号损失。

处理：解析器接受两种空格形式，渲染器统一输出 GB/T 常见的紧凑形式；增加附录类型和标识的专项回环测试。经验是：渲染器必须产出解析器明确接受的 CSM 子集，且每一种结构性标题都需要回环测试。

### 5.5 等价比较必须排除派生数据，但不能只比较文本

问题：SSIR ID、源锚点、输入哈希、行号、处理运行和质量评估在重渲染后必然不同；直接 JSON 对比会产生误报。另一方面，只比较整段文本又可能遗漏表格或公式变化。

处理：生成身份、结构、内容、语义四层视图；表格、图、公式、列表和 UnknownContent 独立参与内容比较；再单列关键损失规则。后续新增 SSIR 字段时必须明确该字段属于语义数据、内容数据还是派生数据，并同步更新比较器和测试。

### 5.6 “通过测试”不等于“完整标准合规审查”

问题：当前质量规则与关键损失检查是 M1 的可执行子集，不能替代专家对 GB/T、行业标准、计量单位和产品安全法规的全面审查。

处理：README、格式规范和报告均将其描述为诊断/提示，不给出法律或完整合规结论。下一阶段若要提高规则覆盖率，应建立可版本化的 profile 与 Golden 样本，并由标准化领域专家审核规则。

## 6. 已知限制与技术债

- Markdown 解析器是面向 CSM 约束子集的实现，不是完整 CommonMark/GFM 浏览器渲染器；复杂嵌套 Markdown、HTML、脚注和跨页语义仍需扩展测试后支持。
- Render.md 是可再解析的规范化 CSM，不是 GB/T 1.1 传统 PDF 成品。它不处理封面、目次页码、页眉页脚、分页、字体、表格跨页、图像排版或印刷版式。
- 当前 SSIR 的 Turtle 只是稳定 RDF 投影，不等同于具有完整领域语义、推理规则和受控词表的 lookWhy 本体。
- 当前关键损失中的单位、引用和条件识别使用有限的规则模式；它们能覆盖现有样例，但需要随领域和语种扩展。
- CSM 的 `title-en`、发布机构、发布日期、ICS/CCS 等丰富元数据在当前 M1 映射和比较中尚未形成完整的端到端覆盖，应在扩展元数据时先补 Schema、builder、renderer 与回环测试。
- 现有样例为验证集，不应自动视为已人工签字确认的 Golden SSIR；冻结 Golden JSON 前必须人工审阅。
- 未实现生产级 API、持久化、权限、文件大小控制、并发任务和审计存储。

## 7. 后续开发建议

后续三项工作应共享 CSM、SSIR Schema、质量报告和回环测试的核心契约，不应绕过 Canonical 或直接在各适配器中各自定义结构。

### 7.1 工作 2：SSIR -> 符合 GB/T 1.1 的传统 PDF 标准

目标：从已验证的 SSIR JSON 生成可发布或可人工审阅的传统 PDF 标准文件。

建议顺序：

1. 先定义 Rendering IR：页尺寸、版心、字体、标题编号、段落、表格、图、公式、页眉页脚、封面、前言、目次与附录的排版对象；不要直接从 SSIR 拼接 PDF 字符串。
2. 以 GB/T 1.1 为依据定义可版本化的 `GB_T_1.1-2020` PDF rendering profile；明确哪些规则可自动处理、哪些必须由人工提供（封面、发布信息、分页、复杂图表）。
3. 选择可重复的 PDF 生成后端，并在 CI 中固定版本、字体和区域设置；输出 PDF 同时保留 Rendering IR、渲染配置和文件哈希。
4. 将 PDF 验收拆为语义验收与视觉验收：先保证从 SSIR 到渲染文本、表格、公式的关键内容零损失，再用页图像或 PDF 结构做版式基线比较。
5. 建立“SSIR -> PDF -> 文本/CSM -> SSIR”的后续回环，但不要把 PDF 视觉差异混入当前 Markdown M1 的等价比较。

主要风险：中文字体授权和嵌入、复杂表格分页、公式字体、图片分辨率、页码/目次更新及 PDF 可访问性。应先选择 2 至 3 个带图表和附录的 Golden 标准逐步实现。

### 7.2 工作 3：SSIR -> lookWhy 知识图谱/本体标准

目标：将 SSIR 中的文件、条款、要求、试验、检验、产品、量值、单位、引用和关系表达为 lookWhy 格式的 ontology/knowledge graph。

建议顺序：

1. 冻结 lookWhy 的命名空间、类、属性、IRI 规则、版本策略和序列化格式（建议至少明确 Turtle/JSON-LD 之一）；不要直接把现有通用 TTL 投影宣称为领域本体。
2. 制定 SSIR 到本体的映射表：结构节点映射为文档/条款资源，内容元素映射为可引用的文本陈述；要求、试验方法、检验规则和引用要有独立实体及来源回链。
3. 定义受控词表：规范性强度、关系类型、量纲/单位、产品分类、试验和检验术语；复用成熟词表时记录对齐关系。
4. 对从自然语言抽取的实体/关系区分“确定性结构映射”和“推断结果”，后者必须包含置信度、模型/规则版本和人工复核状态，不能覆盖原文 SSIR。
5. 建立 SHACL 或等价的图约束与查询测试；使用少量人工审核的 SSIR/图谱对作为 Golden 数据集。

主要风险：本体范围过宽、文本中模态词和条件的语义丢失、单位/量值建模不一致、引用版本漂移，以及自动抽取结果被误当作权威标准文本。

### 7.3 工作 4：传统 PDF/扫描标准 -> CSM Markdown

目标：补全第一步，以 PDF、扫描 PDF 或 MinerU 输出为输入，生成符合 CSM 1.0 的原始 Markdown，随后复用现有 `normalize -> Canonical -> SSIR` 链路。

建议顺序：

1. 定义输入适配器接口，输出为“原始 CSM + provenance sidecar + 资产目录”，而不是直接写 SSIR；同一接口可容纳 MinerU、OCR、DOCX 等来源。
2. 先处理文本型 PDF，再处理扫描件。文本型 PDF 要提取目录、标题、段落、表、图、公式和页码；扫描件还要管理 OCR 置信度、版面分析和人工复核队列。
3. 生成 CSM 时保留原始正文，使用既有 `ssir:` 指令记录 block ID、表格合并、图像资产与无法识别内容；不由 PDF 适配器“猜测性修正”规范性语义。
4. sidecar 至少记录原 PDF 哈希、页码、bbox、MinerU/OCR block ID、置信度、生成版本和 CSM block 映射；SSIR M1 现有 Markdown anchor 可与它关联，但不得伪造 PDF 坐标。
5. 建立含原 PDF、期望 CSM、人工审查注记的 Golden 集；分别度量 OCR 字符错误、标题层级、表格单元格、公式、图/表编号和 Markdown 到 SSIR 的回环结果。

主要风险：扫描质量、双栏/跨页表、页眉页脚混入正文、公式识别、图像裁切、表格合并、标准编号和附录误识别。首批应只选版式较稳定、可人工核验的 PDF，并为低置信度内容设计显式的 UnknownContent/待复核标记。

## 8. 下次开发前检查清单

开始任一后续阶段前，建议先确认：

1. `PYTHONPATH=src python3 -m unittest discover -v` 仍全部通过。
2. 对准备修改的 CSM/SSIR 字段，明确它是源语义、表现信息、来源信息还是派生信息，并同步更新 Schema、builder、renderer、比较器和测试。
3. 不修改或删除现有 `corpus/golden/csm/` 样例的正文语义；如需变更，应新增样例并说明原因。
4. 任何自动“修复”均必须可逆或可报告，且不得改写规范性文本的语义。
5. PDF、OCR、PDF 渲染和本体推断的中间产物必须有版本、哈希和来源映射。
6. 新增功能先写最小 Golden 测试和负向测试，再扩大样例范围。
