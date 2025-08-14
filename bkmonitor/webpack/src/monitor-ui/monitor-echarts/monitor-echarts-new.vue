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
    v-bkloading="{ isLoading: loading, zIndex: 2000 }"
    :style="{ 'background-image': backgroundUrl }"
    class="monitor-echart-wrap"
    @mouseenter="isHover = true"
    @mouseleave="isHover = false"
  >
    <div
      v-if="chartTitle || $slots.title"
      class="echart-header"
    >
      <slot name="title">
        <chart-title
          class="chart-title-wrap"
          :menu-list="chartOption.tool.list"
          :show-more="!readonly && showTitleTool"
          :subtitle="chartSubTitle"
          :title="chartTitle"
          @menuClick="handleMoreToolItemSet"
          @selectChild="handleSelectChildMenu"
        />
      </slot>
    </div>
    <div
      ref="charWrapRef"
      :style="{
        flexDirection: !chartOption.legend.toTheRight ? 'column' : 'row',
        minHeight: chartWrapHeight + 'px',
        maxHeight: chartWrapHeight + 'px',
      }"
      class="chart-wrapper-echarts"
      tabindex="-1"
      @blur="handleCharBlur"
    >
      <div
        v-if="!noData"
        :style="{ height: chartHeight + 'px' }"
        class="echart-instance-wrap"
      >
        <div
          ref="chartRef"
          class="echart-instance"
          @click.stop="handleChartClick"
          @dblclick.prevent="handleChartDblClick"
        >
          <status-chart
            v-if="chartType === 'status'"
            :series="statusSeries"
          />
          <text-chart
            v-else-if="chartType === 'text'"
            :series="textSeries"
          />
          <table-chart
            v-else-if="chartType === 'table'"
            :max-height="chartHeight + 'px'"
            :series="tableSeries"
          />
        </div>
        <span
          v-if="showRestore"
          class="chart-restore"
          @click="handleChartRestore"
        >
          {{ $t('复位') }}
        </span>
      </div>
      <div
        v-if="!noData"
        :style="{
          maxHeight: (chartOption.legend.toTheRight ? chartHeight : chartOption.legend.maxHeight) + 'px',
        }"
        class="echart-legend"
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
        v-if="!readonly && chartOption.annotation.show"
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
    <div
      v-if="scatterTips.show && hasTraceInfo"
      ref="scatterTipsRef"
      v-bk-clickoutside="handleScatterTipOutside"
      :style="{
        left: `${scatterTips.left}px`,
        top: `${scatterTips.top}px`,
      }"
      class="scatter-tips"
    >
      <div class="time">
        {{ scatterTips.data.time }}
      </div>
      <div
        v-for="(item, index) in scatterTips.data.list"
        :key="index"
        class="info-item"
      >
        <span class="label">{{ item.label }}: </span>
        <span
          v-if="item.type === 'link'"
          class="content"
        >
          <span
            :class="['link', { pointer: item.label === 'traceID' }]"
            @click="() => handleTraceLink(item)"
          >
            {{ item.content }}
          </span>
          <span
            class="icon-monitor copy icon-mc-copy"
            @click="() => handleCopy(item.content)"
          />
        </span>
        <span v-else-if="item.type === 'string'">
          {{ item.content }}
        </span>
      </div>
      <div class="bottom">
        <span
          :style="{ background: scatterTips.data.target.color }"
          class="point"
        />
        <span class="label">{{ scatterTips.data.target.label }}</span>
      </div>
    </div>
    <span
      v-if="errorMsg"
      v-bk-tooltips="{
        content: errorMsg,
        placement: 'top-start',
        extCls: 'monitor-wrapper-error-tooltip',
        allowHTML: false,
      }"
      class="is-error"
    />
    <div
      v-if="hasResize"
      class="chart-resize-line"
      @mousedown="handleResize"
    />

    <div
      v-if="hasTable"
      class="chart-table-box"
    >
      <div class="chart-table-title">
        <span>{{ $t('原始数据') }}</span>
        <span class="title-count">{{ $t('共 {num} 条', { num: tableData?.length || 0 }) }}</span>
        <bk-button
          class="export-csv-btn"
          size="small"
          @click="handleExportCsv"
        >
          {{ $t('导出CSV') }}
        </bk-button>
      </div>

      <bk-table
        class="chart-table"
        :virtual-render="{
          lineHeight: 32,
        }"
        :data="tableData"
        :height="tableHeight"
      >
        <bk-table-column
          :label="$t('时间')"
          min-width="180"
          prop="date"
          sortable
        />
        <bk-table-column
          v-for="item of seriesData"
          :key="item.target"
          :label="item.target"
          :prop="item.key"
          :render-header="renderHeader"
          min-width="120"
          sortable
        >
          <template #default="{ row }">
            {{ row[item.key] }}
          </template>
        </bk-table-column>
      </bk-table>
    </div>
  </div>
</template>
<script lang="ts">
import type { CreateElement } from 'vue';

