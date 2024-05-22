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

import { Component, Prop, Ref, Vue } from 'vue-property-decorator';
// import Echarts from 'echarts';
import dayjs from 'dayjs';
import $http from '@/api';
import './field-analysis.scss';

const lineColor = [
  '#A3C5FD', // 0: pale green
  '#EAB839', // 1: mustard
  '#6ED0E0', // 2: light blue
  '#EF843C', // 3: orange
  '#E24D42', // 4: red
  '#1F78C1', // 5: ocean
  '#BA43A9', // 6: purple
  '#705DA0', // 7: violet
  '#508642', // 8: dark green
  '#CCA300', // 9: dark sand
  '#447EBC',
  '#C15C17',
  '#890F02',
  '#0A437C',
  '#6D1F62',
  '#584477',
  '#B7DBAB',
  '#F4D598',
  '#70DBED',
  '#F9BA8F',
  '#F29191',
  '#82B5D8',
  '#E5A8E2',
  '#AEA2E0',
  '#629E51',
  '#E5AC0E',
  '#64B0C8',
  '#E0752D',
  '#BF1B00',
  '#0A50A1',
  '#962D82',
  '#614D93',
  '#9AC48A',
  '#F2C96D',
  '#65C5DB',
  '#F9934E',
  '#EA6460',
  '#5195CE',
  '#D683CE',
  '#806EB7',
  '#3F6833',
  '#967302',
  '#2F575E',
  '#99440A',
  '#58140C',
  '#052B51',
  '#511749',
  '#3F2B5B',
  '#E0F9D7',
  '#FCEACA',
  '#CFFAFF',
  '#F9E2D2',
  '#FCE2DE',
  '#BADFF4',
  '#F9D9F9',
  '#DEDAF7'
];

@Component
export default class FieldAnalysis extends Vue {
  @Prop({ type: Object, default: () => ({}) }) private readonly queryParams: any;
  @Ref('fieldChart') private readonly fieldChartRef!: HTMLDivElement;

  chart = null;
  height = 170;
  // height = 200;
  infoLoading = false;
  chartLoading = false;

  lineChartOption = {
    tooltip: {
      trigger: 'axis'
    },
    color: [],
    legend: {
      itemWidth: 10,
      itemHeight: 10,
      padding: 0,
      bottom: 0,
      icon: 'rect',
      data: []
    },
    grid: {
      left: '0',
      right: '4%',
      top: '4%',
      bottom: '20%',
      containLabel: true
    },
    xAxis: {
      boundaryGap: false,
      axisLine: {
        show: false
      },
      axisTick: {
        show: false
      },
      axisLabel: {
        color: '#979BA5'
      },
      data: []
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

  pillarChartOption = {
    tooltip: {
      trigger: 'axis'
      // formatter: this.handleSetPillarTooltips
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

  get isShowValueAnalysis() {
    return this.isPillarChart && !Object.values(this.fieldData?.value_analysis).every(item => item === 0);
  }

  get isPillarChart() {
    return ['integer', 'long', 'double'].includes(this.queryParams?.field_type);
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
        this.pillarChartOption.series[0].data = res.data.map(item => item[1]);
        this.pillarChartOption.xAxis.data = res.data.map((item, index) => {
          if (index === 0 || index === res.data.length - 1 || this.fieldData.distinct_count < 10) {
            return item[0];
          }
          return `${res.data[index - 1][0]} ~ ${item[0]}`;
        });
      } else {
        // 折线图数据初始化
        const timeData = res.data.series[0].values.map(vItem => dayjs.tz(vItem[0]).format('YYYY-MM-DD HH:mm:ss'));
        const seriesData = res.data.series.map(item => {
          return {
            name: item.group_values[0],
            data: item.values.map(vItem => vItem[1])
          };
        });
        this.lineChartOption.xAxis.data = timeData;
        const series = [];
        const legendData = [];
        seriesData.forEach((el, index) => {
          legendData.push(el.name);
          series.push({
            type: 'line',
            lineStyle: {
              normal: {
                color: lineColor[index]
              }
            },
            symbol: 'none',
            name: el.name,
            data: el.data
          });
        });
        // if (seriesData.length === 1) {
        //   this.lineChartOption.grid.bottom = '0%';
        //   legendData.splice(0, legendData.length);
        // }
        this.lineChartOption.series = series;
        this.lineChartOption.legend.data = legendData;
        this.lineChartOption.color = lineColor.slice(0, seriesData.length);
      }
    } catch (error) {
    } finally {
      this.chartLoading = false;
    }
  }

  initFieldChart() {
    const echarts = require('echarts');
    const chart: any = echarts.init(this.fieldChartRef, null, {
      height: 'auto'
    });
    const getInitChartOption = this.isPillarChart ? this.pillarChartOption : this.lineChartOption;
    chart && chart.setOption(getInitChartOption);
    this.chart = chart;
    this.chart.resize();
  }

  handleSetPillarTooltips() {
    // if (this.fieldData.distinct_count > 10) {
    // }
    // return `<div>${1}</div>`;
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
          {this.isShowValueAnalysis && (
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
            {!this.isPillarChart ? window.mainComponent.$t('TOP 5 时序图') : window.mainComponent.$t('数值分布直方图')}
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
