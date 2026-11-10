/* Copyright (C) 2026 Tencent. BlueKing PaaS, MIT License. */
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, relative } from 'node:path';
import { parse } from '@vue/compiler-sfc';
import ts from 'typescript';
const root = fileURLToPath(new URL('../', import.meta.url));
const bridgeFiles = new Set([
  'platform/compat/vue-runtime.mjs', 'platform/compat/vue-runtime.d.mts', 'platform/compat/class-component-jsx.d.ts',
  'platform/compat/native-sdk-vue.ts', 'platform/compat/polyfill.ts',
  ...['bkui-icons', 'bkui-vue', 'info-box-contract', 'info-box', 'legacy-control-styles', 'legacy-functional', 'legacy-slot', 'loading-contract', 'loading', 'magic-controls', 'runtime-contract', 'select-filter']
    .map(name => `platform/compat/tdesign/${name}.ts`),
]);
const legacyModulePattern = /(?:bk-magic-vue|compat\/tdesign\/(?:magic-controls|info-box|loading))/;
const externalComponents = new Set(['bk-user-selector', 'bk-user-display-name', 'BkUserSelector', 'BkUserDisplayName']);
const isLegacyComponent = name => !externalComponents.has(name) && (/^bk-/.test(name) || /^Bk[A-Z]/.test(name));
const isLegacyDirective = name => /^v?-?bk(?:loading|[-A-Z])/.test(name);
const walk = dir => readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? walk(resolve(dir, entry.name)) : [resolve(dir, entry.name)]);
export function auditBusinessControls(sourceRoot = resolve(root, 'src')) {
  const occurrences = [];
  for (const filename of walk(sourceRoot).filter(file => /\.(?:vue|[cm]?[jt]sx?)$/.test(file))) {
    const path = relative(sourceRoot, filename).replaceAll('\\', '/');
    if (bridgeFiles.has(path)) continue;
    const source = readFileSync(filename, 'utf8');
    const record = (kind, name, start) => occurrences.push({ file: path, kind, name, line: source.slice(0, start).split('\n').length });
    const sections = [];
    if (filename.endsWith('.vue')) {
      const { descriptor } = parse(source);
      const visit = node => {
        if (node.type === 1 && isLegacyComponent(node.tag)) record('component', node.tag, node.loc.start.offset);
        for (const prop of node.props || []) if (prop.type === 7 && /^bk/.test(prop.name)) record('directive', prop.name, prop.loc.start.offset);
        for (const child of node.children || []) visit(child);
      };
      if (descriptor.template?.ast) visit(descriptor.template.ast);
      for (const script of [descriptor.script, descriptor.scriptSetup].filter(Boolean)) sections.push({ text: script.content, offset: script.loc.start.offset });
    } else sections.push({ text: source, offset: 0 });
    for (const section of sections) {
      const ast = ts.createSourceFile(filename, section.text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
      const imported = new Map();
      for (const node of ast.statements) {
        if (ts.isImportDeclaration(node) && legacyModulePattern.test(node.moduleSpecifier.text)) {
          for (const item of node.importClause?.namedBindings?.elements || []) imported.set(item.name.text, (item.propertyName || item.name).text);
          record('import', node.moduleSpecifier.text, section.offset + node.getStart(ast));
        }
        if (ts.isExportDeclaration(node) && node.moduleSpecifier && legacyModulePattern.test(node.moduleSpecifier.text)) {
          record('reexport', node.moduleSpecifier.text, section.offset + node.getStart(ast));
        }
      }
      const visit = node => {
        if (ts.isModuleDeclaration(node) && ts.isStringLiteral(node.name) && node.name.text === 'bk-magic-vue') record('declaration', node.name.text, section.offset + node.getStart(ast));
        if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
          const name = node.tagName.getText(ast);
          if (isLegacyComponent(name) || imported.has(name)) record('component', name, section.offset + node.getStart(ast));
          for (const prop of node.attributes.properties) if (prop.name && /^v-bk/.test(prop.name.getText(ast))) record('directive', prop.name.getText(ast), section.offset + prop.getStart(ast));
        }
        if (ts.isCallExpression(node)) {
          const name = node.expression.getText(ast);
          if (/\.(?:\$bkMessage|\$bkInfo|\$bkNotify|\$bkLoading|\$bkPopover)$/.test(name) || imported.has(name)) record('service', name, section.offset + node.getStart(ast));
          const first = node.arguments[0];
          const firstText = first && (ts.isStringLiteral(first) || ts.isNoSubstitutionTemplateLiteral(first)) ? first.text : null;
          if (
            firstText &&
            ((/\.(?:component)$/.test(name) || name === 'resolveComponent' || name === 'h') && isLegacyComponent(firstText) ||
              /\.(?:directive)$/.test(name) && isLegacyDirective(firstText))
          ) {
            record('registration', firstText, section.offset + node.getStart(ast));
          }
          if (/\.(?:use)$/.test(name) && first && ts.isIdentifier(first) && imported.has(first.text)) {
            record('registration', imported.get(first.text), section.offset + node.getStart(ast));
          }
        }
        ts.forEachChild(node, visit);
      };
      visit(ast);
    }
  }
  const counts = {};
  for (const item of occurrences) counts[item.kind] = (counts[item.kind] || 0) + 1;
  return { status: occurrences.length ? 'INCOMPLETE' : 'PASSED', scope: 'business source and declarations excluding explicit vendor bridge files and external user components', files: new Set(occurrences.map(item => item.file)).size, total: occurrences.length, counts, occurrences };
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const report = auditBusinessControls();
  if (process.argv.includes('--write')) writeFileSync(resolve(root, 'ai-native/business-controls.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ ...report, occurrences: undefined }, null, 2));
  if (!process.argv.includes('--write') && report.total) process.exitCode = 1;
}
