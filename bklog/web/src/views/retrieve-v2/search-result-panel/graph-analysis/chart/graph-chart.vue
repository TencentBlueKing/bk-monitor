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
import BASE_CHART_OPTIONS from "@/hooks/trend-chart-options.ts";
// import { BASE_CHART_OPTIONS } from './charts';
import { merge } from "lodash";
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
const segment = ref([]);
const xAxis = ref([]);
const yAxis = ref([]);
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

  if (props.activeGraphCategory === "table" || props.activeGraphCategory === "line_bar")
    return;
  myChart.clear();
  console.log("tableData", tableData.value);

  if (!tableData.value.length) {
    return;
  }
  const option = merge({}, BASE_CHART_OPTIONS, getChartOption(props.activeGraphCategory));
  console.log("option", option);
  myChart.setOption(option, {
    notMerge: true,
    lazyUpdate: false,
    silent: true,
  });
}
function setOption(data, xAxisValue, yAxisValue, segmented = []) {
  // segment.value = segmented;
  tableData.value = data.data.list;
  xAxis.value = xAxisValue;
  yAxis.value = yAxisValue;

  updateChart();
}
function getChartOption(type) {
  if (type === "pie") {
    const pieData = tableData.value.map((item, index) => {
      const nmae = segment.value.forEach((seg) => {});
      const dimensionCombination = item.value.join("-");
      const totalValue = item.value.reduce((acc, val) => acc + val, 0);
      const combinedNameValue = `${item.name} (${dimensionCombination})`;
      return {
        name: combinedNameValue,
        value: totalValue,
      };
    });

    return {
      series: [
        {
          type: "pie",
          data: pieData,
        },
      ],
    };
  }
  const xAxisData = [];
  xAxis.value.forEach((x) => {
    tableData.value.forEach((item) => {
        xAxisData.push(item[x]);
    });
  });
  

  return {
    // xAxis: { type: "category", data: tableData.value.map((item) => item.name) },
    // yAxis: { type: "value" },
    // series: series,
  };
}
defineExpose({
  setOption,
});
</script>
<template>
  <div class="graph-context graph-chart">
    <bk-exception
      v-if="!tableData.length"
      class="exception-wrap-item exception-part"
      type="empty"
      scene="part"
    >
    </bk-exception>
    <div ref="chartRef" style="width: 1000px; height: 400px"></div>
    <div>
      <div></div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.graph-context {
  width: 100%;
  height: calc(100% - 22px);
  margin-left: 30px;
}
</style>
