# leleby SSIR JSON Schema Specification v0.3

> **文档状态**：正式发布 | **版本**：0.3 | **日期**：2026-08-15
>
> **变更说明**（v0.2 → v0.3）：
> - **更新 Data Model 引用**：从 v0.3 升级至 v0.4（基于 Round-trip 语义增强）
> - **新增 `ssirVersion` 枚举值**：增加 `"0.4"` 支持新版 Data Model
> - **新增 `NormativeRenderingProfile` 枚举**：用于标识渲染时使用的规范性配置文件
> - **更新 Scope 描述**：明确 Round-trip 验证目标为 `SSIR ≈ Verify`（SSIR 语义等价性），而非 `源文档 ≈ 渲染文档`
> - **更新 Validation Layers 说明**：与 Data Model v0.4 的四个验证概念（Source Fidelity、Rendering Conformance、Round-trip Completeness、Round-trip Equivalence）对齐
> - **新增 `RenderingProfile` 字段**：在 QualityAssessment 中记录渲染使用的 Profile，支持 Rendering Conformance 验证
> - **更新示例中的 `ssirVersion`**：从 `"0.3"` 改为 `"0.4"`
> - **更新文档元数据**：反映 Data Model v0.4 的变更
> - **更新 Next Steps**：增加 Schema → Data Model v0.4 对齐确认步骤


## 1. Scope

本规范规定了 leleby SSIR（Standard Structured Information Representation）的 JSON Schema，基于《leleby SSIR Data Model v0.4》定义所有核心对象、嵌套类型、枚举和约束。本 Schema 兼容 JSON Schema Draft-07。

**本 Schema 的职责边界**：

| 层级 | 职责 | 实施方式 |
|------|------|----------|
| **JSON Schema Validation** | 类型、必填、枚举、基本格式、数组结构、条件存在 | 本 Schema（机器可执行） |
| **Semantic Validation** | ID 引用存在性、parent 关系、TextSpan 边界、表格行列匹配 | 独立 Semantic Validator |
| **Round-trip Validation** | `SSIR → 渲染 → 重新提取 → Verify`，验证 `SSIR ≈ Verify` | 独立 Round-trip Validator |

本 Schema 仅覆盖第一层（JSON Schema Validation）。第二层和第三层由独立规范定义。

**与 Data Model v0.4 的对应关系**：
- Data Model §7.2 Source Fidelity → Schema Validation + Semantic Validation
- Data Model §7.3 Normative Rendering → 独立 Rendering Conformance 验证（非 Schema 范围）
- Data Model §7.5 SSIR Equivalence → 独立 Round-trip Validator（非 Schema 范围）


## 2. JSON Schema 概述

- **$schema**：`http://json-schema.org/draft-07/schema#`
- **$id**：`https://leleby.io/schemas/ssir/v0.3.schema.json`
- **根类型**：`object`，必须包含 `SSIRDocument` 定义的所有必选属性
- **定义组织**：所有类型定义在 `definitions` 中，根模式引用 `#/definitions/SSIRDocument`

## 3. ID Pattern 约束

| ID 类型 | Pattern | 示例 |
|---------|---------|------|
| `SSIRDocument.id` | `^ssir:[A-Za-z0-9._:/-]+$` | `ssir:GBT-22373-2021` |
| `SourceFile.id` | `^src:[A-Fa-f0-9]{16,}$` | `src:a1b2c3d4e5f67890` |
| `ProcessingRun.id` | `^ssir:processing/run/[0-9]{8}-[0-9]+$` | `ssir:processing/run/20260815-001` |
| `StructuralNode.id` | `^ssir:[A-Za-z0-9._:/-]+/[A-Za-z0-9._-]+$` | `ssir:GBT-22373-2021/clause-5.2` |
| `ContentElement.id` | `^ssir:[A-Za-z0-9._:/-]+/content/[A-Za-z0-9_-]+$` | `ssir:GBT-22373-2021/content/c-001` |
| `Table.id` | `^ssir:[A-Za-z0-9._:/-]+/table/[A-Za-z0-9_-]+$` | `ssir:GBT-22373-2021/table/t-001` |
| `Figure.id` | `^ssir:[A-Za-z0-9._:/-]+/figure/[A-Za-z0-9_-]+$` | `ssir:GBT-22373-2021/figure/f-001` |
| `Formula.id` | `^ssir:[A-Za-z0-9._:/-]+/formula/[A-Za-z0-9_-]+$` | `ssir:GBT-22373-2021/formula/fm-001` |
| `UnknownContent.id` | `^ssir:[A-Za-z0-9._:/-]+/unknown/[A-Za-z0-9_-]+$` | `ssir:GBT-22373-2021/unknown/u-001` |
| `TextSpan.id` | `^ssir:[A-Za-z0-9._:/-]+/span/[A-Za-z0-9_-]+$` | `ssir:GBT-22373-2021/span/s-001` |
| `SourceAnchor.id` | `^ssir:[A-Za-z0-9._:/-]+/anchor/[A-Za-z0-9_-]+$` | `ssir:GBT-22373-2021/anchor/a-001` |
| `EntityMention.id` | `^ssir:[A-Za-z0-9._:/-]+/mention/[A-Za-z0-9_-]+$` | `ssir:GBT-22373-2021/mention/m-001` |
| `RelationMention.id` | `^ssir:[A-Za-z0-9._:/-]+/relation/[A-Za-z0-9_-]+$` | `ssir:GBT-22373-2021/relation/r-001` |
| `Reference.id` | `^ssir:[A-Za-z0-9._:/-]+/reference/[A-Za-z0-9_-]+$` | `ssir:GBT-22373-2021/reference/ref-001` |
| `DocumentRelationship.id` | `^ssir:[A-Za-z0-9._:/-]+/docrel/[A-Za-z0-9_-]+$` | `ssir:GBT-22373-2021/docrel/dr-001` |
| `ListItem.id` | `^[A-Za-z0-9_-]+$`（局部唯一） | `li-001` |
| `TableRow.id` | `^[A-Za-z0-9_-]+$`（局部唯一） | `row-001` |
| `TableCell.id` | `^[A-Za-z0-9_-]+$`（局部唯一） | `cell-001` |

## 4. 通用约定

