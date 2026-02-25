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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { loadApp, mount, unmount } from '@blueking/bk-weweb';

import aiWhaleStore from '@/store/modules/ai-whale';
import '@blueking/bk-weweb';

import type { AIBluekingShortcut } from '@/components/ai-whale/types';
import type { Vue3WewebData } from '@/types/weweb/weweb';

import './alarm-center.scss';

const alarmCenterAppId = 'alarm-center';
Component.registerHooks(['beforeRouteLeave']);
@Component
export default class AlarmCenterComponent extends tsc<object> {
  @Ref('alarmCenterApp') alarmCenterApp: HTMLElement;
  unmountCallback: () => void;
  get alarmCenterHost() {
    return process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7002` : location.origin;
  }
  get alarmCenterUrl() {
    return process.env.NODE_ENV === 'development'
      ? `${this.alarmCenterHost}/?bizId=${this.$store.getters.bizId}/#/trace/alarm-center`
      : `${location.origin}${window.site_url}trace/?bizId=${this.$store.getters.bizId}/#/trace/alarm-center`;
  }
  get alarmCenterData(): Vue3WewebData {
    return {
      host: this.alarmCenterHost,
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
    if (!window.customElements.get('alarm-center')) {
      class AlarmCenterElement extends HTMLElement {
        async connectedCallback() {
          if (!this.shadowRoot) {
            this.attachShadow({ delegatesFocus: false, mode: 'open' });
          }
        }
      }
      window.customElements.define('alarm-center', AlarmCenterElement);
    }
  }
  async mounted() {
    await loadApp({
      url: this.alarmCenterUrl,
      id: alarmCenterAppId,
      setShadowDom: true,
      container: this.alarmCenterApp.shadowRoot,
      data: this.alarmCenterData,
      showSourceCode: false,
      scopeCss: false,
      scopeJs: true,
      scopeLocation: false,
    });
    mount(alarmCenterAppId, this.alarmCenterApp.shadowRoot);
    setTimeout(() => {
      this.$store.commit('app/SET_ROUTE_CHANGE_LOADING', false);
    }, 300);
  }
  beforeDestroy() {
    this.unmountCallback?.();
    unmount(alarmCenterAppId);
    this.unmountCallback = undefined;
  }
  render() {
    return (
      <div class='alarm-center-wrap'>
        <div class='alarm-center-wrap-iframe'>
          <alarm-center ref='alarmCenterApp' />
        </div>
      </div>
    );
  }
}
