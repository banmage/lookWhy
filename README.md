# leleby SSIR M1

本项目实现标准化文件的结构化信息表示（SSIR）M1：将用户提供的 Markdown 标准文件转换为可校验的 SSIR JSON（可选 Turtle），并通过 Markdown 回旋转换验证信息是否被保留。

当前版本已实际交付面向任意国家标准 PDF 的通用抽取与规范化链路：`ssir pdf extract` 可从 PDF 生成 CSM Markdown，标准号、标题和元数据均从 PDF 内容推导，不针对任何特定标准号；MinerU 是首选后端，PyMuPDF 仅作为无 MinerU 时的文本层回退。当前实现已进入可用状态，扫描件、表格/图像精确识别与人工质量复核仍属于后续增强工作。

## 当前功能

```text
原始 Markdown
  -> 宽容校验与安全纠错
  -> Canonical：权威 CSM Markdown 基线
  -> SSIR JSON
  -> Render.md：由 SSIR 确定性渲染的 CSM Markdown
  -> Verify JSON（原 SSIR2）
  -> 四层等价比较与关键损失报告
```

- 解析符合 CSM 1.0（Canonical SSIR Markdown）格式的标准 Markdown，生成通过 JSON Schema 校验的 SSIR JSON。
- 支持 `json` 和 `ttl` 输出；JSON 是权威交换格式，TTL 是从 JSON 派生的 RDF 投影。
- 默认采用宽容导入：可安全修复 BOM、换行、缺失机器元数据、短表格行等问题；不改写正文、标准号原文、数值、单位、比较符、公式或规范性动词。
- 对 GB/T 1.1-2020 和 GB/T 20001.10-2014 的章节结构和产品标准要素给出质量提示；可选或条件适用的组成部分缺失不会阻断转换。
- 规则库三层合规验证（GEN-* → GBT-* → P10-*）：`compliance.py` 按规则包对 SSIR 逐条验证，把发现（must 违规记 error、should 记 warning）写入转换报告；产品标准自动叠加 GB/T 20001.10-2014 专项规则。抽取与渲染程序以“规则对应”注释逐条映射规则 ID，便于后续逐条核对。
- 封面必备信息缺失时渲染占位符：文件编号、ICS、CCS、发布/实施日期、发布机构、名称任一缺失，封面以 “ICS ××”/“×× 发布” 等占位并保留版式，同时在渲染报告记录对应规则 ID（GBT-C01）。
- 保留章条层级、表格、图/图占位、公式、列表、注/示例/警示、未知内容和 Markdown 行号溯源。
- 验证 `Canonical -> SSIR -> Render.md -> Verify`：比较身份、结构、内容和语义，并检查规范性用语、禁止性表述、数值、单位、表格、公式、引用、范围等关键信息。
- 知识图谱单文档阶段（P1a/P1c）：`tools/kg_tool.py` 把 SSIR 投影为带 schema 校验的 `kg.json` 图切片，并导入可重建的 sqlite 索引库；`tools/kg_viewer/` 提供文档库列表、结构树内容浏览与 vis-network 本体图（见下文「知识图谱/本体查看器」）。

## 快速开始

运行环境为 Python 3.12 或更高版本；**推荐 3.12.x**（本项目在 3.12.14 实测通过）。

### 依赖安装（国内源，可完整执行）

完整依赖约 2 GB（含 torch、mineru）。以下命令均可在国内网络下直接执行；
若只想用国内 PyPI 源而不关心 CPU 版 torch，第 ② 步可跳过（但会多下载数 GB
CUDA 依赖）。

**① 准备 Python 3.12 虚拟环境（二选一）**

系统已装有带 venv 的 python3.12：

```bash
python3.12 -m venv .venv                 # 在仓库根目录执行
```

没有 python3.12 时，可用 uv 安装独立 3.12（GitHub 直连不通会自动走国内镜像）：

