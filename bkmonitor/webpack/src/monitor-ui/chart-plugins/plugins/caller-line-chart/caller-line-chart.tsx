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

import { Component, Emit, InjectReactive, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { CancelToken } from 'monitor-api/index';
import { Debounce, deepClone, random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { type ValueFormatter, getValueFormat } from '../../../monitor-echarts/valueFormats';
import ListLegend from '../../components/chart-legend/common-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { COLOR_LIST, COLOR_LIST_BAR, MONITOR_LINE_OPTIONS } from '../../constants';
import { reviewInterval } from '../../utils';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from '../../utils/axis';
import { VariablesService } from '../../utils/variable';
import { CommonSimpleChart } from '../common-simple-chart';
import BaseEchart from '../monitor-base-echart';

import type {
  DataQuery,
  IExtendMetricData,
  ILegendItem,
  IMenuChildItem,
  ITimeSeriesItem,
  PanelModel,
  ZrClickEvent,
} from '../../../chart-plugins/typings';
import type { CallOptions } from '../apm-service-caller-callee/type';
import type { IUnifyQuerySeriesItem } from 'monitor-pc/pages/view-detail/utils';

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

@Component
class CallerLineChart extends CommonSimpleChart {
  // 当前粒度
  @InjectReactive('downSampleRange') readonly downSampleRange: number | string;
  // yAxis是否需要展示单位
  @InjectReactive('yAxisNeedUnit') readonly yAxisNeedUnit: boolean;
  @InjectReactive('callOptions') readonly callOptions: CallOptions;

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

  get yAxisNeedUnitGetter() {
    return this.yAxisNeedUnit ?? true;
  }
  // 同时hover显示多个tooltip
  get hoverAllTooltips() {
    return this.panel.options?.time_series?.hoverAllTooltips;
  }

  // 是否允许对比
  get isSupportCompare() {
    return this.panel.options?.is_support_compare === undefined ? true : this.panel.options.is_support_compare;
  }

  // 是否允许自定groupBy
  get isSupportGroupBy() {
    return !!this.panel.options?.is_support_group_by;
  }

  @Watch('callOptions')
  onCallOptionsChange() {
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
        if (key !== 'time_shift') {
          callOptions[key] = this.callOptions[key];
        }
      }
      const variablesService = new VariablesService({
        ...this.viewOptions,
        ...callOptions,
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
          const newParams = {
            ...variablesService.transformVariables(
              dataFormat({ ...item.data }),
              {
                ...this.viewOptions.filters,
                ...(this.viewOptions.filters?.current_target || {}),
                ...this.viewOptions,
                ...this.viewOptions.variables,
                ...this.callOptions,
                time_shift: timeShiftFormat(time_shift),
              },
              noTransformVariables
            ),
            ...params,
            down_sample_range,
          };
          if (this.callOptions?.call_filter?.length) {
            const callFilter = this.callOptions?.call_filter.filter(f => f.key !== 'time');
            for (const item of newParams?.query_configs || []) {
              item.where = [...(item?.where || []), ...callFilter];
            }
            for (const item of newParams?.unify_query_param?.query_configs || []) {
              item.where = [...(item?.where || []), ...callFilter];
            }
            if (newParams?.group_by_limit?.where) {
              newParams.group_by_limit.where = [...newParams.group_by_limit.where, ...callFilter];
            }
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
                    name: `${this.callOptions.time_shift?.length ? `${this.handleTransformTimeShift(time_shift || 'current')}-` : ''}${
                      this.handleSeriesName(item, set) || set.target
                    }`,
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
                        return obj.text + (this.yAxisNeedUnitGetter ? obj.suffix : '');
                      }
                      return v;
                    }
                  : (v: number) => this.handleYxisLabelFormatter(v - this.minBase),
              },
              splitNumber: this.height < 120 ? 2 : 4,
              minInterval: 1,
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
      console.error(e);
    }
    this.cancelTokens = [];
    this.handleLoadingChange(false);
  }

  // 转换time_shift显示
  handleTransformTimeShift(val: string) {
    const timeMatch = val.match(/(-?\d+)(\w+)/);
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    const hasMatch = timeMatch && timeMatch.length > 2;
    if (dateRegex.test(val)) {
      return val;
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
        precision,
        lineStyle: {
          width: 1,
        },
      };
    });
    this.legendData = legendData;
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
  render() {
    return (
      <div class='apm-caller-line-chart'>
        <ChartHeader
          collectIntervalDisplay={this.collectIntervalDisplay}
          descrition={this.panel.descrition}
          draging={this.panel.draging}
          isInstant={this.panel.instant}
          metrics={this.metrics}
          needMoreMenu={false}
          showAddMetric={false}
          showMore={true}
          subtitle={this.panel.subTitle || ''}
          title={this.panel.title}
        />
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
