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
import { Component, InjectReactive, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import deepmerge from 'deepmerge';
import { CancelToken } from 'monitor-api/index';
import { Debounce } from 'monitor-common/utils/utils';

// import ListLegend from '../../components/chart-legend/common-legend';

import { VariablesService } from '../../utils/variable';
import CommonSimpleChart from '../common-simple-chart';
import BaseEchart from '../monitor-base-echart';

import type { IExtendMetricData, ILegendItem, LegendActionType, PanelModel } from '../../typings';
import type { MonitorEchartOptions } from '../../typings';
import type { CallOptions, IDataItem } from '../apm-service-caller-callee/type';

import './caller-bar-chart.scss';

interface IPieEchartProps {
  panel: PanelModel;
}
@Component
class CallerBarChart extends CommonSimpleChart {
  height = 600;
  width = 960;
  minBase = 0;
  needResetChart = true;
  inited = false;
  metrics: IExtendMetricData[];
  emptyText = window.i18n.tc('查无数据');
  empty = true;
  cancelTokens = [];
  options = {};
  baseOptions: MonitorEchartOptions = {
    series: [],
    grid: {
      top: 30,
      right: 32,
    },
    color: ['#689DF3'],
    xAxis: {
      type: 'category',
      axisPointer: {
        type: 'shadow',
      },
      data: [],
    },
    yAxis: {
      type: 'value',
      splitLine: {
        show: true,
        lineStyle: {
          color: '#F0F1F5',
          type: 'solid',
        },
      },
    },
    tooltip: {
      className: 'caller-pie-chart-tooltips',
      show: true,
      trigger: 'axis',
      axisPointer: {
        type: 'line',
        label: {
          backgroundColor: '#6a7985',
        },
      },
      formatter: p => {
        const data = p[0].data;
        return `<div class="monitor-chart-tooltips">
          <p class="tooltips-span">
          ${data.name}
          </p>
          <p class="tooltips-span">
          ${data.metricCalTypeName}：${data.value}
          </p>
          <p class="tooltips-span">
          ${this.$t('占比')}：${data.proportion}%
          </p>
          </div>`;
      },
    },
  };
  // legendData = [];
  @InjectReactive('dimensionParam') readonly dimensionParam: CallOptions;
  @InjectReactive('dimensionChartOpt') readonly dimensionChartOpt: IDataItem;

  @Watch('dimensionParam', { deep: true })
  onCallOptionsChange() {
    this.getPanelData();
  }
  /**
   * @description: 在图表数据没有单位或者单位不一致时则不做单位转换 y轴label的转换用此方法做计数简化
   * @param {number} num
   * @return {*}
   */
  handleYxisLabelFormatter(num: number): string {
    const si = [
      { value: 1, symbol: '' },
      { value: 1e3, symbol: 'K' },
      { value: 1e6, symbol: 'M' },
      { value: 1e9, symbol: 'G' },
      { value: 1e12, symbol: 'T' },
      { value: 1e15, symbol: 'P' },
      { value: 1e18, symbol: 'E' },
    ];
    const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;
    let i: number;
    for (i = si.length - 1; i > 0; i--) {
      if (num >= si[i].value) {
        break;
      }
    }
    return (num / si[i].value).toFixed(3).replace(rx, '$1') + si[i].symbol;
  }

  get metricCalTypeName() {
    return this.dimensionChartOpt?.metric_cal_type_name;
  }
  /**
   * @description: 获取图表数据
   */
  @Debounce(100)
  async getPanelData(start_time?: string, end_time?: string) {
    if (!(await this.beforeGetPanelData())) {
      return;
    }
    this.cancelTokens.forEach(cb => cb?.());
    this.cancelTokens = [];
    if (this.inited) this.handleLoadingChange(true);
    try {
      this.unregisterOberver();
      const variablesService = new VariablesService({
        ...this.viewOptions,
        ...this.dimensionParam,
      });
      const { metric_cal_type, time_shift } = this.dimensionChartOpt;
      const promiseList = this.panel.targets.map(item => {
        const params = variablesService.transformVariables(item.data, {
          ...this.viewOptions.filters,
          ...(this.viewOptions.filters?.current_target || {}),
          ...this.viewOptions,
          ...this.viewOptions.variables,
          ...this.dimensionParam,
        });
        (this as any).$api[item.apiModule]
          ?.[item.apiFunc](
            {
              ...params,
              metric_cal_type,
              time_shift,
              where: this.dimensionParam.whereParams,
              ...this.dimensionParam.timeParams,
            },
            {
              cancelToken: new CancelToken((cb: () => void) => this.cancelTokens.push(cb)),
              needMessage: false,
            }
          )
          .then(res => {
            const seriesData = res.data || [];
            this.updateChartData(seriesData);
            this.clearErrorMsg();
            return true;
          })
          .catch(error => {
            this.handleErrorMsgChange(error.msg || error.message);
          });
      });
      const res = await Promise.all(promiseList);
      if (res) {
        this.inited = true;
        this.empty = false;
      } else {
        this.emptyText = window.i18n.tc('查无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      console.error(e);
    }
    this.handleLoadingChange(false);
  }
  /**
   * @description: 更新图表的数据
   */
  updateChartData(srcData) {
    // const legendList = [];
    const dataList = [];
    const xAxisLabel = [];
    const metricCalTypeName = this.dimensionChartOpt?.metric_cal_type_name;
    // biome-ignore lint/complexity/noForEach: <explanation>
    srcData.forEach(item => {
      const { proportion, name, value } = item;
      dataList.push({ proportion, name, value: value, metricCalTypeName });
      xAxisLabel.push(item.name);
    });
    // this.legendData = legendList;
    const seriesData = [
      {
        barMaxWidth: 20,
        data: dataList,
        type: 'bar',
      },
    ];
    this.options = Object.freeze(
      deepmerge(this.baseOptions, {
        xAxis: {
          data: xAxisLabel,
        },
        yAxis: {
          ...this.baseOptions.yAxis,
          axisLabel: {
            formatter: (v: number) => this.handleYxisLabelFormatter(v - this.minBase),
          },
        },
        series: seriesData,
      })
    ) as MonitorEchartOptions;
  }
  /**
   * @description: 选中图例触发事件
   * @param {LegendActionType} actionType 事件类型
   * @param {ILegendItem} item 当前选中的图例
   */
  handleSelectLegend({ actionType, item }: { actionType: LegendActionType; item: ILegendItem }) {
    this.handleSelectPieLegend({ option: this.options, actionType, item });
  }
  render() {
    return (
      <div class='caller-bar-chart'>
        {!this.empty ? (
          <div class={'time-series-content'}>
            <div
              ref='chart'
              class='chart-instance'
            >
              {this.inited && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.height}
                  options={this.options}
                />
              )}
            </div>
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}

export default ofType<IPieEchartProps>().convert(CallerBarChart);
