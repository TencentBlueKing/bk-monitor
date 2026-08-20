# AI UI SDK 资源选择弹窗后端接口文档

> 版本：`@blueking/ai-ui-sdk 0.4.1-beta.19`
> 适用范围：`analysis-config-sideslider.tsx` 中仅使用 **Agent / Knowledgebase / Skill** 三种资源模块
> 配套文件：
>
> - [组件使用说明](./ai-ui-sdk-resource-dialog-usage.md)
> - [后端对接对齐文档](./ai-ui-sdk-resource-dialog-backend-alignment.md)

---

## 一、通用约定

### 1.1 接口域名 / URL 前缀

组件内部所有请求基于同一个 `apiPrefix` 拼接，最终 URL 格式统一为：

```text
{apiPrefix}/{module}/{version}/{resource}/
```

当前项目侧弹窗传入 `apiPrefix = ''`，若网关需要统一前缀（如 `/api/ai`），则最终路径变为 `/api/ai/agent/v1/agent/` 等。

> **注意**：`memberUrl` 为完整 URL，组件内部不会再拼接 `apiPrefix`。

### 1.2 请求头

所有内部请求自动携带以下请求头：

```http
x-space-id: {spaceId}
Content-Type: application/json
```

### 1.3 响应结构约定

```json
{
  "code": "success" | 0,
  "data": { ... },
  "message": "..."
}
```

只有 `code` 为 `"success"` 或 `0` 时，组件才会消费 `data`。

### 1.4 分页参数约定

组件内部统一使用驼峰命名，实际发送到后端的参数会转换为下划线命名：

| 组件内字段 | 后端字段    | 类型     | 说明     |
| ---------- | ----------- | -------- | -------- |
| `page`     | `page`      | `number` | 当前页码 |
| `pageSize` | `page_size` | `number` | 每页条数 |

---

## 二、接口列表

---

### 2.1 空间模块

#### 2.1.1 获取有权限空间列表

| 项目     | 内容                                                                         |
| -------- | ---------------------------------------------------------------------------- |
| 接口说明 | 拉取当前用户有权限的空间列表，用于弹窗左侧空间筛选栏（`showSpace=true`）展示 |
| 请求方式 | `GET`                                                                        |
| 请求 URL | `{apiPrefix}/meta/v1/space/authorized_spaces/`                               |

**请求头：**

```http
x-space-id: {spaceId}
```

**Query 参数：**

| 参数        | 类型     | 必填 | 说明     |
| ----------- | -------- | ---- | -------- |
| `page`      | `number` | 否   | 页码     |
| `page_size` | `number` | 否   | 每页条数 |

**请求示例：**

```http
GET /meta/v1/space/authorized_spaces/?page=1&page_size=100 HTTP/1.1
x-space-id: xxx
```

**响应参数：**

| 参数         | 类型               | 说明     |
| ------------ | ------------------ | -------- |
| `code`       | `string \| number` | 状态码   |
| `data`       | `object`           | —        |
| `data.list`  | `ISpace[]`         | 空间列表 |
| `data.total` | `number`           | 总条数   |
| `message`    | `string`           | 提示信息 |

**响应示例：**

```json
{
  "code": "success",
  "data": {
    "list": [
      {
        "space_id": "space-1",
        "space_name": "默认空间",
        "permission": {
          "view_agent": true,
          "use_agent": true,
          "create_agent": true,
          "manage_agent": false
        }
      },
      {
        "space_id": "space-2",
        "space_name": "AI 研发空间",
        "permission": {
          "view_agent": true,
          "use_agent": true,
          "create_agent": false,
          "manage_agent": false
        }
      }
    ],
    "total": 2
  },
  "message": "ok"
}
```

> **注意**：当前项目 `RenderResourceDialog` 的 `spaces` props 由宿主注入，组件本身不直接调用该接口；该接口实际由卡片内部 `render-relate-agent` 子组件使用。若后端需要为弹窗空间栏提供数据源，需确认是否复用此接口。

---

### 2.2 Agent 模块

#### 2.1.1 获取 Agent 列表

| 项目     | 内容                                            |
| -------- | ----------------------------------------------- |
| 接口说明 | 拉取 Agent 资源列表，支持分页、搜索、空间筛选等 |
| 请求方式 | `GET`                                           |
| 请求 URL | `{apiPrefix}/agent/v1/agent/`                   |

**请求头：**

```http
x-space-id: {spaceId}
```

**Query 参数：**

