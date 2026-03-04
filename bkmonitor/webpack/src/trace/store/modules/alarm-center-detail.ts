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

import { computed, onScopeDispose, reactive, shallowRef, watch } from 'vue';

import {
  alertEventTotal,
  alertHostTarget,
  alertK8sTarget,
  alertLogRelationList,
  alertTraces,
} from 'monitor-api/modules/alert_v2';
import { defineStore } from 'pinia';

import { handleTransformToTimestampMs } from '../../components/time-range/utils';
import { AlarmType } from '../../pages/alarm-center/typings';
import { ALARM_CENTER_PANEL_TAB_MAP } from '../../pages/alarm-center/utils/constant';
import { createAutoTimeRange } from '../../plugins/charts/failure-chart/failure-alarm-chart';
import { useAppStore } from './app';
import { fetchActionDetail, fetchAlarmDetail } from '@/pages/alarm-center/services/alarm-detail';

import type { AlarmDetail } from '../../pages/alarm-center/typings/detail';
import type { ActionDetail } from '@/pages/alarm-center/typings/action-detail';
import type { DateValue } from '@blueking/date-picker';

export const useAlarmCenterDetailStore = defineStore('alarmCenterDetail', () => {
  /** 告警详情 */
  const alarmDetail = shallowRef<AlarmDetail | null>();
  /** 告警ID */
  const alarmId = shallowRef<string>('');
  /** 处理记录ID */
  const actionId = shallowRef<string>('');
  /** 处理记录详情 */
  const actionDetail = shallowRef<ActionDetail | null>();
  /** 告警类型 */
  const alarmType = shallowRef<AlarmType>(AlarmType.ALERT);
  /** 加载状态 */
  const loading = shallowRef<boolean>(false);
  const defaultTab = shallowRef('');
  /** 需要检测禁用状态的 tab 列表 */
  const TAB_DISABLED_KEYS = [
    ALARM_CENTER_PANEL_TAB_MAP.LOG,
    ALARM_CENTER_PANEL_TAB_MAP.TRACE,
    ALARM_CENTER_PANEL_TAB_MAP.HOST,
    ALARM_CENTER_PANEL_TAB_MAP.CONTAINER,
    ALARM_CENTER_PANEL_TAB_MAP.EVENT,
  ] as string[];
  /** Tab 禁用状态 Map：key 为 tab name，value 为 true 表示该 tab 数据为空（禁用），默认禁用 */
  const tabDisabledMap = reactive<Record<string, boolean>>(
    Object.fromEntries(TAB_DISABLED_KEYS.map(key => [key, true]))
  );
  /** Tab 禁用状态是否正在加载 */
  const tabDisabledLoading = shallowRef(false);
  /** 用于取消上一次 tab 禁用状态请求的 AbortController */
  let tabDisabledAbortController: AbortController | null = null;
  const appStore = useAppStore();
  /** 数据间隔 */
  const interval = computed(
    () => alarmDetail.value.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60
  );
  /** 时间范围(毫秒级时间戳格式) */
  const timeRange = computed<DateValue>(() => {
    const { startTime, endTime } = createAutoTimeRange(
      alarmDetail.value.begin_time,
      alarmDetail.value.end_time,
      interval.value
    );
    return handleTransformToTimestampMs([startTime, endTime]);
  });
  const bizId = computed(() => {
    return alarmDetail.value?.bk_biz_id || (window.bk_biz_id as number) || (window.cc_biz_id as number) || undefined;
  });
  const bizItem = computed(() => {
    return appStore.bizList.find(item => +item.id === +bizId.value);
  });
  const detail = computed(() => {
    return alarmType.value === AlarmType.ALERT ? alarmDetail.value : actionDetail.value;
  });

  /**
   * @description 获取告警详情
   * @param id 告警ID
   */
  const getAlertDetailData = async (id: string) => {
    loading.value = true;
    const data = await fetchAlarmDetail(id).catch(() => null);
    alarmDetail.value = data;
    loading.value = false;
  };

  const getActionDetailData = async (id: string) => {
    loading.value = true;
    const data = await fetchActionDetail(id).catch(() => null);
    actionDetail.value = data;
    loading.value = false;
  };

  /**
   * @description 重置所有 tab 禁用状态为 true，并取消进行中的请求
   */
  const resetTabDisabledMap = () => {
    if (tabDisabledAbortController) {
      tabDisabledAbortController.abort();
      tabDisabledAbortController = null;
    }
    for (const key of TAB_DISABLED_KEYS) {
      tabDisabledMap[key] = true;
    }
  };

  /**
   * @description 并行请求各 tab 关键接口，判断数据是否为空以设置 tab 禁用状态
   * @param id 告警ID
   */
  const fetchTabDisabledStatus = async (id: string) => {
    const controller = new AbortController();
    tabDisabledAbortController = controller;
    const { signal } = controller;

    tabDisabledLoading.value = true;

    const tabApiMap = [
      {
        tab: ALARM_CENTER_PANEL_TAB_MAP.LOG,
        fn: () => alertLogRelationList({ alert_id: id }, { signal }).catch(() => []),
        isEmpty: (data: any) => !data?.length,
      },
      {
        tab: ALARM_CENTER_PANEL_TAB_MAP.TRACE,
        fn: () => alertTraces({ alert_id: id, offset: 0, limit: 1 }, { signal }).catch(() => ({ list: [] })),
        isEmpty: (data: any) => !data?.list?.length,
      },
      {
        tab: ALARM_CENTER_PANEL_TAB_MAP.HOST,
        fn: () => alertHostTarget({ alert_id: id }, { signal }).catch(() => []),
        isEmpty: (data: any) => !data?.length,
      },
      {
        tab: ALARM_CENTER_PANEL_TAB_MAP.CONTAINER,
        fn: () => alertK8sTarget({ alert_id: id }, { signal }).catch(() => ({ target_list: [] })),
        isEmpty: (data: any) => !data?.target_list?.length,
      },
      {
        tab: ALARM_CENTER_PANEL_TAB_MAP.EVENT,
        fn: () => alertEventTotal({ alert_id: id }, { signal }).catch(() => ({ total: 0 })),
        isEmpty: (data: any) => !data?.total,
      },
    ];

    const results = await Promise.allSettled(tabApiMap.map(item => item.fn()));

    // 如果已被取消，则不更新状态（新请求会覆盖）
    if (signal.aborted) return;

    for (const [index, result] of results.entries()) {
      const { tab, isEmpty } = tabApiMap[index];
      tabDisabledMap[tab] = result.status === 'fulfilled' ? isEmpty(result.value) : true;
    }
    tabDisabledLoading.value = false;
  };

  watch(
    () => alarmId.value,
    newVal => {
      resetTabDisabledMap();
      if (newVal && !loading.value) {
        getAlertDetailData(newVal);
        fetchTabDisabledStatus(newVal);
      }
    },
    { immediate: true }
  );

  watch(
    () => actionId.value,
    newVal => {
      if (newVal && !loading.value) {
        getActionDetailData(newVal);
      }
    }
  );

  onScopeDispose(() => {
    alarmId.value = '';
    alarmDetail.value = null;
    loading.value = false;
    resetTabDisabledMap();
  });

  return {
    alarmDetail,
    detail,
    alarmId,
    defaultTab,
    actionId,
    actionDetail,
    alarmType,
    loading,
    bizId,
    bizItem,
    interval,
    timeRange,
    tabDisabledMap,
  };
});
