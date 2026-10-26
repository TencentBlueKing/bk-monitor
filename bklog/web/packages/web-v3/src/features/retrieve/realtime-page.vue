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
      <h2 class="resource-page__title">实时日志</h2>
      <t-button theme="primary" :disabled="state.uiState === 'streaming'" @click="start">开始</t-button>
      <t-button :disabled="state.uiState !== 'streaming'" @click="stop">停止</t-button>
      <t-button @click="append">追加一条</t-button>
      <t-tag>{{ state.uiState }}</t-tag>
    </header>
    <t-empty v-if="!state.records.length" description="尚未收到实时日志" />
    <t-table v-else row-key="id" :data="state.records" :columns="columns" />
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, reactive } from 'vue';

import { RealtimeController, type RealtimeSnapshot } from './realtime-controller';

const controller = new RealtimeController(8);
const state = reactive<RealtimeSnapshot>(controller.getState());
const columns = [
  { colKey: 'id', title: 'ID', width: 80 },
  { colKey: 'dtEventTimeStamp', title: '时间', width: 180 },
  { colKey: 'log', title: '日志' },
];
let seq = 0;

const sync = (next: RealtimeSnapshot) => {
  Object.assign(state, next);
};

const start = () => {
  sync(controller.start());
};

const stop = () => {
  sync(controller.stop());
};

const append = () => {
  seq += 1;
  sync(controller.append({
    id: String(seq),
    dtEventTimeStamp: Date.now(),
    log: `stream line ${seq}`,
  }));
};

onBeforeUnmount(() => {
  controller.stop();
});
</script>
