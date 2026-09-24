# lookWhy / leleby SSIR — 项目开发说明（面向 AI 与开发者）

> 本文档是 AI 接手本项目的第一手资料：功能、运行环境、目录结构、核心数据流、
> 关键约定与常见陷阱。读完本文即可安全修改代码。用户操作手册见 `README.md`。

> ⚠️ **基本工作规则（最高优先，任何改动必须遵守）**：本项目的任何优化、转换与
> 修复都**面向问题类、禁止针对个例的一次性数据手术**；每个缺陷先做根因分析并
> 落为通用规则（附回归夹具 + 跨语料验证）；抽取层真值丢失如实标注为抽取局限、
> 不人工改写掩盖。完整规则见仓库根 **`AGENTS.md`**。

---

## 1. 项目定位

lookWhy 实现 **leleby SSIR**（Structured Standard Information Representation，
结构化标准信息表示）：把中国标准文件（国家标准 GB/GB/T、行业标准 JB/QB/SJ/DL…、
地方标准 DB、团体标准 T/、企业标准 Q/）在

```
PDF ──MinerU OCR──▶ raw CSM Markdown / middle.json ──normalize──▶ canonical CSM
   ──parse──▶ SSIR JSON ──render──▶ 标准风格 PDF + 等价 markdown（render.md 投影）
   （验证独立：tools/verify_conversion.py 出合规/质量报告，回环验证已下线）
```

之间转换，并按 **规则库三层合规验证**（GEN-* → GBT-* → P10-*）审计结果。

> **命名（2026-08 重构）**：数据形态统一为 `canonical`、`ssir`、`render.md`、
> `verify`；文件名 `<STANDARD_ID>.<representation>.<ext>`，实现集中在
> `src/leleby_ssir/naming.py`，规范见 `naming_specification.txt`。

核心价值：不是普通 PDF 转换器，而是"**规则驱动**"的标准文档生产线——每条
抽取/渲染逻辑都在源码中以 `规则对应: XXX` 注释映射到 `rules/` 下的规则 ID，
规则文件自带标准原文章节号溯源（如 GBT-L03 ← 附录F 序号06、07）。

仓库：`/home/jlx/projects/lookWhy`（github.com/joylix/lookWhy），当前分支
main，Python 3.12，venv 在 `.venv/`。

## 2. 运行环境

- **Python ≥ 3.12**（实测 3.12.14）；系统无 pip 模块（PEP 668），必须用 venv：
  ```bash
  python3 -m venv .venv
  .venv/bin/pip install -e .     # 安装 leleby-ssir 包 + 全部依赖
  ```
- **依赖**（pyproject.toml）：PyYAML、jsonschema、reportlab（PDF 渲染）、
  PyMuPDF/fitz（PDF 文本层回退 + 封面图裁剪）、`mineru[core]` + torch/torchvision
  （OCR 后端）、`httpx[socks]`（系统走 SOCKS 代理时必须）。
- **系统字体**（渲染必需，profile 声明）：
  - 黑体标题：`/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`
  - 宋体正文：`/usr/share/fonts/truetype/arphic/uming.ttc`
  - reportlab 不能加载 OpenType/CFF 轮廓，只能用 TrueType 轮廓字体（wqy/arphic 满足）。
- **MinerU 后端**：首次运行会下载模型（数 GB）；通过 `mineru` CLI 或本地
  FastAPI 服务（http://127.0.0.1:54017）工作。
- **入口命令**：
  - `ssir`（CLI：csm validate/normalize/parse/project、pdf render 等）
  - `.venv/bin/python tools/mineru_full_standard.py`（PDF 全流程工具，见 §5）
  - `PYTHONPATH=src python3 -m leleby_ssir`（未安装时等价）

## 3. 核心概念

| 概念 | 说明 |
|---|---|
| **CSM** | Canonical SSIR Markdown：YAML front-matter + 结构化 Markdown，`<!-- ssir:... -->` 指令承载表格/图/块 |
| **Canonical** | normalize 后的权威 CSM（`<ID>.canonical.md`），**唯一人工可编辑的权威基线** |
| **SSIR** | 结构化 JSON（`ssir.schema.json` 校验，additionalProperties:false），`metadata.common/standard` + `structuralRoot` 树 + `tables/figures/formulas` 注册表 |
| **Render.md** | SSIR 的标准 markdown 投影（`<ID>.render.md`）：零指令、零 HTML 注释，与 PDF 内容等价；不再参与任何往返 |
| **Verify** | 从 render.md 再解析的 SSIR（`<ID>.verify.json`，原 SSIR2） |
| **规则三层** | Layer1 GEN-*（通用抽取/渲染工程规则）→ Layer2 GBT-*（GB/T 1.1-2020 要求）→ Layer3 P10-*（GB/T 20001.10-2014 产品标准专项，仅产品标准加载） |
| **documentBlock** | 无编号的块节点（封面标题、前 言、无编号小节标题等） |
| **section** | 带编号的章条节点（1、4.7.1、附录 A） |

## 4. 目录结构

