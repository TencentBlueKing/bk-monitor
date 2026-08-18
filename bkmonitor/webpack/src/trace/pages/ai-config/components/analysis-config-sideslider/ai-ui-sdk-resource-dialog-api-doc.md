# AI UI SDK 资源选择弹窗后端接口文档

> 版本：`@blueking/ai-ui-sdk 0.4.1-beta.19`
> 适用范围：`analysis-config-sideslider.tsx` 中仅使用 **Agent / Knowledgebase / Skill** 三种资源模块
> 配套文件：
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

| 组件内字段 | 后端字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| `page` | `page` | `number` | 当前页码 |
| `pageSize` | `page_size` | `number` | 每页条数 |

---

## 二、接口列表

---

### 2.1 空间模块

#### 2.1.1 获取有权限空间列表

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 拉取当前用户有权限的空间列表，用于弹窗左侧空间筛选栏（`showSpace=true`）展示 |
| 请求方式 | `GET` |
| 请求 URL | `{apiPrefix}/meta/v1/space/authorized_spaces/` |

**请求头：**

```http
x-space-id: {spaceId}
```

**Query 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | `number` | 否 | 页码 |
| `page_size` | `number` | 否 | 每页条数 |

**请求示例：**

```http
GET /meta/v1/space/authorized_spaces/?page=1&page_size=100 HTTP/1.1
x-space-id: xxx
```

**响应参数：**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `string \| number` | 状态码 |
| `data` | `object` | — |
| `data.list` | `ISpace[]` | 空间列表 |
| `data.total` | `number` | 总条数 |
| `message` | `string` | 提示信息 |

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

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 拉取 Agent 资源列表，支持分页、搜索、空间筛选等 |
| 请求方式 | `GET` |
| 请求 URL | `{apiPrefix}/agent/v1/agent/` |

**请求头：**

```http
x-space-id: {spaceId}
```

**Query 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | `number` | 否 | 页码 |
| `page_size` | `number` | 否 | 每页条数 |
| `group_type` | `GroupType` | 否 | `all` / `space` / `user` / `deleted` |
| `space_id` | `string` | 否 | 空间 ID |
| `can_apply` | `boolean` | 否 | 是否可申请资源 |
| `with_private` | `boolean` | 否 | 是否包含私有资源 |
| `created_by` | `string` | 否 | 创建人，用于「我的」筛选 |
| `agent_type` | `AgentType` | 否 | `single` / `flow` |
| `exclude_agent_id` | `number` | 否 | 排除自身 ID |
| `is_published` | `boolean` | 否 | 仅已发布 |
| `fuzzy` | `string` | 否 | 模糊搜索 |
| `generate_type` | `EnumCharacter` | 否 | `all` / `system` / `user` / `public` / `space` |
| `agent_name` | `string` | 否 | 按名称精确搜索 |
| `agent_code` | `string` | 否 | 按编码精确搜索 |
| `description` | `string` | 否 | 按描述搜索 |
| `updated_by` | `string` | 否 | 按更新人搜索 |

**请求示例：**

```http
GET /agent/v1/agent/?page=1&page_size=20&space_id=xxx&is_published=true HTTP/1.1
x-space-id: xxx
```

**响应参数：**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `string \| number` | 状态码，成功为 `"success"` 或 `0` |
| `data` | `object` | 见下 |
| `data.list` | `IAgent[]` | Agent 列表 |
| `data.total` | `number` | 总条数 |
| `message` | `string` | 提示信息 |

**响应示例：**

