# 重构实施方案（raw 起点 · 源 PDF 隔离 · 标注方案落地）v0.2

> 状态：待评审 | 日期：2026-09-22
> 上位裁定（用户 2026-09-22 六条答复，见 §0）：**回环验证与 docx 链路永久放弃**；
> **MinerU 之后不再读取源 PDF**；以 raw（json/md）或 canonical 为起点重建全部产物。
> 依据：`docs/14`（元素与结构清单）、`docs/15`（标注方案）、`docs/12`（问题→规则知识库）、
> `AGENTS.md` §0 四原则、`naming_specification.txt`、`标准要素完整清单.md`、`GB_T_22373-2021.json`。

---

## 0. 决策记录（2026-09-22）

| # | 用户裁定 | 本方案落地方式 |
| D1 | **源 PDF 在 MinerU 之后不允许再读取** | 抽取阶段（唯一允许读 PDF 的阶段，含内容与几何分析）产出一份**版面/结构附加信息** `01_extract/<ID>.layout.json`；normalize/parse/渲染只读 raw 与 sidecar。只记录**非模板化**信息（框线、并列、块位置、注锚点等），GB/T 1.1 统一规定的版式（页边距、字体字号、行距、缩进、列宽）**不记录**，仍由渲染 profile 决定 |
| D2 | **无 canonical 则重生成并覆盖；有 canonical 则从 canonical 续跑；程序必须支持从 rawFile（json 或 md）起步** | 三种入口都保留且互不依赖：`rawFile/<ID>.json`（MinerU middle.json）/ `rawFile/<ID>.md` / `canonical/<ID>.canonical.md`；`out/` 为纯运行时产物，可整体删除重跑 |
| D3 | **"基本纠错"边界：按已有做法执行** | normalize 只做现有 GEN 规则覆盖的安全纠错；凡需要跨块猜上下文的一律**如实标注 issue、不改字符**（AGENTS.md §0.3） |
| D4 | **`out/` 全部删除重跑；metadata.json 参照 `标准要素完整清单.md` + `GB_T_22373-2021.json`** | 重建前先做**保护性归位**（§8，已执行）；`metadata.json` 为新交付产物，字段 = GBT-M01—M14 |
| D5 | **术语条目/表格注等写法：按我的建议执行** | 见 §5 |
| D6 | **有判据者按现有判据默认处理，无判据者留待手工** | docs/15 §2.2 的新增声明指令**降级为可选**：有普适判据的（列项组、式中变量解释、术语条目、目次）解析器直接识别、canonical 零新增声明；无判据的（注归属、图脚注作用域、图中标引序号、框边界）才允许手工声明，未声明则记 issue 不猜 |

**本轮交付口径（三条）**：① 元数据（GBT-M01—M14）抽取正确；② 全部元素与结构识别并结构化进 SSIR JSON；
③ 从 JSON 正确渲染 `render.pdf`，并派生**标准 markdown** `render.md`。

---

## 1. 新数据流

```
源 PDF ──┐
rawFile/<ID>.json（MinerU middle.json）─┤
rawFile/<ID>.md（云端 MinerU / 人工整理）┴─▶ [抽取阶段：唯一可读源 PDF 的阶段]
                                             ├─ 01_extract/<ID>.raw.md        （原始 Markdown）
                                             ├─ 01_extract/<ID>.layout.json   （版面/结构附加信息，新增）
                                             └─ 01_extract/<ID>.provenance.json
                                                        │
                              normalize（安全纠错，只读 raw + layout）▼
                                    canonical/<ID>.canonical.md  ← 唯一人工可编辑基线（curated）
                                                        │
                                            parse（SSIR 构建）▼
                                    03_ssir/<ID>.ssir.json  ← 唯一真值
                                                        │
        ┌───────────────┬────────────────────┬──────────┴────────────┐
   04_render/*.pdf  04_render/*.md      metadata.json          校验报告（结构/注/引用/元数据）
   （GB/T 1.1）    （标准 markdown 投影）
```

- **回环链取消**：不存在 `render.md → parse → verify` 的任何路径，也不再有"从渲染产物回读"的程序。
- **渲染端零推断**：渲染只读 SSIR 字段；字段缺失报错（§5.3）。
- 验证职责改为：元数据校验 + 结构/归属校验 + 渲染零推断断言 + PDF 产物校验（基于 PDF 内部对象）。

---

## 2. 产物与目录契约

### 2.1 输入 home（有版本控制，可人工编辑）

| 路径 | 内容 | 说明 |
| `rawFile/<ID>.json` | MinerU `middle.json` | 原始抽取结果；**只增不改** |
| `rawFile/<ID>.md` | 云端 MinerU / 人工整理的 Markdown | 与 json 同源，任选其一为起点 |
| `canonical/<ID>.canonical.md` | **curated canonical 基线（新增目录）** | 现由 `out/*/02_canonical` 保护性归位而来（§8）；人工 curation 的唯一权威副本 |
| `corpus/golden/**` | 源 PDF 与手写夹具 | 只读夹具库，不变 |

### 2.2 运行时产物（`out/mineru/<ID>/`，gitignored，可整体删除重跑）

| 路径 | 内容 | 变更 |
| `00_source/<ID>.source.pdf` | 源 PDF 副本 | 保留（供人工核对，引擎不再读） |
| `01_extract/<ID>.raw.md` | 原始 Markdown | 保留 |
| `01_extract/<ID>.layout.json` | **版面/结构附加信息（新增）** | 见 §2.3 |
| `01_extract/<ID>.provenance.json` | 来源 sidecar（源文件/SHA-256/分块锚点） | 保留 |
| `02_canonical/<ID>.canonical.md` | canonical 工作副本（来自 `canonical/`，无则从 raw 生成） | 语义变更：**可被覆盖重建** |
| `03_ssir/<ID>.ssir.json` + parse-report | SSIR 唯一真值 | 保留 |
| `04_render/<ID>.render.pdf` | 发布 PDF | 保留 |
| `04_render/<ID>.render.md` | **标准 markdown 投影（语义变更）** | 原为"渲染回的 CSM"，现为 CommonMark+GFM 子集投影，**零 ssir 指令、零 HTML 注释**；「式中」解释组照写、资产引用按产物目录补前缀（GEN-126/127）；表脚注投影成**表末行**（GEN-131） |
| `04_render/<ID>.render.html` | **结构投影（新增）** | 同一 SSIR 的 HTML 结构投影：真实 `<table>`/CSS 承载框线、并列分栏、合并单元格等 markdown 子集表达不了的形态（GEN-130）；与 `render.md` 同源同判据、同一资产前缀，表脚注为表内 `<td class="table-note">` 通栏行（GEN-131） |
| `04_render/<ID>.render-report.json` | 渲染报告 | 保留 |
| `metadata.json`（文档根） | **元数据交付产物（新增）** | 字段 = GBT-M01—M14，见 §2.4 |
| `05_check/<ID>.check.json`（原 `05_verify`） | 结构/注/引用/元数据校验报告 | 回环报告 `roundtrip.json`、`verify.json` 随回环一并删除 |

### 2.3 `layout.json`（版面/结构附加信息）内容清单

**已实现口径（2026-09-23 落地；生产者唯一：`src/leleby_ssir/layout.py`，抽取阶段调用）**：

```
{
  "schemaVersion": "1.0",
  "source":    {"pdfSha256": "...", "pageCount": 17, "producer": "mineru+layout"},
  "cover":     {"pdfPage0Lines": ["中华人民共和国国家标准", "…"]},        // GEN-016/014：封面原始行（不做页眉页脚过滤）
  "textLines": [{"page": 3, "x0": 78.0, "y0": 457.0, "x1": 344.0, "y1": 469.0, "text": "……"}],  // GEN-092：省略号补盲的输入（过滤页眉 y0<80 与页脚纯页码）
  "ellipsisLines": [{"page": 3, "x0": 78.0, "y0": 457.0, "text": "……"}],  // 短省略号行读数
  "frames":    [{"page": 37, "bbox": [...], "style": "frame|shaded"}],     // GEN-052/CSM-STRUCT-006：大尺寸框线读数（有填充→shaded，否则描边→frame）
  "imageRects": [{"page": 5, "bbox": [...], "width": 433.7, "height": 274.9}],  // GEN-096/098：图元矩形读数（封面徽标除外）；扫描页的整页位图也在读数里——「不是内容图矩形」的判定在消费端（GEN-143）
  "columns":   [{"page": 37, "blocks": [{"type": "text|image|interline_equation", "bbox": [...],
                  "text": "…", "asset": "xxx.jpg", "latex": "…", "spans": [["文本", x0, y0, x1, y1]]}]}],  // GEN-095：并列版面几何（来自 parts/*_middle.json 与整份 middle.json）
  "pages":     [{"page": 3, "width": 595.3, "height": 841.9}],             // 页尺寸（「页底 0.68×页高」类判据需要）
  "textSpans": [{"page": 3, "bbox": [...], "origin": [x, y], "size": 10.0, "text": "…"}],  // CSM-OCR-014 / CSM-OCR-015：脚注、表角标回收的逐页 span 读数
  "unresolved": [{"channel": "textLines", "reason": "源 PDF 文本层无内容行（扫描型或 pymupdf 不可用）"}]
}
```