| 参数               | 类型            | 必填 | 说明                                             |
| ------------------ | --------------- | ---- | ------------------------------------------------ |
| `page`             | `number`        | 否   | 页码，默认 `1`                                   |
| `page_size`        | `number`        | 否   | 每页条数，默认 `100`                             |
| `group_type`       | `GroupType`     | 否   | `all` / `space` / `user` / `deleted`，默认 `all` |
| `space_id`         | `string`        | 否   | 空间 ID                                          |
| `can_apply`        | `boolean`       | 否   | 是否可申请资源                                   |
| `with_private`     | `boolean`       | 否   | 是否包含私有资源                                 |
| `created_by`       | `string`        | 否   | 创建人，用于「我的」筛选                         |
| `agent_type`       | `AgentType`     | 否   | `single` / `flow`                                |
| `exclude_agent_id` | `number`        | 否   | 排除自身 ID                                      |
| `is_published`     | `boolean`       | 否   | 仅已发布                                         |
| `fuzzy`            | `string`        | 否   | 模糊搜索                                         |
| `generate_type`    | `EnumCharacter` | 否   | `all` / `system` / `user` / `public` / `space`   |
| `agent_name`       | `string`        | 否   | 按名称精确搜索                                   |
| `agent_code`       | `string`        | 否   | 按编码精确搜索                                   |
| `description`      | `string`        | 否   | 按描述搜索                                       |
| `updated_by`       | `string`        | 否   | 按更新人搜索                                     |

**请求示例：**

```http
GET {apiPrefix}/agent/v1/agent/?group_type=all&page=1&page_size=100&agent_type=single&is_published=true&with_private=false&exclude_agent_id=4750&can_apply=false&created_by=mock_user HTTP/1.1
x-space-id: {spaceId}
```

**响应参数：**

| 参数             | 类型               | 说明       |
| ---------------- | ------------------ | ---------- |
| `result`         | `boolean`          | 是否成功   |
| `code`           | `string \| number` | 状态码     |
| `data`           | `object`           | 分页数据   |
| `data.page`      | `number`           | 当前页码   |
| `data.num_pages` | `number`           | 总页数     |
| `data.count`     | `number`           | 总条数     |
| `data.results`   | `IAgent[]`         | Agent 列表 |
| `message`        | `string \| null`   | 提示信息   |
| `request_id`     | `string`           | 请求 ID    |
| `trace_id`       | `string`           | 追踪 ID    |

**响应示例：**

```json
{
  "result": true,
  "code": "success",
  "data": {
    "page": 1,
    "num_pages": 1,
    "count": 1,
    "results": [
      {
        "id": 156,
        "prompt_setting": {
          "llm_code": "deepseek-r1-70b"
        },
        "favorite": false,
        "favorite_count": 0,
        "created_at": "2025-05-28 14:58:46",
        "created_by": "mock_user",
        "updated_at": "2026-08-12 11:18:52",
        "updated_by": "mock_user",
        "property": {},
        "space_id": "mock-space-id",
        "tenant_id": "system",
        "generate_type": "public",
        "is_public": true,
        "agent_code": "mock-agent-code",
        "agent_name": "Mock Agent 名称",
        "app_code": "mock-app-code",
        "latest_version": "1.1.0",
        "agent_sdk_version": "",
        "icon": "https://example.com/icon.png",
        "agent_type": "single",
        "description": "Mock Agent 描述",
        "is_bind_bk_saas": false,
        "is_plugin_app": true,
        "deploy_mode": "code_package",
        "agent_url": "http://mock-agent.example.com",
        "user_guide": "# 智能体插件 API 调用文档\n\n## 1.1 接口协议...",
        "service_catalogue": [],
        "expected_efficiency_minutes": 0,
        "iam_group_id": null,
        "user_scope": "public",
        "status": "ready",
        "agent_api_url": "http://mock-agent-api.example.com",
        "agent_callable": true,
        "sandbox_grant_status": "success",
        "sandbox_grant_message": "",
        "sandbox_granted_at": "2026-08-12 11:18:52",
        "download_url": "//example.com/agent/156/download/",
        "tag_names": [],
        "business_ids": [],
        "ref_count": 0,
        "conversation_settings": {
          "commands": [
            {
              "id": "mock-agent-code",
              "name": "Mock Agent 名称",
              "icon": "ai",
              "agent_code": null,
              "components": [
                {
                  "type": "text",
                  "name": "输入",
                  "key": "input",
                  "placeholder": null,
                  "default": null,
                  "required": false,
                  "fill_back": false,
                  "fill_regx": null,
                  "rows": null,
                  "min": null,
                  "max": null,
                  "options": null,
                  "hide": false
                }
              ],
              "content": null,
              "agent_id": 156,
              "agent_name": "Mock Agent 名称",
              "space_id": "mock-space-id",
              "alias": null,
              "status": "ready",
              "enable_fill_back": false,
              "fill_back_component_key": null,
              "fill_regx": null,
              "support_upload": {},
              "updated_by": "mock_user",
              "updated_at": "2026-08-12 11:18:52"
            }
          ]
        },
        "permission": {
          "manage_agent": false,
          "use_agent": true
        }
      }
    ]
  },
  "message": null,
  "request_id": "mock-request-id",
  "trace_id": "mock-trace-id"
}
```

---

#### 2.1.2 获取 Agent 空间计数

