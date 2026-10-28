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
  <section class="manage-right manage-module" data-ui="manage-right" :data-module="spec.id">
    <header class="collection-toolbar">
      <h2 class="manage-right__title">{{ spec.title }}</h2>
      <nav class="manage-module__tabs" data-ui="manage-module-tabs">
        <button
          v-for="item in spec.tabs"
          :key="item.id"
          type="button"
          :class="['manage-module__tab', { 'is-active': state.tab === item.id }]"
          :data-ui="`manage-tab-${item.id}`"
          @click="onTab(item.id)"
        >
          {{ item.title }}
        </button>
      </nav>
      <t-input v-model="filterQuery" placeholder="搜索名称" style="width: 200px" @enter="onFilter" />
      <t-button class="collection-toolbar__grow" theme="primary" data-ui="manage-create" @click="openSave">
        {{ spec.createLabel }}
      </t-button>
    </header>
    <t-empty v-if="!visible.length" :description="spec.empty" :data-ui="`${spec.id}-empty`" />
    <t-table v-else row-key="id" size="small" :data="visible" :columns="tableColumns">
      <template #op="{ row }">
        <t-button theme="danger" variant="text" @click="onRemove(row.id)">删除</t-button>
      </template>
    </t-table>
    <t-dialog
      :visible="saveVisible"
      :header="spec.createLabel"
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

import { ManageModuleController, type ManageModuleSnapshot } from './manage-module';

const props = defineProps<{ moduleId: string }>();

const controller = ref(new ManageModuleController(props.moduleId));
const spec = computed(() => controller.value.getSpec());
const state = reactive<ManageModuleSnapshot>(controller.value.getState());
const visible = computed(() => controller.value.getVisibleItems());
const filterQuery = ref('');
const saveVisible = ref(false);
const saveName = ref('');
const tableColumns = computed(() => [
  ...spec.value.columns,
  { colKey: 'op', title: '操作', cell: 'op', width: 100 },
]);

const sync = (next: ManageModuleSnapshot) => {
  Object.assign(state, next);
};

watch(() => props.moduleId, () => {
  controller.value = new ManageModuleController(props.moduleId);
  filterQuery.value = '';
  sync(controller.value.getState());
});

const onTab = (tab: string) => {
  filterQuery.value = '';
  sync(controller.value.setTab(tab));
};

const onFilter = () => {
  sync(controller.value.setFilterQuery(filterQuery.value));
};

const openSave = () => {
  saveName.value = '';
  saveVisible.value = true;
};

const onSave = () => {
  sync(controller.value.save(saveName.value));
  saveVisible.value = false;
};

const onRemove = (id: string) => {
  sync(controller.value.remove(id));
};
</script>
