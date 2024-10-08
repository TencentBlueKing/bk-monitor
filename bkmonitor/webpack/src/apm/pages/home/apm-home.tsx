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

import { Component, Provide } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SearchSelect from '@blueking/search-select-v3/vue2';
import { deleteApplication, listApplication } from 'monitor-api/modules/apm_meta';
import introduceModule, { IntroduceRouteKey } from 'monitor-pc/common/introduce';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import GuidePage from 'monitor-pc/components/guide-page/guide-page';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import AlarmTools from 'monitor-pc/pages/monitor-k8s/components/alarm-tools';
import DashboardTools from 'monitor-pc/pages/monitor-k8s/components/dashboard-tools';
import OperateOptions from 'monitor-pc/pages/uptime-check/components/operate-options';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';

import ListMenu, { type IMenuItem } from '../../components/list-menu/list-menu';
import authorityStore from '../../store/modules/authority';
import AddAppSide from './add-app/add-app-side';
import AppHomeList from './components/apm-home-list';
import ApmHomeResizeLayout from './components/apm-home-resize-layout';
import NavBar from './nav-bar';
import ApmHomeSkeleton from './skeleton/apm-home-skeleton';
import {
  charColor,
  OPERATE_OPTIONS,
  ALERT_PANEL_DATA,
  getDefaultAppListSearchCondition,
  type ISearchCondition,
} from './utils';

import type { IAppListItem } from './typings/app';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { INavItem } from 'monitor-pc/pages/monitor-k8s/typings';

import './apm-home.scss';
import '@blueking/search-select-v3/vue2/vue2.css';

@Component({})
export default class AppList extends tsc<object> {
  routeList: INavItem[] = [
    {
      id: '',
      name: 'APM',
    },
  ];
  /** 时间范围 */
  timeRange: TimeRangeType = ['now-1h', 'now'];
  refreshKey = 0;
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

  /* 应用分类数据 */
  appList: IAppListItem[] = [];
  loading = false;

  refreshInstance = null;
  appName = '';

  showFilterPanel = true;

  isShowAppAdd = false;

  searchData: ISearchCondition[] = getDefaultAppListSearchCondition();
  searchCondition: ISearchCondition[] = [];

  /** 仪表盘工具栏 策略和告警panel */
  alarmToolsPanel = null;
  // 帮助文档弹窗数据
  apmIntroduceData = null;

  get appData() {
    return this.appList?.find(item => item.app_name === this.appName);
  }

  @Provide('handleShowAuthorityDetail')
  handleShowAuthorityDetail(actionIds: string | string[]) {
    authorityStore.getAuthorityDetail(actionIds);
  }

