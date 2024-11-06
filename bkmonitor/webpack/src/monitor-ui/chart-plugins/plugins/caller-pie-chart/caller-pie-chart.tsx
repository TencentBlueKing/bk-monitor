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
import { Debounce, deepClone } from 'monitor-common/utils/utils';

import { MONITOR_PIE_OPTIONS } from '../../../chart-plugins/constants';
import PieLegend from '../../components/chart-legend/pie-legend';
import { VariablesService } from '../../utils/variable';
import CommonSimpleChart from '../common-simple-chart';
import BaseEchart from '../monitor-base-echart';

import type { IExtendMetricData, ILegendItem, LegendActionType, PanelModel } from '../../typings';
import type { MonitorEchartOptions } from '../../typings';
import type { CallOptions, IDataItem } from '../apm-service-caller-callee/type';

import './caller-pie-chart.scss';

interface IPieEchartProps {
  panel: PanelModel;
}
@Component
class CallerPieChart extends CommonSimpleChart {
  height = 300;
  width = 640;
  needResetChart = true;
  inited = false;
  metrics: IExtendMetricData[];
  emptyText = window.i18n.tc('查无数据');
  empty = true;
  cancelTokens = [];
  options = {};
  legendData = [];
  defaultColors = Object.freeze([
    '#699DF4',
    '#F7B936',
    '#1788C9',
    '#C8E74A',
    '#FF2D23',
    '#57AC3E',
    '#FF5422',
    '#8C00A9',
    '#A91947',
    '#FB962E',
  ]);
  @InjectReactive('dimensionParam') readonly dimensionParam: CallOptions;
  @InjectReactive('dimensionChartOpt') readonly dimensionChartOpt: IDataItem;

  @Watch('dimensionParam', { deep: true })
  onCallOptionsChange() {
    this.getPanelData();
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
    this.emptyText = window.i18n.tc('加载中...');
    try {
      this.unregisterOberver();
      const variablesService = new VariablesService({
        ...this.viewOptions,
        ...this.dimensionParam,
      });
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
              ...this.dimensionChartOpt,
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
    const legendList = [];
    const dataList = [];
    // biome-ignore lint/complexity/noForEach: <explanation>
    srcData.forEach((item, index) => {
      const defaultColor = this.defaultColors[index % this.defaultColors.length];
      const { name, value, color = defaultColor, borderColor = defaultColor } = item;
      legendList.push({ name, value, color, borderColor, show: true });
      dataList.push({ name, value, itemStyle: { color } });
    });
    this.legendData = legendList;
    const echartOptions = deepClone(MONITOR_PIE_OPTIONS);
    this.options = Object.freeze(
      deepmerge(echartOptions, {
        // tooltip: {
        //   className: 'caller-pie-chart-tooltips',
        // },
        series: [
          {
            label: {
              show: false,
              position: 'center',
            },
            labelLine: {
              normal: {
                show: false,
              },
            },
            radius: '50%',
            data: dataList,
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)',
              },
            },
            type: 'pie',
          },
        ],
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
      <div class='caller-pie-chart'>
        {!this.empty ? (
          <div class='pie-echart-content right-legend'>
            <div
              ref='chart'
              class='chart-instance'
            >
              <BaseEchart
                ref='baseChart'
                width={this.width}
                height={this.height}
                options={this.options}
              />
            </div>
            {
              <div class='chart-legend right-legend'>
                <PieLegend
                  legendData={this.legendData as any}
                  onSelectLegend={this.handleSelectLegend}
                />
              </div>
            }
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}

export default ofType<IPieEchartProps>().convert(CallerPieChart);
