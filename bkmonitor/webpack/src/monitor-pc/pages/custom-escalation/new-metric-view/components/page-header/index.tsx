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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './index.scss';

@Component
export default class NewMetricView extends tsc<object> {
  render() {
    return (
      <div class='new-metric-view-page-header'>
        <div class='page-title'>
          <i class='icon-monitor icon-back-left navigation-bar-back' />
          <div class='app-name'>
            <bk-select
              clearable={false}
              popover-min-width={240}
            >
              <div
                class='app-select-value'
                slot='trigger'
              >
                hellow
                <i
                  style='margin-left: 10px'
                  class='icon-monitor icon-mc-arrow-down'
                />
              </div>
              <bk-option
                id='asd'
                name='asdasd'
              ></bk-option>
            </bk-select>
          </div>
        </div>
        <div class='index-tag'>
          指标：system.disk.in_use
          <i class='icon-monitor icon-mc-share' />
        </div>
        <div class='page-action-extend'>{this.$slots.default}</div>
      </div>
    );
  }
}
