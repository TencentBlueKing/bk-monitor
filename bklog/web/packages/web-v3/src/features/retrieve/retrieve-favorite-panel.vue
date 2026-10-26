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
  <aside class="retrieve-favorite-panel" data-ui="favorite-panel">
    <header class="retrieve-favorite-panel__header">
      <strong>收藏</strong>
      <t-checkbox :checked="state.currentOnly" @change="onCurrentOnly">仅当前索引集</t-checkbox>
    </header>
    <t-input
      :model-value="filterDraft"
      placeholder="搜索收藏名称或关键字"
      clearable
      @update:model-value="onFilterInput"
      @enter="onFilterEnter"
    />
    <t-alert v-if="state.uiState === 'error'" theme="error" :message="state.error" />
    <t-collapse :value="openedGroups">
      <t-collapse-panel
        v-for="group in visibleGroups"
        :key="group.groupId"
        :value="group.groupId"
        :header="`${group.groupName} (${group.favorites.length})`"
      >
        <ul class="retrieve-favorite-list">
          <li
            v-for="item in group.favorites"
            :key="item.id"
            :class="['retrieve-favorite-item', { 'is-active': item.id === state.activeId }]"
          >
            <button type="button" class="retrieve-favorite-item__main" @click="onApply(item.id)">
              <span>{{ item.name }}</span>
              <small>{{ item.keyword }}</small>
            </button>
            <t-popconfirm content="确认删除该收藏？" @confirm="onRemove(item.id)">
              <t-button size="small" variant="text" theme="danger">删除</t-button>
            </t-popconfirm>
          </li>
        </ul>
      </t-collapse-panel>
    </t-collapse>
    <t-empty v-if="!visibleGroups.length" description="没有匹配的收藏" />
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

import type { FavoriteGroup, FavoriteSnapshot } from './favorite-controller';

const props = defineProps<{
  state: FavoriteSnapshot;
  visibleGroups: FavoriteGroup[];
}>();

const emit = defineEmits<{
  filter: [value: string];
  'current-only': [value: boolean];
  apply: [id: string];
  remove: [id: string];
}>();

const filterDraft = ref(props.state.filterQuery);
const openedGroups = computed(() => props.visibleGroups.map(group => group.groupId));

const onFilterInput = (value: string) => {
  filterDraft.value = value;
};

const onFilterEnter = () => {
  emit('filter', filterDraft.value);
};

const onCurrentOnly = (checked: boolean | { checked?: boolean }) => {
  emit('current-only', typeof checked === 'boolean' ? checked : Boolean(checked?.checked));
};

const onApply = (id: string) => {
  emit('apply', id);
};

const onRemove = (id: string) => {
  emit('remove', id);
};
</script>
