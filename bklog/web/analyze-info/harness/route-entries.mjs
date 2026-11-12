import { localArtifactUrl, localArtifactPath } from './local-artifacts.mjs';
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

import {createRequire} from 'node:module';
import {readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const require = createRequire(new URL('../../packages/web-v3/package.json', import.meta.url));
const ts = require('typescript');

/** Resolve declarations, wrappers and lazy factories without executing application code. */
export function routeEntries(graph, routes, readSource, {componentPrefixes = ['views/', 'components/']} = {}) {
  const files = new Map();
  for (const route of routes) {
    if (files.has(route.file)) continue;
    const source = ts.createSourceFile(route.file, readSource(route.file), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const declarations = new Map(), objects = new Map();
    function visit(node) {
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) declarations.set(node.name.text, node.initializer);
      if (ts.isObjectLiteralExpression(node)) objects.set(node.getStart(source), node);
      ts.forEachChild(node, visit);
    }
    visit(source);
    files.set(route.file, {source, declarations, objects});
  }
  return routes.map(route => {
    const {source, declarations, objects} = files.get(route.file);
    const node = objects.get(route.start), seen = new Set(), lazy = new Set(), imported = new Set();
    const wrappers = new Set(), dynamic = [];
    function follow(node) {
      if (!node || seen.has(node)) return;
      seen.add(node);
      if (ts.isIdentifier(node)) {
        if (declarations.has(node.text)) {wrappers.add(node.text); follow(declarations.get(node.text));}
        for (const dependency of graph.dependencies.filter(d => d.file === route.file && d.bindings?.includes(node.text))) imported.add(dependency.target ?? dependency.specifier);
      }
      if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
        const argument = node.arguments[0];
        if (ts.isStringLiteral(argument)) {
          const dependency = graph.dependencies.find(d => d.file === route.file && d.syntax === 'dynamic-import' && d.specifier === argument.text);
          lazy.add(dependency?.target ?? argument.text);
        } else dynamic.push({line: source.getLineAndCharacterOfPosition(node.pos).line + 1, expression: node.getText(source)});
        return;
      }
      ts.forEachChild(node, follow);
    }
    const component = node?.properties.find(p => ts.isPropertyAssignment(p) && ['component', 'components'].includes(p.name.getText(source)));
    follow(component?.initializer);
    return {...route, entryKind: !component ? 'REDIRECT_OR_CONTAINER' : lazy.size ? 'LAZY_OR_VERSIONED_COMPONENT' : imported.size ? 'IMPORTED_COMPONENT' : 'LOCAL_LAYOUT', componentSources: [...new Set([...lazy, ...imported])].filter(path => componentPrefixes.some(prefix => path.startsWith(prefix))).sort(), referencedDependencies: [...imported].sort(), declarationChain: [...wrappers].sort(), unresolvedFactories: dynamic, contractStatus: 'UNREVIEWED', runtimeAccepted: false};
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = fileURLToPath(new URL('../../packages/web-v2/src/', import.meta.url));
  const graph = JSON.parse(readFileSync(localArtifactUrl('source/entry-graph.json'), 'utf8'));
  const routes = JSON.parse(readFileSync(localArtifactUrl('source/routes.json'), 'utf8'));
  const entries = routeEntries(graph, routes, file => readFileSync(resolve(root, file), 'utf8'));
  writeFileSync(localArtifactUrl('source/route-entries.json'), JSON.stringify(entries, null, 2) + '\n');
  console.log(JSON.stringify({routes: entries.length, withComponents: entries.filter(e => e.componentSources.length).length, localLayouts: entries.filter(e => e.entryKind === 'LOCAL_LAYOUT').length, unresolvedFactories: entries.flatMap(e => e.unresolvedFactories).length, scope: 'SOURCE_PROVENANCE_NOT_ACCEPTANCE'}));
}
