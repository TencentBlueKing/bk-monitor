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
  DiagnosisInteraction,
  DiagnosisRelatedFailure,
  DiagnosisSummaryVariant,
  DimensionAnalysisViewModel,
  EventAnalysisViewModel,
  LogAnalysisViewModel,
  TraceAnalysisViewModel,
} from '@/components/ai-diagnosis';

export type AlertAnalysisMessage =
  | { payload: AnalysisPayload<DimensionAnalysisViewModel>; schemaVersion: 1; type: 'dimension_analysis' }
  | { payload: AnalysisPayload<EventAnalysisViewModel>; schemaVersion: 1; type: 'event_analysis' }
  | { payload: AnalysisPayload<LogAnalysisViewModel>; schemaVersion: 1; type: 'log_analysis' }
  | { payload: AnalysisPayload<TraceAnalysisViewModel>; schemaVersion: 1; type: 'trace_analysis' }
  | { payload: SummaryPayload; schemaVersion: 1; type: 'summary' };

type AnalysisPayload<T> = {
  items: T[];
  summary?: string;
};

type SummaryPayload = {
  alertReason?: string;
  recommendation?: string;
  relatedFailure?: DiagnosisRelatedFailure;
  treatmentPlan?: string;
  variant?: DiagnosisSummaryVariant;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const hasOnlyKeys = (value: Record<string, unknown>, keys: string[]) =>
  Object.keys(value).every(key => keys.includes(key));

const isInteraction = (value: unknown): value is DiagnosisInteraction => {
  if (!isRecord(value) || typeof value.type !== 'string') return false;
  if (value.type === 'link') {
    return (
      typeof value.target === 'string' &&
      /^(https?:\/\/|\/(?!\/)|#)/.test(value.target) &&
      hasOnlyKeys(value, ['payload', 'target', 'type'])
    );
  }
  if (value.type === 'drawer') {
    if (!isRecord(value.detailRef) || typeof value.detailRef.panel !== 'string') return false;
    const taskId = value.detailRef.incident_task_id;
    const validTaskId =
      (typeof taskId === 'string' && /^[1-9]\d*$/.test(taskId)) ||
      (typeof taskId === 'number' && Number.isSafeInteger(taskId) && taskId > 0);
    return validTaskId && hasOnlyKeys(value, ['detailRef', 'payload', 'type']);
  }
  if (value.type === 'error') {
    return typeof value.message === 'string' && hasOnlyKeys(value, ['message', 'payload', 'type']);
  }
  if (value.type === 'action') {
    return typeof value.action === 'string' && hasOnlyKeys(value, ['action', 'payload', 'type']);
  }
  return value.type === 'none' && hasOnlyKeys(value, ['payload', 'type']);
};

const isOptionalString = (value: unknown) => value === undefined || typeof value === 'string';
const isOptionalInteraction = (value: unknown) => value === undefined || isInteraction(value);
const isDimensionValue = (value: unknown) =>
  value === null ||
  value === undefined ||
  typeof value === 'string' ||
  typeof value === 'number' ||
  (Array.isArray(value) && value.every(item => typeof item === 'string' || typeof item === 'number'));
const isDimensions = (value: unknown) => isRecord(value) && Object.values(value).every(isDimensionValue);

const hasOnlyOptionalStrings = (value: Record<string, unknown>, keys: string[]) =>
  Object.entries(value).every(([key, item]) => keys.includes(key) && typeof item === 'string');

const isSummaryPayload = (value: unknown): value is SummaryPayload =>
  isRecord(value) &&
  hasOnlyOptionalStrings(
    Object.fromEntries(
      Object.entries(value).filter(([key]) => ['alertReason', 'recommendation', 'treatmentPlan'].includes(key))
    ),
    ['alertReason', 'recommendation', 'treatmentPlan']
  ) &&
  (value.variant === undefined || ['linked', 'unlinked'].includes(String(value.variant))) &&
  (value.relatedFailure === undefined ||
    (isRecord(value.relatedFailure) &&
      typeof value.relatedFailure.label === 'string' &&
      isOptionalInteraction(value.relatedFailure.interaction) &&
      hasOnlyKeys(value.relatedFailure, ['interaction', 'label']))) &&
  Object.keys(value).every(key =>
    ['alertReason', 'recommendation', 'relatedFailure', 'treatmentPlan', 'variant'].includes(key)
  );

const isDimensionItem = (value: unknown): value is DimensionAnalysisViewModel =>
  isRecord(value) &&
  typeof value.id === 'string' &&
  isOptionalString(value.title) &&
  (value.score === undefined || (typeof value.score === 'number' && Number.isFinite(value.score))) &&
  (value.alertCount === undefined || (typeof value.alertCount === 'number' && Number.isFinite(value.alertCount))) &&
  (value.dimensions === undefined || isDimensions(value.dimensions)) &&
  isOptionalInteraction(value.interaction) &&
  hasOnlyKeys(value, ['alertCount', 'dimensions', 'id', 'interaction', 'score', 'title']);

const isTraceItem = (value: unknown): value is TraceAnalysisViewModel =>
  isRecord(value) &&
  typeof value.id === 'string' &&
  ['title', 'traceId', 'serviceName', 'spanName', 'error'].every(key => isOptionalString(value[key])) &&
  isOptionalInteraction(value.interaction) &&
  hasOnlyKeys(value, ['error', 'id', 'interaction', 'serviceName', 'spanName', 'title', 'traceId']);

const isLogItem = (value: unknown): value is LogAnalysisViewModel =>
  isRecord(value) &&
  typeof value.id === 'string' &&
  ['title', 'pattern', 'sample', 'source'].every(key => isOptionalString(value[key])) &&
  isOptionalInteraction(value.interaction) &&
  hasOnlyKeys(value, ['id', 'interaction', 'pattern', 'sample', 'source', 'title']);

const isEventItem = (value: unknown): value is EventAnalysisViewModel =>
  isRecord(value) &&
  typeof value.id === 'string' &&
  ['title', 'eventName', 'time', 'reason'].every(key => isOptionalString(value[key])) &&
  isOptionalInteraction(value.interaction) &&
  hasOnlyKeys(value, ['eventName', 'id', 'interaction', 'reason', 'time', 'title']);

const isAnalysisPayload = <T>(
  value: unknown,
  validateItem: (item: unknown) => item is T
): value is AnalysisPayload<T> =>
  isRecord(value) &&
  Array.isArray(value.items) &&
  value.items.every(validateItem) &&
  (value.summary === undefined || typeof value.summary === 'string') &&
  Object.keys(value).every(key => key === 'items' || key === 'summary');

export const parseAlertAnalysisMessage = (value: unknown): AlertAnalysisMessage | null => {
  if (!isRecord(value) || value.schemaVersion !== 1 || typeof value.type !== 'string') return null;
  if (value.type === 'summary' && isSummaryPayload(value.payload)) {
    return value as AlertAnalysisMessage;
  }
  if (value.type === 'dimension_analysis' && isAnalysisPayload(value.payload, isDimensionItem))
    return value as AlertAnalysisMessage;
  if (value.type === 'trace_analysis' && isAnalysisPayload(value.payload, isTraceItem))
    return value as AlertAnalysisMessage;
  if (value.type === 'log_analysis' && isAnalysisPayload(value.payload, isLogItem))
    return value as AlertAnalysisMessage;
  if (value.type === 'event_analysis' && isAnalysisPayload(value.payload, isEventItem))
    return value as AlertAnalysisMessage;
  return null;
};

export const getAlertAnalysisMessage = (message: unknown): AlertAnalysisMessage | null => {
  if (!isRecord(message) || !isRecord(message.property) || !isRecord(message.property.extra)) return null;
  return parseAlertAnalysisMessage(message.property.extra.alert_analysis_message);
};
