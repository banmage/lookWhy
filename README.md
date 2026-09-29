# leleby SSIR M1

把中文国家标准（PDF 或已有抽取稿）转成**可校验的结构化表示（SSIR）**，并渲染回传统标准版式的
PDF 草稿与等价的 markdown。核心链路是 MinerU raw（json/md）→ CSM Markdown（Canonical）→
SSIR JSON → render.pdf + render.md（SSIR 的标准 markdown 投影）；抽取侧用 MinerU 识别 PDF，
渲染侧用 reportlab 生成可复制文本的 A4 PDF。**回环验证与 docx 渲染已于 2026-09-22 永久下线**。

**M1 范围**：Markdown → SSIR 核心链路、PDF → CSM 抽取、SSIR → PDF 渲染、知识图谱单文档查看器。
扫描件质量、表格/图像精确识别与人工复核流程属后续增强。

---

## 1. 功能概览

### 1.1 数据链路

```text
PDF ──(MinerU 抽取)──▶ 01_extract/<ID>.raw.md ──┐
rawFile/<ID>.json（MinerU middle.json）─────────┤
rawFile/<ID>.md（云端 MinerU / 人工整理）───────┘
                                                │
                        normalize（安全纠错）   ▼
                    02_canonical/<ID>.canonical.md   ← 唯一人工可编辑的权威基线
                                                │
                             parse（SSIR 构建） ▼
                    03_ssir/<ID>.ssir.json       ──▶ render.pdf / render-report.json
                                                │
                    04_render/<ID>.render.pdf + <ID>.render.md（markdown 投影）
                                                │
              验证（独立程序，可选）：SSIR markdown 投影 + 合规/质量报告 + PDF 对比
                    05_verify/<ID>.verify.json、04_render/<ID>.render-comparison.json
```

### 1.2 能力

- **CSM → SSIR**：解析符合 CSM 格式的标准 Markdown，生成通过 JSON Schema 校验的 SSIR JSON（可选 `ttl` RDF 投影）。
- **宽容纠错**：可安全修复 BOM、换行、缺失机器元数据、短表格行等；不改写正文、标准号、数值、单位、比较符、公式与规范性动词。
- **PDF 抽取**：MinerU 为首选后端（含文本层质量预检、可选 hybrid 表格通道），无 MinerU 时回退 PyMuPDF 文本层。
- **版式还原渲染**：GB/T 1.1 封面/前置要素/章条/表格/图/公式/附录/页眉页脚；封面必备信息缺失时以 `××` 占位并记录规则 ID（GBT-C01），不伪造数据。
- **三层规则合规**：`GEN-*` → `GBT-*` → `P10-*` 逐条验证，must 违规记 error、should 记 warning，写入解析报告。
- **独立验证**：`tools/verify_conversion.py` 生成 SSIR markdown 投影与合规/质量报告，并可选与源 PDF 做版面/文本量对比（回环四层比较已下线）。
- **规范性引用管理**：解析层把第 2 章清单与正文引用点抽成 `SSIR.references`（被引标准号/版本/名称/引用类型/被引条款/出现条款 + 引用性质），可列出某标准引用的全部文件及本文内部 表/图/式 引用点（`tools/list_references.py`，精确到条款与元素 id）。
- **知识图谱**：SSIR → `kg.json` 图切片 + 可重建 sqlite 索引 + Web 查看器（结构树浏览与本体图）。
- **溯源**：SSIR 保留章条层级、Markdown 行号锚点与处理记录。

### 1.3 三条链路与程序入口

代码分三层，`tools/` 下每个程序都只是薄壳，阶段实现集中在 `src/leleby_ssir/`。

| 层 | 程序 | 输入 → 输出 | 不负责 |
|---|---|---|---|
| 抽取 | `tools/mineru_full_standard.py` | PDF → `01_extract/<ID>.raw.md`（+ `parts/`、`00_source/`） | 不做 normalize / SSIR / 渲染（`--stage all` 例外，见 §4.3） |
| 构建 | `tools/build_ssir.py` | raw（`.md`/`.json`）或 canonical → `02_canonical/` → `03_ssir/` → `render.pdf` + `render.md` → `manifest.json` | 不做 OCR 抽取；**不做验证** |
| 验证 | `tools/verify_conversion.py` | SSIR markdown 投影 + 合规/质量报告（+ 可选 PDF 对比），只读产物 | 不生成 canonical、不改任何输入 |
| 引用查询 | `tools/list_references.py` | 某标准的规范性引用清单（六元组 + 出现条款/被引条款/内部引用点），只读产物 | 不重跑构建、不改 canonical |
| CLI | `ssir`（`src/leleby_ssir/cli.py`） | 单阶段命令：`csm validate/normalize/parse/project`、`pdf extract/render`、`references` | 不编排全流程 |

