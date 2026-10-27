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
    <aside v-show="!leftCollapsed" class="collection-left" data-ui="collection-left">
      <header class="collection-left__title">
        全部采集项
        <span class="collection-left__total">{{ state.items.length }}</span>
      </header>
      <div class="collection-left__search">
        <button type="button" class="collection-left__add" data-ui="collection-group-add" title="新建分组">+</button>
        <t-input v-model="groupQuery" placeholder="搜索" @enter="noop">
          <template #prefix-icon><i class="bklog-icon bklog-sousuo-" /></template>
        </t-input>
      </div>
      <nav class="collection-left__tree" data-ui="collection-groups">
        <button
          v-for="item in visibleGroups"
          :key="item.id"
          type="button"
          :class="['collection-left__item', { 'is-active': state.group === item.id }]"
          @click="onGroup(item.id)"
        >
          <i :class="['bklog-icon', item.id === 'all' ? 'bklog-all2' : 'bklog-rizhicaiji']" />
          <span class="collection-left__label">{{ item.name }}</span>
          <span class="collection-left__count">{{ item.count }}</span>
        </button>
      </nav>
    </aside>
    <button
      type="button"
      class="collection-collapse"
      data-ui="collection-collapse"
      :title="leftCollapsed ? '展开分组' : '收起分组'"
      @click="leftCollapsed = !leftCollapsed"
    >
      {{ leftCollapsed ? '>' : '<' }}
    </button>
    <section class="collection-right" data-ui="collection-right">
      <template v-if="!state.wizardOpen">
        <header class="collection-toolbar">
          <button type="button" class="collection-toolbar__create" data-ui="collection-create" @click="openWizard">
            <i class="bklog-icon bklog-plus" />
          </button>
          <button
            type="button"
            :class="['collection-toolbar__chip', { 'is-active': scenario === 'all' }]"
            @click="onScenario('all')"
          >全部</button>
          <button
            type="button"
            :class="['collection-toolbar__chip', { 'is-active': scenario === 'linux' }]"
            @click="onScenario('linux')"
          >主机</button>
          <button
            type="button"
            :class="['collection-toolbar__chip', { 'is-active': scenario === 'container_stdout' }]"
            @click="onScenario('container_stdout')"
          >容器</button>
          <t-select v-model="status" :options="statusOptions" class="collection-toolbar__status" @change="onStatus" />
          <t-input v-model="filterQuery" class="collection-toolbar__search" placeholder="搜索采集名称" @enter="onFilter">
            <template #suffix-icon><i class="bklog-icon bklog-sousuo-" /></template>
          </t-input>
        </header>
        <t-alert v-if="state.uiState === 'error'" theme="error" :message="state.error" />
        <t-table v-if="visible.length" row-key="id" :data="visible" :columns="columns">
          <template #name="{ row }">
            <button type="button" class="collection-name" @click="openWizard">{{ row.name }}</button>
          </template>
          <template #status="{ row }">
            <span :class="['collection-status', `is-${row.status}`]">{{ statusLabel(row.status) }}</span>
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
        <div v-else class="collection-empty" data-ui="collection-empty">
          <p>暂无采集项</p>
        </div>
        <footer class="collection-pager">
          <span>共 {{ visible.length }} 条</span>
          <span>10 条/页</span>
          <span>1 / 1</span>
        </footer>
      </template>
      <section v-else class="collection-wizard" data-ui="collection-wizard">
        <header class="collection-wizard__head">
          <h2>新建采集项</h2>
          <t-steps :current="stepIndex" :options="stepOptions" />
        </header>
        <t-alert v-if="state.error" theme="error" :message="state.error" />
        <div v-if="state.step === 'classify'" class="collection-classify">
          <section v-for="family in classifyFamilies" :key="family.value" class="collection-classify__family">
            <h3>{{ family.label }}</h3>
            <div class="collection-classify__cards">
              <button
                v-for="card in family.children"
                :key="card.value"
                type="button"
                :class="['collection-card', { 'is-active': state.draft.scenario === card.value }]"
                :data-ui="`classify-${card.value}`"
                @click="onDraftScenario(card.value)"
              >
                <i :class="['bklog-icon', card.icon]" />
                <span>{{ card.label }}</span>
              </button>
            </div>
          </section>
        </div>
        <t-form v-else-if="state.step === 'config'" class="collection-wizard__form">
          <t-form-item label="名称">
            <t-input :model-value="state.draft.name" @update:model-value="value => patch({ name: value })" />
          </t-form-item>
          <t-form-item v-if="needPath" label="日志路径">
            <t-input :model-value="state.draft.path" @update:model-value="value => patch({ path: value })" />
          </t-form-item>
        </t-form>
        <t-form v-else-if="state.step === 'clean'" class="collection-wizard__form">
          <t-form-item label="清洗">
            <t-input disabled model-value="默认清洗，可在后续波次扩展" />
          </t-form-item>
        </t-form>
        <t-form v-else class="collection-wizard__form">
          <t-form-item label="存储集群">
            <t-input :model-value="state.draft.cluster" @update:model-value="value => patch({ cluster: value })" />
          </t-form-item>
        </t-form>
        <footer class="collection-wizard__foot">
          <t-button @click="closeWizard">取消</t-button>
          <t-button v-if="stepIndex > 0" @click="prev">上一步</t-button>
          <t-button v-if="stepIndex < 3" theme="primary" @click="next">下一步</t-button>
          <t-button v-else theme="primary" @click="submit">完成</t-button>
        </footer>
      </section>
    </section>
  </section>