```json
{
  "code": "success",
  "data": {
    "list": [
      {
        "id": 1,
        "agent_code": "code-analyzer",
        "agent_name": "代码分析助手",
        "agent_type": "single",
        "generate_type": "space",
        "icon": "icon-robot",
        "description": "用于源码分析的 Agent",
        "status": "ready",
        "version": "1.0.0",
        "latest_version": "1.0.0",
        "agent_url": "https://example.com/agent/1",
        "download_url": "https://example.com/agent/1/download",
        "tenant_id": "tenant-1",
        "from_paas": false,
        "ref_count": 10,
        "space_id": "space-1",
        "created_by": "admin",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_by": "admin",
        "updated_at": "2026-08-01T00:00:00Z",
        "permission": {
          "view_agent": true,
          "use_agent": true
        }
      }
    ],
    "total": 100
  },
  "message": "ok"
}
```

---

#### 2.1.2 获取 Agent 空间计数

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 按空间统计 Agent 数量，用于左侧空间列表展示角标 |
| 请求方式 | `POST` |
| 请求 URL | `{apiPrefix}/agent/v1/agent/count/` |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Body 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `space_ids` | `string[]` | 是 | 包含 `all` 和具体空间 ID |
| `can_apply` | `boolean` | 否 | — |
| `with_private` | `boolean` | 否 | — |
| `group_type` | `GroupType` | 否 | — |
| `created_by` | `string` | 否 | — |
| `agent_type` | `AgentType` | 否 | — |
| `exclude_agent_id` | `number` | 否 | — |
| `is_published` | `boolean` | 否 | — |

**请求示例：**

```http
POST /agent/v1/agent/count/ HTTP/1.1
x-space-id: xxx
Content-Type: application/json

{
  "space_ids": ["all", "space-1", "space-2"],
  "is_published": true
}
```

**响应参数：**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `string \| number` | 状态码 |
| `data` | `object` | 以 `space_id` 为 key 的计数对象 |
| `message` | `string` | 提示信息 |

**响应示例：**

```json
{
  "code": "success",
  "data": {
    "all": 100,
    "space-1": 30,
    "space-2": 70
  },
  "message": "ok"
}
```

---

### 2.3 Knowledgebase 模块

#### 2.3.1 获取 Knowledgebase 列表

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 拉取知识库资源列表 |
| 请求方式 | `POST` |
| 请求 URL | `{apiPrefix}/knowledgebase/v1/knowledgebase/list/` |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Body 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | `number` | 否 | 页码 |
| `page_size` | `number` | 否 | 每页条数 |
| `group_type` | `GroupType` | 否 | — |
| `space_id` | `string` | 否 | 空间 ID |
| `can_apply` | `boolean` | 否 | — |
| `with_private` | `boolean` | 否 | — |
| `created_by` | `string` | 否 | — |
| `fuzzy` | `string` | 否 | 模糊搜索 |
| `anchor_paths` | `string[]` | 否 | — |
| `anchor_path` | `string` | 否 | — |
| `filter_link` | `boolean` | 否 | — |
| `hidden_files` | `boolean` | 否 | — |
| `name` | `string` | 否 | 按名称搜索 |
| `knowledgebase_code` | `string` | 否 | 按编码搜索 |
| `id` | `number` | 否 | 按 ID 搜索 |
| `without_children` | `boolean` | 否 | — |
| `description` | `string` | 否 | 按描述搜索 |
| `updated_by` | `string` | 否 | 按更新人搜索 |

**请求示例：**

```http
POST /knowledgebase/v1/knowledgebase/list/ HTTP/1.1
x-space-id: xxx
Content-Type: application/json

{
  "page": 1,
  "page_size": 20,
  "space_id": "space-1",
  "fuzzy": "java"
}
```

**响应参数：**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `string \| number` | 状态码 |
| `data` | `object` | — |
| `data.list` | `IKnowledgebase[]` | 知识库列表 |
| `data.total` | `number` | 总条数 |
| `message` | `string` | 提示信息 |

**响应示例：**

