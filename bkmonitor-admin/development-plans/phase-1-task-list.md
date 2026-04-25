# 第一期 Task List

本文档用于跟踪 `bkmonitor-admin` 第一期落地任务。后续实现过程中需要持续更新状态、负责人、阻塞项和验收结果。

## 状态约定

| 状态        | 说明                       |
| ----------- | -------------------------- |
| Todo        | 尚未开始                   |
| In Progress | 正在实现                   |
| Blocked     | 被依赖、环境或方案问题阻塞 |
| Review      | 已完成实现，等待 review    |
| Done        | 已完成并验证               |

## 角色约定

后续实现时可以拆给不同子 Agent：

- Coordinator：居中规划、拆任务、合并设计、处理跨前后台契约。
- Backend Agent：实现 bkmonitor `kernel_api/rpc/functions/admin/` 下的只读 RPC。
- Frontend Agent：实现 `bkmonitor-admin` 前端项目、页面、状态和交互。
- QA Agent：补测试、跑检查、做基础端到端验证。

## 总体里程碑

| 阶段 | 目标                                   | 状态 |
| ---- | -------------------------------------- | ---- |
| M1   | 项目脚手架、质量门禁、多环境基础能力   | Done |
| M2   | 后端 Admin RPC 只读接口                | Done |
| M3   | 前端 DataSource / ResultTable 信息展示 | Done |
| M4   | 前后台联调、测试、文档收口             | Done |

## 任务清单

### P1-001 项目脚手架初始化

状态：Done

建议负责人：Frontend Agent

目标：

- 初始化 `bkmonitor-admin` 前端工程。
- 使用 React + TypeScript + Vite。
- 建立 feature-first 目录结构。

主要产出：

- `package.json`
- `pnpm-lock.yaml`
- `vite.config.ts`
- `tsconfig.json`
- `src/` 基础目录
- 基础 app shell

依赖：

- [公共技术选型](./technology.md)
- [AI 友好与 Agent 能力设计](./agent-friendly.md)

验收：

- `pnpm install` 成功。
- `pnpm dev` 可启动。
- 首页能显示基础 admin 布局占位。

### P1-002 代码质量与 pre-commit 落地

状态：Done

建议负责人：Frontend Agent

目标：

- 落地完整代码检查和提交前检查。

主要产出：

- `.pre-commit-config.yaml`
- `eslint.config.js`
- `prettier.config.js`
- Vitest 配置
- Playwright 配置
- `pnpm format:check`
- `pnpm lint`
- `pnpm typecheck`
- `pnpm test`
- `pnpm check`
- `pnpm check:ci`

依赖：

- [代码质量与 pre-commit](./quality.md)

验收：

- `pnpm check` 可执行。
- `pre-commit run --all-files` 可执行。
- TypeScript strict 开启。

### P1-003 多环境配置基础能力

状态：Done

建议负责人：Frontend Agent

目标：

- 支持多套 bkmonitor 环境配置和切换。
- 所有 API client、路由、缓存都绑定 `environmentId`。

主要产出：

- `features/environments/`
- 环境配置 schema
- 默认环境配置
- 运行时 `/admin-config.json` 加载逻辑
- 全局环境选择器
- `?env=<environmentId>` 路由参数结构

依赖：

- [多环境配置与切换](./environments.md)

验收：

- 可配置至少两个环境。
- URL 可表达当前环境。
- 切换环境后资源列表重新请求。
- TanStack Query key 包含 `environmentId`。

### P1-004 Kernel RPC 前端 client

状态：Done

建议负责人：Frontend Agent

目标：

- 封装 environment-aware kernel RPC client。
- 页面和 feature API 不直接拼 RPC URL。

主要产出：

- `features/kernel-rpc/`
- RPC request / response types
- envelope 解析
- 错误结构解析
- trace 信息保留
- operation 到 backend `func_name` 的映射
- 浏览器只调用 `/admin-api/kernel-rpc/call`，APIGW 地址和 app secret 由 Admin API/BFF 后台使用

依赖：

- [Kernel RPC 与数据接口设计](./kernel-rpc.md)
- [多环境配置与切换](./environments.md)

验收：

- client 调用必须传 `environmentId`。
- client 能调用 `__meta__` 或 mock RPC。
- 单元测试覆盖成功响应、错误响应、BFF 调用和 mock fallback。

### P1-005 后端 Admin RPC 包结构

状态：Done

建议负责人：Backend Agent

目标：

- 在 bkmonitor 后端创建 admin RPC 包结构。
- 确保 `KernelRPCRegistry` 能加载 admin 子模块。

主要产出：

- `kernel_api/rpc/functions/admin/__init__.py`
- `kernel_api/rpc/functions/admin/common.py`
- `kernel_api/rpc/functions/admin/datasource.py`
- `kernel_api/rpc/functions/admin/result_table.py`

依赖：

