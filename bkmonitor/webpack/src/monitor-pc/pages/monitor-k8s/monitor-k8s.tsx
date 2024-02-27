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
import { Component, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { random } from 'monitor-common/utils/utils';

import { handleGotoLink } from '../../common/constant';
import introduce from '../../common/introduce';
import GuidePage from '../../components/guide-page/guide-page';
import { destroyTimezone } from '../../i18n/dayjs';

import CommonNavBar from './components/common-nav-bar';
import CommonPage from './components/common-page-new';
import { INavItem, IViewOptions, SceneType } from './typings';

import './monitor-k8s.scss';

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
@Component
export default class MonitorK8s extends tsc<{}> {
  @Prop({ type: String, default: '' }) id: string;
  @InjectReactive('readonly') readonly readonly: boolean;
  viewOptions: IViewOptions = {};
  // 导航条设置
  routeList: INavItem[] = [];
  sceneId = 'kubernetes';
  sceneType: SceneType = 'overview';

  /** 用于详情返回同路由刷新页面数据 */
  backToOverviewKey = random(8);

  /** 当前tab */
  tabName: string | TranslateResult = '';
  /** 定位详情文案 */
  subName = '';

  get positonText() {
    const label = this.tabName;
    const value = this.sceneType === 'overview' ? window.i18n.tc('概览') : this.subName;
    return `${label}：${value}`;
  }
  // 获取引导页状态
  get showGuidePage() {
    return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
  }
  beforeRouteEnter(to, from, next) {
    next((vm: MonitorK8s) => {
      if (vm.showGuidePage) return;
      vm.routeList = [
        {
          id: 'k8s',
          name: 'Kubernetes',
          subName: ''
        }
      ];
      const { sceneId = 'kubernetes', sceneType = 'overview' } = to.query;
      vm.sceneId = sceneId;
      vm.sceneType = sceneType;
      vm.viewOptions = {
        method: 'sum_without_time'
      };
    });
  }
  beforeRouteLeave(to, from, next) {
    destroyTimezone();
    next();
  }
  handleTitleChange(title) {
    this.subName = title;
  }
  handleSceneTabChange(id, name = '') {
    this.tabName = name;
  }
  /** 详情返回列表操作刷新列表的数据 */
  handleRouterBack() {
    this.backToOverviewKey = random(8);
  }
  handleSecendTypeChange(type) {
    this.sceneType = type;
  }
  handleAddCluster() {
    handleGotoLink('addClusterMd');
  }
  render() {
    if (this.showGuidePage) return <GuidePage guideData={introduce.data.k8s.introduce} />;
    return (
      <div class='monitor-k8s'>
        <CommonPage
          sceneId={this.sceneId}
          sceneType={this.sceneType}
          defaultViewOptions={this.viewOptions}
          backToOverviewKey={this.backToOverviewKey}
          onSceneTypeChange={this.handleSecendTypeChange}
          tab2SceneType
          toggleTabSearchFilterKeys={['bcs_cluster_id']}
          onTitleChange={this.handleTitleChange}
          onTabChange={this.handleSceneTabChange}
        >
          <CommonNavBar
            slot='nav'
            routeList={this.routeList}
            needShadow={true}
            callbackRouterBack={this.handleRouterBack}
            needCopyLink
            positionText={this.positonText}
          />
          {!this.readonly && (
            <bk-button
              style='margin-left: 8px;'
              slot='dashboardTools'
              size='small'
              theme='primary'
              onClick={this.handleAddCluster}
            >
              <span class='add-btn'>
                <i class='icon-monitor icon-mc-add add-icon'></i>
                <span>{this.$t('新建集群')}</span>
              </span>
            </bk-button>
          )}
        </CommonPage>
      </div>
    );
  }
}
