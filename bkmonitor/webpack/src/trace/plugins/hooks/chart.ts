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
import {
  type ComputedRef,
  type Ref,
  type WatchStopHandle,
  computed,
  inject,
  onBeforeUnmount,
  provide,
  watch,
} from 'vue';
import { shallowRef } from 'vue';

import { SearchType } from '../../pages/profiling/typings';
import { isShadowEqual } from '../../utils';

import type { TimeRangeType } from '../../components/time-range/utils';
import type { IPanelModel, IViewOptions } from '../typings';
import type { PanelToolsType } from 'monitor-pc/pages/monitor-k8s/typings';

export const TIME_RANGE_KEY = 'timeRange';
export const TIMEZONE_KEY = 'timezone';
export const REFRESH_INTERVAL_KEY = 'refreshInterval';
export const VIEW_OPTIONS_KEY = 'viewOptions';
export const REFRESH_IMMEDIATE_KEY = 'refreshImmediate';
export const TIME_OFFSET_KEY = 'timeOffset';
export const CHART_PROVIDER_KEY = 'CHART_PROVIDER_KEY';
export const QUERY_DATA_KEY = 'queryData';
export const COMPARE_TYPE = 'compareType';
export const READONLY = 'readonly';
export const IS_ENABLED_PROFILING = 'IS_ENABLED_PROFILING';

export interface IChartProvider {
  // 图表是否立即刷新
  readonly refreshImmediate: Ref<number | string>;
  // 图表数据刷新间隔
  readonly refreshInterval: Ref<number>;
  // 图表对比数据
  readonly timeOffset: Ref<number[] | string[]>;
  // 数据时间间隔
  readonly timeRange: Ref<TimeRangeType>;
  // 时区
  readonly timezone: Ref<string>;
  // 通用图表查询数据配置
  readonly viewOptions: Ref<IViewOptions>;
}

// 通用视图注入数据
export const useChartProvider = (data: IChartProvider) => {
  provide(CHART_PROVIDER_KEY, data);
};
// 通用视图注入数据获取
export const useChartInject = () => inject<IChartProvider>(CHART_PROVIDER_KEY);
// 图表注入数据监听
export const useCommonChartWatch = (getPanelData: () => Promise<void>) => {
  // 用于配置后台图表数据的特殊设置
  const viewOptions = useViewOptionsInject();
  let unWatchViewOptions: null | WatchStopHandle = null;
  if (viewOptions) {
    unWatchViewOptions = watch(viewOptions, (v, o) => {
      // 用于配置后台图表数据的特殊设置
      if (JSON.stringify(v) === JSON.stringify(o)) return;
      if (isShadowEqual(v, o)) return;
      getPanelData();
    });
  }
  // 数据时间间隔
  const timeRange = useTimeRangeInject();
  let unWatchTimeRange: null | WatchStopHandle = null;

  /** 用于 profiling 趋势图注入的查询类型 */
  /** 当前如果是上传 profiling 则不需要监听时间选择器变化 */
  const uploadProfilingSearch = inject<Ref<SearchType>>('profilingSearchType', undefined)?.value === SearchType.Upload;

  if (timeRange && !uploadProfilingSearch) {
    unWatchTimeRange = watch(timeRange, () => getPanelData());
  }
  // 时区
  const timezone = useTimezoneInject();
  let unWatchTimezone: null | WatchStopHandle = null;
  if (timezone) {
    unWatchTimezone = watch(timezone, () => getPanelData());
  }

  // 数据时间间隔
  const refreshInterval = useRefreshIntervalInject();
  let refreshIntervalTimer = 0;
  let unWatchRefreshInterval: null | WatchStopHandle = null;
  if (refreshInterval) {
    unWatchRefreshInterval = watch(
      refreshInterval,
      v => {
        window.clearInterval(refreshIntervalTimer);
        if (v <= 0) return;
        refreshIntervalTimer = window.setInterval(() => {
          getPanelData();
        }, refreshInterval.value);
      },
      { immediate: true }
    );
  }
  // 图表是否立即刷新
  const refreshImmediate = useRefreshImmediateInject();
  let unWatchRefreshImmediate: null | WatchStopHandle = null;
  if (refreshImmediate) {
    unWatchRefreshImmediate = watch(refreshImmediate, v => v && getPanelData());
  }

  // 图表对比数据
  const timeOffset = useTimeOffsetInject();
  let unWatchTimeOffset: null | WatchStopHandle = null;
  if (timeOffset) {
    unWatchTimeOffset = watch(timeOffset, (v, o) => {
      if (JSON.stringify(v) === JSON.stringify(o)) return;
      getPanelData();
    });
  }
  function beforeUnmount() {
    unWatchViewOptions?.();
    unWatchTimeRange?.();
    unWatchRefreshInterval?.();
    unWatchRefreshImmediate?.();
    unWatchTimeOffset?.();
    unWatchTimezone?.();
    window.clearInterval(refreshIntervalTimer);
  }
  onBeforeUnmount(() => {
    unWatchViewOptions?.();
    unWatchTimeRange?.();
    unWatchRefreshInterval?.();
    unWatchRefreshImmediate?.();
    unWatchTimeOffset?.();
    unWatchTimezone?.();
    window.clearInterval(refreshIntervalTimer);
  });
  return {
    unWatchViewOptions,
    unWatchTimeRange,
    unWatchRefreshInterval,
    unWatchRefreshImmediate,
    unWatchTimeOffset,
    unWatchTimezone,
    refreshIntervalTimer,
    beforeUnmount,
  };
};

