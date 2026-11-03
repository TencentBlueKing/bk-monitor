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
import { transformInteraction } from './transform';

import type { DiagnosticPanelKey, IncidentDiagnosisDto } from './typing';
import type {
  DiagnosisAnalysisViewModel,
  DiagnosisContentCardViewModel,
  DiagnosisDetailAction,
  DiagnosisDisplayValue,
  DiagnosisGroupViewModel,
  DiagnosisInteractiveContent,
  DiagnosisSummaryViewModel,
  DimensionDiagnosisViewModel,
  EventDiagnosisAnalysisViewModel,
} from '@/components/ai-diagnosis/view-types';

export type DiagnosisPanelView =
  | DiagnosisAnalysisViewModel<DiagnosisContentCardViewModel>
  | DiagnosisAnalysisViewModel<DimensionDiagnosisViewModel>
  | EventDiagnosisAnalysisViewModel;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const asString = (value: unknown) => {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return '';
};

const asNumber = (value: unknown) => (typeof value === 'number' && Number.isFinite(value) ? value : undefined);

const toDisplayValue = (value: unknown): DiagnosisDisplayValue | undefined => {
  if (value === null || ['string', 'boolean'].includes(typeof value)) {
    return value as DiagnosisDisplayValue;
  }
  if (typeof value === 'number') return Number.isFinite(value) ? value : undefined;
  if (Array.isArray(value)) {
    return value.flatMap(item => {
      const displayValue = toDisplayValue(item);
      return displayValue === undefined ? [] : [displayValue];
    });
  }
  if (!isRecord(value)) return undefined;
  return Object.fromEntries(
    Object.entries(value).flatMap(([key, item]) => {
      if (key === 'interaction') return [];
      const displayValue = toDisplayValue(item);
      return displayValue === undefined ? [] : [[key, displayValue]];
    })
  );
};

const toDisplayText = (value: DiagnosisDisplayValue) => {
  if (value === null) return '';
  if (Array.isArray(value)) return value.map(item => toDisplayText(item)).join(', ');
  if (isRecord(value)) return JSON.stringify(value);
  return String(value);
};

const toDetailAction = (value: unknown): DiagnosisDetailAction | undefined => {
  const interaction = transformInteraction(value);
  if (!interaction || interaction.type === 'action') return undefined;
  return interaction;
};

const createContent = ({
  addToChat = true,
  detailAction,
  format = 'text',
  itemId,
  key,
  label,
  panel,
  value,
}: {
  addToChat?: boolean;
  detailAction?: DiagnosisDetailAction;
  format?: DiagnosisInteractiveContent['format'];
  itemId: string;
  key: string;
  label?: string;
  panel: DiagnosticPanelKey;
  value: DiagnosisDisplayValue;
}): DiagnosisInteractiveContent => ({
  addToChat,
  chatReference: {
    ...(detailAction?.type === 'drawer' ? { detailRef: detailAction.detailRef } : {}),
    displayText: toDisplayText(value),
    fieldKey: key,
    itemId,
    panel,
  },
  ...(detailAction ? { detailAction } : {}),
  ...(format === 'text' ? {} : { format }),
  key,
  ...(label ? { label } : {}),
  value,
});

const createSummary = (panel: DiagnosticPanelKey, value: unknown): DiagnosisInteractiveContent | undefined => {
  const summary = asString(value);
  if (!summary) return undefined;
  return createContent({
    addToChat: false,
    format: 'markdown',
    itemId: `${panel}-summary`,
    key: 'summary',
    panel,
    value: summary,
  });
};

