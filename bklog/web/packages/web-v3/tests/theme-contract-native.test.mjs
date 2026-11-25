import test from 'node:test';
import assert from 'node:assert/strict';
import { compile } from 'sass';
import postcss from 'postcss';
import { readFileSync } from 'node:fs';

const css = compile('src/shared/styles/theme/tdesign-bklog.scss').css;
const root = postcss.parse(css);
test('semantic TDesign mapping resolves every business token and retains critical control contracts', () => {
  const declarations = new Map();
  root.walkDecls(decl => { if (decl.prop.startsWith('--bklog-')) declarations.set(decl.prop, decl.value); });
  root.walkDecls(decl => {
    for (const [,token] of decl.value.matchAll(/var\((--bklog-[\w-]+)/g)) assert.ok(declarations.has(token), `undefined semantic token ${token}`);
  });
  assert.equal(declarations.get('--bklog-brand-primary'), '#3974ff');
  assert.equal(declarations.get('--bklog-control-size-small'), '26px');
  assert.equal(declarations.get('--bklog-control-size-medium'), '32px');
  assert.equal(declarations.get('--bklog-control-size-large'), '38px');
  assert.equal(declarations.get('--bklog-space-8'), '8px');
  assert.equal(declarations.get('--bklog-border-width'), '1px');
  assert.equal(declarations.get('--bklog-radius-none'), '0');
  const selectorFor = prop => {
    const found = [];
    root.walkDecls(decl => { if (decl.prop === prop) found.push(decl.parent.selector); });
    return found;
  };
  assert.deepEqual(selectorFor('--bklog-space-8'), [':root']);
  assert.deepEqual(selectorFor('--bklog-brand-primary'), [':root:not([theme-mode=dark])']);
  assert.doesNotMatch(css, /t-button--size-medium/);
  assert.match(css, /:where\(\.t-button:not\(\.t-size-s\):not\(\.t-size-l\)\)/);
  assert.match(css, /--td-comp-size-xs: var\(--bklog-control-size-small\)/);
  assert.match(css, /--td-comp-size-xl: var\(--bklog-standard-control-size-large\)/);
  assert.equal(declarations.get('--bklog-standard-control-size-large'), '40px');
  assert.equal(declarations.get('--bklog-standard-control-radius'), '4px');
});
test('theme entry compiles form profiles without pulling business layouts into global controls', () => {
  const rules = [];
  root.walkRules(rule => { if (rule.selector.includes('bklog-form--drawer')) rules.push(rule); });
  assert.ok(rules.length >= 5);
  assert.ok(rules.some(rule => rule.selector.includes('.t-form.bklog-form--drawer-stack .t-form__item:last-child')));
  assert.ok(rules.some(rule => rule.nodes.some(node => node.prop === '--bklog-form-item-adjacent' && node.value === 'var(--bklog-space-8)')));
  assert.doesNotMatch(css, /repository-card|source-item|debug-result-table/);
  assert.doesNotThrow(() => compile('src/shared/styles/theme/compat-drawer.scss'));
  assert.doesNotThrow(() => compile('src/shared/styles/theme/management-lists.scss'));
  for (const entry of ['src/app/bootstrap/start.js','src/app/entries/monitor-bootstrap.ts']) {
    assert.match(readFileSync(entry,'utf8'), /tdesign-bklog.scss/);
  }
});