| 项目     | 内容                                            |
| -------- | ----------------------------------------------- |
| 接口说明 | 按空间统计 Agent 数量，用于左侧空间列表展示角标 |
| 请求方式 | `POST`                                          |
| 请求 URL | `{apiPrefix}/agent/v1/agent/count/`             |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Body 参数：**

| 参数               | 类型        | 必填 | 说明                     |
| ------------------ | ----------- | ---- | ------------------------ |
| `with_private`     | `boolean`   | 否   | 是否包含私有资源         |
| `can_apply`        | `boolean`   | 否   | 是否可申请资源           |
| `space_name`       | `string`    | 否   | 空间名称                 |
| `group_type`       | `GroupType` | 否   | `all` / `space` / `user` |
| `exclude_agent_id` | `number`    | 否   | 排除自身 ID              |
| `agent_type`       | `AgentType` | 否   | `single` / `flow`        |
| `is_published`     | `boolean`   | 否   | 仅已发布                 |

**请求示例：**

```http
POST {apiPrefix}/agent/v1/agent/count/ HTTP/1.1
x-space-id: {spaceId}
Content-Type: application/json

{
  "with_private": false,
  "can_apply": false,
  "space_name": "",
  "group_type": "all",
  "exclude_agent_id": 4750,
  "agent_type": "single",
  "is_published": true
}
```

**响应参数：**

| 参数                | 类型               | 说明                  |
| ------------------- | ------------------ | --------------------- |
| `result`            | `boolean`          | 是否成功              |
| `code`              | `string \| number` | 状态码                |
| `data`              | `ISpaceCount[]`    | 各空间 Agent 计数列表 |
| `data[].space_id`   | `string`           | 空间 ID               |
| `data[].space_name` | `string`           | 空间名称              |
| `data[].count`      | `number`           | 该空间下的 Agent 数量 |
| `message`           | `string \| null`   | 提示信息              |
| `request_id`        | `string`           | 请求 ID               |
| `trace_id`          | `string`           | 追踪 ID               |

**响应示例：**

```json
{
  "result": true,
  "code": "success",
  "data": [
    {
      "space_id": "all",
      "space_name": "全部",
      "count": 91
    },
    {
      "space_id": "mock-space-id-1",
      "space_name": "Mock Space 1",
      "count": 1
    },
    {
      "space_id": "mock-space-id-2",
      "space_name": "Mock Space 2",
      "count": 4
    },
    {
      "space_id": "mock-space-id-3",
      "space_name": "Mock Space 3",
      "count": 33
    },
    {
      "space_id": "mock-space-id-4",
      "space_name": "Mock Space 4",
      "count": 8
    },
    {
      "space_id": "mock-space-id-5",
      "space_name": "Mock Space 5",
      "count": 2
    }
  ],
  "message": null,
  "request_id": "mock-request-id",
  "trace_id": "mock-trace-id"
}
```

---

#### 2.2.3 获取 Agent 标签树

| 项目     | 内容                                                            |
| -------- | --------------------------------------------------------------- |
| 接口说明 | 获取 Agent 资源标签树，用于弹窗标签搜索（`showTagSearch=true`） |
| 请求方式 | `GET`                                                           |
| 请求 URL | `{apiPrefix}/agent/v1/agent/tag_tree/`                          |

**请求头：**

```http
x-space-id: {spaceId}
```

**Query 参数：**

| 参数         | 类型        | 必填 | 说明                                             |
| ------------ | ----------- | ---- | ------------------------------------------------ |
| `group_type` | `GroupType` | 否   | `all` / `space` / `user` / `deleted`，默认 `all` |
| `space_id`   | `string`    | 否   | 空间 ID                                          |

**请求示例：**

```http
GET {apiPrefix}/agent/v1/agent/tag_tree/?group_type=all HTTP/1.1
x-space-id: xxx
```

**响应参数：**

| 参数         | 类型               | 说明             |
| ------------ | ------------------ | ---------------- |
| `result`     | `boolean`          | 是否成功         |
| `code`       | `string \| number` | 状态码           |
| `data`       | `object`           | 标签树数据       |
| `data.tree`  | `ITagNode[]`       | 标签树根节点列表 |
| `data.all`   | `number`           | 全部资源数量     |
| `message`    | `string \| null`   | 提示信息         |
| `request_id` | `string`           | 请求 ID          |
| `trace_id`   | `string`           | 追踪 ID          |

**响应示例：**

```json
{
  "result": true,
  "code": "success",
  "data": {
    "tree": [
      {
        "tag_name": "无标签",
        "tag_id": -1,
        "count": 29,
        "level": 1,
        "property": null,
        "children": []
      },
      {
        "tag_name": "业务操作",
        "tag_id": 315,
        "count": 38,
        "level": 1,
        "property": {
          "is_editable": false,
          "built_in": true
        },
        "children": [
          {
            "tag_name": "研发服务",
            "tag_id": 667,
            "count": 18,
            "level": 2,
            "property": {
              "is_editable": false,
              "built_in": true
            },
            "children": [
              {
                "tag_name": "其他研发日常需求处理",
                "tag_id": 673,
                "count": 10,
                "level": 3,
                "property": {
                  "is_editable": false,
                  "built_in": true,
                  "id": 245,
                  "code_path": "/operation/r_d_service/other_research_require"
                },
                "children": []
              }
            ]
          }
        ]
      },
      {
        "tag_name": "test",
        "tag_id": 2267,
        "count": 2,
        "level": 1,
        "property": {
          "is_editable": false,
          "built_in": true,
          "bk_biz_id": 5000323
        },
        "children": []
      }
    ],
    "all": 124
  },
  "message": null,
  "request_id": "xxxx",
  "trace_id": "xxxx"
}
```

