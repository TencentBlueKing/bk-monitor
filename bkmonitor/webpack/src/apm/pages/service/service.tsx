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
import { random } from 'monitor-common/utils/utils';
import { destroyTimezone } from 'monitor-pc/i18n/dayjs';
import CommonPage, { type SceneType } from 'monitor-pc/pages/monitor-k8s/components/common-page-new';

import ApmCommonNavBar, {
  type INavItem,
  type ISelectItem,
} from '../../components/apm-common-nav-bar/apm-common-nav-bar';
import ListMenu, { type IMenuItem } from '../../components/list-menu/list-menu';
import applicationStore from '../../store/modules/application';

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
  serviceList = [];
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
    this.handleUpdateAppName(this.tabId);
    this.pageKey += 1;
  }

  async beforeRouteEnter(to, from, next) {
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
  beforeRouteLeave(to, from, next) {
    destroyTimezone();
    next();
  }

  /** 更新当前路由的信息 */
  async handleUpdateAppName(id, name = '') {
    await this.$nextTick();
    const { query } = this.$route;
    this.appName = (query['filter-app_name'] as string) || '';
    this.routeList[1].name = `${this.$tc('应用')}：${this.appName}`;
    this.routeList[1].selectOption.value = this.appName;
    this.serviceName = (query['filter-service_name'] as string) || '';
    this.routeList[2].name = `${this.$tc('服务')}：${this.serviceName}`;
    this.routeList[2].selectOption.value = this.serviceName;
    this.dashboardId = (query.dashboardId as string) || '';
    this.tabId = id;
    this.tabName = ['topo', 'overview'].includes(id) ? this.$t('服务') : name;
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
    this.routeList[2].selectOption.loading = true;
    const listData = await simpleServiceList({ app_name: this.appName }).catch(() => []);
    this.routeList[2].selectOption.loading = false;
    this.serviceList = listData.map(item => ({
      id: item.service_name,
      name: item.service_name,
      ...item,
    }));
    this.routeList[2].selectOption.selectList = this.serviceList;
  }

  /** 导航栏下拉选择 */
  async handleNavSelect(item: ISelectItem, navId) {
    const { to, from, interval, timezone, refreshInterval, dashboardId } = this.$route.query;
    // 选择应用
    if (navId === 'application') {
      const { id } = this.routeList[1];
      this.appName = item.id;
      const targetRoute = this.$router.resolve({
        name: id,
        query: { 'filter-app_name': this.appName, dashboardId: dashboardId || this.dashboardId, to, from },
      });
      /** 防止出现跳转当前地址导致报错 */
      if (targetRoute.resolved.fullPath !== this.$route.fullPath) {
        this.$router.push({
          name: id,
          query: { 'filter-app_name': this.appName, dashboardId: dashboardId || this.dashboardId, to, from },
        });
      }
    } else {
      this.serviceName = item.id;
      // const { to, from, interval, timezone, refreshInterval, dashboardId } = this.$route.query;
      this.$router.replace({
        name: this.$route.name,
        query: {
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
        },
      });
      this.viewOptions = {
        filters: {
          app_name: item.app_name,
          service_name: item.service_name,
          category: item.category,
          kind: item.kind,
          predicate_value: item.predicate_value,
        },
      };
      this.handleUpdateAppName(this.tabId);
      this.pageKey += 1;
    }
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
            defaultDashboardId={this.dashboardId}
            defaultViewOptions={this.viewOptions}
            isShowSplitPanel={false}
            sceneId={'apm_service'}
            sceneType={'overview'}
            tab2SceneType
            onSceneTypeChange={this.handleSceneTypeChange}
            onTabChange={this.handleUpdateAppName}
            onTitleChange={this.handleTitleChange}
          >
            {globalUrlFeatureMap.APM_SUBMENU && (
              <ApmCommonNavBar
                slot='nav'
                needBack={false}
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
