---
name: bklog-utils
description: Utils 地图（落点/边界/改动半径）。
---

# Utils（最小地图）

## Map

Core: `src/common/util.js`
Message: `src/common/bkmagic.js`
Bus: `src/common/bus.js`
Field: `src/common/field-resolver.ts`
Global: `src/global/utils/`

## ChangeImpact（只写层级）

- New util → `src/common/util.js` 或 `src/global/utils/`
- Message change → `src/common/bkmagic.js` + call-sites
- Field resolve change → field-resolver + views/components

## Boundaries（否定约束）

- No copy-paste util into View/Component
- No new util before search in existing util modules
- No UI / DOM side-effects in pure util (except explicit DOM helpers)
