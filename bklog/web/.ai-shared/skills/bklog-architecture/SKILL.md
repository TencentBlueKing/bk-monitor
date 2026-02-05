---
name: bklog-architecture
description: BKLog Web 架构地图（分层/边界/模块映射）。
---

# BKLog Web（最小地图）

## Scope（工作边界）

Only: `bklog/web/src/`
Ignore: `packages/*`

## Map

Project: SPA / Admin
Stack: Vue2 + TS/TSX + Vuex + VueRouter + bk-magic-vue

## Layers

- View: `src/views/`
- Store: `src/store/`
- Services: `src/services/`
- HTTP: `src/api/`
- Hooks: `src/hooks/`

## DataFlow

URL → Store(url-resolver) → Services → Store → View

## Modules（业务模块→核心入口）

- 日志检索/retrieve: `views/retrieve-v3/` + `store/url-resolver.ts` + `store/default-values.ts`
- 收藏/favorite: `views/retrieve-v3/favorite/`
- 管理/manage: `views/manage/`
- 仪表盘/dashboard: `views/dashboard/`
- 采集/collect: `views/manage/manage-access/`

## Domain

spaceUid, bkBizId, indexSetId, retrieve, favorite, addition, keyword, unionList

## ChangeImpact

- UI change → View + Components
- URL/Query change → Store(url-resolver) + View
- Field change → Services + Store + View

## Boundaries

- No API call in View
- No mutation outside Vuex
- No work in packages/*
