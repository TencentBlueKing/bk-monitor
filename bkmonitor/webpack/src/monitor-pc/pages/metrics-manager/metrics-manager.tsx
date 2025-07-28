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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getMetricListV2 } from 'monitor-api/modules/strategies';
// import { MetricType } from '../../components/metric-selector/typings';
import { random } from 'monitor-common/utils/utils';

import FilterPanel, { type IFilterData } from '../strategy-config/strategy-config-list/filter-panel';
import { handleMouseDown, handleMouseMove } from '../strategy-config/util';
import MetricsTable from './metrics-table';

import type { EmptyStatusType } from '../../components/empty-status/types';
import type { IGroupData } from '../strategy-config/strategy-config-list/group';
import type { IMetricDetail } from '../strategy-config/strategy-config-set-new/typings';

import './metrics-manager.scss';
/** 采集来源数据 */
const dataSourceCheckedList = [
  { id: 'bk_monitor', name: window.i18n.t('监控采集指标'), count: 0 },
  { id: 'bk_data', name: window.i18n.t('计算平台指标'), count: 0 },
  { id: 'custom', name: window.i18n.t('自定义指标'), count: 0 },
  { id: 'bk_log_search', name: window.i18n.t('日志平台指标'), count: 0 },
  { id: 'bk_apm', name: window.i18n.t('应用监控Trace指标'), count: 0 },
];

@Component
export default class MetricsManager extends tsc<object> {
  /* 左边容器宽度 */
  drapWidth = 240;
  /* 是否显示左边容器 */
  showLeft = true;
  /* 是否hover到拖拽部分 */
  drapActive = false;
  /* 左侧统计数据 */
  leftFilter: {
    checkedData: IFilterData[];
    defaultActiveName: string[];
    filterList: IGroupData[];
    key: string;
    show: boolean;
  } = {
    filterList: [],
    checkedData: [],
    defaultActiveName: [],
    show: true,
    key: random(8),
  };
  /* 监控对象列表 */
  scenarioList = [];
  /* 数据来源 */
  dataSourceList = [];
  /* 表格数据 */
  tableData: IMetricDetail[] = [];
  /* 分页数据 */
  pagination = {
    current: 1,
    count: 0,
    limit: 10,
    showTotalCount: true,
  };
  /* 表头列表筛选列表 */
  tableHeaderFilters = {
    metricType: [],
    unit: [],
    enabled: [],
  };
  loading = false;
  tableLoading = false;
  // 表格查询结果所对应的状态
  emptyStatusType: EmptyStatusType = 'empty';
  /* 搜索条件 */
  condition = [];
  /* 数据来源筛选 */
  dataSource = [];

  activated() {
    this.getMetricList(true);
  }

  /* 获取指标列表 */
  async getMetricList(isInit = false) {
    if (isInit) {
      this.loading = true;
    } else {
      this.tableLoading = true;
    }
    const dataSourceLabels = [];
    const resultTableLabels = [];
    this.leftFilter.checkedData.forEach(item => {
      if (item.id === 'data_source_label') {
        dataSourceLabels.push(...item.values.map(v => v.id));
      }
      if (item.id === 'result_table_label') {
        resultTableLabels.push(...item.values.map(v => v.id));
      }
    });
    const dataSource = [];
    dataSourceLabels.forEach(item => {
      if (!dataSource.map(d => d[0]).includes(item)) {
        dataSource.push([item, 'time_series']);
      }
    });
    this.dataSource.forEach(item => {
      if (!dataSource.map(d => d[0]).includes(item[0])) {
        dataSource.push([item[0], 'time_series']);
      }
    });
    this.emptyStatusType = 'empty';
    const data = await getMetricListV2({
      conditions: this.condition,
      data_type_label: 'time_series',
      result_table_label: resultTableLabels,
      data_source: dataSource,
      tag: '',
      page: this.pagination.current,
      page_size: this.pagination.limit,
    })
      .then(response => {
        this.handleShowLeft(true);
        if (!response.count) {
          this.emptyStatusType = 'search-empty';
          this.handleShowLeft(false);
        }
        return response;
      })
      .catch(() => {
        this.emptyStatusType = '500';
        this.handleShowLeft(false);
        return {
          count: 0,
          data_source_list: [],
          metric_list: [],
          scenario_list: [],
        };
      });
    this.scenarioList = data.scenario_list;
    this.dataSourceList = data.data_source_list;
    this.tableData = data.metric_list;
    this.pagination.count = data.count;
    this.getFilterList();
    if (isInit) {
      this.leftFilter.key = random(8);
    }
    this.loading = false;
    this.tableLoading = false;
  }

