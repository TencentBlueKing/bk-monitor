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
// import type { PanelModel } from '../../typings';
import { dataTypeBarQuery } from 'monitor-api/modules/apm_topo';
import { topoView } from 'monitor-api/modules/apm_topo';
import { Debounce } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';

import { CommonSimpleChart } from '../common-simple-chart';
import StatusTab from '../table-chart/status-tab';
import ApmRelationGraphContent from './components/apm-relation-graph-content';
import ApmRelationTopo from './components/apm-relation-topo';
import BarAlarmChart from './components/bar-alarm-chart';
import ResourceTopo from './components/resource-topo/resource-topo';
import ServiceOverview from './components/service-overview';
import { alarmBarChartDataTransform, DATA_TYPE_LIST, EDataType, type EdgeDataType } from './components/utils';

import type { ITableColumn, ITablePagination } from 'monitor-pc/pages/monitor-k8s/typings/table';

import './apm-relation-graph.scss';

enum EColumn {
  avgTime = 'avg_time',
  callCount = 'call_count',
  callService = 'call_service',
  callType = 'call_type',
  errorRate = 'error_rate',
  operate = 'operate',
  serverName = 'service_name',
}

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

  /* 筛选列表 */
  filterList = [
    {
      id: 'all',
      name: '全部',
      icon: 'icon-gailan',
    },
    {
      id: 'http',
      name: '网页',
      icon: 'icon-wangye',
    },
    {
      id: 'rpc',
      name: '远程调用',
      icon: 'icon-yuanchengfuwu',
    },
    {
      id: 'db',
      name: '数据库',
      icon: 'icon-DB',
    },
    {
      id: 'messaging',
      name: '消息队列',
      icon: 'icon-xiaoxizhongjianjian',
    },
    {
      id: 'async_backend',
      name: '后台任务',
      icon: 'icon-renwu',
    },
    {
      id: 'other',
      name: '其他',
      icon: 'icon-zidingyi',
    },
  ];
  curFilter = 'all';
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
  expanded = ['topo', 'overview'];

  /* 表格数据 */
  tableColumns: ITableColumn[] = [];
  tableData = [];
  /** 分页数据 */
  pagination: ITablePagination = {
    current: 1,
    count: 2,
    limit: 10,
    showTotalCount: true,
  };

  searchValue = '';

  graphData = {
    nodes: [],
    edges: [],
  };

  /* 获取头部告警柱状条形图数据方法 */
  getAlarmBarData = null;

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
      search: this.searchValue,
    };
  }

  created() {
    this.tableColumns = [
      {
        type: 'link',
        id: EColumn.serverName,
        name: window.i18n.tc('服务名称'),
      },
      {
        type: 'scoped_slots',
        id: EColumn.callType,
        name: window.i18n.tc('调用类型'),
      },
      {
        type: 'string',
        id: EColumn.callService,
        name: window.i18n.tc('调用服务'),
      },
      {
        type: 'number',
        id: EColumn.callCount,
        name: window.i18n.tc('调用数'),
      },
      {
        type: 'scoped_slots',
        id: EColumn.errorRate,
        name: window.i18n.tc('错误率'),
      },
      {
        type: 'scoped_slots',
        id: EColumn.avgTime,
        name: window.i18n.tc('平均响应耗时'),
      },
      {
        type: 'scoped_slots',
        id: EColumn.operate,
        name: window.i18n.tc('操作'),
      },
    ];
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
        setData(alarmBarChartDataTransform(this.dataType, data.series));
      };
    } catch (e) {
      console.error(e);
    }
    this.handleLoadingChange(false);
  }

  async getTopoData(params?) {
    let res = params;
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
    this.graphData = await topoView({
      ...res,
      edge_data_type: this.edgeDataType,
      export_type: this.showType,
    }).catch(() => ({ edges: [], nodes: [] }));
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

  handleFilterChange(id) {
    this.curFilter = id;
  }

  handleShowTypeChange(item) {
    this.showType = item.id;
  }

  handleDataTypeChange() {
    this.getPanelData();
  }

  dataZoom(startTime: string, endTime: string) {
    if (this.enableSelectionRestoreAll) {
      this.handleChartDataZoom([startTime, endTime]);
    } else {
      this.getPanelData(startTime, endTime);
    }
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
              getData={this.getAlarmBarData}
              itemHeight={16}
              onDataZoom={this.dataZoom as any}
            />
          </div>
          <div class='header-search-wrap'>
            <StatusTab
              class='ml-24'
              needAll={false}
              needExpand={true}
              statusList={this.filterList}
              value={this.curFilter}
              onChange={this.handleFilterChange}
            />
            <bk-checkbox class='ml-24'>无数据节点</bk-checkbox>
            <bk-input
              class='ml-24'
              v-model={this.searchValue}
              behavior='simplicity'
              placeholder={'搜索服务、接口'}
              right-icon='bk-icon icon-search'
              clearable
            />
          </div>
          <div class='header-tool-wrap'>
            <div class='tool-btns'>
              {this.expandList.map(item => (
                <div
                  key={item.id}
                  class={['tool-btn', { active: this.expanded.includes(item.id) }]}
                  onClick={() => this.handleExpand(item.id)}
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
            <ApmRelationTopo
              activeNode={['node1', 'node2']}
              data={this.graphData}
              edgeType={this.edgeDataType}
              scene='request'
              onEdgeTypeChange={this.handleEdgeTypeChange}
            />
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
                  <div class='title'>服务概览</div>
                  <div
                    class='expand-btn'
                    onClick={() => this.handleExpand('overview')}
                  >
                    <span class='icon-monitor icon-zhankai' />
                  </div>
                </div>
                <div class='content-wrap'>
                  <ServiceOverview data={{}} />
                </div>
              </div>
            </div>
          </ApmRelationGraphContent>
        ) : (
          <div class='apm-relation-graph-table-wrap'>
            <div class='table-wrap'>
              <CommonTable
                checkable={false}
                columns={this.tableColumns}
                data={this.tableData}
                pagination={this.pagination}
                paginationType={'simple'}
              />
            </div>
          </div>
        )}
      </div>
    );
  }
}