```
lookWhy/
├── src/leleby_ssir/            # 核心包（pip install -e . 安装）
│   ├── naming.py               # ★ 命名单一事实源：ID 推导/文件名解析/报告路径
│   ├── cli.py                  # ssir 命令入口（argparse 子命令）
│   ├── service.py              # 公共服务层：normalize/parse/validate 编排
│   ├── parser.py               # CSM → AST（Block/Directive），宽容导入、可恢复问题
│   ├── csm_normalizer.py       # AST → canonical CSM（安全纠错、权威基线）
│   ├── builder.py              # AST → SSIR JSON（章节树、注册表、ID 生成）
│   ├── csm_renderer.py         # SSIR → render.md（标准 markdown 投影，确定性）
│   ├── validation.py           # jsonschema + M1 语义校验（ssir.schema.json）
│   ├── exporters.py            # JSON 权威输出 + Turtle(RDF) 投影
│   ├── report.py               # 转换报告（SHA-256、issue 列表、修复动作）
│   ├── compliance.py           # 三层合规验证（GEN→GBT→P10），写 findings
│   ├── standard_name.py        # ★ 标准名称解析：类型（GBT-N01）与主对象（GBT-N02）
│   ├── mineru_middle.py        # MinerU middle.json → CSM raw Markdown（raw 起点工具用）
│   ├── pipeline.py             # ★ 构建/验证阶段库：normalize→canonical→SSIR→印记→render→manifest
│   ├── pdf_compare.py          # 源 PDF 与渲染 PDF 的版面/文本量对比（验证程序用）
│   ├── pdf_extractor.py        # PDF→CSM：MinerU 首选、PyMuPDF 文本层回退
│   ├── pdf_renderer.py         # SSIR → 标准风格 PDF（reportlab，封面/目次/正文/附录）
│   └── ssir.schema.json        # SSIR JSON Schema（元数据键必须在此登记）
├── tools/
│   ├── mineru_full_standard.py # ★ PDF 抽取工具（分块抽取→合并；--stage all 时续 normalize→parse→render）
│   ├── parse_standard_names.py # 批量解析标准名称 CSV → 类型/主对象/场合 TSV
│   │   ├── reprocess_canonical.py  # canonical 半程重跑（已被 build_ssir.py 的同款入口覆盖）
│   │   ├── build_ssir.py          # ★ 构建入口：raw(json/md) 或 canonical → canonical → SSIR → render（验证独立）
│   │   ├── verify_conversion.py    # ★ 独立验证：markdown 投影 + 合规/质量报告（+ 可选 PDF 对比），只读产物
│   │   └── extract_schema.py       # schema 工具
├── config/
│   ├── rendering/GB_T_1.1-2020.yaml   # 渲染 profile：字体/字号/边距/emblems 徽标映射
│   ├── emblems/                # ★ 封面徽标固定目录（GB_logo.png/JB_logo.png/company_logo.png…）
│   └── pipeline/               # audit-profile-*.yaml（审核 profile 草稿）
├── rules/                      # ★ 规则库（系统"程序"，与 corpus/storage 分离）
│   ├── base/GB_T_1.1-2020/
│   │   ├── requirements.yaml       # GBT-* 70 条（内容/结构/排版/命名，100% 带 source 章节号）
│   │   ├── extraction-rules.yaml   # GEN-* 34 条（抽取/合成/渲染工程规则，16 条带 gbt11-ref）
│   │   ├── audit.yaml              # 通用审核准则 11 条（GEN-STRUCT/REF/PRES-*）
│   │   └── source.*                # GB/T 1.1-2020 源 CSM/SSIR/转换报告
│   ├── base/GB_T_20001.10-2014/     # 产品标准专项
│   │   ├── requirements.yaml       # P10-* 7 条（要素/撰写/排版，带 source）
│   │   ├── extraction-rules.yaml   # P10-GEN-* 7 条（产品标准抽取专项）
│   │   └── audit.yaml              # P10-AUD-* 7 条（产品标准审核）
│   ├── schemas/audit-rule-set.schema.json  # audit.yaml 的 JSON Schema
│   └── README.md                # 规则库结构说明
├── corpus/
│   ├── golden/                  # ★ 金标准语料（回归验证用 PDF + csm/ 手写 canonical CSM）
│   │   ├── GB_T_1.1-2020.pdf / GB_T_25141-2022.pdf / JB_T_14425-2023.pdf /
│   │   │   SJ_T_11859-2022.pdf / Q_001..004.pdf / DB11_T_1000.1-2020.pdf …
│   │   └── csm/                 # 企业/团体标准手写 CSM（Q_HKT_16016-2026.canonical.md 等）
│   └── reference-standards/     # 参考标准 Markdown（元模型类，未来规则来源）
├── tests/                       # unittest（44 个）
│   ├── test_csm_to_ssir.py / test_compliance.py / test_pdf_extractor.py / test_pdf_renderer.py
├── out/                         # 运行产物（gitignored；mineru/<文档>/ 单文档阶段目录，见 4.2 布局）
├── pyproject.toml               # 包定义（name=leleby-ssir，script=ssir）
├── README.md                    # 用户手册
└── temp.txt / temp2.txt         # 历史对话记录（需求来源，可忽略）
```

## 5. 主要流程（按工具走一遍）

### 5.1 单元级（无 OCR）
```bash
.venv/bin/python -m unittest discover                       # 全部测试
.venv/bin/python tools/verify_conversion.py GB_T_39567-2020        # 独立验证（投影 + 合规报告 + PDF 对比）
# 手动单文档：
.venv/bin/ssir csm normalize --input in.md --canonical-output out/GB_T_15034-2012.canonical.md --report out/r.json
.venv/bin/ssir csm parse     --input out/GB_T_15034-2012.canonical.md --output out/GB_T_15034-2012.ssir.json --format json --report out/r2.json
.venv/bin/ssir csm project   --input out/GB_T_15034-2012.canonical.md --output out/GB_T_15034-2012.render.md
.venv/bin/ssir pdf render    --input out/GB_T_15034-2012.ssir.json --output out/GB_T_15034-2012.render.pdf --toc-depth 2
```

### 5.2 PDF 全流程（MinerU OCR，推荐）
```bash
.venv/bin/python tools/mineru_full_standard.py \
  --input 'corpus/golden/Q_003.pdf' \
  --output-dir out/mineru/Q_003 \
  --chunk-size 18 --stage all --render
```
- **可恢复**：失败页块只重跑自己；`--stage {extract,merge,finalize,all}` 分段；
  状态在 `out/mineru/<std>/pipeline-state.json`。
- **命名方案**（用户确认，实现于 `src/leleby_ssir/naming.py`）：输出 stem 按标准号规范化——
  标准号斜杠一律转下划线（GB/T→`GB_T_15034-2012`、JB/T→`JB_T_14054-2021`、DB11/T→`DB11_T_1000-2020`、
  Q/→`Q_XKBZ_002-2026`、T/→`T_CAS_501-2021`）；显式 `--output-stem` 优先。
- **产物**（单文档阶段目录，见 `naming_specification.txt` §4.2）：
  `00_source/<ID>.source.pdf` + `.checksum.sha256`、`01_extract/<ID>.raw.md` +
  `.provenance.json`、`02_canonical/<ID>.canonical.md` + `.normalize-report.json`、
  `03_ssir/<ID>.ssir.json` + `.parse-report.json`、`04_render/<ID>.render.pdf` +
  `.render.md` + `.render-report.json` + `.render-comparison.json`、
  `05_verify/<ID>.verify.json`（独立验证程序写，构建流程不写）、`assets/images/`（图/公式资产）、
  `manifest.json`（文档索引）。
- 后台跑法（长文档）：`terminal(background=true)` + 日志轮询；6 页小 PDF 约 1 分钟。
- **半程重跑**（手工编辑 canonical 后刷新下游，**不重跑 normalize、不覆盖 canonical**）：
  `.venv/bin/python tools/reprocess_canonical.py GB_T_1.1-2020`——以
  `02_canonical/GB_T_1.1-2020.canonical.md` 为输入跑 parse → render
  （PDF）+ render.md 投影 → manifest；共享 src/leleby_ssir/pipeline.py 的阶段路径/版面印记逻辑。
- **自动半程续跑**：`mineru_full_standard.py` 检测到 `02_canonical/<ID>.canonical.md`
  已存在时，同一快捷命令自动跳过 OCR/PDF 抽取、合并与 normalize，直接从 canonical
  续跑（与 reprocess_canonical.py 功能等同，canonical 不被覆盖）；
  显式 `--stage extract/merge/finalize` 仍按原语义执行。
