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

import dayjs from 'dayjs';
// import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { CancelToken } from 'monitor-api/cancel';
import { Debounce } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { MONITOR_LINE_OPTIONS } from '../../../chart-plugins/constants';
import { getValueFormat } from '../../../monitor-echarts/valueFormats';
import ChartHeader from '../../components/chart-title/chart-title';
import { replaceRegexWhere } from '../../utils/method';
import { reviewInterval } from '../../utils/utils';
import { VariablesService } from '../../utils/variable';
import { intervalLowBound } from '../apm-service-caller-callee/utils';
import { CommonSimpleChart } from '../common-simple-chart';
import BaseEchart from '../monitor-base-echart';

import type { PanelModel, ZrClickEvent } from '../../../chart-plugins/typings';
import type { CallOptions } from '../apm-service-caller-callee/type';

import './apm-heatmap.scss';
interface IApmHeatmapProps {
  panel: PanelModel;
}
@Component
class ApmHeatmap extends CommonSimpleChart {
  metrics = [];
  initialized = false;
  options = {};
  empty = true;
  emptyText = window.i18n.t('暂无数据');
  cancelTokens = [];
  collectIntervalDisplay = '1m';

  @InjectReactive('callOptions') readonly callOptions: CallOptions;

  @Watch('callOptions')
  onCallOptionsChange() {
    this.getPanelData();
  }
  @Debounce(100)
  async getPanelData() {
    // console.info(this.callOptions, this.panel, '========');
    if (!(await this.beforeGetPanelData())) {
      return;
    }
    this.cancelTokens.forEach(cb => cb?.());
    this.cancelTokens = [];
    if (this.initialized) this.handleLoadingChange(true);
    this.emptyText = window.i18n.t('加载中...');
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const interval = reviewInterval(this.viewOptions.interval, startTime - endTime, this.panel.collect_interval);
    const variablesService = new VariablesService({
      ...this.viewOptions,
      ...this.callOptions,
      interval,
    });
    const series = [];
    const metrics = [];
    const promiseList = this.panel.targets.map(item => {
      if (!this.panel.options?.is_support_group_by && item.data.group_by_limit) {
        item.data.group_by_limit = undefined;
      }
      const down_sample_range = this.downSampleRangeComputed('auto', [startTime, endTime], 'unifyQuery');
      const [v] = down_sample_range.split('s');
      const interval = intervalLowBound(Math.ceil((+v * 4) / 60));
      this.collectIntervalDisplay = `${interval}m`;
      const params = variablesService.transformVariables(item.data, {
        ...this.viewOptions.filters,
        ...(this.viewOptions.filters?.current_target || {}),
        ...this.viewOptions,
        ...this.viewOptions.variables,
        ...this.callOptions,
        interval,
      });
      return this.$api[item.apiModule]
        [item.apiFunc](
          {
            ...params,
            start_time: startTime,
            end_time: endTime,
            query_configs: params?.query_configs.map(config => {
              return {
                ...config,
                interval,
                interval_unit: 'm',
                where: [...(config?.where || []), ...replaceRegexWhere(this.callOptions?.call_filter || [])],
                functions: config?.functions?.map(func => {
                  if (func.id === 'increase') {
                    return {
                      ...func,
                      params: func.params?.map(p => ({
                        ...p,
                        value: p.value ? `${interval}m` : p.value,
                      })),
                    };
                  }
                  return func;
                }),
              };
            }),
            unify_query_param: {
              ...params?.unify_query_param,
              query_configs: params?.query_configs.map(config => {
                return {
                  ...config,
                  interval,
                  interval_unit: 'm',
                  where: [...(config?.where || []), ...replaceRegexWhere(this.callOptions?.call_filter || [])],
                  functions: config?.functions?.map(func => {
                    if (func.id === 'increase') {
                      return {
                        ...func,
                        params: func.params?.map(p => ({
                          ...p,
                          value: p.value ? `${interval}m` : p.value,
                        })),
                      };
                    }
                    return func;
                  }),
                };
              }),
            },
          },
          {
            cancelToken: new CancelToken((cb: () => void) => this.cancelTokens.push(cb)),
            needMessage: false,
          }
        )
        .then(res => {
          res.metrics && metrics.push(...res.metrics);
          res.series && series.push(...res.series);
          this.clearErrorMsg();
          return true;
        })
        .catch(error => {
          this.handleErrorMsgChange(error.msg || error.message);
        });
    });
    await Promise.all(promiseList);
    this.metrics = metrics;
    if (series.length) {
      const panelUnit = this.panel.options?.unit || 's';
      const unitFormatter = getValueFormat(panelUnit);
      const xAxisCategory = new Set<number>();
      const yAxisCategory = new Set();
      const seriesData = [];
      let seriesIndex = 0;
      let min = Number.MAX_VALUE;
      let max = Number.MIN_VALUE;
      for (const item of series) {
        let dataIndex = 0;
        for (const datapoint of item.datapoints) {
          xAxisCategory.add(datapoint[1]);
          seriesData.push([dataIndex, seriesIndex, datapoint[0]]);
          dataIndex += 1;
          min = Math.min(min, datapoint[0]);
          max = Math.max(max, datapoint[0]);
        }
        seriesIndex += 1;
        yAxisCategory.add(item.dimensions.le);
      }
      const xAxisData: number[] = Array.from(xAxisCategory);
      const yAxisData = Array.from(yAxisCategory);
      const minX = xAxisData.at(0);
      const maxX = xAxisData.at(-1);
      const duration = Math.abs(dayjs.tz(+maxX).diff(dayjs.tz(+minX), 'second'));
      const secondFormatter = getValueFormat('s');
      this.options = {
        tooltip: {
          ...MONITOR_LINE_OPTIONS.tooltip,
          formatter: p => {
            if (p.data?.length < 2) {
              return '';
            }
            const xValue = xAxisData[p.data[0]];
            let xPreValue = xAxisData[p.data[0] - 1];
            if (p.data[0] === 0) {
              xPreValue = xValue - (xAxisData[p.data[0] + 1] - xValue);
            }
            const yValue = yAxisData[p.data[1]];
            const yPreValue = yAxisData[p.data[1] - 1];
            const demissionValue = p.data[2];
            const getYValue = (v: string | undefined) => {
              if (v === '+Inf') return v;
              if (v === undefined) return '-Inf';
              const { text, suffix } = unitFormatter(+v, 0);
              return `${text}${suffix}`;
            };
            return `<div class="monitor-chart-tooltips">
            <p class="tooltips-header">
                ${dayjs.tz(+xPreValue).format('YYYY-MM-DD HH:mm:ss')}
            </p>
            <p class="tooltips-header">
              ${dayjs.tz(+xValue).format('YYYY-MM-DD HH:mm:ss')}
            </p>
            <ul class="tooltips-content">
              <li class="tooltips-content-item">
                <span class="item-series"
                  style="background-color:${p.color};">
                </span>
                <span class="item-name">${getYValue(yPreValue as string)} ~ ${getYValue(yValue as string)}:</span>
                <span class="item-value">
                ${demissionValue || '--'}</span>
               </li>
            </ul>
            </div>`;
          },
          trigger: 'item',
          axisPointer: {
            type: 'none',
          },
          position: this.commonChartTooltipsPosition,
        },
        grid: {
          ...MONITOR_LINE_OPTIONS.grid,
          bottom: 40,
        },
        xAxis: {
          type: 'category',
          data: xAxisData,
          splitArea: {
            show: true,
          },
          axisTick: {
            show: false,
          },
          axisLine: {
            show: false,
          },
          axisLabel: {
            formatter: (v: any) => {
              if (duration < 1 * 60) {
                return dayjs.tz(+v).format('mm:ss');
              }
              if (duration < 60 * 60 * 24 * 1) {
                return dayjs.tz(+v).format('HH:mm');
              }
              if (duration < 60 * 60 * 24 * 6) {
                return dayjs.tz(+v).format('MM-DD HH:mm');
              }
              if (duration <= 60 * 60 * 24 * 30 * 12) {
                return dayjs.tz(+v).format('MM-DD');
              }
              return dayjs.tz(+v).format('YYYY-MM-DD');
            },
            fontSize: 12,
            color: '#979BA5',
            align: 'left',
          },
        },
        yAxis: {
          type: 'category',
          data: yAxisData,
          splitArea: {
            show: true,
          },
          axisLabel: {
            color: '#979BA5',
            formatter: (v: string) => {
              if (v === '+Inf') return v;
              const { text, suffix } = secondFormatter(+v);
              return `${text.replace(/\.0+$/, '')}${suffix}`;
            },
          },
          axisTick: {
            show: false,
          },
        },
        visualMap: {
          min,
          max,
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: -6,
          itemWidth: 16,
          itemHeight: 240,
          color: ['#3A84FF', '#C5DBFF', '#EDF3FF', '#F0F1F5'],
          show: true,
        },
        series: [
          {
            type: 'heatmap',
            data: seriesData,
            itemStyle: {
              borderWidth: 2,
              borderColor: '#fff',
            },
            emphasis: {
              disabled: false,
            },
          },
        ],
      };
      this.initialized = true;
      this.empty = false;
    } else {
      this.initialized = this.metrics.length > 0;
      this.emptyText = window.i18n.t('暂无数据');
      this.empty = true;
    }
    this.cancelTokens = [];
    this.handleLoadingChange(false);
    this.unregisterObserver();
  }
  handleClickItem(item) {
    this.$emit('zrClick', {
      xAxis: +item.name,
      interval: +this.collectIntervalDisplay.replace('m', '') * 60,
    });
  }
  render() {
    return (
      <div class='apm-heatmap'>
        <ChartHeader
          collectIntervalDisplay={this.collectIntervalDisplay}
          description={this.panel.description}
          dragging={this.panel.dragging}
          isInstant={this.panel.instant}
          metrics={this.metrics}
          needMoreMenu={false}
          showAddMetric={false}
          showMore={true}
          subtitle={this.panel.subTitle || ''}
          title={this.panel.title}
        />
        {!this.empty ? (
          <div class={'apm-heatmap-content'}>
            <div
              ref='chart'
              class='chart-instance'
            >
              {this.initialized && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.height}
                  options={this.options}
                  onClick={this.handleClickItem}
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

export default ofType<
  IApmHeatmapProps,
  {
    onZrClick?: (event: ZrClickEvent) => void;
  }
>().convert(ApmHeatmap);