  created() {
    this.initRouteParams();
    this.getAppList();
    this.alarmToolsPanel = new PanelModel(ALERT_PANEL_DATA);
  }
  mounted() {
    // 帮助文档弹窗数据
    window.requestIdleCallback(async () => {
      await introduceModule.getIntroduce(IntroduceRouteKey['apm-home']);
      const introduceData = introduceModule.data[IntroduceRouteKey['apm-home']]?.introduce;
      introduceData.is_no_source = false;
      introduceData.data.buttons[0].url = window.__POWERED_BY_BK_WEWEB__
        ? '#/apm/application/add'
        : '#/application/add';
      this.apmIntroduceData = introduceData;
    });
  }
  initRouteParams() {
    const { query } = this.$route;
    const defaultSearchCondition = [];
    for (const [key, val] of Object.entries(query)) {
      if (key === 'app_keyword') {
        defaultSearchCondition.push({
          id: val.toString(),
          name: val.toString(),
        });
        continue;
      }
      if (key === 'app_name') {
        this.appName = (val || '').toString();
        continue;
      }
      const item = this.searchData.find(item => item.id === key);
      if (item) {
        defaultSearchCondition.push({
          id: item.id,
          values: typeof val === 'string' ? [val] : val,
        });
      }
    }
    this.searchCondition = defaultSearchCondition;
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
    };
    this.loading = true;
    const listData: {
      data: IAppListItem[];
    } = await listApplication(params).catch(() => {
      return {
        data: [],
      };
    });
    this.loading = false;
    this.appList = listData.data.map((item, ind: number) => {
      let firstCode: string = item.app_alias?.slice(0, 1) || '-';
      const charCode = firstCode.charCodeAt(0);
      if (charCode >= 97 && charCode <= 122) {
        firstCode = firstCode.toUpperCase();
      }
      return {
        ...item,
        firstCodeColor: charColor(ind),
        firstCode,
        loading: false,
      };
    });
    // 初始化 app_name
    if (this.appList.length) {
      if (!this.appName) {
        this.appName = listData.data[0].app_name;
      } else if (!params.keyword && !profilingDataStatus && isEnabledProfiling === null) {
        const checkedItem = this.appList.find(item => item.app_name === this.appName);
        if (!checkedItem) {
          this.appName = listData.data[0].app_name;
        }
      }
    }
    this.handleReplaceRouteUrl({}, params);
  }
  handleReplaceRouteUrl(serviceParams: Record<string, any> = {}, appSearchParams: Record<string, any> = {}) {
    // 路由同步查询关键字
    const routerParams = {
      name: this.$route.name,
      query: {
        ...this.$route.query,
        ...serviceParams,
        app_keyword: appSearchParams.keyword || undefined,
        app_name: this.appName,
        profiling_data_status: appSearchParams.profiling_data_status || undefined,
        is_enabled_profiling:
          typeof appSearchParams.is_enabled_profiling !== 'boolean'
            ? undefined
            : String(appSearchParams.is_enabled_profiling),
      },
    };
    this.$router.replace(routerParams).catch(() => {});
  }
  /**
   * @description 时间范围
   * @param v
   */
  handleTimeRangeChange(v: TimeRangeType) {
    this.timeRange = v;
    this.getAppList();
  }

  /**
   * @description 手动刷新
   */
  handleImmediateRefresh() {
    this.getAppList();
    this.refreshKey++;
  }

  /**
   * @description 自动刷新
   * @param val
   */
  handleRefreshChange(val: number) {
    window.clearInterval(this.refreshInstance);
    if (val > 0) {
      this.refreshInstance = setInterval(() => {
        this.getAppList();
        this.refreshKey++;
      }, val);
    }
  }

  /** 展示添加弹窗 */
  handleToggleAppAdd(v: boolean) {
    this.isShowAppAdd = v;
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

  /**
   * @description 应用列表点击
   * @param row
   */
  handleAppClick(row: IAppListItem) {
    if (this.appName === row.app_name) return;
    this.appName = row.app_name;
  }

  /**
   * @description 更多选项
   * @param id
   * @param row
   */
  handleConfig(id: string, row: IAppListItem) {
    if (id === 'appDetails') {
      this.$router.push({
        name: 'application',
        query: {
          'filter-app_name': row.app_name,
        },
      });
      return;
    }
    if (id === 'appConfig') {
      this.$router.push({
        name: 'application-config',
        params: {
          appName: this.appName,
        },
      });
      return;
    }
    // 存储状态、数据状态、指标维度、新增无数据告警 分别跳到配置页 query: active
    const toConfigKeys = ['storageState', 'dataStatus', 'indicatorDimension', 'noDataAlarm'];
    // 接入服务
    if (toConfigKeys.includes(id)) {
      this.$router.push({
        name: 'application-config',
        params: {
          appName: this.appName,
        },
        query: {
          active: id === 'noDataAlarm' ? 'dataStatus' : id,
        },
      });
    } else if (id === 'accessService') {
      this.$router.push({
        name: 'service-add',
        params: {
          appName: row.app_name,
        },
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
            this.getAppList();
          });
        },
      });
    }
  }

  /**
   * @description 条件搜索
   * @param value
   */
  handleSearchCondition(value) {
    this.searchCondition = value;
    this.getAppList();
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
                isSplitPanel={false}
                showListMenu={false}
                timeRange={this.timeRange}
                onImmediateReflesh={() => this.handleImmediateRefresh()}
                onRefleshChange={this.handleRefreshChange}
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
        <ApmHomeResizeLayout
          class='apm-home-content'
          initSideWidth={300}
          isShowCollapse={true}
          maxWidth={400}
          minWidth={150}
        >
          <div
            class='app-list'
            slot='aside'
          >
            <div class='app-list-title'>{this.$t('应用列表')}</div>
            <div class='app-list-search'>
              <SearchSelect
                class='app-list-search-select'
                data={this.searchData}
                modelValue={this.searchCondition}
                placeholder={this.$t('应用名或ID')}
                uniqueSelect={true}
                onChange={this.handleSearchCondition}
              />
              <div
                class='app-list-add'
                v-bk-tooltips={{ content: this.$t('新建应用') }}
                onClick={() => this.handleToggleAppAdd(true)}
              >
                <i class='icon-monitor icon-mc-add app-add-icon' />
              </div>
              <AddAppSide
                isShow={this.isShowAppAdd}
                onShowChange={v => this.handleToggleAppAdd(v)}
                onSuccess={this.getAppList}
              />
            </div>
            {this.loading ? (
              <ApmHomeSkeleton />
            ) : this.appList.length ? (
              <ul class='app-list-data'>
                {this.appList.map(item => (
                  <li
                    key={item.application_id}
                    class={['data-item', { selected: this.appName === item.app_name }]}
                    onClick={() => this.handleAppClick(item)}
                  >
                    <div
                      style={{
                        background: item.firstCodeColor,
                      }}
                      class='first-code'
                    >
                      {item.firstCode}
                    </div>
                    <div
                      class='biz-name-01'
                      v-bk-overflow-tips
                    >
                      <span>{item.app_alias}</span>
                      <span>（{item.app_name}）</span>
                    </div>
                    <div class='item-content'>
                      <span class='item-service-count'>{item?.service_count}</span>
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
            ) : (
              <EmptyStatus
                textMap={{ empty: this.$t('暂无数据') }}
                type={this.searchCondition.length ? 'search-empty' : 'empty'}
                onOperation={() => this.handleSearchCondition([])}
              />
            )}
          </div>
          <div class='app-list-service'>
            <AppHomeList
              key={this.refreshKey}
              appData={this.appData}
              appName={this.appName}
              timeRange={this.timeRange}
              onRouteUrlChange={this.handleReplaceRouteUrl}
            />
          </div>
        </ApmHomeResizeLayout>
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
