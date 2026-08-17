# leleby CSM-to-SSIR Implementation Specification v0.1

> **文档状态**：当前开发基线 | **版本**：0.1 | **日期**：2026-08-17
>
> **目标读者**：开发团队、QA、AI Coding Agent
>
> **前置规范**：
> 1. leleby SSIR Data Model v0.4
> 2. leleby SSIR JSON Schema Specification v0.3
> 3. leleby Canonical SSIR Markdown Format Specification v0.1
> 4. GB/T 1.1-2020、GB/T 20001.10-2014（产品标准配置适用时）

## 1. 目标和边界

本迭代（M1）实现下列确定链路：

```text
CSM Markdown -> CSMValidator -> CSMNormalizer -> Markdown AST
-> Extraction IR -> SSIR Builder -> SSIR Validator -> SSIR JSON
-> Optional Turtle Exporter
```

M1 的目标是让用户直接提交符合 CSM 1.0 的 Markdown 标准文件，并得到可校验、可追溯的 SSIR 文档。权威输出格式为 SSIR JSON；Turtle 是从已通过 JSON Schema 与语义校验的 JSON 派生的可选 RDF 视图。

M1 明确不实现下列能力：

- PDF、扫描 PDF、DOCX 的上传和解析；
- MinerU、OCR、PDF 页面/坐标提取和 PDF provenance sidecar 的生成；
- SSIR 到 DOCX/PDF 的规范性渲染；
- 文档再提取和 Round-trip Equivalence；
- L4 实体、关系和本体推理。

这些能力保留为 M2+ 的适配器和流水线扩展。M1 不得安装 MinerU、PyMuPDF、OCR、LibreOffice、Celery、Redis 或数据库作为运行前提。

## 2. 输入和输出契约

### 2.1 输入

M1 接受一个 UTF-8（无 BOM）、LF 换行的 `.md` 文件，且必须满足 CSM 1.0：

- YAML front matter 中存在 `csm-version: "1.0"`、文档标识、标题、语言、来源模式和 `extensions`；
- 仅一个 H1，且与 front matter `title` 一致；
- 标题层级、章条编号、表格、图、公式、列表、注和 `ssir` 指令满足 CSM 规范；
- `source.mode` 为 `user-markdown` 或 `mineru-pdf`。M1 支持前者；后者只在用户已提供合法 CSM 时按 Markdown 解析，不能执行 MinerU；
- 可选 provenance sidecar 在 M1 中只校验其文件名、哈希和 Markdown block 映射，不解析或生成 PDF 坐标。

允许输入中存在 `extensions.quality-notices`。它们应转为 SSIR 的质量提示，不得被当作正文内容，也不得自动改写用户正文。

### 2.2 主输出：SSIR JSON

成功时生成 `<input-stem>.ssir.json`。该文件必须：

- 通过 SSIR JSON Schema v0.3 和 M1 语义验证；
- 声明 `ssirVersion: "0.4"`；
- 将输入文件表示为 `SourceFile`，`mimeType` 为 `text/markdown`，文件哈希使用 SHA-256；
- 为每个结构节点和内容块创建 `SourceAnchor`，使用 `anchorType: "markdown"`、Markdown 起止行和 AST 节点路径或 CSM block ID；
- 不填充 `pdfPageIndex`、`documentPageLabel`、`bbox` 等 PDF 专属字段；
- 完整保留 CSM 中的表格单元格、图题/图占位、公式原文和编号、列表 marker、注/示例/警示、UnknownContent 和出现顺序；
- 在 `QualityAssessment` 中记录 CSM 结构错误、保真警告和产品标准 `quality-notices`。

M1 的最低目标是 Markdown 可追溯的 Level 3 SSIR；“Level 3”仅表示源锚点完整，不表示具备 PDF 页面或坐标溯源。

### 2.3 可选输出：Turtle

`--format ttl` 或 `format=ttl` 只能在 JSON 主输出验证成功后执行。Turtle：

- 使用固定命名空间 `https://leleby.io/ns/ssir#`；
- 表达文档身份、结构树、内容对象、表格/图/公式标识和 Markdown 溯源；
- 必须在输出中声明对应 JSON 文件的 SHA-256；
- 不是权威存储或回读格式，不得替代 `.ssir.json`，也不得承担 JSON 中无法无损表达的复杂富文本语义。

## 3. 处理阶段