- **raw 起点（跳过抽取）**：完整步骤（含「改 canonical → 只重渲下游」的走法 B、
产物清单与验收清单）见 README §4『全流程详解：raw(JSON) → canonical →（可选人工修改）→ PDF』。
- **raw 起点（跳过抽取）**：抽取稿已存在时用
  `.venv/bin/python tools/build_ssir.py <raw.md|middle.json 或 裸ID> [--source-pdf <pdf>]`——
  从 raw 跑 normalize → canonical → SSIR → render（PDF）+ render.md 投影 → manifest，
  产物布局与全流程工具完全一致（复用同一批阶段路径/印记/尾部函数）。
  裸 raw（无 YAML front matter，如 <ID>/01_extract 之外的人工稿、云端 MinerU 结果）
  会先做 MinerU 标记适配（`convert_mineru_markup`：HTML 表格 → `ssir:table` 指令、HTML 行内公式
  `<eq>…</eq>` → `$…$`、资产
  路径与图题注归一、占位替代文本 `![image](…)` 清空、公式资产绑定——与 merge 同一套、
  幂等）、封面/横幅与附录标题归位，再从封面区恢复 front matter 字段并推导标题（取不到留空，
  不猜——AGENTS.md §0.3）；输入为 MinerU `middle.json` 时先经 `src/leleby_ssir/mineru_middle.py`
  翻成同形 raw（标题层级/段落 CJK 拼接/表格 HTML/图片与公式；首页页眉页脚的 ICS/CCS 与发布机构
  另行恢复为 front matter 字段）；raw 里的远程图片（cdn-mineru URL）下载到 `assets/images/`
  并改写为相对链接，失败保持原链接并记入 provenance 的 `imageFailures`。已存在
  `02_canonical/<ID>.canonical.md` 时默认改为从 canonical 续跑下游（不覆盖人工基线，
  AGENTS.md §2），需重建才用 `--overwrite-canonical`；`--source-pdf` 可选（缺省查
  `corpus/golden/<ID>.pdf`）：图源尺寸（GEN-098）在有源 PDF 时取源 PDF 图元矩形，源 PDF
  不在场时（如只给 `middle.json`）取 MinerU 图块 bbox（同坐标系，实测偏差 0.2%~5%）——
  因此 raw 起点不必依赖 `corpus/golden/` 的 PDF 即可还原图尺寸；仍只由源 PDF 提供的是
  条文脚注回收（CSM-OCR-014）、示例框样式（GBT-B11）与 PDF 渲染对比统计。

### 5.3 关键阶段函数（工具层薄壳 + `src/leleby_ssir/pipeline.py` 2254 行阶段库）

下游构建/验证阶段（`finalize`、`_post_parse_verify_render`、`_run_from_existing_canonical`、版面印记、
脚注/表注回收、`_stage_paths`/`_write_manifest`）自 2026-09-12 起位于 `src/leleby_ssir/pipeline.py`，
抽取工具只保留扫描/合并（`extract`/`merge`；hybrid 与 docx 导入已永久移除）并 re-export 旧名以免破坏既有 import。
表内列出的是抽取侧函数：
| 函数 | 职责 |
|---|---|
| `standard_filename` / `standard_number_from_text` | 编号识别 + 命名规范化（**位于 src/leleby_ssir/naming.py**，Q/、SJ/T 等前缀） |
| `_convert_mineru_markup` | MinerU HTML→CSM：表格题注捕获/推断、公式绑定、表 N 裸题注 |
| `_recover_annex_headings` | 附录标题四种拆分变体合并（GEN-030） |
| `_is_cover_banner` / `_demote_cover_headings` / `_cover_title` | 封面横幅识别（含 `<机构名>企业标准`）、H1 降级、标题恢复 |
| `_cover_metadata` | 封面字段回收：日期/发布机构（含 footer+"发布"拆分合并）/英文标题/代替号 |
| `_classification_codes` | content_list 回收 ICS/CCS（MinerU 丢成页眉） |
| `merge` / `finalize` / `compare` | 合并→normalize→parse→渲染对比 |

## 6. 渲染器要点（pdf_renderer.py，3377 行）

- **封面**：`_cover_story` 按 metadata 绘制（ICS/CCS、横幅、编号、标题、英文名、
  日期、发布机构）；缺失字段以 `××` 占位并记 warning（GBT-C01）；横幅按标准号
  前缀推导（`_cover_banner_text`：GB→中华人民共和国国家标准、Q/→企业标准…）。
- **徽标**：`_cover_emblem_path` 按前缀查 profile `emblems.mapping`（最长前缀
  优先）→ `config/emblems/<file>`，缺文件回退 default，再缺不绘制；**不再使用**
  SSIR 里的 coverBadge 字段（兼容保留）。
- **正文**：documentBlock 无编号→front 样式；section 按深度→section/clause/
  subclause；`_clause_leading_number(text, enclosing)` 检测无标题条款首行编号→
  `body-flush` 顶格样式（不用 justify——reportlab justify 会撑大短行空格）。
  谓词默认只认「编号后跟汉字/括号/引号」；**编号后接拉丁字母**的裸条
  （`4.2 SI 是采用如下常量的单位制：`）与「数值 + 单位」句（`3.2 kW 的电机…`）
  完全同形，因此这一类必须由**所在节点的条号**确认（`enclosing`，渲染时取
  `_heading_parts(node)[0]`）：编号是该节点的**直接子条**才顶格，否则退回正文段；
  顶格那一类的 1 汉字字隙由 `_clause_head_gap` 在调用方补写（`_markup` 的共享
  正则不含拉丁字母，见 docs/12 §3.59）。
- **表格**：`_append_table` 处理 rowspan/colspan；OCR 丢失整行注 colspan 时
  单长文本单元格跨整行（GEN-080）；题注"表 N"无题名也合法（GBT-X02）。
- **内联公式**：`_latex_to_text` 把 `$K_{...}$` 展平成可读文本，CSM/SSIR 保留
  LaTeX 源（原样保留，不展平存储）。
- **TOC**：有目次时两遍构建（preflight 记页码 → 最终）。

## 7. 规则体系（改代码前必读）

- **新增元数据键**：必须先加进 `src/leleby_ssir/ssir.schema.json` 的
  `metadata.common/standard`（additionalProperties:false），否则 normalize 失败。
- **源码注释约定**：每条处理逻辑标注 `规则对应: XXX`；新逻辑必须给规则 ID。
- **规则文件与代码同步**：在 `rules/` 加/改规则时，检查源码注释是否引用该 ID
  （`grep -rhoE "(GBT|GEN|P10)-[A-Z0-9-]+" src tools`）。
