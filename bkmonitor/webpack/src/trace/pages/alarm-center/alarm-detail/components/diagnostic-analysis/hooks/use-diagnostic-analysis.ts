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
import { computed, onScopeDispose, shallowRef, unref, watch } from 'vue';
import type { MaybeRef } from 'vue';

import { MessageStatus } from '@blueking/chat-x';
import { fetchAiSetting } from 'monitor-api/modules/aiops';
import { getBizRouteHref } from 'monitor-common/utils';
import { storeToRefs } from 'pinia';

import { transformDiagnosisPanelView } from '../diagnosis-view-adapter';
import { createDiagnosticPanelState } from '../model';
import { diagnosticDataService } from '../services/diagnostic-data-service';
import {
  isValidDetailRef,
  resolveDiagnosticStatus,
  transformAlertsAnalysisPanel,
  transformEventsAnalysisPanel,
  transformIncidentRelation,
  transformLogsAnalysisPanel,
  transformTextPanel,
  transformTraceAnalysisPanel,
} from '../transform';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { DiagnosticStatusType } from '../components/diagnostic-status';
import type { DiagnosisPanelView } from '../diagnosis-view-adapter';
import type {
  DiagnosticAnalysisStatus,
  DiagnosticCommandCapability,
  DiagnosticEventGroupViewModel,
  DiagnosticIncidentViewModel,
  DiagnosticPanelDetailState,
  DiagnosticPanelState,
  DiagnosticSubPanelsState,
} from '../model';
import type { DiagnosticDataService } from '../services/diagnostic-data-service';
import type { DiagnosticPanelKey, PanelDetailParamsDto } from '../typing';
import type { DiagnosisInteraction, DiagnosisSerializableValue } from '@/components/ai-diagnosis/types';
import type {
  DimensionAnalysisViewModel,
  LogAnalysisViewModel,
  TraceAnalysisViewModel,
} from '@/components/ai-diagnosis/types';

const PANEL_KEYS: DiagnosticPanelKey[] = [
  'summary',
  'suggestion',
  'alerts_analysis',
  'trace_analysis',
  'logs_analysis',
  'events_analysis',
];
const COMMAND_UNAVAILABLE_REASON = '告警级诊断启动与重试接口尚未提供';

export interface DiagnosticCommandAdapter {
  retry?: (context: { alarmId: string; bizId: number }) => Promise<void>;
  start?: (context: { alarmId: string; bizId: number }) => Promise<void>;
}

export interface UseDiagnosticAnalysisOptions {
  alarmId?: MaybeRef<string>;
  bizId?: MaybeRef<number>;
  commandAdapter?: DiagnosticCommandAdapter;
  service?: DiagnosticDataService;
}

export type UseDiagnosticAnalysisReturn = ReturnType<typeof useDiagnosticAnalysis>;

const errorMessage = (error: unknown) => {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return '';
};

const isAborted = (error: unknown, signal: AbortSignal) =>
  signal.aborted ||
  (error instanceof Error && ['AbortError', 'CanceledError'].includes(error.name)) ||
  errorMessage(error).toLowerCase() === 'canceled';

