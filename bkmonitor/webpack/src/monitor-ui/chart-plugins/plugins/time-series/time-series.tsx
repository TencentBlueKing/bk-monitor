/* eslint-disable no-param-reassign */
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
import { Component, Inject, InjectReactive, Mixins, Prop, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';
import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import type { EChartOption } from 'echarts';

import { CancelToken } from '../../../../monitor-api/index';
import { deepClone, random } from '../../../../monitor-common/utils/utils';
import { TimeRangeType } from '../../../../monitor-pc/components/time-range/time-range';
import { handleTransformToTimestamp } from '../../../../monitor-pc/components/time-range/utils';
import {
  downCsvFile,
  IUnifyQuerySeriesItem,
  transformSrcData,
  transformTableDataToCsvStr
} from '../../../../monitor-pc/pages/view-detail/utils';
import { handleTimeRange } from '../../../../monitor-pc/utils';
import { getValueFormat, ValueFormatter } from '../../../monitor-echarts/valueFormats';
import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { IChartTitleMenuEvents } from '../../components/chart-title/chart-title-menu';
import { COLOR_LIST, COLOR_LIST_BAR, MONITOR_LINE_OPTIONS } from '../../constants';
import {
  ChartLoadingMixin,
  ErrorMsgMixins,
  IntersectionMixin,
  LegendMixin,
  ResizeMixin,
  ToolsMxin
} from '../../mixins';
import {
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
  PanelModel
} from '../../typings';
import { isShadowEqual, reviewInterval } from '../../utils';
import { handleRelateAlert } from '../../utils/menu';
import { VariablesService } from '../../utils/variable';
import BaseEchart from '../monitor-base-echart';

import './time-series.scss';

interface ITimeSeriesProps {
  panel: PanelModel;
  showHeaderMoreTool?: boolean;
  showChartHeader?: boolean;
  customTimeRange?: [string, string];
  customMenuList?: ChartTitleMenuType[];
  needSetEvent?: boolean;
}
interface ITimeSeriesEvent {
  onFullScreen: PanelModel;
  onDataZoom: void;
  onDblClick: void;
  onCollectChart?: () => void; // 保存到仪表盘
  onSelectLegend: ILegendItem[]; // 选择图例时
  onDimensionsOfSeries?: string[]; // 图表数据包含维度是派出
  onSeriesData?: any;
}
@Component
export class LineChart
  extends Mixins<ResizeMixin & IntersectionMixin & ToolsMxin & LegendMixin & ChartLoadingMixin & ErrorMsgMixins>(
    ResizeMixin,
    IntersectionMixin,
    ToolsMxin,
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
  // 图表的数据时间间隔
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  // 图表刷新间隔
  @InjectReactive('refleshInterval') readonly refleshInterval!: number;
  // 图表特殊参数
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  // 立即刷新图表
  @InjectReactive('refleshImmediate') readonly refleshImmediate: string;
  // 时区
  @InjectReactive('timezone') readonly timezone: string;
  // 时间对比的偏移量
  @InjectReactive('timeOffset') readonly timeOffset: string[];
  // 当前粒度
  @InjectReactive('downSampleRange') readonly downSampleRange: string | number;
  // 当前使用的业务id
  @InjectReactive('bkBizId') readonly bkBizId: string | number;
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
  options: EChartOption = null;
  inited = false;
  refleshIntervalInstance = null;
  metrics: IExtendMetricData[];
  empty = true;
  emptyText = window.i18n.tc('暂无数据');
  hasSetEvent = false;
  cancelTokens: Function[] = [];
  minBase = 0;
  renderThresholds = false;
  thresholdLine = [];
  drillDownOptions: IMenuChildItem[] = [];
  /** 导出csv数据时候使用 */
  series: IUnifyQuerySeriesItem[];
  // 切换图例时使用
  seriesList = [];
  // 是否展示复位按钮
  showRestore = false;

  // datasource为time_series才显示保存到仪表盘，数据检索， 查看大图
  get menuList(): ChartTitleMenuType[] {
    if (this.readonly) return ['fullscreen'];
    if (this.customMenuList) return this.customMenuList;
    const [target] = this.panel.targets;
    return target.datasource === 'time_series'
      ? ['save', 'more', 'fullscreen', 'explore', 'set', 'area', 'drill-down', 'relate-alert']
      : ['screenshot', 'set', 'area'];
  }

  // 是否显示添加指标到策略选项
  get showAddMetric(): boolean {
    const [target] = this.panel.targets;
    return !this.readonly && target.datasource === 'time_series';
  }

  // 只需要一条_result_的数据
  get onlyOneResult() {
    return !!this.panel.options?.time_series?.only_one_result;
  }

  // 开启自定时间范围，选择时间范围和双击操作时生效
  get isCustomTimeRange() {
    return !!this.panel.options?.time_series?.custom_timerange;
  }

  get yAxisNeedUnitGetter() {
    return this.yAxisNeedUnit ?? true;
  }
  // 近多少条数据（series取多少条线）
  get nearSeriesNum() {
    return Number(this.panel.options?.time_series?.nearSeriesNum || 0);
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
  @Watch('refleshInterval')
  // 数据刷新间隔
  handleRefleshIntervalChange(v: number) {
    if (this.refleshIntervalInstance) {
      window.clearInterval(this.refleshIntervalInstance);
    }
    if (v <= 0) return;
    this.refleshIntervalInstance = window.setInterval(() => {
      this.inited && this.getPanelData();
    }, this.refleshInterval);
  }
  @Watch('refleshImmediate')
  // 立刻刷新
  handleRefleshImmediateChange(v: string) {
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
            ...dimensions_translation
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
        current: this.$t('当前')
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
      : val.replace('current', window.i18n.tc('当前'));
  }
  // 图表tooltip 可用于继承组件重写该方法
  handleSetTooltip() {
    return {};
  }
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
      let series = [];
      const metrics = [];
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      let params = {
        start_time: start_time ? dayjs(start_time).unix() : startTime,
        end_time: end_time ? dayjs(end_time).unix() : endTime
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
        const noTransformVariables = !!this.panel?.options?.time_series?.noTransformVariables;
        const list = this.panel.targets.map(item => {
          const newPrarams = {
            ...variablesService.transformVariables(
              item.data,
              {
                ...this.viewOptions.filters,
                ...(this.viewOptions.filters?.current_target || {}),
                ...this.viewOptions,
                ...this.viewOptions.variables,
                time_shift,
                interval
              },
              noTransformVariables
            ),
            ...params,
            down_sample_range: this.downSampleRangeComputed(
              this.downSampleRange as string,
              [params.start_time, params.end_time],
              item.apiFunc
            )
          };
          // 主机监控ipv6特殊逻辑 用于去除不必要的group_by字段
          if (item.ignore_group_by?.length && newPrarams.query_configs.some(set => set.group_by?.length)) {
            newPrarams.query_configs = newPrarams.query_configs.map(config => ({
              ...config,
              group_by: config.group_by.filter(key => !item.ignore_group_by.includes(key))
            }));
          }
          return (this as any).$api[item.apiModule]
            [item.apiFunc](newPrarams, {
              cancelToken: new CancelToken((cb: Function) => this.cancelTokens.push(cb)),
              needMessage: false
            })
            .then(res => {
              this.$emit('seriesData', res);
              res.metrics && metrics.push(...res.metrics);
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
            });
        });
        promiseList.push(...list);
      });
      await Promise.all(promiseList).catch(() => false);
      if (series.length) {
        /* 派出图表数据包含的维度*/
        this.emitDimensions(series);
        this.series = Object.freeze(series) as any;
        if (this.onlyOneResult) {
          let hasResultSeries = false;
          series = series.filter(item => {
            const pass = !(hasResultSeries && item.alias === '_result_');
            pass && (hasResultSeries = true);
            return pass;
          });
        }
        if (!!this.nearSeriesNum) {
          series = series.slice(0, this.nearSeriesNum);
        }
        const seriesResult = series
          .filter(item => ['extra_info', '_result_'].includes(item.alias))
          .map(item => ({
            ...item,
            datapoints: item.datapoints.map(point => [JSON.parse(point[0])?.anomaly_score ?? point[0], point[1]])
          }));
        let seriesList = this.handleTransformSeries(
          seriesResult.map((item, index) => ({
            name: item.name,
            cursor: 'auto',
            data: item.datapoints.reduce((pre: any, cur: any) => (pre.push(cur.reverse()), pre), []),
            stack: item.stack || random(10),
            unit: this.panel.options?.unit || item.unit,
            markPoint: this.createMarkPointData(item, series),
            markLine: this.createMarkLine(index),
            markArea: this.createMarkArea(item, index),
            z: 1,
            traceData: item.trace_data ?? ''
          })) as any
        );
        const boundarySeries = seriesResult.map(item => this.handleBoundaryList(item, series)).flat(Infinity);
        if (!!boundarySeries) {
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
              value: [set.value[0], set.value[1] !== null ? set.value[1] + this.minBase : null]
            };
          })
        }));
        this.seriesList = Object.freeze(seriesList) as any;
        // 1、echarts animation 配置会影响数量大时的图表性能 掉帧
        // 2、echarts animation配置为false时 对于有孤立点不连续的图表无法放大 并且 hover的点放大效果会潇洒 (貌似echarts bug)
        // 所以此处折中设置 在有孤立点情况下进行开启animation 连续的情况不开启
        const hasShowSymbol = seriesList.some(item => item.showSymbol);
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
        const isBar = this.panel.options?.time_series?.type === 'bar';
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
              min: v => {
                let min = Math.min(v.min, +minThreshold);
                // 柱状图y轴不能以最小值作为起始点
                if (isBar) min = min <= 10 ? 0 : min - 10;
                return min;
              }
            },
            xAxis: {
              axisLabel: {
                formatter: formatterFunc || '{value}'
              },
              splitNumber: Math.ceil(this.width / 80),
              min: 'dataMin'
            },
            series: seriesList,
            tooltip: this.handleSetTooltip()
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
        this.emptyText = window.i18n.tc('暂无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      console.error(e);
    }
    // 初始化刷新定时器
    if (!this.refleshIntervalInstance && this.refleshInterval) {
      this.handleRefleshIntervalChange(this.refleshInterval);
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
          name: item.name
        });
      }
      return total;
    }, []);
  }

  handleSetThreholds() {
    const { markLine } = this.panel?.options?.time_series || {};
    const thresholdList = markLine?.data?.map?.(item => item.yAxis) || [];
    const max = Math.max(...thresholdList);
    return {
      canScale: thresholdList.length > 0 && thresholdList.every((set: number) => set > 0),
      minThreshold: Math.min(...thresholdList),
      maxThreshold: max + max * 0.1 // 防止阈值最大值过大时title显示不全
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
      3: 3
    };
    boundaryList.push({
      upBoundary: upperBound.datapoints,
      lowBoundary: lowerBound.datapoints,
      color: '#e6e6e6',
      type: 'line',
      stack: `boundary-${level}`,
      z: algorithm2Level[level]
    });
    // 上下边界处理
    if (boundaryList?.length) {
      boundaryList.forEach((item: any) => {
        const base = -item.lowBoundary.reduce(
          (min: number, val: any) => (val[1] !== null ? Math.floor(Math.min(min, val[1])) : min),
          Infinity
        );
        this.minBase = Math.max(base, this.minBase);
      });
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
          opacity: 0
        },
        stack: item.stack,
        symbol: 'none',
        z: item.z || 4
      },
      {
        name: `upper-${item.stack}-no-tips`,
        type: 'line',
        data: item.upBoundary.map((set: any, index: number) => [
          set[1],
          set[0] === null ? null : set[0] - item.lowBoundary[index][0]
        ]),
        lineStyle: {
          opacity: 0
        },
        areaStyle: {
          color: item.color || '#e6e6e6'
        },
        stack: item.stack,
        symbol: 'none',
        z: item.z || 4
      }
    ];
  }

  /** 阈值线 */
  createMarkLine(index: number) {
    if (!!index) return {};
    return this.panel.options?.time_series?.markLine || {};
  }

  /** 区域标记 */
  createMarkArea(item, index) {
    /** 阈值区域 */
    const thresholdsMarkArea = !!index ? {} : this.panel.options?.time_series?.markArea || {};
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
    const currentIsAanomalyData = series.find(
      item => item.alias === 'is_anomaly' && currentDimStr === getDimStr(item.dimensions)
    );
    let markPointData = [];
    if (!!currentIsAanomalyData) {
      currentDataPoints.forEach(item => currentDataPointsMap.set(item[0], item[1]));
      const currentIsAanomalyPoints = currentIsAanomalyData.datapoints;
      markPointData = currentIsAanomalyPoints.reduce((total, cur) => {
        const key = cur[1];
        const val = currentDataPointsMap.get(key);
        const isExit = currentDataPointsMap.has(key) && !!cur[0];
        /** 测试条件 */
        // const isExit = currentDataPointsMap.has(key) && val > 31.51;
        isExit && total.push([key, val]);
        return total;
      }, []);
    }
    /** 红色告警点 */
    data = markPointData.map(item => ({
      itemStyle: {
        color: '#EA3636'
      },
      xAxis: item[0],
      yAxis: item[1]
    }));

    !!item.markPoints?.length &&
      data.push(
        ...item.markPoints.map(item => ({
          xAxis: item[1],
          yAxis: item[0],
          symbolSize: 12
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
        show: false
      }
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
      (formatterFunc = (v: any) => {
        const duration = dayjs.tz(maxX).diff(dayjs.tz(minX), 'second');
        if (onlyBeginEnd && v > minX && v < maxX) {
          return '';
        }
        if (duration < 60 * 60 * 24 * 1) {
          return dayjs.tz(v).format('HH:mm');
        }
        if (duration < 60 * 60 * 24 * 8) {
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
      { value: 1e18, symbol: 'E' }
    ];
    const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;
    let i;
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
        dimensions: item.dimensions as unknown as Record<string, string>
      };
      // 动态单位转换
      const unitFormatter =
        item.unit !== 'none'
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
              opacity: 1
            },
            traceData
          } as any;
        }
        return seriesItem;
      });

      legendItem.avg = +(+legendItem.total / (hasValueLength || 1)).toFixed(2);
      legendItem.total = Number(legendItem.total).toFixed(2);
      // 获取y轴上可设置的最小的精确度
      const precision = this.handleGetMinPrecision(
        item.data.filter((set: any) => typeof set[1] === 'number').map((set: any[]) => set[1]),
        unitFormatter,
        item.unit
      );
      if (item.name) {
        Object.keys(legendItem).forEach(key => {
          if (['min', 'max', 'avg', 'total'].includes(key)) {
            const val = legendItem[key];
            legendItem[`${key}Source`] = val;
            const set: any = unitFormatter(val, item.unit !== 'none' && precision < 1 ? 2 : precision);
            legendItem[key] = set.text + (set.suffix || '');
          }
        });
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
          width: 1
        }
      };
    });
    this.legendData = legendData;
    return tranformSeries;
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
            shadowBlur: 0
          }
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
            shadowBlur: 0
          }
        }
      ]),
      opacity: 0.1
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
        show: false
      }
    };
    return markPoint;
  }
  /**
   * @description: 图表头部工具栏事件
   * @param {IMenuItem} menuItem
   * @return {*}
   */
  handleMenuToolsSelect(menuItem: IMenuItem) {
    const variablesService = new VariablesService({ ...this.viewOptions });
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
        // eslint-disable-next-line no-case-declarations
        const variablesService = new VariablesService({
          ...this.viewOptions.filters,
          ...(this.viewOptions.filters?.current_target || {}),
          ...this.viewOptions,
          ...this.viewOptions.variables,
          interval: reviewInterval(
            this.viewOptions.interval,
            dayjs.tz(endTime).unix() - dayjs.tz(startTime).unix(),
            this.panel.collect_interval
          )
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
      // eslint-disable-next-line no-case-declarations
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
          ...this.viewOptions.variables
        });
        break;
      case 'strategy': // 新增策略
        this.handleAddStrategy(this.panel, null, this.viewOptions, true);
        break;
      case 'drill-down': // 下钻 默认主机
        this.handleDrillDown(menuItem.childValue);
        break;
      case 'relate-alert':
        this.panel?.targets?.forEach(target => {
          if (target.data?.query_configs?.length) {
            let queryConfig = deepClone(target.data.query_configs);
            queryConfig = variablesService.transformVariables(queryConfig);
            target.data.query_configs = queryConfig;
          }
        });
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
        ...this.viewOptions.variables
      },
      false
    );
    const result = targets.map(item => {
      item.data.query_configs = item.data.query_configs.map(query => {
        query.group_by = [id];
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
        this.handleAddStrategy(this.panel, null, this.viewOptions, true);
        break;
      case 1:
        // eslint-disable-next-line max-len
        window.open(location.href.replace(location.hash, `#/strategy-config?metricId=${JSON.stringify(metricIds)}`));
        break;
      case 2:
        // eslint-disable-next-line no-case-declarations
        const eventTargetStr = alarmStatus.targetStr;
        // eslint-disable-next-line max-len
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

  /**
   * 根据图表接口响应数据下载csv文件
   */
  handleExportCsv() {
    if (!!this.series?.length) {
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
    this.handleAddStrategy(this.panel, metric, this.viewOptions);
  }

  /**
   * @description: 点击所有指标
   * @param {*}
   * @return {*}
   */
  handleAllMetricClick() {
    this.handleAddStrategy(this.panel, null, this.viewOptions, true);
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
    data.sort();
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
      // eslint-disable-next-line no-loop-func
      const samp = sampling.reduce((pre, cur) => {
        pre[formattter(cur, precision).text] = 1;
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
      this.legendData.forEach(l => {
        l.show && showNames.push(l.name);
      });
      copyOptions.series = this.seriesList.filter(s => showNames.includes(s.name));
      this.options = Object.freeze({ ...copyOptions });
    };
    if (actionType === 'shift-click') {
      item.show = !item.show;
      setSeriesFilter();
      this.$emit('selectLegend', this.legendData);
    } else if (actionType === 'click') {
      const hasOtherShow = this.legendData.filter(item => !item.hidden).some(set => set.name !== item.name && set.show);
      this.legendData.forEach(legend => {
        legend.show = legend.name === item.name || !hasOtherShow;
      });
      setSeriesFilter();
      this.$emit('selectLegend', this.legendData);
    }
    setTimeout(() => {
      this.handleResize();
    }, 100);
  }

  emitDimensions(series) {
    const dimensionSet = new Set();
    series.forEach(s => {
      if (s.dimensions) {
        Object.keys(s.dimensions).forEach(dKey => {
          dimensionSet.add(dKey);
        });
      }
    });
    this.$emit('dimensionsOfSeries', [...dimensionSet]);
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
            descrition={this.panel.options?.header?.tips || ''}
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

export default ofType<ITimeSeriesProps, ITimeSeriesEvent>().convert(LineChart);
