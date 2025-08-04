<!--
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
-->
<template>
  <div
    class="monitor-echart-wrap"
    :style="{ 'background-image': backgroundUrl }"
  >
    <div
      v-if="chartTitle || $slots.title"
      class="echart-header"
    >
      <slot name="title">
        <div class="header-title">{{ chartTitle }}{{ chartUnit ? `（${chartUnit}）` : '' }}</div>
      </slot>
      <div
        v-if="!!chart && !noData"
        class="header-tools"
      >
        <slot name="tools">
          <i
            v-if="false"
            class="icon-monitor icon-mc-mark tools-icon"
          />
        </slot>
      </div>
    </div>
    <div
      ref="charWrapRef"
      class="chart-wrapper"
      :style="{
        flexDirection: !showExtremum ? 'column' : 'row',
        minHeight: height - (chartTitle ? 36 : 0) + 'px',
        maxHeight: height - (chartTitle ? 36 : 0) + 'px',
      }"
      @dblclick="handleChartDblClick"
      @click="handleChartClick"
    >
      <div
        ref="chartRef"
        class="echart-instance"
        :style="{ minHeight: chartHeight + 'px', maxHeight: chartHeight + 'px' }"
      />
      <div
        class="echart-legend"
        :style="{
          maxHeight: (showExtremum ? height - (chartTitle ? 36 : 0) - 5 : 30) + 'px',
          marginRight: showExtremum ? '20px' : '2px',
        }"
      >
        <chart-legend
          v-if="legend.show"
          :legend-data="legend.list"
          :legend-type="showExtremum ? 'table' : 'common'"
          @legend-event="handleLegendEvent"
        />
      </div>
      <div
        v-if="chartType === 'pie'"
        class="echart-pie-center"
      >
        <slot name="chartCenter" />
      </div>
    </div>
    <div
      v-if="setNoData"
      v-show="noData"
      class="echart-content"
    >
      <slot name="noData">
        {{ emptyText }}
      </slot>
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { type ResizeCallback, addListener, removeListener } from '@blueking/fork-resize-detector';
import dayjs from 'dayjs';
import deepMerge from 'deepmerge';
import { debounce } from 'throttle-debounce';

import ChartLegend from './components/chart-legend.vue';
import { colorList } from './options/constant';
import EchartOptions from './options/echart-options';
import { type MonitorEchartOptions, type MonitorEchartSeries, echarts } from './types/monitor-echarts';
import watermarkMaker from './utils/watermarkMaker';

import type { ILegendItem } from './options/type-interface';

interface ICurValue {
  color: string;
  dataIndex: number;
  name: string;
  seriesIndex: number;
  xAxis: number | string;
  yAxis: number | string;
}

@Component({
  name: 'monitor-mobile-echarts',
  components: {
    ChartLegend,
  },
})
export default class MonitorMobileEcharts extends Vue {
  @Ref() readonly chartRef!: HTMLDivElement;
  @Ref() readonly charWrapRef!: HTMLDivElement;

  chart: echarts.ECharts = null;
  resizeHandler: ResizeCallback<HTMLDivElement>;
  unwatchOptions: () => void;
  unwatchSeries: () => void;
  chartTitle = '';
  chartUnit = '';
  intersectionObserver: IntersectionObserver = null;
  needObserver = true;
  loading = false;
  noData = false;
  timeRange: string[] = [];
  curValue: ICurValue = { xAxis: '', yAxis: '', dataIndex: -1, color: '', name: '', seriesIndex: -1 };
  refreshIntervalInstance = 0;
  chartOptionInstance = null;
  hasInitChart = false;
  legend: { list: ILegendItem[]; show: boolean } = {
    show: false,
    list: [],
  };
  curChartOption: any;
  // echarts配置项
  @Prop() readonly options: MonitorEchartOptions;
  // echarts配置项是否深度监听
  @Prop({ default: true }) readonly watchOptionsDeep: boolean;
  // 是否自动resize
  @Prop({ default: true }) readonly autoresize: boolean;
  // 是使用组件内的无数据设置
  @Prop({ default: true }) readonly setNoData: boolean;
  // 是否显示极值
  @Prop({ default: false }) readonly showExtremum: boolean;
  // 图表刷新间隔
  @Prop({ default: 0 }) readonly refreshInterval: number;
  // 图表类型
  @Prop({ default: 'line' }) readonly chartType: 'bar' | 'line';
  // 图表title
  @Prop({ default: '' }) readonly title: string;
  // 图表单位
  @Prop({ default: '' }) readonly unit: string;

