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
import { Component, Mixins, Prop, Watch, InjectReactive } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { toPng } from 'html-to-image';
import { CancelToken } from 'monitor-api/index';
import { graphUnifyQuery } from 'monitor-api/modules/grafana';
import { Debounce, deepClone, random } from 'monitor-common/utils/utils';
import { generateFormatterFunc, handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import {
  downCsvFile,
  transformSrcData,
  transformTableDataToCsvStr,
  type IUnifyQuerySeriesItem,
} from 'monitor-pc/pages/view-detail/utils';
import ChartHeader from 'monitor-ui/chart-plugins/components/chart-title/chart-title';
import ListLegend from 'monitor-ui/chart-plugins/components/chart-legend/common-legend';
import { COLOR_LIST, COLOR_LIST_BAR, MONITOR_LINE_OPTIONS } from 'monitor-ui/chart-plugins/constants';
import StatusTab from 'monitor-ui/chart-plugins/plugins/apm-custom-graph/status-tab';
import CommonSimpleChart from 'monitor-ui/chart-plugins/plugins/common-simple-chart';
import BaseEchart from 'monitor-ui/chart-plugins/plugins/monitor-base-echart';
import { downFile, handleRelateAlert, reviewInterval } from 'monitor-ui/chart-plugins/utils';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from 'monitor-ui/chart-plugins/utils/axis';
import { VariablesService } from 'monitor-ui/chart-plugins/utils/variable';
import { type ValueFormatter, getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import { metricData } from './mock-data';
import { timeToDayNum, handleSetFormatterFunc, handleYxisLabelFormatter, handleTimeOffset } from './utils';

import type {
  DataQuery,
  ILegendItem,
  ITimeSeriesItem,
  PanelModel,
  ZrClickEvent,
} from 'monitor-ui/chart-plugins/typings';

import './metric-chart.scss';
const APM_CUSTOM_METHODS = ['SUM', 'AVG', 'MAX', 'MIN', 'INC'];

interface INewMetricChartProps {
  chartHeight?: number;
  isToolIconShow?: boolean;
  panel?: PanelModel;
  isShowLegend?: boolean;
}
interface INewMetricChartEvents {
  onMenuClick?: () => void;
  onDrillDown?: () => void;
  onLegendData?: (list: ILegendItem[], loading: boolean) => void;
}
/** 图表 - 曲线图 */
@Component
class NewMetricChart extends CommonSimpleChart {
  @Prop({ default: 300 }) chartHeight: number;
  @Prop({ default: true }) isToolIconShow: boolean;
  /** 是否展示图例 */
  @Prop({ default: false }) isShowLegend: boolean;
  // yAxis是否需要展示单位
  @InjectReactive('yAxisNeedUnit') readonly yAxisNeedUnit: boolean;
  methodList = APM_CUSTOM_METHODS.map(method => ({
    id: method,
    name: method,
  }));
  customScopedVars: Record<string, any> = {};
  width = 300;
  init = false;
  metrics = metricData;
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
  method = 'SUM';
  loading = false;
  /** 导出csv数据时候使用 */
  series: IUnifyQuerySeriesItem[];
  // 图例排序
  legendSorts: { name: string; timeShift: string }[] = [];
  // 切换图例时使用
  seriesList = null;
  minBase = 0;
  get yAxisNeedUnitGetter() {
    return this.yAxisNeedUnit ?? true;
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
    return ['save', 'explore', 'drill-down', 'relate-alert', 'screenshot'];
  }
  /** 拉伸的时候图表重新渲染 */
  @Watch('chartHeight')
  handleHeightChange() {
    this.handleResize();
  }
  /** 重新拉取数据 */
  @Watch('panel', { deep: true })
  handlePanelChange() {
    this.getPanelData();
  }
  /** 切换计算的Method */
  handleMethodChange(method: (typeof APM_CUSTOM_METHODS)[number]) {
    this.method = method;
    this.customScopedVars = {
      method,
    };
    this.getPanelData();
  }
  removeTrailingZeros(num) {
    if (num && num !== '0') {
      return num
        .toString()
        .replace(/(\.\d*?)0+$/, '$1')
        .replace(/\.$/, '');
    }
    return num;
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
        latest: 0,
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
      let latestVal = 0;
      let latestInd = 0;
      const data = item.data.map((seriesItem: any, seriesIndex: number) => {
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
      legendItem.latest = item.data[latestInd][1];

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
        result.push(lItem);
      }
    }
    this.legendData = result;
    return tranformSeries;
  }
  handleSeriesName(item: DataQuery, set) {
    const { dimensions = {}, dimensions_translation = {} } = set;
    if (!item.alias)
      return set.time_offset
        ? handleTimeOffset(set.time_offset)
        : Object.values({
            ...dimensions,
            ...dimensions_translation,
          }).join('|');
    const aliasFix = Object.values(dimensions).join('|');
    if (!aliasFix.length) return item.alias;
    return `${item.alias}-${aliasFix}`;
  }
  /**
   * @description: 获取图表数据
   */
  @Debounce(100)
  async getPanelData(start_time?: string, end_time?: string) {
    this.legendData = [];
    this.legendSorts = [];
    this.init = false;
    this.cancelTokens.forEach(cb => cb?.());
    this.cancelTokens = [];
    if (!this.isInViewPort()) {
      if (this.intersectionObserver) {
        this.unregisterOberver();
      }
      this.registerObserver();
      return;
    }
    this.formatterFunc = generateFormatterFunc(this.timeRange);
    if (this.init) this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    this.loading = true;
    try {
      this.unregisterOberver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const series = [];
      const metrics = [];
      let params = {
        // start_time: start_time ? dayjs(start_time).unix() : startTime,
        // end_time: end_time ? dayjs(end_time).unix() : endTime,
        start_time: 1740567339,
        end_time: 1740567839,
      };
      const promiseList = [];
      const variablesService = new VariablesService({
        ...this.viewOptions,
        ...this.customScopedVars,
      });
      const list = this.panel.targets.map(item => {
        (item?.query_configs || []).map(config => {
          config.metrics.map(metric => (metric.method = this.method));
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
                  // const name = this.handleSeriesName(item, set) || set.target;
                  const name = set.target;
                  this.legendSorts.push({
                    name,
                    timeShift: '1d',
                  });
                  return {
                    ...set,
                    name,
                  };
                })
              );
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
      if (series.length) {
        console.log(series, 'series');
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
        const formatterFunc = handleSetFormatterFunc(formatData);

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
                        return this.removeTrailingZeros(obj.text) + (this.yAxisNeedUnitGetter ? obj.suffix : '');
                      }
                      return v;
                    }
                  : (v: number) => handleYxisLabelFormatter(v - this.minBase),
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
            },
            customData: {
              // customData 自定义的一些配置 用户后面echarts实例化后的配置
              maxXInterval,
              maxSeriesCount,
            },
          })
        );
        // this.handleDrillDownOption(this.metrics);
        console.log('option', this.options, this.legendData.length);
        this.init = true;
        this.empty = false;
        setTimeout(() => {
          this.handleResize();
        }, 100);
      } else {
        this.init = this.metrics.length > 0;
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
    console.log('====');
    const el = targetEl || (this.$el as HTMLElement);
    return toPng(el)
      .then(dataUrl => {
        if (customSave) return dataUrl;
        downFile(dataUrl, `${title}.png`);
      })
      .catch(() => {});
  }
  getCopyPanel() {
    return JSON.parse(JSON.stringify(this.panel));
  }
  /** 工具栏各个icon的操作 */
  handleIconClick(menuItem) {
    console.log(menuItem?.id, '1====');
    switch (menuItem.id) {
      /** 维度下钻 */
      case 'drillDown':
        this.$emit('drillDown', this.panel);
        break;
      // 保存到仪表盘
      case 'save':
        this.handleCollectChart();
        break;
      case 'screenshot': // 保存到本地
        setTimeout(() => {
          this.handleStoreImage(this.panel.title || '测试');
        }, 300);
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
  render() {
    return (
      <div class='new-metric-chart'>
        <ChartHeader
          collectIntervalDisplay={this.collectIntervalDisplay}
          customArea={true}
          // draging={this.panel.draging}
          isHoverShow={true}
          // isInstant={this.panel.instant}
          menuList={this.menuList as any}
          metrics={this.metrics}
          needMoreMenu={true}
          showMore={true}
          subtitle={this.panel.sub_title || ''}
          title={this.panel.title}
          onMenuClick={this.handleIconClick}
        >
          <span class='status-tab-view'>
            <StatusTab
              maxWidth={this.width - 300}
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
              {this.handleIconList.map(item => (
                <i
                  key={item.id}
                  class={`icon-monitor ${item.icon} menu-list-icon`}
                  v-bk-tooltips={{
                    content: this.$t(item.text),
                    delay: 200,
                  }}
                  onClick={() => this.handleIconClick(item)}
                ></i>
              ))}
            </span>
          )}
        </ChartHeader>
        {!this.empty ? (
          <div class='new-metric-chart-content'>
            <div
              ref='chart'
              class='chart-instance'
            >
              {this.init ? (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.chartHeight}
                  groupId={this.panel.dashboardId}
                  options={this.options}
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
