# AGENTS.md — lookWhy 项目基本工作规则

> 本文件对在此仓库工作的**任何 AI 代理、协作者与开发者同等生效**（Hermes、
> Claude Code、Codex、OpenCode、纯手工开发…）。规则优先于个人习惯。
> 详细环境 / 目录 / 流程见 `PROJECT.md`；问题→规则知识库（权威记录）见 `docs/12`。
> 修改本文件或任何规则需在提交信息中说明。

---

## 0. 最高原则（用户 2026-09 确立；任何改动不得违反）

### 0.1 面向问题类，禁止个例手术
- 任何优化、转换、修复与策略都**不得针对某个特定文档/标准/数据行专门设计**；
- 禁止为了让单个样例通过、好看或"语义正确"而**手改 canonical / raw / SSIR /
  渲染数据**（一次性数据手术）；
- **任何时候都不修复个例的偶发缺陷**。

### 0.2 根因 → 通用规则 → 回归夹具 → 跨语料验证
- 每个缺陷先做根因分析，判断同类问题是否会在其它文档上复现，并定位到归属层：
  parser / normalize / renderer / compliance / tools；
- 只把**面向问题类**的通用规则落进代码，且必须**附回归夹具（单测）**并**跨语料
  验证**（corpus/golden 与 csm 手写夹具重 parse / roundtrip 无回归、干净夹具命中为 0）；
- 无法证明共性的修复不做：宁可如实记录，不为个例开洞。

### 0.3 抽取层真值丢失 → 如实标注，不伪造
- OCR 语义损失、公式区误识别、整行 marker/文本残缺等，若经分析确认无法以安全
  通用规则恢复，**如实标注为"抽取局限"**并记入 `docs/12`；
- canonical 等中间产物保留抽取原样（含噪声）；禁止用人工改写掩盖缺陷，禁止用
  外部推断值替换抽取真值。

### 0.4 既有产物的"外科手术" = 规则实例回放，先规则后数据
- 对 canonical 等产物做修补（结构修复回放等）前，对应通用规则**必须先落地**
  （代码 + 回归测试 + docs/12 记录）；
- 修补必须是该规则对实例的**确定性应用**（不是特判）；
- 回放后重 parse 该规则命中必须为 0（幂等断言），roundtrip 必须 passed。
- **禁止"先改数据、后补理由"**。

---

## 1. 缺陷处理闭环（每个新问题必走）

1. **先查知识库**：`docs/12` §2 问题→规则映射、§3 详细记录、§5.3 issue 码。
   已覆盖的问题不重复发明。
2. **根因三层区分**：源 PDF 文本层损坏 / MinerU（抽取工具）缺陷 / 本引擎缺陷
   （parser / normalize / renderer / compliance）。
3. **规则落点与 ID**：
   - 标准有明文规定 → `rules/base/<ID>/requirements.yaml`（`GBT-*`，`source` 标注章节）；
   - 标准无规定但通过通用性确认（根因通用、修复通用、可复现）→
     `extraction-rules.yaml`（`GEN-*`）；
   - parser 修复的 issue 码按序分配（`CSM-OCR-*` / `CSM-STRUCT-*` / `CSM-TABLE-*`，
     登记 `docs/12` §5.3）。
4. **验证**：unittest 全绿 → 相关流水线 roundtrip passed → 跨语料重 parse 无回归
   → 渲染抽查（基于 PDF 内部对象，非视觉比对）。
5. **沉淀**：`docs/12` §3 追加记录（现象/根因/修复/规则化/验证），同步
   §2 / §5.3 / §7 历史；rules/ 文件与源码「规则对应: XXX」注释同步。

---

## 2. 关键工程约定（防踩坑速查；细节见 PROJECT.md / docs/12）

- **命名唯一入口**：`src/leleby_ssir/naming.py` + `naming_specification.txt`。
  标准号斜杠→下划线、字母大写、空格→下划线；规则包 / 渲染 profile 与标准 ID
  同名同值（`rules/base/<ID>/`、`config/rendering/<ID>.yaml`）。规则 ID
  （GBT-C01 等）与渲染样式名属代码标识符，不随命名变更。
- **分层与验证独立性（2026-09-12 起）**：`tools/` 只放薄壳入口——抽取
  （`mineru_full_standard.py`，PDF → raw）、构建（`build_ssir.py`，raw 或 canonical →
  canonical → SSIR → render.pdf；两个起点都能独立重跑）、验证（`verify_conversion.py`，
  独立执行，构建流程默认不调用）；阶段实现集中在 `src/leleby_ssir/pipeline.py` 与 `pdf_compare.py`。
- **输入优先 Word（暂时停用）**：Word（docx/doc）输入与 .docx 渲染产物已于 2026-09-12
  暂时停用（docs/12 §3.47），当前只解析 `corpus/golden/` 下的 PDF；原规则为按 docx → doc → pdf
  顺序找输入，恢复时按 docs/12 §3.47 接回。PDF 走
  MinerU（`--method auto` 带文本层质量预检 GEN-092，损坏自动切 OCR）。
- **产物目录**：`out/mineru/<ID>/{00_source,01_extract,02_canonical,03_ssir,
  04_render,05_verify}` 为 gitignored 运行时产物；代码改动后重跑使其与代码一致，
  各阶段产物需同源一致（canonical → SSIR → render）。
- **raw 可能过期**：本库 GB_T_1.1 的 `01_extract/raw.md` 含已知粘连缺陷（4.1
  标题并入正文）。**禁止从旧 raw 整跑 normalize 覆盖 curated canonical**；需要
  更新 canonical 时按 §0.4 判定后做最小回放。
- **渲染字体**：渲染 profile 只能注册 TrueType 轮廓字体（正文思源宋体
  `config/rendering/fonts/NotoSerifCJKsc-Regular.ttf`、标题黑体 wqy-zenhei）；
  reportlab 不能加载 CFF/OpenType 轮廓。
- **PDF 文本层测试夹具**：必须用 pymupdf 内置 CJK 字体
  （`fontname="china-s"`）造真实中文文本层；不要用 reportlab canvas
  （helv 无中文字形 → 静默测垃圾数据）。
- **验证命令**：`.venv/bin/python -m unittest discover`；
  `tools/verify_markdown_roundtrip.py --examples-dir corpus/golden/csm`；
  `tools/mineru_full_standard.py <ID>`（抽取 + 渲染，快捷模式不再自动跑回环）；
  `tools/build_ssir.py <raw|canonical|ID>`（构建）；**回环验证是独立程序**：
  `tools/verify_conversion.py <ID|文档根|canonical|ssir>`（含可选 PDF 对比）；
  **规则回放是独立程序**（改动抽取/解析规则后对既有产物做确定性回放，带内容不变量与幂等断言）：
  `tools/replay_table_header_rows.py [--apply] [文件…]`（GEN-114 表头行数，canonical 与 raw 同源回放）；
  `ssir csm normalize/parse/roundtrip`、`ssir pdf render`（`--docx-output` 已暂时停用）。

---

## 3. 参考

- `PROJECT.md` — 环境 / 目录 / 流程；§7 规则体系（改代码前必读）、§8 陷阱、§9 测试。
- `docs/12` — 问题→规则知识库权威记录（§6 验证手册）。
- `docs/00~11` — 规格文档；`rules/` — 规则文件；`naming_specification.txt` — 命名规范。
- `README.md` — 用户操作手册。
