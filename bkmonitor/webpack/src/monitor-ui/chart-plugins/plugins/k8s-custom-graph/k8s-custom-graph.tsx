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

import { Component, Inject, InjectReactive, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { toPng } from 'html-to-image';
import { CancelToken } from 'monitor-api/cancel';
import { Debounce, deepClone, random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import {
  downCsvFile,
  transformSrcData,
  transformTableDataToCsvStr,
  type IUnifyQuerySeriesItem,
} from 'monitor-pc/pages/view-detail/utils';

import { type ValueFormatter, getValueFormat } from '../../../monitor-echarts/valueFormats';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { COLOR_LIST, COLOR_LIST_BAR, MONITOR_LINE_OPTIONS } from '../../constants';
import { convertToSeconds, downFile, isShadowEqual } from '../../utils';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from '../../utils/axis';
import { VariablesService } from '../../utils/variable';
import { CommonSimpleChart } from '../common-simple-chart';
import BaseEchart from '../monitor-base-echart';
import K8sDimensionDrillDown from './k8s-dimension-drilldown';

import type {
  DataQuery,
  IExtendMetricData,
  ILegendItem,
  IMenuChildItem,
  IMenuItem,
  ITitleAlarm,
  ITimeSeriesItem,
  PanelModel,
} from '../../../chart-plugins/typings';
import type { IChartTitleMenuEvents } from '../../components/chart-title/chart-title-menu';

import './k8s-custom-graph.scss';
const SpecialSeriesColorMap = {
  request: {
    color: '#FEA56B',
    labelColor: '#E38B02',
    itemColor: '#FDEED8',
  },
  limit: {
    color: '#FF5656',
    labelColor: '#E71818',
    itemColor: '#FFEBEB',
  },
  capacity: {
    color: '#4DA6FF', // 明亮的蓝色
    labelColor: '#0073E6', // 稍深的蓝色，用于标签
    itemColor: '#E6F2FF', // 非常浅的蓝色，用于背景
  },
};
interface IProps {
  panel: PanelModel;
}

function removeTrailingZeros(num) {
  if (num && num !== '0') {
    return num
      .toString()
      .replace(/(\.\d*?)0+$/, '$1')
      .replace(/\.$/, '');
  }
  return num;
}

function getNumberAndUnit(str) {
  const match = str.match(/^(\d+)([a-zA-Z])$/);
  return match ? { number: Number.parseInt(match[1], 10), unit: match[2] } : null;
}

function timeToDayNum(t) {
  const regex = /^\d{4}-\d{2}-\d{2}$/;
  if (regex.test(t)) {
    return dayjs().diff(dayjs(t), 'day');
  }
  const timeInfo = getNumberAndUnit(t);
  if (timeInfo?.unit === 'd') {
    return timeInfo.number;
  }
  if (timeInfo?.unit === 'w') {
    return timeInfo.number * 7;
  }
  return 0;
}

@Component
class K8SCustomChart extends CommonSimpleChart {
  // 当前粒度
  @InjectReactive('downSampleRange') readonly downSampleRange: number | string;
  // yAxis是否需要展示单位
  @InjectReactive('yAxisNeedUnit') readonly yAxisNeedUnit: boolean;

  // 框选事件范围后需应用到所有图表(包含三个数据 框选方法 是否展示复位  复位方法)
  @Inject({ from: 'enableSelectionRestoreAll', default: false }) readonly enableSelectionRestoreAll: boolean;
  @Inject({ from: 'handleChartDataZoom', default: () => null }) readonly handleChartDataZoom: (value: any) => void;
  @Inject({ from: 'handleRestoreEvent', default: () => null }) readonly handleRestoreEvent: () => void;
  @Inject({ from: 'onDrillDown', default: () => null }) readonly onDrillDown: (group: string, name: string) => void;
  @Inject({ from: 'onShowDetail', default: () => null }) readonly onShowDetail: (
    dimensions: Record<string, string>
  ) => void;
  @InjectReactive({ from: 'showRestore', default: false }) readonly showRestoreInject: boolean;
  // 时间对比的偏移量
  @InjectReactive('timeOffset') readonly timeOffset: string[];
  metrics = [];
  options = {};
  empty = true;
  emptyText = window.i18n.t('暂无数据');
  cancelTokens = [];

  /** 导出csv数据时候使用 */
  series: IUnifyQuerySeriesItem[];
  minBase = 0;
  // 切换图例时使用
  seriesList = null;
  drillDownOptions: IMenuChildItem[] = [];
  hasSetEvent = false;
  collectIntervalDisplay = '1m';

  // 是否展示复位按钮
  showRestore = false;

  // 图例排序
  legendSorts: { name: string; timeShift: string }[] = [];

  get yAxisNeedUnitGetter() {
    return this.yAxisNeedUnit ?? true;
  }
  // 同时hover显示多个tooltip
  get hoverAllTooltips() {
    return this.panel.options?.time_series?.hoverAllTooltips;
  }

  get curTitle() {
    return this.panel.title;
  }

  get menuList() {
    return ['save', 'more', 'explore', 'area', 'drill-down', 'strategy', 'relate-alert'];
  }

  @Watch('showRestoreInject', { immediate: true })
  handleShowRestoreInject(v: boolean) {
    this.showRestore = v;
  }

  @Watch('panel')
  panelChange(val, old) {
    if (isShadowEqual(val, old)) return;
    this.getPanelData();
  }

  @Watch('timeOffset')
  handleTimeOffsetChange(v: string[], o: string[]) {
    if (JSON.stringify(v) === JSON.stringify(o)) return;
    this.getPanelData();
  }

  /**
   * @description: 获取图表数据
   * @param {*}
   * @return {*}
   */
  @Debounce(100)
  async getPanelData(start_time?: string, end_time?: string) {
    if (!(await this.beforeGetPanelData())) {
      return;
    }
    if (!this.$el?.clientWidth) return;
    this.cancelTokens.forEach(cb => cb?.());
    this.cancelTokens = [];
    if (this.initialized) this.handleLoadingChange(true);
    this.emptyText = window.i18n.t('加载中...');
    if (
      this.panel.targets.some(item =>
        item.data?.query_configs?.some(q => q.data_source_label === 'prometheus' && !q.promql)
      )
    ) {
      this.empty = true;
      this.emptyText = window.i18n.t('暂无数据');
    } else {
      try {
        this.unregisterObserver();
        const series = [];
        const metrics = [];
        this.legendSorts = [];
        const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
        let params = {
          start_time: start_time ? dayjs(start_time).unix() : startTime,
          end_time: end_time ? dayjs(end_time).unix() : endTime,
        };
        if (this.bkBizId) {
          params = Object.assign({}, params, {
            bk_biz_id: this.bkBizId,
          });
        }
        const promiseList = [];
        const timeShiftList = ['', ...this.timeOffset];
        const down_sample_range =
          this.downSampleRangeComputed(
            this.viewOptions.interval.toString(),
            [params.start_time, params.end_time],
            'unifyQuery'
          ) || '';
        const [v] = down_sample_range.split('s');
        const interval = this.viewOptions.interval === 'auto' ? `${Math.ceil(+v / 60)}m` : down_sample_range;
        this.collectIntervalDisplay = interval;
        const variablesService = new VariablesService({});
        for (const timeShift of timeShiftList) {
          const noTransformVariables = this.panel?.options?.time_series?.noTransformVariables;
          const list = this.panel.targets
            .filter(item => (timeShiftList.length > 1 ? !item.request_or_limit : true))
            .map(item => {
              const newParams = structuredClone({
                ...variablesService.transformVariables(
                  item.data,
                  {
                    ...this.viewOptions.filters,
                    ...this.viewOptions,
                    ...this.viewOptions.variables,
                    time_shift: !timeShift ? ' ' : `offset ${timeShift}`,
                    interval,
                    interval_second: convertToSeconds(interval),
                  },
                  noTransformVariables
                ),
                ...params,
                down_sample_range,
              });
              return (this as any).$api[item.apiModule]
                [item.apiFunc](newParams, {
                  cancelToken: new CancelToken((cb: () => void) => this.cancelTokens.push(cb)),
                  needMessage: false,
                })
                .then(res => {
                  res.metrics && metrics.push(...res.metrics);
                  // if (res.series?.length > 1) {
                  //   res.series = res.series.slice(0, 1);
                  // }
                  res.series &&
                    series.push(
                      ...res.series.map(set => {
                        let name: string = this.handleSeriesName(item, set) || set.target;
                        let timeShiftName = '';
                        if (this.timeOffset.length) {
                          timeShiftName = this.handleTransformTimeShift(timeShift || 'current');
                          name = `${timeShiftName}-${name}`;
                        } else if (['limit', 'request', 'capacity'].includes(newParams.query_configs?.[0]?.alias)) {
                          name = newParams.query_configs?.[0]?.alias;
                        }
                        name = name.replace(/\|/g, ':');
                        this.legendSorts.push({
                          name: name,
                          timeShift: timeShift,
                        });
                        return {
                          ...set,
                          name,
                          customData: {
                            timeShiftName: timeShiftName,
                            metricName: name.replace(`${timeShiftName}-`, ''),
                          },
                        };
                      })
                    );
                  // 用于获取原始query_config
                  this.panel.setRawQueryConfigs(
                    item,
                    res.query_config || {
                      ...newParams,
                    }
                  );
                  this.clearErrorMsg();
                  return true;
                })
                .catch(error => {
                  this.handleErrorMsgChange(error.msg || error.message);
                });
            });
          promiseList.push(...list);
        }
        await Promise.all(promiseList).catch(() => false);
        this.metrics = metrics || [];
        if (series.length) {
          const { maxSeriesCount, maxXInterval } = getSeriesMaxInterval(series);
          /* 派出图表数据包含的维度*/
          this.series = Object.freeze(series) as any;
          const seriesResult = series
            .filter(item => ['extra_info', '_result_'].includes(item.alias))
            .map(item => ({
              ...item,
              name: item.name,
              datapoints: item.datapoints.map(point => [JSON.parse(point[0])?.anomaly_score ?? point[0], point[1]]),
            }));
          let seriesList = this.handleTransformSeries(
            seriesResult.map(item => ({
              name: item.name,
              cursor: 'auto',
              // biome-ignore lint/style/noCommaOperator: <explanation>
              data: item.datapoints.reduce((pre: any, cur: any) => (pre.push(cur.reverse()), pre), []),
              stack: item.stack || random(10),
              unit: this.viewOptions.unit || this.panel.options?.unit || item.unit,
              z: 1,
              traceData: item.trace_data ?? '',
              customData: item.customData,
              dimensions: item.dimensions ?? {},
            })) as any
          );
          let limitFirstY = 0;
          let requestFirstY = 0;
          let capacityFirstY = 0;
          seriesList = seriesList.map((item: any) => {
            const isSpecialSeries = this.isSpecialSeries(item.name);
            let color = item.lineStyle?.color;
            let markPoint = {};
            if (isSpecialSeries) {
              const isLimit = item.name === 'limit';
              const isCapacity = item.name === 'capacity';
              const colorMap = SpecialSeriesColorMap[item.name];
              color = colorMap.color;
              const labelColor = colorMap.labelColor;
              const itemColor = colorMap.itemColor;
              const firstValue = item.data?.find(item => item.value?.[1]);
              const firstValueY = firstValue?.value?.[1] || 0;
              if (isLimit) {
                limitFirstY = firstValueY;
              } else if (item.name === 'capacity') {
                capacityFirstY = firstValueY;
              } else {
                requestFirstY = firstValueY;
              }
              markPoint = {
                symbol: 'rect',
                symbolSize: [isLimit ? 30 : isCapacity ? 52 : 46, 16],
                symbolOffset: ['50%', 0],
                label: {
                  show: true,
                  color: labelColor,
                  formatter: () => item.name,
                },
                itemStyle: {
                  color: itemColor,
                },
                data: [
                  {
                    coord: firstValue?.value,
                  },
                ],
                emphasis: {
                  disabled: true,
                },
              };
              const legendItem = this.legendData.find(legend => legend.name === item.name);
              legendItem.color = color;
              legendItem.lineStyleType = isSpecialSeries ? 'dashed' : 'solid';
              legendItem.silent = isSpecialSeries;
            }
            return {
              ...item,
              minBase: this.minBase,
              color: isSpecialSeries ? color : undefined,
              data: item.data.map((set: any) => {
                if (set?.length) {
                  return [set[0], set[1] !== null ? set[1] + this.minBase : null];
                }
                return {
                  ...set,
                  value: [set.value[0], set.value[1] !== null ? set.value[1] + this.minBase : null],
                };
              }),
              lineStyle: {
                type: isSpecialSeries ? 'dashed' : 'solid',
                dashOffset: '4',
                color,
                width: 1.5,
              },
              areaStyle: isSpecialSeries
                ? undefined
                : {
                    opacity: 0.2,
                    color,
                  },
              markPoint,
            };
          });
          // 判断limit 与request是否重叠
          let min = 0;
          let max = 0;
          for (const item of this.legendData) {
            const minValue = Number(item.minSource);
            const maxValue = Number(item.maxSource);
            if (minValue < min) {
              min = minValue;
            }
            if (maxValue > max) {
              max = maxValue;
            }
          }
          const limitEqualRequest =
            Math.abs(limitFirstY - requestFirstY) / (max - min) < 16 / (this.height - 26) ||
            Math.abs(capacityFirstY - requestFirstY) / (max - min) < 16 / (this.height - 26);
          const capacityEqualRequest = Math.abs(limitFirstY - capacityFirstY) / (max - min) < 16 / (this.height - 26);
          seriesList = seriesList.map(item => {
            if ((limitEqualRequest && item.name === 'request') || (capacityEqualRequest && item.name === 'capacity')) {
              return {
                ...item,
                markPoint: {},
              };
            }
            return item;
          });
          this.seriesList = Object.freeze(seriesList) as any;
          // 1、echarts animation 配置会影响数量大时的图表性能 掉帧
          // 2、echarts animation配置为false时 对于有孤立点不连续的图表无法放大 并且 hover的点放大效果会潇洒 (貌似echarts bug)
          // 所以此处折中设置 在有孤立点情况下进行开启animation 连续的情况不开启
          const hasShowSymbol = seriesList.some(item => item.showSymbol);
          if (hasShowSymbol) {
            for (const item of seriesList) {
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
            }
          }
          const formatData = seriesList.find(item => item.data?.length > 0)?.data || [];
          const formatterFunc = this.handleSetFormatterFunc(formatData);

          const chartBaseOptions = MONITOR_LINE_OPTIONS;
          const echartOptions = deepmerge(
            deepClone(chartBaseOptions),
            this.panel.options?.time_series?.echart_option || {},
            { arrayMerge: (_, newArr) => newArr }
          );
          const isBar = this.panel.options?.time_series?.type === 'bar';
          const width = this.$el?.getBoundingClientRect?.()?.width;
          const xInterval = getTimeSeriesXInterval(maxXInterval, width || this.width, maxSeriesCount);
          this.options = Object.freeze(
            deepmerge(echartOptions, {
              animation: hasShowSymbol,
              color: isBar ? COLOR_LIST_BAR : COLOR_LIST,
              animationThreshold: 1,
              yAxis: {
                axisLabel: {
                  formatter: seriesList.every((item: any) => item.unit === seriesList[0].unit)
                    ? (v: any) => {
                        if (seriesList[0].unit !== 'none') {
                          const obj = getValueFormat(seriesList[0].unit)(v, seriesList[0].precision);
                          return removeTrailingZeros(obj.text) + (this.yAxisNeedUnitGetter ? obj.suffix : '');
                        }
                        return v;
                      }
                    : (v: number) => this.handleYAxisLabelFormatter(v - this.minBase),
                },
                splitNumber: this.height < 120 ? 2 : 4,
                minInterval: 1,
                max: 'dataMax',
                min: 0,
                scale: false,
              },
              xAxis: {
                axisLabel: {
                  formatter: formatterFunc || '{value}',
                },
                ...xInterval,
                splitNumber: 4,
              },
              series: seriesList,
              tooltip: {
                extraCssText: 'max-width: 50%',
              },
              customData: {
                // customData 自定义的一些配置 用户后面echarts实例化后的配置
                maxXInterval,
                maxSeriesCount,
              },
            })
          );
          this.handleDrillDownOption(this.metrics);
          this.initialized = true;
          this.empty = false;
          if (!this.hasSetEvent) {
            setTimeout(this.handleSetLegendEvent, 300);
            this.hasSetEvent = true;
          }
          setTimeout(() => {
            this.handleResize();
          }, 100);
        } else {
          this.initialized = this.metrics.length > 0;
          this.emptyText = window.i18n.t('暂无数据');
          this.empty = true;
        }
      } catch (e) {
        console.error(e);
        this.empty = true;
        this.emptyText = window.i18n.t('出错了');
      }
    }

    this.cancelTokens = [];
    this.handleLoadingChange(false);
    this.unregisterObserver();
  }
  isSpecialSeries(name: string) {
    return ['request', 'limit', 'capacity'].includes(name);
  }
  // 转换time_shift显示
  handleTransformTimeShift(val: string) {
    const timeMatch = val.match(/(-?\d+)(\w+)/);
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    const hasMatch = timeMatch && timeMatch.length > 2;
    if (dateRegex.test(val)) {
      return val;
    }
    if (val === '1d') {
      return this.$t('昨天');
    }
    if (val === '1w') {
      return this.$t('上周');
    }
    return hasMatch
      ? (dayjs() as any).add(-timeMatch[1], timeMatch[2]).fromNow().replace(/\s*/g, '')
      : val.replace('current', window.i18n.t('当前'));
  }

  handleSeriesName(item: DataQuery, set) {
    const { dimensions = {}, dimensions_translation = {} } = set;
    if (!item.alias)
      return set.time_offset
        ? this.handleTimeOffset(set.time_offset)
        : Object.values({
            ...dimensions,
            ...dimensions_translation,
          }).join('|');
    const aliasFix = Object.values(dimensions).join('|');
    if (!aliasFix.length) return item.alias;
    return `${item.alias}-${aliasFix}`;
  }
  /** 处理时间对比时线条名字 */
  handleTimeOffset(timeOffset: string) {
    const match = timeOffset.match(/(current|(\d+)([hdwM]))/);
    if (match) {
      const [target, , num, type] = match;
      const map = {
        d: this.$t('{n} 天前', { n: num }),
        w: this.$t('{n} 周前', { n: num }),
        M: this.$t('{n} 月前', { n: num }),
        current: this.$t('当前'),
      };
      return map[type || target];
    }
    return timeOffset;
  }

  /**
   * @description: 转换时序数据 并设置图例
   * @param {ITimeSeriesItem} series 图表时序数据
   * @return {*}
   */
  handleTransformSeries(series: ITimeSeriesItem[], colors?: string[]) {
    const legendData: ILegendItem[] = [];
    const specialSeriesCount = series.filter(item => item.name in SpecialSeriesColorMap)?.length || 0;
    const transformSeries = series.map((item, index) => {
      const colorList = this.panel.options?.time_series?.type === 'bar' ? COLOR_LIST_BAR : COLOR_LIST;
      const color = item.color || (colors || colorList)[Math.max(index - specialSeriesCount, 0) % colorList.length];
      let showSymbol = false;
      const legendItem: ILegendItem = {
        name: String(item.name),
        max: 0,
        min: '',
        avg: 0,
        total: 0,
        color,
        show: true,
        minSource: 0,
        maxSource: 0,
        avgSource: 0,
        totalSource: 0,
        metricField: item.metricField,
        dimensions: item.dimensions,
      };
      // 动态单位转换
      const unitFormatter = !['', 'none', undefined, null].includes(item.unit)
        ? getValueFormat(this.yAxisNeedUnitGetter ? item.unit || '' : '')
        : (v: any) => ({ text: v });
      let hasValueLength = 0;
      const data = item.data.map((seriesItem: any, seriesIndex: number) => {
        if (seriesItem?.length && typeof seriesItem[1] === 'number') {
          // 当前点数据
          const pre = item.data[seriesIndex - 1] as [number, number];
          const next = item.data[seriesIndex + 1] as [number, number];
          const y = +seriesItem[1];
          hasValueLength += 1;
          // 设置图例数据
          legendItem.max = Math.max(+legendItem.max, y);
          legendItem.min = legendItem.min === '' ? y : Math.min(+legendItem.min, y);
          legendItem.total = +legendItem.total + y;
          // 是否为孤立的点
          const hasNoBrother =
            (!pre && !next) || (pre && next && pre.length && next.length && pre[1] === null && next[1] === null);
          if (hasNoBrother) {
            showSymbol = true;
          }
          return {
            symbolSize: hasNoBrother ? 10 : 6,
            value: [seriesItem[0], seriesItem[1]],
            itemStyle: {
              borderWidth: hasNoBrother ? 10 : 6,
              enabled: true,
              shadowBlur: 0,
              opacity: 1,
            },
            customData: item.customData,
          } as any;
        }
        return seriesItem;
      });

      legendItem.avg = +(+legendItem.total / (hasValueLength || 1)).toFixed(2);
      legendItem.total = Number(legendItem.total).toFixed(2);
      // 获取y轴上可设置的最小的精确度
      const precision = this.handleGetMinPrecision(
        item.data.filter((set: any) => typeof set[1] === 'number').map((set: any[]) => set[1]),
        getValueFormat(this.yAxisNeedUnitGetter ? item.unit || '' : ''),
        item.unit
      );
      if (item.name) {
        for (const key in legendItem) {
          if (['min', 'max', 'avg', 'total'].includes(key)) {
            const val = legendItem[key];
            legendItem[`${key}Source`] = val;
            const set: any = unitFormatter(val, item.unit !== 'none' && precision < 1 ? 2 : precision);
            legendItem[key] = set.text + (set.suffix || '');
          }
        }
        legendData.push(legendItem);
      }
      return {
        ...item,
        color,
        type: this.panel.options?.time_series?.type || 'line',
        data,
        showSymbol,
        symbol: 'circle',
        z: 4,
        smooth: 0,
        unitFormatter,
        precision: this.panel.options?.precision || precision || 4,
        lineStyle: {
          width: 2,
        },
      };
    });
    this.legendSorts.sort((a, b) => {
      return timeToDayNum(a.timeShift) - timeToDayNum(b.timeShift);
    });
    const result = [];
    for (const item of this.legendSorts) {
      const lItem = legendData.find(l => l.name === item.name);
      if (lItem) {
        result.push(lItem);
      }
    }
    this.legendData = result;
    return transformSeries;
  }

  // 设置x轴label formatter方法
  public handleSetFormatterFunc(seriesData: any, onlyBeginEnd = false) {
    let formatterFunc = null;
    const [firstItem] = seriesData;
    const lastItem = seriesData[seriesData.length - 1];
    const val = new Date('2010-01-01').getTime();
    const getXVal = (timeVal: any) => {
      if (!timeVal) return timeVal;
      return timeVal[0] > val ? timeVal[0] : timeVal[1];
    };
    const minX = Array.isArray(firstItem) ? getXVal(firstItem) : getXVal(firstItem?.value);
    const maxX = Array.isArray(lastItem) ? getXVal(lastItem) : getXVal(lastItem?.value);
    minX &&
      maxX &&
      // biome-ignore lint/suspicious/noAssignInExpressions: <explanation>
      (formatterFunc = (v: any) => {
        const duration = Math.abs(dayjs.tz(maxX).diff(dayjs.tz(minX), 'second'));
        if (onlyBeginEnd && v > minX && v < maxX) {
          return '';
        }
        if (duration < 1 * 60) {
          return dayjs.tz(v).format('mm:ss');
        }
        if (duration < 60 * 60 * 24 * 1) {
          return dayjs.tz(v).format('HH:mm');
        }
        if (duration < 60 * 60 * 24 * 6) {
          return dayjs.tz(v).format('MM-DD HH:mm');
        }
        if (duration <= 60 * 60 * 24 * 30 * 12) {
          return dayjs.tz(v).format('MM-DD');
        }
        return dayjs.tz(v).format('YYYY-MM-DD');
      });
    return formatterFunc;
  }

  /**
   * @description: 在图表数据没有单位或者单位不一致时则不做单位转换 y轴label的转换用此方法做计数简化
   * @param {number} num
   * @return {*}
   */
  handleYAxisLabelFormatter(num: number): string {
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

  /**
   * @description: 设置精确度
   * @param {number} data
   * @param {ValueFormatter} formatter
   * @param {string} unit
   * @return {*}
   */
  handleGetMinPrecision(data: number[], formatter: ValueFormatter, unit: string) {
    if (!data || data.length === 0) {
      return 0;
    }
    data.sort((a, b) => a - b);
    const len = data.length;
    if (data[0] === data[len - 1]) {
      if (['none', ''].includes(unit) && !data[0].toString().includes('.')) return 0;
      const setList = String(data[0]).split('.');
      return !setList || setList.length < 2 ? 2 : setList[1].length;
    }
    let precision = 0;
    let sampling = [];
    const middle = Math.ceil(len / 2);
    sampling.push(data[0]);
    sampling.push(data[Math.ceil(middle / 2)]);
    sampling.push(data[middle]);
    sampling.push(data[middle + Math.floor((len - middle) / 2)]);
    sampling.push(data[len - 1]);
    sampling = Array.from(new Set(sampling.filter(n => n !== undefined)));
    while (precision < 5) {
      const samp = sampling.reduce((pre, cur) => {
        pre[Number(formatter(cur, precision).text)] = 1;
        return pre;
      }, {});
      if (Object.keys(samp).length >= sampling.length) {
        return precision;
      }
      precision += 1;
    }
    return precision;
  }

  /**
   * 生成可下钻的类型 主机 、实例
   * @param queryConfigs 图表查询数据
   */
  handleDrillDownOption(metrics: IExtendMetricData[]) {
    const dimensions = metrics[0]?.dimensions || [];
    this.drillDownOptions = dimensions.reduce((total, item) => {
      if (item.is_dimension ?? true) {
        total.push({
          id: item.id,
          name: item.name,
        });
      }
      return total;
    }, []);
  }

  dataZoom(startTime: string, endTime: string) {
    if (this.enableSelectionRestoreAll) {
      this.handleChartDataZoom([startTime, endTime]);
    } else {
      this.getPanelData(startTime, endTime);
    }
  }
  handleRestore() {
    if (this.enableSelectionRestoreAll) {
      this.handleRestoreEvent();
    } else {
      this.dataZoom(undefined, undefined);
    }
  }

  /**
   * @description: 图表头部工具栏事件
   * @param {IMenuItem} menuItem
   * @return {*}
   */
  handleMenuToolsSelect(menuItem: IMenuItem) {
    switch (menuItem.id) {
      case 'save': // 保存到仪表盘
        this.handleCollectChart();
        break;
      case 'screenshot': // 保存到本地
        setTimeout(() => {
          this.handleStoreImage(this.curTitle || '测试');
        }, 300);
        break;
      case 'fullscreen': {
        // 大图检索
        const panel = this.panel.toDataRetrieval();
        this.handleFullScreen(panel as any);
        break;
      }
      case 'set': // 转换Y轴大小
        (this.$refs.baseChart as any)?.handleSetYAxisSetScale(!menuItem.checked);
        break;
      case 'explore': {
        const data = this.panel.toDataRetrieval();
        const url = `${location.origin}${location.pathname.toString().replace('fta/', '')}?bizId=${
          this.$store.getters.bizId
        }#/data-retrieval/?targets=${encodeURIComponent(JSON.stringify(data))}&from=${
          this.toolTimeRange[0]
        }&to=${this.toolTimeRange[1]}&timezone=${(this as any).timezone || window.timezone}`;
        window.open(url);
        break;
      }
      case 'strategy': {
        // 新增策略
        const result = this.panel.toStrategy();
        const url = `${location.origin}${location.pathname.toString().replace('fta/', '')}?bizId=${
          this.$store.getters.bizId
        }#/strategy-config/add/?${result?.query_configs?.length ? `data=${JSON.stringify(result)}&` : ''}from=${this.toolTimeRange[0]}&to=${
          this.toolTimeRange[1]
        }&timezone=${(this as any).timezone || window.timezone}`;
        window.open(url);
        break;
      }
      case 'relate-alert': {
        // 关联告警
        const queryString = this.panel.toRelateEvent();
        queryString &&
          window.open(
            location.href.replace(
              location.hash,
              `#/event-center?from=${this.timeRange[0]}&to=${this.timeRange[1]}&timezone=${window.timezone}&${queryString}`
            )
          );
        break;
      }
      default:
        break;
    }
  }

  /**
   * 点击更多菜单的子菜单
   * @param data 菜单数据
   */
  handleSelectChildMenu(data: IChartTitleMenuEvents['onSelectChild']) {
    switch (data.menu.id) {
      case 'more' /** 更多操作 */:
        if (data.child.id === 'screenshot') {
          /** 截图 */
          setTimeout(() => {
            this.handleStoreImage(this.curTitle);
          }, 300);
        } else if (data.child.id === 'export-csv') {
          /** 导出csv */
          this.handleExportCsv();
        }
        break;
      default:
        break;
    }
  }

  /**
   * @description: 下载图表为png图片
   * @param {string} title 图片标题
   * @param {HTMLElement} targetEl 截图目标元素 默认组件$el
   * @param {*} customSave 自定义保存图片
   */
  handleStoreImage(title: string, targetEl?: HTMLElement, customSave = false) {
    const el = targetEl || (this.$el as HTMLElement);
    return toPng(el)
      .then(dataUrl => {
        if (customSave) return dataUrl;
        downFile(dataUrl, `${title}.png`);
      })
      .catch(() => {});
  }

  /**
   * 根据图表接口响应数据下载csv文件
   */
  handleExportCsv() {
    if (this.series?.length) {
      const { tableThArr, tableTdArr } = transformSrcData(this.series);
      const csvString = transformTableDataToCsvStr(tableThArr, tableTdArr);
      downCsvFile(csvString, this.curTitle);
    }
  }

  /**
   * @description: 点击所有指标
   * @param {*}
   * @return {*}
   */
  handleAllMetricClick() {
    const configs = this.panel.toStrategy(null);
    if (configs) {
      this.handleAddStrategy(this.panel, null, {});
      return;
    }
  }

  /**
   * @description: 点击单个指标
   * @param {IExtendMetricData} metric
   * @return {*}
   */
  handleMetricClick(metric: IExtendMetricData) {
    const configs = this.panel.toStrategy(metric);
    if (configs) {
      this.handleAddStrategy(this.panel, metric, {});
      return;
    }
  }
  /** 处理点击左侧响铃图标 跳转策略的逻辑 */ /** 处理点击左侧响铃图标 跳转策略的逻辑 */
  handleAlarmClick(alarmStatus: ITitleAlarm) {
    const metricIds = this.metrics.map(item => item.metric_id);
    switch (alarmStatus.status) {
      case 0:
        this.handleAddStrategy(this.panel, null, this.viewOptions, true);
        break;
      case 1:
        window.open(location.href.replace(location.hash, `#/strategy-config?metricId=${JSON.stringify(metricIds)}`));
        break;
      case 2: {
        const eventTargetStr = alarmStatus.targetStr;
        window.open(
          location.href.replace(
            location.hash,
            `#/event-center?queryString=${metricIds.map(item => `metric : "${item}"`).join(' AND ')}${
              eventTargetStr ? ` AND ${eventTargetStr}` : ''
            }&activeFilterId=NOT_SHIELDED_ABNORMAL&from=${this.timeRange[0]}&to=${this.timeRange[1]}`
          )
        );
        break;
      }
    }
  }
  customTooltips(params: any) {
    const tableData = new Map<string, Record<string, string>>();
    const columns = new Set<string>(['', this.$tc('当前')]);
    const pointTime = dayjs.tz(params[0].axisValue).format('YYYY-MM-DD HH:mm:ss');

    for (const item of params) {
      const { customData } = item.data;
      const curSeries: any = this.options.series[item.seriesIndex];
      const unitFormat = curSeries.unitFormatter || (v => ({ text: v }));
      const precision =
        !['none', ''].some(val => val === curSeries.unit) && +curSeries.precision < 1 ? 2 : +curSeries.precision;
      const valueObj = unitFormat(item.value[1], precision);
      const value = `<span class="series-legend" style="--series-color: ${item.color}"></span> ${valueObj?.text}${valueObj?.suffix || ''}`;

      if (customData) {
        const { metricName, timeShiftName } = customData;
        const name = timeShiftName || this.$t('当前');
        columns.add(name);
        if (!tableData.has(metricName)) {
          tableData.set(metricName, { [name]: value });
          continue;
        }
        tableData.set(metricName, {
          ...tableData.get(metricName),
          [name]: value,
        });
      }
    }
    let html = '<table class="monitor-chart-tooltips-table">\n';
    html += '  <tr>\n';
    for (const column of columns) {
      html += `    <th>${column}</th>\n`;
    }
    html += '  </tr>\n';
    for (const [name, metrics] of tableData) {
      html += '  <tr>\n';
      html += `    <td>${name}</td>\n`;
      for (const column of Array.from(columns).slice(1)) {
        html += `    <td>${metrics[column] || '--'}</td>\n`;
      }
      html += '  </tr>\n';
    }
    html += '</table>';
    return `<div class="monitor-chart-tooltips">
            <p class="tooltips-header">
                ${pointTime}
            </p>
             ${html}
            </div>`;
  }
  render() {
    const showLegend = this.panel.options?.legend?.displayMode !== 'hidden';
    const groupByField = this.panel.externalData?.groupByField;
    const canShowDetail = groupByField !== 'namespace';
    return (
      <div class='k8s-custom-graph'>
        <ChartHeader
          collectIntervalDisplay={this.collectIntervalDisplay}
          customArea={true}
          description={this.panel.description}
          dragging={this.panel.dragging}
          isInstant={this.panel.instant}
          menuList={this.menuList as any}
          metrics={this.metrics || this.panel.externalData?.metrics}
          needMoreMenu={!this.empty}
          showMore={true}
          subtitle={this.panel.subTitle || ''}
          title={this.curTitle}
          onAlarmClick={this.handleAlarmClick}
          onAllMetricClick={this.handleAllMetricClick}
          onMenuClick={this.handleMenuToolsSelect}
          onMetricClick={this.handleMetricClick}
          onSelectChild={this.handleSelectChildMenu}
        />
        {!this.empty ? (
          <div class={`time-series-content ${showLegend ? 'right-legend' : ''}`}>
            <div
              ref='chart'
              class={`chart-instance ${showLegend ? 'is-table-legend' : ''}`}
            >
              {this.initialized && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.height}
                  customTooltips={this.timeOffset?.length > 0 ? this.customTooltips : undefined}
                  groupId={this.panel.dashboardId}
                  hoverAllTooltips={this.hoverAllTooltips}
                  needZrClick={this.panel.options?.need_zr_click_event}
                  options={this.options}
                  showRestore={this.showRestore}
                  onDataZoom={this.dataZoom}
                  onRestore={this.handleRestore}
                />
              )}
            </div>
            {showLegend && (
              <div class={'chart-legend right-legend'}>
                <TableLegend
                  scopedSlots={{
                    name: ({ item }) => (
                      <div
                        class='k8s-legend-name'
                        onMousedown={(e: MouseEvent) => e.stopPropagation()}
                      >
                        <span
                          class={[
                            'metric-name',
                            item.show ? 'is-show' : '',
                            item.show && !this.isSpecialSeries(item.name) && canShowDetail ? 'can-show-detail' : '',
                          ]}
                          v-bk-overflow-tips={{ placement: 'top', offset: '100, 0' }}
                          onClick={() => canShowDetail && this.onShowDetail(item.name)}
                        >
                          {item.name}
                        </span>
                        {!this.isSpecialSeries(item.name) && (
                          <K8sDimensionDrillDown
                            dimension={this.panel.externalData?.groupByField}
                            value={this.panel.externalData?.groupByField}
                            onHandleDrillDown={({ dimension }) => this.onDrillDown(dimension, item.name)}
                          />
                        )}
                      </div>
                    ),
                  }}
                  legendData={this.legendData}
                  preventEvent={true}
                  onSelectLegend={this.handleSelectLegend}
                />
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

export default ofType<IProps>().convert(K8SCustomChart);
