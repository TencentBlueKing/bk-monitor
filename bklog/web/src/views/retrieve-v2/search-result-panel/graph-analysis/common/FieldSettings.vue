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
import { ref, defineProps, watch, computed, defineEmits } from "vue";

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
  select_fields_order: {
    type: Array,
  },
});
const emit = defineEmits(["update"]);
const selectedXAxis = ref(props.xAxis);
const selectedYAxis = ref(props.yAxis);
const segmentedField = ref([]);
const hiddenField = ref([]);
const list = computed(() => props.select_fields_order);
// 监听 props.xAxis 的变化并更新 selectedXAxis
watch(
  () => props.xAxis,
  (newValue) => {
    selectedXAxis.value = newValue;
  }
);

// 同样操作 yAxis，如果需要的话
watch(
  () => props.yAxis,
  (newValue) => {
    selectedYAxis.value = newValue;
  }
);
function change(axis, newValue) {
  // if (axis === "x") {
  
  emit("update", axis, newValue);
  // } else if (axis === "y") {
  // emit("update-yAxis", newValue);
  // }
}
</script>
<template>
  <div class="">
    <div v-show="activeGraphCategory == 'bar' || activeGraphCategory == 'line'">
      <div class="title">x轴字段</div>
      <bk-select
        v-model="selectedXAxis"
        searchable
        @change="change('x', $event)"
        :clearable="false"
        multiple
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
    <div  v-show="activeGraphCategory == 'bar' || activeGraphCategory == 'line'">
      <div class="title">y轴字段</div>
      <bk-select
        v-model="selectedYAxis"
        searchable
        @change="change('y', $event)"
        :clearable="false"
        multiple
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
    <div  v-show="activeGraphCategory == 'line_bar' || activeGraphCategory == 'pie'">
      <div class="title">显示字段</div>
      <bk-select v-model="selectedYAxis"  @change="change('y', $event)"  :clearable="false"  searchable>
        <bk-option
          v-for="(option, index) in list"
          :key="index"
          :id="option"
          :name="option"
        >
        </bk-option>
      </bk-select>
    </div>
    <div v-show="activeGraphCategory !== 'table'">
      <div class="title">时间维度</div>
      <bk-select v-model="segmentedField" :clearable="false"  @change="change('segmented', $event)" multiple searchable>
        <bk-option
          v-for="(option, index) in list"
          :key="index"
          :id="option"
          :name="option"
        >
        </bk-option>
      </bk-select>
    </div>
    <div v-show="activeGraphCategory == 'table'">
      <div class="title">隐藏字段</div>
      <bk-select
        v-model="hiddenField"
        :clearable="false"
        multiple
        @change="change('hidden', $event)"
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
.title {
  margin: 10px 0;
}
</style>
