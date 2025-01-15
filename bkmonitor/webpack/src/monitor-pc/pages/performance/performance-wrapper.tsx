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
import { Component, Prop, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils/utils';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';

import introduce from '../../common/introduce';
import GuidePage from '../../components/guide-page/guide-page';
import AlarmTools from '../monitor-k8s/components/alarm-tools';
import DashboardTools from '../monitor-k8s/components/dashboard-tools';
import PageTitle from '../monitor-k8s/components/page-title';
import SplitPanel from '../monitor-k8s/components/split-panel';
import { type IBookMark, type ITabItem, SPLIT_MAX_WIDTH, SPLIT_MIN_WIDTH } from '../monitor-k8s/typings';
import Performance from './performance.vue';

import './performance-wrapper.scss';

@Component
export default class PerformanceWrapper extends tsc<object> {
  // 监控左侧栏是否收缩配置 自愈默认未收缩
  @Prop({ default: false, type: Boolean }) toggleSet: boolean;
  activeTab = 'list';
  tabList: ITabItem[] = [];
  loading = false;
  sceneData: IBookMark = { id: '', panels: [], name: '' };

  isSplitPanel = false;
  splitPanelWidth = 0;
  defaultPanelWidth = 0;

  @ProvideReactive('refleshInterval') refleshInterval = -1;
  @ProvideReactive('refleshImmediate') refleshImmediate = '';

  get alarmToolsPanel() {
    const data = {
      title: this.$t('主机列表'),
      type: 'dict',
      targets: [
        {
          datasource: 'host',
          dataType: 'dict',
          api: 'scene_view.getStrategyAndEventCount',
          data: {
            scene_id: 'host',
          },
        },
      ],
    };
    return new PanelModel(data as any);
  }
  // 是否显示引导页
  get showGuidePage() {
    return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
  }
  async created() {
    this.loading = true;
    this.tabList = [
      {
        id: 'list',
        name: window.i18n.tc('主机列表'),
      },
    ];
    this.loading = false;
  }
  mounted() {
    this.defaultPanelWidth = this.$el.getBoundingClientRect().width / 2;
    this.splitPanelWidth = this.defaultPanelWidth;
  }
  // 立刻刷新
  handleImmediateReflesh() {
    this.refleshImmediate = random(10);
  }
  handleTabChange(v: ITabItem) {
    this.activeTab = v.id.toString();
  }
  handleSplitPanel(v: boolean) {
    this.isSplitPanel = v;
    this.splitPanelWidth = v ? this.defaultPanelWidth : 0;
  }
  handleDragMove(v: number) {
    this.splitPanelWidth = v;
    this.isSplitPanel = v > 0;
  }

  render() {
    if (this.showGuidePage) return <GuidePage guideData={introduce.data.performance.introduce} />;
    return (
      <div class='performance-wrapper'>
        <PageTitle
          activeTab={this.activeTab}
          showFilter={false}
          showInfo={false}
          showSearch={false}
          showSelectPanel={false}
          tabList={this.tabList}
          onTabChange={this.handleTabChange}
        >
          <span slot='title'>{this.$t('主机监控')}</span>
          <AlarmTools
            style={{ marginRight: '8px' }}
            slot='tools'
            panel={this.alarmToolsPanel}
          />
          <DashboardTools
            slot='tools'
            isSplitPanel={this.isSplitPanel}
            refleshInterval={this.refleshInterval}
            showDownSampleRange={false}
            showListMenu={false}
            showTimeRange={false}
            onImmediateReflesh={this.handleImmediateReflesh}
            onRefleshChange={v => (this.refleshInterval = v)}
            onSplitPanelChange={this.handleSplitPanel}
          />
        </PageTitle>
        <div class='performance-wrapper-container'>
          <Performance class='table-wrapper' />
          <div
            style={{
              width: `${this.splitPanelWidth}px`,
              display: this.splitPanelWidth > SPLIT_MIN_WIDTH && this.isSplitPanel ? 'flex' : 'none',
            }}
            class='split-panel-wrapper'
          >
            {this.isSplitPanel ? (
              <SplitPanel
                splitMaxWidth={Math.max(this.splitPanelWidth + 300, SPLIT_MAX_WIDTH)}
                toggleSet={this.toggleSet}
                onDragMove={this.handleDragMove}
              />
            ) : undefined}
          </div>
        </div>
      </div>
    );
  }
}
