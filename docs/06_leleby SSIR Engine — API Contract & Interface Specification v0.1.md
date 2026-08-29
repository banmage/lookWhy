# leleby SSIR Engine — API Contract & Interface Specification v0.1

> **文档状态**：正式发布 | **版本**：0.1 | **日期**：2026-08-15
>
> **前置依赖**：
> 1. leleby SSIR Data Model v0.4
> 2. leleby SSIR JSON Schema Specification v0.3
> 3. leleby SSIR Processing Pipeline & Architecture Specification v0.4
> 4. leleby SSIR Round-trip & Conformance Test Specification v0.3
> 5. leleby SSIR Engine — AI Coding Implementation Specification v0.4
>
> **目标读者**：AI Coding Agent / 开发团队 / API 使用者 / 前端团队

> **当前 M1 API 边界**：当前只提供 CSM Markdown 到 SSIR 的同步解析接口和 CLI 等价能力。`POST /documents` 的 PDF/DOCX 上传、MinerU 异步任务、渲染、Round-trip 和质量回溯接口保留为 M2 设计，不得作为 M1 必需实现。
>
> M1 推荐接口：`POST /v1/csm/parse`（上传一个 `.md`，返回 SSIR JSON 或校验错误）；可选 `format=ttl` 只能在 JSON Schema 校验成功后执行。完整请求/响应和错误码见 `docs/08_leleby CSM-to-SSIR Implementation Specification v0.1.md`。


## 1. Scope

本规范定义了 leleby SSIR Engine Phase 1 的：

1. **REST API Contract**：所有对外 HTTP API 端点的完整定义
2. **Internal Interface Contract**：核心模块间的 Python 接口定义（抽象类/协议）
3. **Async Task Interface**：Celery 异步任务接口定义
4. **Event/Webhook Specification**：系统事件和通知机制

本规范是 API 服务端和客户端的唯一契约，所有实现必须严格遵循。


## 2. REST API Overview

### 2.1 基础信息

| 属性 | 值 |
|------|---|
| **Base URL** | `http://api.leleby.io/ssir/v1` |
| **协议** | HTTPS（生产环境）/ HTTP（开发环境） |
| **认证** | Bearer Token / API Key（规划中，Phase 1 可简化） |
| **数据格式** | JSON |
| **字符编码** | UTF-8 |
| **时区** | UTC |

### 2.2 通用响应格式

#### 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": { ... },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

#### 错误响应

