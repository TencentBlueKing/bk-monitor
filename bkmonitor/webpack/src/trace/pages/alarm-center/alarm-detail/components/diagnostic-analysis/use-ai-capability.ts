/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { computed, shallowRef, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';

import { fetchAlertIncidentDetail } from '@/pages/alarm-center/services/alarm-detail';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { IAlertIncidentBrief, IBkFaraProcessItem } from './typing';

/**
 * 告警详情 AI诊断 展示条件：
 * - 纳入故障 → 结论里带「关联故障」，可跳故障详情
 * - 未纳入故障 → 结论只针对当前这条告警
 * - BKFara 事件分析 → 展示流程名称 / 执行时间 / 执行结果
 * - 通用能力始终展示
 */
export function useAiCapability() {
  const route = useRoute();
  const alarmCenterDetailStore = useAlarmCenterDetailStore();
  const { alarmId, bizId } = storeToRefs(alarmCenterDetailStore);

  const incident = shallowRef<IAlertIncidentBrief | null>(null);
  const loading = shallowRef(false);

  const mockFlags = computed(() => {
    void route.fullPath;
    return window.__ALARM_DETAIL_AI_MOCK__?.getFlags?.() || null;
  });

  const realHasIncident = computed(() => Boolean(incident.value?.id || incident.value?.incident_id));

  const hasIncident = computed(() => mockFlags.value?.hasIncident ?? realHasIncident.value);
  const displayIncident = computed<IAlertIncidentBrief | null>(() => {
    if (mockFlags.value) {
      return mockFlags.value.incident;
    }
    return incident.value;
  });
  const bkFaraProcesses = computed<IBkFaraProcessItem[]>(() => mockFlags.value?.bkFaraProcesses ?? []);

  const loadIncident = async (id: string, biz: number) => {
    if (!id || mockFlags.value) {
      incident.value = null;
      return;
    }
    loading.value = true;
    const res = await fetchAlertIncidentDetail(id, biz);
    const data = res?.incident;
    incident.value = data && Object.keys(data).length ? (data as IAlertIncidentBrief) : null;
    loading.value = false;
  };

  watch(
    () => [alarmId.value, bizId.value, mockFlags.value] as const,
    ([id, biz]) => {
      loadIncident(id, biz);
    },
    { immediate: true }
  );

  return {
    bkFaraProcesses,
    displayIncident,
    hasIncident,
    loading,
  };
}
