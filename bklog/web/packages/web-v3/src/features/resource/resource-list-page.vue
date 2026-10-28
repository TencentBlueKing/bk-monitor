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
  <section class="manage-right" data-ui="manage-right">
      <header class="collection-toolbar">
        <h2 class="manage-right__title">{{ catalog.title }}</h2>
        <t-input v-model="filterQuery" placeholder="搜索名称或关键字" style="width: 220px" @enter="onFilter" />
        <t-select v-model="status" :options="statusOptions" style="width: 140px" @change="onStatus" />
        <t-button @click="onFilter">过滤</t-button>
        <t-button class="collection-toolbar__grow" theme="primary" @click="openSave">新增</t-button>
      </header>
      <t-alert v-if="state.uiState === 'error'" theme="error" :message="state.error" />
      <t-empty v-if="!visible.length" description="没有匹配的资源" />
      <t-table v-else row-key="id" size="small" :data="visible" :columns="columns">
        <template #status="{ row }">
          <t-tag :theme="statusTheme(row.status)">{{ statusLabel(row.status) }}</t-tag>
        </template>
        <template #op="{ row }">
          <t-button theme="danger" variant="text" @click="onRemove(row.id)">删除</t-button>
        </template>
      </t-table>
      <t-dialog
        :visible="saveVisible"
        header="保存资源"
        confirm-btn="保存"
        cancel-btn="取消"
        @confirm="onSave"
        @close="saveVisible = false"
      >
        <t-form>
          <t-form-item label="名称">
            <t-input v-model="saveName" placeholder="输入名称" />
          </t-form-item>
        </t-form>
      </t-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';

import { MANAGE_MODULES } from '../catalog';
import {
  ResourceListController,
  type ResourceSnapshot,
  type ResourceStatus,
} from '../../shared/resource/resource-list-controller';

const props = defineProps<{ moduleId: string }>();

const catalog = computed(() => MANAGE_MODULES.find(item => item.id === props.moduleId) ?? MANAGE_MODULES[0]);
const controller = ref(new ResourceListController(catalog.value.items));
const state = reactive<ResourceSnapshot>(controller.value.getState());
const visible = computed(() => controller.value.getVisibleItems());
const filterQuery = ref('');
const status = ref<ResourceStatus | 'all'>('all');
const saveVisible = ref(false);
const saveName = ref('');
const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '运行中', value: 'running' },
  { label: '就绪', value: 'ready' },
  { label: '已停用', value: 'stopped' },
  { label: '失败', value: 'failed' },
];
const statusText: Record<string, string> = {
  running: '运行中',
  ready: '就绪',
  stopped: '已停用',
  failed: '失败',
};
const columns = [
  { colKey: 'name', title: '名称' },
  { colKey: 'status', title: '状态', cell: 'status', width: 120 },
  { colKey: 'keyword', title: '关键字', width: 160 },
  { colKey: 'op', title: '操作', cell: 'op', width: 100 },
];

const sync = (next: ResourceSnapshot) => {
  Object.assign(state, next);
};

watch(() => props.moduleId, () => {
  controller.value = new ResourceListController(catalog.value.items);
  filterQuery.value = '';
  status.value = 'all';
  sync(controller.value.getState());
});

const onFilter = () => {
  sync(controller.value.setFilterQuery(filterQuery.value));
};

const onStatus = (value: ResourceStatus | 'all') => {
  sync(controller.value.setStatus(value));
};

const openSave = () => {
  saveName.value = '';
  saveVisible.value = true;
};

const onSave = () => {
  const next = controller.value.save({ name: saveName.value });
  sync(next);
  if (next.uiState !== 'error') {
    saveVisible.value = false;
  }
};

const onRemove = (id: string) => {
  sync(controller.value.remove(id));
};

const statusLabel = (value: string) => statusText[value] ?? value;

const statusTheme = (value: ResourceStatus) => {
  if (value === 'failed') return 'danger';
  if (value === 'running') return 'warning';
  if (value === 'ready') return 'success';
  return 'default';
};
</script>
