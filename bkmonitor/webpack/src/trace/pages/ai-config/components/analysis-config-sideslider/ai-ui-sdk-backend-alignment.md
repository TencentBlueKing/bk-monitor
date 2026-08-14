# AI UI SDK 卡片（Info 模式）后端对齐文档

> 基于 [`ai-ui-sdk-card-usage.md`](./ai-ui-sdk-card-usage.md) 整理，用于前端与后端就 `@blueking/ai-ui-sdk` Info 模式卡片能力进行接口与数据对齐。
> 版本：`@blueking/ai-ui-sdk 0.4.1-beta.19`

---

## 一、卡片组件类型与使用场景

| 卡片组件                  | 对应资源                | 主要使用场景                                                 |
| ------------------------- | ----------------------- | ------------------------------------------------------------ |
| `RenderAgentCard`         | Agent（智能体）         | 展示智能体信息、快捷指令、删除/恢复、关联至智能体            |
| `RenderKnowledgebaseCard` | Knowledgebase（知识库） | 展示知识库信息、查看、删除、关联至智能体                     |
| `RenderSkillCard`         | Skill（技能）           | 展示 Skill 信息、环境变量配置、下载、删除/恢复、关联至智能体 |

所有卡片在当前项目均使用 `ResourceCardType.Info` 模式，只读展示 + 右上角操作。

---

## 二、需要后端提供的数据结构

### 2.1 Agent 数据结构 `IAgent`

```ts
interface IAgent extends IAgentForm, IResourceCommon {
  version: string; // 当前版本
  latestVersion: string; // 最新版本
  agentUrl: string; // 访问地址（发布后才有）
  appCode?: string;
  downloadUrl: string;
  tenantId: string;
  fromPaas: boolean;
  refCount?: number; // 引用量，用于引用量图标
}

interface IAgentForm extends IResourceFormCommon {
  agentCode: string;
  agentName: string;
  icon: string;
  agentType: AgentType; // single / flow
  userGuide: string; // 使用文档
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

interface IAgentCommand {
  id: string;
  name: string;
  icon?: string;
  enableFillBack?: boolean;
  fillBackComponentKey?: string;
  fillRegx?: string;
  components: IAgentCommandComponent[];
  content: string | null;
  agentId: number;
  agentName: string;
  status?: ResourceStatus;
  spaceId?: string;
  alias?: string;
  updatedAt?: string;
  updatedBy?: string;
}
```

**需要后端对齐的关键字段：**

| 字段                                                                         | 说明                                                                   | 是否需要后端确认             |
| ---------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------- |
| `id`                                                                         | 资源唯一标识                                                           | 是                           |
| `status`                                                                     | 资源状态：`ready` / `deleted` / `no_permission` / `permission-pending` | 是，需确认状态机             |
| `version` / `latestVersion`                                                  | 当前版本与最新版本语义                                                 | 是                           |
| `agentUrl`                                                                   | 智能体访问地址                                                         | 是，是否由后端生成           |
| `refCount`                                                                   | 引用量，用于展示引用图标                                               | 是，计算逻辑                 |
| `permission`                                                                 | 权限对象                                                               | 是                           |
| `conversationSettings.commands`                                              | 快捷指令列表                                                           | 是                           |
| `relatedAgents` / `relatedSkills` / `relatedTools` / `knowledgebaseSettings` | 关联资源                                                               | 是，是否需要后端在详情中返回 |

### 2.2 Knowledgebase 数据结构 `IKnowledgebase`

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

**需要后端对齐的关键字段：**

| 字段                      | 说明                           | 是否需要后端确认 |
| ------------------------- | ------------------------------ | ---------------- |
| `id` vs `knowledgebaseId` | 两个 ID 字段的语义区别         | 是               |
| `knowledgebaseCode`       | 知识库编码                     | 是               |
| `filePath`                | 文件路径                       | 是               |
| `status`                  | 资源状态                       | 是               |
| `url`                     | 查看地址，点击可查看图标时跳转 | 是               |
| `permission`              | 权限对象                       | 是               |
| `children`                | 子知识库列表                   | 是               |

### 2.3 Skill 数据结构 `ISkill`