**两个可人工修改的起点**（都能独立重跑下游）：`rawFile`（或 `01_extract/*.raw.md`）与
`02_canonical/<ID>.canonical.md`。canonical 是权威基线，重跑下游时**永不被写回**。

---

## 2. 安装

### 2.1 环境要求

- Python **3.12+**（推荐 3.12.x，本项目在 3.12.14 实测通过）
- 依赖：`PyYAML`、`jsonschema`、`reportlab`、`PyMuPDF`、`flask`（见 `pyproject.toml`）
- 可选：`mineru` + `torch`（PDF 抽取用；完整约 2 GB）
- 字体：渲染用 TrueType 中文字体，仓库已带 `config/rendering/fonts/`

### 2.2 安装步骤（国内源）

**① 准备 Python 3.12 虚拟环境（二选一）**

```bash
python3.12 -m venv .venv                      # 在仓库根目录执行
```

没有 python3.12 时用 uv 装独立 3.12（GitHub 直连不通会自动走国内镜像）：

```bash
export UV_PYTHON_INSTALL_MIRROR="https://ghfast.top/https://github.com/astral-sh/python-build-standalone/releases/download"
uv python install 3.12.14
export UV_DEFAULT_INDEX="https://mirrors.aliyun.com/pypi/simple/"
uv venv --seed --python 3.12.14 .venv         # --seed 使 venv 自带 pip
```

**② 先装 CPU 版 torch（无 NVIDIA GPU 时必做）**

阿里源上的默认 torch 是 CUDA 版，会额外拉取数 GB nvidia 依赖；先固定 CPU 轮子，第 ③ 步就不会再改动它。

```bash
export TMPDIR="$HOME/tmp" && mkdir -p "$TMPDIR"   # WSL 的 /tmp 是内存盘，务必换到真实磁盘
.venv/bin/pip install --no-cache-dir --timeout 600 \
  --index-url https://mirrors.aliyun.com/pypi/simple/ \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  "torch==2.14.0+cpu" "torchvision==0.29.0+cpu"
```

需要 CUDA 时去掉 `+cpu` 与 `--extra-index-url`，或改装对应 `cu1xx` 版本。

**③ 安装本项目与其余依赖**

```bash
.venv/bin/pip install --no-cache-dir --timeout 600 \
  --index-url https://mirrors.aliyun.com/pypi/simple/ -e .
```

### 2.3 核验

```bash
.venv/bin/python -c "import torch; print(torch.__version__)"   # 应显示 ...+cpu
.venv/bin/pip check                                            # 无 broken requirements
.venv/bin/ssir --help                                          # 命令可用即环境就绪
.venv/bin/python -m unittest discover                          # 全量单测（约 10 秒）
```

说明：

- 嫌命令太长可写入 `~/.config/pip/pip.conf`：`[global] index-url = https://mirrors.aliyun.com/pypi/simple/`。
- 未安装包时，也可在仓库根目录用 `PYTHONPATH=src .venv/bin/python -m leleby_ssir <子命令>` 运行；本文档其余示例
  统一用 `.venv/bin/python tools/<工具>.py` 或 `PYTHONPATH=src .venv/bin/python -m leleby_ssir`。
- MinerU 的模型不在此步下载：首次 PDF 抽取时自动拉取（数 GB），模型来源可在 mineru 配置的
  `model-source` 中选 `modelscope` 或 `huggingface`（`--hf-endpoint` 可指定镜像）。

---

## 3. 快速开始

三个场景覆盖绝大多数用法。产物统一落在 `out/mineru/<ID>/`（`<ID>` 形如 `GB_T_10401-2023`）。

### 3.1 场景 A：已有 raw → canonical → SSIR → PDF（最常用）

输入可以是云端 MinerU 的 markdown、MinerU `middle.json`、历史 `01_extract/*.raw.md` 或人工整理稿。

