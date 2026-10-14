const assert = require('node:assert/strict');
const fs = require('node:fs');
const { createRequire } = require('node:module');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const bridgePath = 'src/trace/components/monitor-ip-selector/vue3.x.js';
const collectionPath = 'src/trace/pages/profiling-explore/components/collection/collection-host-selector.tsx';
const bundle = fs.readFileSync(path.join(root, 'src/trace/node_modules/@blueking/ip-selector/dist/vue2.6.x.esm.js'), 'utf8');

function loadSource(file, dependencies) {
  const source = fs.readFileSync(path.join(root, file), 'utf8');
  const { outputText } = ts.transpileModule(source, {
    fileName: file,
    compilerOptions: {
      module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React,
      experimentalDecorators: true, useDefineForClassFields: false,
    },
  });
  const module = { exports: {} };
  new Function('require', 'module', 'exports', outputText)(dependencies, module, module.exports);
  return module.exports.default;
}

// Run the installed package's manager without loading its DOM-dependent UI bundle.
function loadManagerModule(marker, dependencies, errors = []) {
  const position = bundle.indexOf(marker);
  assert.notEqual(position, -1, `Missing package module: ${marker}`);
  const start = bundle.lastIndexOf('/***/ (', position);
  const end = bundle.indexOf('\n/***/ })', position);
  const source = bundle.slice(start + '/***/ ('.length, end + '\n/***/ }'.length).replace(/\n\/\*\*\*\/ }$/, '}');
  const ids = new Map();
  for (const match of source.matchAll(/var (_\w+) = (?:_interopRequireDefault\()?__webpack_require__\((\d+)\)/g)) {
    ids.set(Number(match[2]), match[1]);
  }
  const exports = {};
  new Function('console', `return (${source});`)({ error: message => errors.push(message) })(
    {}, exports, id => {
      const name = ids.get(id);
      if (!name) return {};
      assert.ok(name in dependencies, `Missing dependency ${name}`);
      return dependencies[name];
    }
  );
  return exports;
}

function managerHarness() {
  const errors = [];
  const dependencies = {
    _interopRequireDefault: value => ({ default: value }),
    _flattenDeep2: values => values.flat(Infinity),
    _isFunction2: value => typeof value === 'function',
    _has2: (value, key) => Object.hasOwn(value, key),
    _uniq2: values => [...new Set(values)],
    _useI18n2: () => ({ t: value => value }),
  };
  const manager = loadManagerModule('var merge = exports.merge', dependencies, errors);
  const localManager = context => loadManagerModule('nameStyle: _manager.default.nameStyle', {
    ...dependencies,
    _manager: manager.default,
    _useIpSelector: () => context,
  }).default();
  return { ...manager, errors, localManager };
}

function bridgeHarness() {
  const hooks = {};
  const events = [];
  const component = {
    props: { mode: { default: 'dialog' }, value: {}, originalValue: {}, config: {}, service: {}, showDialog: {} },
    emits: ['change', 'close-dialog', 'panel-change', 'output-field-change'],
  };
  class Vue2 {
    constructor(options) {
      this.options = options;
      this.handlers = {};
      this.$refs = { componentRef: {
        $on: (name, listener) => { this.handlers[name] = listener; },
        $forceUpdate() {},
      } };
      this.$el = {};
    }
    $mount() { this.$forceUpdate(); }
    $forceUpdate() {
      this.options.render((_component, { props, on }) => {
        Object.assign(this.$refs.componentRef, props);
        Object.assign(this.handlers, on);
      });
    }
    $destroy() { this.destroyed = true; }
  }
  const create = loadSource(bridgePath, id => {
    if (id === 'vue') return {
      h() {},
      ref: () => ({}),
      shallowRef: () => ({}),
      onMounted: callback => { hooks.mount = callback; },
      onUpdated: callback => { hooks.update = callback; },
      onBeforeUnmount: callback => { hooks.unmount = callback; },
    };
    assert.equal(id, '@blueking/ip-selector/dist/vue2.6.x.esm');
    return { Component: component, merge() {}, Vue2 };
  });
  const bridge = create({ version: '4', serviceConfigError: false });
  const props = {
    value: { host_list: [{ host_id: 1 }] }, originalValue: {},
    config: { panelList: ['staticTopo'] }, service: { fetchHostCheck: () => 1 }, showDialog: false,
  };
  const state = bridge.setup(props, { emit: (...args) => events.push(args) });
  const children = [];
  state.rootRef.value = {
    appendChild: element => {
      children.push(element);
      element.parentNode = { removeChild: child => children.splice(children.indexOf(child), 1) };
    },
  };
  hooks.mount();
  return { hooks, props, state, events, component, bridge, children };
}

test('Profiling factory does not validate instance services before they are provided', () => {
  const manager = managerHarness();
  loadSource(collectionPath, id => {
    if (id === 'vue') return { defineComponent: options => options };
    if (id.endsWith('.css')) return {};
    assert.equal(id, '../../../../components/monitor-ip-selector/vue3.x');
    return { default: options => { manager.merge(options); return {}; } };
  });
  assert.deepEqual(manager.errors, []);
});

