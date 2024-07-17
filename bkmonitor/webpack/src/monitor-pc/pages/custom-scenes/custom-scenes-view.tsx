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

import introduce from '../../common/introduce';
import GuidePage from '../../components/guide-page/guide-page';
import { destroyTimezone } from '../../i18n/dayjs';
import CommonNavBar from '../monitor-k8s/components/common-nav-bar';
import CommonPage from '../monitor-k8s/components/common-page';

import type { IMenuItem, INavItem, IViewOptions } from '../monitor-k8s/typings';

import './custom-scenes-view.scss';

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);

enum ESceneType {
  customEvent = 'custom_event',
  customMetric = 'custom_metric',
  plugin = 'plugin',
}
@Component
export default class CustomScenesView extends tsc<object> {
  @Prop({ type: [String, Number], default: '' }) readonly id: string;
  @Prop({ type: String, default: '' }) readonly title: string;

  viewOptions: IViewOptions = {};
  // 导航条设置
  routeList: INavItem[] = [
    // { id: 'custom-scenes', name: '自定义场景' },
    // { id: 'custom-scenes', name: '' },
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
  // route navbar title change
  headerTitleChange(v: string) {
    this.routeList[0].subName = v;
  }
  beforeRouteEnter(to, from, next) {
    next((vm: CustomScenesView) => {
      if (vm.showGuidePage) return;
      vm.viewOptions = {
        filters: {},
      };
      vm.sceneId = to.params.id;
      vm.routeList[0].name = to.query.name || '';
    });
  }
  beforeRouteLeave(to, from, next) {
    destroyTimezone();
    next();
  }
  handleMenuSelect({ id }) {
    if (id === 'source-manage') {
      this.handleToCollect();
    }
  }

  handleToCollect() {
    const {
      query: { customQuery },
    } = this.$route;
    const pluginTypes = ['snmp_trap', 'log'];
    const { sceneType, sceneId, pluginType } = JSON.parse((customQuery as string) || '{}');
    if (sceneType === ESceneType.plugin) {
      if (pluginTypes.includes((pluginType as string).toLowerCase())) {
        this.$router.push({
          name: 'collect-config',
          query: {
            id: sceneId,
          },
        });
      } else {
        this.$router.push({
          name: 'collect-config',
          params: {
            pluginId: sceneId as string,
          },
        });
      }
    } else {
      const types = {
        [ESceneType.customMetric]: {
          name: 'custom-detail-timeseries',
          type: 'customTimeSeries',
        },
        [ESceneType.customEvent]: {
          name: 'custom-detail-event',
          type: 'customEvent',
        },
      };
      this.$router.push({
        name: types[sceneType as ESceneType].name,
        params: {
          id: sceneId as string,
          type: types[sceneType as ESceneType].type,
        },
      });
    }
  }

  render() {
    if (this.showGuidePage) return <GuidePage guideData={introduce.data['custom-scenes'].introduce} />;
    return (
      <div class='custom-scenes-view-page'>
        {this.sceneId && (
          <CommonPage
            defaultViewOptions={this.viewOptions}
            isMergeMenuList={true}
            menuList={this.menuList}
            sceneId={this.sceneId}
            sceneType={'detail'}
            title={this.$tc('自定义场景')}
            onMenuSelect={this.handleMenuSelect}
            // onPageTitleChange={this.handlePageTitleChange}
            onTitleChange={this.headerTitleChange}
          >
            <CommonNavBar
              slot='nav'
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