```bash
# 一条命令跑完构建（raw.json 或 .md 都可以；省略 --source-pdf 则不做脚注回收/几何印记）
.venv/bin/python tools/build_ssir.py rawFile/GB_T_20001.6-2017.json \
  --source-pdf corpus/golden/GB_T_20001.6-2017.pdf
```

日志依次经过 raw 落盘 → MinerU 标记适配 → 封面字段 → normalize → canonical → parse → SSIR →
render，最后打印 `{"output": ".../04_render/<ID>.render.pdf", "pageCount": …, "warnings": …}` 并以退出码 `0` 结束。
产物：

| 路径（`out/mineru/<ID>/`） | 内容 |
|---|---|
| `01_extract/<ID>.raw.md`、`.provenance.json` | 归一后的 raw 与输入溯源（远程图下载、失败列表） |
| `02_canonical/<ID>.canonical.md`（+ `normalize-report.json`） | **权威基线**（可人工编辑）与纠错报告 |
| `03_ssir/<ID>.ssir.json`（+ `parse-report.json`） | SSIR 与解析/合规报告 |
| `04_render/<ID>.render.pdf`（+ `render-report.json`） | 最终 PDF 与页数/警告报告 |
| `manifest.json` | 各阶段产物索引 |

需要验证时单独跑（验证不从属于构建流程）：

```bash
.venv/bin/python tools/verify_conversion.py GB_T_20001.6-2017 --source-pdf corpus/golden/GB_T_20001.6-2017.pdf
```

### 3.2 场景 B：从 PDF 抽取出 raw，再构建

```bash
# ① 抽取（文件名默认在 corpus/golden/ 下解析；= --stage all --render）
.venv/bin/python tools/mineru_full_standard.py GB_T_1.1-2020

# ② 只抽取/合并，供后续用 build_ssir 反复构建
.venv/bin/python tools/mineru_full_standard.py GB_T_1.1-2020 --stage extract
.venv/bin/python tools/mineru_full_standard.py GB_T_1.1-2020 --stage merge

# ③ 构建（从抽取产物起跑；canonical 已存在时默认拒绝覆盖）
.venv/bin/python tools/build_ssir.py GB_T_1.1-2020
```

无 MinerU 或用 PyMuPDF 快速取文本层：

```bash
PYTHONPATH=src .venv/bin/python -m leleby_ssir pdf extract \
  --input corpus/golden/GB_T_1.1-2020.pdf \
  --output out/GB_T_1.1-2020.csm.md --backend pymupdf
```

### 3.3 场景 C：手工编辑 canonical 后重新渲染

canonical 允许人工校核（改错字、补丢失内容、调结构），改完只重跑下游即可：

```bash
$EDITOR out/mineru/GB_T_20001.6-2017/02_canonical/GB_T_20001.6-2017.canonical.md

# 传 canonical 文件、文档根目录或裸 ID 都可以
.venv/bin/python tools/build_ssir.py GB_T_20001.6-2017
.venv/bin/python tools/reprocess_canonical.py GB_T_20001.6-2017     # 等价入口
```

三条纪律：

- canonical **不会被静默覆盖**；只有显式 `--overwrite-canonical` 才会用 raw 重建（会丢弃人工编辑，先备份）。
- 改动必须是合法 CSM（见 [CSM 格式规范](docs/07_leleby%20Canonical%20SSIR%20Markdown%20Format%20Specification%20v0.1.md)），
  否则解析报告会给出 issue 码与行号。
- 重跑会重新套用源 PDF 的几何印记（示例框样式、图源尺寸），图尺寸不会因重跑而漂移。

改完想确认改动确实进了 PDF（不靠肉眼截图）：

```bash
.venv/bin/python - <<'PY'
import re, pymupdf
pdf = pymupdf.open("out/mineru/GB_T_20001.6-2017/04_render/GB_T_20001.6-2017.render.pdf")
text = "".join(page.get_text() for page in pdf)
print("页数:", pdf.page_count, "| 改动在文本层:", "你写的片段" in re.sub(r"\s+", "", text))
PY
```

---

## 4. 程序与参数

### 4.1 `tools/build_ssir.py` — 构建（推荐主入口）

```bash
.venv/bin/python tools/build_ssir.py <raw|canonical|文档根目录|裸 ID> [选项]
```