  @Prop({ default: false }) readonly showLegend: boolean;
  // 图表系列数据
  @Prop() readonly series: MonitorEchartSeries;

  // 背景图
  @Prop({
    type: String,
    default() {
      return window.graph_watermark ? `url('${watermarkMaker(window.user_name || window.username)}')` : '';
    },
  })
  backgroundUrl: string;

  // 获取图标数据
  @Prop() getSeriesData: (timeFrom?: string, timeTo?: string, range?: boolean) => Promise<void>;

  @Prop({
    default: () => colorList,
  })
  // 图标系列颜色集合
  colors: string[];

  @Prop({
    default() {
      return '查无数据';
    },
  })
  emptyText: string;

  // 图表高度
  @Prop({ default: 310 }) height: number | string;

  // 监控图表默认配置
  get defaultOptions() {
    if (['bar', 'line'].includes(this.chartType)) {
      return {
        tooltip: {
          axisPointer: {
            type: 'cross',
            axis: 'auto',
            label: {
              show: false,
              formatter: params => {
                if (this.chartType !== 'line') return;
                if (params.axisDimension === 'y') {
                  this.curValue.yAxis = params.value;
                } else {
                  this.curValue.xAxis = params.value;
                  this.curValue.dataIndex = params.seriesData?.length ? params.seriesData[0].dataIndex : -1;
                }
              },
            },
            crossStyle: {
              color: 'transparent',
              opacity: 0,
              width: 0,
            },
          },
          formatter: this.handleSetTooltip,
        },
      };
    }
    return {};
  }

  get chartHeight() {
    let { height } = this;
    if (this.chartTitle) {
      height -= 36;
    }
    if (!this.showExtremum && this.legend.show) {
      height -= 30;
    }
    return height;
  }
  @Watch('refreshInterval', { immediate: true })
  onRefreshIntervalChange(v: number) {
    if (this.refreshIntervalInstance) {
      window.clearInterval(this.refreshIntervalInstance);
    }
    if (!this.getSeriesData || !v || +v < 60 * 1000) return;
    this.refreshIntervalInstance = window.setInterval(() => {
      this.handleSeriesData();
    }, v);
  }
  @Watch('height')
  onHeightChange() {
    this.chart?.resize?.();
  }
  @Watch('series')
  onSeriesChange(s: any) {
    this.handleSetChartData(deepMerge({}, { series: s }));
  }

  mounted() {
    if (this.series) {
      this.initChart();
      this.handleSetChartData(
        deepMerge(
          {},
          {
            series: this.series,
          }
        )
      );
    } else if (this.options?.series?.length) {
      this.initChart();
      this.handleSetChartData(deepMerge({}, this.options));
    }
    if (this.getSeriesData) {
      this.registerObserver();
      this.intersectionObserver.observe(this.$el);
    }
  }

