---
name: bklog-components
description: Components 地图（目录/全局注册/改动半径）。
---

# Components（最小地图）

## Map

Local: `src/components/`
App-global: `src/global/`
Register: `src/main.js`
UI: `bk-magic-vue`（`bk-*`）

## ChangeImpact（只写层级）

- Reusable component → `src/components/<kebab>/`（`index.(tsx|vue)` + `index.scss`）
- App-shell component → `src/global/`
- Global registration change → `src/main.js`

## Boundaries（否定约束）

- No business API in component
- No duplicated component before search in `src/components/`

## Refs（按需读取）

`components-reference.md`
