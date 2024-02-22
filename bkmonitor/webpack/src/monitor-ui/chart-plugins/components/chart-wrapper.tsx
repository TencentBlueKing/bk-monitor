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

import { TimeRangeType } from '../../../monitor-pc/components/time-range/time-range';
import { PanelToolsType } from '../../../monitor-pc/pages/monitor-k8s/typings';
import { IQueryOption } from '../../../monitor-pc/pages/performance/performance-type';
import { IDetectionConfig } from '../../../monitor-pc/pages/strategy-config/strategy-config-set-new/typings';
// import ViewDetail from '../../../monitor-pc/pages/view-detail/view-detail.vue';
import ViewDetail from '../../../monitor-pc/pages/view-detail/view-detail-new';
import watermarkMaker from '../../monitor-echarts/utils/watermarkMaker';
import loadingIcon from '../icons/spinner.svg';
import AiopsChart from '../plugins/aiops-chart/aiops-chart';
import AiopsDimensionLint from '../plugins/aiops-dimension-lint/aiops-dimension-lint';
import ApdexChart from '../plugins/apdex-chart/apdex-chart';
import BarEchart from '../plugins/bar-echart/bar-echart';
import ChartRow from '../plugins/chart-row/chart-row';
import ColumnBarEchart from '../plugins/column-bar-echart/column-bar-echart';
import EventLogChart from '../plugins/event-log-chart/event-log-chart';
import ExceptionGuide from '../plugins/exception-guide/exception-guide';
import IconChart from '../plugins/icon-chart/icon-chart';
import LineBarEchart from '../plugins/line-bar-echart/line-bar-echart';
import ListChart from '../plugins/list-chart/list-chart';
import MessageChart from '../plugins/message-chart/message-chart';
import NumberChart from '../plugins/number-chart/number-chart';
import PercentageBarChart from '../plugins/percentage-bar/percentage-bar';
import PerformanceChart from '../plugins/performance-chart/performance-chart';
import PieEcharts from '../plugins/pie-echart/pie-echart';
import PortStatusChart from '../plugins/port-status-chart/port-status-chart';
import ProfilinGraph from '../plugins/profiling-graph/profiling-graph';
import RatioRingChart from '../plugins/ratio-ring-chart/ratio-ring-chart';
import RelatedLogChart from '../plugins/related-log-chart/related-log-chart';
import RelationGraph from '../plugins/relation-graph/relation-graph';
import ResourceChart from '../plugins/resource-chart/resource-chart';
import StatusListChart from '../plugins/status-list-chart/status-list-chart';
import ChinaMap from '../plugins/status-map/status-map';
import TableBarChart from '../plugins/table-bar-chart/table-bar-chart';
import TableChart from '../plugins/table-chart/table-chart';
import TagChart from '../plugins/tag-chart/tag-chart';
import TextUnit from '../plugins/text-unit/text-unit';
import LineEcharts from '../plugins/time-series/time-series';
import TimeSeriesForecast from '../plugins/time-series-forecast/time-series-forecast';
import TimeSeriesOutlier from '../plugins/time-series-outlier/time-series-outlier';
import { PanelModel } from '../typings';

import './chart-wrapper.scss';

interface IChartWrapperProps {
  panel: PanelModel;
  detectionConfig?: IDetectionConfig;
  needHoverStryle?: boolean;
  needCheck?: boolean;
}
interface IChartWrapperEvent {
  onChartCheck: boolean;
  onCollapse: boolean;
  onCollectChart?: () => void;
  onDimensionsOfSeries?: string[];
}
interface IChartWrapperEvent {
  onChartCheck: boolean;
  onCollapse: boolean;
  onCollectChart?: () => void;
  onChangeHeight?: (height: number) => void;
  onDblClick?: void;
}
@Component
export default class ChartWrapper extends tsc<IChartWrapperProps, IChartWrapperEvent> {
  @Prop({ required: true, type: Object }) readonly panel: PanelModel;
  /** 检测算法 */
  @Prop({ type: Object }) detectionConfig: IDetectionConfig;
  /* 是否可选中图表 */
  @Prop({ type: Boolean, default: true }) needCheck: boolean;

  // 图表的数据时间间隔
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  // 图表刷新间隔
  @InjectReactive('refleshInterval') readonly refleshInterval!: number;
  // 时间对比的偏移量
  @InjectReactive('timeOffset') readonly timeOffset: string[];
  // 对比类型
  @InjectReactive('compareType') compareType: PanelToolsType.CompareId;
  @InjectReactive('readonly') readonly: boolean;

