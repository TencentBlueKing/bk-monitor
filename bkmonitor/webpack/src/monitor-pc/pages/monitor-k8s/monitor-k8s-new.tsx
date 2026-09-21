/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { Component, Mixins } from 'vue-property-decorator';

import introduce from '../../common/introduce';
import GuidePage from '../../components/guide-page/guide-page';
import K8sMonitorPanel from '../../components/k8s-silder/k8s-monitor-panel';
import { buildK8sMonitorQuery, parseK8sMonitorQuery } from '../../components/k8s-silder/utils';
import NewUserConfigMixin from '../../mixins/newUserStoreConfig';
import K8sNavBar from './components/k8s-nav-bar/K8s-nav-bar';
import { SceneEnum } from './typings/k8s-new';

import type { K8sMonitorNavBarScope } from '../../components/k8s-silder/k8s-monitor-panel';
import type { K8sMonitorInitialParams, K8sMonitorStateChangeEvent } from '../../components/k8s-silder/typings';

const CACHE_SEARCH_QUERY = 'cacheSearchQuery';

/**
 * 容器监控（新版）路由页。
 *
 * 只负责路由相关的事：URL ↔ 视图状态同步、引导页、离开时缓存查询条件，
 * 以及在 navBar 插槽里渲染顶部导航。视图主体在 `K8sMonitorPanel`，与侧滑共用。
 */
@Component
export default class MonitorK8sNew extends Mixins(NewUserConfigMixin) {
  bizId = this.$store.getters.bizId;

  /** 只在进入页面时解析一次，避免回写 URL 时反复给视图传入新的初始状态 */
  initialParams: K8sMonitorInitialParams | null = null;

  /** 插槽对象保持同一引用，避免每次渲染都强制视图整树更新 */
  panelSlots = {
    navBar: (scope: K8sMonitorNavBarScope) => this.navBarRender(scope),
  };

  // 获取引导页状态
  get showGuidePage() {
    return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
  }

  created() {
    /** URL 带参时由 URL 决定初始状态；不带参则交给视图用缓存的查询条件恢复 */
    this.initialParams = Object.keys(this.$route.query).length ? parseK8sMonitorQuery(this.$route.query) : null;
  }

  beforeRouteLeave(to, from, next) {
    // 离开时缓存当前查询条件，方便下次进入时使用
    const cluster = (from.query?.cluster as string) || '';
    this.handleSetUserConfig(`${CACHE_SEARCH_QUERY}_${this.bizId}_${cluster}`, JSON.stringify(from.query));
    next();
  }

  /**
   * @description 视图状态变更后回写 URL
   */
  handleStateChange({ state, extra }: K8sMonitorStateChangeEvent) {
    const query = {
      ...buildK8sMonitorQuery(state),
      // 事件场景的表格排序沿用事件检索的 URL 字段，未被 extra 覆盖时保持原值
      ...(state.scene === SceneEnum.Event
        ? { prop: this.$route.query?.prop || '', order: this.$route.query?.order || '' }
        : {}),
      ...extra,
    };

    const targetRoute = this.$router.resolve({ query });

    /** 防止出现跳转当前地址导致报错 */
    if (targetRoute.resolved.fullPath !== this.$route.fullPath) {
      this.$router.replace({ query });
    }
  }

  navBarRender(scope: K8sMonitorNavBarScope) {
    return (
      <K8sNavBar
        refreshInterval={scope.refreshInterval}
        timeRange={scope.timeRange}
        timezone={scope.timezone}
        value={scope.scene}
        onImmediateRefresh={scope.onImmediateRefresh}
        onRefreshChange={scope.onRefreshChange}
        onSelected={scope.onSceneChange}
        onTimeRangeChange={scope.onTimeRangeChange}
        onTimezoneChange={scope.onTimezoneChange}
      >
        {scope.showCancelDrill && (
          <div
            class='cancel-drill-down'
            onClick={scope.onCancelDrillDown}
          >
            <div class='back-icon'>
              <i class='icon-monitor icon-undo' />
            </div>
            <span class='text'>{this.$t('撤回下钻')}</span>
          </div>
        )}
      </K8sNavBar>
    );
  }

  render() {
    if (this.showGuidePage)
      return (
        <GuidePage
          guideData={introduce.data['k8s-new'].introduce}
          guideId='k8s'
        />
      );
    return (
      <K8sMonitorPanel
        initialParams={this.initialParams}
        queryCacheKey={CACHE_SEARCH_QUERY}
        scopedSlots={this.panelSlots}
        onStateChange={this.handleStateChange}
      />
    );
  }
}
