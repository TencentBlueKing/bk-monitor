import { localArtifactPath } from './local-artifacts.mjs';
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
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { pathToFileURL, fileURLToPath } from 'node:url';
const web = fileURLToPath(new URL('../../', import.meta.url)).replace(/\/$/, ''),
  pkg = web + '/packages/web-v3',
  root = pkg + '/src';
const require = createRequire(pkg + '/package.json'),
  ts = require('typescript'),
  { parse } = require('@vue/compiler-sfc');
const { auditBusinessControls } = await import(pathToFileURL(pkg + '/tools/business-control-audit.mjs'));
const controls = auditBusinessControls(root);
const walk = (dir) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(dir + '/' + e.name) : [dir + '/' + e.name]
  );
const risks = [],
  sourceDigests = [];
const record = (file, line, kind, detail) =>
  risks.push({
    file,
    line,
    kind,
    detail,
    status: 'SOURCE_CONTRACT_MISMATCH_CANDIDATE_NOT_RUNTIME_ACCEPTANCE',
  });
for (const full of walk(root).filter((p) => /\.(tsx?|vue)$/.test(p) && !p.includes('/platform/'))) {
  const file = full.slice(root.length + 1),
    source = readFileSync(full, 'utf8');
  sourceDigests.push({ file, sha256: createHash('sha256').update(source).digest('hex') });
  const sections = [];
  if (full.endsWith('.vue')) {
    const { descriptor: d } = parse(source);
    for (const part of [d.script, d.scriptSetup].filter(Boolean))
      sections.push({ text: part.content, offset: part.loc.start.offset });
    const visit = (n) => {
      if (n.type === 1) {
        const line = n.loc.start.line + (d.template?.loc.start.line ?? 1) - 1;
        if (
          n.tag === 'bk-select' &&
          (n.children ?? []).some((c) =>
            c.props?.some((p) => p.type === 7 && p.name === 'slot' && p.arg?.content === 'trigger')
          )
        )
          record(file, line, 'SELECT_TRIGGER_SLOT_DROPPED', 'bk-select child #trigger');
        if (n.tag === 'bk-option' && (n.children ?? []).some((c) => c.type !== 2 || c.content.trim()))
          record(
            file,
            line,
            'OPTION_RENDER_CONTENT_FLATTENED',
            'option children reduced to label/value by adapter'
          );
        if (
          n.tag === 'bk-sideslider' &&
          n.props.some((p) => p.name === 'before-close' || p.arg?.content === 'before-close')
        )
          record(
            file,
            line,
            'DRAWER_BEFORE_CLOSE_UNMAPPED',
            'before-close is not TDesign Drawer close lifecycle'
          );
        if (
          n.tag === 'bk-form' &&
          n.props.some((p) => p.name === 'form-type' && p.value?.content === 'vertical')
        )
          record(
            file,
            line,
            'FORM_VERTICAL_LABEL_UNMAPPED',
            'form-type vertical does not set labelAlign top'
          );
      }
      for (const c of n.children ?? []) visit(c);
    };
    if (d.template?.ast) visit(d.template.ast);
  } else sections.push({ text: source, offset: 0 });
  for (const section of sections) {
    const ast = ts.createSourceFile(full, section.text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX),
      refs = new Map();
    const visit = (n) => {
      const line = source.slice(0, section.offset + n.getStart(ast)).split('\n').length;
      if (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) {
        const name = n.tagName.getText(ast),
          props = n.attributes.properties,
          find = (k) => props.find((p) => p.name?.getText(ast) === k),
          ref = find('ref');
        if (ref?.initializer && ts.isJsxExpression(ref.initializer) && ref.initializer.expression)
          refs.set(ref.initializer.expression.getText(ast), name);
        if (
          name === 'bk-select' &&
          find('v-slots')
            ?.initializer?.getText(ast)
            .match(/\btrigger\s*:/)
        )
          record(file, line, 'SELECT_TRIGGER_SLOT_DROPPED', 'v-slots.trigger is not forwarded by BkSelect');
        if (
          name === 'bk-option' &&
          ts.isJsxOpeningElement(n) &&
          ts.isJsxElement(n.parent) &&
          n.parent.children.some((c) => !ts.isJsxText(c) || c.text.trim())
        )
          record(
            file,
            line,
            'OPTION_RENDER_CONTENT_FLATTENED',
            'custom option children are discarded by optionNodes'
          );
        if (name === 'bk-option' && find('disabled'))
          record(file, line, 'OPTION_DISABLED_PROP_DROPPED', 'optionNodes retains label/value only');
        if (name === 'bk-sideslider' && find('before-close'))
          record(
            file,
            line,
            'DRAWER_BEFORE_CLOSE_UNMAPPED',
            'before-close is passed through attrs but not called by adapter'
          );
        if (name === 'bk-form' && find('form-type')?.initializer?.text === 'vertical')
          record(
            file,
            line,
            'FORM_VERTICAL_LABEL_UNMAPPED',
            'form-type vertical does not set labelAlign top'
          );
      }
      ts.forEachChild(n, visit);
    };
    visit(ast);
    const calls = (n) => {
      if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression)) {
        const method = n.expression.name.text,
          receiver = n.expression.expression.getText(ast).replace(/\.value$/, '');
        if (['showHandler', 'hideHandler'].includes(method))
          record(
            file,
            source.slice(0, section.offset + n.getStart(ast)).split('\n').length,
            'LEGACY_POPOVER_INSTANCE_METHOD',
            { receiver, method, component: refs.get(receiver) ?? 'UNRESOLVED_REVIEW' }
          );
        if (method === 'close' && refs.get(receiver) === 'bk-select')
          record(
            file,
            source.slice(0, section.offset + n.getStart(ast)).split('\n').length,
            'SELECT_CLOSE_METHOD_NOT_EXPOSED',
            { receiver, method, component: refs.get(receiver) }
          );
      }
      ts.forEachChild(n, calls);
    };
    calls(ast);
  }
}
const byKind = {};
for (const r of risks) {
  (byKind[r.kind] ??= { occurrences: 0, files: new Set(), modules: new Set() }).occurrences++;
  byKind[r.kind].files.add(r.file);
  byKind[r.kind].modules.add(r.file.startsWith('features/') ? r.file.split('/')[1] : 'shared');
}
const registrySource = readFileSync(root + '/platform/compat/tdesign/legacy-bk-controls.tsx', 'utf8');
const registeredNames = new Set(
  [
    ...registrySource
      .slice(registrySource.indexOf('export function installLegacyBkControls'))
      .matchAll(/'([^']+)'\s*:/g),
  ].map((m) => m[1])
);
const registeredCalls = controls.occurrences.filter(
  (o) =>
    o.kind === 'component' &&
    registeredNames.has(o.name) &&
    (o.file.startsWith('features/') || o.file.startsWith('shared/'))
);
const literalCalls = {
  occurrences: registeredCalls.length,
  files: new Set(registeredCalls.map((o) => o.file)).size,
  byModule: {},
};
for (const o of registeredCalls) {
  const module = o.file.startsWith('features/') ? o.file.split('/')[1] : 'shared';
  const bucket = (literalCalls.byModule[module] ??= { occurrences: 0, files: new Set() });
  bucket.occurrences++;
  bucket.files.add(o.file);
}
for (const bucket of Object.values(literalCalls.byModule)) bucket.files = bucket.files.size;
const business = controls.occurrences.filter(
  (o) => o.file.startsWith('features/') || o.file.startsWith('shared/')
);
const byModule = {};
for (const o of business) {
  const mod = o.file.startsWith('features/') ? o.file.split('/')[1] : 'shared';
  const g = (byModule[mod] ??= { occurrences: 0, files: new Set(), components: {} });
  g.occurrences++;
  g.files.add(o.file);
  g.components[o.name] = (g.components[o.name] ?? 0) + 1;
}
const result = {
  schemaVersion: 1,
  candidateTotals: { occurrences: risks.length, files: new Set(risks.map((r) => r.file)).size },
  scope: 'READ_ONLY_STATIC_SOURCE_RISK_AUDIT_NOT_FUNCTION_COVERAGE',
  generatedAt: new Date().toISOString(),
  registeredLegacyBusinessComponentCalls: literalCalls,
  controls: {
    status: controls.status,
    total: controls.total,
    files: controls.files,
    counts: controls.counts,
    businessOnly: {
      occurrences: business.length,
      files: new Set(business.map((o) => o.file)).size,
      byModule: Object.fromEntries(
        Object.entries(byModule).map(([k, v]) => [k, { ...v, files: v.files.size }])
      ),
    },
  },
  riskSummary: Object.fromEntries(
    Object.entries(byKind).map(([k, v]) => [k, { ...v, files: v.files.size, modules: [...v.modules].sort() }])
  ),
  risks,
  sourceDigests,
  limits: [
    'Static hits are candidates; they are not independently confirmed user-visible defects or scenarios.',
    'Only literal component names and resolvable local JSX refs are analyzed; dynamic aliases, native TDesign API and inherited implicit library behaviors require separate review.',
    'Source reference inventory does not freeze backend data or browser state.',
  ],
};
writeFileSync(
  localArtifactPath('runs/alignment-audit-20261112/source-contract-risks.json'),
  JSON.stringify(result, null, 2) + '\n'
);
console.log(JSON.stringify({ ...result, risks: undefined, sourceDigests: undefined }, null, 2));
