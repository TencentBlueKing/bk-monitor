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
import { Component, Mixins } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';
import axios from 'axios';

import { getLabel } from '../../../monitor-api/modules/commons';
import { getObservationSceneList, getObservationSceneStatusList } from '../../../monitor-api/modules/scene_view';
import { Debounce } from '../../../monitor-common/utils/utils';
import introduce from '../../common/introduce';
import EmptyStatus from '../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../components/empty-status/types';
import GuidePage from '../../components/guide-page/guide-page';
import authorityMixinCreate from '../../mixins/authorityMixin';
import CommonStatus, { CommonStatusType } from '../monitor-k8s/components/common-status/common-status';
import CommonTable from '../monitor-k8s/components/common-table';
import PageTitle from '../monitor-k8s/components/page-title';
import { ITableColumn, ITablePagination, TableRow } from '../monitor-k8s/typings';

import * as authMap from './authority-map';

import './custom-scenes.scss';

enum ESceneType {
  plugin = 'plugin',
  customMetric = 'custom_metric',
  customEvent = 'custom_event'
}

const STATUS_TYPE = {
  NODATA: window.i18n.t('无数据'),
  SUCCESS: window.i18n.t('正常')
};

const addTypes: { id: ESceneType; name: string | any }[] = [
  { id: ESceneType.plugin, name: window.i18n.t('插件采集') },
  { id: ESceneType.customMetric, name: window.i18n.t('自定义指标') },
  { id: ESceneType.customEvent, name: window.i18n.t('自定义事件') }
];

interface ITableItem {
  id: string;
  name: string;
  sub_name: string;
  scene_type: ESceneType;
  plugin_type?: string;
  scenario: string;
  collect_config_count: number;
  strategy_count: number;
  scene_view_id: string;
  status: CommonStatusType;
  metric_id?: string;
}

@Component
class CustomScenes extends Mixins(authorityMixinCreate(authMap)) {
  /* 搜索 */
  keyword = '';
  /* 表格数据 */
  tableData: { columns: ITableColumn[]; allData: ITableItem[]; data: TableRow[]; pagination: ITablePagination } = {
    columns: [
      { id: 'nameColumn', name: window.i18n.t('名称') as string, type: 'scoped_slots' },
      { id: 'sceneType', name: window.i18n.t('类型') as string, type: 'string' },
      { id: 'scenarioName', name: window.i18n.t('监控对象') as string, type: 'string' },
      { id: 'statusColumn', name: window.i18n.t('数据状态') as string, type: 'scoped_slots' },
      {
        id: 'strategyColumn',
        name: window.i18n.t('策略项') as string,
        width: 90,
        type: 'scoped_slots',
        props: { maxWidth: 68 }
      },
      {
        id: 'collectorColumn',
        name: window.i18n.t('已启用采集项') as string,
        width: 155,
        type: 'scoped_slots',
        props: { maxWidth: 68 }
      },
      { id: 'operate', name: window.i18n.t('操作') as string, type: 'scoped_slots', props: { maxWidth: 100 } }
    ],
    data: [],
    /* 此数据会根据搜索变化 */
    allData: [],
    pagination: {
      count: 0,
      current: 1,
      limit: 10
    }
  };
  /* 所有数据，此数据不会变化 */
  allData: ITableItem[] = [];
  /* scenario */
  scenarioLabels = {};
  /* loading */
  loading = false;
  authorityMap = { ...authMap };
  emptyStatusType: EmptyStatusType = 'empty';
  /* status loading  */
  statusLoading = false;

  cancelTokenSource = null;
  // 是否显示引导页
  get showGuidePage() {
    return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
  }
  async activated() {
    if (this.showGuidePage) return;
    this.loading = true;
    if (!Object.keys(this.scenarioLabels).length) {
      const scenarioLists = await getLabel().catch(() => []);
      scenarioLists.forEach(item => {
        item.children.forEach(child => {
          this.scenarioLabels[child.id] = `${item.name}-${child.name}`;
        });
      });
    }
    this.handleChangeTableData(true);
  }

  /**
   *
   * @param isInit 是否初始化
   * @description 获取表格数据
   */
  async handleChangeTableData(isInit = false) {
    if (isInit) {
      this.loading = true;
      this.tableData.pagination.current = 1;
      const res = await getObservationSceneList().catch(() => {
        this.emptyStatusType = '500';
        return [];
      });
      this.tableData.allData = res;
      this.allData = res;
      this.loading = false;
    }
    if (this.keyword) {
      this.tableData.allData = this.allData.filter(
        item => String(item.name).indexOf(this.keyword) > -1 || String(item.sub_name).indexOf(this.keyword) > -1
      );
    }
    this.tableData.pagination.count = this.tableData.allData.length;
    this.getTableData();
  }

  /* 搜索 */
  @Debounce(300)
  handleSearchChange() {
    this.emptyStatusType = this.keyword ? 'search-empty' : 'empty';
    this.tableData.pagination.current = 1;
    if (this.keyword) {
      this.tableData.allData = this.allData.filter(
        item => String(item.name).indexOf(this.keyword) > -1 || String(item.sub_name).indexOf(this.keyword) > -1
      );
    } else {
      this.tableData.allData = this.allData.map(item => item);
    }
    this.tableData.pagination.count = this.tableData.allData.length;
    this.getTableData();
  }

