---
name: bklog-coding-patterns
description: BKLog 项目代码实现规范和最佳实践。包含命名规范、文件组织、组件编写、类型定义等编码习惯。当需要编写新代码、重构或保持代码风格一致性时使用。
---

# BKLog 代码实现规范

## 文件命名

### 组件/模块

- **目录名**: kebab-case（如 `time-range/`, `log-view/`）
- **Vue SFC**: kebab-case.vue（如 `index.vue`, `step-add.vue`）
- **TSX 组件**: index.tsx（目录为组件名）
- **样式文件**: 与组件同名或 index.scss
- **类型文件**: type.ts 或 xxx.type.ts

### 函数/变量

```typescript
// 常量：大写下划线
const TABLE_FOUNT_FAMILY = 'Menlo, Monaco...';
const BK_LOG_STORAGE = { LAST_INDEX_SET_ID: 'lastIndexSetId' };

// 函数：camelCase
const formatTimeZone = (time: number) => {};
const handleClick = () => {};

// 类：PascalCase
class Storage { }

// 接口/类型：PascalCase
interface LogSearchResult { }
type IndexSetDataList = { }[];
```

## TSX 组件模式

```tsx
import { defineComponent, PropType, ref, computed, watch, onMounted } from 'vue';
import './index.scss';

export default defineComponent({
  name: 'ComponentName',
  
  props: {
    // 必填属性
    value: {
      type: String as PropType<string>,
      required: true,
    },
    // 可选属性带默认值
    disabled: {
      type: Boolean,
      default: false,
    },
    // 复杂类型
    data: {
      type: Array as PropType<DataItem[]>,
      default: () => [],
    },
  },
  
  emits: ['change', 'update:value', 'submit'],
  
  setup(props, { emit, slots, expose }) {
    // 1. refs
    const inputRef = ref<HTMLInputElement>();
    
    // 2. 响应式状态
    const localValue = ref(props.value);
    
    // 3. computed
    const isValid = computed(() => localValue.value.length > 0);
    
    // 4. watch
    watch(() => props.value, (newVal) => {
      localValue.value = newVal;
    });
    
    // 5. methods
    const handleChange = (val: string) => {
      localValue.value = val;
      emit('change', val);
      emit('update:value', val);
    };
    
    // 6. lifecycle
    onMounted(() => {
      // 初始化逻辑
    });
    
    // 7. expose (如需要)
    expose({ focus: () => inputRef.value?.focus() });
    
    // 8. render
    return () => (
      <div class="component-name">
        <bk-input
          ref={inputRef}
          v-model={localValue.value}
          disabled={props.disabled}
          onChange={handleChange}
        />
        {slots.default?.()}
      </div>
    );
  },
});
```

## Vue SFC 组件模式

```vue
<template>
  <div class="component-name">
    <bk-input
      v-model="localValue"
      :disabled="disabled"
      @change="handleChange"
    />
    <slot />
  </div>
</template>

<script>
export default {
  name: 'ComponentName',
  
  props: {
    value: {
      type: String,
      required: true,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
  },
  
  data() {
    return {
      localValue: this.value,
    };
  },
  
  watch: {
    value(newVal) {
      this.localValue = newVal;
    },
  },
  
  methods: {
    handleChange(val) {
      this.$emit('change', val);
      this.$emit('update:value', val);
    },
  },
};
</script>

<style lang="scss" scoped>
@import '@/scss/mixins/index.scss';

.component-name {
  // 样式
}
</style>
```

## Store Action 模式

```javascript
// Vuex action
async requestData({ commit, state }, payload) {
  try {
    const res = await http.request('domain/apiName', {
      params: payload.params,
      data: payload.data,
    });
    
    if (res.result) {
      commit('SET_DATA', res.data);
      return res.data;
    }
    
    throw new Error(res.message);
  } catch (error) {
    console.error('requestData error:', error);
    throw error;
  }
}
```

## 服务定义模式

```javascript
// src/services/xxx.js
export const apiName = {
  url: '/api/path/:id/',
  method: 'post',
};

// 带类型定义 (TypeScript)
export interface ResponseType {
  id: number;
  name: string;
}

export const typedApi = {
  url: '/api/typed/',
  method: 'get',
};
```

## 样式规范

### SCSS 变量和 Mixin

```scss
@import '@/scss/conf.scss';
@import '@/scss/mixins/index.scss';

.component {
  // 使用变量
  color: $primaryColor;
  
  // 使用 mixin
  @include ellipsis();
  @include flex-center();
  @include scroller($backgroundColor, $thumbColor);
}
```

### BEM 命名

```scss
.log-view {
  // Block
  
  &__header {
    // Element
  }
  
  &__content {
    // Element
    
    &--active {
      // Modifier
    }
  }
  
  &--loading {
    // Modifier
  }
}
```

## 类型定义模式

```typescript
// 接口定义
export interface FieldInfo {
  field_name: string;
  field_type: 'text' | 'keyword' | 'date' | 'integer';
  is_analyzed: boolean;
  description?: string;
}

// 类型别名
export type FieldList = FieldInfo[];

// 联合类型
export type Status = 'pending' | 'running' | 'success' | 'failed';

// 泛型
export interface ApiResponse<T> {
  result: boolean;
  data: T;
  message: string;
  code: number;
}
```

## 注释规范

```javascript
/**
 * 格式化时间戳为日期字符串
 * @param {number|string} val - 时间戳或 ISO 时间字符串
 * @param {boolean} isTimezone - 是否包含时区信息
 * @returns {string} 格式化后的日期字符串，格式：2023-11-04 12:00:00
 * @example
 * formatDate(1699084800000) // "2023-11-04 12:00:00"
 */
export function formatDate(val, isTimezone = false) {
  // ...
}
```

## 错误处理模式

```typescript
// 异步操作
try {
  const result = await api.getData();
  // 处理成功
} catch (error) {
  console.error('getData failed:', error);
  messageError(error.message || '操作失败');
  // 可选：上报错误
}

// Promise 链
api.getData()
  .then(handleSuccess)
  .catch((error) => {
    messageError(error.message);
  });
```

## 常用代码模式

### 防抖/节流

```javascript
import { Debounce } from '@/common/util';

// 装饰器方式
@Debounce(300)
handleSearch() { }

// 函数方式
const debouncedSearch = debounce(search, 300);
```

### 条件渲染

```tsx
// TSX
return () => (
  <div>
    {condition && <Component />}
    {condition ? <A /> : <B />}
    {list.map(item => <Item key={item.id} data={item} />)}
  </div>
);
```

### v-model 双向绑定

```tsx
// TSX 组件
<bk-input v-model={localValue.value} />

// 自定义组件
<CustomInput
  value={props.value}
  onInput={(val) => emit('update:value', val)}
/>
```
