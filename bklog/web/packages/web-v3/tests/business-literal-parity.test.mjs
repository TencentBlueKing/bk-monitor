import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
const sourceRoot = new URL('../src/', import.meta.url);
const legacyRoot = new URL('../../web-v2/src/', import.meta.url);
const files = [
  ['shared/global/head-navi/index.tsx', 'global/head-navi/index.tsx'],
  ['shared/global/json-view/index.ts', 'global/json-view/index.ts'],
  ['features/collection/access/step-field.vue', 'components/collection-access/step-field.vue'],
  [
    'features/charts/value-formats-package/value-formats.ts',
    'components/monitor-echarts/value-formats-package/value-formats.ts',
  ],
  [
    'features/retrieval/workbench/field-filter-comp/field-item.tsx',
    'views/retrieve-v2/field-filter-comp/field-item.tsx',
  ],
  [
    'features/retrieval/workbench/components/text-segmentation/index.tsx',
    'views/retrieve-v2/components/text-segmentation/index.tsx',
  ],
  [
    'features/retrieval/workbench/search-result-panel/graph-analysis/sql-editor/lang.ts',
    'views/retrieve-v2/search-result-panel/graph-analysis/sql-editor/lang.ts',
  ],
  [
    'features/retrieval/workspace/search-result/original-log/components/origin-log-result/index.tsx',
    'views/retrieve-v3/search-result/original-log/components/origin-log-result/index.tsx',
  ],
  [
    'features/extraction/current/extract-config/config-slider.tsx',
    'views/manage-v2/log-extract/extract-config/config-slider.tsx',
  ],
  [
    'features/extraction/classic/manage-extract-permission/directory-manage.vue',
    'views/manage/manage-extract/manage-extract-permission/directory-manage.vue',
  ],
];
const calls = new Set(['split', 'join', 'concat', 'indexOf', 'includes', 'startsWith', 'endsWith']);
function literals(url) {
  let source = readFileSync(url, 'utf8');
  if (url.pathname.endsWith('.vue')) source = source.match(/<script\b[^>]*>([\s\S]*?)<\/script>/)?.[1] ?? '';
  const ast = ts.createSourceFile(fileURLToPath(url), source, ts.ScriptTarget.Latest, true);
  const result = [];
  function visit(node) {
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      calls.has(node.expression.name.text)
    ) {
      const argument = node.arguments[0];
      if (argument && ts.isStringLiteral(argument) && ['.', './index'].includes(argument.text))
        result.push([node.expression.name.text, argument.text]);
    }
    ts.forEachChild(node, visit);
  }
  visit(ast);
  return result;
}
for (const [target, legacy] of files)
  test(`V2 business delimiters remain unchanged: ${target}`, () => {
    const expected = literals(new URL(legacy, legacyRoot));
    assert.ok(expected.length > 0);
    assert.deepEqual(literals(new URL(target, sourceRoot)), expected);
  });

test('module entry resolution cannot rewrite a business delimiter anywhere in V3', () => {
  const invalid = [];
  function walk(dir) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const url = new URL(entry.name + (entry.isDirectory() ? '/' : ''), dir);
      if (entry.isDirectory()) walk(url);
      else if (/\.(?:ts|tsx|vue|js)$/.test(entry.name)) {
        if (literals(url).some(([, value]) => value === './index')) invalid.push(fileURLToPath(url));
      }
    }
  }
  walk(sourceRoot);
  assert.deepEqual(invalid, []);
});

function businessParentPaths(url) {
  let source = readFileSync(url, 'utf8');
  if (url.pathname.endsWith('.vue')) source = source.match(/<script\b[^>]*>([\s\S]*?)<\/script>/)?.[1] ?? '';
  const ast = ts.createSourceFile(fileURLToPath(url), source, ts.ScriptTarget.Latest, true);
  const values = [];
  function visit(node) {
    if (
      ts.isStringLiteral(node) &&
      ['../', '../index'].includes(node.text) &&
      !ts.isImportDeclaration(node.parent) &&
      !ts.isExportDeclaration(node.parent)
    ) {
      values.push([ts.SyntaxKind[node.parent.kind], node.text]);
    }
    ts.forEachChild(node, visit);
  }
  visit(ast);
  return values;
}
for (const [target, legacy] of [
  ['features/extraction/download/create/preview-files.vue', 'views/extract/create/preview-files.vue'],
  [
    'features/extraction/current/extract-task/task-create/preview-files.tsx',
    'views/manage-v2/log-extract/extract-task/task-create/preview-files.tsx',
  ],
])
  test(`file explorer parent directory preserves V2 protocol: ${target}`, () => {
    const expected = businessParentPaths(new URL(legacy, legacyRoot));
    assert.ok(expected.length > 0);
    assert.deepEqual(businessParentPaths(new URL(target, sourceRoot)), expected);
  });
