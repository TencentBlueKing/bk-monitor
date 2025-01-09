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

import { destroyTimezone } from '../../i18n/dayjs';
import CommonNavBar from './components/common-nav-bar';
import CommonPage from './components/common-page';

import type { INavItem, IViewOptions } from './typings';

import './monitor-k8s-detail.scss';

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
@Component
export default class MonitorK8s extends tsc<object> {
  @Prop({ type: String, default: '' }) id: string;

  viewOptions: IViewOptions = {};
  // 导航条设置
  routeList: INavItem[] = [];

  // 是否展示引导页
  showGuidePages = false;

  // route navbar title change
  headerTitleChange(v: string) {
    this.routeList[this.routeList.length - 1].name = v;
  }
  // 页签名变更
  handlePageTitleChange(v: string, query: Record<string, any> = {}) {
    const routeItem = this.routeList[1];
    routeItem.name = v;
    routeItem.query = query;
  }
  beforeRouteEnter(to, from, next) {
    next((vm: MonitorK8s) => {
      vm.routeList = [
        {
          id: 'k8s',
          name: '容器监控',
        },
        {
          id: 'k8s',
          name: 'container',
          query: {},
        },
        {
          id: '',
          name: 'loading...',
        },
      ];
      vm.viewOptions = {};
    });
  }
  beforeRouteLeave(to, from, next) {
    destroyTimezone();
    next();
  }
  render() {
    return (
      <div class='monitor-k8s-detail'>
        <CommonPage
          defaultViewOptions={this.viewOptions}
          sceneId={'kubernetes'}
          sceneType={'detail'}
          onPageTitleChange={this.handlePageTitleChange}
          onTitleChange={this.headerTitleChange}
        >
          <CommonNavBar
            slot='nav'
            needBack={false}
            needShadow={true}
            routeList={this.routeList}
            needCopyLink
          />
        </CommonPage>
      </div>
    );
  }
}
