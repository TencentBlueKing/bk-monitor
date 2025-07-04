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
import { Component, Mixins, Provide, Ref } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import {
  customTimeSeriesList,
  deleteCustomEventGroup,
  deleteCustomTimeSeries,
  queryCustomEventGroup,
} from 'monitor-api/modules/custom_report';
import { checkAllowedByActionIds, getAuthorityDetail } from 'monitor-api/modules/iam';
import { commonPageSizeGet, commonPageSizeSet } from 'monitor-common/utils';
import { deepClone } from 'monitor-common/utils/utils';
// import LeftPanel from './left-panel.vue';
import { debounce } from 'throttle-debounce';

import EmptyStatus from '../../components/empty-status/empty-status';
import PageTips from '../../components/pageTips/pageTips.vue';
import TableSkeleton from '../../components/skeleton/table-skeleton';
import authorityMixinCreate from '../../mixins/authorityMixin';
import CommonTable, { type ICommonTableProps } from '../monitor-k8s/components/common-table';
import OperateOptions from '../uptime-check/components/operate-options';
import * as customAuth from './authority-map';

import type { EmptyStatusOperationType, EmptyStatusType } from '../../components/empty-status/types';
import type { ITableColumn } from '../monitor-k8s/typings';

import './custom-report.scss';

type pageType = 'custom-event' | 'custom-metric';
const CUSTOM_EVENT = 'custom-event';
const CUSTOM_METRIC = 'custom-metric';

const BK_EVENT_GROUP_ID = 'bk_event_group_id';
const TIME_SERIES_GROUP_ID = 'time_series_group_id';

const dataIdName = {
  [BK_EVENT_GROUP_ID]: 'bkEventGroupId',
  [TIME_SERIES_GROUP_ID]: 'timeSeriesGroupId',
};

const dataIdMap = {
  [CUSTOM_EVENT]: BK_EVENT_GROUP_ID,
  [CUSTOM_METRIC]: TIME_SERIES_GROUP_ID,
};

const detailRouteName = {
  [CUSTOM_EVENT]: 'custom-detail-event',
  [CUSTOM_METRIC]: 'custom-detail-timeseries',
};

const detailType = {
  [CUSTOM_EVENT]: 'customEvent',
  [CUSTOM_METRIC]: 'customTimeSeries',
};

const addPageName = {
  [CUSTOM_EVENT]: 'custom-set-event',
  [CUSTOM_METRIC]: 'custom-set-timeseries',
};

enum EFilterType {
  current = 'current',
  platform = 'platform',
}
const filterTypes = [
  {
    id: EFilterType.current,
    name: window.i18n.tc('当前空间'),
  },
  {
    id: EFilterType.platform,
    name: window.i18n.tc('平台数据'),
  },
];

// const panelList: { name: string, id: string, href: boolean }[] = [
//   {
//     name: 'API',
//     id: 'api',
//     href: true
//   },
//   {
//     name: 'Python',
//     id: 'python',
//     href: true
//   }
// ];

interface IEventItem {
  bk_biz_id?: number;
  bk_data_id?: number;
  bk_event_group_id?: number;
  time_series_group_id?: number;
  create_time?: string;
  create_user?: string;
  is_deleted?: boolean;
  is_enable?: boolean;
  name?: string;
  related_strategy_count?: number;
  scenario?: string;
  scenario_display?: string[];
  table_id: string;
  type: string;
  update_time: string;
  update_user: string;
  is_readonly?: boolean; // 是否只读
  is_platform?: boolean; // 是否为公共
  is_edit?: boolean; // 是否为编辑态
  oldName?: string; // 修改之前的名字
}

const commonTableProps: ICommonTableProps = {
  checkable: false,
  defaultSize: 'medium',
  hasColumnSetting: false,
  paginationType: 'normal',
  columns: [
    { id: 'bkDataId', name: window.i18n.tc('数据ID'), type: 'string', props: { minWidth: 100 } },
    { id: 'nameBtn', name: window.i18n.tc('名称'), type: 'scoped_slots', props: { minWidth: 100 } },
    { id: 'scenarioStr', name: window.i18n.tc('监控对象'), type: 'string', props: { minWidth: 80 } },
    { id: 'relatedStrategyLink', name: window.i18n.tc('关联策略'), type: 'scoped_slots', props: { minWidth: 100 } },
    { id: 'create', name: window.i18n.tc('创建记录'), type: 'scoped_slots' },
    { id: 'update', name: window.i18n.tc('更新记录'), type: 'scoped_slots' },
    { id: 'opreate', name: window.i18n.tc('操作'), type: 'scoped_slots' },
  ],
};

