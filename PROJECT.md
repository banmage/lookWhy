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
PDF ──MinerU OCR──▶ raw CSM Markdown ──normalize──▶ canonical CSM
   ──parse──▶ SSIR JSON ──render──▶ 标准风格 PDF
   ──roundtrip──▶ render.md CSM ──parse──▶ verify（验证信息等价）
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
  - `ssir`（CLI：csm validate/normalize/parse/roundtrip、pdf render 等）
  - `.venv/bin/python tools/mineru_full_standard.py`（PDF 全流程工具，见 §5）
  - `PYTHONPATH=src python3 -m leleby_ssir`（未安装时等价）

## 3. 核心概念

| 概念 | 说明 |
|---|---|
| **CSM** | Canonical SSIR Markdown：YAML front-matter + 结构化 Markdown，`<!-- ssir:... -->` 指令承载表格/图/块 |
| **Canonical** | normalize 后的权威 CSM（`<ID>.canonical.md`），roundtrip 唯一输入 |
| **SSIR** | 结构化 JSON（`ssir.schema.json` 校验，additionalProperties:false），`metadata.common/standard` + `structuralRoot` 树 + `tables/figures/formulas` 注册表 |
| **Render.md** | 从 SSIR 确定性渲染回 CSM（`<ID>.render.md`），再 parse 成 verify 对比等价性 |
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
│   ├── service.py              # 公共服务层：normalize/parse/roundtrip/validate 编排
│   ├── parser.py               # CSM → AST（Block/Directive），宽容导入、可恢复问题
│   ├── csm_normalizer.py       # AST → canonical CSM（安全纠错、权威基线）
│   ├── builder.py              # AST → SSIR JSON（章节树、注册表、ID 生成）
│   ├── csm_renderer.py         # SSIR → render.md CSM（确定性渲染）
│   ├── roundtrip.py            # SSIR/verify 四层等价比较（身份/结构/内容/语义）
│   ├── validation.py           # jsonschema + M1 语义校验（ssir.schema.json）
│   ├── exporters.py            # JSON 权威输出 + Turtle(RDF) 投影
│   ├── report.py               # 转换报告（SHA-256、issue 列表、修复动作）
│   ├── compliance.py           # 三层合规验证（GEN→GBT→P10），写 findings
│   ├── standard_name.py        # ★ 标准名称解析：类型（GBT-N01）与主对象（GBT-N02）
│   ├── pdf_extractor.py        # PDF→CSM：MinerU 首选、PyMuPDF 文本层回退
│   ├── pdf_renderer.py         # SSIR → 标准风格 PDF（reportlab，封面/目次/正文/附录）
│   └── ssir.schema.json        # SSIR JSON Schema（元数据键必须在此登记）
├── tools/
│   ├── mineru_full_standard.py # ★ PDF 全流程工具（分块抽取→合并→normalize→parse→roundtrip→render）
│   ├── parse_standard_names.py # 批量解析标准名称 CSV → 类型/主对象/场合 TSV
│   │   ├── verify_markdown_roundtrip.py  # 批量 roundtrip 回归（corpus/golden/csm）
│   │   ├── reprocess_canonical.py  # ★ canonical 半程重跑：改 canonical → parse/roundtrip/render 刷新
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
.venv/bin/python tools/verify_markdown_roundtrip.py \
  --examples-dir corpus/golden/csm --output-dir out/roundtrip  # 批量 roundtrip
# 手动单文档：
.venv/bin/ssir csm normalize --input in.md --canonical-output out/GB_T_15034-2012.canonical.md --report out/r.json
.venv/bin/ssir csm parse     --input out/GB_T_15034-2012.canonical.md --output out/GB_T_15034-2012.ssir.json --format json --report out/r2.json
.venv/bin/ssir csm roundtrip --input out/GB_T_15034-2012.canonical.md --render-md-output out/GB_T_15034-2012.render.md --verify-output out/GB_T_15034-2012.verify.json
.venv/bin/ssir pdf render    --input out/GB_T_15034-2012.ssir.json --output out/GB_T_15034-2012.render.pdf --toc-depth 2
```

### 5.2 PDF 全流程（MinerU OCR，推荐）
```bash
.venv/bin/python tools/mineru_full_standard.py \
  --input 'corpus/golden/Q_003.pdf' \
  --output-dir out/mineru/Q_003 \
  --chunk-size 18 --stage all --roundtrip --render
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
  `05_verify/<ID>.verify.json` + `.roundtrip.json`、`assets/images/`（图/公式资产）、
  `manifest.json`（文档索引）。
