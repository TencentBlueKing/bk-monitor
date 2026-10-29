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
import { readFileSync, readdirSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve, relative, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';

const web = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(resolve(web, 'package.json'));
const { parse } = require('@babel/parser');
const { parse: parseSfc } = require('@vue/compiler-sfc');
const extensions = ['.ts', '.tsx', '.js', '.jsx', '.vue', '.mjs', '.scss', '.css'];
function walk(node, visit) {
  if (!node || typeof node !== 'object') return;
  if (node.type) visit(node);
  for (const [key, value] of Object.entries(node)) {
    if (['loc', 'start', 'end', 'comments', 'tokens'].includes(key)) continue;
    if (Array.isArray(value)) value.forEach(item => walk(item, visit));
    else if (value && typeof value === 'object') walk(value, visit);
  }
}
function files(dir) {
  return readdirSync(dir, { withFileTypes: true }).sort((a,b) => a.name.localeCompare(b.name)).flatMap(entry => {
    const path = resolve(dir, entry.name);
    return entry.isDirectory() ? files(path) : [path];
  });
}
function resolveLocal(specifier, importer) {
  if (!specifier.startsWith('.') && !specifier.startsWith('@/')) return null;
  const base = specifier.startsWith('@/') ? resolve(web, 'src', specifier.slice(2)) : resolve(dirname(importer), specifier);
  return [base, ...extensions.map(ext => base + ext), ...extensions.map(ext => resolve(base, 'index' + ext))]
    .find(path => existsSync(path) && !readdirIsDirectory(path)) || null;
}
import { statSync } from 'node:fs';
function readdirIsDirectory(path) { return statSync(path).isDirectory(); }
export function analyzeSource(source, filename) {
  let script = source;
  if (extname(filename) === '.vue') {
    const { descriptor, errors } = parseSfc(source, { filename });
    const fatal = errors.filter(error => !String(error).includes('<template functional>'));
    if (fatal.length) throw new Error(fatal.map(String).join('; '));
    script = [descriptor.script?.content, descriptor.scriptSetup?.content].filter(Boolean).join('\n');
  }
  const ast = parse(script, { sourceType: 'unambiguous', plugins: [['typescript', { dts: filename.endsWith('.d.ts') }], 'jsx', 'decorators-legacy'], errorRecovery: false });
  const imports = new Map();
  const lazy = new Map();
  const refs = new Set();
  walk(ast, node => {
    if (node.type === 'ImportDeclaration' || node.type === 'ExportNamedDeclaration' || node.type === 'ExportAllDeclaration') {
      if (node.source?.value) refs.add(node.source.value);
      for (const specifier of node.specifiers || []) imports.set(specifier.local?.name, node.source?.value);
    }
    if (node.type === 'CallExpression' && (node.callee.type === 'Import' || node.callee.name === 'require') && node.arguments[0]?.type === 'StringLiteral') refs.add(node.arguments[0].value);
    if (node.type === 'VariableDeclarator' && node.id.type === 'Identifier') {
      walk(node.init, child => {
        if (child.type === 'CallExpression' && child.callee.type === 'Import' && child.arguments[0]?.type === 'StringLiteral') lazy.set(node.id.name, child.arguments[0].value);
      });
    }
  });
  const routes = [];
  walk(ast, node => {
    if (node.type !== 'ObjectExpression') return;
    const props = Object.fromEntries(node.properties.filter(p => p.type === 'ObjectProperty').map(p => [p.key.name || p.key.value, p.value]));
    if (props.path?.type !== 'StringLiteral' || !(props.component || props.redirect || props.children)) return;
    const component = props.component?.name;
    routes.push({ name: props.name?.value || null, path: props.path.value, line: node.loc.start.line,
      component: lazy.get(component) || imports.get(component) || null,
      componentExpression: component || props.component?.type || null,
      redirect: Boolean(props.redirect), container: Boolean(props.children) });
  });
  return { refs: [...refs].sort(), routes };
}

export function inventory() {
  const sourceFiles = files(resolve(web, 'src'));
  const modules = [];
  const errors = [];
  const routes = [];
  for (const file of sourceFiles.filter(file => /\.(?:[jt]sx?|vue|mjs)$/.test(file))) {
    const path = relative(web, file);
    try {
      const result = analyzeSource(readFileSync(file, 'utf8'), file);
      const dependencies = result.refs.map(specifier => {
        const target = resolveLocal(specifier, file);
        return { specifier, target: target ? relative(web, target) : null, local: specifier.startsWith('.') || specifier.startsWith('@/') };
      });
      modules.push({ path, dependencies });
      if (/^src\/router\//.test(path)) for (const route of result.routes) {
        const target = route.component && resolveLocal(route.component, file);
        routes.push({ id: route.name || `${path}:${route.line}`, source: path, ...route,
          target: target ? relative(web, target) : null, business: 'PENDING', visual: 'PENDING', scenarios: [],
          note: 'AST source inventory; runtime branches and component behavior require verification' });
      }
    } catch (error) { errors.push({ path, error: error.message }); }
  }
  const hashes = [...sourceFiles, ...['package.json', 'package-lock.json', 'webpack.config.js'].map(p => resolve(web, p))]
    .map(file => ({ path: relative(web, file), sha256: createHash('sha256').update(readFileSync(file)).digest('hex') }));
  return { schemaVersion: 1, generatedAt: new Date().toISOString(),
    revision: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: web, encoding: 'utf8' }).trim(),
    snapshotSha256: createHash('sha256').update(JSON.stringify(hashes)).digest('hex'),
    sourceHashes: hashes, routes, modules, errors,
    limitations: ['Conditional compilation and feature flags are not executed', 'Vue template global components, SCSS imports, computed imports and runtime events require further analysis', 'Statuses are discovery defaults, not acceptance results; do not overwrite reviewed task records'] };
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const report = inventory();
  const output = resolve(web, 'migration-project/artifacts/inventory');
  mkdirSync(output, { recursive: true });
  writeFileSync(resolve(output, 'source-inventory.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ routes: report.routes.length, modules: report.modules.length, errors: report.errors.length, snapshotSha256: report.snapshotSha256 }));
  if (report.errors.length) process.exitCode = 1;
}
