---
name: bklog-hooks
description: BKLog 项目 Vue Composition API Hooks 使用指南。包含项目内封装的可复用 hooks 目录、使用方式和最佳实践。当需要使用或创建 hooks、处理响应式逻辑时使用。
---

# BKLog Hooks 指南

## Hooks 目录

所有公共 hooks 位于 `src/hooks/` 目录。

## 核心 Hooks

### useStore

获取 Vuex store 实例。

```typescript
import useStore from '@/hooks/use-store';

const store = useStore();
const spaceUid = store.state.spaceUid;
store.dispatch('requestIndexSetQuery');
```

### useRouter / useRoute

获取路由实例和当前路由。

```typescript
import useRouter from '@/hooks/use-router';
import useRoute from '@/hooks/use-route';

const router = useRouter();
const route = useRoute();

// 导航
router.push({ name: 'retrieve', query: { spaceUid } });

// 获取参数
const indexId = route.params.indexId;
```

### useUtils

通用工具函数 hook，主要用于时区处理。

```typescript
import useUtils from '@/hooks/use-utils';

const { timezone, formatTimeZone, formatResponseListTimeZoneString } = useUtils();

// 格式化时间
const formattedTime = formatTimeZone('2024-11-01T08:56:24.274552Z');
// 输出: 2025-11-04 21:44:38+0800

// 批量格式化列表时间字段
const formattedList = formatResponseListTimeZoneString(list, {}, ['created_at', 'updated_at']);
```

### useLocale

国际化相关。

```typescript
import useLocale from '@/hooks/use-locale';

const { t, locale } = useLocale();
const text = t('搜索');
```

### useRetrieveEvent

检索模块事件订阅。

```typescript
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import { RetrieveEvent } from '@/views/retrieve-core/retrieve-events';

const { on, emit } = useRetrieveEvent();

// 订阅事件
on(RetrieveEvent.TREND_GRAPH_SEARCH, (data) => {
  // 处理趋势图搜索
});

// 触发事件
emit(RetrieveEvent.LEFT_FIELD_INFO_UPDATE, fieldInfo);
```

### useRetrieveParams

获取和管理检索参数。

```typescript
import useRetrieveParams from '@/hooks/use-retrieve-params';

const { 
  indexId, 
  keyword, 
  addition, 
  timeRange,
  getSearchParams 
} = useRetrieveParams();
```

### useTrendChart

趋势图数据处理。

```typescript
import useTrendChart from '@/hooks/use-trend-chart';

const { chartOptions, updateChartData } = useTrendChart();
```

### useResizeObserve

元素尺寸监听。

```typescript
import useResizeObserve from '@/hooks/use-resize-observe';

const { width, height } = useResizeObserve(elementRef);

watch([width, height], ([w, h]) => {
  // 处理尺寸变化
});
```

### useIntersectionObserver

元素可见性监听。

```typescript
import useIntersectionObserver from '@/hooks/use-intersection-observer';

const { isVisible } = useIntersectionObserver(elementRef, {
  threshold: 0.1,
});
```

### useScroll

滚动监听。

```typescript
import useScroll from '@/hooks/use-scroll';

const { scrollTop, scrollLeft, isScrolling } = useScroll(containerRef);
```

### useFieldName

字段名称处理。

```typescript
import useFieldName from '@/hooks/use-field-name';

const { getFieldDisplayName, getFieldAlias } = useFieldName();
```

### useJsonFormatter

JSON 格式化。

```typescript
import useJsonFormatter from '@/hooks/use-json-formatter';

const { format, highlight } = useJsonFormatter();
const formattedJson = format(jsonData);
```

### useTextSegmentation

文本分词。

```typescript
import useTextSegmentation from '@/hooks/use-text-segmentation';

const { segment, highlight } = useTextSegmentation();
```

## Hook 开发规范

### 命名规范

- 文件名: `use-xxx.ts`
- 导出函数名: `useXxx`

### 模板

```typescript
import { ref, computed, onMounted, onUnmounted } from 'vue';
import useStore from './use-store';

export default function useCustomHook(options?: { key?: string }) {
  const store = useStore();
  
  // 响应式状态
  const data = ref<string>('');
  
  // 计算属性
  const derivedData = computed(() => {
    return data.value.toUpperCase();
  });
  
  // 方法
  const updateData = (val: string) => {
    data.value = val;
  };
  
  // 生命周期
  onMounted(() => {
    // 初始化逻辑
  });
  
  onUnmounted(() => {
    // 清理逻辑
  });
  
  return {
    data,
    derivedData,
    updateData,
  };
}
```

## 使用建议

1. **优先使用已有 hooks**: 先查找 `src/hooks/` 是否有满足需求的 hook
2. **保持单一职责**: 每个 hook 只处理一个关注点
3. **正确清理副作用**: 在 `onUnmounted` 中清理订阅、定时器等
4. **类型安全**: 使用 TypeScript 定义参数和返回值类型