  getTableData() {
    const { current, limit } = this.tableData.pagination;
    this.tableData.data = this.tableData.allData.slice((current - 1) * limit, current * limit).map(item => ({
      ...item,
      nameColumn: { slotId: 'name' },
      statusColumn: { slotId: 'status' },
      strategyColumn: { slotId: 'strategy' },
      collectorColumn: { slotId: 'collector' },
      operate: { slotId: 'operate' },
      status: item.status || null,
      sceneType: addTypes.find(t => t.id === item.scene_type)?.name || '--',
      scenarioName: this.scenarioLabels?.[item.scenario] || '--'
    }));
    const sceneViewIds = this.tableData.data.map(item => item.scene_view_id);
    this.cancelTokenSource?.cancel?.();
    this.setAsyncStatusData(sceneViewIds);
  }

  /* 异步加载 */
  setAsyncStatusData(sceneViewIds = []) {
    this.statusLoading = true;
    this.cancelTokenSource = axios.CancelToken.source();
    getObservationSceneStatusList(
      { scene_view_ids: sceneViewIds },
      {
        cancelToken: this.cancelTokenSource.token
      }
    )
      .then(res => {
        this.statusLoading = false;
        this.tableData.data.forEach(item => {
          if (res[item.scene_view_id as string]?.status) {
            item.status = res[item.scene_view_id as string].status;
          }
        });
      })
      .catch(error => {
        if (!axios.isCancel(error)) {
          this.statusLoading = false;
        }
      });
  }

  /* 点击新建 */
  handleAdd(id: ESceneType) {
    if (id === ESceneType.plugin) {
      this.$router.push({ name: 'collect-config-add' });
    } else if (id === ESceneType.customMetric) {
      this.$router.push({ name: 'custom-set-timeseries' });
    } else if (id === ESceneType.customEvent) {
      this.$router.push({ name: 'custom-set-event' });
    }
  }

  /* 分页 */
  handlePageChange(page: number) {
    this.tableData.pagination.current = page;
    this.handleChangeTableData();
  }
  /* 分页 */
  handleLimitChange(limit: number) {
    this.tableData.pagination.current = 1;
    this.tableData.pagination.limit = limit;
    this.handleChangeTableData();
  }

  /* 新增（表格内） */
  handleAddItem(row: ITableItem) {
    const type = row.scene_type;
    if (type === ESceneType.plugin) {
      const pluginTypes = ['snmp_trap', 'log', 'process'];
      const isNotPluginId = pluginTypes.includes(String(row.plugin_type).toLowerCase());
      this.$router.push({
        name: 'collect-config-add',
        params: {
          objectId: row.scenario,
          pluginType: row.plugin_type,
          pluginId: isNotPluginId ? undefined : row.id
        }
      });
    } else if (type === ESceneType.customMetric) {
      this.$router.push({ name: 'custom-set-timeseries' });
    } else if (type === ESceneType.customEvent) {
      this.$router.push({ name: 'custom-set-event' });
    }
  }

  /* 跳转到视图页面 */
  handleToView(row: ITableItem) {
    const auth = this.getAuthority(row);
    if (!auth.authority) {
      this.handleShowAuthorityDetail(auth.authorityDetail);
      return;
    }
    this.$router.push({
      name: 'custom-scenes-view',
      params: {
        id: row.scene_view_id
      },
      query: {
        name: row.name,
        customQuery: JSON.stringify({
          sceneType: row.scene_type,
          sceneId: row.id,
          pluginType: row.plugin_type || ''
        })
      }
    });
  }
  /* 跳转到策略列表 */
  handleToStrategy(row: ITableItem) {
    const pluginTypes = ['snmp_trap', 'log'];
    let pluginParams = {};
    if (row.metric_id && pluginTypes.includes(String(row?.plugin_type || '').toLowerCase())) {
      pluginParams = { metricId: row.metric_id };
    } else {
      pluginParams = { pluginId: row.id };
    }
    const params = {
      [ESceneType.plugin]: pluginParams,
      [ESceneType.customMetric]: { timeSeriesGroupId: row.id },
      [ESceneType.customEvent]: { bkEventGroupId: row.id }
    };
    this.$router.push({
      name: 'strategy-config',
      params: {
        ...params[row.scene_type]
      }
    });
  }
  /* 采集项跳转 */
  handleToCollect(row: ITableItem) {
    const pluginTypes = ['snmp_trap', 'log'];
    const type = row.scene_type;
    if (type === ESceneType.plugin) {
      if (pluginTypes.includes(String(row?.plugin_type || '').toLowerCase())) {
        this.$router.push({
          name: 'collect-config',
          query: {
            id: row.id
          }
        });
      } else {
        this.$router.push({
          name: 'collect-config',
          params: {
            pluginId: row.id
          }
        });
      }
    } else {
      const types = {
        [ESceneType.customMetric]: {
          name: 'custom-detail-timeseries',
          type: 'customTimeSeries'
        },
        [ESceneType.customEvent]: {
          name: 'custom-detail-event',
          type: 'customEvent'
        }
      };
      this.$router.push({
        name: types[type].name,
        params: {
          id: row.id,
          type: types[type].type
        }
      });
    }
  }

