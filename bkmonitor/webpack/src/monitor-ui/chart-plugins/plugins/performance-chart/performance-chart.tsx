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
import { Component } from 'vue-property-decorator';
import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { EChartOption } from 'echarts';
import { CancelToken } from 'monitor-api/index';
import { deepClone, random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { getValueFormat } from '../../../monitor-echarts/valueFormats';
import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { COLOR_LIST, COLOR_LIST_BAR, MONITOR_LINE_OPTIONS } from '../../constants';
import { ILegendItem, ITimeSeriesItem, LegendActionType } from '../../typings';
import { reviewInterval } from '../../utils';
import { VariablesService } from '../../utils/variable';
import BaseEchart from '../monitor-base-echart';
import TimeSeries from '../time-series/time-series';

@Component
export default class PerformanceChart extends TimeSeries {
  // 标记区间
  markArea;
  // series
  seriesList = [];
  /**
   * @description: 获取图表数据
   * @param {*}
   * @return {*}
   */
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
    if (!this.enableSelectionRestoreAll) {
      this.showRestore = !!start_time;
    }
    try {
      this.unregisterOberver();
      const series = [];
      const metrics = [];
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      let params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime
      };
      if (this.bkBizId) {
        params = Object.assign({}, params, {
          bk_biz_id: this.bkBizId
        });
      }
      const promiseList = [];
      const timeShiftList = ['', ...this.timeOffset];
      const interval = reviewInterval(
        this.viewOptions.interval,
        params.end_time - params.start_time,
        this.panel.collect_interval
      );
      const variablesService = new VariablesService({
        ...this.viewOptions,
        interval
      });
      timeShiftList.forEach(time_shift => {
        const list = this.panel.targets.map(item => {
          const newPrarams = {
            ...variablesService.transformVariables(item.data, {
              ...this.viewOptions.filters,
              ...(this.viewOptions.filters?.current_target || {}),
              ...this.viewOptions,
              ...this.viewOptions.variables,
              time_shift,
              interval
            }),
            ...params,
            down_sample_range: this.downSampleRangeComputed(
              this.downSampleRange as string,
              [params.start_time, params.end_time],
              item.apiFunc
            )
          };
          return (this as any).$api[item.apiModule]
            [item.apiFunc](newPrarams, {
              cancelToken: new CancelToken((cb: Function) => this.cancelTokens.push(cb)),
              needMessage: false
            })
            .then(res => {
              this.$emit('seriesData', res);
              metrics.push(...res.metrics);
              series.push(
                ...res.series.map(set => ({
                  ...set,
                  metric_id: res.metrics?.[0]?.metric_id,
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
            });
        });
        promiseList.push(...list);
      });
      await Promise.all(promiseList).catch(() => false);
      if (series.length) {
        /* 派出图表数据包含的维度*/
        const emitDimensions = () => {
          const dimensionSet = new Set();
          series.forEach(s => {
            if (s.dimensions) {
              Object.keys(s.dimensions).forEach(dKey => {
                dimensionSet.add(dKey);
              });
            }
          });
          this.$emit('dimensionsOfSeries', [...dimensionSet]);
        };
        emitDimensions();
        let anomalyRange;
        if (metrics.length) {
          // 主机ai异常指标检查
          anomalyRange = await this.$api.aiops
            .hostIntelligenAnomalyRange({
              start_time: params.start_time,
              end_time: params.end_time,
              interval: this.viewOptions.interval,
              metric_ids: metrics?.map(item => item.metric_id),
              host: [
                {
                  ...this.viewOptions.current_target
                }
              ]
            })
            .catch(() => ({}));
        }
        this.series = Object.freeze(series) as any;
        let seriesList = this.handleTransformSeries(
          series.map((item, index) => {
            if (anomalyRange?.[item.metric_id]?.length) {
              item.markTimeRange = anomalyRange[item.metric_id];
            }
            return {
              name: item.name,
              cursor: 'auto',
              data: item.datapoints.reduce((pre: any, cur: any) => (pre.push(cur.reverse()), pre), []),
              stack: item.stack || random(10),
              unit: item.unit,
              markPoint: this.createMarkPointData(item, series),
              markLine: this.createMarkLine(index),
              markArea: this.createMarkArea(item, index),
              z: 2
            };
          }) as any
        );
        seriesList = seriesList.map((item: any) => {
          if (item.markArea && !this.markArea?.data) {
            this.markArea = { ...item.markArea };
          }
          return {
            ...item,
            minBase: this.minBase,
            data: item.data.map((set: any) => {
              if (set?.length) {
                return [set[0], set[1] !== null ? set[1] + this.minBase : null];
              }
              return {
                ...set,
                value: [set.value[0], set.value[1] !== null ? set.value[1] + this.minBase : null]
              };
            })
          };
        });
        // 1、echarts animation 配置会影响数量大时的图表性能 掉帧
        // 2、echarts animation配置为false时 对于有孤立点不连续的图表无法放大 并且 hover的点放大效果会潇洒 (貌似echarts bug)
        // 所以此处折中设置 在有孤立点情况下进行开启animation 连续的情况不开启
        this.seriesList = seriesList;
        const hasShowSymbol = seriesList.some(item => item.showSymbol);
        if (this.markArea) seriesList = this.handleSetOnlyOneMarkArea(seriesList) as any;
        if (hasShowSymbol) {
          seriesList.forEach(item => {
            item.data = item.data.map(set => {
              if (set?.symbolSize) {
                return {
                  ...set,
                  symbolSize: set.symbolSize > 6 ? 6 : 1,
                  itemStyle: {
                    borderWidth: set.symbolSize > 6 ? 6 : 1,
                    enabled: true,
                    shadowBlur: 0,
                    opacity: 1
                  }
                };
              }
              return set;
            });
          });
        }
        const formatterFunc = this.handleSetFormatterFunc(seriesList[0].data);
        const { canScale, minThreshold, maxThreshold } = this.handleSetThreholds();
        // eslint-disable-next-line max-len
        const chartBaseOptions = MONITOR_LINE_OPTIONS;
        // eslint-disable-next-line max-len
        const echartOptions = deepmerge(
          deepClone(chartBaseOptions),
          this.panel.options?.time_series?.echart_option || {},
          { arrayMerge: (_, newArr) => newArr }
        ) as EChartOption<EChartOption.Series>;
        this.options = Object.freeze(
          deepmerge(echartOptions, {
            animation: hasShowSymbol,
            color: this.panel.options?.time_series?.type === 'bar' ? COLOR_LIST_BAR : COLOR_LIST,
            animationThreshold: 1,
            yAxis: {
              axisLabel: {
                formatter: seriesList.every((item: any) => item.unit === seriesList[0].unit)
                  ? (v: any) => {
                      if (seriesList[0].unit !== 'none') {
                        const obj = getValueFormat(seriesList[0].unit)(v, seriesList[0].precision);
                        return obj.text + (this.yAxisNeedUnitGetter ? obj.suffix : '');
                      }
                      return v;
                    }
                  : (v: number) => this.handleYxisLabelFormatter(v - this.minBase)
              },
              splitNumber: this.height < 120 ? 2 : 4,
              minInterval: 1,
              scale: this.height < 120 ? false : canScale,
              max: v => Math.max(v.max, +maxThreshold),
              min: v => Math.min(v.min, +minThreshold),
              z: 1
            },
            xAxis: {
              axisLabel: {
                formatter: formatterFunc || '{value}'
              },
              splitNumber: Math.ceil(this.width / 80),
              min: 'dataMin'
            },
            series: seriesList
          })
        );
        this.metrics = metrics || [];
        this.handleDrillDownOption(this.metrics);
        this.inited = true;
        this.empty = false;
        if (!this.hasSetEvent && this.needSetEvent) {
          setTimeout(this.handleSetLegendEvent, 300);
          this.hasSetEvent = true;
        }
        setTimeout(() => {
          this.handleResize();
        }, 100);
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

  /**
   * @description:
   * @param {ITimeSeriesItem} serieList
   * @return {*}
   */
  handleSetOnlyOneMarkArea(serieList: ITimeSeriesItem[]) {
    if (!this.markArea) return;
    const markAreaItemList = serieList.filter(item => !!item.markArea);
    if (markAreaItemList.length > 1) {
      markAreaItemList.forEach((item, index) => {
        index >= 1 && (item.markArea = undefined);
      });
    } else if (markAreaItemList.length < 1) {
      const legendDataShowItemName = this.legendData.find(item => item.show)?.name;
      const item = serieList.find(item => item.name === legendDataShowItemName);
      item && (item.markArea = { ...this.markArea });
    }
    return serieList;
  }

  handleSelectLegend({ actionType, item }: { actionType: LegendActionType; item: ILegendItem }) {
    if (this.legendData.length < 2) {
      return;
    }
    const copyOptions = { ...this.options };
    const setOnlyOneMarkArea = () => {
      const showNames = [];
      this.legendData.forEach(l => {
        l.show && showNames.push(l.name);
      });
      copyOptions.series = this.seriesList.filter(s => showNames.includes(s.name));
      copyOptions.series = this.handleSetOnlyOneMarkArea(copyOptions.series as any);
      this.options = Object.freeze({ ...copyOptions });
    };
    if (actionType === 'shift-click') {
      item.show = !item.show;
      setOnlyOneMarkArea();
      this.$emit('selectLegend', this.legendData);
    } else if (actionType === 'click') {
      const hasOtherShow = this.legendData.filter(item => !item.hidden).some(set => set.name !== item.name && set.show);
      this.legendData.forEach(legend => {
        legend.show = legend.name === item.name || !hasOtherShow;
      });
      setOnlyOneMarkArea();
      this.$emit('selectLegend', this.legendData);
      setTimeout(() => {
        this.handleResize();
      }, 100);
    }
  }

  handleRestore() {
    if (!!this.enableSelectionRestoreAll) {
      this.handleRestoreEvent();
    } else {
      this.dataZoom(undefined, undefined);
    }
  }

  render() {
    const { legend } = this.panel?.options || { legend: {} };
    return (
      <div class='time-series'>
        {this.showChartHeader && (
          <ChartHeader
            class='draggable-handle'
            title={this.panel.title}
            showMore={this.showHeaderMoreTool}
            inited={this.inited}
            menuList={this.menuList}
            drillDownOption={this.drillDownOptions}
            showAddMetric={this.showAddMetric}
            draging={this.panel.draging}
            metrics={this.metrics}
            subtitle={this.panel.subTitle || ''}
            isInstant={this.panel.instant}
            onAlarmClick={this.handleAlarmClick}
            onUpdateDragging={() => this.panel.updateDraging(false)}
            onMenuClick={this.handleMenuToolsSelect}
            onSelectChild={this.handleSelectChildMenu}
            onMetricClick={this.handleMetricClick}
            onAllMetricClick={this.handleAllMetricClick}
          />
        )}
        {!this.empty ? (
          <div class={`time-series-content ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
            <div
              class={`chart-instance ${legend?.displayMode === 'table' ? 'is-table-legend' : ''}`}
              ref='chart'
            >
              {this.inited && (
                <BaseEchart
                  ref='baseChart'
                  showRestore={this.showRestore}
                  height={this.height}
                  width={this.width}
                  options={this.options}
                  groupId={this.panel.dashboardId}
                  onDataZoom={this.dataZoom}
                  onDblClick={this.handleDblClick}
                  onRestore={this.handleRestore}
                />
              )}
            </div>
            {legend?.displayMode !== 'hidden' && (
              <div class={`chart-legend ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
                {legend?.displayMode === 'table' ? (
                  <TableLegend
                    onSelectLegend={this.handleSelectLegend}
                    legendData={this.legendData}
                  />
                ) : (
                  <ListLegend
                    onSelectLegend={this.handleSelectLegend}
                    legendData={this.legendData}
                  />
                )}
              </div>
            )}
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}
