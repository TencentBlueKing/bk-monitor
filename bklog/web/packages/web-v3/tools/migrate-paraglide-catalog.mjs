/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import ts from 'typescript';
import { getBaselineRoot } from './source-baseline.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
const require = createRequire(new URL('../package.json', import.meta.url));
const sources = ['route', 'button', 'label', 'content'].map(name => `language/lang/en/${name}.ts`);
const sourcePath = file => resolve(getBaselineRoot(), file);
function readDictionary(file) {
  const source = readFileSync(sourcePath(file), 'utf8');
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  if (ast.statements.some(ts.isImportDeclaration)) throw new Error(`Catalog must remain a data-only module: ${file}`);
  const output = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
  const exports = {};
  new Function('exports', output)(exports);
  return exports.default;
}
function flatten(input, prefix = '', output = {}) {
  for (const [key, value] of Object.entries(input)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'string') output[path] = value;
    else if (value && typeof value === 'object') flatten(value, path, output);
    else throw new Error(`Unsupported translation value: ${path}`);
  }
  return output;
}
const dictionaries = sources.map(readDictionary);
const english = Object.assign({}, ...dictionaries);
const owner = Object.assign({}, ...dictionaries.map((dictionary, index) => Object.fromEntries(Object.keys(dictionary).map(key => [key, sources[index].split('/').at(-1).replace('.ts', '')]))));
const zh = flatten(require('bk-magic-vue/lib/locale/lang/zh-CN').default);
const en = flatten(require('bk-magic-vue/lib/locale/lang/en-US').default);
for (const [key, value] of Object.entries(english)) { zh[key] = key; en[key] = value; }
for (const key of new Set([...Object.keys(zh), ...Object.keys(en)])) {
  zh[key] ??= key;
  en[key] ??= zh[key];
}
const output = resolve(root, 'src/platform/i18n/messages');
mkdirSync(output, {recursive: true});
const keyFile = resolve(root, 'src/platform/i18n/legacy-message-keys.json');
const previous = existsSync(keyFile) ? JSON.parse(readFileSync(keyFile, 'utf8')) : {};
const keys = {};
const ids = new Set();
for (const key of Object.keys(zh)) {
  const phrase = key.startsWith('bk.') ? key : en[key];
  const slug = phrase.toLowerCase().replace(/\{[^}]*\}/g, '').replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 48).replace(/_$/, '') || 'message';
  const id = previous[key] ?? `${owner[key] ?? 'control'}_${slug}_${createHash('sha256').update(key).digest('hex').slice(0, 12)}`;
  if (ids.has(id)) throw new Error(`Duplicate canonical message ID: ${id}`);
  ids.add(id); keys[key] = id;
}
writeFileSync(keyFile, JSON.stringify(keys, null, 2) + '\n');
for (const [locale, messages] of Object.entries({'zh-cn': zh, en})) {
  const canonical = Object.fromEntries(Object.entries(messages).map(([key, value]) => [keys[key], value]));
  writeFileSync(resolve(output, `${locale}.json`), JSON.stringify(canonical, null, 2) + '\n');
}

const provenance = { schemaVersion: 1, migration: 'vue-i18n-to-paraglide', locales: ['zh-cn', 'en'],
  policy: 'Stable canonical IDs avoid compiler identifier collisions. Original keys remain in legacy-message-keys.json. Preserve translations and interpolation names; no generated translations.',
  ownMessages: Object.keys(english).length, messages: { 'zh-cn': Object.keys(zh).length, en: Object.keys(en).length },
  sources: sources.map(file => ({ file, sha256: createHash('sha256').update(readFileSync(sourcePath(file))).digest('hex') })),
  vendor: { package: 'bk-magic-vue', version: require('bk-magic-vue/package.json').version, dictionaries: ['lib/locale/lang/zh-CN.js', 'lib/locale/lang/en-US.js'] },
};
writeFileSync(resolve(root, 'ai-native/paraglide-catalog-origin.json'), JSON.stringify(provenance, null, 2) + '\n');
console.log(JSON.stringify({ownMessages: provenance.ownMessages, messages: provenance.messages}, null, 2));
