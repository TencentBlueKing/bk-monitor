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
  <section class="retrieve-shell">
    <retrieve-favorite-panel
      v-if="toolbar.favoriteShown"
      :state="favorite"
      :visible-groups="visibleGroups"
      @filter="onFavoriteFilter"
      @current-only="onCurrentOnly"
      @apply="onApplyFavorite"
      @remove="onRemoveFavorite"
    />
    <section class="retrieve-main">
      <retrieve-toolbar
        v-model:keyword="keyword"
        :loading="search.uiState === 'loading'"
        :toolbar="toolbar"
        @search="onSearch"
        @toggle-favorite="onToggleFavorite"
        @change-time="onChangeTime"
        @auto-refresh="onAutoRefresh"
        @save-favorite="openSave"
        @open-help="openHelp"
      />
      <t-alert v-if="search.uiState === 'error'" theme="error" :message="search.error" />
      <t-loading :loading="search.uiState === 'loading'">
        <t-empty v-if="search.uiState === 'empty'" description="没有匹配的日志" />
        <t-table
          v-else
          row-key="id"
          :data="search.records"
          :columns="columns"
          :empty="search.uiState === 'idle' ? '提交关键字开始检索' : '暂无数据'"
        />
      </t-loading>
      <retrieve-grep-panel
        :state="grep"
        @field="onGrepField"
        @pattern="onGrepPattern"
        @run="onRunGrep"
      />
    </section>
    <t-dialog
      :visible="helpVisible"
      header="检索说明"
      :confirm-btn="null"
      cancel-btn="关闭"
      :z-index="helpZIndex"
      @close="closeHelp"
    >
      <p>关键字会自动去除首尾空白；条件或时间变化后分页重置为 1；旧请求不会覆盖新结果。</p>
      <p>收藏按分组展示，应用后回填关键字并重新检索；自动刷新不重置分页。</p>
    </t-dialog>
    <t-dialog
      :visible="saveVisible"
      header="保存收藏"
      confirm-btn="保存"
      cancel-btn="取消"
      :z-index="saveZIndex"
      @confirm="onSaveFavorite"
      @close="closeSave"
    >
      <t-form>
        <t-form-item label="名称">
          <t-input v-model="saveName" placeholder="输入收藏名称" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';

import { overlayManager } from '../../shared/overlay/overlay-manager';
import { FavoriteController, type FavoriteSnapshot } from './favorite-controller';
import { GrepController, type GrepSnapshot } from './grep-controller';
import RetrieveFavoritePanel from './retrieve-favorite-panel.vue';
import RetrieveGrepPanel from './retrieve-grep-panel.vue';
import {
  createLocalSearchFetcher,
  RetrieveSearchController,
  type RetrieveSnapshot,
} from './retrieve-search-controller';
import RetrieveToolbar from './retrieve-toolbar.vue';
import {
  ToolbarController,
  type SearchIntent,
  type TimePreset,
  type ToolbarSnapshot,
} from './toolbar-controller';

const now = Date.now();
const dataset = [
  { id: '1', dtEventTimeStamp: now - 60_000, log: 'error timeout from api', indexSetId: 'index-a' },
  { id: '2', dtEventTimeStamp: now - 120_000, log: 'info user login', indexSetId: 'index-a' },
  { id: '3', dtEventTimeStamp: now - 180_000, log: 'error disk full', indexSetId: 'index-a' },
];

const searchController = new RetrieveSearchController(createLocalSearchFetcher(dataset));
const favoriteController = new FavoriteController();
const toolbarController = new ToolbarController(intent => {
  void submitSearch(intent);
});

const keyword = ref('');
const saveName = ref('');
const grepController = new GrepController();
const search = reactive<RetrieveSnapshot>(searchController.getState());
const favorite = reactive<FavoriteSnapshot>(favoriteController.getState());
const toolbar = reactive<ToolbarSnapshot>(toolbarController.getState());
const grep = reactive<GrepSnapshot>(grepController.getState());
const visibleGroups = computed(() => favoriteController.getVisibleGroups());
const helpVisible = ref(false);
const saveVisible = ref(false);
const helpZIndex = ref(2500);
const saveZIndex = ref(2510);
const columns = [
  { colKey: 'id', title: 'ID', width: 80 },
  { colKey: 'dtEventTimeStamp', title: '时间', width: 180 },
  { colKey: 'log', title: '日志' },
];

