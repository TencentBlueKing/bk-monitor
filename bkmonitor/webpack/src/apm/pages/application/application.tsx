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
import { Component, InjectReactive, Mixins, Prop, Provide, Ref } from 'vue-property-decorator';

import { random } from '../../../monitor-common/utils/utils';
import type { TimeRangeType } from '../../../monitor-pc/components/time-range/time-range';
import { handleTransformToTimestamp } from '../../../monitor-pc/components/time-range/utils';
import { destroyTimezone } from '../../../monitor-pc/i18n/dayjs';
import CommonAlert from '../../../monitor-pc/pages/monitor-k8s/components/common-alert';
import CommonNavBar from '../../../monitor-pc/pages/monitor-k8s/components/common-nav-bar';
import CommonPage, { SceneType } from '../../../monitor-pc/pages/monitor-k8s/components/common-page-new';
import { INavItem } from '../../../monitor-pc/pages/monitor-k8s/typings';
import { IViewOptions } from '../../../monitor-ui/chart-plugins/typings';
import ListMenu, { IMenuItem } from '../../components/list-menu/list-menu';
import authorityMixinCreate from '../../mixins/authorityMixin';
import applicationStore from '../../store/modules/application';
import AppAddForm from '../home/app-add-form';

import * as authorityMap from './../home/authority-map';
import NoDataGuide from './app-add/no-data-guide';

import './application.scss';

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
@Component
export default class Application extends Mixins(authorityMixinCreate(authorityMap)) {
  @Prop({ type: String, default: '' }) id: string;

  @Ref() commonPageRef: CommonPage;

  @Provide('authority') authority;
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  sceneType: SceneType = 'overview';

  backToOverviewKey = random(8);

  viewOptions: IViewOptions = {};
  // 导航条设置
  routeList: INavItem[] = [];

  // 是否展示引导页
  showGuidePages = false;

  // 显示无数据指引弹窗
  showGuideDialog = false;

  /** 视图无数据 */
  viewHasNoData = true;
  appInfo: Record<string, any> = null;

  /** 应用名 */
  appName = '';
  /** 选中的插件id */
  pluginId = '';
  /** 新建应用弹窗 */
  showAddDialog = false;
  /** 前置条件 */
  isReady = false;
  /** 当前tab */
  tabId = '';
  tabName: string | TranslateResult = '';
  /** 定位详情文案 */
  subName = '';
  // menu list
  menuList: IMenuItem[] = [
    {
      id: 'basicConfiguration',
      name: window.i18n.tc('基础配置')
    },
    {
      id: 'customService',
      name: window.i18n.tc('自定义服务')
    },
    {
      id: 'storageState',
      name: window.i18n.tc('存储状态')
    },
    {
      id: 'dataStatus',
      name: window.i18n.tc('数据状态')
    }
  ];

  get pluginsList() {
    return applicationStore.pluginsListGetter || [];
  }
  /** 页面权限校验实例资源 */
  get authorityResource() {
    return { application_name: this.$route.query?.['filter-app_name'] || '' };
  }
  get positonText() {
    // eslint-disable-next-line no-nested-ternary
    const value =
      this.sceneType === 'overview'
        ? // eslint-disable-next-line no-nested-ternary
          this.tabName === window.i18n.tc('服务')
          ? window.i18n.tc('列表')
          : this.tabId === 'topo'
            ? window.i18n.tc('拓扑')
            : window.i18n.tc('概览')
        : this.subName;
    return `${this.tabName}：${value}`;
  }

  beforeRouteEnter(to, from, next) {
    const { query } = to;
    const appName = query['filter-app_name'] as string;
    next(async (vm: Application) => {
      vm.routeList = [
        {
          id: 'home',
          name: 'APM'
        },
        {
          id: 'application',
          name: `${window.i18n.tc('应用')}：${appName}`,
          subName: ''
        }
      ];
      vm.viewOptions = {};
      const { query } = to;
      vm.appName = query['filter-app_name'] as string;
      applicationStore.getPluginList();
      vm.handleGetAppInfo();
    });
  }
  beforeRouteLeave(to, from, next) {
    destroyTimezone();
    next();
  }
  /** 切换时间范围重新请求以获取无数据状态 */
  handelTimeRangeChange() {
    this.handleGetAppInfo();
  }
  /** 获取应用信息 */
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

    if (data) {
      this.appInfo = data;
      this.viewHasNoData = this.appInfo.data_status === 'no_data';
      this.isReady = true;
    }
  }
  /** 跳转接入服务页面 */
  handleAddService() {
    this.$router.push({
      name: 'service-add',
      params: {
        appName: this.appName
      }
    });
  }
  handleSecendTypeChange(type) {
    this.sceneType = type;
  }
  /** 详情返回列表操作刷新列表的数据 */
  handleRouterBack() {
    this.backToOverviewKey = random(8);
  }
  handleTitleChange(title) {
    this.subName = title;
  }
  handleSceneTabChange(id, name = '') {
    this.tabId = id;
    this.tabName = ['topo', 'overview'].includes(id) ? this.$t('应用') : name;
  }
  /** 更多设置 */
  handleSettingsMenuSelect(option) {
    this.$router.push({
      name: 'application-config',
      params: {
        id: this.appInfo.application_id
      },
      query: {
        active: option.id
      }
    });
  }
  handleCloseGuideDialog() {
    this.showGuideDialog = false;
  }
  render() {
    return (
      <div class='application'>
        {
          <CommonPage
            ref='commonPageRef'
            sceneId={'apm_application'}
            sceneType={'overview'}
            isShowSplitPanel={false}
            defaultViewOptions={this.viewOptions}
            backToOverviewKey={this.backToOverviewKey}
            tab2SceneType
            onTabChange={this.handleSceneTabChange}
            onTimeRangeChange={this.handelTimeRangeChange}
            onSceneTypeChange={this.handleSecendTypeChange}
            onTitleChange={this.handleTitleChange}
          >
            <CommonNavBar
              slot='nav'
              routeList={this.routeList}
              needShadow={true}
              needCopyLink
              needBack={false}
              positionText={this.positonText}
            />
            {this.isReady && this.viewHasNoData && (
              <div slot='noData'>
                <CommonAlert class='no-data-alert'>
                  <div slot='title'>
                    <bk-spin
                      theme='warning'
                      size='mini'
                    />
                    {this.$t('当前数据还未加载完成，如数据长时间未加载出来可')}
                    <span
                      class='link'
                      onClick={() => (this.showGuideDialog = true)}
                    >
                      {this.$t('查看操作指引')}
                    </span>
                  </div>
                </CommonAlert>
              </div>
            )}
            {!this.readonly && !!this.appName && (
              <div
                class='application-tools'
                slot='buttonGroups'
              >
                <bk-button
                  size='small'
                  theme='primary'
                  onClick={this.handleAddService}
                >
                  <span class='add-service-btn'>
                    <i class='icon-monitor icon-mc-add add-service-icon'></i>
                    <span>{this.$t('接入服务')}</span>
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
          </CommonPage>
        }
        <AppAddForm
          pluginId={this.pluginId}
          v-model={this.showAddDialog}
        ></AppAddForm>
        <bk-dialog
          value={this.showGuideDialog}
          mask-close={true}
          ext-cls='no-data-guide-dialog'
          width={1280}
          position={{ top: 50 }}
          show-footer={false}
          on-cancel={this.handleCloseGuideDialog}
        >
          <NoDataGuide
            type='noData'
            appName={this.appInfo?.app_name}
          />
        </bk-dialog>
      </div>
    );
  }
}
