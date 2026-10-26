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
      <h2 class="resource-page__title">日志聚类</h2>
      <t-input v-model="query" placeholder="过滤模式或原文" style="width: 240px" @enter="refresh" />
      <t-button theme="primary" @click="refresh">聚类</t-button>
    </header>
    <t-empty v-if="!groups.length" description="没有匹配的聚类" />
    <t-table v-else row-key="pattern" :data="groups" :columns="columns" />
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';

import { ClusteringController, type ClusterGroup } from './clustering-controller';

const dataset = [
  { id: '1', dtEventTimeStamp: Date.now() - 60_000, log: 'error timeout from api 12' },
  { id: '2', dtEventTimeStamp: Date.now() - 120_000, log: 'error timeout from api 34' },
  { id: '3', dtEventTimeStamp: Date.now() - 180_000, log: 'info user login' },
];

const controller = new ClusteringController();
const query = ref('');
const groups = ref<ClusterGroup[]>(controller.group(dataset));
const columns = [
  { colKey: 'pattern', title: '模式' },
  { colKey: 'count', title: '数量', width: 100 },
  { colKey: 'sample', title: '样例' },
];

const refresh = () => {
  groups.value = controller.group(dataset, query.value);
};
</script>
