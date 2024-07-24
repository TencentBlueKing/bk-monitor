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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import introduce from '../../../common/introduce';
import GuidePage from '../../../components/guide-page/guide-page';
import { destroyTimezone } from '../../../i18n/dayjs';
import CommonNavBar from '../../monitor-k8s/components/common-nav-bar';
import CommonPage from '../../monitor-k8s/components/common-page';

import type { IMenuItem, INavItem, IViewOptions } from '../../monitor-k8s/typings';

import './collector-view.scss';

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
@Component
export default class CollectorView extends tsc<object> {
  @Prop({ type: [String, Number], default: '' }) readonly id: string;
  @Prop({ type: String, default: '' }) readonly title: string;

  viewOptions: IViewOptions = {};
  // 导航条设置
  routeList: INavItem[] = [
    // { id: 'collect-config', name: '数据采集' },
    // { id: 'collect-config', name: '' },
    { id: '', name: '', subName: '' },
  ];

  // sceneId
  sceneId = '';

  navName = 'loading...';
  menuList: IMenuItem[] = [
    {
      id: 'source-manage',
      name: this.$t('数据源管理') as string,
      show: true,
    },
  ];
  // 是否显示引导页
  get showGuidePage() {
    return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
  }

  get customQuery() {
    return JSON.parse((this.$route.query.customQuery as string) || '{}');
  }

  get bizId() {
    return this.customQuery.bizId || this.$store.getters.bizId;
  }

  // route navbar title change
  headerTitleChange(v: string) {
    this.routeList[0].subName = v;
    // this.navName = `${this.configName} #${v}`;
  }
  beforeRouteEnter(to, from, next) {
    next((vm: CollectorView) => {
      vm.viewOptions = {
        filters: {
          bk_biz_id: vm.bizId,
        },
      };
      vm.sceneId = `collect_${to.params.id}`;
      vm.routeList[0].name = to.query.name || '';
    });
  }
  beforeRouteLeave(to, from, next) {
    destroyTimezone();
    next();
  }
  handleMenuSelect({ id }) {
    if (id === 'source-manage') {
      this.$router.push({
        name: 'collect-config-edit',
        params: {
          title: this.$route.query.name as string,
          id: this.$route.params.id,
          pluginId: this.customQuery.pluginId as string,
        },
      });
    }
  }

  render() {
    if (this.showGuidePage) return <GuidePage guideData={introduce.data.performance.introduce} />;
    return (
      <div class='collect-view'>
        {this.sceneId && (
          <CommonPage
            defaultViewOptions={this.viewOptions}
            isMergeMenuList={true}
            menuList={this.menuList}
            sceneId={this.sceneId}
            sceneType={'detail'}
            showListMenu={this.bizId === this.$store.getters.bizId}
            title={this.$tc('数据采集')}
            onMenuSelect={this.handleMenuSelect}
            // onPageTitleChange={this.handlePageTitleChange}
            onTitleChange={this.headerTitleChange}
          >
            <CommonNavBar
              slot='nav'
              navMode={'share'}
              needBack={true}
              needShadow={true}
              routeList={this.routeList}
              needCopyLink
            />
          </CommonPage>
        )}
      </div>
    );
  }
}
