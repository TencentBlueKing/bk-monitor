const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const vue = require('../src/trace/node_modules/vue');

const base = path.join(__dirname, '../src/trace/pages/profiling-explore/components/collection');

const stubComponent = name => ({ name, props: {}, render: () => null });

// 执行真实组件 setup/render；只隔离外部 UI 库、服务与浏览器生命周期。
function loadComponent(file, overrides = {}) {
  const source = fs.readFileSync(path.join(base, file), 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
      jsxFragmentFactory: 'Fragment',
    },
  }).outputText;
  const module = { exports: {} };
  const load = id => {
    if (id in overrides) return overrides[id];
    if (/\.(scss|css|png|svg)$/.test(id)) return {};
    if (id === 'vue') {
      return { ...vue, onMounted() {}, onScopeDispose() {}, useTemplateRef: () => vue.shallowRef(null) };
    }
    if (id === 'vue-i18n') return { useI18n: () => ({ t: value => value }) };
    if (id === '@vueuse/core') return { onClickOutside: () => () => {}, promiseTimeout: async () => {} };
    if (id === 'bkui-vue') return { Alert: stubComponent('Alert'), Button: stubComponent('Button') };
    if (id === '@/components/retrieval-filter/value-tag-selector') return { default: stubComponent('ValueTagSelector') };
    if (id === '@/components/retrieval-filter/value-options') return { default: stubComponent('ValueOptions') };
    throw new Error(`Unexpected import: ${id}`);
  };
  new Function('require', 'module', 'exports', 'h', 'Fragment', code)(
    load,
    module,
    module.exports,
    vue.h,
    vue.Fragment
  );
  return module.exports.default;
}

function candidateService(requests) {
  return {
    COLLECTION_CANDIDATE_MAX_LIMIT: 200,
    COLLECTION_CANDIDATE_PAGE_SIZE: 20,
    getCollectionCandidates: (bizId, range, field, query, signal) =>
      new Promise(resolve => {
        requests.push({ bizId, range: [...range], field, query: { ...query }, signal, resolve });
      }),
  };
}

test('任务候选切换业务或时间后，旧响应不写入新缓存并按新范围重新请求', async () => {
  const requests = [];
  const component = loadComponent('collection-single-select.tsx', {
    '../../services/collection-history': candidateService(requests),
  });
  const scope = vue.effectScope();
  const props = vue.shallowReactive({ bizId: 2, range: [1000, 2000], modelValue: '', placeholder: '' });
  const view = scope.run(() => component.setup(props, { emit() {} }));
  try {
    const first = view.getValueFn({ search: '', limit: 20, field: 'task_name' });
    assert.equal(requests.length, 1);
    assert.equal(requests[0].bizId, 2);

    props.bizId = 3;
    props.range = [3000, 4000];
    await vue.nextTick();
    assert.equal(requests[0].signal.aborted, true, '切换后中止旧请求');

    // 旧请求即使成功返回也不能写入新缓存
    requests[0].resolve([{ value: 'OLD', alias: 'old' }]);
    assert.deepEqual(await first, { count: 0, list: [] });

    const second = view.getValueFn({ search: '', limit: 20, field: 'task_name' });
    assert.equal(requests.length, 2, '未命中旧缓存，按新范围重新请求');
    assert.equal(requests[1].bizId, 3);
    assert.deepEqual(requests[1].range, [3000, 4000]);

    requests[1].resolve([{ value: 'NEW' }]);
    assert.deepEqual(await second, { count: 1, list: [{ id: 'NEW', name: 'NEW' }] });
  } finally {
    scope.stop();
  }
});

test('IP/进程候选切换业务或时间后，旧响应不污染新缓存', async () => {
  const requests = [];
  const component = loadComponent('collection-value-tag-selector.tsx', {
    '../../services/collection-history': candidateService(requests),
    '../../utils/collection-history': { PID_PREFIX: 'pid:' },
  });
  const scope = vue.effectScope();
  const props = vue.shallowReactive({
    bizId: 2,
    range: [1000, 2000],
    fields: ['target'],
    value: [],
    placeholder: '',
  });
  const view = scope.run(() => component.setup(props, { emit() {} }));
  try {
    const first = view.getValueFn({ search: '', limit: 20, field: 'target' });
    assert.equal(requests.length, 1);

    props.bizId = 3;
    props.range = [3000, 4000];
    await vue.nextTick();
    assert.equal(requests[0].signal.aborted, true, '切换后中止旧请求');
    const preloadRequest = requests.find(request => request.bizId === 3);
    assert.ok(preloadRequest, '切换后按新范围重新预加载');

    // 先让新范围结果写入缓存，旧请求再返回，模拟旧响应后到的竞态
    preloadRequest.resolve([{ value: 'NEW' }]);
    await vue.nextTick();
    await new Promise(resolve => setImmediate(resolve));

    requests[0].resolve([{ value: 'OLD' }]);
    assert.deepEqual(await first, { count: 0, list: [] }, '旧响应被中止，不写入新缓存');
    await new Promise(resolve => setImmediate(resolve));

    const before = requests.length;
    const fresh = await view.getValueFn({ search: '', limit: 20, field: 'target' });
    assert.equal(requests.length, before, '命中新缓存不再请求');
    assert.deepEqual(
      fresh.list.map(item => item.id),
      ['NEW']
    );
  } finally {
    scope.stop();
  }
});

test('候选加载失败后重试递增版本号强制重挂选择器并清除失败标记', async () => {
  const ValueTagSelector = stubComponent('CollectionValueTagSelector');
  const CollectionSingleSelect = stubComponent('CollectionSingleSelect');
  const utils = {
    createHistoryFilters: () => ({ ips: [], task_name: '', process_names: [], process_pids: [], task_id: null }),
    parseProcessSelection: () => ({}),
  };
  const component = loadComponent('collection-filters.tsx', {
    '../../utils/collection-history': utils,
    './collection-value-tag-selector': { default: ValueTagSelector },
    './collection-single-select': { default: CollectionSingleSelect },
  });
  const scope = vue.effectScope();
  const props = vue.shallowReactive({
    filters: utils.createHistoryFilters(),
    bizId: 2,
    range: [1000, 2000],
    autoQuery: false,
    taskName: '',
  });
  const view = scope.run(() => component.setup(props, { emit() {} }));

  const countSelectors = tree => {
    const found = [];
    const walk = node => {
      if (!node || typeof node !== 'object') return;
      if (Array.isArray(node)) return node.forEach(walk);
      if (node.__v_isVNode) {
        if (node.type === ValueTagSelector || node.type === CollectionSingleSelect) found.push(node);
        walk(node.children);
      }
    };
    walk(tree);
    return found;
  };
  const renderKeys = () => {
    const ctx = {};
    for (const [key, value] of Object.entries({ ...view, ...props })) {
      ctx[key] = vue.isRef(value) ? value.value : value;
    }
    ctx.t = value => value;
    return countSelectors(component.render.call(ctx)).map(node => String(node.key));
  };

  try {
    assert.equal(view.revision.value, 0);
    view.setIpError(true);
    assert.equal(view.candidateError.value, true);

    view.reloadCandidates();
    assert.equal(view.candidateError.value, false, '重试清除失败标记');
    assert.equal(view.revision.value, 1, '重试递增版本号');
    assert.deepEqual(renderKeys(), ['1', '1', '1'], '三个选择器 key 跟随版本号强制重挂');

    view.reloadCandidates();
    assert.equal(view.revision.value, 2);
    assert.deepEqual(renderKeys(), ['2', '2', '2']);
  } finally {
    scope.stop();
  }
});
