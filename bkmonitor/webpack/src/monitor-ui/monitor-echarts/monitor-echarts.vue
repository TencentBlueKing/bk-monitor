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
    v-bkloading="{ isLoading: loading }"
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
        v-if="chartOption.tool.show && !!chart && !noData"
        class="header-tools"
      >
        <slot name="tools">
          <chart-tools
            :show-more="chartOption.tool.moreShow"
            :need-full-screen="needFullScreen"
            :is-full-screen="isFullScreen"
            @store-img="handleStoreImage"
            @full-screen="handleFullScreen"
            @tool-item="handleMoreToolItemSet"
          />
        </slot>
      </div>
    </div>
    <div
      ref="charWrapRef"
      class="chart-wrapper"
      tabindex="-1"
      :style="{
        flexDirection: !chartOption.legend.toTheRight ? 'column' : 'row',
        minHeight: height - (chartTitle ? 36 : 0) + 'px',
        maxHeight: height - (chartTitle ? 36 : 0) + 'px',
      }"
      @blur="handleCharBlur"
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
          maxHeight: (chartOption.legend.toTheRight ? height - (chartTitle ? 36 : 0) - 5 : 30) + 'px',
          marginRight: chartOption.legend.toTheRight ? '20px' : '2px',
        }"
      >
        <chart-legend
          v-if="legend.show"
          :legend-data="legend.list"
          class="fix-same-code"
          :legend-type="chartOption.legend.asTable ? 'table' : 'common'"
          :to-the-right="chartOption.legend.toTheRight"
          @legend-event="handleLegendEvent"
        />
      </div>
      <div
        v-if="chartType === 'pie'"
        class="fix-same-code echart-pie-center"
      >
        <slot name="chartCenter" />
      </div>
      <chart-annotation
        v-if="chartOption.annotation.show"
        class="fix-same-code"
        :annotation="annotation"
      />
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
    <template v-if="needFullScreen">
      <template v-if="needChild">
        <monitor-dialog
          :z-index="4000"
          :value.sync="isFullScreen"
          full-screen
          :need-header="false"
          :need-footer="false"
        >
          <keep-alive>
            <monitor-echarts
              v-if="isFullScreen && childProps"
              v-bind="childProps"
              :need-child="false"
            />
          </keep-alive>
        </monitor-dialog>
      </template>
    </template>
  </div>
