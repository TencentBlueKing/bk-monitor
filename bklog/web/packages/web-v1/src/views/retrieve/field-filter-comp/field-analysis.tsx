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

import axios from 'axios';
import dayjs from 'dayjs';
import * as echarts from 'echarts';
import { cloneDeep } from 'lodash-es';

import $http from '../../../api';
import { formatNumberWithRegex } from '../../../common/util';
import { lineOrBarOptions, pillarChartOption } from '../../../components/monitor-echarts/options/echart-options-config';
import { lineColor } from '../../../store/constant';
import store from '@/store';

import './field-analysis.scss';
const CancelToken = axios.CancelToken;

const timeSeriesBase = {
  lineStyle: {
    width: 1,
  },
  transitionDuration: 750, // 动画响应毫秒数
  type: 'line',
  symbol: 'circle', // 设置数据点的形状
  symbolSize: 1, // 设置数据点的初始大小
  itemStyle: {
    borderWidth: 2,
    enabled: true,
    shadowBlur: 0,
    opacity: 1,
  },
};

/** 柱状图基础高度 */
const PILLAR_CHART_BASE_HEIGHT = 236;
/** 柱状图英文情况下的基础高度 */
const PILLAR_CHART_EN_BASE_HEIGHT = 220;
/** 折线图图基础高度 */
const LINE_CHART_BASE_HEIGHT = 270;
/** 柱状图图高度盒子 保证图表出来后popover总高度不变 */
const PILLAR_CHART_BOX_HEIGHT = 264;
/** 折线图高度盒子 保证图表出来后popover总高度不变 */
const LINE_CHART_BOX_HEIGHT = 348;
/** 折线图分页的高度 */
const LEGEND_BOX_HEIGHT = 40;
let formatStr = 'HH:mm';
type LegendActionType = 'click' | 'shift-click';

@Component
export default class FieldAnalysis extends Vue {
  @Prop({ type: Object, default: () => ({}) }) readonly queryParams: any;
  @Ref('fieldChart') readonly chartRef!: HTMLDivElement;
  @Ref('commonLegend') readonly commonLegendRef!: HTMLDivElement;

  chart = null;
  /** 图表高度 */
  height = 0;
  /** 图例数据 */
  legendData = [];
  /** 所有的分组数据 */
  seriesData = [];
  /** 当前页 */
  currentPageNum = 1;
  /** 所有页 */
  legendMaxPageNum = 1;
  infoLoading = false;
  chartLoading = false;
  /** 是否无数据 展示空数据 */
  isShowEmpty = false;
  /** 是否展示分页ICON */
  isShowPageIcon = false;
  /** 错误提示字符串 */
  emptyTipsStr = '';
  emptyStr = window.mainComponent.$t('暂无数据');
  lineOptions = {};
  pillarOption = {};

  /** 基础信息数据 */
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
  /** 是否显示柱状图 是否是数字类型字段 */
  get isPillarChart() {
    return ['integer', 'long', 'double'].includes(this.queryParams?.field_type);
  }

  /** 获取数值类型查询时间段 */
  get getPillarQueryTime() {
    const { start_time: startTime, end_time: endTime } = this.queryParams;
    if (startTime && endTime && this.isPillarChart) {
      const pillarFormatStr = 'YYYY-MM-DD HH:mm:ss';
      return `${window.mainComponent.$t('查询时段')}: ${dayjs(startTime).format(pillarFormatStr)} - ${dayjs(endTime).format(pillarFormatStr)}`;
    }
    return '';
  }

  get pillarChartHeight() {
    return store.getters.isEnLanguage ? PILLAR_CHART_EN_BASE_HEIGHT : PILLAR_CHART_BASE_HEIGHT;
  }

  @Watch('currentPageNum')
  watchPageNum(v: number) {
    this.commonLegendRef.scrollTo({
      top: (v - 1) * LEGEND_BOX_HEIGHT,
    });
  }

  @Emit('statisticsInfoFinish')
  statisticsInfoFinish() {
    return true;
  }