  /* 获取左侧统计列表 */
  getFilterList() {
    const scenarioCountMap = {};
    this.scenarioList.forEach(item => {
      scenarioCountMap[item.id] = item.count;
    });
    this.leftFilter.defaultActiveName = ['data_source_label', 'result_table_label'];
    this.leftFilter.filterList = [
      {
        id: 'data_source_label',
        name: this.$tc('采集来源'),
        data: dataSourceCheckedList
          .map(item => {
            const target = this.dataSourceList.find(
              set => set.data_type_label === 'time_series' && set.data_source_label === item.id
            );
            const count = target?.count || 0;
            return {
              id: item.id,
              name: item.name,
              count,
            };
          })
          .filter(item => !!item.count),
      },
      {
        id: 'result_table_label',
        name: this.$tc('监控对象'),
        data: this.scenarioList
          .map(item => {
            this.$set(item, 'count', scenarioCountMap[item.id] || 0);
            return item;
          })
          .filter(item => !!item.count),
      },
    ];
  }

  handleMouseDown(e) {
    handleMouseDown(e, 'resizeTarget', 114, { min: 200, max: 500 }, width => {
      if (this.showLeft) {
        const offset = 10;
        this.showLeft = width !== 200;
        this.drapWidth = width + offset;
      }
    });
  }
  handleMouseMove(e) {
    handleMouseMove(e);
  }

  /* 收起/展开 左边容器 */
  handleShowLeft(value: boolean) {
    if (value) {
      this.drapWidth = 240;
    } else {
      this.drapWidth = 0;
    }
    this.showLeft = value;
  }

  /* 左侧筛选选择  */
  handleFilterSelectChange(data) {
    this.leftFilter.checkedData = data;
    this.pagination.current = 1;
    this.getMetricList();
  }
  /* 分页 */
  handPageChange(page: number) {
    this.pagination.current = page;
    this.getMetricList();
  }
  handleLimitChange(limit: number) {
    this.pagination.current = 1;
    this.pagination.limit = limit;
    this.getMetricList();
  }
  /* 条件搜索 */
  handleConditionChange(condition: { key: string; value: string }[]) {
    this.condition = condition;
    this.pagination.current = 1;
    this.getMetricList();
  }

  handleDataSourceChange(dataSource: string[][]) {
    this.dataSource = dataSource;
    this.pagination.current = 1;
    this.getMetricList();
  }

  /* 检索 */
  handleToDataRetrieval(metricId: string) {
    window.open(`${location.origin}${location.pathname}${location.search}#/data-retrieval/?metric_id=${metricId}`);
  }

  handleEnableChange(value: string) {
    this.pagination.current = 1;
    if (value.length && !value.includes('enable')) {
      this.scenarioList = [];
      this.dataSourceList = [];
      this.tableData = [];
      this.pagination.count = 0;
      this.getFilterList();
    } else {
      this.getMetricList();
    }
  }

  // 在表格中点击清空筛选
  handleClearFilter() {
    this.leftFilter.checkedData = [];
    this.condition.length = 0;
    this.getMetricList();
  }

  // 在表格中点击刷新
  handleRefresh() {
    this.getMetricList();
  }

  render() {
    return (
      <div
        class='metrics-manager-page'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='metrics-manager-content'>
          <div
            style={{ width: `${this.drapWidth}px`, display: this.showLeft ? 'block' : 'none' }}
            class={['content-left', { drapActive: this.drapActive }]}
            data-tag='resizeTarget'
          >
            <div
              class='content-left-drag'
              onMousedown={this.handleMouseDown}
              onMouseenter={() => (this.drapActive = true)}
              onMouseleave={() => (this.drapActive = false)}
              onMousemove={this.handleMouseMove}
            />
            <FilterPanel
              key={this.leftFilter.key}
              checkedData={this.leftFilter.checkedData}
              data={this.leftFilter.filterList}
              defaultActiveName={this.leftFilter.defaultActiveName}
              show={this.leftFilter.show}
              on-change={this.handleFilterSelectChange}
            >
              <div slot='header'>
                <div class='header mb20'>
                  <span class='left'>{this.$t('统计')}</span>
                  <span
                    class='right icon-monitor icon-double-up'
                    onClick={() => this.handleShowLeft(false)}
                  />
                </div>
              </div>
            </FilterPanel>
          </div>
          <div
            class='content-right'
            v-bkloading={{ isLoading: this.tableLoading }}
          >
            <MetricsTable
              emptyStatusType={this.emptyStatusType}
              pagination={this.pagination as any}
              tableData={this.tableData}
              onClearFilter={this.handleClearFilter}
              onConditionChange={this.handleConditionChange}
              onDataRetrieval={this.handleToDataRetrieval}
              onDataSourceChange={this.handleDataSourceChange}
              onEnableChange={this.handleEnableChange}
              onLimitChange={this.handleLimitChange}
              onPageChange={this.handPageChange}
              onRefresh={this.handleRefresh}
            >
              {!this.showLeft ? (
                <span slot='headerLeft'>
                  <span
                    class='right icon-monitor icon-double-up'
                    onClick={() => this.handleShowLeft(true)}
                  />
                </span>
              ) : undefined}
            </MetricsTable>
          </div>
        </div>
      </div>
    );
  }
}
