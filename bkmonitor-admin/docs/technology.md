# 公共技术选型

## 推荐栈

一期建议使用：

- 语言：TypeScript
- 框架：React
- 构建：Vite
- 包管理：pnpm
- 路由：TanStack Router
- 服务端状态：TanStack Query
- 表格：TanStack Table
- Schema：Zod
- 样式：Tailwind CSS
- 组件：shadcn/ui component-copy 方案
- 本地配置服务：Fastify + TypeScript
- 环境配置存储：SQLite 默认，MySQL 可选
- 测试：Vitest + Testing Library + Playwright
- 代码质量：Prettier + ESLint flat config + TypeScript strict + pre-commit

## 选择 React + TanStack 的原因

这次项目不需要受当前 `bkmonitor/webpack` 技术栈限制，因此优先选择更适合 AI 协作和现代 admin 开发的栈。

- React + TypeScript 的公开语料、组件生态和 AI 代码生成稳定性更好。
- Vite 提供轻量、快速、框架无关的前端工程基础。
- TanStack Router 强调类型安全路由，适合资源详情页、搜索参数和嵌套路由。
- TanStack Query 适合管理服务端状态、缓存、重试、加载态和错误态。
- TanStack Table 适合服务端分页、过滤、排序和列配置，尤其适合 DataSource / ResultTable 这种后台列表。
- Zod 可以作为前端 schema 的单一事实源，并能服务于运行时校验和 Agent tool schema 生成。
- shadcn/ui 这类 component-copy 方案更容易由 AI 直接修改源码，不会被大型黑盒组件库限制。
- 环境配置需要在页面内维护，独立 Fastify Admin API 可以把配置落到 SQLite/MySQL，同时避免把 `secret_key` 写死在静态前端源码里。
- 完整的 lint/typecheck/test/pre-commit 链路可以让 AI 生成代码后快速自检，降低隐性回归。

## 项目形态

`bkmonitor-admin` 独立于 `bkmonitor/webpack`：

```text
bk-monitor/
├── bkmonitor/
├── bk-monitor-base/
├── bklog/
└── bkmonitor-admin/
```

一期不接入 `bkmonitor/webpack` 的微前端构建链，避免被现有多应用构建、历史依赖和发布流程牵制。后续如果需要嵌入 bkmonitor 主站，可以再评估微前端、独立蓝鲸应用或静态资源集成。

## 建议目录结构

```text
bkmonitor-admin/
├── server/
│   ├── index.ts
│   └── stores/
├── docs/
├── src/
│   ├── app/
│   ├── routes/
│   ├── pages/
│   │   ├── datasources/
│   │   └── result-tables/
│   ├── features/
│   │   ├── environments/
│   │   ├── kernel-rpc/
│   │   ├── datasource/
│   │   └── result-table/
│   ├── shared/
│   │   ├── api/
│   │   ├── components/
│   │   ├── schemas/
│   │   ├── table/
│   │   └── utils/
│   └── main.tsx
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── vite.config.ts
├── eslint.config.js
├── prettier.config.js
└── .pre-commit-config.yaml
```

## 运行环境

开发期会启动两个本地服务：

- Vite 前端：`http://127.0.0.1:5173/`
- Admin API：`http://127.0.0.1:5174/admin-api`

Vite 会把 `/admin-api` 代理到 Admin API。Admin API 负责环境配置的读取、写入、默认环境设置，以及 Kernel RPC 后台代理。

浏览器只请求 `/admin-api/kernel-rpc/call`，不直接请求 bkmonitor APIGW。Admin API 根据环境配置在后台请求：

- `/api/v4/kernel_rpc/call/`：直接访问后端内部路径。
- 或 `/app/kernel_rpc/call/`：通过 APIGW internal resource 访问。

具体走哪条路径取决于部署方式：

- 如果和 bkmonitor 后端同域部署，优先走 `/api/v4/kernel_rpc/call/`。
- 如果作为独立蓝鲸应用部署，优先走 APIGW，并由后端/BFF 注入应用鉴权。

项目需要支持多环境配置和切换。环境配置优先来自 Admin API 数据库，其次来自运行时 `/admin-config.json`，最后回退到构建时默认配置。所有请求、TanStack Query key、URL 路由和 Agent 调用都必须携带环境上下文。

## 一期需要避免的技术债

- 不在页面里硬编码每个 Django 模型的全部字段。
- 不把 `kernel_rpc` 的调用散落在页面组件里。
- 不在浏览器资源请求中直连 APIGW 或携带 `secret_key`，必须经由 Admin API/BFF。
- 不在前端做跨租户兜底猜测。
- 不在前端做隐式环境兜底，尤其禁止无环境上下文时默认调用生产环境。
- 不在 ResultTable 列表中直接拉全量字段。
- 不把 AI 交互提前写死进页面布局。
- 不把 API schema 只写成人类文档；需要能逐步演进成 Agent 可消费的机器描述。
- 不允许绕过 `pre-commit` 和 `pnpm check` 合入代码。