  mounted() {
    this.$nextTick(async () => {
      if (!this.isPillarChart) {
        const { start_time: startTime, end_time: endTime } = this.queryParams;
        this.setFormatStr(startTime, endTime);
      }
      await this.queryStatisticsInfo();
      await this.queryStatisticsGraph();
      this.initFieldChart();
    });
  }

  beforeDestroy() {
    this.getInfoCancelFn();
    this.getChartsCancelFn();
    this.commonLegendRef?.removeEventListener('wheel', this.legendWheel);
  }

  async queryStatisticsInfo() {
    try {
      this.infoLoading = true;
      this.chartLoading = true;
      const res = await $http.request(
        'retrieve/fieldStatisticsInfo',
        {
          data: {
            ...this.queryParams,
          },
        },
        {
          cancelToken: new CancelToken(c => {
            this.getInfoCancelFn = c;
          }),
        },
      );
      Object.assign(this.fieldData, res.data);
    } finally {
      this.infoLoading = false;
    }
  }
  /** 图表请求 */
  async queryStatisticsGraph() {
    try {
      const data = {
        ...this.queryParams,
      };
      if (this.isPillarChart) {
        Object.assign(data, {
          distinct_count: this.fieldData.distinct_count,
          max: this.fieldData.value_analysis.max,
          min: this.fieldData.value_analysis.min,
        });
      }
      const res = await $http.request(
        'retrieve/fieldStatisticsGraph',
        {
          data,
        },
        {
          catchIsShowMessage: false,
          cancelToken: new CancelToken(c => {
            this.getChartsCancelFn = c;
          }),
        },
      );
      this.isShowEmpty = false;
      // 分折线图和柱状图显示
      if (this.isPillarChart) {
        this.height = this.pillarChartHeight;
        const resData = res.data;
        if (!resData.length) {
          this.isShowEmpty = true;
          return;
        }
        const xAxisData = resData.map((item, index) => {
          // 去重小于10 直接展示单个
          if (this.fieldData.distinct_count < 10) {
            return item[0];
          }
          // 去重大于10 所有的值都是范围 最大的数字范围是info的max
          if (index === resData.length - 1) {
            return `${item[0]} - ${this.fieldData.value_analysis.max}`;
          }
          return `${item[0]} - ${resData[index + 1][0]}`;
        });
        const pillarInterval = Math.round(xAxisData.length / 2) - 1;
        this.pillarOption = cloneDeep(pillarChartOption);
        // 柱状图初始化
        Object.assign(this.pillarOption, {
          tooltip: {
            trigger: 'axis',
            transitionDuration: 0,
            axisPointer: {
              type: 'line',
              lineStyle: {
                type: 'dashed',
              },
            },
            backgroundColor: 'rgba(0,0,0,0.8)',
            formatter: p => this.handleSetPillarTooltip(p),
            position: this.handleSetPosition,
          },
          xAxis: {
            ...pillarChartOption.xAxis,
            axisLabel: {
              color: '#979BA5',
              interval: pillarInterval,
              showMaxLabel: true,
              formatter: value => {
                if (value.length > 18) {
                  return `${value.slice(0, 18)}...`;
                } // 只显示前18个字符
                return value;
              },
            },
            data: xAxisData,
          },
          series: [
            {
              data: res.data.map(item => item[1]),
              type: 'bar',
              itemStyle: {
                color: '#689DF3',
              },
            },
          ],
        });
      } else {
        const seriesData = res.data.series;
        if (!seriesData.length) {
          this.isShowEmpty = true;
          return;
        }
        this.height = LINE_CHART_BASE_HEIGHT;
        const series: any[] = [];
        seriesData.forEach((el, index) => {
          series.push({
            ...timeSeriesBase,
            smooth: true,
            areaStyle: {
              // 透明度 80是0.5  00是0
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: `${lineColor[index]}80` }, // 顶部颜色
                { offset: 1, color: `${lineColor[index]}00` }, // 底部颜色
              ]),
            },
            name: el.group_values[0],
            data: el.values,
            z: 999,
          });
        });
        this.seriesData = series;
        this.legendData = series.map((item, index) => ({
          color: lineColor[index],
          name: item.name,
          show: true,
        }));
        // 收集所有时间戳
        const allTimestamps = series.reduce((acc, seriesItem) => {
          return acc.concat(seriesItem.data.map(item => item[0]));
        }, []);

