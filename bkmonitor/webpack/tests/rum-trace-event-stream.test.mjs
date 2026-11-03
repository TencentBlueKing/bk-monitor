import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const file = 'src/trace/utils/utils.ts';
const compiled = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
  fileName: file,
  reportDiagnostics: true,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
assert.equal(compiled.diagnostics.length, 0);
const encoder = new TextEncoder();
const flush = () => new Promise(resolve => setImmediate(resolve));

function harness() {
  const errors = [];
  const requests = [];
  const exports = {};
  let controller;
  const stream = new ReadableStream({
    start(value) {
      controller = value;
    },
  });
  const dependencies = {
    dayjs: {},
    'monitor-common/utils': { random: length => 'a'.repeat(length) },
    'monitor-common/utils/xss': { xssFilter: value => value },
  };
  const fetch = async (url, options) => {
    requests.push({ url, ...options });
    options.signal?.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')));
    return { ok: true, body: stream };
  };
  new Function('require', 'exports', 'fetch', 'console', compiled.outputText)(
    name => {
      assert.ok(name in dependencies, `Unexpected dependency: ${name}`);
      return dependencies[name];
    },
    exports,
    fetch,
    { error: (...args) => errors.push(args) }
  );
  return {
    ...exports,
    errors,
    requests,
    stream,
    push: chunk => controller.enqueue(encoder.encode(chunk)),
    close: () => controller.close(),
  };
}

test('streams complete data events before the response ends and preserves aggregated results', async () => {
  const state = harness();
  const snapshots = [];
  let complete = false;
  const pending = state.fetchEventStream('/trace-search', { onData: data => snapshots.push(data) }).then(result => {
    complete = true;
    return result;
  });
  state.push('event: start\n\ndata: {"items":[{"trace_id":"trace-a","app_name":"app-a"}');
  await flush();
  assert.deepEqual(snapshots, []);
  state.push(']}\n\ndata: {"items":[');
  await flush();
  assert.equal(complete, false);
  assert.deepEqual(snapshots, [{ items: [{ trace_id: 'trace-a', app_name: 'app-a' }] }]);
  state.push('{"trace_id":"trace-b","app_name":"应用-b"}]}\n\nevent: end\n\n');
  state.close();
  assert.deepEqual(await pending, snapshots);
  assert.equal(snapshots.length, 2);
  assert.equal(state.stream.locked, false);
});

test('keeps the existing aggregate-only call compatible and ignores non-data or malformed events', async () => {
  const state = harness();
  const pending = state.fetchEventStream('/trace-search');
  state.push('event: start\n\ndata: invalid-json\n\ndata: {"type":"trace","items":[]}\n\nevent: end\n\n');
  state.close();
  assert.deepEqual(await pending, [{ type: 'trace', items: [] }]);
  assert.deepEqual(state.errors, []);
});

test('forwards cancellation and stops buffered callbacks after the first callback aborts', async () => {
  const state = harness();
  const abort = new AbortController();
  const snapshots = [];
  const pending = state.fetchEventStream('/trace-search', {
    signal: abort.signal,
    onData: data => {
      snapshots.push(data);
      abort.abort();
    },
  });
  state.push('data: {"trace_id":"trace-a"}\n\ndata: {"trace_id":"trace-b"}\n\n');
  assert.deepEqual(await pending, [{ trace_id: 'trace-a' }]);
  assert.deepEqual(snapshots, [{ trace_id: 'trace-a' }]);
  assert.equal(state.requests[0].signal, abort.signal);
  assert.deepEqual(state.errors, []);
  assert.equal(state.stream.locked, false);
});

test('cancels an active reader without reporting the cancellation as a query error', async () => {
  const state = harness();
  const abort = new AbortController();
  const snapshots = [];
  const pending = state.fetchEventStream('/trace-search', {
    signal: abort.signal,
    onData: data => snapshots.push(data),
  });
  await flush();
  abort.abort();
  assert.deepEqual(await pending, []);
  assert.deepEqual(snapshots, []);
  assert.deepEqual(state.errors, []);
  assert.equal(state.stream.locked, false);
});
