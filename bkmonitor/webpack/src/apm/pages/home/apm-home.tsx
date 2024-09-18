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

import { Component, Provide, Watch, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deleteApplication, listApplication, listApplicationAsync } from 'monitor-api/modules/apm_meta';
import { serviceList, serviceListAsync } from 'monitor-api/modules/apm_metric';
import { Debounce } from 'monitor-common/utils/utils';
import GuidePage from 'monitor-pc/components/guide-page/guide-page';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import AlarmTools from 'monitor-pc/pages/monitor-k8s/components/alarm-tools';
import DashboardTools from 'monitor-pc/pages/monitor-k8s/components/dashboard-tools';
import OperateOptions from 'monitor-pc/pages/uptime-check/components/operate-options';
import introduceData from 'monitor-pc/router/space';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';

import ListMenu, { type IMenuItem } from '../../components/list-menu/list-menu';
import authorityStore from '../../store/modules/authority';
import AppNewAdd from '../application/app-new-add/app-new-add';
import AppHomeList from './components/apm-home-list';
import NavBar from './nav-bar';
import ApmHomeSkeleton from './skeleton/apm-home-skeleton';
import { SEARCH_KEYS, charColor, OPERATE_OPTIONS } from './utils';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { ICommonTableProps } from 'monitor-pc/pages/monitor-k8s/components/common-table';
import type { IFilterDict, INavItem } from 'monitor-pc/pages/monitor-k8s/typings';

import './apm-home.scss';
import '@blueking/search-select-v3/vue2/vue2.css';

export interface IAppListItem {
  isExpan: boolean;
  app_alias: {
    value: string;
  };
  app_name: string;
  application_id: number;
  firstCode: string;
  permission: {
    [key: string]: boolean;
  };
  loading: false;
  service_count?: {
    value?: number;
  };
  firstCodeColor: string;
  tableData: ICommonTableProps & {
    paginationData: {
      current: number;
      limit: number;
      count: number;
      isEnd?: boolean;
    };
  };
  tableDataLoading: boolean;
  tableSortKey: string;
  tableFilters: IFilterDict;
  profiling_data_status: string;
  data_status: string;
}

@Component({})
export default class AppList extends tsc<object> {
  @Ref() mainResize: any;
  routeList: INavItem[] = [
    {
      id: '',
      name: 'APM',
    },
  ];
  /** 时间范围 */
  timeRange: TimeRangeType = ['now-1h', 'now'];
  /** 显示引导页 */
  showGuidePage = false;
  // menu list
  menuList: IMenuItem[] = [
    {
      id: 'help-docs',
      name: window.i18n.tc('帮助文档'),
    },
  ];
  /** 是否显示帮助文档弹窗 */
  showGuideDialog = false;
  /** 搜索关键词 */
  searchKeyword = '';
  /* 是否展开 */
  isExpan = false;
  /* 应用分类数据 */
  appList: IAppListItem[] = [];
  pagination = {
    current: 1,
    limit: 10,
    total: 100,
    isEnd: false,
  };
  loading = false;

  refreshInstance = null;

  itemRow = {};

  hasSelected = false;

  showFilterPanel = true;

  isShowAppAdd = false;

  searchQuery = '';

