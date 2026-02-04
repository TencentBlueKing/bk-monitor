---
name: bklog-api-services
description: API/Services 地图（入口/落点/改动半径）。
---

# API / Services（最小地图）

## Map

Entry: `http.request('domain/apiName', config)`
Services: `src/services/*.(js|ts)` + `src/services/index.js`
HTTP: `src/api/`

## DataFlow

view/store → http.request → services map → http layer → backend

## ChangeImpact（只写层级）

- New API → Services(domain) + Services(index export) + call-site(Store/Hook/View)
- URL/method change → Services(domain)
- Auth/header/cancel/cache change → HTTP layer (`src/api/`)

## Boundaries（否定约束）

- No direct URL in View/Store
- No direct axios in View/Store
- No API call in View (prefer Store action / service boundary)

## Refs（按需读取）

`api-reference.md`
