export interface DiagnosisAnalysisPanel<T> {
  items: T[];
  summary: string;
}
export interface DiagnosisCollapseCardViewModel {
  id: string;
  index?: number;
  interaction?: DiagnosisInteraction;
  metric?: string;
  rows: DiagnosisValueRow[];
  title?: string;
}
export type DiagnosisInteraction<TPayload extends DiagnosisSerializableValue = DiagnosisSerializableValue> =
  | { action: string; payload?: TPayload; type: 'action' }
  | { detailRef: DiagnosisSerializableValue; payload?: TPayload; type: 'drawer' }
  | { message: string; payload?: TPayload; type: 'error' }
  | { payload?: TPayload; target: string; type: 'link' }
  | { payload?: TPayload; type: 'none' };

export interface DiagnosisRelatedFailure {
  interaction?: DiagnosisInteraction;
  label: string;
}

export type DiagnosisSerializablePrimitive = boolean | null | number | string;

export type DiagnosisSerializableValue =
  | DiagnosisSerializablePrimitive
  | DiagnosisSerializableValue[]
  | { [key: string]: DiagnosisSerializableValue };

export interface DiagnosisStrategyViewModel {
  alertIds: string[];
  id: string;
  interaction?: DiagnosisInteraction;
  name: string;
}

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
export type DiagnosisSummaryVariant = 'linked' | 'unlinked';

export interface DiagnosisTreatmentPlan {
  id: string;
  interaction?: DiagnosisInteraction;
  name: string;
  status: 'failed' | 'success';
  time?: string;
}

export interface DiagnosisValueRow {
  interaction?: DiagnosisInteraction;
  key: string;
  label: string;
  value: DiagnosisSerializablePrimitive;
}

export interface DimensionAnalysisViewModel {
  alertCount?: number;
  dimensions?: Record<string, Array<number | string> | null | number | string | undefined>;
  id: string;
  interaction?: DiagnosisInteraction;
  score?: number;
  strategies?: DiagnosisStrategyViewModel[];
  title?: string;
  alerts?: Array<{
    id: string;
    strategyId?: string;
    strategyName?: string;
  }>;
}

export interface EventAnalysisGroupViewModel {
  fields: Record<string, string>;
  id: string;
  interaction?: DiagnosisInteraction;
  items: EventAnalysisViewModel[];
  source?: 'bcs' | 'itsm' | 'other';
  title: string;
  top?: number;
  total?: number;
  unit?: string;
}

export interface EventAnalysisViewModel {
  eventName?: string;
  id: string;
  interaction?: DiagnosisInteraction;
  reason?: string;
  subCount?: number;
  time?: string;
  title?: string;
  values?: Record<string, DiagnosisSerializablePrimitive>;
}

export interface LogAnalysisViewModel {
  id: string;
  interaction?: DiagnosisInteraction;
  logCount?: number;
  pattern?: string;
  sample?: string;
  source?: string;
  title?: string;
}

export interface TraceAnalysisViewModel {
  appName?: string;
  error?: string;
  id: string;
  interaction?: DiagnosisInteraction;
  kind?: string;
  logCount?: number;
  pattern?: string;
  serviceName?: string;
  spanId?: string;
  spanName?: string;
  title?: string;
  traceId?: string;
}
