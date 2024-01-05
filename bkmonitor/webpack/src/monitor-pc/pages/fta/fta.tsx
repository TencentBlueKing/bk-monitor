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

import '@blueking/bk-weweb';

import './fta.scss';

Component.registerHooks(['beforeRouteLeave']);

@Component
export default class FTA extends tsc<{}> {
  @Prop() a: number;
  loading = true;
  get ftaHost() {
    return process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7002` : location.origin;
  }
  get ftaUrl() {
    // return `${this.ftaHost}/fta/`;
    return process.env.NODE_ENV === 'development'
      ? this.ftaHost
      : `${location.origin}${window.site_url}fta/?bizId=${this.$store.getters.bizId}`;
  }
  get ftaData() {
    return JSON.stringify({
      host: this.ftaHost,
      baseroute: '/fta/'
    });
  }
  beforeRouteLeave(to, from, next) {
    next();
  }
  mounted() {
    setTimeout(() => {
      window.requestIdleCallback(() => (this.loading = false));
    });
  }
  render() {
    return (
      <div
        class='fta-wrap'
        v-monitor-loading={{ isLoading: this.loading }}
      >
        <bk-weweb
          class='fta-wrap-iframe'
          url={this.ftaUrl}
          id='fta'
          data={this.ftaData}
        />
      </div>
    );
  }
}
