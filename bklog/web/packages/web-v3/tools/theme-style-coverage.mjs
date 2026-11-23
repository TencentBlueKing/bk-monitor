/** Full source ownership ledger; records source metadata only, never runtime data. */
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { inlineControlStyleMetrics } from './inline-control-styles.mjs';
import { styleDeclarations, normalizeStyle } from './tdesign-style-source.mjs';

const project = fileURLToPath(new URL('../', import.meta.url));
const source = resolve(project, 'src');
const ledgerFile = resolve(project, 'ai-native/theme-style-contracts.json');
const componentRoot = 'shared/styles/theme/components/';
// Colors that still have no semantic token. A new hex in these files is rejected.
const retainedHex = {
  'shared/styles/theme/components/display.scss': ['#14a568', '#fe9c00', '#ea3536', '#c5daff', '#f0f8ff', '#ffdfac', '#fff4e2', '#94f5a4', '#f2fff4', '#ffd2d2', '#ffeded'],
  'shared/styles/theme/components/options.scss': ['#f4f6fa'],
};

export function sharedComponentLiteralViolations(file, text) {
  if (!file.startsWith(componentRoot)) return [];
  const stripped = text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
  const allowed = new Set(retainedHex[file] || []);
  const violations = [];
  for (const match of stripped.matchAll(/#[\da-f]{3,8}\b/gi)) {
    const color = match[0].toLowerCase();
    if (!allowed.has(color)) violations.push(`hex:${color}`);
  }
  if (/font-size\s*:[^;{}]*\b(?:12|14|16)px\b/.test(stripped)) violations.push('font-size');
  if (/border-radius\s*:[^;{}]*\b2px\b/.test(stripped)) violations.push('border-radius');
  if (/(?:^|[^-\w])border(?:-(?:top|right|bottom|left))?(?:-width)?\s*:[^;{}]*\b1px\b/m.test(stripped)) violations.push('border-width');
  return violations;
}

function collectCoverage() {
  const walk = dir => readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? walk(resolve(dir, entry.name)) : entry.isFile() ? [resolve(dir, entry.name)] : []);
  const visual = /^(?:color|background(?:-color)?|border(?:-(?:top|right|bottom|left))?(?:-color)?|outline(?:-color)?|font(?:-size|-family|-weight)?|line-height|box-shadow|border-radius|fill|stroke)$/;
  const files = [];
  let pending = 0;
  const literalViolations = [];
  for (const path of walk(source).filter(path => /\.(scss|vue|[jt]sx?)$/.test(path))) {
    const file = relative(source, path).replaceAll('\\', '/');
    const text = readFileSync(path, 'utf8');
    const violations = sharedComponentLiteralViolations(file, text);
    if (violations.length) literalViolations.push({ file, violations });
    const sections = file.endsWith('.scss') ? [text] : [...text.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)].map(match => match[1]);
    const declarations = sections.flatMap(styleDeclarations);
    const inline = inlineControlStyleMetrics(file, text);
    const contracts = [...text.matchAll(/@include bklogControls\.([\w-]+)/g)].map(match => match[1]);
    const classes = [...new Set(sections.flatMap(section => (section.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '').match(/\.t-[\w-]+/g) || [])))].sort();
    if (!classes.length && !contracts.length && !inline.nativeStyleSites) continue;
    const owner = file.startsWith('features/') ? 'business-context' : file.startsWith('shared/styles/theme/') ? 'shared-theme' : file.startsWith('shared/ui/') ? 'shared-control' : 'application-shell';
    const localVisual = declarations.filter(decl => visual.test(decl.property) && !decl.value.includes('--bklog-'));
    const pendingNormalization = sections.reduce((sum, section) => sum + normalizeStyle(section).count, 0);
    pending += pendingNormalization + inline.pendingInlineNormalization;
    files.push({ file, owner, inline, componentClasses: classes, sharedContracts: [...new Set(contracts)].sort(), semanticDeclarations: declarations.filter(decl => decl.value.includes('--bklog-')).length, contextualDeclarations: declarations.filter(decl => !visual.test(decl.property)).length, localVisualProperties: [...new Set(localVisual.map(decl => decl.property))].sort(), localVisualDeclarations: localVisual.length, pendingNormalization });
  }
  files.sort((a, b) => a.file.localeCompare(b.file));
  return { files, pending, literalViolations };
}

function main() {
  const { files, pending, literalViolations } = collectCoverage();
  const coverage = { schemaVersion: 1, scope: 'SCSS, Vue style blocks and static inline visuals on native controls. Dynamic inline bindings retain business ownership. Local geometry, state adaptations, transparent/inherit values and special visuals retain their source selector; not a runtime acceptance ledger.', files };
  if (literalViolations.length) {
    console.error('Shared theme components reintroduced standard literals.');
    console.error(JSON.stringify(literalViolations, null, 2));
    process.exitCode = 1;
  }
  if (process.argv.includes('--write')) writeFileSync(ledgerFile, JSON.stringify(coverage, null, 2) + '\n');
  else {
    const expected = JSON.parse(readFileSync(ledgerFile, 'utf8'));
    if (JSON.stringify(expected) !== JSON.stringify(coverage)) { console.error('Theme source ownership changed; review the affected files before updating the ledger.'); process.exitCode = 1; }
  }
  const modules = {};
  for (const file of files.filter(file => file.owner === 'business-context')) { const module = file.file.split('/')[1]; modules[module] = (modules[module] || 0) + 1; }
  console.log(JSON.stringify({ status: literalViolations.length ? 'SHARED_LITERALS' : pending ? 'PENDING_NORMALIZATION' : process.exitCode ? 'REVIEW_REQUIRED' : 'COVERED', files: files.length, businessFiles: files.filter(file => file.owner === 'business-context').length, pendingNormalization: pending, inlineSites: files.reduce((sum, file) => sum + file.inline.nativeStyleSites, 0), dynamicInlineSites: files.reduce((sum, file) => sum + file.inline.dynamicStyleSites, 0), modules }, null, 2));
  if (pending) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
