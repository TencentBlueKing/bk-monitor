# AI UI SDK 资源选择弹窗（RenderResourceDialog）后端对接文档

> 版本：`@blueking/ai-ui-sdk 0.4.1-beta.19`
> 使用范围：`analysis-config-sideslider.tsx` 中仅使用 **Agent / Knowledgebase / Skill** 三种资源模块
> 配套文件：[组件使用说明](./ai-ui-sdk-resource-dialog-usage.md)
>
> 本文档用于前端与后端就资源选择弹窗的接口、数据结构和交互约定进行对齐评估与开发。

---

## 一、背景与目的

### 1.1 业务场景

在 `analysis-config-sideslider`（源码分析配置侧弹窗）中，用户需要为源码分析规则配置三类资源：

- **Agent（智能体）**：用于执行源码分析任务
- **Knowledgebase（知识库）**：用于提供分析所需的领域知识
- **Skill（技能）**：用于扩展分析能力

### 1.2 组件作用

`RenderResourceDialog` 是 `@blueking/ai-ui-sdk` 提供的通用资源选择弹窗，支持：

- 按资源模块浏览、搜索、勾选
- 按空间筛选资源
- 在右侧「选择结果」面板集中展示已选内容
- 通过 `confirm` 事件将选中的资源一次性回传给宿主

### 1.3 对接目标

明确组件运行时依赖的接口、数据结构和交互约定，帮助后端一次性评估并开发所需接口。

---

## 二、组件运行时依赖的最小 props 清单

> 以下属性为 `RenderResourceDialog` 在实际运行时必定会使用到的配置。后端同学可通过此清单快速了解：组件内部哪些行为依赖外部传入的配置，以及这些配置与后续接口约定的关系。
> 当前项目仅使用 **Agent / Knowledgebase / Skill** 三种资源模块，故下表已按该范围精简。

### 2.1 必传属性

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `isShow` | `boolean` | 是否展示弹窗 |
| `module` | `Module` | 当前资源模块；当前项目取值：`Module.Agent` / `Module.Knowledgebase` / `Module.Skill` |
| `spaceId` | `string` | 当前空间 ID，所有内部请求都会以 `x-space-id` 请求头带上 |
| `memberUrl` | `string` | 成员搜索 URL（完整地址，组件不再拼接 `apiPrefix`） |
| `username` | `string` | 当前用户名，用于「我的/全部」筛选 |
| `spaces` | `ISpace[]` | 空间列表，用于左侧空间栏展示空间名称 |
| `apiPrefix` | `string` | 接口前缀；组件内部所有 HTTP 请求都会基于此拼接 URL |

### 2.2 按模块传入的已选资源（回显用）

| 属性 | 类型 | 使用场景 |
| --- | --- | --- |
| `agents` | `IAgent[]` | `module === Module.Agent` |
| `knowledgebases` | `IKnowledgebase[]` | `module === Module.Knowledgebase` |
| `skills` | `ISkill[]` | `module === Module.Skill` |

### 2.3 常用可选属性

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `title` | `string` | `''` | 弹窗标题 |
| `multiple` | `boolean` | `false` | 是否支持多选；当前项目三种资源均多选 |
| `showSpace` | `boolean` | `false` | 是否展示左侧空间筛选栏 |
| `showGenerateType` | `boolean` | `false` | 是否展示生成类型标签 |
| `showTagSearch` | `boolean` | `false` | 是否展示标签搜索 |
| `canApply` | `boolean` | `false` | 是否「可申请资源」模式 |
| `agentId` | `number` | — | 选择 Agent 时排除自身 |
| `agentType` | `AgentType` | — | 关联智能体类型（`single` / `flow`），用于 Agent 列表过滤 |
| `defaultIcon` | `string` | — | 默认图标 |

### 2.4 事件

