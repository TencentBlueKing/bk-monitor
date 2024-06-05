/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component, Prop, Ref, Vue, Emit, Watch } from 'vue-property-decorator';
import $http from '../../../api';
import { lineColor } from '../../../store/constant';
import './field-analysis.scss';
import dayjs from 'dayjs';
import axios from 'axios';
import EmptyStatus from '../../../components/empty-status';
const CancelToken = axios.CancelToken;

const timeSeriesBase = {
  lineStyle: {
    width: 1
  },
  type: 'line',
  symbol: 'circle', // 设置数据点的形状
  symbolSize: 1, // 设置数据点的初始大小
  itemStyle: {
    borderWidth: 2,
    enabled: true,
    shadowBlur: 0,
    opacity: 1
  }
};

/** 柱状图基础高度 */
const PILLAR_CHART_BASE_HEIGHT = 236;
/** 折线图图基础高度 */
const LINE_CHART_BASE_HEIGHT = 270;
/** 折线图分页的高度 */
const LEGEND_BOX_HEIGHT = 40;
let formatStr = 'HH:mm';
type LegendActionType = 'click' | 'shift-click';

@Component
export default class FieldAnalysis extends Vue {
  @Prop({ type: Object, default: () => ({}) }) private readonly queryParams: any;
  @Ref('fieldChart') private readonly chartRef!: HTMLDivElement;
  @Ref('commonLegend') private readonly commonLegendRef!: HTMLDivElement;

  chart = null;
  /** 图表高度 */
  height = PILLAR_CHART_BASE_HEIGHT;
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

