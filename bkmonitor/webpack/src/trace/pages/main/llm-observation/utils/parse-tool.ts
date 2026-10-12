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
import { getByPath, isRecord, parseJsonValue, pickList, stringifyContent } from './helpers';

import type { LlmToolObservation } from './typings';

/**
 * @description 从 Span attributes 解析 Tool 观测页（描述 / 参数 / 结果）
 */
export function parseToolObservation(attributes: Record<string, unknown>): LlmToolObservation {
  const name = String(getByPath(attributes, 'gen_ai.tool.name') || '').trim();
  return {
    name,
    description: pickToolDescription(attributes, name),
    arguments: parseJsonValue(getByPath(attributes, 'gen_ai.tool.call.arguments')) ?? {},
    result: parseJsonValue(getByPath(attributes, 'gen_ai.tool.call.result')) ?? {},
  };
}

/** 优先取 gen_ai.tool.description，否则从 definitions 按名称回落 */
function pickToolDescription(attributes: Record<string, unknown>, name: string): string {
  const direct = stringifyContent(getByPath(attributes, 'gen_ai.tool.description')).trim();
  if (direct) return direct;
  if (!name) return '';
  const definitions = pickList(attributes, ['gen_ai.tool.definitions']);
  for (const item of definitions) {
    if (!isRecord(item)) continue;
    if (String(item.name || '').trim() !== name) continue;
    return stringifyContent(item.description).trim();
  }
  return '';
}