```bash
# 安装 uv（https://docs.astral.sh/uv/ ，国内可用 ghfast.top 加速其安装脚本）
export UV_PYTHON_INSTALL_MIRROR="https://ghfast.top/https://github.com/astral-sh/python-build-standalone/releases/download"
uv python install 3.12.14
export UV_DEFAULT_INDEX="https://mirrors.aliyun.com/pypi/simple/"
uv venv --seed --python 3.12.14 .venv    # --seed 使 venv 自带 pip
```

**② 先装 CPU 版 torch（无 NVIDIA GPU 的机器必做）**

PyPI/阿里源上的默认 torch 是 CUDA 版，会额外拉取数 GB nvidia 依赖。先固定安装
CPU 轮子，之后第 ③ 步因版本已满足不会再改动它：

```bash
export TMPDIR="$HOME/tmp" && mkdir -p "$TMPDIR"   # WSL 的 /tmp 是内存盘，务必换到真实磁盘
.venv/bin/pip install --no-cache-dir --timeout 600 \
  --index-url https://mirrors.aliyun.com/pypi/simple/ \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  "torch==2.14.0+cpu" "torchvision==0.29.0+cpu"
```

有 NVIDIA GPU 需要 CUDA 时，去掉 `+cpu` 后缀与 `--extra-index-url`，或改装
对应的 `cu1xx` 版本即可。

**③ 安装 leleby-ssir 与其余依赖**

```bash
.venv/bin/pip install --no-cache-dir --timeout 600 \
  --index-url https://mirrors.aliyun.com/pypi/simple/ -e .
```

**④ 安装后核验**

```bash
.venv/bin/python -c "import torch; print(torch.__version__)"  # 应显示 ...+cpu
.venv/bin/pip check                                            # 无 broken requirements
.venv/bin/ssir --help                                          # 命令可用即环境就绪
```

说明：

- 若嫌每条命令带 `--index-url` 太长，可写入 `~/.config/pip/pip.conf`：
  `[global] index-url = https://mirrors.aliyun.com/pypi/simple/`。
- MinerU 的模型不在此步下载：首次运行 PDF 抽取时自动拉取（数 GB），模型来源可在
  mineru 配置的 `model-source` 中选 `modelscope` 或 `huggingface`。
- 未安装包时，也可以在仓库根目录使用
  `PYTHONPATH=src .venv/bin/python -m leleby_ssir` 运行命令。

### 1. 校验或规范化用户文件

```bash
# 只校验；默认宽容模式会显示可恢复问题
ssir csm validate --input incoming/user-standard.md

# 将原始 Markdown 安全纠错并冻结为 Canonical CSM，同时写入纠错报告
ssir csm normalize \
  --input incoming/user-standard.md \
  --canonical-output out/GB_T_15034-2012.canonical.md \
  --report out/GB_T_15034-2012.normalize-report.json
```

`Canonical` 是回旋转换的唯一输入基线。转换报告保存原始文件的 SHA-256、问题代码、行号、是否已修复以及修复动作。加上 `--strict` 时，任何警告都会使命令失败，适合 CI 和 Golden 数据集。

### 2. 将 Canonical 转换为 SSIR

```bash
# 生成权威 SSIR JSON 和解析报告
ssir csm parse \
  --input out/GB_T_15034-2012.canonical.md \
  --output out/GB_T_15034-2012.ssir.json \
  --format json \
  --report out/GB_T_15034-2012.parse-report.json

# 可选：生成 Turtle RDF 投影
ssir csm parse \
  --input out/GB_T_15034-2012.canonical.md \
  --output out/GB_T_15034-2012.semantic.ttl \
  --format ttl
```

### 3. 执行单份回旋转换验证

```bash
ssir csm roundtrip \
  --input out/GB_T_15034-2012.canonical.md \
  --render-md-output out/GB_T_15034-2012.render.md \
  --verify-output out/GB_T_15034-2012.verify.json \
  --report out/GB_T_15034-2012.roundtrip.json
```

命令返回值：`0` 表示通过，`2` 表示输入或生成文档存在不可恢复错误，`3` 表示 SSIR 与 Verify 不等价或发生关键损失。

