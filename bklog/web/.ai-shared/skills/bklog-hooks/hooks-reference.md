# Hooks 参考

## 完整 Hooks 列表

| Hook | 文件 | 说明 |
|------|------|------|
| useStore | use-store.ts | 获取 Vuex store 实例 |
| useRouter | use-router.ts | 获取 Vue Router 实例 |
| useRoute | use-route.ts | 获取当前路由信息 |
| useLocale | use-locale.ts | 国际化 |
| useUtils | use-utils.ts | 通用工具（时区处理等）|
| useRetrieveEvent | use-retrieve-event.ts | 检索事件订阅 |
| useRetrieveParams | use-retrieve-params.ts | 检索参数管理 |
| useTrendChart | use-trend-chart.ts | 趋势图数据处理 |
| useResizeObserve | use-resize-observe.ts | 元素尺寸监听 |
| useIntersectionObserver | use-intersection-observer.ts | 元素可见性监听 |
| useMutationObserver | use-mutation-observer.ts | DOM 变化监听 |
| useScroll | use-scroll.ts | 滚动监听 |
| useWheel | use-wheel.ts | 鼠标滚轮监听 |
| useElementEvent | use-element-event.ts | DOM 事件监听 |
| useFieldName | use-field-name.ts | 字段名称处理 |
| useFieldEgges | use-field-egges.ts | 字段边缘处理 |
| useFieldAliasRequestParams | use-field-alias-request-params.tsx | 字段别名请求参数 |
| useJsonFormatter | use-json-formatter.ts | JSON 格式化 |
| useJsonRoot | use-json-root.ts | JSON 根节点处理 |
| useTextSegmentation | use-text-segmentation.ts | 文本分词 |
| useSegmentPop | use-segment-pop.ts | 分词弹窗 |
| useTruncateText | use-truncate-text.ts | 文本截断 |
| useListSort | use-list-sort.ts | 列表排序 |
| useNavMenu | use-nav-menu.ts | 导航菜单 |

## 事件类型

`src/views/retrieve-core/retrieve-events.ts` 定义的事件：

```typescript
export const RetrieveEvent = {
  TREND_GRAPH_SEARCH: 'trend-graph-search',
  LEFT_FIELD_INFO_UPDATE: 'left-field-info-update',
  TABLE_SEARCH: 'table-search',
  REFRESH_SEARCH: 'refresh-search',
  // ...
};
```