- **优先级语义**：must=应（违规 fail）、should=宜（warning）、may=可；
  非 must 的 fail 会在 verify 末尾降级为 warning。
- **产品标准判定**：`is_product_standard`（compliance.py）——document-type 为
  product-standard 或标题/节点标题命中 `产品标准|通用技术条件|技术条件|总规范|
  通用规范|specification...`，且标题不含 `试验方法|测试方法|检验方法|导则|指南`
  排除项。

## 8. 常见陷阱（踩过的坑，改代码注意）

1. **企业标准横幅**不是"中华人民共和国国家标准"，而是 `<机构名>企业标准`
   （如"晋中经纬新科机械有限公司企业标准"），必须用 `_is_cover_banner`
   （整行匹配 机构名+国家/行业/地方/团体/企业+标准）识别，否则标题误取横幅。
2. **多位数条款** `5.10`、`8.12`：编号正则必须是 `\d+(?:\.\d+)+`，`\d+(\.\d)+`
   只匹配单位数段，导致深度算 0 渲染成正文。
3. **MinerU 拆分发布机构**：`<机构>发布` 常被拆成 footer（机构名）+ page_number
   （"发 布"）两条，issuer 恢复必须先合并（`_cover_metadata` 的 prev_footer 逻辑）。
4. **OCR 型 PDF**（文本层乱码或坏 CJK 字体，如 `犐犆犛`=ICS）必须走 MinerU
   auto-OCR；`corpus/golden/` 部分 PDF 文本层乱码属正常。
5. **附录标题拆分**：MinerU 把附录头拆成 3 段（裸行/标题+裸性质行/heading），
   `_recover_annex_headings` 必须在 title 推导前合并，否则 title 误取"附录B"、
   附录编号/标题识别错位。
6. **封面 H1 降级**：`_demote_cover_headings` 只处理 part 0 且第一个 `##` 之前；
   企业/团体标准封面横幅被 MinerU 提升为 H1 时必须降级。
7. **parts 缓存复用**：`--stage finalize` 复用缓存 parts；改 merge 逻辑后要
   重跑 merge 阶段，parts 缓存不受影响。
8. **徽标/横幅分派互不影响**：每类标准独立映射条目，改一种类型不得影响其他。
9. **合并单元格表格**（GBT-X02）：MinerU HTML 的 rowspan 会被旧转换器丢弃导致行左移错位。
   `src/leleby_ssir/mineru_html.py` 统一处理（占位对齐 + `ssir:table-merge` 指令，
   row 为 0-based 表格行、row=0 即表头行，表头跨列也正确合并）；两条抽取路径共用，
   改表格逻辑只改这一处。
10. **报告断言**：对外声称的 pageCount/warnings 数量要以实际产物为准，不要凭
    印象；改渲染后重跑 `--render` 对比 `04_render/<stem>.render-comparison.json`。
11. **版式间隙不得用空格表达**：reportlab 两端对齐按 PDF 字间距（Tw）分摊余量，
    只作用于空格字节，且一行中只要有一个被它计作空格的字符（`_nbspCount` 认
    U+00A0），该行**所有空格一起变宽**（实测数值-单位间隙 0.95–1.60 个汉字宽、
    列项 marker 后 2.69→8.67pt）。GB/T 规定的是固定汉字位/四分之一汉字，一律用
    **固定字隙**：PDF 用白字哨兵（`_markup` 的 `\x00QEM\x00`、`_fixed_gap` 的
    `\x00WSP<pt>\x00`，按点数绘 1em 宽白字，故点数即宽度）。U+2009/U+202F 等窄空格 Noto Serif CJK SC
    无字形（会成 .notdef 方框），不可用。
12. **公式编号可能藏在 LaTeX `\tag` 里**：MinerU 把整条公式行（公式 + `…………(1)`）
    识别成一个 equation 块，引导线连编号写进 `\tag{……………………(1}`（常缺右花括号），
    所以 `formulas[].number` 为空**不代表**原文没有编号——按 CSM-OCR-017 从 `\tag`
    提取（不要手改 canonical）；抽取确实没有编号的公式保持无编号（GB/T 1.1-2020
    9.9.2 只在需要引用/提示时要求编号，**不填补、不重排**）。渲染端公式行是
    `_FormulaLeaderLine`：公式居中 + 两个汉字间隔 +
    省略号（个数按可用宽度实算）+ 编号右端对齐，公式图会先收到留得下引导线的宽度。
    「式中：」变量解释走 CSM-OCR-018 的固定形态「变量——解释；/。」，破折号两侧的
    四分之一汉字字隙由渲染层补（陷阱 11 同技术），canonical 里不写空格。
13. **表注角标 = 「行内角标标记」，只有一种形式**：canonical 写 `[:sup:a]…[:/sup]`
    （角标 + 注解区）或自闭合 `[:sup:a/]`（引用点，空注解区），下角标用 `[:sub:2]`
    （1–4 字的角标字符，如 a、1)、†）。旧写法 `[:^a]`／`[^a]…[^a/]` 由 parser 确定性
    迁移并校验配对（CSM-STRUCT-007；docs/07 §6.7），不要再按角标字符设计新标记对。
    **多条注在同一单元格里连排、不写 `<br>`**：渲染端（`inline_script_item_breaks`）
    自动在相邻两对标记之间换行；旧 canonical 的 `<br>` 仍被接受。
    回收端（CSM-OCR-015）有两个坑：① 视觉行聚类必须按**基线**（`_cluster_visual_lines`）
    ——同一表格行里中文字体字框顶比西文低 ≈4pt，按 bbox 顶聚类会把锚文本与紧随的
    上标拆成两行（表20 电容器端电压d、无线电干扰的测试e 就是这样漏检的）；② 连排
    注文补位要按「整格已出现的字母集 + 命中位点独占」设门槛，否则共享长前缀的注文头
    （表20 f/g 都以「只有在产品标准中规定了」起头）会把字母补到相邻注文的起点上。
14. **显式框标记是精确语法，写错就静默失效，且框线必须是细线**：canonical 的框线起止
    只能是 HTML 注释 `<!-- ssir:box -->`（可带 `style="frame|shaded"`）与
    `<!-- ssir:/box -->`——**斜杠在 `ssir:` 之后**（不是 `/ssir:box`），`<`/`>` 一个都
    不能少。形态不对的行会退化成普通段落：框直接消失，开标记笔误连 issue 都不报（只在
    关标记近似指令行时给 CSM-STRUCT-001 提示）。手工加框后确认 SSIR 里真的出现 `"box"`
    字段（`grep '"box"' <stem>.ssir.json`）或渲染图上真有框线，不要只看 canonical。
    **框线默认细实线**（GB/T 1.1 10.4.5；`_EXAMPLE_FRAME_WIDTH = 0.5pt`，与表网格线
    同宽；源 PDF 实测示例框 0.33pt、表外框线 0.76pt）——框线不得
    粗于表线。线宽与表线同宽后，几何回归不再能按线宽区分框/表：框 = 页面上最外的一对
    通高竖线（tests/test_pdf_renderer.py 的 RenderPdfExampleBoxGeometryTests 用这个口径）。