---

### 2.3 Knowledgebase 模块

#### 2.3.1 获取 Knowledgebase 列表

| 项目     | 内容                                               |
| -------- | -------------------------------------------------- |
| 接口说明 | 拉取知识库资源列表                                 |
| 请求方式 | `POST`                                             |
| 请求 URL | `{apiPrefix}/knowledgebase/v1/knowledgebase/list/` |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Body 参数：**

| 参数                 | 类型        | 必填 | 说明         |
| -------------------- | ----------- | ---- | ------------ |
| `page`               | `number`    | 否   | 页码         |
| `page_size`          | `number`    | 否   | 每页条数     |
| `group_type`         | `GroupType` | 否   | —            |
| `space_id`           | `string`    | 否   | 空间 ID      |
| `can_apply`          | `boolean`   | 否   | —            |
| `with_private`       | `boolean`   | 否   | —            |
| `created_by`         | `string`    | 否   | —            |
| `fuzzy`              | `string`    | 否   | 模糊搜索     |
| `anchor_paths`       | `string[]`  | 否   | —            |
| `anchor_path`        | `string`    | 否   | —            |
| `filter_link`        | `boolean`   | 否   | —            |
| `hidden_files`       | `boolean`   | 否   | —            |
| `name`               | `string`    | 否   | 按名称搜索   |
| `knowledgebase_code` | `string`    | 否   | 按编码搜索   |
| `id`                 | `number`    | 否   | 按 ID 搜索   |
| `without_children`   | `boolean`   | 否   | —            |
| `description`        | `string`    | 否   | 按描述搜索   |
| `updated_by`         | `string`    | 否   | 按更新人搜索 |

**请求示例：**

```http
POST {apiPrefix}/knowledgebase/v1/knowledgebase/list/ HTTP/1.1
x-space-id: {spaceId}
Content-Type: application/json

{
  "group_type": "all",
  "page": 1,
  "page_size": 100,
  "space_id": "mock-space-id",
  "with_private": false,
  "can_apply": false
}
```

**响应参数：**

| 参数             | 类型               | 说明       |
| ---------------- | ------------------ | ---------- |
| `result`         | `boolean`          | 是否成功   |
| `code`           | `string \| number` | 状态码     |
| `data`           | `object`           | 分页数据   |
| `data.page`      | `number`           | 当前页码   |
| `data.num_pages` | `number`           | 总页数     |
| `data.count`     | `number`           | 总条数     |
| `data.results`   | `IKnowledgebase[]` | 知识库列表 |
| `message`        | `string \| null`   | 提示信息   |
| `request_id`     | `string`           | 请求 ID    |
| `trace_id`       | `string`           | 追踪 ID    |

**响应示例：**

```json
{
  "result": true,
  "code": "success",
  "data": {
    "page": 1,
    "num_pages": 1,
    "count": 1,
    "results": [
      {
        "id": 907,
        "space_id": "mock-space-id",
        "total_file_size": 48279,
        "generate_type": "space",
        "name": "Mock Knowledgebase 名称",
        "config": {
          "file_root_path": "mock/file_repository/userfiles/mock_kb_code",
          "document_loader": "default_document_loader",
          "pipeline_code": "",
          "pipeline_codes": {
            "fulltext": "fulltext_mock_pipeline",
            "structured_data": "structured_mock_pipeline"
          },
          "handle_type": ["vector-embedding"]
        },
        "knowledgebase_code": "mock-kb-code",
        "knowledge_count": 5,
        "collection_name": "Mock Knowledgebase 名称",
        "updated_by": "mock_user",
        "updated_at": "2026-08-11T12:10:08.742174Z",
        "index_config": {
          "full_text_indexes": [],
          "vector_indexes": [],
          "scalar_indexes": []
        },
        "pipeline_codes": {
          "fulltext": "fulltext_mock_pipeline",
          "structured_data": "structured_mock_pipeline"
        },
        "pipeline_status": {},
        "anchor_path": "/907",
        "folder_num": 3,
        "description": "Mock 知识库描述。",
        "type": "default",
        "children": [],
        "is_public": true,
        "favorite": false,
        "favorite_count": 0,
        "permission": {
          "manage_knowledgebase": false,
          "use_knowledgebase": true
        }
      }
    ]
  },
  "message": null,
  "request_id": "mock-request-id",
  "trace_id": "mock-trace-id"
}
```

