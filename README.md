# leleby SSIR M1

本项目实现标准化文件的结构化信息表示（SSIR）M1：将用户提供的 Markdown 标准文件转换为可校验的 SSIR JSON（可选 Turtle），并通过 Markdown 回旋转换验证信息是否被保留。

当前版本已实际交付面向任意国家标准 PDF 的通用抽取与规范化链路：`ssir pdf extract` 可从 PDF 生成 CSM Markdown，标准号、标题和元数据均从 PDF 内容推导，不针对任何特定标准号；MinerU 是首选后端，PyMuPDF 仅作为无 MinerU 时的文本层回退。当前实现已进入可用状态，扫描件、表格/图像精确识别与人工质量复核仍属于后续增强工作。

## 当前功能

```text
原始 Markdown
  -> 宽容校验与安全纠错
  -> Std0：冻结的 CSM Markdown 基线
  -> SSIR1 JSON
  -> Std1：由 SSIR1 确定性渲染的 CSM Markdown
  -> SSIR2 JSON
  -> 四层等价比较与关键损失报告
```

- 解析符合 CSM 1.0（Canonical SSIR Markdown）格式的标准 Markdown，生成通过 JSON Schema 校验的 SSIR JSON。
- 支持 `json` 和 `ttl` 输出；JSON 是权威交换格式，TTL 是从 JSON 派生的 RDF 投影。
- 默认采用宽容导入：可安全修复 BOM、换行、缺失机器元数据、短表格行等问题；不改写正文、标准号原文、数值、单位、比较符、公式或规范性动词。
- 对 GB/T 1.1-2020 和 GB/T 20001.10-2014 的章节结构和产品标准要素给出质量提示；可选或条件适用的组成部分缺失不会阻断转换。
- 保留章条层级、表格、图/图占位、公式、列表、注/示例/警示、未知内容和 Markdown 行号溯源。
- 验证 `Std0 -> SSIR1 -> Std1 -> SSIR2`：比较身份、结构、内容和语义，并检查规范性用语、禁止性表述、数值、单位、表格、公式、引用、范围等关键信息。

## 快速开始

运行环境为 Python 3.11 或更高版本。

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

若希望直接启用 MinerU PDF 后端，请同时确保系统中可用 `mineru`（或 `magic-pdf` 兼容 CLI）命令；`pyproject.toml` 已加入 `mineru` 依赖，安装后会一并放入环境。

未安装包时，也可以在仓库根目录使用 `PYTHONPATH=src python3 -m leleby_ssir` 运行命令。

### 1. 校验或规范化用户文件

```bash
# 只校验；默认宽容模式会显示可恢复问题
ssir csm validate --input incoming/user-standard.md

# 将原始 Markdown 安全纠错并冻结为 Std0，同时写入转换报告
ssir csm normalize \
  --input incoming/user-standard.md \
  --std0-output out/user-standard.std0.csm.md \
  --report out/user-standard.std0.conversion-report.json
```

`Std0` 是回旋转换的唯一输入基线。转换报告保存原始文件的 SHA-256、问题代码、行号、是否已修复以及修复动作。加上 `--strict` 时，任何警告都会使命令失败，适合 CI 和 Golden 数据集。

### 2. 将 Std0 转换为 SSIR

```bash
# 生成权威 SSIR JSON 和转换报告
ssir csm parse \
  --input out/user-standard.std0.csm.md \
  --output out/user-standard.ssir.json \
  --format json \
  --report out/user-standard.conversion-report.json

# 可选：生成 Turtle RDF 投影
ssir csm parse \
  --input out/user-standard.std0.csm.md \
  --output out/user-standard.ttl \
  --format ttl
```

### 3. 执行单份回旋转换验证

```bash
ssir csm roundtrip \
  --input out/user-standard.std0.csm.md \
  --std1-output out/user-standard.std1.csm.md \
  --report out/user-standard.roundtrip-report.json
```

命令返回值：`0` 表示通过，`2` 表示输入或生成文档存在不可恢复错误，`3` 表示 SSIR1 与 SSIR2 不等价或发生关键损失。

### 4. 从 PDF 提取 CSM Markdown