15. **列项两个层次各有自己的汉字位，字隙不能按错基准算**（GB/T 1.1 10.2.2）：第一层次
    marker 空 2 汉字起排、文字（含回行）在第 5 个汉字位；第二层次 marker 空 4 汉字、
    文字在第 7 个汉字位。PDF 的字隙 = **`-firstLineIndent` − marker 宽**（marker 从
    `leftIndent + firstLineIndent` 起排）——不能拿 `leftIndent + firstLineIndent` 当
    「目标位」：那只在第一层次（4/2 汉字）凑巧相等，第二层次（6/2）会把文字推到第 8
    个汉字位，而白字占位符的**字号就是字隙宽**（26pt 的行框会把该行撑高、与相邻行框
    重叠）。级别判定由 `_list_is_sub_level` 单一判据给出。
16. **表格列宽有下界，超宽表横排——列宽分配不能产出「容不下一个字」的列**（GEN-103）：
    `_table_column_widths` 把版心按需求比例分完，超版心时余量按数据需求摊给各列；**没有表头兜底
    的列**（表头 colspan 没盖到，如 GB/T 5171.1-2014 表9 26 列里的第 26 列）会分到 ≈0.6pt，
    而 reportlab 的单元格可用宽 = 列宽 − 左右边距(4+4) → 负值直接 `ValueError` 中止**整篇**渲染
    （`error: SSIR PDF renderer failed`、退出码 2、`04_render/` 为空），连别的页也一起没了。
    现在每列至少「2×边距 + 一个汉字宽」，不足从最宽列扣减（Σ 恒＝版心）。但**列宽修正并不能让
    超宽表排下**：26 列挤进 455pt 后每行一字折行、行高 150~200pt，跨行合并（rowspan）锁定的行组
    切分后仍高于一页 → `LayoutError`。这类表按 GEN-103 整表旋转 90°（表头落订口一侧、题注随表、
    可用宽＝版心高）：判据是「Σ列需求 > 容器宽 且 ≤ 版心高 且竖排 `split()` 后仍有片段高于一页」，
    第三条保证普通「要折行但能分页」的长表不被横排。手改列宽/字号前先看这条。
17. **「编号 + 拉丁字母」的裸条只能靠文档结构确认，不要把 `_CLAUSE_AFTER` 放宽到含拉丁字母**
    （GBT-B02；docs/12 §3.59）：`_clause_leading_number()` 原先只认「编号后跟汉字/括号/引号」的行
    → `4.2 SI 是采用如下常量的单位制：`、`8.2.5 SI词头符号…` 这类裸条被当正文段空两个汉字起排
    （实测左边界 106.37 vs 顶格 85.37），编号后的 1 汉字字隙也没补、反被 GBT-B12 的数值-单位规则
    压成 2.62pt。判据必须是**形状之外**的证据：`enclosing`（所在节点条号，`_node_clause_number(node)`）
    ——编号是它的直接子条才顶格，所以这个参数要从节点渲染路径一路传到 `_append_content`
    （正文/附录、`_append_nodes`、`ssir:box` 显式路径 `_append_marked_node`、`make_story` 题注内容
    四处，漏一处就静默退回旧行为）。**别把拉丁字母直接加进 `_CLAUSE_AFTER`**：它有负例夹具
    （`"3.2 kW 的电机应可靠工作。"` 必须判为正文段），放宽后每个「数值 + 单位」句都会顶格。字隙由
    `_clause_head_gap()` 在调用方写（`_markup()` 的共享正则**不动** → 其余文本零漂移）。验收口径：
    同一 SSIR 新旧代码 A/B 只准那 4 行左边界变化（`out/probe-3100/ab_acceptance.py`）+ 跨语料判定
    审计（2493 段中仅 4 段变化）；全量单测 **479 绿**。
18. **术语行判据只能有一份：`parser.term_entry_pair`（CSM-OCR-003/007；docs/12 §3.60）**。术语行的字符类
    曾在 parser（间隙归一 `restore_term_entry_gap`、条目形态归一 `_repair_term_entry_headings`）与
    builder（`term`/`englishTerm` 抽取）**各写一份**，宽窄不一：术语本体限 `[\u4e00-\u9fff]{1,24}`、
    英文对应词类不含逗号 → 「SI词头　SI prefix」（术语带拉丁缩写）与「国际单位制　International
    System of Units, SI」（英文含逗号）在**两种抽取形态**下都抽不出 `term`/`englishTerm`，目次标签
    （`_toc_nodes` 用 `node["term"]` 合成，2 段条目编号不走 `_term_entry_text` 的两行版式判据）只剩
    条目编号（GB_3100-2026 3.8/3.13）。新增判据是**单源**的，改字符类时三处一起变；两条守卫不能
    省：术语本体须含 **≥1 个汉字**（纯拉丁行是正文或英文标题换行，如 `structure and drafting of ISO
    and IEC documents,NEQ)`）、英文段**不得含汉字**（定义段不是术语行）。`restore_term_entry_gap` 的
    **无间隙形态**必须留在**纯汉字术语**上：放宽后的术语类含拉丁字母，空间隔会让贪婪匹配把英文词尾
    吞进术语（`标准化文件standardizing document` → 术语 `标准化文件standardizing`）。验收口径：同一
    canonical 新旧代码 A/B 只准目次那两行变化（文本行 1030/1030、页数 25/25、警告集相同）+ 跨语料
    13 份 canonical 判定审计（11 份逐字节不变）；全量单测 **487 绿**。
