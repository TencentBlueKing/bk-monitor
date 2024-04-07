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

import authorityMixinCreate from '../../../mixins/authorityMixin';
import { ISpaceItem } from '../../../types';
import * as grafanaAuth from '../authority-map';

import DashboardAside, { GRAFANA_HOME_ID } from './dashboard-aside';
import { IFavListItem } from './fav-list';
import { TreeMenuItem } from './utils';

// import ResizeLayout from '../../../components/resize-layout/resize-layout';
import './dashboard-container.scss';

interface IProps {
  bizIdList: ISpaceItem[];
}
interface IEvents {
  onBizChange: number;
  onOpenSpaceManager?: void;
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
  handleGotoFavaritate(item: IFavListItem) {
    if (item.uid === GRAFANA_HOME_ID) {
      this.$router.push({
        name: 'grafana-home'
      });
    } else {
      this.$router.push({
        path: `/grafana/d/${item.uid}`
      });
    }
  }

  handleOpenSpace() {
    this.$emit('openSpaceManager');
  }

  render() {
    return (
      <bk-resize-layout
        class='dashboard-container'
        ref='bkResizeLayout'
        min={240}
        max={800}
        initial-divide={this.expend ? 280 : 5}
        border={false}
        collapsible
        immediate
        placement='left'
      >
        <DashboardAside
          slot='aside'
          bizIdList={this.bizIdList}
          onSelectedFav={this.handleGotoFavaritate}
          onSelectedDashboard={this.handleGotoDashboard}
          onBizChange={this.handleBizChange}
          onOpenSpaceManager={this.handleOpenSpace}
        />
        <div
          slot='main'
          style='height: 100%'
        >
          {this.$slots.main}
        </div>
        <div
          slot='collapse-trigger'
          class={['toggle-wrap', { expend: this.expend }]}
          onClick={this.handleExpend}
        >
          {!this.expend && <span class='toggle-wrap-text'>{this.$t('目录')}</span>}
          <i class='icon-monitor icon-arrow-left'></i>
        </div>
      </bk-resize-layout>
    );
  }
}

export default ofType<IProps, IEvents>().convert(DashboardContainer);
