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
  <aside class="retrieve-field-panel" data-ui="field-panel">
    <header class="retrieve-field-panel__header">
      <span>显示字段</span>
      <span class="retrieve-field-panel__tools">
        <button type="button" title="字段设置" data-ui="field-setting" @click="settingOpen = !settingOpen">
          <i class="bklog-icon bklog-shezhi" />
        </button>
      </span>
    </header>
    <t-input
      class="retrieve-field-panel__search"
      :model-value="state.filterQuery"
      placeholder="搜索字段"
      clearable
      @update:model-value="value => emit('filter', value)"
    >
      <template #prefix-icon>
        <i class="bklog-icon bklog-sousuo-" />
      </template>
    </t-input>
    <t-alert v-if="state.uiState === 'error'" theme="error" :message="state.error" />
    <section class="retrieve-field-section">
      <header>已选 {{ displayed.length }}</header>
      <label v-for="field in displayed" :key="field.name" class="retrieve-field-item" :data-ui="`field-${field.name}`">
        <t-checkbox :checked="field.visible" @change="value => emit('toggle', field.name, Boolean(value))" />
        <span class="retrieve-field-item__type" :data-type="field.kind">{{ typeChar(field.kind) }}</span>
        <span class="retrieve-field-item__name">{{ field.name }}</span>
        <span class="retrieve-field-item__alias">{{ field.alias }}</span>
        <button
          v-if="field.analyzable"
          type="button"
          class="retrieve-field-item__analyze"
          data-ui="field-analyze"
          title="字段分析"
          @click.prevent="analyzeName = field.name"
        >
          <i class="bklog-icon bklog-chart" />
        </button>
      </label>
    </section>
    <section class="retrieve-field-section">
      <header>其他字段 {{ hidden.length }}</header>
      <label v-for="field in hidden" :key="field.name" class="retrieve-field-item" :data-ui="`field-${field.name}`">
        <t-checkbox :checked="field.visible" @change="value => emit('toggle', field.name, Boolean(value))" />
        <span class="retrieve-field-item__type" :data-type="field.kind">{{ typeChar(field.kind) }}</span>
        <span class="retrieve-field-item__name">{{ field.name }}</span>
        <span class="retrieve-field-item__alias">{{ field.alias }}</span>
        <button
          v-if="field.analyzable"
          type="button"
          class="retrieve-field-item__analyze"
          data-ui="field-analyze"
          title="字段分析"
          @click.prevent="analyzeName = field.name"
        >
          <i class="bklog-icon bklog-chart" />
        </button>
      </label>
    </section>
    <aside v-if="settingOpen" class="retrieve-field-setting" data-ui="field-setting-panel">
      <header>字段设置</header>
      <p>勾选要在原始日志表展示的字段，至少保留一列。</p>
    </aside>
    <aside v-if="analyzeName" class="retrieve-field-analyze" data-ui="field-analyze-panel">
      <header>{{ analyzeName }} 分析</header>
      <p>按当前检索结果统计该字段取值分布（本波占位）。</p>
      <button type="button" @click="analyzeName = ''">关闭</button>
    </aside>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

import type { FieldKind, FieldSnapshot } from './field-controller';

const props = defineProps<{
  state: FieldSnapshot;
}>();

defineEmits<{
  toggle: [name: string, visible: boolean];
  filter: [value: string];
}>();

const settingOpen = ref(false);
const analyzeName = ref('');
const query = computed(() => props.state.filterQuery.toLowerCase());
const matched = computed(() => props.state.fields.filter(item => (
  !query.value
  || item.name.toLowerCase().includes(query.value)
  || item.alias.toLowerCase().includes(query.value)
)));
const displayed = computed(() => matched.value.filter(item => item.visible));
const hidden = computed(() => matched.value.filter(item => !item.visible));

const typeChar = (kind: FieldKind) => ({
  text: 'T',
  keyword: 'K',
  date: 'D',
  integer: 'N',
}[kind]);
</script>