| 事件 | 参数 | 触发时机 |
| --- | --- | --- |
| `update:isShow` | `(isShow: boolean)` | 关闭弹窗时 |
| `confirm` | `({ agents, knowledgebases, skills })` | 点击「确定」提交时 |
| `navigate` | `(value: ISdkNavigateAction)` | 点击「去添加」「去申请」等需要外部路由跳转时 |

---

## 三、接口通用约定

### 3.1 URL 拼接规则

组件内部所有请求基于同一个 `apiPrefix` 拼接，最终格式统一为：

```text
{apiPrefix}/{module}/{version}/{resource}/
```

**当前项目涉及的接口示例：**

| apiPrefix | 完整路径 |
| --- | --- |
| `''` | `/agent/v1/agent/` |
| `''` | `/agent/v1/agent/count/` |
| `''` | `/knowledgebase/v1/knowledgebase/list/` |
| `''` | `/knowledgebase/v1/knowledgebase/count/` |
| `''` | `/skill/v1/skill/` |
| `''` | `/skill/v1/skill/count/` |

> 若实际网关需要统一前缀（如 `/api/ai`），则最终路径为 `/api/ai/agent/v1/agent/` 等。
>
> **注意**：`memberUrl` 是完整 URL，组件内部不会再拼接 `apiPrefix`。

### 3.2 请求头

所有内部请求自动携带：

```http
x-space-id: {spaceId}
```

### 3.3 响应结构约定

组件内置 fetch 的成功拦截器要求接口返回：

```json
{
  "code": "success" | 0,
  "data": { ... },
  "message": "..."
}
```

只有 `code` 为 `"success"` 或 `0` 时，组件才会消费 `data`。

### 3.4 分页参数约定

组件内部统一使用驼峰命名，实际发送到后端的参数会转换为下划线命名：

| 组件内字段 | 后端字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| `page` | `page` | `number` | 当前页码 |
| `pageSize` | `page_size` | `number` | 每页条数 |

---

## 四、组件依赖的接口清单

### 4.1 Agent 模块接口

| 触发条件 | 完整路径 | 方法 | 用途 |
| --- | --- | --- | --- |
| 加载列表 / 滚动加载 | `{apiPrefix}/agent/v1/agent/` | GET | 拉取 Agent 列表 |
| 空间列表计数 | `{apiPrefix}/agent/v1/agent/count/` | POST | 按空间统计 Agent 数量 |
| 空间全选 | `{apiPrefix}/agent/v1/agent/` | GET | 拉取某空间下全部 Agent（单次 `pageSize` 取最大值） |

#### Agent 列表请求参数

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

#### Agent 计数接口请求参数

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

---

### 4.2 Knowledgebase 模块接口

| 触发条件 | 完整路径 | 方法 | 用途 |
| --- | --- | --- | --- |
| 加载列表 / 滚动加载 | `{apiPrefix}/knowledgebase/v1/knowledgebase/list/` | POST | 拉取知识库列表 |
| 空间列表计数 | `{apiPrefix}/knowledgebase/v1/knowledgebase/count/` | POST | 按空间统计知识库数量 |
| 空间全选 | `{apiPrefix}/knowledgebase/v1/knowledgebase/list/` | POST | 拉取某空间下全部知识库 |

#### Knowledgebase 列表请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | `number` | 否 | 页码 |
| `page_size` | `number` | 否 | 每页条数 |
| `group_type` | `GroupType` | 否 | — |
| `space_id` | `string` | 否 | — |
| `can_apply` | `boolean` | 否 | — |
| `with_private` | `boolean` | 否 | — |
| `created_by` | `string` | 否 | — |
| `fuzzy` | `string` | 否 | — |
| `anchor_paths` | `string[]` | 否 | — |
| `anchor_path` | `string` | 否 | — |
| `filter_link` | `boolean` | 否 | — |
| `hidden_files` | `boolean` | 否 | — |
| `name` | `string` | 否 | — |
| `knowledgebase_code` | `string` | 否 | — |
| `id` | `number` | 否 | — |
| `without_children` | `boolean` | 否 | — |
| `description` | `string` | 否 | — |
| `updated_by` | `string` | 否 | — |

