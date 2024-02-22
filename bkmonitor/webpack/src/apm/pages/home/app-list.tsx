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
// import * as tsx from 'vue-tsx-support';
// import { Component, Mixins, Provide } from 'vue-tsx-support';
import { Component, Provide, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { CancelToken } from '../../../monitor-api/index';
import {
  deleteApplication,
  listApplication,
  listApplicationAsync,
  metaConfigInfo,
  start,
  stop
} from '../../../monitor-api/modules/apm_meta';
import { Debounce } from '../../../monitor-common/utils/utils';
import EmptyStatus from '../../../monitor-pc/components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../../monitor-pc/components/empty-status/types';
import GuidePage from '../../../monitor-pc/components/guide-page/guide-page';
import type { INodeType, TargetObjectType } from '../../../monitor-pc/components/monitor-ip-selector/typing';
import type { TimeRangeType } from '../../../monitor-pc/components/time-range/time-range';
import { handleTransformToTimestamp } from '../../../monitor-pc/components/time-range/utils';
// import DashboardTools from '../../../monitor-pc/pages/monitor-k8s/components/dashboard-tools';
import AlarmTools from '../../../monitor-pc/pages/monitor-k8s/components/alarm-tools';
import CommonTable, { ICommonTableProps } from '../../../monitor-pc/pages/monitor-k8s/components/common-table';
import { IFilterDict, INavItem } from '../../../monitor-pc/pages/monitor-k8s/typings';
import OperateOptions, { IOperateOption } from '../../../monitor-pc/pages/uptime-check/components/operate-options';
import introduceData from '../../../monitor-pc/router/space';
import { PanelModel } from '../../../monitor-ui/chart-plugins/typings';
import { ITableDataItem } from '../../../monitor-ui/chart-plugins/typings/table-chart';
import ListMenu, { IMenuItem } from '../../components/list-menu/list-menu';
import authorityStore from '../../store/modules/authority';

import AppAddForm from './app-add-form';
import { IAppSelectOptItem } from './app-select';
import * as authorityMap from './authority-map';
import NavBar from './nav-bar';

import './app-list.scss';

export interface ICreateAppFormData {
  name: string;
  enName: string;
  desc: string;
  pluginId: string;
  enableProfiling: boolean;
  enableTracing: boolean;
  plugin_config?: {
    target_node_type: INodeType;
    target_object_type: TargetObjectType;
    target_nodes: any[];
    data_encoding: string;
    paths: string[];
  };
}

const commonTableProps: ICommonTableProps = {
  checkable: false,
  defaultSize: 'medium',
  hasColnumSetting: true,
  paginationType: 'normal',
  columns: []
};
export interface IGuideLink {
  access_url: string;
  best_practice: string;
  metric_description: string;
}
@Component
export default class AppList extends tsc<{}> {
  @Ref() addForm: any;

  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;

  loading = false;

  /** 显示添加表单 */
  showAddDialog = false;
  /** 选中的插件id */
  pluginId = '';
  /** 显示引导页 */
  showGuidePage = false;
  /** 排序字段 */
  sortKey = '';
  /** 时间范围 */
  timeRange: TimeRangeType = ['now-1h', 'now'];
  /** 表格列数据项过滤 */
  filterDict: IFilterDict = {};

  routeList: INavItem[] = [
    {
      id: '',
      name: 'APM'
    }
  ];
  opreateOptions: IOperateOption[] = [
    // {
    //   id: '',
    //   name: window.i18n.t('关联场景'),
    //   authority: true
    // },
    {
      id: 'storageState',
      name: window.i18n.t('存储状态'),
      authority: true
    },
    {
      id: 'dataStatus',
      name: window.i18n.t('数据状态'),
      authority: true
    },
    // {
    //   id: 'indicatorDimension',
    //   name: window.i18n.t('指标维度'),
    //   authority: true
    // },
    {
      id: 'accessService',
      name: window.i18n.t('接入服务'),
      authority: true
    },
    {
      id: 'noDataAlarm',
      name: window.i18n.t('新增无数据告警'),
      authority: true
    },
    {
      id: 'delete',
      name: window.i18n.t('删除'),
      authority: true
    }
  ];
  /** 通用表格数据 */
  tableData = {
    ...commonTableProps,
    pagination: {
      count: 20,
      current: 1,
      limit: 10,
      showTotalCount: true
    },
    loading: false,
    data: [],
    storeKey: 'apmAppList'
  };
  /** 搜索关键词 */
  searchKeyword = '';

  /** 是否显示帮助文档弹窗 */
  showGuideDialog = false;

  /** 插件列表 */
  pluginsList: IAppSelectOptItem[] = [];
  /** 快速链接 */
  guideUrl: IGuideLink = null;
  // menu list
  menuList: IMenuItem[] = [
    {
      id: 'help-docs',
      name: window.i18n.tc('帮助文档')
    }
  ];
  emptyStatusType: EmptyStatusType = 'empty';

  /** 异步查询字段取消请求方法 */
  queryFieldCancelFn: Record<string, () => {}> = {};

  get apmIntroduceData() {
    const apmData = introduceData['apm-home'];
    apmData.is_no_source = false;
    apmData.data.buttons[0].url = window.__POWERED_BY_BK_WEWEB__ ? '#/apm/application/add' : '#/application/add';
    return apmData;
  }

  get alarmToolsPanel() {
    const data = {
      title: this.$t('应用列表'),
      type: 'dict',
      targets: [
        {
          datasource: 'apm',
          dataType: 'dict',
          api: 'scene_view.getStrategyAndEventCount',
          data: {
            scene_id: 'apm'
          }
        }
      ]
    };
    return new PanelModel(data as any);
  }

  created() {
    const { query } = this.$route || {};
    if (query?.queryString) {
      this.searchKeyword = query.queryString as string;
    }
    this.initData();
  }

  /** 初始化页面数据 */
  initData() {
    this.getTableData();
    this.getPluginList();
  }

  async getPluginList() {
    const {
      plugins = [],
      // eslint-disable-next-line @typescript-eslint/naming-convention
      setup: { guide_url = {} }
    } = await metaConfigInfo().catch(() => ({}));
    this.pluginsList = plugins.map(
      (item): IAppSelectOptItem => ({
        id: item.id,
        name: item.name,
        icon: item.icon || '',
        desc: item.short_description || ''
      })
    );
    this.guideUrl = guide_url as IGuideLink;
  }
  /** 获取表格数据 */
  async getTableData() {
    this.tableData.loading = true;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const params = {
      start_time: startTime,
      end_time: endTime,
      keyword: this.searchKeyword,
      sort: this.sortKey,
      filter_dict: this.filterDict,
      page: this.tableData.pagination.current,
      page_size: this.tableData.pagination.limit
    };
    const listData = await listApplication(params).catch(() => {
      this.emptyStatusType = '500';
      return [];
    });
    this.emptyStatusType = this.searchKeyword ? 'search-empty' : 'empty';
    this.tableData.pagination.count = listData?.total || 0;
    this.tableData.loading = false;
    this.tableData.data = listData?.data || [];
    this.tableData.columns = [
      ...(listData?.columns || []),
      ...[
        {
          id: 'enable',
          name: window.i18n.tc('启/停'),
          type: 'scoped_slots',
          showOverflowTooltip: false,
          checked: true
        },
        {
          id: 'opreate',
          name: window.i18n.tc('操作'),
          type: 'scoped_slots',
          showOverflowTooltip: false,
          width: 100,
          checked: true,
          disabled: true
        }
      ]
    ];
    this.showGuidePage = !this.tableData.pagination.count && !this.searchKeyword;

    const asyncFields = this.tableData.columns.filter(col => col.asyncable).map(val => val.id);
    if (asyncFields.length) {
      this.getAsyncData(asyncFields);
    }

    // 路由同步查询关键字
    const routerParams = {
      name: this.$route.name,
      query: {
        ...this.$route.query,
        queryString: this.searchKeyword
      }
    };
    this.$router.replace(routerParams).catch(() => {});
  }

  /** 异步获取部分字段值 */
  async getAsyncData(fields: string[]) {
    this.$nextTick();
    fields.forEach(item => {
      const params = {
        column: item,
        application_ids: this.tableData.data.map(val => val.application_id)
      };
      listApplicationAsync(params, {
        cancelToken: new CancelToken(c => (this.queryFieldCancelFn[item] = c))
      })
        .then(res => {
          const dataMap = res.reduce((pre, cur) => {
            // eslint-disable-next-line no-param-reassign
            if (!pre[cur.application_id]) pre[cur.application_id] = cur[item];
            return pre;
          }, {});
          const newData = this.tableData.data.map(data => ({ ...data, [item]: dataMap[data.application_id] }));
          this.tableData.data = [...newData];
        })
        .finally(() => {
          this.tableData.columns = this.tableData.columns.map(col => ({
            ...col,
            asyncable: col.id === item ? false : col.asyncable
          }));
        });
    });
  }

  /** 展示添加弹窗 */
  handleAddApp() {
    // this.pluginId = opt.id;
    // this.showAddDialog = true;
    this.$router.push({
      name: 'application-add'
    });
  }

  /** 时间范围变更 */
  handleTimeRangeChange(timeRange: TimeRangeType) {
    this.timeRange = timeRange;
    this.getTableData();
  }
  /**
   * @desc 配置应用
   * @param { Stirng } id
   */
  handleConfig(id, row) {
    // 存储状态、数据状态、指标维度、新增无数据告警 分别跳到配置页 query: active
    const toConfigKeys = ['storageState', 'dataStatus', 'indicatorDimension', 'noDataAlarm'];
    // 接入服务 /service-add/opentelemetry/apm_test_have_data
    const toAccessService = ['accessService'];
    if (toConfigKeys.includes(id)) {
      this.handleCancelAsyncGetFields();
      this.$router.push({
        name: 'application-config',
        params: {
          id: row.application_id
        },
        query: {
          active: id === 'noDataAlarm' ? 'dataStatus' : id
        }
      });
    } else if (toAccessService.includes(id)) {
      this.handleCancelAsyncGetFields();
      this.$router.push({
        name: 'service-add',
        params: {
          appName: row.app_name
        }
      });
    } else if (id === 'config') {
      this.handleCancelAsyncGetFields();
      this.$router.push({
        name: 'application-config',
        params: {
          id: row.application_id
        }
      });
    } else if (id === 'delete') {
      this.$bkInfo({
        type: 'warning',
        title: this.$t('确认删除该应用？'),
        maskClose: true,
        escClose: true,
        confirmFn: () => {
          deleteApplication({ app_name: row.app_name }).then(() => {
            this.$bkMessage({ theme: 'success', message: this.$t('删除成功') });
            this.getTableData();
          });
        }
      });
    }
  }
  /** 翻页 */
  handlePageChange(page: number) {
    this.tableData.pagination.current = page;
    this.getTableData();
  }
  /** 切换单页数 */
  handlePageLimitChange(limit: number) {
    this.tableData.pagination.limit = limit;
    this.tableData.pagination.current = 1;
    this.getTableData();
  }

  /** 列表排序 */
  handleSortChange({ prop, order }) {
    switch (order) {
      case 'ascending':
        this.sortKey = prop;
        break;
      case 'descending':
        this.sortKey = `-${prop}`;
        break;
      default:
        this.sortKey = undefined;
    }
    this.getTableData();
  }

  /** 表格数据项过滤 */
  handleFilterChange(filters: IFilterDict) {
    this.filterDict = filters;
    this.tableData.pagination.current = 1;
    this.getTableData();
  }

  /** 列表搜索 */
  @Debounce(300)
  handleSearch() {
    this.tableData.pagination.current = 1;
    this.getTableData();
  }
  // eslint-disable-next-line @typescript-eslint/no-dupe-class-members
  handleShowAuthorityDetail(actionIds: string | string[]) {
    authorityStore.getAuthorityDetail(actionIds);
  }

  /** 开关前置校验 */
  handleEnablePreCheck(row: ITableDataItem, hasPermission: boolean) {
    if (!hasPermission) {
      this.handleShowAuthorityDetail(authorityMap.MANAGE_AUTH);
      return Promise.reject();
    }
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { is_enabled, application_id } = row;
    return new Promise((resolve, reject) => {
      this.$bkInfo({
        title: this.$t(is_enabled ? '你确认要停用？' : '你确认要启用？'),
        confirmLoading: true,
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        confirmFn: async () => {
          const api = is_enabled ? stop : start;
          const isPass = await api({ application_id })
            .then(() => true)
            .catch(() => false);
          if (isPass) {
            this.getTableData();
            resolve(true);
          } else {
            reject();
          }
        },
        cancelFn: () => {
          reject();
        }
      });
    });
  }

  handleGetEnableColumn(row: ITableDataItem) {
    const hasPermission = row?.permission[authorityMap.VIEW_AUTH] ?? true;
    return (
      <bk-switcher
        v-authority={{ active: !hasPermission }}
        v-model={row.is_enabled}
        theme='primary'
        size='small'
        pre-check={() => this.handleEnablePreCheck(row, hasPermission)}
      ></bk-switcher>
    );
  }
  handleGetOprateColumn(row: ITableDataItem) {
    const hasPermission = row?.permission[authorityMap.VIEW_AUTH] ?? true;
    return (
      <div>
        <OperateOptions
          options={{
            outside: [
              {
                id: 'config',
                name: window.i18n.tc('配置'),
                authorityDetail: authorityMap.VIEW_AUTH,
                authority: hasPermission
              }
            ],
            popover: this.opreateOptions.map(item => ({
              ...item,
              authority: hasPermission,
              authorityDetail: authorityMap.VIEW_AUTH
            }))
          }}
          onOptionClick={id => this.handleConfig(id, row)}
        ></OperateOptions>
      </div>
    );
  }

  /** 全屏操作 */
  handleFullscreenChange() {
    if (!document.fullscreenElement) {
      this.$el.requestFullscreen();
    } else if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  }

  /** 跳转服务概览 */
  linkToOverview(app_name) {
    this.handleCancelAsyncGetFields();
    this.$router.push({
      name: 'application',
      query: {
        'filter-app_name': app_name
      }
    });
  }

  /** 设置打开帮助文档 */
  handleSettingsMenuSelect(option) {
    if (option.id === 'help-docs') {
      this.showGuideDialog = true;
    }
  }

  /** 关闭弹窗 */
  handleCloseGuideDialog() {
    this.showGuideDialog = false;
  }

  handleOperation(val: EmptyStatusOperationType) {
    if (val === 'clear-filter') {
      this.searchKeyword = '';
      this.handleSearch();
    }

    switch (val) {
      case 'clear-filter':
        this.searchKeyword = '';
        break;
      case 'refresh':
        this.emptyStatusType = 'empty';
      default:
        break;
    }
  }

  handleCancelAsyncGetFields() {
    Object.keys(this.queryFieldCancelFn || {}).forEach(item => {
      this.queryFieldCancelFn[item]();
    });
  }

  render() {
    return (
      <div
        class='app-list-wrap'
        v-bkloading={{ isLoading: this.loading }}
      >
        {
          <NavBar routeList={this.routeList}>
            {!this.showGuidePage && (
              <div
                slot='handler'
                class='dashboard-tools-wrap'
              >
                <AlarmTools
                  class='alarm-tools'
                  panel={this.alarmToolsPanel}
                />
                {/* <AppSelect
                  list={this.pluginsList}
                  onSelected={this.handleAddApp}>
                  <bk-button size="small" theme="primary">
                    <span class="app-add-btn">
                      <i class="icon-monitor icon-mc-add app-add-icon"></i><span>{this.$t('新建应用')}</span>
                    </span>
                  </bk-button>
                </AppSelect> */}
                <bk-button
                  size='small'
                  theme='primary'
                  onClick={this.handleAddApp}
                >
                  <span class='app-add-btn'>
                    <i class='icon-monitor icon-mc-add app-add-icon'></i>
                    <span>{this.$t('新建应用')}</span>
                  </span>
                </bk-button>
                <ListMenu
                  list={this.menuList}
                  onMenuSelect={this.handleSettingsMenuSelect}
                >
                  <i class='icon-monitor icon-mc-more-tool' />
                </ListMenu>
              </div>
            )}
          </NavBar>
        }
        <div class='app-list-main'>
          {this.showGuidePage ? (
            <GuidePage
              guideId='apm-home'
              guideData={this.apmIntroduceData}
            />
          ) : (
            <div class='app-list-content'>
              <bk-input
                class='app-list-search'
                placeholder={this.$t('输入搜索或筛选')}
                v-model={this.searchKeyword}
                clearable
                onInput={this.handleSearch}
              ></bk-input>
              <CommonTable
                {...{ props: this.tableData }}
                onPageChange={this.handlePageChange}
                onLimitChange={this.handlePageLimitChange}
                onSortChange={this.handleSortChange}
                onFilterChange={this.handleFilterChange}
                scopedSlots={{
                  enable: this.handleGetEnableColumn,
                  opreate: this.handleGetOprateColumn,
                  app_alias: row => (
                    <div class='app-info'>
                      <span
                        class='app-alias-name'
                        v-authority={{ active: !authorityMap.VIEW_AUTH }}
                        onClick={() =>
                          authorityMap.VIEW_AUTH
                            ? this.linkToOverview(row.app_name)
                            : this.handleShowAuthorityDetail(authorityMap.VIEW_AUTH)
                        }
                      >
                        {row.app_alias?.value}
                      </span>
                      <span class='app-en-name'>{row.app_name}</span>
                    </div>
                  )
                }}
              >
                <EmptyStatus
                  type={this.emptyStatusType}
                  slot='empty'
                  onOperation={this.handleOperation}
                />
              </CommonTable>
            </div>
          )}
        </div>
        <AppAddForm
          pluginId={this.pluginId}
          v-model={this.showAddDialog}
        ></AppAddForm>
        <bk-dialog
          value={this.showGuideDialog}
          mask-close={true}
          ext-cls='guide-create-dialog'
          width={1360}
          show-footer={false}
          on-cancel={this.handleCloseGuideDialog}
        >
          <GuidePage
            marginless
            guideId='apm-home'
            guideData={this.apmIntroduceData}
          />
        </bk-dialog>
      </div>
    );
  }
}