- [后端 Admin RPC 函数规划](./backend-admin-rpc.md)

验收：

- `__meta__.list` 能看到 `admin.datasource.*` 和 `admin.result_table.*`。
- 不影响已有 `kernel_api/rpc/functions` 加载逻辑。

### P1-006 后端 DataSource RPC

状态：Done

建议负责人：Backend Agent

目标：

- 实现 DataSource 只读列表和详情接口。

主要产出：

- `admin.datasource.list`
- `admin.datasource.detail`
- 入参校验
- 分页与排序白名单
- DataSourceOption / SpaceDataSource / DataSourceResultTable / DataIdConfig / ResultTable 摘要组装
- Kafka 集群摘要与 KafkaTopic 配置组装
- 后端单元测试

依赖：

- P1-005
- [DataSource 资源设计](./resources/datasource.md)
- [后端 Admin RPC 函数规划](./backend-admin-rpc.md)

验收：

- 支持 `bk_data_id`、`data_name`、`created_from`、`source_label`、`type_label`、`space_uid`、`table_id` 过滤。
- 列表返回关联计数。
- 列表返回 Kafka 集群摘要，用于展示集群名称并通过 tooltip 暴露集群 ID。
- 详情返回文档约定结构。
- 详情返回 Kafka 集群 ID/名称和 KafkaTopic 配置。
- 不返回 token 明文，只返回 `has_token`。

### P1-007 后端 ResultTable RPC

状态：Done

建议负责人：Backend Agent

目标：

- 实现 ResultTable 只读列表、详情、字段分页和字段 options。

主要产出：

- `admin.result_table.list`
- `admin.result_table.detail`
- `admin.result_table.field_list`
- `admin.result_table.field_options`
- ResultTableOption / DataSource / CustomGroup / ESStorage / AccessVMRecord 摘要组装
- ResultTableField 独立分页
- 后端单元测试

依赖：

- P1-005
- [ResultTable 资源设计](./resources/result-table.md)
- [后端 Admin RPC 函数规划](./backend-admin-rpc.md)

验收：

- 支持 `table_id`、`bk_data_id`、`data_label`、`label`、`schema_type`、`default_storage` 等过滤。
- 详情不返回字段全量。
- 字段列表分页加载。
- 字段 options 独立查询。

### P1-008 前端 DataSource 页面

状态：Done

建议负责人：Frontend Agent

目标：

- 实现 DataSource 资源列表、过滤、详情和关联跳转。

主要产出：

- DataSource list page
- DataSource filters
- DataSource table
- DataSource detail page / panel
- Kafka cluster column
- KafkaTopic config section
- Options tab
- SpaceDataSource tab
- ResultTable relation tab
- DataIdConfig tab

依赖：

- P1-003
- P1-004
- P1-006 或 mock API
- [DataSource 资源设计](./resources/datasource.md)

验收：

- 可按 `bk_data_id` 快速定位。
- 可按核心字段过滤。
- 可从 DataSource 跳转 ResultTable。
- 切换环境后请求正确环境。

### P1-009 前端 ResultTable 页面

状态：Done

建议负责人：Frontend Agent

目标：

- 实现 ResultTable 列表、过滤、详情、字段分页和关联信息展示。

主要产出：

- ResultTable list page
- ResultTable filters
- ResultTable table
- ResultTable detail page / panel
- Options tab
- Datasource tab
- CustomGroup tab
- Storage tab
- VM tab
- Field tab with server-side pagination
- Field option detail

依赖：

- P1-003
- P1-004
- P1-007 或 mock API
- [ResultTable 资源设计](./resources/result-table.md)

验收：

- 可按 `table_id` 快速定位。
- 可按 `bk_data_id` 反查。
- ResultTable 详情首屏不拉字段全量。
- Field tab 分页和过滤可用。

### P1-010 前端基础布局与导航

状态：Done

建议负责人：Frontend Agent

目标：

- 实现传统 admin 布局。

主要产出：

- 左侧资源导航
- 顶部环境选择器
- 顶部租户上下文展示与切换，租户列表来自 `admin.tenant.list`
- 全局 loading / error boundary
- 空状态、错误态、无数据态

依赖：

- P1-001
- P1-003

验收：

- 左侧可在 DataSource / ResultTable 间切换。
- 顶部可识别当前环境。
- 生产环境有明显标识。

### P1-011 前后台契约对齐与 mock 数据

状态：Done

建议负责人：Coordinator

目标：

- 在后端实现完成前，保证前端可以基于稳定契约开发。
- 后端实现后，对齐实际响应。

主要产出：

- RPC operation map
- 前端 Zod schema
- mock responses
- 契约差异记录

依赖：

- P1-004
- P1-006
- P1-007

验收：

- mock 响应和后端响应字段一致。
- schema 能校验核心响应结构。
- 差异项记录并回填文档。

### P1-012 测试与验证

状态：Done

建议负责人：QA Agent

