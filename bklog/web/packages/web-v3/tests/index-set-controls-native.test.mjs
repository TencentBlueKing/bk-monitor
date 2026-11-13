import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import * as Vue from 'vue';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const root = new URL('../src/features/retrieval/workbench/components/index-set-choice/', import.meta.url);
const native = Object.fromEntries(
  ['Checkbox', 'Input', 'Empty', 'Form', 'FormItem', 'Button', 'Loading'].map((name) => [name, { name }]),
);
const Popover = { name: 'Popover' },
  Tags = { name: 'Tags' };
const compiler = { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' };
const selection = loadTypeScript(new URL('use-index-set-list.tsx', root), { vue: Vue }).default;
const tagSync = loadTypeScript(new URL('tag-search-sync.ts', root));
function all(node) {
  if (!node) return [];
  if (Array.isArray(node)) return node.flatMap(all);
  if (typeof node !== 'object') return [];
  return [node, ...all(node.children)];
}
const find = (node, type) => all(node).find((x) => x.type === type);
const byClass = (node, name) =>
  all(node).filter((x) =>
    String(x.props?.class ?? '')
      .split(/\s+/)
      .includes(name),
  );
const text = (node) =>
  typeof node === 'string'
    ? node
    : Array.isArray(node)
      ? node.map(text).join('')
      : node && typeof node === 'object'
        ? text(node.children)
        : '';
const mouse = () => ({
  stopped: false,
  stopPropagation() {
    this.stopped = true;
  },
});
function node(id, name, extra = {}) {
  return { unique_id: id, index_set_id: id, index_set_name: name, tags: [], permission: { SEARCH: true }, ...extra };
}
function setup(props) {
  const previous = globalThis.window;
  globalThis.window = { __IS_MONITOR_COMPONENT__: false };
  const calls = [],
    timers = [],
    scope = Vue.effectScope();
  function debounce(fn) {
    let args;
    const queued = (...value) => (args = value);
    queued.cancel = () => {
      args = undefined;
    };
    queued.flush = () => {
      if (args) {
        const current = args;
        args = undefined;
        fn(...current);
      }
    };
    timers.push(queued);
    return queued;
  }
  const component = loadTypeScript(
    new URL('index-set-list.tsx', root),
    {
      vue: Vue,
      'tdesign-vue-next': native,
      '@/shared/utils/typed-record': { includesValue: (list, value) => list.includes(value) },
      '@/shared/composables/use-locale': () => ({ $t: (x) => (x === 'bk.exception.searchEmpty' ? '搜索为空' : x) }),
      'lodash-es': { debounce },
      '../../../../../shared/lib/authority-map': { SEARCH_LOG_AUTH: 'SEARCH' },
      '../../../../../shared/ui/bklog-popover/index': Popover,
      './use-index-set-list': selection,
      './tag-search-sync': tagSync,
      './index-set-list.scss': {},
    },
    compiler,
  ).default;
  const state = Vue.reactive({
    list: [],
    type: 'single',
    value: [],
    textDir: 'ltr',
    spaceUid: 'bkcc__900001',
    ...props,
  });
  const render = scope.run(() => component.setup(state, { emit: (...args) => calls.push(args) }));
  return {
    render,
    state,
    calls,
    timers,
    stop() {
      scope.stop();
      if (previous === undefined) delete globalThis.window;
      else globalThis.window = previous;
    },
  };
}
test('index selector business controls use native input/form/empty/loading APIs', () => {
  for (const file of ['index-set-list.tsx', 'common-list.tsx'])
    assert.doesNotMatch(
      readFileSync(new URL(file, root), 'utf8'),
      /<\/?bk-(input|form|form-item|exception)\b|v-bkloading|\.validator\./,
    );
});
test('search has immediate draft, delayed filtering and immediate clear without stale results', () => {
  const c = setup({ list: [node('900101', 'Demo'), node('900105', 'Other')] });
  try {
    const input = find(c.render(), native.Input);
    input.props.onChange('Other');
    assert.equal(find(c.render(), native.Input).props.value, 'Other');
    assert.equal(byClass(c.render(), 'index-set-item').length, 2);
    c.timers[0].flush();
    assert.equal(byClass(c.render(), 'index-set-item').length, 1);
    assert.ok(text(byClass(c.render(), 'index-set-item')[0]).includes('Other'));
    find(c.render(), native.Input).props.onChange('missing');
    find(c.render(), native.Input).props.onChange('');
    c.timers[0].flush();
    assert.equal(byClass(c.render(), 'index-set-item').length, 2);
  } finally {
    c.stop();
  }
});
test('no-data visibility and empty search keep source filtering behavior', () => {
  const c = setup({
    list: [node('a', 'With data'), node('b', 'Empty', { tags: [{ tag_id: 4, name: '无数据', color: '' }] })],
  });
  try {
    assert.equal(byClass(c.render(), 'index-set-item').length, 1);
    find(c.render(), native.Checkbox).props.onChange(false);
    assert.equal(byClass(c.render(), 'index-set-item').length, 2);
    find(c.render(), native.Input).props.onChange('missing');
    c.timers[0].flush();
    assert.equal(find(c.render(), native.Empty).props.title, '搜索为空');
  } finally {
    c.stop();
  }
});
test('permission veto and authorization event remain separate from selection', () => {
  const c = setup({ list: [node('denied', 'Denied', { permission: { SEARCH: false } })] });
  try {
    const row = byClass(c.render(), 'index-set-item')[0];
    row.props.onClick(mouse());
    assert.equal(c.calls.length, 0);
    byClass(row, 'index-set-tag-item')[0].props.onClick(mouse());
    assert.equal(c.calls[0][0], 'auth-request');
    assert.equal(c.calls[0][1].unique_id, 'denied');
  } finally {
    c.stop();
  }
});
test('single selection retains unique IDs and complete item metadata', () => {
  const c = setup({ list: [node('#_900101', 'Demo', { collector_config_id: 99 })] });
  try {
    byClass(c.render(), 'index-set-item')[0].props.onClick(mouse());
    assert.deepEqual(c.calls, [['value-change', ['#_900101']]]);
    byClass(c.render(), 'favorite-icon')[0].props.onClick(mouse());
    assert.equal(c.calls[1][0], 'favorite-change');
    assert.equal(c.calls[1][1].collector_config_id, 99);
    assert.equal(c.calls[1][1].index_set_type, 'single');
  } finally {
    c.stop();
  }
});
test('union footer removal restores children preserved by the source grouped-selection contract', () => {
  const child = node('child', 'Child'),
    other = node('other', 'Other'),
    group = node('group', 'Group', { children: [child, other], is_group: true });
  const c = setup({ type: 'union', list: [group], value: [child] });
  try {
    byClass(c.render(), 'index-set-item')[0].props.onClick(mouse());
    assert.deepEqual(c.calls.at(-1), ['value-change', ['group']]);
    c.state.value = [group];
    byClass(byClass(c.render(), 'row-value-item')[0], 'bklog-close')[0].props.onClick(mouse());
    assert.deepEqual(c.calls.at(-1), ['value-change', ['child']]);
  } finally {
    c.stop();
  }
});
test('union favorite shows native validation, emits only after name and allows cancel', () => {
  const c = setup({ type: 'union', list: [node('a', 'Demo')], value: [] });
  try {
    const pop = find(c.render(), Popover);
    let hidden = 0;
    pop.ref.r.value = {
      hide() {
        hidden++;
      },
    };
    const form = () => pop.props['v-slots'].content();
    const buttons = () => all(form()).filter((n) => n.type === native.Button);
    buttons()[0].props.onClick(mouse());
    assert.equal(c.calls.length, 0);
    assert.equal(find(form(), native.FormItem).props.status, 'error');
    assert.equal(find(form(), native.FormItem).props.tips, '收藏名称不能为空');
    find(form(), native.Input).props.onChange('Owned combination');
    assert.equal(find(form(), native.FormItem).props.status, undefined);
    buttons()[0].props.onClick(mouse());
    assert.deepEqual(c.calls, [['favorite-change', 'Owned combination', true]]);
    assert.equal(hidden, 1);
    buttons()[1].props.onClick();
    assert.equal(hidden, 2);
  } finally {
    c.stop();
  }
});
test('history list keeps loading, source row events and item/all delete semantics', () => {
  const events = [],
    scope = Vue.effectScope();
  const component = loadTypeScript(
    new URL('common-list.tsx', root),
    {
      vue: Vue,
      'tdesign-vue-next': native,
      '@/shared/composables/use-locale': () => ({ $t: (x) => (x === 'bk.exception.searchEmpty' ? '搜索为空' : x) }),
      '../../../../../shared/ui/ellipsis-tag-list/index': Tags,
      './common-list.scss': {},
    },
    compiler,
  ).default;
  const props = Vue.reactive({
    list: [],
    isLoading: true,
    type: 'history',
    idField: 'id',
    nameField: 'name',
    itemIcon: {},
    showDelItem: true,
    value: 7,
  });
  try {
    const render = scope.run(() => component.setup(props, { emit: (...args) => events.push(args) }));
    assert.equal(render().type.name, 'SkeletonLoading');
    assert.equal(render().props.loading, true);
    assert.equal(find(render(), native.Empty), undefined);
    props.isLoading = false;
    assert.equal(find(render(), native.Empty).props.title, '暂无数据');
    const record = { id: 7, name: 'Saved', addition: [{ field: 'host', value: ['a'] }], search_mode: 'ui' };
    props.list = [record];
    byClass(render(), 'common-row')[0].props.onClick();
    assert.deepEqual(events[0], ['value-click', record]);
    const event = mouse();
    byClass(render(), 'bklog-log-delete')[0].props.onClick(event);
    assert.equal(event.stopped, true);
    assert.deepEqual(events[1], ['delete', record]);
    byClass(render(), 'bklog-saoba')[0].props.onClick(mouse());
    assert.deepEqual(events[2], ['delete', null]);
  } finally {
    scope.stop();
  }
});

test('native search empty title preserves both frozen V2 locale strings', () => {
  const keys = JSON.parse(
    readFileSync(new URL('../src/platform/i18n/legacy-message-keys.json', import.meta.url), 'utf8'),
  );
  const zh = JSON.parse(readFileSync(new URL('../src/platform/i18n/messages/zh-cn.json', import.meta.url), 'utf8'));
  const en = JSON.parse(readFileSync(new URL('../src/platform/i18n/messages/en.json', import.meta.url), 'utf8'));
  const id = keys['bk.exception.searchEmpty'];
  assert.equal(zh[id], '搜索为空');
  assert.equal(en[id], 'Search Is Empty');
  assert.match(
    readFileSync(new URL('index-set-list.tsx', root), 'utf8'),
    /title=\{type === 'search-empty' \? \$t\('bk.exception.searchEmpty'\)/,
  );
});