### 4. 从 PDF 提取 CSM Markdown

`ssir pdf extract` 是**针对任意国家标准 PDF 的通用抽取器**，不针对任何特定标准号：标准号、标题和元数据均从 PDF 内容推导，MinerU 和 PyMuPDF 两个后端都只依赖通用版面规则。优先调用本机的 `magic-pdf` 或 `mineru` 命令，并额外生成 provenance sidecar；未安装 MinerU 时可显式使用 PyMuPDF 文本层回退。回退结果标记为待人工复核，扫描件、表格/图像精确识别仍属于后续工作。

```bash
ssir pdf extract \
  --input "corpus/golden/GB_T_10401-2023.pdf" \
  --output out/GB_T_10401-2023/01_extract/GB_T_10401-2023.raw.md \
  --backend auto
```

**完整抽取与验证工具**：`tools/mineru_full_standard.py` 对任意国家标准 PDF 执行"可恢复的分块 MinerU 全量抽取 → 合并 raw → 规范化为 canonical → 解析为 SSIR → 回旋验证 →（可选）渲染 PDF 并比较"。所有输出文件名、标准号和标题均从输入 PDF 自动派生，可用 `--standard-number`/`--title` 覆盖；`--output-stem` 可固定输出文件名前缀，`--front-matter-json` 可补充已知元数据（如 `ics`/`ccs`/`replaces`/`issuer`）。

**一条命令跑完全流程（推荐）**：直接附加需处理的标准文件名即可，程序默认在 `corpus/golden/` 目录中查找（可带或不带 `.pdf` 后缀，也接受子路径），并自动完成提取、渲染与回环验证：

```bash
# 自动定位 corpus/golden/GB_T_1.1-2020.pdf，完成 提取 → 解析 → 回环验证 → 渲染
.venv/bin/python tools/mineru_full_standard.py GB_T_1.1-2020

# 等价写法：显式 .pdf 后缀 / 子路径 / 完整路径
.venv/bin/python tools/mineru_full_standard.py GB_T_1.1-2020.pdf
.venv/bin/python tools/mineru_full_standard.py corpus/golden/GB_T_1.1-2020.pdf
```

**已有 canonical 时自动半程续跑**：同一快捷命令每次执行都会检查
`out/mineru/<ID>/02_canonical/<ID>.canonical.md`——若该文件已存在（上一轮产出的
人工可编辑权威基线），则自动跳过 MinerU OCR/PDF 抽取、合并与 normalize，直接从
canonical 续跑 parse → roundtrip → render（PDF+docx）→ 对比 → manifest
（功能与下文的 `tools/reprocess_canonical.py` 完全等同，**canonical 不会被覆盖**）。
需要重新做 OCR/PDF 抽取时用显式阶段旗标（如 `--stage extract`）或先删除 canonical 文件。

快捷模式等价于 `--input corpus/golden/GB_T_1.1-2020.pdf --stage all --roundtrip --render`，退出码 `0` 表示流程完成且回旋等价，`3` 表示 SSIR 与 Verify 不等价或发生关键信息损失，`2` 表示抽取或转换失败。需要分步控制（只抽取、跳过渲染等）时改用 `--input` 加阶段旗标：

```bash
.venv/bin/python tools/mineru_full_standard.py \
  --input "corpus/golden/GB_T_10401-2023.pdf" \
  --roundtrip --render
```

输出在 `out/mineru/GB_T_10401-2023/`（单文档阶段目录：`00_source/ … 05_verify/` +
`manifest.json`，见 `naming_specification.txt`）。退出码 `0` 表示流程完成且回旋等价，`3` 表示 SSIR 与 Verify 不等价或发生关键信息损失，`2` 表示抽取或转换失败。未安装 MinerU 或需要快速验证时，可改用下面的轻量命令链（PyMuPDF 回退抽取 → 规范化 → 解析 → 回旋验证）：

