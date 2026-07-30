# Skill: Architecture Impact and Test Forecast

This skill runs after the user confirms they want impact analysis and test references at task completion.

Trigger: user answers **是 / Yes / 需要 / Y** to the mandatory completion question defined in the global AAFE task-completion-impact rule.

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

Required artifacts: `impact_scope`, `architecture_evidence`

## Step 2 — Minimal test case design

Design the **smallest sufficient** test set for this change only:

| Field | Requirement |
| --- | --- |
| ID | TC-001, TC-002, ... |
| Priority | P0 required path / P1 important edge / P2 regression |
| Scenario | What behavior is verified |
| Mock setup | All external deps mocked; **no real API or prod data** |
| Steps | Arrange → Act → Assert |
| Assertions | Concrete expected outcomes |
| Boundary coverage | Which edge case this case covers |

Must cover when relevant:

- happy path
- validation / empty / null / max boundary
- error and rejection paths
- permission / unauthorized
- cancellation / timeout / concurrent requests
- cache stale / reload / degradation
- Store or API contract changes → dependent UI paths

Required artifact: `test_cases`

## Step 3 — Execute tests and report results

- Run unit/component tests where the project test runner exists
- Use Mock/fixtures for API, Store, router, browser APIs
- For each case report: **pass | fail | skipped | not_run**
- Include command or execution method when run
- **Never claim pass without actual execution**

Required artifact: `test_results`

## Step 4 — Residual risks

- unverified_risks
- items needing manual QA or E2E
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
### 架构依据
...

## 测试用例
| ID | 优先级 | 场景 | Mock 要点 | 断言 | 覆盖边界 |
...

## 测试执行结果
| ID | 状态 | 命令/方式 | 结果摘要 |
...

## 未覆盖风险
...
```

## Rules

- Scope tests to **this task's diff** only; avoid unrelated full-suite regression unless P2 and justified.
- Mock all external I/O; document mock shape in each test case.
- Distinguish **tested / predicted / not covered** explicitly.
- If no automated test is feasible, provide executable manual verification steps and mark not_run with reason.
