import type { DiagnosisAddToChatPayload } from '@/components/ai-diagnosis';
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
import type { TagSchema } from '@blueking/chat-x';

const MODULE_TITLE_KEYS: Record<string, string> = {
  alerts_analysis: '告警异常维度分析',
  events_analysis: '事件分析',
  logs_analysis: '日志分析',
  suggestion: '处理建议',
  summary: '诊断总结',
  trace_analysis: 'Trace 分析',
};

type DraftNode = TagSchema[number][number];

const isTextNode = (node: DraftNode): node is { text: string; type: 'text' } =>
  node.type === 'text' && typeof node.text === 'string';

const moduleTitle = (moduleName: string) => `${moduleName}：`;

const lineText = (line: DraftNode[]) => (line.length === 1 && isTextNode(line[0]) ? line[0].text : undefined);

const isModuleTitleLine = (line: DraftNode[]) => {
  const text = lineText(line);
  return typeof text === 'string' && text.endsWith('：');
};

const displayTextOf = (payload: DiagnosisAddToChatPayload) =>
  payload.reference?.displayText ??
  (typeof payload.content.value === 'string' ? payload.content.value : JSON.stringify(payload.content.value));

const chipLabelOf = (payload: DiagnosisAddToChatPayload, displayText: string) => {
  const fieldLabel = (payload.content.label || '').replace(/[:：]\s*$/, '').trim();
  return fieldLabel ? `${fieldLabel} = ${displayText}` : displayText;
};

const createTagNode = (payload: DiagnosisAddToChatPayload) => {
  const displayText = displayTextOf(payload);
  return {
    data: {
      description: displayText,
      icon: '',
      label: chipLabelOf(payload, displayText),
      type: 'diagnosis-reference',
      value: JSON.stringify(
        payload.reference || {
          displayText,
          fieldKey: payload.content.key,
        }
      ),
    },
    type: 'tag' as const,
  };
};

const draftLines = (draft: string | TagSchema): DraftNode[][] => {
  if (typeof draft === 'string') return draft ? [[{ text: draft, type: 'text' }]] : [];
  return draft.map(line => [...line]);
};

const appendChip = (line: DraftNode[], tagNode: DraftNode) =>
  line.length ? [...line, { text: ' ', type: 'text' as const }, tagNode] : [tagNode];

export const diagnosisChatModuleTitleKey = (panel?: string) =>
  (panel && MODULE_TITLE_KEYS[panel]) || panel || '诊断总结';

export const appendDiagnosisReferenceToDraft = (
  draft: string | TagSchema,
  payload: DiagnosisAddToChatPayload,
  moduleName: string
): TagSchema => {
  const lines = draftLines(draft);
  const title = moduleTitle(moduleName);
  const tagNode = createTagNode(payload);
  const titleIndex = lines.findIndex(line => lineText(line) === title);
  if (titleIndex >= 0) {
    const next = lines[titleIndex + 1];
    if (!next || isModuleTitleLine(next)) {
      lines.splice(titleIndex + 1, 0, [tagNode]);
    } else {
      lines[titleIndex + 1] = appendChip(next, tagNode);
    }
    return lines as TagSchema;
  }
  lines.push([{ text: title, type: 'text' }], [tagNode]);
  return lines as TagSchema;
};
