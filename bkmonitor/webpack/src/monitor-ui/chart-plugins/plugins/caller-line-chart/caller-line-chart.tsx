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

import { Component, Emit, Inject, InjectReactive, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { toPng } from 'html-to-image';
import { CancelToken } from 'monitor-api/index';
import { Debounce, deepClone, random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import {
  downCsvFile,
  transformSrcData,
  transformTableDataToCsvStr,
  type IUnifyQuerySeriesItem,
} from 'monitor-pc/pages/view-detail/utils';

import { type ValueFormatter, getValueFormat } from '../../../monitor-echarts/valueFormats';
import ListLegend from '../../components/chart-legend/common-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { COLOR_LIST, COLOR_LIST_BAR, MONITOR_LINE_OPTIONS } from '../../constants';
import { downFile, handleRelateAlert, reviewInterval } from '../../utils';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from '../../utils/axis';
import { replaceRegexWhere } from '../../utils/method';
import { VariablesService } from '../../utils/variable';
import { CommonSimpleChart } from '../common-simple-chart';
import BaseEchart from '../monitor-base-echart';

import type {
  DataQuery,
  IExtendMetricData,
  ILegendItem,
  IMenuChildItem,
  IMenuItem,
  IPanelModel,
  ITimeSeriesItem,
  PanelModel,
  ZrClickEvent,
} from '../../../chart-plugins/typings';
import type { IChartTitleMenuEvents } from '../../components/chart-title/chart-title-menu';
import type { CallOptions, IFilterCondition } from '../apm-service-caller-callee/type';

import './caller-line-chart.scss';

interface IProps {
  panel: PanelModel;
}

function timeShiftFormat(t: string) {
  const regex = /^\d{4}-\d{2}-\d{2}$/;
  if (regex.test(t)) {
    return `${dayjs().diff(dayjs(t), 'day')}d`;
  }
  return t;
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
class CallerLineChart extends CommonSimpleChart {
  // 当前粒度
  @InjectReactive('downSampleRange') readonly downSampleRange: number | string;
  // yAxis是否需要展示单位
  @InjectReactive('yAxisNeedUnit') readonly yAxisNeedUnit: boolean;
  @InjectReactive('callOptions') readonly callOptions: CallOptions;

  // 框选事件范围后需应用到所有图表(包含三个数据 框选方法 是否展示复位  复位方法)
  @Inject({ from: 'enableSelectionRestoreAll', default: false }) readonly enableSelectionRestoreAll: boolean;
  @Inject({ from: 'handleChartDataZoom', default: () => null }) readonly handleChartDataZoom: (value: any) => void;
  @Inject({ from: 'handleRestoreEvent', default: () => null }) readonly handleRestoreEvent: () => void;
  @InjectReactive({ from: 'showRestore', default: false }) readonly showRestoreInject: boolean;

  metrics = [];
  options = {};
  empty = true;
  emptyText = window.i18n.tc('暂无数据');
  cancelTokens = [];

  /** 导出csv数据时候使用 */
  series: IUnifyQuerySeriesItem[];
  minBase = 0;
  // 切换图例时使用
  seriesList = null;
  drillDownOptions: IMenuChildItem[] = [];
  hasSetEvent = false;
  collectIntervalDisplay = '1m';
  panelsSelector = 'timeout_rate';

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

  // 是否允许对比
  get isSupportCompare() {
    return typeof this.panel.options?.is_support_compare !== 'boolean' ? true : this.panel.options.is_support_compare;
  }

  // 是否允许自定groupBy
  get isSupportGroupBy() {
    return !!this.panel.options?.is_support_group_by;
  }

  // title是否需要展示下拉框
  get enablePanelsSelector() {
    return !!this.panel.options?.enable_panels_selector;
  }

  get curSelectPanel() {
    return (this.childPanelsSelectorVariables || []).find(item => this.panelsSelector === item.id);
  }

  get curTitle() {
    return this.enablePanelsSelector ? this.curSelectPanel?.title : this.panel.title;
  }

  get childPanelsSelectorVariables() {
    return this.panel.options?.child_panels_selector_variables || [];
  }
  get menuList() {
    return ['save', 'more', 'fullscreen', 'explore', 'area', 'drill-down', 'relate-alert'];
  }

  @Watch('showRestoreInject')
  handleShowRestoreInject(v: boolean) {
    this.showRestore = v;
  }

  @Watch('callOptions')
  onCallOptionsChange() {
    this.getPanelData();
  }

  handlePanelsSelector() {
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
    this.cancelTokens.forEach(cb => cb?.());
    this.cancelTokens = [];
    if (this.inited) this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    try {
      this.unregisterOberver();
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
      const timeShiftList = [
        '',
        ...(this.isSupportCompare && this.callOptions.time_shift?.length
          ? this.callOptions.time_shift.map(t => t.alias)
          : []),
      ];
      const down_sample_range = this.downSampleRangeComputed(
        'auto',
        [params.start_time, params.end_time],
        'unifyQuery'
      );
      const [v] = down_sample_range.split('s');
      const interval = Math.ceil(+v / 60);
      this.collectIntervalDisplay = `${interval}m`;
      const callOptions = {};
      for (const key in this.callOptions) {
        if (key !== 'time_shift' && (key === 'group_by' ? this.isSupportGroupBy : true)) {
          callOptions[key] = this.callOptions[key];
        }
      }
      let selectPanelParams = {};
      if (this.enablePanelsSelector) {
        selectPanelParams = this.curSelectPanel.variables;
      }
      const variablesService = new VariablesService({
        ...this.viewOptions,
        ...callOptions,
        ...selectPanelParams,
      });
      for (const time_shift of timeShiftList) {
        const noTransformVariables = this.panel?.options?.time_series?.noTransformVariables;
        const dataFormat = data => {
          const paramsResult = data;
          if (!this.callOptions.group_by?.length || !this.isSupportGroupBy) {
            paramsResult.group_by_limit = undefined;
          }
          return paramsResult;
        };
        const list = this.panel.targets.map(item => {
          const newParams = structuredClone({
            ...variablesService.transformVariables(
              dataFormat({ ...item.data }),
              {
                ...this.viewOptions.filters,
                ...(this.viewOptions.filters?.current_target || {}),
                ...this.viewOptions,
                ...this.viewOptions.variables,
                ...(this.callOptions || {}),
                time_shift: timeShiftFormat(time_shift),
                group_by: this.isSupportGroupBy ? this.callOptions.group_by : [],
                interval,
              },
              noTransformVariables
            ),
            ...params,
            down_sample_range,
          });
          if (this.callOptions?.call_filter?.length) {
            const callFilter: IFilterCondition[] = this.callOptions?.call_filter.filter(f => f.key !== 'time');
            for (const item of newParams?.query_configs || []) {
              item.where = [...(item?.where || []), ...replaceRegexWhere(callFilter)];
            }
            for (const item of newParams?.unify_query_param?.query_configs || []) {
              item.where = [...(item?.where || []), ...replaceRegexWhere(callFilter)];
            }
            if (newParams?.group_by_limit?.where) {
              newParams.group_by_limit.where = [...newParams.group_by_limit.where, ...replaceRegexWhere(callFilter)];
            }
          }
          const primaryKey = item?.primary_key;
          const paramsArr = [];
          if (primaryKey) {
            paramsArr.push(primaryKey);
          }
          paramsArr.push({
            ...newParams,
            unify_query_param: {
              ...newParams.unify_query_param,
              down_sample_range,
            },
          });
          return (this as any).$api[item.apiModule]
            [item.apiFunc](...paramsArr, {
              cancelToken: new CancelToken((cb: () => void) => this.cancelTokens.push(cb)),
              needMessage: false,
            })
            .then(res => {
              this.$emit('seriesData', res);
              res.metrics && metrics.push(...res.metrics);
              res.series &&
                series.push(
                  ...res.series.map(set => {
                    if (this.enablePanelsSelector) {
                      item.alias = this.curTitle;
                    }
                    const name = `${this.callOptions.time_shift?.length ? `${this.handleTransformTimeShift(time_shift || 'current')}-` : ''}${
                      this.handleSeriesName(item, set) || set.target
                    }`;
                    this.legendSorts.push({
                      name: name,
                      timeShift: time_shift,
                    });
                    return {
                      ...set,
                      name,
                    };
                  })
                );
              // 用于获取原始query_config
              if (res.query_config) {
                this.panel.setRawQueryConfigs(item, res.query_config);
              }
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
            unit: this.panel.options?.unit || item.unit,
            z: 1,
            traceData: item.trace_data ?? '',
            dimensions: item.dimensions ?? {},
          })) as any
        );
        seriesList = seriesList.map((item: any) => ({
          ...item,
          minBase: this.minBase,
          data: item.data.map((set: any) => {
            if (set?.length) {
              return [set[0], set[1] !== null ? set[1] + this.minBase : null];
            }
            return {
              ...set,
              value: [set.value[0], set.value[1] !== null ? set.value[1] + this.minBase : null],
            };
          }),
        }));
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
        const xInterval = getTimeSeriesXInterval(maxXInterval, this.width, maxSeriesCount);
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
                  : (v: number) => this.handleYxisLabelFormatter(v - this.minBase),
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
        this.inited = true;
        this.empty = false;
        if (!this.hasSetEvent) {
          setTimeout(this.handleSetLegendEvent, 300);
          this.hasSetEvent = true;
        }
        setTimeout(() => {
          this.handleResize();
        }, 100);
      } else {
        this.inited = this.metrics.length > 0;
        this.emptyText = window.i18n.tc('暂无数据');
        this.empty = true;
      }
    } catch (e) {
      console.error(e);
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
    }
    this.cancelTokens = [];
    this.handleLoadingChange(false);
    this.unregisterOberver();
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
      : val.replace('current', window.i18n.tc('当前'));
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
    const tranformSeries = series.map((item, index) => {
      const colorList = this.panel.options?.time_series?.type === 'bar' ? COLOR_LIST_BAR : COLOR_LIST;
      const color = item.color || (colors || colorList)[index % colorList.length];
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
          // profiling 趋势图 其中 Trace 数据需包含span列表
          const traceData = item.traceData ? item.traceData[seriesItem[0]] : undefined;
          return {
            symbolSize: hasNoBrother ? 10 : 6,
            value: [seriesItem[0], seriesItem[1]],
            itemStyle: {
              borderWidth: hasNoBrother ? 10 : 6,
              enabled: true,
              shadowBlur: 0,
              opacity: 1,
            },
            traceData,
          } as any;
        }
        return seriesItem;
      });

      legendItem.avg = +(+legendItem.total / (hasValueLength || 1)).toFixed(2);
      legendItem.total = Number(legendItem.total).toFixed(2);
      // 获取y轴上可设置的最小的精确度
      let precision = this.handleGetMinPrecision(
        item.data.filter((set: any) => typeof set[1] === 'number').map((set: any[]) => set[1]),
        getValueFormat(this.yAxisNeedUnitGetter ? item.unit || '' : ''),
        item.unit
      );
      precision = precision > 2 ? 2 : precision;
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
        precision,
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
    return tranformSeries;
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

  /**
   * @description: 设置精确度
   * @param {number} data
   * @param {ValueFormatter} formattter
   * @param {string} unit
   * @return {*}
   */
  handleGetMinPrecision(data: number[], formattter: ValueFormatter, unit: string) {
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
        pre[Number(formattter(cur, precision).text)] = 1;
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
  @Emit('zrClick')
  handleZrClick(params: ZrClickEvent) {
    return params;
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
    const callOptions = {};
    for (const key in this.callOptions) {
      if (key !== 'time_shift' && (key === 'group_by' ? this.isSupportGroupBy : true)) {
        callOptions[key] = this.callOptions[key];
      }
    }
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
        const copyPanel = this.getCopyPanel();
        this.handleFullScreen(copyPanel as any);
        break;
      }

      case 'area': // 面积图
        (this.$refs.baseChart as any)?.handleTransformArea(menuItem.checked);
        break;
      case 'set': // 转换Y轴大小
        (this.$refs.baseChart as any)?.handleSetYAxisSetScale(!menuItem.checked);
        break;
      case 'explore': {
        // 跳转数据检索
        const copyPanel = this.getCopyPanel();
        console.log('copyPanel', copyPanel);
        this.handleExplore(copyPanel as any, {});
        break;
      }
      case 'strategy': {
        // 新增策略
        const copyPanel = this.getCopyPanel();
        this.handleAddStrategy(copyPanel as any, null, {}, true);
        break;
      }
      case 'relate-alert': {
        // 大图检索
        const copyPanel = this.getCopyPanel();
        handleRelateAlert(copyPanel as any, this.timeRange);
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

  queryConfigsSetCallOptions(targetData) {
    if (!this.callOptions.group_by?.length || !this.isSupportGroupBy) {
      targetData.group_by_limit = undefined;
    } else {
    }
    if (this.callOptions?.call_filter?.length) {
      const callFilter = this.callOptions?.call_filter.filter(f => f.key !== 'time');
      for (const item of targetData?.query_configs || []) {
        item.where = [...(item?.where || []), ...callFilter];
      }
      for (const item of targetData?.unify_query_param?.query_configs || []) {
        item.where = [...(item?.where || []), ...callFilter];
      }
      if (targetData?.group_by_limit?.where) {
        targetData.group_by_limit.where = [...targetData.group_by_limit.where, ...callFilter];
      }
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
      console.log('this.panel', this.panel);
      this.handleAddStrategy(this.panel, null, {});
      return;
    }
    const copyPanel = this.getCopyPanel();
    console.log('copyPanel-all', copyPanel);
    this.handleAddStrategy(copyPanel as any, null, {}, true);
  }

  getCopyPanel() {
    try {
      const callOptions = {};
      for (const key in this.callOptions) {
        if (key !== 'time_shift' && (key === 'group_by' ? this.isSupportGroupBy : true)) {
          callOptions[key] = this.callOptions[key];
        }
      }
      let copyPanel: IPanelModel = JSON.parse(JSON.stringify(this.panel));
      copyPanel.dashboardId = random(8);
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      let selectPanelParams = {};
      if (this.enablePanelsSelector) {
        selectPanelParams = this.curSelectPanel.variables;
      }
      const variablesService = new VariablesService({
        ...this.viewOptions.filters,
        ...(this.viewOptions.filters?.current_target || {}),
        ...this.viewOptions,
        ...this.viewOptions.variables,
        ...callOptions,
        group_by: this.isSupportGroupBy ? this.callOptions.group_by : [],
        interval: reviewInterval(
          this.viewOptions.interval,
          dayjs.tz(endTime).unix() - dayjs.tz(startTime).unix(),
          this.panel.collect_interval
        ),
        ...selectPanelParams,
      });
      copyPanel = variablesService.transformVariables(copyPanel);
      for (const t of copyPanel.targets) {
        for (const q of t?.data?.query_configs || []) {
          q.functions = (q.functions || []).filter(f => f.id !== 'time_shift');
        }
        this.queryConfigsSetCallOptions(t?.data);
      }
      if (this.enablePanelsSelector) {
        copyPanel.title = this.curTitle;
        copyPanel.targets.map(item => (item.alias = this.curTitle));
      }
      return copyPanel;
    } catch (error) {
      console.log(error);
      return JSON.parse(JSON.stringify(this.panel));
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
    const copyPanel: PanelModel = this.getCopyPanel();
    this.handleAddStrategy(copyPanel, metric, {});
  }

  render() {
    return (
      <div class='apm-caller-line-chart'>
        <ChartHeader
          collectIntervalDisplay={this.collectIntervalDisplay}
          customArea={true}
          descrition={this.panel.descrition}
          draging={this.panel.draging}
          isInstant={this.panel.instant}
          menuList={this.menuList as any}
          metrics={this.metrics}
          needMoreMenu={true}
          showMore={true}
          subtitle={this.panel.subTitle || ''}
          title={this.curTitle}
          onAllMetricClick={this.handleAllMetricClick}
          onMenuClick={this.handleMenuToolsSelect}
          onMetricClick={this.handleMetricClick}
          onSelectChild={this.handleSelectChildMenu}
        >
          <div slot='title'>
            {this.enablePanelsSelector ? (
              <div>
                <bk-select
                  class='enable-select'
                  v-model={this.panelsSelector}
                  behavior='simplicity'
                  clearable={false}
                  size='small'
                  onChange={this.handlePanelsSelector}
                >
                  {(this.childPanelsSelectorVariables || []).map(option => (
                    <bk-option
                      id={option.id}
                      key={option.id}
                      name={option.title}
                    />
                  ))}
                </bk-select>
              </div>
            ) : (
              <span>{this.panel.title}</span>
            )}
          </div>
        </ChartHeader>
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
                  groupId={this.panel.dashboardId}
                  hoverAllTooltips={this.hoverAllTooltips}
                  needZrClick={this.panel?.options?.need_zr_click_event}
                  options={this.options}
                  showRestore={this.showRestore}
                  onDataZoom={this.dataZoom}
                  onRestore={this.handleRestore}
                  onZrClick={this.handleZrClick}
                />
              )}
            </div>
            <div class={'chart-legend'}>
              <ListLegend
                legendData={this.legendData || []}
                onSelectLegend={this.handleSelectLegend}
              />
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
  IProps,
  {
    onZrClick?: (event: ZrClickEvent) => void;
  }
>().convert(CallerLineChart);
