# Skill: Dataflow On-Demand

Generated: 2026-08-21T07:15:50.295Z
Project: blueking-log

## Purpose

Load dataflow facts **per module**.

## Agent loading protocol

1. `.aafe/index.json` → `.aafe/modules/index.json`
2. `.aafe/modules/<id>/index.json`
3. `.aafe/modules/<id>/json/dataflow.json`
4. Cross-module: `.aafe/knowledge/relations/json/dataflow.json`
5. Human: `.aafe/modules/<id>/mmd/dataflow.mmd`
6. **Forbidden:** dump all flows into context

## Module ids (summary)

- `route-retrieve-v2`
- `route-retrieve-v3`
- `route-manage-v2`
- `src-views-manage-v2`
- `route-manage`
- `src-views-manage`
- `src-services`
- `src-views-retrieve-v3`
- `src-store`
- `src-hooks`
- `route-extract`
- `route-retrieve-core`
- `src-storage-services`
- `route-client-log-search`
- `src-common`
- `src-components-collection-access`
- `src-views-client-log-search`
- `route-retrieve`
- `src-views-retrieve-v2`
- `src`
- `src-router`
- `src-storage-repositories`
- `src-storage-utils`
- `src-components-log-masking`
- `src-directives`
- `src-global-head-navi`
- `src-language-lang`
- `src-mixins`
- `src-store-actions`
- `src-api`
- `src-global-bk-space-choice`
- `route-dashboard`
- `src-store-modules`
- `src-store-services`
- `src-views`
- `src-views-authorization`
- `src-views-dashboard`
- `src-views-retrieve-core`
- `route-authorization`
- `route-playground`

## Related

- Architecture: `.ai-agent/skills/architecture-on-demand.md`
