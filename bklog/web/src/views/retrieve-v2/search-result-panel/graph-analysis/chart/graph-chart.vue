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
import { ref, onMounted, defineProps, watch, onUnmounted, defineExpose  } from "vue";
import useLocale from "@/hooks/use-locale";
import BASE_CHART_OPTIONS from "@/hooks/trend-chart-options.ts";
// import { BASE_CHART_OPTIONS } from "./chart";
import { merge } from "lodash";
const { $t } = useLocale();
import * as echarts from "echarts";
const emit = defineEmits(["sqlQuery"]);
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
const hint = ref(true);
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
  const option = Object.assign(
    // const option = merge(
    {},
    BASE_CHART_OPTIONS,
    getChartOption(props.activeGraphCategory)
  );
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
  let xAxisData = [];
  // const yAxisData = [];
  // xAxis.value.forEach((x) => {
  //   tableData.value.forEach((item) => {
  //     xAxisData.push(item[x]);
  //   });
  // });
  // xAxisData = [...new Set(xAxisData)];
  // yAxis.value.forEach((x) => {
  //   tableData.value.forEach((item) => {
  //     yAxisData.push(item[x]);
  //   });
  // });
  let summedGseIndexes = [];
  function sumGseIndexByHostId(data, xAxisNames, yAxis) {
    const result = {};
    console.log(xAxisNames, yAxis);

    data.forEach((item) => {
      let xAxisName = xAxisNames.reduce((accumulator, currentValue, index) => {
        return (
          accumulator + item[currentValue] + (index === xAxisNames.length - 1 ? "" : "_")
        );
      }, "");

      if (!result[xAxisName]) {
        result[xAxisName] = 0;
      }
      result[xAxisName] += item[yAxis];
    });
    console.log(result);
    summedGseIndexes.push(Object.values(result));
    xAxisData.push(...Object.keys(result));
    // return Object.values(result);
  }
  // const summedGseIndexes = sumGseIndexByHostId(tableData.value,xAxis.value[0],yAxis.value[0]);

  // xAxis.value.forEach((x,index) => {
  yAxis.value.forEach((y, index2) => {
    sumGseIndexByHostId(tableData.value, xAxis.value, yAxis.value[index2]);
  });
  // })
  console.log(summedGseIndexes);
  const series = summedGseIndexes.map((item) => {
    return {
      type: type,
      data: item,
    };
  });
  return {
    xAxis: {
      type: "category",
      data: xAxisData,
      axisLine: {
        show: false,
        lineStyle: {
          color: "#666",
          width: 1,
          type: "solid",
        },
        onZero: true,
        onZeroAxisIndex: null,
        symbol: ["none", "none"],
        symbolSize: [10, 15],
      },
      axisTick: {
        show: false,
        inside: false,
        length: 5,
        lineStyle: {
          width: 1,
        },
      },
    },
    yAxis: {
      type: "value",
      axisLine: {
        show: false,
        lineStyle: {
          color: "#666",
          width: 1,
          type: "dashed",
        },
        onZero: true,
        onZeroAxisIndex: null,
        symbol: ["none", "none"],
        symbolSize: [10, 15],
      },
      axisTick: {
        show: false,
        inside: false,
        length: 5,
        lineStyle: {
          width: 1,
        },
      },
    },
    series: series,
    tooltip: {
      formatter: function (params) {
        return `<div>
           <strong>${params?.name || "No Data"}</strong>
           <div style="display: flex; align-items: center;">
             <span style="display: inline-block; background-color:${
               params.color
             };margin-right: 4px;width: 6px;height: 6px; border-radius: 50%;"></span> 
             ${params?.data || "No Value"}
           </div>
         </div>`;
      },
    },
  };
}
function search() {
  emit("sqlQuery");
}
defineExpose({
  setOption,
});
</script>
<template>
  <div class="graph-context graph-chart">
    <!-- <bk-exception
      v-if="!tableData.length"
      class="exception-wrap-item exception-part"
      type="empty"
      scene="part"
    >
    </bk-exception> -->
    <!-- <bk-exception class="exception-wrap-item" v-if="isQueryChange && hint" type="500">
      <span class="title">图表查询配置已变更</span>
      <div class="text-wrap">
        <span class="text">请重新发起查询</span>
        <div>
          <bk-button
            :theme="'primary'"
            type="submit"
            @click="search"
            class="mr10"
            size="small"
          >
            查询
          </bk-button>
          <bk-button size="small" class="mr10" @click="hint=false">我知道了</bk-button>
        </div>
      </div>
    </bk-exception> -->
    <div ref="chartRef" style="width: 1000px; height: 100%"></div>
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
  .exception-wrap-item {
    padding: 10px;
    height: 100%;
    ::v-deep .bk-exception-img {
      height: 100%;
      .exception-image {
        height: 80%;
      }
    }
    .title {
      font-family: MicrosoftYaHei;
      font-size: 16px;
      color: #63656e;
    }
    .text-wrap {
      display: flex;
      align-items: center;
      justify-content: center;
      color: #3a84ff;
      font-size: 14px;
      margin-top: 14px;
      flex-direction: column;
      .text {
        font-family: MicrosoftYaHei;
        font-size: 12px;
        color: #979ba5;
        margin-bottom: 10px;
      }
    }
  }
}
</style>