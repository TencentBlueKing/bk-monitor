/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, InjectReactive, Prop, Provide, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listApplicationInfo, simpleServiceList } from 'monitor-api/modules/apm_meta';
import { globalUrlFeatureMap } from 'monitor-common/utils/global-feature-map';
import { onExternalParams } from 'monitor-common/utils/iframe-bridge';
import { random } from 'monitor-common/utils/utils';
import { destroyTimezone } from 'monitor-pc/i18n/dayjs';
import CommonPage, { type SceneType } from 'monitor-pc/pages/monitor-k8s/components/common-page-new';
import { isNavigationFailure } from 'vue-router';

import ApmCommonNavBar, {
  type INavItem,
  type ISelectItem,
} from '../../components/apm-common-nav-bar/apm-common-nav-bar';
import ListMenu, { type IMenuItem } from '../../components/list-menu/list-menu';
import applicationStore from '../../store/modules/application';
import { LLM_SESSION_PANEL_TYPE } from './contents/llm_session/constants';
import LlmSession from './contents/llm_session/llm-session';

import type { IAppSelectOptItem } from '../home/app-select';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';
import type { TranslateResult } from 'vue-i18n';

import './service.scss';

interface IServiceParams {
  is_relation: boolean; // 是否关联
  target: string; // 跳转方式
  url: string; // 跳转地址
}

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
@Component
export default class Service extends tsc<object> {
  @Prop({ type: String, default: '' }) id: string;

  @Ref() commonPageRef: CommonPage;
  @InjectReactive('readonly') readonly: boolean;
  viewOptions: IViewOptions = {};
  // 导航条设置
  routeList: INavItem[] = [];

  // 是否展示引导页
  showGuidePages = false;

  backToOverviewKey = random(10);

  sceneType: SceneType = 'overview';

  /** common-page组件的key */
  pageKey = 1;
  appName = '';
  serviceName = '';
  pluginId = '';
  dashboardId = '';
  tabId = '';
  tabName: string | TranslateResult = '';
  subName = '';
  appList = [];
  /** 避免较早的应用切换请求覆盖最新选择 */
  appSwitchRequestId = 0;
  serviceListRequestId = 0;
  /** 取消订阅父页面参数联动 */
  unsubscribeExternalParams: () => void = null;
  // menu list
  menuList: IMenuItem[] = [
    {
      id: 'basic',
      name: window.i18n.tc('基本设置'),
    },
  ];

  /** 列表 */
  get pluginsList(): IAppSelectOptItem[] {
    return applicationStore.pluginsListGetter || [];
  }

  get bizId() {
    return this.$store.getters.bizId;
  }

  get positionText() {
    const label = this.tabName;

    const value =
      this.sceneType === 'overview'
        ? this.tabId === 'topo'
          ? window.i18n.tc('拓扑')
          : window.i18n.tc('概览')
        : this.subName;
    return `${label}：${value}`;
  }

  @Provide('linkSelfClick')
  linkSelfClick() {
    this.syncPageStateFromRoute(this.tabId);
    this.pageKey += 1;
  }

  async beforeRouteEnter(to, _from, next) {
    const { query } = to;
    const appName = query['filter-app_name'] as string;
    const serviceName = query['filter-service_name'] as string;
    applicationStore.getPluginList();
    const nextTo: any = (vm: Service) => {
      vm.routeList = [
        {
          id: 'home',
          name: 'APM',
          query: {
            app_name: appName,
          },
        },
        {
          id: 'application',
          name: `${window.i18n.tc('应用')}：${appName}`,
          query: {
            'filter-app_name': appName,
          },
          selectOption: {
            value: appName,
            selectList: [],
            loading: false,
          },
        },
        {
          id: 'service',
          name: `${window.i18n.tc('服务')}：${serviceName}`,
          selectOption: {
            value: serviceName,
            selectList: [],
            loading: false,
          },
        },
      ];
      vm.viewOptions = {
        filters: {
          app_name: appName,
          service_name: serviceName,
        },
      };
      vm.appName = appName;
      vm.serviceName = serviceName;
      vm.dashboardId = query.dashboardId as string;
      vm.getApplicationList();
      vm.getServiceList();
    };
    next(nextTo);
  }
  beforeRouteLeave(_to, _from, next) {
    this.appSwitchRequestId += 1;
    this.serviceListRequestId += 1;
    destroyTimezone();
    next();
  }

  mounted() {
    this.unsubscribeExternalParams = onExternalParams(this.handleExternalParams);
  }

  beforeDestroy() {
    this.appSwitchRequestId += 1;
    this.serviceListRequestId += 1;
    this.unsubscribeExternalParams?.();
  }

