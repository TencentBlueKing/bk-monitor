<!--
  Tencent is pleased to support the open source community by making
  蓝鲸智云PaaS平台 (BlueKing PaaS) available.

  Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.

  蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.

  License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
  ---------------------------------------------------
  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
  to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  The above copyright notice and this permission notice shall be included in all copies or substantial portions of
  the Software.
  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
  THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
  CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
  IN THE SOFTWARE.
-->
<template>
  <header class="retrieve-toolbar">
    <t-button
      :theme="toolbar.favoriteShown ? 'primary' : 'default'"
      variant="outline"
      @click="emit('toggle-favorite')"
    >
      收藏
    </t-button>
    <t-input
      :model-value="keyword"
      placeholder="输入关键字检索"
      clearable
      @update:model-value="value => emit('update:keyword', value)"
      @enter="emit('search')"
    />
    <t-select :model-value="toolbar.timePreset" style="width: 120px" @change="onTimeChange">
      <t-option value="15m" label="近 15 分钟" />
      <t-option value="1h" label="近 1 小时" />
      <t-option value="24h" label="近 24 小时" />
    </t-select>
    <t-switch :model-value="toolbar.autoRefresh" label="自动刷新" @change="onAutoRefresh" />
    <t-button theme="primary" :loading="loading" @click="emit('search')">检索</t-button>
    <t-button variant="outline" @click="emit('save-favorite')">保存收藏</t-button>
    <t-button variant="outline" @click="emit('open-help')">说明</t-button>
  </header>
</template>

<script setup lang="ts">
import type { TimePreset, ToolbarSnapshot } from './toolbar-controller';

defineProps<{
  keyword: string;
  loading: boolean;
  toolbar: ToolbarSnapshot;
}>();

const emit = defineEmits<{
  'update:keyword': [value: string];
  search: [];
  'toggle-favorite': [];
  'change-time': [preset: TimePreset];
  'auto-refresh': [enabled: boolean];
  'save-favorite': [];
  'open-help': [];
}>();

const onTimeChange = (value: TimePreset) => {
  emit('change-time', value);
};

const onAutoRefresh = (value: boolean) => {
  emit('auto-refresh', value);
};
</script>