```json
{
  "code": 40001,
  "message": "Invalid document format",
  "details": "Only PDF and DOCX files are supported",
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

### 2.3 HTTP 状态码

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 200 | OK | 请求成功 |
| 202 | Accepted | 异步任务已接受 |
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未认证 |
| 403 | Forbidden | 无权限 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 资源冲突 |
| 422 | Unprocessable Entity | 验证失败 |
| 500 | Internal Server Error | 服务器内部错误 |
| 503 | Service Unavailable | 服务暂时不可用 |

### 2.4 错误码定义

| 错误码 | 名称 | 说明 |
|--------|------|------|
| 0 | SUCCESS | 成功 |
| 40001 | INVALID_FILE_FORMAT | 不支持的文件格式 |
| 40002 | INVALID_FILE_SIZE | 文件大小超限 |
| 40003 | INVALID_RENDERING_PROFILE | 不支持的渲染配置 |
| 40004 | INVALID_DOCUMENT_ID | 文档 ID 格式无效 |
| 40005 | INVALID_SSIR_SCHEMA | SSIR Schema 验证失败 |
| 40006 | MISSING_REQUIRED_FIELD | 缺少必填字段 |
| 40401 | DOCUMENT_NOT_FOUND | 文档不存在 |
| 40402 | SSIR_NOT_FOUND | SSIR 不存在 |
| 40403 | RENDERED_FILE_NOT_FOUND | 渲染文件不存在 |
| 40901 | DOCUMENT_ALREADY_PROCESSING | 文档正在处理中 |
| 40902 | DOCUMENT_ALREADY_EXISTS | 文档已存在 |
| 42201 | SSIR_VALIDATION_FAILED | SSIR 语义验证失败 |
| 42202 | ROUNDTRIP_FAILED | 往返测试失败 |
| 50001 | EXTRACTION_FAILED | 提取失败 |
| 50002 | RENDERING_FAILED | 渲染失败 |
| 50003 | STORAGE_FAILED | 存储失败 |
| 50301 | SERVICE_UNAVAILABLE | 服务不可用 |


## 3. REST API Endpoints

### 3.1 文档管理

#### 3.1.1 上传文档

```
POST /documents
```

**请求体**（multipart/form-data）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | file | ✅ | PDF 或 DOCX 文件 |
| `metadata` | object | ❌ | 用户提供的元数据覆盖 |
| `renderingProfile` | string | ❌ | 渲染配置，默认 `GB_T_1.1-2020` |
| `autoProcess` | boolean | ❌ | 是否自动启动提取，默认 `true` |

**`renderingProfile` 枚举**：
- `GB_T_1.1-2020`
- `iso-iec-directives-part-2`
- `custom`

**响应**（202 Accepted）：

```json
{
  "code": 0,
  "message": "Document uploaded successfully",
  "data": {
    "documentId": "ssir:GBT-42093.1-2022",
    "sourceFileId": "src:a1b2c3d4e5f67890",
    "status": "PROCESSING",
    "renderingProfile": "GB_T_1.1-2020",
    "createdAt": "2026-08-15T10:30:00Z"
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

**错误响应**：

```json
{
  "code": 40001,
  "message": "Invalid file format",
  "details": "Only PDF and DOCX files are supported. Received: image/png",
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

#### 3.1.2 获取文档列表

```
GET /documents
```

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `limit` | integer | ❌ | 每页数量，默认 20，最大 100 |
| `offset` | integer | ❌ | 偏移量，默认 0 |
| `status` | string | ❌ | 筛选状态 |
| `documentType` | string | ❌ | 筛选文档类型 |
| `fromDate` | string | ❌ | 起始日期（ISO 8601） |
| `toDate` | string | ❌ | 结束日期（ISO 8601） |
| `search` | string | ❌ | 全文搜索关键词 |

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "documentId": "ssir:GBT-42093.1-2022",
        "documentType": "standard",
        "title": "标准文档结构化 元模型 第1部分：全文",
        "standardNumber": "GB/T 42093.1-2022",
        "status": "COMPLETED",
        "preservationLevel": "Level3",
        "createdAt": "2026-08-15T10:30:00Z",
        "updatedAt": "2026-08-15T11:00:00Z"
      }
    ],
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 42
    }
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

#### 3.1.3 获取文档详情

```
GET /documents/{documentId}
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "documentId": "ssir:GBT-42093.1-2022",
    "documentType": "standard",
    "metadata": {
      "common": {
        "documentIdentifier": "GB/T 42093.1-2022",
        "title": "标准文档结构化 元模型 第1部分：全文"
      },
      "standard": {
        "standardNumber": "GB/T 42093.1-2022",
        "publishingBody": "国家市场监督管理总局",
        "ccs": "L67",
        "ics": "35.240.30"
      }
    },
    "sourceFiles": [
      {
        "id": "src:a1b2c3d4e5f67890",
        "fileName": "GB_T_42093.1-2022.pdf",
        "mimeType": "application/pdf",
        "pageCount": 30
      }
    ],
    "status": "COMPLETED",
    "preservationLevel": "Level3",
    "createdAt": "2026-08-15T10:30:00Z",
    "updatedAt": "2026-08-15T11:00:00Z",
    "qualityAssessment": {
      "id": "ssir:GBT-42093.1-2022/qa/qa-001",
      "overallStatus": "complete",
      "renderingProfile": "GB_T_1.1-2020",
      "structureConfidence": 0.99,
      "contentConfidence": 0.98,
      "assessedAt": "2026-08-15T11:00:00Z"
    }
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

#### 3.1.4 删除文档

```
DELETE /documents/{documentId}
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `force` | boolean | ❌ | 强制删除（忽略状态），默认 `false` |

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "Document deleted successfully",
  "data": {
    "documentId": "ssir:GBT-42093.1-2022",
    "deleted": true
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```


### 3.2 文档处理

#### 3.2.1 启动 SSIR 提取

```
POST /documents/{documentId}/process
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**请求体**：

```json
{
  "forceReprocess": false,
  "options": {
    "enableEntityExtraction": false,
    "enableRelationExtraction": false,
    "enableReferenceExtraction": false
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `forceReprocess` | boolean | ❌ | 是否强制重新处理，默认 `false` |
| `options.enableEntityExtraction` | boolean | ❌ | 是否启用实体提取（L4），默认 `false` |
| `options.enableRelationExtraction` | boolean | ❌ | 是否启用关系提取（L4），默认 `false` |
| `options.enableReferenceExtraction` | boolean | ❌ | 是否启用引用提取（L4），默认 `false` |

**响应**（202 Accepted）：

```json
{
  "code": 0,
  "message": "Processing started",
  "data": {
    "documentId": "ssir:GBT-42093.1-2022",
    "processingRunId": "ssir:processing/run/20260815-001",
    "status": "PROCESSING",
    "estimatedDuration": 120
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

#### 3.2.2 获取处理状态

```
GET /documents/{documentId}/status
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "documentId": "ssir:GBT-42093.1-2022",
    "status": "PROCESSING",
    "progress": 45,
    "currentStage": "Content Building",
    "processingRunId": "ssir:processing/run/20260815-001",
    "stages": [
      { "name": "Ingestion", "status": "COMPLETED", "duration": 2.5 },
      { "name": "Extraction", "status": "COMPLETED", "duration": 45.0 },
      { "name": "Structure", "status": "COMPLETED", "duration": 5.2 },
      { "name": "Content", "status": "IN_PROGRESS", "duration": 12.3 },
      { "name": "Provenance", "status": "PENDING", "duration": null },
      { "name": "Validation", "status": "PENDING", "duration": null }
    ],
    "estimatedRemaining": 65
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

#### 3.2.3 取消处理

```
POST /documents/{documentId}/cancel
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "Processing cancelled",
  "data": {
    "documentId": "ssir:GBT-42093.1-2022",
    "cancelled": true,
    "status": "CANCELLED"
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```


### 3.3 SSIR 访问

#### 3.3.1 获取 SSIR

```
GET /documents/{documentId}/ssir
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | integer | ❌ | SSIR 版本号，默认最新 |
| `format` | string | ❌ | 输出格式：`json`（默认）、`yaml` |
| `minify` | boolean | ❌ | 是否压缩 JSON，默认 `false` |

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    // 完整 SSIRDocument 对象 (v0.4)
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

#### 3.3.2 获取 SSIR 结构树

```
GET /documents/{documentId}/structure
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `depth` | integer | ❌ | 展开深度，默认全部 |
| `includeContent` | boolean | ❌ | 是否包含内容元素，默认 `false` |

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "documentId": "ssir:GBT-42093.1-2022",
    "structure": {
      "id": "ssir:GBT-42093.1-2022/document",
      "nodeType": "document",
      "children": [
        {
          "id": "ssir:GBT-42093.1-2022/block-foreword",
          "nodeType": "documentBlock",
          "logicalId": "block-foreword",
          "number": null,
          "title": "前言",
          "children": [
            {
              "id": "ssir:GBT-42093.1-2022/para-001",
              "nodeType": "paragraph",
              "contentElementCount": 1
            }
          ]
        },
        {
          "id": "ssir:GBT-42093.1-2022/section-1",
          "nodeType": "section",
          "logicalId": "section-1",
          "number": "1",
          "title": "范围",
          "children": []
        }
      ]
    }
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

#### 3.3.3 获取 SSIR 内容

```
GET /documents/{documentId}/content
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `nodeId` | string | ❌ | 指定节点 ID，默认全部 |
| `presentationType` | string | ❌ | 筛选内容类型 |
| `semanticType` | string | ❌ | 筛选语义类型 |
| `includeSourceAnchor` | boolean | ❌ | 是否包含溯源信息，默认 `false` |

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "documentId": "ssir:GBT-42093.1-2022",
    "totalElements": 1520,
    "items": [
      {
        "id": "ssir:GBT-42093.1-2022/content/c-001",
        "parentNodeId": "ssir:GBT-42093.1-2022/section-1",
        "presentationType": "paragraph",
        "semanticTypes": ["scope"],
        "textContent": "本文件从三个维度描述标准文档结构化的全文元模型...",
        "sortOrder": 0
      }
    ]
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```


### 3.4 渲染服务

#### 3.4.1 渲染传统文档

```
POST /documents/{documentId}/render
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `format` | string | ❌ | 输出格式：`docx`（默认）、`pdf`、`html` |
| `profile` | string | ❌ | 渲染配置，默认 `GB_T_1.1-2020` |

**请求体**：

```json
{
  "profile": "GB_T_1.1-2020",
  "options": {
    "includeCover": true,
    "includeTOC": true,
    "pageSize": "A4",
    "language": "zh-CN"
  }
}
```

**响应**（200 OK）：

```
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="GBT-42093.1-2022_rendered.docx"

[文件二进制数据]
```

#### 3.4.2 获取渲染状态

```
GET /documents/{documentId}/render/status
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `format` | string | ❌ | 渲染格式：`docx`、`pdf`、`html` |

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "documentId": "ssir:GBT-42093.1-2022",
    "format": "docx",
    "status": "COMPLETED",
    "fileSize": 245760,
    "fileUri": "object://rendered/ssir:GBT-42093.1-2022/document.docx",
    "createdAt": "2026-08-15T11:30:00Z"
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```


### 3.5 往返测试

#### 3.5.1 执行往返测试

```
POST /documents/{documentId}/roundtrip
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `profile` | string | ❌ | 渲染配置，默认 `GB_T_1.1-2020` |
| `includeFidelity` | boolean | ❌ | 是否包含 Rendering Fidelity 测试，默认 `true` |
| `includeCriticalLoss` | boolean | ❌ | 是否包含 Critical Loss 检查，默认 `true` |

**请求体**：

```json
{
  "profile": "GB_T_1.1-2020",
  "options": {
    "includeFidelity": true,
    "includeCriticalLoss": true,
    "maxCycles": 3
  }
}
```

**响应**（202 Accepted）：

```json
{
  "code": 0,
  "message": "Round-trip test started",
  "data": {
    "documentId": "ssir:GBT-42093.1-2022",
    "roundtripRunId": "ssir:roundtrip/run/20260815-001",
    "status": "PROCESSING"
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

#### 3.5.2 获取往返测试结果

```
GET /documents/{documentId}/roundtrip/result
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `runId` | string | ❌ | 指定运行 ID，默认最新 |

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "reportId": "rt-20260815-001",
    "timestamp": "2026-08-15T10:30:00Z",
    "documentId": "ssir:GBT-42093.1-2022",
    "renderingProfile": "GB_T_1.1-2020",
    "summary": {
      "overallStatus": "PASS",
      "criticalLoss": false,
      "criticalCount": 0,
      "cycleCount": 1
    },
    "equivalence": {
      "identity": {
        "status": "PASS",
        "details": {}
      },
      "structure": {
        "status": "PASS",
        "details": {
          "nodes": 45,
          "matched": 45
        }
      },
      "content": {
        "status": "PASS",
        "details": {
          "elements": 1432,
          "matched": 1430,
          "matchRate": 0.9986
        }
      },
      "semantics": {
        "status": "PASS",
        "details": {}
      }
    },
    "criticalCheck": {
      "status": "PASS",
      "violations": [],
      "checks": {
        "normative_wording": "PASS",
        "prohibition": "PASS",
        "numeric_value": "PASS",
        "unit": "PASS",
        "comparison_operator": "PASS",
        "clause_identifier": "PASS",
        "table_cell": "PASS",
        "formula_raw": "PASS",
        "reference_raw": "PASS",
        "scope": "PASS",
        "applicability": "PASS",
        "mandatory_condition": "PASS"
      }
    },
    "renderingFidelity": {
      "status": "PASS",
      "matched": 98,
      "total": 100
    },
    "overallStatus": "PASS",
    "recommendations": []
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```


### 3.6 质量与监控

#### 3.6.1 获取质量报告

```
GET /documents/{documentId}/quality
```

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `documentId` | string | ✅ | SSIR 文档 ID |

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | integer | ❌ | SSIR 版本号，默认最新 |

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "qualityAssessment": {
      "id": "ssir:GBT-42093.1-2022/qa/qa-001",
      "documentId": "ssir:GBT-42093.1-2022",
      "runId": "ssir:processing/run/20260815-001",
      "renderingProfile": "GB_T_1.1-2020",
      "overallStatus": "complete",
      "dimensions": {
        "textExtraction": {
          "status": "PASS",
          "confidence": 0.95
        },
        "structureRecognition": {
          "status": "PASS",
          "confidence": 0.98
        },
        "tableExtraction": {
          "status": "PASS",
          "confidence": 0.92
        },
        "figurePreservation": {
          "status": "PASS",
          "confidence": 1.0
        },
        "formulaPreservation": {
          "status": "PASS",
          "confidence": 1.0
        },
        "provenanceCoverage": {
          "status": "PASS",
          "coverage": 0.99
        },
        "renderingProfileValidation": {
          "status": "PASS",
          "profile": "GB_T_1.1-2020"
        }
      },
      "assessedAt": "2026-08-15T11:00:00Z"
    }
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

#### 3.6.2 健康检查

```
GET /health
```

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "healthy",
  "data": {
    "status": "healthy",
    "version": "0.1.0",
    "services": {
      "database": "healthy",
      "storage": "healthy",
      "redis": "healthy",
      "celery": "healthy"
    },
    "timestamp": "2026-08-15T10:30:00Z"
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```

#### 3.6.3 就绪检查

```
GET /ready
```

**响应**（200 OK）：

```json
{
  "code": 0,
  "message": "ready",
  "data": {
    "status": "ready",
    "timestamp": "2026-08-15T10:30:00Z"
  },
  "timestamp": "2026-08-15T10:30:00Z",
  "requestId": "req_abc123"
}
```


## 4. Internal Interface Contract

### 4.1 Core Module Interfaces

#### 4.1.1 Ingestion Service

```python
# packages/ingestion/interface.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from packages.core.ssir import SourceFile, ProcessingRun
from packages.ingestion.profiles import DocumentSourceProfile


class IngestionService(ABC):
    """文档接入服务接口"""

    @abstractmethod
    def detect(self, file_path: Path) -> DocumentSourceProfile:
        """检测文件类型和质量"""
        pass

    @abstractmethod
    def create_source_file(self, file_path: Path, metadata: Optional[dict] = None) -> SourceFile:
        """创建 SourceFile 对象"""
        pass

    @abstractmethod
    def create_processing_run(self, source_file_id: str) -> ProcessingRun:
        """创建 ProcessingRun 对象"""
        pass

    @abstractmethod
    def store_file(self, source_file: SourceFile, file_path: Path) -> str:
        """存储源文件到对象存储，返回 storageUri"""
        pass
```

#### 4.1.2 Extraction Service

```python
# packages/extraction/interface.py
from abc import ABC, abstractmethod
from pathlib import Path
from packages.core.extraction_ir import ExtractionIR
from packages.core.ssir import SourceFile, ProcessingRun


class ExtractionAdapter(ABC):
    """解析器适配器接口"""

    @abstractmethod
    def extract(self, source_file: SourceFile, file_path: Path) -> ExtractionIR:
        """提取文档内容，返回 Extraction IR"""
        pass

    @abstractmethod
    def supports(self, mime_type: str) -> bool:
        """判断是否支持该 MIME 类型"""
        pass


class OCRPipeline(ABC):
    """OCR 管道接口"""

    @abstractmethod
    def process(self, file_path: Path, pages: Optional[list] = None) -> ExtractionIR:
        """对扫描 PDF 执行 OCR"""
        pass

    @abstractmethod
    def get_confidence(self) -> float:
        """获取 OCR 置信度"""
        pass
```

#### 4.1.3 SSIR Builder

```python
# packages/ssir_builder/interface.py
from abc import ABC, abstractmethod
from packages.core.extraction_ir import ExtractionIR
from packages.core.ssir import SSIRDocument, SourceFile, ProcessingRun


class SSIRBuilder(ABC):
    """SSIR 构建器接口"""

    @abstractmethod
    def build(
        self,
        extraction_ir: ExtractionIR,
        source_file: SourceFile,
        processing_run: ProcessingRun
    ) -> SSIRDocument:
        """从 Extraction IR 构建 SSIR 文档"""
        pass

    @abstractmethod
    def build_canonical_text(self, extraction_ir: ExtractionIR) -> "CanonicalText":
        """构建权威文本"""
        pass

    @abstractmethod
    def build_structure(self, extraction_ir: ExtractionIR) -> "StructuralNode":
        """构建结构树"""
        pass

    @abstractmethod
    def build_content(self, extraction_ir: ExtractionIR) -> list:
        """构建内容元素"""
        pass

    @abstractmethod
    def build_provenance(self, ssir: SSIRDocument) -> None:
        """建立溯源信息"""
        pass
```

#### 4.1.4 Validation Service

```python
# packages/validator/interface.py
from abc import ABC, abstractmethod
from packages.core.ssir import SSIRDocument, QualityAssessment
from packages.validator.types import ValidationReport


class ValidationService(ABC):
    """验证服务接口"""

    @abstractmethod
    def validate_schema(self, ssir: SSIRDocument) -> ValidationReport:
        """Schema 验证"""
        pass

    @abstractmethod
    def validate_structural(self, ssir: SSIRDocument) -> ValidationReport:
        """结构验证"""
        pass

    @abstractmethod
    def validate_content(self, ssir: SSIRDocument) -> ValidationReport:
        """内容验证"""
        pass

    @abstractmethod
    def validate_provenance(self, ssir: SSIRDocument) -> ValidationReport:
        """溯源验证"""
        pass

    @abstractmethod
    def assess_quality(self, ssir: SSIRDocument) -> QualityAssessment:
        """生成质量评估"""
        pass
```

#### 4.1.5 Normative Rendering Service

```python
# packages/rendering/interface.py
from abc import ABC, abstractmethod
from packages.core.ssir import SSIRDocument
from packages.core.rendering_ir import RenderingIR
from packages.rendering.profile import NormativeRenderingProfile


class RenderingService(ABC):
    """规范性渲染服务接口"""

    @abstractmethod
    def render(
        self,
        ssir: SSIRDocument,
        profile: NormativeRenderingProfile,
        options: Optional[dict] = None
    ) -> RenderingIR:
        """从 SSIR 生成 Rendering IR"""
        pass

    @abstractmethod
    def to_docx(self, rendering_ir: RenderingIR) -> bytes:
        """Rendering IR → DOCX"""
        pass

    @abstractmethod
    def to_pdf(self, rendering_ir: RenderingIR) -> bytes:
        """Rendering IR → PDF"""
        pass

    @abstractmethod
    def to_html(self, rendering_ir: RenderingIR) -> str:
        """Rendering IR → HTML"""
        pass
```

#### 4.1.6 Round-trip Verification Service

```python
# packages/roundtrip/interface.py
from abc import ABC, abstractmethod
from pathlib import Path
from packages.core.ssir import SSIRDocument
from packages.core.equivalence import SSIREquivalenceResult
from packages.core.roundtrip import RoundTripReport
from packages.roundtrip.critical_check import CriticalLossResult
from packages.rendering.profile import NormativeRenderingProfile


class RoundtripVerifier(ABC):
    """往返测试验证器接口"""

    @abstractmethod
    def verify(
        self,
        canonical: Path,
        profile: NormativeRenderingProfile
    ) -> RoundTripReport:
        """执行完整的往返测试"""
        pass

    @abstractmethod
    def compare_ssir(self, ssir: SSIRDocument, verify: SSIRDocument) -> SSIREquivalenceResult:
        """四层比较两个 SSIR"""
        pass

    @abstractmethod
    def check_critical_loss(self, ssir: SSIRDocument, verify: SSIRDocument) -> CriticalLossResult:
        """执行 12 项 Critical Loss 检查"""
        pass

    @abstractmethod
    def test_rendering_fidelity(
        self,
        ssir: SSIRDocument,
        profile: NormativeRenderingProfile
    ) -> dict:
        """独立的 Rendering Fidelity 测试"""
        pass
```

#### 4.1.7 Repository

```python
# packages/storage/interface.py
from abc import ABC, abstractmethod
from typing import Optional, List
from packages.core.ssir import SSIRDocument, SourceFile, ProcessingRun, QualityAssessment


class Repository(ABC):
    """数据仓库接口"""

    # Document operations
    @abstractmethod
    def save_document(self, document: SSIRDocument) -> str:
        """保存 SSIR 文档"""
        pass

    @abstractmethod
    def get_document(self, document_id: str, version: Optional[int] = None) -> Optional[SSIRDocument]:
        """获取 SSIR 文档"""
        pass

    @abstractmethod
    def list_documents(self, limit: int = 20, offset: int = 0, **filters) -> List[SSIRDocument]:
        """列出 SSIR 文档"""
        pass

    @abstractmethod
    def delete_document(self, document_id: str, force: bool = False) -> bool:
        """删除 SSIR 文档"""
        pass

    # SourceFile operations
    @abstractmethod
    def save_source_file(self, source_file: SourceFile) -> str:
        pass

    @abstractmethod
    def get_source_file(self, source_file_id: str) -> Optional[SourceFile]:
        pass

    # ProcessingRun operations
    @abstractmethod
    def save_processing_run(self, run: ProcessingRun) -> str:
        pass

    # QualityAssessment operations
    @abstractmethod
    def save_quality_assessment(self, qa: QualityAssessment) -> str:
        pass

    @abstractmethod
    def get_quality_assessment(self, document_id: str) -> Optional[QualityAssessment]:
        pass


class ObjectStorage(ABC):
    """对象存储接口"""

    @abstractmethod
    def upload(self, key: str, data: bytes, content_type: str) -> str:
        """上传文件，返回 URI"""
        pass

    @abstractmethod
    def download(self, key: str) -> bytes:
        """下载文件"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除文件"""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查文件是否存在"""
        pass
```


## 5. Async Task Interface

### 5.1 Celery Task 定义

```python
# apps/worker/tasks/__init__.py
from celery import shared_task


@shared_task(bind=True, name="extraction.process")
def process_extraction(self, document_id: str, options: dict) -> dict:
    """
    异步提取任务

    Args:
        document_id: SSIR 文档 ID
        options: 处理选项

    Returns:
        dict: 处理结果，包含 SSIR ID 和状态
    """
    pass


@shared_task(bind=True, name="rendering.render")
def render_document(self, document_id: str, profile: str, format: str, options: dict) -> dict:
    """
    异步渲染任务

    Args:
        document_id: SSIR 文档 ID
        profile: 渲染配置名称
        format: 输出格式 (docx, pdf, html)
        options: 渲染选项

    Returns:
        dict: 渲染结果，包含文件 URI 和状态
    """
    pass


@shared_task(bind=True, name="roundtrip.verify")
def verify_roundtrip(self, document_id: str, profile: str, options: dict) -> dict:
    """
    异步往返测试任务

    Args:
        document_id: SSIR 文档 ID
        profile: 渲染配置名称
        options: 测试选项

    Returns:
        dict: 测试结果，包含 RoundTripReport
    """
    pass


@shared_task(bind=True, name="roundtrip.fidelity")
def test_rendering_fidelity(self, document_id: str, profile: str) -> dict:
    """
    异步 Rendering Fidelity 测试任务

    Args:
        document_id: SSIR 文档 ID
        profile: 渲染配置名称

    Returns:
        dict: 测试结果
    """
    pass
```

### 5.2 Task 状态

```python
class TaskStatus(str, Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REVOKED = "REVOKED"
    RETRY = "RETRY"
```

### 5.3 Task 结果格式

```json
{
  "taskId": "celery_task_abc123",
  "status": "SUCCESS",
  "result": {
    "documentId": "ssir:GBT-42093.1-2022",
    "runId": "ssir:processing/run/20260815-001",
    "startedAt": "2026-08-15T10:30:00Z",
    "completedAt": "2026-08-15T10:32:00Z",
    "durationSeconds": 120,
    "output": { ... }
  },
  "traceback": null
}
```


## 6. Webhook & Event Specification

### 6.1 事件类型

| 事件名称 | 触发条件 | Payload |
|----------|----------|---------|
| `document.uploaded` | 文档上传完成 | 文档元数据 |
| `document.processing.started` | 处理开始 | 文档 ID + 运行 ID |
| `document.processing.completed` | 处理完成 | 文档 ID + SSIR 摘要 |
| `document.processing.failed` | 处理失败 | 文档 ID + 错误信息 |
| `document.rendering.completed` | 渲染完成 | 文档 ID + 文件 URI |
| `document.roundtrip.completed` | 往返测试完成 | 文档 ID + 测试结果 |
| `document.quality.updated` | 质量评估更新 | 文档 ID + 质量报告 |

### 6.2 Webhook 配置

```json
{
  "url": "https://your-service.com/webhook",
  "events": ["document.processing.completed", "document.rendering.completed"],
  "headers": {
    "X-API-Key": "your-api-key"
  },
  "retry": {
    "maxAttempts": 3,
    "intervalSeconds": 5
  }
}
```

### 6.3 Webhook Payload 格式

```json
{
  "event": "document.processing.completed",
  "timestamp": "2026-08-15T10:30:00Z",
  "data": {
    "documentId": "ssir:GBT-42093.1-2022",
    "runId": "ssir:processing/run/20260815-001",
    "status": "COMPLETED",
    "preservationLevel": "Level3",
    "summary": {
      "totalNodes": 45,
      "totalContentElements": 1432,
      "totalTables": 5,
      "totalFigures": 3
    },
    "quality": {
      "overallStatus": "complete",
      "structureConfidence": 0.99
    }
  }
}
```


## 7. Rate Limiting & Quotas

### 7.1 Rate Limit 规则

| 端点 | 限制 | 窗口 |
|------|------|------|
| `POST /documents` | 10/min | 每分钟 |
| `POST /documents/{id}/process` | 5/min | 每分钟 |
| `POST /documents/{id}/render` | 10/min | 每分钟 |
| `POST /documents/{id}/roundtrip` | 3/min | 每分钟 |
| `GET /documents` | 30/min | 每分钟 |
| `GET /documents/{id}` | 60/min | 每分钟 |
| `GET /documents/{id}/ssir` | 20/min | 每分钟 |

### 7.2 Rate Limit 响应头

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 8
X-RateLimit-Reset: 1600000000
Retry-After: 30
```


## 8. Version History

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 0.1 | 2026-08-15 | 初始版本，定义 REST API、内部接口、异步任务、Webhook |


## 9. Next Steps

1. **Review & Freeze**: 本规范评审并冻结
2. **生成 OpenAPI 文档**: 将本规范转换为 OpenAPI 3.0 YAML/JSON
3. **生成 SDK**: 生成 Python/JavaScript SDK（可选）
4. **实现 Mock Server**: 实现 API Mock 供前端联调
5. **更新 AI Coding Specification**: 将本规范同步到 AI Coding Implementation Specification
