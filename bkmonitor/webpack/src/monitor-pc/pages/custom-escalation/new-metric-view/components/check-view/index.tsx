/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Prop, Provide, ProvideReactive, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone, random } from 'monitor-common/utils';
import MonitorDropdown from 'monitor-pc/components/monitor-dropdown';
import TimeRange, { type TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { getTimeDisplay } from 'monitor-pc/components/time-range/utils';
import { updateTimezone } from 'monitor-pc/i18n/dayjs';

import NewMetricChart from '../../metric-chart-view/metric-chart';
import { refreshList } from '../../metric-chart-view/utils';
import HeaderBox from '../header-box/index';
import CheckViewTable from './check-view-table';

import type { IDimensionItem, IRefreshItem } from '../../type';
import type { IMetricAnalysisConfig } from 'monitor-pc/pages/custom-escalation/new-metric-view/type';
import type { ILegendItem, IPanelModel } from 'monitor-ui/chart-plugins/typings';

import './index.scss';
interface IDrillAnalysisViewEvents {
  onClose?: () => void;
}
/** 维度下钻 */
interface IDrillAnalysisViewProps {
  currentMethod?: string;
  dimensionsList?: IDimensionItem[];
  panel?: IPanelModel;
  timeRangeData?: TimeRangeType;
}
interface IViewConfig {
  config: IPanelModel;
  filterOption?: IMetricAnalysisConfig;
}
@Component
export default class CheckViewDetail extends tsc<IDrillAnalysisViewProps, IDrillAnalysisViewEvents> {
  // 图表panel实例
  @Prop({ default: () => ({}) }) panel: IViewConfig;
  @Prop({ default: () => ({}) }) timeRangeData: TimeRangeType;
  /** 当前汇聚方法 */
  @Prop({ default: '' }) currentMethod: string;
  @Ref('viewRef') viewRef: HTMLElement;
  @Ref('viewMain') viewMainRef: HTMLDivElement;
  @Ref('metricChart') metricChartRef: HTMLDivElement;
  dimensionParams: Record<string, any> = {};
  /* 主动刷新图表 */
  chartKey = random(8);
  timezone = window.timezone;
  /* 刷新时间列表 */
  refreshList: IRefreshItem[] = [];
  refreshInterval = -1;
  /** 自动刷新定时器 */
  timer = null;
  panelData = {
    targets: [],
  };
  divHeight = 0;
  resizeObserver = null;
  showStatisticalValue = true;
  /* 拖拽数据 */
  drag = { height: 300, minHeight: 240, maxHeight: 400 };
  /* 原始数据 */
  tableData = [];
  legendData: ILegendItem[] = [];
  loading = false;
  isHasCompare = false;
  isHasDimensions = false;
  compare: string[] = [];
  hoverPoint: { value?: number } = {};
  cacheTimeRange = [];
  @ProvideReactive('timeRange') timeRange: TimeRangeType = ['now-1h', 'now'];
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  @ProvideReactive('showRestore') showRestore = false;

  @Provide('handleChartDataZoom')
  handleChartDataZoom(value) {
    if (JSON.stringify(this.timeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.timeRange));
      this.timeRange = value;
      this.showRestore = true;
    }
  }
  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    this.timeRange = JSON.parse(JSON.stringify(this.cacheTimeRange));
    this.showRestore = false;
  }
  get titleName() {
    return this.panel?.config?.title || '';
  }

  mounted() {
    this.loading = true;
    this.timeRange = this.timeRangeData;
    this.refreshList = refreshList;
    this.$nextTick(() => {
      /** 初始化数据 */
      const { config, filterOption } = this.panel;
      this.panelData = deepClone(config);
      this.dimensionParams = deepClone(filterOption);
      this.isHasDimensions = filterOption?.group_by?.length > 0;
      this.isHasCompare = filterOption?.compare?.offset?.length > 0;
      this.compare = filterOption?.compare?.offset || [];
      if (this.viewMainRef) {
        // 初始化 ResizeObserver
        this.resizeObserver = new ResizeObserver(entries => {
          for (const entry of entries) {
            this.divHeight = entry.contentRect.height;
          }
        });
        // 观察目标元素
        this.resizeObserver.observe(this.viewMainRef);
      }
    });
    document.body.appendChild(this.viewRef);
    this.$once('hook:beforeDestroy', () => {
      this.viewRef?.parentNode?.removeChild(this.viewRef);
    });
  }
  beforeUnmount() {
    // 销毁观察器
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  }

  beforeDestroy() {
    this.timer && clearInterval(this.timer);
  }
  /** 关闭按钮 */
  handleClose() {
    this.$emit('close');
  }

  /** 修改刷新间隔 */
  handleRefreshInterval(val: number) {
    this.refreshInterval = val;
    this.timer && clearInterval(this.timer);
    if (val > -1) {
      this.timer = setInterval(() => {
        this.handleImmediateRefresh();
      }, val);
    }
  }
  /** 手动刷新 */
  handleImmediateRefresh() {
    this.chartKey = random(8);
    this.loading = true;
  }
  /** 修改时间间隔 */
  handleTimeRangeChange(val: TimeRangeType) {
    this.showRestore = false;
    this.timeRange = [...val];
    this.loading = true;
  }
  /** 修改时区 */
  handleTimezoneChange(timezone: string) {
    updateTimezone(timezone);
    this.loading = true;
  }
  /** 支持上下拖拽 */
  handleResizing(height: number) {
    this.drag.height = height;
  }
  /** 设置panel的值 */
  setPanelConfigAndRefresh(keys: string, value) {
    const keysArray = keys.split('.');
    let current = this.panelData.targets[0].query_configs[0];

    for (let i = 0; i < keysArray.length; i++) {
      const key = keysArray[i];
      if (i === keysArray.length - 1) {
        current[key] = value;
      } else {
        if (!current[key]) {
          current[key] = {};
        }
        current = current[key];
      }
    }
    this.panelData = deepClone(this.panelData);
  }
  /** 修改过滤值的时候重置panel的数据 */
  handleDimensionParamsChange(payload: any) {
    const { group_by, common_conditions, limit, where, compare } = payload;
    const commonConditions = {};
    common_conditions.map(item => {
      commonConditions[item.key] = item.value;
    });

    this.setPanelConfigAndRefresh(
      'group_by',
      group_by.map(item => item.field)
    );
    this.isHasDimensions = group_by.length > 0;
    this.setPanelConfigAndRefresh('where', where);
    this.setPanelConfigAndRefresh('filter_dict.common_filter', commonConditions);
    this.setPanelConfigAndRefresh('functions', [
      {
        id: limit.function,
        params: [
          {
            id: 'n',
            value: limit.limit,
          },
        ],
      },
    ]);
    this.setPanelConfigAndRefresh('interval', payload.interval || 'auto');
    this.panelData.targets[0].function = !compare.type ? {} : { time_compare: compare.offset };
    this.isHasCompare = compare.offset.length > 0;
    this.compare = compare.offset || [];
    this.dimensionParams = Object.freeze(payload);
    this.loading = true;
  }

  /* 获取原始数据 */
  handleGetSeriesData(res) {
    this.tableData = res;
  }
  handleLegendData(list: ILegendItem[], loading: boolean) {
    this.legendData = list;
    this.loading = loading;
  }
  /** 点击表格的图例，与图表联动 */
  handleRowClick(item: ILegendItem) {
    this.metricChartRef?.handleSelectLegend({ actionType: 'click', item });
  }

  handleContextMenuClick() {
    this.$emit('contextMenuClick', this.panelData);
  }

  handleZrMouseover(data: { value: number }) {
    this.hoverPoint = data;
  }

  render() {
    return (
      <div
        ref='viewRef'
        class='check-view-detail'
      >
        <div class='check-view-detail-head'>
          <i
            class='icon-monitor icon-back-left close-btn'
            onClick={this.handleClose}
          />
          {this.$t('查看大图')}
          <span class='detail-head-title'>{this.titleName}</span>
          <div class='detail-head-right'>
            {/* 时间工具栏 */}
            {window.__BK_WEWEB_DATA__?.lockTimeRange ? (
              <span class='dashboard-tools-timerange'>{getTimeDisplay(this.timeRange)}</span>
            ) : (
              <TimeRange
                class='filter-tools-timerange'
                timezone={this.timezone}
                value={this.timeRange}
                onChange={this.handleTimeRangeChange}
                onTimezoneChange={this.handleTimezoneChange}
              />
            )}
            <span class='right-line' />
            <MonitorDropdown
              class='filter-tools-interval'
              icon='icon-zidongshuaxin'
              isRefreshInterval={true}
              list={this.refreshList}
              text-active={this.refreshInterval !== -1}
              value={this.refreshInterval}
              on-change={this.handleRefreshInterval}
              on-on-icon-click={this.handleImmediateRefresh}
            />
          </div>
        </div>
        <div class='check-view-detail-body'>
          <HeaderBox
            dimenstionParams={this.dimensionParams}
            exclude={['metric']}
            isShowExpand={false}
            offsetSingle={true}
            splitable={false}
            onChange={this.handleDimensionParamsChange}
          >
            <template slot='actionExtend'>
              <bk-checkbox v-model={this.showStatisticalValue}>{this.$t('展示统计值')}</bk-checkbox>
            </template>
          </HeaderBox>
          <div
            ref='viewMain'
            class='check-view-main'
          >
            <bk-resize-layout
              extCls='check-view-main-layout'
              slot='aside'
              border={false}
              initial-divide={'70%'}
              max={400}
              min={240}
              placement='top'
              onResizing={this.handleResizing}
            >
              <div
                class='check-view-main-chart'
                slot='aside'
              >
                <span class='chart-context-menu-info'>
                  <i class='icon-monitor icon-mc-mouse mouse-icon' />
                  {this.$t('右键更多操作')}
                </span>
                <NewMetricChart
                  key={this.chartKey}
                  ref='metricChart'
                  style={{ height: `${this.drag.height - 30}px` }}
                  chartHeight={this.drag.height}
                  currentMethod={this.currentMethod}
                  isNeedMenu={true}
                  isNeedUpdateAxisPointer={true}
                  isShowLegend={false}
                  isToolIconShow={false}
                  panel={this.panelData}
                  onContextmenuClick={this.handleContextMenuClick}
                  onLegendData={this.handleLegendData}
                  onSeriesData={this.handleGetSeriesData}
                  onZrMouseover={this.handleZrMouseover}
                />
              </div>
              <div
                style={{ height: `${this.divHeight - this.drag.height}px` }}
                class='check-view-main-table'
                slot='main'
              >
                <CheckViewTable
                  compare={this.compare}
                  data={this.tableData}
                  hoverPoint={this.hoverPoint}
                  isHasCompare={this.isHasCompare}
                  isHasDimensions={this.isHasDimensions}
                  isShowStatistical={this.showStatisticalValue}
                  legendData={this.legendData}
                  loading={this.loading}
                  title={this.panelData?.title}
                  onHeadClick={this.handleRowClick}
                  onToggle={status => {
                    this.showStatisticalValue = status;
                  }}
                />
              </div>
            </bk-resize-layout>
          </div>
        </div>
      </div>
    );
  }
}