19. **强调标记（`**粗体**`/`*斜体*`/`***粗斜体***`）有一套自己的坑（GEN-108；docs/12 §3.61）**：
    ① **判据不能按邻接字符**。旧实现把「两侧都不是 `[A-Za-z0-9]` 的星号簇」当字面星号
    （`(?<![A-Za-z0-9])\*+(?![A-Za-z0-9])`），而**汉字不在该字符类里** → `***封面***`、`*目次*`、
    `**范围**` 这类汉字内容的强调标记**成对出现也被吞成字面星号**（拉丁内容的 `**bold**` 一直正常，
    所以这个缺口只表现为「汉字加粗/斜体无效」）。现按**定界符簇配对**判定：簇长 1/2/3 = 斜体/粗体/
    粗斜体，「可开」= 其后首个非空白字符存在且不是 `*`、「可闭」= 其前首个非空白字符存在且不是 `*`，
    同长度簇就近配对，**未配对簇一律按字面星号输出**（负例：GB/T 1.1-2020 9.12.1 的「即 * 、 ** 、 ***」、
    9.7.3/9.8.4 的「共*页」；字面星号需确定时写 `\*`）。改这套判据前先看负例夹具。
    ② **reportlab 的 `<b>`/`<i>` 只从已注册字族取成员**——字体没登记字族时两个标签被**静默忽略**
    （同陷阱族里的「cannot fake bold」）。`render_pdf` 必须 `registerFontFamily` 才能让标签生效。
    ③ **中文「斜体」是机斜，必须是真实字体资产**，且 `tools/prepare_oblique_font.py` 生成的机斜字体
    **PostScript 名必须与直立体不同**：reportlab 在 `pdfmetrics.registerFont` 里按 `face.name`
    （name 表 ID 6）去重，同名时后注册的机斜字体被**丢弃并复用直立体对象**——字形已机斜、PDF 里
    却仍是直立体字体名、`<i>` 依旧静默无效（实测踩到；改 name 表 ID 1/2/4/6/16/17 即可）。字形缺失时
    渲染报告会记 `[GEN-108] 强调斜体字形文件缺失`，看到这条告警说明 profile 的 `fonts.italic-file`
    或 `fonts.bold-italic-file` 没生成（先跑 `tools/prepare_oblique_font.py`）。
    验收口径：同一 SSIR 旧/新 A/B 只准强调行变化（20001.10 实测 23/619 行、页数 22/22、x/y 不变；
    1.1-2020 0/2677 行）；**判据级审计**用 `inspect.getsource(_markup)` 把改动在进程内退回，别用
    `git show HEAD:`——工作区常带其它会话的未提交改动，HEAD 不等于「当前树减去我的改动」。

20. **块级公式是 display math，分数别写成行内样式（GEN-109；docs/12 §3.62）**：canonical 的
    `ssir:formula`（`$$…$$`）在源文里按**显示样式**排版（分数分子分母与基准字母同大），而 MathText 的
    `$…$` 等价 LaTeX 的**行内 text style**——`\frac` 的分子分母被降成脚标号、`\sqrt{…}` 里的分数被
    压得更扁，公式因此"看起来偏小"（1.1-2020 9.9.3.1 示例1 实测分数堆高 12.9pt，源文 17.0pt）。
    MathText **不支持** `\displaystyle`，只能靠源码改写：`_formula_image` 生成图前调
    `_display_style_latex()` 把**最外层**的 `\frac` 改写为 `\dfrac`。改写规则的两条易错点：
    ① **花括号只作分组、不改变样式**（TeX），所以 `\sqrt{\frac{a}{b}}` 里的分数**必须**提升，别按
    "括号深度 0" 判断；样式降级只由**分数的参数**与**上/下标**触发；② 修的是**样式不是字号**——
    em 仍等于正文字号（GEN-105 的换算与 0.3 系数不动），长高只来自分数恢复字号；想放大字号是另一个
    话题（先看 docs/12 §3.56 的墨迹口径证据）。另有缓存坑：生成图文件名取表达式的哈希，改动必须在
    提升**之后**取哈希，否则旧的行内样式图一直命中缓存、修复对已渲染过的文档不生效。

21. **「竖排能否分页」要按 reportlab 的递归语义算，一次 `split()` 不算数（GEN-103；docs/12 §3.63）**：
    `Table.split(aW, aH)` 返回的是「本页装得下的**第一片** + **其余**」，而「其余」那一片本来就允许高于
    一页——它会在下一次 add 失败时被再切一次。`_table_exceeds_frame`（GEN-103 判据③）曾只查一级片段，
    于是任何**两页以上**的长表都被判成「竖排必然排不下」而整表旋转 90°；旋转后沿**页宽**方向的尺寸 =
    表高 + 题注高（GB/T 30819-2024 表2：624 + 14 = 638pt）远大于版心宽 441.5pt，reportlab 拿不出装得下
    的片段，直接抛 `LayoutError: Splitting error(n==2)` **中止整篇**（`04_render/` 空、退出码 2）。
    两条规矩：① 判定必须切到**不动点**（递归/栈式，仍有一片高于一页才算排不下；跨行合并锁定的行组
    即此类——GB/T 5171.1-2014 表9 一级分页后仍有 1897.5pt 片段且切不动，横排照旧）；② 旋转件
    （`_RotatedTable`）的内块可用宽**恒取** `_ROTATED_TABLE_MEASURE`，`split` 返回的片段必须**本页真能
    放下**（垂直尺寸高于本页剩余高、或切不出更小片段 → 返回空列表让 reportlab 推迟到下一页），
    否则「一张表」就会中止整篇。验收口径：源 PDF 排版方向要核对（表2/表4 源文 `dir == (1,0)` 竖排跨页、
    表头随页重复），跨语料 smoke 页数/警告集全等（表9 的旋转行数逐行相同），回归 3 例（旧码下 1 失败
    1 报错）。
22. **表格列宽按「折行代价」分配，不按「自然宽需求」（GEN-110；docs/12 §3.64）**：
    列宽是**资源**：给一列多宽，要问它「能省下多少折行」。旧口径（表头自然宽 + 12pt 与数据
    80% 分位取大，再「富余均分 / 按需求比例分」）只看「这列看起来需要多宽」，于是表头长而
    数据短的列被撑到表头自然宽却**照样折行**，而接近临界宽度的列成片折行（GB/T 30819-2024
    表4 第 4/5 列 130/94pt vs 源排版 84/69pt、数据只需 19pt；GB/T 1.1-2020 表F.1 第 4 列
    117pt vs 内容 189pt、8 处折行）。两条规矩：① 列宽的「长度单位」必须是**真实折行**——
    用渲染端同一实现（`_table_cell_flowables`）测量，绝不用字符宽估计去猜（`_TableCellMeasurer`
    的 docstring 说明了它为什么挂在 styles 上：文档级缓存，跨表复用）；② 目标有**次序**：
    整表总高 → 折行总次数 → 内容完整度 → 空白/文字平衡，前三条满足后才谈平衡，且平衡 =
    各列「空白/文字」**比值**一致（余额按列宽比例分，不是富余均分）。代价：渲染耗时 1.2—2.2×，
    别在表多的大文档上惊讶。
