# 验证报告 Q_YYJD 分层规则包 v0.1（规则包分层继承功能验证）

> 目的：以真实电机企业标准 Q/YYJD 001-2024《永磁直流无刷电动机》验证《规则包分层叠加与审核规则包模型 v0.1》的分层继承、分阶段审查、冲突裁决与溯源语义。
> 执行：2026-09-02；复现命令：`<repo>/.venv/bin/python tools/validate_profile_layering.py`（输出 out/profile-demo/report-qyyjd.json + stdout 摘要）
> 数据真实性声明：审查对象与技术规则源均为**真实 SSIR 产物**（Q_YYJD_001-2024、GB_T_5171.1-2014）；形式规则来自**真实 requirements.yaml**（GBT-E*/H*）。标 `demo` 者（旋转电机域包条目、企业模板层、语义裁决输入值）为演示构造，报告内均已注明，不作为 Q_YYJD 的真实合规结论。

---

## 1. 验证场景与输入

| 项 | 值 |
|---|---|
| 审查对象 | Q/YYJD 001-2024 永磁直流无刷电动机（企业标准；out/mineru/Q_YYJD_001-2024/03_ssir/） |
| 命中 profile | prof.brushless-pm-ent-review v1.1.0（industry-shared / industry-approved，系统管理员直接新增示例） |
| 层声明 | L1 base/GB_T_1.1-2020(formal-floor) → L2 base/GB_3100-2026(formal-floor) → L3 企业模板(formal-template) → L4 旋转电机域(technical-baseline) → L5 小功率电动机域(technical-optional) |
| 真实技术规则源 | GB_T_5171.1-2014 SSIR（auto-clause 候选抽取，需规则工程师批准转 approved） |
| 演示构造（demo:true） | 旋转电机域包条目（GB/T 755 规则包待建）、企业模板层（语料反推待建）、语义裁决输入值 |

---

## 2. 分层解析与挂载原因（验证"叠加与不加载无关数据"）

| 层 | 角色 | 类别/阶段 | 状态 | 挂载原因 |
|---|---|---|---|---|
| L1 GB_T_1.1-2020 | formal-floor | formal/form | approved | profile 声明（国家底线） |
| L2 GB_3100-2026 | formal-floor | formal/form | candidate(待建包) | profile 声明（国家底线） |
| L3 企业模板 v3 | formal-template | formal/form | approved(demo) | profile 声明 |
| L4 旋转电机域 | technical-baseline | technical/technical | candidate(demo) | **产品类归属 + 第 2 章引用命中（GB 755-2008 → 旋转电机域）** |
| L5 小功率电动机域 | technical-optional | technical/technical | candidate | **产品类归属**（brushless-pm-motor 属小功率无刷；文档未引用 5171.1 → 触发 CIT-HINT 推荐性提示） |

- 有效规则集：form=6（GBT-E01/E03/E05/E06/E07/E11，真实必备要素规则）、technical=36（小功率域候选 36 条，10 个域全覆盖：运行条件/额定值/温升/效率/介电/性能/噪声/振动/安全/电磁兼容）。
- **不加载无关数据**机制验证：profile 命中由 subject（doc-class=Q_、product=brushless-pm-motor）决定；审查按 review-stage 门控（form 阶段只载 L1-L3，technical 阶段才载 L4-L5）。照明类审查对象不会命中本 profile。
- 快照：hash=75dd768b1792f059（profile 版本 + 层序 + 有效规则 ID），pins-lock=true。

## 3. 阶段 A 形式审查结果（真实 findings，20 条：error 4 / warning 3 / info 13）

| 严重度 | 规则 | 发现 | 解读 |
|---|---|---|---|
| error | GBT-H02 | 顶层章号序列 [1,2,3,4,5,7,7,8] **缺少章 6** | 文档内存在 6.1/6.4..6.18 试验条款但无"6 试验方法"章标题——章标题丢失/被吞 |
| error | GBT-H02 | 章号**重复 7**（温升限值 与 检验规则） | 温升限值章疑实为 **5.7**（前缀 5. 丢失）；检验规则章应顺延 |
| error | GBT-H03 | 章 7(温升限值) 下子条 5.8…5.17 不以父号前缀 | 与上同源：5.x 后续条款被挂到错误父章 |
| error | GBT-H03 | 同级条号**重复 7.3.1**（出厂检验/型式试验） | 应顺序编号 7.3.1、7.3.2 |
| warning | GEN-093 | 游离顶层 documentBlock「包装箱内应附有以下文件：」 | 内容疑属 8.2 使用说明书/包装条款，被误提升为文档级块 |
| warning | GBT-E03 | 要素「前言」（必备）未检出 | 启发式结果，需人工复核源文件 |
| warning | TPL-02 | 企业模板要素「试验方法章标题」缺失但存在 6.x 条款 | 与"缺章 6"同源，提示源文件复核或规则化修复 |
| info | GB3100-R01 | 第 4 章数值 15 处/单位 3 处、第 5 章数值 5 处/单位 0 处 | 单位检查为待建包演示级；第 5 章数值多位于表格/条件句中，需正式规则细化 |
| info | GBT-H03/CIT-HINT/GBT-E01/E05/E06/E07/E11/TPL-* | 5.x 缺口提示；GB 755-2008 更新版提示；必备要素（封面/范围/引用/术语/核心要素）已检出；模板要素覆盖 | — |