```ts
interface ISkill extends ISkillForm, IResourceCommon<SkillStatus> {
  latestStatus?: SkillStatus; // publishing / published / online / failed / deleted
  latestVersion?: string;
  skillMarkdown?: string;
  downloadCount?: number;
  installCount?: number;
  refCount?: number;
  scanner?: ISkillScanner; // 安全扫描结果
  envs?: ISkillEnv[]; // 环境变量，影响右上角配置图标
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

**需要后端对齐的关键字段：**

| 字段                                          | 说明                       | 是否需要后端确认 |
| --------------------------------------------- | -------------------------- | ---------------- |
| `id`                                          | 资源唯一标识               | 是               |
| `status` / `latestStatus`                     | 状态枚举及流转             | 是               |
| `version` / `latestVersion`                   | 版本语义                   | 是               |
| `url`                                         | Skill 文件地址             | 是               |
| `downloadCount` / `installCount` / `refCount` | 统计数据                   | 是，计算逻辑     |
| `scanner`                                     | 安全扫描结果               | 是               |
| `envs`                                        | 环境变量，影响配置图标展示 | 是，保存接口     |
| `bkaiDependencies.envs`                       | 依赖的环境变量             | 是               |

### 2.4 公共类型

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

interface IResourceFormCommon {
  tagNames: string[][];
  generateType: EnumCharacter; // all / system / user / public / space
  isPublic: boolean;
  description: string;
}

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
  // ... 其他权限字段
}
```

**需要后端对齐：**

- `generateType` 枚举值是否完全一致。
- `permission` 字段的完整定义及每个字段的鉴权规则。
- `spaceId` 的取值规则与空间隔离策略。

---

## 三、卡片内部调用的接口清单

所有接口路径基于 `apiPrefix` 拼接，统一格式：

```text
{apiPrefix}/{模块}/{版本}/{资源路径}/
```

所有内部请求自动携带请求头：`x-space-id: {spaceId}`。

### 3.1 Agent 卡片内部接口

| 触发条件                           | 完整路径                                                           | 方法   | 说明                                      | 需要后端确认                   |
| ---------------------------------- | ------------------------------------------------------------------ | ------ | ----------------------------------------- | ------------------------------ |
| 点击归档确认                       | `{apiPrefix}/agent/v1/agent/{agentId}/`                            | DELETE | 归档智能体，成功后 emit `success-delete`  | 路径、参数、返回值             |
| 点击恢复确认                       | `{apiPrefix}/agent/v1/agent/{agentId}/restore/`                    | POST   | 恢复智能体，成功后 emit `success-restore` | 路径、参数、返回值             |
| 点击快捷指令图标                   | `{apiPrefix}/agent/v1/agent/{originAgentId}/get_related_commands/` | GET    | 获取来源智能体可关联到当前卡片的指令      | `originAgentId` 语义、返回结构 |
| 点击引用量                         | `{apiPrefix}/agent/v1/agent/{agentId}/referring_agents/`           | GET    | 获取引用该智能体的智能体列表              | 分页、返回结构                 |
| 关联至智能体弹窗：拉取有权限空间   | `{apiPrefix}/meta/v1/space/authorized_spaces/`                     | GET    | 由 `render-relate-agent` 发起             | 返回结构                       |
| 关联至智能体弹窗：拉取可关联 Agent | `{apiPrefix}/agent/v1/agent/`                                      | GET    | 由 `render-relate-agent` 发起             | 过滤参数、分页、返回结构       |
| 关联至智能体弹窗：保存关联         | `{apiPrefix}/agent/v1/agent/{targetAgentId}/`                      | PUT    | 由 `render-relate-agent` 发起             | 请求体结构、关联字段           |

### 3.2 Knowledgebase 卡片内部接口

`RenderKnowledgebaseCard` 自身不直接调用 HTTP，下列请求由其内部通用子组件 `render-relate-agent` 发起：

| 触发条件                           | 完整路径                                       | 方法 | 需要后端确认             |
| ---------------------------------- | ---------------------------------------------- | ---- | ------------------------ |
| 关联至智能体弹窗：拉取有权限空间   | `{apiPrefix}/meta/v1/space/authorized_spaces/` | GET  | 返回结构                 |
| 关联至智能体弹窗：拉取可关联 Agent | `{apiPrefix}/agent/v1/agent/`                  | GET  | 过滤参数、分页、返回结构 |
| 关联至智能体弹窗：保存关联         | `{apiPrefix}/agent/v1/agent/{targetAgentId}/`  | PUT  | 请求体结构               |

> 注：知识库卡片的“查看”通过 `navigate` 事件由宿主处理，不直接调用接口。

### 3.3 Skill 卡片内部接口