| 参数 | 说明 |
|---|---|
| `file`（位置） | raw 路径（`.md` / `.json`）、`.canonical.md`、文档根目录，或裸 ID（先找 `out/mineru/<ID>/01_extract/<ID>.raw.md`，再找 `rawFile/<ID>.md`、`rawFile/<ID>.json`） |
| `--input PATH` | 与位置参数二选一 |
| `--source-pdf PATH` | 源 PDF：条文脚注回收（CSM-OCR-014）、版面印记、PDF 对比；缺省查 `corpus/golden/<ID>.pdf`，查不到就跳过 |
| `--output-dir DIR` | 文档根目录（默认 `out/mineru/<ID>`） |
| `--output-stem STEM` | 产物文件名前缀（默认由标准号规范化：`GB/T` → `GB_T`） |
| `--standard-number` / `--title` | 覆盖 front matter 的标准号 / 标题（默认从封面区或文件名推导，取不到留空不猜） |
| `--front-matter-json FILE` | 补充/覆盖 front matter 顶层键，如 `{"ics": "29.160.30", "issuer": "…"}` |
| `--side-by-side-middle PATH` | 并列版面识别（GEN-095）用的**整份文档** `middle.json`（与文档根 `parts/` 合并使用）；输入是 `.json` 时默认就用它自己 |
| `--toc-depth N\|all` | 渲染目次最大层数（默认 2） |
| `--no-image-download` | 不下载 raw 里的远程图片（保留原链接） |
| `--no-render` | 只跑到 canonical + SSIR，不渲染 |
| `--verify` | 渲染后**另起进程**调起 `tools/verify_conversion.py`（默认不做任何验证） |
| `--no-pdf-comparison` | 仅配合 `--verify`：跳过 PDF 版面/文本量对比 |
| `--overwrite-canonical` | 用 raw 重建 canonical（**丢弃人工编辑**） |

退出码：`0` 成功，`2` 失败。中间产物可随时删除重跑（`out/` 是 gitignore 的运行时目录）。

### 4.2 `tools/verify_conversion.py` — 独立验证

```bash
.venv/bin/python tools/verify_conversion.py <ID|文档根|canonical.md|ssir.json> [--source-pdf PDF] [--no-pdf-comparison]
```

只读既有产物，写出的报告：`04_render/<ID>.render.md`（SSIR 回写）、
`05_verify/<ID>.verify.json`（合规/质量报告）、
字段 `passed` / `overallStatus` / `layerStatus` / `differences` / `criticalInformationLoss`）、
`04_render/<ID>.render-comparison.json`（与源 PDF 的页数/字节/文本量对比）。

退出码：`0` 等价，`3` 不等价（关键信息丢失等），`2` 用法或引擎错误。

### 4.2b `tools/list_references.py` — 规范性引用清单（只读）

```bash
.venv/bin/python tools/list_references.py <ID|文档根|canonical.md|ssir.json> [--standard 号] [--include-informative] [--no-internal] [--json]
```

列出该标准引用了哪些文件（TDRS 六元组：被引标准号 / 版本 / 名称 / 引用类型
`dated|undated|all_parts` / 被引条款 / 出现条款 + 引用性质 `normative|informative`），
并列出**本文内部引用点**（`表N` / `图X.N` / `式(N)` / 条款号）及其目标元素 id；
每个引用点带 canonical 字符区间（`textSpan`）与 SSIR 元素 id，便于回溯到原文。
末尾给出两段「待复核」：① 清单里列出、但正文中没有引用点的条目（合规告警
`GBT-C06/reference-entry-not-cited`）；② 正文规范性引用了、但清单未列出的文件（合规告警
`GBT-C06/normative-citation-not-listed`）。两段都只给条款号、引用原文与元素 id（不给行号：
解析器行号记账在目次区段后有系统偏移，见 `docs/12` §3.97）。数据来自解析层 `SSIR.references`
（解析层一次抽取，可由 canonical 独立产出，见 `docs/12` §3.95/§3.96）。
等价的 CLI 入口：`ssir references <文件>`。

给的是**文档根或 SSIR 产物**时优先读 `03_ssir/*.ssir.json`；产物早于引用抽取（无
`references` 键）会提示改用 canonical 现场解析或重跑构建。

### 4.3 `tools/mineru_full_standard.py` — PDF 抽取

```bash
.venv/bin/python tools/mineru_full_standard.py <ID 或 PDF 路径> [选项]
```

