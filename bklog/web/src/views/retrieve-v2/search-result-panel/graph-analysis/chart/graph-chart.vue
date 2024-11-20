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
const segment = ref([]);
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
  const option = getChartOption(props.activeGraphCategory);
  console.log("option", option);
  myChart.setOption(option);
}
function setOption(data, xAxis, yAxis, segmented = []) {
  segment.value = segmented;
  tableData.value = data.data.list.map((item) => {
    const segmentedValues = segmented.length > 0 ? segmented.map((seg) => item[seg]) : [];
    return {
      name: item[xAxis],
      value: [item[yAxis], ...segmentedValues],
    };
  });
  updateChart();
}
function getChartOption(type) {
  if (type === "pie") {
    const pieData = tableData.value.map((item,index) => {
      console.log();
      const nmae = segment.value.forEach((seg) => {

      });
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
  const series = [];

  const valueLength = tableData.value.length > 0 ? tableData.value[0].value.length : 0;

  for (let i = 0; i < valueLength; i++) {
    const seriesData = tableData.value.map((item) => item.value[i]);

    switch (type) {
      case "line":
        series.push({ data: seriesData, type: "line", name: `Series ${i + 1}` });
        break;
      case "bar":
        series.push({ data: seriesData, type: "bar", name: `Series ${i + 1}` });
        break;
      // case "line_bar":
      //   if (i < 1) {
      //     series.push({ data: seriesData, type: "bar", name: `Series ${i + 1}` });
      //   } else {
      //     series.push({ data: seriesData, type: "line", name: `Series ${i + 1}` });
      //   }
      //   break;
      // case "pie":
      //   if (i > 1) {
      //     series.push({
      //       type: "pie",
      //       data: tableData.value.map(item => ({ name: item.name, value: item.value[i] })),
      //       name: `Series ${i + 1}`
      //     });
      //   }
      //   break;
      default:
        break;
    }
  }

  return {
    xAxis: { type: "category", data: tableData.value.map((item) => item.name) },
    yAxis: { type: "value" },
    series: series,
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
