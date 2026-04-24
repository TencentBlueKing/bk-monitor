# AGENTS.md

本项目默认使用中文协作。

## 项目定位

`bkmonitor-admin` 是 bkmonitor 的独立管理后台，也是一个 AI 友好的 TypeScript 项目。项目编码、重构、文档维护和后续功能扩展会大量由 AI 助手参与，因此代码结构、接口协议、文档和测试都要优先考虑 AI 可理解、可检索、可安全修改。

第一期只做核心资源信息展示，不做写操作和自动排障执行。后续会逐步加入 AI 辅助排障能力。

## AI 协作原则

- 修改前先理解 `docs/` 中的设计文档，尤其是资源文档和 API 约束。
- 新增资源、页面或接口时，同步更新对应文档。
- 执行第一期任务时必须更新 `docs/phase-1-task-list.md` 中对应任务的状态、阻塞项和验收结果。
- 代码组织要按 feature 拆分，避免把业务逻辑、请求、表格状态和 UI 混在单个大组件里。
- API client、schema、类型定义必须集中维护，页面组件不要直接拼 `kernel_rpc` 请求。
- 所有 API 调用必须显式经过 environment-aware client，不能在页面或 feature 中直接拼环境 URL。
- 资源字段、过滤条件、分页参数和返回结构应显式类型化，不依赖隐式 `any`。
- 面向 AI Agent 的接口必须提供机器可读 schema、示例参数、响应示例、安全级别和错误结构。
- 面向 AI Agent 的接口必须明确环境上下文，禁止无环境上下文时隐式调用默认生产环境。
- 对高风险能力使用显式 safety level。第一期只允许 `read` 类型能力。
- 不要提前实现 AI 自动操作、写操作、批量变更或隐式修复。

## 技术方向

默认按以下方向实现，除非后续设计文档明确调整：

- React + TypeScript + Vite
- TanStack Router
- TanStack Query
- TanStack Table
- Zod
- Tailwind CSS + shadcn/ui component-copy 方案
- Vitest + Testing Library
- Playwright
- pre-commit + ESLint + Prettier + TypeScript strict checks

## 代码结构约定

建议目录：

```text
server/                 # 本地 Admin API，负责环境配置的 SQLite/MySQL 存储
src/
├── app/
├── routes/
├── features/
│   ├── environments/
│   ├── kernel-rpc/
│   ├── datasource/
│   └── result-table/
├── shared/
│   ├── api/
│   ├── components/
│   ├── schemas/
│   ├── table/
│   └── utils/
└── main.tsx
```

约定：

- `features/kernel-rpc/` 负责 RPC client、协议类型、错误处理、trace 信息。
- `features/environments/` 负责环境配置加载、环境切换、当前环境状态和环境安全提示。
- `features/datasource/` 负责 DataSource 的 API 封装、schema、页面和组件。
- `features/result-table/` 负责 ResultTable 的 API 封装、schema、页面和组件。
- `shared/components/` 只放跨资源复用的展示组件。
- `shared/components/ui/` 放 shadcn/ui 风格的 copy-in 基础组件，业务组件优先组合这些基础组件。
- `shared/schemas/` 放跨资源复用的 Zod schema 和类型推导。

## API 设计约定

所有面向前端和 AI Agent 的 API 必须遵守：

- 操作名稳定，例如 `datasource.list`、`datasource.detail`、`result_table.field_list`。
- 所有 operation 必须绑定 `environment_id` 或由会话上下文显式绑定环境。
- 入参和响应必须有 JSON Schema 或可导出的 Zod schema。
- 列表接口必须分页，不允许默认返回全量。
- 返回结构必须有稳定 envelope，包含 `data`、`trace_id`、`warnings`。
- 错误结构必须稳定，包含 `code`、`message`、`details`、`trace_id`。
- 每个操作必须标注 `safety_level`，一期固定为 `read`。
- 每个操作必须提供 `examples`，便于 AI Agent 自动构造调用。
- 高成本字段或大列表必须通过单独接口懒加载，例如 ResultTableField。

## 代码质量约定

- 项目必须配置 `.pre-commit-config.yaml`，用 Python `pre-commit` 框架管理 Git hooks。
- `package.json` 必须提供 `format:check`、`lint`、`typecheck`、`test`、`check`、`check:ci`。
- TypeScript 必须开启 strict 系列检查。
- ESLint 必须覆盖 TypeScript、React、Hooks、可访问性、TanStack Query 以及项目边界规则。
- pre-commit 运行快速检查；Playwright 全量 E2E 放到 CI 或关键改动后的手动验证。
- AI 助手修改代码后，应根据改动范围运行对应检查，不能只做静态阅读。

## 文档维护

- 总体目标更新：修改 `docs/overview.md`。
- 第一期任务状态更新：修改 `docs/phase-1-task-list.md`。
- 技术选型更新：修改 `docs/technology.md`。
- RPC/API 约束更新：修改 `docs/kernel-rpc.md`。
- 后端 Admin RPC 函数规划更新：修改 `docs/backend-admin-rpc.md`。
- 多环境配置更新：修改 `docs/environments.md`。
- 代码质量与 pre-commit 更新：修改 `docs/quality.md`。
- DataSource 资源更新：修改 `docs/resources/datasource.md`。
- ResultTable 资源更新：修改 `docs/resources/result-table.md`。
- AI 友好与 Agent 能力设计更新：修改 `docs/agent-friendly.md`。

## 验证要求

后续开始写代码后，常规验证优先级：

1. `pnpm format:check`
2. `pnpm lint`
3. `pnpm typecheck`
4. `pnpm test`
5. 关键页面用 Playwright 做基础交互验证

如果本地环境无法运行某类检查，需要在最终说明中写清楚阻塞原因。
