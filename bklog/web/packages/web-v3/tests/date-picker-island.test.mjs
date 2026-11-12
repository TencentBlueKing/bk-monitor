import { test } from 'node:test';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { auditThirdPartyBoundary } from '../tools/third-party-boundary-audit.mjs';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import * as Vue from 'vue';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const { bundleDatePicker } = loadTypeScript(new URL('../tools/date-picker-island.ts', import.meta.url));
const root = fileURLToPath(new URL('..', import.meta.url));

test('official DatePicker and every SDK dependency bundle against native Vue3 only', async () => {
  const result = await bundleDatePicker(root);
  assert.ok(result.inputs.some((path) => path.includes('@blueking/date-picker/vue3/')));
  assert.ok(result.inputs.some((path) => path.includes('@vue/runtime-dom')));
  assert.ok(result.inputs.some((path) => path.includes('tdesign-vue-next')));
  assert.ok(result.inputs.some((path) => path.includes('bkui-vue.ts')));
  assert.ok(!result.inputs.some((path) => path.includes('@vue/compat') || path.includes('vue-runtime.mjs')));
  assert.ok(result.code.includes('mountDatePicker'));
});

test('native bridge preserves values, clones range arrays, forwards events and unmounts the SDK', () => {
  let render;
  let mounted;
  let unmounted = 0;
  const { mountDatePicker } = loadTypeScript(
    new URL('../src/platform/sdk/date-picker/native-entry.ts', import.meta.url),
    {
      vue: {
        ...Vue,
        createApp: (root) => ({
          mount(host) {
            mounted = host;
            render = root.setup();
          },
          unmount() {
            unmounted++;
          },
        }),
      },
      '@blueking/date-picker': { name: 'OfficialDatePicker' },
    },
  );
  const initial = {
    modelValue: ['now-15m', 'now'],
    behavior: 'simplicity',
    needTimezone: true,
    timezone: 'Asia/Shanghai',
    format: 'YYYY-MM-DD HH:mm:ss',
  };
  const values = [];
  const formats = [];
  const timezones = [];
  const host = {};
  const handle = mountDatePicker(host, initial, {
    value: (v) => values.push(v),
    format: (v) => formats.push(v),
    timezone: (v) => timezones.push(v),
  });
  assert.equal(mounted, host);
  let vnode = render();
  assert.deepEqual(vnode.props.modelValue, initial.modelValue);
  assert.notEqual(vnode.props.modelValue, initial.modelValue);
  assert.equal(vnode.props.enableFormatClick, true);
  vnode.props['onUpdate:modelValue']([1000, 2000]);
  vnode.props['onUpdate:format']('x');
  vnode.props['onUpdate:timezone']('UTC');
  assert.deepEqual(values, [[1000, 2000]]);
  assert.deepEqual(formats, ['x']);
  assert.deepEqual(timezones, ['UTC']);
  const next = { ...initial, modelValue: ['now-30m', 'now'], timezone: 'UTC' };
  handle.update(next);
  vnode = render();
  assert.deepEqual(vnode.props.modelValue, next.modelValue);
  assert.notEqual(vnode.props.modelValue, next.modelValue);
  assert.equal(vnode.props.timezone, 'UTC');
  let opened = 0,
    closed = 0;
  vnode.props.ref.value = {
    handleShowPanel() {
      opened++;
    },
    handleHidePanel() {
      closed++;
    },
  };
  handle.handleShowPanel();
  handle.handleHidePanel();
  handle.destroy();
  assert.equal(opened, 1);
  assert.equal(closed, 1);
  assert.equal(unmounted, 1);
});

