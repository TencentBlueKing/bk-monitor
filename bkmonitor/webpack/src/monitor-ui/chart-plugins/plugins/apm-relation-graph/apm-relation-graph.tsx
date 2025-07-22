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

import { Component, Inject, InjectReactive, ProvideReactive, Ref, Watch } from 'vue-property-decorator';

// import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';
import { CancelToken } from 'monitor-api/cancel';
// import type { PanelModel } from '../../typings';
import { dataTypeBarQuery } from 'monitor-api/modules/apm_topo';
import { topoView } from 'monitor-api/modules/apm_topo';
import { Debounce, random } from 'monitor-common/utils';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { getDateRange, getTimeDisplay, handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';

import { CustomChartConnector } from '../../utils/utils';
import { CommonSimpleChart } from '../common-simple-chart';
import StatusTab from '../table-chart/status-tab';
import ApmRelationGraphContent from './components/apm-relation-graph-content';
import ApmRelationTopo, { type INodeModel } from './components/apm-relation-topo';
import BarAlarmChart from './components/bar-alarm-chart';
// import ResourceTopo from './components/resource-topo/resource-topo';
import ServiceOverview from './components/service-overview';
import {
  alarmBarChartDataTransform,
  CategoryEnum,
  DATA_TYPE_LIST,
  EDataType,
  nodeIconClass,
  type EdgeDataType,
} from './components/utils';

import type { IFilterDict, ITableColumn, ITablePagination } from 'monitor-pc/pages/monitor-k8s/typings/table';

import './apm-relation-graph.scss';

@Component({
  name: 'ApmRelationGraph',
  components: {
    ResourceTopo: () => import('./components/resource-topo/resource-topo'),
  },
})
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
  @ProvideReactive('customChartConnector') customChartConnector: CustomChartConnector = null;
  showTypes = [
    {
      id: 'topo',
      icon: 'icon-mc-apm-topo',
      size: '18px',
    },
    {
      id: 'table',
      icon: 'icon-mc-list',
      size: '16px',
    },
  ];
  showType = 'topo';
  /* 数据类型 */
  dataType = EDataType.Alert;

  edgeDataType: EdgeDataType = 'request_count';

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
    /** 搜索值 */
    searchValue: '',
  };

  filterColumn: IFilterDict = {};
  columnSort = {
    field: '',
    order: 'ascending',
  };
  expanded = [];

  /** 是否需要缓存 */
  needCache = true;
  /** 拓扑图和表格数据缓存 */
  graphAndTableDataCache = new Map();
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

  /** topo图是否需要重新布局 */
  refreshTopoLayout = true;
  /** 图表数据 */
  graphData = {
    nodes: [],
    edges: [],
  };

  /** 取消拓扑图请求 */
  topoCancelFn = null;
  requestId = 0;
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
  selectedIcon = '';

  nodeTipsMap = new Map();
  timeTips = '';

  dashboardId = random(8);
  /* 展开列表 */
  get expandList() {
    return [
      {
        id: 'topo',
        tips: this.resourceDisable
          ? this.selectedEndpoint
            ? window.i18n.t('请选择非接口节点')
            : window.i18n.t('请选择节点')
          : window.i18n.t('资源拓扑'),
        icon: 'icon-ziyuan',
      },
      {
        id: 'overview',
        tips: this.overviewDisable
          ? window.i18n.t('请选择节点')
          : this.selectedEndpoint
            ? window.i18n.t('接口概览')
            : window.i18n.t('服务概览'),
        icon: 'icon-mc-overview',
      },
    ];
  }

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
  get overviewDisable() {
    return this.showType === 'table' || !this.selectedServiceName;
  }
  get resourceDisable() {
    return this.showType === 'table' || !!this.selectedEndpoint || !this.selectedServiceName;
  }
  setTimeTips() {
    if (this.sliceTimeRange[0] && this.sliceTimeRange[1]) {
      this.timeTips = getTimeDisplay(this.sliceTimeRange);
      return;
    }
    if (this.timeRange.some(time => time.toString().includes('now'))) {
      const dateRange = getDateRange(this.timeRange);
      this.timeTips = getTimeDisplay([dateRange.startDate, dateRange.endDate]);
      return;
    }
    this.timeTips = getTimeDisplay(this.timeRange);
  }

  created() {
    this.getSliceTimeRange();
    this.customChartConnector = new CustomChartConnector(this.dashboardId);
  }
  beforeDestroy() {
    this.customChartConnector?.removeChartInstance();
  }
  destroyed() {
    this.topoCancelFn?.();
  }

  @Watch('timeRange')
  // 数据时间间隔
  handleTimeRangeChange() {
    this.refreshTopoLayout = true;
    this.needCache = false;
    this.selectedServiceName = '';
    this.expanded = [];
    this.getPanelData();
  }

  @Watch('refreshInterval')
  // 数据刷新间隔
  handleRefreshIntervalChange(v: number) {
    if (this.refreshIntervalInstance) {
      window.clearInterval(this.refreshIntervalInstance);
    }
    if (!v || +v < 60 * 1000) return;
    this.refreshIntervalInstance = window.setInterval(() => {
      if (this.initialized) {
        this.refreshTopoLayout = false;
        this.needCache = false;
        this.selectedServiceName = '';
        this.expanded = [];
        this.getPanelData();
      }
    }, v);
  }
  @Watch('refreshImmediate')
  // 立刻刷新
  handleRefreshImmediateChange(v: string) {
    if (v) {
      this.refreshTopoLayout = false;
      this.needCache = false;
      // this.selectedServiceName = '';
      // this.expanded = [];
      this.getPanelData();
    }
  }

  /**
   * @description: 获取图表数据
   */
  @Debounce(200)
  async getPanelData(start_time?: string, end_time?: string) {
    this.beforeGetPanelData(start_time, end_time);
    this.handleLoadingChange(true);
    try {
      this.unregisterObserver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
        app_name: this.appName,
        service_name: this.serviceName,
        data_type: this.dataType,
      };
      this.getTopoData();
      this.getAlarmBarData = async setData => {
        const data = await dataTypeBarQuery({
          ...params,
        }).catch(() => ({ series: [] }));
        const result = alarmBarChartDataTransform(this.dataType, data.series);
        if (result.length >= 2) {
          /* 默认切片时间 */
          const lastTime = result[result.length - 1].time;
          const firstTime = result[0].time;
          if (this.sliceTimeRange.every(t => t)) {
            if (this.sliceTimeRange[0] > lastTime || this.sliceTimeRange[1] < firstTime) {
              this.handleSliceTimeRangeChange([0, 0], true);
            }
          }
        } else {
          this.handleSliceTimeRangeChange([0, 0], true);
        }
        /* if (!this.sliceTimeRange.every(t => t) || this.sliceTimeRange[0] > lastTime || this.isAlarmBarDataZoomed) {
          const sliceTimeRange = getSliceTimeRange(result, result[result.length - 1].time);
          this.handleSliceTimeRangeChange(sliceTimeRange as any);
          this.isAlarmBarDataZoomed = false;
        } */
        setData(result, this.sliceTimeRange);
      };
    } catch (e) {
      console.error(e);
    }
    this.handleLoadingChange(false);
  }

  async getTopoData() {
    this.setTimeTips();
    this.requestId += 1;
    const requestId = this.requestId;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const exportType = this.showType;
    const [sliceTimeStart, sliceTimeEnd] = this.sliceTimeRange;
    const params = {
      start_time: startTime,
      end_time: endTime,
      app_name: this.appName,
      metric_start_time: sliceTimeStart / 1000 || startTime,
      metric_end_time: sliceTimeEnd / 1000 || endTime,
      service_name: this.serviceName,
      edge_data_type: this.edgeDataType,
      export_type: exportType,
      ...(this.showType === 'topo' && {
        data_type: this.dataType,
      }),
    };
    this.topoCancelFn?.();
    const cacheKey = JSON.stringify({
      ...params,
      start_time: startTime,
      end_time: endTime,
      metric_start_time: sliceTimeStart,
      metric_end_time: sliceTimeEnd,
    });
    let data = null;
    this.loading[exportType] = true;
    this.refreshTopoLayout = this.refreshTopoLayout || (!this.graphData.nodes.length && !this.graphData.edges.length);
    if (this.needCache && this.graphAndTableDataCache.has(cacheKey)) {
      data = this.graphAndTableDataCache.get(cacheKey);
      if (exportType === 'topo' && data?.nodes?.length > 100) {
        setTimeout(() => (this.loading[exportType] = false), 500);
      } else {
        this.loading[exportType] = false;
      }
    } else {
      data = await topoView(params, {
        cancelToken: new CancelToken(c => {
          this.topoCancelFn = c;
        }),
      }).catch(() => {
        if (exportType === 'topo') return { edges: [], nodes: [] };
        return { columns: [], data: [] };
      });
      this.needCache = true;
      /** 两个请求ID不一样， 说明是取消请求， 不关闭loading */
      if (this.requestId !== requestId) return;
      this.graphAndTableDataCache.set(cacheKey, data);
      if (exportType === 'topo' && data?.nodes?.length > 100) {
        setTimeout(() => (this.loading[exportType] = false), 500);
      } else {
        this.loading[exportType] = false;
      }
    }
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
        if (item.id === 'operators') {
          return {
            ...item,
            showOverflowTooltip: false,
          };
        }
        return item;
      });
      this.tableData = data.data;
    }
  }

  handleEdgeTypeChange(edgeType) {
    this.edgeDataType = edgeType;
    this.refreshTopoLayout = false;
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

  @Debounce(200)
  handleSearch(v) {
    this.filterCondition.searchValue = v;
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
        return order === 'ascending'
          ? (a[field] ?? '').localeCompare(b[field])
          : (b[field] ?? '').localeCompare(a[field]);
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
    this.refreshTopoLayout = false;
    this.getTopoData();
  }

  handleDataTypeChange() {
    this.refreshTopoLayout = false;
    this.getPanelData();
  }

  dataZoom(startTime: string, endTime: string) {
    this.isAlarmBarDataZoomed = true;
    this.refreshTopoLayout = true;
    if (this.enableSelectionRestoreAll) {
      this.handleChartDataZoom([startTime, endTime]);
    } else {
      this.getPanelData(startTime, endTime);
    }
  }

  /** 点击节点 */
  handleNodeClick(node: INodeModel) {
    this.nodeTipsMap.set(node.data.id, node.node_tips);
    this.selectedServiceName = node.data.id;
    this.selectedEndpoint = '';
    this.selectedIcon = nodeIconClass[node.data.category];
    if (!this.expanded.includes('overview')) {
      this.handleExpand('overview');
    }
  }

  /** 资源拓扑 */
  handleResourceDrilling(node: INodeModel) {
    this.nodeTipsMap.set(node.data.id, node.node_tips);
    this.selectedServiceName = node.data.id;
    this.selectedEndpoint = '';
    this.selectedIcon = nodeIconClass[node.data.category];
    if (!this.expanded.includes('topo')) {
      this.handleExpand('topo');
    }
  }

  /** 服务概览 */
  handleServiceDetail(node: INodeModel) {
    this.nodeTipsMap.set(node.data.id, node.node_tips);
    this.selectedServiceName = node.data.id;
    this.selectedIcon = nodeIconClass[node.data.category];
    this.selectedEndpoint = '';
    if (!this.expanded.includes('overview')) {
      this.handleExpand('overview');
    }
  }

  /** 下钻接口节点点击 */
  handleDrillingNodeClick(node: INodeModel, drillingItem) {
    this.nodeTipsMap.set(node.data.id, node.node_tips);
    this.nodeTipsMap.set(`${node.data.id}___${drillingItem.name}`, drillingItem?.endpoint_tips || []);
    this.selectedServiceName = node.data.id;
    this.selectedEndpoint = drillingItem.name;
    this.selectedIcon = 'icon-fx';
    if (this.expanded.includes('topo')) {
      this.handleExpand('topo');
    }
    if (!this.expanded.includes('overview')) {
      this.handleExpand('overview');
    }
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
  handleSliceTimeRangeChange(timeRange: [number, number], refreshLayout = false) {
    this.sliceTimeRange = JSON.parse(JSON.stringify(timeRange));
    this.handleCustomRouteQueryChange({
      sliceStartTime: this.sliceTimeRange[0],
      sliceEndTime: this.sliceTimeRange[1],
    });
    this.refreshTopoLayout = refreshLayout;
    this.getTopoData();
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
                  style={{ fontSize: item.size }}
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
              disabled={this.showType === 'table'}
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
              enableZoom={true}
              getData={this.getAlarmBarData}
              groupId={this.dashboardId}
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
            <bk-input
              class='ml-24'
              behavior='simplicity'
              placeholder={'搜索服务'}
              right-icon='bk-icon icon-search'
              value={this.filterCondition.searchValue}
              clearable
              show-clear-only-hove
              onBlur={this.handleSearch}
              onChange={this.handleSearch}
              onClear={this.handleSearch}
              onEnter={this.handleSearch}
            />
          </div>
          <div class='header-tool-wrap'>
            <div
              style={{
                display: this.showType === 'topo' ? 'flex' : 'none',
              }}
              class='tool-btns'
            >
              {this.expandList.map(item => (
                <div
                  key={item.id}
                  class={[
                    'tool-btn',
                    { disabled: item.id === 'topo' ? this.resourceDisable : this.overviewDisable },
                    { active: this.expanded.includes(item.id) },
                  ]}
                  v-bk-tooltips={{
                    content: item.tips,
                  }}
                  onClick={() =>
                    !(item.id === 'topo' ? this.resourceDisable : this.overviewDisable) && this.handleExpand(item.id)
                  }
                >
                  <span class={`icon-monitor ${item.icon}`} />
                </div>
              ))}
            </div>
          </div>
        </div>
        <ApmRelationGraphContent
          ref='content-wrap'
          style={{
            display: this.showType === 'topo' ? 'block' : 'none',
          }}
          expanded={this.expanded}
        >
          <ApmRelationTopo
            activeNode={this.selectedServiceName}
            appName={this.appName}
            data={this.graphData}
            dataType={this.dataType}
            edgeType={this.edgeDataType}
            expandMenuList={this.expanded}
            filterCondition={this.filterCondition}
            refreshTopoLayout={this.refreshTopoLayout}
            showType={this.showType}
            onDrillingNodeClick={this.handleDrillingNodeClick}
            onEdgeTypeChange={this.handleEdgeTypeChange}
            onNodeClick={this.handleNodeClick}
            onResourceDrilling={this.handleResourceDrilling}
            onServiceDetail={this.handleServiceDetail}
          >
            <div slot='timeTips'>{this.timeTips}</div>
          </ApmRelationTopo>
          {this.loading.topo && (
            <div class={{ 'apm-topo-empty-chart': true, 'all-loading': this.refreshTopoLayout }}>
              {this.refreshTopoLayout ? <div v-bkloading={{ isLoading: true }} /> : <bk-spin spinning />}
            </div>
          )}

          <template slot='side1'>
            <div class='header-wrap'>
              <div class='title'>{this.$t('资源拓扑')}</div>
              {/* <div
                class='expand-btn'
                onClick={() => this.handleExpand('topo')}
              >
                <span class='icon-monitor icon-zhankai' />
              </div> */}
            </div>
            <div class='content-wrap'>
              <resource-topo serviceName={this.expanded.includes('topo') ? this.selectedServiceName : ''} />
            </div>
          </template>
          <template slot='side2'>
            <div class='header-wrap'>
              <div class='title'>{this.selectedEndpoint ? this.$t('接口概览') : this.$t('服务概览')}</div>
              {/* <div
                class='expand-btn'
                onClick={() => this.handleExpand('overview')}
              >
                <span class='icon-monitor icon-zhankai' />
              </div> */}
            </div>
            <div class={'content-wrap'}>
              <ServiceOverview
                appName={this.appName}
                dashboardId={this.dashboardId}
                data={this.serviceOverviewData}
                detailIcon={this.selectedIcon}
                endpoint={this.selectedEndpoint}
                nodeTipsMap={this.nodeTipsMap}
                serviceName={this.selectedServiceName}
                show={this.expanded.includes('overview')}
                sliceTimeRange={this.sliceTimeRange}
                timeRange={this.timeRange}
                onSliceTimeRangeChange={this.handleSliceTimeRangeChange}
              />
            </div>
          </template>
        </ApmRelationGraphContent>
        <div
          style={{
            display: this.showType !== 'topo' ? 'block' : 'none',
          }}
          class='apm-relation-graph-table-wrap'
        >
          <div class='table-wrap'>
            <keep-alive>
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
            </keep-alive>
          </div>
        </div>
      </div>
    );
  }
}