const dataTransform = (data: IEventItem[]) =>
  data.map(item => ({
    ...item,
    bkDataId: `#${item.bk_data_id}`,
    nameBtn: { slotId: 'name' },
    scenarioStr: item.scenario_display.join('-'),
    relatedStrategyLink: { slotId: 'related' },
    create: { slotId: 'create' },
    update: { slotId: 'update' },
    opreate: { slotId: 'opreate' },
    is_edit: false,
    oldName: item.name,
  }));

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);

@Component({
  name: 'CustomReport',
})
class CustomReport extends Mixins(authorityMixinCreate(customAuth)) {
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Ref('nameInput') readonly nameInput!: HTMLInputElement;
  tableData = {
    ...commonTableProps,
    pagination: {
      count: 0,
      current: 1,
      limit: 10,
      showTotalCount: true,
    },
    loading: false,
    data: [],
  };
  search = '';
  loading = false;
  authChecked = false;
  applyUrl = '';
  handleSearch: (() => void) | null = null;

  emptyType: EmptyStatusType = 'empty';

  /* 当前筛选项 */
  filterType = EFilterType.current;

  isEnterKey = false;

  get getRouterName(): pageType {
    return this.$route.name as pageType;
  }

  get hasViewAuth() {
    const auth = {
      [CUSTOM_EVENT]: this.authority.VIEW_CUSTOM_EVENT,
      [CUSTOM_METRIC]: this.authority.VIEW_CUSTOM_METRIC,
    };
    return auth[this.getRouterName];
  }

  get hasManageAuth() {
    const auth = {
      [CUSTOM_EVENT]: this.authority.MANAGE_CUSTOM_EVENT,
      [CUSTOM_METRIC]: this.authority.MANAGE_CUSTOM_METRIC,
    };
    return auth[this.getRouterName];
  }

  get manageAuthDetail() {
    const auth = {
      [CUSTOM_EVENT]: customAuth.MANAGE_CUSTOM_EVENT,
      [CUSTOM_METRIC]: customAuth.MANAGE_CUSTOM_METRIC,
    };
    return auth[this.getRouterName];
  }

  created() {
    this.handleSearch = debounce(300, this.handleSearchChange);
  }
  mounted() {
    if (!this.loading && !this.tableData.loading) {
      this.clearConditions();
      this.init();
    }
  }
  beforeRouteEnter(to, from, next) {
    next(vm => {
      vm.dataReset();
      if (
        !['custom-escalation-form', 'custom-detail-event', 'custom-detail-timeseries', 'custom-scenes-view'].includes(
          from.name
        )
      ) {
        vm.clearConditions();
      }
      !vm.loading && vm.init();
    });
  }

  /**
   * 处理自定义指标表格特有的数据
   */
  handleCustomMetricTable() {
    this.tableData.hasColumnSetting = true;
    this.tableData.columns.splice(
      2,
      0,
      ...([
        { id: 'data_label', name: window.i18n.tc('数据标签'), type: 'string', props: { minWidth: 100 } },
        { id: 'desc', name: window.i18n.tc('描述'), type: 'string', props: { minWidth: 100 } },
        { id: 'protocol', name: window.i18n.tc('上报协议'), type: 'string', props: { minWidth: 100 } },
      ] as ITableColumn[])
    );
    /** 隐藏的字段 */
    const excludeCheckedId = ['protocol', 'create'];
    this.tableData.columns = this.tableData.columns.map(item => ({
      ...item,
      checked: !excludeCheckedId.includes(item.id),
    }));
  }
  /* 重置数据 */
  dataReset() {
    this.tableData = {
      ...{
        ...deepClone(commonTableProps),
      },
      pagination: {
        count: 0,
        current: 1,
        limit: commonPageSizeGet(),
        showTotalCount: true,
      },
      loading: false,
      data: [],
    };
    this.getRouterName === CUSTOM_METRIC && this.handleCustomMetricTable();
    this.search = this.$route.params.id || '';
    this.loading = false;
  }