23. **并列组列宽按「各列内容自然宽」分配，别只量图片（GEN-111；docs/12 §3.65）**：
    并列容器（`ssir:columns`，示例框里的「正确/不正确」对照）里，**文本也是内容**：
    只把图/公式图片计入需求、给无图列 60pt 占位，就会把「含汉字公式（GEN-106 拍平成文本）」的那一栏
    挤到半宽——GB/T 1.1-2020 9.9.3.1 示例4 右栏因此 131pt（一行需 166.4pt）、公式被迫折成两行，
    左栏反而空着 100pt+。三条规矩：① 需求用**实测**自然宽（图取 `drawWidth`；段落按 reportlab
    自己解析的 `Paragraph.frags` 累加，别用字符数模型）；② 分配**先等分**再「让宽」——对照型并列的
    对称性不该被内容长短拉偏（源排版就是近等分），只有排不下的列才从有余量的列取宽；③ 显式
    `widths` 属性与公式图「只缩小不穿列」的既有契约不动。

24. **并列组（`ssir:columns`）里的图也有题注，分图题注还不带「图」字（GBT-B06 执行侧；docs/12 §3.66）**：
    `_append_side_by_side` 的 figure 分支早年只 `append(image)`，`ssir:columns` 内的图题注**整体不渲染**
    ——用户看到的「只有第 3 张图显示了图下名称」其实是 MinerU 裁剪图把题注像素一起裁走了。题注形态/样式
    只能有**一个入口**：`_figure_caption_text`（通栏「图N 题名」；分图编号 `a)`/`a）` 输出「{编号} {分图题}」，
    GB/T 1.1-2020 9.7.6 的分图不提升为独立图号）与 `_figure_caption_style`（分图用 `subcaption` 9pt 黑体，
    其余 `caption` 10.5pt）；通栏 `_append_figure` 与并列 `_append_side_by_side` 两处必须同规。
25. **分图题注的归属与像素都只能靠几何，且资产裁剪必须幂等（GEN-112/GEN-113；docs/12 §3.66）**：
    MinerU 逐行检出的 `image_caption` 块按阅读顺序贪心挂块，一行分图的题注会挂到**别的**图块上、
    整行图的「图N 题名」也会挂到某一张分图上——只取「块内第一条题注」就会把 a 图写成 c 图的名字、
    c 图没有题注、整图题注整条丢失。三条规矩：① 归属按**横向几何**重排（重叠 ≥ 题注宽一半；本图块或
    题注缺 bbox 时保持原位，不猜），「图N 题名」不落在本图块内就摘成独立题注行排在该页最后一个图块之后；
    ② 图块 bbox 越界圈进题注行（**双轴相交**、压缩量 < 图块高三成）时，题注像素不属于图——把资产裁到
    题注上边界；③ 裁剪必须**幂等**：目标像素高按几何与该资产**宽向**密度算（宽不受裁剪影响）、只裁不放，
    且 `image_source_sizes` 的高度同步扣除，否则资产裁短后图会被纵向压扁；④ `convert_mineru_markup` 的
    6 行前视题注吸附也要加护栏——题注行的图号与图片替代文本里的图号**不一致**时不吸附，否则「图3 …」
    这类整行题注会**覆盖**掉分图已有的题注（`_figure_number_token`）。

26. **表头是多行是常态，表跨页必须重复整块表头并补「（续）」与单位陈述（GEN-114/GEN-115、GBT-B13；docs/12 §3.67）**：
    GB/T 表的表头常不止一行（「尺寸代号｜规格代号」+ 各列规格号、「参数名称｜转速」+ 各转速段、「机座号｜基本尺寸及公差带」+
    D/D₁/L/L₁ + h7/H7），MinerU 的 HTML 用 `rowspan` 表达表头区跨度（实测 2~4）。三条规矩：① 表头行数 = **首行起点的最大 rowspan**
    （下限 1、上限「行数 − 1」——至少留一行数据，否则 reportlab 认为切点永远落在表头内、表永不可分页），由
    `mineru_html.html_table_to_csm` 写进 `header-rows`；② `table-merge` 的 `row` 是**绝对 0-based 行号**（row=0 即第一行，
    表头行也算在内）——旧 builder 用 `header_rows + row − 1` 的「相对数据行」口径，在 header-rows=1 时恰好重合、表头多行时整体错位；
    ③ 续表要**重复全部表头行**并补「表N 表题（续）」（「（续）」五号宋体）与「单位为××」右对齐行，且题注不得与表框拆到两页
    （`_table_caption_keep_height` + `CondPageBreak`）。既有 canonical **必须与 raw 同源回放**（`tools/replay_table_header_rows.py`）：
    raw 是 normalize 的上游，只改 canonical 的话下一次 normalize 重跑就会覆盖回去（实测被并发会话覆盖过一次）。
    **症状「续表少一行表头」先跑干跑，再怀疑代码**：`tools/replay_table_header_rows.py`（不带 `--apply`）按 canonical 自带的
    `ssir:table-merge` 指令从 `row="0"` 的最大 rowspan 推表头行数——报出 `header-rows 1 → 2` 就是 **canonical 掉了回放**
    （规则与 raw 都对：raw 由同一规则写出，当前 `normalize` 实测会把 raw 的值原样带到 canonical）；`--apply` 后重建
    （`tools/build_ssir.py <canonical>`，不改写 canonical），干跑回到 0 命中即幂等、也证明期间没人再改。表头行数只落在
    canonical 的指令行上，`parse → SSIR(isHeader)` → `render`（`repeatRows`）全链照抄该值，所以「续表少一行」在
    canonical 属性正确时不会发生（GB_T_30819-2024 表2 实测：p14 续表只重复首行、缺「润滑油润滑(O)｜润滑脂润滑(G)」行）。

27. **行内公式（`$…$`）拍平必须保住「变量斜体 + 上划线」（GEN-116；docs/12 §3.68）**：
    行内 math 只能拍平成文本，而拍平链路会丢掉两条版式约定：`\overline`/`\bar` 是「未知命令」，`_latex_expand_nested`
    先把它连命令带花括号拆掉（`\overline { { \eta } }` 形态更是拍成空串）；拍平只输出字符、没有斜体约定（源版面是
    「量符号斜体、单位与下标正体」）。三条规矩：① 上划线 → **矢量短横线**（区间哨兵 → reportlab `<u offset=… width=…>`，
    宽度 = 被覆盖 run 的推进宽、高度 = 该字符**在其实际字面**里的墨迹高度 + 0.19em）。**不要再用字体的组合上划线
    U+0304**：它属 CJK em 框（0.268em 宽、固定在 em 框顶），x 高字母悬空半字宽、cap 字母（P/T/X）整条埋进顶衬线
    （5171.1 的 X̄ 因此「看不出上划线」）；② 基字位置的拉丁/希腊字母 → 斜体哨兵（GEN-108 机斜字族），`\mathrm`/`\text` 内容、
    上/下标、数字、算子（Δ/Σ/Π/∂/Ω）与「紧跟 `^{…}` 的单字母基字」（单位幂 m²）保持正体；
    ③ 替换顺序：直立遮罩与上划线哨兵必须在 `_latex_expand_nested` **之前**，哨兵 → `<u>` 必须在 `_wrap_greek_letters`
    **之后**（否则量不到希腊字形的墨迹），斜体化在拍平当步完成（区域哨兵只包住该片段），
    否则「数值-单位固定字隙」等既有文本规则会被哨兵挡住。改 `_latex_to_text` 或 `_markup` 的拍平链路时先跑
    `tests/test_pdf_renderer.py::InlineMathVariableStyleTests` 与跨语料片段审计（8 份 canonical 538 处行内 math）。

