---
name: bk-magicbox-vue
description: 蓝鲸 MagicBox Vue 组件库使用指南。包含常用组件的使用方式、属性配置和最佳实践。当需要使用 UI 组件、了解组件 API 或实现交互功能时使用。
---

# 蓝鲸 MagicBox Vue 组件库指南

## 引入方式

项目已全局注册 bk-magic-vue 组件，可直接在模板中使用 `bk-xxx` 组件。

```javascript
// 按需引入（如需要）
import { bkMessage, bkInfoBox } from 'bk-magic-vue';
```

## 常用组件

### 按钮 bk-button

```vue
<template>
  <bk-button theme="primary" :loading="isLoading" @click="handleClick">
    提交
  </bk-button>
  
  <bk-button theme="default" outline>
    取消
  </bk-button>
  
  <bk-button theme="danger" :disabled="isDisabled">
    删除
  </bk-button>
</template>
```

**常用属性:**
- `theme`: 'default' | 'primary' | 'warning' | 'success' | 'danger'
- `size`: 'small' | 'normal' | 'large'
- `loading`: boolean
- `disabled`: boolean
- `outline`: boolean

### 输入框 bk-input

```vue
<template>
  <bk-input
    v-model="value"
    placeholder="请输入"
    :clearable="true"
    :disabled="false"
    @change="handleChange"
    @enter="handleEnter"
  />
  
  <!-- 搜索框 -->
  <bk-input
    v-model="keyword"
    type="search"
    right-icon="bk-icon icon-search"
    @right-icon-click="handleSearch"
  />
  
  <!-- 密码框 -->
  <bk-input v-model="password" type="password" />
  
  <!-- 数字输入 -->
  <bk-input v-model="num" type="number" :min="0" :max="100" />
</template>
```

### 选择器 bk-select

```vue
<template>
  <bk-select
    v-model="selected"
    :clearable="true"
    :searchable="true"
    :multiple="false"
    @change="handleChange"
  >
    <bk-option
      v-for="item in options"
      :key="item.id"
      :id="item.id"
      :name="item.name"
    />
  </bk-select>
  
  <!-- 分组 -->
  <bk-select v-model="selected">
    <bk-option-group
      v-for="group in groupOptions"
      :key="group.id"
      :name="group.name"
    >
      <bk-option
        v-for="item in group.children"
        :key="item.id"
        :id="item.id"
        :name="item.name"
      />
    </bk-option-group>
  </bk-select>
</template>
```

### 表格 bk-table

```vue
<template>
  <bk-table
    :data="tableData"
    :pagination="pagination"
    :max-height="500"
    @page-change="handlePageChange"
    @page-limit-change="handleLimitChange"
    @sort-change="handleSortChange"
  >
    <bk-table-column
      label="名称"
      prop="name"
      :sortable="true"
      :min-width="100"
    />
    
    <bk-table-column label="状态" prop="status">
      <template #default="{ row }">
        <span :class="['status', row.status]">{{ row.statusText }}</span>
      </template>
    </bk-table-column>
    
    <bk-table-column label="操作" :width="150">
      <template #default="{ row }">
        <bk-button text @click="handleEdit(row)">编辑</bk-button>
        <bk-button text theme="danger" @click="handleDelete(row)">删除</bk-button>
      </template>
    </bk-table-column>
  </bk-table>
</template>

<script>
export default {
  data() {
    return {
      pagination: {
        current: 1,
        count: 100,
        limit: 10,
      },
    };
  },
};
</script>
```

### 弹窗 bk-dialog

```vue
<template>
  <bk-dialog
    v-model="visible"
    title="弹窗标题"
    :width="600"
    :mask-close="false"
    :confirm-loading="submitting"
    @confirm="handleConfirm"
    @cancel="handleCancel"
  >
    <template #default>
      <!-- 弹窗内容 -->
    </template>
    
    <template #footer>
      <!-- 自定义底部 -->
    </template>
  </bk-dialog>
</template>
```

### Sideslider 侧边栏

```vue
<template>
  <bk-sideslider
    :is-show.sync="isShow"
    :width="640"
    :title="title"
    :quick-close="true"
    :before-close="handleBeforeClose"
  >
    <template #content>
      <!-- 内容 -->
    </template>
  </bk-sideslider>
</template>
```

### 消息提示

