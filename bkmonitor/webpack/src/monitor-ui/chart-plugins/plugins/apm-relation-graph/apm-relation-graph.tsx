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

import { Component, Inject, InjectReactive, Ref } from 'vue-property-decorator';

// import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';
import { CancelToken } from 'monitor-api/index';
// import type { PanelModel } from '../../typings';
import { dataTypeBarQuery } from 'monitor-api/modules/apm_topo';
import { topoView } from 'monitor-api/modules/apm_topo';
import { Debounce } from 'monitor-common/utils';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';

import { CommonSimpleChart } from '../common-simple-chart';
import StatusTab from '../table-chart/status-tab';
import ApmRelationGraphContent from './components/apm-relation-graph-content';
import ApmRelationTopo, { type INodeModel } from './components/apm-relation-topo';
import BarAlarmChart, { getSliceTimeRange } from './components/bar-alarm-chart';
import ResourceTopo from './components/resource-topo/resource-topo';
import ServiceOverview from './components/service-overview';
import {
  alarmBarChartDataTransform,
  CategoryEnum,
  DATA_TYPE_LIST,
  EDataType,
  type EdgeDataType,
} from './components/utils';

import type { IFilterDict, ITableColumn, ITablePagination } from 'monitor-pc/pages/monitor-k8s/typings/table';

import './apm-relation-graph.scss';

const sideTopoMinWidth = 400;
const sideOverviewMinWidth = 320;

@Component
export default class ApmRelationGraph extends CommonSimpleChart {
  @Ref('content-wrap') contentWrap: ApmRelationGraphContent;

  // 框选事件范围后需应用到所有图表(包含三个数据 框选方法 是否展示复位  复位方法)
  @Inject({ from: 'enableSelectionRestoreAll', default: false }) readonly enableSelectionRestoreAll: boolean;
  @Inject({ from: 'handleChartDataZoom', default: () => null }) readonly handleChartDataZoom: (
    value: [number | string, number | string]
  ) => void;
  @Inject({ from: 'handleRestoreEvent', default: () => null }) readonly handleRestoreEvent: () => void;
  @InjectReactive({ from: 'showRestore', default: false }) readonly showRestoreInject: boolean;

  callColumn = {
    caller: {
      name: window.i18n.t('主调'),
      icon: 'icon-back-right',
    },
    callee: {
      name: window.i18n.t('被调'),
      icon: 'icon-back-left',
    },
  };

  @InjectReactive({ from: 'customRouteQuery', default: () => ({}) }) customRouteQuery: Record<string, number | string>;
  @Inject('handleCustomRouteQueryChange') handleCustomRouteQueryChange: (
    customRouterQuery: Record<string, number | string>
  ) => void;
  /* 概览图、列表图切换 */
  showTypes = [
    {
      id: 'topo',
      icon: 'icon-mc-overview',
    },
    {
      id: 'table',
      icon: 'icon-mc-list',
    },
  ];
  showType = 'topo';
  /* 数据类型 */
  dataType = EDataType.Alert;

  edgeDataType: EdgeDataType = 'request_count';

  /** 激活节点, 节点id */
  activeNode = '';

  /* 筛选列表 */
  filterList = [
    {
      id: CategoryEnum.ALL,
      name: '全部',
      icon: 'icon-gailan',
    },
    {
      id: CategoryEnum.HTTP,
      name: '网页',
      icon: 'icon-wangye',
    },
    {
      id: CategoryEnum.RPC,
      name: '远程调用',
      icon: 'icon-yuanchengfuwu',
    },
    {
      id: CategoryEnum.DB,
      name: '数据库',
      icon: 'icon-DB',
    },
    {
      id: CategoryEnum.MESSAGING,
      name: '消息队列',
      icon: 'icon-xiaoxizhongjianjian',
    },
    {
      id: CategoryEnum.ASYNC_BACKEND,
      name: '后台任务',
      icon: 'icon-renwu',
    },
    {
      id: CategoryEnum.OTHER,
      name: '其他',
      icon: 'icon-zidingyi',
    },
  ];

  /** 筛选条件 */
  filterCondition = {
    /** 筛选类型 */
    type: CategoryEnum.ALL,
    /** 展示无数据节点 */
    showNoData: true,
    /** 搜索值 */
    searchValue: '',
  };

  filterColumn: IFilterDict = {};
  columnSort = {
    field: '',
    order: 'ascending',
  };

  /* 展开列表 */
  expandList = [
    {
      id: 'topo',
      icon: 'icon-ziyuan',
    },
    {
      id: 'overview',
      icon: 'icon-mc-overview',
    },
  ];
  expanded = [];