test('installed selector reports exactly the eight missing factory services', () => {
  const manager = managerHarness();
  manager.merge({ version: '4', serviceConfigError: true });
  assert.deepEqual(manager.errors.map(message => message.match(/\*(.+)\*/)[1]), [
    'fetchCustomSettings', 'updateCustomSettings', 'fetchConfig', 'fetchTopologyHostCount',
    'fetchTopologyHostsNodes', 'fetchTopologyHostIdsNodes', 'fetchHostsDetails', 'fetchHostCheck',
  ]);
});

test('instance services remain isolated and explicit false config overrides package defaults', () => {
  const manager = managerHarness();
  manager.merge({ version: '4', serviceConfigError: false });
  const first = { service: { fetchHostCheck: () => 'first' }, config: { warningSelectAllBusinesses: false } };
  const second = { service: { fetchHostCheck: () => 'second' }, config: {} };
  const a = manager.localManager(first);
  const b = manager.localManager(second);
  assert.equal(a.service.fetchHostCheck(), 'first');
  assert.equal(b.service.fetchHostCheck(), 'second');
  assert.equal(a.config.warningSelectAllBusinesses, false);
  assert.equal(b.config.warningSelectAllBusinesses, true);
  first.service = { fetchHostCheck: () => 'replaced' };
  assert.equal(a.service.fetchHostCheck(), 'replaced');
  assert.equal(b.service.fetchHostCheck(), 'second');
  assert.throws(() => a.service.fetchConfig, /fetchConfig/);
});

test('bridge forwards replacement values, config, services and dialog state', () => {
  const { hooks, props, state } = bridgeHarness();
  Object.assign(props, {
    value: { host_list: [{ host_id: 2 }] }, originalValue: { host_list: [{ host_id: 1 }] },
    config: { panelList: ['manualInput'] }, service: { fetchHostCheck: () => 2 }, showDialog: true,
  });
  hooks.update();
  for (const key of Object.keys(props)) assert.equal(state.app.$refs.componentRef[key], props[key], key);
});

test('bridge preserves events and destroys its Vue2 instance on unmount', () => {
  const { hooks, state, events, component, children } = bridgeHarness();
  for (const name of component.emits) state.app.handlers[name]('payload');
  assert.deepEqual(events, component.emits.map(name => [name, 'payload']));
  hooks.unmount();
  assert.equal(state.app.destroyed, true);
  assert.equal(children.length, 0);
});

test('bridge section default does not mutate the package component default', () => {
  const { bridge, component } = bridgeHarness();
  assert.equal(bridge.props.mode.default, 'section');
  assert.equal(component.props.mode.default, 'dialog');
});

test('Vue2 retains all existing panel services and request scope after upgrading', async () => {
  const pcRequire = createRequire(path.join(root, 'src/monitor-pc/package.json'));
  const manager = managerHarness();
  const calls = [];
  const api = new Proxy({}, { get: (_target, name) => params => {
    calls.push({ name, params });
    return Promise.resolve(name === 'queryHostIdInfosIpChooserTopo' ? { data: [{ host_id: 1, cloud_id: 0 }] } : []);
  } });
  const Wrapper = loadSource('src/monitor-pc/components/monitor-ip-selector/monitor-ip-selector.tsx', id => {
    if (id.endsWith('.css') || id.endsWith('.scss')) return {};
    if (id === './utils') return {};
    if (id === 'monitor-api/modules/model') return api;
    if (id === '@blueking/ip-selector/dist/index.esm') return {
      default: options => { manager.merge(options); return {}; },
    };
    return pcRequire(id);
  });
  const panels = ['staticTopo', 'dynamicTopo', 'dynamicGroup', 'serviceTemplate', 'setTemplate', 'serviceInstance', 'manualInput'];
  const instance = new Wrapper({
    beforeCreate() { this.$store = { getters: { bizId: 42 } }; },
    propsData: { panelList: panels },
  });
  manager.merge({ ...instance.ipSelectorServices, panelList: panels, serviceConfigError: true });
  assert.deepEqual(manager.errors, []);
  assert.equal(instance.ipSelectorConfig.warningSelectAllBusinesses, false);
  await instance.ipSelectorServices.fetchTopologyHostsNodes({ search_content: '', start: 0, page_size: 10 });
  assert.deepEqual(calls.pop(), {
    name: 'queryHostsIpChooserTopo',
    params: { scope_list: [{ scope_type: 'biz', scope_id: 42 }], start: 0, page_size: 10 },
  });
  const hosts = await instance.ipSelectorServices.fetchTopologyHostIdsNodes({ search_content: 'host-1' });
  assert.equal(calls.pop().params.search_content, 'host-1');
  assert.deepEqual(hosts.data[0].cloud_area, { id: 0 });
  await instance.ipSelectorServices.fetchHostCheck({ ip_list: ['192.0.2.1'] });
  assert.deepEqual(calls.pop(), {
    name: 'checkIpChooserHost',
    params: { scope_list: [{ scope_type: 'biz', scope_id: 42 }], ip_list: ['192.0.2.1'] },
  });
  instance.$destroy();
});
