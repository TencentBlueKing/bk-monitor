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

import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { parse } from '@vue/compiler-sfc';
const root = fileURLToPath(new URL('../src/', import.meta.url));
const walk = (dir) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((item) =>
    item.isDirectory() ? walk(dir + item.name + '/') : [dir + item.name],
  );
const published = new Set([
  'app/state/index.ts',
  'app/state/application-runtime.ts',
  'app/state/monitor-store-compatibility.ts',
  'platform/embedding/monitor-application.ts',
  'app/entries/monitor-bootstrap.ts',
  'features/retrieval/workspace/monitor/apm.ts',
  'features/retrieval/workspace/monitor/trace.ts',
  'features/retrieval/workbench/monitor/index.ts',
]);
const violations = [],
  boundaryImports = [];
let scanned = 0;
for (const file of walk(root).filter((file) => /\.(vue|tsx?|js)$/.test(file) && !file.includes('/assets/'))) {
  const relative = file.slice(root.length);
  if (published.has(relative)) continue;
  const source = readFileSync(file, 'utf8'),
    descriptor = file.endsWith('.vue') ? parse(source).descriptor : null;
  const blocks = descriptor ? [descriptor.script?.content, descriptor.scriptSetup?.content].filter(Boolean) : [source];
  scanned++;
  for (const block of blocks) {
    const ast = ts.createSourceFile(file, block, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const visit = (node) => {
      if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
        const id = node.moduleSpecifier.text;
        if (id === 'vuex' || /use-store$|map-helpers$|state\/(?:domain-store|state-runtime)$/.test(id))
          violations.push({ file: relative, kind: 'retired-import', expression: id });
        if (
          (/(?:@\/app\/state(?:\/index)?|^\.\/index)$/.test(id) && relative.startsWith('app/state/')) ||
          /@\/app\/state(?:\/index)?$/.test(id)
        )
          boundaryImports.push({ file: relative, specifier: id });
      }
      if (ts.isPropertyAccessExpression(node)) {
        const receiver = node.expression;
        if (
          node.name.text === '$store' ||
          (ts.isIdentifier(receiver) &&
            ['store', 'logStore', 'bklogStore'].includes(receiver.text) &&
            ['state', 'getters', 'commit', 'dispatch'].includes(node.name.text))
        )
          violations.push({ file: relative, kind: 'retired-access', expression: node.getText(ast) });
      }
      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'mapPiniaState') {
        const map = node.arguments[1];
        if (map && ts.isObjectLiteralExpression(map))
          for (const prop of map.properties)
            if (
              ts.isPropertyAssignment(prop) &&
              ts.isStringLiteral(prop.initializer) &&
              /^(retrieve|collect|globals)\//.test(prop.initializer.text)
            )
              violations.push({ file: relative, kind: 'qualified-native-selector', expression: prop.getText(ast) });
      }
      ts.forEachChild(node, visit);
    };
    visit(ast);
  }
  if (descriptor?.template) {
    const template = descriptor.template.content.replace(/<!--[\s\S]*?-->/g, '');
    for (const match of template.matchAll(/(?:\$store|(?:store|logStore)\.(?:state|getters|commit|dispatch))\b/g))
      violations.push({ file: relative, kind: 'retired-template-access', expression: match[0] });
  }
}
for (const item of boundaryImports) violations.push({ ...item, kind: 'internal-monitor-boundary-import' });
console.log(JSON.stringify({ scanned, publishedBoundaryFiles: [...published], violations }, null, 2));
if (violations.length) process.exitCode = 1;
