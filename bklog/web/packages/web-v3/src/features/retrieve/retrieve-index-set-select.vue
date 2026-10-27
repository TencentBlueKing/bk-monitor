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
  <div ref="rootRef" class="retrieve-index-select" data-ui="index-set">
    <button type="button" class="retrieve-index-select__trigger" data-ui="index-set-trigger" @click="toggle">
      <span class="retrieve-index-select__label" :title="activeLabel">{{ activeLabel }}</span>
      <i :class="['bklog-icon', 'bklog-arrow-down', { 'is-open': open }]" />
    </button>
    <section v-if="open" class="retrieve-index-select__popover" data-ui="index-set-popover">
      <div class="retrieve-index-select__search">
        <i class="bklog-icon bklog-search" />
        <input
          ref="inputRef"
          v-model.trim="query"
          data-ui="index-set-filter"
          type="text"
          placeholder="搜索索引集"
          @keydown.escape.stop.prevent="close"
        />
      </div>
      <p v-if="error" class="retrieve-index-select__error" data-ui="index-set-error">{{ error }}</p>
      <ul v-else-if="filteredOptions.length" class="retrieve-index-select__list" data-ui="index-set-list">
        <li v-for="item in filteredOptions" :key="item.value">
          <button
            type="button"
            :class="['retrieve-index-select__option', { 'is-active': item.value === modelValue }]"
            @click="select(item.value)"
          >
            <i v-if="item.value === modelValue" class="bklog-icon bklog-check-line" />
            <span :title="item.label">{{ item.label }}</span>
          </button>
        </li>
      </ul>
      <t-empty v-else description="暂无匹配索引集" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue';

const props = defineProps<{
  modelValue: string;
  options: Array<{ label: string; value: string }>;
  error?: string;
}>();

const emit = defineEmits<{
  change: [value: string];
}>();

const open = ref(false);
const query = ref('');
const rootRef = ref<HTMLElement | null>(null);
const inputRef = ref<HTMLInputElement | null>(null);

const activeLabel = computed(() => (
  props.options.find(item => item.value === props.modelValue)?.label || props.modelValue || '请选择索引集'
));
const filteredOptions = computed(() => {
  const keyword = query.value.toLowerCase();
  if (!keyword) {
    return props.options;
  }
  return props.options.filter(item => (
    item.label.toLowerCase().includes(keyword)
    || item.value.toLowerCase().includes(keyword)
  ));
});

const onDocumentClick = (event: MouseEvent) => {
  if (!rootRef.value?.contains(event.target as Node)) {
    close();
  }
};

const toggle = () => {
  open.value = !open.value;
  if (open.value) {
    document.addEventListener('mousedown', onDocumentClick);
    void nextTick(() => inputRef.value?.focus());
  } else {
    document.removeEventListener('mousedown', onDocumentClick);
  }
};

const close = () => {
  open.value = false;
  document.removeEventListener('mousedown', onDocumentClick);
};

const select = (value: string) => {
  emit('change', value);
  query.value = '';
  close();
};

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocumentClick);
});
</script>
