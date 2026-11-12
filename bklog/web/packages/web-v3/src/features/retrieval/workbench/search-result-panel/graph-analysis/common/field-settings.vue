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
<script setup lang="ts">
import { computed, h, type PropType } from 'vue';
import { Select as TSelect, Tooltip as TTooltip } from 'tdesign-vue-next';
import useLocale from '@/shared/composables/use-locale';
const { t } = useLocale();
interface SchemaField {
  field_alias: string;
  field_type: string;
}
interface FieldOptions {
  xFields: string[];
  yFields: string[];
  dimensions: string[];
  hiddenFields: string[];
  category: string;
}

const props = defineProps({
  options: {
    type: Object as PropType<FieldOptions>,
    default: () => ({
      xFields: [],
      yFields: [],
      dimensions: [],
      hiddenFields: [],
      category: '',
    }),
  },

  resultSchema: {
    type: Array as PropType<SchemaField[]>,
    default: () => [],
  },
});

const emit = defineEmits(['update']);
const list = computed(() => props.resultSchema.map((item) => item.field_alias));

const excludeList = computed(() => [...props.options.yFields, ...props.options.dimensions, ...props.options.xFields]);
const xFieldOptions = computed(() =>
  props.resultSchema
    .filter((item) => !excludeList.value.includes(item.field_alias) || props.options.xFields.includes(item.field_alias))
    .map((item) => {
      return {
        value: item.field_alias,
        label: item.field_alias,
        disabled: false,
      };
    }),
);

const yFieldOptions = computed(() =>
  props.resultSchema
    .filter(
      (item) =>
        /long|number|int|float|bigint|double/.test(item.field_type) &&
        (!excludeList.value.includes(item.field_alias) || props.options.yFields.includes(item.field_alias)),
    )
    .map((item) => {
      return {
        value: item.field_alias,
        label: item.field_alias,
        disabled: false,
      };
    }),
);

const dimensionsOptions = computed(() =>
  props.resultSchema
    .filter(
      (item) => !excludeList.value.includes(item.field_alias) || props.options.dimensions.includes(item.field_alias),
    )
    .map((item) => {
      return {
        value: item.field_alias,
        label: item.field_alias,
        disabled: false,
      };
    }),
);

const hiddenFieldOptions = computed(() =>
  list.value.map((field) => {
    const disabled =
      list.value.length - props.options.hiddenFields.length === 1 && !props.options.hiddenFields.includes(field);
    return {
      value: field,
      label: field,
      disabled,
      content: disabled
        ? () =>
            h(TTooltip, { content: t('至少需要一个字段'), placement: 'top-left' }, { default: () => h('span', field) })
        : field,
    };
  }),
);

function change(axis: string, newValue: unknown) {
  emit('update', axis, newValue);
}
</script>
<template>
  <div class="bklog-chart-field">
    <div v-show="options.category !== 'table'">
      <div class="title">{{ $t('指标') }}</div>
      <TSelect
        :value="options.yFields"
        filterable
        :clearable="false"
        multiple
        :options="yFieldOptions"
        @change="change('yFields', $event)"
      />
    </div>
    <div v-show="options.category !== 'table' && options.category !== 'number'">
      <div class="title">{{ $t('维度') }}</div>
      <TSelect
        :value="options.xFields"
        filterable
        :clearable="false"
        multiple
        :options="xFieldOptions"
        @change="change('xFields', $event)"
      />
    </div>
    <div v-show="options.category == 'bar' || options.category == 'line'">
      <div class="title">{{ $t('时间维度') }}</div>
      <TSelect
        :value="options.dimensions[0]"
        filterable
        :options="dimensionsOptions"
        @change="change('dimensions', $event)"
      />
    </div>
    <div v-show="options.category == 'table'">
      <div class="title">{{ $t('隐藏字段') }}</div>
      <TSelect
        :value="options.hiddenFields"
        :clearable="true"
        multiple
        filterable
        :options="hiddenFieldOptions"
        @change="change('hiddenFields', $event)"
      />
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