  async init() {
    this.tableData.loading = true;
    const params = {
      search_key: this.search,
      page: this.tableData.pagination.current,
      page_size: this.tableData.pagination.limit,
      is_platform: this.filterType === EFilterType.platform ? 1 : undefined,
    };
    this.emptyType = this.search ? 'search-empty' : 'empty';
    const hasAuth = await this.handleAuthCheck();
    if (hasAuth) {
      const api = {
        [CUSTOM_EVENT]: queryCustomEventGroup,
        [CUSTOM_METRIC]: customTimeSeriesList,
      };
      const data = await api[this.getRouterName](params).catch(() => {
        this.emptyType = '500';
        return { list: [], total: 0 };
      });
      this.tableData.data = dataTransform(data.list);
      this.tableData.pagination.count = data.total;
      this.authChecked = true;
    }
    this.tableData.loading = false;
  }

  // 权限设置
  async handleAuthCheck(): Promise<boolean> {
    if (this.authChecked) return this.hasViewAuth;
    const auth = {
      [CUSTOM_EVENT]: customAuth.VIEW_CUSTOM_EVENT,
      [CUSTOM_METRIC]: customAuth.VIEW_CUSTOM_METRIC,
    };
    const authName = auth[this.getRouterName];
    const data = await checkAllowedByActionIds({ action_ids: [authName] }).catch(() => false);
    const hasAuth = Array.isArray(data) ? data.some(item => item.is_allowed) : false;
    if (!hasAuth) {
      const authDetail = await getAuthorityDetail({
        action_ids: [authName],
      });
      this.applyUrl = authDetail.apply_url;
    }
    this.authChecked = true;
    return hasAuth;
  }

  //  还原分页参数和清空搜索框
  clearConditions() {
    const defaultPageSize = commonPageSizeGet();
    this.tableData.pagination = {
      current: 1,
      count: 0,
      limit: defaultPageSize,
      showTotalCount: true,
    };
    this.search = '';
  }

  /**
   * @description: 跳转详情
   * @param {IEventItem} row
   * @return {*}
   */
  handleGotoDetail(row: IEventItem) {
    const name = detailRouteName[this.getRouterName];
    this.$router.push({
      name,
      params: {
        id: row[dataIdMap[this.getRouterName]],
        type: detailType[this.getRouterName],
      },
    });
  }
  /**
   * @description: 跳转到策略
   * @param {IEventItem} row
   * @return {*}
   */
  handleGotoStrategy(row: IEventItem) {
    if (!row.related_strategy_count) return;
    const dataId = dataIdMap[this.getRouterName];
    this.$router.push({
      name: 'strategy-config',
      params: {
        [dataIdName[dataId]]: row[dataId],
      },
    });
  }

  /**
   * @description: 跳转检查试图及删除操作
   * @param {*} v
   * @param {IEventItem} row
   * @return {*}
   */
  handleOperate(v: 'delete' | 'manage' | 'view', row: IEventItem) {
    const toView = {
      [CUSTOM_EVENT]: () => {
        this.$router.push({
          name: 'custom-escalation-event-view',
          params: { id: String(row.bk_event_group_id) },
          query: { name: row.name },
        });
      },
      [CUSTOM_METRIC]: () => {
        this.$router.push({
          name: 'custom-escalation-view',
          params: { id: String(row.time_series_group_id) },
          query: { name: row.name },
        });
      },
    };
    const handleDeleteItem = async () => {
      this.loading = true;
      const api = {
        [CUSTOM_EVENT]: deleteCustomEventGroup,
        [CUSTOM_METRIC]: deleteCustomTimeSeries,
      };
      const key = dataIdMap[this.getRouterName];
      const res = await api[this.getRouterName]({ [key]: row[key] })
        .then(() => true)
        .catch(() => false);
      if (res) {
        this.$bkMessage({
          theme: 'success',
          message: this.$t('删除成功'),
        });
        this.tableData.pagination.current = 1;
        this.init();
      }
      this.loading = false;
    };
    switch (v) {
      case 'view':
        toView[this.getRouterName]();
        break;
      case 'manage':
        this.handleGotoDetail(row);
        break;
      case 'delete':
        this.$bkInfo({
          title: this.getRouterName === CUSTOM_EVENT ? this.$t('确定删除该事件？') : this.$t('确定删除该指标？'),
          confirmFn: () => {
            handleDeleteItem();
          },
        });
        break;
    }
  }

