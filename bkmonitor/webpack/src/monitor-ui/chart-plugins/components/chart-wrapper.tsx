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
import { Component, Emit, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

// import ViewDetail from 'monitor-pc/pages/view-detail/view-detail.vue';
import ViewDetail from 'monitor-pc/pages/view-detail/view-detail-new';

import loadingIcon from '../icons/spinner.svg';
import AiopsChart from '../plugins/aiops-chart/aiops-chart';
import AiopsDimensionLint from '../plugins/aiops-dimension-lint/aiops-dimension-lint';
import AlarmEventChart from '../plugins/alarm-event-chart/alarm-event-chart';
import ApdexChart from '../plugins/apdex-chart/apdex-chart';
import ApmCustomGraph from '../plugins/apm-custom-graph/apm-custom-graph';
import ApmHeatmap from '../plugins/apm-heatmap/apm-heatmap';
import ApmRelationGraph from '../plugins/apm-relation-graph/apm-relation-graph';
import ApmServiceCallerCallee from '../plugins/apm-service-caller-callee/apm-service-caller-callee';
import ApmTimeSeries from '../plugins/apm-time-series/apm-time-series';
import BarEchart from '../plugins/bar-echart/bar-echart';
import ApmCallerBarChart from '../plugins/caller-bar-chart/caller-bar-chart';
import ApmCallerLineChart from '../plugins/caller-line-chart/caller-line-chart';
import ApmCallerPieChart from '../plugins/caller-pie-chart/caller-pie-chart';
import ChartRow from '../plugins/chart-row/chart-row';
import ColumnBarEchart from '../plugins/column-bar-echart/column-bar-echart';
import EventLogChart from '../plugins/event-log-chart/event-log-chart';
import ExceptionGuide from '../plugins/exception-guide/exception-guide';
import IconChart from '../plugins/icon-chart/icon-chart';
import K8sCustomGraph from '../plugins/k8s-custom-graph/k8s-custom-graph';
import LineBarEchart from '../plugins/line-bar-echart/line-bar-echart';
import ListChart from '../plugins/list-chart/list-chart';
import MessageChart from '../plugins/message-chart/message-chart';
import NumberChart from '../plugins/number-chart/number-chart';
import PercentageBarChart from '../plugins/percentage-bar/percentage-bar';
import PerformanceChart from '../plugins/performance-chart/performance-chart';
import PieEcharts from '../plugins/pie-echart/pie-echart';
import PortStatusChart from '../plugins/port-status-chart/port-status-chart';
import ProfilingGraph from '../plugins/profiling-graph/profiling-graph';
import RatioRingChart from '../plugins/ratio-ring-chart/ratio-ring-chart';
import RelatedLogChart from '../plugins/related-log-chart/related-log-chart';
// import RelationGraph from '../plugins/relation-graph/relation-graph';
import ResourceChart from '../plugins/resource-chart/resource-chart';
import StatusListChart from '../plugins/status-list-chart/status-list-chart';
import ChinaMap from '../plugins/status-map/status-map';
import TableBarChart from '../plugins/table-bar-chart/table-bar-chart';
import TableChart from '../plugins/table-chart/table-chart';
import TagChart from '../plugins/tag-chart/tag-chart';
import TextUnit from '../plugins/text-unit/text-unit';
import TimeSeriesForecast from '../plugins/time-series-forecast/time-series-forecast';
import TimeSeriesOutlier from '../plugins/time-series-outlier/time-series-outlier';
import LineEcharts from '../plugins/time-series/time-series';
import { initLogRetrieveWindowsFields } from '../utils/init-windows';

import type { ChartTitleMenuType, IDataItem, PanelModel, ZrClickEvent } from '../typings';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { PanelToolsType } from 'monitor-pc/pages/monitor-k8s/typings';
import type { IQueryOption } from 'monitor-pc/pages/performance/performance-type';
import type { IDetectionConfig } from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';

import './chart-wrapper.scss';

interface IChartWrapperEvent {
  onChartCheck: boolean;
  onCollapse: boolean;
  onDimensionsOfSeries?: string[];
  onChangeHeight?: (height: number) => void;
  onCollectChart?: () => void;
  onDblClick?: () => void;
  /** 图表鼠标右击事件的回调方法 */
  onMenuClick?: (data: IDataItem) => void;
  onZrClick?: (event: ZrClickEvent) => void;
}
interface IChartWrapperProps {
  chartChecked?: boolean;
  collapse?: boolean;
  customMenuList?: ChartTitleMenuType[];
  detectionConfig?: IDetectionConfig;
  isSingleChart?: boolean;
  needCheck?: boolean;
  panel: PanelModel;
}

@Component({
  components: {
    RelationGraph: () => import(/* webpackChunkName: "RelationGraph" */ '../plugins/relation-graph/relation-graph'),
    MonitorRetrieve: () =>
      import(/* webpackChunkName: "MonitorRetrieve" */ '../plugins/monitor-retrieve/monitor-retrieve'),
    ApmEventExplore: () =>
      import(/* webpackChunkName: "ApmEventExplore" */ 'monitor-pc/pages/event-explore/apm-event-explore'),
  },
})
export default class ChartWrapper extends tsc<IChartWrapperProps, IChartWrapperEvent> {
  @Prop({ required: true, type: Object }) readonly panel: PanelModel;
  /** 检测算法 */
  @Prop({ type: Object }) detectionConfig: IDetectionConfig;
  /* 是否可选中图表 */
  @Prop({ type: Boolean, default: true }) needCheck: boolean;
  @Prop({ type: Boolean, default: undefined }) collapse: boolean;
  @Prop({ type: Boolean, default: undefined }) chartChecked: boolean;
  @Prop({ type: Array, default: null }) customMenuList: ChartTitleMenuType[];
  // 是否为单图模式
  @Prop({ default: false, type: Boolean }) isSingleChart: boolean;

  // 图表的数据时间间隔
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  // 图表刷新间隔
  @InjectReactive('refreshInterval') readonly refreshInterval!: number;
  // 时间对比的偏移量
  @InjectReactive('timeOffset') readonly timeOffset: string[];
  // 对比类型
  @InjectReactive('compareType') compareType: PanelToolsType.CompareId;
  @InjectReactive('readonly') readonly: boolean;

  /** 鼠标在图表内 */
  showHeaderMoreTool = true;
  /** 图表加载状态 */
  loading = false;
  /** 是否显示大图 */
  showViewDetail = false;
  /** 查看大图参数配置 */
  viewQueryConfig = {};

  errorMsg = '';

  /** 水印图 */
  waterMaskImg = '';

  /** 对比工具栏数据 */
  get compareValue(): IQueryOption {
    return {
      compare: {
        type: this.compareType !== 'time' ? 'none' : this.compareType,
        value: this.compareType === 'time' ? this.timeOffset : '',
      },
      tools: {
        timeRange: this.timeRange,
        refreshInterval: this.refreshInterval,
        searchValue: [],
      },
    };
  }

  /** hover样式 */
  get needHoverStyle() {
    const { time_series_forecast, time_series_list } = this.panel?.options || {};
    return (time_series_list?.need_hover_style ?? true) && (time_series_forecast?.need_hover_style ?? true);
  }

  get isChecked() {
    return this.chartChecked === undefined ? this.panel.checked : this.chartChecked;
  }

  get isCollapsed() {
    return this.collapse === undefined ? this.panel.collapsed : this.collapse;
  }
  get needWaterMask() {
    return !['log-retrieve', 'event-explore'].includes(this.panel?.type);
  }
  beforeCreate() {
    initLogRetrieveWindowsFields();
  }
  /**
   * @description: 供子组件更新loading的状态
   * @param {boolean} loading
   */
  handleChangeLoading(loading: boolean) {
    this.loading = loading;
  }

  /**
   * @description: 错误处理
   * @param {string} msg
   */
  handleErrorMsgChange(msg: string) {
    this.errorMsg = msg;
  }

  /**
   * @description: 清除错误
   */
  handleClearErrorMsg() {
    this.errorMsg = '';
  }
  /**
   * @description: 查看大图
   * @param {boolean} loading
   */
  handleFullScreen(config: PanelModel, compareValue?: typeof this.compareValue) {
    this.viewQueryConfig = {
      config: JSON.parse(JSON.stringify(config)),
      compareValue: JSON.parse(JSON.stringify({ ...this.compareValue, ...compareValue })),
    };
    this.showViewDetail = true;
  }
  /**
   * @description: 保存到仪表盘
   * @param {*}
   */
  @Emit('collectChart')
  handleCollectChart(v) {
    return v;
  }
  /**
   * @description: 关闭查看大图弹窗
   */
  handleCloseViewDetail() {
    this.showViewDetail = false;
    this.viewQueryConfig = {};
  }
  @Emit('chartCheck')
  handleChartCheck() {
    return !this.isChecked;
  }
  @Emit('collapse')
  handleCollapsed() {
    return !this.isCollapsed;
  }
  @Emit('changeHeight')
  handleChangeHeight(height: number) {
    return height;
  }
  @Emit('dimensionsOfSeries')
  handleDimensionsOfSeries(dimensions: string[]) {
    return dimensions;
  }
  handleDblClick() {
    this.$emit('dblClick');
  }
  @Emit('zrClick')
  handleZrClick(event: ZrClickEvent) {
    return event;
  }
  @Emit('menuClick')
  handleMenuClick(data) {
    return data;
  }
  handlePanel2Chart() {
    switch (this.panel.type) {
      case 'line-bar':
        return (
          <LineBarEchart
            panel={this.panel}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'status-map':
        return (
          <ChinaMap
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'pie-echart':
        return (
          <PieEcharts
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'ratio-ring':
        return (
          <RatioRingChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'apdex-chart':
        return (
          <ApdexChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'percentage-bar':
        return (
          <PercentageBarChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'bar-echart':
        return (
          <BarEchart
            panel={this.panel}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'number-chart':
        return (
          <NumberChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'tag-chart':
        return <TagChart panel={this.panel} />;
      case 'table-chart':
        return (
          <TableChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onChangeHeight={this.handleChangeHeight}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'table-bar-chart':
        return (
          <TableBarChart
            panel={this.panel}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'icon-chart':
        return (
          <IconChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'row':
        return (
          <ChartRow
            panel={this.panel}
            onCollapse={this.handleCollapsed}
          />
        );
      case 'list-chart':
        return (
          <ListChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'text':
      case 'text-unit':
        return (
          <TextUnit
            panel={this.panel}
            onLoading={this.handleChangeLoading}
          />
        );
      // 不需要报错显示
      case 'port-status':
      case 'status':
        return (
          <PortStatusChart
            panel={this.panel}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'time-series-forecast':
        return (
          <TimeSeriesForecast
            clearErrorMsg={this.handleClearErrorMsg}
            customMenuList={['screenshot', 'explore', 'set', 'area']}
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'time-series-outlier':
        return (
          <TimeSeriesOutlier
            clearErrorMsg={this.handleClearErrorMsg}
            customMenuList={['screenshot', 'explore', 'set', 'area']}
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'aiops-dimension-lint':
        return (
          <AiopsDimensionLint
            panel={this.panel}
            {...{
              props: this.$attrs,
            }}
            clearErrorMsg={this.handleClearErrorMsg}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onCollectChart={this.handleCollectChart}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
            onErrorMsg={this.handleErrorMsgChange}
            onFullScreen={this.handleFullScreen}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'graphs':
        return (
          <AiopsChart
            clearErrorMsg={this.handleClearErrorMsg}
            panels={this.panel.panels}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
            onErrorMsg={this.handleErrorMsgChange}
          />
        );
      case 'event-log':
        return (
          <EventLogChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onChangeHeight={this.handleChangeHeight}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      // case 'relation-graph':
      //   return (
      //     <relation-graph
      //       clearErrorMsg={this.handleClearErrorMsg}
      //       panel={this.panel}
      //       onErrorMsg={this.handleErrorMsgChange}
      //       onLoading={this.handleChangeLoading}
      //     />
      //   );
      case 'api_message':
        return (
          <MessageChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'profiling':
        return (
          <ProfilingGraph
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'related-log-chart':
        return (
          <RelatedLogChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'log-retrieve':
        return <monitor-retrieve />;
      case 'exception-guide':
        return (
          <ExceptionGuide
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
          />
        );
      case 'resource':
        return (
          <ResourceChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onCollectChart={this.handleCollectChart}
            onErrorMsg={this.handleErrorMsgChange}
            onFullScreen={this.handleFullScreen}
          />
        );
      case 'status-list':
        return (
          <StatusListChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
          />
        );
      case 'column-bar':
        return (
          <ColumnBarEchart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
          />
        );
      case 'performance-chart':
        return (
          <PerformanceChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onCollectChart={this.handleCollectChart}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
            onErrorMsg={this.handleErrorMsgChange}
            onFullScreen={this.handleFullScreen}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'apm-timeseries-chart':
        return (
          <ApmTimeSeries
            clearErrorMsg={this.handleClearErrorMsg}
            customMenuList={this.customMenuList}
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onCollectChart={this.handleCollectChart}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
            onErrorMsg={this.handleErrorMsgChange}
            onFullScreen={this.handleFullScreen}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'relation-graph':
      case 'apm-relation-graph':
        return <ApmRelationGraph panel={this.panel} />;
      case 'apm-service-caller-callee':
        return <ApmServiceCallerCallee panel={this.panel} />;
      case 'alarm-event-chart':
        return <AlarmEventChart panel={this.panel} />;
      case 'apm_heatmap':
        return (
          <ApmHeatmap
            panel={this.panel}
            onLoading={this.handleChangeLoading}
            onZrClick={this.handleZrClick}
          />
        );
      case 'caller-line-chart':
        return (
          <ApmCallerLineChart
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onCollectChart={this.handleCollectChart}
            onDblClick={this.handleDblClick}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
            onErrorMsg={this.handleErrorMsgChange}
            onFullScreen={this.handleFullScreen}
            onLoading={this.handleChangeLoading}
            onZrClick={this.handleZrClick}
          />
        );
      case 'caller-pie-chart':
        return (
          <ApmCallerPieChart
            panel={this.panel}
            onMenuClick={this.handleMenuClick}
          />
        );
      case 'caller-bar-chart':
        return (
          <ApmCallerBarChart
            panel={this.panel}
            onMenuClick={this.handleMenuClick}
          />
        );

      case 'apm_custom_graph':
        return (
          <ApmCustomGraph
            clearErrorMsg={this.handleClearErrorMsg}
            isSingleChart={this.isSingleChart}
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onCollectChart={this.handleCollectChart}
            onDblClick={this.handleDblClick}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
            onErrorMsg={this.handleErrorMsgChange}
            onFullScreen={this.handleFullScreen}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'k8s_custom_graph':
        return (
          <K8sCustomGraph
            clearErrorMsg={this.handleClearErrorMsg}
            isSingleChart={this.isSingleChart}
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onCollectChart={this.handleCollectChart}
            onDblClick={this.handleDblClick}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
            onErrorMsg={this.handleErrorMsgChange}
            onFullScreen={this.handleFullScreen}
            onLoading={this.handleChangeLoading}
          />
        );
      case 'event-explore':
        return <apm-event-explore />;
      // 不需要报错显示
      // case 'graph':
      default:
        return (
          <LineEcharts
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onCollectChart={this.handleCollectChart}
            onDblClick={this.handleDblClick}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
            onErrorMsg={this.handleErrorMsgChange}
            onFullScreen={this.handleFullScreen}
            onLoading={this.handleChangeLoading}
            onZrClick={this.handleZrClick}
          />
        );
    }
  }
  render() {
    return (
      <div
        style={{ 'border-color': this.panel.type === 'tag-chart' ? '#eaebf0' : 'transparent' }}
        class={{
          'chart-wrapper': true,
          'grafana-check': this.panel.canSetGrafana,
          'is-checked': this.isChecked,
          'is-collapsed': this.isCollapsed,
          'hover-style': this.needCheck && this.needHoverStyle,
          'row-chart': this.panel.type === 'row',
        }}
        // onMouseenter={() => (this.showHeaderMoreTool = true)}
        // onMouseleave={() => (this.showHeaderMoreTool = false)}
      >
        {window?.graph_watermark && this.needWaterMask && (
          <div
            class='wm'
            v-watermark={{
              text: window.user_name || window.username,
            }}
          />
        )}
        {this.handlePanel2Chart()}
        {this.loading ? (
          <img
            class='loading-icon'
            alt=''
            src={loadingIcon}
          />
        ) : undefined}
        {!this.readonly && this.panel.canSetGrafana && !this.panel.options?.disable_wrap_check && (
          <span
            class='check-mark'
            onClick={this.handleChartCheck}
          />
        )}
        {/* 全屏查看大图 */}
        {this.showViewDetail && (
          <ViewDetail
            show={this.showViewDetail}
            viewConfig={this.viewQueryConfig}
            on-close-modal={this.handleCloseViewDetail}
          />
        )}
        {!!this.errorMsg && (
          <span
            class='is-error'
            v-bk-tooltips={{
              content: this.errorMsg,
              extCls: 'chart-wrapper-error-tooltip',
              placement: 'top-start',
              allowHTML: false,
            }}
          />
        )}
      </div>
    );
  }
}
