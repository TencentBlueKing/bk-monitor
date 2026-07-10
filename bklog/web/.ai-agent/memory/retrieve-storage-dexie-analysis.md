# Retrieve Storage / Dexie Analysis

## Scope

- Project: `bklog/web`
- Ignored: `bklog/web/packages/web-v1`
- Target data flow: retrieve `/search/` result rows and `/fields/` metadata.

## LocalStorage / SessionStorage Usage Summary

### Global user settings

- `src/store/default-values.ts`
  - `STORAGE_KEY_BKLOG_GLOBAL`
  - Stores UI preferences and global retrieve options: table line wrap, JSON format, show alias, text ellipsis, field-setting width, last space/biz, etc.
- `src/store/index.js`
  - `updateStorage` writes global storage back to localStorage.

### Retrieve preferences

- `src/components/time-range/time-range.tsx`
  - `SEARCH_DEFAULT_TIME`
  - `SEARCH_DEFAULT_TIME_FORMAT`
- `src/views/retrieve-helper.tsx`
  - recent index set memory: `MONITOR_LOG_RECENT_INDEX_SET_ID`
  - favorite panel width/show/current index flags
- `src/views/retrieve-hub.tsx`, `src/global/version-switch.vue`, `src/store/index.js`
  - `retrieve_version`
- `src/views/retrieve-v2/search-result-panel/log-result/index.vue`
  - `SEARCH_STORAGE_ACTIVE_TAB`

### Retrieve field / index selector caches

- `src/views/retrieve-v2/condition-comp/select-index-set.tsx`
  - `INDEX_SET_TAG_CATCH`
  - `CATCH_INDEX_SET_ID_LIST`
- `src/common/util.js`
  - `TABLE_SELECT_FILED`
  - `TABLE_FORCE`
  - `CATCH_INDEX_SET_ID_LIST`

### SessionStorage temporary flows

- `src/store/helper.ts`
  - Scene retrieve session records.
- extract clone / collection update pages store one-shot clone/update data in `sessionStorage`.

## Vuex Local State Flow

### `/fields/` flow

1. `store.dispatch('requestIndexSetFieldInfo')`
2. Endpoint:
   - normal: `retrieve/getLogTableHead` -> `/search/index_set/:index_set_id/fields/`
   - union: `unionSearch/unionMapping`
   - scene: `retrieve/getSceneFields`
3. Commits:
   - `resetIndexFieldInfo({ is_loading: true })`
   - `updateIndexFieldInfo(res.data)`
   - `updataOperatorDictionary(res.data)`
   - `updateNotTextTypeFields(res.data)`
   - `updateIndexSetFieldConfig(res.data)`
   - `retrieve/updateFiledSettingConfigID(res.data.config_id)`
   - `retrieve/updateCatchFieldCustomConfig(res.data.user_custom_config)`
   - `resetVisibleFields()`
   - `resetIndexSetOperatorConfig()`
4. Consumers:
   - search bar field selector
   - result field filter
   - log rows visible fields / width calculation
   - context and real-time log field config
   - aggregation terms / dropdown values

Decision: `/fields/` metadata is configuration-scale data and deeply coupled with Vuex reactivity, aliases, visible fields, operator config and UI settings. It is not moved to Dexie in this step.

### `/search/` flow before Dexie

1. `store.dispatch('requestIndexSetQuery')`
2. Endpoint:
   - normal: `/search/index_set/:index_set_id/search/`
   - union: `/search/index_set/union_search/`
   - scene: `/search/scene/search/`
3. Response blob -> `readBlobRespToJson` -> `parseBigNumberList` / `normalizeLogRenderList`
4. Full row list committed into Vuex:
   - `indexSetQueryResult.list`
5. Rendering:
   - v2 `log-rows.tsx` reads `indexSetQueryResult.list`
   - v3 `origin-log-result` reads outer `indexSetQueryResult.list` for context side panel

Problem: full log row objects are large and become Vuex reactive state. Search pagination repeatedly concatenates rows, causing high memory pressure and expensive render dependency tracking.

## Dexie Storage Design Implemented

### Files

- `src/storage/core/db.ts`
- `src/storage/repositories/retrieve-row.repository.ts`
- `src/storage/services/retrieve-row-cache.service.ts`
- `src/storage/index.ts`

### Schema

Database: `bklog-web-storage`

Table: `retrieveRows`

```ts
{
  key: string;       // `${queryKey}:${seq}`
  queryKey: string;  // one search request sequence
  seq: number;       // row order
  row: object;       // full normalized log row
  createdAt: number;
  expireAt: number;
}
```

### New Vuex lightweight metadata

`IndexSetQueryResult` now includes:

```ts
row_keys: string[];
row_query_key: string;
cached_count: number;
```

`list` remains as a small compatibility mirror for first-page / old consumers.

### Search write flow after Dexie

1. `/search/` returns rows.
2. Normalize rows.
3. Store full rows in IndexedDB through `retrieveRowCacheService`.
4. Commit only row keys and metadata into Vuex:
   - `row_keys`
   - `row_query_key`
   - `cached_count`
5. Keep at most first 50 rows in `indexSetQueryResult.list` as compatibility mirror.

### Render read flow after Dexie

- v2 `log-rows.tsx`
  - `tableDataSize` is based on `row_keys.length || list.length`.
  - `setRenderList` reads current visible range by keys through `retrieveRowCacheService.getRows(keys)`.
  - If row keys are missing, falls back to legacy `list`.
- v3 `origin-log-result/index.tsx`
  - If `row_keys` exist, reads first page from Dexie for side panel.
  - Otherwise falls back to `list`.

## Expected Performance Benefit

- Vuex no longer owns full large result rows for all loaded pages.
- Reduces Vue reactivity cost and retained heap from big row objects.
- Rendering code reads only current visible page/range.
- Dexie + small memory LRU keeps recently accessed rows fast while letting large pages stay outside Vuex.

## Constraints / Follow-up

- `/fields/` remains in Vuex due to high reactive coupling.
- Existing consumers that directly use `indexSetQueryResult.list` should gradually migrate to `row_keys + retrieveRowCacheService.getRows`.
- Current compatibility mirror keeps first 50 rows in `list`; future work can remove it after all consumers migrate.
