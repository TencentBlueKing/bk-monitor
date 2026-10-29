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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type SingleHostMonitorTarget, parseSingleHostMonitorUrl } from 'monitor-common/utils/host-monitor-url';
import { finalizeHostMonitorUrl } from 'monitor-pc/common/legacy-host-url';

interface HostObserveSliderEvents {
  onShowChange: (isShow: boolean) => void;
}

interface HostObserveSliderProps {
  activeTab?: string;
  bkBizId?: string;
  bkCloudId?: string;
  bkHostId?: string;
  hostProcessName?: string;
  ip?: string;
  isShow?: boolean;
  refreshInterval?: number;
  timeRange?: Array<number | string>;
  timezone?: string;
}

interface HostPanelMountHandle {
  unmount: () => void;
  update: (props: Record<string, unknown>) => void;
}

const panelHandles = new WeakMap<object, HostPanelMountHandle>();

/** 事件检索里的主机监控抽屉。第一次打开才加载 Vue3 子应用，关闭只把 isShow 设为 false。 */
@Component
export default class HostObserveSlider extends tsc<HostObserveSliderProps, HostObserveSliderEvents> {
  @Prop({ type: Boolean, default: false }) readonly isShow: boolean;
  @Prop({ type: String, default: '' }) readonly bkHostId: string;
  @Prop({ type: String, default: '' }) readonly ip: string;
  @Prop({ type: String, default: '' }) readonly bkCloudId: string;
  @Prop({ type: String, default: '' }) readonly bkBizId: string;
  @Prop({ type: Array, default: () => [] }) readonly timeRange: Array<number | string>;
  @Prop({ type: String, default: '' }) readonly timezone: string;
  @Prop({ type: Number, default: -1 }) readonly refreshInterval: number;
  @Prop({ type: String, default: '' }) readonly activeTab: string;
  @Prop({ type: String, default: '' }) readonly hostProcessName: string;

  private isUnmounted = false;
  private mountPromise: null | Promise<void> = null;

  get sliderProps() {
    return {
      activeTab: this.activeTab,
      bkBizId: this.bkBizId,
      bkCloudId: this.bkCloudId,
      bkHostId: this.bkHostId,
      hostProcessName: this.hostProcessName,
      ip: this.ip,
      isShow: this.isShow,
      refreshInterval: this.refreshInterval,
      timeRange: this.timeRange,
      timezone: this.timezone,
    };
  }

  @Watch('isShow')
  @Watch('bkHostId')
  @Watch('ip')
  @Watch('bkCloudId')
  @Watch('hostProcessName')
  @Watch('activeTab')
  async handleTargetChange() {
    if (!this.isShow) {
      panelHandles.get(this)?.update({ ...this.sliderProps, isShow: false });
      return;
    }
    if (!panelHandles.has(this)) await this.mountPanel();
    panelHandles.get(this)?.update({ ...this.sliderProps });
  }

  async mountPanel() {
    if (panelHandles.has(this) || this.isUnmounted) return;
    if (!this.mountPromise) this.mountPromise = this.createPanel();
    await this.mountPromise;
  }

  async createPanel() {
    await this.$nextTick();
    const el = this.$refs.root as HTMLElement;
    if (!el || this.isUnmounted) return;
    const savedI18n = window.i18n;
    await import('@blueking/apm-vue3-for-vue2/index.css');
    const { mountHostPanel: mount } = (await import('@blueking/apm-vue3-for-vue2')) as unknown as {
      mountHostPanel: (
        el: HTMLElement | string,
        options?: {
          onEvent?: (event: string, ...args: unknown[]) => void;
          props?: Record<string, unknown>;
        }
      ) => HostPanelMountHandle;
    };
    window.i18n = savedI18n;
    if (this.isUnmounted) return;
    panelHandles.set(
      this,
      mount(el, {
        props: { ...this.sliderProps },
        onEvent: (event: string) => {
          if (event === 'sliderClose') this.$emit('showChange', false);
        },
      })
    );
  }

  beforeDestroy() {
    this.isUnmounted = true;
    panelHandles.get(this)?.unmount();
    panelHandles.delete(this);
  }

  render() {
    return <div ref='root' />;
  }
}

export const readHostSliderTarget = (url: string): null | SingleHostMonitorTarget =>
  parseSingleHostMonitorUrl(finalizeHostMonitorUrl(url));
