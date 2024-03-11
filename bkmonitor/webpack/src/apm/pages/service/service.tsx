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
import { TranslateResult } from 'vue-i18n';
import { Component, InjectReactive, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { random } from 'monitor-common/utils/utils';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import { destroyTimezone } from 'monitor-pc/i18n/dayjs';
import CommonNavBar from 'monitor-pc/pages/monitor-k8s/components/common-nav-bar';
import CommonPage, { SceneType } from 'monitor-pc/pages/monitor-k8s/components/common-page-new';
import { INavItem } from 'monitor-pc/pages/monitor-k8s/typings';
import { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import ListMenu, { IMenuItem } from '../../components/list-menu/list-menu';
import applicationStore from '../../store/modules/application';
import { IAppSelectOptItem } from '../home/app-select';

import './service.scss';

// interface IServiceConfigItem{
//   id: string;
//   name: TranslateResult;
//   serviceName: TranslateResult;
//   params: IServiceParams;
// }

interface IServiceParams {
  is_relation: boolean; // 是否关联
  target: string; // 跳转方式
  url: string; // 跳转地址
}

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
@Component
export default class Service extends tsc<{}> {
  @Prop({ type: String, default: '' }) id: string;

  @Ref() commonPageRef: CommonPage;
  @InjectReactive('readonly') readonly readonly: boolean;
  viewOptions: IViewOptions = {};
  // 导航条设置
  routeList: INavItem[] = [];

  // 是否展示引导页
  showGuidePages = false;

  backToOverviewKey = random(10);

  sceneType: SceneType = 'overview';

  appName = '';
  pluginId = '';
  dashboardId = '';
  tabId = '';
  tabName: string | TranslateResult = '';
  subName = '';
  // menu list
  menuList: IMenuItem[] = [
    {
      id: 'basic',
      name: window.i18n.tc('基本设置')
    }
  ];

  /** 列表 */
  get pluginsList(): IAppSelectOptItem[] {
    return applicationStore.pluginsListGetter || [];
  }

  get bizId() {
    return this.$store.getters.bizId;
  }

  get positonText() {
    const label = this.tabName;
    // eslint-disable-next-line no-nested-ternary
    const value =
      this.sceneType === 'overview'
        ? this.tabId === 'topo'
          ? window.i18n.tc('拓扑')
          : window.i18n.tc('概览')
        : this.subName;
    return `${label}：${value}`;
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
          name: 'APM'
        },
        {
          id: 'application',
          name: `${window.i18n.tc('应用')}：${appName}`,
          query: {
            'filter-app_name': appName
          }
        },
        {
          id: 'service',
          name: `${window.i18n.tc('服务')}：${serviceName}`
        }
      ];
      vm.viewOptions = {};
      vm.appName = query['filter-app_name'] as string;
      vm.handleGetAppInfo();
    };
    next(nextTo);
  }
  beforeRouteLeave(to, from, next) {
    destroyTimezone();
    next();
  }
  /** 切换时间范围重新请求以获取无数据状态 */
  handelTimeRangeChange() {
    this.handleGetAppInfo();
  }

  /** 通过应用信息接口获取无数据状态 */
  async handleGetAppInfo() {
    let queryTimeRange;
    const { from, to } = this.$route.query;
    if (from && to) {
      const timeRanges = [from, to];
      const formatValue = handleTransformToTimestamp(timeRanges as TimeRangeType);
      if (formatValue) {
        queryTimeRange = formatValue;
      }
    }
    const timeRange = queryTimeRange || handleTransformToTimestamp(this.commonPageRef?.timeRange);
    const [startTime, endTime] = timeRange;
    const params = {
      app_name: this.appName,
      start_time: startTime,
      end_time: endTime
    };
    const data = await applicationStore.getAppInfo(params);

    /** 当前应用无数据跳转应用无数据页面展示 */
    if (data && data.data_status === 'no_data' && data.profiling_data_status === 'no_data') {
      this.$router.push({
        name: 'application',
        query: {
          'filter-app_name': this.appName
        }
      });
    }
  }
  /** 更新当前路由的信息 */
  async handleUpdateAppName(id, name = '') {
    await this.$nextTick();
    const { query } = this.$route;
    this.appName = (query['filter-app_name'] as string) || '';
    this.dashboardId = (query.dashboardId as string) || '';
    this.tabId = id;
    this.tabName = ['topo', 'overview'].includes(id) ? this.$t('服务') : name;
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
        service_name: (query['filter-service_name'] as string) || ''
      }
    });
  }
  /** 详情返回列表操作刷新列表的数据 */
  handleRouterBack() {
    this.backToOverviewKey = random(8);
  }
  handleSecendTypeChange(type) {
    this.sceneType = type;
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
            ref='commonPageRef'
            sceneId={'apm_service'}
            sceneType={'overview'}
            isShowSplitPanel={false}
            backToOverviewKey={this.backToOverviewKey}
            defaultViewOptions={this.viewOptions}
            tab2SceneType
            // eslint-disable-next-line @typescript-eslint/no-misused-promises
            onTabChange={this.handleUpdateAppName}
            onTimeRangeChange={this.handelTimeRangeChange}
            onTitleChange={this.handleTitleChange}
            onSceneTypeChange={this.handleSecendTypeChange}
          >
            <CommonNavBar
              slot='nav'
              routeList={this.routeList}
              needShadow={true}
              needCopyLink
              needBack={false}
              positionText={this.positonText}
            />
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
