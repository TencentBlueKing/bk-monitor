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
  <section class="retrieve-searchbar" data-ui="searchbar">
    <div class="retrieve-searchbar__box">
      <div class="retrieve-searchbar__modes" data-ui="search-mode">
        <button
          v-for="item in modes"
          :key="item.id"
          type="button"
          :class="['retrieve-searchbar__mode', { 'is-active': mode === item.id }]"
          :data-ui="`search-mode-${item.id}`"
          @click="setMode(item.id)"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="retrieve-searchbar__body">
        <div v-if="mode === 'ui'" class="retrieve-searchbar__line">
          <div class="retrieve-searchbar__chips" data-ui="search-chips">
          <span v-for="(chip, index) in chips" :key="`${chip.field}-${chip.value}-${index}`" class="retrieve-chip">
            <em v-if="chip.field !== '*'">{{ chip.field }}</em>
            <span>{{ chip.value }}</span>
            <button type="button" aria-label="删除条件" @click="removeChip(index)">
              <i class="bklog-icon bklog-shanchu" />
            </button>
          </span>
          <button type="button" class="retrieve-chip retrieve-chip--add" data-ui="condition-add" @click="toggleConditionBuilder">+ 添加条件</button>
          </div>
          <t-input
            ref="inputRef"
            class="retrieve-searchbar__input"
            borderless
            :model-value="keyword"
            placeholder="请输入检索语句，回车检索"
            clearable
            @update:model-value="value => emit('update:keyword', value)"
            @focus="conditionBuilderOpen = false"
            @enter="emit('search')"
          />
        </div>
        <section v-if="mode === 'ui' && conditionBuilderOpen" class="retrieve-searchbar__builder" data-ui="condition-builder">
          <div
            v-for="(condition, index) in conditions"
            :key="condition.id"
            class="retrieve-searchbar__condition"
            data-ui="condition-row"
          >
            <select v-model="condition.logic" :disabled="index === 0" aria-label="关系">
              <option value="AND">AND</option>
              <option value="OR">OR</option>
            </select>
            <select v-model="condition.field" aria-label="字段">
              <option v-for="field in fieldOptions" :key="field" :value="field">{{ field === '*' ? '全文' : field }}</option>
            </select>
            <select v-model="condition.operator" aria-label="操作符">
              <option value="contains">包含</option>
              <option value="eq">等于</option>
              <option value="not">不包含</option>
            </select>
            <input v-model="condition.value" type="text" placeholder="输入条件值" @keydown.enter.prevent="applyConditions" />
            <button type="button" aria-label="删除条件" @click="removeCondition(index)">
              <i class="bklog-icon bklog-shanchu" />
            </button>
          </div>
          <footer class="retrieve-searchbar__builder-footer">
            <button type="button" data-ui="condition-row-add" @click="addCondition">继续添加</button>
            <button type="button" data-ui="condition-apply" @click="applyConditions">应用条件</button>
          </footer>
        </section>
        <textarea
          v-if="mode === 'sql'"
          class="retrieve-searchbar__sql"
          data-ui="search-sql"
          :value="keyword"
          placeholder="log:error AND status:500"
          @input="onSqlInput"
          @keydown.enter.exact.prevent="emit('search')"
        />
        <textarea
          v-if="mode === 'ai'"
          class="retrieve-searchbar__sql retrieve-searchbar__ai"
          data-ui="search-ai"
          :value="keyword"
          placeholder="用自然语言描述检索需求，例如：最近一小时 nginx 5xx"
          @input="onSqlInput"
          @keydown.enter.exact.prevent="emit('search')"
        />
      </div>
      <button type="button" class="retrieve-searchbar__icon-btn" data-ui="search-history" title="历史" @click="toggleHistory">
        <i class="bklog-icon bklog-history-2" />
      </button>
      <button type="button" class="retrieve-searchbar__icon-btn" data-ui="search-copy" title="复制检索条件" @click="copyQuery">
        <i class="bklog-icon bklog-copy" />
      </button>
      <button type="button" class="retrieve-searchbar__icon-btn" data-ui="search-clear" title="清空检索条件" @click="clearQuery">
        <i class="bklog-icon bklog-delete" />
      </button>
      <button type="button" class="retrieve-searchbar__icon-btn" data-ui="search-setting" title="查询设置" @click="toggleConditionBuilder">
        <i class="bklog-icon bklog-log-setting" />
      </button>
      <button
        type="button"
        class="retrieve-searchbar__submit"
        data-ui="search-submit"
        :disabled="loading"
        aria-label="检索"
        title="检索"
        @click="emit('search')"
      >
        <i class="bklog-icon bklog-sousuo-" />
      </button>
    </div>
    <ul v-if="historyOpen" class="retrieve-searchbar__history" data-ui="search-history-panel">
      <li v-if="!history.length" class="retrieve-searchbar__history-empty">暂无检索历史</li>
      <li v-for="item in history" :key="item">
        <button type="button" @click="onHistory(item)">{{ item }}</button>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