目标：

- 建立第一期基础测试覆盖。

主要产出：

- RPC client 单元测试
- schema 单元测试
- DataSource 页面组件测试
- ResultTable 字段分页测试
- Playwright 冒烟测试

依赖：

- P1-002
- P1-008
- P1-009

验收：

- `pnpm check` 通过。
- 核心页面 Playwright 冒烟通过。
- 后端相关 targeted tests 通过，或明确记录本地环境阻塞。

### P1-013 文档收口

状态：Done

建议负责人：Coordinator

目标：

- 实现完成后更新设计文档，保证文档反映真实实现。

主要产出：

- 更新本 task list 状态。
- 更新 API 入参出参差异。
- 更新运行方式。
- 更新验证结果。
- 更新已知限制。

依赖：

- P1-001 至 P1-012

验收：

- README 能指导启动项目。
- 资源文档与后端实际 RPC 一致。
- AGENTS.md 与真实工程脚本一致。

## 推荐并行方式

第一轮可以并行：

- Frontend Agent：P1-001、P1-002、P1-003、P1-004、P1-010。
- Backend Agent：P1-005、P1-006、P1-007。
- Coordinator：P1-011 契约对齐，持续更新文档。

第二轮可以并行：

- Frontend Agent：P1-008、P1-009。
- QA Agent：P1-012。
- Coordinator：处理前后台契约差异和文档收口。

## 当前阻塞与待确认

- 部署形态仍需最终确认：独立蓝鲸应用、同域静态资源，还是后续接入主站。
- 后端 Admin RPC 更严格的 tool meta 接口一期暂缓。
- 后端 pytest 在本地仍受运行环境阻塞：`ai_agent` 依赖缺失，继续执行还需要可用 MySQL 测试库。

## 本轮实现记录

更新时间：2026-04-24

已完成：

- 初始化 `bkmonitor-admin` React + TypeScript + Vite 工程。
- 落地 ESLint、Prettier、TypeScript strict、Vitest、Playwright、pre-commit 配置。
- 实现多环境配置、环境切换、`?env=<environmentId>` 路由参数。
- 实现 environment-aware Kernel RPC client，默认走真实 RPC；mock fallback 仅在环境配置中显式开启。
- 实现 DataSource 列表、详情、关联信息展示。
- DataSource 列表补充 Kafka 集群列，详情补充 Kafka 集群 ID/名称和 KafkaTopic 配置展示。
- 实现 ResultTable 列表、详情、字段分页展示。
- 在 bkmonitor 后端新增 `kernel_api/rpc/functions/admin/`，实现一期只读 RPC。
- 补充前端单测、Playwright 冒烟测试和后端轻量测试。

追加完成：

- 新增 TypeScript Fastify Admin API，提供 `/admin-api/config`、环境增删改、默认环境设置。
- 环境配置支持 SQLite 文件存储，保留 MySQL 配置和适配器。
- 环境 schema 增加 `appCode` / `secretKey`，APIGW 模式下由 Admin API/BFF 在后台通过 `X-Bkapi-Authorization` 请求头发送；APIGW `X-Bk-Tenant-Id` 固定为默认租户 `system`。
- 新增“环境配置”页面，可在页面直接查看和维护 APIGW 地址、app_code、secret_key、RPC path 和标签；租户从环境配置中拆出，作为顶部运行时上下文切换，并通过 `admin.tenant.list` 提供候选列表。
- UI 基础组件重构为 shadcn/ui component-copy 风格，列表、分页、详情摘要和配置页已切换到统一组件。
- 左侧导航调整为二级菜单，分为“资源管理”和“系统设置”。
- 环境配置为空时，首页和环境路由会进入 `/settings/environments` 引导页，不再报错或隐式跳到不存在的环境。

验证结果：

- `pnpm check` 通过。
- `pnpm build` 通过。
- `pnpm test:e2e` 通过。
- `uv run python -m py_compile kernel_api/rpc/functions/admin/__init__.py kernel_api/rpc/functions/admin/common.py kernel_api/rpc/functions/admin/datasource.py kernel_api/rpc/functions/admin/result_table.py kernel_api/rpc/tests/test_admin_rpc.py` 通过。
- `uv run ruff check kernel_api/rpc/functions/admin kernel_api/rpc/tests/test_admin_rpc.py` 通过。
- `uv run ruff format --check kernel_api/rpc/functions/admin kernel_api/rpc/tests/test_admin_rpc.py` 通过。
- `uvx pre-commit run --config bkmonitor-admin/.pre-commit-config.yaml --files <bkmonitor-admin untracked files>` 通过。

未完成验证：

- `uv run pytest kernel_api/rpc/tests/test_admin_rpc.py -q` 未通过，阻塞于本地 Django 环境依赖：缺少 `ai_agent` 模块；此前 worker 进一步尝试后也遇到 MySQL `Unknown database 'bk_monitorv3'`。
