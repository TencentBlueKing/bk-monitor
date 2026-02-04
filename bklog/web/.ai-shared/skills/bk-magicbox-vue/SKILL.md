---
name: bk-magicbox-vue
description: MagicBox UI 地图（可用性/边界/改动半径）。
---

# MagicBox（最小地图）

## Map

UI lib: `bk-magic-vue`
Usage: template/tsx 中直接使用 `bk-*`
Message: `bkMessage` / `bkInfoBox`（以及项目封装 `src/common/bkmagic.js`）

## ChangeImpact（只写层级）

- UI interaction change → View/Component + MagicBox props/events
- Message style change → `src/common/bkmagic.js` + call-sites

## Boundaries（否定约束）

- No re-implement MagicBox component before search
- No custom UI pattern that conflicts with existing `bk-*` usage