| 参数 | 说明 |
|---|---|
| `file`（位置） | 文件名（默认在 `corpus/golden/` 下解析）或路径；**只接受 PDF**（Word 输入已暂时停用，见 §8） |
| `--stage {extract,merge,finalize,all}` | 抽取 / 合并 / 合并后 normalize+parse / 全流程（默认 `all`） |
| `--method {auto,ocr,txt}` | MinerU 抽取方法（默认 `auto`；文本层丢拉丁/数字串时用 `ocr`） |
| `--hybrid-tables` | 含表页额外跑 hybrid-engine（GEN-094）；默认关闭（VLM 通道慢） |
| `--chunk-size N` | 每个 MinerU 分片的页数（默认 18，便于断点续跑） |
| `--render` | 渲染 PDF（默认不做；快捷模式自动带 `--render`） |
| `--toc-depth N\|all` | 渲染目次最大层数 |
| `--standard-number` / `--title` / `--front-matter-json` | 同 §4.1 |

已有 `02_canonical/<ID>.canonical.md` 时自动跳过抽取与 normalize、从 canonical 续跑（不覆盖基线）。

### 4.4 其它工具

| 工具 | 用途 | 用法 |
|---|---|---|
| `tools/reprocess_canonical.py` | 半程重跑（`build_ssir.py` 的 canonical 起点已覆盖同等能力） | `reprocess_canonical.py <ID\|canonical.md\|目录>` |
| `tools/kg_tool.py` | 知识图谱 CLI：`build` / `import` / `list` / `serve` | 见 §7 |
| `tools/validate_profile_layering.py` | 渲染 profile 分层校验（需先备好其 registry 输入） | `--help` |
| `tools/prepare_serif_font.py`、`prepare_label_font.py`、`prepare_oblique_font.py` | 生成渲染用 TrueType 字体（正文宋体 / 注示例黑体粗 / 强调用机斜，均由已入库字体转换或按 15.8° 机斜） | `--help` |
| `tools/parse_standard_names.py` | 标准名称 CSV → TSV（GBK/UTF-8） | `parse_standard_names.py <csv> [-o out.tsv]` |
| `tools/verify_standard_versions.py` | 校验同一标准跨文档根的多版本管理 | `--docroot <dir> [--docroot …]` |
| `tools/replay_text_spacing.py`、`extract_schema.py` | 规则回放 / Schema 导出（维护用） | `--help` |

### 4.5 CLI `ssir`

```bash
PYTHONPATH=src .venv/bin/python -m leleby_ssir <命令>      # 或安装后的 .venv/bin/ssir
```

| 子命令 | 作用 | 主要参数 |
|---|---|---|
| `csm validate` | 校验 CSM（默认宽容模式显示可恢复问题） | `--input`、`--strict` |
| `csm normalize` | raw Markdown → canonical CSM | `--input`、`--canonical-output`、`--report`、`--strict` |
| `csm parse` | canonical CSM → SSIR JSON / TTL | `--input`、`--output`、`--format {json,ttl}`、`--report`、`--strict` |
| `csm project` | SSIR/canonical → 标准 markdown 投影（render.md） | `--input`、`--output` |
| `pdf extract` | PDF → CSM Markdown | `--input`、`--output`、`--backend {auto,mineru,pymupdf}`、`--report`、`--sidecar` |
| `pdf render` | SSIR → PDF | `--input`、`--output`、`--profile`、`--report`、`--toc-depth LEVEL\|all` |

单阶段示例：

```bash
# raw → canonical（输入必须已带 YAML front matter；裸 raw 请用 tools/build_ssir.py，
# 它会补 front matter 并做 MinerU 标记适配）
PYTHONPATH=src .venv/bin/python -m leleby_ssir csm normalize \
  --input out/mineru/<ID>/01_extract/<ID>.raw.md --canonical-output out/<ID>.canonical.md
PYTHONPATH=src .venv/bin/python -m leleby_ssir csm parse \
  --input out/<ID>.canonical.md --output out/<ID>.ssir.json --format json
PYTHONPATH=src .venv/bin/python -m leleby_ssir pdf render \
  --input out/<ID>.ssir.json --output out/<ID>.render.pdf --toc-depth all
PYTHONPATH=src .venv/bin/python -m leleby_ssir references out/<ID>.canonical.md   # 规范性引用清单
```

---

## 5. 产物、报告与目录

### 5.1 阶段产物

`out/mineru/<ID>/`（gitignore，可删除重建）：

