---
name: bklog-hooks
description: Hooks 地图（目录/命名/改动半径）。
---

# Hooks（最小地图）

## Map

Dir: `src/hooks/`
Naming: `use-xxx.ts` / `useXxx`
Core: useStore / useRoute / useRouter / useUtils / useLocale

## ChangeImpact（只写层级）

- New hook → `src/hooks/`
- Hook signature change → call-sites（views/components/hooks）
- Shared hook change → wide impact（优先全局检索调用点）

## Boundaries（否定约束）

- No side-effect leak（must cleanup timers/subscriptions）
- No multi-responsibility hook
- No duplicated hook before search in `src/hooks/`

## Refs（按需读取）

`hooks-reference.md`