**与 v0.1 草案的差异（如实记录，不事后美化）**：草案里的 `cover.titleEn/issuer/ics`、`blocks`、
`figures`、`tables[].noteMarkers/noteRows`、`footnotes` 都是**已判定的结论**，判定需要 SSIR 注册表
与 md 分组（属消费端输入），抽取阶段拿不到；通道只搬**读数**——原始行、矩形、MinerU 块几何、逐页
span——判定按 §3「通道不改判据」留在 `pipeline.py`。`columns` 因此是「页 → 块几何」而非
`columnCount`（分列聚类在消费端），`ellipsisLines` 是读数（补到哪、补不补仍由 GEN-092 在消费端判）。

**体积实测**：0.8–7.5 MB（≈2× 同文档 `middle.json`；最大 GB_T_1.1-2020 72 页 / 7.5 MB），属 gitignored
运行时产物。

**不记**（由 GB/T 1.1 + 渲染 profile 决定，属模板化版式）：页边距、页眉页脚尺寸、字体字号矩阵、
行距、缩进与悬挂、列宽、线条粗细、页码位置、终结线。

**产出与消费**：
- 产出：抽取阶段（唯一可读源 PDF 的阶段），`tools/mineru_full_standard.py --stage layout`
  （可对既有文档根单独补跑，不必重抽）；
- 消费：merge 的省略号补盲/表角标回收、finalize 的封面临界字段与脚注回收、构建端（`build_ssir.py`、
  `reprocess_canonical.py`）的版面印记与并列版面；**只读通道，不读源 PDF**；通道缺失时按「无判据」
  处理 —— 记日志/unresolved、不猜、不阻断（回退到旧通道：整份 `middle.json`、分片目录里的 PDF 副本）。

### 2.4 `metadata.json` 口径

字段 = `标准要素完整清单.md` §1 的 GBT-M01—M14（定义参照 `GB_T_22373-2021.json`）：

```
{
  "GBT-M01": {"value": "GB/T 30819-2024", "status": "extracted", "source": "cover.pdf-text-layer", "rule": "GEN-012"},
  ...
  "GBT-M11": {"value": null, "status": "absent-in-source", "note": "前言未列归口单位"},
  "GBT-M13": {"value": null, "status": "manual", "note": "关键词在标准正文中不存在"}
}
```

`status ∈ {extracted, absent-in-source, extraction-loss, manual, conflict}`：
`absent-in-source` = 源文件确无（§0.3：保持空）；`extraction-loss` = 源有而抽取丢失（记 issue，不伪造）；
`conflict` = 多处出现且不一致（不自动择一）。**不允许用外部数据源补全**（D3/§0.3）。

---

## 3. 源 PDF 读取点迁移表（D1 落地；**2026-09-23 完成**，见 §14.6）

迁移后 `pipeline.py` 里**唯一**读源 PDF 的地方是 `leleby_ssir.layout` 的探针
（`text_layer_content_lines` / `pdf_page_lines` / `vector_frame_rects` / `image_rects` / `text_spans`）
与 `parse_middle_geometry`（MinerU 几何）；下游一律读 `01_extract/<ID>.layout.json`。原 11 个读取点与去向：

| 函数 | 作用 | 规则 | 迁移去向（已落地） |
| `_page_count` | 页数 | — | 抽取阶段（保留：抽取的输入判据，不进通道） |
| `_cover_metadata` | 封面字段（文本层扫描） | GEN-011~017 | `cover.pdfPage0Lines`（判定仍在消费端） |
| `_cover_english_from_pdf` | 英文译名 | GEN-016 | `cover.pdfPage0Lines` |
| `_cover_issuer_from_pdf` | 发布机构 | GEN-014 | `cover.pdfPage0Lines` |
| `_text_layer_content_lines` | 文本层行（含坐标） | — | `textLines`（单一来源在 `layout`） |
| `_restore_ellipsis_lines` | 目次/公式引导线 `……` 还原 | GEN-092 | `textLines`（＋`ellipsisLines` 读数） |
| `_stamp_example_styles` | 示例框线风格 | GEN-052/CSM-STRUCT-006 | `frames`（stroke/fill 读数，风格判定在消费端） |
| `_stamp_figure_source_sizes` | 图源尺寸 | GEN-096/098、GEN-143 | `imageRects`（尺寸匹配与密度回退在消费端；整页位图矩形剔除，页尺寸取 `pages`） |
| `_stamp_side_by_side_layout` | 并列组（**原本已用 middle.json**） | GEN-095 | `columns`（通道优先；`parts/*_middle.json` 保留为回退通道） |
| `_recover_table_note_markers` | 表角标回收 | GEN-119/CSM-OCR-015 | `textSpans` + `pages` |
| `_recover_pdf_footnotes` | 条文脚注回收 | GEN-118/CSM-OCR-014 | `textSpans` + `pages` |

迁移原则：**通道不改判据**（GEN 规则与判据保持原样），只把「读 PDF」换成「读 `layout.json`」，
并把产出时刻前移到抽取阶段。`_run_from_existing_canonical` 与 `tools/reprocess_canonical.py`
的转换路径不再打开源 PDF；`--source-pdf` 只剩两个用途：图源尺寸的 `figure_size_map` 回退
（无 layout.json 的 raw 起点）与 PDF 对比（`pdf_compare`，属验证）。

---

## 4. 删除清单（永久放弃）

| 类别 | 对象 |
| docx 链路 | `src/leleby_ssir/docx_importer.py`、`docx_renderer.py`、`tests/test_docx_renderer.py`、`naming.py` 的 `.render.docx` 与相关注释、`mineru_full_standard.py:999-1000` 的 docx 分支、`pyproject.toml` 的 `python-docx` 依赖；`pdf_renderer` 中"与 docx 侧共用"的注释改为中性表述（**判据函数不动**） |
| 回环链路 | `src/leleby_ssir/roundtrip.py`、`service.round_trip_csm`、CLI `ssir csm roundtrip`、`tools/verify_markdown_roundtrip.py`、`tools/verify_conversion.py` 的回环段、`tools/verify_standard_versions.py` 的第 5 项（Roundtrip integrity）、`tools/reprocess_canonical.py` 的 roundtrip 逻辑、`pipeline._post_parse_verify_render` 的 roundtrip 分支、`naming.py` 的 `REP_ROUNDTRIP/REP_DIFF`、`csm_renderer` 的"SSIR → CSM 写回"能力（若其仍被单测使用则降级为测试夹具或改断言 SSIR） |
| 产物 | `05_verify/*.roundtrip.json`、`05_verify/*.verify.json`、`04_render/*.render.md`（旧 CSM 形态，183 处 `ssir` 指令）、`out/` 既有全部内容（§8 归位后） |
| 文档措辞 | `docs/12 §3.47`、`AGENTS.md §2`、`PROJECT.md`、`README.md`、`naming_specification.txt` 中"暂时停用/回环验证"的表述改为"已永久移除"；`naming_specification.txt` 同步新目录与新产物 |

---

## 5. 标注方案落地要点（docs/15 收敛结论）

### 5.1 声明指令降级（D6）

| docs/15 原方案 | 落地 |
| `[foot:a]` 行内标记 | **保留启用**（与 `$^{…}$` 语义分离，正是为了消除"角注 vs 数学上标"同形歧义）；`$^{a}$` 兼容期按角注读并记 CSM-STRUCT-010 |
| `<!-- ssir:list -->` 强制括起列项组 | **降级为可选**：裸 marker 行按现有判据（引语 `：` 收尾 + marker 族 + 终止符）解析，落 `ListGroup{kind, level, introRef, terminator}`，记 CSM-STRUCT-013（提示）非错误 |
| `<!-- ssir:note kind= owner= -->` | **仅在归属不可判时要求**（跨页/被抽取打散/多候选）；可判时不写，落 `notes[].ownerRef` |
| `<!-- ssir:formula-vars -->` | **可选**：`式中：` + `变量——解释；` 由现有 `FORMULA_VAR_ITEM_RE` 判据识别（组边界按"公式后首个 `式中：` 至下一个块级结构"确定） |
| `<!-- ssir:toc -->` | **可选**：`条目……页码` 判据识别 |
| `<!-- ssir:figure-legend -->` | **必需**（无普适判据：`1——…；2——…。` 与列项同形，只能靠显式声明）；未声明则记 issue |
| 术语条目新写法（编号独占一行） | 解析器**双形态宽容**：现有"裸编号段落"与"编号在标题行"都识别；**新产物只写新形态** |

### 5.2 判据单源（P3）

- 结构判据只在 `parser.py` 实现一次，产出 `Block.kind` + `Block.data`；
- `builder.py` 只做字段搬运与注册；`pdf_renderer` 只读 SSIR 字段（例外白名单：公式/单位/字隙排版必需的行内解析）。

### 5.3 渲染端零推断（可测）

