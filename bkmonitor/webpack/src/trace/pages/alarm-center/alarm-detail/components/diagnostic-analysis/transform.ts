import type { DiagnosticAnalysisStatus, DiagnosticEventGroupViewModel, DiagnosticIncidentViewModel } from './model';
import type {
  AlertIncidentDetailDto,
  AlertsAnalysisItemDto,
  DiagnosisInteractionDto,
  IncidentDiagnosisDto,
  IncidentDiagnosisStatusDto,
  LogAnalysisItemDto,
  TraceAnalysisItemDto,
} from './typing';
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
import type {
  DiagnosisAnalysisPanel,
  DiagnosisInteraction,
  DiagnosisSerializableValue,
  DimensionAnalysisViewModel,
  EventAnalysisGroupViewModel,
  LogAnalysisViewModel,
  TraceAnalysisViewModel,
} from '@/components/ai-diagnosis/types';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const asIdString = (value: unknown): string | undefined => {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' && Number.isSafeInteger(value)) return String(value);
  return undefined;
};

const asDisplayString = (value: unknown): string | undefined => {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return undefined;
};

const asNumber = (value: unknown): number | undefined =>
  typeof value === 'number' && Number.isFinite(value) ? value : undefined;

const toSerializable = (value: unknown): DiagnosisSerializableValue | undefined => {
  if (value === null || ['string', 'boolean'].includes(typeof value)) {
    return value as DiagnosisSerializableValue;
  }
  if (typeof value === 'number') return Number.isFinite(value) ? value : undefined;
  if (Array.isArray(value)) {
    return value.flatMap(item => {
      const serializable = toSerializable(item);
      return serializable === undefined ? [] : [serializable];
    });
  }
  if (!isRecord(value)) return undefined;
  return Object.fromEntries(
    Object.entries(value).flatMap(([key, item]) => {
      const serializable = toSerializable(item);
      return serializable === undefined ? [] : [[key, serializable]];
    })
  );
};

export const isValidDetailRef = (value: unknown): value is Record<string, DiagnosisSerializableValue> => {
  if (!isRecord(value) || !Object.keys(value).length) return false;
  const panel = value.panel;
  const taskId = value.incident_task_id;
  const hasValidTaskId =
    (typeof taskId === 'string' && /^[1-9]\d*$/.test(taskId)) ||
    (typeof taskId === 'number' && Number.isSafeInteger(taskId) && taskId > 0);
  return typeof panel === 'string' && panel.length > 0 && hasValidTaskId;
};

