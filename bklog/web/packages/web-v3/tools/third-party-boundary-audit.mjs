/* Copyright (C) 2026 Tencent. BlueKing PaaS, MIT License. */
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from '@vue/compiler-sfc';
import ts from 'typescript';

const root = fileURLToPath(new URL('../', import.meta.url));
const oldUiPackages = new Set(['bk-magic-vue', 'bkui-vue', '@blueking/bkui-library']);
const walk = directory =>
  readdirSync(directory, { withFileTypes: true }).flatMap(entry =>
    entry.isDirectory() ? walk(resolve(directory, entry.name)) : [resolve(directory, entry.name)],
  );
const normalize = value => value.replaceAll('\\', '/');

function classifyImport(file, source, typeOnly) {
  const compat = /(?:^|\/)platform\/compat\/tdesign\/(?:magic-controls|bkui-vue|bkui-icons)$/.test(source);
  const oldUi = oldUiPackages.has(source);
  const sdk = source.startsWith('@blueking/');
  const trackedDebt =
    compat ||
    (source === 'bk-magic-vue' && file === 'shared/types/global-controls.d.ts' && typeOnly) ||
    source.startsWith('@blueking/ai-blueking/vue2') ||
    source === '@blueking/user-selector' ||
    source === '@blueking/ip-selector/dist/styles/vue2.6.x.css';
  return { compat, oldUi, sdk, trackedDebt };
}

function sdkViolation(file, source) {
  if (source.startsWith('@blueking/date-picker')) {
    if (file === 'platform/sdk/date-picker/native-entry.ts' && source === '@blueking/date-picker') return '';
    const validEntry = source === '@blueking/date-picker' || source === '@blueking/date-picker/vue3/vue3.css';
    return !validEntry || !file.startsWith('shared/ui/time-range/') ? 'date-picker must use its Vue3 boundary' : '';
  }
  if (source.startsWith('@blueking/bk-user-selector')) {
    const valid =
      source === '@blueking/bk-user-selector'
        ? file === 'shared/ui/user-selector/index.tsx'
        : source === '@blueking/bk-user-selector/vue3/vue3.css' &&
          ['app/bootstrap/start.js', 'app/entries/monitor-bootstrap.ts'].includes(file);
    return valid ? '' : 'bk-user-selector must use its Vue3 boundary';
  }
  if (source.startsWith('@blueking/login-userinfo')) {
    const valid =
      file === 'shared/global/head-navi/index.tsx' &&
      (source === '@blueking/login-userinfo' || source === '@blueking/login-userinfo/vue3/vue3.css');
    return valid ? '' : 'login-userinfo must use its Vue3 boundary';
  }
  const packageName = source.split('/').slice(0, 2).join('/');
  const owners = {
    '@blueking/ai-blueking': ['shared/global/ai-assitant/index.tsx'],
    '@blueking/bk-user-display-name': ['app/bootstrap/preload.ts'],
    '@blueking/ip-selector': ['features/collection/ip-selector/log-ip-selector.tsx'],
    '@blueking/log-web': ['features/retrieval/classic/helper.ts'],
    '@blueking/login-modal': ['platform/http/index.js'],
    '@blueking/notice-component': ['app/shell/app.tsx'],
    '@blueking/open-telemetry': ['platform/observability/open-telemetry.ts'],
    '@blueking/platform-config': ['app/state/modules/platform-config.ts'],
    '@blueking/user-selector': [
      'features/clusters/current/cluster-manage/intro-panel.tsx',
      'features/clusters/status/es-cluster-mess/components/intro-panel.vue',
      'features/extraction/classic/manage-extract-permission/directory-manage.vue',
      'features/extraction/classic/manage-extract-permission/validate-user-selector.vue',
      'features/retrieval/workbench/search-result-panel/log-clustering/components/quick-create-subscription-drawer/create-subscription-form.tsx',
      'features/retrieval/workbench/search-result-panel/log-clustering/data-fingerprint.vue',
      'features/retrieval/workspace/search-result/log-clustering/log-table/content-table/index.tsx',
      'features/retrieval/workspace/search-result/log-clustering/top-operation/email-subscription/create-subscription/subscription-form/send-config/index.tsx',
    ],
  };
  return owners[packageName]?.includes(file) ? '' : 'BlueKing SDK import is outside its frozen owner';
}

