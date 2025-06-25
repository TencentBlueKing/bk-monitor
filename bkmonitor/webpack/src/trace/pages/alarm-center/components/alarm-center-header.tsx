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

import CommonHeader from '../../../components/common-header/common-header';
import { useAlarmCenterStore } from '../../../store/modules/alarm-center';
import { alarmTypeMap, type AlarmType } from '../typings';

import type { TimeRangeType } from '../../../components/time-range/utils';

import './alarm-center-header.scss';

export default defineComponent({
  name: 'AlarmCenterHeader',
  setup() {
    const { t } = useI18n();
    const alarmStore = useAlarmCenterStore();

    function handleAlarmTypeChange(value: AlarmType) {
      alarmStore.alarmType = value;
      alarmStore.conditions = [];
      alarmStore.queryString = '';
    }

    function handleImmediateRefreshChange(value: string) {
      alarmStore.refreshImmediate = value;
    }

    function handleRefreshIntervalChange(value: number) {
      alarmStore.refreshInterval = value;
    }

    function handleTimeRangeChange(value: TimeRangeType) {
      alarmStore.timeRange = value;
    }

    function handleTimezoneChange(value: string) {
      alarmStore.timezone = value;
    }

    function handleGotoOld() {}

    return {
      t,
      alarmTypeMap,
      handleAlarmTypeChange,
      handleImmediateRefreshChange,
      handleRefreshIntervalChange,
      handleTimeRangeChange,
      handleTimezoneChange,
      handleGotoOld,
      alarmStore,
    };
  },
  render() {
    return (
      <div class='alarm-center-header-comp'>
        <CommonHeader
          refreshImmediate={this.alarmStore.refreshImmediate}
          refreshInterval={this.alarmStore.refreshInterval}
          timeRange={this.alarmStore.timeRange}
          timezone={this.alarmStore.timezone}
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
                    class={['alarm-type-nav-bar-item', { active: item.value === this.alarmStore.alarmType }]}
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
