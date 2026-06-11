---
name: aafe-self-update
description: BKLog Web 项目知识自更新协议。新增模块、更新模块、调整路由/组件/API/Hook/规则时，必须同步更新 .ai-agent 中对应的项目知识文件，保持 AI 入口可定位、可复用、不过期。
---

# AAFE Project Knowledge Self Update

## Goal

.ai-agent is the single AI runtime and project knowledge root. Any code change that creates, removes, moves, or meaningfully changes a BKLog Web module must update the corresponding project knowledge file in the same task.

This keeps project skills accurate and prevents future agents from relying on stale .ai-agent/project-skills maps.

## Trigger Conditions

Run this self-update protocol when any of these changes happen:

1. New module / route / page / major component is added.
2. Existing module responsibility, entry file, or data flow changes.
3. API service key, request path, request contract, or response contract changes.
4. Shared hook, common util, store module, or event contract changes.
5. UI interaction pattern becomes a reusable convention.
6. A bugfix reveals a stable constraint that future edits must follow.
7. A file is moved/renamed/deleted and old knowledge points to it.

Do not update project knowledge for purely local typo/style changes that do not affect navigation, contracts, or conventions.

## Update Targets

| Change Type | Required Knowledge File |
| --- | --- |
| Route/page/module entry changed | .ai-agent/project-skills/bklog-architecture/SKILL.md |
| Reusable component or component directory changed | .ai-agent/project-skills/bklog-components/SKILL.md and maybe components-reference.md |
| API service added/changed | .ai-agent/project-skills/bklog-api-services/SKILL.md and maybe api-reference.md |
| Hook/composable added/changed | .ai-agent/project-skills/bklog-hooks/SKILL.md and maybe hooks-reference.md |
| Utility/formatter/parser convention changed | .ai-agent/project-skills/bklog-utils/SKILL.md |
| Coding/location/naming convention changed | .ai-agent/project-skills/bklog-coding-patterns/SKILL.md |
| retrieve-v2/log-result UI/performance invariant changed | .ai-agent/rules/retrieve-v2-ui.mdc |
| Vue development style or workspace rule changed | .ai-agent/rules/vue-development-mode.mdc / .ai-agent/rules/workspace-boundary.mdc |
| Reusable debugging/fix decision learned | .ai-agent/memory/decisions.md or .ai-agent/memory/experience.md |
| New project skill category introduced | .ai-agent/project-skills/README.md and .ai-agent/project.md |

## Minimal Update Format

Knowledge updates must be small and searchable. Prefer adding one of these sections:

### Module Map

- domain: entry file + store/service/hook - short responsibility.

### Contract Notes

- api or hook: input to output; important constraints.

### ChangeImpact

- If changing feature, also check related files.

### Boundaries

- Do not ...
- Must ...

Avoid dumping long implementation details. Keep entries as navigation hints and stable constraints.

## Required Workflow

1. Before editing code, read .ai-agent/project.md and the domain-specific project skill.
2. After editing code, classify whether knowledge changed using Trigger Conditions.
3. If yes, update the minimal target file from Update Targets.
4. Run static checks for changed knowledge files:
   - ensure editor entries do not point to the removed legacy shared AI directory
   - git diff --check -- .ai-agent .cursor .codebuddy .aafe.config.json
5. In the final response, include a short Knowledge update line:
   - updated: files
   - not needed: reason

## Single Entry Constraint

Do not recreate the legacy shared AI directory.
Do not point .cursor or .codebuddy to project knowledge outside .ai-agent.
Do not duplicate the same knowledge across editor-specific files; editor entries should only point to .ai-agent.