  /** 父页面下发参数联动：应用/服务可独立变化，携带服务参数时切换当前服务，与当前一致则忽略 */
  handleExternalParams(params: Record<string, string>) {
    const appName = params['filter-app_name'];
    const serviceName = params['filter-service_name'];
    if (appName && (!serviceName || serviceName === this.serviceName)) {
      return this.applyAppName(appName);
    }
    if (!serviceName || serviceName === this.serviceName) return;
    return this.handleNavSelect(
      {
        id: serviceName,
        name: serviceName,
        app_name: appName || this.appName,
        service_name: serviceName,
      },
      'service'
    );
  }

  /** 切换应用时保留同名服务、页签及查询条件，仅在服务不存在时返回应用页 */
  async applyAppName(appName: string) {
    const requestId = ++this.appSwitchRequestId;
    if (appName === this.appName) {
      this.routeList[2].selectOption.loading = false;
      return;
    }
    this.routeList[2].selectOption.loading = true;
    // 查询失败不等同于服务不存在，保留当前页面，由 API 层展示错误。
    const listData = await simpleServiceList({ app_name: appName }).catch(() => null);
    if (requestId !== this.appSwitchRequestId) return;
    this.routeList[2].selectOption.loading = false;
    if (!listData) return;

    const service = listData.find(item => item.service_name === this.serviceName);
    const query = {
      ...this.$route.query,
      'filter-app_name': appName,
      'filter-service_name': service?.service_name,
      'filter-category': service?.category,
      'filter-kind': service?.kind,
      'filter-predicate_value': service?.predicate_value,
      dashboardId: this.$route.query.dashboardId || this.dashboardId,
      sceneId: service ? 'apm_service' : 'apm_application',
      sceneType: service ? this.$route.query.sceneType : 'overview',
    };
    try {
      if (!service) {
        await this.$router.push({ name: 'application', query });
        return;
      }
      // 路由完成后再重建视图，确保 CommonPage 从新应用的完整查询参数恢复状态。
      await this.$router.replace({ name: 'service', query });
    } catch (error) {
      if (!isNavigationFailure(error)) throw error;
      return;
    }
    if (requestId !== this.appSwitchRequestId) return;
    if (this.$route.name !== 'service' || this.$route.query['filter-app_name'] !== appName) return;
    this.serviceListRequestId += 1;
    this.updateServiceList(listData);
    await this.refreshServicePage(requestId);
  }

  /** 根据路由同步应用、服务导航及当前页签 */
  async syncPageStateFromRoute(id: string, name: string | TranslateResult = '') {
    await this.$nextTick();
    const { query } = this.$route;
    this.appName = (query['filter-app_name'] as string) || '';
    this.routeList[0].query = { app_name: this.appName };
    this.routeList[1].name = `${this.$tc('应用')}：${this.appName}`;
    this.routeList[1].query = { 'filter-app_name': this.appName };
    this.routeList[1].selectOption.value = this.appName;
    this.serviceName = (query['filter-service_name'] as string) || '';
    this.routeList[2].name = `${this.$tc('服务')}：${this.serviceName}`;
    this.routeList[2].selectOption.value = this.serviceName;
    this.dashboardId = (query.dashboardId as string) || '';
    this.tabId = id;
    this.tabName = ['topo', 'overview'].includes(id) ? this.$t('服务') : name;
  }

  /** 应用或服务切换后，从已完成的路由统一刷新导航和视图 */
  async refreshServicePage(requestId: number) {
    await this.syncPageStateFromRoute(this.tabId, this.tabName);
    if (requestId !== this.appSwitchRequestId) return;
    const { query } = this.$route;
    this.viewOptions = {
      filters: {
        app_name: query['filter-app_name'],
        service_name: query['filter-service_name'],
        category: query['filter-category'],
        kind: query['filter-kind'],
        predicate_value: query['filter-predicate_value'],
      },
    };
    this.pageKey += 1;
  }

  /** 获取应用列表 */
  async getApplicationList() {
    this.routeList[1].selectOption.loading = true;
    const listData = await listApplicationInfo().catch(() => []);
    this.appList = listData.map(item => ({
      id: item.app_name,
      name: `${item.app_name}(${item.app_alias})`,
      ...item,
    }));
    this.routeList[1].selectOption.loading = false;
    this.routeList[1].selectOption.selectList = this.appList;
  }