---

#### 2.3.2 获取 Knowledgebase 空间计数

| 项目     | 内容                                                |
| -------- | --------------------------------------------------- |
| 接口说明 | 按空间统计知识库数量                                |
| 请求方式 | `POST`                                              |
| 请求 URL | `{apiPrefix}/knowledgebase/v1/knowledgebase/count/` |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Body 参数：**

| 参数           | 类型        | 必填 | 说明                     |
| -------------- | ----------- | ---- | ------------------------ |
| `with_private` | `boolean`   | 否   | 是否包含私有资源         |
| `can_apply`    | `boolean`   | 否   | 是否可申请资源           |
| `space_name`   | `string`    | 否   | 空间名称                 |
| `group_type`   | `GroupType` | 否   | `all` / `space` / `user` |

**请求示例：**

```http
POST {apiPrefix}/knowledgebase/v1/knowledgebase/count/ HTTP/1.1
x-space-id: {spaceId}
Content-Type: application/json

{
  "with_private": false,
  "can_apply": false,
  "space_name": "",
  "group_type": "all"
}
```

**响应参数：**

| 参数                | 类型               | 说明                 |
| ------------------- | ------------------ | -------------------- |
| `result`            | `boolean`          | 是否成功             |
| `code`              | `string \| number` | 状态码               |
| `data`              | `ISpaceCount[]`    | 各空间知识库计数列表 |
| `data[].space_id`   | `string`           | 空间 ID              |
| `data[].space_name` | `string`           | 空间名称             |
| `data[].count`      | `number`           | 该空间下的知识库数量 |
| `message`           | `string \| null`   | 提示信息             |
| `request_id`        | `string`           | 请求 ID              |
| `trace_id`          | `string`           | 追踪 ID              |

**响应示例：**

```json
{
  "result": true,
  "code": "success",
  "data": [
    {
      "space_id": "all",
      "space_name": "全部",
      "count": 147
    },
    {
      "space_id": "mock-space-id-1",
      "space_name": "Mock Space 1",
      "count": 1
    },
    {
      "space_id": "mock-space-id-2",
      "space_name": "Mock Space 2",
      "count": 38
    },
    {
      "space_id": "mock-space-id-3",
      "space_name": "Mock Space 3",
      "count": 76
    },
    {
      "space_id": "mock-space-id-4",
      "space_name": "Mock Space 4",
      "count": 4
    },
    {
      "space_id": "mock-space-id-5",
      "space_name": "Mock Space 5",
      "count": 6
    }
  ],
  "message": null,
  "request_id": "mock-request-id",
  "trace_id": "mock-trace-id"
}
```

---

### 2.4 Skill 模块

#### 2.4.1 获取 Skill 列表

| 项目     | 内容                          |
| -------- | ----------------------------- |
| 接口说明 | 拉取 Skill 资源列表           |
| 请求方式 | `GET`                         |
| 请求 URL | `{apiPrefix}/skill/v1/skill/` |

**请求头：**

```http
x-space-id: {spaceId}
```

**Query 参数：**

| 参数            | 类型            | 必填 | 说明         |
| --------------- | --------------- | ---- | ------------ |
| `page`          | `number`        | 否   | 页码         |
| `page_size`     | `number`        | 否   | 每页条数     |
| `group_type`    | `GroupType`     | 否   | —            |
| `space_id`      | `string`        | 否   | 空间 ID      |
| `can_apply`     | `boolean`       | 否   | —            |
| `with_private`  | `boolean`       | 否   | —            |
| `created_by`    | `string`        | 否   | —            |
| `generate_type` | `EnumCharacter` | 否   | —            |
| `fuzzy`         | `string`        | 否   | 模糊搜索     |
| `skill_name`    | `string`        | 否   | 按名称搜索   |
| `skill_code`    | `string`        | 否   | 按编码搜索   |
| `description`   | `string`        | 否   | 按描述搜索   |
| `updated_by`    | `string`        | 否   | 按更新人搜索 |
| `status`        | `SkillStatus`   | 否   | 状态过滤     |

**请求示例：**

```http
GET {apiPrefix}/skill/v1/skill/?group_type=all&page=1&page_size=100&can_apply=false&space_id=mock-space-id HTTP/1.1
x-space-id: {spaceId}
```

**响应参数：**

| 参数             | 类型               | 说明       |
| ---------------- | ------------------ | ---------- |
| `result`         | `boolean`          | 是否成功   |
| `code`           | `string \| number` | 状态码     |
| `data`           | `object`           | 分页数据   |
| `data.page`      | `number`           | 当前页码   |
| `data.num_pages` | `number`           | 总页数     |
| `data.count`     | `number`           | 总条数     |
| `data.results`   | `ISkill[]`         | Skill 列表 |
| `message`        | `string \| null`   | 提示信息   |
| `request_id`     | `string`           | 请求 ID    |
| `trace_id`       | `string`           | 追踪 ID    |

