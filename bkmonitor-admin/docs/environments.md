# 多环境配置与切换

## 背景

`bkmonitor-admin` 需要管理多套蓝鲸监控平台环境，例如本地开发、测试环境、预发布环境、生产环境，甚至多套独立部署的 bkmonitor。环境切换必须是一等能力，而不是临时修改代理地址或浏览器配置。

## 目标

- 支持配置多个 bkmonitor 环境。
- 支持在页面中切换当前环境。
- 支持环境配置为空时进入初始化引导，而不是默认报错或隐式访问某个环境。
- 每个环境有独立的 API endpoint、鉴权方式和显示标识；租户是运行时上下文，不属于环境连接配置。
- 请求、缓存、审计、历史记录都必须携带环境标识。
- 防止误把生产环境当测试环境操作。第一期只读，但仍需要清晰提示。

## 核心概念

### Environment

环境配置建议包含：

```ts
interface AdminEnvironment {
  id: string;
  name: string;
  description?: string;
  apiBaseUrl: string;
  kernelRpcPath: string;
  gatewayBaseUrl?: string;
  appCode?: string;
  secretKey?: string;
  authMode: 'apigw';
  readonly?: boolean;
  tags?: string[];
  mockFallback?: boolean;
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| id | 稳定环境 ID，例如 `dev`、`stag`、`prod-main` |
| name | 展示名称 |
| description | 环境说明 |
| apiBaseUrl | bkmonitor API 根地址 |
| kernelRpcPath | kernel RPC 路径，通常是 `/api/v4/kernel_rpc/call/` 或 `/app/kernel_rpc/call/` |
| gatewayBaseUrl | APIGW 地址，可选 |
| appCode | APIGW 调用使用的蓝鲸应用 `app_code` |
| secretKey | APIGW 调用使用的应用 `secret_key`，存储在 Admin API 配置库中，由后台代理请求时放入 `X-Bkapi-Authorization` |
| authMode | 鉴权模式；一期固定为 `apigw` |
| readonly | 是否强制只读；一期所有资源操作均为只读，当前主要作为安全标识，后续写操作会用它做前端/Agent 拦截 |
| tags | 环境标签，如 `prod`、`test`、`internal` |
| mockFallback | RPC 请求失败后是否允许回退到本地 mock 数据，默认关闭，仅用于开发演示 |

## 配置来源

一期已支持三类配置来源，优先级从高到低：

### 数据库存储

默认通过本地 Admin API 读写 `/admin-api/config`，并在页面“环境配置”中直接维护环境信息。数据库首次初始化不会自动写入环境，允许配置为空，并由页面引导创建第一个环境。

本地默认使用 SQLite 文件：

```bash
BKMONITOR_ADMIN_DB_CLIENT=sqlite
BKMONITOR_ADMIN_SQLITE_PATH=.data/bkmonitor-admin.sqlite
```

也可以切换到 MySQL：

```bash
BKMONITOR_ADMIN_DB_CLIENT=mysql
BKMONITOR_ADMIN_MYSQL_HOST=127.0.0.1
BKMONITOR_ADMIN_MYSQL_PORT=3306
BKMONITOR_ADMIN_MYSQL_USER=root
BKMONITOR_ADMIN_MYSQL_PASSWORD=
BKMONITOR_ADMIN_MYSQL_DATABASE=bkmonitor_admin
```

Admin API 会自动创建两张表：

- `admin_environments`：按环境 ID 存储完整 JSON payload。
- `admin_settings`：存储默认环境等全局设置。

### 构建时默认配置

当数据库未启动时，前端会回退到内置常用环境：

```ts
export const defaultEnvironments = [
  {
    id: 'local',
    name: '本地开发',
    apiBaseUrl: 'http://localhost:8000',
    kernelRpcPath: '/api/v4/kernel_rpc/call/',
    authMode: 'apigw',
    readonly: true
  }
];
```

### 运行时配置文件

当 Admin API 不可用时，前端还会尝试读取 `/admin-config.json`，适合部署后调整，不需要重新构建：

```json
{
  "environments": [
    {
      "id": "prod-main",
      "name": "生产主环境",
      "apiBaseUrl": "https://bkmonitor.example.com",
      "kernelRpcPath": "/app/kernel_rpc/call/",
      "authMode": "apigw",
      "appCode": "bk_monitor",
      "secretKey": "******",
      "readonly": true,
      "tags": ["prod"]
    }
  ],
  "defaultEnvironmentId": "prod-main"
}
```

运行时配置建议放在静态资源路径，例如 `/admin-config.json`，启动后先加载，再初始化应用。

## 管理页面

环境配置页面路径：

```text
/settings/environments
/settings/environments?env=prod-main
```

页面能力：

- 无环境时显示初始化引导。
- 查看当前配置来源：数据库、静态文件或默认配置。
- 新建、编辑、删除环境。
- 设置默认环境。
- 查看和配置 APIGW 地址、`app_code`、`secret_key`、Kernel RPC path。
- 配置只读标记、标签和 mock fallback；正常环境默认不开启 mock fallback。

## 环境切换

页面需要提供全局环境选择器：

- 展示当前环境名称和标签。
- 生产环境使用明显标识。
- 切换环境时清空当前资源详情状态。
- 切换环境后恢复该环境上次使用的租户，并重新加载 meta、资源列表。
- URL 中可以保留环境 ID，便于分享和恢复。

建议 URL 设计：

```text
/datasources?env=prod-main
/datasources/:bkDataId?env=prod-main
/result-tables?env=prod-main
/result-tables/:tableId?env=prod-main
/settings/environments
```

环境 ID 使用 search param：

```text
/datasources?env=prod-main
```

这样资源页和设置页共用同一套路由根，`/settings/environments` 既可以用于初始化第一套环境，也可以在已有环境下通过 `?env=` 保留当前环境上下文。

## 请求约束

所有 API 请求必须显式携带当前环境上下文：

```ts
kernelRpc.call({
  environmentId,
  operation: 'datasource.detail',
  params
});
```

请求 client 根据 `environmentId` 解析：

- `apiBaseUrl`
- `kernelRpcPath`
- `authMode`，一期固定为 `apigw`
- APIGW app 鉴权请求头，由 Admin API/BFF 后台注入：`X-Bkapi-Authorization` 携带 `bk_app_code` / `bk_app_secret`，`X-Bk-Tenant-Id` 固定为 `system`
- 当前 tenant，从 `admin.tenant.list` 返回的租户列表中选择，也支持手动输入兜底；最终作为 `bk_tenant_id` 注入 DataSource / ResultTable 资源查询参数

页面和 feature API 不允许直接读取全局配置拼 URL，必须通过统一 environment-aware client。

## 缓存约束

TanStack Query 的 query key 必须包含环境 ID：

```ts
['datasource', environmentId, 'detail', bkTenantId, bkDataId]
```

禁止不同环境共享缓存。环境切换时可以选择：

- 保留旧环境缓存，但 query key 隔离。
- 或主动清理非当前环境缓存。

一期推荐 query key 隔离，不强制清空全部缓存。

## Agent 调用约束

未来 AI Agent 调用 API 时，必须明确环境：

```json
{
  "environment_id": "prod-main",
  "operation": "datasource.detail",
  "params": {
    "bk_tenant_id": "system",
    "bk_data_id": 50010
  }
}
```

Agent-facing tool schema 中必须包含 `environment_id`，或者由会话上下文显式绑定环境。禁止在没有环境上下文时隐式调用默认生产环境。

Agent 响应也必须回显环境：

```json
{
  "data": {},
  "trace_id": "00-...",
  "meta": {
    "environment_id": "prod-main",
    "operation": "datasource.detail",
    "safety_level": "read"
  },
  "warnings": []
}
```

## 安全与防误操作

第一期只读，但仍建议：

- 生产环境加明显标签。
- 详情页显示当前环境。
- 复制请求参数时带上 `environment_id`。
- 后续写操作必须要求环境二次确认。
- 后续 `write` / `destructive` 操作不得在未知环境执行。

## 一期验收标准

- 可以配置至少两个环境。
- 无任何环境配置时，可以进入环境配置引导并创建第一个环境。
- 可以在 UI 中切换环境。
- 环境切换后 DataSource / ResultTable 列表请求指向对应环境。
- query cache 以环境隔离。
- URL 能表达或恢复当前环境。
- Agent-facing API 设计文档包含 `environment_id`。
