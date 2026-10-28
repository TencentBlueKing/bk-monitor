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
  <section class="retrieve-grep-panel" data-ui="grep-panel">
    <header class="retrieve-toolbar">
      <strong>Grep</strong>
      <t-input data-ui="grep-field" :model-value="state.field" placeholder="字段，默认 log" style="width: 140px" @update:model-value="onField" />
      <t-input data-ui="grep-pattern" :model-value="state.pattern" placeholder="正则，如 error|timeout" @update:model-value="onPattern" @enter="emit('run')" />
      <t-button data-ui="grep-run" theme="primary" :disabled="state.uiState === 'waiting'" @click="emit('run')">过滤</t-button>
    </header>
    <t-alert v-if="state.uiState === 'waiting'" theme="warning" message="主检索进行中，Grep 等待完成后再过滤" />
    <t-alert v-if="state.uiState === 'error'" theme="error" :message="state.error" />
    <t-empty v-if="state.uiState === 'empty'" description="没有匹配的 Grep 结果" />
    <t-table
      v-else-if="state.uiState === 'success'"
      row-key="id"
      :data="state.matches"
      :columns="columns"
    />
  </section>
</template>

<script setup lang="ts">
import type { GrepSnapshot } from './grep-controller';

defineProps<{
  state: GrepSnapshot;
}>();

const emit = defineEmits<{
  field: [value: string];
  pattern: [value: string];
  run: [];
}>();

const columns = [
  { colKey: 'id', title: 'ID', width: 80 },
  { colKey: 'log', title: '日志' },
];

const onField = (value: string) => {
  emit('field', value);
};

const onPattern = (value: string) => {
  emit('pattern', value);
};
</script>