**响应示例：**

```json
{
  "result": true,
  "code": "success",
  "data": {
    "page": 1,
    "num_pages": 1,
    "count": 1,
    "results": [
      {
        "id": 205,
        "favorite": false,
        "favorite_count": 0,
        "created_at": "2026-03-30 15:41:12",
        "created_by": "mock_user",
        "updated_at": "2026-07-31 15:17:00",
        "updated_by": "mock_user",
        "property": {},
        "space_id": "mock-space-id",
        "tenant_id": "system",
        "generate_type": "public",
        "is_public": true,
        "skill_name": "Mock Skill 名称",
        "skill_code": "mock-skill-code",
        "description": "Mock Skill 描述。",
        "icon": "https://example.com/icons/mock-skill.png",
        "url": "/mock/file_repository/skillfiles/mock-space-id_timestamp/mock-skill-code.zip",
        "version": "1.0.0",
        "download_count": 14,
        "install_count": 0,
        "file_name": "mock-skill-code",
        "file_size": 117971,
        "file_type": "zip",
        "image_status": "successful",
        "image_error_message": "",
        "ref_count": 3,
        "tag_names": [["标签一"], ["标签二"], ["标签三"]],
        "scanner": {
          "effective_status": "pass",
          "effective_status_cn": "安全",
          "last_scan_at": "2026-08-04T20:56:14.012098+00:00",
          "report_content": "# 安全扫描报告: mock-skill-code\n\n## 基本信息\n\n| 项目 | 值 |\n|------|-----|\n| Skill 名称 | mock-skill-code |\n| 安全状态 | **安全** |\n| 最后扫描 | 2026/08/04 20:56:14 |\n\n## 风险摘要\n\n| 等级 | 数量 |\n|------|------|\n\n## 风险详情\n\n未发现安全风险。"
        },
        "status": "published",
        "latest_version": "1.0.0",
        "latest_status": "published",
        "bkai_dependencies": {
          "envs": []
        },
        "permission": {
          "manage_skill": false,
          "use_skill": true
        }
      }
    ]
  },
  "message": null,
  "request_id": "mock-request-id",
  "trace_id": "mock-trace-id"
}
```

---

#### 2.4.2 获取 Skill 空间计数

| 项目     | 内容                                |
| -------- | ----------------------------------- |
| 接口说明 | 按空间统计 Skill 数量               |
| 请求方式 | `POST`                              |
| 请求 URL | `{apiPrefix}/skill/v1/skill/count/` |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Body 参数：**

| 参数           | 类型      | 必填 | 说明             |
| -------------- | --------- | ---- | ---------------- |
| `with_private` | `boolean` | 否   | 是否包含私有资源 |
| `can_apply`    | `boolean` | 否   | 是否可申请资源   |
| `space_name`   | `string`  | 否   | 空间名称         |
| `created_by`   | `string`  | 否   | 创建人           |

**请求示例：**

```http
POST {apiPrefix}/skill/v1/skill/count/ HTTP/1.1
x-space-id: {spaceId}
Content-Type: application/json

{
  "with_private": false,
  "can_apply": false,
  "space_name": "",
  "created_by": "mock_user"
}
```

**响应参数：**

| 参数                | 类型               | 说明                  |
| ------------------- | ------------------ | --------------------- |
| `result`            | `boolean`          | 是否成功              |
| `code`              | `string \| number` | 状态码                |
| `data`              | `ISpaceCount[]`    | 各空间 Skill 计数列表 |
| `data[].space_id`   | `string`           | 空间 ID               |
| `data[].space_name` | `string`           | 空间名称              |
| `data[].count`      | `number`           | 该空间下的 Skill 数量 |
| `message`           | `string \| null`   | 提示信息              |
| `request_id`        | `string`           | 请求 ID               |
| `trace_id`          | `string`           | 追踪 ID               |

**响应示例：**

```json
{
  "result": true,
  "code": "success",
  "data": [
    {
      "space_id": "all",
      "space_name": "全部",
      "count": 0
    },
    {
      "space_id": "mock-space-id-1",
      "space_name": "Mock Space 1",
      "count": 1
    }
  ],
  "message": null,
  "request_id": "mock-request-id",
  "trace_id": "mock-trace-id"
}
```

---

#### 2.4.3 获取 Skill 标签树

| 项目     | 内容                                                            |
| -------- | --------------------------------------------------------------- |
| 接口说明 | 获取 Skill 资源标签树，用于弹窗标签搜索（`showTagSearch=true`） |
| 请求方式 | `GET`                                                           |
| 请求 URL | `{apiPrefix}/skill/v1/skill/tag_tree/`                          |

**请求头：**

```http
x-space-id: {spaceId}
```

**Query 参数：**

| 参数         | 类型        | 必填 | 说明                                             |
| ------------ | ----------- | ---- | ------------------------------------------------ |
| `group_type` | `GroupType` | 否   | `all` / `space` / `user` / `deleted`，默认 `all` |
| `space_id`   | `string`    | 否   | 空间 ID                                          |