  activated() {
    if (this.autoresize) {
      this.chart?.resize();
    }
  }
  beforeDestroy() {
    this.timeRange = [];
    this.unwatchSeries?.();
    this.unwatchOptions?.();
    if (this.intersectionObserver) {
      this.intersectionObserver.unobserve(this.$el);
      this.intersectionObserver.disconnect();
    }
    this.refreshIntervalInstance && window.clearInterval(this.refreshIntervalInstance);
  }
  destroyed() {
    this.chart && this.destroy();
  }
  initChart() {
    const chart: any = echarts.init(this.chartRef);
    this.chartTitle = this.title;
    this.chart = chart;
    this.chartUnit = this.unit;
    if (this.autoresize) {
      const handler = debounce(300, () => this.resize());
      this.resizeHandler = async () => {
        await this.$nextTick();
        this.chartRef?.offsetParent !== null && handler();
      };
      addListener(this.chartRef, this.resizeHandler);
    }
    this.initPropsWatcher();
  }
  // 注册Intersection监听
  registerObserver(): void {
    this.intersectionObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (this.needObserver) {
          if (entry.intersectionRatio > 0) {
            this.handleSeriesData();
          } else {
            // 解决临界点、慢滑不加载数据问题
            const { top, bottom } = this.$el.getBoundingClientRect();
            if (top === 0 && bottom === 0) return;
            const { innerHeight } = window;
            const isVisiable = (top > 0 && top <= innerHeight) || (bottom >= 0 && bottom < innerHeight);
            isVisiable && this.handleSeriesData();
          }
        }
      });
    });
  }

  // 获取seriesData
  async handleSeriesData(startTime?: string, endTime?: string) {
    this.loading = true;
    this.intersectionObserver?.unobserve(this.$el);
    this.intersectionObserver?.disconnect();
    this.needObserver = false;
    try {
      const isRange = startTime && startTime.length > 0 && endTime && endTime.length > 0;
      const data = await this.getSeriesData(startTime, endTime, isRange).catch(() => ({}));
      if (data && Object.keys(data).length) {
        await this.handleSetChartData(data);
      } else {
        this.noData = true;
      }
    } catch (e) {
      console.info(e);
      this.noData = true;
    } finally {
      this.loading = false;
    }
  }
  handleTransformSeries(data) {
    if (data?.series) {
      return data || [];
    }
    const mapData = {};
    return {
      series: data?.map(({ datapoints, target, ...item }) => {
        mapData[target] !== undefined ? (mapData[target] += 1) : (mapData[target] = 0);
        return {
          ...item,
          data: datapoints.map(set => (Array.isArray(set) ? set.slice().reverse() : [])),
          name: !mapData[target] ? target : target + mapData[target],
          symbolSize: 6,
          showSymbol: false, // 默认不显示点，只有hover时候显示该点
        };
      }),
    };
  }

  // 设置chart配置
  async handleSetChartData(data) {
    return new Promise(resolve => {
      if (!this.chart) {
        this.initChart();
      }
      const { unit, title, series } = data || {};
      title && !this.title && (this.chartTitle = title.text);
      this.chartUnit = unit || this.unit || '';
      const hasSeries =
        (series && series.length > 0 && series.some(item => item.datapoints?.length)) ||
        (series && Object.hasOwn(series, 'series') && series.series.length);
      this.chartOptionInstance = new EchartOptions({
        chartType: this.chartType,
        colors: this.colors,
        showExtremum: this.showExtremum,
        chartOption: this.options,
        lineWidth: 1,
      });
      const optionData = this.chartOptionInstance.getOptions(this.handleTransformSeries(series), {});
      if (['bar', 'line'].includes(this.chartType)) {
        this.legend.show = this.showLegend && hasSeries && optionData.legendData.length > 0;
      } else {
        this.legend.show = optionData.options.lengend
          ? Object.hasOwn(optionData.options.lengend, 'show')
            ? optionData.options.lengend.show
            : true
          : false;
      }
      this.legend.list = optionData.legendData || [];
      if (this.options?.grid) {
        optionData.options.grid.bottom = this.options.grid.bottom;
      }
      setTimeout(() => {
        this.chart.setOption(deepMerge(optionData.options, this.defaultOptions), {
          notMerge: false,
          lazyUpdate: false,
          silent: false,
        });
        if (!this.hasInitChart) {
          this.hasInitChart = true;
          if (optionData.options.toolbox) {
            this.initChartAction();
            this.chart.on('dataZoom', async event => {
              this.loading = true;
              const [batch] = event.batch;
              if (batch.startValue && batch.endValue) {
                const timeFrom = dayjs(+batch.startValue.toFixed(0)).format('YYYY-MM-DD HH:mm');
                const timeTo = dayjs(+batch.endValue.toFixed(0)).format('YYYY-MM-DD HH:mm');
                this.timeRange = [timeFrom, timeTo];
                if (this.getSeriesData) {
                  this.chart.dispatchAction({
                    type: 'restore',
                  });
                  await this.handleSeriesData(timeFrom, timeTo);
                }
              }
              this.loading = false;
            });
          }
          this.initChartEvent();
        }
        this.noData = !hasSeries;
        this.curChartOption = Object.freeze(Object.assign({}, this.chart.getOption()));
        resolve(undefined);
      }, 320);
    }).catch(console.log);
  }
  // 设置tooltip
  handleSetTooltip(params) {
    if (!params || params.length < 1 || params.every(item => item.value[1] === null)) {
      this.chartType === 'line' &&
        (this.curValue = {
          color: '',
          name: '',
          seriesIndex: -1,
          dataIndex: -1,
          xAxis: '',
          yAxis: '',
        });
      return;
    }
    const pointTime = dayjs.tz(params[0].axisValue).format('YYYY-MM-DD HH:mm:ss');
    const data = params
      .map(item => ({ color: item.color, seriesName: item.seriesName, value: item.value[1] }))
      .sort((a, b) => Math.abs(a.value - +this.curValue.yAxis) - Math.abs(b.value - +this.curValue.yAxis));

    const liHtmlList = params
      .filter(item => !item.seriesName.match(/-no-tips$/))
      .map(item => {
        let markColor = "color: '#fafbfd';";
        if (data[0].value === item.value[1]) {
          markColor = "color: '#ffffff';font-weight: bold;";
          this.chartType === 'line' &&
            (this.curValue = {
              color: item.color,
              name: item.seriesName,
              seriesIndex: item.seriesIndex,
              dataIndex: item.dataIndex,
              xAxis: item.value[0],
              yAxis: item.value[1],
            });
        }
        if (item.value[1] === null) return '';
        const curSeries = this.curChartOption.series[item.seriesIndex];
        const unitFormatter = curSeries.unitFormatter || (v => ({ text: v }));
        const minBase = curSeries.minBase || 0;
        const precision = curSeries.unit !== 'none' && +curSeries.precision < 1 ? 2 : +curSeries.precision;
        const valueObj = unitFormatter(item.value[1] - minBase, precision);
        return `<li style="display: flex;align-items: center;">
                <span
                 style="background-color:${item.color};margin-right: 10px;width: 6px;height: 6px; border-radius: 50%;">
                </span>
                <span style="${markColor}">${item.seriesName}:</span>
                <span style="${markColor} flex: 1;margin-left: 5px;">
                ${valueObj.text} ${valueObj.suffix || ''}</span>
                </li>`;
      });
    return `<div style="z-index:12; border-radius: 6px">
            <p style="text-align:center;margin: 0 0 5px 0;font-weight: bold;">
                ${pointTime}
            </p>
            <ul style="padding: 0;margin: 0;">
                ${liHtmlList.join('')}
            </ul>
            </div>`;
  }

  // 双击触发重置选择数据
  handleChartDblClick() {
    if (this.timeRange.length > 0) {
      this.timeRange = [];
      this.chart.dispatchAction({
        type: 'restore',
      });
      this.getSeriesData &&
        setTimeout(() => {
          this.handleSeriesData();
        }, 100);
    }
    this.$emit('dblclick');
  }

  // 单击图表触发
  handleChartClick() {
    this.$emit('click');
  }

  handleLegendEvent({ actionType, item }: { actionType: string; item: ILegendItem }) {
    if (this.legend.list.length < 2) {
      return;
    }
    if (actionType === 'shift-click') {
      this.chart.dispatchAction({
        type: !item.show ? 'legendSelect' : 'legendUnSelect',
        name: item.name,
      });
      item.show = !item.show;
    } else if (actionType === 'click') {
      const hasOtherShow = this.legend.list
        .filter(item => !item.hidden)
        .some(set => set.name !== item.name && set.show);
      this.legend.list.forEach(legend => {
        this.chart.dispatchAction({
          type:
            legend.name === item.name ||
            !hasOtherShow ||
            (legend.name.includes(`${item.name}-no-tips`) && legend.hidden)
              ? 'legendSelect'
              : 'legendUnSelect',
          name: legend.name,
        });
        legend.show = legend.name === item.name || !hasOtherShow;
      });
    }
  }

  // resize
  resize(options: MonitorEchartOptions = null) {
    this.chartRef && this.delegateMethod('resize', options);
  }

  dispatchAction(payload) {
    this.delegateMethod('dispatchAction', payload);
  }

  delegateMethod(name: string, ...args) {
    return this.chart[name](...args);
  }

  delegateGet(methodName: string) {
    return this.chart[methodName]();
  }

  // 初始化Props监听
  initPropsWatcher() {
    this.unwatchOptions = this.$watch(
      'options',
      () => {
        if (this.getSeriesData) {
          this.handleSeriesData();
        } else {
          this.handleSetChartData(deepMerge({}, { series: this.series }));
        }
      },
      { deep: !this.watchOptionsDeep }
    );
  }

  // 初始化chart事件
  initChartEvent() {
    this.chart.on('click', e => {
      this.$emit('chart-click', e);
    });
  }

  // 初始化chart Action
  initChartAction() {
    this.dispatchAction({
      type: 'takeGlobalCursor',
      key: 'dataZoomSelect',
      dataZoomSelectActive: true,
    });
  }

  // echarts 实例销毁
  destroy() {
    if (this.autoresize && this.chartRef) {
      removeListener(this.chartRef, this.resizeHandler);
    }
    this.delegateMethod('dispose');
    this.chart = null;
  }
}
</script>

