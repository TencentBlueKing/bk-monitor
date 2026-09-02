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

import { computed, ref as deepRef, shallowRef } from 'vue';

import { defineStore } from 'pinia';

import { type TimeRangeType, DEFAULT_TIME_RANGE } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import { ALL_SPAN_TYPE, RumModeEnum } from '../../pages/rum-explore/constants';

import type { IRumApplication, RumModeType } from '../../pages/rum-explore/typings';

/**
 * RUM 检索的跨组件共享状态。
 *
 * 只放需要被 header / 检索区 / 维度面板 / 表格多方读写的状态；
 * 单个区域内部的状态（如维度面板的搜索词）留在各自组件里。
 */
export const useRumExploreStore = defineStore('rumExplore', () => {
  const timeRange = deepRef<TimeRangeType>(DEFAULT_TIME_RANGE);
  const timezone = shallowRef(getDefaultTimezone());
  const mode = shallowRef<RumModeType>(RumModeEnum.SPAN);
  const appName = shallowRef('');
  const appList = shallowRef<IRumApplication[]>([]);
  /** 自动刷新间隔，-1 表示关闭 */
  const refreshInterval = shallowRef(-1);
  /** 变更即触发一次立即刷新，值本身无意义 */
  const refreshImmediate = shallowRef('');
  /** 「类型选择」快捷筛选选中的 span 类型，空串表示全部 */
  const spanType = shallowRef(ALL_SPAN_TYPE);
  /** 用户显式设置的排序（与接口一致，降序加 `-` 前缀，如 '-end_time'）。null 表示未设置（回落默认排序），空数组表示明确不排序 */
  const userSort = shallowRef<null | string[]>(null);
  /** 视图配置的默认排序，随应用 / 视角变化刷新 */
  const defaultSort = shallowRef<string[]>([]);
  /** 实际生效的排序参数：用户未设置时回落到视图配置的默认排序，空数组是有效值不回落 */
  const sortParams = computed<string[]>(() => userSort.value ?? defaultSort.value);

  const currentApp = computed(() => appList.value.find(app => app.app_name === appName.value));

  /** 从 URL 或收藏配置整体初始化，未提供的项回落到默认值 */
  function init(data: {
    appName?: string;
    mode?: RumModeType;
    refreshInterval?: number;
    sortParams?: null | string[];
    spanType?: string;
    timeRange?: TimeRangeType;
    timezone?: string;
  }) {
    timeRange.value = data.timeRange || DEFAULT_TIME_RANGE;
    timezone.value = data.timezone || getDefaultTimezone();
    mode.value = data.mode || RumModeEnum.SPAN;
    appName.value = data.appName || '';
    refreshInterval.value = data.refreshInterval ?? -1;
    spanType.value = data.spanType || ALL_SPAN_TYPE;
    userSort.value = data.sortParams ?? null;
  }

  return {
    appList,
    appName,
    currentApp,
    defaultSort,
    mode,
    refreshImmediate,
    refreshInterval,
    sortParams,
    spanType,
    timeRange,
    timezone,
    userSort,
    init,
  };
});