        // 找到最小和最大时间戳
        const minTimestamp = Math.min.apply(null, allTimestamps);
        const maxTimestamp = Math.max.apply(null, allTimestamps);
        const {
          xAxis: { minInterval: _minInterval, splitNumber: _splitNumber, ...resetxAxis },
        } = lineOrBarOptions;
        this.lineOptions = cloneDeep(lineOrBarOptions);
        Object.assign(this.lineOptions, {
          useUTC: false,
          tooltip: {
            trigger: 'axis',
            axisPointer: {
              type: 'line',
              lineStyle: {
                type: 'dashed',
              },
            },
            backgroundColor: 'rgba(0,0,0,0.8)',
            transitionDuration: 0,
            appendTo: () => document.body,
            formatter: p => this.handleSetTimeTooltip(p),
            position: this.handleSetPosition,
          },
          color: lineColor,
          xAxis: {
            ...resetxAxis,
            axisLabel: {
              color: '#979BA5',
              boundaryGap: false,
              // showMinLabel: false,
              // showMaxLabel: false,
              fontSize: 12,
              formatter: value => {
                return dayjs.tz(value).format(formatStr);
              },
              interval: index => {
                // 控制显示的刻度数量
                return index % 2 === 0; // 每两个刻度点显示一个
              },
            },
            scale: false,
            min: minTimestamp,
            max: maxTimestamp,
          },
          yAxis: {
            ...lineOrBarOptions.yAxis,
            axisLine: {
              show: false,
            },
          },
          legend: [],
          series,
        });

