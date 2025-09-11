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

import { Component, Prop, Ref, Vue, Emit, Watch } from 'vue-property-decorator';

import ChartSkeleton from '@/skeleton/chart-skeleton';
import ItemSkeleton from '@/skeleton/item-skeleton';
import axios from 'axios';
import dayjs from 'dayjs';

import $http from '../../../api';
import { formatNumberWithRegex } from '../../../common/util';
import { lineOrBarOptions, pillarChartOption } from '../../../components/monitor-echarts/options/echart-options-config';
import { lineColor } from '../../../store/constant';
import AggChart from './agg-chart';
import store from '@/store';

import './field-analysis.scss';

const CancelToken = axios.CancelToken;

// 提取为常量
const TIME_SERIES_BASE = {
  lineStyle: { width: 1 },
  transitionDuration: 750,
  type: 'line',
  symbol: 'circle',
  symbolSize: 1,
  itemStyle: {
    borderWidth: 2,
    enabled: true,
    shadowBlur: 0,
    opacity: 1,
  },
};

const CHART_HEIGHTS = {
  PILLAR_BASE: 140,
  PILLAR_EN_BASE: 130,
  LINE_BASE: 140,
  PILLAR_BOX: 264,
  LINE_BOX: 460,
  LEGEND_BOX: 40,
};
type LegendActionType = 'click' | 'shift-click';

@Component
export default class FieldAnalysis extends Vue {
  @Prop({ type: Object, default: () => ({}) }) readonly queryParams: any;
  @Ref('fieldChart') readonly chartRef!: HTMLDivElement;
  @Ref('commonLegend') readonly commonLegendRef!: HTMLDivElement;
  // 图表位置
  chartRect: DOMRect | null = null;
  // echarts实例
  echarts: any = null;
  chart: echarts.ECharts | null = null;
  height = 0;
  legendData: Array<{ color: string; name: string; show: boolean }> = [];
  seriesData: any[] = [];
  currentPageNum = 1;
  legendMaxPageNum = 1;
  infoLoading = false;
  chartLoading = false;
  isShowEmpty = false;
  isShowPageIcon = false;
  emptyTipsStr = '';
  emptyStr = window.mainComponent.$t('暂无数据');
  lineOptions = {};
  pillarOption = {};
  formatStr = 'HH:mm';
  splitNumber = 5;

  fieldData = {
    total_count: 0,
    field_count: 0,
    distinct_count: 0,
    field_percent: 0,
    value_analysis: {
      avg: 0,
      max: 0,
      median: 0,
      min: 0,
    },
  };

  totalConfig = [
    { key: 'max', label: '最大值' },
    { key: 'min', label: '最小值' },
    { key: 'avg', label: '平均值' },
    { key: 'median', label: '中位数' },
  ];

  route = window.mainComponent.$route;
  ifShowMore = false;

  /** 是否显示柱状图 是否是数字类型字段 */
  get isPillarChart() {
    return ['integer', 'long', 'double'].includes(this.queryParams?.field_type);
  }

  get pillarChartHeight() {
    return store.getters.isEnLanguage ? CHART_HEIGHTS.PILLAR_EN_BASE : CHART_HEIGHTS.PILLAR_BASE;
  }

  /** 获取数值类型查询时间段 */
  get pillarQueryTime() {
    const { start_time: startTime, end_time: endTime } = this.queryParams;
    if (startTime && endTime && this.isPillarChart) {
      const pillarFormatStr = 'YYYY-MM-DD HH:mm:ss';
      return `${window.mainComponent.$t('查询时段')}: ${dayjs(startTime).format(pillarFormatStr)} - ${dayjs(endTime).format(pillarFormatStr)}`;
    }
    return '';
  }

  // 图表标题
  get chartTitle() {
    return this.isPillarChart
      ? window.mainComponent.$t('数值分布直方图')
      : `TOP 5 ${window.mainComponent.$t('时序图')}`;
  }

