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
import { Component, Emit, Inject, InjectReactive, Mixins, Prop, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { CancelToken } from 'monitor-api/cancel';
import { deepClone, random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import {
  type IUnifyQuerySeriesItem,
  downCsvFile,
  transformSrcData,
  transformTableDataToCsvStr,
} from 'monitor-pc/pages/view-detail/utils';
import { handleTimeRange } from 'monitor-pc/utils';

import { type ValueFormatter, getValueFormat } from '../../../monitor-echarts/valueFormats';
import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { COLOR_LIST, COLOR_LIST_BAR, MONITOR_LINE_OPTIONS } from '../../constants';
import {
  ChartLoadingMixin,
  ErrorMsgMixins,
  IntersectionMixin,
  LegendMixin,
  ResizeMixin,
  ToolsMixin,
} from '../../mixins';
import { isShadowEqual, reviewInterval } from '../../utils';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from '../../utils/axis';
import { handleRelateAlert } from '../../utils/menu';
import { VariablesService } from '../../utils/variable';
import BaseEchart from '../monitor-base-echart';

import type { IChartTitleMenuEvents } from '../../components/chart-title/chart-title-menu';
import type {
  ChartTitleMenuType,
  DataQuery,
  ICommonCharts,
  IExtendMetricData,
  ILegendItem,
  IMenuChildItem,
  IMenuItem,
  IPanelModel,
  IPlotBand,
  ITimeSeriesItem,
  ITitleAlarm,
  IViewOptions,
  LegendActionType,
  MonitorEchartOptions,
  PanelModel,
  ZrClickEvent,
} from '../../typings';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './time-series.scss';

interface ITimeSeriesProps {
  panel: PanelModel;
  showHeaderMoreTool?: boolean;
  showChartHeader?: boolean;
  customTimeRange?: [string, string];
  customMenuList?: ChartTitleMenuType[];
  needSetEvent?: boolean;
  isSingleChart?: boolean;
}
interface ITimeSeriesEvent {
  onFullScreen: PanelModel;
  onDataZoom: () => void;
  onDblClick: () => void;
  onCollectChart?: () => void; // 保存到仪表盘
  onSelectLegend: ILegendItem[]; // 选择图例时
  onDimensionsOfSeries?: string[]; // 图表数据包含维度是派出
  onSeriesData?: any;
  onZrClick: ZrClickEvent;
  onOptionsLoaded(): void;
}
@Component
export class LineChart
  extends Mixins<ResizeMixin & IntersectionMixin & ToolsMixin & LegendMixin & ChartLoadingMixin & ErrorMsgMixins>(
    ResizeMixin,
    IntersectionMixin,
    ToolsMixin,
    ChartLoadingMixin,
    LegendMixin,
    ErrorMsgMixins
  )
  implements ICommonCharts
{
  @Prop({ required: true }) panel: PanelModel;
  // 是否展示图标头部
  @Prop({ default: true, type: Boolean }) showChartHeader: boolean;
  // 自定义时间范围
  @Prop({ type: Array }) customTimeRange: [string, string]; // 起始时间
  // 自定义更多菜单
  @Prop({ type: Array }) customMenuList: ChartTitleMenuType[];
  @Prop({ type: Boolean, default: true }) needSetEvent: boolean;
  // 是否为单图模式
  @Prop({ default: false, type: Boolean }) isSingleChart: boolean;
  // 图表的数据时间间隔
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  // 图表刷新间隔
  @InjectReactive('refreshInterval') readonly refreshInterval!: number;
  // 图表特殊参数
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  // 立即刷新图表
  @InjectReactive('refreshImmediate') readonly refreshImmediate: string;
  // 时区
  @InjectReactive('timezone') readonly timezone: string;
  // 时间对比的偏移量
  @InjectReactive('timeOffset') readonly timeOffset: string[];
  // 当前粒度
  @InjectReactive('downSampleRange') readonly downSampleRange: number | string;
  // 当前使用的业务id
  @InjectReactive('bkBizId') readonly bkBizId: number | string;
  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  // yAxis是否需要展示单位
  @InjectReactive('yAxisNeedUnit') readonly yAxisNeedUnit: boolean;
  // 框选事件范围后需应用到所有图表(包含三个数据 框选方法 是否展示复位  复位方法)
  @Inject({ from: 'enableSelectionRestoreAll', default: false }) readonly enableSelectionRestoreAll: boolean;
  @Inject({ from: 'handleChartDataZoom', default: () => null }) readonly handleChartDataZoom: (value: any) => void;
  @Inject({ from: 'handleRestoreEvent', default: () => null }) readonly handleRestoreEvent: () => void;
  @InjectReactive({ from: 'showRestore', default: false }) readonly showRestoreInject: boolean;

  height = 100;
  width = 300;
  legendData: ILegendItem[] = [];
  options: MonitorEchartOptions = null;
  initialized = false;
  refreshIntervalInstance = null;
  metrics: IExtendMetricData[];
  empty = true;
  emptyText = window.i18n.t('暂无数据');
  hasSetEvent = false;
  cancelTokens: (() => void)[] = [];
  minBase = 0;
  renderThresholds = false;
  thresholdLine = [];
  drillDownOptions: IMenuChildItem[] = [];
  /** 导出csv数据时候使用 */
  series: IUnifyQuerySeriesItem[];
  // 切换图例时使用
  seriesList = null;
  // 是否展示复位按钮
  showRestore = false;
  customScopedVars: Record<string, any> = {};

  // datasource为time_series才显示保存到仪表盘，数据检索， 查看大图
  get menuList(): ChartTitleMenuType[] {
    if (this.readonly) return ['fullscreen'];
    if (this.customMenuList) return this.customMenuList;
    const [target] = this.panel.targets;
    return target?.datasource === 'time_series'
      ? ['save', 'more', 'fullscreen', 'explore', 'area', 'drill-down', 'relate-alert']
      : ['screenshot', 'area'];
  }

  // 是否显示添加指标到策略选项
  get showAddMetric(): boolean {
    const [target] = this.panel.targets;
    return !this.readonly && target?.datasource === 'time_series';
  }

  // 只需要一条_result_的数据
  get onlyOneResult() {
    return this.panel.options?.time_series?.only_one_result;
  }

  // 开启自定时间范围，选择时间范围和双击操作时生效
  get isCustomTimeRange() {
    return this.panel.options?.time_series?.custom_timerange;
  }

  get yAxisNeedUnitGetter() {
    return this.yAxisNeedUnit ?? true;
  }
  // 近多少条数据（series取多少条线）
  get nearSeriesNum() {
    return Number(this.panel.options?.time_series?.nearSeriesNum || 0);
  }
  // 同时hover显示多个tooltip
  get hoverAllTooltips() {
    return this.panel.options?.time_series?.hoverAllTooltips;
  }

  // Y轴刻度标签文字占位宽度
  get YAxisLabelWidth() {
    return this.panel.options?.time_series?.YAxisLabelWidth || 0;
  }

  // 是否展示所有告警区域数据
  get needAllAlertMarkArea() {
    return this.panel.options?.time_series?.needAllAlertMarkArea;
  }
  // 自定义数据步长 collect_interval_display
  get collectIntervalDisplay() {
    return this.panel.options?.collect_interval_display;
  }
  // 是否允许对比
  get isSupportCompare() {
    return typeof this.panel.options?.is_support_compare !== 'boolean' ? true : this.panel.options.is_support_compare;
  }

  // 是否允许自定groupBy
  get isSupportGroupBy() {
    return !!this.panel.options?.is_support_group_by;
  }

  @Watch('viewOptions')
  // 用于配置后台图表数据的特殊设置
  handleFieldDictChange(v: IViewOptions, o: IViewOptions) {
    if (JSON.stringify(v) === JSON.stringify(o)) return;
    if (isShadowEqual(v, o)) return;
    this.getPanelData();
  }
  @Watch('timeRange')
  // 数据时间间隔
  handleTimeRangeChange() {
    this.getPanelData();
  }
  @Watch('refreshInterval')
  // 数据刷新间隔
  handleRefreshIntervalChange(v: number) {
    if (this.refreshIntervalInstance) {
      window.clearInterval(this.refreshIntervalInstance);
    }
    if (v == null || v <= 0) return;
    this.refreshIntervalInstance = window.setInterval(() => {
      this.initialized && this.getPanelData();
    }, this.refreshInterval);
  }
  @Watch('refreshImmediate')
  // 立刻刷新
  handleRefreshImmediateChange(v: string) {
    if (v) this.getPanelData();
  }
  @Watch('timezone')
  // 时区变更刷新图表
  handleTimezoneChange(v: string) {
    if (v) this.getPanelData();
  }
  @Watch('timeOffset')
  handleTimeOffsetChange(v: string[], o: string[]) {
    if (JSON.stringify(v) === JSON.stringify(o)) return;
    this.getPanelData();
  }

  @Watch('customTimeRange')
  customTimeRangeChange(val: [string, string]) {
    if (!val) {
      const { startTime, endTime } = handleTimeRange(this.timeRange);
      this.getPanelData(
        dayjs(startTime * 1000).format('YYYY-MM-DD HH:mm:ss'),
        dayjs(endTime * 1000).format('YYYY-MM-DD HH:mm:ss')
      );
    } else {
      this.getPanelData(val[0], val[1]);
    }
  }
  /* 粒度 */
  @Watch('downSampleRange')
  handleDownSampleRangeChange() {
    this.getPanelData();
  }
  @Watch('panel')
  panelChange(val, old) {
    if (isShadowEqual(val, old)) return;
    this.getPanelData();
  }
  @Watch('showRestoreInject')
  handleShowRestoreInject(v: boolean) {
    this.showRestore = v;
  }

  beforeDestroy() {
    this.handleUnSetLegendEvent();
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
  // 转换time_shift显示
  handleTransformTimeShift(val: string) {
    const timeMatch = val.match(/(-?\d+)(\w+)/);
    const hasMatch = timeMatch && timeMatch.length > 2;
    return hasMatch
      ? (dayjs() as any).add(-timeMatch[1], timeMatch[2]).fromNow().replace(/\s*/g, '')
      : val.replace('current', window.i18n.t('当前'));
  }
  // 图表tooltip 可用于继承组件重写该方法
  handleSetTooltip() {
    return {
      extraCssText: 'max-width: 50%',
    };
  }

  /**
   * @description 请求前 loading 状态改值逻辑（可用于继承组件重写该方法）
   **/
  handleBeforeRequestLoadingChange() {
    if (this.initialized) this.handleLoadingChange(true);
  }

  /**
   * @description: 获取图表数据
   * @param {*}
   * @return {*}
   */
  async getPanelData(start_time?: string, end_time?: string) {
    for (const cb of this.cancelTokens) {
      cb?.();
    }
    this.cancelTokens = [];
    if (!this.isInViewPort()) {
      if (this.intersectionObserver) {
        this.unregisterObserver();
      }
      this.registerObserver(start_time, end_time);
      return;
    }
    this.handleBeforeRequestLoadingChange();
    this.emptyText = window.i18n.t('加载中...');
    if (!this.enableSelectionRestoreAll) {
      this.showRestore = !!start_time;
    }
    try {
      this.unregisterObserver();
      let series = [];
      const metrics = [];
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      let params = {
        start_time: start_time ? dayjs(start_time).unix() : startTime,
        end_time: end_time ? dayjs(end_time).unix() : endTime,
      };
      if (this.collectIntervalDisplay === '1d') {
        // 如果数据步长为1天 则时间范围最小为7天
        const weekTime = 7 * 24 * 60 * 60;
        const dTime = 24 * 60 * 60;
        if (params.end_time - params.start_time < weekTime) {
          params.start_time = params.end_time - weekTime;
        }
        params.end_time = params.end_time + dTime;
      }
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
        ...(this.viewOptions?.groupByVariables || {}),
        ...this.customScopedVars,
      });
      for (const time_shift of timeShiftList) {
        const noTransformVariables = this.panel?.options?.time_series?.noTransformVariables;
        const list = this.panel.targets.map(item => {
          const newParams = {
            ...variablesService.transformVariables(
              item.data,
              {
                ...this.viewOptions.filters,
                ...(this.viewOptions.filters?.current_target || {}),
                ...this.viewOptions,
                ...this.viewOptions.variables,
                ...(this.viewOptions?.groupByVariables || {}),
                time_shift,
                interval,
                ...this.customScopedVars,
              },
              noTransformVariables
            ),
            ...params,
            down_sample_range: this.downSampleRangeComputed(
              this.downSampleRange as string,
              [params.start_time, params.end_time],
              item.apiFunc
            ),
          };
          // 主机监控ipv6特殊逻辑 用于去除不必要的group_by字段
          if (item.ignore_group_by?.length && newParams.query_configs.some(set => set.group_by?.length)) {
            newParams.query_configs = newParams.query_configs.map(config => ({
              ...config,
              group_by: config.group_by.filter(key => !item.ignore_group_by.includes(key)),
            }));
          }
          if (!this.viewOptions?.groupByVariables?.group_by_limit_enabled) {
            newParams.group_by_limit = undefined;
          }
          const primaryKey = item?.primary_key;
          const paramsArr = [];
          if (primaryKey) {
            paramsArr.push(primaryKey);
          }
          paramsArr.push(newParams);
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
                  ...res.series.map(set => ({
                    ...set,
                    name: `${this.timeOffset.length ? `${this.handleTransformTimeShift(time_shift || 'current')}-` : ''}${
                      this.handleSeriesName(item, set) || set.target
                    }`,
                  }))
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
        this.emitDimensions(series);
        this.series = Object.freeze(series) as any;
        if (this.onlyOneResult) {
          let hasResultSeries = false;
          series = series.filter(item => {
            const pass = !(hasResultSeries && item.alias === '_result_');
            if (pass) {
              hasResultSeries = true;
            }
            return pass;
          });
        }
        if (this.nearSeriesNum) {
          series = series.slice(0, this.nearSeriesNum);
        }
        const seriesResult = series
          .filter(item => ['extra_info', '_result_'].includes(item.alias))
          .map(item => ({
            ...item,
            datapoints: item.datapoints.map(point => [JSON.parse(point[0])?.anomaly_score ?? point[0], point[1]]),
          }));
        let seriesList = this.handleTransformSeries(
          seriesResult.map((item, index) => ({
            name: item.name,
            cursor: 'auto',
            // biome-ignore lint/style/noCommaOperator: <explanation>
            data: item.datapoints.reduce((pre: any, cur: any) => (pre.push(cur.reverse()), pre), []),
            stack: item.stack || random(10),
            unit: this.panel.options?.unit || item.unit,
            markPoint: this.createMarkPointData(item, series),
            markLine: this.createMarkLine(index),
            markArea: this.createMarkArea(item, index),
            z: 1,
            traceData: item.trace_data ?? '',
            dimensions: item.dimensions ?? {},
            color: item?.color,
          })) as any
        );
        const boundarySeries = seriesResult
          .map(item => this.handleBoundaryList(item, series))
          .flat(Number.POSITIVE_INFINITY);
        if (boundarySeries) {
          seriesList = [...seriesList.map((item: any) => ({ ...item, z: 6 })), ...boundarySeries];
        }
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
        const { canScale, minThreshold, maxThreshold } = this.handleSetThresholds();

        const chartBaseOptions = MONITOR_LINE_OPTIONS;
        const echartOptions = deepmerge(
          deepClone(chartBaseOptions),
          this.panel.options?.time_series?.echart_option || {},
          { arrayMerge: (_, newArr) => newArr }
        );
        const isBar = this.panel.options?.time_series?.type === 'bar';
        const { width } = this.$el.getBoundingClientRect();
        const xInterval = getTimeSeriesXInterval(maxXInterval, width, maxSeriesCount);
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
                        if (['', undefined, null].includes(seriesList[0].unit)) {
                          return obj.text + (obj.suffix ?? '');
                        }
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
              min: v => {
                let min = Math.min(v.min, +minThreshold);
                // 柱状图y轴不能以最小值作为起始点
                if (isBar) min = min <= 10 ? 0 : min - 10;
                return min;
              },
            },
            xAxis: {
              axisLabel: {
                formatter: formatterFunc || '{value}',
              },
              ...xInterval,
            },
            series: seriesList,
            tooltip: this.handleSetTooltip(),
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
        if (!this.hasSetEvent && this.needSetEvent) {
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
      this.$emit('optionsLoaded');
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.t('出错了');
      console.error(e);
    }
    // 初始化刷新定时器
    if (!this.refreshIntervalInstance && this.refreshInterval) {
      this.handleRefreshIntervalChange(this.refreshInterval);
    }
    this.cancelTokens = [];
    this.handleLoadingChange(false);
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

  handleSetThresholds() {
    const { markLine } = this.panel?.options?.time_series || {};
    const thresholdList = markLine?.data?.map?.(item => item.yAxis) || [];
    const max = Math.max(...thresholdList);
    return {
      canScale: thresholdList.length > 0 && thresholdList.every((set: number) => set > 0),
      minThreshold: Math.min(...thresholdList),
      maxThreshold: max + max * 0.1, // 防止阈值最大值过大时title显示不全
    };
  }

  /** 处理图表上下边界的数据 */
  handleBoundaryList(item, series) {
    const currentDimensions = item.dimensions || [];
    const getDimStr = dim => `${dim.bk_target_ip}-${dim.bk_target_cloud_id}`;
    const currentDimStr = getDimStr(currentDimensions);
    const lowerBound = series.find(ser => ser.alias === 'lower_bound' && getDimStr(ser.dimensions) === currentDimStr);
    const upperBound = series.find(ser => ser.alias === 'upper_bound' && getDimStr(ser.dimensions) === currentDimStr);
    if (!lowerBound || !upperBound) return [];
    const boundaryList = [];
    const level = 1;
    const algorithm2Level = {
      1: 5,
      2: 4,
      3: 3,
    };
    boundaryList.push({
      upBoundary: upperBound.datapoints,
      lowBoundary: lowerBound.datapoints,
      color: '#e6e6e6',
      type: 'line',
      stack: `boundary-${level}`,
      z: algorithm2Level[level],
    });
    // 上下边界处理
    if (boundaryList?.length) {
      for (const item of boundaryList) {
        const base = -item.lowBoundary.reduce(
          (min: number, val: any) => (val[1] !== null ? Math.floor(Math.min(min, val[1])) : min),
          Number.POSITIVE_INFINITY
        );
        this.minBase = Math.max(base, this.minBase);
      }
      const boundarySeries = boundaryList.map((item: any) => this.createBoundarySeries(item, this.minBase));
      return boundarySeries;
    }
  }

  createBoundarySeries(item: any, base: number) {
    return [
      {
        name: `lower-${item.stack}-no-tips`,
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
        name: `upper-${item.stack}-no-tips`,
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
        },
        stack: item.stack,
        symbol: 'none',
        z: item.z || 4,
      },
    ];
  }

  /** 阈值线 */
  createMarkLine(index: number) {
    if (index) return {};
    return this.panel.options?.time_series?.markLine || {};
  }

  /** 区域标记 */
  createMarkArea(item, index) {
    /** 阈值区域 */
    const thresholdsMarkArea = index ? {} : this.panel.options?.time_series?.markArea || {};
    let alertMarkArea = {};
    /** 告警区域 */
    if (item.markTimeRange?.length) {
      alertMarkArea = this.handleSetThresholdBand(item.markTimeRange.slice());
    }
    return deepmerge(alertMarkArea, thresholdsMarkArea);
  }

  /** 获取告警点数据 */
  createMarkPointData(item, series) {
    let data = [];
    /** 获取is_anomaly的告警点数据 */
    const currentDataPoints = item.datapoints;
    const currentDataPointsMap = new Map();
    const currentDimensions = item.dimensions || [];
    const getDimStr = dim => `${dim.bk_target_ip}-${dim.bk_target_cloud_id}`;
    const currentDimStr = getDimStr(currentDimensions);
    const currentIsAnomalyData = series.find(
      item => item.alias === 'is_anomaly' && currentDimStr === getDimStr(item.dimensions)
    );
    let markPointData = [];
    if (currentIsAnomalyData) {
      for (const item of currentDataPoints) {
        currentDataPointsMap.set(item[0], item[1]);
      }
      const currentIsAnomalyPoints = currentIsAnomalyData.datapoints;
      markPointData = currentIsAnomalyPoints.reduce((total, cur) => {
        const key = cur[1];
        const val = currentDataPointsMap.get(key);
        const isExit = currentDataPointsMap.has(key) && cur[0];
        /** 测试条件 */
        // const isExit = currentDataPointsMap.has(key) && val > 31.51;
        isExit && total.push([key, val]);
        return total;
      }, []);
    }
    /** 红色告警点 */
    data = markPointData.map(item => ({
      itemStyle: {
        color: '#EA3636',
      },
      xAxis: item[0],
      yAxis: item[1],
    }));

    item.markPoints?.length &&
      data.push(
        ...item.markPoints.map(item => ({
          xAxis: item[1],
          yAxis: item[0],
          symbolSize: 12,
        }))
      );
    /** 事件中心告警开始点 */
    const markPoint = {
      data,
      zlevel: 0,
      symbol: 'circle',
      symbolSize: 6,
      z: 10,
      label: {
        show: false,
      },
    };
    return markPoint;
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
   * @description: 转换时序数据 并设置图例
   * @param {ITimeSeriesItem} series 图表时序数据
   * @return {*}
   */
  handleTransformSeries(series: ITimeSeriesItem[], colors?: string[]) {
    const legendData: ILegendItem[] = [];
    this.renderThresholds = false;
    const transformSeries = series.map((item, index) => {
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
      const precision = this.handleGetMinPrecision(
        item.data.filter((set: any) => typeof set[1] === 'number').map((set: any[]) => set[1]),
        getValueFormat(this.yAxisNeedUnitGetter ? item.unit || '' : ''),
        item.unit
      );
      if (item.name) {
        for (const key of Object.keys(legendItem)) {
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
        precision: this.panel.options?.precision || precision,
        lineStyle: {
          width: 1,
        },
      };
    });
    this.legendData = legendData;
    return transformSeries;
  }

  /** 设置事件中心告警区域 */
  handleSetThresholdBand(plotBands: IPlotBand[]) {
    return {
      silent: true,
      show: true,
      data: plotBands.map(item => [
        {
          xAxis: item.from,
          y: 'max',
          itemStyle: {
            color: item.color || '#FFF5EC',
            borderWidth: 1,
            borderColor: item.borderColor || '#FFE9D5',
            shadowColor: item.shadowColor || '#FFF5EC',
            borderType: item.borderType || 'solid',
            shadowBlur: 0,
          },
        },
        {
          xAxis: item.to || 'max',
          y: '0%',
          itemStyle: {
            color: item.color || '#FFF5EC',
            borderWidth: 1,
            borderColor: item.borderColor || '#FFE9D5',
            shadowColor: item.shadowColor || '#FFF5EC',
            borderType: item.borderType || 'solid',
            shadowBlur: 0,
          },
        },
      ]),
      opacity: 0.1,
    };
  }

  /** 标记点 */
  getMarkPoint(data = []) {
    const markPoint = {
      data,
      zlevel: 0,
      symbol: 'circle',
      symbolSize: 6,
      z: 10,
      label: {
        show: false,
      },
    };
    return markPoint;
  }
  /**
   * @description: 图表头部工具栏事件
   * @param {IMenuItem} menuItem
   * @return {*}
   */
  handleMenuToolsSelect(menuItem: IMenuItem) {
    const variablesService = new VariablesService({ ...this.viewOptions, ...this.customScopedVars });
    switch (menuItem.id) {
      case 'save': // 保存到仪表盘
        this.handleCollectChart();
        break;
      case 'screenshot': // 保存到本地
        setTimeout(() => {
          this.handleStoreImage(this.panel.title || '测试');
        }, 300);
        break;
      case 'fullscreen': {
        // 大图检索
        let copyPanel: IPanelModel = JSON.parse(JSON.stringify(this.panel));
        const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);

        const variablesService = new VariablesService({
          ...this.viewOptions.filters,
          ...(this.viewOptions.filters?.current_target || {}),
          ...this.viewOptions,
          ...this.viewOptions.variables,
          interval: reviewInterval(
            this.viewOptions.interval,
            dayjs.tz(endTime).unix() - dayjs.tz(startTime).unix(),
            this.panel.collect_interval
          ),
          ...this.customScopedVars,
        });
        copyPanel = variablesService.transformVariables(copyPanel);
        copyPanel.targets.forEach((t, tIndex) => {
          const queryConfigs = this.panel.targets[tIndex].data.query_configs;
          t.data.query_configs.forEach((q, qIndex) => {
            q.functions = JSON.parse(JSON.stringify(queryConfigs[qIndex].functions));
          });
        });
        this.handleFullScreen(copyPanel as any);
        break;
      }

      case 'area': // 面积图
        (this.$refs.baseChart as any)?.handleTransformArea(menuItem.checked);
        break;
      case 'set': // 转换Y轴大小
        (this.$refs.baseChart as any)?.handleSetYAxisSetScale(!menuItem.checked);
        break;
      case 'explore': // 跳转数据检索
        this.handleExplore(this.panel, {
          ...this.viewOptions.filters,
          ...(this.viewOptions.filters?.current_target || {}),
          ...this.viewOptions,
          ...this.viewOptions.variables,
          ...this.customScopedVars,
        });
        break;
      case 'strategy': // 新增策略
        this.handleAddStrategy(
          this.panel,
          null,
          {
            ...this.viewOptions,
            ...this.customScopedVars,
          },
          true
        );
        break;
      case 'drill-down': // 下钻 默认主机
        this.handleDrillDown(menuItem.childValue);
        break;
      case 'relate-alert':
        for (const target of this.panel?.targets || []) {
          if (target.data?.query_configs?.length) {
            let queryConfig = deepClone(target.data.query_configs);
            queryConfig = variablesService.transformVariables(queryConfig);
            target.data.query_configs = queryConfig;
          }
        }
        handleRelateAlert(this.panel, this.timeRange);
        break;
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
      case 'drill-down' /** 下钻到检索 */:
        this.handleDrillDown(data.child.id);
        break;
      case 'more' /** 更多操作 */:
        if (data.child.id === 'screenshot') {
          /** 截图 */
          setTimeout(() => {
            this.handleStoreImage(this.panel.title);
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
   * 下钻到检索
   * @param type 主机 | 实例
   */
  handleDrillDown(id: string) {
    const targets = this.handleExplore(
      this.panel,
      {
        ...this.viewOptions.filters,
        ...(this.viewOptions.filters?.current_target || {}),
        ...this.viewOptions,
        ...this.viewOptions.variables,
        ...this.customScopedVars,
      },
      false
    );
    const result = targets.map(item => {
      item.data.query_configs = item.data.query_configs.map(query => {
        const groupBySet = new Set(query.group_by);
        groupBySet.add(id);
        query.group_by = [...groupBySet];
        query.where = [];
        query.filter_dict = {};
        return query;
      });
      return item;
    });
    const url = `${location.origin}${location.pathname.toString().replace('fta/', '')}?bizId=${
      this.panel.targets?.[0]?.data?.bk_biz_id || this.panel.bk_biz_id || this.$store.getters.bizId
    }#/data-retrieval/?targets=${encodeURIComponent(JSON.stringify(result))}&from=${this.timeRange[0]}&to=${
      this.timeRange[1]
    }&timezone=${this.timezone}`;
    window.open(url);
  }
  /** 处理点击左侧响铃图标 跳转策略的逻辑 */
  handleAlarmClick(alarmStatus: ITitleAlarm) {
    const metricIds = this.metrics.map(item => item.metric_id);
    switch (alarmStatus.status) {
      case 0:
        this.handleAddStrategy(
          this.panel,
          null,
          {
            ...this.viewOptions,
            ...this.customScopedVars,
          },
          true
        );
        break;
      case 1:
        window.open(location.href.replace(location.hash, `#/strategy-config?metricId=${JSON.stringify(metricIds)}`));
        break;
      case 2:
        {
          const eventTargetStr = alarmStatus.targetStr;
          window.open(
            location.href.replace(
              location.hash,
              `#/event-center?queryString=${metricIds.map(item => `metric : "${item}"`).join(' AND ')}${
                eventTargetStr ? ` AND ${eventTargetStr}` : ''
              }&activeFilterId=NOT_SHIELDED_ABNORMAL&from=${this.timeRange[0]}&to=${this.timeRange[1]}`
            )
          );
        }
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
   * @description: 点击单个指标
   * @param {IExtendMetricData} metric
   * @return {*}
   */
  handleMetricClick(metric: IExtendMetricData) {
    this.handleAddStrategy(this.panel, metric, {
      ...this.viewOptions,
      ...this.customScopedVars,
    });
  }

  /**
   * @description: 点击所有指标
   * @param {*}
   * @return {*}
   */
  handleAllMetricClick() {
    this.handleAddStrategy(
      this.panel,
      null,
      {
        ...this.viewOptions,
        ...this.customScopedVars,
      },
      true
    );
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
  handleDblClick() {
    this.isCustomTimeRange ? this.$emit('dblClick') : this.getPanelData();
  }
  dataZoom(startTime: string, endTime: string) {
    if (this.enableSelectionRestoreAll) {
      this.handleChartDataZoom([startTime, endTime]);
    } else {
      this.isCustomTimeRange ? this.$emit('dataZoom', startTime, endTime) : this.getPanelData(startTime, endTime);
    }
  }
  /* 粒度计算 */
  /* 粒度计算 */
  downSampleRangeComputed(downSampleRange: string, timeRange: number[], api: string) {
    if (downSampleRange === 'raw' || !['unifyQuery', 'graphUnifyQuery'].includes(api)) {
      return undefined;
    }
    if (downSampleRange === 'auto') {
      let width = 1;
      if (this.$refs.chart) {
        width = (this.$refs.chart as Element).clientWidth;
      } else {
        width = this.$el.clientWidth - (this.panel.options?.legend?.placement === 'right' ? 320 : 0);
      }
      const size = (timeRange[1] - timeRange[0]) / width;
      return size > 0 ? `${Math.ceil(size)}s` : undefined;
    }
    return downSampleRange;
  }

  handleSelectLegend({ actionType, item }: { actionType: LegendActionType; item: ILegendItem }) {
    if (this.legendData.length < 2) {
      return;
    }
    const copyOptions = { ...this.options };
    const setSeriesFilter = () => {
      const showNames = [];
      for (const l of this.legendData) {
        l.show && showNames.push(l.name);
      }
      copyOptions.series = this.seriesList?.filter(s => showNames.includes(s.name));
      this.options = Object.freeze({ ...copyOptions });
    };
    if (actionType === 'shift-click') {
      item.show = !item.show;
      setSeriesFilter();
      this.$emit('selectLegend', this.legendData);
    } else if (actionType === 'click') {
      const hasOtherShow = this.legendData.filter(item => !item.hidden).some(set => set.name !== item.name && set.show);
      for (const legend of this.legendData) {
        legend.show = legend.name === item.name || !hasOtherShow;
      }
      setSeriesFilter();
      this.$emit('selectLegend', this.legendData);
    }
    setTimeout(() => {
      this.handleResize();
    }, 100);
  }

  emitDimensions(series) {
    const dimensionSet = new Set();
    for (const s of series) {
      if (s.dimensions) {
        for (const dKey of Object.keys(s.dimensions)) {
          dimensionSet.add(dKey);
        }
      }
    }
    this.$emit('dimensionsOfSeries', [...dimensionSet]);
  }
  handleRestore() {
    if (this.enableSelectionRestoreAll) {
      this.handleRestoreEvent();
    } else {
      this.dataZoom(undefined, undefined);
    }
  }

  setOptions(option) {
    if (!option) return;
    this.options = Object.freeze(option);
  }

  @Emit('zrClick')
  handleZrClick(params: ZrClickEvent) {
    return params;
  }
  render() {
    const { legend } = this.panel?.options || { legend: {} };
    return (
      <div class='time-series'>
        {this.showChartHeader && (
          <ChartHeader
            class='draggable-handle'
            collectIntervalDisplay={this.collectIntervalDisplay}
            description={this.panel.options?.header?.tips || ''}
            dragging={this.panel.dragging}
            drillDownOption={this.drillDownOptions}
            initialized={this.initialized}
            isInstant={this.panel.instant}
            menuList={this.menuList}
            metrics={this.metrics}
            showAddMetric={this.showAddMetric}
            showMore={this.showHeaderMoreTool}
            subtitle={this.panel.subTitle || ''}
            title={this.panel.title}
            onAlarmClick={this.handleAlarmClick}
            onAllMetricClick={this.handleAllMetricClick}
            onMenuClick={this.handleMenuToolsSelect}
            onMetricClick={this.handleMetricClick}
            onSelectChild={this.handleSelectChildMenu}
            onUpdateDragging={() => this.panel.updateDragging(false)}
          />
        )}
        {!this.empty ? (
          <div class={`time-series-content ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
            <div
              ref='chart'
              class={`chart-instance ${legend?.displayMode === 'table' ? 'is-table-legend' : ''}`}
            >
              {this.initialized && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.height}
                  groupId={this.panel.dashboardId}
                  hoverAllTooltips={this.hoverAllTooltips}
                  needZrClick={this.panel.options?.need_zr_click_event}
                  options={this.options}
                  showRestore={this.showRestore}
                  onDataZoom={this.dataZoom}
                  onDblClick={this.handleDblClick}
                  onRestore={this.handleRestore}
                  onZrClick={this.handleZrClick}
                />
              )}
            </div>
            {legend?.displayMode !== 'hidden' && (
              <div class={`chart-legend ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
                {legend?.displayMode === 'table' ? (
                  <TableLegend
                    legendData={this.legendData}
                    onSelectLegend={this.handleSelectLegend}
                  />
                ) : (
                  <ListLegend
                    legendData={this.legendData}
                    onSelectLegend={this.handleSelectLegend}
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

export default ofType<ITimeSeriesProps, ITimeSeriesEvent>().convert(LineChart);
