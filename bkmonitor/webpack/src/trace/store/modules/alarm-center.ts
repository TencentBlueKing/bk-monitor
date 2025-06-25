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

import { computed, ref as deepRef, shallowRef, watch, watchEffect } from 'vue';
import { onScopeDispose } from 'vue';
import { customRef } from 'vue';

import { useAlarmTable } from '@/pages/alarm-center/composables/use-alarm-table';
import { AlarmServiceFactory, type AlarmService } from '@page/alarm-center/services/alarm-services';
import { defineStore } from 'pinia';

import { DEFAULT_TIME_RANGE, handleTransformToTimestamp, type TimeRangeType } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import { AlarmType } from '../../pages/alarm-center/typings';

import type {
  CommonCondition,
  QuickFilterItem,
  FilterTableResponse,
  ActionTableItem,
  AlertTableItem,
  IncidentTableItem,
} from '@/pages/alarm-center/typings';

export interface IAlarmCenterState {
  timeRange: TimeRangeType; // 时间范围
  timezone: string; // 时区
  refreshInterval: number; // 刷新间隔
  refreshImmediate: string; // 是否立即刷新
  alarmType: AlarmType; // 告警类型
  bizIds: number[]; // 业务ID
  conditions: CommonCondition[]; // 条件
  queryString: string; // 查询字符串
}

export const useAlarmCenterStore = defineStore('alarmCenter', () => {
  const timeRange = deepRef(DEFAULT_TIME_RANGE);
  const timezone = shallowRef(getDefaultTimezone());
  const innerRefreshInterval = shallowRef(-1);

  const refreshImmediate = shallowRef('');
  const alarmType = shallowRef<AlarmType>(AlarmType.ALERT);
  const bizIds = deepRef([-1]);
  // 上层搜索条件
  const conditions = deepRef<CommonCondition[]>([]);
  // 快速过滤条件
  const quickFilterValue = deepRef<CommonCondition[]>([]);

  const queryString = shallowRef('');
  // 快速过滤条件loading
  const quickFilterLoading = shallowRef(false);
  // 维度分析loading
  const analysisDimensionLoading = shallowRef(false);

  const cacheMap = shallowRef<
    Map<
      AlarmType,
      {
        conditions?: CommonCondition[];
        queryString?: string;
      }
    >
  >(new Map());

  const alarmService = shallowRef<AlarmService<AlarmType>>();
  const quickFilterList = shallowRef<QuickFilterItem[]>([]);
  const filterTableList = shallowRef<FilterTableResponse<ActionTableItem | AlertTableItem | IncidentTableItem>>({
    total: 0,
    data: [],
  });
  const analysisDimensionFields = shallowRef<Omit<QuickFilterItem, 'children'>[]>([]);

  const timeRangeTimestamp = computed(() => {
    const [start, end] = handleTransformToTimestamp(timeRange.value);
    return {
      start_time: start,
      end_time: end,
    };
  });
  const commonFilterParams = computed(() => {
    return {
      bk_biz_ids: bizIds.value,
      conditions: [...conditions.value, ...quickFilterValue.value],
      query_string: queryString.value,
      ...timeRangeTimestamp.value,
    };
  });
  const effectFunc = async () => {
    quickFilterLoading.value = true;
    analysisDimensionLoading.value = true;
    alarmService.value
      .getQuickFilterList(commonFilterParams.value)
      .then(quickFilter => {
        quickFilterList.value = quickFilter;
      })
      .finally(() => {
        quickFilterLoading.value = false;
      });
    alarmService.value
      .getAnalysisDimensionFields(commonFilterParams.value)
      .then(analysisDimension => {
        analysisDimensionFields.value = analysisDimension;
      })
      .finally(() => {
        analysisDimensionLoading.value = false;
      });
  };
  const refreshInterval = customRef((track, trigger) => {
    let timer: ReturnType<typeof setInterval>;
    return {
      get() {
        track();
        return innerRefreshInterval.value;
      },
      set(value) {
        if (timer) {
          clearInterval(timer);
        }
        if (value > 0) {
          timer = setInterval(
            () => {
              effectFunc();
              refreshTableData();
            },
            Math.max(value, 1000 * 60)
          );
        }
        innerRefreshInterval.value = value;
        trigger();
      },
    };
  });
  watch(
    alarmType,
    () => {
      cacheMap.value.set(alarmType.value, {
        conditions: JSON.parse(JSON.stringify(conditions.value)),
        queryString: JSON.parse(JSON.stringify(queryString.value)),
      });
      alarmService.value = AlarmServiceFactory(alarmType.value);
      const cache = cacheMap.value.get(alarmType.value);
      if (cache) {
        conditions.value = cache.conditions;
        queryString.value = cache.queryString;
      }
    },
    {
      immediate: true,
    }
  );

  watchEffect(effectFunc);
  watch(refreshImmediate, () => {
    effectFunc();
    refreshTableData();
  });

  const {
    pageSize,
    page,
    total,
    data,
    loading: tableLoading,
    refresh: refreshTableData,
  } = useAlarmTable(commonFilterParams, alarmService);

  onScopeDispose(() => {
    quickFilterList.value = [];
    filterTableList.value = {
      total: 0,
      data: [],
    };
    analysisDimensionFields.value = [];
    alarmService.value = undefined;
    bizIds.value = [+window.bk_biz_id];
    conditions.value = [];
    queryString.value = '';
    timeRange.value = DEFAULT_TIME_RANGE;
    timezone.value = getDefaultTimezone();
    refreshInterval.value = -1;
    refreshImmediate.value = '';
    quickFilterLoading.value = false;
    analysisDimensionLoading.value = false;
    quickFilterValue.value = [];
    cacheMap.value.clear();
  });
  return {
    quickFilterLoading,
    analysisDimensionLoading,
    timeRange,
    timezone,
    refreshInterval,
    refreshImmediate,
    alarmType,
    bizIds,
    conditions,
    queryString,
    commonFilterParams,
    timeRangeTimestamp,
    alarmService,
    quickFilterList,
    filterTableList,
    analysisDimensionFields,
    pageSize,
    page,
    total,
    data,
    tableLoading,
    quickFilterValue,
  };
});