- 删除：`_is_figure_note_shape`、`_is_table_caption_shape`、`_cell_note_letters`、`_plain_note_cell_text` 的渲染侧使用；
- 新增断言：渲染输入缺 `notes[].ownerRef` / `Table.caption` / `Figure.caption` 时**报错**，不回退启发式；
- 切换方式：先补字段 → 逐份重建产物 → 再删启发式（避免 8 份语料同时渲染中断）。

---

## 6. 文档体系收敛

| 文档 | 处置 |
| `docs/15` | 升 v0.2：并入 §5 的降级结论与 `layout.json`/`metadata.json` 契约，作为标注方案唯一权威 |
| `docs/14` §5 | 与 docs/15 §7 合并成一份"render.md 标准 markdown 投影规范"（多处不一致：公式写法、列表写法、缺资产图写法、角标） |
| `docs/04`（Round-trip & Conformance Test Specification） | 标注"已废弃（回环功能永久移除）"，保留供历史查阅 |
| `docs/07`（CSM 语法 v1.1） | 升版：新增 `[foot:a]`、可选声明、删除"render.md 即渲染回的 CSM"表述 |
| `docs/01`/`docs/02` | 随 `ssir.schema.json` 增补字段同步（notes / ListGroup / TocEntry / Reference / TermSource / annexScope / 元数据新字段） |
| `AGENTS.md` §2、`PROJECT.md` §7–9、`README.md`、`naming_specification.txt` | 同步验证命令（删除回环）、目录契约（`canonical/`）、阶段名（`05_check`） |

---

## 7. 实施顺序与验收

| 阶段 | 内容 | 验收 |
| P0-0 | **保护性归位**（§8，已执行） | `canonical/` 8 份基线 + `rawFile/` 8 md / 7 json 校验通过 |
| P0-A | 命名层（§10）：`naming.py` 新增 TDRS 转义与标识函数 | `tests/test_naming_element_ids.py`（16 项）全绿 |
| P0-B | SSIR 标识切 TDRS（§10）：schema pattern + builder 分配器 + 既有产物回放 | `tests/test_tdrs_element_ids.py`（8 项）全绿；`tools/replay_element_ids.py --apply` 后二次干跑零命中、`validate_ssir` 全过；8 份产物重 parse 无回归 |
| P0-1 | schema 增补 + `metadata.json` 字段口径 | `ssir.schema.json` 校验通过；未登记键构建失败的守卫测试仍绿 |
| P0-2 | **已完成 2026-09-23（§14.6）**：抽取阶段产出 `layout.json`（§2.3），PDF 读取点按 §3 迁移 | 9 个文档根「通道 == 直读」逐字段相等；6 根四轮重建的 SSIR 逐字节 sha256、页数、文本层签名、警告数 **0 变化**；移开源 PDF 仍能构建；单测 610 全绿 |
| P0-3 | 解析器实现 `[foot:a]`、双形态术语条目、式中解释组、目次条目；判据单源整理 | 新增单测 + 5 份手写夹具重 parse 无回归；干净夹具零命中 |
| P0-4 | 渲染端读新字段、删除 4 处启发式、新增缺字段断言 | 8 份语料 `render.pdf` 全部生成；断言测试绿 |
| P0-5 | `render.md` 标准 markdown 投影（替代 `csm_renderer` 的 render.md 用途） | 硬约束：零 `ssir` 指令、零 HTML 注释、块间空行、合法 GFM marker |
| P0-6 | 回环与 docx 下线（§4） | `unittest discover` 全绿（现基线 553 项 / 37s）；CLI 无 `roundtrip` 子命令 |
| P1 | `metadata.json` 校验程序（GBT-M01—M14 对照源 PDF 文本层）、结构/注/引用校验层 | 8 份语料报告逐字段有结论 |
| P2 | 解释组/图 legend/清单/目次/引用结构化；M11—M14 规则入库 | 见 docs/14 §7 |

**全局验收（本轮"完成"的定义）**：8 份语料均可从三个入口（raw json / raw md / curated canonical）独立重跑；
parse 0 阻断错误；元数据报告逐字段有结论；`render.pdf` 与 `render.md` 全部生成且 `render.md` 零私有标记；
单测全绿；跨语料重 parse 无回归。

---

## 8. `out/` 重置程序（已执行 ①，②③ 待 P0-2 完成）

① **保护性归位（2026-09-22 已执行）**：`out/` 是 gitignored 且未跟踪，直接删除会丢失**人工 curation 的
canonical**。经逐文件对照（以其自身 `raw.md` 重新 normalize 作对照，见下表），8 份 canonical **全部带有
人工编辑**，故先归位：

| 文档 | 与「同源 raw 重跑 normalize」的差异行数 | 差异性质（抽样） |
| `GB_T_1.1-2020` | 3635 | 结构重组与手写条目 |
| `GB_T_5171.1-2014` | 1457 | 标准号拆分（`GB/T51711-2014`→`GB/T 5171.1-2014`）、`title-en`/`issuer`/`replaces`/`ics` 补写 |
| `GB_T_30819-2024` | 299 | 表/注改写 |
| `GB_T_20001.5-2017` | 128 | `——` 列项 marker、`$\leqslant$`、`ssir:box` 块、`……` 占位行 |
| `GB_T_20001.10-2014` | 113 | 同上 |
| `GB_T_10401-2023` | 113 | 同上 |
| `GB_T_20001.6-2017` | 38 | 表内强调 `***封面***`、`<br>`、`ssir:box` 块 |

归位结果：`canonical/<ID>.canonical.md`（8 份）、`rawFile/<ID>.md`（8 份）、
`rawFile/GB_T_20001.10-2014.json`（自 `out/.../parts/**/ocr/*_middle.json` 迁入）。
**仍缺 raw json：`GB_T_10401-2023`**（需从 `corpus/golden/GB_T_10401-2023_bak.pdf`，29 页，重跑 MinerU 抽取）。

② **删除 `out/`**：前置条件 P0-2（layout.json 与 PDF 读取点迁移）已于 2026-09-23 落地（§14.6），本步骤现在可执行
（何时执行由用户决定；9 个文档根当前均已产出 `layout.json`），然后按三个入口各跑一遍全量重建。

③ **重跑批次**：8 份语料 × `[layout] → normalize → canonical → parse → SSIR → render.pdf → render.md → metadata.json → 校验报告`。

---

## 9. 待确认项（少量）

1. `canonical/`、`rawFile/<ID>.md`、`01_extract/<ID>.layout.json`、`metadata.json`、`05_check` 五处命名与
   位置（`naming_specification.txt` 同步）——若你要别的名字，改动只在一处常量表。
2. `GB_T_10401-2023` 的 raw json 是否需要现在补跑 MinerU（约 29 页，CPU 抽取耗时较长）。
3. `corpus/golden/csm/` 5 份手写 canonical 的定位：建议保留为"语法夹具 + 干净夹具零命中"基线，不迁入 `canonical/`。
4. `python-docx` 依赖是否随 docx 链路一并从 `pyproject.toml` 移除（若有其它用途请指出）。

---

## 10. 元素命名（TDRS 命名规则；2026-09-22 用户裁定）

权威来源：`技术文件智能审查系统（TDRS）设计说明文档v2.0.md` 命名规则部分（§一 标准号、§二 条款号引用、
§四 附录、§五 项、§六 表图公式、§八 变量、§九 概念）。实现单一入口：`src/leleby_ssir/naming.py`；
SSIR 中的元素标识由 `builder.py` 的 `_ElementIds` / `assign_element_ids` 统一分配。

### 10.1 标识形态

| 元素 | 标识 | 例 |
| 文档（= SSIR `id`） | `<标准号转义>` | `GB_T_1.1-2020`（`GB/T 1.1—2020`） |
| 结构根 | `<标识>#Root` | `GB_T_1.1-2020#Root` |
| 章/条（含 subClause） | `<标识>#<条款号>` | `GB_T_1.1-2020#8.2.1` |
| 附录 / 附录条 | `<标识>#Annex_<字母>[.<条款号>]` | `#Annex_A`、`#Annex_A.2.1` |
| 无编号要素 | 固定英文名 | `#Cover`、`#Contents`、`#Foreword`、`#Introduction`、`#Bibliography`、`#Index` |
| 无编号且未收录的要素 | `<标识>#<nodeType>_<序号4位>` | `#documentBlock_0007` |
| 表 / 图 / 公式 | `<标识>#Table_<号>` / `#Figure_<号>` / `#Formula_<号>` | `#Table_3`；附录内 `#Table_A.1` |
| 内容元素（位置槽） | `<标识>#<条款路径>/<Kind>-<序号3位>` | `#8.2.1/Paragraph-058`、`#4.1/Block-016`（表槽）、`#Foreword/Paragraph-002` |
| 列表项 | `<标识>#<条款路径>_<marker>` | `#4.2_1`（`1）`）、`#5_a`（`a）`） |
| 列表项（无字母/数字 marker） | `<标识>#<条款路径>_Item<该条款内序号>` | `#2_Item1`（`—` 项） |
| 源定位锚点 | `<标识>#Anchor-<序号4位>` | `#Anchor-0044` |
| canonical 文本 / 处理运行 / 质量评估 | 固定段 | `#Canonical`、`#ProcessingRun_19700101-001`、`#QualityAssessment_M1` |
| 表内行/单元格 | 表内局部标识（`^[A-Za-z0-9_-]+$`，TDRS 不覆盖） | `r-0001`、`r0c0` |
| 源文件 | `<标识>#` 之外独立段（保持现状） | `src:<sha256 前16位>` |

