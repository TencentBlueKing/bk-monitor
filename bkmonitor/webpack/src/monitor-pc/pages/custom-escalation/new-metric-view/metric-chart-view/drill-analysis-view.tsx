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
import { Component, Ref, Prop, ProvideReactive, Provide } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from '@store/modules/custom-escalation-view';
import { graphDrillDown } from 'monitor-api/modules/scene_view';
import { random, deepClone } from 'monitor-common/utils';
import MonitorDropdown from 'monitor-pc/components/monitor-dropdown';
import TimeRange, { type TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import { getTimeDisplay } from 'monitor-pc/components/time-range/utils';
import { updateTimezone } from 'monitor-pc/i18n/dayjs';

import DrillAnalysisFilter from './drill-analysis-filter';
import DrillAnalysisTable from './drill-analysis-table';
import NewMetricChart from './metric-chart';
import { refreshList } from './utils';

import type { IDimensionItem, IRefreshItem, IResultItem } from '../type';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

import './drill-analysis-view.scss';

/** 维度下钻 */
interface IDrillAnalysisViewProps {
  dimensionsList?: IDimensionItem[];
  currentMethod?: string;
  panel?: IPanelModel;
  timeRangeData?: TimeRangeType;
}
interface IDrillAnalysisViewEvents {
  onClose?: () => void;
}
@Component
export default class DrillAnalysisView extends tsc<IDrillAnalysisViewProps, IDrillAnalysisViewEvents> {
  // 图表panel实例
  @Prop({ default: () => ({}) }) panel: IPanelModel;
  @Prop({ default: () => ({}) }) timeRangeData: TimeRangeType;
  /** 当前汇聚方法 */
  @Prop({ default: '' }) currentMethod: string;
  @Ref('rootRef') rootRef: HTMLElement;
  @Ref('drillMain') drillMainRef: HTMLDivElement;

  panelData = {
    targets: [],
  };
  /* 主动刷新图表 */
  chartKey = random(8);
  /** 表格数据 */
  tableList = [];
  refreshInterval = -1;
  /** 多维分析列表 */
  dimensionsList: IDimensionItem[];
  /* 刷新时间列表 */
  refreshList: IRefreshItem[] = [];
  timezone = window.timezone;
  /* 拖拽数据 */
  drag = { height: 400, minHeight: 300, maxHeight: 550 };
  divHeight = 0;
  resizeObserver = null;
  /** 选中的维度值 */
  dimensionsActiveKey = [];
  loading = false;
  tableLoading = false;
  filterConfig = {
    compare: { type: '', offset: [] },
    metrics: [],
    where: [],
    group_by: [],
    drill_group_by: [],
    limit: {
      function: 'top',
      limit: 10,
    },
    function: {
      time_compare: [],
    },
    commonConditions: [],
  };
  defaultCommonConditions = [];
  /** 自动刷新定时器 */
  timer = null;
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
  /** 默认的图表配置 */
  get defaultPanelConfig() {
    return this.panelData?.targets[0] || {};
  }
  /** 默认的图表query_configs */
  get defaultPanelQuery() {
    return this.defaultPanelConfig?.query_configs[0] || {};
  }
  /** 指标列表 */
  get currentSelectedMetricList() {
    return customEscalationViewStore.currentSelectedMetricList;
  }

  mounted() {
    this.timeRange = this.timeRangeData;
    window.addEventListener('keydown', this.handleKeydown);
    this.refreshList = refreshList;
    this.$nextTick(() => {
      /** 初始化数据 */
      this.panelData = deepClone(this.panel);
      this.handleGetCustomTsMetricGroups();
      this.getTableList();
      if (this.drillMainRef) {
        // 初始化 ResizeObserver
        this.resizeObserver = new ResizeObserver(entries => {
          for (const entry of entries) {
            this.divHeight = entry.contentRect.height;
          }
        });
        // 观察目标元素
        this.resizeObserver.observe(this.drillMainRef);
      }
    });
    document.body.appendChild(this.rootRef);
    this.$once('hook:beforeDestroy', () => {
      this.rootRef?.parentNode?.removeChild(this.rootRef);
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
    window.removeEventListener('keydown', this.handleKeydown);
  }

  handleKeydown(event) {
    if (event.key === 'Escape') {
      this.handleClose();
    }
  }

  /** 获取当前可选的维度值 */
  handleGetCustomTsMetricGroups() {
    let metrics = [];
    (this.panelData.targets || []).map(item => {
      const timeCompare = item.function;
      /** 初始化处理对比 */
      this.filterConfig.compare =
        timeCompare.time_compare?.length > 0
          ? {
              type: 'time',
              offset: timeCompare.time_compare,
            }
          : { type: '', offset: [] };
      this.filterConfig.function = timeCompare?.time_compare ? timeCompare : { time_compare: [] };
      /** 初始化过滤条件 */
      (item.query_configs || []).map(query => {
        const commonConditions = [];
        Object.keys(query.filter_dict.concat_filter || {}).map(key =>
          commonConditions.push({
            key: key.split('__')[0],
            method: key.split('__')[1],
            value: query.filter_dict.concat_filter[key],
          })
        );
        this.defaultCommonConditions = query.filter_dict.concat_filter;
        metrics = query.metrics.map(metrics => metrics.field);
        this.filterConfig = {
          ...this.filterConfig,
          where: query.where,
          group_by: query.group_by,
          limit: {
            limit: query.functions[0]?.params[0]?.value || 10,
            function: query.functions[0]?.id || 'top',
          },
          commonConditions,
        };
      });
    });
    const list = this.currentSelectedMetricList.find(item => metrics.includes(item.metric_name)) || { dimensions: [] };
    this.dimensionsList = list?.dimensions || [];

    const len = this.filterConfig.group_by.length;
    if (this.dimensionsList.length > 0) {
      for (const item of this.dimensionsList) {
        item.checked = this.filterConfig.group_by.includes(item.name);
      }
      if (len === 0) {
        this.setPanelConfigAndRefresh('group_by', [this.dimensionsList[0].name], false);
        this.dimensionsList[0].checked = true;
      }
      this.filterConfig.drill_group_by = len === 0 ? [this.dimensionsList[0].name] : this.filterConfig.group_by;
    }
  }
  /** 关闭按钮 */
  handleClose() {
    this.$emit('close');
  }

  /** 更新维度 */
  handleUpdateDimensions(list: IDimensionItem[], activeKey: string[]) {
    this.dimensionsList = list;
    this.filterConfig.drill_group_by = activeKey;
    this.setPanelConfigAndRefresh('group_by', activeKey);
  }
  /** 维度下钻 */
  handleChooseDrill(list, activeKey: string[]) {
    this.dimensionsList = this.dimensionsList.map((dimension: IDimensionItem) =>
      Object.assign(dimension, {
        checked: activeKey.includes(dimension.name),
      })
    );
    this.filterConfig.drill_group_by = activeKey;

    const drillFilter = {};
    list.map(item => (drillFilter[item.key] = item.value));
    this.setPanelConfigAndRefresh('group_by', activeKey, false);
    this.setPanelConfigAndRefresh('filter_dict.drill_filter', drillFilter);
  }
  /** 设置panel的值 */
  setPanelConfigAndRefresh(keys: string, value, isGetList = true) {
    const keysArray = keys.split('.');
    let current = this.panelData.targets[0].query_configs[0];

    for (let i = 0; i < keysArray.length; i++) {
      const key = keysArray[i];
      if (key === '__proto__' || key === 'constructor') continue;
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
    isGetList && this.getTableList();
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
    this.getTableList();
  }
  /** 修改时间间隔 */
  handleTimeRangeChange(val: TimeRangeType) {
    this.timeRange = [...val];
    this.getTableList();
  }
  /** 修改时区 */
  handleTimezoneChange(timezone: string) {
    this.showRestore = false;
    updateTimezone(timezone);
    this.getTableList();
  }
  /** 支持上下拖拽 */
  handleResizing(height: number) {
    this.drag.height = height;
    // this.chartKey = random(8);
  }
  /** 修改时间对比 */
  handleComparTypeChange(payload: IResultItem['compare']) {
    this.panelData.targets[0].function = !payload.type ? {} : { time_compare: payload.offset };
    this.filterConfig.function.time_compare = payload.offset;
    this.panelData = deepClone(this.panelData);
    this.getTableList();
  }
  /** 获取表格数据 */
  getTableList() {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    this.tableLoading = true;
    const len = (this.filterConfig.function.time_compare || []).length || 0;
    const baseParams = {
      start_time: startTime,
      end_time: endTime,
      group_by: this.filterConfig.drill_group_by,
    };
    const params = len > 0 ? { ...baseParams, ...{ function: this.filterConfig.function } } : baseParams;
    // biome-ignore lint/performance/noDelete: <explanation>
    len === 0 && delete this.panelData.targets[0].function;

    graphDrillDown({ ...this.panelData.targets[0], ...params })
      .then(res => {
        this.tableList = (res || []).map(item => {
          const compareValues = {};
          item.compare_values.map(compare => {
            compareValues[`${compare.offset}_value`] = compare.value;
            compareValues[`${compare.offset}_fluctuation`] = compare.fluctuation;
          });
          return { ...item, ...compareValues };
        });
      })
      .finally(() => {
        this.tableLoading = false;
      });
  }
  /** 修改聚合维度 */
  handleGroupByChange(item: IResultItem['group_by']) {
    this.setPanelConfigAndRefresh(
      'group_by',
      item.map(item => item.field)
    );
  }
  /** 修改限制 */
  handleLimitChange(item: IResultItem['limit']) {
    this.setPanelConfigAndRefresh('limit', item);
  }
  /** 修改过滤条件 */
  handleConditionChange(payload: { where: IResultItem['where']; custom_data: IResultItem['common_conditions'] }) {
    this.setPanelConfigAndRefresh('where', payload.where);
    const concatFilter = deepClone(this.defaultCommonConditions);
    payload.custom_data.map(item => {
      const key = `${item.key}__${item.method}`;
      concatFilter[key] = item.value;
    });
    this.setPanelConfigAndRefresh('filter_dict.concat_filter', concatFilter);
  }
  render() {
    return (
      <div
        ref='rootRef'
        class='drill-analysis-view'
      >
        <div class='drill-analysis-head'>
          <i
            class='icon-monitor icon-back-left close-btn'
            onClick={this.handleClose}
          />
          {this.$t('维度下钻')}
          <div class='filter-head-right'>
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
        <DrillAnalysisFilter
          filterConfig={this.filterConfig}
          refreshInterval={this.refreshInterval}
          timeRange={this.timeRange}
          onComparTypeChange={this.handleComparTypeChange}
          onConditionChange={this.handleConditionChange}
          onGroupByChange={this.handleGroupByChange}
          onLimitChange={this.handleLimitChange}
        />
        <div
          ref='drillMain'
          class='drill-analysis-main'
        >
          <bk-resize-layout
            extCls='drill-analysis-main-layout'
            slot='aside'
            border={false}
            initial-divide={'50%'}
            max={680}
            min={340}
            placement='top'
            onResizing={this.handleResizing}
          >
            <div
              class='drill-main-chart'
              slot='aside'
            >
              <NewMetricChart
                key={this.chartKey}
                style={{ height: `${this.drag.height - 30}px` }}
                chartHeight={this.drag.height}
                currentMethod={this.currentMethod}
                isShowLegend={true}
                isToolIconShow={false}
                panel={this.panelData}
              />
            </div>
            <div
              style={{ height: `${this.divHeight - this.drag.height - 4}px` }}
              class='drill-main-table'
              slot='main'
            >
              <DrillAnalysisTable
                dimensionsList={this.dimensionsList}
                filterConfig={this.filterConfig}
                loading={this.loading}
                tableList={this.tableList}
                tableLoading={this.tableLoading}
                onChooseDrill={this.handleChooseDrill}
                onUpdateDimensions={this.handleUpdateDimensions}
              />
            </div>
          </bk-resize-layout>
        </div>
      </div>
    );
  }
}
