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
  <section class="retrieve-graph-panel" data-ui="graph-panel">
    <header class="retrieve-graph-panel__meta">
      <span>时间分桶</span>
      <strong data-ui="graph-total">{{ total }} 条</strong>
    </header>
    <t-empty v-if="!buckets.length" description="没有可分析的日志" />
    <div v-else class="retrieve-graph-panel__bars" data-ui="graph-bars">
      <button
        v-for="item in buckets"
        :key="item.startTime"
        type="button"
        class="retrieve-graph-panel__bar"
        :title="`${formatTime(item.startTime)} · ${item.count}`"
      >
        <span :style="{ height: `${barHeight(item.count)}%` }" />
        <small>{{ item.count }}</small>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { GraphBucket } from './graph-controller';

const props = defineProps<{
  buckets: GraphBucket[];
}>();

const total = computed(() => props.buckets.reduce((sum, item) => sum + item.count, 0));
const maxCount = computed(() => Math.max(1, ...props.buckets.map(item => item.count)));

const barHeight = (count: number) => Math.max(8, Math.round((count / maxCount.value) * 100));

const formatTime = (value: number) => {
  const date = new Date(value);
  const pad = (item: number) => String(item).padStart(2, '0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
};
</script>
