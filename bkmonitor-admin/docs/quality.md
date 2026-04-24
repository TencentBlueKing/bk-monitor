# 代码质量与 pre-commit

## 目标

`bkmonitor-admin` 会长期由 AI 助手参与编码，因此代码质量门禁必须足够明确、自动化、可重复。AI 修改代码后，应能通过固定命令快速发现格式、类型、lint、测试和路由生成问题。

质量体系分三层：

- 编辑期：编辑器和 TypeScript 即时反馈。
- 提交前：`pre-commit` 快速阻断明显问题。
- CI：全量验证构建、测试和浏览器交互。

## 工具选择

一期建议：

| 类型 | 工具 | 说明 |
| --- | --- | --- |
| 包管理 | pnpm | 项目唯一包管理器 |
| 格式化 | Prettier | 统一 TS/TSX/CSS/Markdown/JSON 格式 |
| Lint | ESLint flat config | TypeScript、React、Hooks、可访问性、导入顺序 |
| 类型检查 | TypeScript `tsc --noEmit` | 不允许类型错误进入主分支 |
| Schema 校验 | Zod | 资源 API 入参/响应类型单一事实源 |
| 单元测试 | Vitest | API client、schema、表格状态、格式化工具 |
| 组件测试 | Testing Library | 关键过滤器、表格和详情组件 |
| E2E | Playwright | 核心页面冒烟验证 |
| Git Hook | pre-commit | 提交前统一执行快速检查 |

## package scripts

后续 scaffold 时必须提供以下脚本：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "lint": "eslint .",
    "lint:fix": "eslint . --fix",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test",
    "check": "pnpm format:check && pnpm lint && pnpm typecheck && pnpm test",
    "check:ci": "pnpm check && pnpm build && pnpm test:e2e"
  }
}
```

如果使用 TanStack Router file-based routing，脚本中还需要补充 route generation 校验，确保生成文件不会和源码漂移。

## pre-commit 策略

项目使用 Python `pre-commit` 框架统一管理 Git hooks。即使是 TypeScript 项目，也优先使用 `.pre-commit-config.yaml`，因为它对多语言仓库和 AI 助手都更稳定。

### 提交前快速检查

pre-commit 只运行足够快的检查：

- trailing whitespace
- end of file fixer
- YAML / JSON / Markdown 基础检查
- Prettier check
- ESLint
- TypeScript typecheck
- Vitest related tests 或全量 unit tests

不建议在 pre-commit 中跑 Playwright 全量 E2E，避免提交体验过重。E2E 放到 CI 和关键改动后的人工触发。

### 推荐 `.pre-commit-config.yaml`

后续 scaffold 后落地：

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: mixed-line-ending
        args: ["--fix=lf"]

  - repo: local
    hooks:
      - id: pnpm-format-check
        name: pnpm format:check
        entry: pnpm format:check
        language: system
        pass_filenames: false

      - id: pnpm-lint
        name: pnpm lint
        entry: pnpm lint
        language: system
        pass_filenames: false

      - id: pnpm-typecheck
        name: pnpm typecheck
        entry: pnpm typecheck
        language: system
        pass_filenames: false

      - id: pnpm-test
        name: pnpm test
        entry: pnpm test
        language: system
        pass_filenames: false
```

如果 unit tests 后续变慢，可以把 `pnpm test` 改成只跑 changed related tests，但 CI 必须保留全量。

## ESLint 要求

ESLint 配置至少覆盖：

- TypeScript 推荐规则。
- React 推荐规则。
- React Hooks 规则。
- JSX 可访问性规则。
- TanStack Query 推荐规则。
- 禁止隐式 `any` 和未处理 Promise。
- 禁止页面组件直接调用底层 `kernelRpc.call`。
- 限制相对路径层级，鼓励 feature/public API 导入。

建议保留少量项目自定义规则：

- `features/*/api.ts` 可以调用 `features/kernel-rpc`。
- `pages` 和 `components` 只能调用 feature api/query hooks，不能直接拼 RPC 请求。
- `schemas.ts` 是资源类型和校验的入口，页面里不重复声明接口类型。

## TypeScript 要求

`tsconfig` 应开启严格模式：

- `strict`
- `noUncheckedIndexedAccess`
- `exactOptionalPropertyTypes`
- `noImplicitOverride`
- `noFallthroughCasesInSwitch`
- `useUnknownInCatchVariables`

所有 API 返回先经过 schema 校验或类型收敛，再进入页面。

## 测试策略

### 必测对象

- RPC client 的 envelope、错误解析和 trace 传递。
- DataSource / ResultTable query 参数 schema。
- 列表过滤器到 query params 的转换。
- ResultTableField 分页和懒加载。
- JSON 展示组件对大对象的折叠行为。

### E2E 冒烟

Playwright 至少覆盖：

- 打开 DataSource 列表。
- 输入 `bk_data_id` 搜索并进入详情。
- 从 DataSource 详情跳转到 ResultTable。
- 打开 ResultTable 字段 tab，验证字段分页加载。

## AI 助手验证清单

AI 助手完成代码改动后，默认按改动范围运行：

- 文档改动：检查链接和 Markdown 格式。
- 类型/schema/API 改动：`pnpm typecheck && pnpm test`。
- UI 改动：`pnpm lint && pnpm typecheck && pnpm test`，必要时运行 Playwright。
- 路由改动：额外确认 route generation 或路由类型检查。

如果某项检查因本地依赖、网络或环境缺失无法执行，需要在最终说明里明确写出。
