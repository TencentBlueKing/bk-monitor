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
import { CancelToken } from 'monitor-api/cancel';
import { Debounce, deepClone, random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { getValueFormat } from '../../../monitor-echarts/valueFormats';
import ListLegend from '../../components/chart-legend/common-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { COLOR_LIST_OUTLIER, MONITOR_LINE_OPTIONS } from '../../constants';
import { reviewInterval } from '../../utils';
import { VariablesService } from '../../utils/variable';
import BaseEchart from '../monitor-base-echart';
import { LineChart } from '../time-series/time-series';

import type { ILegendItem, ITimeSeriesItem, LegendActionType } from '../../typings';

import './time-series-outlier.scss';

interface ISensitivityRangeItem {
  color: string;
  id: string;
  name: string;
}
const LOWER_STR = 'lower-';
const UPPER_STR = 'upper-';
const RESULT_SERIES_NAME = '_result_';
const COLOR_LIST = [
  '#F4F9FC',
  '#E7F2F7',
  '#DCECF4',
  '#D1E6F1',
  '#C5DFEC',
  '#B9D9E9',
  '#AED3E5',
  '#A3CDE2',
  '#96C6DE',
  '#96C6DE',
  '#96C6DE',
];
const sensitivityRangeList: ISensitivityRangeItem[] = COLOR_LIST.map((color, index) => ({
  id: `${index}`,
  name: `${window.i18n.t('敏感度区间')}${index}`,
  color,
}));
@Component
export default class TimeSeriesOutlier extends LineChart {
  // y值基数
  minBase = 0;
  // 候选列表
  selectSensitivity: string[] = ['0', '5', '10'];
  // series
  seriesList = [];
  // bound series
  boundarySeries = {};
  // 标记区间
  markArea;

  // legend
  get localLegendData() {
    const list = this.legendData.reduce((total, item) => {
      if ([RESULT_SERIES_NAME].includes(item.metricField)) {
        item.name = this.createLegendName(item.dimensions) || item.name;
        total.push(item);
      }
      return total;
    }, []);
    const sensitivityList = [];
    this.boundarySeries &&
      sensitivityRangeList.forEach(item => {
        if (this.selectSensitivity.includes(item.id)) {
          sensitivityList.push({
            color: item.color,
            name: item.name,
            show: true,
          });
        }
      });
    return [...list, ...sensitivityList];
  }

  /**
   * 根据维度信息创建图例名字
   * @param dimensions 维度值
   * @returns 图例名
   */
  createLegendName(dimensions: Record<string, string>) {
    const list = Object.entries(dimensions).reduce((total, item) => {
      const [, value] = item;
      try {
        const obj = JSON.parse(value as string);
        total.push(obj);
      } catch (error) {
        console.log(error);
      }
      return total;
    }, []);
    const item = list[0];
    if (item) {
      return Object.entries(item)
        .reduce((total, tar) => {
          const [, val] = tar;
          total.push(val);
          return total;
        }, [])
        .join('|');
    }
    return '';
  }

  /** 阈值线 */
  createMarkLine(item) {
    if (item.metric_field !== RESULT_SERIES_NAME) return {};
    return this.panel.options?.time_series_forecast?.markLine || {};
  }
  /** 区域标记 */
  createMarkArea(item) {
    if (item.metric_field !== RESULT_SERIES_NAME) return {};
    // /** 阈值区域 */
    let alertMarkArea: Record<string, any> = {};
    /** 告警区域 */
    if (item.markTimeRange?.length) {
      const [{ from, to }] = item.markTimeRange;
      alertMarkArea = this.handleSetThresholdBand([
        {
          from,
          to,
          color: 'rgba(253, 156, 156, 0.2)',
          borderColor: 'rgba(253, 156, 156, 0.2)',
          shadowColor: 'rgba(253, 156, 156, 0.2)',
        },
      ]);
    }
    return { ...alertMarkArea, z: 10 };
  }
  /**
   * @description:
   * @return {*}
   */
  handleSetThresholds() {
    const { markLine } = this.panel?.options?.time_series_forecast || {};
    const thresholdList = markLine?.data?.map?.(item => item.yAxis) || [];
    const max = Math.max(...thresholdList);
    return {
      canScale: thresholdList.length > 0 && thresholdList.every((set: number) => set > 0),
      minThreshold: Math.min(...thresholdList),
      maxThreshold: max + max * 0.1, // 防止阈值最大值过大时title显示不全
    };
  }
  /**
   * @description:
   * @param {ITimeSeriesItem} serieList
   * @return {*}
   */
  handleSetOnlyOneMarkArea(serieList: ITimeSeriesItem[]) {
    if (!this.markArea) return;
    const markAreaItemList = serieList.filter(item => item.markArea?.data);
    if (markAreaItemList.length > 1) {
      markAreaItemList.forEach((item, index) => {
        index >= 1 && (item.markArea = undefined);
      });
    } else if (markAreaItemList.length < 1) {
      const item = serieList.find(item => !sensitivityRangeList.some(set => item.name.includes(set.name)));
      item && (item.markArea = { ...this.markArea });
    }
    return serieList;
  }
  /**
   * @description: 获取图表数据
   * @param {*}
   * @return {*}
   */
  @Debounce(200)
  async getPanelData(start_time?: string, end_time?: string) {
    this.cancelTokens.forEach(cb => cb?.());
    this.cancelTokens = [];
    if (!this.isInViewPort()) {
      if (this.intersectionObserver) {
        this.unregisterObserver();
      }
      this.registerObserver(start_time, end_time);
      return;
    }
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.t('加载中...');
    try {
      this.unregisterObserver();
      let series = [];
      const metrics = [];
      // mock 数据 暂时注释接口
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      let params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
      };
      if (this.bkBizId) {
        params = Object.assign({}, params, {
          bk_biz_id: this.bkBizId,
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
        interval,
      });
      timeShiftList.forEach(time_shift => {
        const list = this.panel.targets.map(item => {
          const newParams = {
            ...variablesService.transformVariables(item.data, {
              ...this.viewOptions.filters,
              ...(this.viewOptions.filters?.current_target || {}),
              ...this.viewOptions,
              ...this.viewOptions.variables,
              time_shift,
              interval,
            }),
            ...params,
            down_sample_range: this.downSampleRangeComputed(
              this.downSampleRange as string,
              [params.start_time, params.end_time],
              item.apiFunc
            ),
          };
          return (this as any).$api[item.apiModule]
            [item.apiFunc](newParams, {
              cancelToken: new CancelToken((cb: () => void) => this.cancelTokens.push(cb)),
              needMessage: false,
            })
            .then(res => {
              metrics.push(...res.metrics);
              series.push(
                ...res.series.map(set => ({
                  ...set,
                  name: `${this.timeOffset.length ? `${this.handleTransformTimeShift(time_shift || 'current')}-` : ''}
                     ${this.handleSeriesName(item, set) || set.target}`,
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
        this.series = series;
        if (this.onlyOneResult) {
          let hasResultSeries = false;
          series = series.filter(item => {
            const pass = !(hasResultSeries && item.alias === RESULT_SERIES_NAME);
            pass && (hasResultSeries = true);
            return pass;
          });
        }
        const seriesResult = series
          .filter(item => ['extra_info', RESULT_SERIES_NAME].includes(item.alias))
          .map(item => ({
            ...item,
            datapoints: item.datapoints.map(point => [JSON.parse(point[0])?.anomaly_score ?? point[0], point[1]]),
          }));
        let seriesList = this.handleTransformSeries(
          seriesResult.map((item, index) => ({
            name: this.createLegendName(item.dimensions) || item.name,
            cursor: 'auto',
            dimensions: item.dimensions,
            data: item.datapoints.reduce((pre: any, cur: any) => (pre.push(cur.reverse()), pre), []),
            stack: item.stack || random(10),
            unit: item.unit,
            metricField: item.metric_field,
            markLine: this.createMarkLine(index),
            markArea: this.createMarkArea(item),
            z: 1,
          })) as any,
          COLOR_LIST_OUTLIER
        );
        // mock 数据
        const boundarySeries = this.handleOutlierBoundaryList(series);
        let boundarySeriesList = [];
        this.boundarySeries = boundarySeries;
        if (boundarySeries) {
          boundarySeriesList = this.selectSensitivity.reduce((result, id) => {
            result.push(boundarySeries[id][0]);
            result.push(boundarySeries[id][1]);
            return result;
          }, []);
        }
        seriesList = [...seriesList.map((item: any) => ({ ...item, z: 6 })), ...boundarySeriesList];
        seriesList = seriesList.map((item: any) => {
          if (item.markArea && !this.markArea?.data) {
            this.markArea = { ...item.markArea };
          }
          return {
            ...item,
            minBase: this.minBase,
            data:
              item.metricField === RESULT_SERIES_NAME
                ? item.data.map((set: any) => {
                    if (set?.length) {
                      return [set[0], set[1] !== null ? set[1] + this.minBase : null];
                    }
                    return {
                      ...set,
                      value: [set.value[0], set.value[1] !== null ? set.value[1] + this.minBase : null],
                    };
                  })
                : item.data,
          };
        });
        this.seriesList = Object.freeze([
          ...seriesList.filter(item => !sensitivityRangeList.some(set => set.name === item.name)),
        ]) as any;
        // 1、echarts animation 配置会影响数量大时的图表性能 掉帧
        // 2、echarts animation配置为false时 对于有孤立点不连续的图表无法放大 并且 hover的点放大效果会潇洒 (貌似echarts bug)
        // 所以此处折中设置 在有孤立点情况下进行开启animation 连续的情况不开启
        const hasShowSymbol = seriesList.some(item => item.showSymbol);
        if (this.markArea) this.handleSetOnlyOneMarkArea(seriesList);
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
                    opacity: 1,
                  },
                };
              }
              return set;
            });
          });
        }
        const formatterFunc = this.handleSetFormatterFunc(seriesList[0].data);
        const { canScale, minThreshold, maxThreshold } = this.handleSetThresholds();

        const chartBaseOptions = MONITOR_LINE_OPTIONS;

        const echartOptions = deepmerge(
          deepClone(chartBaseOptions),
          this.panel.options?.time_series?.echart_option || {},
          { arrayMerge: (_, newArr) => newArr }
        );
        this.options = Object.freeze(
          deepmerge(
            echartOptions,
            {
              animation: hasShowSymbol,
              color: COLOR_LIST_OUTLIER,
              animationThreshold: 1,
              tooltip: {
                formatter: p => this.handleSetTooltip(p),
              },
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
                    : (v: number) => this.handleYAxisLabelFormatter(v - this.minBase),
                },
                splitNumber: this.height < 120 ? 2 : 4,
                minInterval: 1,
                scale: this.height < 120 ? false : canScale,
                max: v => Math.max(v.max, +maxThreshold),
                min: v => Math.min(v.min, +minThreshold),
              },
              xAxis: {
                axisLabel: {
                  formatter: formatterFunc || '{value}',
                },
                splitNumber: Math.ceil(this.width / 80),
                min: 'dataMin',
              },
              series: seriesList,
            },
            {
              arrayMerge: (_, sourceArray) => sourceArray,
            }
          )
        );
        this.metrics = metrics || [];
        this.handleDrillDownOption(this.metrics);
        this.initialized = true;
        this.empty = false;
        if (!this.hasSetEvent && this.needSetEvent) {
          setTimeout(this.handleSetLegendEvent, 300);
          this.hasSetEvent = true;
        }
        setTimeout(() => {
          this.handleResize();
        }, 100);
      } else {
        this.emptyText = window.i18n.t('查无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.t('出错了');
      console.error(e);
    }
    this.cancelTokens = [];
    this.handleLoadingChange(false);
  }
  handleOutlierBoundaryList(series: any[]) {
    const tartletBoundary = series.find(item => item.metric_field === 'bounds');
    if (tartletBoundary) {
      const data = sensitivityRangeList.reduce(
        (pre, item, index) => ({
          ...pre,
          [`${UPPER_STR}${index}`]: [],
          [`${LOWER_STR}${index}`]: [],
        }),
        {}
      );
      const bound = tartletBoundary.datapoints.reduce((result, item) => {
        const timeBound = JSON.parse(item[0]);
        const timeValue = item[1];
        if (!timeBound) {
          Object.values(data).forEach((v: any) => v.push([null, timeValue]));
          return result;
        }
        timeBound.cluster1.upper.forEach((up, index) => {
          result[`${UPPER_STR}${index}`].push([up, timeValue]);
        });
        timeBound.cluster1.lower.forEach((low, index) => {
          result[`${LOWER_STR}${index}`].push([low, timeValue]);
        });
        return result;
      }, data);
      const boundaryList = sensitivityRangeList.map(({ color, name, id }, index) => ({
        upBoundary: bound[`${UPPER_STR}${index}`],
        lowBoundary: bound[`${LOWER_STR}${index}`],
        type: 'line',
        stack: `boundary-${index}`,
        color,
        name,
        id,
      }));
      // 上下边界处理
      if (boundaryList?.length) {
        boundaryList.forEach((item: any) => {
          const base = -item.lowBoundary.reduce(
            (min: number, val: any) => (val[0] !== null ? Math.floor(Math.min(min, val[0])) : min),
            Number.POSITIVE_INFINITY
          );
          this.minBase = Math.max(base, this.minBase);
        });
        const boundarySeries = boundaryList.reduce((result, item) => {
          result[item.id] = this.createBoundarySeries(item, this.minBase);
          return result;
        }, {});
        return boundarySeries;
      }
    }
  }
  /**
   *
   * @param item 边界数据
   * @param base 边界数据最小值
   * @returns 边界数据series
   */
  createBoundarySeries(item: any, base: number) {
    return [
      {
        name: `${LOWER_STR}${item.name}`,
        type: 'line',
        data: item.lowBoundary.map((item: any) => [item[1], item[0] === null ? null : item[0] + base]),
        lineStyle: {
          opacity: 0,
        },
        stack: item.stack,
        symbol: 'none',
        z: item.z || 4,
      },
      {
        name: `${UPPER_STR}${item.name}`,
        type: 'line',
        data: item.upBoundary.map((set: any, index: number) => [
          set[1],
          set[0] === null ? null : set[0] - item.lowBoundary[index][0],
        ]),
        lineStyle: {
          opacity: 0,
        },
        areaStyle: {
          color: item.color || '#e6e6e6',
          opacity: 0.6,
        },
        stack: item.stack,
        symbol: 'none',
        z: item.z || 4,
      },
    ];
  }
  handleSetTooltip(params) {
    if (!params || params.length < 1 || params.every(item => item.value[1] === null)) {
      return;
    }
    let liHtmlList = [];
    const ulStyle = '';
    const pointTime = dayjs.tz(params[0].axisValue).format('YYYY-MM-DD HH:mm:ss');
    if (params[0]?.data?.tooltips) {
      liHtmlList.push(params[0].data.tooltips);
    } else {
      const data = params.map(item => ({ color: item.color, seriesName: item.seriesName, value: item.value[1] }));
      const list = [];
      const boundList = [];
      params.forEach(item => {
        if (item.seriesName.match(/^(upper|lower)-/)) {
          const seriesName = item.seriesName.replace(/^(upper|lower)-/, '');
          if (!boundList.some(set => set.seriesName === seriesName)) {
            const tooltipValues = params.filter(set => set.seriesName.includes(seriesName)).map(item => item.value[1]);
            tooltipValues.sort((a, b) => a - b);
            const v = +seriesName.match(/敏感度区间([\d]+)$/)?.[1];
            boundList.push({
              ...item,
              value: [item.value[0], v],
              seriesName,
              tooltipValues,
            });
          }
        } else {
          list.push({
            ...item,
          });
        }
      });
      list.sort((a, b) => b.value[1] - a.value[1]);
      boundList.sort((a, b) => a.value[1] - b.value[1]);
      liHtmlList = [...list, ...boundList].map(item => {
        let markColor = 'color: #fafbfd;';
        if (data[0].value === item.value[1]) {
          markColor = 'color: #fff;font-weight: bold;';
        }
        if (item.value[1] === null) return '';
        let curSeries: any = this.options.series[item.seriesIndex];
        if (curSeries?.stack?.includes('boundary-')) {
          curSeries = this.options.series.find((item: any) => !item?.stack?.includes('boundary-'));
        }
        const unitFormatter = curSeries.unitFormatter || (v => ({ text: v }));
        const precision =
          !['none', ''].some(val => val === curSeries.unit) && +curSeries.precision < 1 ? 2 : +curSeries.precision;
        let text = '';
        if (item.tooltipValues) {
          text = `(${item.tooltipValues
            .map((v, index) => {
              const valueObj = unitFormatter(
                index === 0 ? v - this.minBase : v + (item.tooltipValues[0] - this.minBase),
                precision
              );
              return `${valueObj?.text} ${valueObj?.suffix || ''}`;
            })
            .join(',')})`;
        } else {
          const valueObj = unitFormatter(item.value[1] - this.minBase, precision);
          text = `${valueObj?.text} ${valueObj?.suffix || ''}`;
        }
        return `<li class="tooltips-content-item">
                  <span class="item-series"
                   style="background-color:${item.color};">
                  </span>
                  <span class="item-name" style="${markColor}">${item.seriesName}:</span>
                  <span class="item-value" style="${markColor}">
                  ${text}</span>
                  </li>`;
      });
      if (liHtmlList?.length < 1) return '';
    }
    return `<div class="monitor-chart-tooltips">
            <p class="tooltips-header">
                ${pointTime}
            </p>
            <ul class="tooltips-content" style="${ulStyle}">
                ${liHtmlList?.join('')}
            </ul>
            </div>`;
  }
  handleSensitivityRangeChange(sensitivity: ISensitivityRangeItem) {
    const copyOptions = { ...this.options };
    const index = this.selectSensitivity.findIndex(item => item === sensitivity.id);
    if (index > -1) {
      this.selectSensitivity.splice(index, 1);
      copyOptions.series = this.handleSetOnlyOneMarkArea(
        copyOptions.series.filter(item => !item.name.includes(sensitivity.name)) as any
      );
    } else {
      this.selectSensitivity.push(sensitivity.id);
      copyOptions.series = this.handleSetOnlyOneMarkArea([
        ...copyOptions.series,
        ...this.boundarySeries[sensitivity.id],
      ]);
    }
    this.options = Object.freeze({ ...copyOptions });
    setTimeout(() => {
      this.handleResize();
    }, 100);
  }

  handleSelectLegend({ actionType, item }: { actionType: LegendActionType; item: ILegendItem }) {
    if (actionType === 'click') {
      const copyOptions = { ...this.options };
      const targetLegend = this.localLegendData.find(legend => legend.name === item.name);
      if (targetLegend.show) {
        copyOptions.series = this.handleSetOnlyOneMarkArea(
          copyOptions.series.filter(ser => {
            if (ser.name === item.name) {
              return false;
            }
            if (sensitivityRangeList.some(set => set.name === item.name)) {
              return !ser.name.includes(item.name);
            }
            return true;
          }) as any
        );
      } else {
        const series = this.seriesList.filter(ser => ser.name === item.name);
        if (series.length) {
          copyOptions.series = this.handleSetOnlyOneMarkArea([...copyOptions.series, ...series]);
        } else {
          const value: any = Object.values(this.boundarySeries).find((set: any[]) =>
            set.some(v => v.name.includes(targetLegend.name))
          );
          copyOptions.series = this.handleSetOnlyOneMarkArea([...copyOptions.series, ...value]);
        }
      }
      targetLegend.show = !item.show;
      this.options = Object.freeze({ ...copyOptions });
      setTimeout(() => {
        this.handleResize();
      }, 100);
    }
  }
  render() {
    const { legend } = this.panel?.options || {};
    return (
      <div class='time-series-outliter time-series'>
        {this.showChartHeader && (
          <ChartHeader
            class='draggable-handle'
            dragging={this.panel.dragging}
            isInstant={this.panel.instant}
            menuList={this.menuList}
            metrics={this.metrics}
            showAddMetric={this.showAddMetric}
            showMore={false}
            subtitle={this.panel.subTitle || ''}
            title={this.panel.title}
            onAlarmClick={this.handleAlarmClick}
            onAllMetricClick={this.handleAllMetricClick}
            onMenuClick={this.handleMenuToolsSelect}
            onMetricClick={this.handleMetricClick}
            onUpdateDragging={() => this.panel.updateDragging(false)}
          />
        )}
        {!this.empty ? (
          <div class={`time-series-content ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
            <div
              ref='chart'
              class='chart-instance'
            >
              {this.initialized && (
                <BaseEchart
                  width={this.width}
                  height={this.height}
                  groupId={this.panel.dashboardId}
                  options={this.options}
                  onDataZoom={this.dataZoom}
                  onDblClick={this.handleDblClick}
                />
              )}
            </div>
            {legend?.displayMode !== 'hidden' && (
              <div class={`chart-legend ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
                <ListLegend
                  legendData={this.localLegendData}
                  onSelectLegend={this.handleSelectLegend}
                >
                  {this.boundarySeries && (
                    <bk-dropdown-menu
                      slot='expand'
                      positionFixed={true}
                    >
                      <div
                        class='dropdown-trigger-btn'
                        slot='dropdown-trigger'
                      >
                        <i
                          style='margin-right:4px'
                          class='bk-icon icon-cog-shape'
                        />
                        <span>{this.$t('更多敏感度区间设置')}</span>
                      </div>
                      <ul
                        style='height: 250px'
                        slot='dropdown-content'
                      >
                        {sensitivityRangeList.map(item => (
                          <li
                            class={{ active: this.selectSensitivity.includes(item.id) }}
                            onClick={() => {
                              this.handleSensitivityRangeChange(item);
                            }}
                          >
                            <span>{item.name}</span>
                            {this.selectSensitivity.includes(item.id) && (
                              <i class='bk-option-icon bk-icon icon-check-1' />
                            )}
                          </li>
                        ))}
                      </ul>
                    </bk-dropdown-menu>
                  )}
                </ListLegend>
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