**请求示例：**

```http
GET {apiPrefix}/skill/v1/skill/tag_tree/?group_type=all HTTP/1.1
x-space-id: {spaceId}
```

**响应参数：**

| 参数         | 类型               | 说明             |
| ------------ | ------------------ | ---------------- |
| `result`     | `boolean`          | 是否成功         |
| `code`       | `string \| number` | 状态码           |
| `data`       | `object`           | 标签树数据       |
| `data.tree`  | `ITagNode[]`       | 标签树根节点列表 |
| `data.all`   | `number`           | 全部资源数量     |
| `message`    | `string \| null`   | 提示信息         |
| `request_id` | `string`           | 请求 ID          |
| `trace_id`   | `string`           | 追踪 ID          |

**响应示例：**

```json
{
  "result": true,
  "code": "success",
  "data": {
    "tree": [
      {
        "tag_name": "无标签",
        "tag_id": -1,
        "count": 220,
        "level": 1,
        "property": null,
        "children": []
      },
      {
        "tag_name": "编程",
        "tag_id": 7,
        "count": 7,
        "level": 1,
        "property": {
          "is_editable": true,
          "built_in": false
        },
        "children": []
      },
      {
        "tag_name": "报告",
        "tag_id": 666,
        "count": 6,
        "level": 1,
        "property": null,
        "children": []
      },
      {
        "tag_name": "蓝鲸",
        "tag_id": 33,
        "count": 5,
        "level": 1,
        "property": {
          "is_editable": true,
          "built_in": false
        },
        "children": []
      },
      {
        "tag_name": "工具",
        "tag_id": 17,
        "count": 4,
        "level": 1,
        "property": {
          "is_editable": true,
          "built_in": false
        },
        "children": []
      },
      {
        "tag_name": "前端",
        "tag_id": 18,
        "count": 4,
        "level": 1,
        "property": {
          "is_editable": true,
          "built_in": false
        },
        "children": []
      },
      {
        "tag_name": "Mock Skill 标签一",
        "tag_id": 1001,
        "count": 4,
        "level": 1,
        "property": null,
        "children": []
      },
      {
        "tag_name": "Mock Skill 标签二",
        "tag_id": 1002,
        "count": 3,
        "level": 1,
        "property": {
          "is_editable": true,
          "built_in": false
        },
        "children": []
      },
      {
        "tag_name": "Mock Skill 标签三",
        "tag_id": 1003,
        "count": 3,
        "level": 1,
        "property": null,
        "children": []
      },
      {
        "tag_name": "Mock Skill 标签四",
        "tag_id": 1004,
        "count": 2,
        "level": 1,
        "property": null,
        "children": []
      },
      {
        "tag_name": "Mock Skill 标签五",
        "tag_id": 1005,
        "count": 1,
        "level": 1,
        "property": {
          "is_editable": true,
          "built_in": false
        },
        "children": []
      }
    ],
    "all": 277
  },
  "message": null,
  "request_id": "mock-request-id",
  "trace_id": "mock-trace-id"
}
```

> **注意**：字段结构与 Agent 标签树保持一致，具体数值以实际接口返回为准。

---

### 2.5 成员搜索接口

| 项目     | 内容                                  |
| -------- | ------------------------------------- |
| 接口说明 | 搜索成员，用于弹窗内按创建人筛选      |
| 请求方式 | `GET`                                 |
| 请求 URL | `{memberUrl}`（完整地址，由宿主传入） |

> **注意**：`memberUrl` 为完整 URL，组件内部不会再拼接 `apiPrefix`。当前项目传入的 `memberUrl` 为 `bk-magicbox` 成员搜索接口，返回 JSONP 格式。

**Query 参数：**

| 参数            | 类型     | 必填 | 说明                                                 |
| --------------- | -------- | ---- | ---------------------------------------------------- |
| `callback`      | `string` | 是   | JSONP 回调函数名，如 `jsonp_init_bk_member_{random}` |
| `app_code`      | `string` | 是   | 应用标识，如 `bk-magicbox`                           |
| `fuzzy_lookups` | `string` | 否   | 搜索关键字，支持模糊匹配用户名 / 中文名 / 英文名等   |
| `page`          | `number` | 否   | 页码                                                 |
| `page_size`     | `number` | 否   | 每页条数                                             |

**请求示例：**

```http
GET {memberUrl}?callback=jsonp_init_bk_member_130&app_code=bk-magicbox&fuzzy_lookups=mock_keyword HTTP/1.1
```

**响应参数：**