  @Watch('currentPageNum')
  watchPageNum(v: number) {
    if (this.commonLegendRef) {
      this.commonLegendRef.scrollTo({ top: (v - 1) * CHART_HEIGHTS.LEGEND_BOX });
    }
  }

  @Emit('statisticsInfoFinish')
  statisticsInfoFinish() {
    return true;
  }

  @Emit('downloadFieldStatistics')
  downloadFieldStatistics() {
    return true;
  }

  mounted() {
    this.initializeComponent();
  }

  // 初始化逻辑封装
  async initializeComponent() {
    await this.$nextTick();

    if (!this.isPillarChart) {
      const { start_time: startTime, end_time: endTime } = this.queryParams;
      this.setFormatStr(startTime, endTime);
    }

    // 优化：并行执行数据请求
    await Promise.all([this.queryStatisticsInfo(), this.loadEChartsLibrary()]);

    await this.queryStatisticsGraph();
    this.initFieldChart();
    this.showMore(false);
  }

  beforeDestroy() {
    this.cleanupResources();
  }

  // 资源清理封装
  cleanupResources() {
    this.getInfoCancelFn?.();
    this.getChartsCancelFn?.();

    if (this.commonLegendRef) {
      this.commonLegendRef.removeEventListener('wheel', this.legendWheel);
    }

    if (this.chart) {
      this.chart.dispose();
      this.chart = null;
    }
  }

  // 异步加载ECharts
  async loadEChartsLibrary() {
    if (!this.echarts) {
      this.echarts = await import('echarts');
    }
    return this.echarts;
  }

  async queryStatisticsInfo() {
    try {
      this.infoLoading = true;
      this.chartLoading = true;

      const res = await $http.request(
        'retrieve/fieldStatisticsInfo',
        { data: { ...this.queryParams } },
        { cancelToken: new CancelToken(c => (this.getInfoCancelFn = c)) },
      );

      Object.assign(this.fieldData, res.data);
    } finally {
      this.infoLoading = false;
    }
  }

  // 图表请求
  async queryStatisticsGraph() {
    try {
      const data = { ...this.queryParams };

      if (this.isPillarChart) {
        Object.assign(data, {
          distinct_count: this.fieldData.distinct_count,
          max: this.fieldData.value_analysis.max,
          min: this.fieldData.value_analysis.min,
        });
      }

      const res = await $http.request(
        'retrieve/fieldStatisticsGraph',
        { data },
        {
          catchIsShowMessage: false,
          cancelToken: new CancelToken(c => (this.getChartsCancelFn = c)),
        },
      );

      this.isShowEmpty = false;
      // 分折线图和柱状图显示

      if (this.isPillarChart) {
        this.processPillarChartData(res);
      } else {
        await this.processLineChartData(res);
      }
    } catch (error) {
      this.isShowEmpty = true;
      this.emptyTipsStr = error.message || window.mainComponent.$t('查询失败');
      this.emptyStr = window.mainComponent.$t('查询异常');
    } finally {
      this.statisticsInfoFinish();
      this.chartLoading = false;
    }
  }