</template>

<script setup lang="ts">
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
const groups = computed(() => controller.getGroups());
const filterQuery = ref('');
const groupQuery = ref('');
const leftCollapsed = ref(false);
const scenario = ref<CollectorScenario | 'all'>('all');
const status = ref<CollectStatus | 'all'>('all');
const visibleGroups = computed(() => groups.value.filter(item => item.name.includes(groupQuery.value.trim())));
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
const classifyFamilies = [
  {
    label: '主机采集',
    value: 'host',
    children: [
      { label: '主机日志', value: 'linux' as CollectorScenario, icon: 'bklog-host' },
      { label: 'Windows Event', value: 'winevent' as CollectorScenario, icon: 'bklog-host' },
    ],
  },
  {
    label: '容器采集',
    value: 'container',
    children: [
      { label: '文件采集', value: 'container_file' as CollectorScenario, icon: 'bklog-rizhicaiji' },
      { label: '标准输出', value: 'container_stdout' as CollectorScenario, icon: 'bklog-rizhicaiji' },
    ],
  },
  {
    label: '其他',
    value: 'other',
    children: [
      { label: '自定义上报', value: 'custom_report' as CollectorScenario, icon: 'bklog-rizhitiqupeizhi' },
    ],
  },
];
const stepOptions = [
  { title: '接入类型', value: 'classify' },
  { title: '配置', value: 'config' },
  { title: '清洗', value: 'clean' },
  { title: '存储', value: 'storage' },
];
const columns = [
  { colKey: 'name', title: '采集项名称', cell: 'name' },
  { colKey: 'nameEn', title: '数据名', width: 160 },
  { colKey: 'scenario', title: '类型', cell: 'scenario', width: 140 },
  { colKey: 'status', title: '状态', cell: 'status', width: 120 },
  { colKey: 'cluster', title: '存储集群', width: 140 },
  { colKey: 'op', title: '操作', cell: 'op', width: 160 },
];
const stepIndex = computed(() => stepOptions.findIndex(item => item.value === state.step));
const needPath = computed(() => state.draft.scenario === 'linux' || state.draft.scenario === 'winevent');

const sync = (next: CollectionSnapshot) => {
  Object.assign(state, next);
};

const noop = () => undefined;
const onFilter = () => sync(controller.setFilterQuery(filterQuery.value));
const onGroup = (value: string) => sync(controller.setGroup(value));
const onScenario = (value: CollectorScenario | 'all') => {
  scenario.value = value;
  sync(controller.setScenario(value));
};
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
</script>