- **日期时间**：使用 ISO 8601 格式，如 `"2026-08-15T10:30:00Z"`
- **日期**：使用 `YYYY-MM-DD` 格式
- **置信度**：浮点数，取值范围 `0.0` ~ `1.0`
- **空值**：可选属性如未提供，应省略该键，而不是设为 `null`
- **数组顺序**：除非特别说明，顺序有意义，应保持原始顺序
- **bbox 坐标系统**：`[x1, y1, x2, y2]`，PDF Point 坐标系，原点为页面左上角，单位为 points（1/72 英寸）


## 5. JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://leleby.io/schemas/ssir/v0.3.schema.json",
  "title": "leleby SSIR Schema v0.3",
  "description": "JSON Schema for leleby SSIR (Standard Structured Information Representation) v0.4 data model",
  "type": "object",
  "allOf": [{ "$ref": "#/definitions/SSIRDocument" }],
  "definitions": {
    "SSIRDocument": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+$",
          "description": "SSIR文档唯一标识符"
        },
        "ssirVersion": {
          "type": "string",
          "enum": ["0.3", "0.4"],
          "description": "SSIR数据模型版本"
        },
        "documentType": { "$ref": "#/definitions/DocumentType" },
        "metadata": { "$ref": "#/definitions/DocumentMetadata" },
        "sourceFiles": {
          "type": "array",
          "items": { "$ref": "#/definitions/SourceFile" },
          "minItems": 1
        },
        "canonicalText": { "$ref": "#/definitions/CanonicalText" },
        "structuralRoot": { "$ref": "#/definitions/StructuralNode" },
        "tables": {
          "type": "array",
          "items": { "$ref": "#/definitions/Table" },
          "description": "表格对象注册表"
        },
        "figures": {
          "type": "array",
          "items": { "$ref": "#/definitions/Figure" },
          "description": "图对象注册表"
        },
        "formulas": {
          "type": "array",
          "items": { "$ref": "#/definitions/Formula" },
          "description": "公式对象注册表"
        },
        "unknownContents": {
          "type": "array",
          "items": { "$ref": "#/definitions/UnknownContent" },
          "description": "未知内容对象注册表"
        },
        "references": {
          "type": "array",
          "items": { "$ref": "#/definitions/Reference" }
        },
        "documentRelationships": {
          "type": "array",
          "items": { "$ref": "#/definitions/DocumentRelationship" }
        },
        "entityMentions": {
          "type": "array",
          "items": { "$ref": "#/definitions/EntityMention" }
        },
        "relationMentions": {
          "type": "array",
          "items": { "$ref": "#/definitions/RelationMention" }
        },
        "processingRuns": {
          "type": "array",
          "items": { "$ref": "#/definitions/ProcessingRun" },
          "minItems": 1
        },
        "qualityAssessments": {
          "type": "array",
          "items": { "$ref": "#/definitions/QualityAssessment" }
        },
        "preservationLevel": { "$ref": "#/definitions/PreservationLevel" },
        "createdAt": { "type": "string", "format": "date-time" },
        "updatedAt": { "type": "string", "format": "date-time" }
      },
      "required": [
        "id",
        "ssirVersion",
        "documentType",
        "metadata",
        "sourceFiles",
        "structuralRoot",
        "processingRuns",
        "createdAt"
      ],
      "allOf": [
        {
          "if": {
            "properties": {
              "documentType": {
                "const": "standard"
              }
            },
            "required": ["documentType"]
          },
          "then": {
            "properties": {
              "metadata": {
                "required": ["standard"]
              }
            }
          }
        }
      ],
      "additionalProperties": false
    },

    "DocumentType": {
      "type": "string",
      "enum": [
        "standard",
        "regulation",
        "specification",
        "enterpriseStandard",
        "contract",
        "testReport",
        "other"
      ]
    },

    "DocumentMetadata": {
      "type": "object",
      "properties": {
        "common": { "$ref": "#/definitions/CommonMetadata" },
        "standard": { "$ref": "#/definitions/StandardMetadata" }
      },
      "required": ["common"],
      "additionalProperties": false
    },

    "CommonMetadata": {
      "type": "object",
      "properties": {
        "documentIdentifier": { "type": "string" },
        "title": { "type": "string" },
        "titleEn": { "type": "string" },
        "language": { "type": "string" },
        "publicationDate": { "type": "string", "format": "date" },
        "effectiveDate": { "type": "string", "format": "date" },
        "issuer": { "type": "string" },
        "status": { "type": "string" },
        "version": { "type": "string" }
      },
      "required": ["documentIdentifier", "title"],
      "additionalProperties": false
    },

    "StandardMetadata": {
      "type": "object",
      "properties": {
        "standardNumber": { "type": "string" },
        "chineseTitle": { "type": "string" },
        "englishTitle": { "type": "string" },
        "originalTitle": { "type": "string" },
        "publishingBody": { "type": "string" },
        "publishingBodyCode": { "type": "string" },
        "ccs": { "type": "string" },
        "ics": { "type": "string" },
        "drafters": {
          "type": "array",
          "items": { "type": "string" }
        },
        "proposer": { "type": "string" },
        "mirrorBody": { "type": "string" },
        "adoption": { "type": "string" }
      },
      "required": ["standardNumber"],
      "additionalProperties": false
    },

    "SourceFile": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^src:[A-Fa-f0-9]{16,}$"
        },
        "fileName": { "type": "string" },
        "storageUri": { "type": "string", "format": "uri" },
        "fileHash": { "$ref": "#/definitions/FileHash" },
        "fileSize": { "type": "integer", "minimum": 0 },
        "mimeType": { "type": "string" },
        "pageCount": { "type": "integer", "minimum": 0 },
        "metadata": { "type": "object" }
      },
      "required": ["id", "fileName", "fileHash", "mimeType"],
      "additionalProperties": false
    },

    "FileHash": {
      "type": "object",
      "properties": {
        "algorithm": {
          "type": "string",
          "enum": ["SHA-256", "SHA-512", "MD5", "SHA-1"]
        },
        "value": { "type": "string" }
      },
      "required": ["algorithm", "value"],
      "additionalProperties": false
    },

    "CanonicalText": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/canonical$"
        },
        "text": { "type": "string" },
        "normalizationPolicy": { "$ref": "#/definitions/NormalizationPolicy" },
        "sourceElementRefs": {
          "type": "array",
          "items": { "type": "string" }
        },
        "version": { "type": "string" }
      },
      "required": ["id", "text"],
      "additionalProperties": false
    },

    "NormalizationPolicy": {
      "type": "string",
      "enum": [
        "ssir-canonical-text-v1"
      ],
      "description": "SSIR Canonical Text Normalization Algorithm v1: 去除多余空白（保留段落间单个换行）、统一空格、Unicode NFC 规范化"
    },

    "NormativeRenderingProfile": {
      "type": "string",
      "enum": [
        "GB_T_1.1-2020",
        "iso-iec-directives-part-2",
        "custom"
      ],
      "description": "规范性渲染配置文件，用于标识从 SSIR 生成传统文档时使用的规范化规则"
    },

    "StructuralNode": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/[A-Za-z0-9._-]+$"
        },
        "logicalId": { "type": "string" },
        "nodeType": { "$ref": "#/definitions/StructuralNodeType" },
        "level": { "type": "integer" },
        "number": { "type": "string" },
        "title": { "type": "string" },
        "children": {
          "type": "array",
          "items": { "$ref": "#/definitions/StructuralNode" }
        },
        "contentElements": {
          "type": "array",
          "items": { "$ref": "#/definitions/ContentElement" }
        },
        "sourceAnchors": {
          "type": "array",
          "items": { "$ref": "#/definitions/SourceAnchor" }
        },
        "sortOrder": { "type": "integer" }
      },
      "required": ["id", "logicalId", "nodeType", "sortOrder"],
      "allOf": [
        {
          "if": {
            "properties": {
              "nodeType": {
                "not": { "const": "document" }
              }
            }
          },
          "then": {
            "properties": {
              "sourceAnchors": {
                "minItems": 1
              }
            }
          }
        }
      ],
      "additionalProperties": false
    },

    "StructuralNodeType": {
      "type": "string",
      "enum": [
        "document",
        "documentBlock",
        "section",
        "clause",
        "subClause",
        "item",
        "subItem",
        "annex",
        "annexSection"
      ]
    },

    "ContentElement": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/content/[A-Za-z0-9_-]+$"
        },
        "presentationType": { "$ref": "#/definitions/PresentationType" },
        "parentNodeId": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/[A-Za-z0-9._-]+$"
        },
        "semanticTypes": {
          "type": "array",
          "items": { "$ref": "#/definitions/SemanticType" }
        },
        "normativeStatus": { "$ref": "#/definitions/NormativeStatus" },
        "sortOrder": { "type": "integer" },
        "sourceAnchors": {
          "type": "array",
          "items": { "$ref": "#/definitions/SourceAnchor" },
          "minItems": 1
        },
        "textContent": { "type": "string" },
        "richText": {
          "type": "array",
          "items": { "$ref": "#/definitions/RichTextSpan" }
        },
        "listItems": {
          "type": "array",
          "items": { "$ref": "#/definitions/ListItem" }
        },
        "tableRef": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/table/[A-Za-z0-9_-]+$"
        },
        "figureRef": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/figure/[A-Za-z0-9_-]+$"
        },
        "formulaRef": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/formula/[A-Za-z0-9_-]+$"
        },
        "unknownRef": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/unknown/[A-Za-z0-9_-]+$"
        }
      },
      "required": ["id", "presentationType", "parentNodeId", "sortOrder", "sourceAnchors"],
      "allOf": [
        {
          "if": {
            "properties": {
              "presentationType": {
                "const": "table"
              }
            }
          },
          "then": {
            "required": ["tableRef"]
          }
        },
        {
          "if": {
            "properties": {
              "presentationType": {
                "const": "figure"
              }
            }
          },
          "then": {
            "required": ["figureRef"]
          }
        },
        {
          "if": {
            "properties": {
              "presentationType": {
                "const": "formula"
              }
            }
          },
          "then": {
            "required": ["formulaRef"]
          }
        },
        {
          "if": {
            "properties": {
              "presentationType": {
                "const": "other"
              }
            }
          },
          "then": {
            "required": ["unknownRef"]
          }
        }
      ],
      "additionalProperties": false
    },

    "PresentationType": {
      "type": "string",
      "enum": [
        "paragraph",
        "heading",
        "list",
        "table",
        "figure",
        "formula",
        "note",
        "example",
        "warning",
        "quote",
        "footnote",
        "other"
      ]
    },

    "SemanticType": {
      "type": "string",
      "enum": [
        "scope",
        "normativeReference",
        "termDefinition",
        "symbolDefinition",
        "classification",
        "requirement",
        "testMethod",
        "inspectionRule",
        "markingRequirement",
        "packagingTransportStorage",
        "example",
        "warning",
        "note",
        "appendixExplanation",
        "bibliographicReference"
      ]
    },

    "NormativeStatus": {
      "type": "string",
      "enum": ["normative", "informative", "unknown", "notApplicable"]
    },

    "RichTextSpan": {
      "type": "object",
      "properties": {
        "text": { "type": "string" },
        "bold": { "type": "boolean" },
        "italic": { "type": "boolean" },
        "subscript": { "type": "boolean" },
        "superscript": { "type": "boolean" },
        "underline": { "type": "boolean" },
        "style": { "type": "string" }
      },
      "required": ["text"],
      "additionalProperties": false
    },

    "ListItem": {
      "type": "object",
      "properties": {
        "id": { "type": "string", "pattern": "^[A-Za-z0-9_-]+$" },
        "text": { "type": "string" },
        "richText": {
          "type": "array",
          "items": { "$ref": "#/definitions/RichTextSpan" }
        },
        "marker": { "type": "string" },
        "markerType": { "$ref": "#/definitions/MarkerType" },
        "subItems": {
          "type": "array",
          "items": { "$ref": "#/definitions/ListItem" }
        },
        "sourceAnchor": { "$ref": "#/definitions/SourceAnchor" },
        "sortOrder": { "type": "integer" }
      },
      "required": ["id", "sortOrder"],
      "additionalProperties": false
    },

    "MarkerType": {
      "type": "string",
      "enum": ["lowerAlpha", "upperAlpha", "numeric", "roman", "bullet", "dash", "other"]
    },

    "Table": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/table/[A-Za-z0-9_-]+$"
        },
        "number": { "type": "string" },
        "caption": { "type": "string" },
        "rowCount": { "type": "integer", "minimum": 0 },
        "colCount": { "type": "integer", "minimum": 0 },
        "rows": {
          "type": "array",
          "items": { "$ref": "#/definitions/TableRow" }
        },
        "tableNote": {
          "type": "array",
          "items": { "type": "string" }
        },
        "sourceAnchors": {
          "type": "array",
          "items": { "$ref": "#/definitions/SourceAnchor" },
          "minItems": 1
        },
        "crossPage": { "type": "boolean" },
        "preservationStatus": { "$ref": "#/definitions/PreservationStatus" }
      },
      "required": ["id", "rowCount", "colCount", "rows", "sourceAnchors"],
      "additionalProperties": false
    },

    "TableRow": {
      "type": "object",
      "properties": {
        "id": { "type": "string", "pattern": "^[A-Za-z0-9_-]+$" },
        "rowIndex": { "type": "integer", "minimum": 0 },
        "cells": {
          "type": "array",
          "items": { "$ref": "#/definitions/TableCell" }
        },
        "isHeader": { "type": "boolean" }
      },
      "required": ["id", "rowIndex", "cells"],
      "additionalProperties": false
    },

    "TableCell": {
      "type": "object",
      "properties": {
        "id": { "type": "string", "pattern": "^[A-Za-z0-9_-]+$" },
        "rowIndex": { "type": "integer", "minimum": 0 },
        "colIndex": { "type": "integer", "minimum": 0 },
        "text": { "type": "string" },
        "richText": {
          "type": "array",
          "items": { "$ref": "#/definitions/RichTextSpan" }
        },
        "colspan": { "type": "integer", "minimum": 1, "default": 1 },
        "rowspan": { "type": "integer", "minimum": 1, "default": 1 },
        "isHeader": { "type": "boolean" },
        "sourceAnchor": { "$ref": "#/definitions/SourceAnchor" }
      },
      "required": ["id", "rowIndex", "colIndex"],
      "additionalProperties": false
    },

    "Figure": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/figure/[A-Za-z0-9_-]+$"
        },
        "number": { "type": "string" },
        "caption": { "type": "string" },
        "assetRef": { "type": "string" },
        "altText": { "type": "string" },
        "sourceAnchors": {
          "type": "array",
          "items": { "$ref": "#/definitions/SourceAnchor" },
          "minItems": 1
        },
        "preservationStatus": { "$ref": "#/definitions/PreservationStatus" }
      },
      "required": ["id", "sourceAnchors"],
      "additionalProperties": false
    },

    "Formula": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/formula/[A-Za-z0-9_-]+$"
        },
        "number": { "type": "string" },
        "rawText": { "type": "string" },
        "latex": { "type": "string" },
        "sourceAnchors": {
          "type": "array",
          "items": { "$ref": "#/definitions/SourceAnchor" },
          "minItems": 1
        },
        "preservationStatus": { "$ref": "#/definitions/PreservationStatus" }
      },
      "required": ["id", "rawText", "sourceAnchors"],
      "additionalProperties": false
    },

    "UnknownContent": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/unknown/[A-Za-z0-9_-]+$"
        },
        "rawContent": { "type": "string" },
        "contentTypeHint": { "type": "string" },
        "sourceAnchors": {
          "type": "array",
          "items": { "$ref": "#/definitions/SourceAnchor" },
          "minItems": 1
        }
      },
      "required": ["id", "rawContent", "sourceAnchors"],
      "additionalProperties": false
    },

    "TextSpan": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/span/[A-Za-z0-9_-]+$"
        },
        "canonicalTextId": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/canonical$"
        },
        "startChar": { "type": "integer", "minimum": 0 },
        "endChar": { "type": "integer", "minimum": 1 },
        "text": { "type": "string" },
        "sourceAnchor": { "$ref": "#/definitions/SourceAnchor" }
      },
      "$comment": "Note: startChar < endChar MUST be enforced by Semantic Validator (JSON Schema cannot express cross-field comparison)",
      "required": ["id", "canonicalTextId", "startChar", "endChar", "text"],
      "additionalProperties": false
    },

    "SourceAnchor": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/anchor/[A-Za-z0-9_-]+$"
        },
        "sourceFileId": {
          "type": "string",
          "pattern": "^src:[A-Fa-f0-9]{16,}$"
        },
        "anchorType": { "$ref": "#/definitions/AnchorType" },
        "pdfPageIndex": { "type": "integer", "minimum": 0 },
        "documentPageLabel": { "type": "string" },
        "bbox": {
          "type": "array",
          "items": { "type": "number" },
          "minItems": 4,
          "maxItems": 4,
          "description": "[x1, y1, x2, y2], PDF Point coordinate system, top-left origin"
        },
        "textSpanRef": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/span/[A-Za-z0-9_-]+$"
        },
        "textQuote": { "type": "string" },
        "sourceBlockId": { "type": "string" },
        "markdownStartLine": { "type": "integer", "minimum": 1 },
        "markdownStartColumn": { "type": "integer", "minimum": 1 },
        "markdownEndLine": { "type": "integer", "minimum": 1 },
        "markdownEndColumn": { "type": "integer", "minimum": 1 },
        "markdownNodePath": { "type": "string" },
        "assetRef": { "type": "string" },
        "extractionRegion": { "type": "string" }
      },
      "required": ["id", "sourceFileId", "anchorType"],
      "$comment": "Conditional constraints based on anchorType MUST be enforced by Semantic Validator (not expressible in JSON Schema Draft-07)",
      "allOf": [
        {
          "if": {
            "properties": {
              "anchorType": {
                "const": "bbox"
              }
            }
          },
          "then": {
            "required": ["pdfPageIndex", "bbox"]
          }
        },
        {
          "if": {
            "properties": {
              "anchorType": {
                "const": "textSpan"
              }
            }
          },
          "then": {
            "required": ["textSpanRef"]
          }
        },
        {
          "if": {
            "properties": {
              "anchorType": {
                "const": "block"
              }
            }
          },
          "then": {
            "required": ["sourceBlockId"]
          }
        },
        {
          "if": {
            "properties": {
              "anchorType": {
                "const": "tableCell"
              }
            }
          },
          "then": {
            "required": ["sourceBlockId", "pdfPageIndex"]
          }
        },
        {
          "if": {
            "properties": {
              "anchorType": {
                "const": "page"
              }
            }
          },
          "then": {
            "required": ["pdfPageIndex"]
          }
        },
        {
          "if": {
            "properties": {
              "anchorType": {
                "const": "markdown"
              }
            }
          },
          "then": {
            "required": ["markdownStartLine", "markdownEndLine"]
          }
        },
        {
          "if": {
            "properties": {
              "anchorType": {
                "const": "figureRegion"
              }
            }
          },
          "then": {
            "required": ["pdfPageIndex", "bbox"]
          }
        }
      ],
      "additionalProperties": false
    },

    "AnchorType": {
      "type": "string",
      "enum": ["page", "bbox", "textSpan", "block", "tableCell", "figureRegion", "markdown"]
    },

    "EntityMention": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/mention/[A-Za-z0-9_-]+$"
        },
        "surfaceForm": { "type": "string" },
        "normalizedForm": { "type": "string" },
        "mentionType": { "$ref": "#/definitions/EntityMentionType" },
        "parentNodeId": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/[A-Za-z0-9._-]+$"
        },
        "sourceElementId": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/content/[A-Za-z0-9_-]+$"
        },
        "textSpan": { "$ref": "#/definitions/TextSpan" },
        "context": { "type": "string" },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "candidateMappings": {
          "type": "array",
          "items": { "$ref": "#/definitions/CandidateMapping" }
        }
      },
      "required": ["id", "surfaceForm", "mentionType", "parentNodeId", "textSpan"],
      "additionalProperties": false
    },

    "EntityMentionType": {
      "type": "string",
      "enum": [
        "documentConcept",
        "product",
        "material",
        "organization",
        "standard",
        "regulation",
        "process",
        "equipment",
        "parameter",
        "unit",
        "value",
        "time",
        "location",
        "identifier",
        "other"
      ]
    },

    "CandidateMapping": {
      "type": "object",
      "properties": {
        "ontology": { "type": "string" },
        "conceptId": { "type": "string" },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "status": { "type": "string", "enum": ["candidate", "confirmed", "rejected"] }
      },
      "required": ["ontology", "conceptId"],
      "additionalProperties": false
    },

    "RelationMention": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/relation/[A-Za-z0-9_-]+$"
        },
        "relationType": { "$ref": "#/definitions/RelationMentionType" },
        "sourceId": { "type": "string" },
        "targetId": { "type": "string" },
        "targetMentionText": { "type": "string" },
        "parentNodeId": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/[A-Za-z0-9._-]+$"
        },
        "sourceElementId": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/content/[A-Za-z0-9_-]+$"
        },
        "textSpan": { "$ref": "#/definitions/TextSpan" },
        "evidence": { "type": "string" },
        "resolutionStatus": { "$ref": "#/definitions/ResolutionStatus" },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
      },
      "$comment": "At least one of targetId or targetMentionText MUST be provided (Semantic Validator)",
      "required": ["id", "relationType", "sourceId", "parentNodeId", "textSpan"],
      "additionalProperties": false
    },

    "RelationMentionType": {
      "type": "string",
      "enum": [
        "defines",
        "hasProperty",
        "appliesTo",
        "measures",
        "requires",
        "constrains",
        "equivalentTo"
      ]
    },

    "ResolutionStatus": {
      "type": "string",
      "enum": ["resolved", "unresolved", "partiallyResolved"]
    },

    "Reference": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/reference/[A-Za-z0-9_-]+$"
        },
        "sourceNodeId": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/[A-Za-z0-9._-]+$"
        },
        "referenceType": { "$ref": "#/definitions/ReferenceType" },
        "targetType": { "$ref": "#/definitions/ReferenceTargetType" },
        "rawTarget": { "type": "string" },
        "resolvedDocumentId": { "type": "string" },
        "resolvedVersion": { "type": "string" },
        "resolvedClause": { "type": "string" },
        "citedText": { "type": "string" },
        "textSpan": { "$ref": "#/definitions/TextSpan" },
        "resolutionStatus": { "$ref": "#/definitions/ResolutionStatus" },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
      },
      "required": ["id", "sourceNodeId", "referenceType", "targetType", "rawTarget", "textSpan"],
      "additionalProperties": false
    },

    "ReferenceType": {
      "type": "string",
      "enum": ["normative", "informative", "mandatory", "conditional"]
    },

    "ReferenceTargetType": {
      "type": "string",
      "enum": [
        "internalClause",
        "internalAnnex",
        "internalTable",
        "internalFigure",
        "externalStandard",
        "externalRegulation",
        "externalDocument",
        "externalTechnicalSpecification"
      ]
    },

    "DocumentRelationship": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/docrel/[A-Za-z0-9_-]+$"
        },
        "sourceDocumentId": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+$"
        },
        "relationType": { "$ref": "#/definitions/DocumentRelationshipType" },
        "targetDocumentId": { "type": "string" },
        "targetVersion": { "type": "string" },
        "validity": { "type": "string" },
        "sourceAnchor": { "$ref": "#/definitions/SourceAnchor" },
        "evidence": { "type": "string" },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
      },
      "required": ["id", "sourceDocumentId", "relationType", "targetDocumentId"],
      "additionalProperties": false
    },

    "DocumentRelationshipType": {
      "type": "string",
      "enum": [
        "replaces",
        "replacedBy",
        "amends",
        "amendedBy",
        "supplements",
        "supplementedBy",
        "equivalentTo",
        "adopts",
        "adoptedBy",
        "references",
        "referencedBy"
      ]
    },

    "ProcessingRun": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:processing/run/[0-9]{8}-[0-9]+$"
        },
        "sourceFileId": {
          "type": "string",
          "pattern": "^src:[A-Fa-f0-9]{16,}$"
        },
        "runType": { "$ref": "#/definitions/RunType" },
        "tool": { "type": "string" },
        "toolVersion": { "type": "string" },
        "ocrUsed": { "type": "boolean" },
        "ocrEngine": { "type": "string" },
        "model": { "type": "string" },
        "modelVersion": { "type": "string" },
        "timestamp": { "type": "string", "format": "date-time" },
        "configuration": { "type": "object" },
        "durationSeconds": { "type": "number", "minimum": 0 },
        "outputSummary": { "type": "object" }
      },
      "required": ["id", "sourceFileId", "runType", "tool", "toolVersion", "timestamp"],
      "additionalProperties": false
    },

    "RunType": {
      "type": "string",
      "enum": [
        "extraction",
        "classification",
        "entityRecognition",
        "relationExtraction",
        "referenceResolution",
        "humanReview",
        "other"
      ]
    },

    "QualityAssessment": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+/qa/[A-Za-z0-9_-]+$"
        },
        "documentId": {
          "type": "string",
          "pattern": "^ssir:[A-Za-z0-9._:/-]+$"
        },
        "runId": {
          "type": "string",
          "pattern": "^ssir:processing/run/[0-9]{8}-[0-9]+$"
        },
        "renderingProfile": { "$ref": "#/definitions/NormativeRenderingProfile" },
        "overallStatus": { "$ref": "#/definitions/OverallStatus" },
        "structureConfidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "tableConfidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "figureConfidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "formulaConfidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "ocrConfidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "entityConfidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "relationConfidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "referenceConfidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "missingPages": {
          "type": "array",
          "items": { "type": "integer", "minimum": 0 }
        },
        "unresolvedTables": {
          "type": "array",
          "items": { "type": "string" }
        },
        "unresolvedFigures": {
          "type": "array",
          "items": { "type": "string" }
        },
        "unresolvedFormulas": {
          "type": "array",
          "items": { "type": "string" }
        },
        "unresolvedReferences": {
          "type": "array",
          "items": { "type": "string" }
        },
        "humanReviewStatus": { "$ref": "#/definitions/HumanReviewStatus" },
        "comments": { "type": "string" },
        "assessedAt": { "type": "string", "format": "date-time" }
      },
      "required": ["id", "documentId", "overallStatus", "assessedAt"],
      "additionalProperties": false
    },

    "OverallStatus": {
      "type": "string",
      "enum": ["complete", "partial", "extractionFailed", "requiresReview", "approved", "rejected"]
    },

    "HumanReviewStatus": {
      "type": "string",
      "enum": ["unreviewed", "machineReviewed", "humanReviewed", "approved", "rejected"]
    },

    "PreservationLevel": {
      "type": "string",
      "enum": ["Level0", "Level1", "Level2", "Level3", "Level4"]
    },

    "PreservationStatus": {
      "type": "string",
      "enum": ["preserved", "partiallyPreserved", "notPreserved"]
    }
  }
}
```


## 6. Validation Layers（重要）

本 Schema 仅覆盖 **JSON Schema Validation** 层。完整的 SSIR 验证需要三个层次，与 Data Model v0.4 的四个验证概念对齐：

| 验证概念（Data Model v0.4） | 对应层级 | 验证内容 | 实施方式 |
|----|------|----------|----------|
| **Source Fidelity** | Layer 1 + 2 | 类型、必填、枚举、ID 引用、parent 关系、边界约束 | 本 Schema + Semantic Validator |
| **Rendering Conformance** | 独立验证 | `渲染文档` 是否符合 Rendering Profile（如 GB/T 1.1-2020） | 独立 Rendering Validator |
| **Round-trip Completeness** | Layer 2 | SSIR 是否保存了重建所需的信息 | Semantic Validator |
| **Round-trip Equivalence** | Layer 3 | `SSIR → 渲染 → 重新提取 → Verify`，验证 `SSIR ≈ Verify` | 独立 Round-trip Validator |

**Layer 1 无法表达的约束**（须由 Layer 2 保证）：
- `TextSpan.startChar < TextSpan.endChar`
- `SourceAnchor` 条件约束（如 `anchorType=bbox` 时 `pdfPageIndex` 和 `bbox` 必须存在）
- `RelationMention` 至少提供 `targetId` 或 `targetMentionText` 之一
- ID 引用的对象实际存在（如 `tableRef` 指向的 Table 确实在 `tables` 数组中）
- 结构树的完整性和一致性
- 表格行列数与实际 rows/cells 匹配

## 7. 使用说明

### 7.1 根文档
所有 SSIR 文档的根必须是一个 JSON 对象，符合 `SSIRDocument` 定义。

### 7.2 对象注册表引用闭环

`ContentElement` 中的 `tableRef`、`figureRef`、`formulaRef`、`unknownRef` 必须指向 `SSIRDocument` 中对应的注册表数组：

| 引用字段 | 目标注册表 |
|----------|-----------|
| `tableRef` | `SSIRDocument.tables[]` |
| `figureRef` | `SSIRDocument.figures[]` |
| `formulaRef` | `SSIRDocument.formulas[]` |
| `unknownRef` | `SSIRDocument.unknownContents[]` |

### 7.3 bbox 坐标系统

`bbox` 数组格式：`[x1, y1, x2, y2]`
- 坐标系：PDF Point
- 单位：points（1/72 英寸）
- 原点：页面左上角
- x1 为左边界，x2 为右边界
- y1 为上边界，y2 为下边界

### 7.4 条件必填

- `metadata.standard` 在 `documentType=standard` 时必须提供
- `StructuralNode` 非根节点（`nodeType != document`）时 `sourceAnchors` 必须至少 1 个
- `tableRef` 在 `presentationType=table` 时必须提供
- `figureRef` 在 `presentationType=figure` 时必须提供
- `formulaRef` 在 `presentationType=formula` 时必须提供
- `unknownRef` 在 `presentationType=other` 时必须提供

### 7.5 示例

#### 示例 A — 最小结构

```json
{
  "$schema": "https://leleby.io/schemas/ssir/v0.3.schema.json",
  "id": "ssir:GBT-99999-2026",
  "ssirVersion": "0.4",
  "documentType": "standard",
  "metadata": {
    "common": {
      "documentIdentifier": "GB/T 99999-2026",
      "title": "示例标准"
    },
    "standard": {
      "standardNumber": "GB/T 99999-2026"
    }
  },
  "sourceFiles": [
    {
      "id": "src:0123456789abcdef",
      "fileName": "example.pdf",
      "fileHash": {
        "algorithm": "SHA-256",
        "value": "abc123..."
      },
      "mimeType": "application/pdf"
    }
  ],
  "canonicalText": {
    "id": "ssir:GBT-99999-2026/canonical",
    "text": "1 范围\n本标准规定...",
    "normalizationPolicy": "ssir-canonical-text-v1"
  },
  "structuralRoot": {
    "id": "ssir:GBT-99999-2026/document",
    "logicalId": "document",
    "nodeType": "document",
    "sourceAnchors": [],
    "sortOrder": 0,
    "children": [
      {
        "id": "ssir:GBT-99999-2026/section-1",
        "logicalId": "section-1",
        "nodeType": "section",
        "number": "1",
        "title": "范围",
        "sourceAnchors": [
          {
            "id": "ssir:GBT-99999-2026/anchor/a-001",
            "sourceFileId": "src:0123456789abcdef",
            "anchorType": "page",
            "pdfPageIndex": 1
          }
        ],
        "sortOrder": 0,
        "contentElements": [
          {
            "id": "ssir:GBT-99999-2026/content/c-001",
            "presentationType": "paragraph",
            "parentNodeId": "ssir:GBT-99999-2026/section-1",
            "sortOrder": 0,
            "sourceAnchors": [
              {
                "id": "ssir:GBT-99999-2026/anchor/a-002",
                "sourceFileId": "src:0123456789abcdef",
                "anchorType": "bbox",
                "pdfPageIndex": 1,
                "bbox": [72, 120, 540, 160]
              }
            ],
            "textContent": "本标准规定示例标准的范围..."
          }
        ]
      }
    ]
  },
  "tables": [],
  "figures": [],
  "formulas": [],
  "unknownContents": [],
  "processingRuns": [
    {
      "id": "ssir:processing/run/20260815-001",
      "sourceFileId": "src:0123456789abcdef",
      "runType": "extraction",
      "tool": "MinerU",
      "toolVersion": "2.0.0",
      "timestamp": "2026-08-15T10:30:00Z"
    }
  ],
  "createdAt": "2026-08-15T10:30:00Z"
}
```

#### 示例 B — 复杂标准（含表格、图、公式、引用）

```json
{
  "id": "ssir:GBT-88888-2026",
  "ssirVersion": "0.4",
  "documentType": "standard",
  "metadata": {
    "common": {
      "documentIdentifier": "GB/T 88888-2026",
      "title": "复杂标准示例"
    },
    "standard": {
      "standardNumber": "GB/T 88888-2026"
    }
  },
  "sourceFiles": [],
  "canonicalText": {
    "id": "ssir:GBT-88888-2026/canonical",
    "text": "5.2 电气性能\n表1 电气性能要求\n5.3 试验方法\n图1 试验流程图\n(1) P=UI",
    "normalizationPolicy": "ssir-canonical-text-v1"
  },
  "structuralRoot": {
    "id": "ssir:GBT-88888-2026/document",
    "logicalId": "document",
    "nodeType": "document",
    "sourceAnchors": [],
    "sortOrder": 0,
    "children": [
      {
        "id": "ssir:GBT-88888-2026/clause-5.2",
        "logicalId": "clause-5.2",
        "nodeType": "clause",
        "number": "5.2",
        "title": "电气性能要求",
        "sourceAnchors": [],
        "sortOrder": 0,
        "contentElements": [
          {
            "id": "ssir:GBT-88888-2026/content/c-001",
            "presentationType": "paragraph",
            "parentNodeId": "ssir:GBT-88888-2026/clause-5.2",
            "sortOrder": 0,
            "sourceAnchors": [],
            "textContent": "电动机额定效率应不低于90%。"
          },
          {
            "id": "ssir:GBT-88888-2026/content/c-002",
            "presentationType": "table",
            "parentNodeId": "ssir:GBT-88888-2026/clause-5.2",
            "sortOrder": 1,
            "sourceAnchors": [],
            "tableRef": "ssir:GBT-88888-2026/table/t-001"
          }
        ]
      },
      {
        "id": "ssir:GBT-88888-2026/clause-5.3",
        "logicalId": "clause-5.3",
        "nodeType": "clause",
        "number": "5.3",
        "title": "试验方法",
        "sourceAnchors": [],
        "sortOrder": 1,
        "contentElements": [
          {
            "id": "ssir:GBT-88888-2026/content/c-003",
            "presentationType": "paragraph",
            "parentNodeId": "ssir:GBT-88888-2026/clause-5.3",
            "sortOrder": 0,
            "sourceAnchors": [],
            "textContent": "试验应按GB/T 99999-2026执行。"
          },
          {
            "id": "ssir:GBT-88888-2026/content/c-004",
            "presentationType": "figure",
            "parentNodeId": "ssir:GBT-88888-2026/clause-5.3",
            "sortOrder": 1,
            "sourceAnchors": [],
            "figureRef": "ssir:GBT-88888-2026/figure/f-001"
          },
          {
            "id": "ssir:GBT-88888-2026/content/c-005",
            "presentationType": "formula",
            "parentNodeId": "ssir:GBT-88888-2026/clause-5.3",
            "sortOrder": 2,
            "sourceAnchors": [],
            "formulaRef": "ssir:GBT-88888-2026/formula/fm-001"
          }
        ]
      }
    ]
  },
  "tables": [
    {
      "id": "ssir:GBT-88888-2026/table/t-001",
      "number": "表1",
      "caption": "电气性能要求",
      "rowCount": 3,
      "colCount": 2,
      "rows": [
        {
          "id": "row-001",
          "rowIndex": 0,
          "cells": [
            {
              "id": "cell-001",
              "rowIndex": 0,
              "colIndex": 0,
              "text": "项目",
              "isHeader": true
            },
            {
              "id": "cell-002",
              "rowIndex": 0,
              "colIndex": 1,
              "text": "要求",
              "isHeader": true
            }
          ]
        },
        {
          "id": "row-002",
          "rowIndex": 1,
          "cells": [
            {
              "id": "cell-003",
              "rowIndex": 1,
              "colIndex": 0,
              "text": "额定效率"
            },
            {
              "id": "cell-004",
              "rowIndex": 1,
              "colIndex": 1,
              "text": "≥ 90%"
            }
          ]
        }
      ],
      "sourceAnchors": []
    }
  ],
  "figures": [
    {
      "id": "ssir:GBT-88888-2026/figure/f-001",
      "number": "图1",
      "caption": "试验流程图",
      "assetRef": "object://documents/ssir:GBT-88888-2026/figure-001.png",
      "sourceAnchors": []
    }
  ],
  "formulas": [
    {
      "id": "ssir:GBT-88888-2026/formula/fm-001",
      "number": "(1)",
      "rawText": "P = UI",
      "latex": "P = UI",
      "sourceAnchors": []
    }
  ],
  "references": [
    {
      "id": "ssir:GBT-88888-2026/reference/ref-001",
      "sourceNodeId": "ssir:GBT-88888-2026/clause-5.3",
      "referenceType": "normative",
      "targetType": "externalStandard",
      "rawTarget": "GB/T 99999-2026",
      "resolvedDocumentId": "ssir:GBT-99999-2026",
      "textSpan": {
        "id": "ssir:GBT-88888-2026/span/s-001",
        "canonicalTextId": "ssir:GBT-88888-2026/canonical",
        "startChar": 100,
        "endChar": 116,
        "text": "GB/T 99999-2026"
      }
    }
  ],
  "unknownContents": [],
  "processingRuns": [],
  "createdAt": "2026-08-15T10:30:00Z"
}
```

#### 示例 C — 扫描标准（含 OCR 溯源）

```json
{
  "id": "ssir:GBT-77777-2026",
  "ssirVersion": "0.4",
  "documentType": "standard",
  "metadata": {
    "common": {
      "documentIdentifier": "GB/T 77777-2026",
      "title": "扫描标准示例"
    },
    "standard": {
      "standardNumber": "GB/T 77777-2026"
    }
  },
  "sourceFiles": [
    {
      "id": "src:fedcba9876543210",
      "fileName": "scanned_standard.pdf",
      "fileHash": {
        "algorithm": "SHA-256",
        "value": "def456..."
      },
      "mimeType": "application/pdf",
      "pageCount": 10
    }
  ],
  "canonicalText": {
    "id": "ssir:GBT-77777-2026/canonical",
    "text": "3.1 术语\n额定电压\n3.2 ...",
    "normalizationPolicy": "ssir-canonical-text-v1"
  },
  "structuralRoot": {
    "id": "ssir:GBT-77777-2026/document",
    "logicalId": "document",
    "nodeType": "document",
    "sourceAnchors": [],
    "sortOrder": 0,
    "children": [
      {
        "id": "ssir:GBT-77777-2026/clause-3.1",
        "logicalId": "clause-3.1",
        "nodeType": "clause",
        "number": "3.1",
        "title": "术语",
        "sourceAnchors": [
          {
            "id": "ssir:GBT-77777-2026/anchor/a-001",
            "sourceFileId": "src:fedcba9876543210",
            "anchorType": "bbox",
            "pdfPageIndex": 3,
            "bbox": [72, 200, 540, 230],
            "textQuote": "3.1 术语"
          }
        ],
        "sortOrder": 0,
        "contentElements": [
          {
            "id": "ssir:GBT-77777-2026/content/c-001",
            "presentationType": "paragraph",
            "parentNodeId": "ssir:GBT-77777-2026/clause-3.1",
            "sortOrder": 0,
            "sourceAnchors": [
              {
                "id": "ssir:GBT-77777-2026/anchor/a-002",
                "sourceFileId": "src:fedcba9876543210",
                "anchorType": "bbox",
                "pdfPageIndex": 3,
                "bbox": [72, 240, 540, 260],
                "textQuote": "额定电压是指..."
              }
            ],
            "textContent": "额定电压是指..."
          }
        ]
      }
    ]
  },
  "tables": [],
  "figures": [],
  "formulas": [],
  "unknownContents": [],
  "processingRuns": [
    {
      "id": "ssir:processing/run/20260815-001",
      "sourceFileId": "src:fedcba9876543210",
      "runType": "extraction",
      "tool": "MinerU",
      "toolVersion": "2.0.0",
      "ocrUsed": true,
      "ocrEngine": "PaddleOCR",
      "timestamp": "2026-08-15T10:30:00Z"
    }
  ],
  "qualityAssessments": [
    {
      "id": "ssir:GBT-77777-2026/qa/qa-001",
      "documentId": "ssir:GBT-77777-2026",
      "runId": "ssir:processing/run/20260815-001",
      "renderingProfile": "GB_T_1.1-2020",
      "overallStatus": "partial",
      "ocrConfidence": 0.92,
      "structureConfidence": 0.85,
      "assessedAt": "2026-08-15T11:00:00Z"
    }
  ],
  "preservationLevel": "Level3",
  "createdAt": "2026-08-15T10:30:00Z"
}
```


## 8. Version History

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 0.1 | 2026-08-15 | 初始版本 |
| 0.2 | 2026-08-15 | 新增对象注册表（tables/figures/formulas/unknownContents）；修正 StandardMetadata 条件约束；修正 StructuralNode.sourceAnchors 根节点特例；完善 SourceAnchor 条件约束（$comment）；明确 bbox 坐标系统；增加 ID Pattern 约束；fileHash 增加 algorithm 字段；filePath → storageUri；CanonicalText.normalizationPolicy 标准化；新增完整非规范性示例；新增 Validation Layers 说明 |
| 0.3 | 2026-08-15 | 更新 Data Model 引用至 v0.4；`ssirVersion` 增加 `"0.4"`；新增 `NormativeRenderingProfile` 枚举；更新 Scope 和 Validation Layers 说明与 Data Model v0.4 对齐；QualityAssessment 增加 `renderingProfile` 字段；示例中 `ssirVersion` 更新为 `"0.4"` |
| 0.3-M1 | 2026-08-17 | 增加 `anchorType=markdown` 及 Markdown 行/列/AST 溯源字段，支持 CSM Markdown → SSIR |


## 9. Next Steps

本 Schema 已与 leleby SSIR Data Model v0.4 对齐，并反映了 Round-trip 语义增强的变更。建议下一步：

1. **Review & Freeze**: 本规范评审并冻结
2. **实现 Semantic Validator**: 根据第 6 节定义的 Layer 2 职责，实现独立的 Semantic Validator，验证 Data Model v0.4 §7.2 Source Fidelity 中定义的约束
3. **实现 Rendering Conformance Validator**: 验证 Data Model v0.4 §7.3 中定义的 Normative Rendering 规则是否被遵守
4. **更新 AI Coding Specification**: 将本 Schema 的变更同步到 AI Coding Implementation Specification
