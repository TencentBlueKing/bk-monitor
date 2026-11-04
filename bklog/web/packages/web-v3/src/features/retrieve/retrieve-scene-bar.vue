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
  <section class="retrieve-scene-bar" data-ui="scene-bar">
    <div class="retrieve-scene-bar__scenes">
      <button
        v-for="item in scenes"
        :key="item.id"
        type="button"
        :class="['retrieve-scene-bar__scene', { 'is-active': state.scene === item.id }]"
        :data-ui="`scene-${item.id}`"
        @click="emit('change', item.id)"
      >
        {{ item.title }}
      </button>
    </div>
    <div v-if="fields.length" class="retrieve-scene-bar__filters" data-ui="scene-filters">
      <label v-for="field in fields" :key="field.key" class="retrieve-scene-bar__filter">
        <span>{{ field.title }}</span>
        <t-input
          size="small"
          :model-value="state.filters[field.key] || ''"
          :placeholder="field.title"
          @update:model-value="value => emit('filter', field.key, value)"
        />
      </label>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import { SCENE_FILTERS, SCENE_OPTIONS, type SceneId, type SceneSnapshot } from './scene-controller';

const props = defineProps<{
  state: SceneSnapshot;
}>();

const emit = defineEmits<{
  change: [scene: SceneId];
  filter: [key: string, value: string];
}>();

const scenes = SCENE_OPTIONS;
const fields = computed(() => SCENE_FILTERS[props.state.scene]);
</script>