- 后台跑法（长文档）：`terminal(background=true)` + 日志轮询；6 页小 PDF 约 1 分钟。
- **半程重跑**（手工编辑 canonical 后刷新下游，**不重跑 normalize、不覆盖 canonical**）：
  `.venv/bin/python tools/reprocess_canonical.py GB_T_1.1-2020`——以
  `02_canonical/GB_T_1.1-2020.canonical.md` 为输入跑 parse → roundtrip → render
  （PDF+docx）→ compare → manifest；共享 mineru_full_standard 的阶段路径/版面印记/对比逻辑。
- **自动半程续跑**：`mineru_full_standard.py` 检测到 `02_canonical/<ID>.canonical.md`
  已存在时，同一快捷命令自动跳过 OCR/PDF 抽取、合并与 normalize，直接从 canonical
  续跑（与 reprocess_canonical.py 功能等同，canonical 不被覆盖）；
  显式 `--stage extract/merge/finalize` 仍按原语义执行。

### 5.3 关键阶段函数（tools/mineru_full_standard.py，约 1240 行）
| 函数 | 职责 |
|---|---|
| `standard_filename` / `standard_number_from_text` | 编号识别 + 命名规范化（**位于 src/leleby_ssir/naming.py**，Q/、SJ/T 等前缀） |
| `_convert_mineru_markup` | MinerU HTML→CSM：表格题注捕获/推断、公式绑定、表 N 裸题注 |
| `_recover_annex_headings` | 附录标题四种拆分变体合并（GEN-030） |
| `_is_cover_banner` / `_demote_cover_headings` / `_cover_title` | 封面横幅识别（含 `<机构名>企业标准`）、H1 降级、标题恢复 |
| `_cover_metadata` | 封面字段回收：日期/发布机构（含 footer+"发布"拆分合并）/英文标题/代替号 |
| `_classification_codes` | content_list 回收 ICS/CCS（MinerU 丢成页眉） |
| `merge` / `finalize` / `compare` | 合并→normalize→parse→渲染对比 |

## 6. 渲染器要点（pdf_renderer.py，1113 行）

- **封面**：`_cover_story` 按 metadata 绘制（ICS/CCS、横幅、编号、标题、英文名、
  日期、发布机构）；缺失字段以 `××` 占位并记 warning（GBT-C01）；横幅按标准号
  前缀推导（`_cover_banner_text`：GB→中华人民共和国国家标准、Q/→企业标准…）。
- **徽标**：`_cover_emblem_path` 按前缀查 profile `emblems.mapping`（最长前缀
  优先）→ `config/emblems/<file>`，缺文件回退 default，再缺不绘制；**不再使用**
  SSIR 里的 coverBadge 字段（兼容保留）。
- **正文**：documentBlock 无编号→front 样式；section 按深度→section/clause/
  subclause；`_clause_leading_number` 检测无标题条款首行编号→`body-flush` 顶格
  样式（不用 justify——reportlab justify 会撑大短行空格）。
- **表格**：`_append_table` 处理 rowspan/colspan；OCR 丢失整行注 colspan 时
  单长文本单元格跨整行（GEN-080）；题注"表 N"无题名也合法（GBT-X02）。
- **内联公式**：`_latex_to_text` 把 `$K_{...}$` 展平成可读文本，CSM/SSIR 保留
  LaTeX 源（roundtrip 安全）。
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
   roundtrip 挂 C7/C4。
6. **封面 H1 降级**：`_demote_cover_headings` 只处理 part 0 且第一个 `##` 之前；
   企业/团体标准封面横幅被 MinerU 提升为 H1 时必须降级。
