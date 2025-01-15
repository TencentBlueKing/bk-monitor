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
import { Component, Mixins, Prop, Provide, ProvideReactive } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import { random } from 'monitor-common/utils/utils';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';

import introduce from '../../common/introduce';
import GuidePage from '../../components/guide-page/guide-page';
import authorityMixinCreate from '../../mixins/authorityMixin';
import AlarmTools from '../monitor-k8s/components/alarm-tools';
import HeaderTool from '../monitor-k8s/components/dashboard-tools';
import PageTitle from '../monitor-k8s/components/page-title';
import SplitPanel from '../monitor-k8s/components/split-panel';
import { type DashboardMode, type IMenuItem, SPLIT_MAX_WIDTH, SPLIT_MIN_WIDTH } from '../monitor-k8s/typings';
import { type ITabItem, type IUptimeCheckType, UPTIME_CHECK_LIST } from '../monitor-k8s/typings/tools';
import * as uptimeAuth from './authority-map';
import UptimeCheckNode from './uptime-check-node';
import UptimeCheckTask from './uptime-check-task';

import './uptime-check.scss';

export type IActive = IUptimeCheckType['node'] | IUptimeCheckType['task'];

@Component({
  name: 'UptimeCheck',
})
class UptimeCheck extends Mixins(authorityMixinCreate(uptimeAuth)) {
  @Prop({ default: false, type: Boolean }) toggleSet: boolean;
  @ProvideReactive('authority') authority: Record<string, boolean> = {};
  @Provide('authorityMap') authorityMap = { ...uptimeAuth };
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Provide('uptimeAuth') uptimeAuth;

  active: IActive = 'uptime-check-task';
  isActiveSet = false; // 用于判断是否获取完url的值
  loading = false;
  dashboardMode: DashboardMode = 'chart';

  // 用于刷新数据的key
  refreshKeys = {
    'uptime-check-task': random(8),
    'uptime-check-node': random(8),
  };

  // 分屏
  isSplitPanel = false;
  splitPanelWidth = 0;
  defaultPanelWidth = 0;

  isTaskGroup = false;

  // 自动刷新
  refleshInstance = null;

  // 节点名称 用于任务列表搜索
  nodeName = '';

  menuList: IMenuItem[] = [
    {
      id: 'task-group-edit',
      name: this.$tc('编辑'),
      show: true,
    },
    {
      id: 'task-group-delete',
      name: this.$tc('解散任务组'),
      show: true,
    },
  ];

  get alarmToolsPanel() {
    const data = {
      title: this.$t('拨测列表'),
      type: 'dict',
      targets: [
        {
          datasource: 'host',
          dataType: 'dict',
          api: 'scene_view.getStrategyAndEventCount',
          data: {
            scene_id: 'uptime_check',
          },
        },
      ],
    };
    return new PanelModel(data as any);
  }
  get showGuidePage() {
    return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
  }

  beforeRouteEnter(to, from, next) {
    next((vm: UptimeCheck) => {
      if (vm.showGuidePage) return;
      if (['uptime-check-task-edit', 'uptime-check-task-detail', 'uptime-check-node-edit'].includes(from.name)) {
        // 从详情页面回来时保留缓存值
        vm.active = to.query.dashboardId || 'uptime-check-task';
        vm.handleResetRouteQuery();
        return;
      }
      const query = from.name ? from.query : to.query;
      vm.dashboardMode = query.dashboardMode || 'chart';
      vm.active = query.dashboardId || 'uptime-check-task';
      vm.$nextTick(() => {
        /* 无需缓存任务组展开状态 */
        (vm.$refs.uptimeCheckTaskRef as any)?.handleBackGroup?.();
      });
    });
  }
  // 分屏start
  activated() {
    this.isActiveSet = true;
    this.defaultPanelWidth = this.$el.getBoundingClientRect().width / 2;
    this.splitPanelWidth = this.defaultPanelWidth;
  }

  deactivated() {
    window.clearInterval(this.refleshInstance);
    this.refleshInstance = null;
    this.isActiveSet = false;
  }

  async handleFullscreen() {
    if (!document.fullscreenElement) {
      this.$store.commit('app/SET_FULL_SCREEN', true);
      await document.body.requestFullscreen();
    } else if (document.exitFullscreen) {
      await document.exitFullscreen();
      this.$store.commit('app/SET_FULL_SCREEN', false);
    }
  }
  handleSplitPanel(v: boolean) {
    this.isSplitPanel = v;
    this.splitPanelWidth = v ? this.defaultPanelWidth : 0;
  }
  handleDragMove(v: number) {
    this.splitPanelWidth = v;
    this.isSplitPanel = v > 0;
  }
  // 分屏end

  handleTabChangeProxy(item: ITabItem) {
    this.handleTabChange(item.id as IActive);
  }
  // 切换任务或节点
  handleTabChange(v: IActive) {
    this.active = v;
    this.handleResetRouteQuery();
  }
  // 重新载入节点或者任务数据
  handleRefreshData(v: IActive) {
    this.refreshKeys[v] = random(8);
  }

