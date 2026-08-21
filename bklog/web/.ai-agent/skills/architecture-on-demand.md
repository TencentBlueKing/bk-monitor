# Skill: Architecture On-Demand

Generated: 2026-08-21T06:33:08.700Z
Project: blueking-log

## Purpose

Load architecture facts **per module** without scanning the whole tree.

## Agent loading protocol

1. `.aafe/manifest.json`
2. `.aafe/index.json`
3. `.aafe/modules/index.json` → pick one module id
4. `.aafe/modules/<id>/index.json` (module entry)
5. Only then open `.aafe/modules/<id>/json/architecture.json` / `routes.json` / `components.json`
6. Human diagrams (optional): `.aafe/modules/<id>/mmd/`
7. **Forbidden:** eagerly open every module or `knowledge/graph/jsonl/`

## Module ids (summary)

- `route-retrieve-v2` (142 files)
- `route-retrieve-v3` (115 files)
- `route-manage-v2` (113 files)
- `src-views-manage-v2` (98 files)
- `route-manage` (56 files)
- `src-views-manage` (36 files)
- `src-services` (35 files)
- `src-views-retrieve-v3` (26 files)
- `src-store` (15 files)
- `src-hooks` (14 files)
- `route-extract` (12 files)
- `route-retrieve-core` (12 files)
- `src-storage-services` (11 files)
- `route-client-log-search` (10 files)
- `src-common` (9 files)
- `src-components-collection-access` (9 files)
- `src-views-client-log-search` (8 files)
- `route-retrieve` (7 files)
- `src-views-retrieve-v2` (7 files)
- `src` (6 files)
- `src-router` (6 files)
- `src-storage-repositories` (6 files)
- `src-storage-utils` (6 files)
- `src-components-log-masking` (5 files)
- `src-directives` (5 files)
- `src-global-head-navi` (5 files)
- `src-language-lang` (5 files)
- `src-mixins` (5 files)
- `src-store-actions` (5 files)
- `src-api` (4 files)
- `src-global-bk-space-choice` (4 files)
- `route-dashboard` (3 files)
- `src-store-modules` (3 files)
- `src-store-services` (3 files)
- `src-views` (3 files)
- `src-views-authorization` (3 files)
- `src-views-dashboard` (3 files)
- `src-views-retrieve-core` (3 files)
- `route-authorization` (2 files)
- `route-playground` (2 files)

## Related

- Locator: `.ai-agent/skills/project-architecture-locator.md`
- Dataflow: `.ai-agent/skills/dataflow-on-demand.md`
