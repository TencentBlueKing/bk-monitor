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
      <span class="retrieve-favorite-panel__title">
        收藏夹
        <em>{{ totalCount }}</em>
      </span>
      <span class="retrieve-favorite-panel__tools">
        <button type="button" title="新建收藏" data-ui="favorite-new" @click="emit('save')">
          <i class="bklog-icon bklog-plus" />
        </button>
        <button type="button" title="分享" data-ui="favorite-share">
          <i class="bklog-icon bklog-share" />
        </button>
        <button type="button" title="收藏管理">
          <i class="bklog-icon bklog-shezhi" />
        </button>
        <button type="button" title="收起" @click="emit('collapse')">
          <i class="bklog-icon bklog-collapse" />
        </button>
      </span>
    </header>
    <t-input
      class="retrieve-favorite-panel__search"
      :model-value="filterDraft"
      placeholder="搜索收藏"
      clearable
      @update:model-value="onFilterInput"
    >
      <template #prefix-icon>
        <i class="bklog-icon bklog-sousuo-" />
      </template>
    </t-input>
    <label class="retrieve-favorite-panel__current">
      <input type="checkbox" :checked="state.currentOnly" @change="onCurrentOnlyNative">
      仅显示当前索引集
    </label>
    <t-alert v-if="state.uiState === 'error'" theme="error" :message="state.error" />
    <nav class="retrieve-favorite-tree" data-ui="favorite-tree">
      <section v-for="group in visibleGroups" :key="group.groupId" class="retrieve-favorite-group">
        <button
          type="button"
          class="retrieve-favorite-group__title"
          :data-ui="`favorite-group-${group.groupId}`"
          @click="toggleGroup(group.groupId)"
        >
          <i :class="['bklog-icon', collapsed[group.groupId] ? 'bklog-arrow-right' : 'bklog-arrow-down']" />
          <i class="bklog-icon bklog-folder-fill" />
          <span class="retrieve-favorite-group__name">{{ group.groupName }}</span>
          <em>{{ group.favorites.length }}</em>
        </button>
        <ul v-show="!collapsed[group.groupId]" class="retrieve-favorite-list">
          <li
            v-for="item in group.favorites"
            :key="item.id"
            :class="['retrieve-favorite-item', { 'is-active': item.id === state.activeId }]"
          >
            <button type="button" class="retrieve-favorite-item__main" @click="onApply(item.id)">
              <span>{{ item.name }}</span>
              <small>{{ item.keyword }}</small>
            </button>
            <span class="retrieve-favorite-item__ops">
              <button type="button" title="分享" @click.stop="onShare(item.keyword)">
                <i class="bklog-icon bklog-share" />
              </button>
              <t-popconfirm content="确认删除该收藏？" @confirm="onRemove(item.id)">
                <button type="button" title="删除">
                  <i class="bklog-icon bklog-shanchu" />
                </button>
              </t-popconfirm>
            </span>
          </li>
        </ul>
      </section>
    </nav>
    <p v-if="!visibleGroups.length" class="retrieve-favorite-empty">没有匹配的收藏</p>
  </aside>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue';

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
  save: [];
  collapse: [];
}>();

const filterDraft = ref(props.state.filterQuery);
const collapsed = reactive<Record<string, boolean>>({});
const totalCount = computed(() => props.visibleGroups.reduce((sum, group) => sum + group.favorites.length, 0));

const onFilterInput = (value: string) => {
  filterDraft.value = value;
  emit('filter', value);
};

const onCurrentOnlyNative = (event: Event) => {
  emit('current-only', (event.target as HTMLInputElement).checked);
};

const toggleGroup = (groupId: string) => {
  collapsed[groupId] = !collapsed[groupId];
};

const onApply = (id: string) => {
  emit('apply', id);
};

const onRemove = (id: string) => {
  emit('remove', id);
};

const onShare = (keyword: string) => {
  void navigator.clipboard?.writeText(keyword);
};
</script>
