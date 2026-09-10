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

import type { IDiagnosticNavigateIntent } from '../../pages/alarm-center/alarm-detail/components/diagnostic-analysis/navigate-typing';
import type { AlarmDetail } from '../../pages/alarm-center/typings/detail';
import type { ActionDetail } from '@/pages/alarm-center/typings/action-detail';
import type { DateValue } from '@blueking/date-picker';

/** 左侧划词「添加至聊天」带到右侧输入框的引用内容 */
export interface IChatContextItem {
  /** 划词所在区域，如「维度信息」「视图」，同一区域的引用在输入框里归到一组 */
  category: string;
  id: string;
  /** 该文本所属对象，如维度名 / 字段名 / 表头，取不到时为空 */
  label: string;
  text: string;
}

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
  const bizId = shallowRef<number>((window.bk_biz_id as number) || (window.cc_biz_id as number) || undefined);
  const appStore = useAppStore();
  /**
   * 右侧 AI 诊断驱动左侧详情 tab 的导航意图。
   * common-detail 负责切 tab，各 panel 负责消费 filter。
   */
  const diagnosticNavigate = shallowRef<IDiagnosticNavigateIntent | null>(null);
  /** 左侧划词添加的引用，由右侧聊天输入框消费 */
  const chatContexts = shallowRef<IChatContextItem[]>([]);
  /** 视图 - 维度分析已加载的可下钻维度，右侧诊断需要用它对齐维度名 */
  const viewDimensionList = shallowRef<{ id: string; name: string }[]>([]);
  /** 递增以请求宿主展开右侧 AI 诊断面板 */
  const aiAnalysisOpenNonce = shallowRef(0);
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

  /**
   * @description 获取告警详情
   * @param id 告警ID
   */
  const getAlertDetailData = async (id: string) => {
    loading.value = true;
    const data = await fetchAlarmDetail(id, bizId.value).catch(() => null);
    alarmDetail.value = data;
    loading.value = false;
  };

  const getActionDetailData = async (id: string) => {
    loading.value = true;
    const data = await fetchActionDetail(id, bizId.value).catch(() => null);
    actionDetail.value = data;
    loading.value = false;
  };

  const navigateFromDiagnostic = (intent: IDiagnosticNavigateIntent) => {
    diagnosticNavigate.value = intent;
  };

  const clearDiagnosticNavigate = () => {
    diagnosticNavigate.value = null;
  };

  /** 添加划词引用，同一区域下的同一段文本不重复入列，但每次都请求展开 AI 诊断面板 */
  const addChatContext = (item: Omit<IChatContextItem, 'id'>) => {
    const text = item.text.trim();
    if (!text) return;
    const exists = chatContexts.value.some(
      context => context.text === text && context.label === item.label && context.category === item.category
    );
    if (!exists) {
      chatContexts.value = [...chatContexts.value, { ...item, text, id: `chat-context-${Date.now()}` }];
    }
    aiAnalysisOpenNonce.value = Date.now();
  };

  const removeChatContext = (id: string) => {
    chatContexts.value = chatContexts.value.filter(item => item.id !== id);
  };

  const clearChatContexts = () => {
    chatContexts.value = [];
  };

  const setViewDimensionList = (list: { id: string; name: string }[]) => {
    viewDimensionList.value = list;
  };

  watch(
    () => alarmId.value,
    newVal => {
      chatContexts.value = [];
      if (newVal && !loading.value) {
        getAlertDetailData(newVal);
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
    diagnosticNavigate.value = null;
    chatContexts.value = [];
  });

  return {
    alarmDetail,
    detail,
    alarmId,
    actionId,
    actionDetail,
    alarmType,
    loading,
    bizId,
    bizItem,
    interval,
    timeRange,
    diagnosticNavigate,
    navigateFromDiagnostic,
    clearDiagnosticNavigate,
    chatContexts,
    aiAnalysisOpenNonce,
    addChatContext,
    removeChatContext,
    clearChatContexts,
    viewDimensionList,
    setViewDimensionList,
  };
});
