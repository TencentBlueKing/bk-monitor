/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { readFileSync, readdirSync, existsSync, writeFileSync } from 'node:fs';
import { resolve, dirname, relative, extname, posix } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const ts = require('typescript');
const { parse: parseSfc } = require('@vue/compiler-sfc');
export const packageRoot = fileURLToPath(new URL('../', import.meta.url));
const sourceRoot = resolve(packageRoot, 'src');
const metadataRoot = resolve(packageRoot, 'ai-native');
const readJson = name => JSON.parse(readFileSync(resolve(metadataRoot, name), 'utf8'));
export function walk(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap(entry =>
    entry.isDirectory() ? walk(resolve(root, entry.name)) : [resolve(root, entry.name)]).sort();
}
export function moduleOf(file) {
  const parts = file.split('/');
  if (parts.length === 1) return 'app';
  return parts[0] === 'features' ? `features/${parts[1]}` : parts[0];
}
export function resolveReference(owner, specifier, root = sourceRoot) {
  let path = specifier.split(/[?#]/)[0];
  if (path.includes('!')) path = path.split('!').at(-1);
  if (path.startsWith('@/')) path = resolve(root, path.slice(2));
  else if (path.startsWith('.')) path = resolve(root, dirname(owner), path);
  else return null;
  for (const extension of ['', '.js', '.ts', '.d.ts', '.tsx', '.jsx', '.vue', '.mjs', '.json', '.scss', '.css']) {
    for (const candidate of [path + extension, resolve(path, 'index' + extension), resolve(dirname(path), '_' + posix.basename(path) + extension)]) {
      if (existsSync(candidate) && !readdirIsDirectory(candidate)) return relative(root, candidate).split('\\').join('/');
    }
  }
  return undefined;
}
function readdirIsDirectory(path) {
  try { readdirSync(path); return true; } catch { return false; }
}
export function references(code, file) {
  const sources = [];
  if (file.endsWith('.vue')) {
    const { descriptor } = parseSfc(code, { filename: file });
    for (const block of [descriptor.script, descriptor.scriptSetup]) if (block) sources.push(block.content);
  } else if (/\.[cm]?[jt]sx?$/.test(file)) sources.push(code);
  const result = [];
  for (const source of sources) {
    const ast = ts.createSourceFile(file + '.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const visit = node => {
      if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
        const bindings = ts.isImportDeclaration(node) ? node.importClause?.namedBindings : node.exportClause;
        const typeOnly = node.isTypeOnly || node.importClause?.isTypeOnly ||
          (bindings && ts.isNamedImports(bindings) && bindings.elements.length > 0 && bindings.elements.every(binding => binding.isTypeOnly));
        result.push({ specifier: node.moduleSpecifier.text, kind: typeOnly ? 'type' : 'module' });
      }
      // Methods passed to selectors/retry helpers retain their service owner.
      if (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) {
        const name = node.getText(ast);
        const named = /^ServicesInstance\.(\w+)\.(\w+)$/.exec(name);
        const indexed = /^ServicesInstance\.(\w+)\[/.exec(name);
        if (named || indexed) result.push({ specifier: named ? `${named[1]}/${named[2]}` : `${indexed[1]}/*`, kind: 'service-call' });
      }
      if ((ts.isCallExpression(node) || ts.isNewExpression(node)) && node.arguments?.length) {
        const name = node.expression.getText(ast);
        if (/(?:\$http|\bhttp)\.request$/.test(name)) {
          result.push(ts.isStringLiteral(node.arguments[0])
            ? { specifier: node.arguments[0].text, kind: 'service-call' }
            : { specifier: node.arguments[0].getText(ast), kind: 'dynamic-request' });
        }
        if (['import', 'require', 'URL', 'Worker', 'import.meta.glob'].includes(name)) {
          if (ts.isStringLiteral(node.arguments[0])) result.push({ specifier: node.arguments[0].text, kind: name });
          else if (name === 'import' || name === 'require') result.push({ specifier: node.arguments[0].getText(ast), kind: 'dynamic-unresolved' });
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(ast);
  }
  // Include template assets and Sass/CSS edges in impact analysis, beyond JavaScript imports.
  for (const match of code.matchAll(/(?:@(?:import|use)\s+|\b(?:src|href)=|url\(\s*)['"]([^'"\n]+)['"]/g))
    result.push({ specifier: match[1], kind: 'style-or-asset' });
  return result;
}
function serviceProviders(root) {
  const owner = ['app/bootstrap/service-definitions.ts', 'app/bootstrap/service-definitions.js', 'services/index.js'].find(file => existsSync(resolve(root, file)));
  if (!owner) return new Map();
  if (!existsSync(resolve(root, owner))) return new Map();
  const ast = ts.createSourceFile(owner, readFileSync(resolve(root, owner), 'utf8'), ts.ScriptTarget.Latest, true);
  const imports = new Map(), providers = new Map();
  for (const node of ast.statements) {
    if (ts.isImportDeclaration(node)) {
      const local = node.importClause?.name || (node.importClause?.namedBindings && ts.isNamespaceImport(node.importClause.namedBindings) ? node.importClause.namedBindings.name : undefined);
      if (local) imports.set(local.text, resolveReference(owner, node.moduleSpecifier.text, root));
    }
  }
  for (const node of ast.statements) if (ts.isExportAssignment(node) && ts.isObjectLiteralExpression(node.expression)) {
    for (const prop of node.expression.properties) {
      const key = prop.name?.getText(ast).replace(/['"]/g, '');
      const identifier = ts.isShorthandPropertyAssignment(prop) ? prop.name.text : ts.isPropertyAssignment(prop) ? prop.initializer.getText(ast) : '';
      if (key) providers.set(key, imports.get(identifier) || owner);
    }
  }
  return providers;
}
export function scan(root = sourceRoot) {
  const files = walk(root).map(file => relative(root, file).split('\\').join('/'));
  const edges = [], unresolved = [], dynamic = [];
  const providers = serviceProviders(root);
  for (const file of files) {
    if (!/\.(?:[cm]?[jt]sx?|vue|scss|css|html)$/.test(file)) continue;
    const code = readFileSync(resolve(root, file), 'utf8');
    for (const ref of references(code, file)) {
      if (ref.kind === 'service-call') {
        const provider = providers.get(ref.specifier.split('/')[0]);
        if (provider) edges.push({ from: file, to: provider, kind: ref.kind });
        else dynamic.push({ file, ...ref, note: 'Unknown service namespace; inspect request contract' });
        continue;
      }
      if (ref.kind === 'dynamic-unresolved' || ref.kind === 'dynamic-request' || ref.kind === 'import.meta.glob') { dynamic.push({ file, ...ref }); continue; }
      const to = resolveReference(file, ref.specifier, root);
      if (to === undefined) unresolved.push({ file, ...ref });
      else if (to !== null) edges.push({ from: file, to, kind: ref.kind });
    }
  }
  return { schemaVersion: 1, files, edges, unresolved, dynamic };
}
export function impacted(graph, changed) {
  const reverse = new Map();
  for (const edge of graph.edges) reverse.set(edge.to, [...(reverse.get(edge.to) || []), edge.from]);
  const seen = new Set(changed), queue = [...changed];
  for (let index = 0; index < queue.length; index++)
    for (const caller of reverse.get(queue[index]) || []) if (!seen.has(caller)) { seen.add(caller); queue.push(caller); }
  return [...seen].sort();
}
const edgeKey = edge => `${edge.from} -> ${edge.to}`;
export function architectureViolations(graph, debt) {
  const allowed = new Set(debt.map(edgeKey));
  return graph.edges.filter(edge => edge.kind !== 'type' && ['platform', 'shared'].includes(moduleOf(edge.from)) && moduleOf(edge.to).startsWith('features/') && !allowed.has(edgeKey(edge)));
}
// Type annotations and formatting do not change a redirect contract. Canonicalize
// both the frozen V2 expression and the current expression through TS emission.
function routeExpression(node, ast) {
  if (!node) return null;
  const emitted = ts.transpileModule(`const redirect = ${node.getText(ast)};`, { compilerOptions: {
    target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.ESNext, removeComments: true,
  } }).outputText;
  return emitted.trim().replace(/^const redirect = /, '').replace(/;$/, '');
}
export function routeSignatures(root = sourceRoot, prefix = 'app/router') {
  const result = [];
  for (const file of ['retrieve.js', 'monitor.js', 'dashboard.js', 'manage.js', 'index.js']) {
    const actualFile = existsSync(resolve(root, prefix, file)) ? file : file.replace(/\.js$/, '.ts');
    const code = readFileSync(resolve(root, prefix, actualFile), 'utf8');
    const ast = ts.createSourceFile(file, code, ts.ScriptTarget.Latest, true);
    const visit = node => {
      if (ts.isObjectLiteralExpression(node)) {
        const props = Object.fromEntries(node.properties.filter(ts.isPropertyAssignment).map(prop => [prop.name.getText(ast), prop.initializer]));
        if (props.path && ts.isStringLiteral(props.path)) result.push({ file, path: props.path.text,
          name: props.name && ts.isStringLiteral(props.name) ? props.name.text : null,
          component: props.component?.getText(ast) || null, redirect: routeExpression(props.redirect, ast) });
      }
      ts.forEachChild(node, visit);
    };
    visit(ast);
  }
  return result;
}
export function check(graph) {
  const errors = [];
  const manifest = readJson('source-map.json');
  if (manifest.files.length + (manifest.excluded?.length || 0) + (manifest.consolidated?.length || 0) !== manifest.sourceCount) errors.push('source inventory count mismatch');
  const targets = new Set();
  for (const item of manifest.files) {
    if (targets.has(item.target)) errors.push(`duplicate target ${item.target}`);
    targets.add(item.target);
    const targetRoot = item.targetScope === 'package-test' ? packageRoot : sourceRoot;
    if (item.targetScope && item.targetScope !== 'package-test') errors.push(`unknown target scope ${item.targetScope}`);
    if (!existsSync(resolve(targetRoot, item.target))) errors.push(`missing migrated file ${item.target}`);
  }
  for (const item of manifest.consolidated || []) {
    if (!item.reason || !targets.has(item.target)) errors.push(`untracked consolidation ${item.source}`);
  }
  for (const file of graph.files.filter(file => /\.(?:[cm]?[jt]sx?|vue|scss|css)$/.test(file))) {
    const code = readFileSync(resolve(sourceRoot, file), 'utf8');
    if (/src-native\//.test(code)) errors.push(`baseline runtime reference ${file}`);
  }
  const known = new Set(readJson('unresolved-baseline.json').map(item => `${item.file}:${item.specifier}:${item.kind}`));
  for (const item of graph.unresolved) if (!known.has(`${item.file}:${item.specifier}:${item.kind}`)) errors.push(`unresolved ${item.file}: ${item.specifier}`);
  for (const edge of architectureViolations(graph, readJson('boundary-debt.json'))) errors.push(`new upward dependency ${edgeKey(edge)}`);
  if (JSON.stringify(routeSignatures()) !== JSON.stringify(readJson('route-signatures.json'))) errors.push('route behavior changed: review source contract before updating signatures');
  const saved = readJson('dependency-graph.json');
  if (JSON.stringify(saved) !== JSON.stringify(graph)) errors.push('graph stale: run ai:index and review changes');
  return errors;
}
function writeIndex(graph) {
  writeFileSync(resolve(metadataRoot, 'dependency-graph.json'), JSON.stringify(graph, null, 2) + '\n');
  const previous = readJson('modules.json').map(item => ({ ...item, data: readJson(item.descriptor.replace('ai-native/', '')) }));
  const modules = [...new Set(graph.files.map(moduleOf))].sort();
  const index = [];
  for (const id of modules) {
    const descriptor = `ai-native/modules/${id.replaceAll('/', '-')}.json`;
    const files = graph.files.filter(file => moduleOf(file) === id);
    const old = previous.find(item => item.id === id)?.data || {};
    const data = { ...old, id, root: `src/${id}`, files: files.length,
      entryPoints: files.filter(file => /(?:^|\/)(?:index|main)\.(?:vue|tsx|ts|js)$/.test(file)),
      services: files.filter(file => file.includes('/services/')),
      dependsOn: [...new Set(graph.edges.filter(edge => moduleOf(edge.from) === id && moduleOf(edge.to) !== id).map(edge => moduleOf(edge.to)))].sort() };
    writeFileSync(resolve(packageRoot, descriptor), JSON.stringify(data, null, 2) + '\n');
    index.push({ id, descriptor });
  }
  writeFileSync(resolve(metadataRoot, 'modules.json'), JSON.stringify(index, null, 2) + '\n');
}
function main() {
  const [command = 'check', ...args] = process.argv.slice(2);
  const graph = scan();
  if (command === 'index') {
    writeIndex(graph);
    console.log(`Indexed ${graph.files.length} files, ${graph.edges.length} static edges; ${graph.dynamic.length} dynamic patterns require review.`);
    return;
  }
  if (command === 'check') {
    const errors = check(graph);
    console.log(JSON.stringify({ status: errors.length ? 'FAILED' : 'PASSED', files: graph.files.length, edges: graph.edges.length, errors }, null, 2));
    process.exitCode = errors.length ? 1 : 0;
    return;
  }
  if (!['context', 'impact'].includes(command)) throw new Error('Use check, index, context or impact');
  const moduleArg = args.find(arg => arg.startsWith('--module='))?.slice(9);
  const seeds = args.filter(arg => !arg.startsWith('--')).map(file => file.replace(/^src\//, ''));
  if (moduleArg) {
    const files = graph.files.filter(file => moduleOf(file) === `features/${moduleArg}` || moduleOf(file) === moduleArg);
    seeds.push(...files.filter(file => /(?:^|\/)index\.(?:tsx?|js|vue)$/.test(file)), ...files.filter(file => file.includes('/services/')), ...files);
  }
  const uniqueSeeds = [...new Set(seeds)]; seeds.length = 0; seeds.push(...uniqueSeeds);
  if (!seeds.length) throw new Error('Specify --module=retrieval or source-relative changed files');
  const unknown = seeds.filter(file => !graph.files.includes(file));
  if (unknown.length) throw new Error(`Unknown files: ${unknown.join(', ')}`);
  const affected = impacted(graph, seeds);
  const modules = [...new Set(affected.map(moduleOf))];
  const requestedLimit = Number(args.find(arg => arg.startsWith('--limit='))?.slice(8) || 30);
  if (!Number.isInteger(requestedLimit) || requestedLimit < 1 || requestedLimit > 100) throw new Error('--limit must be an integer from 1 to 100');
  const limit = requestedLimit;
  const dependencies = graph.edges.filter(edge => seeds.includes(edge.from)).map(edge => edge.to);
  const selected = [...new Set([...seeds, ...dependencies, ...affected])];
  const routes = readJson('routes.json').filter(route => affected.includes(route.targetRouter));
  console.log(JSON.stringify({ schemaVersion: 1, command, seeds: seeds.slice(0, limit), seedCount: seeds.length, affectedCount: affected.length,
    modules, files: (command === 'context' ? selected : affected).slice(0, limit), truncated: selected.length > limit,
    routeCount: routes.length, routes: routes.slice(0, limit).map(route => ({ name: route.name, path: route.path })),
    moduleDescriptors: readJson('modules.json').filter(item => modules.includes(item.id)).map(item => ({ id: item.id, descriptor: item.descriptor })),
    failureMemory: 'ai-native/failure-memory.json',
    commands: ['pnpm --ignore-workspace ai:check', 'pnpm --ignore-workspace test', 'pnpm --ignore-workspace build'],
    limitations: 'Conservative static graph; route reachability includes both version branches. Browser and dynamic paths still require verification.' }, null, 2));
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
