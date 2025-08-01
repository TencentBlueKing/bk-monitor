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
import { Component, Emit, Mixins, Prop, Provide, ProvideReactive, Ref } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import { addAccessRecord } from 'monitor-api/modules/overview';

import authorityMixinCreate from '../../../mixins/authorityMixin';
import * as grafanaAuth from '../authority-map';
import DashboardAside, { GRAFANA_HOME_ID } from './dashboard-aside';

import type { ISpaceItem } from '../../../types';
import type { IFavListItem } from './fav-list';
import type { TreeMenuItem } from './utils';

// import ResizeLayout from '../../../components/resize-layout/resize-layout';
import './dashboard-container.scss';

interface IEvents {
  onBizChange: number;
  onOpenSpaceManager?: () => void;
}
interface IProps {
  bizIdList: ISpaceItem[];
}
@Component
class DashboardContainer extends Mixins(authorityMixinCreate(grafanaAuth, 'created')) {
  @Prop({ type: Array, default: () => [] }) bizIdList: ISpaceItem[];
  @Ref() bkResizeLayout: any;
  @ProvideReactive('authority') authority: Record<string, boolean> = {};
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Provide('authorityMap') authorityMap = grafanaAuth;
  expend = true;

  handleExpend() {
    this.bkResizeLayout.setCollapse();
    this.expend = !this.expend;
  }

  @Emit('bizChange')
  handleBizChange(bizId: number) {
    return bizId;
  }
  handleGotoDashboard(item: TreeMenuItem) {
    if (!item.children?.length && item.uid) {
      this.handleGotoFavaritate(item as any);
    }
  }
  async handleGotoFavaritate(item: IFavListItem) {
    if (item.uid === GRAFANA_HOME_ID) {
      this.$router.push({
        name: 'grafana-home',
      });
    } else {
      // 新版首页最近使用埋点
      await addAccessRecord({
        function: 'dashboard',
        config: { dashboard_uid: item.uid },
      });
      this.$router.push({
        path: item.url?.startsWith?.('/grafana') ? item.url : `/grafana/d/${item.uid}`,
        params: {
          rawUrl: item.url,
        },
      });
    }
  }

  handleOpenSpace() {
    this.$emit('openSpaceManager');
  }

  render() {
    return (
      <bk-resize-layout
        ref='bkResizeLayout'
        class='dashboard-container'
        border={false}
        initial-divide={this.expend ? 280 : 5}
        max={800}
        min={240}
        placement='left'
        collapsible
        immediate
      >
        <DashboardAside
          slot='aside'
          bizIdList={this.bizIdList}
          onBizChange={this.handleBizChange}
          onOpenSpaceManager={this.handleOpenSpace}
          onSelectedDashboard={this.handleGotoDashboard}
          onSelectedFav={this.handleGotoFavaritate}
        />
        <div
          style='height: 100%'
          slot='main'
        >
          {this.$slots.main}
        </div>
        <div
          class={['toggle-wrap', { expend: this.expend }]}
          slot='collapse-trigger'
          onClick={this.handleExpend}
        >
          {!this.expend && <span class='toggle-wrap-text'>{this.$t('目录')}</span>}
          <i class='icon-monitor icon-arrow-left' />
        </div>
      </bk-resize-layout>
    );
  }
}

export default ofType<IProps, IEvents>().convert(DashboardContainer);