  /** 折线图数据 */
  lineChartOption = {
    useUTC: false,
    animationThreshold: 2000,
    animationDurationUpdate: 0,
    animationDuration: 20,
    animationDelay: 300,
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
        lineStyle: {
          type: 'dashed'
        }
      },
      formatter: p => this.handleSetTimeTooltip(p),
      position: this.handleSetPosition
    },
    color: lineColor,
    legend: {
      itemWidth: 10,
      itemHeight: 10,
      padding: 0,
      bottom: 0,
      icon: 'rect',
      textStyle: {
        fontSize: 12
      },
      formatter: name => {
        // 限制显示文本的长度
        return name.length > 10 ? `${name.slice(0, 10)}...` : name;
      },
      tooltip: {
        show: true
      },
      data: []
    },
    grid: {
      left: 0,
      right: 30,
      top: 10,
      bottom: 0,
      containLabel: true,
      backgroundColor: 'transparent'
    },
    xAxis: {
      axisLine: {
        show: false
      },
      axisTick: {
        show: false
      },
      axisLabel: {
        color: '#979BA5',
        boundaryGap: false,
        showMinLabel: false,
        showMaxLabel: false,
        // rotate: -30,
        fontSize: 12,
        formatter: value => {
          return dayjs.tz(value).format(formatStr);
        }
      },
      splitLine: {
        show: false
      },
      type: 'time'
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#979BA5'
      },
      axisLine: {
        show: false
      },
      axisTick: {
        show: false
      },
      splitLine: {
        lineStyle: {
          type: 'dashed',
          color: '#F0F1F5'
        },
        show: true
      }
    },
    series: []
  };

  /** 柱状图数据 */
  pillarChartOption = {
    tooltip: {
      trigger: 'axis',
      formatter: p => this.handleSetPillarTooltip(p),
      position: this.handleSetPosition
    },
    xAxis: {
      axisLine: {
        show: false
      },
      axisTick: {
        show: false
      },
      axisLabel: {
        color: '#979BA5',
        interval: 3,
        formatter: value => {
          if (value.length > 18) return `${value.slice(0, 18)}...`; // 只显示前18个字符
          return value;
        }
      },
      type: 'category',
      data: []
    },
    yAxis: {
      type: 'value',
      axisTick: {
        show: false
      },
      axisLine: {
        show: false
      },
      splitLine: {
        lineStyle: {
          type: 'dashed',
          color: '#F0F1F5'
        },
        show: true
      },
      axisLabel: {
        color: '#979BA5'
      }
    },
    grid: {
      left: '0',
      right: '4%',
      top: '4%',
      bottom: '0',
      containLabel: true
    },
    series: [
      {
        data: [],
        type: 'bar',
        itemStyle: {
          color: '#689DF3'
        }
      }
    ]
  };
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
      min: 0
    }
  };
  /** 是否显示柱状图 是否是数字类型字段 */
  get isPillarChart() {
    return ['integer', 'long', 'double'].includes(this.queryParams?.field_type);
  }

  @Watch('currentPageNum')
  watchPageNum(v: number) {
    this.commonLegendRef.scrollTo({
      top: (v - 1) * LEGEND_BOX_HEIGHT
    });
  }

  @Emit('statisticsInfoFinish')
  private statisticsInfoFinish() {
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
    this.commonLegendRef?.removeAllListeners('wheel');
  }

  async queryStatisticsInfo() {
    try {
      this.infoLoading = true;
      this.chartLoading = true;
      const res = await $http.request(
        'retrieve/fieldStatisticsInfo',
        {
          data: {
            ...this.queryParams
          }
        },
        {
          cancelToken: new CancelToken(c => {
            this.getInfoCancelFn = c;
          })
        }
      );
      Object.assign(this.fieldData, res.data);
    } catch (error) {
    } finally {
      this.infoLoading = false;
    }
  }
  /** 图表请求 */
  async queryStatisticsGraph() {
    try {
      const data = {
        ...this.queryParams
      };
      if (this.isPillarChart) {
        Object.assign(data, {
          distinct_count: this.fieldData.distinct_count,
          max: this.fieldData.value_analysis.max,
          min: this.fieldData.value_analysis.min
        });
      }
      const res = await $http.request(
        'retrieve/fieldStatisticsGraph',
        {
          data
        },
        {
          getAllErrorValue: true,
          catchIsShowMessage: false,
          cancelToken: new CancelToken(c => {
            this.getChartsCancelFn = c;
          })
        }
      );
      this.isShowEmpty = false;
      // 分折线图和柱状图显示
      if (this.isPillarChart) {
        if (!res.data.length) {
          this.isShowEmpty = true;
          return;
        }
        // 折线图初始化
        this.pillarChartOption.series[0].data = res.data.map(item => item[1]);
        this.pillarChartOption.xAxis.data = res.data.map((item, index) => {
          if (index === 0 || index === res.data.length - 1 || this.fieldData.distinct_count < 10) {
            return item[0];
          }
          return `${res.data[index - 1][0]} - ${item[0]}`;
        });
      } else {
        if (!res.data.series.length) {
          this.isShowEmpty = true;
          return;
        }
        this.height = LINE_CHART_BASE_HEIGHT;
        const series = [];
        res.data.series.forEach(el => {
          series.push({
            ...timeSeriesBase,
            name: el.group_values[0],
            data: el.values
          });
        });
        this.seriesData = series;
        this.legendData = series.map((item, index) => ({
          color: lineColor[index],
          name: item.name,
          show: true
        }));
        // 收集所有时间戳
        const allTimestamps = series.reduce((acc, series) => {
          return acc.concat(series.data.map(item => item[0]));
        }, []);

        // 找到最小和最大时间戳
        const minTimestamp = Math.min.apply(null, allTimestamps);
        const maxTimestamp = Math.max.apply(null, allTimestamps);

        Object.assign(this.lineChartOption, {
          xAxis: {
            ...this.lineChartOption.xAxis,
            min: minTimestamp,
            max: maxTimestamp
          },
          series
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
    if (!start || !end) return;
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
    const echarts = require('echarts');
    const chart: any = echarts.init(this.chartRef, null, {
      height: `${this.height}px`
    });
    const getInitChartOption = this.isPillarChart ? this.pillarChartOption : this.lineChartOption;
    chart && chart.setOption(getInitChartOption);
    this.chart = chart;
    this.chart.resize();
  }
  /** 设置时间戳类型Tooltips */
  handleSetTimeTooltip(params) {
    const liHtmls = params
      .sort((a, b) => b.value[1] - a.value[1])
      .map((item, index) => {
        let markColor = 'color: #fafbfd;';
        if (index === 0) {
          markColor = 'color: #fff;font-weight: bold;';
        }
        return `<li class="tooltips-content-item">
                  <span class="item-series" style="background-color:${item.color};"></span>
                  <span class="item-name" style="${markColor}">${item.seriesName}:</span>
                  <span class="item-value" style="${markColor}">${item.value[1]}</span>
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
        <li class="tooltips-content-item">
          <span class="item-name" style="color: #fff;font-weight: bold;">${params[0].axisValue}:</span>
          <span class="item-value" style="color: #fff;font-weight: bold;">${params[0].value}</span>
        </li>
      </ul>
    </div>`;
  }
  /** 设置定位 */
  handleSetPosition(pos: number[], params: any, dom: any, rect: any, size: any) {
    const { contentSize } = size;
    const chartRect = dom.getBoundingClientRect();
    const posRect = {
      x: chartRect.x + +pos[0],
      y: chartRect.y + +pos[1]
    };
    const position = {
      left: 0,
      top: 0
    };
    const canSetBottom = window.innerHeight - posRect.y - contentSize[1];
    if (canSetBottom > 0) {
      position.top = +pos[1] - Math.min(20, canSetBottom);
    } else {
      position.top = +pos[1] + canSetBottom - 20;
    }
    const canSetLeft = window.innerWidth - posRect.x - contentSize[0] + 160;

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
      this.legendData.forEach(legend => {
        legend.show = legend.name === item.name || !hasOtherShow;
      });
    }
    const showSeriesName = this.legendData.filter(legend => legend.show).map(item => item.name);
    const showSeries = this.seriesData.filter(item => showSeriesName.includes(item.name));
    const options = this.chart.getOption();

    this.chart.setOption(
      {
        ...options,
        series: showSeries
      },
      {
        notMerge: true,
        lazyUpdate: false,
        silent: true
      }
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
      if (this.currentPageNum > 1) this.currentPageNum -= 1;
    } else {
      // 向下滚动
      if (this.currentPageNum < this.legendMaxPageNum) this.currentPageNum += 1;
    }
  }

  render() {
    return (
      <div class='field-analysis-container'>
        <div v-bkloading={{ isLoading: this.infoLoading }}>
          <div class='total-num-container'>
            <span class='total-num'>
              {window.mainComponent.$t('总行数')} : {this.fieldData.total_count}
            </span>
            <span class='appear-num'>
              {window.mainComponent.$t('出现行数')} : {this.fieldData.field_count}
            </span>
          </div>
          <div class='log-num-container'>
            <div class='num-box'>
              <span class='num-val'>
                <span class='log-num'>{this.fieldData.field_percent * 100}</span>
                <span class='log-unit'>%</span>
              </span>
              <span class='log-str'>{window.mainComponent.$t('日志条数')}</span>
            </div>
            <div class='num-box'>
              <span class='num-val'>
                <span class='log-num'>{this.fieldData.distinct_count}</span>
                <span class='log-unit'>{window.mainComponent.$t('次')}</span>
              </span>
              <span class='log-str'>{window.mainComponent.$t('去重日志条数')}</span>
            </div>
          </div>
          {this.isPillarChart && (
            <div class='number-num-container'>
              <div class='num-box'>
                <span class='num-key'>{window.mainComponent.$t('最大值')}</span>
                <span class='num-val'>{this.fieldData.value_analysis.max}</span>
              </div>
              <div class='num-box'>
                <span class='num-key'>{window.mainComponent.$t('最小值')}</span>
                <span class='num-val'>{this.fieldData.value_analysis.min}</span>
              </div>
              <div class='num-box'>
                <span class='num-key'>{window.mainComponent.$t('平均值')}</span>
                <span class='num-val'>{this.fieldData.value_analysis.avg}</span>
              </div>
              <div class='num-box'>
                <span class='num-key'>{window.mainComponent.$t('中位数')}</span>
                <span class='num-val'>{this.fieldData.value_analysis.median}</span>
              </div>
            </div>
          )}
        </div>
        <div v-bkloading={{ isLoading: this.chartLoading }}>
          {!this.isShowEmpty ? (
            <div>
              <div class='chart-title'>
                {!this.isPillarChart
                  ? `TOP 5 ${window.mainComponent.$t('时序图')}`
                  : window.mainComponent.$t('数值分布直方图')}
              </div>
              <div
                ref='fieldChart'
                style={{ width: '100%', height: `${this.height}px` }}
              ></div>
              {!this.isPillarChart && (
                <div
                  class='legend-box'
                  style={{ height: `${LEGEND_BOX_HEIGHT}px` }}
                >
                  <div
                    class='common-legend'
                    ref='commonLegend'
                  >
                    {this.legendData.map((legend, index) => {
                      return (
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
                      );
                    })}
                  </div>
                  {this.isShowPageIcon && (
                    <div class='legend-icon-box'>
                      <i
                        class={{
                          'bk-select-angle bk-icon icon-angle-up-fill last-page-up': true,
                          disabled: this.currentPageNum === 1
                        }}
                        onClick={() => {
                          if (this.currentPageNum > 1) this.currentPageNum -= 1;
                        }}
                      ></i>
                      <i
                        class={{
                          'bk-select-angle bk-icon icon-angle-up-fill': true,
                          disabled: this.currentPageNum === this.legendMaxPageNum
                        }}
                        onClick={() => {
                          if (this.currentPageNum < this.legendMaxPageNum) this.currentPageNum += 1;
                        }}
                      ></i>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div
              class='not-data-empty'
              style={{ height: `${this.height}px` }}
            >
              <EmptyStatus
                empty-type={!!this.emptyTipsStr ? '500' : 'empty'}
                show-text={false}
              >
                <div style={{ marginTop: '-20px' }}>
                  <span>{this.emptyStr}</span>
                  {!!this.emptyTipsStr && (
                    <i
                      v-bk-tooltips={{
                        content: this.emptyTipsStr
                      }}
                      class='bk-icon icon-exclamation-circle'
                    ></i>
                  )}
                </div>
              </EmptyStatus>
            </div>
          )}
        </div>
      </div>
    );
  }
}
