# bkmonitor-admin

<img src="./public/logo-mark.png" width="96" alt="bkmonitor-admin logo" />

`bkmonitor-admin` 是一个独立的 TypeScript 前端项目，定位为 bkmonitor 的管理后台。

这个项目需要对 AI 友好：项目编码主要由 AI 助手参与，后续 API 也需要方便 AI Agent 调用，并逐步承载 AI 辅助排障能力。

第一期目标先聚焦核心资源信息展示，不引入复杂 AI 编排和写操作。页面形态采用传统 admin：左侧为资源类型导航，右侧为列表、详情、关联信息和检索过滤。

## 文档索引

- [项目目标](./docs/overview.md)
- [第一期 Task List](./docs/phase-1-task-list.md)
- [公共技术选型](./docs/technology.md)
- [品牌资产](./docs/brand.md)
- [代码质量与 pre-commit](./docs/quality.md)
- [多环境配置与切换](./docs/environments.md)
- [Kernel RPC 与数据接口设计](./docs/kernel-rpc.md)
- [后端 Admin RPC 函数规划](./docs/backend-admin-rpc.md)
- [AI 友好与 Agent 能力设计](./docs/agent-friendly.md)
- [DataSource 资源设计](./docs/resources/datasource.md)
- [ResultTable 资源设计](./docs/resources/result-table.md)

## 一期资源范围

- DataSource
  - DataSource
  - DataSourceOption
  - SpaceDataSource
  - DataSourceResultTable
  - DataIdConfig
  - 关联 ResultTable 摘要

- ResultTable
  - ResultTable
  - ResultTableOption
  - ResultTableField
  - ResultTableFieldOption
  - TimeSeriesGroup / EventGroup / LogGroup
  - ESStorage
  - DataSource
  - AccessVMRecord

## 暂缓范围

- AI 对话与自动操作
- 写操作、修复操作、批量变更
- 复杂权限申请流程
- 面向普通用户的业务功能入口

## 本地启动

```bash
pnpm install
cp .env.example .env
pnpm dev
```

`pnpm dev` 会同时启动：

- Vite 前端：`http://127.0.0.1:5173/`
- 环境配置 API：`http://127.0.0.1:5174/admin-api`

默认使用 SQLite 文件 `.data/bkmonitor-admin.sqlite` 存储环境配置。首次启动如果没有任何环境配置，页面会进入 `/settings/environments` 引导你添加第一个环境。需要连接本地 MySQL 时，在 `.env` 中设置：

```bash
BKMONITOR_ADMIN_DB_CLIENT=mysql
BKMONITOR_ADMIN_MYSQL_HOST=127.0.0.1
BKMONITOR_ADMIN_MYSQL_PORT=3306
BKMONITOR_ADMIN_MYSQL_USER=root
BKMONITOR_ADMIN_MYSQL_PASSWORD=
BKMONITOR_ADMIN_MYSQL_DATABASE=bkmonitor_admin
```

页面中的“环境配置”可以直接查看和维护 APIGW 地址、`app_code`、`secret_key`、Kernel RPC path 和标签。租户是运行时上下文，在顶部“当前租户”中切换。资源查询不会由浏览器直连 APIGW，而是通过 Admin API 后台代理 `/admin-api/kernel-rpc/call` 请求目标环境。