export const transformInteraction = (value: unknown): DiagnosisInteraction | undefined => {
  if (!isRecord(value)) return undefined;
  const interaction = value as DiagnosisInteractionDto;
  const payload = toSerializable(value);
  if (
    interaction.action === 'link' &&
    typeof interaction.url === 'string' &&
    /^(https?:\/\/|\/(?!\/)|#)/.test(interaction.url)
  ) {
    return { type: 'link', target: interaction.url, payload };
  }
  if (interaction.action === 'drawer' && isValidDetailRef(interaction.detail_ref)) {
    const detailRef = toSerializable(interaction.detail_ref);
    return { type: 'drawer', detailRef, payload };
  }
  if (interaction.action === 'error') {
    const message =
      asDisplayString(interaction.error?.code) ||
      asDisplayString(interaction.error?.target) ||
      asDisplayString(value.message) ||
      'diagnosis_interaction_error';
    return { type: 'error', message, payload };
  }
  if (interaction.action && !['none', 'link', 'drawer', 'error'].includes(interaction.action)) {
    return { type: 'none', payload };
  }
  return payload ? { type: 'none', payload } : undefined;
};

export const transformIncidentRelation = (dto: AlertIncidentDetailDto): DiagnosticIncidentViewModel | undefined => {
  const incident = dto.incident;
  if (!incident || !Object.keys(incident).length) return undefined;
  const id = asIdString(incident.id);
  const incidentId = asIdString(incident.incident_id);
  const bizId = asNumber(incident.bk_biz_id);
  if (!id || !incidentId || bizId === undefined) return undefined;
  return {
    id,
    incidentId,
    bizId,
    name: asDisplayString(incident.incident_name) || '',
    alertCount: asNumber(incident.alert_count),
    treatmentPlans: Array.isArray(incident.treatment_plans)
      ? incident.treatment_plans.flatMap((plan, index) => {
          const name = asDisplayString(plan.name);
          if (!name || !['failed', 'success'].includes(String(plan.status))) return [];
          return [
            {
              id: asIdString(plan.id) || `treatment-plan-${index + 1}`,
              name,
              status: plan.status as 'failed' | 'success',
              time: asDisplayString(plan.time),
            },
          ];
        })
      : [],
  };
};

const toDimensionValues = (
  value: unknown
): Record<string, Array<number | string> | null | number | string | undefined> | undefined => {
  if (!isRecord(value)) return undefined;
  const result: Record<string, Array<number | string> | null | number | string | undefined> = {};
  for (const [key, item] of Object.entries(value)) {
    if (item === null) {
      result[key] = null;
    } else if (typeof item === 'string' || typeof item === 'number') {
      result[key] = item;
    } else if (Array.isArray(item)) {
      result[key] = item.filter(
        (entry): entry is number | string => typeof entry === 'string' || typeof entry === 'number'
      );
    }
  }
  return result;
};

export const transformAlertsAnalysis = (dto: IncidentDiagnosisDto): DimensionAnalysisViewModel[] => {
  if (!Array.isArray(dto.contents)) return [];
  return dto.contents.flatMap((value, index) => {
    if (!isRecord(value)) return [];
    const item = value as AlertsAnalysisItemDto;
    const firstAlertId = Array.isArray(item.alerts) ? asIdString(item.alerts[0]?.id) : undefined;
    const alerts = Array.isArray(item.alerts)
      ? item.alerts.flatMap(alert => {
          const id = asIdString(alert.id);
          if (!id) return [];
          return [
            {
              id,
              strategyId: asIdString(alert.strategy_id),
              strategyName: asDisplayString(alert.strategy_name),
            },
          ];
        })
      : [];
    const strategies = isRecord(item.strategy_alerts_mapping)
      ? Object.entries(item.strategy_alerts_mapping).flatMap(([key, strategy]) => {
          if (!isRecord(strategy)) return [];
          const id = asIdString(strategy.strategy_id) || key;
          const alertIds = Array.isArray(strategy.alerts)
            ? strategy.alerts.flatMap(alertId => {
                const id = asIdString(alertId);
                return id ? [id] : [];
              })
            : [];
          const interaction = transformInteraction(strategy.interaction);
          return [
            {
              id,
              name: asDisplayString(strategy.strategy_name) || id,
              alertIds,
              ...(interaction ? { interaction } : {}),
            },
          ];
        })
      : [];
    return [
      {
        id: firstAlertId || `alerts-analysis-${index + 1}`,
        score: asNumber(item.score),
        dimensions: toDimensionValues(item.dimension_values),
        alertCount: asNumber(item.alert_count),
        alerts,
        strategies,
        interaction: transformInteraction(item.interaction),
      },
    ];
  });
};

export const transformTraceAnalysis = (dto: IncidentDiagnosisDto): TraceAnalysisViewModel[] => {
  if (!isRecord(dto.contents) || !Array.isArray(dto.contents.trace_messages_analysis)) return [];
  return dto.contents.trace_messages_analysis.flatMap((value, index) => {
    if (!isRecord(value)) return [];
    const item = value as TraceAnalysisItemDto;
    const traceId = asIdString(item.trace_id);
    return [
      {
        id: traceId || `trace-analysis-${index + 1}`,
        title: asDisplayString(item.name),
        traceId,
        spanId: asIdString(item.span_id),
        appName: asDisplayString(item.app_name),
        serviceName: asDisplayString(item.service_name) || asDisplayString(item.app_name),
        spanName: asDisplayString(item.span_name) || asDisplayString(item.name),
        kind: asDisplayString(item.kind),
        logCount: asNumber(item.log_count),
        pattern: asDisplayString(item.pattern) || asDisplayString(item.error_message) || asDisplayString(item.error),
        error: asDisplayString(item.error_message) || asDisplayString(item.error),
        interaction: transformInteraction(item.interaction),
      },
    ];
  });
};

export const transformLogsAnalysis = (dto: IncidentDiagnosisDto): LogAnalysisViewModel[] => {
  if (!isRecord(dto.contents) || !Array.isArray(dto.contents.logs_from_alerts)) return [];
  return dto.contents.logs_from_alerts.flatMap((value, index) => {
    if (!isRecord(value)) return [];
    const item = value as LogAnalysisItemDto;
    return [
      {
        id: `logs-analysis-${index + 1}`,
        pattern: asDisplayString(item.pattern),
        sample: asDisplayString(item.sample) || asDisplayString(item.demo_log),
        source: asDisplayString(item.source) || asDisplayString(item.log_source),
        logCount: asNumber(item.log_count),
        interaction: transformInteraction(item.interaction),
      },
    ];
  });
};

const resolveEventSource = (group: string): EventAnalysisGroupViewModel['source'] => {
  if (/k8s|bcs/i.test(group)) return 'bcs';
  if (/ticket|itsm/i.test(group)) return 'itsm';
  return 'other';
};

export const transformEventsAnalysis = (dto: IncidentDiagnosisDto): DiagnosticEventGroupViewModel[] => {
  if (!isRecord(dto.contents)) return [];
  return Object.entries(dto.contents).flatMap(([group, value]) => {
    if (!Array.isArray(value)) return [];
    const fields = dto.display?.fields?.[group] || {};
    const labels = dto.display?.labels_mapping?.[group];
    const items = value.flatMap((record, index) => {
      if (!isRecord(record)) return [];
      const values = Object.fromEntries(
        Object.keys(fields).flatMap(key => {
          const fieldValue = record[key];
          return ['string', 'number', 'boolean'].includes(typeof fieldValue) || fieldValue === null
            ? [[key, fieldValue]]
            : [];
        })
      );
      return [
        {
          id: `${group}-${index + 1}`,
          title: asDisplayString(record.title),
          eventName: asDisplayString(record.event_name) || asDisplayString(record.title),
          time: asDisplayString(record.time),
          reason:
            asDisplayString(record.event_content) ||
            asDisplayString(record.desc) ||
            asDisplayString(record.description) ||
            asDisplayString(record.impact),
          subCount: asNumber(record._sub_count),
          values,
          interaction: transformInteraction(record.interaction),
        },
      ];
    });
    return [
      {
        id: group,
        title: labels?.label || group,
        source: resolveEventSource(group),
        unit: labels?.unit,
        top: asNumber(labels?.top),
        total: asNumber(dto.display?.statistics?.[group]?.total),
        fields,
        items,
        interaction: transformInteraction(labels?.interaction),
      },
    ];
  });
};

const transformPanel = <T>(dto: IncidentDiagnosisDto, items: T[]): DiagnosisAnalysisPanel<T> => ({
  items,
  summary: asDisplayString(dto.individual_summary) || '',
});

export const transformAlertsAnalysisPanel = (
  dto: IncidentDiagnosisDto
): DiagnosisAnalysisPanel<DimensionAnalysisViewModel> => transformPanel(dto, transformAlertsAnalysis(dto));

export const transformTraceAnalysisPanel = (
  dto: IncidentDiagnosisDto
): DiagnosisAnalysisPanel<TraceAnalysisViewModel> => transformPanel(dto, transformTraceAnalysis(dto));

export const transformLogsAnalysisPanel = (dto: IncidentDiagnosisDto): DiagnosisAnalysisPanel<LogAnalysisViewModel> =>
  transformPanel(dto, transformLogsAnalysis(dto));

export const transformEventsAnalysisPanel = (
  dto: IncidentDiagnosisDto
): DiagnosisAnalysisPanel<DiagnosticEventGroupViewModel> => transformPanel(dto, transformEventsAnalysis(dto));

export const transformTextPanel = (dto: IncidentDiagnosisDto): string =>
  typeof dto.contents === 'string' ? dto.contents : '';

export const resolveDiagnosticStatus = (
  diagnosis?: IncidentDiagnosisStatusDto
): { error?: string; status: DiagnosticAnalysisStatus } => {
  if (diagnosis?.enabled !== true) return { status: 'notDiagnosed' };
  if (diagnosis.status === 'running') return { status: 'diagnosing' };
  if (diagnosis.status === 'failed') {
    return { status: 'failed', ...(diagnosis.message ? { error: diagnosis.message } : {}) };
  }
  const hasEnabledPanel = Object.values(diagnosis.sub_panels || {}).some(panel => panel?.enabled === true);
  if (diagnosis.status === 'finished' && hasEnabledPanel) return { status: 'ready' };
  return { status: 'notDiagnosed' };
};
