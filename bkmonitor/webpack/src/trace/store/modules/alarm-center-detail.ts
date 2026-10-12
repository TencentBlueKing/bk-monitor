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

import { computed, onScopeDispose, shallowRef, watch } from 'vue';

import { defineStore } from 'pinia';

import { handleTransformToTimestampMs } from '../../components/time-range/utils';
import { AlarmType } from '../../pages/alarm-center/typings';
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
  const alertLoading = shallowRef(false);
  const actionLoading = shallowRef(false);
  const alertError = shallowRef(false);
  const actionError = shallowRef(false);
  const loading = computed(() => alarmType.value === AlarmType.ALERT ? alertLoading.value : actionLoading.value);
  let alertRequestId = 0;
  let actionRequestId = 0;
  const bizId = shallowRef<number>((window.bk_biz_id as number) || (window.cc_biz_id as number) || undefined);
  const appStore = useAppStore();
  /** 数据间隔 */
  const interval = computed(
    () => alarmDetail.value?.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60
  );
  /** 时间范围(毫秒级时间戳格式) */
  const timeRange = computed<DateValue>(() => {
    const { startTime, endTime } = createAutoTimeRange(
      alarmDetail.value?.begin_time || 0,
      alarmDetail.value?.end_time || 0,
      interval.value
    );
    return handleTransformToTimestampMs([startTime, endTime]);
  });

  const bizItem = computed(() => {
    return appStore.bizList.find(item => +item.id === +bizId.value);
  });
  const detail = computed(() => {
    return alarmType.value === AlarmType.ALERT ? alarmDetail.value : actionDetail.value;
  });

  const getAlertDetailData = async () => {
    const requestId = ++alertRequestId;
    const id = alarmId.value;
    const biz = bizId.value;
    const isCurrent = () => requestId === alertRequestId && id === alarmId.value && biz === bizId.value
      && alarmType.value === AlarmType.ALERT;
    alertError.value = false;
    if (!id || alarmType.value !== AlarmType.ALERT) {
      alertLoading.value = false;
      alarmDetail.value = null;
      return;
    }
    if (alarmDetail.value?.id !== id || +alarmDetail.value?.bk_biz_id !== +biz) alarmDetail.value = null;
    alertLoading.value = true;
    try {
      const data = await fetchAlarmDetail(id, biz);
      if (!isCurrent()) return;
      if (!data) {
        alertError.value = true;
        return;
      }
      alarmDetail.value = data;
    } catch {
      if (isCurrent()) alertError.value = true;
    } finally {
      if (isCurrent()) alertLoading.value = false;
    }
  };

  const getActionDetailData = async () => {
    const requestId = ++actionRequestId;
    const id = actionId.value;
    const biz = bizId.value;
    const isCurrent = () => requestId === actionRequestId && id === actionId.value && biz === bizId.value
      && alarmType.value === AlarmType.ACTION;
    actionError.value = false;
    if (!id || alarmType.value !== AlarmType.ACTION) {
      actionLoading.value = false;
      actionDetail.value = null;
      return;
    }
    actionDetail.value = null;
    actionLoading.value = true;
    try {
      const data = await fetchActionDetail(id, biz);
      if (!isCurrent()) return;
      actionDetail.value = data;
      actionError.value = !data;
    } catch {
      if (isCurrent()) actionError.value = true;
    } finally {
      if (isCurrent()) actionLoading.value = false;
    }
  };

  const reset = () => {
    ++alertRequestId;
    ++actionRequestId;
    alarmId.value = '';
    actionId.value = '';
    alarmDetail.value = null;
    actionDetail.value = null;
    alertLoading.value = false;
    actionLoading.value = false;
    alertError.value = false;
    actionError.value = false;
  };

  watch([alarmId, bizId, alarmType], getAlertDetailData, { immediate: true });
  watch([actionId, bizId, alarmType], getActionDetailData);
  onScopeDispose(reset);

  return {
    alarmDetail,
    detail,
    alarmId,
    actionId,
    actionDetail,
    alarmType,
    loading,
    alertError,
    actionError,
    getAlertDetailData,
    getActionDetailData,
    reset,
    bizId,
    bizItem,
    interval,
    timeRange,
  };
});
