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

import type { AIBluekingShortcut } from '@/components/ai-whale/types';
import type { Vue3WewebData } from '@/types/weweb/weweb';

import './profiling-explore.scss';

const appId = 'profiling-explore-app';

@Component
export default class ProfilingExplore extends tsc<object> {
  @Ref('profilingApp') profilingApp: HTMLElement;
  unmountCallback: (() => void) | undefined;
  disposed = false;

  get host() {
    return process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7002` : location.origin;
  }

  get url() {
    const base = process.env.NODE_ENV === 'development' ? `${this.host}/` : `${this.host}${window.site_url}trace/`;
    return `${base}?bizId=${this.$store.getters.bizId}${location.hash}`;
  }

  get appData(): Vue3WewebData {
    return {
      host: this.host,
      parentRoute: '/trace/',
      get enableAiAssistant() {
        return aiWhaleStore.enableAiAssistant;
      },
      setUnmountCallback: callback => {
        this.unmountCallback = callback;
      },
      handleAIBluekingShortcut: (shortcut: AIBluekingShortcut) => aiWhaleStore.setCustomFallbackShortcut(shortcut),
    };
  }

  created() {
    if (!window.customElements.get(appId)) {
      window.customElements.define(
        appId,
        class extends HTMLElement {
          connectedCallback() {
            if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
          }
        }
      );
    }
  }

  async mounted() {
    try {
      await loadApp({
        url: this.url,
        id: appId,
        container: this.profilingApp.shadowRoot,
        data: this.appData,
        setShadowDom: true,
        showSourceCode: false,
        scopeCss: true,
        scopeJs: true,
        scopeLocation: false,
      });
      // loadApp 完成前可能已离开页面，此时只清理已加载资源，不能再挂载微应用。
      if (this.disposed) {
        this.unmountCallback?.();
        unmount(appId);
        return;
      }
      mount(appId, this.profilingApp.shadowRoot as ShadowRoot);
    } finally {
      if (!this.disposed) this.$store.commit('app/SET_ROUTE_CHANGE_LOADING', false);
    }
  }

  beforeDestroy() {
    this.disposed = true;
    this.unmountCallback?.();
    unmount(appId);
    this.unmountCallback = undefined;
  }

  render() {
    return (
      <div class='profiling-explore-wrap'>
        <profiling-explore-app ref='profilingApp' />
      </div>
    );
  }
}