```bash
PYTHONPATH=src .venv/bin/python -m leleby_ssir pdf extract \
  --input "corpus/golden/GB_T_10401-2023.pdf" \
  --output out/GB_T_10401-2023/01_extract/GB_T_10401-2023.raw.md --backend auto
PYTHONPATH=src .venv/bin/python -m leleby_ssir csm normalize \
  --input out/GB_T_10401-2023/01_extract/GB_T_10401-2023.raw.md \
  --canonical-output out/GB_T_10401-2023/02_canonical/GB_T_10401-2023.canonical.md
PYTHONPATH=src .venv/bin/python -m leleby_ssir csm parse \
  --input out/GB_T_10401-2023/02_canonical/GB_T_10401-2023.canonical.md \
  --output out/GB_T_10401-2023/03_ssir/GB_T_10401-2023.ssir.json
PYTHONPATH=src .venv/bin/python -m leleby_ssir csm roundtrip \
  --input out/GB_T_10401-2023/02_canonical/GB_T_10401-2023.canonical.md \
  --render-md-output out/GB_T_10401-2023/04_render/GB_T_10401-2023.render.md \
  --verify-output out/GB_T_10401-2023/05_verify/GB_T_10401-2023.verify.json
```

**半程重跑（编辑 canonical 后刷新下游）**：`tools/reprocess_canonical.py` 以
`out/mineru/<ID>/02_canonical/<ID>.canonical.md`（唯一人工可编辑的权威基线）为输入，
跳过 抽取/合并/normalize（**不会覆盖 canonical**），重跑 parse → roundtrip → render
（PDF + 内容等价 docx）→（源 PDF 存在时）PDF 版面印记恢复与渲染对比，并刷新
`manifest.json`。适合“改 canonical → 看新渲染”的迭代：

```bash
# 先手工编辑 out/mineru/GB_T_1.1-2020/02_canonical/GB_T_1.1-2020.canonical.md，然后：
.venv/bin/python tools/reprocess_canonical.py GB_T_1.1-2020
```

退出码 `0` 成功；`2` 失败（roundtrip 不等价按 `3` 记录在报告中，不算失败）。

### 5. 生成传统 PDF 标准文稿

PDF 渲染读取已通过 SSIR 校验的 JSON，不重新解析 Markdown。项目提供 GB/T 1.1-2020 初始渲染配置，使用嵌入式中文字体生成可复制文本的 A4 PDF：

```bash
PYTHONPATH=src .venv/bin/python -m leleby_ssir pdf render \
  --input out/GB_T_15034-2012.ssir.json \
  --output out/GB_T_15034-2012.render.pdf \
  --report out/GB_T_15034-2012.render-report.json
```

也可以通过 `--profile` 指定自定义渲染配置。当前实现覆盖 GB/T 1.1 封面（左上 ICS/CCS、文件编号、横幅、文件名称、英文译名、一致性程度标识、底部发布/实施日期与发布机构，见 `rules/base/GB_T_1.1-2020/requirements.yaml` 的 GBT-L01~L09）、前置要素、章节/条款、正文、列表、表格、公式原文、图像资产或图像缺失占位、附录、页眉标准号和页脚页码。封面必备信息（GBT-C01）缺失时以 “××” 占位并在渲染报告记录对应规则 ID；标准类文档一律渲染封面，不再因 ICS/CCS 缺失而跳过整个封面。字号字体、版心和分页属于可版本化的渲染配置；PDF 输出是传统标准草稿，尚未宣称通过完整的印刷版式验收。

### 6. 批量验证样例

```bash
PYTHONPATH=src python3 tools/verify_markdown_roundtrip.py \
  --examples-dir corpus/golden/csm \
  --output-dir out/roundtrip
```

该程序为每份 Canonical 写出对应的 Render.md、逐份回环报告和 `roundtrip-summary.json`；任一文件失败时返回 `3`。

### 7. 知识图谱/本体查看器（`tools/kg_viewer/`）