  /* 权限（能否进入视图页） */
  getAuthority(row: ITableItem) {
    const type = row.scene_type;
    const authMap = {
      [ESceneType.plugin]: {
        authority: this.authority.VIEW_COLLECTION,
        authorityDetail: this.authorityMap.VIEW_COLLECTION
      },
      [ESceneType.customMetric]: {
        authority: this.authority.VIEW_CUSTOM_EVENT,
        authorityDetail: this.authorityMap.VIEW_CUSTOM_EVENT
      },
      [ESceneType.customEvent]: {
        authority: this.authority.VIEW_CUSTOM_METRIC,
        authorityDetail: this.authorityMap.VIEW_CUSTOM_METRIC
      }
    };
    return authMap[type];
  }

  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.keyword = '';
      this.handleSearchChange();
      return;
    }
    if (type === 'refresh') {
      this.handleChangeTableData(true);
      return;
    }
  }

  render() {
    if (this.showGuidePage) return <GuidePage guideData={introduce.data['custom-scenes'].introduce} />;
    return (
      <div
        class='custom-scenes-page'
        v-bkloading={{ isLoading: this.loading }}
      >
        <PageTitle
          tabList={[]}
          activeTab={''}
          showSearch={false}
          showFilter={false}
          showInfo={false}
          showSelectPanel={false}
        >
          <span slot='title'>{this.$t('自定义场景')}</span>
        </PageTitle>
        <div class='custom-scenes-page-wrapper'>
          <div class='table-wrapper'>
            <div class='wrapper-header'>
              <bk-dropdown-menu positionFxed>
                <bk-button
                  slot='dropdown-trigger'
                  icon='plus'
                  theme='primary'
                >
                  {this.$t('新建')}
                </bk-button>
                <ul
                  class='header-select-list'
                  slot='dropdown-content'
                >
                  {addTypes.map(item => (
                    <li
                      onClick={() => this.handleAdd(item.id)}
                      class='list-item'
                    >
                      {item.name}
                    </li>
                  ))}
                </ul>
              </bk-dropdown-menu>
              <bk-input
                class='search-wrapper-input'
                placeholder={window.i18n.t('搜索')}
                v-model={this.keyword}
                right-icon='bk-icon icon-search'
                onChange={this.handleSearchChange}
                on-enter={this.handleSearchChange}
                on-right-icon-click={this.handleSearchChange}
              />
            </div>
            <CommonTable
              columns={this.tableData.columns}
              data={this.tableData.data}
              pagination={this.tableData.pagination}
              checkable={false}
              scopedSlots={{
                name: (row: ITableItem) => (
                  <div class='column-name'>
                    <div
                      class='title'
                      v-authority={{ active: !this.getAuthority(row).authority }}
                      onClick={() => this.handleToView(row)}
                    >
                      {row.name}
                    </div>
                    <div class='subtitle'>{row.sub_name}</div>
                  </div>
                ),
                status: (row: ITableItem) =>
                  this.statusLoading ? (
                    <div class='spinner'></div>
                  ) : (
                    <div class='column-status'>
                      {row.status ? (
                        <CommonStatus
                          type={row.status}
                          text={STATUS_TYPE[row.status]}
                        ></CommonStatus>
                      ) : (
                        '--'
                      )}
                    </div>
                  ),
                strategy: (row: ITableItem) => (
                  <div class='column-count'>
                    {row.strategy_count > 0 ? (
                      <bk-button
                        text
                        onClick={() => this.handleToStrategy(row)}
                      >
                        {row.strategy_count}
                      </bk-button>
                    ) : (
                      '--'
                    )}
                  </div>
                ),
                collector: (row: ITableItem) => (
                  <div class='column-count'>
                    {row.collect_config_count > 0 ? (
                      <bk-button
                        text
                        onClick={() => this.handleToCollect(row)}
                      >
                        {row.collect_config_count}
                      </bk-button>
                    ) : (
                      '--'
                    )}
                  </div>
                ),
                operate: (row: ITableItem) => [
                  row.scene_type === ESceneType.plugin ? (
                    <bk-button
                      style={{ marginLeft: '10px' }}
                      text
                      onClick={() => this.handleAddItem(row)}
                    >
                      {window.i18n.t('新建采集')}
                    </bk-button>
                  ) : (
                    ''
                  )
                ]
              }}
              onPageChange={this.handlePageChange}
              onLimitChange={this.handleLimitChange}
            >
              <EmptyStatus
                slot='empty'
                type={this.emptyStatusType}
                onOperation={this.handleOperation}
              />
            </CommonTable>
          </div>
        </div>
      </div>
    );
  }
}
export default tsx.ofType<{}>().convert(CustomScenes);