| 参数                           | 类型        | 说明     |
| ------------------------------ | ----------- | -------- |
| `result`                       | `boolean`   | 是否成功 |
| `code`                         | `number`    | 状态码   |
| `message`                      | `string`    | 提示信息 |
| `data`                         | `object`    | —        |
| `data.count`                   | `number`    | 总条数   |
| `data.results`                 | `IMember[]` | 成员列表 |
| `data.results[].id`            | `number`    | 用户 ID  |
| `data.results[].username`      | `string`    | 用户名   |
| `data.results[].domain`        | `string`    | 域       |
| `data.results[].display_name`  | `string`    | 展示名称 |
| `data.results[].staff_status`  | `string`    | 在职状态 |
| `data.results[].logo`          | `string`    | 头像 URL |
| `data.results[].category_id`   | `number`    | 分类 ID  |
| `data.results[].category_name` | `string`    | 分类名称 |
| `request_id`                   | `string`    | 请求 ID  |

**响应示例：**

```json
{
  "message": "",
  "code": 0,
  "data": {
    "count": 3,
    "results": [
      {
        "username": "mock_user_1",
        "domain": "mock-domain.com",
        "display_name": "Mock User 1",
        "staff_status": "IN",
        "logo": "",
        "category_id": 2,
        "id": 100001,
        "category_name": "Mock Category"
      },
      {
        "username": "mock_user_2",
        "domain": "mock-domain.com",
        "display_name": "Mock User 2",
        "staff_status": "IN",
        "logo": "",
        "category_id": 2,
        "id": 100002,
        "category_name": "Mock Category"
      },
      {
        "username": "mock_user_3",
        "domain": "mock-domain.com",
        "display_name": "Mock User 3",
        "staff_status": "IN",
        "logo": "",
        "category_id": 2,
        "id": 100003,
        "category_name": "Mock Category"
      }
    ]
  },
  "result": true,
  "request_id": "mock-request-id"
}
```

---

## 三、数据结构约定

### 3.1 空间结构 `ISpace`

```ts
interface ISpace {
  spaceId: string; // 空间唯一标识
  spaceName: string; // 空间展示名称
}
```

后端字段（下划线命名）：`space_id`, `space_name`。

**字段说明：**

| 字段         | 类型     | 说明                                                   |
| ------------ | -------- | ------------------------------------------------------ |
| `space_id`   | `string` | 空间唯一标识，所有内部请求通过 `x-space-id` 请求头传递 |
| `space_name` | `string` | 空间展示名称，用于弹窗左侧空间列表、已选结果分组展示   |

**响应示例：**

```json
{
  "space_id": "space-1",
  "space_name": "默认空间"
}
```

> 当前项目 `RenderResourceDialog` 通过 `spaces` props 由宿主注入空间列表，组件本身不直接请求空间接口；但实际业务中空间数据通常来源于 `GET /meta/v1/space/authorized_spaces/`。

### 3.2 标签树节点 `ITagNode`

```ts
interface ITagNode {
  tag_id: number; // 标签节点唯一标识，`-1` 表示「无标签」
  tag_name: string; // 标签名称
  count: number; // 该标签下的资源数量
  level: number; // 标签层级（从 1 开始）
  property: ITagProperty | null; // 标签扩展属性
  children: ITagNode[]; // 子标签节点列表，无子节点时为 `[]`
}

interface ITagProperty {
  is_editable?: boolean;
  built_in?: boolean;
  id?: number;
  code_path?: string;
  bk_biz_id?: number;
  // 后端可能透传其它业务字段
}
```

**字段说明：**

| 字段       | 类型                   | 说明                                  |
| ---------- | ---------------------- | ------------------------------------- |
| `tag_id`   | `number`               | 标签节点唯一标识，`-1` 表示「无标签」 |
| `tag_name` | `string`               | 标签展示名称                          |
| `count`    | `number`               | 该标签关联的资源数量                  |
| `level`    | `number`               | 标签层级，从 1 开始递增               |
| `property` | `ITagProperty \| null` | 标签扩展属性；`null` 表示无额外属性   |
| `children` | `ITagNode[]`           | 子标签节点列表                        |

**`property` 字段说明：**

| 字段          | 类型      | 说明                          |
| ------------- | --------- | ----------------------------- |
| `is_editable` | `boolean` | 是否可编辑                    |
| `built_in`    | `boolean` | 是否内置标签                  |
| `id`          | `number`  | 业务侧标签 ID                 |
| `code_path`   | `string`  | 标签路径编码                  |
| `bk_biz_id`   | `number`  | 蓝鲸业务 ID（仅部分标签存在） |

**响应示例：**

```json
{
  "tag_name": "业务操作",
  "tag_id": 315,
  "count": 38,
  "level": 1,
  "property": {
    "is_editable": false,
    "built_in": true
  },
  "children": [
    {
      "tag_name": "研发服务(SRE左移)",
      "tag_id": 667,
      "count": 18,
      "level": 2,
      "property": {
        "is_editable": false,
        "built_in": true
      },
      "children": [
        {
          "tag_name": "其他研发日常需求处理",
          "tag_id": 673,
          "count": 10,
          "level": 3,
          "property": {
            "is_editable": false,
            "built_in": true,
            "id": 245,
            "code_path": "/operation/r_d_service/other_research_require"
          },
          "children": []
        }
      ]
    }
  ]
}
```