| 阶段 | 输入 | 输出 | 必须执行的工作 |
|------|------|------|----------------|
| M1-1 CSM 预检 | Markdown 字节流 | 文件诊断 | UTF-8/LF、front matter、扩展名、文件哈希、大小限制 |
| M1-2 语法与结构校验 | CSM 文本 | CSM AST + 诊断 | CommonMark/GFM 解析、H1、编号/层级、指令、表格列数、唯一 ID |
| M1-3 规范化 | 合法 AST | 规范 AST | 仅执行 CSM 允许的无语义损失规范化；不得改动规范性动词、数值、单位或编号 |
| M1-4 Extraction IR | 规范 AST | parser-neutral IR | 生成按文档顺序排列的 heading、paragraph、table、figure、formula、list、note、unknown block |
| M1-5 SSIR 构建 | Extraction IR | SSIR 对象图 | 构建元数据、结构树、内容注册表、CanonicalText、TextSpan、Markdown SourceAnchor |
| M1-6 验证与导出 | SSIR 对象图 | JSON / 可选 TTL | Schema、引用完整性、语义约束、质量评估、确定性序列化 |

任何阶段发现结构性错误必须停止并返回错误；保真或产品标准质量问题可继续生成 JSON，但必须使 `QualityAssessment` 为 `PARTIAL`。

## 4. CSM 到 SSIR 的映射

| CSM 元素 | SSIR 目标 | 关键规则 |
|----------|-----------|----------|
| YAML front matter | `SSIRDocument.metadata`、`SourceFile`、`ProcessingRun` | `standard-number`、标题和来源信息均须保留；`extensions` 中未识别项保留为扩展或质量提示 |
| H1 和 `##` 前置/后置要素 | `StructuralNode` | H1 是文档名称；前言、目次、参考文献等为 `documentBlock` |
| 编号章、条、附录标题 | `StructuralNode` 树 | 从标题深度和编号建立父子关系；编号原样保存，不在 M1 自动更正 |
| 普通段落 | `ContentElement` | 保存原始正文和 `sortOrder`；关联所属结构节点 |
| GFM 表格 + `ssir:table` | `Table`、行、单元格、表注 | 表题、表号、表头、展开的合并信息均须保留 |
| 图语法或图占位 + `ssir:figure` | `Figure` | 缺失资产保留为占位和质量警告，不得删除图 |
| 公式 + `ssir:formula` | `Formula` | 保留 LaTeX/raw 表示和式号；不得转述为自然语言 |
| Markdown/指令列表 | `ListItem` | 保留顺序、层级和 marker 类型，包括 `a）`、`1）` 等 |
| 注、示例、警示、脚注 | `ContentElement` | 区分表现类型；前缀文本必须保留 |
| `ssir:unknown` | `UnknownContent` | 原文逐字保存；不得静默丢弃 |
| `quality-notices` | `QualityAssessment` | 映射 severity、code、message 和可定位的 source anchor |

所有由 AST 产生的块 ID 必须稳定：输入已有 `ssir:block id` 时保留；否则以规范化 AST 路径生成。相同输入字节、相同解析器版本和相同配置必须生成相同的对象 ID、排序和 JSON 字节序列。

## 5. 最小模块划分

```text
packages/
  core/                 # SSIR Pydantic 模型、Extraction IR、枚举、JSON Schema
  csm/
    reader.py           # 编码、文件哈希、front matter
    parser.py           # CommonMark/GFM -> 带位置的 AST
    directives.py       # ssir 指令解析与关联
    validator.py        # CSM 1.0 和产品标准配置检查
    normalizer.py       # 允许的无损规范化
    extraction_ir.py    # AST -> Extraction IR
  ssir_builder/         # Extraction IR -> SSIR，对应既有模型职责
  validator/            # Schema、结构、引用、Markdown provenance、质量评估
  exporters/
    json_exporter.py    # 确定性 JSON（必需）
    turtle_exporter.py  # 可选 RDF 投影
apps/
  cli/                  # M1 必需 CLI
  api/                  # M1 可选同步 FastAPI 路由
tests/
  unit/ integration/ golden/ negative/
```

`packages/csm` 只依赖 Markdown/HTML 注释语法和 CSM 契约；不得导入 MinerU、OCR 或 PDF 包。未来 M2 必须通过一个 `PDF -> CSM` 适配器产出完全相同的 CSM 文件，再复用本模块。

## 6. CLI 和 API

### 6.1 CLI（M1 必需）

