/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { unmount } from '@blueking/bk-weweb';

import './rotation.scss';

const wewebId = 'trace';
Component.registerHooks(['beforeRouteLeave']);
@Component
export default class Rotation extends tsc<{}> {
  get rotationHost() {
    return process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7002` : location.origin;
  }
  get rotationUrl() {
    return process.env.NODE_ENV === 'development'
      ? `${this.rotationHost}/?bizId=${this.$store.getters.bizId}/#/trace/rotation`
      : `${location.origin}${window.site_url}trace/?bizId=${this.$store.getters.bizId}/#/trace/rotation`;
  }
  get rotationData() {
    return JSON.stringify({
      host: this.rotationHost,
      baseroute: '/trace/'
    });
  }
  beforeRouteLeave(to, from, next) {
    unmount(wewebId);
    next();
  }
  render() {
    return (
      <div class='rotation-wrap'>
        <bk-weweb
          setShodowDom={true}
          class='rotation-iframe'
          url={this.rotationUrl}
          showSourceCode={true}
          id={wewebId}
          data={this.rotationData}
        />
      </div>
    );
  }
}