| 触发条件                           | 完整路径                                                 | 方法   | 说明                                                               | 需要后端确认             |
| ---------------------------------- | -------------------------------------------------------- | ------ | ------------------------------------------------------------------ | ------------------------ |
| 点击归档确认                       | `{apiPrefix}/skill/v1/skill/{skillId}/`                  | DELETE | 归档 Skill，成功后 emit `success-delete`                           | 路径、返回值             |
| 点击恢复确认                       | `{apiPrefix}/skill/v1/skill/{skillId}/restore/`          | POST   | 恢复 Skill，成功后 emit `success-restore`                          | 路径、返回值             |
| 点击下载                           | `{apiPrefix}/skill/v1/skill/{skillId}/download/`         | GET    | 下载 Skill，成功后 `window.open(res.url)`，emit `success-download` | `res.url` 生成逻辑       |
| 点击引用量                         | `{apiPrefix}/skill/v1/skill/{skillId}/referring_agents/` | GET    | 获取引用该 Skill 的智能体列表                                      | 分页、返回结构           |
| 关联至智能体弹窗：拉取有权限空间   | `{apiPrefix}/meta/v1/space/authorized_spaces/`           | GET    | 由 `render-relate-agent` 发起                                      | 返回结构                 |
| 关联至智能体弹窗：拉取可关联 Agent | `{apiPrefix}/agent/v1/agent/`                            | GET    | 由 `render-relate-agent` 发起                                      | 过滤参数、分页、返回结构 |
| 关联至智能体弹窗：保存关联         | `{apiPrefix}/agent/v1/agent/{targetAgentId}/`            | PUT    | 由 `render-relate-agent` 发起                                      | 请求体结构               |

---

## 四、建议补充对齐的信息

除了卡片类型、数据结构、接口路径/方法外，建议与后端进一步对齐以下内容：

### 4.1 接口通用约定

| 对齐项           | 说明                                                            |
| ---------------- | --------------------------------------------------------------- |
| `apiPrefix` 取值 | 当前项目传空字符串 `''`，但实际是否统一为 `/api/ai` 或其他前缀  |
| 统一响应结构     | 成功/失败响应格式，如 `{ code, data, message }` 或 RESTful 标准 |
| 错误码规范       | 各接口错误码及含义，特别是权限、资源不存在、版本冲突等          |
| 请求头规范       | `x-space-id` 是否必须、是否还有其他自定义头                     |
| 鉴权方式         | Cookie / Token / 其他，以及权限不足时的返回行为                 |

### 4.2 资源状态与状态机

| 对齐项                | 说明                                                                         |
| --------------------- | ---------------------------------------------------------------------------- |
| `ResourceStatus` 定义 | `ready` / `deleted` / `no_permission` / `permission-pending` 的完整定义      |
| 状态流转              | 哪些操作会导致状态变更（如归档 `ready -> deleted`，恢复 `deleted -> ready`） |
| 删除语义              | `DELETE` 是物理删除还是逻辑归档（当前 SDK 语义为“归档/恢复”）                |
| `SkillStatus` 定义    | `publishing` / `published` / `online` / `failed` / `deleted` 的完整定义      |

### 4.3 权限模型

| 对齐项                         | 说明                                                      |
| ------------------------------ | --------------------------------------------------------- |
| `IResourcePermission` 完整字段 | Agent / Knowledgebase / Skill 各自的权限字段是否完整      |
| 权限与 UI 的映射               | 哪些权限控制哪些按钮展示（如 `manageAgent` 控制删除按钮） |
| 数据权限                       | 公共空间 / 个人空间 / 授权空间的资源可见性规则            |
| `isPublic` 与 `generateType`   | 公共、空间、个人资源的划分规则                            |

### 4.4 关联至智能体弹窗相关接口

| 对齐项                                        | 说明                                                                                    |
| --------------------------------------------- | --------------------------------------------------------------------------------------- |
| `authorized_spaces` 返回字段                  | 空间 ID、名称、权限等                                                                   |
| `agent` 列表查询参数                          | 关键字、分页、空间过滤、资源类型过滤等                                                  |
| `PUT /agent/v1/agent/{targetAgentId}/` 请求体 | 关联关系如何回写（如 `relatedAgents` / `knowledgebaseSettings` / `relatedSkills` 字段） |
| 关联去重/覆盖策略                             | 新增关联是追加还是覆盖                                                                  |

### 4.5 文件与下载

| 对齐项              | 说明                                                        |
| ------------------- | ----------------------------------------------------------- |
| Skill 下载接口响应  | `{ url: string }` 中的 `url` 是临时下载链接还是永久链接     |
| 文件上传/存储       | Skill 文件 `url`、`fileName`、`fileSize`、`fileType` 的来源 |
| Agent `downloadUrl` | 是否同样需要后端生成下载地址                                |

### 4.6 环境变量（Skill）

| 对齐项               | 说明                                                                   |
| -------------------- | ---------------------------------------------------------------------- |
| `envs` 保存接口      | 点击配置图标确认后，数据通过 `update:skill` 回传，是否需要单独保存接口 |
| `secret` 字段        | 敏感环境变量是否加密存储/脱敏展示                                      |
| `default` 与 `value` | 默认值与用户填写值的优先级                                             |