        this.$nextTick(() => {
          const comLegRef = this.commonLegendRef;
          this.isShowPageIcon = comLegRef.scrollHeight > comLegRef.clientHeight;
          if (this.isShowPageIcon) {
            comLegRef.addEventListener('wheel', this.legendWheel);
            this.legendMaxPageNum = Math.ceil(comLegRef.scrollHeight / LEGEND_BOX_HEIGHT);
          }
        });
      }
    } catch (error) {
      this.isShowEmpty = true;
      this.emptyTipsStr = error.message;
      this.emptyStr = window.mainComponent.$t('查询异常');
    } finally {
      this.statisticsInfoFinish();
      this.chartLoading = false;
    }
  }

  /** 设置时间戳时间显示格式 与检索趋势图保持一致 */
  setFormatStr(start: number, end: number) {
    if (!(start && end)) {
      return;
    }
    const differenceInHours = Math.abs(start - end) / (60 * 60);
    if (differenceInHours <= 48) {
      formatStr = 'HH:mm';
    } else if (differenceInHours > 48 && differenceInHours <= 168) {
      formatStr = 'MM-DD HH:mm';
    } else if (differenceInHours > 168) {
      formatStr = 'MM-DD';
    }
  }

  initFieldChart() {
    if (this.isShowEmpty) {
      return;
    }
    const chart: any = echarts.init(this.chartRef, null, {
      height: `${this.height}px`,
    });
    const getInitChartOption = this.isPillarChart ? this.pillarOption : this.lineOptions;
    chart?.setOption(getInitChartOption);
    this.chart = chart;
    this.chart.resize();
  }

  /** 设置时间戳类型Tooltips */
  handleSetTimeTooltip(params) {
    const liHtmls = params
      .sort((a, b) => b.value[1] - a.value[1])
      .map(item => {
        /** 折线图tooltips不能使用纯CSS来处理换行 会有宽度贴图表边缘变小问题 字符串添加换行倍数为85 */
        return `<li class="tooltips-content-item">
                  <span class="item-series" style="background-color:${item.color};"></span>
                  <span class="item-name is-warp">${item.seriesName.replace(/(.{85})(?=.{85})/g, '$1\n')}:</span>
                  <div class="item-value-box is-warp">
                    <span class="item-value">${formatNumberWithRegex(item.value[1])}</span>
                  </div>
                </li>`;
      });
    const pointTime = dayjs.tz(params[0].axisValue).format('YYYY-MM-DD HH:mm:ss');
    return `<div id="monitor-chart-tooltips">
        <p class="tooltips-header">
            ${pointTime}
        </p>
        <ul class="tooltips-content">
            ${liHtmls?.join('')}
        </ul>
      </div>`;
  }

  /** 设置柱状图类型Tooltips */
  handleSetPillarTooltip(params) {
    return `<div id="monitor-chart-tooltips">
      <ul class="tooltips-content">
        <li class="tooltips-content-item" style="align-items: center;">
          <span class="item-name" style="color: #fff;font-weight: bold;">${params[0].axisValue}:</span>
          <div class="item-value-box">
            <span class="item-value"  style="color: #fff;font-weight: bold;">${params[0].value}</span>
          </div>
        </li>
      </ul>
    </div>`;
  }
  /** 设置定位 */
  handleSetPosition(pos: number[], _params: any, _dom: any, _rect: any, size: any) {
    const { contentSize } = size;
    const chartRect = this.chartRef.getBoundingClientRect();
    const posRect = {
      x: chartRect.x + +pos[0],
      y: chartRect.y + +pos[1],
    };
    const position = {
      left: 0,
      top: 0,
    };
    const canSetBottom = window.innerHeight - posRect.y - contentSize[1];
    if (canSetBottom > 0) {
      position.top = +pos[1] - Math.min(20, canSetBottom);
    } else {
      position.top = +pos[1] + canSetBottom - 20;
    }
    const canSetLeft = window.innerWidth - posRect.x - contentSize[0];

    position.left = +pos[0] + Math.min(20, canSetLeft);

    return position;
  }

  /** 点击分组 */
  handleLegendEvent(e: MouseEvent, actionType: LegendActionType, item) {
    if (this.legendData.length < 2) {
      return;
    }
    let eventType = actionType;
    if (e.shiftKey && actionType === 'click') {
      eventType = 'shift-click';
    }
    if (eventType === 'shift-click') {
      item.show = !item.show;
    } else if (eventType === 'click') {
      const hasOtherShow = this.legendData.some(set => set.name !== item.name && set.show);
      for (const legend of this.legendData) {
        legend.show = legend.name === item.name || !hasOtherShow;
      }
    }
    const showSeriesName = this.legendData.filter(legend => legend.show).map(leItem => leItem.name);
    const showSeries = this.seriesData.filter(sItem => showSeriesName.includes(sItem.name));
    const options = this.chart.getOption();
    const showColor = this.legendData.filter(legend => legend.show).map(lItem => lItem.color);

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
    setTimeout(() => {
      this.chart.resize();
    }, 100);
  }

  getChartsCancelFn() {}
  getInfoCancelFn() {}

  legendWheel(event: WheelEvent) {
    event.preventDefault();
    // 根据 event.deltaY 判断滚动方向
    if (event.deltaY < 0) {
      // 向上滚动
      if (this.currentPageNum > 1) {
        this.currentPageNum -= 1;
      }
    } else if (this.currentPageNum < this.legendMaxPageNum) {
      // 向下滚动
      this.currentPageNum += 1;
    }
  }

  render() {
    return (
      <div class='field-analysis-container'>
        <div v-bkloading={{ isLoading: this.infoLoading }}>
          <div class='total-num-container'>
            <span class='total-num'>
              {window.mainComponent.$t('总行数')} : {formatNumberWithRegex(this.fieldData.total_count)}
            </span>
            <span
              class='appear-num'
              v-bk-tooltips={{ content: window.mainComponent.$t('字段在该事件范围内有数据的日志条数') }}
            >
              {window.mainComponent.$t('出现行数')} : {formatNumberWithRegex(this.fieldData.field_count)}
            </span>
          </div>
          <div class='log-num-container'>
            <div
              class='num-box'
              v-bk-tooltips={{
                content: window.mainComponent.$t('计算规则：出现行数/总行数。若该值不为100%，该字段存在空值。'),
              }}
            >
              <span class='num-val'>
                <span class='log-num'>{this.fieldData.field_percent * 100}</span>
                <span class='log-unit'>%</span>
              </span>
              <span class='log-str'>{window.mainComponent.$t('日志条数')}</span>
            </div>
            <div class='num-box'>
              <span class='num-val'>
                <span class='log-num'>{formatNumberWithRegex(this.fieldData.distinct_count)}</span>
                <span class='log-unit'>{window.mainComponent.$t('条')}</span>
              </span>
              <span class='log-str'>{window.mainComponent.$t('去重后条数')}</span>
            </div>
          </div>
          {this.isPillarChart && (
            <div class='number-num-container'>
              <div class='num-box'>
                <span class='num-key'>{window.mainComponent.$t('最大值')}</span>
                <span class='num-val'>{formatNumberWithRegex(this.fieldData.value_analysis.max)}</span>
              </div>
              <div class='num-box'>
                <span class='num-key'>{window.mainComponent.$t('最小值')}</span>
                <span class='num-val'>{formatNumberWithRegex(this.fieldData.value_analysis.min)}</span>
              </div>
              <div class='num-box'>
                <span class='num-key'>{window.mainComponent.$t('平均值')}</span>
                <span class='num-val'>{formatNumberWithRegex(this.fieldData.value_analysis.avg)}</span>
              </div>
              <div class='num-box'>
                <span class='num-key'>{window.mainComponent.$t('中位数')}</span>
                <span class='num-val'>{formatNumberWithRegex(this.fieldData.value_analysis.median)}</span>
              </div>
            </div>
          )}
        </div>
        <div
          style={{
            height: this.isPillarChart ? `${PILLAR_CHART_BOX_HEIGHT}px` : `${LINE_CHART_BOX_HEIGHT}px`,
            alignItems: 'center',
          }}
          v-bkloading={{ isLoading: this.chartLoading }}
        >
          {this.isShowEmpty ? (
            <div class='not-data-empty'>
              <bk-exception
                scene='part'
                type={this.emptyTipsStr ? '500' : 'empty'}
              >
                <div style={{ marginTop: '10px' }}>
                  <span>{this.emptyStr}</span>
                  {!!this.emptyTipsStr && (
                    <i
                      class='bk-icon icon-exclamation-circle'
                      v-bk-tooltips={{
                        content: this.emptyTipsStr,
                      }}
                    />
                  )}
                </div>
              </bk-exception>
            </div>
          ) : (
            <div>
              <div class='chart-title'>
                <span>
                  {this.isPillarChart
                    ? window.mainComponent.$t('数值分布直方图')
                    : `TOP 5 ${window.mainComponent.$t('时序图')}`}
                </span>
                <span>{this.getPillarQueryTime}</span>
              </div>
              <div
                ref='fieldChart'
                style={{ width: '100%', height: `${this.height}px` }}
              />
              {!this.isPillarChart && (
                <div
                  style={{ height: `${LEGEND_BOX_HEIGHT}px` }}
                  class='legend-box'
                >
                  <div
                    ref='commonLegend'
                    class='common-legend'
                  >
                    {this.legendData.map((legend, index) => {
                      return (
                        <div
                          key={`${index}-${legend}`}
                          class='common-legend-item'
                          title={legend.name}
                          onClick={e => this.handleLegendEvent(e, 'click', legend)}
                        >
                          <span
                            style={{ backgroundColor: legend.show ? legend.color : '#ccc' }}
                            class='legend-icon'
                          />
                          <div
                            style={{ color: legend.show ? '#63656e' : '#ccc' }}
                            class='legend-name title-overflow'
                          >
                            {legend.name}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {this.isShowPageIcon && (
                    <div class='legend-icon-box'>
                      <i
                        class={{
                          'bk-select-angle bk-icon icon-angle-up-fill last-page-up': true,
                          disabled: this.currentPageNum === 1,
                        }}
                        onClick={() => {
                          if (this.currentPageNum > 1) {
                            this.currentPageNum -= 1;
                          }
                        }}
                      />
                      <i
                        class={{
                          'bk-select-angle bk-icon icon-angle-up-fill': true,
                          disabled: this.currentPageNum === this.legendMaxPageNum,
                        }}
                        onClick={() => {
                          if (this.currentPageNum < this.legendMaxPageNum) {
                            this.currentPageNum += 1;
                          }
                        }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }
}