const syncSearch = (next: RetrieveSnapshot) => {
  Object.assign(search, next);
};

const syncFavorite = (next: FavoriteSnapshot) => {
  Object.assign(favorite, next);
};

const syncToolbar = (next: ToolbarSnapshot) => {
  Object.assign(toolbar, next);
};

const syncGrep = (next: GrepSnapshot) => {
  Object.assign(grep, next);
};

const refreshGrep = () => {
  syncGrep(grepController.search(search.records, search.uiState === 'loading'));
};

const submitSearch = async (intent?: SearchIntent) => {
  const timeRange = intent?.timeRange ?? toolbar.timeRange;
  const page = intent?.resetPage ? 1 : search.page;
  syncSearch(await searchController.submit({
    keyword: keyword.value,
    page,
    startTime: timeRange.startTime,
    endTime: timeRange.endTime,
  }));
  refreshGrep();
};

const onSearch = async () => {
  await submitSearch({ resetPage: false, timeRange: toolbar.timeRange });
};

const onToggleFavorite = () => {
  syncToolbar(toolbarController.toggleFavoriteShown());
};

const onChangeTime = async (preset: TimePreset) => {
  const { state, intent } = toolbarController.setTimePreset(preset);
  syncToolbar(state);
  if (keyword.value.trim()) {
    await submitSearch(intent);
  }
};

const onAutoRefresh = (enabled: boolean) => {
  syncToolbar(toolbarController.setAutoRefresh(enabled));
};

const onFavoriteFilter = (value: string) => {
  syncFavorite(favoriteController.setFilterQuery(value));
};

const onCurrentOnly = (value: boolean) => {
  syncFavorite(favoriteController.setCurrentOnly(value));
};

const onApplyFavorite = async (id: string) => {
  const result = favoriteController.apply(id);
  syncFavorite(result.state);
  if (result.keyword) {
    keyword.value = result.keyword;
    await submitSearch({ resetPage: true, timeRange: toolbar.timeRange });
  }
};

const onRemoveFavorite = (id: string) => {
  syncFavorite(favoriteController.remove(id));
};

const onGrepField = (value: string) => {
  syncGrep(grepController.setField(value));
};

const onGrepPattern = (value: string) => {
  syncGrep(grepController.setPattern(value));
};

const onRunGrep = () => {
  refreshGrep();
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

const openSave = () => {
  const record = overlayManager.open({ id: 'retrieve-save-favorite', kind: 'dialog', group: 'retrieve-save' });
  saveZIndex.value = record.zIndex;
  saveName.value = keyword.value.trim();
  saveVisible.value = true;
};

const closeSave = () => {
  overlayManager.close('retrieve-save-favorite');
  saveVisible.value = false;
};

const onSaveFavorite = () => {
  const next = favoriteController.save({
    name: saveName.value,
    keyword: keyword.value,
    groupId: 'private',
    indexSetId: 'index-a',
  });
  syncFavorite(next);
  if (next.uiState !== 'error') {
    closeSave();
  }
};

const onEscape = (event: KeyboardEvent) => {
  if (event.key !== 'Escape') {
    return;
  }
  const closed = overlayManager.handleEscape();
  if (closed?.id === 'retrieve-help') {
    helpVisible.value = false;
  }
  if (closed?.id === 'retrieve-save-favorite') {
    saveVisible.value = false;
  }
};

onMounted(() => {
  window.addEventListener('keydown', onEscape);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onEscape);
  searchController.dispose();
  toolbarController.dispose();
  overlayManager.close('retrieve-help');
  overlayManager.close('retrieve-save-favorite');
});
</script>
