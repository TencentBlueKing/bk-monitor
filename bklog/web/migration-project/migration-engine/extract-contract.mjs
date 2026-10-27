/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { readFileSync } from 'node:fs';

const TAGS = ['bk-button', 'bk-input', 'bk-select', 'bk-option'];
const MAPPED_ATTRS = new Set([
  'theme',
  'disabled',
  'type',
  'clearable',
  'placeholder',
  'searchable',
  'allow-create',
  'multiple',
  'id',
  'name',
  'v-model',
]);
const SKIP_ATTRS = new Set(['class', 'style', 'ref', 'key', 'v-for']);

function lineOf(text, index) {
  return text.slice(0, index).split('\n').length;
}

function parseAttrs(raw) {
  const attrs = {};
  const events = {};
  const unmapped = [];
  const tokenRe = /((?:[:@]|v-model(?::[\w-]+)?)?[\w.-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
  for (const match of raw.matchAll(tokenRe)) {
    const key = match[1];
    const bare = key.replace(/^[:@]/, '');
    if (!key || SKIP_ATTRS.has(bare) || SKIP_ATTRS.has(key)) continue;
    const value = match[2] ?? match[3] ?? match[4] ?? true;
    if (key.startsWith('@')) {
      events[bare] = value;
      continue;
    }
    attrs[key] = value;
    if (!MAPPED_ATTRS.has(bare)) unmapped.push(key);
  }
  return { attrs, events, unmapped };
}

function openingTags(text, tag) {
  const found = [];
  const startRe = new RegExp(`<${tag}\\b`, 'g');
  for (const match of text.matchAll(startRe)) {
    let quote = '';
    let index = match.index + match[0].length;
    for (; index < text.length; index += 1) {
      const char = text[index];
      if (quote) {
        if (char === quote) quote = '';
        continue;
      }
      if (char === '"' || char === "'") {
        quote = char;
        continue;
      }
      if (char === '>') {
        found.push({
          index: match.index,
          raw: text.slice(match.index + match[0].length, index),
        });
        break;
      }
    }
  }
  return found;
}

export function extractContract(filePath, id) {
  const text = readFileSync(filePath, 'utf8');
  const controls = [];
  for (const tag of TAGS) {
    for (const match of openingTags(text, tag)) {
      const parsed = parseAttrs(match.raw);
      controls.push({
        tag,
        line: lineOf(text, match.index),
        attrs: parsed.attrs,
        events: parsed.events,
        unmapped: parsed.unmapped,
      });
    }
  }
  return {
    id,
    source: filePath,
    controls,
    invariants: [],
  };
}