export function useDiagnosticAnalysis(options: UseDiagnosticAnalysisOptions = {}) {
  const alarmDetailStore = storeToRefs(useAlarmCenterDetailStore());
  const alarmId = options.alarmId ?? alarmDetailStore.alarmId ?? shallowRef('');
  const bizId = options.bizId ?? alarmDetailStore.bizId ?? shallowRef(0);
  const detail = alarmDetailStore.detail as undefined | { value?: null | { bk_biz_id?: number; strategy_id?: number } };
  const service = options.service || diagnosticDataService;
  const contextKey = computed(() => `${unref(bizId)}:${unref(alarmId)}`);
  const panelState = shallowRef(createDiagnosticPanelState());
  const status = shallowRef<DiagnosticAnalysisStatus>('loading');
  const wxCsLink = shallowRef('');
  const diagnosisStatus = computed<DiagnosticStatusType | undefined>(() => {
    if (status.value === 'loading' || status.value === 'diagnosing') return 'diagnosing';
    if (status.value === 'failed') return 'error';
    if (status.value === 'notDiagnosed') return 'unconfigured';
    return undefined;
  });
  const error = shallowRef<string>();
  const incident = shallowRef<DiagnosticIncidentViewModel>();
  const summary = shallowRef('');
  const suggestion = shallowRef('');
  const alerts = shallowRef<DimensionAnalysisViewModel[]>([]);
  const traces = shallowRef<TraceAnalysisViewModel[]>([]);
  const logs = shallowRef<LogAnalysisViewModel[]>([]);
  const events = shallowRef<DiagnosticEventGroupViewModel[]>([]);
  const panelSummaries = shallowRef<Partial<Record<DiagnosticPanelKey, string>>>({});
  const panelViews = shallowRef<Partial<Record<DiagnosticPanelKey, DiagnosisPanelView>>>({});
  const subPanels = shallowRef<DiagnosticSubPanelsState>({});
  const panelDetail = shallowRef<DiagnosticPanelDetailState>();
  const activeDetailRef = shallowRef<DiagnosisSerializableValue>();
  let generation = 0;
  let requestController: AbortController | undefined;
  let detailController: AbortController | undefined;

  const clearContext = () => {
    requestController?.abort();
    detailController?.abort();
    panelState.value = createDiagnosticPanelState();
    status.value = 'loading';
    error.value = undefined;
    incident.value = undefined;
    summary.value = '';
    suggestion.value = '';
    alerts.value = [];
    traces.value = [];
    logs.value = [];
    events.value = [];
    panelSummaries.value = {};
    panelViews.value = {};
    subPanels.value = {};
    panelDetail.value = undefined;
    activeDetailRef.value = undefined;
  };

  const applyPanelData = (
    key: DiagnosticPanelKey,
    data: Awaited<ReturnType<DiagnosticDataService['getIncidentDiagnosis']>>
  ) => {
    if (['alerts_analysis', 'trace_analysis', 'logs_analysis', 'events_analysis'].includes(key)) {
      panelViews.value = { ...panelViews.value, [key]: transformDiagnosisPanelView(key, data) };
    }
    if (key === 'summary') summary.value = transformTextPanel(data);
    if (key === 'suggestion') suggestion.value = transformTextPanel(data);
    if (key === 'alerts_analysis') {
      const panel = transformAlertsAnalysisPanel(data);
      alerts.value = panel.items;
      panelSummaries.value = { ...panelSummaries.value, [key]: panel.summary };
    }
    if (key === 'trace_analysis') {
      const panel = transformTraceAnalysisPanel(data);
      traces.value = panel.items;
      panelSummaries.value = { ...panelSummaries.value, [key]: panel.summary };
    }
    if (key === 'logs_analysis') {
      const panel = transformLogsAnalysisPanel(data);
      logs.value = panel.items;
      panelSummaries.value = { ...panelSummaries.value, [key]: panel.summary };
    }
    if (key === 'events_analysis') {
      const panel = transformEventsAnalysisPanel(data);
      events.value = panel.items;
      panelSummaries.value = { ...panelSummaries.value, [key]: panel.summary };
    }
  };

  const load = async () => {
    clearContext();
    const currentGeneration = ++generation;
    const controller = new AbortController();
    requestController = controller;
    const isCurrent = () => currentGeneration === generation && !controller.signal.aborted;
    const currentAlarmId = String(unref(alarmId) || '');
    if (!currentAlarmId) {
      status.value = 'notDiagnosed';
      return;
    }

    try {
      const relationDto = await service.getAlertIncidentDetail(currentAlarmId, { signal: controller.signal });
      if (!isCurrent()) return;
      const relation = transformIncidentRelation(relationDto);
      if (!relation) {
        status.value = 'notDiagnosed';
        return;
      }
      incident.value = relation;

      const results = await service.getIncidentResults(relation.id, relation.bizId, { signal: controller.signal });
      if (!isCurrent()) return;
      const diagnosis = results.panels?.incident_diagnosis;
      const diagnosticStatus = resolveDiagnosticStatus(diagnosis);
      status.value = diagnosticStatus.status;
      error.value = diagnosticStatus.error;

      const enabledPanels =
        diagnosis?.enabled === true ? PANEL_KEYS.filter(key => diagnosis.sub_panels?.[key]?.enabled === true) : [];
      subPanels.value = Object.fromEntries(
        enabledPanels.map(key => [
          key,
          {
            enabled: true,
            loading: true,
            status: diagnosis?.sub_panels?.[key]?.status,
          },
        ])
      );
      await Promise.all(
        enabledPanels.map(async key => {
          try {
            const data = await service.getIncidentDiagnosis(relation.id, relation.bizId, key, {
              signal: controller.signal,
            });
            if (!isCurrent()) return;
            applyPanelData(key, data);
            subPanels.value = {
              ...subPanels.value,
              [key]: { ...subPanels.value[key], enabled: true, loading: false },
            };
          } catch (panelError) {
            if (!isCurrent() || isAborted(panelError, controller.signal)) return;
            subPanels.value = {
              ...subPanels.value,
              [key]: {
                ...subPanels.value[key],
                enabled: true,
                loading: false,
                error: errorMessage(panelError),
              },
            };
          }
        })
      );
    } catch (loadError) {
      if (!isCurrent() || isAborted(loadError, controller.signal)) return;
      status.value = 'failed';
      error.value = errorMessage(loadError);
    }
  };

  const openExternalLink = (url?: string) => {
    if (!url) return;
    window.open(url, '_blank', 'noopener,noreferrer');
  };
  const loadWxCsLink = async () => {
    const currentDetail = detail?.value;
    const bkBizId = currentDetail?.bk_biz_id ?? Number(unref(bizId));
    if (!bkBizId) {
      wxCsLink.value = '';
      return;
    }
    const res = await fetchAiSetting({ bk_biz_id: bkBizId }).catch(() => ({ wx_cs_link: '' }));
    wxCsLink.value = res?.wx_cs_link ?? '';
  };
  const handleConfigure = () => {
    const currentDetail = detail?.value;
    const strategyId = currentDetail?.strategy_id;
    if (!strategyId) return;
    openExternalLink(
      getBizRouteHref(`/strategy-config/edit/${strategyId}`, currentDetail?.bk_biz_id ?? Number(unref(bizId)))
    );
  };
  const handleContactAdmin = () => {
    openExternalLink(wxCsLink.value);
  };

  watch(contextKey, load, { immediate: true });
  watch([contextKey, () => detail?.value?.bk_biz_id], loadWxCsLink, {
    immediate: true,
  });

  const loadPanelDetail = async (interaction?: DiagnosisInteraction, page = 1, pageSize = 30) => {
    if (interaction?.type !== 'drawer' || !incident.value) return;
    const payload =
      interaction.payload && typeof interaction.payload === 'object' && !Array.isArray(interaction.payload)
        ? interaction.payload
        : {};
    const drawerType = payload.drawer_type;
    if (!['event', 'log', 'trace'].includes(String(drawerType))) return;
    const detailRef = interaction.detailRef;
    if (!isValidDetailRef(detailRef)) return;
    const taskId = typeof detailRef === 'object' && !Array.isArray(detailRef) ? detailRef.incident_task_id : undefined;
    const currentGeneration = generation;
    detailController?.abort();
    const controller = new AbortController();
    detailController = controller;
    activeDetailRef.value = detailRef;
    panelDetail.value = { loading: true };
    const params: PanelDetailParamsDto = {
      bk_biz_id: incident.value.bizId,
      incident_id: incident.value.incidentId,
      drawer_type: drawerType as PanelDetailParamsDto['drawer_type'],
      detail_ref: detailRef,
      ...(typeof taskId === 'string' || typeof taskId === 'number' ? { incident_task_id: String(taskId) } : {}),
      page,
      page_size: pageSize,
    };
    try {
      const data = await service.getPanelDetail(params, { signal: controller.signal });
      if (currentGeneration !== generation || controller.signal.aborted) return;
      panelDetail.value = { loading: false, data };
    } catch (detailError) {
      if (currentGeneration !== generation || isAborted(detailError, controller.signal)) return;
      panelDetail.value = { loading: false, error: errorMessage(detailError) };
    }
  };

  const commandCapability: DiagnosticCommandCapability = {
    canStart: typeof options.commandAdapter?.start === 'function',
    canRetry: typeof options.commandAdapter?.retry === 'function',
    reason:
      typeof window !== 'undefined' && window.i18n
        ? (window.i18n.t(COMMAND_UNAVAILABLE_REASON) as string)
        : COMMAND_UNAVAILABLE_REASON,
  };
  const runCommand = (command: 'retry' | 'start') => {
    const handler = options.commandAdapter?.[command];
    if (!handler) return Promise.resolve();
    return handler({ alarmId: String(unref(alarmId) || ''), bizId: Number(unref(bizId)) });
  };

  onScopeDispose(() => {
    generation += 1;
    requestController?.abort();
    detailController?.abort();
  });

  const handleDraftChange = (draft: DiagnosticPanelState['draft']) => {
    panelState.value = { ...panelState.value, draft };
  };

  return {
    activeDetailRef,
    alerts,
    commandCapability,
    contextKey,
    diagnosisStatus,
    error,
    handleConfigure,
    handleContactAdmin,
    events,
    incident,
    loadPanelDetail,
    logs,
    panelDetail,
    panelSummaries,
    panelViews,
    panelState,
    reload: load,
    retryDiagnosis: () => runCommand('retry'),
    startDiagnosis: () => runCommand('start'),
    status,
    subPanels,
    suggestion,
    summary,
    traces,
    wxCsLink,
    // 会话发送由 useDiagnosticSession 接管；这里保留禁用态，避免面板数据 hook 直接发消息。
    messageStatus: MessageStatus.Disabled,
    handleDraftChange,
  };
}
