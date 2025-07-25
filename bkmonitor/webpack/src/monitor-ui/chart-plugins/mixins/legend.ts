/*
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
 */
import { Component, Prop, Vue } from 'vue-property-decorator';

import { deepClone } from 'monitor-common/utils/utils';

import type { ILegendItem, LegendActionType, MonitorEchartOptions } from '../typings';

@Component
export default class ResizeMixin extends Vue {
  legendData: ILegendItem[] = [];
  // 鼠标是否进入图表内
  @Prop({ default: false, type: Boolean }) showHeaderMoreTool: boolean;
  handleLegendChange() {
    if (!this.showHeaderMoreTool) {
      // const item = this.legendData.find(item => item.name === e.name);
      // item && (item.show = e.type === 'legendselected');
      const chartInstance = this.$refs.baseChart as any;
      chartInstance.instance.dispatchAction({
        type: 'restore',
      });
    }
  }
  // 根据选中图例重置图表
  handleResetPieChart(option: MonitorEchartOptions, needResetChart?: boolean, hideLabel?: boolean) {
    let totalValue = 0;
    const resArr = [];
    const chartInstance = this.$refs.baseChart as any;
    const targetOption = deepClone(option);
    const targetData = targetOption.series[0].data.map(val => val);

    this.legendData.forEach(legend => {
      targetData.forEach(target => {
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
        formatter: params => {
          if (params.dataIndex === 0) {
            const divide = Number((params.value / totalValue).toFixed(2));
            const ratio = Number.isNaN(divide) ? 0 : divide * 100;
            return `${ratio}%\n${params.name}`;
          }
          return '';
        },
      };
      targetOption.series[0].emphasis.label = {
        show: !hideLabel,
      };
    }

    chartInstance.instance.setOption(targetOption);
  }
  handleSelectLegend({ actionType, item }: { actionType: LegendActionType; item: ILegendItem }) {
    if (this.legendData.filter(item => !item.silent).length < 2) {
      return;
    }
    const chartInstance = this.$refs.baseChart as any;
    if (actionType === 'shift-click') {
      chartInstance.dispatchAction({
        type: !item.show ? 'legendSelect' : 'legendUnSelect',
        name: item.name,
      });
      item.show = !item.show;
      this.$emit('selectLegend', this.legendData);
    } else if (actionType === 'click') {
      const hasOtherShow = this.legendData.filter(item => !item.hidden).some(set => set.name !== item.name && set.show);
      for (const legend of this.legendData) {
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
      }
      this.$emit('selectLegend', this.legendData);
    }
  }
  // pie-chart 选中图例事件
  handleSelectPieLegend({
    actionType,
    item,
    option,
    needResetChart = false,
    hideLabel = false,
  }: {
    actionType: LegendActionType;
    hideLabel?: boolean;
    item: ILegendItem;
    needResetChart?: boolean;
    option: MonitorEchartOptions;
  }) {
    const chartInstance = this.$refs.baseChart as any;
    if (['highlight', 'downplay'].includes(actionType)) {
      chartInstance.dispatchAction({
        type: actionType,
        name: item.name,
      });
    }

    if (this.legendData.length < 2) {
      return;
    }

    if (actionType === 'shift-click') {
      item.show = !item.show;
      this.handleResetPieChart(option, needResetChart, hideLabel);
    } else if (actionType === 'click') {
      const hasOtherShow = this.legendData.some(set => set.name !== item.name && set.show);
      this.legendData.forEach(legend => {
        legend.show = legend.name === item.name || !hasOtherShow;
      });
      this.handleResetPieChart(option, needResetChart, hideLabel);
    }
  }
  handleSetLegendEvent() {
    const chartInstance = this.$refs.baseChart as any;
    chartInstance?.instance.on('legendselected', this.handleLegendChange);
    chartInstance?.instance.on('legendunselected', this.handleLegendChange);
  }
  handleUnSetLegendEvent() {
    const chartInstance = this.$refs.baseChart as any;
    chartInstance?.instance?.off?.('legendselected', this.handleLegendChange);
    chartInstance?.instance?.off?.('legendunselected', this.handleLegendChange);
  }
}