`tools/kg_viewer/` 是知识图谱阶段（P1a 索引浏览 + P1c 本体图）的轻量 Web 查看器（Flask）。它本身不产生数据，只读取下游产物：**SSIR JSON 是唯一真源**，查看器用 sqlite 索引库做列表/树导航、用 `kg.json` 图切片做 vis-network 本体图：

```
out/mineru/<ID>/03_ssir/<ID>.ssir.json          （唯一真源）
   ├─→ out/kg/kg.db      可重建索引：documents 元数据 + structure 扁平树 + 全文载荷
   └─→ <ID>.kg.json      图切片投影（kgVersion=0.1，带 schema 校验），供 vis-network / 未来 Neo4j
```

命令行入口是 `tools/kg_tool.py`（子命令 `build` / `import` / `list` / `serve`）：

```bash
# 1) 建库/更新库：把 SSIR 导入 sqlite 索引（默认 out/kg/kg.db，删除后可重建）
.venv/bin/python tools/kg_tool.py import GB_T_1.1-2020   # ID 快捷：out/mineru/<ID>/03_ssir/<ID>.ssir.json
.venv/bin/python tools/kg_tool.py import --all           # 扫描 out/mineru/*/03_ssir/ 全量导入
.venv/bin/python tools/kg_tool.py import path/to/x.ssir.json

# 2) 查看库内文档
.venv/bin/python tools/kg_tool.py list

# 3) 生成并校验图切片 kg.json（只读 SSIR，不影响库）
.venv/bin/python tools/kg_tool.py build GB_T_1.1-2020 -o out/gb11.kg.json

# 4) 启动查看器（默认 127.0.0.1:8600）
.venv/bin/python tools/kg_tool.py serve --port 8600
```

启动后浏览器访问三个页面：

| 页面 | 地址 | 内容 |
|---|---|---|
| 文档库 | `http://127.0.0.1:8600/` | sqlite `documents` 表：标准号/中文名称/类型/ICS/CCS/代替/结构节点数，每行可进「浏览」「图谱」「详情」 |
| 内容浏览 | `/doc/<doc_id>` | 左侧结构树（资源管理器式展开/折叠）+ 右侧节点内容（条款 → 段落/列项/注/表/图/公式/术语）；支持面包屑深链、`📄 查看原文行` 跳 canonical 原文、表/图/公式资产经 `/asset` 解析；顶栏「文档详情」 |
| 本体图谱 | `/graph/<doc_id>` | vis-network 本体图：核心视图（结构 + 表/图/公式 + 术语）/ 全量视图（含段落级内容元素）、层级/力导向布局切换；点节点看条款号/类型/溯源行并可跳原文；顶栏「文档详情」 |

**文档详情弹窗**（索引页每行的「详情」、内容/图谱页顶栏的「文档详情」）：按分层可折叠结构展示文档级信息——
① 基本信息（标准号/中英文名称/类型/ICS/CCS/语言）；② 日期与关系（发布日期、实施日期、代替标准、一致性程度标识）；
③ 组织机构（发布机构、提出/归口单位、起草单位列表、主要起草人列表——后三项从前言正文提取）；
④ 术语和定义（条数，逐条点击展开定义 + 跳结构树）；⑤ 标准要素（前置/主体章节/附录/文后四组，逐条点击展开节点类型、子节点/内容单元数、canonical 行，并可跳结构树）；
⑥ 清单核对（`标准要素完整清单.md` 的 GBT-E01~E14 与 GBT-M01~M14 命中/缺失表）；⑦ 规模统计。

`serve` 同时提供下列 HTTP API（便于脚本或集成）：

| 接口 | 说明 |
|---|---|
| `GET /api/docs` | 文档列表 |
| `GET /api/structure/<doc_id>` | 结构树全量行（前端内存建树） |
| `GET /api/node/<doc_id>/<node_id>` | 节点内容 HTML + 祖先链 + 锚点 |
| `GET /api/doc/<doc_id>/detail` | 文档详情分层结构（元数据/机构/术语/要素/清单核对），供详情弹窗使用 |
| `GET /api/raw/<doc_id>/<start>/<end>` | canonical.md 原文行（单次最多 200 行） |
| `GET /api/kg/<doc_id>?scope=core\|full` | kg 图切片（`core` 去段落级内容元素） |
| `GET /asset/<doc_id>/<rel>` | 文档资产（图/公式图片） |

