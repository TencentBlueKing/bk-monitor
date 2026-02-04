---
name: bklog-coding-patterns
description: 编码约定地图（命名/落点/边界）。
---

# Coding Patterns（最小地图）

## Map（落点）

- View: `src/views/`
- Components: `src/components/`（目录 kebab-case）
- Hooks: `src/hooks/`（`use-xxx.ts`）
- Store: `src/store/`
- Services: `src/services/`

## Naming（只保留稳定约定）

- Dir: kebab-case
- TSX component: `index.tsx`
- Vue SFC: `index.vue`
- Style: `index.scss`
- Types: `type.ts` / `*.type.ts`

## ChangeImpact（只写层级）

- New UI module → View + Components + Hooks + Store + Services
- Rename/move component dir → imports in View/Components

## Boundaries（否定约束）

- No mixed component paradigms in a single file（Options + Composition）
- No business logic in View render
