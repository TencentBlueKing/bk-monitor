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
import { defineStore } from 'pinia';

import { DEFAULT_TIME_RANGE, type TimeRangeType } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';

import type { IApplicationItem } from '../../pages/trace-explore/typing';
import type { TableProps } from 'tdesign-vue-next';

export interface ITraceExploreState {
  timeRange: TimeRangeType;
  timezone: string;
  mode: 'span' | 'trace';
  appName: string;
  refreshInterval: number;
  refreshImmediate: string;
  appList: IApplicationItem[];
  tableList: TableProps['data'];
}
export const useTraceExploreStore = defineStore('explore', {
  state: (): ITraceExploreState => ({
    timeRange: DEFAULT_TIME_RANGE,
    timezone: getDefaultTimezone(),
    mode: 'trace',
    appName: null,
    refreshInterval: -1,
    refreshImmediate: '',
    appList: [],
    tableList: [],
  }),
  getters: {
    currentApp: state => state.appList.find(app => app.app_name === state.appName),
  },
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
    updateAppName(appName: string) {
      this.appName = appName;
    },
    updateRefreshInterval(refreshInterval: number) {
      this.refreshInterval = refreshInterval;
    },
    updateRefreshImmediate(refreshImmediate: string) {
      this.refreshImmediate = refreshImmediate;
    },
    updateAppList(appList: IApplicationItem[]) {
      this.appList = appList;
    },
    updateTableList(tableList: TableProps['data']) {
      this.tableList = tableList;
    },
    init(data: Partial<ITraceExploreState>) {
      this.timeRange = data.timeRange || DEFAULT_TIME_RANGE;
      this.timezone = data.timezone || getDefaultTimezone();
      this.mode = data.mode || 'trace';
      this.appName = data.appName || '';
      this.refreshInterval = data.refreshInterval || -1;
      this.refreshImmediate = data.refreshImmediate;
    },
  },
});
