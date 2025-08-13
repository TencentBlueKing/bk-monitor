import type { Ref } from 'vue';

/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
 */
import { deepClone } from 'monitor-common/utils/utils';

import type BaseEchart from '../base-echart';
import type { ILegendItem, LegendActionType } from '../typings';
import type { MonitorEchartOptions } from 'monitor-ui/monitor-echarts/types/monitor-echarts';

export function useChartLegend(
  baseChart: Ref<typeof BaseEchart | undefined>,
  showHeaderMoreTool: Ref<boolean>,
  legendData: Ref<ILegendItem[]>
) {
  function handleSelectLegend({ actionType, item }: { actionType: LegendActionType; item: ILegendItem }) {
    if (legendData.value.length < 2) {
      return;
    }
    const chartInstance = baseChart.value?.instance;
    if (actionType === 'shift-click') {
      chartInstance.dispatchAction({
        type: !item.show ? 'legendSelect' : 'legendUnSelect',
        name: item.name,
      });
      item.show = !item.show;
    } else if (actionType === 'click') {
      const hasOtherShow = legendData.value
        .filter(item => !item.hidden)
        .some(set => set.name !== item.name && set.show);
      legendData.value.forEach(legend => {
        chartInstance.dispatchAction({
          type:
            legend.name === item.name ||
            !hasOtherShow ||
            (legend.name.includes(`${item.name}-no-tips`) && legend.hidden)
              ? 'legendSelect'
              : 'legendUnSelect',
          name: legend.name,
        });
        legend.show = legend.name === item.name || !hasOtherShow;
      });
    }
  }
  function handleLegendChange() {
    if (!showHeaderMoreTool.value) {
      const chartInstance = baseChart.value?.instance;
      chartInstance.dispatchAction({
        type: 'restore',
      });
    }
  }
  // // 根据选中图例重置图表
  function handleResetPieChart(option: MonitorEchartOptions, needResetChart?: boolean) {
    let totalValue = 0;
    const resArr: any[] = [];
    const targetOption = deepClone(option);
    const targetData = targetOption.series[0].data.slice();

    legendData.value.forEach(legend => {
      targetData.forEach((target: { name: string; value: number }) => {
        if (target.name === legend.name && legend.show) {
          resArr.push(target);
          totalValue = totalValue + target.value;
        }
      });
    });
    if (!resArr.length) return;

    targetOption.series[0].data = resArr;

    if (needResetChart) {
      // 默认显示
      targetOption.series[0].label = {
        formatter: (params: { dataIndex: number; name: any; value: number }) => {
          if (params.dataIndex === 0) {
            const divide = Number((params.value / totalValue).toFixed(2));
            const ratio = isNaN(divide) ? 0 : divide * 100;
            return `${ratio}%\n${params.name}`;
          }
          return '';
        },
      };
      targetOption.series[0].emphasis.label = {
        show: true,
      };
    }
    const chartInstance = baseChart.value?.instance;
    chartInstance.setOption(targetOption);
  }
  // // pie-chart 选中图例事件
  function handleSelectPieLegend({
    actionType,
    item,
    option,
    needResetChart = false,
  }: {
    actionType: LegendActionType;
    item: ILegendItem;
    needResetChart?: boolean;
    option: MonitorEchartOptions;
  }) {
    if (['highlight', 'downplay'].includes(actionType)) {
      const chartInstance = baseChart.value?.instance;
      chartInstance.dispatchAction({
        type: actionType,
        name: item.name,
      });
    }

    if (legendData.value.length < 2) {
      return;
    }

    if (actionType === 'shift-click') {
      item.show = !item.show;
      handleResetPieChart(option, needResetChart);
    } else if (actionType === 'click') {
      const hasOtherShow = legendData.value.some(set => set.name !== item.name && set.show);
      legendData.value.forEach(legend => {
        legend.show = legend.name === item.name || !hasOtherShow;
      });
      handleResetPieChart(option, needResetChart);
    }
  }
  function handleSetLegendEvent() {
    const chartInstance = baseChart.value?.instance;
    chartInstance?.on('legendselected', handleLegendChange);
    chartInstance?.on('legendunselected', handleLegendChange);
  }
  function handleUnSetLegendEvent() {
    const chartInstance = baseChart.value?.instance;
    chartInstance?.off?.('legendselected', handleLegendChange);
    chartInstance?.off?.('legendunselected', handleLegendChange);
  }
  return {
    handleSelectLegend,
    handleLegendChange,
    handleResetPieChart,
    handleSelectPieLegend,
    handleSetLegendEvent,
    handleUnSetLegendEvent,
  };
}
