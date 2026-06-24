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

import { defineComponent } from 'vue';

import { ResizeLayout } from 'bkui-vue';
import { storeToRefs } from 'pinia';

import { HOST_PAGE_HEADER_NAV_BAR_LIST } from './constants/constants';
import CommonHeader from '@/components/common-header/common-header';
import { useHostStore } from '@/store/modules/host';

import './host.scss';

export default defineComponent({
  name: 'HostPage',
  setup() {
    const { timeRange, timezone, refreshImmediate, refreshInterval, scene } = storeToRefs(useHostStore());
    return {
      timeRange,
      timezone,
      refreshImmediate,
      refreshInterval,
      scene,
    };
  },
  render() {
    return (
      <div class='host-page'>
        <CommonHeader
          class='host-page-header'
          hideFeature={['gotoOld']}
          refreshImmediate={this.refreshImmediate}
          refreshInterval={this.refreshInterval}
          timeRange={this.timeRange}
          timezone={this.timezone}
          onImmediateRefreshChange={value => (this.refreshImmediate = value)}
          onRefreshIntervalChange={value => (this.refreshInterval = value)}
          onTimeRangeChange={value => (this.timeRange = value)}
          onTimezoneChange={value => (this.timezone = value)}
        >
          {{
            left: () => (
              <ul class='host-page-header-nav'>
                {HOST_PAGE_HEADER_NAV_BAR_LIST.map(item => (
                  <li
                    key={item.value}
                    class={['host-page-header-nav-item', { active: item.value === this.scene }]}
                    onClick={() => (this.scene = item.value)}
                  >
                    <div class='bar-name'>{item.label}</div>
                  </li>
                ))}
              </ul>
            ),
          }}
        </CommonHeader>
        <div class='host-page-content'>
          <ResizeLayout
            class='host-page-content-layout'
            v-slots={{
              aside: () => (
                <div class='host-page-content-aside'>
                  <div class='host-page-content-aside-top' />
                </div>
              ),
              main: () => (
                <div class='host-page-content-main'>
                  <div class='host-page-content-main-left'>
                    <div class='host-page-content-main-left-top' />
                  </div>
                </div>
              ),
            }}
            border={false}
            initialDivide={280}
            max={800}
            min={200}
            placement='left'
            collapsible
            immediate
          />
        </div>
      </div>
    );
  },
});
