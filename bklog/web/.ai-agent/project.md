# BKLog Web Project Knowledge Entry

This file is the single project-specific knowledge entry for BKLog Web.

## Purpose

`.ai-agent` is the single AI runtime and knowledge root for this frontend project:

- AAFE Runtime: `.ai-agent/runtime/`, `.ai-agent/pipelines/`, `.ai-agent/skills/`
- AAFE Memory: `.ai-agent/memory/`
- BKLog project-specific skills migrated from legacy shared config: `.ai-agent/project-skills/`
- BKLog project-specific rules migrated from legacy shared config: `.ai-agent/rules/`

The legacy shared AI directory has been removed to avoid duplicate AI entry points and stale context conflicts.

## Scope

- Primary editable frontend scope: `bklog/web/src/`
- Ignore by default: `bklog/web/packages/*`
- Avoid repo-wide search unless explicitly required; prefer scoped search under `src/`.

## Quick Map

| Domain | Minimal Entry |
| --- | --- |
| 日志检索 / retrieve | `src/store/url-resolver.ts` + `src/store/default-values.ts` + `src/views/retrieve-v3/` |
| retrieve v2 result panel | `src/views/retrieve-v2/search-result-panel/` |
| 收藏 / favorite | `src/views/retrieve-v3/favorite/` |
| 管理 / manage | `src/views/manage/`, `src/views/manage-v2/` |
| 采集 / collection | `src/views/manage/manage-access/`, `src/views/manage-v2/log-collection/` |
| 仪表盘 / dashboard | `src/views/dashboard/` |
| API services | `src/services/*.(js|ts)` + `src/services/index.js` |
| HTTP layer | `src/api/` |
| Hooks | `src/hooks/` |
| Common utils | `src/common/`, `src/global/utils/` |

## How to Use Project Skills

Read minimally:

1. Always start with `.ai-agent/project-skills/bklog-architecture/SKILL.md` for project map and boundaries.
2. Then read domain-specific skills only when needed:
   - UI/components: `.ai-agent/project-skills/bklog-components/SKILL.md`
   - Hooks/reactive logic: `.ai-agent/project-skills/bklog-hooks/SKILL.md`
   - API/services: `.ai-agent/project-skills/bklog-api-services/SKILL.md`
   - Utils/formatting: `.ai-agent/project-skills/bklog-utils/SKILL.md`
   - Naming/placement/conventions: `.ai-agent/project-skills/bklog-coding-patterns/SKILL.md`
   - MagicBox UI: `.ai-agent/project-skills/bk-magicbox-vue/SKILL.md`

## Self Update Protocol

Project knowledge must evolve with code changes. When adding or updating modules, routes, APIs, hooks, reusable components, shared rules, or stable bugfix constraints, update `.ai-agent` knowledge in the same task.

- Self-update skill: `.ai-agent/project-skills/aafe-self-update/SKILL.md`
- Always-on rule: `.ai-agent/rules/knowledge-self-update.mdc`
- Editor-specific files must stay as thin pointers to `.ai-agent`; do not duplicate project knowledge there.
- Do not recreate or reference the removed legacy shared AI directory.

## Rules

Project-specific rules live in `.ai-agent/rules/`:

- `workspace-boundary.mdc` - workspace and search boundary
- `vue-development-mode.mdc` - Vue development mode constraints
- `knowledge-self-update.mdc` - keep project knowledge current with code changes
- `retrieve-v2-ui.mdc` - retrieve-v2/log-result UI and performance constraints

These rules complement AAFE architecture gates in `.ai-agent/runtime/gates.yaml`.
