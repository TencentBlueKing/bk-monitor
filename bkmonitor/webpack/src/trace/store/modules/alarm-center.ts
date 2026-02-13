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

import { random } from 'monitor-common/utils';
import { defineStore } from 'pinia';

import { EMode } from '../../components/retrieval-filter/typing';
import { type TimeRangeType, DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import { AlarmType } from '../../pages/alarm-center/typings';
import { AlarmServiceFactory } from '@/pages/alarm-center/services/factory';

import type { AlarmService } from '@/pages/alarm-center/services/base';
import type { CommonCondition, QuickFilterItem } from '@/pages/alarm-center/typings';
const REFRESH_EFFECT_KEY = '__REFRESH_EFFECT_KEY__';

export interface IAlarmCenterState {
  alarmType: AlarmType; // 告警类型
  bizIds: number[]; // 业务ID
  conditions: CommonCondition[]; // 条件
  queryString: string; // 查询字符串
  refreshImmediate: string; // 是否立即刷新
  refreshInterval: number; // 刷新间隔
  timeRange: TimeRangeType; // 时间范围
  timezone: string; // 时区
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
  // 常驻筛选条件
  const residentCondition = deepRef<CommonCondition[]>([]);
  // 快速过滤条件
  const quickFilterValue = deepRef<CommonCondition[]>([]);
  /** 维度tag列表 */
  const dimensionTags = shallowRef<Omit<QuickFilterItem, 'children'>[]>([]);

  const queryString = shallowRef('');
  // 检索栏模式
  const filterMode = shallowRef(EMode.ui);

  const refreshId = shallowRef(random(4));

  const cacheMap: Map<
    AlarmType,
    {
      conditions?: CommonCondition[];
      queryString?: string;
      quickFilterValue?: CommonCondition[];
    }
  > = new Map();

  const alarmService = shallowRef<AlarmService<AlarmType>>();

  /* 收藏列表数据 */
  const favoriteList = shallowRef([]);

  const timeRangeTimestamp = computed(() => {
    const [start, end] = handleTransformToTimestamp(timeRange.value);
    const params = {
      start_time: start,
      end_time: end,
      [REFRESH_EFFECT_KEY]: refreshId.value,
    };
    // 用于主动触发 依赖副作用 更新
    delete params[REFRESH_EFFECT_KEY];
    return params;
  });
  const commonFilterParams = computed(() => {
    const statusQuickFilter = [];
    const otherQuickFilter = [];
    /**
     * 告警的与我相关，状态，
     * 处理记录的执行状态，
     * 以上快捷筛选条件需要特殊处理
     * */
    for (const filter of quickFilterValue.value) {
      /** 是否需要放在status字段中 */
      let isStatus = false;
      if (alarmType.value === AlarmType.ALERT) {
        if (filter.key === 'MINE' || filter.key === 'STATUS') {
          statusQuickFilter.push(...filter.value);
          isStatus = true;
        }
      } else if (alarmType.value === AlarmType.ACTION) {
        if (filter.key === 'action') {
          statusQuickFilter.push(...filter.value);
          isStatus = true;
        }
      } else if (alarmType.value === AlarmType.INCIDENT) {
        if (filter.key === 'INCIDENT_LEVEL' || filter.key === 'MINE') {
          statusQuickFilter.push(...filter.value);
          isStatus = true;
        }
      }
      if (!isStatus) {
        otherQuickFilter.push(filter);
      }
    }
    const params = {
      bk_biz_ids: bizIds.value,
      conditions: [
        ...(filterMode.value === EMode.ui ? [...conditions.value, ...residentCondition.value] : []),
        ...otherQuickFilter,
      ],
      query_string: filterMode.value === EMode.queryString ? queryString.value : '',
      status: statusQuickFilter,
      ...timeRangeTimestamp.value,
      [REFRESH_EFFECT_KEY]: refreshId.value,
    };
    // 用于主动触发 依赖副作用 更新
    delete params[REFRESH_EFFECT_KEY];
    return params;
  });

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
              effectRefresh();
            },
            Math.max(value, 1000 * 60)
          );
        }
        innerRefreshInterval.value = value;
        trigger();
      },
    };
  });

  /** 初始化service */
  const initAlarmService = () => {
    alarmService.value = AlarmServiceFactory(alarmType.value);
    // alarmService.value.getListSearchFavorite({ search_type: alarmType.value }).then(data => {
    //   favoriteList.value = data;
    // });
  };
  initAlarmService();

  /**
   * 告警类型切换
   * 不能使用watch监听alarmType来实现，必须手动调用
   * 使用watch会在页面初始化时调用一次，导致URL参数的数据缓存错误
   */
  const handleAlarmTypeChange = (type: AlarmType) => {
    const oldValue = alarmType.value;
    alarmType.value = type;
    if (oldValue) {
      cacheMap.set(oldValue, {
        conditions: JSON.parse(JSON.stringify(conditions.value)),
        queryString: JSON.parse(JSON.stringify(queryString.value)),
        quickFilterValue: JSON.parse(JSON.stringify(quickFilterValue.value)),
      });
    }
    const cache = cacheMap.get(alarmType.value);
    if (cache) {
      conditions.value = cache.conditions;
      queryString.value = cache.queryString;
      quickFilterValue.value = cache.quickFilterValue;
    } else {
      conditions.value = [];
      queryString.value = '';
      quickFilterValue.value = [];
    }
    initAlarmService();
  };

  const effectRefresh = () => {
    refreshId.value = random(4);
  };

  watch(refreshImmediate, () => {
    effectRefresh();
  });

  watchEffect(() => {
    alarmService.value.getAnalysisDimensionFields(commonFilterParams.value).then(res => {
      dimensionTags.value = res;
    });
  });

  onScopeDispose(() => {
    alarmService.value = undefined;
    bizIds.value = [+window.bk_biz_id];
    conditions.value = [];
    queryString.value = '';
    timeRange.value = DEFAULT_TIME_RANGE;
    timezone.value = getDefaultTimezone();
    refreshInterval.value = -1;
    refreshImmediate.value = '';
    quickFilterValue.value = [];
    favoriteList.value = [];
    cacheMap.clear();
  });
  return {
    timeRange,
    timezone,
    refreshInterval,
    refreshImmediate,
    alarmType,
    dimensionTags,
    bizIds,
    conditions,
    queryString,
    commonFilterParams,
    timeRangeTimestamp,
    alarmService,
    quickFilterValue,
    filterMode,
    residentCondition,
    favoriteList,
    handleAlarmTypeChange,
    initAlarmService,
  };
});
