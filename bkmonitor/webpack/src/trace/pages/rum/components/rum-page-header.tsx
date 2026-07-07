/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, defineComponent } from 'vue';

import CommonHeader from '../../../components/common-header/common-header';

import type { TimeRangeType } from '../../../components/time-range/utils';

import './rum-page-header.scss';

export default defineComponent({
  name: 'RumPageHeader',
  props: {
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => [],
    },
    timezone: {
      type: String,
      default: '',
    },
    refreshImmediate: {
      type: String,
      default: '',
    },
    refreshInterval: {
      type: Number,
      default: -1,
    },
  },
  emits: {
    timeRangeChange: (_value: TimeRangeType) => true,
    timezoneChange: (_value: string) => true,
    immediateRefreshChange: (_value: string) => true,
    refreshIntervalChange: (_value: number) => true,
  },
  setup(_props, { emit }) {
    function handleTimeRangeChange(value: TimeRangeType) {
      emit('timeRangeChange', value);
    }
    function handleTimezoneChange(value: string) {
      emit('timezoneChange', value);
    }
    function handleImmediateRefreshChange(value: string) {
      emit('immediateRefreshChange', value);
    }
    function handleRefreshIntervalChange(value: number) {
      emit('refreshIntervalChange', value);
    }
    return {
      handleTimeRangeChange,
      handleTimezoneChange,
      handleImmediateRefreshChange,
      handleRefreshIntervalChange,
    };
  },
  render() {
    return (
      <div class='rum-page-header-comp'>
        <CommonHeader
          hideFeature={['gotoOld']}
          refreshImmediate={this.refreshImmediate}
          refreshInterval={this.refreshInterval}
          timeRange={this.timeRange}
          timezone={this.timezone}
          onImmediateRefreshChange={this.handleImmediateRefreshChange}
          onRefreshIntervalChange={this.handleRefreshIntervalChange}
          onTimeRangeChange={this.handleTimeRangeChange}
          onTimezoneChange={this.handleTimezoneChange}
        >
          {{
            left: () => (
              <div class='rum-page-header-left'>
                <span class='rum-page-title'>RUM</span>
              </div>
            ),
          }}
        </CommonHeader>
      </div>
    );
  },
});
