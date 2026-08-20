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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { loadApp, mount, unmount } from '@blueking/bk-weweb';

import type { Vue3WewebData } from '@/types/weweb/weweb';

import './ai-config.scss';

const wewebId = 'ai-config';
Component.registerHooks(['beforeRouteLeave']);
/**
 * AI 设置页面容器：以微前端方式加载 trace（Vue3）中的 ai-config 页面
 */
@Component
export default class AiConfig extends tsc<object> {
  @Ref('traceApp') traceApp: HTMLElement;

  unmountCallback: () => void;
  get aiConfigHost() {
    return process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7002` : location.origin;
  }
  get aiConfigUrl() {
    return process.env.NODE_ENV === 'development'
      ? `${this.aiConfigHost}/?bizId=${this.$store.getters.bizId}/#/trace/ai-config`
      : `${location.origin}${window.site_url}trace/?bizId=${this.$store.getters.bizId}/#/trace/ai-config`;
  }
  get aiConfigData(): Vue3WewebData {
    return {
      host: this.aiConfigHost,
      parentRoute: '/trace/',
      setUnmountCallback: (callback: () => void) => {
        this.unmountCallback = callback;
      },
    };
  }
  created() {
    if (!window.customElements.get('trace-explore')) {
      class TraceExploreElement extends HTMLElement {
        async connectedCallback() {
          if (!this.shadowRoot) {
            this.attachShadow({ delegatesFocus: false, mode: 'open' });
          }
        }
      }
      window.customElements.define('trace-explore', TraceExploreElement);
    }
  }
  async mounted() {
    await loadApp({
      url: this.aiConfigUrl,
      id: wewebId,
      setShadowDom: true,
      container: this.traceApp.shadowRoot,
      data: this.aiConfigData,
      showSourceCode: false,
      scopeCss: true,
      scopeJs: true,
      scopeLocation: false,
    });
    mount(wewebId, this.traceApp.shadowRoot);
    setTimeout(() => {
      this.$store.commit('app/SET_ROUTE_CHANGE_LOADING', false);
    }, 300);
  }
  async beforeRouteLeave(_from, _to, next) {
    const res: boolean = await this.unmountCallback?.();
    const isNext = res !== false;
    if (isNext) {
      unmount(wewebId);
      this.unmountCallback = undefined;
      next();
    }
    return isNext;
  }
  render() {
    return (
      <div class='ai-config-wrap'>
        <div class='ai-config-wrap-iframe'>
          <trace-explore ref='traceApp' />
        </div>
      </div>
    );
  }
}
