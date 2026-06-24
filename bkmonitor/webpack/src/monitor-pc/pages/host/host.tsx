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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { loadApp, mount, unmount } from '@blueking/bk-weweb';

import aiWhaleStore from '@/store/modules/ai-whale';
import '@blueking/bk-weweb';

import type { AIBluekingShortcut } from '@/components/ai-whale/types';
import type { Vue3WewebData } from '@/types/weweb/weweb';

import './host.scss';
const hostAppId = 'host-app';
Component.registerHooks(['beforeRouteLeave']);
@Component
export default class Host extends tsc<object> {
  @Prop() a: number;
  @Ref('hostApp') hostApp: HTMLElement;
  unmountCallback: () => void;
  get hostHost() {
    return process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7002` : location.origin;
  }
  get hostUrl() {
    return process.env.NODE_ENV === 'development'
      ? `${this.hostHost}/?bizId=${this.$store.getters.bizId}/#/trace/host`
      : `${location.origin}${window.site_url}trace/?bizId=${this.$store.getters.bizId}/#/trace/host`;
  }
  get hostData(): Vue3WewebData {
    return {
      host: this.hostHost,
      parentRoute: '/trace/',
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
    if (!window.customElements.get('host-app')) {
      class HostAppElement extends HTMLElement {
        async connectedCallback() {
          if (!this.shadowRoot) {
            this.attachShadow({ delegatesFocus: false, mode: 'open' });
          }
        }
      }
      window.customElements.define('host-app', HostAppElement);
    }
  }
  beforeDestroy() {
    this.unmountCallback?.();
    unmount(hostAppId);
    this.unmountCallback = undefined;
  }
  async mounted() {
    await loadApp({
      url: this.hostUrl,
      id: hostAppId,
      container: this.hostApp.shadowRoot,
      data: this.hostData,
      showSourceCode: true,
      scopeCss: true,
      scopeJs: true,
      scopeLocation: false,
    });
    mount(hostAppId, this.hostApp.shadowRoot);
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
      <div class='host-wrap'>
        <div class='host-wrap-iframe'>
          <host-app ref='hostApp' />
        </div>
      </div>
    );
  }
}