要点：Q_YYJD 在真实 SSIR 中存在 **4 个结构性编号缺陷（缺 6、重复 7、前缀错位、重复 7.3.1）**——全部由 L1（GB/T 1.1 真实规则）自动判定，规则可溯源到 requirements.yaml 的 source 章节（表3/7.2/7.3）。这是"分层后的形式审查直接可用"的直接证据。

## 4. 阶段 B 技术要求审查结果

### 4.1 技术规则源自动抽取（GB_T_5171.1-2014，36 条候选）

- 两条抽取路径都命中：嵌套子条路径（第 4/11/13/16 章，如 SPM-4-4.2.1-1"电压偏差±5%时应能连续运行"）与平铺内嵌条款切分路径（第 8/12/18/19/20/22 章，如 SPM-8-8.2-2"额定功率(W)应按…系列选择"）。
- 每条候选规则携带：source-file（真实 SSIR 路径）、source-clause（如 4.2.1、8.2）、obligation（应→mandatory / 宜→recommended）、extract-mode。
- **已知局限（如实记录）**：本演示分类器把"宜…但同时含应/将"的条款整条判为 mandatory；正式建包需按句/按语气切分再判级，且自动候选须经规则工程师批准（status: candidate → approved）。

### 4.2 域覆盖矩阵（5171.1 强制域 vs Q_YYJD 全文关键词）

10/10 域全部命中（运行条件/额定值/温升/效率/介电/性能/噪声/振动/安全/电磁兼容均能在 Q_YYJD 中找到对应表述）。注意覆盖度为关键词代理，正式阶段需条款语义对齐；"安全/接地/防护"命中可能来自标志/说明书文本，需人工确认是否为完整安全条款。

### 4.3 语义裁决演示（decide()，2026-09-02 决策落实）

| 规则 | 义务 | 关系 | 裁决 | 说明 |
|---|---|---|---|---|
| ROT-DEMO-01（GB/T 755 演示） | mandatory | relax（±5%→±10%，演示输入） | **register-required** | 强制放宽 → 生成偏差登记单（裁定人/依据/锚点/有效期待填） |
| SPM-12.3（GB/T 5171.1 §12.3 真实文本） | recommended | gap（未提供效率点，演示输入） | **note** | 推荐未覆盖 → 只记备注，不登记 |
| ROT-DEMO-02（GB/T 755 演示） | mandatory | tighten（≤60→≤55，演示输入） | **pass** | 加严直接通过 |
| GBT-E01 封面（L1）被企业模板覆盖（演示） | legal-floor | override | **blocked-by-legal-floor** | 国家底线不可被模板层放松 |

deviations-register=1（仅强制放宽）、notes=1（推荐备注）——与决策一致。

## 5. 结论

1. **分层继承功能验证通过**：base → 企业模板 → 行业域包按序材料化，逐条携带 layerPath；形式阶段与技术要求阶段按 review-stage 门控分离；规则可沿 layerPath→package→source-file→条款号 溯源。
2. **真实审查价值立即显现**：仅 L1 形式规则就在 Q_YYJD 真实 SSIR 上定位 4 类编号缺陷（与抽取质量同源：温升限值 5.7 编号截断为 7、试验方法章标题丢失、7.3.1 重复、游离块）——这些正对应你 pipeline 侧已修问题的"审查面"。
3. **2026-09-02 两项决策已代码化**：强制性/推荐性分级裁决（decide() 仅强制放宽触发 register）；profile 行业共享与审批字段（share/status + 系统管理员直接新增示例）。
4. **诚实边界**：旋转电机域条目、企业模板层、语义裁决输入值为 demo 构造；auto-clause 为候选抽取（需人工批准）；单位检查为待建包演示级。以上不作为 Q_YYJD 的最终合规结论。

## 6. 下一步（接 Track R）

- R0a 正式化：registry 双区 schema（rule-source-registry + audit-profile）落地 rules/；把 demo 层数据迁为真实规则包（GB_T_755-2025 建包、企业模板建包、GB_3100-2026 建包）。
- R1 形式审查接现有 compliance 引擎：executor 化 findings 与 parse-report 对齐。
- R2 首个 approved 技术规则源：5171.1 auto 候选人工审核批准后转 approved，域包指标范围对标试点。
- 修复联动建议（源文件侧，非本验证范围）：Q_YYJD 的 5.7/6 章标题问题可用 GEN-031/GEN-035 类规则化修复后重跑，验证审查闭环。

## 附：制品

- 引擎：tools/validate_profile_layering.py
- 演示 registry：out/profile-demo/registry-demo.yaml
- 机器报告：out/profile-demo/report-qyyjd.json
- 设计依据：docs/semantic_Stage/lookWhy 规则包分层叠加与审核规则包模型 v0.1.md、规则层分类与分阶段审查设计 v0.1.md
