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
    :style="{ 'background-image': backgroundUrl }"
    class="monitor-echart-wrap"
  >
    <div
      v-if="chartTitle || $slots.title"
      class="echart-header"
    >
      <chart-title
        :title="chartTitle"
        :subtitle="chartSubTitle"
        :menu-list="chartOption.tool.list"
        @menu-click="handleMoreToolItemSet"
      />
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
      @dblclick.prevent="handleChartDblClick"
    >
      <div
        ref="chartRef"
        class="echart-instance"
        :style="{ height: chartHeight - 10 + 'px' }"
        @click.stop="handleChartClick"
      >
        <div
          v-if="chartType === 'status'"
          :series="statusSeries"
        />
        <div
          v-else-if="chartType === 'text'"
          :series="textSeries"
        />
      </div>
      <div
        class="echart-legend"
        :style="{
          maxHeight:
            (chartOption.legend.toTheRight ? height - (chartTitle ? 36 : 0) - 5 : chartOption.legend.maxHeight) + 'px',
        }"
      >
        <chart-legend
          v-if="legend.show"
          :legend-data="legend.list"
          :legend-type="chartOption.legend.asTable ? 'table' : 'common'"
          :to-the-right="chartOption.legend.toTheRight"
          @legend-event="handleLegendEvent"
        />
      </div>
      <div
        v-if="chartType === 'pie'"
        class="echart-pie-center"
      >
        <slot name="chartCenter" />
      </div>
      <chart-annotation
        v-if="chartOption.annotation.show"
        :annotation="annotation"
      />
    </div>
    <div
      v-if="setNoData"
      v-show="noData || !series || !series.length"
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
import { toBlob, toPng } from 'html-to-image';
import { debounce } from 'throttle-debounce';

import ChartAnnotation from './components/chart-annotation.vue';
import ChartLegend from './components/chart-legend.vue';
import ChartTitle from './components/chart-title.vue';
import ChartTools from './components/chart-tools.vue';
import EchartOptions from './options/echart-options';
import { type MonitorEchartOptions, type MonitorEchartSeries, echarts } from './types/monitor-echarts';
import ChartInView from './utils/chart-in-view';
import watermarkMaker from './utils/watermarkMaker';
import { getValueFormat } from './valueFormats';

import type {
  ChartType,
  IAnnotation,
  ILegendItem,
  IMoreToolItem,
  IStatusChartOption,
  IStatusSeries,
  ITextChartOption,
  ITextSeries,
} from './options/type-interface';

const hexToRgbA = (hex, apacity = 1) => {
  let c;
  if (/^#([A-Fa-f0-9]{3}){1,2}$/.test(hex)) {
    c = hex.substring(1).split('');
    if (c.length === 3) {
      c = [c[0], c[0], c[1], c[1], c[2], c[2]];
    }
    c = `0x${c.join('')}`;
    return `rgba(${[(c >> 16) & 255, (c >> 8) & 255, c & 255].join(',')},${apacity})`;
  }
  throw new Error('Bad Hex');
};
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
    ChartLegend,
    ChartTools,
    ChartAnnotation,
    ChartTitle,
  },
})
export default class MonitorEcharts extends Vue {
  @Ref() readonly chartRef!: HTMLDivElement;
  @Ref() readonly charWrapRef!: HTMLDivElement;

  // echarts配置项
  @Prop() readonly options: IStatusChartOption | ITextChartOption | MonitorEchartOptions;
  // echarts配置项是否深度监听
  @Prop({ default: true }) readonly watchOptionsDeep: boolean;
  // 是否自动resize
  @Prop({ default: true }) readonly autoresize: boolean;
  // 是否需要设置全屏
  @Prop({ default: true }) readonly needFullScreen: boolean;
  // 是有fullscreen递归
  @Prop({ default: true }) readonly needChild: boolean;
  // 是使用组件内的无数据设置
  @Prop({ default: true }) readonly setNoData: boolean;
  // 图表刷新间隔
  @Prop({ default: 0 }) readonly refreshInterval: number;
  // 图表类型
  @Prop({ default: 'line' }) readonly chartType: ChartType;
  // 图表title
  @Prop({ default: '' }) readonly title: string;
  @Prop({ default: '' }) readonly subtitle: string;
  // 图表系列数据
  @Prop() readonly series: IStatusSeries | ITextSeries | MonitorEchartSeries;

