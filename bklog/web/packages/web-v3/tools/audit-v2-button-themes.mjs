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

import { createRequire } from 'node:module';
import { readFileSync, readdirSync, existsSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, relative } from 'node:path';
import { createHash } from 'node:crypto';
const require = createRequire(new URL('../package.json', import.meta.url)),
  { parse } = require('@babel/parser');
const v3 = fileURLToPath(new URL('../src/', import.meta.url)),
  v2 = fileURLToPath(new URL('../../web-v2/src/', import.meta.url));
const mappings = [
  ['features/retrieval/workspace/', 'views/retrieve-v3/'],
  ['features/retrieval/workbench/', 'views/retrieve-v2/'],
  ['features/retrieval/log-view/', 'components/log-view/'],
  ['features/collection/current/', 'views/manage-v2/log-collection/'],
  ['features/clusters/current/', 'views/manage-v2/es-cluster/'],
];
const sha = (s) => createHash('sha256').update(s).digest('hex');
function files(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? files(resolve(dir, e.name)) : e.name.endsWith('.tsx') ? [resolve(dir, e.name)] : []
  );
}
function walk(node, visit) {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) {
    for (const child of node) walk(child, visit);
    return;
  }
  if (node.type) visit(node);
  for (const [key, value] of Object.entries(node))
    if (!['loc', 'comments', 'tokens', 'start', 'end', 'extra'].includes(key)) walk(value, visit);
}
function controls(code, native) {
  const ast = parse(code, { sourceType: 'module', plugins: ['typescript', 'jsx', 'decorators-legacy'] }),
    names = new Set(['bk-button', 'bkButton', 'BkButton']),
    nativeNames = new Set();
  for (const node of ast.program.body) {
    if (node.type !== 'ImportDeclaration') continue;
    for (const s of node.specifiers) {
      if (
        s.type === 'ImportSpecifier' &&
        node.source.value === 'tdesign-vue-next' &&
        s.imported.name === 'Button'
      ) {
        names.add(s.local.name);
        nativeNames.add(s.local.name);
      }
      if (
        s.type === 'ImportSpecifier' &&
        node.source.value.includes('bk-magic-vue') &&
        /^(bkButton|Button)$/.test(s.imported.name)
      )
        names.add(s.local.name);
    }
  }
  const buttons = [];
  walk(ast, (node) => {
    if (
      node.type !== 'JSXElement' ||
      node.openingElement.name.type !== 'JSXIdentifier' ||
      !names.has(node.openingElement.name.name)
    )
      return;
    const attributes = Object.fromEntries(
      node.openingElement.attributes
        .filter((a) => a.type === 'JSXAttribute')
        .map((a) => [
          a.name.type === 'JSXIdentifier' ? a.name.name : code.slice(a.name.start, a.name.end),
          a.value?.type === 'StringLiteral'
            ? a.value.value
            : a.value === null
            ? true
            : a.value?.type === 'JSXExpressionContainer' && a.value.expression.type === 'StringLiteral'
            ? a.value.expression.value
            : 'DYNAMIC',
        ])
    );
    attributes.$spreadCount = node.openingElement.attributes.filter(
      (a) => a.type === 'JSXSpreadAttribute'
    ).length;
    const labels = [];
    walk(node.children, (n) => {
      if (
        n.type === 'CallExpression' &&
        n.arguments[0]?.type === 'StringLiteral' &&
        ((n.callee.type === 'Identifier' && /^(t|\$t)$/.test(n.callee.name)) ||
          (n.callee.type === 'MemberExpression' && n.callee.property.name === '$t'))
      )
        labels.push(n.arguments[0].value);
      if (n.type === 'JSXText' && n.value.trim()) labels.push(n.value.trim().replace(/\s+/g, ' '));
    });
    buttons.push({
      line: node.loc.start.line,
      tag: node.openingElement.name.name,
      native: nativeNames.has(node.openingElement.name.name),
      attributes,
      labels,
    });
  });
  return buttons;
}
const candidates = [],
  unpaired = [],
  inputs = [],
  diagnostics = [];
let pairs = 0,
  compared = 0,
  legacy = 0;
for (const [prefix, target] of mappings) {
  for (const path of files(resolve(v3, prefix))) {
    const file = relative(v3, path),
      baseline = target + file.slice(prefix.length),
      oldPath = resolve(v2, baseline);
    if (!existsSync(oldPath)) {
      unpaired.push({ file, reason: 'NO_EXACT_V2_SOURCE' });
      continue;
    }
    const current = readFileSync(path, 'utf8'),
      old = readFileSync(oldPath, 'utf8');
    inputs.push({ v3: file, v3Sha256: sha(current), v2: baseline, v2Sha256: sha(old) });
    let a, b;
    try {
      a = controls(old, false);
      b = controls(current, true);
    } catch (error) {
      diagnostics.push({ file, reason: error.message });
      continue;
    }
    if (a.length !== b.length) {
      unpaired.push({ file, reason: 'CONTROL_COUNT_CHANGED', v2: a.length, v3: b.length });
      continue;
    }
    pairs++;
    for (let i = 0; i < a.length; i++) {
      const before = a[i],
        after = b[i];
      if (!after.native) {
        legacy++;
        continue;
      }
      if (!before.labels.length || JSON.stringify(before.labels) !== JSON.stringify(after.labels)) {
        unpaired.push({
          file,
          line: after.line,
          reason: 'LABELS_NOT_PROVEN_IDENTICAL',
          v2Labels: before.labels,
          v3Labels: after.labels,
        });
        continue;
      }
      compared++;
      const expected = before.attributes.theme ?? 'default',
        actual = after.attributes.theme ?? 'primary';
      if (expected === actual) continue;
      candidates.push({
        status: 'NEEDS_SOURCE_AND_BROWSER_REVIEW',
        labels: before.labels,
        v2: { file: baseline, line: before.line, theme: expected, attributes: before.attributes },
        v3: { file, line: after.line, theme: actual, attributes: after.attributes },
        pairing: 'SAME_COUNT_ORDINAL_AND_TRANSLATION_LABELS',
        businessAccepted: false,
        uiAccepted: false,
      });
    }
  }
}
const report = {
  schemaVersion: 1,
  scope: 'STATIC_BUTTON_THEME_REVIEW_CANDIDATES_NOT_ACCEPTANCE',
  pairedFiles: pairs,
  comparedNativeControls: compared,
  legacyControls: legacy,
  candidates,
  unpaired,
  diagnostics,
  inputs,
  limitations: [
    'Only TSX files under the five explicit directory mappings are scanned.',
    'Ordinal and label equality is evidence for review, not a proof of equivalent branches.',
    'Text variants, dynamic props, theme inheritance and source component CSS require manual verification.',
    'Vue templates, other modules, unpaired controls and all non-button differences remain outside this audit.',
  ],
};
const out = new URL('../../../analyze-info/source/v3-button-theme-candidates.json', import.meta.url);
writeFileSync(out, JSON.stringify(report, null, 2) + '\n');
console.log(
  JSON.stringify({
    scope: report.scope,
    pairedFiles: pairs,
    comparedNativeControls: compared,
    candidates: candidates.length,
    unpaired: unpaired.length,
    diagnostics: diagnostics.length,
  })
);