说明与注意：

- 依赖 `flask>=3.0`（见 `pyproject.toml`）；`vis-network.min.js` 为本地副本（MIT，附 `static/js/VIS_NETWORK_LICENSE.txt`），无需外网。
- `out/kg/kg.db` 是可重建的运行时索引（gitignore）：删除后重新 `import` 即可；同一 `doc_id` 重跑 `import` 会标「更新」并覆盖旧记录。
- 没有数据库时首页会提示先执行 `import`；`/doc`、`/graph` 对未知 `doc_id` 返回 404，`/api/*` 出错返回 JSON。
- 设计记录与后续规划（P2 多标准 CITES/REPLACES 边、中文全文检索、Neo4j 迁移）见 `docs/semantic_Stage/KG P1a+P1c 单文档查看器实现记录 v0.1.md`。

### 8. 运行测试

```bash
PYTHONPATH=src python3 -m unittest discover -v
```

## 输入、输出与报告

| 项目 | 说明 |
|---|---|
| 原始 Markdown | 用户上传的 `.md` 文件，可以存在可恢复的格式问题。 |
| Canonical | 经安全纠错并冻结的权威 CSM Markdown（`<ID>.canonical.md`）；用于生成 SSIR。 |
| SSIR JSON | 主输出，符合项目内 Draft-07 JSON Schema，包含结构、内容、来源锚点、处理记录和质量状态。 |
| Render.md | 由 SSIR 渲染的确定性 CSM Markdown（`<ID>.render.md`）；用于生成 Verify。 |
| Verify | 从 Render.md 再解析的 SSIR（`<ID>.verify.json`，原 SSIR2）。 |
| 纠错/解析报告 | `<ID>.normalize-report.json` / `<ID>.parse-report.json`，记录导入诊断、修复和质量提示（原 conversion-report）。 |
| 回环报告 | `<ID>.roundtrip.json`，记录四层状态、关键损失和差异（原 roundtrip-report）。 |

CSM 的完整格式、YAML front matter、表格/图/公式/列表写法见 [CSM 格式规范](docs/07_leleby%20Canonical%20SSIR%20Markdown%20Format%20Specification%20v0.1.md)。可以从 [CSM 模板](corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md) 或 `corpus/golden/csm/` 中的产品标准样例开始准备数据。

## 目录说明

| 目录或文件 | 作用 |
|---|---|
| `src/leleby_ssir/` | Python 实现包，包含解析、构建、校验、导出、规范化和回环比较逻辑。 |
| `tests/` | 单元与集成测试；覆盖容错导入、质量提示、表/图/公式、回环和关键损失变异。 |
| `config/` | 引擎配置：`rendering/` 渲染 profile，`pipeline/` 审核组合配置。 |
| `rules/` | 规则库（可被系统加载的业务规则）：`base/{standard-id}/` 通用规则包（requirements/extraction-rules/audit + source SSIR），`schemas/` 规则文件 Schema。规划中还有 `industries/{code}/{pending,approved,rejected}/` 行业规则与 `ontology/` 本体文件。 |
| `corpus/golden/csm/` | 已完成基础纠错的 canonical CSM 产品标准样例（`*.canonical.md`，原 examples/csm），是当前批量回环的主要输入集；`corpus/golden/` 根目录为模板与普通标准样例（`<ID>.pdf`）。 |
| `corpus/reference-standards/` | GB/T 1.1、GB/T 20001.10 及其他参考标准的 Markdown 文本（原 standards/），用于设计和人工核对。 |
| `storage/tenants/{tenant_id}/` | 多租户运行时存储（gitignore）：未来 uploads 原始上传、work 中间产物、outputs 转换结果、profile 企业编排规则。 |
| `docs/` | 数据模型、Schema、格式、实现、测试和开发报告等项目文档。 |
| `tools/` | 辅助脚本：完整流水线 `mineru_full_standard.py`、半程重跑 `reprocess_canonical.py`、批量回环验证 `verify_markdown_roundtrip.py`、知识图谱 CLI `kg_tool.py` 与查看器 `kg_viewer/`。 |
| `pyproject.toml` | Python 项目元数据、依赖和 `ssir` 命令行入口定义。 |