| 目录/文件 | 说明 |
|---|---|
| `00_source/` | 源文件副本与 sha256（提供 `--source-pdf` 时） |
| `01_extract/` | `<ID>.raw.md`（归一后的抽取稿）、`.provenance.json`（输入形态、远程图下载与失败列表、图尺寸来源） |
| `02_canonical/` | `<ID>.canonical.md`（**权威基线**）、`.normalize-report.json` |
| `03_ssir/` | `<ID>.ssir.json`（渲染唯一输入）、`.parse-report.json` |
| `04_render/` | `.render.pdf`、`.render.md`、`.render-report.json`、`.render-comparison.json`（验证产出） |
| `05_verify/` | `.verify.json`（合规/质量报告；由独立验证程序写） |
| `manifest.json` | 各阶段产物索引与状态（未提供源 PDF 时 `source`/`checksum` 为 `null`） |
| `assets/images/` | 图/公式资产（渲染按 `assetsRef` 相对路径解析） |

### 5.2 报告怎么读

| 报告 | 关注点 |
|---|---|
| `.normalize-report.json` | 导入诊断与安全修复（issue 码 + 行号 + 修复动作） |
| `.parse-report.json` | parser 修复记录 + 三层合规发现；`status: partial` 表示「有记录项」，不影响渲染 |
| `.render-report.json` | 页数与 warning 列表（**页数异常先看这里**） |

CSM 的完整语法（YAML front matter、表格/图/公式/列表写法）见
[CSM 格式规范](docs/07_leleby%20Canonical%20SSIR%20Markdown%20Format%20Specification%20v0.1.md)；
可从 [CSM 模板](corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md) 或 `corpus/golden/csm/` 的样例起步。

### 5.3 仓库目录

| 路径 | 作用 |
|---|---|
| `src/leleby_ssir/` | 引擎实现（解析/规范化/SSIR 构建/合规/渲染/命名）；阶段编排见 `pipeline.py` |
| `tests/` | 单元与集成测试（容错导入、表/图/公式、脚注锚点、markdown 投影、模块完整性守护） |
| `config/` | 配置：`rendering/` 渲染 profile 与字体，`pipeline/` 审核组合 |
| `rules/` | 规则库：`base/<标准号>/`（requirements / extraction-rules / audit）与 `schemas/` |
| `corpus/golden/` | 金标准语料：`csm/*.canonical.md`（解析夹具）、`SSIR_CANONICAL_MARKDOWN_TEMPLATE.md`、`<ID>.pdf`（抽取输入） |
| `corpus/reference-standards/` | 参考标准文本（GB/T 1.1、GB/T 20001.10 等），用于设计与人工核对 |
| `rawFile/` | 云端 MinerU 产物（`<ID>.md` / `<ID>.json`）等 raw 输入 |
| `tools/` | 薄壳入口（抽取 / 构建 / 验证 / 知识图谱 / 字体与维护脚本） |
| `docs/` | 规格与实现文档；`docs/12` 是问题→规则知识库 |
| `pyproject.toml` | 依赖与 `ssir` 命令入口 |

---

## 6. 测试与回归

```bash
.venv/bin/python -m unittest discover                                          # 全量单测
.venv/bin/python tools/verify_conversion.py GB_T_39567-2020                     # 独立验证（投影 + 合规报告 + PDF 对比）
```

开发约定（改规则/改代码前必读）：[AGENTS.md](AGENTS.md) 是工作规则权威源，
[PROJECT.md](PROJECT.md) 是环境/目录/流程与陷阱，`docs/12` 记录「问题 → 根因 → 规则 → 验证」。

---

## 7. 知识图谱/本体查看器

`tools/kg_viewer/` 是 Flask 轻量查看器；**SSIR JSON 是唯一真源**，索引库与图切片都是可重建的派生产物：

```text
out/mineru/<ID>/03_ssir/<ID>.ssir.json
   ├─→ out/kg/kg.db      可重建索引：文档元数据 + 结构树 + 全文载荷
   └─→ <ID>.kg.json      图切片投影（带 schema 校验），供 vis-network / 未来 Neo4j
```

```bash
.venv/bin/python tools/kg_tool.py import GB_T_1.1-2020    # 建库/更新（--all 扫描 out/mineru/*/03_ssir/）
.venv/bin/python tools/kg_tool.py list                    # 列出库内文档
.venv/bin/python tools/kg_tool.py build GB_T_1.1-2020 -o out/gb11.kg.json
.venv/bin/python tools/kg_tool.py serve --port 8600        # 默认 127.0.0.1:8600
```