import { Component, Inject, InjectReactive, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { type ResizeCallback, addListener, removeListener } from '@blueking/fork-resize-detector';
import dayjs from 'dayjs';
import deepMerge from 'deepmerge';
import { toBlob, toPng } from 'html-to-image';
import { traceListById } from 'monitor-api/modules/apm_trace';
import { copyText, hexToRgbA } from 'monitor-common/utils/utils';
import { type IUnifyQuerySeriesItem, downCsvFile } from 'monitor-pc/pages/view-detail/utils';
import { debounce } from 'throttle-debounce';

import ChartTitle from '../chart-plugins/components/chart-title/chart-title';
import ChartAnnotation from './components/chart-annotation.vue';
import ChartLegend from './components/chart-legend.vue';
import ChartTools from './components/chart-tools.vue';
import StatusChart from './components/status-chart.vue';
import TableChart from './components/table-chart';
import TextChart from './components/text-chart.vue';
import './map/china';
import { colorList } from './options/constant';
import EchartOptions from './options/echart-options';
import { type MonitorEchartOptions, type MonitorEchartSeries, echarts } from './types/monitor-echarts';
import watermarkMaker from './utils/watermarkMaker';
import { getValueFormat } from './valueFormats';

import type {
  ChartType,
  IAnnotation,
  ILegendItem,
  IMoreToolItem,
  IStatusChartOption,
  IStatusSeries,
  ITableSeries,
  ITextChartOption,
  ITextSeries,
} from './options/type-interface';

interface IAlarmStatus {
  alert_number: number;
  status: number;
  strategy_number: number;
}

interface ICurValue {
  color: string;
  dataIndex: number;
  name: string;
  seriesIndex: number;
  seriesType?: string;
  xAxis: number | string;
  yAxis: number | string;
}
@Component({
  name: 'monitor-echarts',
  components: {
    ChartLegend,
    ChartTools,
    ChartAnnotation,
    StatusChart,
    TextChart,
    ChartTitle,
    TableChart,
  },
})
export default class MonitorEcharts extends Vue {
  @Ref() readonly chartRef!: HTMLDivElement;
  @Ref() readonly charWrapRef!: HTMLDivElement;

  // echarts配置项
  @Prop() readonly options: IStatusChartOption | ITextChartOption | MonitorEchartOptions;
  // 是否自动resize
  @Prop({ default: true }) readonly autoresize: boolean;
  // 是否需要设置全屏
  @Prop({ default: true }) readonly needFullScreen: boolean;
  // 当前业务id （用于告警详情视图信息）
  @Prop({ default: '' }) readonly curBizId: string;
  // 是有fullscreen递归
  @Prop({ default: true }) readonly needChild: boolean;
  // echarts配置项是否深度监听
  @Prop({ default: true }) readonly watchOptionsDeep: boolean;
  // 是使用组件内的无数据设置
  @Prop({ default: true }) readonly setNoData: boolean;
  // 图表刷新间隔
  @Prop({ default: 0 }) readonly refreshInterval: number;
  @Prop({ default: '' }) readonly subtitle: string;
  // 图表类型
  @Prop({ default: 'line' }) readonly chartType: ChartType;
  // 图表title
  @Prop({ default: '' }) readonly title: string;
  @Prop({ default: '', type: String }) readonly errorMsg: string;
  // 图表系列数据
  @Prop() readonly series: IStatusSeries | ITextSeries | MonitorEchartSeries;

  // 背景图
  @Prop({
    type: String,
    default() {
      return window.graph_watermark ? `url('${watermarkMaker(window.user_name || window.username)}')` : '';
    },
  })
  backgroundUrl: string;

  // 获取图标数据
  @Prop() getSeriesData: (timeFrom?: string, timeTo?: string, range?: boolean) => Promise<any[]>;
  // 获取指标告警状态信息
  @Prop() getAlarmStatus: (param: any) => Promise<IAlarmStatus>;

  @Prop({
    default: () => colorList,
  })
  // 图标系列颜色集合
  colors: string[];

  @Prop({
    default() {
      return this.$t('查无数据');
    },
  })
  emptyText: string;

  /* line chart 是否包含trace信息散点图 */
  @Prop({ type: Boolean, default: false }) hasTraceInfo: boolean;

  // 图表高度
  @Prop({ default: 310, type: [Number, String] }) height: number | string;
  @Prop({ default: 1, type: [Number, String] }) lineWidth: number;
  // 是否需要展示头部工具栏
  @Prop({ default: false, type: Boolean }) needTools: boolean;
  /** 分组id */
  @Prop({ type: String }) groupId: string;
  /* 调用trace接口需要传入时间范围 */
  @Prop({ type: Object, default: () => ({}) }) traceInfoTimeRange: { end_time: number; start_time: number };
  /** 是否需要高度拉伸功能 */
  @Prop({ type: Boolean, default: false }) hasResize: boolean;
  /** 是否需要图表表格功能 */
  @Prop({ type: Boolean, default: false }) hasTable: boolean;
  @InjectReactive({ from: 'readonly', default: false }) readonly readonly: boolean;
  // 框选事件范围后需应用到所有图表(包含三个数据 框选方法 是否展示复位  复位方法)
  @InjectReactive({ from: 'showRestore', default: false }) readonly showRestoreInject: boolean;
  @Inject({ from: 'enableSelectionRestoreAll', default: false }) readonly enableSelectionRestoreAll: boolean;
  @Inject({ from: 'handleChartDataZoom', default: () => null }) readonly handleChartDataZoom: (
    value: string[],
    immediateQuery?: boolean
  ) => void;
  @Inject({ from: 'handleRestoreEvent', default: () => null }) readonly handleRestoreEvent: () => void;
  // chart: Echarts.ECharts = null
  resizeHandler: ResizeCallback<HTMLDivElement>;
  unwatchOptions: () => void;
  unwatchSeries: () => void;
  needObserver = true;
  intersectionObserver: IntersectionObserver = null;
  loading = false;
  noData = false;
  timeRange: string[] = [];
  chartTitle = '';
  isFullScreen = false;
  childProps = {};
  annotation: IAnnotation = { x: 0, y: 0, show: false, title: '', name: '', color: '', list: [] };
  curValue: ICurValue = { xAxis: '', yAxis: '', dataIndex: -1, color: '', name: '', seriesIndex: -1, seriesType: '' };
  chartSubTitle = '';
  chartOptionInstance = null;
  hasInitChart = false;
  refreshIntervalInstance = 0;
  legend: { list: ILegendItem[]; show: boolean } = {
    show: false,
    list: [],
  };
  textSeries: ITextSeries = {}; // status图表数据
  tableSeries: ITableSeries = {}; // table图表数据
  curChartOption: any;
  statusSeries: IStatusSeries[] = []; // status图表数据
  chart = null;
  localChartHeight = 0; //
  clickTimer = null;
  showTitleTool = true;
  extendMetricData: any = null;
  alarmStatus: IAlarmStatus = { status: 0, alert_number: 0, strategy_number: 0 };
  // tooltips大小 [width, height]
  tooltipSize: number[];
  // tableToolSize
  tableToolSize = 0;
  tableHeight = 0;
  /** 导出csv数据时候使用 */
  seriesData: IUnifyQuerySeriesItem[] = [];
  /*  */
  scatterTips = {
    show: false,
    top: 100,
    left: 0,
    data: {
      time: '',
      list: [],
      target: {
        color: 'red',
        label: 'CPU: 0.99',
      },
    },
  };
  /* 是否展示复位按钮 */
  showRestore = false;
  /** 图表拉伸记录 */
  drawRecord = {
    /** 上一次Y轴坐标 */
    lastY: 0,
    // 是否处于移动中
    moving: false,
  };
  isHover = false; // 是否处于hover状态
  isIntersecting = false; // 是否处于可视区域
  // 监控图表默认配置
  get defaultOptions(): MonitorEchartOptions {
    if (this.chartType === 'bar' || this.chartType === 'line') {
      return {
        tooltip: {
          axisPointer: {
            axis: 'auto',
            type: 'cross',
            label: {
              show: false,
              formatter: params => {
                if (this.chartType !== 'line') return '';
                if (params.axisDimension === 'y') {
                  this.curValue.yAxis = params.value;
                } else {
                  this.curValue.xAxis = params.value;
                  this.curValue.dataIndex = params.seriesData?.length ? params.seriesData[0].dataIndex : -1;
                }
                return '';
              },
            },
            crossStyle: {
              opacity: 0,
              width: 0,
              color: 'transparent',
            },
          },
          formatter: this.handleSetTooltip,
          appendToBody: true,
          position: (pos, _params, _dom, _rect, size) => {
            const { contentSize } = size;
            const chartRect = this.$el.getBoundingClientRect();
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
            if (canSetLeft > 0) {
              position.left = +pos[0] + Math.min(20, canSetLeft);
            } else {
              position.left = +pos[0] - contentSize[0] - 20;
            }
            if (contentSize[0]) this.tooltipSize = contentSize;
            return {
              left: position.left,
              top: position.top < -chartRect.y ? -chartRect.y - 50 : position.top,
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
          list: ['save', 'screenshot', 'fullscreen', 'explore', 'set', 'strategy', 'area', 'relate-alert'],
        },
        annotation: {
          show: false, // 是否显示annotation
          list: ['ip', 'process', 'strategy'], // 要显示的anotation配置id 空数组则为不显示
        },
      },
      (this.options || {}) as MonitorEchartOptions,
      {
        arrayMerge: (_destinationArray, sourceArray) => sourceArray,
      }
    );
  }
  get chartWrapHeight() {
    let { localChartHeight } = this;
    if (this.chartTitle) {
      localChartHeight = Number(localChartHeight) - 36;
    }
    if (this.hasResize) {
      localChartHeight = Number(localChartHeight) - 10;
    }
    return localChartHeight;
  }
  get chartHeight() {
    let { chartWrapHeight } = this;
    if (!this.chartOption.legend.toTheRight && this.legend.show) {
      chartWrapHeight = Number(chartWrapHeight) - this.chartOption.legend.maxHeight;
    }
    return chartWrapHeight;
  }
  get isEchartsRender() {
    return !['status', 'text', 'table'].includes(this.chartType);
  }

  get tableData() {
    /** { time: 各个图表在同一时间点的值 } */
    const data: { [key: string]: { [key: string]: number } } = this.seriesData.reduce((pre, cur) => {
      cur.datapoints.forEach(item => {
        pre[item[1]] = { ...pre[item[1]], [cur.key]: item[0] };
      });
      return pre;
    }, {});
    return Object.entries(data).map(([time, columnData]) => {
      return {
        date: dayjs.tz(Number(time)).format('YYYY-MM-DD HH:mm:ss'),
        ...columnData,
      };
    });
  }

  @Watch('noData')
  onNoDataChange(v) {
    this.$emit('no-data-change', v);
  }

  @Watch('height', { immediate: true })
  onHeightChange(val) {
    this.localChartHeight = val ?? 0;
  }
  @Watch('localChartHeight')
  onLocalChartHeightChange() {
    this?.chart?.resize?.();
  }
  @Watch('refreshInterval', { immediate: true })
  onRefreshIntervalChange(v) {
    if (this.refreshIntervalInstance) {
      window.clearInterval(this.refreshIntervalInstance);
    }
    if (!v || +v < 60 * 1000 || !this.getSeriesData) return;
    this.refreshIntervalInstance = window.setInterval(() => {
      // 上次接口未返回时不执行请求
      !this.loading && this.chart && this.handleSeriesData();
    }, v);
  }
  @Watch('series')
  onSeriesChange(v) {
    this.handleSetChartData(deepMerge({}, { series: v }));
  }
  @Watch('showRestoreInject', { immediate: true })
  handleShowRestoreInject(v: boolean) {
    this.showRestore = v;
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
    this.onRefreshIntervalChange(this.refreshInterval);
    if (this.autoresize) {
      this.chart?.resize?.();
    }
  }
  deactivated() {
    this.refreshIntervalInstance && window.clearInterval(this.refreshIntervalInstance);
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
    document.removeEventListener('mousemove', this.documentMousemove);
    document.removeEventListener('mouseup', this.documentMouseup);
  }

  renderHeader(h: CreateElement, data) {
    const { column } = data;
    return h(
      'div',
      {
        class: 'ellipsis',
        directives: [{ name: 'bk-overflow-tips' }],
      },
      column.label
    );
  }

  /** 图表拉伸 */
  documentMousemove(e) {
    this.drawRecord.moving = true;
    this.localChartHeight += e.clientY - this.drawRecord.lastY;
    this.drawRecord.lastY = e.clientY;
  }
  /** 拉伸停止 */
  documentMouseup() {
    this.drawRecord.moving = false;
    document.removeEventListener('mousemove', this.documentMousemove);
    document.removeEventListener('mouseup', this.documentMouseup);
  }
  handleResize(e) {
    this.drawRecord.lastY = e.clientY;
    document.addEventListener('mousemove', this.documentMousemove);
    document.addEventListener('mouseup', this.documentMouseup);
  }

  /** 初始化图表表格高度 */
  initTableHeight() {
    // 只会获取一次高度
    if (this.tableHeight !== 0) return;
    this.$nextTick(() => {
      const listHeight = (document.querySelector('.dashboard-panels-list') as HTMLDivElement)?.offsetHeight;
      const headerHeight = (document.querySelector('.echart-header') as HTMLDivElement)?.offsetHeight;
      const resizeLineHeight = (document.querySelector('.chart-resize-line') as HTMLDivElement)?.offsetHeight;
      const chartTableTitle = (document.querySelector('.chart-table-title') as HTMLDivElement)?.offsetHeight;
      // 35： margin + padding + border
      this.tableHeight = listHeight - headerHeight - resizeLineHeight - this.chartWrapHeight - chartTableTitle - 36;
    });
  }

  initChart() {
    this.initTableHeight();
    this.chartTitle = this.title;
    this.chartSubTitle = this.subtitle;
    if (this.isEchartsRender && this.chartRef) {
      const chart: any = echarts.init(this.chartRef);
      this.chart = chart;
      this.groupId && (this.chart.group = this.groupId);
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
      for (const entry of entries) {
        this.isIntersecting = entry.isIntersecting;
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
      }
    });
  }
  // 获取seriesData
  async handleSeriesData(startTime?: string, endTime?: string) {
    this.loading = true;
    if (this.chartType === 'line' && !this.enableSelectionRestoreAll) {
      this.showRestore = !!startTime;
    }
    // this.intersectionObserver?.unobserve?.(this.$el);
    // this.intersectionObserver?.disconnect?.();
    this.needObserver = false;
    try {
      const isRange = startTime && startTime.length > 0 && endTime && endTime.length > 0;
      const data = await this.getSeriesData(startTime, endTime, isRange).catch(() => {
        return [];
      });
      this.seriesData = [...data].map(item => ({
        ...item,
        key: item.target.replace(/\./g, '_'),
      }));
      !this.chart && this.initChart();
      if (!this.isEchartsRender || Array.isArray(data)) {
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
    if (data?.series) {
      return data;
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
      if (this.isEchartsRender) {
        const series: any = deepMerge([], data || []);
        const hasSeries =
          (series && series.length > 0 && series.some(item => item?.datapoints?.length)) ||
          (series && Object.hasOwn(series, 'series') && series.series.length);
        if (!hasSeries) {
          this.noData = !hasSeries;
          resolve(undefined);
          return;
        }
        const realSeries = Object.hasOwn(series, 'series') ? series.series : series;
        if (this.chartType === 'line' && realSeries[0]?.metric) {
          const [
            {
              metric: { metric_field: metricFiled, extend_data: extendData },
            },
          ] = realSeries;
          // 获取图表的指标信息 多指标情况下不显示
          let hasExtendMetricData = extendData;
          if (extendData) {
            hasExtendMetricData = realSeries.every(item => item?.metric?.metric_field === metricFiled);
          }
          this.extendMetricData = hasExtendMetricData ? extendData : null;
          if (hasExtendMetricData && typeof this.getAlarmStatus === 'function') {
            this.getAlarmStatus(extendData.metric_id)
              .then(status => (this.alarmStatus = status))
              .catch(() => (this.alarmStatus = { status: 0, alert_number: 0, strategy_number: 0 }));
          }
        }
        this.chartOptionInstance = new EchartOptions({
          lineWidth: this.lineWidth,
          chartType: this.chartType,
          colors: this.colors,
          showExtremum: this.chartOption.legend.asTable,
          chartOption: this.chartOption,
        });

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
        this.$emit(
          'showLegendChange',
          this.legend.list.filter(v => v.show).map(v => v.name)
        );
        if (this.chartOption.grid) {
          optionData.options.grid.bottom = this.chartOption.grid.bottom;
        }
        setTimeout(() => {
          if (this.chart) {
            let options = deepMerge(optionData.options, this.defaultOptions);
            const width = (this.$refs?.chartRef as any)?.clientWidth;
            const splitNumber = Math.ceil(width / 100);
            if (['line', 'bar'].includes(this.chartType) && width) {
              options = deepMerge(options, {
                xAxis: {
                  splitNumber: splitNumber > 12 ? 12 : splitNumber,
                  min: 'dataMin',
                },
              });
            }
            this.chart.setOption(options, {
              notMerge: true,
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
                    let timeTo = dayjs(+batch.endValue.toFixed(0)).format('YYYY-MM-DD HH:mm');
                    if (!this.showTitleTool) {
                      const dataPoints = this.seriesData?.[0]?.datapoints;
                      if (dataPoints?.length) {
                        const maxX = dataPoints[dataPoints.length - 1]?.[1];
                        if (+batch.endValue.toFixed(0) === maxX) {
                          timeTo = dayjs().format('YYYY-MM-DD HH:mm');
                        }
                      }
                    }
                    this.timeRange = [timeFrom, timeTo];
                    if (this.getSeriesData) {
                      this.chart.dispatchAction({
                        type: 'restore',
                      });
                      if (this.enableSelectionRestoreAll) {
                        this.handleChartDataZoom(JSON.parse(JSON.stringify(this.timeRange)), true);
                      } else {
                        await this.handleSeriesData(timeFrom, timeTo);
                      }
                    }
                    this.$emit('data-zoom', this.timeRange);
                  }
                  this.loading = false;
                  // if (this.showTitleTool) {
                  //   this.loading = true;
                  //   const [batch] = event.batch;
                  //   if (batch.startValue && batch.endValue) {
                  //     const timeFrom = dayjs(+batch.startValue.toFixed(0)).format('YYYY-MM-DD HH:mm');
                  //     const timeTo = dayjs(+batch.endValue.toFixed(0)).format('YYYY-MM-DD HH:mm');
                  //     this.timeRange = [timeFrom, timeTo];
                  //     if (this.getSeriesData) {
                  //       this.chart.dispatchAction({
                  //         type: 'restore'
                  //       });
                  //       if (this.enableSelectionRestoreAll) {
                  //         this.handleChartDataZoom(JSON.parse(JSON.stringify(this.timeRange)));
                  //       } else {
                  //         await this.handleSeriesData(timeFrom, timeTo);
                  //       }
                  //     }
                  //     this.$emit('data-zoom', this.timeRange);
                  //   }
                  //   this.loading = false;
                  // } else {
                  //   this.chart.dispatchAction({
                  //     type: 'restore'
                  //   });
                  // }
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
        const datapoints = setData?.datapoints || [''];
        const [value] = datapoints[datapoints.length - 1];
        const formater = getValueFormat(setData?.unit || '')(+value);
        this.textSeries = {
          value: +formater.text || '',
          unit: formater.suffix,
        };
        this.curChartOption = {};
        resolve(undefined);
      } else if (this.chartType === 'table') {
        this.tableSeries = data[0] || {
          columns: [
            { text: 'time', type: 'time' },
            { text: 'content', type: 'string' },
          ],
          rows: [],
        };
        this.curChartOption = {};
        resolve(undefined);
      }
    });
  }
  // 设置tooltip
  handleSetTooltip(params) {
    if (!this.isIntersecting) {
      return undefined;
    }
    // if (!this.isHover) return undefined;
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
    const list = params.filter(item => !item.seriesName.match(/-no-tips$/));
    const liHtmlList = list
      .slice(0, 50)
      .sort((a, b) => b.value[1] - a.value[1])
      .map(item => {
        let markColor = 'color: #fafbfd;';
        if (data[0].value === item.value[1]) {
          markColor = 'color: #ffffff;font-weight: bold;';
          this.chartType === 'line' &&
            (this.curValue = {
              color: item.color,
              name: item.seriesName,
              seriesIndex: item.seriesIndex,
              dataIndex: item.dataIndex,
              xAxis: item.value[0],
              yAxis: item.value[1],
              seriesType: params.seriesType,
            });
        }
        if (item.value[1] === null) return '';
        const curSeries = this.curChartOption.series[item.seriesIndex];
        const unitFormatter = curSeries.unitFormatter || (v => ({ text: v }));
        const minBase = curSeries.minBase || 0;
        const precision = curSeries.unit !== 'none' && +curSeries.precision < 1 ? 2 : +curSeries.precision;
        const valueObj = unitFormatter(item.value[1] - minBase, precision);
        return `<li class="tooltips-content-item">
                <span class="item-series"
                 style="background-color:${item.color};">
                </span>
                <span class="item-name" style="${markColor}">${item.seriesName}:</span>
                <span class="item-value" style="${markColor}">
                ${valueObj.text} ${valueObj.suffix || ''}</span>
                </li>`;
      });
    if (liHtmlList?.length < 1) return '';
    // 如果超出屏幕高度，则分列展示
    let ulStyle = '';
    const maxLen = Math.ceil((window.innerHeight - 100) / 20);
    if (list.length > maxLen && this.tooltipSize) {
      const cols = Math.ceil(list.length / maxLen);
      this.tableToolSize = this.tableToolSize ? Math.min(this.tableToolSize, this.tooltipSize[0]) : this.tooltipSize[0];
      ulStyle = `display:flex; flex-wrap:wrap; width: ${Math.min(5 + cols * this.tableToolSize, window.innerWidth / 1.8)}px;`;
    }
    const hasTrace = params.some(item => item.seriesName === 'bk_trace_value' && item.seriesType === 'scatter');
    /* 如果包含trace散点则不出现tooltip */
    if (hasTrace || (this.hasTraceInfo && this.scatterTips.show)) {
      return '';
    }
    return `<div class="monitor-chart-tooltips">
            <p class="tooltips-header">
                ${pointTime}
            </p>
            <ul class="tooltips-content" style="${ulStyle}">
                ${liHtmlList?.join('')}
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
  /* 复位 */
  handleChartRestore() {
    if (this.enableSelectionRestoreAll) {
      this.handleRestoreEvent();
    } else {
      this.handleChartDblClick();
    }
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
          const fineTuning = -10;
          this.annotation = {
            x: setPixel[0] + fineTuning + 220 > chartWidth ? setPixel[0] - fineTuning - 220 : setPixel[0] + fineTuning,
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
      case 'relate-alert':
        this.$emit('relate-alert');
      default:
        break;
    }
  }
  /**
   * 点击更多菜单的子菜单
   * @param data 菜单数据
   */
  handleSelectChildMenu(data) {
    switch (data.menu.id) {
      case 'more' /** 更多操作 */:
        if (data.child.id === 'screenshot') {
          /** 截图 */
          setTimeout(() => {
            this.handleStoreImage();
          }, 300);
        } else if (data.child.id === 'export-csv') {
          /** 导出csv */
          this.handleExportCsv();
        }
        break;
      default:
        break;
    }
  }
  /**
   * 根据图表接口响应数据下载csv文件
   */
  handleExportCsv() {
    if (this.seriesData?.length) {
      const csvList = [];
      const keys = Object.keys(this.tableData[0]).filter(key => !['$index'].includes(key));
      csvList.push(keys.map(key => key.replace(/,/gim, '_')).join(','));
      this.tableData.forEach(item => {
        const list = [];
        keys.forEach(key => {
          list.push(item[key]);
        });
        csvList.push(list.join(','));
      });
      downCsvFile(csvList.join('\n'), this.title);
    }
  }
  // 点击title 告警图标跳转
  handleTitleAlarmClick() {
    switch (this.alarmStatus.status) {
      case 0:
        this.handleAddStrategy();
        break;
      case 1:
        window.open(
          location.href.replace(location.hash, `#/strategy-config?metricId=${this.extendMetricData.metric_id}`)
        );
        break;
      case 2:
        window.open(location.href.replace(location.hash, `#/event-center?metricId=${this.extendMetricData.metric_id}`));
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
          min: needScale ? 'dataMin' : 0,
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
    if (this.legend.list.length < 2) {
      return;
    }
    const setOnlyOneMarkArea = () => {
      const showSeries = [];
      this.legend.list.forEach(l => {
        if (l.show) {
          const serice = this.seriesData.find(s => s.target === l.name);
          showSeries.push({
            ...serice,
            color: l.color,
          });
        }
      });
      this.$emit(
        'showLegendChange',
        showSeries.map(v => v.target)
      );
      const optionData = this.chartOptionInstance.getOptions(this.handleTransformSeries(showSeries), {});
      this.chart.setOption(deepMerge(optionData.options, this.defaultOptions), {
        notMerge: true,
        lazyUpdate: false,
        silent: false,
      });
    };
    if (actionType === 'shift-click') {
      item.show = !item.show;
      setOnlyOneMarkArea();
    } else if (actionType === 'click') {
      const hasOtherShow = this.legend.list
        .filter(item => !item.hidden)
        .some(set => set.name !== item.name && set.show);
      this.legend.list.forEach(legend => {
        legend.show = legend.name === item.name || !hasOtherShow;
      });
      setOnlyOneMarkArea();
    } else if (actionType === 'parent-change') {
      this.legend.list.forEach(legend => {
        if (legend.name !== item.name) return;
        legend.show = !!item.show;
      });
      setOnlyOneMarkArea();
    }
  }

  // 下载图表为png图片
  async handleStoreImage() {
    if (window.navigator.msSaveOrOpenBlob) {
      toBlob(this.$el as HTMLDivElement)
        .then(blob => window.navigator.msSaveOrOpenBlob(blob, `${this.title}.png`))
        .catch(() => {});
    } else {
      if (this.chartType === 'table') {
        await this.$nextTick();
        const cloneEl = this.$el.cloneNode(true) as HTMLDivElement;
        (cloneEl.querySelector('.chart-wrapper-echarts') as HTMLDivElement).style.maxHeight = 'none';
        (cloneEl.querySelector('.echart-instance') as HTMLDivElement).style.height = 'auto';
        (cloneEl.querySelector('.echart-legend') as HTMLDivElement).style.maxHeight = 'none';
        (cloneEl.querySelector('.bk-table-fit') as HTMLDivElement).style.maxHeight = 'none';
        (cloneEl.querySelector('.bk-table-body-wrapper') as HTMLDivElement).style.maxHeight = 'none';
        const divEl = document.createElement('div');
        divEl.setAttribute('style', 'position: fixed; top: -10000px');
        divEl.setAttribute('class', 'clone-chart-wrapper');
        divEl.appendChild(cloneEl);
        this.$el.appendChild(divEl);
        const width = cloneEl.clientWidth;
        const height = cloneEl.clientHeight;
        toPng(this.$el.querySelector('.clone-chart-wrapper')?.firstElementChild as HTMLDivElement, { width, height })
          .then(dataUrl => {
            const tagA = document.createElement('a');
            tagA.download = `${this.title}.png`;
            tagA.href = dataUrl;
            document.body.appendChild(tagA);
            tagA.click();
            tagA.remove();
            divEl.remove();
          })
          .catch(() => {
            divEl.remove();
          });
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
          .catch(e => console.info(e));
      }
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
          const newV = Object.assign({}, v, { tool: 0, legend: 0, annotation: 0 });
          const oldV = Object.assign({}, ov, { tool: 0, legend: 0, annotation: 0 });
          JSON.stringify(newV) !== JSON.stringify(oldV) && this.handleSeriesData();
        } else {
          this.handleSetChartData(deepMerge({}, { series: this.series }));
        }
      },
      { deep: !this.watchOptionsDeep }
    );
  }

  // 初始化chart事件
  initChartEvent() {
    if (this.hasTraceInfo) {
      this.chart.on('click', 'series.scatter', e => {
        const chartOptions = this.chart.getOption();
        this.scatterTips.data.target.color = chartOptions.color[0];
        const labelList = ['bk_trace_id', 'bk_span_id', 'bk_trace_value'];
        const displayNames = {
          bk_trace_id: 'traceID',
          bk_span_id: 'spanID',
          bk_trace_value: 'traceValue',
        };
        const { scatterData } = e.data;
        this.scatterTips.data.list = labelList.map(item => ({
          type: item === labelList[2] ? 'string' : 'link',
          label: displayNames[item] || item,
          content: scatterData[item],
        }));
        this.scatterTips.data.target.label = `${chartOptions.series[0].name}: ${
          scatterData._value || scatterData.metric_value || '--'
        }`;
        this.scatterTips.data.time = dayjs.tz(e.data.value[0]).format('YYYY-MM-DD HH:mm:ss');
        this.scatterTips.top = -9999;
        this.scatterTips.show = true;
        this.$nextTick(() => {
          const chartWidth = this.$refs.charWrapRef.clientWidth + 10;
          const scatterTipW = this.$refs.scatterTipsRef.clientWidth;
          const { offsetY } = e.event;
          const offsetX = e.event.offsetX + 10;
          const left = chartWidth - offsetX < scatterTipW ? offsetX - scatterTipW - 10 : offsetX + 10;
          const top = offsetY;
          this.scatterTips.left = left;
          this.scatterTips.top = top;
          this.scatterTips.show = true;
          const { series } = chartOptions;
          series.forEach(item => {
            if (item.type === 'scatter' && item.name === 'bk_trace_value') {
              item.data.forEach(d => {
                if (JSON.stringify(d.value) === JSON.stringify(e.data.value)) {
                  d.itemStyle.color = '#699DF4';
                }
              });
            }
          });
          this.chart.setOption({
            series,
          });
        });
      });
      this.chart.on('mouseover', 'series.scatter', () => {
        this.$el.querySelector('canvas').style.cursor = 'pointer';
      });
      this.chart.on('mouseout', 'series.scatter', () => {
        this.$el.querySelector('canvas').style.removeProperty('cursor');
      });
    }
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
    this.intersectionObserver?.unobserve?.(this.$el);
    this.intersectionObserver?.disconnect?.();
  }

  handleScatterTipOutside() {
    this.scatterTips.show = false;
    const { series } = this.chart.getOption();
    series.forEach(item => {
      if (item.type === 'scatter' && item.name === 'bk_trace_value') {
        item.data.forEach(d => {
          d.itemStyle.color = '#E1ECFF';
        });
      }
    });
    this.chart.setOption({
      series,
    });
  }

  handleCopy(value: string) {
    copyText(value);
    this.$bkMessage({
      theme: 'success',
      message: this.$t('复制成功'),
    });
  }

  /* trace id 跳转 */
  handleTraceLink(item) {
    if (item.type === 'link' && item.label === 'traceID') {
      const traceId = item.content;
      traceListById({
        bk_biz_id: this.curBizId,
        trace_ids: [traceId],
        ...this.traceInfoTimeRange,
      }).then(data => {
        const url = data?.[0]?.url || '';
        if (url) {
          window.open(`${location.origin}${url}`);
        }
      });
    }
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

    :deep(.chart-title-wrap) {
      cursor: pointer;

      .chart-title {
        padding: 0;
      }
    }
  }

  .chart-wrapper-echarts {
    position: relative;
    display: flex;

    .echart-instance-wrap {
      position: relative;
      display: flex;
      flex: 1;
      flex-direction: column;
      min-width: 100px;
      overflow: hidden;

      .chart-restore {
        position: absolute;
        top: 5px;
        right: 8px;
        z-index: 2;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 20px;
        font-size: 12px;
        border: 1px solid #c4c6cc;
        border-radius: 2px;

        &:hover {
          color: #63656e;
          cursor: pointer;
          border-color: #979ba5;
        }
      }
    }

    .echart-instance {
      display: flex;
      flex: 1;
      width: 100%;
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

  .scatter-tips {
    position: absolute;
    padding: 10px 6px 6px 6px;
    background: #000;
    border-radius: 2px;
    opacity: 0.8;

    .time {
      margin-bottom: 4px;
      font-size: 12px;
      font-weight: Bold;
      color: #fff;
    }

    .info-item {
      font-size: 12px;
      line-height: 20px;
      color: #fff;

      .content {
        .link,
        .copy {
          color: #a3c5fd;
        }

        .link {
          &.pointer {
            cursor: pointer;
          }
        }

        .copy {
          cursor: pointer;
        }
      }
    }

    .bottom {
      margin-top: 8px;

      .point {
        display: inline-block;
        width: 8px;
        height: 8px;
        margin-right: 10px;
        border-radius: 50%;
      }

      .label {
        color: #fff;
      }
    }
  }

  .is-error {
    position: absolute;
    top: -10px;
    left: -10px;
    z-index: 999;
    display: block;
    color: #fff;
    cursor: pointer;
    border-color: #e0226e transparent transparent #e0226e;
    border-style: solid;
    border-width: 12px;
    border-radius: 2px;

    &::after {
      position: absolute;
      top: -12px;
      left: -6px;
      width: 4px;
      height: 8px;
      content: '!';
    }
  }

  .chart-resize-line {
    position: relative;
    height: 20px;
    margin-top: 5px;
    cursor: row-resize;

    &::before {
      position: absolute;
      top: 50%;
      width: 100%;
      content: '';
      border-top: 1px solid transparent;
      transform: translateY(-50%);
      transition: border-color 0.2s ease-in-out 0s;
    }

    &::after {
      position: absolute;
      top: 50%;
      left: 50%;
      width: 24px;
      height: 3px;
      content: '';
      background: #c4c6cc;
      border-radius: 2px;
      transform: translate(-50%, -50%);
    }

    &:hover {
      &::before {
        border-color: #5794f2;
      }

      &::after {
        background: #3a84ff;
      }
    }
  }

  .chart-table-box {
    border-top: 1px solid #eaebf0;

    .chart-table-title {
      display: flex;
      align-items: center;
      width: 100%;
      height: 54px;
      // justify-content: space-between;
      font-weight: bold;

      .title-count {
        margin-left: 16px;
        font-weight: normal;
        color: #979ba5;
      }

      .export-csv-btn {
        margin-left: auto;
      }
    }

    .chart-table {
      ::v-deep td,
      ::v-deep th.is-leaf {
        height: 32px;
      }
    }

    ::v-deep .ellipsis {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}
</style>