```text
ssir csm validate --input examples/csm/Q_TQDZ_004-2026.csm.md
ssir csm parse --input examples/csm/Q_TQDZ_004-2026.csm.md --output out/Q_TQDZ_004-2026.ssir.json --format json
ssir csm parse --input examples/csm/Q_TQDZ_004-2026.csm.md --output out/Q_TQDZ_004-2026.ttl --format ttl
```

`validate` 在无结构性错误时返回 0；有质量警告时仍返回 0 并输出诊断；存在结构性错误返回非 0。`parse` 只有在 JSON 验证通过后才写入目标文件，避免留下半成品。

### 6.2 HTTP API（M1 可选）

`POST /v1/csm/parse` 使用 `multipart/form-data`：

| 字段 | 必填 | 说明 |
|------|------|------|
| `file` | 是 | 一个 `.md` CSM 文件 |
| `format` | 否 | `json`（默认）或 `ttl` |
| `strict` | 否 | `true` 时将质量警告提升为 422；默认 `false` |

成功响应为 `200`，包含 SSIR JSON（或 TTL）和 `qualityAssessment`。错误响应：`400`（请求参数）、`415`（非 Markdown）、`422`（CSM/Schema/严格模式质量错误）、`500`（内部错误）。该接口同步执行；超过 M1 文件大小上限时返回 `413`，不引入 Celery。

## 7. 测试与验收

M1 初始 Golden 输入集如下：

| 输入 | 必测特征 |
|------|----------|
| `examples/csm/Q_PMRZ_9-2024.csm.md` | 前言、术语、图占位、表格、字母列项、产品标准质量提示 |
| `examples/csm/Q_TQDZ_004-2026.csm.md` | 目次、参数/试验方法对应表、多类列表、检验规则、标签和随行文件、产品标准质量提示 |
| `examples/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md` | CSM 输入契约、公式、附录和参考文献；仅做结构测试 |

验收门槛：

1. 两份 CSM 样例均能生成通过 JSON Schema 的 SSIR JSON。
2. 每个章节、段落、表格、图、公式、列表和 UnknownContent 均有 Markdown `SourceAnchor`；不得出现伪造的 PDF 锚点。
3. 表格行/列/单元格、图题/占位、式号、列表 marker、注/警示和出现顺序 100% 保留。
4. `quality-notices` 必须出现在 `QualityAssessment`，且不改变原始正文。
5. 同一输入连续运行两次，稳定对象 ID、排序和确定性 JSON 输出必须完全一致。
6. 畸形 front matter、重复 SSIR ID、章节跳号、表格列数不一致和未知指令必须有明确的负向测试。
7. `format=ttl` 时，先完成 JSON Schema 验证；TTL 中必须可反查文档 ID 和 JSON SHA-256。

Golden JSON 只能由人工审阅后冻结到 `fixtures/golden/csm/`。系统首次输出只能称为 candidate，不得直接提交为 golden baseline。

## 8. 实施顺序

1. 冻结 CSM 1.0、Markdown `SourceAnchor` 和 JSON Schema 的 M1 扩展；建立 Python 项目、依赖锁定和 CLI 骨架。
2. 实现 reader、front matter、带位置的 Markdown AST、`ssir` 指令和 CSM 结构校验。
3. 实现 AST 到 Extraction IR 的映射，再实现 SSIR 元数据、结构、内容、表格、图、公式、列表、UnknownContent 和 Markdown provenance 构建器。
4. 实现 JSON Schema/语义验证、`QualityAssessment`、确定性 JSON 导出和两份样例的集成测试。
5. 实现可选 Turtle exporter 与同步 HTTP API；审核并冻结 Golden SSIR JSON。
6. M1 验收后再启动 M2：由 MinerU/PDF 适配器生成同一 CSM 1.0，不改变本文件定义的 CSM → SSIR 核心。

## 9. 非目标和兼容原则

- M1 不依据自然语言“修复”标准正文；允许的修复仅限 CSM 规范中定义的无语义损失规范化。
- 用户原始编号或产品标准编写问题以 `quality-notices`/`QualityAssessment` 提示；只有用户明确授权的规范化版本才可修改正文。
- M2 的 PDF 页面、bbox、MinerU block ID 和图像资产应通过 provenance sidecar 增补，不能改变 M1 已生成的逻辑结构、内容 ID 或 Markdown 溯源。
- 所有未来输入适配器都必须输出 CSM 1.0，禁止绕过 CSM 直接生成 SSIR。