7. **roundtrip 复用**：`--stage finalize` 复用缓存 parts；改 merge 逻辑后要
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
    `\x00WSP<pt>\x00`，按点数绘 1em 宽白字，故点数即宽度），docx 用制表符 +
    显式制表位（Word 同样拉伸空格）。U+2009/U+202F 等窄空格 Noto Serif CJK SC
    无字形（会成 .notdef 方框），不可用。
12. **公式编号可能藏在 LaTeX `\tag` 里**：MinerU 把整条公式行（公式 + `…………(1)`）
    识别成一个 equation 块，引导线连编号写进 `\tag{……………………(1}`（常缺右花括号），
    所以 `formulas[].number` 为空**不代表**原文没有编号——按 CSM-OCR-017 从 `\tag`
    提取（不要手改 canonical）；抽取确实没有编号的公式保持无编号（GB/T 1.1-2020
    9.9.2 只在需要引用/提示时要求编号，**不填补、不重排**）。渲染端公式行是
    `_FormulaLeaderLine`（PDF）/ 制表位实现（docx）：公式居中 + 两个汉字间隔 +
    省略号（个数按可用宽度实算）+ 编号右端对齐，公式图会先收到留得下引导线的宽度。
    「式中：」变量解释走 CSM-OCR-018 的固定形态「变量——解释；/。」，破折号两侧的
    四分之一汉字字隙由渲染层补（陷阱 11 同技术），canonical 里不写空格。
13. **表注角标 = 「行内角标标记」，只有一种形式**：canonical 写 `[:sup:a]…[:/sup]`
    （角标 + 注解区）或自闭合 `[:sup:a/]`（引用点，空注解区），下角标用 `[:sub:2]`
    （1–4 字的角标字符，如 a、1)、†）。旧写法 `[:^a]`／`[^a]…[^a/]` 由 parser 确定性
    迁移并校验配对（CSM-STRUCT-007；docs/07 §6.7），不要再按角标字符设计新标记对。
    **多条注在同一单元格里连排、不写 `<br>`**：渲染端（`inline_script_item_breaks`，
    pdf/docx 同源）自动在相邻两对标记之间换行；旧 canonical 的 `<br>` 仍被接受。
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
    同宽、docx `w:sz=4` 同值；源 PDF 实测示例框 0.33pt、表外框线 0.76pt）——框线不得
    粗于表线。线宽与表线同宽后，几何回归不再能按线宽区分框/表：框 = 页面上最外的一对
    通高竖线（tests/test_pdf_renderer.py 的 RenderPdfExampleBoxGeometryTests 用这个口径）。
15. **列项两个层次各有自己的汉字位，字隙不能按错基准算**（GB/T 1.1 10.2.2）：第一层次
    marker 空 2 汉字起排、文字（含回行）在第 5 个汉字位；第二层次 marker 空 4 汉字、
    文字在第 7 个汉字位。PDF 的字隙 = **`-firstLineIndent` − marker 宽**（marker 从
    `leftIndent + firstLineIndent` 起排）——不能拿 `leftIndent + firstLineIndent` 当
    「目标位」：那只在第一层次（4/2 汉字）凑巧相等，第二层次（6/2）会把文字推到第 8
    个汉字位，而白字占位符的**字号就是字隙宽**（26pt 的行框会把该行撑高、与相邻行框
    重叠）。docx 用 `_list_indent`（缩进随层次变，制表位 = 文字列），级别判定与 PDF
    共用 `_list_is_sub_level`。

## 9. 测试与验证惯例

- 改完代码跑 `./.venv/bin/python -m unittest discover`（全量单测，当前 286 例）。
- 全流程验证用金标准 PDF：`corpus/golden/Q_003.pdf`（企业标准 6 页，快）、
  `JB_T_14425-2023.pdf`（OCR 型 21 页）、`GB_T_25141-2022.pdf`（国标 18 页）。
- 验证清单：roundtrip passed、渲染 warnings 数量合理（企业标准 ICS/CCS 缺失
  占位是预期）、SSIR metadata 关键字段（title/issuer/dates/standardNumber）。
- git：本地身份已配置 joylix <joylix@126.com>，提交前无需再设。
