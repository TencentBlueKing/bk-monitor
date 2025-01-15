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

import { destroyTimezone } from '../../../i18n/dayjs';
import CommonNavBar from '../../monitor-k8s/components/common-nav-bar';
import CommonPage from '../../monitor-k8s/components/common-page';

import type { IMenuItem, INavItem, IViewOptions } from '../../monitor-k8s/typings';

import './event-view.scss';

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
@Component
export default class EventView extends tsc<object> {
  @Prop({ type: [String, Number], default: '' }) id: string;

  viewOptions: IViewOptions = {};
  // 导航条设置
  routeList: INavItem[] = [];

  // sceneId
  sceneId = '';

  menuList: IMenuItem[] = [
    {
      id: 'source-manage',
      name: this.$t('数据源管理') as string,
      show: true,
    },
  ];

  handleMenuSelect({ id }) {
    if (id === 'source-manage') {
      this.$router.push({
        name: 'custom-detail-event',
        params: {
          id: this.$route.params.id || '',
          type: 'customEvent',
        },
      });
    }
  }

  // route navbar title change
  headerTitleChange(v: string) {
    this.routeList[0].subName = v;
  }
  beforeRouteEnter(to, from, next) {
    next((vm: EventView) => {
      vm.routeList = [
        {
          id: '',
          name: '',
          subName: '',
        },
      ];
      // vm.routeList[1].name = to.query.name || '';
      vm.viewOptions = {};
      vm.sceneId = `custom_event_${to.params.id}`;
      vm.routeList[0].name = `${vm.$route.query.name}`;
    });
  }
  beforeRouteLeave(to, from, next) {
    destroyTimezone();
    next();
  }
  render() {
    return (
      <div class='event-view'>
        {this.sceneId && (
          <CommonPage
            defaultViewOptions={this.viewOptions}
            isMergeMenuList={true}
            menuList={this.menuList}
            sceneId={this.sceneId}
            sceneType={'detail'}
            title={this.$tc('自定义事件')}
            onMenuSelect={this.handleMenuSelect}
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