### 4.7 版本与引用

| 对齐项                       | 说明                                       |
| ---------------------------- | ------------------------------------------ |
| `version` 与 `latestVersion` | 当前版本与最新版本的区别，是否支持版本切换 |
| `refCount` 计算              | 引用量统计口径（仅当前空间 / 全部空间）    |
| `referring_agents` 返回      | 列表字段、分页参数                         |

### 4.8 安全扫描

| 对齐项                 | 说明                                  |
| ---------------------- | ------------------------------------- |
| `scanner` 数据来源     | 由哪个服务产生，如何同步到 Skill 详情 |
| `effectiveStatus` 枚举 | `pass` / `fail` / `error` 的判定条件  |
| `reportContent` 格式   | 纯文本 / Markdown / HTML              |

### 4.9 空间与多租户

| 对齐项         | 说明                                             |
| -------------- | ------------------------------------------------ |
| `spaceId` 来源 | 从 URL、用户信息还是接口返回获取                 |
| `spaces` 列表  | 用于展示空间名称的数据来源                       |
| 跨空间资源     | Agent / Knowledgebase / Skill 是否允许跨空间关联 |

### 4.10 事件与回调约定

| 对齐项             | 说明                                                                                                           |
| ------------------ | -------------------------------------------------------------------------------------------------------------- |
| 前端事件           | `delete` / `success-delete` / `success-restore` / `update:commands` / `update:skill` / `navigate` 等的触发时机 |
| 接口成功后刷新策略 | 是由前端主动刷新列表，还是依赖接口返回值更新卡片                                                               |

---

## 五、待确认问题清单

1. `apiPrefix` 在当前项目的实际取值是什么？是否统一由后端网关配置？
2. `IAgent.id`、`IKnowledgebase.id` / `knowledgebaseId`、`ISkill.id` 的命名规则是否确定？
3. `ResourceStatus` 与 `SkillStatus` 的完整枚举值及状态机是否已文档化？
4. `DELETE /agent/v1/agent/{id}/` 与 `DELETE /skill/v1/skill/{id}/` 是物理删除还是逻辑归档？
5. `GET /agent/v1/agent/{originAgentId}/get_related_commands/` 中 `originAgentId` 与当前卡片 `agent.id` 的关系是什么？
6. `GET .../referring_agents/` 返回的数据结构及分页参数是什么？
7. `PUT /agent/v1/agent/{targetAgentId}/` 保存关联时，请求体中关联资源的字段命名是什么？
8. `GET /skill/v1/skill/{skillId}/download/` 返回的 `res.url` 是临时签名链接还是持久链接？
9. Skill 环境变量 `envs` 的保存是走单独的接口还是通过更新 Skill 详情接口？
10. `IResourcePermission` 的完整字段及每个字段对应的鉴权规则是什么？

---

## 六、附录：接口汇总表

| 模块  | 路径                                                    | 方法   | 用途                | 对应卡片                                  |
| ----- | ------------------------------------------------------- | ------ | ------------------- | ----------------------------------------- |
| agent | `/agent/v1/agent/{agentId}/`                            | DELETE | 归档智能体          | AgentCard                                 |
| agent | `/agent/v1/agent/{agentId}/restore/`                    | POST   | 恢复智能体          | AgentCard                                 |
| agent | `/agent/v1/agent/{originAgentId}/get_related_commands/` | GET    | 获取可关联指令      | AgentCard                                 |
| agent | `/agent/v1/agent/{agentId}/referring_agents/`           | GET    | 引用该智能体的列表  | AgentCard                                 |
| agent | `/agent/v1/agent/`                                      | GET    | 拉取可关联 Agent    | AgentCard / KnowledgebaseCard / SkillCard |
| agent | `/agent/v1/agent/{targetAgentId}/`                      | PUT    | 保存关联关系        | AgentCard / KnowledgebaseCard / SkillCard |
| meta  | `/meta/v1/space/authorized_spaces/`                     | GET    | 拉取有权限空间      | AgentCard / KnowledgebaseCard / SkillCard |
| skill | `/skill/v1/skill/{skillId}/`                            | DELETE | 归档 Skill          | SkillCard                                 |
| skill | `/skill/v1/skill/{skillId}/restore/`                    | POST   | 恢复 Skill          | SkillCard                                 |
| skill | `/skill/v1/skill/{skillId}/download/`                   | GET    | 下载 Skill          | SkillCard                                 |
| skill | `/skill/v1/skill/{skillId}/referring_agents/`           | GET    | 引用该 Skill 的列表 | SkillCard                                 |