const controls = Object.fromEntries(
  [
    'Button',
    'Checkbox',
    'Dialog',
    'DialogPlugin',
    'Empty',
    'Form',
    'FormItem',
    'Input',
    'Loading',
    'MessagePlugin',
    'Popconfirm',
    'Popup',
    'Select',
    'Option',
    'OptionGroup',
    'Tag',
    'Tabs',
    'TabPanel',
  ].map((name) => [name, { name: `Native${name}` }]),
);
const sdk = loadTypeScript(new URL('../src/platform/compat/tdesign/bkui-vue.ts', import.meta.url), {
  vue: Vue,
  'tdesign-vue-next': controls,
  'tippy.js': () => {},
});
test('SDK Tab descriptors become real TDesign panels and active events propagate', () => {
  const events = [];
  const render = sdk.Tab.setup(
    { active: 'date', type: 'unborder-card' },
    {
      attrs: {},
      emit: (...args) => events.push(args),
      slots: {
        default: () => [
          Vue.h(Vue.Fragment, null, [
            Vue.h(sdk.Tab.TabPanel, { name: 'date', label: '日期选择' }),
            Vue.h(sdk.Tab.TabPanel, { name: 'now-', label: '最近' }),
          ]),
        ],
      },
    },
  );
  const node = render();
  assert.equal(node.type, controls.Tabs);
  assert.equal(node.props.value, 'date');
  const panels = node.children.default();
  assert.equal(panels.length, 2);
  assert.ok(panels.every((panel) => panel.type === controls.TabPanel));
  assert.deepEqual(
    panels.map((panel) => panel.props.value),
    ['date', 'now-'],
  );
  node.props.onChange('now-');
  assert.deepEqual(events, [['update:active', 'now-']]);
});
test('SDK Select maps id/name and controls popup closing without dropping model events', () => {
  let exposed;
  const selected = [];
  const render = sdk.Select.setup(
    { popoverOptions: { extCls: 'sdk-popup' }, popoverMinWidth: 130, prefix: '基于' },
    {
      attrs: { modelValue: 'now', 'onUpdate:modelValue': (value) => selected.push(value) },
      slots: { default: () => [Vue.h(Vue.Fragment, null, [Vue.h(sdk.Select.Option, { id: 'now', name: '此刻' })])] },
      expose: (value) => {
        exposed = value;
      },
    },
  );
  let node = render();
  const option = node.children.default()[0];
  assert.equal(option.type, controls.Option);
  assert.equal(option.props.value, 'now');
  assert.equal(option.props.label, '此刻');
  assert.equal(node.props.popupProps.zIndex, undefined, 'SDK popup layers are assigned by the shared overlay runtime');
  assert.equal(node.props.popupProps.overlayClassName, 'sdk-popup');
  assert.deepEqual(node.props.popupProps.overlayInnerStyle, {minWidth: '130px'});
  node.props['onUpdate:modelValue']('hour');
  assert.deepEqual(selected, ['hour']);
  node.props.onPopupVisibleChange(true);
  assert.equal(render().props.popupVisible, true);
  exposed.hidePopover();
  assert.equal(render().props.popupVisible, false);
});
test('timezone groups retain options, searchable country metadata and toggle events', () => {
  const toggles = [];
  let exposed;
  const render = sdk.Select.setup(
    { popoverOptions: { 'ext-cls': 'timezone-popup' }, filterOption: (word, option) => option.country === word },
    {
      attrs: { onToggle: (open) => toggles.push(open) },
      expose: (value) => {
        exposed = value;
      },
      slots: {
        default: () => [
          Vue.h(Vue.Fragment, null, [
            [Vue.h(sdk.Select.Option, { id: 'browser', name: '浏览器时区' })],
            Vue.h(
              sdk.Select.Group,
              { label: '亚洲' },
              {
                default: () => [
                  Vue.h(sdk.Select.Option, { id: 'Asia/Shanghai', name: 'Asia/Shanghai', country: 'China' }),
                ],
              },
            ),
          ]),
        ],
      },
    },
  );
  const node = render();
  const options = node.children.default();
  assert.equal(options.length, 2);
  assert.equal(options[0].props.value, 'browser');
  assert.equal(options[1].type, controls.OptionGroup);
  const grouped = options[1].children.default();
  assert.equal(grouped[0].props.value, 'Asia/Shanghai');
  assert.equal(node.props.filter('China', { value: 'Asia/Shanghai' }), true);
  assert.equal(node.props.filter('Japan', { value: 'Asia/Shanghai' }), false);
  assert.equal(node.props.popupProps.overlayClassName, 'timezone-popup');
  node.props.onPopupVisibleChange(true);
  node.props.onPopupVisibleChange(false);
  assert.deepEqual(toggles, [true, false]);
});
test('nested date-picker unit popups join the SDK keep-open boundary only inside its panel', () => {
  const render = sdk.Select.setup({}, { attrs: {}, slots: {}, expose() {} });
  let node = render();
  assert.equal(node.props.popupProps.overlayClassName, undefined);
  node.props.ref.value = {
    $el: { closest: (selector) => (selector.includes('__bk-date-picker-popper__') ? {} : null) },
  };
  node.props.onPopupVisibleChange(true);
  node = render();
  assert.equal(node.props.popupProps.overlayClassName, '__bk-date-picker-popper__');
});
test('SDK relative input preserves its prefix and model update contract', () => {
  const values = [];
  let exposed;
  const render = sdk.Input.setup(
    { prefix: '的最近' },
    {
      attrs: { modelValue: 15, type: 'number', 'onUpdate:modelValue': (value) => values.push(value) },
      slots: {},
      expose(value) {
        exposed = value;
      },
    },
  );
  const input = render();
  assert.equal(input.type, controls.Input);
  assert.equal(input.children.prefixIcon().children, '的最近');
  input.props['onUpdate:modelValue']('20');
  assert.deepEqual(values, ['20']);
  let focused = 0;
  input.props.ref.value = {
    focus() {
      focused++;
    },
    blur() {
      focused--;
    },
  };
  exposed.focus();
  assert.equal(focused, 1);
  exposed.blur();
  assert.equal(focused, 0);
});

test('boundary permits the single native DatePicker entry without allowing business or Vue2 imports', () => {
  const root = mkdtempSync(resolve(tmpdir(), 'bklog-date-boundary-'));
  try {
    mkdirSync(resolve(root, 'platform/sdk/date-picker'), { recursive: true });
    writeFileSync(
      resolve(root, 'platform/sdk/date-picker/native-entry.ts'),
      "import DatePicker from '@blueking/date-picker';",
    );
    assert.equal(auditThirdPartyBoundary(root).counts.violations, 0);
    writeFileSync(
      resolve(root, 'platform/sdk/date-picker/native-entry.ts'),
      "import DatePicker from '@blueking/date-picker/vue2';",
    );
    writeFileSync(resolve(root, 'business.ts'), "import DatePicker from '@blueking/date-picker';");
    assert.equal(auditThirdPartyBoundary(root).counts.violations, 2);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
