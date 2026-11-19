const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.join(__dirname, '../src/views/retrieve-v3/search-result/log-clustering');

// Exercise the component callbacks with controlled API responses and a manual timer.
function loadCallback(file, select, context) {
  const source = ts.createSourceFile(
    file,
    fs.readFileSync(path.join(root, file), 'utf8'),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  function find(node) {
    return select(node) || ts.forEachChild(node, find);
  }
  const callback = find(source);
  assert.ok(callback, file);
  const js = ts.transpileModule('(' + callback.getText(source) + ')', {
    compilerOptions: { target: ts.ScriptTarget.ES2020 },
  }).outputText;
  return vm.runInNewContext(js, context);
}

function pollContext(ready) {
  const previous = { quix: { phase: 'running', distance_threshold: '0.5' } };
  const ctx = {
    indexSetId: { value: '42' },
    initializedIndex: { value: ready ? '42' : '' },
    quix: { value: ready ? previous.quix : undefined },
    isShowTopNav: { value: ready },
    clusterStepData: { value: ready ? previous : null },
    statusError: { value: '' },
    isClusterActive: { value: true },
    isShowClusterStep: { value: !ready },
    statusRequest: 0,
    statusTimer: null,
    stopPolling() {
      ctx.statusTimer = null;
    },
    setTimeout(callback, delay) {
      assert.equal(delay, 10000);
      return callback;
    },
    getClusterConfigStatus: async () => {
      throw new Error('timeout');
    },
    Error,
  };
  ctx.clusterPolling = loadCallback(
    'index.tsx',
    node => ts.isVariableDeclaration(node) && node.name.getText() === 'clusterPolling' && node.initializer,
    ctx,
  );
  return ctx;
}

test('failed background polls preserve the initialized result and retry until success', async () => {
  const ctx = pollContext(true);
  const previous = ctx.clusterStepData.value;
  await ctx.clusterPolling();
  await ctx.statusTimer();
  assert.equal(ctx.clusterStepData.value, previous);
  assert.equal(ctx.statusError.value, '');
  assert.equal(ctx.isShowClusterStep.value, false);
  const result = { quix: { ...previous.quix, operation: { status: 'success' } } };
  ctx.getClusterConfigStatus = async () => ({ code: 0, data: result });
  await ctx.statusTimer();
  assert.equal(ctx.clusterStepData.value, result);
  assert.equal(ctx.statusTimer, null);
});

test('initial status failure still offers a manual retry', async () => {
  const ctx = pollContext(false);
  await ctx.clusterPolling();
  assert.equal(ctx.statusError.value, 'timeout');
  assert.equal(ctx.statusTimer, null);
});

for (const [name, quix, operation, notices] of [
  ['unchanged lightweight settings', true, null, 0],
  ['changed lightweight settings', true, 'operation-id', 1],
  ['legacy save', false, null, 1],
]) {
  test(name, () => {
    const messages = [],
      events = [];
    let refreshes = 0;
    const callback = loadCallback(
      'top-operation/cluster-config/edit-config/index.tsx',
      node => {
        if (
          !ts.isCallExpression(node) ||
          !ts.isPropertyAccessExpression(node.expression) ||
          node.expression.name.text !== 'then'
        )
          return;
        const request = node.expression.expression;
        if (ts.isCallExpression(request) && request.arguments[0]?.text === 'retrieve/updateClusteringConfig')
          return node.arguments[0];
      },
      {
        quix: { value: quix },
        t: key => key,
        bkNotify: options => messages.push(options),
        page: { refresh: () => refreshes++ },
        emit: event => events.push(event),
      },
    );
    callback({ data: [operation] });
    assert.deepEqual(events, ['close']);
    assert.equal(messages.length, notices);
    assert.equal(refreshes, quix && operation ? 1 : 0);
    if (notices) assert.equal(messages[0].title, '保存待生效');
    if (!quix) assert.equal(messages[0].message, '该保存需要10分钟生效, 请耐心等待');
  });
}
