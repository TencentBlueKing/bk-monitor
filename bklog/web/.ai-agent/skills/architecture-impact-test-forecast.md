# Skill: Architecture Impact and Test Forecast

Trigger: **同时满足**：
1. 任务评估为**涉及代码变更**（非纯文档/需求分析-only）
2. 用户回答 **是 / Yes / 需要 / Y** 至影响分析条件询问

（Rule: `.ai-agent/rules/task-completion-impact.mdc` when present）

Next skill for execution: `minimal-convergent-self-test.md`.

## Required context

1. Read the target project's `.ai-agent/skills/knowledge-center-architecture.md` when present.
2. Read `.ai-agent/memory/knowledge-center-architecture.md` when present.
3. Read relevant `.docs` architecture documents and Mermaid diagrams.
4. Map **current task changed files only** to modules, routes, components, stores, APIs, workers, storage, flows and tests.

## Step 1 — Impact scope report

Produce:

- **直接影响**：changed files, modules, routes, components, stores, APIs, hooks
- **间接影响**：callers, dependents, shared layers, downstream data flow
- **潜在影响**：auth guards, cache, Worker, IndexedDB, compatibility, degradation paths
- **架构关系依据**：.docs paths, diagram refs, source evidence
- **影响分类标签**（供自测收敛）：`logic` | `store` | `api` | `ui` | `mixed`

Required artifacts: `impact_scope`, `architecture_evidence`, `impact_class`

## Step 2 — Minimal test case design（设计 only）

Design the **smallest sufficient** case list for this diff. Do **not** run browser MCP here.

| Field | Requirement |
| --- | --- |
| ID | TC-001, TC-002, ... |
| Priority | P0 / P1 / P2 |
| Mode | unit（默认）/ ui（仅当影响含可见渲染） |
| Scenario | What behavior is verified |
| Mock setup | fixtures / mocked props; **no real API or prod data** |
| Steps | Arrange → Act → Assert |
| Assertions | Concrete expected outcomes |
| Boundary | edge covered |

Classification hints:

- 组件内数据处理 / 百分比 / 缓存 / 排序 → **unit**，Mock Props 或纯函数 I/O
- Store/API 契约 → **unit**，Mock state/response
- 布局、样式、图表真实渲染、交互可见性 → 标记 **ui**；**仅当任务为代码变更且进入自测流程时**，交给自测 Skill 条件询问浏览器 MCP

Required artifact: `test_cases`

## Step 2.5 — UI 交互路径草案（仅 mode=ui）

若 `test_cases` 含 UI，基于变更文件的模板/render **预读一次**，输出 `ui_test_paths` 草案（可无最终 URL）：

- 标注将用到的 `click` / `switch` / `fill` / `hover` / `assert` 目标（文案、role、稳定 class / data-*）
- 写清从页面壳层到复现点的步骤序列
- 完整格式与硬约束见 `minimal-convergent-self-test.md` Step 2.5

目的：把代码分析前移到设计阶段，自测执行只消费路径。URL 仍须用户提供后才能 `navigate`。

Required artifact when UI: `ui_test_paths`（草案可在自测 Skill 用 URL 补全）

## Step 3 — Hand off to self-test skill

Read and follow `.ai-agent/skills/minimal-convergent-self-test.md` to:

1. Create/update files under install-root `test/`
2. Run unit tests with Mock
3. Ask before any browser MCP; require user-provided URL for UI
4. 执行 UI 前补全并锁定 `ui_test_paths`，再按路径操作
5. 自测结束后：若任务过程中**有关联 TAPD 单** → `tapd-submit-backfill.md`（Commit → PR → 条件回填）；无 TAPD 关联则跳过 TAPD 回填

Collect `test_results`（及 UI 时的 `ui_test_paths`）from that skill.

## Step 4 — Residual risks

- unverified_risks
- items needing manual QA or authorized UI run
- architecture conflicts between .docs and code

## Output template

```markdown
## 影响范围报告
### 直接影响
...
### 间接影响
...
### 潜在影响
...
### 影响分类
logic | store | api | ui | mixed
### 架构依据
...

## 测试用例（设计）
| ID | 优先级 | Mode | 场景 | Mock 要点 | 断言 | 覆盖边界 |
...

## UI 测试路径（草案，若有）
### Path P-001 — ...
1. click|switch|fill|hover|assert | target | expected
...

## 测试执行结果
| ID | Mode | 状态 | 命令/证据 | 结果摘要 |
...

## 未覆盖风险
...
```

## Rules

- Scope to **this task's diff** only.
- Distinguish **tested / predicted / not covered**.
- UI browser work is opt-in via `minimal-convergent-self-test.md`；本 Skill 不自动开浏览器。
- UI 路径分析在设计/自测准备阶段完成；禁止把大量源码分析留到点击执行中。