内容元素 Kind：`Paragraph` / `List` / `Example` / `Block`（表/图/公式/原样块的位置槽）/ `Note` / `Foot` /
`Unknown`。**编号元素对象**（`#Table_3`）与其**内容位置槽**（`#4.1/Block-016`）分属两套标识，跨元素引用
（`tableRef`/`figureRef`/`formulaRef`/`unknownRef`/`footnoteAnchorRef`）指向对象标识。

### 10.2 唯一性与回退（如实报告，不静默改号）

- 重号（源文件编号重复、抽取合并）→ 确定性追加 `-2/-3`，并写入 `qualityAssessments[].comments`
  的 `Element id collisions: …`；
- 编号畸形/缺失（如 `a）` 规范化后为空）→ 回退 `#<Prefix>_Seq<序号4位>`，写入
  `Element ids fell back to sequence: …`；
- 编号规范化：去空白、去尾部括号与句点（`a）`→`a`），只保留 `[A-Za-z0-9.-]`。

### 10.3 与 TDRS 的有意偏离（均为消除真实冲突；来源：naming.py 模块头）

1. **表/图/公式保留附录字母**：TDRS 只给 `Table_1` 形态，但附录表在本项目按 `表A.1` 编号，
   压平会与正文表重号 → 记为 `Table_A.1`。
2. **无编号元素使用固定英文名 + `/<Kind>-序号`**：TDRS 未规定无编号要素/内容位置的标识
   （其示例只覆盖编号元素），故新增该形态并在 `local_element_id` 收敛。
3. **列表项无 marker 时用条款内序号**：TDRS §五 只给字母项；破折号/间隔号项的 marker 无法作后缀，
   用条款内运行序号（不丢项、不重号）。

### 10.4 回放（AGENTS.md §0.4：先规则后数据）