#### Knowledgebase 计数接口请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `space_ids` | `string[]` | 是 | 包含 `all` 和具体空间 ID |
| `can_apply` | `boolean` | 否 | — |
| `with_private` | `boolean` | 否 | — |
| `group_type` | `GroupType` | 否 | — |
| `created_by` | `string` | 否 | — |

---

### 4.3 Skill 模块接口

| 触发条件 | 完整路径 | 方法 | 用途 |
| --- | --- | --- | --- |
| 加载列表 / 滚动加载 | `{apiPrefix}/skill/v1/skill/` | GET | 拉取 Skill 列表 |
| 空间列表计数 | `{apiPrefix}/skill/v1/skill/count/` | POST | 按空间统计 Skill 数量 |
| 空间全选 | `{apiPrefix}/skill/v1/skill/` | GET | 拉取某空间下全部 Skill |

#### Skill 列表请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | `number` | 否 | 页码 |
| `page_size` | `number` | 否 | 每页条数 |
| `group_type` | `GroupType` | 否 | — |
| `space_id` | `string` | 否 | — |
| `can_apply` | `boolean` | 否 | — |
| `with_private` | `boolean` | 否 | — |
| `created_by` | `string` | 否 | — |
| `generate_type` | `EnumCharacter` | 否 | — |
| `fuzzy` | `string` | 否 | — |
| `skill_name` | `string` | 否 | — |
| `skill_code` | `string` | 否 | — |
| `description` | `string` | 否 | — |
| `updated_by` | `string` | 否 | — |
| `status` | `SkillStatus` | 否 | — |

#### Skill 计数接口请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `space_ids` | `string[]` | 是 | 包含 `all` 和具体空间 ID |
| `can_apply` | `boolean` | 否 | — |
| `with_private` | `boolean` | 否 | — |
| `group_type` | `GroupType` | 否 | — |
| `created_by` | `string` | 否 | — |

---

### 4.4 成员搜索接口

| 触发条件 | 完整路径 | 方法 | 用途 |
| --- | --- | --- | --- |
| 搜索框选人 | `{memberUrl}` | GET | 获取成员列表 |

---

## 五、数据结构约定

### 5.1 公共结构

#### IResourceCommon

```ts
interface IResourceCommon<T = ResourceStatus> {
  id: number;
  createdBy: string;
  createdAt: string;
  updatedBy: string;
  updatedAt: string;
  status?: T;
  spaceId?: string;
  approvers?: string[];
  ticketUrl?: string;
  permission: IResourcePermission;
}
```

后端字段（下划线命名）：`id`, `created_by`, `created_at`, `updated_by`, `updated_at`, `status`, `space_id`, `approvers`, `ticket_url`, `permission`。

#### IResourceFormCommon

```ts
interface IResourceFormCommon {
  tagNames: string[][];
  generateType: EnumCharacter; // all / system / user / public / space
  isPublic: boolean;
  description: string;
}
```

后端字段：`tag_names`, `generate_type`, `is_public`, `description`。

#### IResourcePermission

```ts
interface IResourcePermission {
  viewAgent?: boolean;
  useAgent?: boolean;
  createAgent?: boolean;
  manageAgent?: boolean;
  viewKnowledgebase?: boolean;
  useKnowledgebase?: boolean;
  createKnowledgebase?: boolean;
  manageKnowledgebase?: boolean;
  createSkill?: boolean;
  manageSkill?: boolean;
}
```

后端字段：`view_agent`, `use_agent`, `create_agent`, `manage_agent`, `view_knowledgebase`, `use_knowledgebase`, `create_knowledgebase`, `manage_knowledgebase`, `create_skill`, `manage_skill` 等。

---

### 5.2 Agent 响应结构