const transformDimensions = (dto: IncidentDiagnosisDto): DiagnosisAnalysisViewModel<DimensionDiagnosisViewModel> => {
  const items = Array.isArray(dto.contents) ? dto.contents : [];
  return {
    items: items.flatMap((value, index) => {
      if (!isRecord(value)) return [];
      const id = `alerts-analysis-${index + 1}`;
      const detailAction = toDetailAction(value.interaction);
      const rows = isRecord(value.dimension_values)
        ? Object.entries(value.dimension_values).flatMap(([key, rawValue]) => {
            const displayValue = toDisplayValue(rawValue);
            if (displayValue === undefined || toDisplayText(displayValue) === '') return [];
            const normalizedValue = Array.isArray(displayValue) ? toDisplayText(displayValue) : displayValue;
            return [
              createContent({
                detailAction,
                itemId: id,
                key,
                label: key,
                panel: 'alerts_analysis',
                value: normalizedValue,
              }),
            ];
          })
        : [];
      const alertCount = asNumber(value.alert_count);
      return [
        {
          alertCount,
          ...(alertCount === undefined
            ? {}
            : {
                alertCountContent: createContent({
                  addToChat: false,
                  itemId: id,
                  key: 'alert_count',
                  panel: 'alerts_analysis',
                  value: `共 ${alertCount} 个告警`,
                }),
              }),
          blocks: [],
          detailAction,
          id,
          metric: asNumber(value.score) === undefined ? undefined : `${Math.round(Number(value.score) * 100)}%`,
          promptAction: { text: `异常维度（组合）${index + 1}` },
          rows,
          title: `异常维度（组合）${index + 1}`,
        },
      ];
    }),
    summary: createSummary('alerts_analysis', dto.individual_summary),
  };
};

const TRACE_FIELDS: Array<[string, string]> = [
  ['span_id', 'Span ID'],
  ['trace_id', '所属 Trace'],
  ['app_name', '所属应用'],
  ['service_name', '所属服务'],
  ['kind', '调用类型'],
  ['error_message', '异常信息'],
  ['error', '异常信息'],
];

const transformTraces = (dto: IncidentDiagnosisDto): DiagnosisAnalysisViewModel<DiagnosisContentCardViewModel> => {
  const records =
    isRecord(dto.contents) && Array.isArray(dto.contents.trace_messages_analysis)
      ? dto.contents.trace_messages_analysis
      : [];
  return {
    items: records.flatMap((value, index) => {
      if (!isRecord(value)) return [];
      const id = `trace-analysis-${index + 1}`;
      const detailAction = toDetailAction(value.interaction);
      const pattern = asString(value.pattern);
      const rows = TRACE_FIELDS.flatMap(([key, label]) => {
        const displayValue = toDisplayValue(value[key]);
        if (displayValue === undefined || toDisplayText(displayValue) === '') return [];
        return [
          createContent({
            detailAction,
            itemId: id,
            key,
            label,
            panel: 'trace_analysis',
            value: displayValue,
          }),
        ];
      });
      const count = asNumber(value.log_count);
      return [
        {
          blocks: pattern
            ? [
                createContent({
                  itemId: id,
                  key: 'pattern',
                  label: 'Pattern:',
                  panel: 'trace_analysis',
                  value: pattern,
                }),
              ]
            : [],
          detailAction,
          id,
          rows,
          title: `分析结果 ${index + 1}${count === undefined ? '' : `（共 ${count} 条 Span）`}`,
        },
      ];
    }),
    summary: createSummary('trace_analysis', dto.individual_summary),
  };
};

const transformLogs = (dto: IncidentDiagnosisDto): DiagnosisAnalysisViewModel<DiagnosisContentCardViewModel> => {
  const records =
    isRecord(dto.contents) && Array.isArray(dto.contents.logs_from_alerts) ? dto.contents.logs_from_alerts : [];
  return {
    items: records.flatMap((value, index) => {
      if (!isRecord(value)) return [];
      const id = `logs-analysis-${index + 1}`;
      const detailAction = toDetailAction(value.interaction);
      const blocks: DiagnosisInteractiveContent[] = [];
      const pattern = asString(value.pattern);
      const sample = asString(value.sample) || asString(value.demo_log);
      if (pattern) {
        blocks.push(
          createContent({
            detailAction,
            itemId: id,
            key: 'pattern',
            label: 'Pattern:',
            panel: 'logs_analysis',
            value: pattern,
          })
        );
      }
      if (sample) {
        blocks.push(
          createContent({
            detailAction,
            itemId: id,
            key: 'sample',
            label: '示例日志:',
            panel: 'logs_analysis',
            value: sample,
          })
        );
      }
      const count = asNumber(value.log_count);
      return [
        {
          blocks,
          detailAction,
          id,
          promptAction: { text: `展开查看聚类结果 ${index + 1} 的日志明细` },
          rows: [],
          title: `聚类结果 ${index + 1}${count === undefined ? '' : ` (共 ${count} 条日志)`}`,
        },
      ];
    }),
    summary: createSummary('logs_analysis', dto.individual_summary),
  };
};