export const useTimeRangeProvider = (timeRange: Ref<TimeRangeType>) => {
  provide(TIME_RANGE_KEY, timeRange);
};
export const useTimeRangeInject = () => inject<Ref<TimeRangeType>>(TIME_RANGE_KEY, undefined);

export const useTimezoneProvider = (timezone: Ref<string>) => {
  provide(TIMEZONE_KEY, timezone);
};
export const useTimezoneInject = () => inject<Ref<string>>(TIMEZONE_KEY, undefined);

export const useRefreshIntervalProvider = (refreshInterval: Ref<number>) => {
  provide(REFRESH_INTERVAL_KEY, refreshInterval);
};
export const useRefreshIntervalInject = () => inject<Ref<number>>(REFRESH_INTERVAL_KEY, undefined);

export const useViewOptionsProvider = (viewOptions: IViewOptions) => {
  provide(VIEW_OPTIONS_KEY, viewOptions);
};
export const useViewOptionsInject = () => inject<Ref<IViewOptions>>(VIEW_OPTIONS_KEY, undefined);

export const useRefreshImmediateProvider = (refreshImmediate: boolean) => {
  provide(REFRESH_IMMEDIATE_KEY, refreshImmediate);
};
export const useRefreshImmediateInject = () => inject<Ref<boolean>>(REFRESH_IMMEDIATE_KEY, undefined);

export const useTimeOffsetProvider = (timeOffset: number | string) => {
  provide(TIME_OFFSET_KEY, timeOffset);
};
export const useTimeOffsetInject = () => inject<Ref<number[] | string[]>>(TIME_OFFSET_KEY);

// 好像用不着
export const useQueryDataProvider = (queryData: Ref<object>) => {
  provide(QUERY_DATA_KEY, queryData);
};
// 好像用不着
export const useQueryDataInject = () => inject<Ref<object>>(QUERY_DATA_KEY, undefined);

export const useCompareTypeProvider = (compareType: PanelToolsType.CompareId) => {
  provide(COMPARE_TYPE, compareType);
};
export const useCompareTypeInject = () => inject<Ref<PanelToolsType.CompareId>>(COMPARE_TYPE, undefined);

export const useReadonlyProvider = (v: boolean) => {
  provide(READONLY, v);
};
export const useReadonlyInject = () => inject<Ref<boolean>>(READONLY, shallowRef(false));

export const chartDetailProvideKey = Symbol('chart-detail-provide-key');
export const useChartInfoInject = () => inject<IPanelModel>(chartDetailProvideKey);

// 是否开启 profiling
export const useIsEnabledProfilingProvider = (enableProfiling: ComputedRef<boolean>) => {
  provide(IS_ENABLED_PROFILING, enableProfiling);
};
export const useIsEnabledProfilingInject = () =>
  inject<ComputedRef<boolean>>(
    IS_ENABLED_PROFILING,
    computed(() => false)
  );