  // 背景图
  @Prop({
    type: String,
    default() {
      return `url('${watermarkMaker(window.user_name || window.username)}')`;
    },
  })
  backgroundUrl: string;

  // 获取图标数据
  @Prop() getSeriesData: (timeFrom?: string, timeTo?: string, range?: boolean) => Promise<void>;

  @Prop({
    default: () => [
      '#7EB26D', // 0: pale green
      '#EAB839', // 1: mustard
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
      '#DEDAF7',
      '#6ED0E0', // 2: light blue
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

  // 图表高度
  @Prop({ default: 310 }) height: number | string;

  // chart: Echarts.ECharts = null
  resizeHandler: ResizeCallback<HTMLDivElement>;
  unwatchOptions: () => void;
  unwatchSeries: () => void;
  chartTitle = '';
  chartSubTitle = '';
  intersectionObserver: IntersectionObserver = null;
  needObserver = true;
  loading = false;
  noData = false;
  isFullScreen = false;
  timeRange: string[] = [];
  childProps = {};
  annotation: IAnnotation = { x: 0, y: 0, show: false, title: '', name: '', color: '', list: [] };
  curValue: ICurValue = { xAxis: '', yAxis: '', dataIndex: -1, color: '', name: '', seriesIndex: -1 };
  refreshIntervalInstance = 0;
  chartOptionInstance = null;
  hasInitChart = false;
  legend: { list: ILegendItem[]; show: boolean } = {
    show: false,
    list: [],
  };
  statusSeries: IStatusSeries[] = []; // status图表数据
  textSeries: ITextSeries = {}; // status图表数据
  curChartOption: any;
  chart = null;
  clickTimer = null;
  chartInView: ChartInView = null;
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
          appendToBody: true,
          formatter: this.handleSetTooltip,
          position: (pos, params, dom, rect, size) => {
            if (this.chartInView?.chartInTop === undefined) {
              const domRect = this.$el.getBoundingClientRect();
              if (!this.chartInView) {
                this.chartInView = new ChartInView(domRect.y < 100, domRect.bottom + 20 >= window.innerHeight);
              } else {
                this.chartInView.setCharInView(domRect.y < 100, domRect.bottom + 20 >= window.innerHeight);
              }
            }
            const isBig = pos[1] > size.viewSize[1] / 2;
            if (this.chartInView.chartInBottom || (!this.chartInView.chartInTop && isBig)) {
              return {
                left: pos[0] + 20,
                bottom: size.viewSize[1] - pos[1] + 20,
              };
            }
            return {
              left: pos[0] + 20,
              top: pos[1] + -20,
            };
          },
        },
      };
    }
    return {};
  }
  get chartOption(): MonitorEchartOptions {
    return deepMerge(
      {
        legend: {
          asTable: false, // 是否转换为table图例
          toTheRight: false, // 图例位置在右侧
          maxHeight: 30, // 图例最大高度 只对toTheRight为false有效
        },
        tool: {
          show: true, // 工具栏是否显示
          moreList: ['explore', 'set', 'strategy', 'area'], // 要显示的多工具栏的配置id 空数组则为不显示
          list: ['save', 'screenshot', 'fullscreen', 'explore', 'set', 'strategy', 'area'],
        },
        annotation: {
          show: false, // 是否显示annotation
          list: ['ip', 'process', 'strategy'], // 要显示的anotation配置id 空数组则为不显示
        },
      },
      this.options || {},
      {
        arrayMerge: (destinationArray, sourceArray) => sourceArray,
      }
    );
  }
  get chartHeight() {
    let { height } = this;
    if (this.chartTitle) {
      height -= 36;
    }
    if (!this.chartOption.legend.toTheRight && this.legend.show) {
      height -= this.chartOption.legend.maxHeight;
    }
    return height;
  }
  get isEchartsRender() {
    return !['status', 'text'].includes(this.chartType);
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
    this.chartTitle = this.title;
    this.chartSubTitle = this.subtitle;
    if (this.isEchartsRender) {
      const chart: any = echarts.init(this.chartRef);
      this.chart = chart;
      if (this.autoresize) {
        const handler = debounce(300, () => this.resize());
        this.resizeHandler = async () => {
          await this.$nextTick();
          this.chartRef?.offsetParent !== null && handler();
        };
        addListener(this.chartRef, this.resizeHandler);
      }
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
      const data = await this.getSeriesData(startTime, endTime, isRange).catch(() => ({ series: [] }));
      if (
        !this.isEchartsRender ||
        (Array.isArray(data) && data.length && data.some(item => item)) ||
        (data && Object.hasOwn(data, 'series') && data.series.length)
      ) {
        await this.handleSetChartData(data);
      } else {
        this.noData = true;
      }
    } catch (e) {
      console.info(e);
      this.noData = true;
    } finally {
      this.chartTitle = this.title;
      this.chartSubTitle = this.subtitle;
      this.loading = false;
    }
  }
  handleTransformSeries(data) {
    if (!data?.series) {
      return data;
    }
    const mapData = {};
    return {
      series: data.series.map(({ datapoints, target, ...item }) => {
        mapData[target] !== undefined ? (mapData[target] += 1) : (mapData[target] = 0);
        return {
          ...item,
          data: datapoints.map(set => (Array.isArray(set) ? set.slice().reverse() : [])),
          name: !mapData[target] ? target : target + mapData[target],
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
      if (this.isEchartsRender) {
        const series: any = deepMerge([], data || []);
        const hasSeries =
          (series && series.length > 0 && series.some(item => item.datapoints?.length)) ||
          (series && Object.hasOwn(series, 'series') && series.series.length);

        this.chartOptionInstance = new EchartOptions({
          chartType: this.chartType,
          colors: this.colors,
          showExtremum: this.chartOption.legend.asTable,
          chartOption: this.chartOption,
        } as any);
        const optionData = this.chartOptionInstance.getOptions(this.handleTransformSeries(series), {});
        if (['bar', 'line'].includes(this.chartType)) {
          this.legend.show = hasSeries && optionData.legendData.length > 0;
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
          if (this.chart) {
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
            this.curChartOption = Object.freeze(Object.assign({}, this.chart.getOption()));
          }
        }, 320);
      } else if (this.chartType === 'status') {
        this.statusSeries = data || [];
        this.curChartOption = {};
        resolve(undefined);
      } else if (this.chartType === 'text') {
        const setData = Array.isArray(data) ? data[0] : data;
        const value = (setData?.datapoints || []).reduce((pre, cur) => {
          if (pre === '') {
            return typeof cur[0] === 'number' ? cur[0] : '';
          }
          return typeof cur[0] === 'number' ? Math.max(pre, cur[0]) : pre;
        }, '');
        const formater = getValueFormat(setData?.unit || '')(+value);
        this.textSeries = {
          value: +formater.text || '',
          unit: formater.suffix,
        };
        this.curChartOption = {};
        resolve(undefined);
      }
    }).finally(() => {
      this.chartTitle = this.title;
      this.chartSubTitle = this.subtitle;
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
      const curSeries = this.curChartOption.series[item.seriesIndex];
      const unitFormatter = curSeries.unitFormatter || (v => ({ text: v }));
      const precision = curSeries.unit !== 'none' && +curSeries.precision < 1 ? 2 : +curSeries.precision;
      const valueObj = unitFormatter(item.value[1], precision);
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
    clearTimeout(this.clickTimer);
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
    clearTimeout(this.clickTimer);
    this.clickTimer = setTimeout(() => {
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
          const { dimensions = {}, metric = {} } = series[this.curValue.seriesIndex];
          const { annotation } = this.chartOption;
          const chartWidth = this.chart.getWidth();
          this.annotation = {
            x: setPixel[0] + 10 + 220 > chartWidth ? setPixel[0] - 10 - 220 : setPixel[0] + 10,
            y: setPixel[1] + 5,
            title: dayjs.tz(this.curValue.xAxis).format('YYYY-MM-DD HH:mm:ss'),
            name: this.curValue.name,
            color: this.curValue.color,
            show: true,
            list: [
              {
                id: 'ip',
                show: annotation.list.includes('ip') && !!dimensions.bk_target_ip,
                value: `${dimensions.bk_target_ip}${
                  dimensions.bk_target_cloud_id ? `-${dimensions.bk_target_cloud_id}` : ''
                }`,
              },
              {
                id: 'process',
                show: annotation.list.includes('process') && (!!dimensions.process_name || !!dimensions.display_name),
                value: {
                  processId: dimensions.process_name || dimensions.display_name || '',
                  id: `${dimensions.bk_target_ip}-${dimensions.bk_target_cloud_id}`,
                },
              },
              {
                id: 'strategy',
                show: annotation.list.includes('strategy') && !!metric.metric_field,
                value: `${metric.result_table_id}.${metric.metric_field}`,
              },
            ],
          };
          this.charWrapRef.focus();
          this.chart.dispatchAction({ type: 'hideTip' });
        }
      } else {
        this.annotation.show = false;
      }
    }, 300);
  }
  // 点击更多工具栏触发
  handleMoreToolItemSet(item: IMoreToolItem) {
    switch (item.id) {
      case 'save':
        this.handleCollectChart();
        break;
      case 'screenshot':
        this.handleStoreImage();
        break;
      case 'fullscreen':
        this.handleFullScreen();
        break;
      case 'area':
        this.handleTransformArea(item.checked);
        break;
      case 'set':
        this.handleSetYAxisSetScale(!item.checked);
        break;
      case 'explore':
        this.handleExplore();
        break;
      case 'strategy':
        this.handleAddStrategy();
        break;
      default:
        break;
    }
  }
  handleSetYAxisSetScale(needScale) {
    this.$emit('on-yaxis-set-scale', needScale);
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
    this.$emit('on-transform-area', isArea);
    if (this.chartType === 'line' && this.chart) {
      const options = this.chart.getOption();
      this.chart.setOption({
        ...options,
        series: options.series.map((item, index) => ({
          ...item,
          areaStyle: {
            color: isArea ? hexToRgbA(this.colors[index % this.colors.length], 0.2) : 'transparent',
          },
        })),
      });
    }
  }
  handleExplore() {
    this.$emit('export-data-retrieval');
  }
  handleAddStrategy() {
    this.$emit('add-strategy');
  }
  handleCharBlur() {
    this.annotation.show = false;
  }

  handleLegendEvent({ actionType, item }: { actionType: string; item: ILegendItem }) {
    // if (['highlight', 'downplay'].includes(actionType)) {
    //   this.chart.dispatchAction({
    //     type: actionType,
    //     seriesName: item.name
    //   })
    // } else
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

  handleCollectChart() {
    this.$emit('collect-chart');
  }

  // 设置全屏
  handleFullScreen() {
    this.$emit('full-screen');
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
      (v, ov) => {
        if (this.getSeriesData) {
          JSON.stringify(v) !== JSON.stringify(ov) && this.handleSeriesData();
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
  padding-left: 10px;
  color: #63656e;
  background-color: #fff;
  background-repeat: repeat;
  background-position: center;
  border-radius: 2px;

  .echart-header {
    display: flex;
    align-items: center;
    min-width: 100%;
    font-weight: 700;
    color: #63656e;
  }

  .chart-wrapper {
    position: relative;
    display: flex;

    .echart-instance {
      display: flex;
      flex: 1;
      min-width: 100px;
      height: 310px;
      overflow: hidden;
    }

    .echart-legend {
      margin-top: 8px;
      margin-left: 16px;
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
