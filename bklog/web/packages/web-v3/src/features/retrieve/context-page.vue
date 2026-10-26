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
  <section class="resource-page">
    <header class="retrieve-toolbar">
      <h2 class="resource-page__title">上下文日志</h2>
      <t-select v-model="anchorId" :options="anchorOptions" style="width: 180px" @change="open" />
      <t-switch v-model="searching" label="主检索进行中" @change="open" />
    </header>
    <t-alert v-if="state.uiState === 'waiting'" theme="warning" message="主检索进行中，上下文等待完成后再展开" />
    <t-empty v-if="state.uiState === 'empty'" description="找不到锚点日志" />
    <template v-if="state.uiState === 'success'">
      <t-table row-key="id" :data="rows" :columns="columns" />
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue';

import { ContextController, type ContextSnapshot } from './context-controller';

const records = [
  { id: '1', dtEventTimeStamp: 1, log: 'one' },
  { id: '2', dtEventTimeStamp: 2, log: 'two' },
  { id: '3', dtEventTimeStamp: 3, log: 'three' },
];

const controller = new ContextController();
const anchorId = ref('2');
const searching = ref(false);
const state = reactive<ContextSnapshot>(controller.open(records, anchorId.value, searching.value));
const anchorOptions = records.map(item => ({ label: item.log, value: item.id }));
const columns = [
  { colKey: 'role', title: '位置', width: 80 },
  { colKey: 'id', title: 'ID', width: 80 },
  { colKey: 'log', title: '日志' },
];
const rows = computed(() => [
  ...state.before.map(item => ({ ...item, role: '前' })),
  ...records.filter(item => item.id === state.anchorId).map(item => ({ ...item, role: '当前' })),
  ...state.after.map(item => ({ ...item, role: '后' })),
]);

const open = () => {
  Object.assign(state, controller.open(records, anchorId.value, searching.value));
};
</script>