  handleRefleshChange(v) {
    window.clearInterval(this.refleshInstance);
    this.refleshInstance = null;
    if (v <= 0) return;
    this.refleshInstance = setInterval(() => {
      this.handleImmediateReflesh();
    }, v);
  }
  handleImmediateReflesh() {
    this.refreshKeys['uptime-check-node'] = random(8);
    this.refreshKeys['uptime-check-task'] = random(8);
  }

  // 带上节点名称跳转到任务列表
  handleNodeNameChange(v: string) {
    this.nodeName = v;
    if (v) {
      this.dashboardMode = 'chart';
      this.handleTabChange('uptime-check-task');
    }
  }
  handlePanelModeChange(v: boolean) {
    this.dashboardMode = v ? 'list' : 'chart';
    this.handleResetRouteQuery();
  }
  handleResetRouteQuery() {
    this.$router.replace({
      name: this.$route.name,
      query: {
        dashboardMode: this.dashboardMode,
        dashboardId: this.active,
        key: random(10),
      },
    });
  }

  /**
   *
   * @param menuItem
   * 点击菜单
   */
  handleMenuSelect(menuItem: IMenuItem) {
    if (menuItem.id === 'task-group-edit') {
      (this.$refs.uptimeCheckTaskRef as any)?.handleMenuSelectChange('edit');
    } else {
      (this.$refs.uptimeCheckTaskRef as any)?.handleMenuSelectChange('delete');
    }
  }

  /**
   *
   * 获取是否分组状态
   */
  fetchTaskGroupTask(v: boolean) {
    this.isTaskGroup = v;
  }
  getContent(active: string) {
    switch (active) {
      case 'uptime-check-node':
        return (
          <UptimeCheckNode
            refreshKey={`${this.refreshKeys[UPTIME_CHECK_LIST[1].id]}__${this.$store.getters.bizId}`}
            onLoading={(v: boolean) => {
              this.loading = v;
            }}
            onNameChange={this.handleNodeNameChange}
          />
        );
      default:
        return (
          <UptimeCheckTask
            ref='uptimeCheckTaskRef'
            isCard={this.dashboardMode === 'chart'}
            nodeName={this.nodeName}
            refreshKey={`${this.refreshKeys[UPTIME_CHECK_LIST[0].id]}__${this.$store.getters.bizId}`}
            onGroupStatus={(v: boolean) => this.fetchTaskGroupTask(v)}
            onLoading={(v: boolean) => {
              this.loading = v;
            }}
            onNodeNameChange={this.handleNodeNameChange}
            onRefresh={this.handleRefreshData}
          />
        );
    }
  }
  render() {
    if (this.showGuidePage) return <GuidePage guideData={introduce.data['uptime-check'].introduce} />;
    const isShowMenuList = this.active === 'uptime-check-task' && this.isTaskGroup && this.dashboardMode === 'chart';
    return (
      <div
        class='uptime-check-page'
        // v-bkloading={{ isLoading: this.loading }}
      >
        <PageTitle
          activeTab={this.active}
          disableOverview={this.active === 'uptime-check-node'}
          listPanelActive={this.dashboardMode === 'list'}
          showFilter={false}
          showInfo={false}
          showListPanel={true}
          showSearch={false}
          showSelectPanel={false}
          tabList={UPTIME_CHECK_LIST}
          onListPanelChange={this.handlePanelModeChange}
          onTabChange={this.handleTabChangeProxy}
        >
          <span slot='title'>{this.$t('综合拨测')}</span>
          <AlarmTools
            style={{ marginRight: '8px' }}
            slot='tools'
            panel={this.alarmToolsPanel}
          />
          <HeaderTool
            slot='tools'
            isSplitPanel={this.isSplitPanel}
            refleshInterval={-1}
            showDownSampleRange={false}
            showListMenu={isShowMenuList}
            showTimeRange={false}
            onFullscreenChange={this.handleFullscreen}
            onImmediateReflesh={() => this.handleImmediateReflesh()}
            onRefleshChange={v => this.handleRefleshChange(v)}
            onSelectedMenu={v => this.handleMenuSelect(v)}
            onSplitPanelChange={this.handleSplitPanel}
          />
        </PageTitle>
        <div class='uptime-check-page-container'>
          <div class='uptime-check-wrapper'>
            <keep-alive>{this.isActiveSet && this.getContent(this.active)}</keep-alive>
          </div>
          <div
            style={{
              width: `${this.splitPanelWidth}px`,
              display: this.splitPanelWidth > SPLIT_MIN_WIDTH && this.isSplitPanel ? 'flex' : 'none',
            }}
            class='split-panel-wrapper'
          >
            {this.isSplitPanel && (
              <SplitPanel
                splitMaxWidth={Math.max(this.splitPanelWidth + 300, SPLIT_MAX_WIDTH)}
                toggleSet={this.toggleSet}
                onDragMove={this.handleDragMove}
              />
            )}
          </div>
        </div>
      </div>
    );
  }
}

export default tsx.ofType<object>().convert(UptimeCheck);
