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
import { Component, Prop } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';
import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { CancelToken } from 'monitor-api/index';
import { random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { getValueFormat } from '../../../monitor-echarts/valueFormats';
import ChartHeader from '../../components/chart-title/chart-title';
import { COLOR_LIST_BAR, MONITOR_BAR_OPTIONS } from '../../constants';
import { ILegendItem, ITimeSeriesItem, PanelModel } from '../../typings';
import { VariablesService } from '../../utils/variable';
import BaseEchart from '../monitor-base-echart';
import { LineChart } from '../time-series/time-series';

import './apdex-chart.scss';

interface IApdexChartTipItem {
  name: string;
  color: string;
  tips: string;
}
export enum APDEX_CHART_TYPE {
  EVENT = 'event',
  APDEX = 'apdex'
}
interface IApdexChartProps {
  panel: PanelModel;
  splitNumber?: number;
}
interface IApdexChartEvent {
  onDataZoom: void;
  onDblClick: void;
}
@Component
export class ApdexChart extends LineChart {
  @Prop({ type: Number, default: 0 }) splitNumber: number;

  empty = true; // 是否为空
  emptyText = ''; // 空文案
  isFetchingData = false; // 是否正在获取数据
  async getPanelData(start_time?: string, end_time?: string) {
    this.cancelTokens.forEach(cb => cb?.());
    this.cancelTokens = [];
    if (!this.isInViewPort()) {
      if (this.intersectionObserver) {
        this.unregisterOberver();
      }
      this.registerObserver(start_time, end_time);
      return;
    }
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    try {
      this.unregisterOberver();
      // const series = apdexData.series || [];
      const series = [];
      // const metrics = apdexData.series || [];
      const metrics = [];
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime
      };
      const promiseList = [];
      const timeShiftList = ['', ...this.timeOffset];
      const variablesService = new VariablesService(this.viewOptions);
      timeShiftList.forEach(time_shift => {
        const list = this.panel.targets.map(item =>
          (this as any).$api[item.apiModule]
            [item.apiFunc](
              {
                ...variablesService.transformVariables(item.data, {
                  ...this.viewOptions.filters,
                  ...(this.viewOptions.filters?.current_target || {}),
                  ...this.viewOptions,
                  ...this.viewOptions.variables,
                  time_shift
                }),
                ...params
              },
              {
                cancelToken: new CancelToken((cb: Function) => this.cancelTokens.push(cb)),
                needMessage: false
              }
            )
            .then(res => {
              metrics.push(...res.metrics);
              series.push(
                ...res.series.map(set => ({
                  ...set,
                  name: `${this.timeOffset.length ? `${this.handleTransformTimeShift(time_shift || 'current')}-` : ''}${
                    this.handleSeriesName(item, set) || set.target
                  }`
                }))
              );
              this.clearErrorMsg();
              return true;
            })
            .catch(error => {
              this.handleErrorMsgChange(error.msg || error.message);
            })
        );
        promiseList.push(...list);
      });
      await Promise.all(promiseList).catch(() => false);
      if (series.length) {
        const seriesList = this.handleTransformSeries(
          series.map(item => ({
            name: item.target,
            cursor: 'auto',
            data: item.datapoints.reduce((pre: any, cur: any) => (pre.push(cur.reverse()), pre), []),
            stack: item.stack || random(10),
            unit: item.unit,
            z: 1
          })) as any
        );
        const formatterFunc = this.handleSetFormatterFunc(seriesList[0].data, !!this.splitNumber);
        const echartOptions: any = MONITOR_BAR_OPTIONS;
        this.options = Object.freeze(
          deepmerge(echartOptions, {
            animation: true,
            animationThreshold: 1,
            grid: {
              top: 30,
              right: 32
            },
            yAxis: {
              show: false
            },
            xAxis: {
              axisLabel: {
                formatter: formatterFunc || '{value}'
              },
              // splitNumber: this.splitNumber || 0
              splitNumber: this.splitNumber ? seriesList[0].data?.length || 2 : 0
            },
            series: seriesList
          })
        );
        this.metrics = metrics || [];
        this.inited = true;
        this.empty = false;
        if (!this.hasSetEvent) {
          setTimeout(this.handleSetLegendEvent, 300);
          this.hasSetEvent = true;
        }
      } else {
        this.emptyText = window.i18n.tc('查无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      console.error(e);
    }
    this.cancelTokens = [];
    this.handleLoadingChange(false);
  }

  handleTransformSeries(series: ITimeSeriesItem[]): any {
    const legendData: ILegendItem[] = [];
    this.renderThresholds = false;
    const [{ dataType }] = this.panel.targets;
    const tranformSeries = series.map(item => {
      // 动态单位转换
      const unitFormatter = item.unit !== 'none' ? getValueFormat(item.unit || '') : (v: any) => ({ text: v });
      const data = item.data.map((seriesItem: any) => {
        const valY = seriesItem[1];
        if (seriesItem?.length && (typeof valY === 'number' || Array.isArray(valY))) {
          return {
            value: [seriesItem[0], 1],
            rawY: valY,
            ...this.handleSetItemStyle(valY, dataType as APDEX_CHART_TYPE)
          } as any;
        }
        return seriesItem;
      });
      return {
        ...item,
        type: 'bar',
        data,
        z: 4,
        smooth: 0,
        unitFormatter
      };
    });
    this.legendData = legendData;
    return tranformSeries;
  }
  handleSetItemStyle(v: number | number[], dataType: APDEX_CHART_TYPE) {
    const itemStyle = {
      enabled: true,
      shadowBlur: 0,
      opacity: 1,
      color: COLOR_LIST_BAR[0]
    };
    let sets: IApdexChartTipItem;
    switch (dataType) {
      case APDEX_CHART_TYPE.APDEX:
        sets = this.handleSetApdexColor(v as number);
        itemStyle.color = sets.color;
        break;
      case APDEX_CHART_TYPE.EVENT:
        sets = this.handleSetEventColor(v as number[]);
        itemStyle.color = sets.color;
        break;
    }
    const tooltips = `<li class="tooltips-content-item">
    <span class="item-series"
     style="background-color:${sets.color};">
    </span>
    <span class="item-name" style="color: #fff;font-weight: bold;">${sets.name}:</span>
    <span class="item-value" style="color: #fff;font-weight: bold;">
    ${sets.tips}</span>
    </li>`;
    return {
      itemStyle,
      tooltips
    };
  }
  handleSetApdexColor(val: number) {
    const v = +val.toFixed(2);
    if (v > 0.75)
      return {
        name: '满意',
        tips: `Apdex(${v}) > 0.75`,
        color: '#2DCB56'
      };
    if (v <= 0.25)
      return {
        name: '烦躁',
        tips: `Apdex(${v}) <= 0.25`,
        color: '#FF5656'
      };
    return {
      name: '可容忍',
      tips: `0.25 < Apdex(${v}) <= 0.75`,
      color: '#FFB848'
    };
  }
  handleSetEventColor(v: number[]) {
    const tips = v[1].toString();
    if (v[0] === 1)
      return {
        name: '致命',
        tips,
        color: '#FF5656'
      };
    if (v[0] === 2)
      return {
        name: '预警',
        tips,
        color: '#FFB848'
      };
    return {
      name: '无告警',
      tips,
      color: '#2DCB56'
    };
  }
  render() {
    const { legend } = this.panel?.options || {};
    return (
      <div class='apdex-chart'>
        {this.showChartHeader && (
          <ChartHeader
            class='draggable-handle'
            title={this.panel.title}
            showMore={false}
            showAddMetric={false}
            draging={this.panel.draging}
            metrics={this.metrics}
            subtitle={this.panel.subTitle || ''}
            descrition={this.panel.descrition}
            isInstant={this.panel.instant}
            onUpdateDragging={() => this.panel.updateDraging(false)}
          />
        )}
        {!this.empty ? (
          <div class={`apdex-chart-content ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
            <div
              class='chart-instance'
              ref='chart'
            >
              {this.inited && (
                <BaseEchart
                  ref='baseChart'
                  height={this.height}
                  width={this.width}
                  options={this.options}
                  groupId={this.panel.dashboardId}
                  onDataZoom={this.dataZoom}
                  onDblClick={this.handleDblClick}
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

export default ofType<IApdexChartProps, IApdexChartEvent>().convert(ApdexChart);