`ssir pdf extract` 是**针对任意国家标准 PDF 的通用抽取器**，不针对任何特定标准号：标准号、标题和元数据均从 PDF 内容推导，MinerU 和 PyMuPDF 两个后端都只依赖通用版面规则。优先调用本机的 `magic-pdf` 或 `mineru` 命令，并额外生成 provenance sidecar；未安装 MinerU 时可显式使用 PyMuPDF 文本层回退。回退结果标记为待人工复核，扫描件、表格/图像精确识别仍属于后续工作。

```bash
ssir pdf extract \
  --input "examples/GBT 10401-2023.pdf" \
  --output out/GBT-10401-2023.extracted.csm.md \
  --backend auto
```

**完整抽取与验证工具**：`tools/mineru_full_standard.py` 对任意国家标准 PDF 执行"可恢复的分块 MinerU 全量抽取 → 合并 CSM → 规范化为 Std0 → 解析为 SSIR → 回旋验证 →（可选）渲染 PDF 并比较"。所有输出文件名、标准号和标题均从输入 PDF 自动派生，可用 `--standard-number`/`--title` 覆盖；`--output-stem` 可固定输出文件名前缀，`--front-matter-json` 可补充已知元数据（如 `ics`/`ccs`/`replaces`/`issuer`）：

```bash
.venv/bin/python tools/mineru_full_standard.py \
  --input "examples/GBT 10401-2023.pdf" \
  --roundtrip --render
```

输出在 `out/mineru/gbt-10401-2023/`。退出码 `0` 表示流程完成且回旋等价，`3` 表示 SSIR1 与 SSIR2 不等价或发生关键信息损失，`2` 表示抽取或转换失败。未安装 MinerU 或需要快速验证时，可改用下面的轻量命令链（PyMuPDF 回退抽取 → 规范化 → 解析 → 回旋验证）：

```bash
PYTHONPATH=src .venv/bin/python -m leleby_ssir pdf extract \
  --input "examples/GBT 10401-2023.pdf" \
  --output out/gbt-10401-2023/gbt-10401-2023.csm.md --backend auto
PYTHONPATH=src .venv/bin/python -m leleby_ssir csm normalize \
  --input out/gbt-10401-2023/gbt-10401-2023.csm.md \
  --std0-output out/gbt-10401-2023/gbt-10401-2023.std0.csm.md
PYTHONPATH=src .venv/bin/python -m leleby_ssir csm parse \
  --input out/gbt-10401-2023/gbt-10401-2023.std0.csm.md \
  --output out/gbt-10401-2023/gbt-10401-2023.ssir.json
PYTHONPATH=src .venv/bin/python -m leleby_ssir csm roundtrip \
  --input out/gbt-10401-2023/gbt-10401-2023.std0.csm.md \
  --std1-output out/gbt-10401-2023/gbt-10401-2023.std1.csm.md
```

### 5. 生成传统 PDF 标准文稿

PDF 渲染读取已通过 SSIR 校验的 JSON，不重新解析 Markdown。项目提供 GB/T 1.1-2020 初始渲染配置，使用嵌入式中文字体生成可复制文本的 A4 PDF：

```bash
PYTHONPATH=src .venv/bin/python -m leleby_ssir pdf render \
  --input out/user-standard.ssir.json \
  --output out/user-standard.pdf \
  --report out/user-standard.render-report.json
```

也可以通过 `--profile` 指定自定义渲染配置。当前实现覆盖封面标题、前置要素、章节/条款、正文、列表、表格、公式原文、图像资产或图像缺失占位、附录、页眉标准号和页脚页码。字号字体、版心和分页属于可版本化的渲染配置；PDF 输出是传统标准草稿，尚未宣称通过完整的印刷版式验收。

### 6. 批量验证样例

```bash
PYTHONPATH=src python3 tools/verify_markdown_roundtrip.py \
  --examples-dir examples/csm \
  --output-dir out/roundtrip
```

该程序为每份 Std0 写出对应的 Std1、逐份回环报告和 `roundtrip-summary.json`；任一文件失败时返回 `3`。

### 7. 运行测试

```bash
PYTHONPATH=src python3 -m unittest discover -v
```

## 输入、输出与报告

| 项目 | 说明 |
|---|---|
| 原始 Markdown | 用户上传的 `.md` 文件，可以存在可恢复的格式问题。 |
| Std0 | 经安全纠错并冻结的 CSM Markdown；用于生成 SSIR1。 |
| SSIR JSON | 主输出，符合项目内 Draft-07 JSON Schema，包含结构、内容、来源锚点、处理记录和质量状态。 |
| Std1 | 由 SSIR1 渲染的确定性 CSM Markdown；用于生成 SSIR2。 |
| 转换报告 | `<输出>.conversion-report.json`，记录导入诊断、修复和质量提示。 |
| 回环报告 | `<Std1>.roundtrip-report.json`，记录四层状态、关键损失和差异。 |