<style lang="scss" scoped>
.monitor-echart-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  color: #63656e;
  background-color: #fff;
  background-repeat: repeat;
  background-position: center;
  border-radius: 2px;

  .echart-header {
    display: flex;
    align-items: center;
    min-width: 100%;
    height: 36px;
    padding-left: 16px;
    font-weight: 700;
    color: #63656e;

    .header-title {
      flex: 1;
      font-weight: 700;
    }

    .header-tools {
      display: flex;
      align-items: center;
      min-height: 36px;
      margin-right: 10px;
      margin-left: auto;
      font-size: 16px;
      font-weight: normal;
      color: #979ba5;

      .tools-icon {
        margin-right: 8px;

        &:hover {
          color: #3a84ff;
          cursor: pointer;
        }
      }
    }
  }

  .chart-wrapper {
    position: relative;
    display: flex;

    .echart-instance {
      flex: 1;
      min-width: 100px;
      height: 310px;
    }

    .echart-annotation {
      position: absolute;
      z-index: 99;
      width: 220px;
      height: 156px;
      font-size: 12px;
      color: #63656e;
      background: white;
      border-radius: 2px;
      box-shadow: 0px 4px 12px 0px rgba(0, 0, 0, 0.2);

      &-title {
        margin: 6px 0 0 16px;
        line-height: 20px;
      }

      &-name {
        display: flex;
        align-items: center;
        height: 20px;
        padding-left: 18px;
        margin-top: 2px;
        font-weight: 700;
        border-bottom: 1px solid #f0f1f5;

        .name-mark {
          flex: 0 0 12px;
          height: 4px;
          margin-right: 10px;
        }
      }

      &-list {
        display: flex;
        flex-direction: column;

        .list-item {
          display: flex;
          flex: 0 0 30px;
          align-items: center;
          padding-left: 18px;

          .item-icon {
            margin-right: 10px;
            font-size: 14px;
          }

          &:hover {
            color: #3a84ff;
            cursor: pointer;
            background-color: #e1ecff;
          }
        }
      }
    }

    .echart-legend {
      margin-right: 20px;
      overflow: auto;
    }

    .echart-pie-center {
      position: absolute;
      top: 50%;
      left: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      transform: translate3d(-50%, -50%, 0);
    }
  }

  .echart-content {
    position: absolute;
    top: 36px;
    right: 1px;
    bottom: 1px;
    left: 1px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0);
  }
}
</style>