  /** 获取服务列表 */
  async getServiceList() {
    if (!this.appName) return;
    const appName = this.appName;
    const requestId = ++this.serviceListRequestId;
    const switchId = this.appSwitchRequestId;
    this.routeList[2].selectOption.loading = true;
    const listData = await simpleServiceList({ app_name: appName }).catch(() => []);
    if (requestId !== this.serviceListRequestId || appName !== this.$route.query['filter-app_name']) return;
    if (switchId === this.appSwitchRequestId) this.routeList[2].selectOption.loading = false;
    this.updateServiceList(listData);
  }

  updateServiceList(listData: { service_name: string }[]) {
    this.routeList[2].selectOption.selectList = listData.map(item => ({
      ...item,
      id: item.service_name,
      name: item.service_name,
    }));
  }

  /** 导航栏下拉选择 */
  async handleNavSelect(item: ISelectItem, navId: string) {
    if (navId === 'application') return this.applyAppName(item.id);

    const { to, from, interval, timezone, refreshInterval, dashboardId } = this.$route.query;
    const requestId = ++this.appSwitchRequestId;
    this.routeList[2].selectOption.loading = false;
    const appChanged = item.app_name !== this.appName;
    const targetQuery = {
      to,
      from,
      interval,
      timezone,
      refreshInterval,
      dashboardId,
      'filter-app_name': item.app_name,
      'filter-service_name': item.service_name,
      'filter-category': item.category,
      'filter-kind': item.kind,
      'filter-predicate_value': item.predicate_value,
    };
    const targetRoute = this.$router.resolve({ name: this.$route.name, query: targetQuery });
    /** 防止父页面重复下发相同参数导致重复跳转报错 */
    try {
      if (targetRoute.resolved.fullPath !== this.$route.fullPath) {
        await this.$router.replace({ name: this.$route.name, query: targetQuery });
      }
    } catch (error) {
      if (!isNavigationFailure(error)) throw error;
      return;
    }
    if (requestId !== this.appSwitchRequestId) return;
    await this.refreshServicePage(requestId);
    // 父页面参数联动时应用可能一并变化，路由成功后再刷新服务列表。
    if (appChanged && requestId === this.appSwitchRequestId) this.getServiceList();
  }

  /**
   * @desc: 服务配置离开当前页
   * @param {IServiceParams} row 列表参数
   */
  handleLeavePage(row?: IServiceParams) {
    if (row?.url) {
      window.open(row.url, '_blank');
      return;
    }
    this.handleToServiceConfig();
  }
  handleToServiceConfig() {
    const { query } = this.$route;
    this.$router.push({
      name: 'service-config',
      query: {
        app_name: (query['filter-app_name'] as string) || '',
        service_name: (query['filter-service_name'] as string) || '',
      },
    });
  }
  /** 详情返回列表操作刷新列表的数据 */
  handleRouterBack() {
    this.backToOverviewKey = random(8);
  }
  handleSceneTypeChange(type) {
    this.sceneType = type;
    this.dashboardId = '';
  }
  handleTitleChange(title) {
    this.subName = title;
  }
  handleSettingsMenuSelect() {
    this.handleToServiceConfig();
  }

  render() {
    return (
      <div class='service'>
        {
          <CommonPage
            key={this.pageKey}
            ref='commonPageRef'
            class={'apm-service-page'}
            backToOverviewKey={this.backToOverviewKey}
            customContentPanelTypes={[LLM_SESSION_PANEL_TYPE]}
            defaultDashboardId={this.dashboardId}
            defaultViewOptions={this.viewOptions}
            isShowSplitPanel={false}
            sceneId={'apm_service'}
            sceneType={'overview'}
            tab2SceneType
            onSceneTypeChange={this.handleSceneTypeChange}
            onTabChange={this.syncPageStateFromRoute}
            onTitleChange={this.handleTitleChange}
          >
            {/* CommonPage 命中 LLM 会话面板类型时才渲染该插槽，组件也只在那时挂载 */}
            <LlmSession slot='customContent' />
            {globalUrlFeatureMap.APM_SUBMENU && (
              <ApmCommonNavBar
                slot='nav'
                needBack={false}
                needNavList={globalUrlFeatureMap.APM_NAV_LIST}
                needShadow={true}
                positionText={this.positionText}
                routeList={this.routeList}
                needCopyLink
                onNavSelect={this.handleNavSelect}
              />
            )}
            {!this.readonly && !!this.appName && (
              <div
                class='service-tools'
                slot='buttonGroups'
              >
                <ListMenu
                  list={this.menuList}
                  onMenuSelect={this.handleSettingsMenuSelect}
                >
                  <i class='icon-monitor icon-mc-more-tool' />
                </ListMenu>
              </div>
            )}
          </CommonPage>
        }
      </div>
    );
  }
}
