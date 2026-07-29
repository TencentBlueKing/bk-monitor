# Skill: Architecture Impact and Test Forecast

This skill is a mandatory final step after every completed task, fix, refactor, configuration change or documentation update.

## Required context

1. Read the target project's \.ai-agent/skills/knowledge-center-architecture.md when present.
2. Read \.ai-agent/memory/knowledge-center-architecture.md when present.
3. Read the relevant \.docs architecture documents and Mermaid diagrams.
4. Map changed files to modules, routes, components, stores, APIs, workers, storage, flows and tests.

## Required final output

Before reporting completion, produce:

- 修复/变更影响范围：直接影响、间接影响和可能影响；
- 架构关系依据：引用相关 .docs 文件、图表和源码路径；
- 需要测试的范围：单元、组件、集成、端到端、回归和异常路径；
- 测试优先级：P0/P1/P2，并说明预测原因；
- 未验证项、风险和需要人工确认的架构冲突。

## Project-specific rules

- Do not claim a test passed unless it was actually run.
- Distinguish tested, predicted and not covered.
- For changes involving route guards, request cancellation, streaming, parsing, pagination, cache, Worker or IndexedDB, include stale response, cancellation, reload/degradation and concurrent request cases.
- For changes involving Store or API contracts, include dependent pages, actions, services and UI rendering paths.
- If no test is needed, explain why using the architecture relationships and still provide the predicted scope.

Required artifacts:
- impact_scope
- architecture_evidence
- test_forecast
- unverified_risks
