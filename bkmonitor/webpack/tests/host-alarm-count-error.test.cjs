const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');

let vue;
try {
  vue = require('../src/trace/node_modules/vue');
} catch {
  vue = require('../node_modules/.pnpm/@vue+runtime-core@3.5.30/node_modules/@vue/runtime-core');
}

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/trace/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  jsx: 'react',
  jsxFactory: 'h',
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

require.extensions['.scss'] = () => {};
global.h = vue.h;
global.location = { hash: '#/trace/host', href: 'https://example.com/?bizId=2#/trace/host' };

const refreshGeneration = vue.shallowRef(0);
const countRequests = [];
const openedUrls = [];

global.window = {
  open: (...args) => openedUrls.push(args),
};

const deferred = () => {
  let reject;
  let resolve;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

const originalLoad = Module._load;
Module._load = function load(request, parent, isMain) {
  if (request === 'vue') return vue;
  if (request === 'monitor-api/modules/scene_view') {
    return {
      getStrategyAndEventCount: params => {
        const request = deferred();
        countRequests.push({ params, ...request });
        return request.promise;
      },
    };
  }
  if (request === '@/store/modules/host') {
    return { useHostStore: () => ({ refreshGeneration }) };
  }
  if (request === 'pinia') {
    return { storeToRefs: () => ({ refreshGeneration }) };
  }
  if (request === 'vue-i18n') {
    return { useI18n: () => ({ t: (value, params) => (params ? value.replace('{0}', params[0]) : value) }) };
  }
  return originalLoad(request, parent, isMain);
};

const { getStrategyAndEventCountApi } = require('../src/trace/pages/host/services/global-service.ts');
const AlarmTools = require('../src/trace/pages/host/components/alarm-tools/index.tsx').default;
Module._load = originalLoad;

const hostNode = id => ({
  bk_biz_id: 2,
  bk_cloud_id: 0,
  bk_host_id: id,
  bk_host_innerip: `10.0.0.${id}`,
  bk_host_innerip_v6: '',
  id: String(id),
  ip: `10.0.0.${id}`,
  name: `10.0.0.${id}`,
});

const flushPromises = async () => {
  await vue.nextTick();
  await new Promise(resolve => setImmediate(resolve));
};

const setupAlarmTools = (t, node = hostNode(1)) => {
  const props = vue.reactive({ selectedNode: node });
  const scope = vue.effectScope();
  t.after(() => scope.stop());
  const render = scope.run(() => AlarmTools.setup(props));
  return { props, render };
};

const getButtons = render => render().children;
const getButtonText = button =>
  button.children.filter(child => typeof child === 'number' || typeof child === 'string').join('');
const getTooltipContent = button => button.props?.['v-bk-tooltips']?.content ?? button.dirs?.[0]?.value?.content;

test.beforeEach(() => {
  countRequests.length = 0;
  openedUrls.length = 0;
  refreshGeneration.value = 0;
});

test('服务层保留计数接口失败语义', async () => {
  const response = getStrategyAndEventCountApi({ scene_id: 'host', target: hostNode(1) });
  countRequests[0].reject(new Error('network error'));

  await assert.rejects(response, /network error/);
});

test('成功返回零时仍显示真实零值', async t => {
  const { render } = setupAlarmTools(t);
  countRequests[0].resolve({ event_counts: 0, strategy_counts: 0 });
  await flushPromises();

  const [strategyButton, alarmButton] = getButtons(render);
  assert.equal(getButtonText(strategyButton), '0');
  assert.equal(getButtonText(alarmButton), '0');
  assert.equal(getTooltipContent(alarmButton), '无告警事件');
});

test('计数失败显示占位与失败提示，点击后可重试', async t => {
  const { render } = setupAlarmTools(t);
  countRequests[0].reject(new Error('network error'));
  await flushPromises();

  let [strategyButton, alarmButton] = getButtons(render);
  assert.equal(getButtonText(strategyButton), '--');
  assert.equal(getButtonText(alarmButton), '--');
  assert.match(getTooltipContent(strategyButton), /失败/);
  assert.match(getTooltipContent(alarmButton), /重试/);

  alarmButton.props.onClick();
  assert.equal(countRequests.length, 2);
  assert.equal(openedUrls.length, 0);

  countRequests[1].resolve({ event_counts: 3, strategy_counts: 1 });
  await flushPromises();
  [strategyButton, alarmButton] = getButtons(render);
  assert.equal(getButtonText(strategyButton), '1');
  assert.equal(getButtonText(alarmButton), '3');
});

test('旧请求失败不能覆盖新节点的成功计数', async t => {
  const { props, render } = setupAlarmTools(t, hostNode(1));
  props.selectedNode = hostNode(2);
  await vue.nextTick();
  assert.equal(countRequests.length, 2);

  countRequests[1].resolve({ event_counts: 20, strategy_counts: 2 });
  await flushPromises();
  countRequests[0].reject(new Error('late failure'));
  await flushPromises();

  const [strategyButton, alarmButton] = getButtons(render);
  assert.equal(getButtonText(strategyButton), '2');
  assert.equal(getButtonText(alarmButton), '20');
  assert.doesNotMatch(getTooltipContent(alarmButton), /失败/);
});
