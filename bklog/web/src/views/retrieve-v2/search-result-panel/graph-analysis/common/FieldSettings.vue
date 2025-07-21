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
  xAxis: {
    type: Array,
  },
  yAxis: {
    type: Array,
  },

  activeGraphCategory: {
    type: String,
  },
  result_schema: {
    type: Array,
  },
});
const emit = defineEmits(['update']);
const selectedXAxis = ref(props.xAxis);
const selectedYAxis = ref(props.yAxis);
const timeAxis = ref('');
const hiddenField = ref([]);
const list = computed(() => props.result_schema.map(item => item.field_alias));
const filterFields = (typeCheck, excludeList) => {
  return props.result_schema.filter(item => typeCheck(item)).filter(item => !excludeList.includes(item.field_alias));
};

const xAxisFilterList = computed(() => {
  const fields = [...selectedYAxis.value];
  if (props.activeGraphCategory !== 'pie') {
    fields.push(timeAxis.value);
  }
  return filterFields(item => true, fields);
});

const yAxisFilterList = computed(() => {
  return filterFields(item => item.field_type !== 'string', [...selectedXAxis.value, timeAxis.value]);
});

const timeFilterList = computed(() => {
  return filterFields(item => item.field_type == 'long', [...selectedYAxis.value, ...selectedXAxis.value]);
});
// 监听 props.xAxis 的变化并更新 selectedXAxis
watch(
  () => props.xAxis,
  newValue => {
    selectedXAxis.value = newValue;
  }
);

// 同样操作 yAxis，如果需要的话
watch(
  () => props.yAxis,
  newValue => {
    selectedYAxis.value = newValue;
  }
);
watch(
  () => props.activeGraphCategory,
  newValue => {
    if (newValue !== 'pie') {
      selectedXAxis.value = selectedXAxis.value.filter(item => item !== timeAxis.value);
    }
  }
);
function change(axis, newValue) {
  emit('update', axis, newValue);
}
</script>
<template>
  <div class="bklog-chart-field">
    <div v-show="activeGraphCategory !== 'table'">
      <div class="title">{{ this.$t('指标') }}</div>
      <bk-select
        v-model="selectedYAxis"
        searchable
        @change="change('yFields', $event)"
        :clearable="false"
        multiple
      >
        <bk-option
          v-for="option in yAxisFilterList"
          :key="option.field_alias + option.field_index"
          :id="option.field_alias"
          :name="option.field_alias"
        >
        </bk-option>
      </bk-select>
    </div>
    <div v-show="activeGraphCategory !== 'table'">
      <div class="title">{{ this.$t('维度') }}</div>
      <bk-select
        v-model="selectedXAxis"
        searchable
        @change="change('xFields', $event)"
        :clearable="false"
        multiple
      >
        <bk-option
          v-for="option in xAxisFilterList"
          :key="option.field_alias + option.field_index"
          :id="option.field_alias"
          :name="option.field_alias"
        >
        </bk-option>
      </bk-select>
    </div>
    <div v-show="activeGraphCategory == 'bar' || activeGraphCategory == 'line'">
      <div class="title">{{ this.$t('时间维度') }}</div>
      <bk-select
        v-model="timeAxis"
        @change="change('dimensions', $event)"
        searchable
      >
        <bk-option
          v-for="option in timeFilterList"
          :key="option.field_alias + option.field_index"
          :id="option.field_alias"
          :name="option.field_alias"
        >
        </bk-option>
      </bk-select>
    </div>
    <div v-show="activeGraphCategory == 'table'">
      <div class="title">{{ this.$t('隐藏字段') }}</div>
      <bk-select
        v-model="hiddenField"
        :clearable="false"
        multiple
        @change="change('hiddenFields', $event)"
        searchable
      >
        <bk-option
          v-for="(option, index) in list"
          :key="index"
          :id="option"
          :name="option"
        >
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
