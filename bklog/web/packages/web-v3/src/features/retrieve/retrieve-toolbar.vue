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
  <header class="retrieve-topbar" data-ui="topbar">
    <div class="retrieve-topbar__left">
      <button
        type="button"
        :class="['retrieve-fav-toggle', { 'is-active': toolbar.favoriteShown }]"
        data-ui="favorite-toggle"
        aria-label="收藏"
        :title="toolbar.favoriteShown ? '收起收藏' : '展开收藏'"
        @click="emit('toggle-favorite')"
      >
        <folder-icon size="16px" />
      </button>
      <t-select
        :model-value="indexSetId"
        :options="indexSetOptions"
        class="retrieve-topbar__index"
        borderless
        @change="onIndexSet"
      />
    </div>
    <div class="retrieve-topbar__right">
      <t-select :model-value="toolbar.timePreset" class="retrieve-topbar__time" borderless @change="onTimeChange">
        <template #prefixIcon>
          <time-icon />
        </template>
        <t-option value="15m" label="近 15 分钟" />
        <t-option value="1h" label="近 1 小时" />
        <t-option value="24h" label="近 24 小时" />
      </t-select>
      <label class="retrieve-topbar__refresh">
        <refresh-icon />
        <span>自动刷新</span>
        <t-switch size="small" :model-value="toolbar.autoRefresh" @change="onAutoRefresh" />
      </label>
      <t-button variant="text" @click="emit('save-favorite')">
        <template #icon><star-icon /></template>
        保存收藏
      </t-button>
      <t-button variant="text" @click="emit('open-help')">
        <template #icon><help-circle-icon /></template>
        说明
      </t-button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { FolderIcon, HelpCircleIcon, RefreshIcon, StarIcon, TimeIcon } from 'tdesign-icons-vue-next';

import type { TimePreset, ToolbarSnapshot } from './toolbar-controller';

defineProps<{
  toolbar: ToolbarSnapshot;
  indexSetId: string;
  indexSetOptions: Array<{ label: string; value: string }>;
}>();

const emit = defineEmits<{
  'toggle-favorite': [];
  'change-index-set': [id: string];
  'change-time': [preset: TimePreset];
  'auto-refresh': [enabled: boolean];
  'save-favorite': [];
  'open-help': [];
}>();

const onIndexSet = (value: string) => {
  emit('change-index-set', value);
};

const onTimeChange = (value: TimePreset) => {
  emit('change-time', value);
};

const onAutoRefresh = (value: boolean) => {
  emit('auto-refresh', value);
};
</script>
