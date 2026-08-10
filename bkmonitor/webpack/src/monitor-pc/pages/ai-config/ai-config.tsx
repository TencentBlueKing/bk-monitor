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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { unmount } from '@blueking/bk-weweb';

import './ai-config.scss';

const wewebId = 'trace';
Component.registerHooks(['beforeRouteLeave']);
/**
 * AI 设置页面容器：以微前端方式加载 trace（Vue3）中的 ai-config 页面
 */
@Component
export default class AiConfig extends tsc<object> {
  get aiConfigHost() {
    return process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7002` : location.origin;
  }
  get aiConfigUrl() {
    return process.env.NODE_ENV === 'development'
      ? `${this.aiConfigHost}/?bizId=${this.$store.getters.bizId}/#/trace/ai-config`
      : `${location.origin}${window.site_url}trace/?bizId=${this.$store.getters.bizId}/#/trace/ai-config`;
  }
  get aiConfigData() {
    return JSON.stringify({
      host: this.aiConfigHost,
      parentRoute: '/trace/',
    });
  }
  beforeRouteLeave(_to, _from, next) {
    unmount(wewebId);
    next();
  }
  render() {
    return (
      <div class='ai-config-wrap'>
        <bk-weweb
          id={wewebId}
          class='ai-config-iframe'
          data={this.aiConfigData}
          setShadowDom={true}
          showSourceCode={true}
          url={this.aiConfigUrl}
        />
      </div>
    );
  }
}
