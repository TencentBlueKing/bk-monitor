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

import aiWhaleStore from '@/store/modules/ai-whale';
import '@blueking/bk-weweb';

import type { AIBluekingShortcut } from '@/components/ai-whale/types';
import type { Vue3WewebData } from '@/types/weweb/weweb';

import './rum-explore.scss';

/** bk-weweb 子应用实例 id，与 trace 检索、Profiling 检索各自独立，避免相互卸载 */
const rumExploreAppId = 'rum-explore-app';
/** 承载子应用 shadow dom 的自定义元素标签名，不能与本组件类名对应的 kebab-case 同名，否则会被 Vue 解析成组件自身导致递归渲染 */
const rumExploreTagName = 'rum-explore-app';

@Component
export default class RumExplore extends tsc<object> {
  @Ref('rumExploreApp') rumExploreApp: HTMLElement;
  unmountCallback: () => void;
  get rumExploreHost() {
    return process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7002` : location.origin;
  }
  get rumExploreUrl() {
    return process.env.NODE_ENV === 'development'
      ? `${this.rumExploreHost}/?bizId=${this.$store.getters.bizId}/#/trace/rum-explore`
      : `${location.origin}${window.site_url}trace/?bizId=${this.$store.getters.bizId}/#/trace/rum-explore`;
  }
  get rumExploreData(): Vue3WewebData {
    return {
      host: this.rumExploreHost,
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
    if (!window.customElements.get(rumExploreTagName)) {
      class RumExploreElement extends HTMLElement {
        async connectedCallback() {
          if (!this.shadowRoot) {
            this.attachShadow({ delegatesFocus: false, mode: 'open' });
          }
        }
      }
      window.customElements.define(rumExploreTagName, RumExploreElement);
    }
  }
  async mounted() {
    await loadApp({
      url: this.rumExploreUrl,
      id: rumExploreAppId,
      setShadowDom: true,
      container: this.rumExploreApp.shadowRoot,
      data: this.rumExploreData,
      showSourceCode: false,
      scopeCss: true,
      scopeJs: true,
      scopeLocation: false,
    });
    mount(rumExploreAppId, this.rumExploreApp.shadowRoot as ShadowRoot);
    setTimeout(() => {
      this.$store.commit('app/SET_ROUTE_CHANGE_LOADING', false);
    }, 300);
  }
  beforeDestroy() {
    this.unmountCallback?.();
    unmount(rumExploreAppId);
    this.unmountCallback = undefined;
  }
  render() {
    return (
      <div class='rum-explore-wrap'>
        <div class='rum-explore-wrap-iframe'>
          <rum-explore-app ref='rumExploreApp' />
        </div>
      </div>
    );
  }
}
