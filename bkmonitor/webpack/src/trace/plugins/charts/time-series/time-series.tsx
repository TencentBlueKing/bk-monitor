/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { computed, defineComponent, getCurrentInstance, inject, onBeforeUnmount, PropType, Ref, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { bkTooltips } from 'bkui-vue';
import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { debounce } from 'throttle-debounce';

import { CancelToken } from '../../../../monitor-api/index';
import { deepClone, random } from '../../../../monitor-common/utils/utils';
import { COLOR_LIST, COLOR_LIST_BAR, MONITOR_LINE_OPTIONS } from '../../../../monitor-ui/chart-plugins/constants';
import { getValueFormat, ValueFormatter } from '../../../../monitor-ui/monitor-echarts/valueFormats';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { isShadowEqual, reviewInterval, VariablesService } from '../../../utils';
import BaseEchart from '../../base-echart';
import ChartTitle from '../../components/chart-title';
import CommonLegend from '../../components/common-legend';
import TableLegend from '../../components/table-legend';
import {
  useChartIntersection,
  useChartLegend,
  useChartResize,
  useCommonChartWatch,
  useTimeOffsetInject,
  useTimeRanceInject,
  useViewOptionsInject
} from '../../hooks';
import {
  ChartTitleMenuType,
  DataQuery,
  IExtendMetricData,
  ILegendItem,
  IMenuChildItem,
  IMenuItem,
  ITimeSeriesItem,
  ITitleAlarm,
  PanelModel
} from '../../typings';
import {
  downCsvFile,
  handleAddStrategy,
  handleExplore,
  handleRelateAlert,
  handleStoreImage,
  transformSrcData,
  transformTableDataToCsvStr
} from '../../utls/menu';

import './time-series.scss';

const TimeSeriesProps = {
  panel: {
    type: Object as PropType<PanelModel>,
    required: true
  },
  // 是否展示图标头部
  showChartHeader: {
    type: Boolean,
    default: true
  },
  // 是否展示more tools
  showHeaderMoreTool: {
    type: Boolean,
    default: false
  },
  // 自定义时间范围
  customTimeRange: Array as PropType<string[]>,
  // 自定义更多菜单
  customMenuList: Array as PropType<ChartTitleMenuType[]>,
  clearErrorMsg: { default: () => {}, type: Function },
  // 作为单独组件使用 默认用于dashboard
  isUseAlone: {
    type: Boolean,
    default: false
  },
  // 使用自定义tooltips
  customTooltip: {
    type: Object as PropType<Record<string, any>>,
    required: false
  }
};
export default defineComponent({
  name: 'TimeSeries',
  directives: {
    bkTooltips
  },
  props: TimeSeriesProps,
  emits: ['loading', 'errorMsg'],
  setup(props, { emit }) {
    const timeSeriesRef = ref<HTMLDivElement>();
    const chartWrapperRef = ref<HTMLDivElement>();
    const baseChartRef = ref<typeof BaseEchart>();
    const currentInstance = getCurrentInstance();
    const drillDownOptions = ref<IMenuChildItem[]>([]);
    // 宽度
    const width = ref<number>(300);
    // 高度
    const height = ref<number>(100);
    const minBase = ref<number>(0);
    const inited = ref<boolean>(false);
    const empty = ref<boolean>(true);
    const emptyText = ref<string>('');
    const errorMsg = ref<string>('');
    const metrics = ref<IExtendMetricData[]>([]);
    const hasSetEvent = ref<boolean>(false);
    const isInHover = ref<boolean>(false);
    // 图表时序数据
    let csvSeries: any[] = [];
    // 图例数据
    const legendData = ref<ILegendItem[]>([]);
    // 撤销api请求tokens func
    let cancelTokens: Function[] = [];
    // 自动粒度降采样
    const downSampleRange = 'auto';
    const startTime = inject<Ref>('startTime') || ref('');
    const endTime = inject<Ref>('endTime') || ref('');
    const startTimeMinusOneHour = dayjs
      .tz(startTime.value || undefined)
      .subtract(1, 'hour')
      .format('YYYY-MM-DD HH:mm:ss');
    const endTimeMinusOneHour = dayjs
      .tz(endTime.value || undefined)
      .add(1, 'hour')
      .format('YYYY-MM-DD HH:mm:ss');
    const spanDetailActiveTab = inject<Ref>('SpanDetailActiveTab') || ref('');
    // 主机标签页需要特殊处理：因为这里的开始\结束时间是从当前 span 数据的开始时间（-1小时）和结束时间（+1小时）去进行提交、而非直接 inject 时间选择器的时间区间。
    /**
     * 20230807 注意：目前能打开主机标签页的方式有以下两种方式。
     * 1. span 列表打开
     * 2. trace 详情点击瀑布图打开
     */
    const timeRange =
      spanDetailActiveTab.value === 'Host' ? ref([startTimeMinusOneHour, endTimeMinusOneHour]) : useTimeRanceInject();
    const timeOffset = useTimeOffsetInject();
    const viewOptions = useViewOptionsInject();
    const options = ref<echarts.EChartOption>();
    const { t } = useI18n({ useScope: 'global' });

    // datasource为time_series才显示保存到仪表盘，数据检索， 查看大图
    const menuList = computed<ChartTitleMenuType[]>(() => {
      if (props.customMenuList) return props.customMenuList;
      const [target] = props.panel?.targets || [];
      return target?.datasource === 'time_series'
        ? ['more', 'explore', 'area', 'drill-down', 'relate-alert']
        : ['screenshot', 'area'];
    });
    // 是否显示添加指标到策略选项
    const showAddMetric = computed(() => {
      const [target] = props.panel?.targets || [];
      return target?.datasource === 'time_series';
    });
    /* 粒度计算 */
    function downSampleRangeComputed(downSampleRange: string, timeRange: number[], api: string) {
      if (downSampleRange === 'raw' || !['unifyQuery', 'graphUnifyQuery'].includes(api)) {
        return undefined;
      }
      if (downSampleRange === 'auto') {
        let width = 1;
        if (chartWrapperRef.value) {
          width = chartWrapperRef.value.clientWidth;
        } else {
          width = timeSeriesRef.value!.clientWidth - (props.panel?.options?.legend?.placement === 'right' ? 320 : 0);
        }
        const size = (timeRange[1] - timeRange[0]) / width;
        return size > 0 ? `${Math.ceil(size)}s` : undefined;
      }
      return downSampleRange;
    }
    // 转换time_shift显示
    function handleTransformTimeShift(val: string) {
      const timeMatch = val.match(/(-?\d+)(\w+)/);
      const hasMatch = timeMatch && timeMatch.length > 2;
      return hasMatch
        ? dayjs
            .tz()
            .add(-timeMatch[1], timeMatch[2] as dayjs.ManipulateType)
            .fromNow()
            .replace(/\s*/g, '')
        : val.replace('current', t('当前'));
    }
    /** 处理时间对比时线条名字 */
    function handleTimeOffset(timeOffset: string) {
      const match = timeOffset.match(/(current|(\d+)([hdwM]))/);
      if (match) {
        const [target, , num, type] = match;
        const map: any = {
          d: t('{n} 天前', { n: num }),
          w: t('{n} 周前', { n: num }),
          M: t('{n} 月前', { n: num }),
          current: t('当前')
        };
        return map[type || target];
      }
      return timeOffset;
    }
    // 设置series 名称
    function handleSeriesName(item: DataQuery, series: { time_offset?: any; dimensions?: any }) {
      const { dimensions = {} } = series;
      if (!item.alias)
        return series.time_offset ? handleTimeOffset(series.time_offset) : Object.values(dimensions).join('|');
      const aliasFix = Object.values(dimensions).join('|');
      if (!aliasFix.length) return item.alias;
      return `${item.alias}-${aliasFix}`;
    }
    /**
     * @description: 转换时序数据 并设置图例
     * @param {ITimeSeriesItem} series 图表时序数据
     * @return {*}
     */
    function handleTransformSeries(series: ITimeSeriesItem[]) {
      const legendDatas: ILegendItem[] = [];
      const tranformSeries = series.map((item, index) => {
        const colorList = props.panel?.options?.time_series?.type === 'bar' ? COLOR_LIST_BAR : COLOR_LIST;
        const color = item.color || colorList[index % colorList.length];
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
          metricField: item.metricField
        };
        // 动态单位转换
        const unitFormatter = item.unit !== 'none' ? getValueFormat(item.unit || '') : (v: any) => ({ text: v });
        let hasValueLength = 0;
        const data = item.data.map((seriesItem: any, seriesIndex: number) => {
          if (seriesItem?.length && typeof seriesItem[1] === 'number') {
            // 当前点数据
            const pre = item.data[seriesIndex - 1] as [number, number];
            const next = item.data[seriesIndex + 1] as [number, number];
            const y = +seriesItem[1];
            hasValueLength += 1;
            // 设置图例数据
            legendItem.max = Math.max(+legendItem.max!, y);
            legendItem.min = legendItem.min === '' ? y : Math.min(+legendItem.min!, y);
            legendItem.total = +legendItem.total! + y;
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

        legendItem.avg = +(+legendItem.total! / (hasValueLength || 1)).toFixed(2);
        legendItem.total = Number(legendItem.total).toFixed(2);

        if (item.name) {
          Object.keys(legendItem).forEach(key => {
            if (['min', 'max', 'avg', 'total'].includes(key)) {
              const val = (legendItem as any)[key];
              (legendItem as any)[`${key}Source`] = val;
              const set: any = unitFormatter(val, item.unit !== 'none' && precision < 1 ? 2 : precision);
              (legendItem as any)[key] = set.text + (set.suffix || '');
            }
          });
          legendDatas.push(legendItem);
        }
        // 获取y轴上可设置的最小的精确度
        const precision = handleGetMinPrecision(
          item.data.filter((set: any) => typeof set[1] === 'number').map((set: any[]) => set[1]),
          unitFormatter,
          item.unit
        );
        return {
          ...item,
          color,
          type: props.panel?.options?.time_series?.type || 'line',
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
      legendData.value = legendDatas;
      return tranformSeries;
    }
    // 设置x轴label formatter方法
    function handleSetFormatterFunc(seriesData: any, onlyBeginEnd = false) {
      let formatterFunc = null;
      const [firstItem] = seriesData;
      const lastItem = seriesData[seriesData.length - 1];
      const val = new Date('2010-01-01').getTime();
      const getXVal = (timeVal: any) => {
        if (!val) return val;
        return timeVal[0] > val ? timeVal[0] : timeVal[1];
      };
      const minX = Array.isArray(firstItem) ? getXVal(firstItem) : getXVal(firstItem?.value);
      const maxX = Array.isArray(lastItem) ? getXVal(lastItem) : getXVal(lastItem?.value);
      minX &&
        maxX &&
        (formatterFunc = (v: any) => {
          const duration = dayjs.duration(dayjs.tz(maxX).diff(dayjs.tz(minX))).asSeconds();
          if (onlyBeginEnd && v > minX && v < maxX) {
            return '';
          }
          if (duration < 60 * 60 * 24 * 2) {
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
     * @description: 设置精确度
     * @param {number} data
     * @param {ValueFormatter} formattter
     * @param {string} unit
     * @return {*}
     */
    function handleGetMinPrecision(data: number[], formattter: ValueFormatter, unit: string) {
      if (!data || data.length === 0) {
        return 0;
      }
      data.sort();
      const len = data.length;
      if (data[0] === data[len - 1]) {
        if (unit === 'none') return 0;
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
          // eslint-disable-next-line no-param-reassign
          (pre as any)[formattter(cur, precision).text] = 1;
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
     * @description: 在图表数据没有单位或者单位不一致时则不做单位转换 y轴label的转换用此方法做计数简化
     * @param {number} num
     * @return {*}
     */
    function handleYxisLabelFormatter(num: number): string {
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
    function dataZoom(startTime: string, endTime: string) {
      // this.isCustomTimeRange
      //   ? this.$emit('dataZoom', startTime, endTime)
      //   : this.getPanelData(startTime, endTime);
      getPanelData(startTime, endTime);
    }
    /** 处理点击左侧响铃图标 跳转策略的逻辑 */
    function handleAlarmClick(alarmStatus: ITitleAlarm) {
      const metricIds = metrics.value.map(item => item.metric_id);
      switch (alarmStatus.status) {
        case 0:
          // this.handleAddStrategy(props.panel, null, viewOptions?.value, true);
          break;
        case 1:
          // eslint-disable-next-line max-len
          window.open(location.href.replace(location.hash, `#/strategy-config?metricId=${JSON.stringify(metricIds)}`));
          break;
        case 2:
          window.open(
            location.href.replace(
              location.hash,
              `#/event-center?queryString=${metricIds.map(item => `metric : "${item}"`).join(' AND ')}&from=${timeRange
                ?.value[0]}&to=${timeRange?.value[1]}`
            )
          );
          break;
      }
    }
    // 获取图表数据
    const getPanelData = debounce(300, async (start_time?: string, end_time?: string) => {
      cancelTokens.forEach(cb => cb?.());
      cancelTokens = [];
      if (!isInViewPort()) {
        if (intersectionObserver) {
          unregisterOberver();
        }
        registerObserver(start_time, end_time);
        return;
      }
      emit('loading', true);
      emptyText.value = t('加载中...');
      try {
        unregisterOberver();
        const series: any[] = [];
        const metricList: any[] = [];
        const [startTime, endTime] = handleTransformToTimestamp(timeRange!.value);
        const params = {
          start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
          end_time: end_time ? dayjs.tz(end_time).unix() : endTime
        };
        const promiseList: any[] = [];
        const timeShiftList = ['', ...timeOffset!.value];
        const interval = reviewInterval(
          viewOptions!.value.interval || 0,
          params.end_time - params.start_time,
          props.panel!.collect_interval
        );
        const variablesService = new VariablesService({
          ...viewOptions?.value,
          interval
        });
        timeShiftList.forEach(time_shift => {
          const list =
            props.panel?.targets?.map?.(item => {
              const newPrarams = {
                ...variablesService.transformVariables(item.data, {
                  ...viewOptions?.value.filters,
                  ...(viewOptions?.value.filters?.current_target || {}),
                  ...viewOptions?.value,
                  ...viewOptions?.value.variables,
                  time_shift,
                  interval
                }),
                ...params,
                down_sample_range: downSampleRangeComputed(
                  downSampleRange,
                  [params.start_time, params.end_time],
                  item.apiFunc
                )
              };
              // eslint-disable-next-line array-callback-return
              if (!item.apiModule) return;
              return currentInstance?.appContext.config.globalProperties?.$api[item.apiModule]
                [item.apiFunc](newPrarams, {
                  cancelToken: new CancelToken((cb: Function) => cancelTokens.push(cb)),
                  needMessage: false
                })
                .then((res: { metrics: any; series: any[] }) => {
                  res.metrics?.forEach((metric: { metric_id: string }) => {
                    if (!metricList.some(set => set.metric_id === metric.metric_id)) {
                      metricList.push(metric);
                    }
                  });
                  series.push(
                    ...res.series.map(set => ({
                      ...set,
                      name: `${
                        timeOffset?.value.length
                          ? `${handleTransformTimeShift((time_shift as string) || 'current')}-`
                          : ''
                      }${handleSeriesName(item, set) || set.target}`
                    }))
                  );
                  handleClearErrorMsg();
                  return true;
                })
                .catch(error => {
                  handleErrorMsgChange(error.msg || error.message);
                });
            }) ?? [];
          promiseList.push(...(list as any));
        });
        await Promise.all(promiseList).catch(() => false);
        if (series.length) {
          csvSeries = series;
          const seriesResult = series
            .filter(item => ['extra_info', '_result_'].includes(item.alias))
            .map(item => ({
              ...item,
              datapoints: item.datapoints.map((point: any[]) => [
                JSON.parse(point[0])?.anomaly_score ?? point[0],
                point[1]
              ])
            }));
          let seriesList = handleTransformSeries(
            seriesResult.map(item => ({
              name: item.name,
              cursor: 'auto',
              data: item.datapoints.reduce((pre: any, cur: any) => (pre.push(cur.reverse()), pre), []),
              stack: item.stack || random(10),
              unit: item.unit,
              z: 1,
              traceData: item.trace_data ?? ''
            })) as any
          );
          seriesList = seriesList.map((item: any) => ({
            ...item,
            minBase: minBase.value,
            data: item.data.map((set: any) => {
              if (set?.length) {
                return [set[0], set[1] !== null ? set[1] + minBase.value : null];
              }
              return {
                ...set,
                value: [set.value[0], set.value[1] !== null ? set.value[1] + minBase.value : null]
              };
            })
          }));
          // 1、echarts animation 配置会影响数量大时的图表性能 掉帧
          // 2、echarts animation配置为false时 对于有孤立点不连续的图表无法放大 并且 hover的点放大效果会潇洒 (貌似echarts bug)
          // 所以此处折中设置 在有孤立点情况下进行开启animation 连续的情况不开启
          const hasShowSymbol = seriesList.some(item => item.showSymbol);
          if (hasShowSymbol) {
            seriesList.forEach(item => {
              // eslint-disable-next-line no-param-reassign
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
          const formatterFunc = handleSetFormatterFunc(seriesList[0].data);
          // const { canScale, minThreshold, maxThreshold } = this.handleSetThreholds();
          // eslint-disable-next-line max-len
          const chartBaseOptions = MONITOR_LINE_OPTIONS;
          // eslint-disable-next-line max-len
          const echartOptions = deepmerge(
            deepClone(chartBaseOptions),
            props.panel?.options?.time_series?.echart_option || {},
            { arrayMerge: (_, newArr) => newArr }
          ) as echarts.EChartOption<echarts.EChartOption.Series>;
          options.value = Object.freeze(
            deepmerge(echartOptions, {
              animation: hasShowSymbol,
              color: props.panel?.options?.time_series?.type === 'bar' ? COLOR_LIST_BAR : COLOR_LIST,
              animationThreshold: 1,
              yAxis: {
                axisLabel: {
                  formatter: seriesList.every((item: any) => item.unit === seriesList[0].unit)
                    ? (v: any) => {
                        if (seriesList[0].unit !== 'none') {
                          const obj = getValueFormat(seriesList[0].unit)(v, seriesList[0].precision);
                          return obj.text + (obj.suffix || '');
                        }
                        return v;
                      }
                    : (v: number) => handleYxisLabelFormatter(v - minBase.value)
                },
                splitNumber: height.value < 120 ? 2 : 4,
                minInterval: 1,
                scale: !(height.value < 120)
                // max: v => Math.max(v.max, +maxThreshold),
                // min: v => Math.min(v.min, +minThreshold)
              },
              xAxis: {
                axisLabel: {
                  formatter: formatterFunc || '{value}'
                },
                splitNumber: Math.ceil(width.value / 80),
                min: 'dataMin'
              },
              series: seriesList,
              tooltip: props.customTooltip ?? {}
            })
          );
          metrics.value = metricList || [];
          // this.handleDrillDownOption(this.metrics);
          inited.value = true;
          empty.value = false;
          if (!hasSetEvent.value) {
            setTimeout(useLegendRet.handleSetLegendEvent, 500);
            hasSetEvent.value = true;
          }
        } else {
          emptyText.value = t('查无数据');
          empty.value = true;
        }
      } catch (e) {
        empty.value = true;
        emptyText.value = t('出错了');
        console.error(e);
      }
      emit('loading', false);
      // this.cancelTokens = [];
      // this.handleLoadingChange(false);
    });
    // 监听panel
    const unWathPanel = watch(
      () => props.panel,
      (v, o) => {
        if (v && o && isShadowEqual(v, o)) return;
        getPanelData();
      }
    );
    // 监听上层注入
    const unWathChartData = useCommonChartWatch(getPanelData);
    // 监听resize
    const { handleResize } = useChartResize(
      timeSeriesRef as Ref<HTMLDivElement>,
      chartWrapperRef as Ref<HTMLDivElement>,
      width,
      height
    );
    // 监听是否在可视窗口内
    const { isInViewPort, registerObserver, unregisterOberver, intersectionObserver } = useChartIntersection(
      timeSeriesRef! as Ref<HTMLDivElement>,
      getPanelData
    );
    // 通用图表图例设置
    const useLegendRet = useChartLegend(baseChartRef, isInHover, legendData);

    onBeforeUnmount(() => {
      unWathPanel();
      useLegendRet.handleUnSetLegendEvent();
    });
    function handleMenuClick(item: IMenuItem) {
      const variablesService = new VariablesService({ ...viewOptions });
      switch (item.id) {
        case 'explore':
          handleExplore(props.panel!, viewOptions!.value, timeRange!.value);
          return;
        case 'relate-alert':
          props.panel?.targets?.forEach(target => {
            if (target.data?.query_configs?.length) {
              let queryConfig = deepClone(target.data.query_configs);
              queryConfig = variablesService.transformVariables(queryConfig);
              // eslint-disable-next-line no-param-reassign
              target.data.query_configs = queryConfig;
            }
          });
          handleRelateAlert(props.panel!, timeRange!.value);
          return;
        case 'screenshot':
          // 300ms 关闭动画
          setTimeout(() => handleStoreImage(props.panel!.title, timeSeriesRef.value!), 300);
          return;
        case 'export-csv':
          {
            if (csvSeries.length) {
              const { tableThArr, tableTdArr } = transformSrcData(csvSeries);
              const csvString = transformTableDataToCsvStr(tableThArr, tableTdArr);
              downCsvFile(csvString, props.panel!.title);
            }
          }
          return;
      }
    }
    function handleMetricClick(metric: IExtendMetricData | null) {
      handleAddStrategy(props.panel!, metric, viewOptions!.value, timeRange!.value);
    }
    function handleDblClick() {
      getPanelData();
    }
    function handleErrorMsgChange(message: string) {
      props.isUseAlone ? (errorMsg.value = message) : emit('errorMsg', message);
    }
    function handleClearErrorMsg() {
      props.isUseAlone ? (errorMsg.value = '') : props.clearErrorMsg();
    }
    return {
      ...unWathChartData,
      ...useLegendRet,
      baseChartRef,
      width,
      height,
      csvSeries,
      menuList,
      metrics,
      isInHover,
      drillDownOptions,
      showAddMetric,
      getPanelData,
      unWathPanel,
      timeSeriesRef,
      chartWrapperRef,
      handleResize,
      isInViewPort,
      registerObserver,
      unregisterOberver,
      minBase,
      inited,
      empty,
      emptyText,
      errorMsg,
      hasSetEvent,
      legendData,
      cancelTokens,
      timeRange,
      timeOffset,
      viewOptions,
      options,
      t,
      downSampleRangeComputed,
      handleTransformTimeShift,
      handleTimeOffset,
      handleSeriesName,
      handleTransformSeries,
      handleYxisLabelFormatter,
      handleSetFormatterFunc,
      handleGetMinPrecision,
      dataZoom,
      handleAlarmClick,
      handleMenuClick,
      handleMetricClick,
      handleDblClick
    };
  },
  render() {
    const { legend } = this.panel?.options || {};
    return (
      <div
        ref='timeSeriesRef'
        onMouseenter={() => (this.isInHover = true)}
        onMouseleave={() => (this.isInHover = false)}
        class='time-series'
      >
        {this.showChartHeader && this.panel && (
          <ChartTitle
            class='draggable-handle'
            title={this.panel.title}
            showMore={this.isInHover}
            menuList={this.menuList}
            drillDownOption={this.drillDownOptions}
            showAddMetric={this.showAddMetric}
            draging={this.panel.draging}
            metrics={this.metrics}
            subtitle={this.panel.subTitle || ''}
            isInstant={this.panel.instant}
            onMenuClick={this.handleMenuClick}
            onAlarmClick={this.handleAlarmClick}
            onMetricClick={this.handleMetricClick}
            onAllMetricClick={this.handleMetricClick}
            onSelectChild={({ child }) => this.handleMenuClick(child)}
            onUpdateDragging={() => this.panel?.updateDraging(false)}
          />
        )}
        {!this.empty ? (
          <div class={`time-series-content ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
            <div
              class={`chart-instance ${legend?.displayMode === 'table' ? 'is-table-legend' : ''}`}
              ref='chartWrapperRef'
            >
              {this.inited && (
                <BaseEchart
                  ref='baseChartRef'
                  height={this.height}
                  width={this.width}
                  options={this.options}
                  groupId={this.panel!.dashboardId}
                  onDataZoom={this.getPanelData}
                  onDblClick={this.handleDblClick}
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
                  <CommonLegend
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
        {!!this.errorMsg && (
          <span
            class='is-error'
            v-bk-tooltips={{
              content: <div>{this.errorMsg}</div>,
              extCls: 'chart-wrapper-error-tooltip',
              placement: 'top-start'
            }}
          ></span>
        )}
      </div>
    );
  }
});