CSM 的完整格式、YAML front matter、表格/图/公式/列表写法见 [CSM 格式规范](docs/07_leleby%20Canonical%20SSIR%20Markdown%20Format%20Specification%20v0.1.md)。可以从 [CSM 模板](examples/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md) 或 `examples/csm/` 中的产品标准样例开始准备数据。

## 目录说明

| 目录或文件 | 作用 |
|---|---|
| `src/leleby_ssir/` | Python 实现包，包含解析、构建、校验、导出、规范化和回环比较逻辑。 |
| `tests/` | 单元与集成测试；覆盖容错导入、质量提示、表/图/公式、回环和关键损失变异。 |
| `examples/` | CSM 模板、普通标准示例和早期参考数据。 |
| `examples/csm/` | 已完成基础纠错的 Std0 产品标准样例，是当前批量回环的主要输入集。 |
| `standards/` | GB/T 1.1、GB/T 20001.10 及其他参考标准的 Markdown 文本，用于设计和人工核对。 |
| `docs/` | 数据模型、Schema、格式、实现、测试和开发报告等项目文档。 |
| `tools/` | 辅助脚本，包括 Schema 抽取和批量回环验证。 |
| `pyproject.toml` | Python 项目元数据、依赖和 `ssir` 命令行入口定义。 |

## 主要程序入口

| 入口 | 用途 |
|---|---|
| `ssir` | 安装项目后可用的命令行入口，定义在 `pyproject.toml`。 |
| `src/leleby_ssir/__main__.py` | `python3 -m leleby_ssir` 的模块入口。 |
| `src/leleby_ssir/cli.py` | CLI 参数解析和命令分发：`validate`、`normalize`、`parse`、`roundtrip`、`pdf extract`、`pdf render`。 |
| `src/leleby_ssir/service.py` | 面向 CLI 和未来 HTTP API 的转换服务：Std0 生成、CSM 转 SSIR、导出和回环。 |
| `tools/verify_markdown_roundtrip.py` | 对一个或多个 Std0 文件批量执行回环验证。 |
| `tools/mineru_full_standard.py` | 对任意国家标准 PDF 执行可恢复的分块 MinerU 全量抽取、CSM 合并、SSIR 解析、回旋验证和可选 PDF 渲染比较。 |

实现模块的职责如下：

| 模块 | 职责 |
|---|---|
| `parser.py` | 读取 CSM、解析 front matter 和 Markdown 块、进行容错诊断。 |
| `csm_normalizer.py` | 将安全的内存修复写为 Std0。 |
| `builder.py` | 将 CSM AST 转为 SSIR 对象图。 |
| `validation.py` | 执行 JSON Schema 和 SSIR 引用完整性校验。 |
| `exporters.py` | 确定性 JSON 与可选 Turtle 输出。 |
| `csm_renderer.py` | 将 M1 可表达的 SSIR 子集渲染为 Std1。 |
| `roundtrip.py` | SSIR1/SSIR2 四层比较与关键损失检查。 |
| `report.py` | 转换报告数据结构和 JSON 序列化。 |

## 当前状态与后续工作

当前项目已具备两条并行可用链路：

1. M1 已完成 Markdown -> SSIR 的核心链路及 Markdown 回旋验证；
2. PDF -> CSM Markdown 适配器已实现并接入 `ssir pdf extract` / `tools/mineru_full_standard.py`，支持 MinerU 首选后端和 PyMuPDF 回退。

后续按以下顺序推进：

1. 从 SSIR 按 GB/T 1.1 要求生成传统 PDF 标准，并建立 PDF 视觉与语义验收；
2. 从 SSIR 生成知识图谱/本体表达，即 lookWhy 格式标准，并定义 SSIR 到本体的稳定映射和校验；
3. 进一步补全扫描件、表格/图像精确识别和人工质量复核流程，强化 PDF/MinerU 适配器的可追溯 sidecar 与 OCR 能力。

这些工作不得改变已经冻结的 CSM -> SSIR 核心输入契约；新适配器应复用 Std0、SSIR Schema、转换报告和回环测试基准。
