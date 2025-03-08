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
import { Component, Ref, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getCustomTsMetricGroups, getGraphDrillDown } from 'monitor-api/modules/scene_view';
import { random, deepClone } from 'monitor-common/utils';
import MonitorDropdown from 'monitor-pc/components/monitor-dropdown';
import TimeRange, { type TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { DEFAULT_TIME_RANGE, getTimeDisplay } from 'monitor-pc/components/time-range/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import CompareType from '../components/header-box/components/compare-type';
import FilterConditions from '../components/header-box/components/filter-conditions';
import GroupBy from '../components/header-box/components/group-by';
import LimitFunction from '../components/header-box/components/limit-function';
import DrillAnalysisTable from './drill-analysis-table';
import NewMetricChart from './metric-chart';
import { refreshList } from './utils';

import type { IDimensionItem, IRefreshItem } from '../type';
import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

import './drill-analysis-view.scss';

/** 下钻分析 */
interface IDrillAnalysisViewProps {
  dimensionsList?: IDimensionItem[];
}
interface IDrillAnalysisViewEvents {
  onClose?: void;
}
@Component
export default class DrillAnalysisView extends tsc<IDrillAnalysisViewProps, IDrillAnalysisViewEvents> {
  // 图表panel实例
  @Prop({ default: () => ({}) }) panel: PanelModel;
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
  timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  /* 拖拽数据 */
  drag = { height: 400, minHeight: 300, maxHeight: 550 };
  divHeight = 0;
  resizeObserver = null;
  metricsList = [];
  commonDimensionList = [];
  compare: {
    type: '';
    offset: [];
  };
  metricGroups = [];
  /** 选中的维度值 */
  dimensionsActiveKey = [];
  loading = false;
  tableLoading = false;
  filterConfig = {
    metrics: [],
    where: [],
    common_conditions: [],
    group_by: [],
    limit: {
      function: 'top',
      limit: 10,
    },
    compare: {
      type: 'time',
      offset: [],
    },
  };
  /** 默认的图表配置 */
  get defaultPanelConfig() {
    return this.panelData?.targets[0] || {};
  }

  mounted() {
    this.refreshList = refreshList;
    this.$nextTick(() => {
      this.panelData = deepClone(this.panel);
      this.initDefaultFilterConfig();
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
  }
  beforeUnmount() {
    // 销毁观察器
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  }
  /** 初始化过滤条件 */
  initDefaultFilterConfig() {
    const defaultConfig = this.panelData?.targets[0] || {};
    if (!defaultConfig) {
      return;
    }
    const { query_configs = [] } = defaultConfig;
    if (query_configs.length > 0) {
      const metric = query_configs[0]?.group_by;
      this.filterConfig.group_by = metric;
    }
  }
  /** 获取当前可选的维度值 */
  handleGetCustomTsMetricGroups() {
    this.loading = true;
    getCustomTsMetricGroups({ time_series_group_id: 10 })
      .then(res => {
        this.metricGroups = res.metric_groups;
        let metrics = [];
        (this.panelData.targets || []).map(item => {
          (item.query_configs || []).map(query => {
            metrics = query.metrics.map(metrics => metrics.field);
          });
        });
        /** 获取当前需要展示的维度值 */
        this.metricGroups.map(item => {
          item.metrics.map(ele => {
            if (metrics.includes(ele.metric_name)) {
              this.dimensionsList = ele.dimensions;
            }
          });
        });
        if (this.dimensionsList.length > 0) {
          this.dimensionsList.map(ele =>
            Object.assign(ele, { checked: this.filterConfig.group_by.includes(ele.name) })
          );
        }
      })
      .finally(() => {
        this.loading = false;
      });
  }
  /** 关闭按钮 */
  handleClose() {
    this.$emit('close');
  }

  /** 更新维度 */
  handleUpdateDimensions(list: IDimensionItem[], activeKey: string[]) {
    this.dimensionsList = list;
    this.dimensionsActiveKey = activeKey;
    this.filterConfig.group_by = activeKey;
    this.getTableList();
  }
  /** 维度下钻 */
  handleChooseDrill(list, activeKey: string[]) {
    this.dimensionsList = this.dimensionsList.map((dimension: IDimensionItem) =>
      Object.assign(dimension, {
        checked: activeKey.includes(dimension.name),
      })
    );
    this.panelData.targets[0].query_configs[0].filter_dict['drill_filter'] = list;
    this.panelData = deepClone(this.panelData);
    this.filterConfig.group_by = activeKey;
    this.getTableList();
  }
  /** 修改刷新间隔 */
  handleRefreshInterval(val: number) {
    this.refreshInterval = val;
  }
  /** 手动刷新 */
  handleImmediateRefresh() {
    this.chartKey = random(8);
  }
  /** 修改时间间隔 */
  handleTimeRangeChange(val: TimeRangeType) {
    this.timeRange = [...val];
  }
  /** 修改时区 */
  handleTimezoneChange(timezone: string) {
    this.timezone = timezone;
  }
  /** 支持上下拖拽 */
  handleResizing(height: number) {
    this.drag.height = height;
    this.chartKey = random(8);
  }
  /** 修改时间对比 */
  handleComparTypeChange(payload) {
    this.filterConfig.compare = payload;
    this.getTableList();
  }
  /** 获取表格数据 */
  getTableList() {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    function convertData(data) {
      // 创建一个新对象，用于存储转换后的数据
      const result = {
        function: {
          time_compare: [],
        },
      };

      // 将offset数组的元素添加到time_compare数组中
      result.function.time_compare = [...data.offset];

      return result;
    }
    // 调用转换方法
    const output = convertData(this.filterConfig.compare);
    // 输出转换后的结果
    // console.log(output, 'output');
    this.tableLoading = true;
    const params = {
      start_time: startTime,
      end_time: endTime,
      ...this.filterConfig,
      /** 不对比 */
      // function: {
      //   time_compare: [],
      // },
    };
    // console.log('item', this.filterConfig.compare);
    getGraphDrillDown({ ...this.panelData.targets[0], ...params })
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
  handleGroupByChange(item) {
    this.filterConfig.group_by = item;
  }
  /** 修改限制 */
  handleLimitChange(item) {
    this.filterConfig.limit = item;
  }
  render() {
    return (
      <div class='drill-analysis-view'>
        <div class='drill-analysis-head'>
          {this.$t('下钻分析')}
          <i
            class='icon-monitor icon-mc-close close-btn'
            onClick={this.handleClose}
          />
        </div>
        <div class='drill-analysis-filter'>
          <div class='filter-left'>
            <FilterConditions
              commonDimensionList={this.commonDimensionList}
              metricsList={this.metricsList}
              // onChange={this.handleConditionChange}
            />
          </div>
          <div class='filter-right'>
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
              isRefleshInterval={true}
              list={this.refreshList}
              text-active={this.refreshInterval !== -1}
              value={this.refreshInterval}
              on-change={this.handleRefreshInterval}
              on-on-icon-click={this.handleImmediateRefresh}
            />
          </div>
        </div>
        <div class='compare-view'>
          <GroupBy
            metricsList={this.metricsList}
            value={this.filterConfig.group_by}
            onChange={this.handleGroupByChange}
          />
          {this.filterConfig.group_by.length > 0 && (
            <LimitFunction
              value={this.filterConfig.limit}
              onChange={this.handleLimitChange}
            />
          )}
          <CompareType
            value={this.filterConfig.compare}
            onChange={this.handleComparTypeChange}
          />
        </div>
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
