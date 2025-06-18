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

import { defineComponent } from 'vue';
import { useI18n } from 'vue-i18n';

import { storeToRefs } from 'pinia';

import CommonHeader from '../../../components/common-header/common-header';
import { useAlarmCenterStore } from '../../../store/modules/alarm-center';
import { alarmTypeMap, type AlarmType } from '../typing';

import type { TimeRangeType } from '../../../components/time-range/utils';

import './alarm-center-header.scss';

export default defineComponent({
  name: 'AlarmCenterHeader',
  setup() {
    const { t } = useI18n();
    const store = useAlarmCenterStore();
    const { alarmType, timeRange, timezone, refreshImmediate, refreshInterval } = storeToRefs(store);

    function handleAlarmTypeChange(value: AlarmType) {
      store.updateState({
        alarmType: value,
      });
    }

    function handleImmediateRefreshChange(value: string) {
      store.updateState({
        refreshImmediate: value,
      });
    }

    function handleRefreshIntervalChange(value: number) {
      store.updateState({
        refreshInterval: value,
      });
    }

    function handleTimeRangeChange(value: TimeRangeType) {
      store.updateState({
        timeRange: value,
      });
    }

    function handleTimezoneChange(value: string) {
      store.updateState({
        timezone: value,
      });
    }

    function handleGotoOld() {}

    return {
      t,
      alarmTypeMap,
      alarmType,
      timeRange,
      timezone,
      refreshImmediate,
      refreshInterval,
      handleAlarmTypeChange,
      handleImmediateRefreshChange,
      handleRefreshIntervalChange,
      handleTimeRangeChange,
      handleTimezoneChange,
      handleGotoOld,
    };
  },
  render() {
    return (
      <div class='alarm-center-header-comp'>
        <CommonHeader
          refreshImmediate={this.refreshImmediate}
          refreshInterval={this.refreshInterval}
          timeRange={this.timeRange}
          timezone={this.timezone}
          onGotoOld={this.handleGotoOld}
          onImmediateRefreshChange={this.handleImmediateRefreshChange}
          onRefreshIntervalChange={this.handleRefreshIntervalChange}
          onTimeRangeChange={this.handleTimeRangeChange}
          onTimezoneChange={this.handleTimezoneChange}
        >
          {{
            left: () => (
              <ul class='alarm-type-nav-bar'>
                {this.alarmTypeMap.map(item => (
                  <li
                    key={item.value}
                    class={['alarm-type-nav-bar-item', { active: item.value === this.alarmType }]}
                    onClick={() => this.handleAlarmTypeChange(item.value)}
                  >
                    <div class='bar-name'>{item.label}</div>
                  </li>
                ))}
              </ul>
            ),
          }}
        </CommonHeader>
      </div>
    );
  },
});