  /**
   * @description: 新建操作
   * @param {*}
   * @return {*}
   */
  addCustomEscalation() {
    const pageType = {
      [CUSTOM_EVENT]: 'customEvent',
      [CUSTOM_METRIC]: 'customTimeSeries',
    };
    this.$router.push({
      name: addPageName[this.getRouterName],
      params: {
        type: pageType[this.getRouterName],
      },
    });
  }

  /**
   * @description: 搜索
   * @param {*}
   * @return {*}
   */
  handleSearchChange() {
    this.tableData.pagination.current = 1;
    this.init();
  }

  /**
   * @description: 分页
   * @param {number} page
   * @return {*}
   */
  handlePageChange(page: number) {
    this.tableData.pagination.current = page;
    this.init();
  }
  handlePageLimitChange(size: number) {
    if (size !== this.tableData.pagination.limit) {
      this.tableData.pagination.limit = size;
      this.tableData.pagination.current = 1;
      commonPageSizeSet(size);
      this.init();
    }
  }

  /** 空状态操作*/

  handleEmptyOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.search = '';
      this.init();
      return;
    }

    if (type === 'refresh') {
      this.emptyType = 'empty';
      this.init();
      return;
    }
  }

  /**
   * @description 切换当前空间与平台数据
   * @param type
   */
  handleFilterTypeChange(type: EFilterType) {
    if (this.filterType !== type) {
      this.filterType = type;
      this.tableData.pagination.current = 1;
      this.init();
    }
  }
  // 验证名字是否重复的函数
  async validateName(row: IEventItem) {
    try {
      const res = await this.$store.dispatch('custom-escalation/validateCustomTimetName', {
        params: { name: row.name, time_series_group_id: row.time_series_group_id },
      });
      return res.result ?? true;
    } catch (error) {
      console.log(error);
      return false;
    }
  }
  /** 编辑名称 */
  async handleNameBlur(row: IEventItem) {
    /** 没有做修改 */
    if (row.name === row.oldName) {
      row.is_edit = false;
      return;
    }
    // 验证名字是否重复
    const isNameValid = await this.validateName(row);
    if (!isNameValid) {
      row.name = row.oldName;
      this.$nextTick(() => {
        this.nameInput.focus();
      });
      return;
    }

    row.is_edit = false;
    this.loading = true;
    try {
      const params = {
        time_series_group_id: row.time_series_group_id,
        name: row.name,
      };
      const data = await this.$store.dispatch('custom-escalation/editCustomTime', params);
      if (data) {
        this.$bkMessage({ theme: 'success', message: this.$t('修改成功') });
        this.init();
      }
    } finally {
      this.loading = false;
    }
  }

  render() {
    return (
      <div
        class='custom-report-page'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='content-left'>
          <PageTips
            style={{ marginTop: '16px' }}
            tips-text={this.$t(
              '自定义上报是一种最灵活和自由的方式上报数据。如果是通过HTTP上报，agent和插件都不需要安装；如果是通过SDK和命令行上报，依赖bkmonitorbeat采集器。'
            )}
            doc-link={'fromCustomRreporting'}
            link-text={this.$t('采集器安装前往节点管理')}
            link-url={`${this.$store.getters.bkNodeManHost}#/plugin-manager/list`}
          />
          <div class='custom-report-page-content'>
            <div class='content-left-operator'>
              <bk-button
                class='mc-btn-add mr-16'
                v-authority={{ active: !this.hasManageAuth }}
                theme='primary'
                onClick={() =>
                  this.hasManageAuth
                    ? this.addCustomEscalation()
                    : this.handleShowAuthorityDetail(this.manageAuthDetail)
                }
              >
                <span class='icon-monitor icon-plus-line mr-6' />
                {this.$t('新建')}
              </bk-button>
              <div class='bk-button-group bk-button-group-capsule'>
                {filterTypes.map(item => (
                  <div
                    key={item.id}
                    class='bk-button-container'
                  >
                    <bk-button
                      class={this.filterType === item.id ? 'is-selected' : ''}
                      onClick={() => this.handleFilterTypeChange(item.id)}
                    >
                      {item.name}
                    </bk-button>
                  </div>
                ))}
              </div>
              <bk-input
                extCls='operator-input'
                v-model={this.search}
                placeholder={this.$tc('搜索 ID / 名称')}
                rightIcon='bk-icon icon-search'
                on-change={this.handleSearch}
              />
            </div>
            {this.tableData.loading ? (
              <TableSkeleton
                class='mt-16'
                type={2}
              />
            ) : (
              <CommonTable
                class='content-left-table'
                {...{ props: this.tableData }}
                scopedSlots={{
                  name: (row: IEventItem) => (
                    <span class='table-name-cell'>
                      {row?.is_readonly ? (
                        <span>{row.name}</span>
                      ) : row.is_edit ? (
                        <bk-input
                          ref='nameInput'
                          class='table-name-input'
                          v-model={row.name}
                          placeholder={this.$t('请输入')}
                          onBlur={() => {
                            if (!this.isEnterKey) {
                              this.handleNameBlur(row);
                            }
                            this.isEnterKey = false;
                          }}
                          onEnter={(val, e) => {
                            this.isEnterKey = true;
                            e.preventDefault();
                            this.handleNameBlur(row);
                          }}
                        />
                      ) : (
                        <span
                          class='col-btn'
                          onClick={() => this.handleOperate('view', row)}
                        >
                          {row.name}
                        </span>
                      )}
                      {!row.is_edit && row?.is_platform ? (
                        <span class='platform-tag'>{this.$t('公共')}</span>
                      ) : undefined}
                      {/* {!row.is_edit && (
                        <i
                          class='icon-monitor icon-bianji edit-btn'
                          onClick={() => {
                            row.is_edit = !row.is_edit;
                          }}
                        />
                      )} */}
                    </span>
                  ),
                  related: (row: IEventItem) => (
                    <div class='col-strategy'>
                      <span
                        class={{ 'col-btn': row.related_strategy_count > 0 }}
                        onClick={() => this.handleGotoStrategy(row)}
                      >
                        {row.related_strategy_count}
                      </span>
                    </div>
                  ),
                  create: (row: IEventItem) => (
                    <div class='col-change'>
                      <bk-user-display-name
                        class='col-change-author'
                        user-id={row.create_user}
                      />
                      <span>{row.create_time}</span>
                    </div>
                  ),
                  update: (row: IEventItem) =>
                    row.update_time && row.update_user ? (
                      <div class='col-change'>
                        <bk-user-display-name
                          class='col-change-author'
                          user-id={row.update_user}
                        />
                        <span>{row.update_time}</span>
                      </div>
                    ) : (
                      <div>--</div>
                    ),
                  opreate: (row: IEventItem) => (
                    <OperateOptions
                      options={{
                        outside: [
                          { id: 'view', name: window.i18n.tc('可视化'), authority: true },
                          { id: 'manage', name: window.i18n.tc('管理'), authority: true },
                          {
                            id: 'delete',
                            name: window.i18n.tc('删除'),
                            authority: this.hasManageAuth,
                            authorityDetail: this.manageAuthDetail,
                            tip: row?.is_readonly ? this.$tc('非当前业务，不允许操作') : '',
                            disable: row.related_strategy_count !== 0 || !!row?.is_readonly,
                          },
                        ],
                      }}
                      onOptionClick={(v: 'delete' | 'manage' | 'view') => this.handleOperate(v, row)}
                    />
                  ),
                }}
                onLimitChange={this.handlePageLimitChange}
                onPageChange={this.handlePageChange}
              >
                <div slot='empty'>
                  <EmptyStatus
                    type={this.emptyType}
                    onOperation={this.handleEmptyOperation}
                  />
                </div>
              </CommonTable>
            )}
          </div>
        </div>
        {/* <div class="content-right">
          <LeftPanel list={panelList}></LeftPanel>
        </div> */}
      </div>
    );
  }
}

export default tsx.ofType<object>().convert(CustomReport);
