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

function pollContext(...responses) {
  const ctx = {
    indexSetId: { value: '42' },
    initializedIndex: { value: '' },
    clusterStepData: { value: null },
    statusError: { value: '' },
    isClusterActive: { value: true },
    isShowClusterStep: { value: true },
    clusterSwitch: { value: true },
    totalFields: { value: [{}] },
    statusRequest: 0,
    statusTimer: null,
    stopPolling() {
      ctx.statusTimer = null;
    },
    setTimeout(callback, delay) {
      assert.equal(delay, 10000);
      return callback;
    },
    getClusterConfigStatus: async () => responses.shift(),
    filterGroupList() {},
    initTableOperator: async () => {},
  };
  ctx.clusterPolling = loadCallback(
    'index.tsx',
    node => ts.isVariableDeclaration(node) && node.name.getText() === 'clusterPolling' && node.initializer,
    ctx,
  );
  return ctx;
}

for (const lightweight of [true, false]) {
  const mode = lightweight ? 'lightweight' : 'legacy';
  function response(status) {
    const finished = status === 'success';
    const step = { status: status.toUpperCase() };
    const data = { access_finished: finished, flow_create: step, flow_run: step, data_check: step };
    if (lightweight) {
      data.quix = {
        phase: finished ? 'running' : 'enabling',
        distance_threshold: finished ? '0.5' : null,
        operation: { operation_type: 'enable', status },
      };
    }
    return { code: 0, data };
  }

  test(mode + ' first enable polls until results are ready', async () => {
    const ctx = pollContext(response('running'), response('success'));
    await ctx.clusterPolling();
    assert.equal(ctx.isShowClusterStep.value, true);
    await ctx.statusTimer();
    assert.equal(ctx.isShowClusterStep.value, false);
    assert.equal(ctx.initializedIndex.value, '42');
    assert.equal(ctx.statusTimer, null);
  });

  test(mode + ' first enable failure stays on the original progress page', async () => {
    const ctx = pollContext(response('failed'));
    await ctx.clusterPolling();
    assert.equal(ctx.isShowClusterStep.value, true);
    assert.equal(ctx.statusTimer, null);
  });
}

for (const status of ['running', 'awaiting_receipt', 'failed']) {
  test('opening results during update does not start polling: ' + status, async () => {
    const quix = { phase: 'updating', distance_threshold: '0.5', operation: { operation_type: 'update', status } };
    const ctx = pollContext({ code: 0, data: { quix } });
    await ctx.clusterPolling();
    assert.equal(ctx.initializedIndex.value, '42');
    assert.equal(ctx.isShowClusterStep.value, false);
    assert.equal(ctx.statusTimer, null);
  });
}

for (const [name, quix, operation, notices] of [
  ['unchanged lightweight settings', true, null, 0],
  ['changed lightweight settings', true, 'operation-id', 1],
  ['legacy save', false, null, 1],
]) {
  test(name, () => {
    const messages = [],
      events = [];
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
        emit: event => events.push(event),
      },
    );
    callback({ data: [operation] });
    assert.deepEqual(events, ['close']);
    assert.equal(messages.length, notices);
    if (notices) assert.equal(messages[0].title, '保存待生效');
    if (notices) assert.equal(messages[0].message, '该保存需要10分钟生效, 请耐心等待');
  });
}
