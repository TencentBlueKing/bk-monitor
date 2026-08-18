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
- Monitor embed new-tab (`__IS_MONITOR_COMPONENT__` or `from=monitor`) must open `{top.origin}/?bizId=#/log-retrieval?...`，not bklog `/retrieve`
- Independent bklog `window.open` URLs must not inherit layout query `from` / `hl`
- `setQueryCondition` addition.`value` must be `string[]`；store 会把标量/`null`/`undefined` 收成数组。不要在 operator 映射里对未归一化的 `value[0]` 做 eager 读取
- UI 检索栏保留 `custom-placeholder` slot；无自定义内容时宿主 `display: none`，不要用空 `li` 参与 `flex-wrap`；有自定义内容时保留 `paddingLeft`（`blueking_language` + `getAiSpanPaddingLeft`）给输入提示让位，不要删这段计算