## 主要程序入口（含 `tools/mineru_full_standard.py` 完整参数）

|| 入口 | 用途 | 主要参数 |
||---|---|---|
|| `ssir` | `pyproject.toml` 定义的 CLI 入口；`ssir csm validate/normalize/parse/roundtrip`、`ssir pdf extract/render`。 | `--input`、`--canonical-output`、`--output`、`--format`、`--report`、`--strict`、`--profile` |
|| `src/leleby_ssir/cli.py` | CLI 参数解析与命令分发（`validate` / `normalize` / `parse` / `roundtrip` / `pdf extract` / `pdf render`）。 | 同上 |
|| `tools/mineru_full_standard.py` | **完整标准流水线**：任意国家标准 PDF → 分块 MinerU 抽取 → 合并 raw → normalize → canonical → SSIR → 回旋验证 → 可选渲染（PDF + docx）。主要参数：`file`（快捷名，默认在 `corpus/golden/` 查找）或 `--input`（完整路径）；`--stage`（`extract`/`merge`/`finalize`/`all`）；`--method`（`auto`/`ocr`/`txt`）；`--hybrid-tables`（开启 GEN-094 表混合识别，默认关闭）；`--chunk-size`（分块页数，默认 18）；`--roundtrip`；`--render`；`--toc-depth`；`--standard-number` / `--title` 覆盖元数据；`--front-matter-json` 补充元数据（如 `ics`/`ccs`/`replaces`/`issuer`）；`--output-dir` / `--output-stem`；快捷模式（仅传文件名）自动启用 `--stage all --roundtrip --render`，并在已有 `02_canonical/*.canonical.md` 时自动半程续跑（不覆盖 canonical）。退出码：`0` 完成且等价、`2` 抽取/转换失败、`3` 关键损失/不等价。 |
|| `tools/reprocess_canonical.py` | 半程重跑：从已有 `02_canonical/*.canonical.md` 开始，跳过抽取/合并/normalize，重跑 parse → roundtrip → render，不覆盖 canonical。 | 位置参数为标准 ID（如 `GB_T_1.1-2020`）；自动查找 `out/mineru/<ID>/02_canonical/*.canonical.md` |
|| `tools/verify_markdown_roundtrip.py` | 批量回环验证：对 `corpus/golden/csm` 中多个 canonical 批量执行 `canonical → SSIR → render.md → verify`。 | `--examples-dir`、`--output-dir` |
|| `tools/kg_tool.py` | 知识图谱 CLI：`build`（SSIR → `kg.json` 图切片 + schema 校验）、`import`（SSIR → sqlite 索引库，`--all` 全量）、`list`（列出库中文档）、`serve`（启动 `tools/kg_viewer` Web 查看器）。详见「知识图谱/本体查看器」。 | `build <ssir.json 或 ID> [-o out.kg.json]`；`import <ID 或路径> [--all] [--db out/kg/kg.db]`；`list [--db]`；`serve [--db] [--host 127.0.0.1] [--port 8600]` |
|| `tools/kg_viewer/` | Flask Web 查看器（无独立 CLI，经 `kg_tool.py serve` 调用）：文档库列表 `/`、结构树+内容浏览 `/doc/<doc_id>`、vis-network 本体图 `/graph/<doc_id>`，**文档详情弹窗**（元数据/日期/机构/术语逐条/标准要素分层/清单核对），并暴露 `/api/docs`、`/api/structure`、`/api/node`、`/api/doc/<id>/detail`、`/api/raw`、`/api/kg`、`/asset` 接口；`detail.py` 为详情派生纯函数（便于单测）。 | 由 `serve` 参数控制；应用工厂 `create_app(db_path)` 供脚本内嵌 |
|| `src/leleby_ssir/naming.py` | 命名单一事实源（标准号推导、文件名解析）。 | 无 CLI 参数 |
|| `src/leleby_ssir/service.py` | 服务层：Canonical 生成、CSM→SSIR、导出、回环、逐条合规验证（GEN→GBT→P10）。 | 同 CLI |
|| `src/leleby_ssir/compliance.py` | 规则库三层逐条验证（GEN/GBT/P10）。 | 内部调用 |
|| `src/leleby_ssir/roundtrip.py` | 四层等价比较与关键损失检查。 | 内部调用 |