```json
{
  "code": "success",
  "data": {
    "list": [
      {
        "id": 1,
        "knowledgebase_id": 1,
        "knowledgebase_code": "java-guide",
        "name": "Java 开发规范",
        "file_path": "/docs/java-guide",
        "file_name": "java-guide.md",
        "file_type": "md",
        "status": "ready",
        "generate_type": "space",
        "is_public": false,
        "description": "Java 团队开发规范知识库",
        "space_id": "space-1",
        "updated_by": "admin",
        "updated_at": "2026-08-01T00:00:00Z",
        "permission": {
          "view_knowledgebase": true,
          "use_knowledgebase": true
        }
      }
    ],
    "total": 50
  },
  "message": "ok"
}
```

---

#### 2.3.2 获取 Knowledgebase 空间计数

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 按空间统计知识库数量 |
| 请求方式 | `POST` |
| 请求 URL | `{apiPrefix}/knowledgebase/v1/knowledgebase/count/` |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Body 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `space_ids` | `string[]` | 是 | 包含 `all` 和具体空间 ID |
| `can_apply` | `boolean` | 否 | — |
| `with_private` | `boolean` | 否 | — |
| `group_type` | `GroupType` | 否 | — |
| `created_by` | `string` | 否 | — |

**请求示例：**

```http
POST /knowledgebase/v1/knowledgebase/count/ HTTP/1.1
x-space-id: xxx
Content-Type: application/json

{
  "space_ids": ["all", "space-1"]
}
```

**响应示例：**

```json
{
  "code": "success",
  "data": {
    "all": 50,
    "space-1": 50
  },
  "message": "ok"
}
```

---

### 2.4 Skill 模块

#### 2.4.1 获取 Skill 列表

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 拉取 Skill 资源列表 |
| 请求方式 | `GET` |
| 请求 URL | `{apiPrefix}/skill/v1/skill/` |

**请求头：**

```http
x-space-id: {spaceId}
```

**Query 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | `number` | 否 | 页码 |
| `page_size` | `number` | 否 | 每页条数 |
| `group_type` | `GroupType` | 否 | — |
| `space_id` | `string` | 否 | 空间 ID |
| `can_apply` | `boolean` | 否 | — |
| `with_private` | `boolean` | 否 | — |
| `created_by` | `string` | 否 | — |
| `generate_type` | `EnumCharacter` | 否 | — |
| `fuzzy` | `string` | 否 | 模糊搜索 |
| `skill_name` | `string` | 否 | 按名称搜索 |
| `skill_code` | `string` | 否 | 按编码搜索 |
| `description` | `string` | 否 | 按描述搜索 |
| `updated_by` | `string` | 否 | 按更新人搜索 |
| `status` | `SkillStatus` | 否 | 状态过滤 |

**请求示例：**

```http
GET /skill/v1/skill/?page=1&page_size=20&space_id=space-1 HTTP/1.1
x-space-id: xxx
```

**响应参数：**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `string \| number` | 状态码 |
| `data` | `object` | — |
| `data.list` | `ISkill[]` | Skill 列表 |
| `data.total` | `number` | 总条数 |
| `message` | `string` | 提示信息 |

**响应示例：**

```json
{
  "code": "success",
  "data": {
    "list": [
      {
        "id": 1,
        "skill_code": "code-review-skill",
        "skill_name": "代码审查 Skill",
        "icon": "icon-skill",
        "url": "https://example.com/skill/1",
        "file_name": "skill.tar.gz",
        "file_size": 1024,
        "file_type": "tar.gz",
        "version": "1.0.0",
        "latest_version": "1.0.0",
        "status": "online",
        "latest_status": "online",
        "generate_type": "space",
        "description": "用于代码审查的 Skill",
        "download_count": 100,
        "install_count": 50,
        "ref_count": 20,
        "space_id": "space-1",
        "created_by": "admin",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_by": "admin",
        "updated_at": "2026-08-01T00:00:00Z",
        "permission": {
          "create_skill": true,
          "manage_skill": true
        },
        "envs": [
          {
            "key": "API_KEY",
            "description": "API 密钥",
            "required": true,
            "default": "",
            "secret": true
          }
        ],
        "bkai_dependencies": {
          "envs": []
        }
      }
    ],
    "total": 80
  },
  "message": "ok"
}
```

