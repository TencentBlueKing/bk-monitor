<!--
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
-->
<template>
  <div
    class="grafana-wrap"
    v-monitor-loading="{ isLoading: loading }"
  >
    <iframe
      :key="url + '__key'"
      @load="handleLoad"
      ref="iframe"
      class="grafana-wrap-frame"
      allow="fullscreen"
      :src="grafanaUrl"
    />
  </div>
</template>
<script lang="ts">
import { Component, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { getDashboardList } from '../../../monitor-api/modules/grafana';
import bus from '../../../monitor-common/utils/event-bus';
import { DASHBOARD_ID_KEY } from '../../constant/constant';

interface IMessageEvent extends MessageEvent {
  data: {
    pathname?: string;
    redirected?: boolean;
    href?: string;
    status?: 'login' | 'logout';
    login_url?: string;
  };
}
@Component({
  name: 'grafana'
})
export default class Grafana extends Vue {
  @Prop({ default: '' }) url: string;
  grafanaUrl = '';
  unWatch = null;
  loading = true;
  hasLogin = false;
  get orignUrl() {
    return process.env.NODE_ENV === 'development' ? `${process.env.proxyUrl}/` : `${location.origin}${window.site_url}`;
  }
  get dashboardCheck() {
    return this.$store.getters['grafana/dashboardCheck'];
  }
  @Ref('iframe') iframeRef: HTMLIFrameElement;
  @Watch('dashboardCheck')
  onIsCreateChange(v) {
    this.iframeRef?.contentWindow.postMessage(v.split('-')[0], '*');
  }
  @Watch('url', { immediate: true })
  handleUrlChange() {
    this.handleGetGrafanaUrl();
  }
  async handleGetGrafanaUrl() {
    this.loading = true;
    if (!this.url) {
      if (this.$route.name === 'grafana-home') {
        this.grafanaUrl = `${this.orignUrl}grafana/?orgName=${this.$store.getters.bizId}${this.getUrlParamsString()}`;
      } else {
        const list = await getDashboardList().catch(() => []);
        const { bizId } = this.$store.getters;
        const dashboardCache = this.handleGetDashboardCache();
        const dashboardCacheId = dashboardCache?.[bizId] || '';
        if (dashboardCacheId && list.some(item => item.uid === dashboardCacheId)) {
          this.$router.replace({
            name: 'favorite-dashboard',
            params: {
              url: dashboardCacheId
            }
          });
          localStorage.setItem(DASHBOARD_ID_KEY, JSON.stringify({ ...dashboardCache, [bizId]: dashboardCacheId }));
        } else {
          this.grafanaUrl = `${this.orignUrl}grafana/?orgName=${this.$store.getters.bizId}${this.getUrlParamsString()}`;
          this.$router.replace({ name: 'grafana-home' });
        }
        await this.$nextTick();
      }
      // this.unWatch = this.$watch(
      //   'authority',
      //   () => {
      //     this.$store.commit('grafana/setHasManageAuth', this.authority.MANAGE_AUTH);
      //   },
      //   { deep: true, immediate: true }
      // );
    } else {
      const isFavorite = this.$route.name === 'favorite-dashboard';
      this.grafanaUrl = `${this.orignUrl}grafana/${isFavorite ? `d/${this.url}` : this.url}?orgName=${this.$store.getters.bizId}${this.getUrlParamsString()}`;
      isFavorite && this.handleSetDashboardCache(this.url);
    }
  }
  getUrlParamsString() {
    const str =  Object.entries({
      ...(this.$route.query || {}),
      ...Object.fromEntries(new URLSearchParams(location.search))
    }).map(entry => entry.join('='))
      .join('&');
    if (str.length) return `&${str}`;
    return '';
  }
  mounted() {
    window.addEventListener('message', this.handleMessage, false);
  }

  beforeDestroy() {
    window.removeEventListener('message', this.handleMessage, false);
    const iframeContent = this.iframeRef?.contentWindow;
    iframeContent?.document.body.removeEventListener('keydown', this.handleKeydownGlobalSearch);
    // this.unWatch?.();
  }
  handleGetDashboardCache() {
    let dashboardCache;
    try {
      dashboardCache = JSON.parse(localStorage.getItem(DASHBOARD_ID_KEY));
    } catch {}
    return dashboardCache;
  }
  handleSetDashboardCache(dashboardCacheId: string) {
    const dashboardCache = this.handleGetDashboardCache();
    const { bizId } = this.$store.getters;
    localStorage.setItem(DASHBOARD_ID_KEY, JSON.stringify({ ...dashboardCache, [bizId]: dashboardCacheId }));
  }
  handleLoad() {
    setTimeout(() => this.loading = false, 100);
    this.$nextTick(() => {
      const iframeContent = this.iframeRef?.contentWindow;
      this.iframeRef?.focus();
      iframeContent?.document.body.addEventListener('keydown', this.handleKeydownGlobalSearch);
    });
  }
  handleKeydownGlobalSearch(event) {
    // event.stopPropagation();
    bus.$emit('handle-keyup-search', event);
  }
  isAllowedUrl(url: string) {
  // 验证URL格式是否合法
    let parsedUrl: string | URL;
    try {
      parsedUrl = new URL(url);
    } catch (e) {
      return false; // 不是合法的URL
    }
    if (!parsedUrl.protocol.match(/^https?:$/)) {
      return false; // 不安全的协议
    }
    return true;
  }
  handleMessage(e: IMessageEvent) {
    if (e.origin !== location.origin) return;
    // iframe 内路由变化
    if (e?.data?.pathname) {
      const pathname = `${e.data.pathname}`;
      const matches = pathname.match(/\/d\/([^/]+)\//);
      const dashboardId = matches?.[1] || '';
      if (dashboardId && this.url !== dashboardId) {
        this.$router.push({
          name: 'favorite-dashboard',
          params: {
            url: dashboardId
          }
        });
        this.handleSetDashboardCache(dashboardId);
      }
      return;
    }
    // 302跳转
    if (e?.data?.redirected) {
      if (this.isAllowedUrl(e.data.href)) {
        const url = new URL(location.href);
        const curl = url.searchParams.get('c_url');
        if (curl) {
          url.searchParams.set('c_url', curl.replace(/^http:/, location.protocol));
        }
        location.href = `${e.data.href}?c_url=${encodeURIComponent(url.href)}`;
      } else {
        location.reload();
      }
      return;
    }
    // 登录 iframe内登入态失效
    if (e?.data?.status === 'login' && !this.hasLogin) {
      this.hasLogin = true;
      if (e.data.login_url) {
        const url = new URL(e.data.login_url);
        const curl = url.searchParams.get('c_url').replace(/^http:/, location.protocol);
        url.searchParams.set('c_url', curl);
        window.LoginModal.$props.loginUrl =  url.href;
        window.LoginModal.show();
      } else {
        location.reload();
      }
      setTimeout(() => {
        this.hasLogin = false;
      }, 1000 * 60);
    }
  }
}
</script>
<style lang="scss" scoped>
.grafana-wrap {
  // margin: -20px -24px 0;
  position: relative;
  height: 100%;
  overflow: hidden;

  &-frame {
    width: 100%;
    min-width: 100%;
    min-height: 100%;
    border: 0;
  }
}
</style>