  // 处理柱状图数据
  processPillarChartData(res: any) {
    this.height = this.pillarChartHeight;
    const resData = res.data;

    if (!resData.length) {
      this.isShowEmpty = true;
      return;
    }

    const xAxisData = resData.map((item: [number, number], index: number) => {
      if (this.fieldData.distinct_count < 10) {
        return item[0].toString();
      }

      return index === resData.length - 1
        ? `${item[0]} - ${this.fieldData.value_analysis.max}`
        : `${item[0]} - ${resData[index + 1][0]}`;
    });

    const pillarInterval = Math.max(1, Math.round(xAxisData.length / 2) - 1);
    this.pillarOption = { ...pillarChartOption };

    Object.assign(this.pillarOption, {
      tooltip: {
        trigger: 'axis',
        appendToBody: true,
        transitionDuration: 0,
        axisPointer: { type: 'line', lineStyle: { type: 'dashed' } },
        backgroundColor: 'rgba(0,0,0,0.8)',
        formatter: (p: any) => this.handleSetPillarTooltip(p),
        position: this.handleSetPosition,
      },
      xAxis: {
        ...pillarChartOption.xAxis,
        splitNumber: this.splitNumber,
        axisLabel: {
          color: '#979BA5',
          interval: pillarInterval,
          showMaxLabel: true,
          formatter: (value: string) => (value.length > 18 ? `${value.slice(0, 18)}...` : value),
        },
        data: xAxisData,
      },
      series: [
        {
          data: resData.map((item: [number, number]) => item[1]),
          type: 'bar',
          itemStyle: { color: '#689DF3' },
        },
      ],
    });
  }

