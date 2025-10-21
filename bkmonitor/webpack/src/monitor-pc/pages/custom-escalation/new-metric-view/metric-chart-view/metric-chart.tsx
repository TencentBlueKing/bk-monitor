/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Inject, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { toPng } from 'html-to-image';
import { CancelToken } from 'monitor-api/cancel';
import { graphUnifyQuery } from 'monitor-api/modules/grafana';
import { Debounce, deepClone, random } from 'monitor-common/utils/utils';
import { generateFormatterFunc, handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import {
  type IUnifyQuerySeriesItem,
  downCsvFile,
  transformSrcData,
  transformTableDataToCsvStr,
} from 'monitor-pc/pages/view-detail/utils';
import ListLegend from 'monitor-ui/chart-plugins/components/chart-legend/common-legend';
import ChartHeader from 'monitor-ui/chart-plugins/components/chart-title/chart-title';
import { COLOR_LIST_METRIC, MONITOR_LINE_OPTIONS } from 'monitor-ui/chart-plugins/constants';
import StatusTab from 'monitor-ui/chart-plugins/plugins/apm-custom-graph/status-tab';
import CommonSimpleChart from 'monitor-ui/chart-plugins/plugins/common-simple-chart';
import BaseEchart from 'monitor-ui/chart-plugins/plugins/monitor-base-echart';
import { downFile, handleRelateAlert } from 'monitor-ui/chart-plugins/utils';
import { createMenuList } from 'monitor-ui/chart-plugins/utils';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from 'monitor-ui/chart-plugins/utils/axis';
import { VariablesService } from 'monitor-ui/chart-plugins/utils/variable';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import {
  convertTimestamp,
  handleGetMinPrecision,
  handleSetFormatterFunc,
  handleYAxisLabelFormatter,
  timeToDayNum,
} from './utils';
import customEscalationViewStore from '@store/modules/custom-escalation-view';

import type { IMetricAnalysisConfig } from '../type';
import type { IChartTitleMenuEvents } from 'monitor-ui/chart-plugins/components/chart-title/chart-title-menu';
import type {
  DataQuery,
  IExtendMetricData,
  ILegendItem,
  ITimeSeriesItem,
  PanelModel,
} from 'monitor-ui/chart-plugins/typings';

import './metric-chart.scss';
const APM_CUSTOM_METHODS = ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN'];

// 最小展示tooltips高度
const MIN_SHOW_TOOLTIPS_HEIGHT = 200;

interface INewMetricChartEvents {
  onDrillDown?: () => void;
  onLegendData?: (list: ILegendItem[], loading: boolean) => void;
  onMenuClick?: () => void;
}
interface INewMetricChartProps {
  chartHeight?: number;
  isShowLegend?: boolean;
  isToolIconShow?: boolean;
  panel?: PanelModel;
}
/** 图表 - 曲线图 */
@Component
class NewMetricChart extends CommonSimpleChart {
  @Prop({ default: 300 }) chartHeight: number;
  @Prop({ default: true }) isToolIconShow: boolean;
  /** 是否展示图例 */
  @Prop({ default: false }) isShowLegend: boolean;
  /** 当前汇聚方法 */
  @Prop({ default: '' }) currentMethod: string;
  /** groupId */
  @Prop({ default: '' }) groupId: string;
  /** 是否展示图例 */
  @Prop({ default: false }) isNeedMenu: boolean;
  /** 是否需要鼠标hover到x轴的交互*/
  @Prop({ default: false }) isNeedUpdateAxisPointer: boolean;

  // yAxis是否需要展示单位
  @InjectReactive('yAxisNeedUnit') readonly yAxisNeedUnit: boolean;
  @InjectReactive('filterOption') readonly filterOption!: IMetricAnalysisConfig;
  // 框选事件范围后需应用到所有图表(包含三个数据 框选方法 是否展示复位  复位方法)
  @Inject({ from: 'enableSelectionRestoreAll', default: false }) readonly enableSelectionRestoreAll: boolean;
  @Inject({ from: 'handleChartDataZoom', default: () => null }) readonly handleChartDataZoom: (value: any) => void;
  @Inject({ from: 'handleRestoreEvent', default: () => null }) readonly handleRestoreEvent: () => void;
  @InjectReactive({ from: 'showRestore', default: false }) readonly showRestoreInject: boolean;
  @InjectReactive({ from: 'containerScrollTop', default: 0 }) readonly containerScrollTop: number;
  @Ref('baseChart') readonly baseChart: HTMLElement;
  @Ref('chart') readonly chart: HTMLElement;
  methodList = APM_CUSTOM_METHODS.map(method => ({
    id: method,
    name: method,
  }));
  contextmenuInfo = {
    options: [{ id: 'drill', name: window.i18n.tc('维度下钻') }],
    sliceStartTime: 0, // 当前切片起始时间
    sliceEndTime: 0,
  };
  customScopedVars: Record<string, any> = {};
  width = 300;
  initialized = false;
  metrics = [];
  collectIntervalDisplay = '1m';
  cancelTokens = [];
  options = {
    xAxis: {
      type: 'time',
      axisTick: {
        show: false,
      },
      boundaryGap: false,
      axisLabel: {
        fontSize: 12,
        color: '#979BA5',
        showMinLabel: false,
        showMaxLabel: false,
        align: 'left',
      },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: {
        show: true,
        lineStyle: {
          color: '#F0F1F5',
          type: 'solid',
        },
      },
    },
  };
  empty = false;
  emptyText = window.i18n.tc('暂无数据');
  // x轴格式化函数
  formatterFunc = null;
  method = '';
  loading = false;
  // 是否展示复位按钮
  showRestore = false;
  /** 导出csv数据时候使用 */
  series: IUnifyQuerySeriesItem[];
  // 图例排序
  legendSorts: { name: string; target: string; timeShift: string; tipsName: string }[] = [];
  // 切换图例时使用
  seriesList = null;
  minBase = 0;
  enableContextmenu = true;
  // 自动粒度降采样
  downSampleRange = 'auto';
  get yAxisNeedUnitGetter() {
    return this.yAxisNeedUnit ?? true;
  }

  /** 指标列表 */
  get currentSelectedMetricList() {
    return customEscalationViewStore.currentSelectedMetricList;
  }

  get viewWidth() {
    const viewColumn = Number(this.$route.query?.viewColumn) || 2;
    return this.width / (viewColumn + 1) - 40;
  }

  /** 操作的icon列表 */
  get handleIconList() {
    return [
      { id: 'fullscreen', text: window.i18n.tc('查看大图'), icon: 'icon-mc-full-screen' },
      { id: 'drillDown', text: window.i18n.tc('维度下钻'), icon: 'icon-dimension-line' },
    ];
  }
  // /** 更多里的操作列表 */
  get menuList() {
    return ['explore', 'drill-down', 'relate-alert', 'more', 'save'];
  }
  /** hover展示多个tooltips */
  get hoverAllTooltips() {
    // 根据图表是否在可视区域内来判断是否展示多个tooltips
    const { top = MIN_SHOW_TOOLTIPS_HEIGHT } = this.$refs.baseChart?.$el?.getBoundingClientRect() || {};
    return (
      (this.panel.options?.time_series?.hoverAllTooltips && top >= this.containerScrollTop) ||
      top >= MIN_SHOW_TOOLTIPS_HEIGHT
    );
  }
  /** 拉伸的时候图表重新渲染 */
  @Watch('chartHeight')
  handleHeightChange() {
    this.handleResize();
  }
  @Watch('panel')
  handlePanelChange() {
    this.getPanelData();
  }
  @Watch('showRestoreInject')
  handleShowRestoreInject(v: boolean) {
    this.showRestore = v;
  }
  /** 重新拉取数据 */
  @Watch('currentMethod', { immediate: true })
  handleCurrentMethod() {
    this.method = this.currentMethod;
  }
  /** 切换计算的Method */
  handleMethodChange(method: (typeof APM_CUSTOM_METHODS)[number]) {
    this.method = method;
    this.customScopedVars = {
      method,
    };
    this.getPanelData();
    this.$emit('methodChange', method);
  }
  removeTrailingZeros(num: number | string) {
    if (num && num !== '0') {
      return num
        .toString()
        .replace(/(\.\d*?)0+$/, '$1')
        .replace(/\.$/, '');
    }
    return num;
  }

  /**
   * @description: 转换时序数据 并设置图例
   * @param {ITimeSeriesItem} series 图表时序数据
   * @return {*}
   */
  handleTransformSeries(series: ITimeSeriesItem[], colors?: string[]) {
    const legendData: ILegendItem[] = [];
    const transformSeries = series.map((item, index) => {
      const colorList = COLOR_LIST_METRIC;
      const color = item.color || (colors || colorList)[index % colorList.length];
      let showSymbol = false;
      const legendItem: ILegendItem = {
        name: String(item.name),
        max: 0,
        min: '',
        avg: 0,
        total: 0,
        color,
        latest: 0,
        show: true,
        minSource: 0,
        maxSource: 0,
        avgSource: 0,
        totalSource: 0,
        metricField: item.metricField,
        dimensions: item.dimensions,
        timeOffset: item.timeOffset,
      };
      // 动态单位转换
      const unitFormatter = !['', 'none', undefined, null].includes(item.unit)
        ? getValueFormat(this.yAxisNeedUnitGetter ? item.unit || '' : '')
        : (v: any) => ({ text: v });
      let hasValueLength = 0;
      let latestVal = 0;
      let latestInd = 0;
      const data = (item.data || []).map((seriesItem: any, seriesIndex: number) => {
        if (seriesItem?.length && typeof seriesItem[1] === 'number') {
          // 当前点数据
          const pre = item.data[seriesIndex - 1] as [number, number];
          const next = item.data[seriesIndex + 1] as [number, number];
          const y = +seriesItem[1];
          const x = +seriesItem[0];
          hasValueLength += 1;
          /** 最新值 */
          latestVal = Math.max(+latestVal, x);
          latestInd = seriesItem[0] === latestVal ? seriesIndex : -1;
          // 设置图例数据
          legendItem.max = Math.max(+legendItem.max, y);
          legendItem.min = legendItem.min === '' ? y : Math.min(+legendItem.min, y);
          legendItem.total = +legendItem.total + y;
          if (seriesItem[1] === legendItem.max) {
            legendItem.maxTime = seriesItem[0];
          }
          if (seriesItem[1] === legendItem.min) {
            legendItem.minTime = seriesItem[0];
          }
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
      if (item.data.length > 0) {
        legendItem.latest = item.data[latestInd][1];
      }
      legendItem.latestTime = latestVal;

      // 获取y轴上可设置的最小的精确度
      const precision = handleGetMinPrecision(
        item.data.filter((set: any) => typeof set[1] === 'number').map((set: any[]) => set[1]),
        getValueFormat(this.yAxisNeedUnitGetter ? item.unit || '' : ''),
        item.unit
      );
      if (item.name) {
        for (const key in legendItem) {
          if (['min', 'max', 'avg', 'total', 'latest'].includes(key)) {
            const val = legendItem[key];
            legendItem[`${key}Source`] = val;
            const set: any = unitFormatter(val, item.unit !== 'none' && precision < 1 ? 2 : 2);
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
        precision: this.panel.options?.precision || 2,
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
        result.push({ ...lItem, ...{ tipsName: item.tipsName, target: item.target } });
      }
    }
    this.legendData = result;
    return transformSeries;
  }

  convertJsonObject(obj, name: string) {
    const dimensions = this.currentSelectedMetricList.find(ele => ele.metric_name === name)?.dimensions;
    const keys = Object.keys(obj);
    const parts = [];
    for (const key of keys) {
      const info = dimensions.find(item => item.name === key);
      parts.push(`${info.alias || info.name}=${obj[key]}`);
    }
    const separator = '|';
    return parts.join(separator);
  }
  formatTimeStr(timeStr) {
    if (timeStr === 'current') {
      return this.$t('当前');
    }
    const matches = timeStr.match(/(\d+)([dh])/);
    const number = Number.parseInt(matches[1], 10);
    const unit = matches[2];
    if (unit === 'd') {
      return `${number}天前`;
    }
    if (unit === 'h') {
      return `${number}小时前`;
    }
  }
  handleSeriesName(item: DataQuery, set) {
    const { dimensions = {}, dimensions_translation = {}, time_offset } = set;
    const { metric = {} } = item;
    const timeOffset = time_offset ? `${this.formatTimeStr(time_offset)}` : '';
    const output = this.convertJsonObject({ ...dimensions, ...dimensions_translation }, metric.name);
    const outputStr = output ? `${output}` : '';
    if (!timeOffset && !outputStr) {
      return metric.alias || metric.name;
    }
    return `${timeOffset}${time_offset && output ? '-' : ''}${outputStr}`;
  }

  handleTime() {
    const [startTime, endTime] = this.timeRange;
    if (!startTime || !endTime) return;
    if (typeof startTime === 'string') {
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      return [startTime, endTime];
    }
    const startTimeStr = convertTimestamp(startTime);
    const endTimeStr = convertTimestamp(endTime);
    return [startTimeStr, endTimeStr];
  }
  /* 粒度计算 */
  downSampleRangeComputed(downSampleRange: string, timeRange: number[]) {
    if (downSampleRange === 'auto') {
      let width = 1;
      if (this.$refs.chart) {
        width = this.$refs.chart.clientWidth;
      } else {
        width = this.$el.clientWidth - (this.panel?.options?.legend?.placement === 'right' ? 320 : 0);
      }
      const size = ((timeRange[1] - timeRange[0]) / width) * 1.5;
      return size > 0 ? `${Math.ceil(size)}s` : undefined;
    }
    return downSampleRange;
  }
  /**
   * @description: 获取图表数据
   */
  @Debounce(300)
  async getPanelData(start_time?: string, end_time?: string) {
    this.legendData = [];
    this.legendSorts = [];
    this.initialized = false;
    this.cancelTokens.forEach(cb => cb?.());
    this.cancelTokens = [];
    if (!this.isInViewPort()) {
      if (this.intersectionObserver) {
        this.unregisterObserver();
      }
      this.registerObserver();
      return;
    }
    this.formatterFunc = generateFormatterFunc(this.timeRange);
    if (this.initialized) this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    this.loading = true;
    try {
      this.unregisterObserver();
      const [startTime, endTime] = this.handleTime();
      const series = [];
      const metrics = [];
      const params = {
        start_time: start_time ? dayjs(start_time).unix() : startTime,
        end_time: end_time ? dayjs(end_time).unix() : endTime,
      };
      const promiseList = [];
      const variablesService = new VariablesService({
        ...this.viewOptions,
        ...this.customScopedVars,
      });

      const list = this.panel.targets.map(item => {
        (item?.query_configs || []).map(config => {
          config.metrics.map(metric => {
            metric.method = this.method || metric.method;
          });
        });
        const newParams = {
          ...variablesService.transformVariables(item, {
            ...this.customScopedVars,
          }),
          ...params,
        };
        const primaryKey = item?.primary_key;
        const paramsArr = [];
        if (primaryKey) {
          paramsArr.push(primaryKey);
        }

        paramsArr.push({
          ...newParams,
          unify_query_param: {
            ...newParams.unify_query_param,
          },
          down_sample_range: this.downSampleRangeComputed(this.downSampleRange, [startTime, endTime]),
        });
        return graphUnifyQuery(...paramsArr, {
          cancelToken: new CancelToken((cb: () => void) => this.cancelTokens.push(cb)),
          needMessage: false,
        })
          .then(res => {
            this.$emit('seriesData', res);
            res.metrics && metrics.push(...res.metrics);
            res.series &&
              series.push(
                ...res.series.map(set => {
                  const name = this.handleSeriesName(item, set) || set.target;
                  const tipsName = this.handleSeriesName(item, set) || set.target;
                  this.legendSorts.push({
                    name,
                    tipsName,
                    timeShift: set.time_offset || '',
                    target: set.target,
                  });
                  return {
                    ...set,
                    name,
                    tipsName,
                  };
                })
              );
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
      await Promise.all(promiseList).catch(() => false);
      this.metrics = metrics || [];
      const length = series.length;
      const dataLen = series.filter(item => item.datapoints?.length).length;
      if (length && dataLen) {
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
            timeOffset: item.time_offset ?? '',
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
        const formatterFunc = handleSetFormatterFunc(formatData);

        const chartBaseOptions = MONITOR_LINE_OPTIONS;
        const echartOptions = deepmerge(
          deepClone(chartBaseOptions),
          this.panel.options?.time_series?.echart_option || {},
          { arrayMerge: (_, newArr) => newArr }
        );
        const width = this.$el?.getBoundingClientRect?.()?.width;
        const xInterval = getTimeSeriesXInterval(maxXInterval, width || this.width, maxSeriesCount);
        this.options = Object.freeze(
          deepmerge(echartOptions, {
            animation: hasShowSymbol,
            color: COLOR_LIST_METRIC,
            animationThreshold: 1,
            yAxis: {
              axisLabel: {
                formatter: seriesList.every((item: any) => item.unit === seriesList[0].unit)
                  ? (v: any) => {
                      if (seriesList[0].unit !== 'none') {
                        const obj = getValueFormat(seriesList[0].unit)(v, seriesList[0].precision);
                        return this.removeTrailingZeros(obj.text) + (this.yAxisNeedUnitGetter ? obj.suffix : '');
                      }
                      return v;
                    }
                  : (v: number) => handleYAxisLabelFormatter(v - this.minBase),
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
                align: 'center',
              },
              ...xInterval,
              splitNumber: 5,
            },
            series: seriesList,
            tooltip: {
              extraCssText: 'max-width: 50%',
              order: 'valueDesc',
            },
            customData: {
              // customData 自定义的一些配置 用户后面echarts实例化后的配置
              maxXInterval,
              maxSeriesCount,
            },
          })
        );
        this.initialized = true;
        this.empty = false;
        setTimeout(() => {
          this.handleResize();
        }, 100);
      } else {
        this.initialized = true;
        this.emptyText = window.i18n.tc('暂无数据');
        this.empty = true;
      }
    } catch {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
    } finally {
      this.cancelTokens = [];
      this.loading = false;
      this.$emit('legendData', this.legendData || [], this.loading);
    }
    this.handleLoadingChange(false);
  }

  /**
   * @description: 下载图表为png图片
   * @param {string} title 图片标题
   * @param {HTMLElement} targetEl 截图目标元素 默认组件$el
   * @param {*} customSave 自定义保存图片
   */
  handleStoreImage(title: string, targetEl?: HTMLElement, customSave = false) {
    /** 在不显示图例展示表格的情况下 */
    if (!this.isShowLegend) {
      this.$emit('downImage', title, targetEl, customSave);
      return;
    }
    const el = targetEl || (this.$el as HTMLElement);
    return toPng(el)
      .then(dataUrl => {
        if (customSave) return dataUrl;
        downFile(dataUrl, `${title}.png`);
      })
      .catch(() => {});
  }
  dataZoom(startTime: string, endTime: string) {
    this.showRestore = !!startTime;
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
  // 生成随机的dashboardId
  generateRandomDashboardId() {
    return Math.random().toString(36).substr(2, 9);
  }
  getCopyPanel() {
    const [startTime, endTime] = this.handleTime();
    let copyPanel = JSON.parse(JSON.stringify(this.panel));
    const targets = copyPanel.targets.map(item => ({
      ...item,
      api: 'grafana.graphUnifyQuery',
      data: {
        expression: item.expression,
        query_configs: item.query_configs.map(config => ({
          ...config,
          interval: this.viewOptions?.interval || 'auto',
        })),
      },
    }));

    copyPanel = {
      ...copyPanel,
      ...{
        dashboardId: this.generateRandomDashboardId(),
        subTitle: this.panel.sub_title,
        type: 'graph',
        groupId: null,
        id: this.panel.sub_title,
        end_time: endTime,
        start_time: startTime,
        targets,
      },
    };
    return copyPanel;
  }
  /** 工具栏各个icon的操作 */
  handleIconClick(menuItem: { icon: string; id: string; text: string }, ind: number) {
    switch (menuItem.id) {
      /** 维度下钻 */
      case 'drillDown':
        this.$emit('drillDown', this.panel, ind);
        break;
      case 'save': // 保存到仪表盘
        this.handleCollectChart();
        break;
      case 'fullscreen': {
        // 大图
        const copyPanel = this.getCopyPanel();
        this.handleFullScreen(copyPanel as any);
        break;
      }
      case 'explore': {
        // 跳转数据检索
        const copyPanel = this.getCopyPanel();
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
        // 关键告警
        const copyPanel = this.getCopyPanel();
        handleRelateAlert(copyPanel as any, this.timeRange);
        break;
      }
      default:
        break;
    }
  }
  /**
   * 根据图表接口响应数据下载csv文件
   */
  handleExportCsv() {
    if (this.series?.length) {
      const { tableThArr, tableTdArr } = transformSrcData(this.series);
      const csvString = transformTableDataToCsvStr(tableThArr, tableTdArr);
      downCsvFile(csvString, this.panel.title);
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
            this.handleStoreImage(this.panel.title || '测试');
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
   * @description: 点击所有指标
   * @param {*}
   * @return {*}
   */
  handleAllMetricClick() {
    const copyPanel = this.getCopyPanel();
    this.handleAddStrategy(copyPanel as any, null, {}, true);
  }
  /**
   * @description: 点击单个指标
   * @param {IExtendMetricData} metric
   * @return {*}
   */
  handleMetricClick(metric: IExtendMetricData) {
    const copyPanel: PanelModel = this.getCopyPanel();
    this.handleAddStrategy(copyPanel, metric, {});
  }
  /** 获取当前指标的维度列表长度 */
  getDimensionsLen(name: string) {
    const dimensions = this.currentSelectedMetricList.find(ele => ele.metric_name === name)?.dimensions || [];
    return dimensions.length || 0;
  }

  renderToolIconList() {
    return this.handleIconList.map(item => {
      if (this.panel?.targets?.length > 1 && item.id === 'drillDown') {
        return (
          <bk-dropdown-menu
            align={'right'}
            trigger={'click'}
          >
            <div slot='dropdown-trigger'>
              <i
                key={item.id}
                class={`icon-monitor ${item.icon} menu-list-icon`}
                v-bk-tooltips={{
                  content: this.$t(item.text),
                  delay: 200,
                }}
              />
            </div>
            <ul
              class='metric-dropdown-list-tool'
              slot='dropdown-content'
            >
              {this.panel.targets.map((target, ind) => {
                const dimensionsName = target?.metric?.name;
                const dimensionsLen = this.getDimensionsLen(dimensionsName);
                return (
                  <li
                    key={dimensionsName}
                    class={['metric-dropdown-item-tool', { disabled: dimensionsLen === 0 }]}
                    v-bk-tooltips={{
                      content: this.$t('无维度数据'),
                      disabled: dimensionsLen > 0,
                    }}
                    onClick={() => dimensionsLen > 0 && this.handleIconClick(item, ind)}
                  >
                    <span>{dimensionsName}</span>
                  </li>
                );
              })}
            </ul>
          </bk-dropdown-menu>
        );
      }
      const dimensionsLen = this.getDimensionsLen(this.panel?.targets[0]?.metric?.name || '--');
      /** 判断是否有维度可以下钻 */
      const isDrillDisabled = item.id === 'drillDown' && dimensionsLen === 0;
      return (
        <i
          key={item.id}
          class={`icon-monitor ${item.icon} menu-list-icon ${isDrillDisabled ? 'disabled' : ''}`}
          v-bk-tooltips={{
            content: isDrillDisabled ? this.$t('无维度数据可下钻') : this.$t(item.text),
            delay: 200,
          }}
          onClick={() => !isDrillDisabled && this.handleIconClick(item, 0)}
        />
      );
    });
  }
  /* 整个图的右键菜单 */
  handleChartContextmenu(event: MouseEvent) {
    if (this.isNeedMenu) {
      event.preventDefault();
      if (this.enableContextmenu) {
        const { pageX, pageY } = event;
        const instance = (this.$refs.baseChart as any).instance;
        createMenuList(
          this.contextmenuInfo.options,
          { x: pageX, y: pageY },
          (id: string) => {
            this.$emit('contextmenuClick', id, instance);
          },
          instance,
          'drill-down-chart-tab'
        );
      }
    }
  }
  /** x轴hover的相关交互 */
  handleUpdateAxisPointer(params) {
    if (this.isNeedUpdateAxisPointer) {
      const { axesInfo } = params;
      if (axesInfo.length === 0) {
        return;
      }
      this.$emit('zrMouseover', { value: axesInfo[0].value });
    }
  }
  render() {
    return (
      <div class='new-metric-chart'>
        <ChartHeader
          collectIntervalDisplay={this.collectIntervalDisplay}
          customArea={true}
          isHoverShow={true}
          // isInstant={this.panel.instant}
          menuList={this.menuList as any}
          metrics={this.metrics}
          needMoreMenu={true}
          showMore={true}
          subtitle={this.panel?.sub_title || ''}
          title={this.panel.title}
          onAllMetricClick={this.handleAllMetricClick}
          onMenuClick={this.handleIconClick}
          onMetricClick={this.handleMetricClick}
          onSelectChild={this.handleSelectChildMenu}
        >
          <span class='status-tab-view'>
            <StatusTab
              maxWidth={this.viewWidth}
              statusList={this.methodList}
              value={this.method}
              onChange={this.handleMethodChange}
            />
          </span>
          {this.isToolIconShow && (
            <span
              class='icon-tool-list'
              slot='iconList'
            >
              {this.renderToolIconList()}
            </span>
          )}
        </ChartHeader>
        {!this.empty ? (
          <div
            class='new-metric-chart-content'
            onContextmenu={this.handleChartContextmenu}
          >
            <div
              ref='chart'
              class='chart-instance'
            >
              {this.initialized ? (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.chartHeight}
                  groupId={this.panel.groupId}
                  hoverAllTooltips={this.hoverAllTooltips}
                  isContextmenuPreventDefault={true}
                  needTooltips={true}
                  options={this.options}
                  showRestore={this.showRestore}
                  sortTooltipsValue={false}
                  onDataZoom={this.dataZoom}
                  onRestore={this.handleRestore}
                  onUpdateAxisPointer={this.handleUpdateAxisPointer}
                />
              ) : (
                <div class='skeleton-loading-chart'>
                  <div class='skeleton-element'>
                    <i class='icon-monitor icon-mc-line skeleton-icon' />
                  </div>
                </div>
              )}
            </div>
            {this.isShowLegend && this.legendData.length > 0 && (
              <div class={'metric-chart-legend'}>
                <ListLegend
                  legendData={this.legendData || []}
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
export default ofType<INewMetricChartProps, INewMetricChartEvents>().convert(NewMetricChart);
