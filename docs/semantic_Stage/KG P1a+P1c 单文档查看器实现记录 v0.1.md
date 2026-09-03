# KG P1a + P1c 单文档查看器实现记录 v0.1（2026-09-03）

> 对应《lookWhy 知识图谱阶段规划与存储选型建议 v0.1》§6 阶段 1 的 P1a（sqlite 索引 +
> 列表/树浏览）与 P1c（kg.json 图切片 + vis-network 本体图）。全部未提交 git。

## 决策与数据流（延续主规划"文件真源"原则）

```
03_ssir/<ID>.ssir.json（唯一真源）
   ├─→ sqlite（out/kg/kg.db，可重建索引）：documents 元数据 + structure 扁平树 + 全文载荷 JSON
   └─→ kg.json（图切片投影，kgVersion=0.1）：节点复用 SSIR URI；供 vis-network / 未来 neo4j loader
```

- 不做全量 EAV 规范化：载荷 JSON1 存整篇，渲染按需解析；structure 只落扁平树
  （id/parent_id/number/title/term/md_start_line）供树导航 SQL。
- sqlite 用标准库 sqlite3 + KGDocStore 类抽象（切 PostgreSQL 时替换该类）；未引 SQLAlchemy。
- kg.json 是"真源的可复现视图"，可与库内 payload 双向重生成；`kg rebuild` = 重导。

## 命令

```bash
.venv/bin/python tools/kg_tool.py import <ID> [--all]   # ID 快捷: out/mineru/<ID>/03_ssir/<ID>.ssir.json
.venv/bin/python tools/kg_tool.py list
.venv/bin/python tools/kg_tool.py build <ssir.json 或 ID> [-o out.kg.json]   # + jsonschema 校验
.venv/bin/python tools/kg_tool.py serve --port 8600
# http://127.0.0.1:8600/ 列表 → /doc/<ID> 树/内容浏览 → /graph/<ID> vis-network
```

## 制品

- src/leleby_ssir/kg.py —— SSIR→kg 映射器（纯函数 build_kg / validate_kg / extract_references）
- src/leleby_ssir/kg.schema.json —— kg.json 契约（draft-07）
- src/leleby_ssir/kgstore.py —— sqlite 索引库（import/list/all_rows/get_row/payload/canonical_lines）
- tools/kg_tool.py —— build/import/list/serve CLI
- tools/kg_viewer/ —— Flask 查看器（templates + render.py + static；vis-network.min.js 本地副本
  来自 dss_bak/static/js/，MIT，附 VIS_NETWORK_LICENSE.txt）
- tests/test_kg.py —— 8 测试（映射/校验/引用抽取/store 往返/命名）
- pyproject.toml 新增依赖 flask>=3.0

## 实测（真实语料）

- GB_T_1.1-2020：结构 272 节点；kg 全量 1025 节点/1024 边；core 视图 337 节点/336 边
  （段落级 CE 688 个默认隐藏）；schema 校验通过；第 2 章引用 14 条带 md 行。
- Q_YYJD_001-2024：kg 185 节点；引用 12 条（GB/T 12665-2008 等，md 行可跳原文）。
- 表/图/公式渲染：表1 题注+8 行、图 7-4 经 /asset 解析 PNG 均 200；条款 → md 行两步内可达。
- 全量单测 168/168 通过（含本功能 8 个）。

## 已记录坑

1. SSIR assetRef 带 `assets/` 前缀且相对**文档根**；asset_root=docroot/assets 时 join 会重复
   `assets/assets/` → /asset 解析需先剥前缀再拼（与 pdf_renderer._resolve_asset 同思路逐级向上）。
2. 节点 id 形如 `ssir:…/clause-3.1-007` 含 `/` → Flask 路由必须用 `<path:node_id>` 转换器。
3. 内容元素三种形态：paragraph(textContent)、list(listItems[])、note(textContent 已含"注："前缀)；
   表/图/公式 CE 只有 tableRef/figureRef/formulaRef（registry 实体另存），不重复建 CE 节点。
4. Term 节点 id 用 `节点id + "/term"` 派生（非 SSIR 原生 id，schema 允许扩展属性）；
   definitionText 取自该节点 semanticTypes=termDefinition 的首个 CE。
5. kg.schema 里 nodes.anchor 为 object；映射器只在有锚点时才写（None 写进去会校验失败）。
6. graph 页 core 过滤 = 去掉 CE 节点及其 CONTAINS_ELEMENT 入边，保留 registry（表/图/公式）边。

## 下一步（P2/阶段 2 闸门）

- P2 多标准：documents.references（norm 归一键）已有，双侧在场即可生成 CITES 边；
  metadata.replaces 同理生成 REPLACES（GB_T_23132-2008/-2024 已在库）。
- 中文全文检索、运营库（审核流/权限）按主规划 §6 阶段 3；数据量大/多跳查询变扭时再引 Neo4j。
- Track R 可视化面：规则包层（L1..Ln）叠层图数据源 = rules/ registry + profile 材料化产物
  （R0a 落地后自然可接）。
