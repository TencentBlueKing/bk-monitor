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
  <section class="retrieve-page">
    <header class="retrieve-toolbar">
      <t-input
        v-model="keyword"
        placeholder="输入关键字检索"
        clearable
        @enter="onSearch"
      />
      <t-button theme="primary" :loading="state.uiState === 'loading'" @click="onSearch">检索</t-button>
      <t-button variant="outline" @click="openHelp">说明</t-button>
    </header>
    <t-alert v-if="state.uiState === 'error'" theme="error" :message="state.error" />
    <t-loading :loading="state.uiState === 'loading'">
      <t-empty v-if="state.uiState === 'empty'" description="没有匹配的日志" />
      <t-table
        v-else
        row-key="id"
        :data="state.records"
        :columns="columns"
        :empty="state.uiState === 'idle' ? '提交关键字开始检索' : '暂无数据'"
      />
    </t-loading>
    <t-dialog
      :visible="helpVisible"
      header="检索说明"
      :confirm-btn="null"
      cancel-btn="关闭"
      :z-index="helpZIndex"
      @close="closeHelp"
    >
      <p>关键字会自动去除首尾空白；条件变化后分页重置为 1；旧请求不会覆盖新结果。</p>
    </t-dialog>
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue';

import { overlayManager } from '../../shared/overlay/overlay-manager';
import {
  createLocalSearchFetcher,
  RetrieveSearchController,
  type RetrieveSnapshot,
} from './retrieve-search-controller';

const dataset = [
  { id: '1', dtEventTimeStamp: 1710000000001, log: 'error timeout from api' },
  { id: '2', dtEventTimeStamp: 1710000000002, log: 'info user login' },
  { id: '3', dtEventTimeStamp: 1710000000003, log: 'error disk full' },
];

const controller = new RetrieveSearchController(createLocalSearchFetcher(dataset));
const keyword = ref('');
const state = reactive<RetrieveSnapshot>(controller.getState());
const helpVisible = ref(false);
const helpZIndex = ref(2500);
const columns = [
  { colKey: 'id', title: 'ID', width: 80 },
  { colKey: 'dtEventTimeStamp', title: '时间', width: 180 },
  { colKey: 'log', title: '日志' },
];

const syncState = (next: RetrieveSnapshot) => {
  Object.assign(state, next);
};

const onSearch = async () => {
  syncState(await controller.submit({ keyword: keyword.value }));
};

const openHelp = () => {
  const record = overlayManager.open({ id: 'retrieve-help', kind: 'dialog', group: 'retrieve-help' });
  helpZIndex.value = record.zIndex;
  helpVisible.value = true;
};

const closeHelp = () => {
  overlayManager.close('retrieve-help');
  helpVisible.value = false;
};

const onEscape = (event: KeyboardEvent) => {
  if (event.key !== 'Escape') {
    return;
  }
  const closed = overlayManager.handleEscape();
  if (closed?.id === 'retrieve-help') {
    helpVisible.value = false;
  }
};

onMounted(() => {
  window.addEventListener('keydown', onEscape);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onEscape);
  controller.dispose();
  overlayManager.close('retrieve-help');
});
</script>
