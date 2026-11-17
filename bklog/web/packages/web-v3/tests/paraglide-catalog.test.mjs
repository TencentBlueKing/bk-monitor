/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as Vue from 'vue';
import { m } from '#paraglide/messages.js';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
const keys = read('../src/platform/i18n/legacy-message-keys.json');
const catalogs = Object.fromEntries(['zh-cn', 'en'].map(locale => [locale, read(`../src/platform/i18n/messages/${locale}.json`)]));
const { createTranslator } = loadTypeScript(new URL('../src/platform/i18n/translator.ts', import.meta.url), {vue: Vue});
test('shared message IDs accept only punctuation aliases and load every generated function in both locales', () => {
  const canonicalKeys = new Map();
  for (const [key, id] of Object.entries(keys)) {
    const canonical = key.replace(/。$/, '');
    if (canonicalKeys.has(id)) assert.equal(canonicalKeys.get(id), canonical, `unexpected collision: ${key}`);
    else canonicalKeys.set(id, canonical);
  }
  assert.equal(Object.keys(m).length, canonicalKeys.size);
  for (const [key, id] of Object.entries(keys)) {
    assert.equal(typeof m[id], 'function', key);
    for (const locale of ['zh-cn', 'en']) assert.equal(typeof catalogs[locale][id], 'string', `${locale}:${key}`);
  }
});

test('compiled Paraglide preserves the full source catalog text and list/named interpolation', () => {
  const failures = [];
  let checked = 0;
  for (const locale of ['zh-cn', 'en']) {
    const t = createTranslator(key => m[keys[key] ?? key], () => locale);
    for (const [key, id] of Object.entries(keys)) {
      const source = catalogs[locale][id];
      const names = [...source.matchAll(/\{([\w$]+)\}/g)].map(match => match[1]);
      const inputs = value => names.every(name => /^\d+$/.test(name)) ? Array.from({length: Math.max(-1, ...names.map(Number)) + 1}, () => value) : Object.fromEntries(names.filter(name => !/^\d+$/.test(name)).map(name => [name, value]));
      const fixtures = [undefined, inputs('fixture'), inputs(12)];
      for (const values of fixtures) {
        const expected = source.replace(/\{(?:'([^']*)'|([\w$]+))\}/g, (_, literal, name) => literal ?? String(values?.[name] ?? ''));
        const actual = t(key, values);
        if (actual !== expected && failures.length < 15) failures.push({locale, key, expected, actual});
        checked++;
      }
    }
  }
  assert.deepEqual(failures, []);
  assert.ok(checked > 16000);
});

test('legacy interpolation preserves zero, false, null, structured values and untranslated fallback', () => {
  const key = '总共 {0} 条';
  const t = createTranslator(() => undefined, () => 'zh-cn');
  for (const [value, expected] of [[0, '0'], [false, 'false'], [null, ''], [undefined, ''], [{a:1}, Vue.toDisplayString({a:1})], [[1,2], Vue.toDisplayString([1,2])]]) assert.equal(t(key, [value]), `总共 ${expected} 条`);
  assert.equal(t(key, {0: 12}), '总共 12 条');
  assert.equal(t('unknown {name}', {name:'fixture'}), 'unknown fixture');
  assert.equal(t('unknown', 'fallback text'), 'fallback text');
});

test('V3 package installation excludes the old translation engine, including SDK transitive declarations', async () => {
  const { createRequire } = await import('node:module');
  const { hooks } = createRequire(import.meta.url)('../.pnpmfile.cjs');
  const manifest = read('../package.json');
  for (const field of ['dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies']) {
    assert.equal(manifest[field]?.['vue-i18n'], undefined);
    const filtered = hooks.readPackage({ name: 'synthetic-sdk', [field]: { 'vue-i18n': '8.0.0', vue: '3.0.0' } });
    assert.equal(filtered[field]['vue-i18n'], undefined);
    assert.equal(filtered[field].vue, '3.0.0');
  }
  assert.doesNotMatch(readFileSync(new URL('../pnpm-lock.yaml', import.meta.url), 'utf8'), /vue-i18n|@intlify\//);
});