  // 处理折线图数据
  async processLineChartData(res: any) {
    const seriesData = res.data.series;

    if (!seriesData.length) {
      this.isShowEmpty = true;
      return;
    }

    this.height = CHART_HEIGHTS.LINE_BASE;
    const series = [];
    const echarts = this.echarts || (await this.loadEChartsLibrary());

    seriesData.forEach((el: any, index: number) => {
      const color = lineColor[index % lineColor.length];

      series.push({
        ...TIME_SERIES_BASE,
        smooth: true,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: `${color}80` },
            { offset: 1, color: `${color}00` },
          ]),
        },
        name: el.group_values[0],
        data: el.values,
        z: 999,
      });
    });

    this.seriesData = series;
    this.legendData = series.map((item, index) => ({
      color: lineColor[index % lineColor.length],
      name: item.name,
      show: true,
    }));
    // 收集所有时间戳

    const allTimestamps = series.flatMap(s => s.data.map((d: [number, number]) => d[0]));
    const minTimestamp = Math.min(...allTimestamps);
    const maxTimestamp = Math.max(...allTimestamps);

    const {
      xAxis: { minInterval, splitNumber, ...resetxAxis },
    } = lineOrBarOptions;
    this.lineOptions = { ...lineOrBarOptions };

    Object.assign(this.lineOptions, {
      useUTC: false,
      tooltip: {
        trigger: 'axis',
        appendToBody: true,
        axisPointer: { type: 'line', lineStyle: { type: 'dashed' } },
        backgroundColor: 'rgba(0,0,0,0.8)',
        transitionDuration: 0,
        appendTo: document.body,
        formatter: (p: any) => this.handleSetTimeTooltip(p),
        position: this.handleSetPosition,
      },
      color: lineColor,
      xAxis: {
        ...resetxAxis,
        splitNumber: this.splitNumber,
        axisLabel: {
          color: '#979BA5',
          boundaryGap: false,
          fontSize: 11,
          formatter: (value: number) => dayjs.tz(value).format(this.formatStr),
          interval: 0,
        },
        scale: false,
        min: minTimestamp,
        max: maxTimestamp,
      },
      yAxis: {
        ...lineOrBarOptions.yAxis,
        axisLine: { show: false },
      },
      legend: [],
      series,
    });
    this.$nextTick(() => {
      if (this.commonLegendRef) {
        this.isShowPageIcon = this.commonLegendRef.scrollHeight > this.commonLegendRef.clientHeight;

        if (this.isShowPageIcon) {
          this.commonLegendRef.addEventListener('wheel', this.legendWheel);
          this.legendMaxPageNum = Math.ceil(this.commonLegendRef.scrollHeight / CHART_HEIGHTS.LEGEND_BOX);
        }
      }
    });
  }

  setFormatStr(start: number, end: number) {
    if (!start || !end) return;

    const differenceInHours = Math.abs(start - end) / 3600000;

    if (differenceInHours <= 24) {
      this.formatStr = 'HH:mm';
    } else if (differenceInHours > 24 && differenceInHours <= 168) {
      this.formatStr = 'MM-DD HH:mm';
      this.splitNumber = 4;
    } else {
      this.formatStr = 'MM-DD';
    }
  }

  async initFieldChart() {
    if (this.isShowEmpty || !this.chartRef) return;

    try {
      // 清理旧图表实例
      if (this.chart) {
        this.chart.dispose();
        this.chart = null;
      }

      const echarts = this.echarts || (await this.loadEChartsLibrary());

      this.chart = echarts.init(this.chartRef, null, {
        height: `${this.height}px`,
        renderer: 'canvas', // 明确指定渲染器
      });

      const getInitChartOption = this.isPillarChart ? this.pillarOption : this.lineOptions;
      this.chart.setOption(getInitChartOption);

      // 添加窗口大小变化监听
      window.addEventListener('resize', this.handleResize);
    } catch (error) {
      console.error('ECharts initialization failed:', error);
    }
  }

  // 添加防抖的resize处理
  handleResize = () => {
    if (this.chart) {
      this.chart.resize();
    }
  };

  handleSetTimeTooltip(params: any[]) {
    const sortedParams = [...params].sort((a, b) => b.value[1] - a.value[1]);
    const liHtmls = sortedParams.map(item => {
      const formattedName = item.seriesName.replace(/(.{85})(?=.{85})/g, '$1\n');
      const formattedValue = formatNumberWithRegex(item.value[1]);
      /** 折线图tooltips不能使用纯CSS来处理换行 会有宽度贴图表边缘变小问题 字符串添加换行倍数为85 */

      return `<li class="tooltips-content-item">
                <span class="item-series" style="background-color:${item.color};"></span>
                <span class="item-name is-warp">${formattedName}:</span>
                <div class="item-value-box is-warp">
                  <span class="item-value">${formattedValue}</span>
                </div>
              </li>`;
    });

    const pointTime = dayjs.tz(params[0].axisValue).format('YYYY-MM-DD HH:mm:ss');

    return `<div id="monitor-chart-tooltips">
        <p class="tooltips-header">${pointTime}</p>
        <ul class="tooltips-content">${liHtmls.join('')}</ul>
      </div>`;
  }

  handleSetPillarTooltip(params: any) {
    return `<div id="monitor-chart-tooltips">
      <ul class="tooltips-content">
        <li class="tooltips-content-item" style="align-items: center;">
          <span class="item-name" style="color: #fff;font-weight: bold;">${params[0].axisValue}:</span>
          <div class="item-value-box">
            <span class="item-value" style="color: #fff;font-weight: bold;">${params[0].value}</span>
          </div>
        </li>
      </ul>
    </div>`;
  }
  /** 设置定位 */

  handleSetPosition(pos: [number, number], params: any, dom: any, rect: any, size: any) {
    if (!this.chartRect) {
      this.chartRect = this.chartRef.getBoundingClientRect();
    }

    const posX = this.chartRect.x + pos[0];
    const posY = this.chartRect.y + pos[1];
    const { contentSize } = size;
    const position = { left: 0, top: 0 };

    const canSetBottom = window.innerHeight - posY - contentSize[1];
    position.top = canSetBottom > 0 ? pos[1] - Math.min(20, canSetBottom) : pos[1] + canSetBottom - 20;

    const canSetLeft = window.innerWidth - posX - contentSize[0];
    position.left = pos[0] + Math.min(20, canSetLeft);

    return position;
  }
  /** 点击分组 */
  handleLegendEvent(e: MouseEvent, actionType: LegendActionType, item: any) {
    if (this.legendData.length < 2) return;

    const eventType = e.shiftKey && actionType === 'click' ? 'shift-click' : actionType;

    const newLegendData = [...this.legendData];
    const itemIndex = newLegendData.findIndex(legend => legend.name === item.name);

    if (itemIndex === -1) return;

    if (eventType === 'shift-click') {
      newLegendData[itemIndex].show = !newLegendData[itemIndex].show;
    } else if (eventType === 'click') {
      const hasOtherShow = newLegendData.some((legend, idx) => idx !== itemIndex && legend.show);

      newLegendData.forEach((legend, idx) => {
        legend.show = idx === itemIndex || !hasOtherShow;
      });
    }

    this.legendData = newLegendData;

    const showSeriesName = newLegendData.filter(legend => legend.show).map(legend => legend.name);

    const showSeries = this.seriesData.filter(series => showSeriesName.includes(series.name));

    const showColor = newLegendData.filter(legend => legend.show).map(legend => legend.color);

    if (this.chart) {
      const options = this.chart.getOption();

      this.chart.setOption(
        {
          ...options,
          color: showColor,
          series: showSeries,
        },
        {
          notMerge: true,
          lazyUpdate: false,
          silent: true,
        },
      );

      // 使用requestAnimationFrame优化重绘
      requestAnimationFrame(() => {
        if (this.chart) {
          this.chart.resize();
        }
      });
    }
  }

  getChartsCancelFn = () => {};
  getInfoCancelFn = () => {};

  // 添加防抖处理
  legendWheel = (event: WheelEvent) => {
    event.preventDefault();

    if (event.deltaY < 0) {
      this.currentPageNum = Math.max(1, this.currentPageNum - 1);
    } else {
      this.currentPageNum = Math.min(this.legendMaxPageNum, this.currentPageNum + 1);
    }
  };

  showMore(show: boolean) {
    this.ifShowMore = !!show;
    this.$emit('showMore', this.fieldData, !!show);
  }

  render() {
    const {
      isPillarChart,
      fieldData,
      infoLoading,
      chartLoading,
      isShowEmpty,
      emptyTipsStr,
      emptyStr,
      totalConfig,
      height,
      legendData,
      currentPageNum,
      legendMaxPageNum,
      isShowPageIcon,
      chartTitle,
      pillarQueryTime,
    } = this;

    // const distinctCount = formatNumberWithRegex(fieldData.distinct_count);
    const fieldPercent = (fieldData.field_percent * 100).toFixed(2);

    return (
      <div
        class={[
          'retrieve-v2 field-analysis-container',
          {
            'is-no-data': isShowEmpty,
          },
        ]}
      >
        <div>
          <div class='total-num-container'>
            <span class='total-num'>
              {window.mainComponent.$t('总行数')} : {formatNumberWithRegex(fieldData.total_count)}
            </span>
            <span
              class='appear-num'
              v-bk-tooltips={{ content: window.mainComponent.$t('字段在该事件范围内有数据的日志条数') }}
            >
              {window.mainComponent.$t('出现行数')} : {formatNumberWithRegex(fieldData.field_count)}
            </span>
            <span
              class='appear-num'
              v-bk-tooltips={{ content: window.mainComponent.$t('字段在该事件范围内有数据的日志条数') }}
            >
              {window.mainComponent.$t('日志条数')} : {fieldPercent}
              <span class='log-unit'>%</span>
            </span>
          </div>

          {isPillarChart && (
            <div>
              {infoLoading ? (
                <ItemSkeleton
                  columns={2}
                  rowHeight={'22px'}
                  rows={2}
                  widths={['50%', '50%']}
                />
              ) : (
                <div class='number-num-container'>
                  {totalConfig.map(item => (
                    <div
                      key={item.key}
                      class='num-box'
                    >
                      <span class='num-key'>{window.mainComponent.$t(item.label)}</span>
                      <span class='num-val'>{formatNumberWithRegex(fieldData.value_analysis[item.key] || 0)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div
          style={{
            maxHeight: isPillarChart ? `${CHART_HEIGHTS.PILLAR_BOX}px` : `${CHART_HEIGHTS.LINE_BOX}px`,
            alignItems: 'center',
          }}
        >
          {isShowEmpty ? (
            <div class='not-data-empty'>
              <bk-exception
                scene='part'
                type={emptyTipsStr ? '500' : 'empty'}
              >
                <div style={{ marginTop: '10px' }}>
                  <span>{emptyStr}</span>
                  {emptyTipsStr && (
                    <i
                      class='bk-icon icon-exclamation-circle'
                      v-bk-tooltips={{ content: emptyTipsStr }}
                    ></i>
                  )}
                </div>
              </bk-exception>
            </div>
          ) : (
            <div>
              <div class='chart-title'>
                <span style={{ color: '#313238', fontSize: '14px' }}>{chartTitle}</span>
                <span class='chart-title-time'>{pillarQueryTime}</span>
              </div>

              {chartLoading ? (
                <ChartSkeleton type={isPillarChart ? 'bar' : 'line'} />
              ) : (
                <div
                  ref='fieldChart'
                  style={{ width: '100%', height: `${height}px` }}
                />
              )}

              {!chartLoading && !isPillarChart && (
                <div
                  style={{ height: `${CHART_HEIGHTS.LEGEND_BOX}px` }}
                  class='legend-box'
                >
                  <div
                    ref='commonLegend'
                    class='common-legend'
                  >
                    {legendData.map((legend, index) => (
                      <div
                        key={index}
                        class='common-legend-item'
                        title={legend.name}
                        onClick={e => this.handleLegendEvent(e, 'click', legend)}
                      >
                        <span
                          style={{ backgroundColor: legend.show ? legend.color : '#ccc' }}
                          class='legend-icon'
                        ></span>
                        <div
                          style={{ color: legend.show ? '#63656e' : '#ccc' }}
                          class='legend-name title-overflow'
                        >
                          {legend.name}
                        </div>
                      </div>
                    ))}
                  </div>

                  {isShowPageIcon && (
                    <div class='legend-icon-box'>
                      <i
                        class={{
                          'bk-select-angle bk-icon icon-angle-up-fill last-page-up': true,
                          disabled: currentPageNum === 1,
                        }}
                        onClick={() => (this.currentPageNum = Math.max(1, currentPageNum - 1))}
                      ></i>
                      <i
                        class={{
                          'bk-select-angle bk-icon icon-angle-up-fill': true,
                          disabled: currentPageNum === legendMaxPageNum,
                        }}
                        onClick={() => (this.currentPageNum = Math.min(legendMaxPageNum, currentPageNum + 1))}
                      ></i>
                    </div>
                  )}
                </div>
              )}

              <div class='distinct-count-num-box'>
                <div class='count-num'>
                  <span class='count-num-title'>{window.mainComponent.$t('去重后字段统计')}</span>
                </div>
                <div class='more-fn'>
                  {!chartLoading && fieldData.distinct_count > 5 && (
                    <span
                      class='more-distinct'
                      onClick={() => this.showMore(true)}
                    >
                      {window.mainComponent.$t('查看全部')}
                    </span>
                  )}
                  <span
                    class='fn-btn bk-icon icon-download'
                    v-bk-tooltips={window.mainComponent.$t('下载')}
                    onClick={this.downloadFieldStatistics}
                  ></span>
                  {/* <span
                    class='fn-btn bk-icon icon-apps'
                    v-bk-tooltips='查看仪表盘'
                  ></span> */}
                </div>
              </div>

              {this.queryParams.agg_field && (
                <AggChart
                  colorList={lineColor}
                  field-name={this.queryParams.agg_field}
                  field-type={this.queryParams.field_type}
                  is-front-statistics={this.queryParams.isFrontStatistics}
                  parent-expand={true}
                  retrieve-params={this.queryParams}
                  statistical-field-data={this.queryParams.statisticalFieldData}
                />
              )}
            </div>
          )}
        </div>
      </div>
    );
  }
}
