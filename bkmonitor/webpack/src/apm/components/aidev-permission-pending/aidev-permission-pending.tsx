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

import './aidev-permission-pending.scss';

const REFRESH_WAIT_SECONDS = 5;

@Component
export default class AidevPermissionPending extends tsc<object> {
  secondsLeft = REFRESH_WAIT_SECONDS;
  timer: null | number = null;

  get canRefresh() {
    return this.secondsLeft <= 0;
  }

  mounted() {
    this.timer = window.setInterval(() => {
      if (this.secondsLeft <= 1) {
        this.secondsLeft = 0;
        this.clearTimer();
        return;
      }
      this.secondsLeft -= 1;
    }, 1000);
  }

  beforeDestroy() {
    this.clearTimer();
  }

  clearTimer() {
    if (this.timer === null) return;
    window.clearInterval(this.timer);
    this.timer = null;
  }

  handleRefresh() {
    if (!this.canRefresh) return;
    window.location.reload();
  }

  render() {
    return (
      <div class='aidev-permission-pending'>
        <div class='aidev-permission-pending__card'>
          <div class='aidev-permission-pending__icon'>
            <i class='icon-monitor icon-mc-time' />
          </div>
          <h1 class='aidev-permission-pending__title'>{this.$t('暂未检测到访问权限')}</h1>
          <p class='aidev-permission-pending__desc'>{this.$t('当前业务的访问权限正在同步中，请稍后再刷新')}</p>
          {!this.canRefresh && (
            <p class='aidev-permission-pending__countdown'>
              {this.$t('{seconds} 秒后可刷新', { seconds: this.secondsLeft })}
            </p>
          )}
          <bk-button
            disabled={!this.canRefresh}
            theme='primary'
            on-click={this.handleRefresh}
          >
            {this.$t('刷新页面')}
          </bk-button>
        </div>
      </div>
    );
  }
}