```ts
interface IAgent extends IAgentForm, IResourceCommon {
  version: string;
  latestVersion: string;
  agentUrl: string;
  appCode?: string;
  downloadUrl: string;
  tenantId: string;
  fromPaas: boolean;
  refCount?: number;
}

interface IAgentForm extends IResourceFormCommon {
  agentCode: string;
  agentName: string;
  icon: string;
  agentType: AgentType; // single / flow
  userGuide: string;
  isBindBkSaas: boolean;
  isBindCredential?: boolean;
  deployMode?: AgentDeployMode;
  userScope?: UserScope;
  flowSetting?: { flowId: number; flowVersion: string; isThirdPluginEnabled: boolean };
  conversationSettings?: {
    openingRemark: string;
    predefinedQuestions: string[];
    commands?: IAgentCommand[];
    enableChatSession: boolean;
    enableWordSelectionPopup: boolean;
  };
  intentRecognition?: { knowledges: IKnowledge[]; topk: number; llmCode?: string };
  promptSetting?: {
    promptType?: PromptSource;
    promptContent?: string;
    collectionId: number;
    collectionName?: string;
    collectionVariables?: IVariable[];
    collectionContent?: IContent[];
    llmCode: string;
    fallbackModel?: string;
    temperature?: number;
    contextWindow?: number;
    llmTokenLimit?: number;
    maxTokens?: number;
    toolOutputCompressThrd?: number;
  };
  knowledgebaseSettings?: { knowledgebases: IKnowledgebase[] } & IKnowledgeQuerySetting;
  relatedTools?: { tools: ITool[]; mcps: IMcp[] };
  relatedSkills?: { skills: ISkill[] };
  relatedAgents?: { agents: IAgent[] };
  businessIds?: number[];
  approvalSettings?: IApprovalSetting[];
}
```

**关键字段说明：**

| 字段 | 说明 |
| --- | --- |
| `id` | 资源唯一标识 |
| `status` | `ready` / `deleted` / `no_permission` / `permission-pending` |
| `version` / `latest_version` | 当前版本与最新版本 |
| `agent_url` | 智能体访问地址 |
| `ref_count` | 引用量 |
| `permission` | 权限对象 |
| `agent_type` | `single` / `flow` |
| `generate_type` | `all` / `system` / `user` / `public` / `space` |

---

### 5.3 Knowledgebase 响应结构

```ts
interface IKnowledgebase {
  id?: number;
  knowledgebaseId?: number;
  knowledgebaseCode: string;
  spaceId?: string;
  anchorPath?: string;
  parentAnchorPath?: string;
  filePath: string;
  fileName?: string;
  fileType?: string;
  pipelineCodes?: IKnowledgePipelineCodes;
  updateFrequency?: number;
  name: string;
  type?: KnowledgebaseType; // default / intent_recog
  status?: ResourceStatus;
  approvers?: string[];
  ticketUrl?: string;
  generateType?: EnumCharacter;
  isPublic?: boolean;
  pathType?: KnowledgePathType;
  createdType?: KnowledgeType;
  number?: number;
  description?: string;
  folderNumber?: number;
  url?: string;
  updatedBy?: string;
  updatedAt?: string;
  indexConfig?: IKnowledgeIndexConfig;
  permission?: IResourcePermission;
  children?: Array<IKnowledgebase>;
}
```

**关键字段说明：**

| 字段 | 说明 |
| --- | --- |
| `id` / `knowledgebase_id` | 知识库 ID，需确认两个字段语义区别 |
| `knowledgebase_code` | 知识库编码 |
| `file_path` | 文件路径 |
| `status` | 资源状态 |
| `url` | 查看地址 |
| `permission` | 权限对象 |
| `children` | 子知识库列表 |
| `generate_type` | 生成类型 |

---

### 5.4 Skill 响应结构