</template>
<script lang="ts">
import { Component, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { type ResizeCallback, addListener, removeListener } from '@blueking/fork-resize-detector';
import dayjs from 'dayjs';
import deepMerge from 'deepmerge';
import { toBlob, toPng } from 'html-to-image';
import { hexToRgbA } from 'monitor-common/utils/utils';
import MonitorDialog from 'monitor-ui/monitor-dialog/monitor-dialog.vue';
import { debounce } from 'throttle-debounce';

import ChartAnnotation from './components/chart-annotation.vue';
import ChartLegend from './components/chart-legend.vue';
import ChartTools from './components/chart-tools.vue';
import './map/china';
import EchartOptions from './options/echart-options';
import { type MonitorEchartOptions, type MonitorEchartSeries, echarts } from './types/monitor-echarts';
import watermarkMaker from './utils/watermarkMaker';

import type { IAnnotation, ILegendItem, IMoreToolItem } from './options/type-interface';

interface ICurValue {
  color: string;
  dataIndex: number;
  name: string;
  seriesIndex: number;
  xAxis: number | string;
  yAxis: number | string;
}

@Component({
  name: 'monitor-echarts',
  components: {
    MonitorDialog,
    ChartLegend,
    ChartTools,
    ChartAnnotation,
  },
})
export default class MonitorEcharts extends Vue {
  @Ref() chartRef!: HTMLDivElement;
  @Ref() charWrapRef!: HTMLDivElement;

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
  isFullScreen = false;
  timeRange: string[] = [];
  childProps = {};
  annotation: IAnnotation = { x: 0, y: 0, show: false, title: '', name: '', color: '' };
  curValue: ICurValue = { xAxis: '', yAxis: '', dataIndex: -1, color: '', name: '', seriesIndex: -1 };
  refreshIntervalInstance = 0;
  chartOptionInstance = null;
  hasInitChart = false;
  legend: { list: ILegendItem[]; show: boolean } = {
    show: false,
    list: [],
  };
  // echarts配置项
  @Prop() options: MonitorEchartOptions;
  // echarts配置项是否深度监听
  @Prop({ default: true }) watchOptionsDeep: boolean;
  // 是否自动resize
  @Prop({ default: true }) autoresize: boolean;
  // 是否需要设置全屏
  @Prop({ default: true }) needFullScreen: boolean;
  // 是有fullscreen递归
  @Prop({ default: true }) needChild: boolean;
  // 获取图标数据
  @Prop() getSeriesData: (timeFrom?: string, timeTo?: string, range?: boolean) => Promise<void>;
  // 是使用组件内的无数据设置
  @Prop({ default: true }) setNoData: boolean;
  // 图表刷新间隔
  @Prop({ default: 0 }) refreshInterval: number;
  // 图表类型
  @Prop({ default: 'line' }) chartType: 'bar' | 'line' | 'map' | 'pie';
  // 背景图
  @Prop({
    type: String,
    default() {
      return window.graph_watermark ? `url('${watermarkMaker(window.user_name || window.username)}')` : '';
    },
  })
  backgroundUrl: string;
  // 图表title
  @Prop({ default: '' }) title: string;
  // 图表单位
  @Prop({ default: '' }) unit: string;
  // 图表系列数据
  @Prop() series: MonitorEchartSeries;
  // 图表高度
  @Prop({ default: 310 }) height: number | string;
  @Prop({
    default: () => [
      '#2ec7c9',
      '#b6a2de',
      '#5ab1ef',
      '#ffb980',
      '#d87a80',
      '#8d98b3',
      '#e5cf0d',
      '#97b552',
      '#95706d',
      '#dc69aa',
      '#07a2a4',
      '#9a7fd1',
      '#588dd5',
      '#f5994e',
      '#c05050',
      '#59678c',
      '#c9ab00',
      '#7eb00a',
      '#6f5553',
      '#c14089',
    ],
  })
  // 图标系列颜色集合
  colors: string[];

  @Prop({
    default() {
      return '查无数据';
    },
  })
  emptyText: string;

  // 监控图表默认配置
  get defaultOptions() {
    if (['bar', 'line'].includes(this.chartType)) {
      return {
        tooltip: {
          crossStyle: {
            color: 'transparent',
            opacity: 0,
            width: 0,
          },
          appendToBody: true,
          axisPointer: {
            type: 'cross',
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
            axis: 'auto',
          },
          formatter: this.handleSetTooltip,
        },
      };
    }
    return {};
  }
  get chartOption() {
    return deepMerge(
      {
        legend: {
          asTable: false, // 是否转换为table图例
          toTheRight: false, // 图例位置在右侧
        },
        tool: {
          show: true, // 工具栏是否显示
          moreShow: true, // 更多工具栏是否显示
        },
        annotation: {
          show: false, // 是否显示annotation
        },
        grid: {
          left: 20,
        },
      },
      this.options || {}
    );
  }
  get chartHeight() {
    let { height } = this;
    if (this.chartTitle) {
      height -= 36;
    }
    if (!this.chartOption.legend.toTheRight && this.legend.show) {
      height -= 30;
    }
    return height;
  }
  @Watch('height')
  onHeightChange() {
    this.chart?.resize();
  }
  @Watch('refreshInterval', { immediate: true })
  onRefreshIntervalChange(v) {
    if (this.refreshIntervalInstance) {
      window.clearInterval(this.refreshIntervalInstance);
    }
    if (!v || +v < 60 * 1000 || !this.getSeriesData) return;
    this.refreshIntervalInstance = window.setInterval(() => {
      this.handleSeriesData();
    }, v);
  }
  @Watch('series')
  onSeriesChange(v) {
    this.handleSetChartData(deepMerge({}, { series: v }));
  }

  mounted() {
    if (this.series) {
      this.initChart();
      this.handleSetChartData(deepMerge({}, { series: this.series }));
    } else if (this.chartOption?.series?.length) {
      this.initChart();
      this.handleSetChartData(deepMerge({}, this.chartOption));
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
    this.annotation.show = false;
    this.refreshIntervalInstance && window.clearInterval(this.refreshIntervalInstance);
  }
  destroyed() {
    this.chart && this.destroy();
  }
  initChart() {
    const chart: any = echarts.init(this.chartRef);
    // chart.setOption({}, true)
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

  /** 转换接口series的数据 */
  handleTransformSeries(data) {
    return {
      ...data,
      series: data.series.map(item => ({
        ...item,
        symbolSize: 6,
        showSymbol: false, // 默认不显示点，只有hover时候显示该点
      })),
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
      const hasSeries = series && series.length > 0 && series.some(item => item.data?.length);
      this.chartOptionInstance = new EchartOptions({
        chartType: this.chartType,
        colors: this.colors,
        showExtremum: this.chartOption.legend.asTable,
        chartOption: this.chartOption,
      } as any);
      const optionData = this.chartOptionInstance.getOptions(this.handleTransformSeries(data), {});
      const legendShow =
        this.options?.legend && Object.hasOwn(this.options.legend, 'show') ? this.options.legend.show : true;
      if (['bar', 'line'].includes(this.chartType)) {
        this.legend.show = legendShow && hasSeries && optionData.legendData.length > 0;
      } else {
        this.legend.show = optionData.options.lengend
          ? Object.hasOwn(optionData.options.lengend, 'show')
            ? optionData.options.lengend.show
            : true
          : false;
      }
      this.legend.list = optionData.legendData || [];
      if (this.chartOption.grid) {
        optionData.options.grid.bottom = this.chartOption.grid.bottom;
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
        resolve(undefined);
      }, 320);
    });
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

    const liHtmlList = params.map(item => {
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
      return `<li style="display: flex;align-items: center;">
                <span
                 style="background-color:${item.color};margin-right: 10px;width: 6px;height: 6px; border-radius: 50%;">
                </span>
                <span style="${markColor}">${item.seriesName}:</span>
                <span style="${markColor} flex: 1;margin-left: 5px;">
                ${item.value[1]}${this.chartUnit || this.unit}</span>
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
    if (!this.chartOption.annotation.show) {
      return;
    }
    if (this.chartType === 'line' && this.chart && this.curValue.dataIndex >= 0) {
      const { series } = this.chart.getOption() as any;
      if (series?.length) {
        const setPixel = this.chart.convertToPixel({ seriesIndex: this.curValue.seriesIndex }, [
          this.curValue.xAxis,
          this.curValue.yAxis,
        ]);
        const chartWidth = this.chart.getWidth();
        this.annotation = {
          x: setPixel[0] + 10 + 220 > chartWidth ? setPixel[0] - 10 - 220 : setPixel[0] + 10,
          y: setPixel[1] + 5,
          title: dayjs.tz(this.curValue.xAxis).format('YYYY-MM-DD HH:mm:ss'),
          name: this.curValue.name,
          color: this.curValue.color,
          show: true,
        };
        this.charWrapRef.focus();
      }
    } else {
      this.annotation.show = false;
    }
  }
  // 点击更多工具栏触发
  handleMoreToolItemSet(item: IMoreToolItem) {
    switch (item.id) {
      case 'area':
        this.handleTransformArea(item.checked);
        break;
      case 'set':
        this.handleSetYAxisSetScale(!item.checked);
        break;
      default:
        break;
    }
  }
  handleSetYAxisSetScale(needScale) {
    if (this.chartType === 'line' && this.chart) {
      const options = this.chart.getOption();
      this.chart.setOption({
        ...options,
        yAxis: {
          scale: needScale,
        },
      });
    }
  }
  handleTransformArea(isArea: boolean) {
    if (this.chartType === 'line' && this.chart) {
      const options = this.chart.getOption();
      this.chart.setOption({
        ...options,
        series: options.series.map((item, index) => ({
          ...item,
          areaStyle: {
            color: isArea ? hexToRgbA(this.colors[index % this.colors.length], 0.5) : 'transparent',
          },
        })),
      });
    }
  }
  handleCharBlur() {
    this.annotation.show = false;
  }

  handleLegendEvent({ actionType, item }: { actionType: string; item: ILegendItem }) {
    if (['highlight', 'downplay'].includes(actionType)) {
      this.chart.dispatchAction({
        type: actionType,
        seriesName: item.name,
      });
    } else if (actionType === 'shift-click') {
      this.chart.dispatchAction({
        type: actionType,
        name: item.name,
      });
    } else if (actionType === 'click') {
      const hasOtherShow = this.legend.list.some(set => set.name !== item.name && set.show);
      this.legend.list.forEach(legend => {
        this.chart.dispatchAction({
          type: legend.name === item.name || !hasOtherShow ? 'legendSelect' : 'legendUnSelect',
          name: legend.name,
        });
        legend.show = legend.name === item.name || !hasOtherShow;
      });
    }
  }

  // 下载图表为png图片
  handleStoreImage() {
    if (window.navigator.msSaveOrOpenBlob) {
      toBlob(this.$el as HTMLDivElement)
        .then(blob => window.navigator.msSaveOrOpenBlob(blob, `${this.title}.png`))
        .catch(() => {});
    } else {
      toPng(this.$el as HTMLDivElement)
        .then(dataUrl => {
          const tagA = document.createElement('a');
          tagA.download = `${this.title}.png`;
          tagA.href = dataUrl;
          document.body.appendChild(tagA);
          tagA.click();
          tagA.remove();
        })
        .catch(() => {});
    }
  }

  // 设置全屏
  handleFullScreen() {
    this.isFullScreen = !this.isFullScreen;
    if (this.isFullScreen) {
      this.childProps = Object.assign({}, this.$props, {
        height: window.innerHeight - 80,
        needChild: false,
        needFullScreen: false,
      });
    }
    this.$emit('full-screen', this.isFullScreen);
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
  background-position: top;
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
