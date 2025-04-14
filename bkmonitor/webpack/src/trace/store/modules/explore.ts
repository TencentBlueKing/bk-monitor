import { defineStore } from 'pinia';

import type { IApplicationItem } from '../../pages/trace-explore/typing';

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
import { DEFAULT_TIME_RANGE, type TimeRangeType } from '../../components/time-range/utils';

export interface ITraceExploreState {
  timeRange: TimeRangeType;
  timezone: string;
  mode: 'span' | 'trace';
  application: IApplicationItem;
  refreshInterval: number;
  refreshImmediate: string;
}
export const useTraceExploreStore = defineStore('explore', {
  state: (): ITraceExploreState => ({
    timeRange: DEFAULT_TIME_RANGE,
    timezone: '',
    mode: 'trace',
    application: null,
    refreshInterval: -1,
    refreshImmediate: '',
  }),
  actions: {
    updateTimeRange(timeRange: TimeRangeType) {
      this.timeRange = timeRange;
    },
    updateTimezone(timezone: string) {
      this.timezone = timezone;
    },
    updateMode(mode: 'span' | 'trace') {
      this.mode = mode;
    },
    updateApplicationId(application: IApplicationItem) {
      this.application = application;
    },
    updateRefreshInterval(refreshInterval: number) {
      this.refreshInterval = refreshInterval;
    },
    updateRefreshImmediate(refreshImmediate: string) {
      this.refreshImmediate = refreshImmediate;
    },
    init(data: ITraceExploreState) {
      this.timeRange = data.timeRange;
      this.mode = data.mode;
      this.application = data.application;
      this.refreshInterval = data.refreshInterval;
      this.refreshImmediate = data.refreshImmediate;
    },
  },
});
