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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

// import { activated, loadApp, deactivated } from '../../../bk-weweb/src/index';
import { activated, deactivated, loadApp } from '@blueking/bk-weweb';
import { getShareParams } from 'monitor-api/modules/share';

import './share.scss';

interface IWebData {
  baseroute: string;
  host: string;
}
@Component
export default class SharePage extends tsc<object> {
  @Prop() token: string;
  loading = false;
  url = '';
  webData: IWebData;
  isEmpty = false;
  emptyMessage = '';
  created() {
    window.token = '';
  }
  async mounted() {
    this.loading = true;
    const { data, lock_search, has_permission } = await getShareParams(
      {
        token: this.token,
      },
      { needMessage: false }
    )
      // .then(data => ({ ...data, has_permission: false }))
      .catch(err => {
        this.emptyMessage = err?.data?.message;
        return { data: null };
      });
    if (!data) {
      this.isEmpty = true;
      this.loading = false;
      return;
    }
    this.emptyMessage = '';
    let url = '';
    // 事件中心
    if (data.name === 'event-center') {
      url = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}/#/event-center/detail/${data.eventId}`;
    } else if (/^apm_/.test(String(data.query?.sceneId))) {
      // apm 处理
      const route = this.$router.resolve({
        name: data.path,
        params: data.params,
        query: data.query,
      });
      const host = has_permission ? location.origin + location.pathname : data.weWebData.host;
      const path = !has_permission && process.env.NODE_ENV === 'production' ? `${location.pathname}apm/` : '';
      url = `${host}${path}?bizId=${this.$store.getters.bizId}/#${data?.path || '/'}?${route.href.replace(
        /^#\/([^?]*)\?/g,
        ''
      )}`;
    } else {
      const route = this.$router.resolve({
        name: data.name,
        params: data.params,
        query: data.query,
      });
      url = `${process.env.NODE_ENV === 'development' ? `http://${process.env.devUrl}` : location.origin}${
        location.pathname
      }?bizId=${this.$store.getters.bizId}/${route.href}`;
    }
    if (has_permission) {
      location.replace(url);
      this.loading = false;
      return;
    }
    window.token = this.token;
    this.isEmpty = false;
    this.url = url;
    const id = `__${this.token}__`;
    await loadApp({
      url: this.url,
      id,
      container: this.$refs.sharePageWrap as HTMLElement,
      showSourceCode: false,
      scopeCss: true,
      scopeLocation: true,
      setShodowDom: true,
      keepAlive: false,
      data: {
        // host: `http://${process.env.devHost}:7002`,
        // baseroute: '/fta/',
        ...(data.weWebData || {}),
        token: this.token,
        readonly: true,
        navList: data.navList,
        lockTimeRange: !!lock_search,
      },
    });
    activated(id, this.$refs.sharePageWrap as HTMLElement);
    window.requestIdleCallback(() => (this.loading = false));
  }
  beforeDestroy() {
    deactivated(`__${this.token}__`);
    window.token = '';
  }
  beforeRouteLeave(to, from, next) {
    next(() => {
      window.token = '';
    });
  }
  render() {
    return (
      <div
        class='share-wrap'
        v-monitor-loading={{ isLoading: this.loading }}
      >
        {!this.isEmpty ? (
          <div
            ref='sharePageWrap'
            class='share-wrap-iframe'
          />
        ) : (
          <div class='share-wrap-empty'>
            <bk-exception type='404'>
              <span>{this.emptyMessage || this.$t('当前页面分享链接已过期或被收回')}</span>
            </bk-exception>
          </div>
        )}
      </div>
    );
  }
}