`tools/replay_element_ids.py [--apply] [文件…]`：对既有 SSIR 产物确定性应用同一判据，只改标识类字段
（`id`/`logicalId`/`documentId`/`runId`/`parentNodeId`/*Ref/`sourceElementRefs`/`unresolvedFigures`/
锚点 `id`），自带内容不变量（非标识字段逐值不变）、幂等（二次执行逐字节相同）与
「回放后 `validate_ssir` 必须通过」三重断言；旧产物的 `ssir:*`/`li-0001` 标识允许作为回放**输入**失败。

2026-09-22 首次执行（干跑统计）：9 个文件（`out/mineru/*/03_ssir/*.ssir.json` 8 份 +
`tests/fixtures/render_example_box.ssir.json`）共改写 15,363 个标识字段；重号登记 53 项、回退 2 项
（重号集中在源文件重复章号与重复无标记列表，均为既有抽取事实）。

---

## §11 声明型指令落地（P0-D，2026-09-22）

parser 侧单源判据（`src/leleby_ssir/parser.py`），builder 只做字段映射，不再各写一份正则：

| 指令 | 形态 | 判据 |
| --- | --- | --- |
| `ssir:figure-legend` | 声明 + 条目行 | `LEGEND_ITEM_RE`（`1——气隙；`）；归属 `figure=` 指定，缺省最近一图 |
| `ssir:figure-sub` | 声明 + 条目行 | `SUB_CAPTION_ITEM_RE`（`a）局部图`）；归属同上 |
| `ssir:formula-vars` | 声明 + 条目行 | `EXPLANATION_ITEM_RE`（符号 ≤8 字符或 `$…$` + 破折号）；归属 `formula=` 指定，缺省最近一公式 |
| `ssir:toc` … `ssir:/toc` | 括起 | `TOC_ENTRY_RE`（导引符 ≥3 点 / ≥2 其它，页码可缺）；结束指令被消费 |
| `ssir:note` | 单行声明 | 绑定**下一个**注块（`> 注：…`），未被消费即丢弃 |

约定与口径：

1. 声明体 = 连续**条目行**，允许空行分隔（对齐 docs/15 §3.8 示例），终止于首个不匹配条目判据的块；
2. 声明不落文本流 → 不产生内容元素（内容元素数不变，段落判型不受影响）；
3. 条目字段按指令的命名组落位（图例 `index/text`、分图题注 `label/text`、式中解释
   `symbol/definition[/unit][/terminator]`），不匹配判据的行整行保留在 `text` 字段；
4. 归属无法解析（目标不存在）时记 `qualityAssessments.comments` 的 `Unresolved declarations`，
   **不猜、不丢**；`ssir:note` 的 `kind` 超出 schema 枚举时回退缺省并登记；
5. 引用（`notes[].ownerRef|contentRef`、`ListGroup.introRef`）与内容元素标识同源改写，
   不落悬挂引用；内部占位（`introRefPending`）永不进入 SSIR；
6. `ListGroup`（列表组）由 parser 通用标注：引语（前一块以冒号结尾）、终结符（全项尾字符一致才采用）；
   **`level` 暂不产出**——parser 目前不跟踪列表缩进层级，如实留空而非猜测。

对既有产物的影响（须在 P0-F 重建时体现）：list 元素新增 `listGroup.kind|introRef|terminator`；
以 `out/mineru/GB_T_39567-2020` 基线为例，新增 28 个字段（10 处列表），其余结构逐字段相同。

---

## §12 P0-E 顺序裁定：渲染端消费与 canonical 改写同批落地（2026-09-22）

结论：**先渲染端消费新字段，再改写 canonical**，两者必须同一批完成，不能只改 canonical。

理由（实测证据）：8 份 curated canonical 里 `目次` 条目共 170 行（GB_T_1.1-2020 144、GB_T_20001.10-2014 26）。
一旦按新规则把它们括进 `ssir:toc`，parser 会把这些行移出文本流、改记到 `tocEntries[]`；
而当前渲染端对 `tocEntries`/`notes`/`legend`/`subCaptions`/`explanationGroup` 的消费点**为 0**
（`pdf_renderer.py` 全文件命中数 0），结果就是目次页变空、图例/分图题注/式中解释行消失——
即「标注正确、产物退化」。故改写 canonical 的前置条件是渲染端先会读这些字段。

渲染端待落地点（已定位）：

| 位置 | 现状 | P0-E 目标 |
| --- | --- | --- |
| `pdf_renderer.py:1571/1588` + 绘制点 `:2478`（主路径）、`:1683`（并列列内） | 只绘 `figure["caption"]`（`_figure_caption_text`） | ✅ 已落地：追加 `Figure.legend` / `Figure.subCaptions`（同一 KeepTogether 内，两处同源） |
| ~~`pdf_renderer.py:4711`~~ | 实为**表/图目录收集器**（`figure_rows`/`_TOC_FIGURE_CAPTION_RE`），非图注绘制点 | 勘误：不在本片范围 |
| `pdf_renderer.py:1482 _is_figure_note_shape` / `:1495 _is_table_caption_shape` | 正则判「段落以 图N/表N 开头」（调用点 `:1159/:1162/:1284/:1290`） | 删正则，改为字段判据（`figureRef`/`tableRef`/声明），缺字段即断言报错 |
| 注绘制路径 | 注文本仅作为内容元素 | 依 `notes[].ownerRef|contentRef` 归属（表下/图下/条款内），缺归属按内容元素位置兜底并记录 |
| 式中解释 | 无 | ✅ 已落地：`Formula.explanationGroup.items` 逐行绘 ``symbol——definition``（样式暂用注样式，入口 `_formula_explanation_style`） |
| 目次 | 目次行作为内容元素（整块 1 个元素） | **无需渲染端消费**：实测渲染端的目次是由结构树推导（`_toc_nodes` + 图/表行），无视节点内的原始目次行。括起后渲染逐页文本**完全一致**（见下「A/B 实测」） |
| `pipeline.py:1754/1765/2013`（`_plain_note_cell_text`/`_cell_note_letters`/表格注标重建） | 抽取阶段从**源 PDF** 推表格注标 | 归 C3：判据迁到 `layout.json`/声明，抽取后不再读源 PDF |

配套：canonical 改写仍走「规则先落地 + 工具确定性回放 + 内容不变量 + 幂等 + 命中归零」
（AGENTS.md §0.4），工具形态与 `tools/replay_element_ids.py` 一致。

### A/B 实测：目次括起 `ssir:toc` 的渲染影响（GB_T_1.1-2020）

做法：按 SSIR 源锚点取出 `目次` 节点的行区间（48..154），只把该区间括进 `<!-- ssir:toc -->`
… `<!-- ssir:/toc -->`，其余字节不动；A/B 两份 SSIR 各渲一次 PDF，逐页比对文本层。

| | 页数 | 全文文本 sha256（前16） | 逐页差异 |
| --- | --- | --- | --- |
| A 原样 | 72 | `59c663d1ac1d3b74` | — |
| B 括起 | 72 | `59c663d1ac1d3b74` | **无** |

结论：
1. **本 §12 初版「目次会变空」的判断错误**，已改正——渲染端根本不读节点内的目次行，
   它按结构树重建目次；因此 canonical 括起目次**不会**让产物退化。
2. `tocEntries` 仍有价值：它是目次的**结构化来源**（作者侧条目、源页码），供审查/索引，
   不承担渲染分页职责（分页由渲染端重算，`sourcePageLabel` 保留源页码）。
3. 实验同时暴露并修掉一处**真缺陷**：初版声明体在「首个不匹配条目判据的行」处截断，
   144 行只吃进 17 行，余下回落正文 → 目次重复渲染、文档 72 → **76** 页。修法（通用规则，
   非个例）：**有配对结束指令时以结束指令界定声明体**，体内非条目行整行保留为条目；
   无配对时才以条目判据界定。修后条目 106 = 目次区非空行数（不丢行），渲染回到 72 页、
   文本与 A 完全一致。回归夹具：`tests/test_declaration_directives.py::
   test_paired_declaration_body_is_bounded_by_the_closer`。

---

### 形状启发式的删除：先度量（2026-09-22，本轮结论：暂不删）

`_is_figure_note_shape`（`pdf_renderer.py:1482`）/ `_is_table_caption_shape`（`:1495`）各有两个分支：
**结构化分支**（`presentationType == "figure"/"table"`）与**文本猜测分支**（段落文本以 `图N`/`表N` 开头）；
调用点 `:1159/:1162/:1284/:1290` 只用于「图注后紧跟表题 → 空一行」的间距决策与 `prev_figure_note` 状态。

在 8 份 canonical 上按渲染端同一状态机度量（复刻 `prev_figure_note` 更新点）：

| 项 | 全语料合计 |
| --- | --- |
| 判为图注形状 | 47（其中**文本猜测** 3） |
| 判为表题形状 | 99（其中**文本猜测** 4） |
| 由该规则插入的空行 | **11** |

结论与处置（2026-09-22，**已删猜测分支**）：这两处不是死代码，但猜测分支可证安全删除——
只保留结构化分支（`presentationType == "figure"/"table"`），并以全语料**真渲染 A/B** 验证：
8 份 canonical 在删除前后**页数、逐页文本、以及逐词位置（几何签名）三者全部一致**。
即：在本语料上文本猜测分支对产物没有可观测影响（11 处间距都由结构化判据驱动），删除是净收益
（少一处推断来源），且零回归有逐字节证据。回归夹具 `tests/test_shape_heuristics_structural_only.py`
锁「判据不得回退到文本猜测」。度量口径：复刻状态机属近似，判定以真渲染 A/B 为准。

### 第三族的准备：表内角标 → `[foot:a]`（干跑就绪，**未写回**）

工具 `tools/replay_table_foot_markers.py`（缺省干跑、`--apply`）。判据：① 只处理表格行内的 `$^{…}$`；
② 上标内容必须是**纯角标标签序列**（单个字母/数字，或 `、`/`,`/`，` 分隔的多个，允许源空白噪声
`$^{c} $`、`$^{b、d }$`）；③ **证据门**：同文件里必须存在该标签的定义形态（`$^{a}$` 紧跟汉字），
取不到即不转换并如实列出（可能是真数学上标）。断言：内容不变量（上标/标记归一后逐字节相同 +
上标减少量与标记增加量都等于替换处数）、幂等、改写后可 parse 且 `validate_ssir` 通过。

渲染能力前置验证（本族能否按「先渲染后改数据」推进）：表内 `[foot:a]` 已渲染为 GB 标准角标形态
`径向间隙a)`（`$^{a}$` 渲染为 `径向间隙a`）→ 渲染端已会读，符合顺序要求。

干跑结果（未写回）：

| 文件 | 可转换 | 定义标签 |
| --- | --- | --- |
| GB_T_1.1-2020 | 9 | a b c（另有 `***`、`3)` 等非标签序列，不转换） |
| GB_T_10401-2023 | 16 | a b c d |
| GB_T_20001.10-2014 | 3 | a |
| GB_T_5171.1-2014 | 20 | a…h |
| 其余 4 份 | 0 | 无 |

合计 **48 处**、0 失败。**为何暂不写回**：本族的另一半是**定义侧**声明
（`<!--ssir:foot:a-->…<!--ssir:/foot:a-->`，docs/15 §2 第 73 行），目前表下定义行仍是
`$^{a}$`+汉字形态；只改引用点会留下半迁移状态，故两半同批 `--apply` 并做全语料几何级 A/B。

定义侧摆放的实测（夹具，见本轮报告）：

| 摆放 | 结果 |
| --- | --- |
| A 定义留在**表格单元内**（`<br>` 分隔，各条包指令对） | 两条脚注被识别、渲染为 `a) / b) …`；但单元内的 `<br>` **漏成字面文本**（`<br>` 出现在产物里） |
| B 定义**提取为表后独立指令对** | 干净：`a) 分装式电动机不检验。`、`b) 可用部件进行检验。` 各成一行，无 `<br>` 泄漏 |

因此定义侧应走 B（提取为表后注块）。B 需要动表格结构：10401 的定义整行是表的最后一行，
删该行会改动行号，而同表的 `<!-- ssir:table-merge … row="36"/"37" -->` 正引用这两行 → 需同步重算，
属结构性手术，须单独规则 + 回归。

另一处缺口（实测）：表内 `[foot:a]` 引用点 + 指令对定义（两种摆放）下，`notes[]` 仍为 **0 条**——
`anchorKind: tableCell` 的「引用点 → 注」登记尚未接线（docs/15 §2 要求落 `notes[]`）。

`<br>` 的定位（本轮进一步隔离）：**普通单元格的 `<br>` 正常**（`产品专用<br>技术条件规定` 渲染为两行，
无字面 `<br>`，走 `pdf_renderer.py:2615/2639` 的哨兵转换）；泄漏只出现在**含 `[foot:]` 指令对的单元格**，
即脚注单元格路径（`:2124–2131` 的 `replace("<br>", "\x00BR\x00")` + 按「注N：」边界拆分）。
故 A 形态（定义留在单元格内）的可用性取决于该路径对哨兵的处置——修好它即可**免去 B 的表格结构手术**
（10401 需重算 `table-merge` 行号）。语料侧 `<br>` 仅见于 GB_T_10401-2023（668/957/1141 等行，均为单元格内换行）。

故本族的落地顺序应为：① 脚注单元格路径的 `<br>` 处置（通用规则：换行哨兵必须还原为 `<br/>`，
不得漏成字面文本）；② `[foot:LABEL]` 表内引用点的 `notes[]` 登记（`anchorKind: tableCell`、
`ownerRef` = 表节点）；③ 再做 48 处引用点 + 定义侧（A 形态，若 ① 通过）的同批回放与几何级 A/B。

**执行进展（2026-09-22）**：

- ① `<br>` 处置**已落地**：新增判据 `_is_break_only`（只由换行标记/空白组成的片段不产生段落，
  四条单元格路径共用）；夹具实测泄漏消失；603 项单测全绿；8 份 canonical 渲染签名与改动前逐字节一致。
- 引用点族**已写回**：`tools/replay_table_foot_markers.py --apply` → 4 份文件 48 处
  （1.1=9、10401=16、20001.10=3、5171.1=20），幂等复跑 0 处。
- 定义侧的新事实：定义行是表的**最后一个数据行**且 `table-merge` 的 `row` 为**数据行 0-based 索引**
  （实测 10401：`row="36"`=注行、`row="37"`=定义行），故删定义行**不会位移其它行号**，只需删引用它的
  那一条 merge 指令——原估的「整体重算」不必要（更正）。
- 定义侧工具 `tools/replay_table_foot_definitions.py`：**已修正并写回**（19 条 / 4 份：1.1=4、10401=4、
  20001.10=1、5171.1=10；幂等复跑 0）。修正内容：① 改为单趟重建（按原行序输出、遇表块末行就地追加），
  替掉有 off-by-one 的「删完再按索引插入」；② 数据行索引不再把表头行算进去（表头/分隔行都不计），
  于是 10401 的 `row="37"` 定义行 merge 指令被正确删除（共删 2 条）。
- 渲染核查：4 份未改文件签名**逐字节不变**（零回归）；1.1 / 10401 / 20001.10 定义注文**全部在**、
  无 `<br>`/指令泄漏；**GB_T_5171.1-2014 有 1 份异常：10 条定义里 5 条不进渲染产物**。
- 该异常的定位：**SSIR 侧 10 条齐全**（`footnote` 内容元素 10 个、marker a–h 正确、文本完整），
  即损失在**渲染端**：脚注定义走 `_FootnoteAnchor`（占位 0 高，文本由**页钩子绘到本页页脚**，
  `pdf_renderer.py:2368–2370`），同页锚点较多时后半段未落到页脚。属新暴露的问题，
  与「同名标签跨表重复（两表各有 a、b）」可能相关；需单独定位后再决定是否回退该份的定义侧搬迁。

**第三族落地（2026-09-22，已完成）** —— 根因是**图表脚注被当成条文脚注**绘制：

1. **引用点扫描漏表/图**（`builder._footnote_citations`）：只扫 `textContent`，而表/图的引用点
   写在单元格/图题里 → 脚注一律挂到条款节点。改为同时扫描**元素自身的 canonical 片段**
   （判据仍是 `footnote_citations`，不按文本形状猜）。
2. **锚点归属**：表/图元素成为 `footnoteAnchorRef`；`notes[]` 为脚注登记 `type=footnote`
   + `anchorKind`（表 → `tableCell`、图 → `figurePart`、其余 → `page`，**按锚点元素种类**判定）；
   `Table.noteRefs` 延迟解析为**注的标识**（TDRS 引用），不写角标字母（标签跨表重号，
   按 `ownerRef` 配准；配不上的不写）。
3. **绘制位置**（判据单点 `registries["note"]`，`pdf_renderer.py`）：`anchorKind ∈
   {tableCell, figurePart}` → **原位**小五号左对齐排在表/图之下；`page` → 仍走页脚钩子。
   页脚带容量有限，正是 5171.1 丢 5 条定义的原因（修后 10/10）。
4. **一格多角标**：`FOOTNOTE_CITE_RE` 支持 `[foot:b、d]`（`、,，` 分隔），新增
   `split_footnote_labels` / `footnote_citations` 判据单源；渲染端展开为**并排上角标** `b)d)`
   （此前多角标引用点根本不被匹配：`径向间隙[foot:a、c]` 会字面泄漏）。
5. **文本流水线单点**：`_markup` 最前统一做脚注角标替换（图题/单元格/示例框/注全路径同规）；
   实测漏点在**图题路径**（`[foot:c]` 字面泄漏）。
6. **顺带修掉一个真缺陷**（`builder._strip_outer_brackets`）：原 `text.strip("[]")` 会吃掉
   **内层** `[foot:c]` 的右括号（图题 `[图1 电路图[foot:c]]` → `图1 电路图[foot:c`）。
   改为只去**一层配对**外括号（与括号内容无关的通用规则）。

验证（8 份 canonical，几何级）：定义注文**全在**、无 `<br>`/`ssir:`/`[foot:` 泄漏、页数
与改动前逐份相同（72/33/22/37/22/13/30/25）；`notes[]` 脚注数与 `Table.noteRefs` 逐份核对
（1.1: 4+2、10401: 4、20001.10: 1+2、5171.1: 10；其余 0）。回归夹具
`tests/test_footnote_anchor_kinds.py`（3 项：锚点类别与引用标识 / `noteRefs` 用注标识 /
渲染原位与多角标并排 + 无泄漏）；`unittest discover` **606 全绿**。

**render.md = SSIR 的标准 markdown 投影（2026-09-22，已实现）**

- `csm_renderer.render_csm(document, *, asset_base="")`：**零 `<!-- ssir:… -->` 指令、
  零 HTML 注释、无 front matter**（回环已于 2026-09-22 永久下线，`projection=` 参数随之取消）。
- 投影规则：标题层级照旧（章 `##`、附录 `附录 A（规范性）`）；表格 GFM（题注 `**表N 题名**`、
  合并指令不投影——GFM 表达不了，内容仍在单元格文本里）；图表脚注定义写 `a) 注文`
  （GB/T 1.1 9.12.2，且**先去掉抽取文本自带的标记前缀**再补，避免 `a) a) …`）；公式 `$$…$$`
  + `式(N)`；**「式中」解释组**（`Formula.explanationGroup.items`，GEN-126）：条目挂在公式上，
  投影时**粘回紧随其后的「式中：」引入行之后**（判据与解析端同源 `parser.FORMULA_VAR_INTRO_RE`；
  引入行缺失/顺序异常则就地发射，不丢内容），文本形态复用 PDF 端唯一实现
  `pdf_renderer._formula_explanation_lines`；图题 `> [图N 题名（图片占位）]`；未知内容
  ` ```text ` 围栏；引用点 `[foot:a、c]` → 并排角标 `a)c)`（与 PDF 渲染同一判据）。
- **资产引用按产物目录解析**（GEN-127）：SSIR 的 `assetRef` 相对文档根（`assets/…`），产物在
  `04_render/`，故写出时经 `csm_renderer.asset_base_for(产物路径, 文档根)` 补 `"../"` 前缀；
  两个写出点统一（`pipeline._post_parse_verify_render`、`tools/verify_conversion.py`），
  `ssir csm project` 输出路径未知时保持原值。
- 产出点从「回环子进程」改为**构建流程内直接投影**（`pipeline._post_parse_verify_render`，
  `04_render/<STEM>.render.md`）；新增独立入口 `ssir csm project --input <canonical|ssir.json>
  --output <md>`（供单独验证用）。
- 验证：9 份语料投影 **0 处** `ssir:`/HTML 注释；跨语料 **48/48 条图链接可解析**、
  **56/56 条式中条目命中**（GB_T_1.1-2020 13、GB_T_10401-2023 31、GB_T_5171.1-2014 9、
  GB_T_20001.5-2017 3）；回归夹具 `tests/test_markdown_projection.py`（8 项：无指令无注释、
  保留 GB/T 形态、确定性、式中条目粘回引入行、引入行缺失仍发射、资产前缀三态、链接可解析、
  默认前缀保持原值）；`unittest discover` **618 全绿**。

**`render.html` = 同一 SSIR 的结构投影（2026-09-23，用户裁定 C 方案，GEN-130）**

- 动机：`render.md` 必须保持 CommonMark+GFM 子集（**零 `ssir:` 指令、零 HTML 注释**），而示例框线、
  并列分栏、「只有外框线/无框线」的表格、合并单元格在 GFM 里**表达不了**（单元格只容行内内容、表格不能
  嵌套、边框由阅读器决定）；md 内联 HTML/CSS 会破坏该不变量（GitHub 还会剥掉 `style`）。
- 落地：`src/leleby_ssir/html_renderer.py`（`render_html(document, *, asset_base="")`）→
  `04_render/<ID>.render.html`；与 markdown 投影**同源同判据**：同一 SSIR `document`、同一
  `csm_renderer._project_text`（引用点 `[foot:a]` → 角标 `a)`）、同一资产前缀 `asset_base_for`；
  示例框/并列组落成真实 `<table>`/CSS，合并单元格落成 `colspan`/`rowspan`（占位空单元不张冠李戴）。
- 写出点三处一致：`pipeline._post_parse_verify_render`（阶段键 `render_html`、文档根 `metadata` 增
  `renderHtml`）、`ssir csm project`、`tools/verify_conversion.py`；命名登记见 `naming_specification.txt`。
- **控制符零残留**：行内 `$…$` 与公式本体一律经 PDF 端唯一实现 `pdf_renderer._inline_math_markup` 拍平，
  哨兵转 HTML 标签（`<i>`/`<sub>`/`<sup>`/`<span class="overline">`）；覆盖段落、注例警引、列项、脚注、
  表题与表单位行、单元格、式中解释行、公式本体（无资产时不留 LaTeX 命令）。canonical 里单个游离 `$`
  属抽取噪声，按原样字符输出（三份投影一致，不猜删）。
- 验证：`tests/test_html_projection.py`（20 项：真实表格与表头 / 合并单元 / 占位空单元 /
  图示资产 / 示例框与并列分栏 / 式中组 / 未知元素 / 与 md 的内容与顺序同源 / 行内·单元格·表题·式中行的
  数学标记与「零 `$`」断言）→ `unittest discover` 全绿；跨语料 9 份正文 `$` 仅剩 2 处游离字符、LaTeX 残留 0。






### notes[] 的渲染口径：原位绘制，不注入 label（2026-09-22 裁定）

度量（夹具 + 真渲染，见 `tests/test_note_declaration_render.py`）：`ssir:note` 声明的注，
`notes[]` 登记正确（`id/type/kind/label/scope/ownerRef/contentRef` 齐备、引用为 TDRS 标识），
注文由 `contentRef` 指向的内容元素**原位绘制**（走既有 note 样式）；`label`（`注1`/`注2`）
**不出现在产物里**。

裁定：**渲染端不消费 `notes[]` 做二次绘制**，也不据 `label` 重写引导词。理由——
把正文的「注：」改写成「注1：」是**规范化改写**（GB/T 1.1 对同要素内多个注的编号），
需专门规则 + 回归 + 跨语料验证，不属于「零推断」范围；`label` 作为结构化元数据服务于
审查/关联（TDRS 侧），而非替换抽取真值（AGENTS.md §0.3）。
回归：`tests/test_note_declaration_render.py`（注文必须出现、label 不得被注入）。

---

## §13 canonical 标记回放（第一族：目次括起，2026-09-22）

工具：`tools/replay_canonical_markup.py`（`--apply` 写回；缺省干跑）。三重断言：
① 内容不变量（除插入的两行指令外逐字节不变）；② 幂等（已含声明的文件 0 改动）；
③ 改写后可 parse 且 `validate_ssir` 通过，且 `tocEntries` 条目数 = 目次区非空行数（不丢行）。
行区间取自 SSIR 的 markdown 源锚点（不靠正则猜行号）。

已执行（`--apply`，幂等复跑 0 行）：

| 文件 | 目次行区间 | 非空行 → tocEntries |
| --- | --- | --- |
| GB_3100-2026 | 42..59 | 18 → 18 |
| GB_T_1.1-2020 | 48..153 | 106 → 106 |
| GB_T_10401-2023 | 39..80 | 39 → 39 |
| GB_T_20001.10-2014 | 36..63 | 28 → 28 |
| GB_T_20001.5-2017 | 36..53 | 18 → 18 |
| GB_T_20001.6-2017 | 36..51 | 16 → 16 |
| GB_T_30819-2024 | 41..83 | 43 → 43 |
| GB_T_5171.1-2014 | 39..71 | 33 → 33 |

合计 8 份、插入 16 行、301 行目次转为结构化条目，不丢行。渲染影响由全语料 A/B 复核
（`before` = 去掉插入行，`after` = 当前文件；逐页文本层比对）：**8 份全部一致**。

### 第二族：式中解释组（`tools/replay_formula_vars.py`）

把 `式中：` 之后的连续解释行括进 `<!-- ssir:formula-vars formula="…" -->` … `<!-- ssir:/formula-vars -->`。
条目判据复用 parser 的 `EXPLANATION_ITEM_RE`（单源）；归属取该组之前最近 `ssir:formula` 指令的 id，
取不到则不写 `formula=`（parser 缺省「最近一公式」，确定而非猜测）。断言同上三重。

已执行（`--apply`）：5 份文件、17 个组、插 **34 行**、**56 条**解释条目；幂等复跑 0 行。
GB_3100-2026 / GB_T_20001.10-2014 / GB_T_20001.6-2017 / GB_T_30819-2024 无「式中：」解释组（跳过；
其中 GB_3100-2026 的两处「式中」出现在正文句子与表格单元里，按「行首为 式中」判据正确地不识别）。

**本轮暴露并修复的判据缺陷（P0-D 遗留）**：`EXPLANATION_ITEM_RE` 早期符号位 `[^—–-]{1,8}?` 会把
`<!-- ssir:/box -->` 这类指令行判为条目（符号 `<!` + `--` + 释义），导致声明体把紧随其后的指令吞进组内
——GB_T_1.1-2020 实测「18 行括起只产出 13 条」。修法在**判据**（非调用方）：符号位限制为 `$…$` 或
**不以标记字符 `<! # | > ` [ -` 开头**的 ≤8 字符符号；同时放宽破折号容错到 `{1,3}`（`———` 三连写法）。
回归夹具：`tests/test_explanation_item_judge.py`（判据层 + 端到端「式中组遇指令行即止」）。
另一处配套修复：同一公式可有多个「式中」组，条目改**累积**（原先覆盖，会丢前一组）。

**已定位并修复的渲染缺陷（同一片）**：GB_T_1.1-2020 的 4 行式中释义不进渲染产物文本层，
**真因不是 `_markup` 的 `$` 处理**（最初怀疑如此，实测 `_markup("$ t_{i} ——系统 i 的统计量$；")`
输出正常：`<i>t</i><sub>i</sub> ——系统 <i>i</i> 的统计量；`），而是：
渲染端有**两个公式绘制分支**——主路径 `pdf_renderer.py:2425` 与并列列内路径 `:1718`；
式中解释组的绘制最初只加在主路径，**并列列内公式的 `explanationGroup` 整组不绘制**
（GB_T_1.1-2020 的式中组正落在 `<!-- ssir:columns -->` 的列内）。
修法：并列列内路径同规补绘（与图例/分图题注早前在两条路径都补的做法一致）。
判据：**每个公式绘制点都必须绘制式中解释组**。
回归夹具：`tests/test_formula_explanation_render.py::
test_explanation_group_in_side_by_side_column_reaches_text_layer`（columns 夹具 + 文本层断言）。

验证（本修复后）：GB_T_1.1-2020 13 条式中条目**全部**进文本层（修前 4 行释义只剩 1 行）；
全语料 8 份渲染复核——页数逐份与修复前一致；**4 份无式中解释组的文档文本签名与修复前逐字节一致**
（零回归）；4 份有式中组的文档 56 条释义**全部**进文本层。
`canonical/GB_T_1.1-2020.canonical.md` 1740/1742/1754/1755 行的 `$` 配对写法仍为源侧缺陷，
按用户口径由其手工处理（渲染端已能正确呈现其文字）。

---

## §14 P0-F 落地记录：docx 与回环永久下线 + 三入口重建（2026-09-22）

### 14.1 实际删除（§4 删除清单的执行结果；`grep` 复核残留为 0）

| 类别 | 已删除 | 复核方式 |
|---|---|---|
| 引擎 | `src/leleby_ssir/roundtrip.py`、`docx_importer.py`、`docx_renderer.py` | 文件不存在；`grep -rn "roundtrip\|docx_importer\|docx_renderer" src/ tools/ tests/` 仅剩「已永久放弃」说明行 |
| 服务/CLI | `service.round_trip_csm`、`service` 的 `write_csm`/`RoundTripReport`/`compare_ssir` import、CLI `csm roundtrip` 子命令与其分支 | `ssir --help` 无 `roundtrip`；`csm project` 保留 |
| 工具 | `tools/verify_markdown_roundtrip.py`；`verify_conversion.py` 回环段；`build_ssir.py`/`mineru_full_standard.py`/`reprocess_canonical.py` 的 `--roundtrip`/`--no-roundtrip` 开关与回环自检 | 三个工具 `--help` 不再含 roundtrip |
| 渲染器 | `csm_renderer` 的**非投影分支**：`projection` 参数、front matter、`<!-- ssir:… -->` 指令（box/columns/table/table-merge/figure/formula/unknown）、`_next_id` 计数、`write_csm`、`yaml` 依赖 | 模块现只导出 `render_csm(document)` / `render_markdown(document)`（投影） |
| 依赖 | `pyproject.toml` 的 `python-docx` | `grep docx pyproject.toml` = 0 |
| 产物 | `05_verify/*.roundtrip.json`（14 份）、`out/roundtrip/`（11 份） | `find out -name "*.roundtrip.json"` = 0 |
| 测试 | `tests/test_docx_renderer.py`；各测试里的回环断言（`compare_ssir`/`round_trip_csm` 调用、`render_csm` 回环形态断言、docx 渲染用例） | 586 全绿；`tests/ssir_equivalence.py` 只做**幂等性断言**（语义视图比较），不是回环引擎 |

### 14.2 口径变化

- `render.md`（`04_render/<ID>.render.md`）= **SSIR 的标准 markdown 投影**，与 PDF 内容等价：
  零 `ssir:` 指令、零 HTML 注释、无 front matter；脚注定义写 `a) 注文`、引用点转并排角标。
- 验证是**独立程序**：`tools/verify_conversion.py <ID|文档根|canonical|ssir>` → markdown 投影 +
  `05_verify/<ID>.verify.json`（parse 合规/质量报告）+ 可选 PDF 对比；构建流程默认不验证
  （`--verify` 仅按显式要求另起进程调它）。
- `05_verify/` 由验证程序独占写入，构建流程不再产出该目录。

### 14.3 三入口重建验证（2026-09-22）

| 入口 | 命令 | 结果 |
|---|---|---|
| canonical 起点 | `tools/build_ssir.py out/mineru/GB_T_39567-2020/02_canonical/GB_T_39567-2020.canonical.md` | exit 0；SSIR → render.md 投影 → render.pdf **25 页 / warning 0**；manifest 的 stages 不再含 verify/roundtrip |
| raw 起点（scratch 文档根，未触碰人工基线） | `tools/build_ssir.py rawFile/GB_T_10401-2023.md --output-dir <scratch>` | exit 0；normalize → canonical → SSIR → 投影 → render.pdf **34 页**；此前在 normalize 即中断（见 14.4） |
| 独立验证 | `tools/verify_conversion.py GB_T_39567-2020` | exit 0；投影 0 处指令、`verify.json` 已写、`render-comparison.json` 已生成 |

### 14.4 重建中发现并修复的缺陷：GEN-123

raw 起点（`rawFile/*.md` 与 MinerU `middle.json`，两者都自带 front matter）在写回
`01_extract/*.raw.md` 时丢了 `---` 围栏 → normalize 以「CSM must start with YAML front matter」拒收，
**raw 起点整条断链**（裸 raw 分支用的是自带围栏的 `_build_front_matter`，所以只在「已有 front matter
的 raw」上暴露）。根因：`_split_front_matter` 的契约是「FM 正文、不含围栏」，旧实现直接拼进文件。
修复：`build_ssir._materialize_raw()` 统一补围栏（对已带围栏输入幂等），两分支共用；回归夹具
`tests/test_build_ssir.py::RawMaterializationTests`（3 例）。规则 GEN-123（stage=build）已登记
`rules/base/GB_T_1.1-2020/extraction-rules.yaml`，详见 `docs/12` §3.76。

### 14.5 测试计数

`609 → 586`：净减 23 = 删除的回环/docx 用例（`test_docx_renderer` 等、各文件的 `*_round_trip*`
断言、`compare_ssir` 比较器用例）− 新增 3 例 GEN-123 夹具；`tests/test_markdown_projection.py`（3 例）、
`tests/test_footnote_anchor_kinds.py`（3 例）等保留。

### 14.6 P0-C 落地：`layout.json` 通道（2026-09-23 完成，原「唯一剩余大块」）

| 切片 | 内容 | 落点 |
|---|---|---|
| C1-1 | 新模块 `layout.py`（抽取阶段唯一读源 PDF 的通道）：`build_layout` / `write_layout` / `load_layout` + `source`/`textLines`/`ellipsisLines` 通道；`_stage_paths` 增 `layout`；抽取工具增独立 `--stage layout` | `src/leleby_ssir/layout.py`、`pipeline._stage_paths` / `write_stage_layout` |
| C1-2 | 省略号补盲（GEN-092）改读 `textLines`；判据函数与常量（`is_short_ellipsis` / `clause_skeleton` / `raw_line_starts_with_number` / `_ELLIPSIS_CHARS` / `_FULLWIDTH_DIGITS`）移到 `layout` 作**单一来源**，消费端保留原名 | `pipeline._restore_ellipsis_lines(body, layout)` |
| C1-3 | 示例框风格（GEN-052/CSM-STRUCT-006）、图源尺寸（GEN-096/098）改读 `frames` / `imageRects`；两个 stamp 签名由 `(ssir, source_pdf)` 变为 `(ssir, layout)` | `pipeline._stamp_example_styles` / `_stamp_figure_source_sizes` |
| C1-4 | 并列版面（GEN-095）几何进 `columns`；消费端**通道优先**，`parts/*_middle.json` 按 §3 保留为回退通道 | `layout.parse_middle_geometry` / `pipeline._geometry_pages_from_layout` |
| C1-5 | 封面兜底（GEN-016 英文标题 / GEN-014 机构）改读 `cover.pdfPage0Lines` | `pipeline._cover_page0_lines` / `_cover_english_from_pdf` / `_cover_issuer_from_pdf` |
| C1-6 | 脚注回收（CSM-OCR-014）与表角标回收（CSM-OCR-015）改读 `textSpans` + `pages` | `pipeline._pdf_page_spans` / `_recover_pdf_footnotes` / `_recover_table_note_markers` |
| C2 | 构建端（`_run_from_existing_canonical`、`tools/reprocess_canonical.py`）不再打开源 PDF；显式记录「无 layout.json → 记日志、跳过印记、不阻断」 | 同上 |
| C1-7 | 9 个文档根产出 `01_extract/<ID>.layout.json`（孪生 stem 用 `resolve_stage_layout_path` 兜底并记日志） | `out/mineru/*/01_extract/` |

**验证**（AGENTS.md §0.2：单测 + 跨语料 + 记账）：
- 单测 **589 → 610 全绿**：`tests/test_layout_probe.py`（15 例）、`tests/test_layout_channel_consumers.py`（4 例，
  通道 vs 直读 + 无源 PDF）、`tests/test_ssir_columns.py` 通道优先 2 例、`test_pdf_extractor.py` 与
  `test_mineru_table_note_markers.py` 既有夹具走回退路径不回归；
- **通道 == 直读**（9 个文档根逐字段）：`textLines`、`frames`、`imageRects`、`cover.pdfPage0Lines`、
  `textSpans`+`pages`、`columns` 全部与迁移前的直接读数逐字段相等；
- **产物零变化 A/B**：6 个文档根按 canonical 起点重建（含 2 个带 `parts/` 的），9 个文档根的
  SSIR 逐字节 sha256、`render.pdf` 页数与文本层签名、render-report 警告数**全部不变**（四轮重建累计 0 变化）；
- **「拿掉源 PDF 仍能构建」**：同时移开 `corpus/golden/GB_T_30819-2024.pdf` 与文档根
  `00_source/GB_T_30819-2024.source.pdf` 后按 canonical 起点重建 → SSIR sha256 `1e97624a08383808` 与
  render 文本层签名逐字节不变（图源尺寸 14/14 仍从通道命中）；
- **可判别单测**：通道与 `parts/` 同时在场时以通道为准（parts 放单列几何、通道放两列 → 仍成组，若偷偷
  回退即失败）；`pdf=None` 只给通道时脚注/表角标回收结果与走 PDF 时逐字节相同。

**如实记录的边界（不做个例手术）**：
- `_page_count` 与文本层损坏预检（GEN-092 的输入侧）**留在抽取阶段**——它们是抽取的输入判据，不是下游读数；
- raw 起点（无源 PDF）不产出 `layout.json`：消费端回退旧通道（整份 `middle.json`、分片目录里的 PDF 副本），
  行为与迁移前一致；
- 孪生 stem（`GB_T_51711-2014` / `GB_T_5171.1-2014` 型）下 `layout.json` 可能与当前 stem 不同名：
  同名缺失且文档根下恰有一份时取它并**记日志**（静默换源被显式禁止）；零份或多份 → 按无判据处理；
- `layout.json` 体积升到 ≈2× `middle.json`（最大 7.5 MB / 72 页）——`textSpans` 是脚注/表角标回收的必需读数，
  属 gitignored 运行时产物；
- `metadata.json`（§2.4）与 `05_verify → 05_check` 改名仍待做（§7/§9），不在本轮。

---

## §15 第三族尾巴收口：图下脚注定义回放 + 锚点归属 + 框内脚注（2026-09-23）

第三族（图表脚注）在 P0-E 阶段只回放了**引用点**与**表内定义**；1.1-2020 还留下 6 处图/附录下脚注**定义**未按
GEN-118 写成指令对（`$^{b}$ 钉芯头的形状和尺寸由制造者确定。` 等），`notes[]` 未登记、渲染成正文段落。本次一并收口：

| 项 | 处置 | 落点 |
|---|---|---|
| 6 处旧形态定义 | 规则实例回放（确定性、幂等、三重断言） | `tools/replay_figure_foot_definitions.py --apply`（缺省干跑）；判据通用：`$^{L}$ 注文` + 空行分隔块的**末尾连续**定义行 + 块内/相邻有图资产、图题注或 `单位为…` 作归属证据 |
| 锚点跨节点误配 | **GEN-124（parse）**：`node_markers` 按节点分层，引用点只在自身节点及祖先内查；无引用点 → 结构上紧贴的图元素（前邻优先、回跳连续的脚注兄弟，否则最近后邻）→ `anchorKind=figurePart` | `builder.SSIRBuilder._footnote_anchor` / `_adjacent_figure_anchor` |
| 框内脚注丢内容 | **GEN-125（render）**：框内且非 `tableCell/figurePart` 的脚注定义就地绘制（页脚钩子在框表内不触发），SSIR 的 `notes[]` 不改 | `pdf_renderer._append_marked_content` |

**验证（GB_T_1.1-2020）**：`notes[]` 6 → 12（附录 E 5 条锚到图 `Block-650/652/656`，图 × 的 `b` 定义框内就地绘制）；
PDF 文本层 6/6 定义齐全（页 42、69、70、71），`render.md` 投影 0 指令 0 注释、定义呈 `a) …`／`b) …`；
跨语料 A/B：9 个文档根重跑页数 25/85/38/22/22/14/33/25/37 **逐项不变**，1.1 警告 8 条（含 GEN-125 那条），其余 8 份 0/3 条不变；
全量单测 586 → **589 全绿**（`tests/test_footnote_anchor_kinds.py` 新增 3 例）。

**如实记录的受限边界**：同一图块里 `a断裂槽应滚压成型。` 的标号 `a` 被抽取丢失（行首裸字母、无上标标记），
在不臆造标号的前提下不能判定为定义行 → **保持原样**；`canonical/GB_T_10401-2023.canonical.md:953` 的 `$^{c} $`
是内联引用点（非定义行），不动。

## 附：变更记录

- v0.2.1（2026-09-23）：**P0-C 落地**——§2.3 换为已实现通道清单（含与 v0.1 草案的差异说明与体积实测）、§3 迁移表
  标完成并换用落地后的通道名、§7 P0-2 行标记完成、§14.6 由「仍未做」改写为落地记录（切片表 + 验证 + 边界）、
  §8 ② 前置条件解除。改动全部未提交（由用户决定提交时机）。
- v0.2（2026-09-22）：并入 §10 元素命名（TDRS）——标识形态表、唯一性/回退口径、三处有意偏离、回放工具与
  首次执行统计；`§7` 增补 P0-A/P0-B 命名阶段行；新增 §11 声明型指令落地（P0-D）、§12 渲染端消费与
  canonical 改写的顺序裁定（P0-E，含目次 A/B 实测）、§13 canonical 标记回放（目次括起）、
  §14 P0-F 落地记录（docx/回环下线、三入口重建、GEN-123）。
- v0.1（2026-09-22）：首版。记录用户六条裁定，给出新数据流、产物契约（含 `layout.json`、`metadata.json`）、
  源 PDF 读取点迁移表、删除清单、标注方案降级结论、实施顺序与 `out/` 重置程序。
