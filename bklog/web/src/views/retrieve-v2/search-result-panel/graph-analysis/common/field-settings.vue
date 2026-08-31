<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
*
* 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
*
* License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
*
* ---------------------------------------------------
* Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
* documentation files (the "Software"), to deal in the Software without restriction, including without limitation
* the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
* to permit persons to whom the Software is furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in all copies or substantial portions of
* the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
* THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
* CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
* IN THE SOFTWARE.
-->
<script setup>
  import { ref, defineProps, watch, computed, defineEmits } from 'vue';

  const props = defineProps({
    options: {
      type: Object,
      default: () => ({
        xFields: [],
        yFields: [],
        dimensions: [],
        hiddenFields: [],
        category: '',
      }),
    },

    result_schema: {
      type: Array,
    },
  });

  const emit = defineEmits(['update']);
  const list = computed(() => props.result_schema.map(item => item.field_alias));

  const excludeList = computed(() => [...props.options.yFields, ...props.options.dimensions, ...props.options.xFields]);
  const xFieldOptions = computed(() =>
    props.result_schema
      .filter(item => !excludeList.value.includes(item.field_alias) || props.options.xFields.includes(item.field_alias))
      .map(item => {
        return {
          item: item.field_alias,
          disabled: false,
        };
      }),
  );

  const yFieldOptions = computed(() =>
    props.result_schema
      .filter(
        item =>
          /long|number|int|float|bigint|double/.test(item.field_type) &&
          (!excludeList.value.includes(item.field_alias) || props.options.yFields.includes(item.field_alias)),
      )
      .map(item => {
        return {
          item: item.field_alias,
          disabled: false,
        };
      }),
  );

  const dimensionsOptions = computed(() =>
    props.result_schema
      .filter(
        item => !excludeList.value.includes(item.field_alias) || props.options.dimensions.includes(item.field_alias),
      )
      .map(item => {
        return {
          item: item.field_alias,
          disabled: false,
        };
      }),
  );

  function change(axis, newValue) {
    emit('update', axis, newValue);
  }
</script>
<template>
  <div class="bklog-chart-field">
    <div v-show="options.category !== 'table'">
      <div class="title">{{ $t('指标') }}</div>
      <bk-select
        :value="options.yFields"
        searchable
        :clearable="false"
        multiple
        @change="change('yFields', $event)"
      >
        <bk-option
          v-for="option in yFieldOptions"
          :id="option.item"
          :key="option.item"
          :name="option.item"
          :disabled="option.disabled"
        >
        </bk-option>
      </bk-select>
    </div>
    <div v-show="options.category !== 'table' && options.category !== 'number'">
      <div class="title">{{ $t('维度') }}</div>
      <bk-select
        :value="options.xFields"
        searchable
        :clearable="false"
        multiple
        @change="change('xFields', $event)"
      >
        <bk-option
          v-for="option in xFieldOptions"
          :id="option.item"
          :key="option.item"
          :name="option.item"
          :disabled="option.disabled"
        >
        </bk-option>
      </bk-select>
    </div>
    <div v-show="options.category == 'bar' || options.category == 'line'">
      <div class="title">{{ $t('时间维度') }}</div>
      <bk-select
        :value="options.dimensions"
        searchable
        @change="change('dimensions', $event)"
      >
        <bk-option
          v-for="option in dimensionsOptions"
          :id="option.item"
          :key="option.item"
          :name="option.item"
          :disabled="option.disabled"
        >
        </bk-option>
      </bk-select>
    </div>
    <div v-show="options.category == 'table'">
      <div class="title">{{ $t('隐藏字段') }}</div>
      <bk-select
        :value="options.hiddenFields"
        :clearable="true"
        multiple
        searchable
        @change="change('hiddenFields', $event)"
      >
        <bk-option
          v-for="option in list"
          :id="option"
          :key="option"
          :name="option"
          :disabled="list.length - options.hiddenFields.length === 1 && !options.hiddenFields.includes(option)"
        >
          <div v-if="list.length - options.hiddenFields.length !== 1 || options.hiddenFields.includes(option)">
            {{ option }}
          </div>
          <div
            v-else
            v-bk-tooltips="{ content: $t('至少需要一个字段'), placements: ['top-start'] }"
          >
            {{ option }}
          </div>
        </bk-option>
      </bk-select>
    </div>
  </div>
</template>

<style lang="scss" scoped>
  .bklog-chart-field {
    .title {
      margin: 10px 0;
      font-size: 12px;
      color: #63656e;
    }
  }
</style>
