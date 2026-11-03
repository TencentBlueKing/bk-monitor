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
import type { DiagnosisInteraction, DiagnosisSerializableValue } from './types';

export interface DiagnosisAddToChatPayload {
  content: DiagnosisInteractiveContent;
  reference?: DiagnosisChatReference;
}
export interface DiagnosisAnalysisViewModel<T> {
  items: T[];
  summary?: DiagnosisInteractiveContent;
}
export interface DiagnosisChatReference {
  detailRef?: DiagnosisSerializableValue;
  displayText: string;
  fieldKey: string;
  itemId: string;
  panel: string;
  source?: Record<string, DiagnosisSerializableValue>;
}

export interface DiagnosisContentCardViewModel {
  blocks: DiagnosisInteractiveContent[];
  detailAction?: DiagnosisDetailAction;
  id: string;
  metric?: string;
  promptAction?: DiagnosisPromptAction;
  rows: DiagnosisInteractiveContent[];
  title: string;
}

export type DiagnosisContentFormat = 'json' | 'markdown' | 'text';

export type DiagnosisDetailAction = Extract<DiagnosisInteraction, { type: 'drawer' | 'error' | 'link' | 'none' }>;

export type DiagnosisDisplayValue = DiagnosisSerializableValue;

export interface DiagnosisGroupViewModel {
  detailAction?: DiagnosisDetailAction;
  iconSrc?: string;
  id: string;
  items: DiagnosisContentCardViewModel[];
  promptAction?: DiagnosisPromptAction;
  title: string;
  totalContent?: DiagnosisInteractiveContent;
  totalText?: string;
}

export interface DiagnosisInteractiveContent {
  addToChat?: boolean;
  chatReference?: DiagnosisChatReference;
  detailAction?: DiagnosisDetailAction;
  format?: DiagnosisContentFormat;
  key: string;
  label?: string;
  promptAction?: DiagnosisPromptAction;
  value: DiagnosisDisplayValue;
}

export interface DiagnosisPromptAction {
  text: string;
}

export interface DiagnosisSummaryViewModel {
  alertReason?: DiagnosisInteractiveContent;
  recommendation?: DiagnosisInteractiveContent;
  relatedFailure?: DiagnosisInteractiveContent;
  variant: 'linked' | 'unlinked';
  treatmentPlans: Array<{
    content: DiagnosisInteractiveContent;
    id: string;
    status: 'failed' | 'success';
    time?: string;
  }>;
}

export interface DimensionDiagnosisViewModel extends DiagnosisContentCardViewModel {
  alertCount?: number;
  alertCountContent?: DiagnosisInteractiveContent;
}

export interface EventDiagnosisAnalysisViewModel {
  groups: DiagnosisGroupViewModel[];
  summary?: DiagnosisInteractiveContent;
}