  /* 表格数据 */
  tableColumns: ITableColumn[] = [];
  // 所有的表格数据
  tableData = [];

  /** 分页数据 */
  pagination: ITablePagination = {
    current: 1,
    count: 2,
    limit: 10,
    showTotalCount: true,
  };

  graphData = {
    nodes: [],
    edges: [],
  };
  /** 取消拓扑图请求 */
  topoCancelFn = null;
  loading = {
    topo: true,
    table: true,
  };

  /* 获取头部告警柱状条形图数据方法 */
  getAlarmBarData = null;
  isAlarmBarDataZoomed = false;

  sliceTimeRange = [0, 0];
  /* 当前点击的服务 */
  selectedServiceName = '';
  /* 当前点击的接口 */
  selectedEndpoint = '';

  /** 经过过滤的表格数据 */
  get filterTableData() {
    const { searchValue, type } = this.filterCondition;
    const showAll = type === CategoryEnum.ALL;
    const filterData = this.tableData.filter(item => {
      const { other_service, service } = item;
      // 关键字搜索匹配
      const isKeywordMatch = service.name.toLowerCase().includes(searchValue.toLowerCase());
      // 图例过滤
      const isLegendFilter = showAll || [service.category, other_service.category].includes(type);
      const columnFilter = Object.keys(this.filterColumn).every(key => {
        return this.filterColumn[key].includes(item[key]);
      });
      return isKeywordMatch && isLegendFilter && columnFilter;
    });
    this.sortTable(filterData);
    return filterData;
  }

  /** 最终展示的表格数据 */
  get showTableData() {
    const { current, limit } = this.pagination;
    return this.filterTableData.slice((current - 1) * limit, current * limit);
  }

  get appName() {
    return this.viewOptions?.app_name || '';
  }

  get serviceName() {
    return this.viewOptions?.service_name || '';
  }

  /* 当前图表内参数 */
  get filters() {
    return {
      app_name: this.appName,
      service_name: this.serviceName,
      data_type: this.dataType,
      search: this.filterCondition.searchValue,
    };
  }

  get serviceOverviewData() {
    return this.panel.options.apm_relation_graph;
  }

  /* 右侧按钮禁用状态 */
  get rightExpandDisable() {
    return this.showType === 'table' || !(this.selectedServiceName || this.selectedEndpoint);
  }

  created() {
    this.getSliceTimeRange();
  }