import { chipsToKeyword, parseSearchChips, type SearchChip } from './search-query';

const props = defineProps<{
  keyword: string;
  loading: boolean;
  history: string[];
}>();

const emit = defineEmits<{
  'update:keyword': [value: string];
  search: [];
  'apply-history': [value: string];
}>();

const mode = ref<'ui' | 'sql' | 'ai'>('ui');
const modes = [
  { id: 'ui' as const, label: 'UI模式' },
  { id: 'sql' as const, label: '语句模式' },
  { id: 'ai' as const, label: 'AI模式' },
];
const historyOpen = ref(false);
const conditionBuilderOpen = ref(false);
const inputRef = ref<{ focus?: () => void } | null>(null);
const chips = computed(() => parseSearchChips(props.keyword));
const fieldOptions = ['*', 'log', 'status', 'serverIp', 'path'];
let conditionId = 0;
interface ConditionRow {
  id: number;
  logic: 'AND' | 'OR';
  field: string;
  operator: 'contains' | 'eq' | 'not';
  value: string;
}
const createCondition = (): ConditionRow => ({
  id: conditionId++,
  logic: 'AND',
  field: '*',
  operator: 'contains',
  value: '',
});
const conditions = ref<ConditionRow[]>([createCondition()]);

const setMode = (value: 'ui' | 'sql' | 'ai') => {
  mode.value = value;
  historyOpen.value = false;
  conditionBuilderOpen.value = false;
};

const toggleHistory = () => {
  historyOpen.value = !historyOpen.value;
};

const openHistory = () => {
  historyOpen.value = true;
  conditionBuilderOpen.value = false;
};

const focusInput = () => {
  inputRef.value?.focus?.();
};

const toggleConditionBuilder = () => {
  conditionBuilderOpen.value = !conditionBuilderOpen.value;
  historyOpen.value = false;
};

const addCondition = () => {
  conditions.value.push(createCondition());
};

const removeCondition = (index: number) => {
  conditions.value.splice(index, 1);
  if (!conditions.value.length) {
    conditions.value.push(createCondition());
  }
};

const applyConditions = () => {
  const nextConditions: SearchChip[] = conditions.value
    .map(item => ({ ...item, value: item.value.trim() }))
    .filter(item => item.value)
    .flatMap(item => {
      const value = item.operator === 'not' ? `-${item.value}` : item.value;
      const chip = { field: item.field, value };
      return item.logic === 'OR' ? [{ field: '*', value: 'OR' }, chip] : [chip];
    });
  if (!nextConditions.length) {
    focusInput();
    return;
  }
  emit('update:keyword', chipsToKeyword([...chips.value, ...nextConditions]));
  conditionBuilderOpen.value = false;
  emit('search');
};

const removeChip = (index: number) => {
  emit('update:keyword', chipsToKeyword(chips.value.filter((_, itemIndex) => itemIndex !== index)));
};

const onSqlInput = (event: Event) => {
  emit('update:keyword', (event.target as HTMLTextAreaElement).value);
};

const onHistory = (value: string) => {
  historyOpen.value = false;
  emit('apply-history', value);
};

const copyQuery = () => {
  const text = props.keyword || chipsToKeyword(chips.value);
  void navigator.clipboard?.writeText(text);
};

const clearQuery = () => {
  emit('update:keyword', '');
  conditionBuilderOpen.value = false;
  historyOpen.value = false;
  emit('search');
};

defineExpose({ openHistory });
</script>
