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
  <section class="collection-shell" data-ui="collection-root">
    <aside class="collection-left" data-ui="collection-left">
      <header class="collection-left__title">全部采集项 {{ visible.length }}</header>
      <t-input v-model="filterQuery" class="collection-left__search" placeholder="搜索" @enter="onFilter">
        <template #prefix-icon><i class="bklog-icon bklog-sousuo-" /></template>
      </t-input>
      <button
        type="button"
        :class="['collection-left__item', { 'is-active': scenario === 'all' }]"
        @click="onScenario('all')"
      >
        全部采集项
      </button>
      <button
        v-for="item in scenarioOptions.slice(1)"
        :key="item.value"
        type="button"
        :class="['collection-left__item', { 'is-active': scenario === item.value }]"
        @click="onScenario(item.value)"
      >
        {{ item.label }}
      </button>
    </aside>
    <section class="collection-right" data-ui="collection-right">
    <header class="collection-toolbar">
      <t-input v-model="filterQuery" placeholder="搜索采集名称" style="width: 220px" @enter="onFilter">
        <template #prefix-icon><search-icon /></template>
      </t-input>
      <t-select v-model="status" :options="statusOptions" style="width: 140px" @change="onStatus" />
      <t-button @click="onFilter">过滤</t-button>
      <t-button class="collection-toolbar__grow" theme="primary" @click="openWizard">新建采集</t-button>
    </header>
    <t-alert v-if="state.uiState === 'error' && !state.wizardOpen" theme="error" :message="state.error" />
    <t-table row-key="id" :data="visible" :columns="columns">
      <template #status="{ row }">
        <t-tag :theme="statusTheme(row.status)">{{ statusLabel(row.status) }}</t-tag>
      </template>
      <template #scenario="{ row }">
        {{ scenarioLabel(row.scenario) }}
      </template>
      <template #op="{ row }">
        <t-button v-if="row.status !== 'running'" variant="text" @click="onStart(row.id)">启动</t-button>
        <t-button v-else variant="text" @click="onStop(row.id)">停用</t-button>
        <t-button theme="danger" variant="text" @click="onRemove(row.id)">删除</t-button>
      </template>
    </t-table>
    <t-drawer
      :visible="state.wizardOpen"
      header="新建采集"
      size="480px"
      @close="closeWizard"
    >
      <t-steps :current="stepIndex" :options="stepOptions" />
      <t-alert v-if="state.error" theme="error" :message="state.error" />
      <t-form v-if="state.step === 'classify'">
        <t-form-item label="采集类型">
          <t-radio-group :value="state.draft.scenario" @change="onDraftScenario">
            <t-radio value="linux">主机日志</t-radio>
            <t-radio value="winevent">Windows Event</t-radio>
            <t-radio value="container_file">容器文件</t-radio>
            <t-radio value="container_stdout">标准输出</t-radio>
            <t-radio value="custom_report">自定义上报</t-radio>
          </t-radio-group>
        </t-form-item>
      </t-form>
      <t-form v-else-if="state.step === 'config'">
        <t-form-item label="名称">
          <t-input :model-value="state.draft.name" @update:model-value="value => patch({ name: value })" />
        </t-form-item>
        <t-form-item v-if="needPath" label="日志路径">
          <t-input :model-value="state.draft.path" @update:model-value="value => patch({ path: value })" />
        </t-form-item>
      </t-form>
      <t-form v-else-if="state.step === 'clean'">
        <t-form-item label="清洗">
          <t-input disabled model-value="默认清洗，可在后续波次扩展" />
        </t-form-item>
      </t-form>
      <t-form v-else>
        <t-form-item label="存储集群">
          <t-input :model-value="state.draft.cluster" @update:model-value="value => patch({ cluster: value })" />
        </t-form-item>
      </t-form>
      <template #footer>
        <t-button v-if="stepIndex > 0" @click="prev">上一步</t-button>
        <t-button v-if="stepIndex < 3" theme="primary" @click="next">下一步</t-button>
        <t-button v-else theme="primary" @click="submit">完成</t-button>
      </template>
    </t-drawer>
    </section>
  </section>
</template>

<script setup lang="ts">
import { SearchIcon } from 'tdesign-icons-vue-next';
import { computed, reactive, ref } from 'vue';

import {
  CollectionController,
  type CollectionSnapshot,
  type CollectStatus,
  type CollectorScenario,
} from './collection-controller';

const controller = new CollectionController();
const state = reactive<CollectionSnapshot>(controller.getState());
const visible = computed(() => controller.getVisibleItems());
const filterQuery = ref('');
const scenario = ref<CollectorScenario | 'all'>('all');
const status = ref<CollectStatus | 'all'>('all');
const scenarioOptions = [
  { label: '全部类型', value: 'all' },
  { label: '主机日志', value: 'linux' },
  { label: '容器输出', value: 'container_stdout' },
];
const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '运行中', value: 'running' },
  { label: '已停用', value: 'stopped' },
  { label: '失败', value: 'failed' },
  { label: '等待', value: 'pending' },
];
const statusText: Record<CollectStatus, string> = {
  running: '运行中',
  stopped: '已停用',
  failed: '失败',
  pending: '等待',
};
const scenarioText: Record<string, string> = {
  linux: '主机日志',
  winevent: 'Windows Event',
  container_file: '容器文件',
  container_stdout: '容器标准输出',
  custom_report: '自定义上报',
};
const stepOptions = [
  { title: '分类', value: 'classify' },
  { title: '配置', value: 'config' },
  { title: '清洗', value: 'clean' },
  { title: '存储', value: 'storage' },
];
const columns = [
  { colKey: 'name', title: '名称' },
  { colKey: 'scenario', title: '类型', cell: 'scenario', width: 140 },
  { colKey: 'status', title: '状态', cell: 'status', width: 120 },
  { colKey: 'path', title: '路径' },
  { colKey: 'op', title: '操作', cell: 'op', width: 160 },
];
const stepIndex = computed(() => stepOptions.findIndex(item => item.value === state.step));
const needPath = computed(() => state.draft.scenario === 'linux' || state.draft.scenario === 'winevent');

const sync = (next: CollectionSnapshot) => {
  Object.assign(state, next);
};

const onFilter = () => sync(controller.setFilterQuery(filterQuery.value));
const onScenario = (value: CollectorScenario | 'all') => sync(controller.setScenario(value));
const onStatus = (value: CollectStatus | 'all') => sync(controller.setStatus(value));
const onStart = (id: string) => sync(controller.start(id));
const onStop = (id: string) => sync(controller.stop(id));
const onRemove = (id: string) => sync(controller.remove(id));
const openWizard = () => sync(controller.openWizard());
const closeWizard = () => sync(controller.closeWizard());
const next = () => sync(controller.nextStep());
const prev = () => sync(controller.prevStep());
const submit = () => sync(controller.submitWizard());
const patch = (input: { name?: string; path?: string; cluster?: string }) => sync(controller.patchDraft(input));
const onDraftScenario = (value: CollectorScenario) => sync(controller.patchDraft({ scenario: value }));
const statusLabel = (value: CollectStatus) => statusText[value] ?? value;
const scenarioLabel = (value: CollectorScenario) => scenarioText[value] ?? value;
const statusTheme = (value: CollectStatus) => {
  if (value === 'failed') return 'danger';
  if (value === 'running') return 'warning';
  if (value === 'pending') return 'primary';
  return 'default';
};
</script>
