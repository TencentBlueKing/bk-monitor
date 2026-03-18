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
import { defineComponent, shallowRef } from 'vue';

import { Sideslider } from 'bkui-vue';
import { random } from 'monitor-common/utils';
import { getDefaultTimezone } from 'monitor-pc/i18n/dayjs';
import { type IWhereItem, EMode } from 'trace/components/retrieval-filter/typing';

import IssuesSliderHeader from './components/issues-slider-header';
import IssuesSliderWrapper from './components/issues-slider-wrapper';
import RefreshRate from '@/components/refresh-rate/refresh-rate';
import TimeRange from '@/components/time-range/time-range';
import { type TimeRangeType, DEFAULT_TIME_RANGE } from '@/components/time-range/utils';

import './issues-detail-sideslider.scss';

export default defineComponent({
  name: 'IssuesDetailSideSlider',
  props: {
    show: {
      type: Boolean,
      required: true,
    },
    /** Issue ID */
    issueId: {
      type: String,
      default: '',
    },
    /** 告警ID */
    alarmId: {
      type: String,
      default: '',
    },
  },
  emits: ['update:show'],
  setup(_, { emit }) {
    const isFullscreen = shallowRef(false);
    const timeRange = shallowRef<TimeRangeType>(DEFAULT_TIME_RANGE);
    const timezone = shallowRef(getDefaultTimezone());
    const refreshInterval = shallowRef(-1);
    const refreshImmediate = shallowRef(random(4));
    // 筛选条件状态
    const conditions = shallowRef<IWhereItem[]>([]);
    const queryString = shallowRef('');
    const filterMode = shallowRef<EMode>(EMode.ui);

    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    const handleTimeRangeChange = (value: TimeRangeType) => {
      timeRange.value = value;
    };

    const handleTimezoneChange = (value: string) => {
      timezone.value = value;
    };

    const handleImmediateRefresh = () => {
      refreshImmediate.value = random(5);
    };

    const handleRefreshChange = (value: number) => {
      refreshInterval.value = value;
    };

    const handleConditionChange = (val: IWhereItem[]) => {
      conditions.value = val;
    };

    const handleQueryStringChange = (val: string) => {
      queryString.value = val;
    };

    const handleFilterModeChange = (val: EMode) => {
      filterMode.value = val;
    };

    return {
      isFullscreen,
      timeRange,
      timezone,
      refreshInterval,
      conditions,
      queryString,
      filterMode,
      handleShowChange,
      handleTimeRangeChange,
      handleTimezoneChange,
      handleImmediateRefresh,
      handleRefreshChange,
      handleConditionChange,
      handleQueryStringChange,
      handleFilterModeChange,
    };
  },
  render() {
    return (
      <Sideslider
        width={this.isFullscreen ? '100%' : '80%'}
        extCls='issues-detail-sidesSlider'
        v-slots={{
          header: () => (
            <IssuesSliderHeader
              v-slots={{
                tools: () => [
                  <TimeRange
                    key='time-range'
                    modelValue={this.timeRange}
                    timezone={this.timezone}
                    onUpdate:modelValue={this.handleTimeRangeChange}
                    onUpdate:timezone={this.handleTimezoneChange}
                  />,
                  <RefreshRate
                    key='refresh-rate'
                    value={this.refreshInterval}
                    onImmediate={this.handleImmediateRefresh}
                    onSelect={this.handleRefreshChange}
                  />,
                ],
              }}
            />
          ),
          default: () => (
            <div class='issues-detail-side-slider-content'>
              <IssuesSliderWrapper
                alarmId={this.alarmId}
                conditions={this.conditions}
                filterMode={this.filterMode}
                issueId={this.issueId}
                queryString={this.queryString}
                timeRange={this.timeRange}
                onConditionChange={this.handleConditionChange}
                onFilterModeChange={this.handleFilterModeChange}
                onQueryStringChange={this.handleQueryStringChange}
              />
            </div>
          ),
        }}
        isShow={this.show}
        render-directive='if'
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