| 页面 | 地址 | 内容 |
|---|---|---|
| 文档库 | `/` | 标准号/名称/类型/ICS/CCS/代替/结构节点数；每行可进「浏览」「图谱」「详情」 |
| 内容浏览 | `/doc/<doc_id>` | 左侧结构树 + 右侧节点内容（条款/段落/列项/注/表/图/公式/术语）；支持面包屑深链、跳 canonical 原文行 |
| 本体图谱 | `/graph/<doc_id>` | vis-network：核心视图（结构/表/图/公式/术语）与全量视图，层级/力导向切换 |

「文档详情」弹窗按分层展示元数据、日期与关系、组织机构、术语、标准要素、清单核对与规模统计。
HTTP API（`/api/docs`、`/api/structure/<id>`、`/api/node/<id>/<node>`、`/api/doc/<id>/detail`、
`/api/raw/<id>/<start>/<end>`、`/api/kg/<id>?scope=core|full`、`/asset/<id>/<rel>`）便于脚本集成。

注意：`out/kg/kg.db` 是可重建索引（gitignore），删除后重新 `import` 即可；`vis-network` 为本地副本（MIT），无需外网。

---

## 8. 已知限制与常见问题

| 现象 | 说明 / 处置 |
|---|---|
| Word（`.docx`/`.doc`）输入报错、产物里没有 `render.docx` | **Word 输入与 .docx 渲染已永久放弃**（2026-09-22 裁定；导入/渲染模块与产物已删除）。抽取统一走 MinerU（只支持 PDF） |
| 封面出现 `ICS ××`、`×× 发布` 且渲染报告有 GBT-C01 warning | canonical front matter 缺 ICS/CCS/发布机构，且源 PDF 文本层也取不到（如字体编码损坏）。用 `--front-matter-json` 提供已知值，或接受占位——不猜（AGENTS.md §0.3） |
| 图比原文大很多 / 页数与预期不符 | 图源尺寸（GEN-098）优先取源 PDF 图元矩形；没有源 PDF 时取 MinerU 图块 bbox（偏差 0.2%~5%），再取不到就按默认尺寸排版。加 `--source-pdf` 可复现原始尺寸 |
| `parse-report.json` 的 `status: partial` | 正常：报告里有 parser 修复或合规记录项（含规则 ID 与行号）。只有 `parse-report.json` 里带修复记录的行才需要人工核 canonical |
| 表格/公式未按预期呈现 | 先看 raw 是否已是 CSM：云端 MinerU 的 `<table>`/`<eq>` 必须先经标记适配（`build_ssir.py` 会自动做）；再看 `render-report.json` 的 warning |
| 抽取质量差、数字/拉丁串丢失 | 换 `--method ocr`；含表页可加 `--hybrid-tables`（GEN-094，较慢） |
| `out/` 内容混乱 | `out/` 全是运行时产物（gitignore），`rm -rf out/mineru/<ID>` 后重跑即可，源码与语料不受影响 |

已知局限：扫描件与复杂表格/图像的精确识别、印刷版式验收、多标准知识图谱（引用/代替边、中文全文检索）
尚未完成；PDF 输出是传统标准草稿，不宣称通过完整印刷版式验收。

---

## 9. 文档索引

| 文档 | 内容 |
|---|---|
| [AGENTS.md](AGENTS.md) | 项目基本工作规则（缺陷处理闭环、规则落点、验证要求）——**权威源** |
| [PROJECT.md](PROJECT.md) | 环境、目录、流水线流程、模块职责与踩坑速查 |
| `docs/12_…知识库` | 问题 → 规则知识库（§2 问题映射、§3 详细记录、§5 规则 ID、§6 验证手册） |
| `docs/07_…CSM 格式规范` | CSM Markdown 语法（front matter、表格/图/公式/列表） |
| `docs/00`—`docs/11` | 数据模型、Schema、流水线架构、金标准集、API 契约等规格 |
| `docs/16_…重构实施方案` | raw 起点、源 PDF 隔离、标注方案落地与 P0 任务拆解（当前权威） |
| `naming_specification.txt` | 命名与阶段目录规范（`<STANDARD_ID>.<representation>.<ext>`） |
