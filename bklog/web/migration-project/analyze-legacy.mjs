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

import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, extname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { loadRules } from './migration-engine/load-rules.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(readFileSync(resolve(here, 'migration.config.json'), 'utf8'));
const sourceRoot = resolve(here, config.sourceProject);
const srcRoot = resolve(sourceRoot, 'src');
const outDir = resolve(here, 'artifacts/analysis');
const planDir = resolve(here, 'migration-plan');

const sourceExtensions = new Set(['.vue', '.js', '.ts', '.tsx', '.jsx']);
const riskRules = loadRules(resolve(here, 'migration-engine/rules/vue2-to-vue3.json'));
const styleRules = [
  { id: 'v-deep', re: /::v-deep|\/deep\/|>>>/g, disposition: '改为 :deep()' },
  { id: 'deep-fn', re: /:deep\s*\(/g, disposition: '已是 Vue 3 推荐写法，迁移时保留' },
];
const runtimeRules = [
  { id: 'dynamic-component', re: /<component\b|:is\s*=/g, note: '动态组件的真实分支要在运行时确认' },
  { id: 'dynamic-import', re: /import\s*\(/g, note: '懒加载目标要和路由清单对照，不能只看静态 import' },
  { id: 'require-context', re: /require\.context\s*\(/g, note: 'webpack 上下文依赖不能直接当成 Vite 可用' },
];

function walk(dir, files) {
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name === 'dist' || name.startsWith('.')) continue;
    const fullPath = join(dir, name);
    if (statSync(fullPath).isDirectory()) walk(fullPath, files);
    else files.push(fullPath);
  }
}

function lineOf(text, index) {
  return text.slice(0, index).split('\n').length;
}

function collect(text, rule) {
  const hits = [];
  for (const match of text.matchAll(rule.re)) {
    hits.push(lineOf(text, match.index));
  }
  return hits;
}

function toPosix(path) {
  return relative(sourceRoot, path).split('\\').join('/');
}

function extractRoutes(text, file) {
  const lines = text.split('\n');
  const paths = [];
  const names = [];
  lines.forEach((line, index) => {
    const pathMatch = line.match(/^\s*path:\s*['"`]([^'"`]+)['"`]/);
    const nameMatch = line.match(/^\s*name:\s*['"`]([^'"`]+)['"`]/);
    if (pathMatch) {
      const following = lines.slice(index, index + 8).map(item => item.trim()).filter(Boolean);
      const nameAt = following.findIndex(item => item.startsWith('name:'));
      const queryAt = following.findIndex(item => item.startsWith('query:'));
      if (!(queryAt >= 0 && (nameAt < 0 || queryAt < nameAt))) {
        paths.push({ line: index + 1, value: pathMatch[1] });
      }
    }
    if (nameMatch) names.push({ line: index + 1, value: nameMatch[1] });
  });
  const usedPaths = new Set();
  const routes = [];
  const aliases = [];
  for (const name of names) {
    const path = paths
      .filter(item => item.line <= name.line && name.line - item.line <= 30 && !usedPaths.has(item.line))
      .sort((left, right) => right.line - left.line)[0];
    if (!path) {
      aliases.push({ file, line: name.line, name: name.value });
      continue;
    }
    usedPaths.add(path.line);
    const nextPath = paths.find(item => item.line > name.line);
    const titleEnd = nextPath ? nextPath.line - 1 : name.line + 15;
    const titleLine = lines.slice(name.line - 1, titleEnd).find(line => line.includes('title:'));
    const title = titleLine ? (titleLine.match(/title:\s*['"`]([^'"`]+)['"`]/) || [])[1] || '' : '';
    routes.push({ file, path: path.value, pathLine: path.line, name: name.value, nameLine: name.line, title });
  }
  for (const path of paths) {
    if (usedPaths.has(path.line)) continue;
    routes.push({ file, path: path.value, pathLine: path.line, name: '', nameLine: 0, title: '' });
  }
  return { routes, aliases };
}

const files = [];
walk(srcRoot, files);
const sourceFiles = files.filter(file => sourceExtensions.has(extname(file)));
const risks = riskRules.map(rule => ({ ...rule, count: 0, files: [] }));
const styles = styleRules.map(rule => ({ ...rule, count: 0, files: [] }));
const runtime = runtimeRules.map(rule => ({ ...rule, count: 0, files: [] }));
const components = [];
const componentImports = [];
const bkTags = new Map();
const dataflow = {
  storeFiles: [],
  apiFiles: [],
  mapState: 0,
  mapGetters: 0,
  mapActions: 0,
  mapMutations: 0,
  dollarStore: 0,
  dollarHttp: 0,
  axiosImports: 0,
  eventBus: 0,
};
const routes = [];
const routeAliases = [];

for (const file of sourceFiles) {
  const text = readFileSync(file, 'utf8');
  const rel = toPosix(file);
  const ext = extname(file);
  if (rel.startsWith('src/router/') && (ext === '.js' || ext === '.ts')) {
    const extracted = extractRoutes(text, rel);
    routes.push(...extracted.routes);
    routeAliases.push(...extracted.aliases);
  }
  if ((ext === '.vue' || ext === '.tsx') && (rel.startsWith('src/components/') || rel.startsWith('src/views/'))) {
    components.push(rel);
  }
  for (const match of text.matchAll(/from\s+['"](@\/(?:components|views)\/[^'"]+)['"]/g)) {
    componentImports.push({ file: rel, line: lineOf(text, match.index), specifier: match[1] });
  }
  for (const match of text.matchAll(/<\/?(bk-[a-z0-9-]+)/g)) {
    bkTags.set(match[1], (bkTags.get(match[1]) || 0) + 1);
  }
  if (rel.startsWith('src/store/')) dataflow.storeFiles.push(rel);
  if (rel.startsWith('src/api/')) dataflow.apiFiles.push(rel);
  dataflow.mapState += [...text.matchAll(/\bmapState\b/g)].length;
  dataflow.mapGetters += [...text.matchAll(/\bmapGetters\b/g)].length;
  dataflow.mapActions += [...text.matchAll(/\bmapActions\b/g)].length;
  dataflow.mapMutations += [...text.matchAll(/\bmapMutations\b/g)].length;
  dataflow.dollarStore += [...text.matchAll(/\$store\b/g)].length;
  dataflow.dollarHttp += [...text.matchAll(/\$http\b/g)].length;
  dataflow.axiosImports += [...text.matchAll(/from\s+['"]axios['"]/g)].length;
  dataflow.eventBus += [...text.matchAll(/\b(?:eventBus|EventBus|\$bus)\b/g)].length;

  for (const group of [risks, styles, runtime]) {
    for (const rule of group) {
      const lines = collect(text, rule);
      if (!lines.length) continue;
      rule.count += lines.length;
      rule.files.push({ file: rel, lines });
    }
  }
}

const bkTagList = [...bkTags.entries()].sort((a, b) => b[1] - a[1]).map(([tag, count]) => ({ tag, count }));
const importCount = new Map();
for (const item of componentImports) importCount.set(item.specifier, (importCount.get(item.specifier) || 0) + 1);
const topImports = [...importCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 30).map(([specifier, count]) => ({ specifier, count }));

mkdirSync(outDir, { recursive: true });
const writeJson = (name, value) => writeFileSync(resolve(outDir, name), `${JSON.stringify(value, null, 2)}\n`);
writeJson('routes.json', { routes, aliases: routeAliases });
writeJson('components.json', { files: components, imports: componentImports, topImports });
writeJson('vue2-risks.json', risks.map(({ id, count, disposition, files: hits }) => ({ id, count, disposition, files: hits })));
writeJson('style-coupling.json', { rules: styles.map(({ id, count, disposition, files: hits }) => ({ id, count, disposition, files: hits })), bkTags: bkTagList });
writeJson('dataflow.json', dataflow);
writeJson('runtime-unknowns.json', runtime.map(({ id, count, note, files: hits }) => ({ id, count, note, files: hits })));

const routeRows = routes
  .sort((a, b) => a.file.localeCompare(b.file) || a.pathLine - b.pathLine)
  .map(item => `| ${item.file}:${item.pathLine} | \`${item.path}\` | ${item.name || '—'} | ${item.title || '—'} |`)
  .join('\n');
const riskRows = risks.map(item => `| ${item.id} | ${item.count} | ${item.disposition} |`).join('\n');
const styleRows = styles.map(item => `| ${item.id} | ${item.count} | ${item.disposition} |`).join('\n');
const runtimeRows = runtime.map(item => `| ${item.id} | ${item.count} | ${item.note} |`).join('\n');
const tagRows = bkTagList.slice(0, 20).map(item => `| \`${item.tag}\` | ${item.count} |`).join('\n');
const importRows = topImports.map(item => `| \`${item.specifier}\` | ${item.count} |`).join('\n');

const analysis = `# P1 旧项目静态分析

扫描范围：\`bklog/web/src\`。结果来自 \`node migration-project/analyze-legacy.mjs\` 的正则与目录扫描，不是运行时结论。完整命中位置在 \`migration-project/artifacts/analysis/*.json\`。

## 路由

业务路由文件是 \`src/router/index.js\`、\`retrieve.js\`、\`monitor.js\`、\`dashboard.js\`、\`manage.js\`。带 \`path\` 的路由 ${routes.length} 条。没有 \`path\`、只出现 \`name\` 的对象 ${routeAliases.length} 个，它们多半是嵌套占位组件，不计入页面。

| 位置 | path | name | title |
| --- | --- | --- | --- |
${routeRows}

## 组件

\`src/components\` 与 \`src/views\` 下的 \`.vue\` / \`.tsx\` 共 ${components.length} 个，文件清单在 \`components.json\`。静态 import 共 ${componentImports.length} 次。动态 \`import()\`、\`<component :is>\` 不在这张表里。

引用次数前 30：

| specifier | 次数 |
| --- | --- |
${importRows || '| — | 0 |'}

## Vue 2 高风险特性

| ID | 命中 | 处置 |
| --- | --- | --- |
${riskRows}

这些是源码文本命中。同名标识符可能造成少量误报，迁移时以对应文件的行号复核，不在本阶段改业务代码。

## 数据流

| 项 | 数量 |
| --- | --- |
| store 文件 | ${dataflow.storeFiles.length} |
| api 文件 | ${dataflow.apiFiles.length} |
| mapState | ${dataflow.mapState} |
| mapGetters | ${dataflow.mapGetters} |
| mapActions | ${dataflow.mapActions} |
| mapMutations | ${dataflow.mapMutations} |
| $store | ${dataflow.dollarStore} |
| $http | ${dataflow.dollarHttp} |
| axios import | ${dataflow.axiosImports} |
| eventBus / $bus | ${dataflow.eventBus} |

状态入口是 \`src/store/index.js\`。\`Vue.prototype.$http\` 在 \`src/api/index.js\`。事件总线命中要打开对应文件后才能判断是全局总线还是局部变量。

## 样式与组件库

源组件库是 \`bk-magic-vue\`。模板标签命中 ${bkTagList.length} 种 \`bk-*\`。

| 标签 | 次数 |
| --- | --- |
${tagRows || '| — | 0 |'}

| 样式写法 | 命中 | 处置 |
| --- | --- | --- |
${styleRows}

## 需要运行时确认

| ID | 命中 | 原因 |
| --- | --- | --- |
${runtimeRows}

静态扫描不能证明权限、接口返回和弹层的真实行为。登录后的页面仍按 P0 的 R-001 阻塞。
`;

const inventory = `# 组件清单

全量文件路径见 \`migration-project/artifacts/analysis/components.json\`。

- \`.vue\` / \`.tsx\`：${components.length}
- 静态 import：${componentImports.length}
- \`bk-*\` 标签种类：${bkTagList.length}

本清单不包含只在运行时 \`import()\` 或 \`<component :is>\` 中出现的组件。
`;

writeFileSync(resolve(planDir, '02-legacy-analysis.md'), analysis);
writeFileSync(resolve(planDir, '04-component-inventory.md'), inventory);
process.stdout.write(`routes=${routes.length} components=${components.length} risks=${risks.reduce((sum, item) => sum + item.count, 0)}\n`);
