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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';

import { K8sNewTabEnum } from '../../pages/monitor-k8s/typings/k8s-new';
import { buildK8sMonitorQuery, K8S_MONITOR_ROUTE_PATH, parseK8sMonitorUrl } from './utils';

import type K8sMonitorPanelComponent from './k8s-monitor-panel';
import type { K8sMonitorInitialParams, K8sMonitorStateChangeEvent } from './typings';

import './k8s-slider.scss';

/**
 * 容器监控视图很重（图表 / 表格 / 维度列表），做成异步组件在点开侧滑时才加载，
 * 否则会被打进事件检索与 APM 事件 tab 的 chunk，从不点容器链接的用户也要下载。
 * 断言成组件类型是为了保留 TSX 的入参检查，运行时 Vue 会按异步工厂处理。
 */
const loadK8sMonitorPanel = () => import(/* webpackChunkName: 'k8sMonitorPanel' */ './k8s-monitor-panel');
const K8sMonitorPanel = loadK8sMonitorPanel as unknown as typeof K8sMonitorPanelComponent;

interface K8sSliderEvents {
  onShowChange: (isShow: boolean) => void;
}

interface K8sSliderProps {
  /** 抽屉页是否显示 */
  isShow?: boolean;
  /** 侧滑标题上展示的对象描述，一般取跳转入口的 alias */
  subTitle?: string;
  /** 后端下发的容器监控跳转链接，组件内部负责解析成视图参数 */
  url?: string;
  width?: number | string;
}

/**
 * 容器监控侧滑。
 *
 * 把原本需要新开页的容器监控链接就地展开，内部复用 `K8sMonitorPanel`，
 * 不传 navBar 插槽因此不带页面头部。内容在打开时才挂载、关闭即销毁，
 * 避免未展开的侧滑占用请求与定时器。
 */
@Component
export default class K8sSlider extends tsc<K8sSliderProps, K8sSliderEvents> {
  @Prop({ type: Boolean, default: false }) isShow?: boolean;
  @Prop({ type: String, default: '' }) url!: string;
  @Prop({ type: String, default: '' }) subTitle?: string;
  @Prop({ type: [Number, String], default: '80vw' }) width?: number | string;

  initialParams: K8sMonitorInitialParams | null = null;
  /** 每次打开都换新 key，保证换了对象时视图彻底重建而不是复用上一次的状态 */
  panelKey = '';
  /** 视图内最新状态，用于「新开页」时带上用户在侧滑里的调整 */
  latestQuery: null | Record<string, string> = null;
  /** 视图 chunk 是否还在加载 */
  panelLoading = false;

  @Watch('isShow', { immediate: true })
  handleShowChange(isShow: boolean) {
    if (!isShow) {
      this.initialParams = null;
      this.latestQuery = null;
      return;
    }
    this.initialParams = {
      ...parseK8sMonitorUrl(this.url).params,
      // 侧滑用于从事件快速看指标趋势，固定落在指标视图，不跟随链接里的 activeTab
      activeTab: K8sNewTabEnum.CHART,
    };
    this.panelKey = random(8);
    // 与 Vue 解析异步组件共用同一个 promise，chunk 已缓存时会立刻完成
    this.panelLoading = true;
    loadK8sMonitorPanel().finally(() => {
      this.panelLoading = false;
    });
  }

  @Emit('showChange')
  emitIsShow(isShow: boolean) {
    return isShow;
  }

  handleStateChange({ state }: K8sMonitorStateChangeEvent) {
    this.latestQuery = buildK8sMonitorQuery(state);
  }

  /**
   * @description 在新页面打开完整的容器监控，带上侧滑内已调整的查询条件
   * 以后端下发的链接为基底而不是当前应用的路由，因为本组件可能运行在
   * 没有注册 /k8s-new 路由的子应用里（如 APM 事件 tab）
   */
  handleOpenNewPage() {
    if (!this.url) return;
    let href = this.url;
    if (this.latestQuery) {
      try {
        const target = new URL(this.url, location.origin);
        target.hash = `#${K8S_MONITOR_ROUTE_PATH}?${new URLSearchParams(this.latestQuery)}`;
        href = target.href;
      } catch {
        // 链接不可解析时退回原始链接
      }
    }
    window.open(href);
  }

  render() {
    return (
      <bk-sideslider
        width={this.width}
        ext-cls='k8s-slider'
        isShow={this.isShow}
        {...{ on: { 'update:isShow': this.emitIsShow } }}
        quick-close={true}
        transfer={true}
      >
        <div
          class='k8s-slider-title'
          slot='header'
        >
          <span class='title-text'>{this.$t('容器监控')}</span>
          {this.subTitle ? <span class='title-sub'>{this.subTitle}</span> : undefined}
          <i
            class='icon-monitor icon-mc-goto title-goto'
            v-bk-tooltips={{
              content: this.$t('在新页面打开'),
              placement: 'right',
            }}
            onClick={this.handleOpenNewPage}
          />
        </div>
        <div
          class='k8s-slider-content'
          slot='content'
          v-bkloading={{ isLoading: this.panelLoading }}
        >
          {this.isShow ? (
            <K8sMonitorPanel
              key={this.panelKey}
              initialParams={this.initialParams}
              onStateChange={this.handleStateChange}
            />
          ) : undefined}
        </div>
      </bk-sideslider>
    );
  }
}
