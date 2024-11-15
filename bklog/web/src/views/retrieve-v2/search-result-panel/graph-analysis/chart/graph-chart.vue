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
import { ref, onMounted, defineProps, watch, onUnmounted, defineExpose } from "vue";
import useLocale from "@/hooks/use-locale";
const { $t } = useLocale();
import * as echarts from "echarts";

const props = defineProps({
  activeGraphCategory: {
    type: String,
    default: "horizional",
  },
});
const chartRef = ref(null);
const tableData = ref([]);

let myChart = null;
watch(() => props.activeGraphCategory, updateChart);
onMounted(() => {
  myChart = echarts.init(chartRef.value);
  updateChart();
});
onUnmounted(() => {
  if (myChart) {
    myChart.dispose();
  }
});
function updateChart() {
  console.log(props.activeGraphCategory);

  if (props.activeGraphCategory === "table") return;

  const option = getChartOption(props.activeGraphCategory);
  myChart.setOption(option);
}
function setOption(data) {
//   tableData.value = data.data.list;
}
function getChartOption(type) {
  switch (type) {
    case "line":
      return {
        xAxis: { type: "category", data: tableData.value.map((item) => item.name) },
        yAxis: { type: "value" },
        series: [{ data: tableData.value.map((item) => item.value), type: "line" }],
      };
    case "bar":
      return {
        xAxis: { type: "category", data: tableData.value.map((item) => item.name) },
        yAxis: { type: "value" },
        series: [{ data: tableData.value.map((item) => item.value), type: "bar" }],
      };
    case "line-bar":
      return {
        xAxis: { type: "category", data: tableData.value.map((item) => item.name) },
        yAxis: { type: "value" },
        series: [
          { data: tableData.value.map((item) => item.value), type: "bar" },
          { data: tableData.value.map((item) => item.value), type: "line" },
        ],
      };
    case "pie":
      return {
        series: [
          {
            type: "pie",
            data: tableData.value.map((item) => ({ name: item.name, value: item.value })),
          },
        ],
      };
    default:
      return {};
  }
}
defineExpose({
  setOption,
});
</script>
<template>
  <div class="graph-context graph-chart">
    <div ref="chartRef" style="width: 600px; height: 400px"></div>
  </div>
</template>

<style lang="scss" scoped>
.graph-context {
  width: 100%;
  height: calc(100% - 22px);
}
</style>