  /** 鼠标在图表内 */
  showHeaderMoreTool = false;
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
        value: this.compareType === 'time' ? this.timeOffset : ''
      },
      tools: {
        timeRange: this.timeRange,
        refleshInterval: this.refleshInterval,
        searchValue: []
      }
    };
  }

  /** hover样式 */
  get needHoverStryle() {
    const { time_series_forecast, time_series_list } = this.panel?.options || {};
    return (time_series_list?.need_hover_style ?? true) && (time_series_forecast?.need_hover_style ?? true);
  }

  mounted() {
    if (window.graph_watermark) {
      this.waterMaskImg = watermarkMaker(window.user_name || window.username);
    }
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
      compareValue: JSON.parse(JSON.stringify({ ...this.compareValue, ...compareValue }))
    };
    this.showViewDetail = true;
  }
  /**
   * @description: 保存到仪表盘
   * @param {*}
   */
  @Emit('collectChart')
  handleCollectChart() {}
  /**
   * @description: 关闭查看大图弹窗
   */
  handleCloseViewDetail() {
    this.showViewDetail = false;
    this.viewQueryConfig = {};
  }
  @Emit('chartCheck')
  handleChartCheck() {
    return !this.panel.checked;
  }
  @Emit('collapse')
  handleCollapsed() {
    return !this.panel.collapsed;
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
  handlePanel2Chart() {
    switch (this.panel.type) {
      case 'line-bar':
        return (
          <LineBarEchart
            onLoading={this.handleChangeLoading}
            panel={this.panel}
          />
        );
      case 'status-map':
        return (
          <ChinaMap
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
          />
        );
      case 'pie-echart':
        return (
          <PieEcharts
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
          />
        );
      case 'ratio-ring':
        return (
          <RatioRingChart
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
          />
        );
      case 'apdex-chart':
        return (
          <ApdexChart
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
          />
        );
      case 'percentage-bar':
        return (
          <PercentageBarChart
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
          />
        );
      case 'bar-echart':
        return (
          <BarEchart
            onLoading={this.handleChangeLoading}
            panel={this.panel}
          />
        );
      case 'number-chart':
        return (
          <NumberChart
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
          />
        );
      case 'tag-chart':
        return <TagChart panel={this.panel} />;
      case 'table-chart':
        return (
          <TableChart
            panel={this.panel}
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            onChangeHeight={this.handleChangeHeight}
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
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
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
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
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
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            customMenuList={['screenshot', 'explore', 'set', 'area']}
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          />
        );
      case 'time-series-outlier':
        return (
          <TimeSeriesOutlier
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            customMenuList={['screenshot', 'explore', 'set', 'area']}
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          />
        );
      case 'aiops-dimension-lint':
        return (
          <AiopsDimensionLint
            panel={this.panel}
            {...{
              props: this.$attrs
            }}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onFullScreen={this.handleFullScreen}
            onCollectChart={this.handleCollectChart}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          ></AiopsDimensionLint>
        );
      case 'graphs':
        return (
          <AiopsChart
            panels={this.panel.panels}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          ></AiopsChart>
        );
      case 'event-log':
        return (
          <EventLogChart
            panel={this.panel}
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            onChangeHeight={this.handleChangeHeight}
          ></EventLogChart>
        );
      case 'relation-graph':
        return (
          <RelationGraph
            panel={this.panel}
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          />
        );
      case 'api_message':
        return (
          <MessageChart
            panel={this.panel}
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          />
        );
      case 'profiling':
        return (
          <ProfilinGraph
            panel={this.panel}
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          />
        );
      case 'related-log-chart':
        return (
          <RelatedLogChart
            panel={this.panel}
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          />
        );
      case 'exception-guide':
        return (
          <ExceptionGuide
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          />
        );
      case 'resource':
        return (
          <ResourceChart
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onCollectChart={this.handleCollectChart}
            onFullScreen={this.handleFullScreen}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          />
        );
      case 'status-list':
        return (
          <StatusListChart
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          />
        );
      case 'column-bar':
        return (
          <ColumnBarEchart
            panel={this.panel}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
          />
        );
      case 'performance-chart':
        return (
          <PerformanceChart
            onLoading={this.handleChangeLoading}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onFullScreen={this.handleFullScreen}
            onCollectChart={this.handleCollectChart}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
          />
        );
      // 不需要报错显示
      case 'graph':
      default:
        return (
          <LineEcharts
            onLoading={this.handleChangeLoading}
            panel={this.panel}
            showHeaderMoreTool={this.showHeaderMoreTool}
            onFullScreen={this.handleFullScreen}
            onCollectChart={this.handleCollectChart}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
            onErrorMsg={this.handleErrorMsgChange}
            clearErrorMsg={this.handleClearErrorMsg}
            onDblClick={this.handleDblClick}
          />
        );
    }
  }
  render() {
    return (
      <div
        class={{
          'chart-wrapper': true,
          'grafana-check': this.panel.canSetGrafana,
          'is-checked': this.panel.checked,
          'is-collapsed': this.panel.collapsed,
          'hover-style': this.needCheck && this.needHoverStryle,
          'row-chart': this.panel.type === 'row'
        }}
        style={{ 'border-color': this.panel.type === 'tag-chart' ? '#eaebf0' : 'transparent' }}
        onMouseenter={() => (this.showHeaderMoreTool = true)}
        onMouseleave={() => (this.showHeaderMoreTool = false)}
      >
        {this.handlePanel2Chart()}
        {this.loading ? (
          <img
            class='loading-icon'
            src={loadingIcon}
            alt=''
          ></img>
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
        {!!this.waterMaskImg && (
          <div
            class='wm'
            style={{ backgroundImage: `url('${this.waterMaskImg}')` }}
          ></div>
        )}
        {!!this.errorMsg && (
          <span
            class='is-error'
            v-bk-tooltips={{
              content: this.errorMsg,
              extCls: 'chart-wrapper-error-tooltip',
              placement: 'top-start',
              allowHTML: false
            }}
          ></span>
        )}
      </div>
    );
  }
}
