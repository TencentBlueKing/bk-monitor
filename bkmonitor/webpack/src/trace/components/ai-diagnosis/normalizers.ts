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
  DiagnosisCollapseCardViewModel,
  DiagnosisValueRow,
  DimensionAnalysisViewModel,
  EventAnalysisViewModel,
  LogAnalysisViewModel,
  TraceAnalysisViewModel,
} from './types';

const hasValue = (value: unknown) => value !== undefined && value !== null && value !== '';

const createRow = (key: string, label: string, value: unknown): DiagnosisValueRow | undefined => {
  if (!hasValue(value)) return undefined;
  return { key, label, value: String(value) };
};

const compactRows = (rows: Array<DiagnosisValueRow | undefined>) =>
  rows.filter((row): row is DiagnosisValueRow => Boolean(row));

export type DiagnosisFieldLabels = Partial<
  Record<
    | 'error'
    | 'eventName'
    | 'pattern'
    | 'reason'
    | 'sample'
    | 'serviceName'
    | 'source'
    | 'spanName'
    | 'time'
    | 'traceId',
    string
  >
>;

export const normalizeDimensionAnalysis = (items: DimensionAnalysisViewModel[]): DiagnosisCollapseCardViewModel[] =>
  items.map((item, index) => ({
    id: item.id,
    title: item.title,
    index: index + 1,
    metric: Number.isFinite(item.score) ? `${((item.score as number) * 100).toFixed(2)}%` : undefined,
    rows: Object.entries(item.dimensions || {}).flatMap(([label, value]) => {
      const displayValue = Array.isArray(value) ? value.filter(hasValue).join('、') : value;
      const row = createRow(label, label, displayValue);
      return row ? [row] : [];
    }),
    interaction: item.interaction,
  }));

export const normalizeTraceAnalysis = (
  items: TraceAnalysisViewModel[],
  labels: DiagnosisFieldLabels = {}
): DiagnosisCollapseCardViewModel[] =>
  items.map((item, index) => ({
    id: item.id,
    title: item.title,
    index: index + 1,
    rows: compactRows([
      createRow('traceId', labels.traceId || '', item.traceId),
      createRow('serviceName', labels.serviceName || '', item.serviceName),
      createRow('spanName', labels.spanName || '', item.spanName),
      createRow('error', labels.error || '', item.error),
    ]),
    interaction: item.interaction,
  }));

export const normalizeLogAnalysis = (
  items: LogAnalysisViewModel[],
  labels: DiagnosisFieldLabels = {}
): DiagnosisCollapseCardViewModel[] =>
  items.map((item, index) => ({
    id: item.id,
    title: item.title,
    index: index + 1,
    rows: compactRows([
      createRow('pattern', labels.pattern || '', item.pattern),
      createRow('sample', labels.sample || '', item.sample),
      createRow('source', labels.source || '', item.source),
    ]),
    interaction: item.interaction,
  }));

export const normalizeEventAnalysis = (
  items: EventAnalysisViewModel[],
  labels: DiagnosisFieldLabels = {}
): DiagnosisCollapseCardViewModel[] =>
  items.map((item, index) => ({
    id: item.id,
    title: item.title,
    index: index + 1,
    rows: compactRows([
      createRow('eventName', labels.eventName || '', item.eventName),
      createRow('time', labels.time || '', item.time),
      createRow('reason', labels.reason || '', item.reason),
    ]),
    interaction: item.interaction,
  }));
