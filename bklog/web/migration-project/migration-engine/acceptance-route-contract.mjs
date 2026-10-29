/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { createRequire } from 'node:module';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
const webRoot = fileURLToPath(new URL('../..', import.meta.url));
const require = createRequire(resolve(webRoot, 'package.json'));
const { parse } = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const literal = node =>
  node && ['StringLiteral', 'BooleanLiteral', 'NumericLiteral', 'NullLiteral'].includes(node.type)
    ? (node.value ?? null)
    : undefined;
export function scanRouteContracts(root) {
  const routes = [];
  for (const name of ['retrieve', 'manage', 'dashboard', 'monitor', 'index']) {
    const source = ['ts', 'js'].map(extension => resolve(root, `${name}.${extension}`)).find(existsSync);
    const code = readFileSync(source, 'utf8');
    const ast = parse(code, { sourceType: 'module', plugins: ['typescript', 'jsx'] });
    const parents = new Map();
    traverse(ast, {
      ObjectExpression(path) {
        const prop = key =>
          path.node.properties.find(node => node.type === 'ObjectProperty' && node.key.name === key)?.value;
        const localPath = prop('path');
        if (localPath?.type !== 'StringLiteral' || !['name', 'component', 'redirect', 'children'].some(prop)) return;
        let ancestor = path.parentPath;
        while (ancestor && !parents.has(ancestor.node)) ancestor = ancestor.parentPath;
        const prefix = ancestor ? parents.get(ancestor.node).path : '';
        const meta = prop('meta');
        const item = {
          name: literal(prop('name')) ?? null,
          path:
            localPath.value.startsWith('/') || localPath.value === '*'
              ? localPath.value
              : `${prefix.replace(/\/$/, '')}/${localPath.value}`.replace(/\/+/g, '/'),
          meta:
            meta?.type === 'ObjectExpression'
              ? Object.fromEntries(
                  meta.properties
                    .filter(node => node.type === 'ObjectProperty' && literal(node.value) !== undefined)
                    .map(node => [node.key.name, literal(node.value)]),
                )
              : {},
          source: basename(source),
          line: path.node.loc.start.line,
        };
        parents.set(path.node, item);
        routes.push(item);
      },
    });
  }
  return routes;
}
const normalize = route => ({
  name: route.name,
  path: route.name === 'exception' && route.path === '/:pathMatch(.*)*' ? '*' : route.path,
  meta: route.meta,
});
export function compareRouteContracts(source, target) {
  const key = route => JSON.stringify([route.name, route.path]);
  const normalized = target.map(normalize);
  return {
    scope:
      'literal route names, full paths and literal navigation metadata; runtime behavior requires separate evidence',
    sourceRoutes: source.length,
    sourceNamedRoutes: source.filter(route => route.name).length,
    targetRoutes: target.length,
    missing: source.filter(route => !normalized.some(item => key(item) === key(route))),
    extra: normalized.filter(route => !source.some(item => key(item) === key(route))),
    metadataDifferences: source.flatMap(route => {
      const item = normalized.find(item => key(item) === key(route));
      return item &&
        JSON.stringify(Object.entries(item.meta).sort()) !== JSON.stringify(Object.entries(route.meta).sort())
        ? [{ name: route.name, path: route.path, source: route.meta, target: item.meta }]
        : [];
    }),
  };
}
export function currentRouteContract() {
  return compareRouteContracts(
    scanRouteContracts(resolve(webRoot, 'src/router')),
    scanRouteContracts(resolve(webRoot, 'packages/web-v3/src/app/router')),
  );
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const report = currentRouteContract();
  console.log(JSON.stringify(report, null, 2));
  process.exitCode = report.missing.length || report.extra.length || report.metadataDifferences.length ? 1 : 0;
}
