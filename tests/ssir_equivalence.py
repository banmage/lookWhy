"""测试用的 SSIR **语义视图**与等价断言。

背景：回环验证（canonical↔SSIR↔render.md↔verify 的分层比较引擎 `leleby_ssir.roundtrip`）
已于 2026-09-22 永久下线（用户裁定，见 docs/16）。测试里原有的「再解析一次、比较两边是否
等价」这类断言，本意是**幂等性/稳定性**回归（normalize 幂等、canonical 重 parse 稳定），
与已下线的回环验证不是一回事，故在此保留一个**测试局部**的语义视图比较，只取稳定字段：

- 结构树：节点 id / 编号 / 标题 / nodeType + 内容元素（id、类型、文本、列表项、注标记等）；
- 注册表：表 / 图 / 公式 / 未知块 / 注 / 目次条目（含表头行、单元格文本与合并信息）。

**不比较**任何易变字段（provenance、quality、时间戳、页锚点等）——它们与幂等性无关。
"""

from __future__ import annotations

from typing import Any


def semantic_view(document: dict[str, Any]) -> dict[str, Any]:
    """SSIR → 稳定语义视图（用于幂等性断言，不替代已下线的回测引擎）。"""
    return {
        "id": document.get("id"),
        "tree": [_node_view(node) for node in document.get("structuralRoot", {}).get("children", [])],
        "tables": [_table_view(table) for table in document.get("tables") or []],
        "figures": [_figure_view(figure) for figure in document.get("figures") or []],
        "formulas": [_formula_view(formula) for formula in document.get("formulas") or []],
        "unknownContents": [dict(unknown) for unknown in document.get("unknownContents") or []],
        "notes": [dict(note) for note in document.get("notes") or []],
        "tocEntries": [dict(entry) for entry in document.get("tocEntries") or []],
    }


def _node_view(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "number": node.get("number"),
        "title": node.get("title"),
        "nodeType": node.get("nodeType"),
        "contents": [_content_view(content) for content in node.get("contentElements") or []],
        "children": [_node_view(child) for child in node.get("children") or []],
    }


def _content_view(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": content.get("id"),
        "presentationType": content.get("presentationType"),
        "textContent": content.get("textContent"),
        "listItems": [
            {"marker": item.get("marker"), "text": item.get("text")}
            for item in content.get("listItems") or []
        ],
        "footnoteMarker": content.get("footnoteMarker"),
        "tableRef": content.get("tableRef"),
        "figureRef": content.get("figureRef"),
        "formulaRef": content.get("formulaRef"),
        "unknownRef": content.get("unknownRef"),
    }


def _table_view(table: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": table.get("id"),
        "number": table.get("number"),
        "caption": table.get("caption"),
        "unit": table.get("unit"),
        "grid": table.get("grid"),
        "rows": [
            {
                "isHeader": row.get("isHeader"),
                "cells": [
                    {
                        "text": cell.get("text"),
                        "rowIndex": cell.get("rowIndex"),
                        "colIndex": cell.get("colIndex"),
                        "rowspan": cell.get("rowspan"),
                        "colspan": cell.get("colspan"),
                    }
                    for cell in row.get("cells") or []
                ],
            }
            for row in table.get("rows") or []
        ],
    }


def _figure_view(figure: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": figure.get("id"),
        "number": figure.get("number"),
        "caption": figure.get("caption"),
        "unit": figure.get("unit"),
        "altText": figure.get("altText"),
        "preservationStatus": figure.get("preservationStatus"),
    }


def _formula_view(formula: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": formula.get("id"),
        "number": formula.get("number"),
        "rawText": formula.get("rawText"),
        "explanationGroup": formula.get("explanationGroup"),
    }


def assert_ssir_equivalent(test: Any, left: dict[str, Any], right: dict[str, Any]) -> None:
    """断言两份 SSIR 的稳定语义视图一致（幂等性/稳定性回归用）。"""
    test.assertEqual(semantic_view(left), semantic_view(right))
