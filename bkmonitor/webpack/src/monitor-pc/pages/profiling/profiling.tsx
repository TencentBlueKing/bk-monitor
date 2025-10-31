/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { loadApp, mount, unmount } from '@blueking/bk-weweb';

import aiWhaleStore from '@/store/modules/ai-whale';
import '@blueking/bk-weweb';

import type { AIBluekingShortcut } from '@/components/ai-whale/types';
import type { Vue3WewebData } from '@/types/weweb/weweb';

import './profiling.scss';
const profilingAppId = 'profiling-explore';
Component.registerHooks(['beforeRouteLeave']);
@Component
export default class Profiling extends tsc<object> {
  @Prop() a: number;
  @Ref('profilingApp') profilingApp: HTMLElement;
  unmountCallback: () => void;
  get profilingHost() {
    return process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7002` : location.origin;
  }
  get profilingUrl() {
    return process.env.NODE_ENV === 'development'
      ? `${this.profilingHost}/?bizId=${this.$store.getters.bizId}/#/trace/profiling`
      : `${location.origin}${window.site_url}trace/?bizId=${this.$store.getters.bizId}/#/trace/profiling`;
  }
  get profilingData(): Vue3WewebData {
    return {
      host: this.profilingHost,
      baseroute: '/trace/',
      get enableAiAssistant() {
        return aiWhaleStore.enableAiAssistant;
      },
      setUnmountCallback: (callback: () => void) => {
        this.unmountCallback = callback;
      },
      handleAIBluekingShortcut: (shortcut: AIBluekingShortcut) => {
        aiWhaleStore.setCustomFallbackShortcut(shortcut);
      },
    };
  }
  created() {
    if (!window.customElements.get('profiling-explore')) {
      class ProfilingExploreElement extends HTMLElement {
        async connectedCallback() {
          if (!this.shadowRoot) {
            this.attachShadow({ delegatesFocus: false, mode: 'open' });
          }
        }
      }
      window.customElements.define('profiling-explore', ProfilingExploreElement);
    }
  }
  beforeDestroy() {
    this.unmountCallback?.();
    unmount(profilingAppId);
    this.unmountCallback = undefined;
  }
  async mounted() {
    await loadApp({
      url: this.profilingUrl,
      id: profilingAppId,
      container: this.profilingApp.shadowRoot,
      data: this.profilingData,
      showSourceCode: true,
      scopeCss: true,
      scopeJs: true,
      scopeLocation: false,
    });
    mount(profilingAppId, this.profilingApp.shadowRoot);
    setTimeout(() => {
      this.$store.commit('app/SET_ROUTE_CHANGE_LOADING', false);
    }, 300);
  }
  beforeRouteLeave(_to, _fromm, next) {
    document.body.___zrEVENTSAVED = null; // echarts 微应用偶发tooltips错误问题
    next();
  }
  render() {
    return (
      <div class='profiling-wrap'>
        <div class='profiling-wrap-iframe'>
          <profiling-explore ref='profilingApp' />
        </div>
      </div>
    );
  }
}