```ts
interface ISkill extends ISkillForm, IResourceCommon<SkillStatus> {
  latestStatus?: SkillStatus; // publishing / published / online / failed / deleted
  latestVersion?: string;
  skillMarkdown?: string;
  downloadCount?: number;
  installCount?: number;
  refCount?: number;
  scanner?: ISkillScanner;
  envs?: ISkillEnv[];
  bkaiDependencies?: { envs?: ISkillEnv[] };
}

interface ISkillForm extends IResourceFormCommon {
  skillName: string;
  skillCode: string;
  icon?: string;
  url: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  version?: string;
}

interface ISkillScanner {
  effectiveStatus: string; // pass / fail / error
  effectiveStatusCn: string;
  lastScanAt: string;
  reportContent: string;
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

**关键字段说明：**

| 字段 | 说明 |
| --- | --- |
| `id` | 资源唯一标识 |
| `status` / `latest_status` | Skill 状态 |
| `version` / `latest_version` | 版本语义 |
| `url` | Skill 文件地址 |
| `download_count` / `install_count` / `ref_count` | 统计数据 |
| `scanner` | 安全扫描结果 |
| `envs` | 环境变量 |
| `bkai_dependencies.envs` | 依赖的环境变量 |

---

## 六、建议后端对齐清单

### 6.1 接口通用约定

| 对齐项 | 说明 |
| --- | --- |
| `apiPrefix` 取值 | 当前项目侧弹窗传空字符串 `''`，是否统一为 `/api/ai` 或其他前缀 |
| 统一响应结构 | `{ code, data, message }`，`code` 成功值是否为 `"success"` 或 `0` |
| 错误码规范 | 权限不足、资源不存在、参数错误等场景的错误码 |
| 请求头规范 | `x-space-id` 是否必须、是否还有其他自定义头 |
| 鉴权方式 | Cookie / Token / 其他，以及权限不足时的返回行为 |
| 字段命名规范 | 后端使用下划线还是驼峰（SDK 转换器目前默认下划线） |

### 6.2 资源状态与状态机

| 对齐项 | 说明 |
| --- | --- |
| `ResourceStatus` 定义 | `ready` / `deleted` / `no_permission` / `permission-pending` 的完整定义 |
| `SkillStatus` 定义 | `publishing` / `published` / `online` / `failed` / `deleted` 的完整定义 |
| 状态流转 | 哪些操作会导致状态变更 |
| 列表过滤 | `is_published` / `status` 等过滤条件是否生效 |

### 6.3 权限模型

| 对齐项 | 说明 |
| --- | --- |
| `IResourcePermission` 完整字段 | Agent / Knowledgebase / Skill 各自的权限字段是否完整 |
| 权限与 UI 映射 | 哪些权限控制哪些操作（如 `use_agent` 控制能否选择） |
| 数据权限 | 公共空间 / 个人空间 / 授权空间的资源可见性规则 |
| `is_public` 与 `generate_type` | 公共、空间、个人资源的划分规则 |

### 6.4 空间与多租户

| 对齐项 | 说明 |
| --- | --- |
| `space_id` 来源 | 从 URL、用户信息还是接口返回获取 |
| `spaces` 列表 | 用于展示空间名称的数据来源 |
| 跨空间资源 | Agent / Knowledgebase / Skill 是否允许跨空间关联 |
| `space_ids` 包含 `all` | 计数接口中 `all` 代表全部空间，后端是否支持 |

### 6.5 分页与搜索

| 对齐项 | 说明 |
| --- | --- |
| 分页字段 | `page` / `page_size` 是否都支持 |
| 默认分页大小 | 首次加载和滚动加载的 `page_size` 默认值 |
| 搜索参数 | `fuzzy` 的匹配范围（名称/编码/描述） |
| 排序参数 | `order_by` / `order_method` 支持的字段 |

---

## 七、缺失资源与待确认清单

### 7.1 完全缺失接口定义的资源

以下资源当前文档中只提到调用场景，但**尚未明确接口的 URL、请求参数或响应结构**，需要后端从零补齐。

| 缺失资源 | 当前文档中的引用位置 | 需要补齐的内容 |
| --- | --- | --- |
| **空间列表接口** | 第二章 `spaces` props、第六章「空间与多租户」 | 空间列表的数据来源是什么？是单独接口还是由宿主注入？若是接口，需提供 URL、方法、请求参数、响应结构 |
| **成员搜索 URL 接口** | 第二章 `memberUrl` props、第四章 4.4 | `memberUrl` 的完整请求参数（关键字、分页）、响应结构（用户 ID / 用户名 / 头像等字段）、`apiPrefix` 是否需要拼接 |
| **资源申请接口** | 配套使用文档中提到 `agent_resource_apply` | 是否需要在本对接文档中补充？URL、方法、请求体、响应结构 |

### 7.2 已有接口路径但需后端确认详细语义

以下接口在第四章已给出路径模板，但**请求参数、响应字段、过滤行为、状态码约定等细节仍需后端确认或补齐**。

| 待确认接口 | 当前文档中的路径 | 需要确认的内容 |
| --- | --- | --- |
| **Agent 模块列表接口** | `{apiPrefix}/agent/v1/agent/` | GET 参数是否完全支持第四章所列字段；`is_published`、`exclude_agent_id`、`agent_type` 是否后端已实现；响应字段与 `IAgent` 的映射关系 |
| **Agent 模块列表计数接口** | `{apiPrefix}/agent/v1/agent/count/` | 请求方法（GET 或 POST）；`space_ids` 含 `all` 时的返回规则；是否支持按空间明细返回 |
| **Knowledgebase 模块列表接口** | `{apiPrefix}/knowledgebase/v1/knowledgebase/list/` | 请求方法（GET 或 POST）；`id` 与 `knowledgebase_id` 的返回规则；`anchor_paths`、`anchor_path`、`filter_link` 等参数含义 |
| **Knowledgebase 模块列表计数接口** | `{apiPrefix}/knowledgebase/v1/knowledgebase/count/` | 请求方法；`space_ids` 含 `all` 时的返回规则 |
| **Skill 模块列表接口** | `{apiPrefix}/skill/v1/skill/` | GET 参数是否完全支持第四章所列字段；`status` 是否支持多选；是否包含 `latest_status`；响应字段与 `ISkill` 的映射关系 |
| **Skill 模块列表计数接口** | `{apiPrefix}/skill/v1/skill/count/` | 请求方法；`space_ids` 含 `all` 时的返回规则 |

### 7.3 通用约定与行为待确认

| 待确认项 | 说明 |
| --- | --- |
| `apiPrefix` 实际取值 | 当前项目侧弹窗传空字符串 `''`，是否统一为 `/api/ai` 或其他前缀？ |
| 字段命名规范 | 后端使用下划线还是驼峰？是否需要 SDK 转换器覆盖额外字段？ |
| `ResourceStatus` 与 `SkillStatus` 完整定义 | `ready` / `deleted` / `no_permission` / `permission-pending` 以及 `publishing` / `published` / `online` / `failed` / `deleted` 的状态机是否已文档化？ |
| ID 命名规则 | `IAgent.id`、`IKnowledgebase.id` / `knowledgebase_id`、`ISkill.id` 的命名规则是否确定？ |
| 空间全选行为 | 全选时单次 `pageSize` 最大值是多少？后端是否支持无分页拉取某空间下全部资源？ |

---

## 八、附录：接口汇总表

| 模块 | 路径 | 方法 | 用途 |
| --- | --- | --- | --- |
| agent | `{apiPrefix}/agent/v1/agent/` | GET | 拉取 Agent 列表 |
| agent | `{apiPrefix}/agent/v1/agent/count/` | POST | 按空间统计 Agent 数量 |
| knowledgebase | `{apiPrefix}/knowledgebase/v1/knowledgebase/list/` | POST | 拉取知识库列表 |
| knowledgebase | `{apiPrefix}/knowledgebase/v1/knowledgebase/count/` | POST | 按空间统计知识库数量 |
| skill | `{apiPrefix}/skill/v1/skill/` | GET | 拉取 Skill 列表 |
| skill | `{apiPrefix}/skill/v1/skill/count/` | POST | 按空间统计 Skill 数量 |
| common | `{memberUrl}` | GET | 获取成员列表 |
