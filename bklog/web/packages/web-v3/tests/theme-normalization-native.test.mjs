import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeStyle, styleDeclarations, resolveSemanticVariables } from '../tools/tdesign-style-source.mjs';
import { loadTypeScript } from './helpers/load-typescript.mjs';

test('normalization preserves comments, pseudo states, variables, functions, and business geometry', () => {
  const input = `.business { color: #63656e; .t-input { /* retain */ color: #63656e; width: 320px; &:hover { border: 1px solid #c4c6cc !important; } background: var(--existing, #fff); box-shadow: 0 0 0 rgba(0,0,0,.2); } }`;
  const { output, count } = normalizeStyle(input);
  assert.equal(count, 2);
  assert.match(output, /\.business \{ color: #63656e/);
  assert.match(output, /\/\* retain \*\/ color: var\(--bklog-text-secondary, #63656e\)/);
  assert.match(output, /width: 320px/);
  assert.match(output, /border: 1px solid var\(--bklog-border-control, #c4c6cc\) !important/);
  assert.match(output, /background: var\(--existing, #fff\)/);
  assert.match(output, /box-shadow: 0 0 0 rgba\(0,0,0,.2\)/);
  assert.equal(normalizeStyle(output).count, 0);
});
test('nested interpolation and strings never become rewrite targets', () => {
  const input = `.business-#{$suffix} { .t-button { content: '#fff; }'; color: #fff; } .business { color: #fff; } }`;
  assert.equal(normalizeStyle(input).count, 1);
  assert.match(normalizeStyle(input).output, /content: '#fff; }'/);
  const declarations = styleDeclarations(input);
  assert.equal(new Set(declarations.map(d => d.block)).size, 1);
});
test('shared configuration preserves locale, explicit defaults and independent nested objects', () => {
  const { createApplicationControlConfig } = loadTypeScript(new URL('../src/platform/ui/tdesign-config.ts', import.meta.url), {});
  const locale = Object.freeze({ form: Object.freeze({ requiredMarkPosition: 'right' }), drawer: Object.freeze({ cancel: 'Synthetic cancel' }), table: Object.freeze({ empty: 'Synthetic empty' }) });
  const a = createApplicationControlConfig(locale), b = createApplicationControlConfig(locale);
  assert.equal(a.form.requiredMarkPosition, 'right');
  assert.equal(a.drawer.cancel, 'Synthetic cancel');
  assert.equal(a.table.empty, 'Synthetic empty');
  assert.equal(a.table.size, 'medium');
  a.drawer.closeOnOverlayClick = false;
  assert.equal(b.drawer.closeOnOverlayClick, true);
  assert.equal(locale.drawer.closeOnOverlayClick, undefined);
});

test('semantic equivalence resolves nested CSS functions without rewriting quoted strings', () => {
  const value = 'var(--bklog-shadow-small, 0 2px rgba(0, 0, 0, .1))';
  assert.equal(resolveSemanticVariables(value, (_token, fallback) => fallback), '0 2px rgba(0, 0, 0, .1)');
  assert.equal(resolveSemanticVariables('"var(--bklog-surface)"', () => 'white'), '"var(--bklog-surface)"');
  assert.equal(resolveSemanticVariables('var(--host-color, red)', () => 'white'), 'var(--host-color, red)');
});

test('locale provider retains config identity until the locale changes', () => {
  let locale = 'zh-cn';
  const { default: provider } = loadTypeScript(new URL('../src/platform/i18n/locale-provider.ts', import.meta.url), {
    vue: { defineComponent: value => value, h: (_component, props) => props },
    'tdesign-vue-next': { ConfigProvider: {} },
    'tdesign-vue-next/es/locale/en_US': { input: { placeholder: 'Synthetic' } },
    'tdesign-vue-next/es/locale/zh_CN': { input: { placeholder: 'Synthetic Chinese' } },
    './i18n': { getLocale: () => locale },
    '../ui/tdesign-config': { createApplicationControlConfig: value => ({ ...value }) },
  });
  const render = provider.setup(null, { slots: {} });
  const first = render().globalConfig;
  assert.equal(render().globalConfig, first);
  locale = 'en';
  assert.notEqual(render().globalConfig, first);
  locale = 'zh-cn';
  assert.equal(render().globalConfig, first);
});

test('inline visual migration preserves dynamic bindings and unrelated elements', async () => {
  const { normalizeInlineControls } = await import('../tools/inline-control-styles.mjs');
  const source = `<template><t-input :style="{ color: '#fff', width: dynamicWidth }" /><div style="color:#fff" /></template>`;
  const result = normalizeInlineControls('synthetic.vue', source);
  assert.equal(result.count, 1);
  assert.match(result.output, /color: 'var\(--bklog-text-inverse, #fff\)'/);
  assert.match(result.output, /width: dynamicWidth/);
  assert.match(result.output, /<div style="color:#fff"/);
  const script = `import {Button} from 'tdesign-vue-next';const view = h(Button,{style:{fontSize:'14px',color:enabled?'red':'blue'}});`;
  const migrated = normalizeInlineControls('synthetic.ts', script);
  assert.equal(migrated.count, 1);
  assert.match(migrated.output, /color:enabled\?'red':'blue'/);
  assert.equal(normalizeInlineControls('synthetic.ts', migrated.output).count, 0);
});