```javascript
import { bkMessage, bkInfoBox } from 'bk-magic-vue';

// 消息提示
bkMessage({
  theme: 'success',  // 'success' | 'warning' | 'error' | 'primary'
  message: '操作成功',
  delay: 3000,
  ellipsisLine: 2,
});

// 确认框
bkInfoBox({
  title: '确认删除？',
  subTitle: '删除后不可恢复',
  confirmFn: () => {
    // 确认操作
  },
  cancelFn: () => {
    // 取消操作
  },
});

// 项目封装的快捷方式
import { messageSuccess, messageError } from '@/common/bkmagic';
messageSuccess('成功');
messageError('失败');
```

### Loading 加载

```vue
<template>
  <!-- 容器 loading -->
  <div v-bkloading="{ isLoading: loading, title: '加载中' }">
    内容
  </div>
  
  <!-- 组件形式 -->
  <bk-loading :loading="loading" :title="loadingText">
    <div>内容</div>
  </bk-loading>
</template>
```

### 表单 bk-form

```vue
<template>
  <bk-form
    ref="formRef"
    :model="formData"
    :rules="rules"
    :label-width="100"
  >
    <bk-form-item label="名称" property="name" :required="true">
      <bk-input v-model="formData.name" />
    </bk-form-item>
    
    <bk-form-item label="类型" property="type">
      <bk-select v-model="formData.type">
        <bk-option id="1" name="类型1" />
        <bk-option id="2" name="类型2" />
      </bk-select>
    </bk-form-item>
    
    <bk-form-item>
      <bk-button theme="primary" @click="handleSubmit">提交</bk-button>
    </bk-form-item>
  </bk-form>
</template>

<script>
export default {
  data() {
    return {
      formData: { name: '', type: '' },
      rules: {
        name: [
          { required: true, message: '必填项', trigger: 'blur' },
          { max: 50, message: '最多50字符', trigger: 'blur' },
        ],
      },
    };
  },
  methods: {
    async handleSubmit() {
      const valid = await this.$refs.formRef.validate();
      if (valid) {
        // 提交
      }
    },
  },
};
</script>
```

### Popover 弹出框

```vue
<template>
  <bk-popover
    theme="light"
    placement="bottom"
    :arrow="true"
    :distance="10"
  >
    <bk-button>触发按钮</bk-button>
    
    <template #content>
      <div>弹出内容</div>
    </template>
  </bk-popover>
</template>
```

### Tab 标签页

```vue
<template>
  <bk-tab
    :active.sync="activeTab"
    type="unborder-card"
    @tab-change="handleTabChange"
  >
    <bk-tab-panel name="tab1" label="标签1">
      内容1
    </bk-tab-panel>
    <bk-tab-panel name="tab2" label="标签2">
      内容2
    </bk-tab-panel>
  </bk-tab>
</template>
```

### 日期选择器 bk-date-picker

```vue
<template>
  <bk-date-picker
    v-model="date"
    type="daterange"
    :placeholder="['开始日期', '结束日期']"
    :shortcuts="shortcuts"
    @change="handleChange"
  />
</template>

<script>
export default {
  data() {
    return {
      date: [],
      shortcuts: [
        { text: '最近7天', value: () => [new Date() - 7 * 86400000, new Date()] },
        { text: '最近30天', value: () => [new Date() - 30 * 86400000, new Date()] },
      ],
    };
  },
};
</script>
```

### Overflow Tips 文本溢出提示

```vue
<template>
  <!-- 指令方式 -->
  <p v-bk-overflow-tips class="ellipsis-text">
    很长的文本内容...
  </p>
  
  <!-- 组件方式 -->
  <bk-overflow-tips>
    <span>很长的文本内容...</span>
  </bk-overflow-tips>
</template>

<style>
.ellipsis-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
```

## TSX 使用方式

```tsx
import { defineComponent, ref } from 'vue';

export default defineComponent({
  setup() {
    const value = ref('');
    const loading = ref(false);
    
    return () => (
      <div>
        <bk-input
          v-model={value.value}
          placeholder="请输入"
        />
        
        <bk-button
          theme="primary"
          loading={loading.value}
          onClick={() => { /* 处理点击 */ }}
        >
          提交
        </bk-button>
        
        <bk-select
          v-model={value.value}
          clearable
        >
          {options.map(item => (
            <bk-option
              key={item.id}
              id={item.id}
              name={item.name}
            />
          ))}
        </bk-select>
      </div>
    );
  },
});
```

## 注意事项

1. **v-model**: Vue 2 中使用 `.sync` 修饰符的属性，在 TSX 中需要同时传递 value 和 onChange
2. **slot**: TSX 中使用 `v-slots` 或 `{{ default: () => <div>内容</div> }}`
3. **样式**: 组件库样式已全局引入，无需单独引入
4. **主题**: 使用 `$primaryColor` 等 SCSS 变量保持风格一致