export function auditThirdPartyBoundary(sourceRoot = resolve(root, 'src')) {
  const imports = [];
  const registrations = [];
  for (const filename of walk(sourceRoot).filter(file => /\.(?:vue|[cm]?[jt]sx?|d\.ts)$/.test(file))) {
    const file = normalize(relative(sourceRoot, filename));
    const source = readFileSync(filename, 'utf8');
    const sections = filename.endsWith('.vue')
      ? [parse(source).descriptor.script, parse(source).descriptor.scriptSetup]
          .filter(Boolean)
          .map(section => section.content)
      : [source];
    for (const section of sections) {
      const ast = ts.createSourceFile(filename, section, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
      const visit = node => {
        let specifier;
        let typeOnly = false;
        if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
          specifier = node.moduleSpecifier;
          typeOnly = Boolean(node.importClause?.isTypeOnly || node.isTypeOnly);
        } else if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
          specifier = node.arguments[0];
        }
        if (specifier && ts.isStringLiteral(specifier)) {
          const classification = classifyImport(file, specifier.text, typeOnly);
          if (classification.compat || classification.oldUi || classification.sdk) {
            const symbols = ts.isImportDeclaration(node)
              ? [
                  ...(node.importClause?.name ? ['default'] : []),
                  ...(node.importClause?.namedBindings && ts.isNamedImports(node.importClause.namedBindings)
                    ? node.importClause.namedBindings.elements.map(item => (item.propertyName || item.name).text)
                    : []),
                  ...(node.importClause?.namedBindings && ts.isNamespaceImport(node.importClause.namedBindings) ? ['*'] : []),
                ]
              : [];
            imports.push({ file, source: specifier.text, symbols, typeOnly, ...classification });
          }
        }
        if (ts.isCallExpression(node)) {
          const callee = node.expression.getText(ast);
          const first = node.arguments[0];
          if (first && ts.isStringLiteral(first)) {
            const legacyComponent =
              node.arguments.length >= 2 && /\.component$/.test(callee) && (/^Bk[A-Z]/.test(first.text) || /^bk-/.test(first.text));
            const legacyDirective = /\.directive$/.test(callee) && /^bk/.test(first.text);
            if (legacyComponent || legacyDirective) registrations.push({ file, kind: legacyComponent ? 'component' : 'directive', name: first.text });
          }
        }
        ts.forEachChild(node, visit);
      };
      visit(ast);
    }
  }
  const violations = [];
  for (const item of imports) {
    if (item.oldUi && !item.trackedDebt) violations.push({ ...item, reason: 'direct old UI package import is forbidden' });
    const reason = item.sdk ? sdkViolation(item.file, item.source) : '';
    if (reason) violations.push({ ...item, reason });
  }
  for (const item of registrations) {
    const allowed =
      item.file === 'features/retrieval/workspace/monitor/trace.ts' ||
      (item.file === 'app/bootstrap/configure-app.ts' && item.kind === 'directive' && item.name === 'bkloading');
    if (!allowed) violations.push({ ...item, reason: 'legacy global registration is outside its frozen owner' });
  }
  const trackedDebt = [
    ...imports.filter(item => item.trackedDebt),
    ...registrations.filter(item =>
      item.file === 'features/retrieval/workspace/monitor/trace.ts' ||
      (item.file === 'app/bootstrap/configure-app.ts' && item.name === 'bkloading'),
    ),
  ];
  return {
    status: violations.length ? 'FAILED' : 'FROZEN_WITH_TRACKED_DEBT',
    scope: 'source imports, dynamic imports, reexports, and literal global registrations',
    counts: {
      imports: imports.length,
      compatibilityImports: imports.filter(item => item.compat).length,
      sdkImports: imports.filter(item => item.sdk).length,
      legacyRegistrations: registrations.length,
      trackedDebt: trackedDebt.length,
      violations: violations.length,
    },
    imports,
    registrations,
    trackedDebt,
    violations,
  };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const report = auditThirdPartyBoundary();
  if (process.argv.includes('--write')) {
    writeFileSync(resolve(root, 'ai-native/third-party-boundary.json'), `${JSON.stringify(report, null, 2)}\n`);
  }
  console.log(JSON.stringify({ ...report, imports: undefined, registrations: undefined, trackedDebt: undefined }, null, 2));
  if (report.violations.length) process.exitCode = 1;
}