---

#### 2.4.2 获取 Skill 空间计数

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 按空间统计 Skill 数量 |
| 请求方式 | `POST` |
| 请求 URL | `{apiPrefix}/skill/v1/skill/count/` |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Body 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `space_ids` | `string[]` | 是 | 包含 `all` 和具体空间 ID |
| `can_apply` | `boolean` | 否 | — |
| `with_private` | `boolean` | 否 | — |
| `group_type` | `GroupType` | 否 | — |
| `created_by` | `string` | 否 | — |

**请求示例：**

```http
POST /skill/v1/skill/count/ HTTP/1.1
x-space-id: xxx
Content-Type: application/json

{
  "space_ids": ["all", "space-1"]
}
```

**响应示例：**

```json
{
  "code": "success",
  "data": {
    "all": 80,
    "space-1": 80
  },
  "message": "ok"
}
```

---

### 2.5 成员搜索接口

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 搜索成员，用于弹窗内按创建人筛选 |
| 请求方式 | `GET` |
| 请求 URL | `{memberUrl}`（完整地址，由宿主传入） |

**请求头：**

```http
x-space-id: {spaceId}
```

**Query 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `keyword` | `string` | 否 | 搜索关键字 |
| `page` | `number` | 否 | 页码 |
| `page_size` | `number` | 否 | 每页条数 |

> 实际字段以 `memberUrl` 对应后端接口定义为准，当前为前端推测。

**响应参数：**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `string \| number` | 状态码 |
| `data` | `object` | — |
| `data.list` | `IMember[]` | 成员列表 |
| `data.total` | `number` | 总条数 |
| `message` | `string` | 提示信息 |

**响应示例：**

```json
{
  "code": "success",
  "data": {
    "list": [
      {
        "id": "user-1",
        "username": "admin",
        "display_name": "管理员"
      }
    ],
    "total": 1
  },
  "message": "ok"
}
```

---

### 2.6 资源申请接口

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 当已选资源中存在 `no_permission` 状态的 Tool/MCP 时，二次确认后调用 |
| 请求方式 | `POST` |
| 请求 URL | `{apiPrefix}/agent/v1/agent/{agentId}/agent_resource_apply/` |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Path 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `agentId` | `number` | 是 | Agent ID |

**Body 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `resources` | `object[]` | 否 | 待申请的资源列表 |
| `resources[].type` | `string` | 否 | 资源类型，如 `tool` / `mcp` |
| `resources[].id` | `number` | 否 | 资源 ID |

> 当前项目主要使用 Agent / Knowledgebase / Skill，通常不会触发 Tool/MCP 的资源申请逻辑。具体字段需后端确认。

**响应示例：**

```json
{
  "code": "success",
  "data": {
    "ticket_id": "T20260801001",
    "ticket_url": "https://example.com/ticket/T20260801001"
  },
  "message": "ok"
}
```

---

## 三、数据结构约定

### 3.1 空间结构 `ISpace`

```ts
interface ISpace {
  spaceId: string;      // 空间唯一标识
  spaceName: string;    // 空间展示名称
}
```

后端字段（下划线命名）：`space_id`, `space_name`。

**字段说明：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `space_id` | `string` | 空间唯一标识，所有内部请求通过 `x-space-id` 请求头传递 |
| `space_name` | `string` | 空间展示名称，用于弹窗左侧空间列表、已选结果分组展示 |

**响应示例：**

```json
{
  "space_id": "space-1",
  "space_name": "默认空间"
}
```

> 当前项目 `RenderResourceDialog` 通过 `spaces` props 由宿主注入空间列表，组件本身不直接请求空间接口；但实际业务中空间数据通常来源于 `GET /meta/v1/space/authorized_spaces/`。

