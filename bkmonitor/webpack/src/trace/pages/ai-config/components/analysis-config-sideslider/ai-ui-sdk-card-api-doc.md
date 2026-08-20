# AI UI SDK 资源卡片后端接口文档（Info 模式）

> 版本：`@blueking/ai-ui-sdk 0.4.1-beta.19`
> 适用范围：`analysis-config-sideslider.tsx` 中使用的 **Agent / Knowledgebase / Skill** 三种资源卡片（**仅 `ResourceCardType.Info` 模式**）
> 配套文件：
> - [资源卡片使用说明](./ai-ui-sdk-card-usage.md)
> - [卡片后端对齐文档](./ai-ui-sdk-backend-alignment.md)
> - [资源选择弹窗后端接口文档](./ai-ui-sdk-resource-dialog-api-doc.md)

---

## 一、通用约定

### 1.1 接口域名 / URL 前缀

组件内部所有请求基于同一个 `apiPrefix` 拼接，最终 URL 格式统一为：

```text
{apiPrefix}/{module}/{version}/{resource}/
```

当前项目侧传入 `apiPrefix = ''`，即接口实际路径形如 `/agent/v1/agent/{agentId}/`。

### 1.2 请求头

所有内部请求自动携带以下请求头：

```http
x-space-id: {spaceId}
```

`POST` 请求额外携带：

```http
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

---

## 二、背景说明

当前分析规则详情接口返回的 `agent_id`（`string`）、`knowledge_base_ids`（`string[]`）、`skill_ids`（`string[]`）仅为资源 ID 集合（见 `src/trace/pages/ai-config/typings/source-analysis-rule.ts`）。

因此资源卡片在 Info 模式下渲染时，需要依赖**新增的批量资源详情接口**将 ID 转换为 `IAgent` / `IKnowledgebase` / `ISkill` 完整数据。以下接口中，**带 ⭐ 的为本次新增接口**。

---

## 三、接口列表

### 3.1 Agent 卡片

#### 3.1.1 批量获取 Agent 详情 ⭐

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 根据分析规则返回的 `agent_id` 批量获取 Agent 详情，用于 Info 模式卡片渲染。当前业务场景下通常为单个 ID，接口统一按数组返回以兼容后续多 Agent 扩展 |
| 请求方式 | `POST` |
| 请求 URL | `{apiPrefix}/agent/v1/agent/batch/` |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Body 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `ids` | `string[]` | 是 | 分析规则中的 `agent_id`，当前为单个 ID |

**请求示例：**

```http
POST /agent/v1/agent/batch/ HTTP/1.1
x-space-id: xxx
Content-Type: application/json

{
  "ids": ["agent-xxx"]
}
```

**响应参数：**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `string \| number` | 状态码 |
| `data` | `IAgent[]` | Agent 详情列表 |
| `message` | `string` | 提示信息 |

**响应示例：**

```json
{
  "code": "success",
  "data": [
    {
      "id": "agent-xxx",
      "agent_code": "code-analyzer",
      "agent_name": "代码分析助手",
      "agent_type": "single",
      "generate_type": "space",
      "is_public": false,
      "icon": "icon-robot",
      "description": "用于源码分析的 Agent",
      "status": "ready",
      "version": "1.0.0",
      "latest_version": "1.0.0",
      "agent_url": "https://example.com/agent/1",
      "download_url": "https://example.com/agent/1/download",
      "tenant_id": "tenant-1",
      "from_paas": false,
      "space_id": "space-1",
      "created_by": "admin",
      "created_at": "2026-01-01T00:00:00Z",
      "updated_by": "admin",
      "updated_at": "2026-08-01T00:00:00Z",
      "permission": {
        "view_agent": true,
        "use_agent": true
      },
      "conversation_settings": {
        "commands": [
          {
            "id": "cmd-1",
            "name": "代码分析",
            "icon": "icon-code",
            "content": "请分析当前代码",
            "agent_id": "agent-xxx",
            "agent_name": "代码分析助手"
          }
        ]
      }
    }
  ],
  "message": "ok"
}
```

---

### 3.2 Knowledgebase 卡片

#### 3.2.1 批量获取 Knowledgebase 详情 ⭐

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 根据分析规则返回的 `knowledge_base_ids` 批量获取知识库详情，用于 Info 模式卡片渲染 |
| 请求方式 | `POST` |
| 请求 URL | `{apiPrefix}/knowledgebase/v1/knowledgebase/batch/` |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Body 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `ids` | `string[]` | 是 | 分析规则中的 `knowledge_base_ids` |

**请求示例：**

```http
POST /knowledgebase/v1/knowledgebase/batch/ HTTP/1.1
x-space-id: xxx
Content-Type: application/json

