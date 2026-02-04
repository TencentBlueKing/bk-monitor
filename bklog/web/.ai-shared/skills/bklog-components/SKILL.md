---
name: bklog-components
description: BKLog 项目公共组件使用指南。包含项目内封装的可复用组件目录、使用方式和最佳实践。当需要使用或创建公共组件、了解组件 API 或查找现有组件时使用。
---

# BKLog 公共组件指南

## 组件目录结构

```
src/components/
├── basic-tab/              # 基础 Tab 组件
├── bklog-popover/          # 自定义 Popover
├── collection-access/      # 采集接入组件（多步骤流程）
├── common/                 # 通用基础组件
├── empty-status/           # 空状态组件
├── filter-rule/            # 过滤规则配置
├── global-dialog/          # 全局弹窗
├── global-setting/         # 全局设置
├── log-button/             # 日志按钮（全局注册）
├── log-icon/               # 日志图标（全局注册）
├── log-masking/            # 脱敏相关组件
├── log-view/               # 日志查看组件
├── monitor-echarts/        # ECharts 图表封装
├── nav/                    # 导航组件
├── rule-table/             # 规则表格
├── step-box/               # 步骤组件
├── time-range/             # 时间范围选择器
└── user-selector/          # 用户选择器
```

## 全局注册组件

以下组件在 `main.js` 中全局注册，可直接使用：

```javascript
// 使用方式
<log-button>按钮</log-button>
<log-icon type="search" />
<json-format-wrapper :data="jsonData" />
```

## 常用组件示例

### 空状态组件

```vue
<template>
  <empty-status
    :type="emptyType"
    :show-text="showText"
    @operation="handleOperation"
  />
</template>

<script>
// type: 'empty' | 'search-empty' | 'no-auth' | '403' | '404' | '500'
</script>
```

### 时间范围选择器

```tsx
import TimeRange from '@/components/time-range/time-range.tsx';

<TimeRange
  value={timeRange}
  onChange={handleTimeChange}
  timezone={timezone}
/>
```

### 日志查看组件

```vue
<template>
  <log-view
    :log-data="logData"
    :fields="fields"
    :highlight-keyword="keyword"
  />
</template>
```

### ECharts 趋势图

```vue
<template>
  <trend-chart
    :chart-data="chartData"
    :title="chartTitle"
    @data-zoom="handleZoom"
  />
</template>

<script>
import TrendChart from '@/components/monitor-echarts/trend-chart.vue';
</script>
```

## 组件开发规范

### 文件组织

```
component-name/
├── index.tsx        # 主组件文件
├── index.scss       # 样式文件
└── types.ts         # 类型定义（可选）
```

### TSX 组件模板

```tsx
import { defineComponent, PropType } from 'vue';
import './index.scss';

export default defineComponent({
  name: 'ComponentName',
  props: {
    value: {
      type: String as PropType<string>,
      default: '',
    },
  },
  emits: ['change', 'update:value'],
  setup(props, { emit }) {
    const handleChange = (val: string) => {
      emit('change', val);
      emit('update:value', val);
    };

    return () => (
      <div class="component-name">
        {/* 组件内容 */}
      </div>
    );
  },
});
```

### Vue SFC 组件模板

```vue
<template>
  <div class="component-name">
    <!-- 组件内容 -->
  </div>
</template>

<script>
export default {
  name: 'ComponentName',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  data() {
    return {};
  },
  methods: {},
};
</script>

<style lang="scss" scoped>
@import '@/scss/mixins/index.scss';
.component-name {
  // 样式
}
</style>
```

## 全局组件目录

`src/global/` 包含应用级全局组件：

```
global/
├── ai-assitant/       # AI 助手
├── bk-space-choice/   # 空间选择器
├── edit-input/        # 可编辑输入框
├── head-navi/         # 头部导航
├── json-view/         # JSON 查看器
├── match-mode/        # 匹配模式选择
└── utils/             # 全局工具函数
```
