import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../..', import.meta.url));
const req = createRequire(root + '/package.json');
const { parse } = req('@babel/parser');
const traverse = req('@babel/traverse').default;
const routes = [];
for (const file of ['retrieve', 'manage', 'dashboard', 'monitor', 'index']) {
  const source = 'src/router/' + file + '.js';
  const code = readFileSync(root + '/' + source, 'utf8');
  const ast = parse(code, { sourceType: 'module' });
  const map = new Map();
  traverse(ast, {
    ObjectExpression(p) {
      const prop = n => p.node.properties.find(e => e.type === 'ObjectProperty' && e.key.name === n)?.value;
      const path = prop('path');
      if (path?.type !== 'StringLiteral' || !['name', 'component', 'redirect', 'children'].some(n => prop(n))) return;
      const name = prop('name'),
        component = prop('component'),
        redirect = prop('redirect');
      const row = {
        source,
        line: p.node.loc.start.line,
        localPath: path.value,
        name: name?.value || null,
        component: component ? code.slice(component.start, component.end) : null,
        redirect: redirect ? code.slice(redirect.start, redirect.end) : null,
        status: 'PENDING',
        businessAccepted: false,
        visualAccepted: false,
        evidence: [],
      };
      let parent = p.parentPath;
      while (parent && !map.has(parent.node)) parent = parent.parentPath;
      const prefix = parent ? map.get(parent.node).path : '';
      row.path =
        path.value.startsWith('/') || path.value === '*'
          ? path.value
          : (prefix.replace(/\/$/, '') + '/' + path.value).replace(/\/+/g, '/');
      map.set(p.node, row);
      routes.push(row);
    },
  });
}
const dir = root + '/migration-project/artifacts/verification/2026-10-28/full-business';
// Preserve accumulated evidence when new source entries are discovered.
try {
  const previous = JSON.parse(readFileSync(dir + '/routes.json', 'utf8')).routes;
  for (const row of routes) {
    const old = previous.find(item => item.source === row.source && item.name === row.name && item.path === row.path);
    if (old)
      for (const key of ['status', 'businessAccepted', 'visualAccepted', 'evidence', 'notes']) {
        if (key in old) row[key] = old[key];
      }
  }
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
mkdirSync(dir, { recursive: true });
writeFileSync(
  dir + '/routes.json',
  JSON.stringify(
    {
      source: 'V2 source routes, including unnamed redirects and layouts',
      routeCount: routes.length,
      named: routes.filter(r => r.name).length,
      routes,
    },
    null,
    2,
  ) + '\n',
);
console.log({ routes: routes.length, named: routes.filter(r => r.name).length });