{
  "ids": ["kb-1", "kb-2"]
}
```

**响应参数：**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `string \| number` | 状态码 |
| `data` | `IKnowledgebase[]` | 知识库详情列表 |
| `message` | `string` | 提示信息 |

**响应示例：**

```json
{
  "code": "success",
  "data": [
    {
      "id": "kb-1",
      "knowledgebase_id": "kb-1",
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
  "message": "ok"
}
```

---

### 3.3 Skill 卡片

#### 3.3.1 批量获取 Skill 详情 ⭐

| 项目 | 内容 |
| --- | --- |
| 接口说明 | 根据分析规则返回的 `skill_ids` 批量获取 Skill 详情，用于 Info 模式卡片渲染 |
| 请求方式 | `POST` |
| 请求 URL | `{apiPrefix}/skill/v1/skill/batch/` |

**请求头：**

```http
x-space-id: {spaceId}
Content-Type: application/json
```

**Body 参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `ids` | `string[]` | 是 | 分析规则中的 `skill_ids` |

**请求示例：**

```http
POST /skill/v1/skill/batch/ HTTP/1.1
x-space-id: xxx
Content-Type: application/json

{
  "ids": ["skill-1", "skill-2"]
}
```

**响应参数：**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `string \| number` | 状态码 |
| `data` | `ISkill[]` | Skill 详情列表 |
| `message` | `string` | 提示信息 |

**响应示例：**

```json
{
  "code": "success",
  "data": [
    {
      "id": "skill-1",
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
      "is_public": false,
      "description": "用于代码审查的 Skill",
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
  "message": "ok"
}
```

---

## 四、数据结构约定

### 4.1 Agent 数据结构 `IAgent`

```ts
interface IAgent extends IResourceCommon {
  agent_code: string;
  agent_name: string;
  agent_type: AgentType; // single / flow
  icon: string;
  description: string;
  status: ResourceStatus;
  version: string;
  latest_version: string;
  agent_url: string;
  download_url: string;
  tenant_id: string;
  from_paas: boolean;
  conversation_settings?: {
    commands?: IAgentCommand[];
  };
}

interface IAgentCommand {
  id: string;
  name: string;
  icon?: string;
  content: string | null;
  agent_id: string;
  agent_name: string;
}

interface IResourceCommon {
  id: string;
  generate_type: EnumCharacter; // all / system / user / public / space
  is_public: boolean;
  space_id?: string;
  created_by: string;
  created_at: string;
  updated_by: string;
  updated_at: string;
  permission: IResourcePermission;
}
```

**Info 模式下需要后端对齐的关键字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `string` | Agent 唯一标识 |
| `agent_code` | `string` | Agent 编码 |
| `agent_name` | `string` | Agent 名称 |
| `agent_type` | `AgentType` | `single` / `flow` |
| `status` | `ResourceStatus` | `ready` / `deleted` / `no_permission` / `permission-pending` |
| `version` / `latest_version` | `string` | 当前版本与最新版本 |
| `agent_url` | `string` | 发布后的访问地址 |
| `download_url` | `string` | 下载地址 |
| `permission` | `IResourcePermission` | 权限对象 |
| `conversation_settings.commands` | `IAgentCommand[]` | 快捷指令列表 |

---

### 4.2 Knowledgebase 数据结构 `IKnowledgebase`

```ts
interface IKnowledgebase {
  id: string;
  knowledgebase_id: string;
  knowledgebase_code: string;
  name: string;
  file_path: string;
  file_name: string;
  file_type: string;
  status: ResourceStatus;
  generate_type: EnumCharacter;
  is_public: boolean;
  description: string;
  space_id?: string;
  updated_by: string;
  updated_at: string;
  permission: IResourcePermission;
}
```

**Info 模式下需要后端对齐的关键字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` / `knowledgebase_id` | `string` | 知识库 ID（需与后端确认语义区别） |
| `knowledgebase_code` | `string` | 知识库编码 |
| `name` | `string` | 知识库名称 |
| `file_path` / `file_name` / `file_type` | `string` | 文件路径与元信息 |
| `status` | `ResourceStatus` | 资源状态 |
| `permission` | `IResourcePermission` | 权限对象 |

---

### 4.3 Skill 数据结构 `ISkill`

```ts
interface ISkill extends IResourceCommon {
  skill_code: string;
  skill_name: string;
  icon?: string;
  url: string;
  file_name: string;
  file_size: number;
  file_type: string;
  version: string;
  latest_version: string;
  status: SkillStatus;
  latest_status: SkillStatus;
  scanner?: ISkillScanner;
  envs?: ISkillEnv[];
  bkai_dependencies?: { envs?: ISkillEnv[]; };
}

interface ISkillScanner {
  effective_status: string; // pass / fail / error
  effective_status_cn: string;
  last_scan_at: string;
  report_content: string;
}

interface ISkillEnv {
  key: string;
  description: string;
  required: boolean;
  default: string;
  secret: boolean;
  value?: string;
}
```

**Info 模式下需要后端对齐的关键字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `string` | Skill 唯一标识 |
| `skill_code` | `string` | Skill 编码 |
| `skill_name` | `string` | Skill 名称 |
| `status` / `latest_status` | `SkillStatus` | 状态枚举 |
| `version` / `latest_version` | `string` | 版本语义 |
| `url` | `string` | Skill 文件地址 |
| `file_name` / `file_size` / `file_type` | `string / number` | 文件元信息 |
| `scanner` | `ISkillScanner` | 安全扫描结果 |
| `envs` | `ISkillEnv[]` | 环境变量，影响右上角配置图标展示 |
| `bkai_dependencies.envs` | `ISkillEnv[]` | 依赖的环境变量 |

---

### 4.4 公共类型

```ts
interface IResourcePermission {
  view_agent?: boolean;
  use_agent?: boolean;
  create_agent?: boolean;
  manage_agent?: boolean;
  view_knowledgebase?: boolean;
  use_knowledgebase?: boolean;
  create_knowledgebase?: boolean;
  manage_knowledgebase?: boolean;
  create_skill?: boolean;
  manage_skill?: boolean;
}

type ResourceStatus = 'ready' | 'deleted' | 'no_permission' | 'permission-pending';
type SkillStatus = 'online' | 'offline' | 'deleted' | 'no_permission' | 'permission-pending';
type AgentType = 'single' | 'flow';
type EnumCharacter = 'all' | 'system' | 'user' | 'public' | 'space';
```

---

## 五、事件回调约定

Info 模式下，删除、查看、环境变量保存等操作均通过事件回传宿主页面，由宿主页面决定是否调用接口。

### 5.1 Agent 卡片事件

| 事件 | 参数 | 触发时机 |
| --- | --- | --- |
| `delete` | `(agent: IAgent)` | 点击右上角删除图标时 |

### 5.2 Knowledgebase 卡片事件

| 事件 | 参数 | 触发时机 |
| --- | --- | --- |
| `delete` | `(knowledgebase: IKnowledgebase)` | 点击右上角删除图标时 |
| `view` | `(knowledgebase: IKnowledgebase)` | 点击可查看图标时 |

### 5.3 Skill 卡片事件

| 事件 | 参数 | 触发时机 |
| --- | --- | --- |
| `delete` | `()` | 点击右上角删除图标时 |
| `view` | `(skill: ISkill)` | 点击查看时 |
| `update:skill` | `(skill: ISkill)` | 环境变量配置弹窗确认后 |
| `show-scanner` | `(content: string)` | 点击安全扫描标签时 |

---

## 六、接口汇总表

| 模块 | 路径 | 方法 | 用途 | 对应卡片 |
| --- | --- | --- | --- | --- |
| agent | `/agent/v1/agent/batch/` | POST | ⭐ 根据 `agent_id` 批量获取 Agent 详情 | AgentCard |
| knowledgebase | `/knowledgebase/v1/knowledgebase/batch/` | POST | ⭐ 根据 `knowledge_base_ids` 批量获取知识库详情 | KnowledgebaseCard |
| skill | `/skill/v1/skill/batch/` | POST | ⭐ 根据 `skill_ids` 批量获取 Skill 详情 | SkillCard |

---

## 七、待后端确认问题

1. `apiPrefix` 在当前项目的实际取值是否统一为空字符串 `''`，还是由后端网关统一为 `/api/ai`？
2. Agent 批量详情接口的 URL、参数名 `ids` 及返回结构 `IAgent[]` 是否可接受？是否需改为 `GET /agent/v1/agent/{agentId}/` 单条查询？
3. Knowledgebase 批量接口的 URL、参数名 `ids` 及返回结构 `IKnowledgebase[]` 是否可接受？是否需改为 `POST /knowledgebase/v1/knowledgebase/list/` 并支持 `id` 过滤？
4. Skill 批量接口的 URL、参数名 `ids` 及返回结构 `ISkill[]` 是否可接受？是否需改为 `GET /skill/v1/skill/?id=...` 单条查询？
5. `ResourceStatus` 与 `SkillStatus` 的完整枚举值及状态机是否已文档化？
6. `IResourcePermission` 的完整字段及每个字段对应的鉴权规则是什么？
8. `IAgent.id`、`IKnowledgebase.id` / `knowledgebase_id`、`ISkill.id` 的命名规则是否确定？
9. `scanner.effective_status` 的枚举值与判定条件是否只包含 `pass` / `fail` / `error`？
10. 知识库在 Info 模式下是否需要返回 `url` 字段用于查看跳转？当前文档未强制要求。

---

## 八、相关文档

- [资源卡片使用说明](./ai-ui-sdk-card-usage.md)
- [卡片后端对齐文档](./ai-ui-sdk-backend-alignment.md)
- [资源选择弹窗后端接口文档](./ai-ui-sdk-resource-dialog-api-doc.md)
