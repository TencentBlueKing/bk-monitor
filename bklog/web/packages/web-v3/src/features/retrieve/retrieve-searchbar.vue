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
      <button type="button" class="retrieve-searchbar__mode" @click="toggleMode">
        {{ mode === 'ui' ? 'UI 查询' : 'SQL 查询' }}
      </button>
      <t-input
        class="retrieve-searchbar__input"
        borderless
        :model-value="keyword"
        placeholder="请输入检索语句，回车或点击检索；空语句将返回当前时间范围内全部日志"
        clearable
        @update:model-value="value => emit('update:keyword', value)"
        @enter="emit('search')"
      />
    </div>
    <t-button
      class="retrieve-searchbar__submit"
      theme="primary"
      :loading="loading"
      @click="emit('search')"
    >
      检索
    </t-button>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';

defineProps<{
  keyword: string;
  loading: boolean;
}>();

defineEmits<{
  'update:keyword': [value: string];
  search: [];
}>();

const mode = ref<'ui' | 'sql'>('ui');

const toggleMode = () => {
  mode.value = mode.value === 'ui' ? 'sql' : 'ui';
};
</script>