  searchCondition = [];

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
            scene_id: 'apm',
          },
        },
      ],
    };
    return new PanelModel(data as any);
  }
  get apmIntroduceData() {
    const apmData = introduceData['apm-home'];
    apmData.is_no_source = false;
    apmData.data.buttons[0].url = window.__POWERED_BY_BK_WEWEB__ ? '#/apm/application/add' : '#/application/add';
    return apmData;
  }
  @Provide('handleShowAuthorityDetail')
  handleShowAuthorityDetail(actionIds: string | string[]) {
    authorityStore.getAuthorityDetail(actionIds);
  }

  created() {
    const { query } = this.$route;
    if (query?.queryString) {
      this.searchCondition.push({
        id: query.queryString,
        name: query.queryString,
      });
    }
    const setSearchCondition = (keys: string[]) => {
      for (const key of keys) {
        const matchingStatus =
          query?.[key] && SEARCH_KEYS.find(item => item.id === key)?.children.find(s => s.id === query[key]);
        if (matchingStatus) {
          const { name } = SEARCH_KEYS.find(item => item.id === key) || {};
          this.searchCondition.push({
            id: key,
            name,
            values: [{ ...matchingStatus }],
          });
        }
      }
    };
    setSearchCondition(['profiling_data_status', 'is_enabled_profiling']);
    this.getLimitOfHeight();
    this.getAppList();
  }

  @Watch('appList')
  changeAppList(newItems) {
    if (newItems.length > 0 && !this.hasSelected) {
      this.handleExpanChange(this.appList[0]);
      this.hasSelected = true;
    }
  }

  /* 搜索应用名/ID */
  handleRemoteMethod() {}

  /**
   * @description 动态计算当前每页数量
   */
  getLimitOfHeight() {
    const itemHeight = 68;
    const limit = Math.ceil((window.screen.height - 164) / itemHeight) + 1;
    this.pagination.limit = limit;
  }

  /**
   * @description 获取应用列表
   */
  async getAppList() {
    if (this.loading) {
      return;
    }
    let queryString = '';
    let profilingDataStatus = '';
    let isEnabledProfiling = null;
    for (const item of this.searchCondition) {
      if (item?.values?.length) {
        if (item.id === 'profiling_data_status') {
          profilingDataStatus = item.values[0].id;
        } else if (item.id === 'is_enabled_profiling') {
          isEnabledProfiling = item.values[0].id === 'true';
        }
      } else {
        queryString = item.id;
      }
    }
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const params = {
      start_time: startTime,
      end_time: endTime,
      keyword: queryString,
      sort: '',
      filter_dict: {
        profiling_data_status: profilingDataStatus || undefined,
        is_enabled_profiling: isEnabledProfiling === null ? undefined : isEnabledProfiling,
      },
      page: this.pagination.current,
      page_size: this.pagination.limit,
    };
    this.loading = true;
    const listData = await listApplication(params).catch(() => {
      return {
        data: [],
      };
    });
    this.loading = false;
    /* 是否到底了 */
    this.pagination.isEnd = listData.data.length < this.pagination.limit;
    /* 总数 */
    this.pagination.total = listData.total || 0;
    const defaultItem = item => {
      const firstCode = item.app_alias?.value?.slice(0, 1) || '-';
      return {
        ...item,
        isExpan: false,
        firstCodeColor: charColor(firstCode),
        firstCode,
        loading: false,
        tableData: {
          pagination: null,
          paginationData: {
            count: 0,
            current: 1,
            limit: 15,
            isEnd: false,
          },
          columns: [],
          data: [],
          loading: false,
          checkable: false,
          showLimit: false,
          outerBorder: true,
          scrollLoading: false,
          maxHeight: 584,
        },
        tableDataLoading: false,
        tableSortKey: '',
        tableFilters: {},
        service_count: null,
      };
    };
    if (this.pagination.current === 1) {
      this.appList = listData.data.map(item => defaultItem(item));
    } else {
      this.appList.push(...listData.data.map(item => defaultItem(item)));
    }
    this.getAsyncData(
      ['service_count'],
      listData.data.map(item => item.application_id)
    );
    // 路由同步查询关键字
    const routerParams = {
      name: this.$route.name,
      query: {
        ...this.$route.query,
        queryString: queryString || undefined,
        profiling_data_status: profilingDataStatus || undefined,
        is_enabled_profiling: isEnabledProfiling === null ? undefined : String(isEnabledProfiling),
      },
    };
    this.$router.replace(routerParams).catch(() => {});
  }

  /* 获取服务数量 */
  getAsyncData(fields: string[], appIds: number[]) {
    for (const field of fields) {
      const params = {
        column: field,
        application_ids: appIds,
      };
      listApplicationAsync(params).then(res => {
        const dataMap = res?.reduce((map, item) => {
          map[String(item.application_id)] = item[field];
          return map;
        }, {});
        this.appList = this.appList.map(app => ({
          ...app,
          [field]: app[field] || dataMap[String(app.application_id)] || null,
        }));
      });
    }
  }
  /**
   * @description 获取服务列表
   * @param appIds
   * @param isScrollEnd
   * @param isReflesh
   */
  getServiceData(appIds: number[], isScrollEnd = false, isReflesh = false) {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const appIdsSet = new Set(appIds);
    this.appList.forEach(item => {
      if (item.tableDataLoading || item.tableData.paginationData.isEnd) {
        return;
      }
      if (!isScrollEnd && item.tableData.data.length && !isReflesh) {
        return;
      }
      if (appIdsSet.has(item.application_id)) {
        if (isScrollEnd) {
          item.tableDataLoading = true;
          item.tableData.scrollLoading = true;
        } else {
          item.tableData.loading = true;
        }
        serviceList({
          app_name: item.app_name,
          start_time: startTime,
          end_time: endTime,
          filter: '',
          sort: item.tableSortKey,
          filter_dict: item.tableFilters,
          check_filter_dict: {},
          page: item.tableData.paginationData.current,
          page_size: item.tableData.paginationData.limit,
          keyword: '',
          condition_list: [],
          view_mode: 'page_home',
          view_options: {
            app_name: item.app_name,
            compare_targets: [],
            current_target: {},
            method: 'AVG',
            interval: 'auto',
            group_by: [],
            filters: {
              app_name: item.app_name,
            },
          },
          bk_biz_id: this.$store.getters.bizId,
        })
          .then(({ columns, data, total }) => {
            if (item.tableData.paginationData.current > 1) {
              item.tableData.data.push(...(data || []));
            } else {
              item.tableData.data = data || [];
            }
            item.tableData.columns = columns || [];
            item.tableData.paginationData.count = total;
            item.tableData.paginationData.isEnd = (data || []).length < item.tableData.paginationData.limit;
            const fields = (columns || []).filter(col => col.asyncable).map(val => val.id);
            const services = (data || []).map(d => d.service_name.value);
            fields.forEach(field => {
              serviceListAsync({
                app_name: item.app_name,
                start_time: startTime,
                end_time: endTime,
                column: field,
                service_names: services,
                bk_biz_id: this.$store.getters.bizId,
              })
                .then(serviceData => {
                  const dataMap = {};
                  serviceData?.forEach(item => {
                    if (item.service_name) {
                      dataMap[String(item.service_name)] = item[field];
                    }
                  });
                  item.tableData.data = item.tableData.data.map(d => ({
                    ...d,
                    [field]: d[field] || dataMap[String(d.service_name.value || '')] || null,
                  }));
                })
                .finally(() => {
                  item.tableData.columns = item.tableData.columns.map(col => ({
                    ...col,
                    asyncable: col.id === field ? false : col.asyncable,
                  }));
                });
            });
          })
          .finally(() => {
            item.tableData.scrollLoading = false;
            item.tableDataLoading = false;
            item.tableData.loading = false;
          });
      }
    });
  }

  /**
   * @description 时间范围
   * @param v
   */
  handleTimeRangeChange(v) {
    this.timeRange = v;
    this.pagination.current = 1;
    this.getAppList();
  }

  /**
   * @description 手动刷新
   */
  handleImmediateReflesh() {
    this.pagination.current = 1;
    this.pagination.isEnd = false;
    this.getAppList();
  }

  /**
   * @description 自动刷新
   * @param val
   */
  handleRefleshChange(val: number) {
    window.clearInterval(this.refreshInstance);
    if (val > 0) {
      this.refreshInstance = setInterval(() => {
        this.pagination.current = 1;
        this.getAppList();
      }, val);
    }
  }

  /** 展示添加弹窗 */
  showAddApp() {
    this.isShowAppAdd = !this.isShowAppAdd;
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

  /** 列表搜索 */
  @Debounce(300)
  handleSearch() {}

  /**
   * @description 展开
   * @param row
   */
  handleExpanChange(row: IAppListItem) {
    row.isExpan = !row.isExpan;
    this.itemRow = row;

    if (row.isExpan) {
      this.getServiceData([row.application_id]);
    }
  }

  /** 跳转服务概览 */
  linkToOverview(row) {
    const routeData = this.$router.resolve({
      name: 'application',
      query: {
        'filter-app_name': row.app_name,
      },
    });
    window.location.href = routeData.href;
  }

  /**
   * @description 跳转到配置页
   * @param row
   */
  handleToConfig(row) {
    const routeData = this.$router.resolve({
      name: 'application-config',
      params: {
        id: row.application_id,
      },
    });
    window.location.href = routeData.href;
  }

  /**
   * @description 更多选项
   * @param id
   * @param row
   */
  handleConfig(id, row) {
    if (id === 'appDetails') {
      this.linkToOverview(row);
      return;
    }
    if (id === 'appConfig') {
      this.handleToConfig(row);
      return;
    }
    // 存储状态、数据状态、指标维度、新增无数据告警 分别跳到配置页 query: active
    const toConfigKeys = ['storageState', 'dataStatus', 'indicatorDimension', 'noDataAlarm'];
    // 接入服务 /service-add/opentelemetry/apm_test_have_data
    const toAccessService = ['accessService'];
    if (toConfigKeys.includes(id)) {
      const routeData = this.$router.resolve({
        name: 'application-config',
        params: {
          id: row.application_id,
        },
        query: {
          active: id === 'noDataAlarm' ? 'dataStatus' : id,
        },
      });
      // window.open(routeData.href);
      window.location.href = routeData.href;
    } else if (toAccessService.includes(id)) {
      const routeData = this.$router.resolve({
        name: 'service-add',
        params: {
          appName: row.app_name,
        },
      });
      // window.open(routeData.href);
      window.location.href = routeData.href;
    } else if (id === 'delete') {
      this.$bkInfo({
        type: 'warning',
        title: this.$t('确认删除该应用？'),
        maskClose: true,
        escClose: true,
        confirmFn: () => {
          deleteApplication({ app_name: row.app_name }).then(() => {
            this.$bkMessage({ theme: 'success', message: this.$t('删除成功') });
            this.pagination.current = 1;
            this.pagination.isEnd = false;
            this.getAppList();
          });
        },
      });
    }
  }

  /**
   * @description 滚动加载
   * @param event
   */
  handleScroll(event: any | Event) {
    if (!this.loading && !this.pagination.isEnd) {
      const { clientHeight } = event.target;
      const { scrollTop } = event.target;
      const { scrollHeight } = event.target;
      const isAtBottom = Math.abs(scrollHeight - (clientHeight + scrollTop)) < 1;
      if (isAtBottom) {
        this.pagination.current += 1;
        this.getAppList();
      }
    }
  }

  /**
   * @description 条件搜索
   * @param value
   */
  handleSearchCondition(value) {
    this.searchCondition = value;
    this.pagination.current = 1;
    this.pagination.isEnd = false;
    this.getAppList();
  }

  /* 候选搜索列表过滤 */
  conditionListFilter() {
    const allKey = this.searchCondition.map(item => item.id);
    return SEARCH_KEYS.filter(item => !allKey.includes(item.id));
  }

  render() {
    return (
      <div class='apm-home-wrap-page'>
        <NavBar routeList={this.routeList}>
          {!this.showGuidePage && (
            <div
              class='dashboard-tools-wrap'
              slot='handler'
            >
              <AlarmTools
                class='alarm-tools'
                panel={this.alarmToolsPanel}
              />
              <DashboardTools
                showListMenu={false}
                timeRange={this.timeRange}
                onImmediateReflesh={() => this.handleImmediateReflesh()}
                onRefleshChange={this.handleRefleshChange}
                onTimeRangeChange={this.handleTimeRangeChange}
              />
              <ListMenu
                list={this.menuList}
                onMenuSelect={this.handleSettingsMenuSelect}
              >
                <i class='icon-monitor icon-mc-more-tool' />
              </ListMenu>
            </div>
          )}
        </NavBar>
        <bk-resize-layout
          auto-minimize={200}
          collapsible={true}
          initial-divide={201}
          min={195}
        >
          <div
            class='app-list'
            slot='aside'
          >
            <div class='app-list-title'>{this.$t('应用列表')}</div>
            <div class='app-list-search'>
              <bk-input
                v-model={this.searchQuery}
                placeholder={this.$t('应用名或ID')}
                right-icon='bk-icon icon-search'
                clearable
                show-clear-only-hover
                onChange={() => this.handleRemoteMethod()}
              />
              <div
                class='app-list-add'
                onClick={this.showAddApp}
              >
                <i class='icon-monitor icon-mc-add app-add-icon' />
              </div>
              <AppNewAdd
                isShow={this.isShowAppAdd}
                onShowChange={this.showAddApp}
              />
            </div>
            {this.pagination.current === 1 && this.loading ? (
              <ApmHomeSkeleton />
            ) : (
              <ul class='app-list-data'>
                {this.appList.map(item => (
                  <li
                    key={item.application_id}
                    class={['data-item', { selected: this.itemRow?.application_id === item.application_id }]}
                    onClick={() => this.handleExpanChange(item)}
                  >
                    <div
                      style={{
                        background: item.firstCodeColor,
                      }}
                      class='first-code'
                    >
                      {item.firstCode}
                    </div>
                    <div class='biz-name-01'>{item.app_alias?.value}</div>
                    <div class='item-content'>
                      <span class='item-service-count'>
                        {item.service_count === null ? <div class='spinner' /> : item?.service_count?.value || 0}
                      </span>
                      <OperateOptions
                        class='operate'
                        options={{
                          outside: [],
                          popover: OPERATE_OPTIONS.map(o => ({
                            ...o,
                          })),
                        }}
                        onOptionClick={id => this.handleConfig(id, item)}
                      >
                        <div
                          class='more-btn'
                          slot='trigger'
                        >
                          <span class='icon-monitor icon-mc-more' />
                        </div>
                      </OperateOptions>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div
            class='app-list-service'
            slot='main'
            onScroll={this.handleScroll}
          >
            <AppHomeList
              itemRow={this.itemRow}
              onGetServiceData={this.getServiceData}
              onHandleSearchCondition={this.handleSearchCondition}
              onHandleToConfig={this.handleToConfig}
              onLinkToOverview={this.linkToOverview}
            />
          </div>
        </bk-resize-layout>

        <bk-dialog
          width={1360}
          ext-cls='guide-create-dialog'
          mask-close={true}
          show-footer={false}
          value={this.showGuideDialog}
          on-cancel={this.handleCloseGuideDialog}
        >
          <GuidePage
            guideData={this.apmIntroduceData}
            guideId='apm-home'
            marginless
          />
        </bk-dialog>
      </div>
    );
  }
}