  /**
   * @description: 获取图表数据
   */
  @Debounce(200)
  async getPanelData(start_time?: string, end_time?: string) {
    this.beforeGetPanelData(start_time, end_time);
    this.handleLoadingChange(true);

    try {
      this.unregisterOberver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
        app_name: this.appName,
        service_name: this.serviceName,
        data_type: this.dataType,
      };
      this.getTopoData(params);
      this.getAlarmBarData = async setData => {
        const data = await dataTypeBarQuery({
          ...params,
        }).catch(() => ({ series: [] }));
        const result = alarmBarChartDataTransform(this.dataType, data.series);
        /* 默认切片时间 */
        const lastTime = result[result.length - 1].time;
        if (!this.sliceTimeRange.every(t => t) || this.sliceTimeRange[0] > lastTime || this.isAlarmBarDataZoomed) {
          const sliceTimeRange = getSliceTimeRange(result, result[result.length - 1].time);
          this.handleSliceTimeRangeChange(sliceTimeRange as any);
          this.isAlarmBarDataZoomed = false;
        }
        setData(result, this.sliceTimeRange);
      };
    } catch (e) {
      console.error(e);
    }
    this.handleLoadingChange(false);
  }

  async getTopoData(params?) {
    let res = params;
    this.topoCancelFn?.();
    if (!params) {
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      res = {
        start_time: startTime,
        end_time: endTime,
        app_name: this.appName,
        service_name: this.serviceName,
        data_type: this.dataType,
      };
    }
    const exportType = this.showType;
    this.loading[exportType] = true;
    const data = await topoView(
      {
        ...res,
        edge_data_type: this.edgeDataType,
        export_type: exportType,
      },
      {
        cancelToken: new CancelToken(c => {
          this.topoCancelFn = c;
        }),
      }
    ).catch(() => {
      if (this.showType === 'topo') return { edges: [], nodes: [] };
      return { columns: [], data: [] };
    });
    this.loading[exportType] = false;
    if (this.showType === 'topo') {
      this.graphData = data;
    } else {
      this.tableColumns = data.columns.map(item => {
        if (item.id === 'type') {
          return {
            ...item,
            type: 'scoped_slots',
          };
        }
        return item;
      });
      this.tableData = data.data;
    }
  }

  handleEdgeTypeChange(edgeType) {
    this.edgeDataType = edgeType;
    this.getTopoData();
  }

  /**
   * @description 伸缩侧栏
   * @param id
   */
  handleExpand(id: string) {
    const index = this.expanded.findIndex(key => key === id);
    if (index >= 0) {
      this.expanded.splice(index, 1);
    } else {
      this.expanded.push(id);
    }
  }

  handleSearch(v) {
    this.filterCondition.searchValue = v;
    this.pagination.current = 1;
  }

  handleShowNoDataChange(val) {
    this.filterCondition.showNoData = val;
    this.pagination.current = 1;
  }

  handleFilterChange(id: CategoryEnum) {
    this.filterCondition.type = id;
    this.pagination.current = 1;
  }

  handleTablePageChange(page) {
    this.pagination.current = page;
  }

  handleTableLimitChange(pageSize) {
    this.pagination.limit = pageSize;
    this.pagination.current = 1;
  }

  handleTableFilterChange(filters: IFilterDict) {
    this.filterColumn = { ...filters };
  }

  handleTableSortChange({ prop, order }) {
    this.columnSort = {
      field: prop,
      order,
    };
  }

  sortTable(list) {
    const { field, order } = this.columnSort;
    if (!field || !order) return;
    list.sort((a, b) => {
      if (field === 'request_count') {
        return order === 'ascending' ? a[field] - b[field] : b[field] - a[field];
      }
      if (field === 'error_rate') {
        return order === 'ascending' ? a[field].localeCompare(b[field]) : b[field].localeCompare(a[field]);
      }
      if (field === 'avg_duration') {
        return order === 'ascending'
          ? a.avg_duration_original - b.avg_duration_original
          : b.avg_duration_original - a.avg_duration_original;
      }
    });
  }

  handleShowTypeChange(item) {
    if (this.showType === item.id) return;
    this.showType = item.id;
    this.getTopoData();
  }

  handleDataTypeChange() {
    this.getPanelData();
  }

  dataZoom(startTime: string, endTime: string) {
    this.isAlarmBarDataZoomed = true;
    if (this.enableSelectionRestoreAll) {
      this.handleChartDataZoom([startTime, endTime]);
    } else {
      this.getPanelData(startTime, endTime);
    }
  }

  /** 点击节点 */
  handleNodeClick(node: INodeModel) {
    this.activeNode = node.data.id;
    this.selectedServiceName = node.data.id;
    if (!this.expanded.includes('overview')) {
      this.handleExpand('overview');
    }
  }

  /** 资源拓扑 */
  handleResourceDrilling(node: INodeModel) {
    this.activeNode = node.data.id;
    this.selectedServiceName = node.data.id;
    if (!this.expanded.includes('topo')) {
      this.handleExpand('topo');
    }
  }

  /** 资源概览 */
  handleServiceDetail(node: INodeModel) {
    this.activeNode = node.data.id;
  }

  /**
   * @description 获取路由的切片时间范围
   */
  getSliceTimeRange() {
    const { sliceStartTime, sliceEndTime } = this.customRouteQuery;
    if (sliceStartTime && sliceEndTime) {
      this.sliceTimeRange = [+sliceStartTime, +sliceEndTime];
    }
  }

  /**
   * @description 切片时间范围变化
   * @param timeRange
   */
  handleSliceTimeRangeChange(timeRange: [number, number]) {
    this.sliceTimeRange = JSON.parse(JSON.stringify(timeRange));
    this.handleCustomRouteQueryChange({
      sliceStartTime: this.sliceTimeRange[0],
      sliceEndTime: this.sliceTimeRange[1],
    });
  }

  render() {
    return (
      <div class='apm-relation-graph'>
        <div class='apm-relation-graph-header'>
          <div class='header-select-wrap'>
            <div class='data-type-select'>
              {this.showTypes.map(item => (
                <div
                  key={item.id}
                  class={['data-type-item', { active: this.showType === item.id }]}
                  onClick={() => this.handleShowTypeChange(item)}
                >
                  <span class={`icon-monitor ${item.icon}`} />
                </div>
              ))}
            </div>
            <bk-select
              class='type-selector'
              v-model={this.dataType}
              clearable={false}
              onChange={this.handleDataTypeChange}
            >
              {DATA_TYPE_LIST.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ))}
            </bk-select>
          </div>
          <div class='header-alarm-wrap'>
            <BarAlarmChart
              activeItemHeight={24}
              dataType={this.dataType}
              enableSelect={true}
              getData={this.getAlarmBarData}
              itemHeight={16}
              sliceTimeRange={this.sliceTimeRange}
              onDataZoom={this.dataZoom as any}
              onSliceTimeRangeChange={this.handleSliceTimeRangeChange}
            />
          </div>
          <div class='header-search-wrap'>
            <StatusTab
              class='ml-24'
              needAll={false}
              needExpand={true}
              statusList={this.filterList}
              value={this.filterCondition.type}
              onChange={this.handleFilterChange}
            />
            <bk-checkbox
              class='ml-24'
              value={this.filterCondition.showNoData}
              onChange={this.handleShowNoDataChange}
            >
              无数据节点
            </bk-checkbox>
            <bk-input
              class='ml-24'
              behavior='simplicity'
              placeholder={'搜索服务、接口'}
              right-icon='bk-icon icon-search'
              value={this.filterCondition.searchValue}
              clearable
              onBlur={this.handleSearch}
              onClear={this.handleSearch}
              onEnter={this.handleSearch}
            />
          </div>
          <div class='header-tool-wrap'>
            <div class='tool-btns'>
              {this.expandList.map(item => (
                <div
                  key={item.id}
                  class={[
                    'tool-btn',
                    { disabled: this.rightExpandDisable },
                    { active: this.expanded.includes(item.id) },
                  ]}
                  onClick={() => !this.rightExpandDisable && this.handleExpand(item.id)}
                >
                  <span class={`icon-monitor ${item.icon}`} />
                </div>
              ))}
            </div>
          </div>
        </div>
        {this.showType === 'topo' ? (
          <ApmRelationGraphContent
            ref='content-wrap'
            expanded={this.expanded}
          >
            {!this.loading.topo ? (
              <ApmRelationTopo
                activeNode={this.activeNode}
                data={this.graphData}
                edgeType={this.edgeDataType}
                filterCondition={this.filterCondition}
                onEdgeTypeChange={this.handleEdgeTypeChange}
                onNodeClick={this.handleNodeClick}
                onResourceDrilling={this.handleResourceDrilling}
                onServiceDetail={this.handleServiceDetail}
              />
            ) : (
              <div class='empty-chart'>{this.$t('加载中')}</div>
            )}

            <div
              class='side-wrap'
              slot='side'
            >
              <div
                style={{
                  minWidth: `${sideTopoMinWidth}px`,
                  display: this.expanded.includes('topo') ? 'block' : 'none',
                }}
                class='source-topo'
              >
                <div class='header-wrap'>
                  <div class='title'>资源拓扑</div>
                  <div
                    class='expand-btn'
                    onClick={() => this.handleExpand('topo')}
                  >
                    <span class='icon-monitor icon-zhankai' />
                  </div>
                </div>
                <div class='content-wrap'>
                  <ResourceTopo />
                </div>
              </div>

              <div
                style={{
                  minWidth: `${sideOverviewMinWidth}px`,
                  display: this.expanded.includes('overview') ? 'block' : 'none',
                }}
                class={['service-overview', { 'no-border': !this.expanded.includes('topo') }]}
              >
                <div class='header-wrap'>
                  <div class='title'>{this.selectedEndpoint ? this.$t('接口概览') : this.$t('服务概览')}</div>
                  <div
                    class='expand-btn'
                    onClick={() => this.handleExpand('overview')}
                  >
                    <span class='icon-monitor icon-zhankai' />
                  </div>
                </div>
                <div class='content-wrap'>
                  <ServiceOverview
                    appName={this.appName}
                    data={this.serviceOverviewData}
                    endpoint={this.selectedEndpoint}
                    serviceName={this.selectedServiceName}
                    show={this.expanded.includes('overview')}
                    timeRange={this.timeRange}
                  />
                </div>
              </div>
            </div>
          </ApmRelationGraphContent>
        ) : (
          <div class='apm-relation-graph-table-wrap'>
            <div class='table-wrap'>
              {this.loading.table ? (
                <TableSkeleton type={2} />
              ) : (
                <CommonTable
                  pagination={{
                    ...this.pagination,
                    count: this.filterTableData.length,
                  }}
                  scopedSlots={{
                    type: row => (
                      <div class='call-type-column'>
                        <span>{this.callColumn[row.type]?.name}</span>
                        <div class={`icon ${row.type}`}>
                          <i class={`icon-monitor ${this.callColumn[row.type]?.icon}`} />
                        </div>
                      </div>
                    ),
                  }}
                  checkable={false}
                  columns={this.tableColumns}
                  data={this.showTableData}
                  paginationType={'simple'}
                  onFilterChange={this.handleTableFilterChange}
                  onLimitChange={this.handleTableLimitChange}
                  onPageChange={this.handleTablePageChange}
                  onSortChange={this.handleTableSortChange}
                />
              )}
            </div>
          </div>
        )}
      </div>
    );
  }
}
