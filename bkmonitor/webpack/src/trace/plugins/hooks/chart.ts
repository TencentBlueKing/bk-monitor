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
import { inject, onBeforeUnmount, provide, Ref, watch, WatchStopHandle } from 'vue';
import { type PanelToolsType } from 'monitor-pc/pages/monitor-k8s/typings';

import { TimeRangeType } from '../../components/time-range/utils';
import { SearchType } from '../../pages/profiling/typings';
import { isShadowEqual } from '../../utils';
import { IViewOptions } from '../typings';

export const TIME_RANGE_KEY = 'timeRange';
export const TIMEZONE_KEY = 'timezone';
export const REFLESH_INTERVAL_KEY = 'refleshInterval';
export const VIEWOPTIONS_KEY = 'viewOptions';
export const REFLESH_IMMEDIATE_KEY = 'refleshImmediate';
export const TIME_OFFSET_KEY = 'timeOffset';
export const CHART_PROVIDER_KEY = 'CHART_PROVIDER_KEY';
export const QUERY_DATA_KEY = 'queryData';
export const COMPARE_TYPE = 'compareType';
export const READONLY = 'readonly';

export interface IChartProvider {
  // 数据时间间隔
  readonly timeRange: Ref<TimeRangeType>;
  // 时区
  readonly timezone: Ref<string>;
  // 图表数据刷新间隔
  readonly refleshInterval: Ref<number>;
  // 通用图表查询数据配置
  readonly viewOptions: Ref<IViewOptions>;
  // 图表是否立即刷新
  readonly refleshImmediate: Ref<number | string>;
  // 图表对比数据
  readonly timeOffset: Ref<string[] | number[]>;
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
  let unWatchViewOptions: WatchStopHandle | null = null;
  if (viewOptions) {
    unWatchViewOptions = watch(viewOptions, (v, o) => {
      // 用于配置后台图表数据的特殊设置
      if (JSON.stringify(v) === JSON.stringify(o)) return;
      if (isShadowEqual(v, o)) return;
      getPanelData();
    });
  }
  // 数据时间间隔
  const timeRange = useTimeRanceInject();
  let unWatchTimeRange: WatchStopHandle | null = null;

  /** 用于 profiling 趋势图注入的查询类型 */
  /** 当前如果是上传 profiling 则不需要监听时间选择器变化 */
  const uploadProfilingSearch = inject<Ref<SearchType>>('profilingSearchType')?.value === SearchType.Upload;

  if (timeRange && !uploadProfilingSearch) {
    unWatchTimeRange = watch(timeRange, () => getPanelData());
  }
  // 时区
  const timezone = useTimezoneInject();
  let unWatchTimezone: WatchStopHandle | null = null;
  if (timezone) {
    unWatchTimezone = watch(timezone, () => getPanelData());
  }

  // 数据时间间隔
  const refleshInterval = useRefleshIntervalInject();
  let refleshIntervalTimer = 0;
  let unWatchRefleshInterval: WatchStopHandle | null = null;
  if (refleshInterval) {
    unWatchRefleshInterval = watch(
      refleshInterval,
      v => {
        window.clearInterval(refleshIntervalTimer);
        if (v <= 0) return;
        refleshIntervalTimer = window.setInterval(() => {
          getPanelData();
        }, refleshInterval.value);
      },
      { immediate: true }
    );
  }
  // 图表是否立即刷新
  const refleshImmediate = useRefleshImmediateInject();
  let unWatchRefleshImmediate: WatchStopHandle | null = null;
  if (refleshImmediate) {
    unWatchRefleshImmediate = watch(refleshImmediate, v => v && getPanelData());
  }

  // 图表对比数据
  const timeOffset = useTimeOffsetInject();
  let unWatchTimeOffset: WatchStopHandle | null = null;
  if (timeOffset) {
    unWatchTimeOffset = watch(timeOffset, (v, o) => {
      if (JSON.stringify(v) === JSON.stringify(o)) return;
      getPanelData();
    });
  }
  function beforeUnmount() {
    unWatchViewOptions?.();
    unWatchTimeRange?.();
    unWatchRefleshInterval?.();
    unWatchRefleshImmediate?.();
    unWatchTimeOffset?.();
    unWatchTimezone?.();
    window.clearInterval(refleshIntervalTimer);
  }
  onBeforeUnmount(() => {
    unWatchViewOptions?.();
    unWatchTimeRange?.();
    unWatchRefleshInterval?.();
    unWatchRefleshImmediate?.();
    unWatchTimeOffset?.();
    unWatchTimezone?.();
    window.clearInterval(refleshIntervalTimer);
  });
  return {
    unWatchViewOptions,
    unWatchTimeRange,
    unWatchRefleshInterval,
    unWatchRefleshImmediate,
    unWatchTimeOffset,
    unWatchTimezone,
    refleshIntervalTimer,
    beforeUnmount
  };
};

export const useTimeRangeProvider = (timeRange: Ref<TimeRangeType>) => {
  provide(TIME_RANGE_KEY, timeRange);
};
export const useTimeRanceInject = () => inject<Ref<TimeRangeType>>(TIME_RANGE_KEY);

export const useTimezoneProvider = (timezone: Ref<string>) => {
  provide(TIMEZONE_KEY, timezone);
};
export const useTimezoneInject = () => inject<Ref<string>>(TIMEZONE_KEY);

export const useRefleshIntervalProvider = (refleshInterval: Ref<number>) => {
  provide(REFLESH_INTERVAL_KEY, refleshInterval);
};
export const useRefleshIntervalInject = () => inject<Ref<number>>(REFLESH_INTERVAL_KEY);

export const useViewOptionsProvider = (viewOptions: IViewOptions) => {
  provide(VIEWOPTIONS_KEY, viewOptions);
};
export const useViewOptionsInject = () => inject<Ref<IViewOptions>>(VIEWOPTIONS_KEY);

export const useRefleshImmediateProvider = (refleshImmediate: boolean) => {
  provide(REFLESH_IMMEDIATE_KEY, refleshImmediate);
};
export const useRefleshImmediateInject = () => inject<Ref<boolean>>(REFLESH_IMMEDIATE_KEY);

export const useTimeOffsetProvider = (timeOffset: string | number) => {
  provide(TIME_OFFSET_KEY, timeOffset);
};
export const useTimeOffsetInject = () => inject<Ref<string[] | number[]>>(TIME_OFFSET_KEY);

// 好像用不着
export const useQueryDataProvider = (queryData: Ref<Object>) => {
  provide(QUERY_DATA_KEY, queryData);
};
// 好像用不着
export const useQueryDataInject = () => inject<Ref<Object>>(QUERY_DATA_KEY);

export const useCompareTypeProvider = (compareType: PanelToolsType.CompareId) => {
  provide(COMPARE_TYPE, compareType);
};
export const useCompareTypeInject = () => inject<Ref<PanelToolsType.CompareId>>(COMPARE_TYPE);

export const useReadonlyProvider = (v: boolean) => {
  provide(READONLY, v);
};
export const useReadonlyInject = () => inject<Ref<boolean>>(READONLY);