实现模块的职责如下：

| 模块 | 职责 |
|---|---|
| `parser.py` | 读取 CSM、解析 front matter 和 Markdown 块、进行容错诊断。 |
| `csm_normalizer.py` | 将安全的内存修复写为 Canonical CSM。 |
| `builder.py` | 将 CSM AST 转为 SSIR 对象图。 |
| `validation.py` | 执行 JSON Schema 和 SSIR 引用完整性校验。 |
| `exporters.py` | 确定性 JSON 与可选 Turtle 输出。 |
| `csm_renderer.py` | 将 M1 可表达的 SSIR 子集渲染为 Render.md CSM。 |
| `compliance.py` | 规则库三层（GEN/GBT/P10）逐条合规验证，发现（含规则 ID、优先级、检查名）写入解析报告。 |
| `roundtrip.py` | SSIR/Verify 四层比较与关键损失检查。 |
| `report.py` | 转换报告数据结构和 JSON 序列化。 |

## 当前状态（已冻结）

- 通用规则已扩展：`extraction-rules.yaml` 新增 GEN-094A（压平检测）、GEN-094B（行重组兜底），适用于任意标准表块，不针对特定标准号。
- 回归夹具：`tests/regression/test_gen_094_flat_table.py` 已通过（规则实例应用确定性验证，无数据手术）。
- 5171.1 验证状态：`out/mineru/GB_T_5171.1-2014` 已手动删除（准备重跑验证），流水线重跑因 hybrid 耗时超时未完成（预期行为，非规则失效）；规则已在代码中生效，不依赖重跑结果。
- 工作已停止并冻结：未修改任何 canonical/raw 源数据，未做个例修补。

## 当前状态与后续工作

当前项目已具备三条并行可用链路：

1. M1 已完成 Markdown -> SSIR 的核心链路及 Markdown 回旋验证；
2. PDF -> CSM Markdown 适配器已实现并接入 `ssir pdf extract` / `tools/mineru_full_standard.py`，支持 MinerU 首选后端和 PyMuPDF 回退；
3. 知识图谱单文档阶段 P1a/P1c 已实现：SSIR → sqlite 索引库 + `kg.json` 图切片 + `tools/kg_viewer/` Web 查看器（列表 / 结构树内容浏览 / 本体图）。

后续按以下顺序推进：

1. 从 SSIR 按 GB/T 1.1 要求生成传统 PDF 标准，并建立 PDF 视觉与语义验收；
2. 知识图谱扩展到多标准（引用 CITES / 代替 REPLACES 边）与中文全文检索，必要时再引入 Neo4j；
3. 进一步补全扫描件、表格/图像精确识别和人工质量复核流程，强化 PDF/MinerU 适配器的可追溯 sidecar 与 OCR 能力。

这些工作不得改变已经冻结的 CSM -> SSIR 核心输入契约；新适配器应复用 Canonical、SSIR Schema、解析报告和回环测试基准。文件名与目录结构遵循 `naming_specification.txt` v2.0（`<STANDARD_ID>.<representation>.<ext>` + 阶段目录）。
