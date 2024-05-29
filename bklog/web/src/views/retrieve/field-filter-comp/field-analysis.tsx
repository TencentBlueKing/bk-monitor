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

import { Component, Prop, Ref, Vue, Emit } from 'vue-property-decorator';
import $http from '../../../api';
import { lineColor } from '../../../store/constant';
import './field-analysis.scss';

/** 无数据提示 */
const graphic = {
  elements: [
    {
      type: 'text',
      left: 'center',
      top: 'center',
      style: {
        text: window.mainComponent.$t('无数据'),
        fontSize: 20,
        fill: '#313238'
      },
      invisible: true
    }
  ]
};

/** 柱状图基础高度 */
const PILLAR_CHART_BASE_HEIGHT = 200;
/** 折线图图基础高度 */
const LINE_CHART_BASE_HEIGHT = 170;
/** 折线图一行的情况下与底部的百分比设置 */
const GRID_PERCENTAGE = 8;
/** 折线图一行的情况下与底部的分类的高度 */
const LINE_CHART_LEGEND_HEIGHT = 18;
/** 折线图向右偏移量 */
const OFFSET_X = 10;
/** 折线图向下偏移量 */
const OFFSET_Y = -10;

@Component
export default class FieldAnalysis extends Vue {
  @Prop({ type: Object, default: () => ({}) }) private readonly queryParams: any;
  @Ref('fieldChart') private readonly fieldChartRef!: HTMLDivElement;

  chart = null;
  /** 图表高度 */
  height = PILLAR_CHART_BASE_HEIGHT;
  infoLoading = false;
  chartLoading = false;

  /** 折线图数据 */
  lineChartOption = {
    tooltip: {
      trigger: 'axis',
      enterable: true,
      position: (point, params, dom) => {
        // point 是当前鼠标的位置 [x坐标, y坐标]
        // 为了更好的显示 Tooltip 会永远出现在鼠标的右上角

        const domRect = dom.getBoundingClientRect();
        // 计算并返回新的 Tooltip 位置
        const x = point[0] + OFFSET_X;
        const y = point[1] - domRect.height + OFFSET_Y;

        return [x, y];
      }
    },
    color: [],
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
      left: '0',
      right: '6%',
      top: '4%',
      bottom: '20%',
      containLabel: true
    },
    xAxis: {
      axisLine: {
        show: false
      },
      axisTick: {
        show: false
      },
      axisLabel: {
        color: '#979BA5'
      },
      boundaryGap: [0, 0], // 设置为0确保时间数据顶边和底边对齐
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
    series: [],
    graphic
  };

  /** 柱状图数据 */
  pillarChartOption = {
    tooltip: {
      trigger: 'axis'
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
          if (value.length > 10) return `${value.slice(0, 10)}...`; // 只显示前10个字符
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
    ],
    graphic
  };

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

  @Emit('statisticsInfoFinish')
  private statisticsInfoFinish() {
    return true;
  }

  mounted() {
    this.$nextTick(async () => {
      await this.queryStatisticsInfo();
      await this.queryStatisticsGraph();
      this.initFieldChart();
    });
  }

  async queryStatisticsInfo() {
    try {
      this.infoLoading = true;
      this.chartLoading = true;
      const res = await $http.request('retrieve/fieldStatisticsInfo', {
        data: {
          ...this.queryParams
        }
      });
      Object.assign(this.fieldData, res.data);
    } catch (error) {
    } finally {
      this.infoLoading = false;
    }
  }
  /** 图表请求 */
  async queryStatisticsGraph() {
    try {
      // this.chartLoading = true;
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
      const res = await $http.request('retrieve/fieldStatisticsGraph', {
        data
      });
      // 分折线图和柱状图显示
      if (this.isPillarChart) {
        // 折线图初始化
        this.pillarChartOption.series[0].data = res.data.map(item => item[1]);
        this.pillarChartOption.xAxis.data = res.data.map((item, index) => {
          if (index === 0 || index === res.data.length - 1 || this.fieldData.distinct_count < 10) {
            return item[0];
          }
          return `${res.data[index - 1][0]} ~ ${item[0]}`;
        });
      } else {
        this.height = LINE_CHART_BASE_HEIGHT;
        const seriesData = res.data.series;
        const series = [];
        const legendData = [];
        seriesData.forEach((el, index) => {
          legendData.push(el.group_values[0]);
          series.push({
            type: 'line',
            lineStyle: {
              normal: {
                color: lineColor[index]
              }
            },
            symbol: 'none',
            name: el.group_values[0],
            data: el.values
          });
        });
        this.lineChartOption.series = series;
        this.lineChartOption.legend.data = legendData;
        this.lineChartOption.color = lineColor.slice(0, seriesData.length);
        // 根据分类数量增加底边的百分比高度
        this.lineChartOption.grid.bottom = `${Math.ceil(legendData.length / 3) * GRID_PERCENTAGE}%`;
        // 根据分类数量增加高度
        this.height = this.height + Math.ceil(legendData.length / 3) * LINE_CHART_LEGEND_HEIGHT;
      }
    } catch (error) {
    } finally {
      this.statisticsInfoFinish();
      this.chartLoading = false;
    }
  }

  /** 设置无数据的显隐 */
  setGraphicInvisible(invisible = true) {
    this.chart.setOption({
      graphic: {
        elements: [
          {
            invisible
          }
        ]
      }
    });
  }

  initFieldChart() {
    const echarts = require('echarts');
    const chart: any = echarts.init(this.fieldChartRef, null, {
      height: `${this.height}px`
    });
    const getInitChartOption = this.isPillarChart ? this.pillarChartOption : this.lineChartOption;
    chart && chart.setOption(getInitChartOption);
    this.chart = chart;
    if (this.isPillarChart) {
      if (!this.pillarChartOption.series[0].data.length) {
        this.setGraphicInvisible(false);
      }
    } else {
      if (!this.lineChartOption.series.length) {
        this.setGraphicInvisible(false);
      } else {
        this.chart.on('legendselectchanged', params => {
          const anySeriesSelected = Object.keys(params.selected).some(key => params.selected[key]);
          this.setGraphicInvisible(anySeriesSelected);
          // 更新无数据文本的显示状态
        });
      }
    }
    this.chart.resize();
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
          <div class='chart-title'>
            {!this.isPillarChart
              ? `TOP 5 ${window.mainComponent.$t('时序图')}`
              : window.mainComponent.$t('数值分布直方图')}
          </div>
          <div
            ref='fieldChart'
            style={{ width: '324px', height: `${this.height}px` }}
          ></div>
        </div>
      </div>
    );
  }
}