const eventTitle = (record: Record<string, unknown>, index: number) =>
  asString(record.title) || asString(record.event_name) || `事件 ${index + 1}`;

const transformEvents = (dto: IncidentDiagnosisDto): EventDiagnosisAnalysisViewModel => {
  if (!isRecord(dto.contents)) return { groups: [], summary: createSummary('events_analysis', dto.individual_summary) };
  return {
    groups: Object.entries(dto.contents).flatMap(([groupKey, value]) => {
      if (!Array.isArray(value)) return [];
      const fields = dto.display?.fields?.[groupKey] || {};
      const labelConfig = dto.display?.labels_mapping?.[groupKey];
      const total = asNumber(dto.display?.statistics?.[groupKey]?.total);
      const detailAction = toDetailAction(labelConfig?.interaction);
      const title = labelConfig?.label || groupKey;
      const top = asNumber(labelConfig?.top);
      const unit = labelConfig?.unit || '个';
      const totalText = total === undefined ? '' : `(共 ${total} ${unit}事件，展示 Top${top || value.length} 如下)`;
      const group: DiagnosisGroupViewModel = {
        detailAction,
        id: groupKey,
        items: value.flatMap((record, index) => {
          if (!isRecord(record)) return [];
          const itemId = `${groupKey}-${index + 1}`;
          const recordAction = toDetailAction(record.interaction);
          const rows = Object.entries(fields).flatMap(([key, label]) => {
            const displayValue = toDisplayValue(record[key]);
            if (displayValue === undefined || toDisplayText(displayValue) === '') return [];
            return [
              createContent({
                detailAction: recordAction,
                itemId,
                key,
                label,
                panel: 'events_analysis',
                value: displayValue,
              }),
            ];
          });
          const rawValue = toDisplayValue(record);
          const blocks =
            rows.length || rawValue === undefined
              ? []
              : [
                  createContent({
                    detailAction: recordAction,
                    format: 'json',
                    itemId,
                    key: 'raw',
                    panel: 'events_analysis',
                    value: rawValue,
                  }),
                ];
          return [
            {
              blocks,
              detailAction: recordAction,
              id: itemId,
              rows,
              title: eventTitle(record, index),
            },
          ];
        }),
        ...(total === undefined ? {} : { promptAction: { text: `${title}这 ${total} 个事件分别是什么？` } }),
        title,
        totalText,
      };
      return [group];
    }),
    summary: createSummary('events_analysis', dto.individual_summary),
  };
};

export const transformDiagnosisPanelView = (
  panel: DiagnosticPanelKey,
  dto: IncidentDiagnosisDto
): DiagnosisPanelView => {
  if (panel === 'alerts_analysis') return transformDimensions(dto);
  if (panel === 'trace_analysis') return transformTraces(dto);
  if (panel === 'logs_analysis') return transformLogs(dto);
  if (panel === 'events_analysis') return transformEvents(dto);
  return { items: [] };
};

export const transformDiagnosisSummaryView = ({
  alertReason,
  recommendation,
  relatedFailure,
  treatmentPlans,
  variant,
}: {
  alertReason: string;
  recommendation: string;
  relatedFailure?: { detailAction?: DiagnosisDetailAction; label: string };
  treatmentPlans: Array<{ id: string; name: string; status: 'failed' | 'success'; time?: string }>;
  variant: DiagnosisSummaryViewModel['variant'];
}): DiagnosisSummaryViewModel => ({
  alertReason: alertReason
    ? createContent({
        format: 'markdown',
        itemId: 'diagnosis-summary',
        key: 'alert_reason',
        panel: 'summary',
        value: alertReason,
      })
    : undefined,
  recommendation: recommendation
    ? createContent({
        format: 'markdown',
        itemId: 'diagnosis-summary',
        key: 'recommendation',
        panel: 'suggestion',
        value: recommendation,
      })
    : undefined,
  relatedFailure: relatedFailure
    ? createContent({
        detailAction: relatedFailure.detailAction,
        itemId: 'diagnosis-summary',
        key: 'related_failure',
        panel: 'summary',
        value: relatedFailure.label,
      })
    : undefined,
  treatmentPlans: treatmentPlans.map(plan => ({
    content: createContent({
      itemId: plan.id,
      key: 'treatment_plan',
      panel: 'suggestion',
      value: plan.name,
    }),
    id: plan.id,
    status: plan.status,
    time: plan.time,
  })),
  variant,
});
