# Skill: Project Architecture Locator

Generated: 2026-08-21T07:15:50.295Z
Project: blueking-log

## Purpose

Locate routes/modules quickly, then deep-dive via on-demand skills against `.aafe`.

## Analysis output (configurable)

Outer Agent entry (read first):
- `.aafe/manifest.json`
- `.aafe/index.json`
- `.aafe/modules/index.json`

Then one module:
- `.aafe/modules/<id>/index.json`
- Agent: `.aafe/modules/<id>/json/`
- Human: `.aafe/modules/<id>/mmd/`

Global knowledge (on demand only): `.aafe/knowledge/`

## Entries

- `src/main.js` (webpack.config)

## Modules

- `route-retrieve-v2` (142 files, 142 routes) → `modules/route-retrieve-v2/index.json`
- `route-retrieve-v3` (115 files, 115 routes) → `modules/route-retrieve-v3/index.json`
- `route-manage-v2` (113 files, 113 routes) → `modules/route-manage-v2/index.json`
- `src-views-manage-v2` (97 files, 0 routes) → `modules/src-views-manage-v2/index.json`
- `route-manage` (56 files, 56 routes) → `modules/route-manage/index.json`
- `src-views-manage` (36 files, 0 routes) → `modules/src-views-manage/index.json`
- `src-services` (35 files, 0 routes) → `modules/src-services/index.json`
- `src-views-retrieve-v3` (26 files, 0 routes) → `modules/src-views-retrieve-v3/index.json`
- `src-store` (15 files, 1 routes) → `modules/src-store/index.json`
- `src-hooks` (14 files, 0 routes) → `modules/src-hooks/index.json`
- `route-extract` (12 files, 12 routes) → `modules/route-extract/index.json`
- `route-retrieve-core` (12 files, 12 routes) → `modules/route-retrieve-core/index.json`
- `src-storage-services` (11 files, 0 routes) → `modules/src-storage-services/index.json`
- `route-client-log-search` (10 files, 10 routes) → `modules/route-client-log-search/index.json`
- `src-common` (9 files, 0 routes) → `modules/src-common/index.json`
- `src-components-collection-access` (9 files, 0 routes) → `modules/src-components-collection-access/index.json`
- `src-views-client-log-search` (8 files, 0 routes) → `modules/src-views-client-log-search/index.json`
- `route-retrieve` (7 files, 7 routes) → `modules/route-retrieve/index.json`
- `src-views-retrieve-v2` (7 files, 0 routes) → `modules/src-views-retrieve-v2/index.json`
- `src` (6 files, 0 routes) → `modules/src/index.json`
- `src-router` (6 files, 0 routes) → `modules/src-router/index.json`
- `src-storage-repositories` (6 files, 0 routes) → `modules/src-storage-repositories/index.json`
- `src-storage-utils` (6 files, 0 routes) → `modules/src-storage-utils/index.json`
- `src-components-log-masking` (5 files, 0 routes) → `modules/src-components-log-masking/index.json`
- `src-directives` (5 files, 0 routes) → `modules/src-directives/index.json`
- `src-global-head-navi` (5 files, 0 routes) → `modules/src-global-head-navi/index.json`
- `src-language-lang` (5 files, 0 routes) → `modules/src-language-lang/index.json`
- `src-mixins` (5 files, 0 routes) → `modules/src-mixins/index.json`
- `src-store-actions` (5 files, 0 routes) → `modules/src-store-actions/index.json`
- `src-api` (4 files, 0 routes) → `modules/src-api/index.json`
- `src-global-bk-space-choice` (4 files, 0 routes) → `modules/src-global-bk-space-choice/index.json`
- `route-dashboard` (3 files, 3 routes) → `modules/route-dashboard/index.json`
- `src-store-modules` (3 files, 0 routes) → `modules/src-store-modules/index.json`
- `src-store-services` (3 files, 0 routes) → `modules/src-store-services/index.json`
- `src-views` (3 files, 0 routes) → `modules/src-views/index.json`
- `src-views-authorization` (3 files, 0 routes) → `modules/src-views-authorization/index.json`
- `src-views-dashboard` (3 files, 0 routes) → `modules/src-views-dashboard/index.json`
- `src-views-retrieve-core` (3 files, 0 routes) → `modules/src-views-retrieve-core/index.json`
- `route-authorization` (2 files, 2 routes) → `modules/route-authorization/index.json`
- `route-playground` (2 files, 2 routes) → `modules/route-playground/index.json`

## Context rules

1. Read outer entry files first (`manifest` / `index`).
2. Load only one matched `modules/<id>/index.json` then its `json/` slice.
3. Prefer JSON/JSONL for Agent; open `mmd/` only for humans.
4. Never eagerly read `knowledge/graph/jsonl/`.
5. Re-run `aafe analyze` after major structure changes.
