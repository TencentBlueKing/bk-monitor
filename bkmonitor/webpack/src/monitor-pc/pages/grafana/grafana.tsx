/*
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
 */
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getDashboardList } from 'monitor-api/modules/grafana';
import { addAccessRecord } from 'monitor-api/modules/overview';
import { skipToDocsLink } from 'monitor-common/utils/docs';
import bus from 'monitor-common/utils/event-bus';

import { DASHBOARD_ID_KEY, UPDATE_GRAFANA_KEY } from '../../constant/constant';
import { getDashboardCache } from './utils';

import './grafana.scss';

interface IMessageEvent extends MessageEvent {
  data: {
    pathname?: string;
    redirected?: boolean;
    href?: string;
    status?: 'login' | 'logout';
    login_url?: string;
  };
}
const FavoriteDashboardRouteName = 'favorite-dashboard';
@Component({
  name: 'grafana',
})
export default class MyComponent extends tsc<object> {
  @Prop({ default: '' }) url: string;
  grafanaUrl = '';
  unWatch = null;
  loading = true;
  hasLogin = false;
  showAlert = false;
  get originUrl() {
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
  async handleUrlChange() {
    this.showAlert = !localStorage.getItem(UPDATE_GRAFANA_KEY);
    if (this.$store.getters.bizIdChangePending) {
      this.loading = true;
      this.grafanaUrl = `${this.originUrl}${this.$store.getters.bizIdChangePending.replace('/home', '')}/?orgName=${
        this.$store.getters.bizId
      }${this.getUrlParamsString()}`;
      setTimeout(() => {
        this.loading = false;
      }, 2000);
      return;
    }
    this.loading = true;
    const grafanaUrl = await this.handleGetGrafanaUrl();
    if (!this.grafanaUrl) {
      this.grafanaUrl = grafanaUrl;
      setTimeout(() => {
        this.loading = false;
      }, 2000);
    } else {
      this.loading = false;
      const url = new URL(grafanaUrl);
      this.iframeRef?.contentWindow.postMessage(
        {
          route: `${url.pathname.replace('/grafana', '')}${url.search || ''}`,
          // search: url.search,
        },
        '*'
      );
    }
  }
  async handleGetGrafanaUrl() {
    let grafanaUrl = '';
    if (!this.url) {
      if (this.$route.name === 'grafana-home') {
        grafanaUrl = `${this.originUrl}grafana/?orgName=${this.$store.getters.bizId}${this.getUrlParamsString()}`;
      } else {
        const list = await getDashboardList().catch(() => []);
        const { bizId } = this.$store.getters;
        const dashboardCache = getDashboardCache();
        const dashboardCacheId = dashboardCache?.[bizId] || '';
        if (dashboardCacheId && list.some(item => item.uid === dashboardCacheId)) {
          this.$router.replace({
            name: FavoriteDashboardRouteName,
            params: {
              url: dashboardCacheId,
            },
          });
          localStorage.setItem(DASHBOARD_ID_KEY, JSON.stringify({ ...dashboardCache, [bizId]: dashboardCacheId }));
        } else {
          grafanaUrl = `${this.originUrl}grafana/?orgName=${this.$store.getters.bizId}${this.getUrlParamsString()}`;
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
      const isFavorite = this.$route.name === FavoriteDashboardRouteName;
      grafanaUrl = `${this.originUrl}grafana/${isFavorite && !this.url?.startsWith('d/') ? `d/${this.url}` : this.url}?orgName=${
        this.$store.getters.bizId
      }${this.getUrlParamsString()}`;
      isFavorite && this.handleSetDashboardCache(this.url);
    }
    return grafanaUrl;
  }
  getUrlParamsString() {
    const str = Object.entries({
      ...(this.$route.query || {}),
      ...Object.fromEntries(new URLSearchParams(location.search)),
    })
      .map(entry => entry.join('='))
      .join('&');
    if (str.length) return `&${str}`;
    return '';
  }
  mounted() {
    this.trackPageVisit(this.url);
    window.addEventListener('message', this.handleMessage, false);
  }
  /** 埋点 */
  trackPageVisit(url) {
    if (!url) return;
    const [uid = ''] = url.split('/');
    uid &&
      addAccessRecord({
        function: 'dashboard',
        config: { dashboard_uid: uid },
      });
  }
  beforeDestroy() {
    window.removeEventListener('message', this.handleMessage, false);
    const iframeContent = this.iframeRef?.contentWindow;
    iframeContent?.document.body.removeEventListener('keydown', this.handleKeydownGlobalSearch);
    // this.unWatch?.();
  }
  handleSetDashboardCache(dashboardCacheId: string) {
    const dashboardCache = getDashboardCache();
    const { bizId } = this.$store.getters;
    localStorage.setItem(DASHBOARD_ID_KEY, JSON.stringify({ ...dashboardCache, [bizId]: dashboardCacheId }));
  }
  handleLoad() {
    this.$nextTick(() => {
      const iframeContent = this.iframeRef?.contentWindow;
      const isBizSelectFocus =
        !!document.querySelector('.tippy-popper.biz-select-list-dark') ||
        !!document.querySelector('.tippy-popper.biz-select-list-light');
      if (!isBizSelectFocus) {
        this.iframeRef?.focus();
      }
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
    } catch {
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
      const dashboardId = pathname.includes('grafana/d/')
        ? pathname.replace(/\/?grafana\/d\//, '').replace(/\/$/, '')
        : '';
      if (dashboardId && this.url !== dashboardId) {
        this.$router.push({
          name: FavoriteDashboardRouteName,
          params: {
            url: dashboardId,
          },
          query: {
            ...Object.fromEntries(new URLSearchParams(e.data?.search || '')),
          },
        });
        this.handleSetDashboardCache(dashboardId);
      }
      return;
    }
    // 302跳转
    if (e?.data?.redirected && !this.hasLogin) {
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
      if (e.data.login_url) {
        this.hasLogin = true;
        const url = new URL(e.data.login_url);
        const curl = url.searchParams.get('c_url').replace(/^http:/, location.protocol);
        url.searchParams.set('c_url', curl);
        url.protocol = location.protocol;
        window.showLoginModal({ loginUrl: url.href });
      } else {
        location.reload();
      }
    }
  }
  handleCloseUpdateAlert() {
    localStorage.setItem(UPDATE_GRAFANA_KEY, 'true');
    this.showAlert = false;
  }
  gotoDocs() {
    skipToDocsLink('grafanaFeatures');
  }
  render() {
    return (
      <div
        class='grafana-wrap'
        v-monitor-loading={{ isLoading: this.loading }}
      >
        {this.showAlert && (
          <bk-alert
            class='grafana-update-alert'
            show-icon={false}
            type='info'
            closable
            onClose={this.handleCloseUpdateAlert}
          >
            <div
              class='grafana-update-alert-title'
              slot='title'
            >
              <i class='icon-monitor icon-inform' />
              {this.$t('Grafana已经升级到10版本，来看看有哪些功能差异')}
              <bk-button
                size='small'
                theme='primary'
                text
                onClick={this.gotoDocs}
              >
                {this.$t('查看详情')}
                <i class='icon-monitor icon-fenxiang link-icon' />
              </bk-button>
            </div>
          </bk-alert>
        )}
        <iframe
          ref='iframe'
          style={{
            'min-height': this.showAlert ? 'calc(100% - 32px)' : '100%',
            height: this.showAlert ? 'calc(100% - 32px)' : '100%',
          }}
          class='grafana-wrap-frame'
          src={this.grafanaUrl}
          title='grafana'
          onLoad={this.handleLoad}
        />
      </div>
    );
  }
}