28. **标题编号确认不依赖空格（GEN-117；docs/12 §3.70）**：canonical 里可能是编号紧贴标题文字的写法
    （`### 6.4分类、标记和编码`、`## 22电磁兼容性`），而渲染端统一写 `编号 + 空格 + 标题`。解析端的「已确认编号」
    判据若要求编号后必须是空白，缺空格的标题就不算已确认 → 其下**裸条款段**（≤40 字、无终止标点，如
    `6.4.3 产品分类的基本要求如下：`）的级联提升失效 → 同一份文件在两种写法下解析出不同条款树
    （structure + C7-clauseIdentifiers + C4-numericalValues）。判据必须与 `builder.py` 的标题拆分一致：
    编号后是空白**或**直接跟标题文字（汉字/字母/括号）。canonical 不需要改写——判据对齐后两种写法解析结果完全相同
    （9 份语料 A/B 逐节点相同，渲染产物不变）。改 `parser._bare_heading_candidates` /
    `_promoted_bare_headings` / `builder` 标题拆分时先跑 `tests/test_csm_to_ssir.py::GluedHeadingNumberTests`。

29. **脚注与表角注标记（GEN-118/119；docs/12 §3.71）**：条文脚注引用点 `[foot:N]`、定义
    `<!--ssir:foot:N-->注释文字<!--ssir:/foot-->`（开闭之间可换行；写在引用段之后，渲染仍落引用所在页页脚）；
    表内角注一律 `$^{a}$`，注文按 `a）注文` 形态。旧写法不做兼容：`[^N]`/`[^N]:` → `CSM-STRUCT-008`，
    `[:sup:…]`/`[:sub:…]`/`[:/sup]`/`[:/sub]` → `CSM-STRUCT-009`（只告警、不解析）。改 `parser._parse_body`
    的脚注分支 / `_reclassify_footnote_definitions` / `csm_renderer` 的 footnote 写回 / `pipeline` 的脚注-表注回收时，
    先跑 `tests/test_parser_title_and_phrase_repairs.py`、`tests/test_mineru_footnote_placement.py`、
    `tests/test_mineru_table_note_markers.py`。

## 9. 测试与验证惯例
30. **宽表横排判据② 是「可行性」不是软需求（GEN-120；docs/12 §3.72）**：横排可行性只看列下界
    （`列数 × (2×单元格边距 + 一个汉字宽) ≤ 横排可用宽`）；Σ列**软需求**（表头自然宽 + 12pt/列、
    数据 80% 分位 + 8pt/列）只是列宽分配的**目标**，不能当否决线——旋转后的列宽和竖排一样是
    「按可用宽分配 + 折行」得到的（源版面的横排表头本就折行排）。GEN-114 把多行表头（表头行 = 首行
    最大 rowspan）正确识别后 `header_min` 会显著变大，若判据② 仍比较软需求，宽表会被误判「旋转后
    排不下」而从横排退回竖排（GB/T 5171.1-2014 表9：Σ软需求 938.5pt > 横排可用宽 688.2pt，而列下界
    和 442pt ≤ 688.2pt → 应横排）。改 `_table_landscape_widths` 判据② 或 `_table_column_demands` 的
    表头口径时先跑 `tests/test_pdf_renderer.py::MultiRowHeaderLandscapeTests`（含 RED 前提自证）与
    跨语料横排 A/B（页数/警告/旋转页集合三项全等）。

31. **列宽起点 = 列下界与「数据需求」取大（GEN-121；docs/12 §3.73）**：折行代价买入（GEN-110）只按
    「加宽能省下多少行」分配，从列下界起步时，一个「自然需求大、但加宽省不下行数」的列（长格由 `<br>`
    固定断行的写法，如 GB/T 5171.1-2014 表18 的名称列）会被饿在下界附近而不必要折行，余量堆到别的列
    （实测 158.0/267.3pt，源版面 198.5/235.5pt）。起点取 `max(列下界, 数据需求 = 80% 分位 + 8pt)`，
    Σ起点 ≤ 版心时生效；**不要**把表头底线（自然宽 + 12pt）当起点（源版面长表头本就折行，30819 表4）。
    改 `_table_column_widths` 前先跑 `tests/test_pdf_renderer.py::ColumnWidthDataNeedFloorTests`
    （夹具 `tests/fixtures/table18_columns.canonical.md`）。

32. **希腊字母从拉丁字形族取形（GEN-122；docs/12 §3.73 第 4 条）**：Noto Serif CJK 把 U+03C6 画成
    「圆圈 + 贯穿竖线」的全高形（y∈[-215,681]/1000 em，x 高只有 516）——小写 φ 读起来像大写 Φ；
    reportlab 内置 Symbol 的 φ 也是这一形。profile 用 `fonts.greek` / `fonts.greek-italic`（+ `-file`，
    本库为 Times 度量的 Liberation Serif 正体/斜体）声明拉丁字形族，`_markup` 收尾 `_wrap_greek_letters`
    按位置换族：`<i>…</i>`（GEN-116 的变量判定）内用拉丁斜体，其余（单位 μ/Ω、算子 Δ/Σ）用正体
    （GBT-B12）。未声明该字族时不替换。`_markup` 的行为依赖渲染期写入的模块槽位 → 相关单测必须
    **显式 setUp 声明字族**，别依赖用例顺序。纯文本量符号（`cosφ`）的斜体化属语义判定，未做。


- 改完代码跑 `./.venv/bin/python -m unittest discover`（全量单测，当前 552 例）。
- 全流程验证用金标准 PDF：`corpus/golden/Q_003.pdf`（企业标准 6 页，快）、
  `JB_T_14425-2023.pdf`（OCR 型 21 页）、`GB_T_25141-2022.pdf`（国标 18 页）。
- 验证清单：render.pdf + render.md 重生成成功、渲染 warnings 数量合理（企业标准 ICS/CCS 缺失
  占位是预期）、SSIR metadata 关键字段（title/issuer/dates/standardNumber）。
- git：本地身份已配置 joylix <joylix@126.com>，提交前无需再设。
