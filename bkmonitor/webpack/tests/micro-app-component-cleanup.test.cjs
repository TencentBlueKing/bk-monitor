const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const test = require('node:test');

const root = path.join(__dirname, '..');
const dependencies = process.env.BK_MONITOR_TEST_DEPENDENCY_ROOT || path.join(root, 'src/trace/node_modules');

function patchedSource(packageName, file, patchName) {
  const sourceRoot = path.join(dependencies, packageName);
  const manifest = JSON.parse(fs.readFileSync(path.join(sourceRoot, 'package.json'), 'utf8'));
  const version = packageName === 'bkui-vue' ? '2.0.2-beta.97' : '0.0.4';
  assert.equal(manifest.version, version);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'monitor-component-cleanup-'));
  let original = fs.readFileSync(path.join(sourceRoot, file), 'utf8');
  try {
    fs.mkdirSync(path.dirname(path.join(dir, file)), { recursive: true });
    fs.writeFileSync(path.join(dir, file), original);
    const patch = path.join(root, 'patches', patchName);
    try {
      execFileSync('git', ['apply', '--check', patch], { cwd: dir, stdio: 'pipe' });
    } catch {
      execFileSync('git', ['apply', '--reverse', '--check', patch], { cwd: dir, stdio: 'pipe' });
      execFileSync('git', ['apply', '--reverse', patch], { cwd: dir });
      original = fs.readFileSync(path.join(dir, file), 'utf8');
    }
    execFileSync('git', ['apply', patch], { cwd: dir });
    return { original, patched: fs.readFileSync(path.join(dir, file), 'utf8') };
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

test('Popover unmount executes its floating cleanup and preserves observer/DOM cleanup', () => {
  const sources = patchedSource('bkui-vue', 'lib/popover/index.js', 'bkui-vue-2.0.2-beta.97.patch');
  const execute = (source, initialized = true) => {
    const calls = [];
    const start = source.indexOf('var onUnmountedFn = function onUnmountedFn() {');
    const end = source.indexOf('  var isClickInside', start);
    assert.ok(start > 0 && end > start);
    const body = source.slice(start, end);
    const document = {
      body: { removeEventListener: () => calls.push('fullscreen') },
      removeEventListener: () => calls.push('outside-click'),
    };
    const observer = { disconnect: () => calls.push('observer') };
    const unmount = new Function(
      'cleanup', 'beforeInstanceUnmount', 'resolvePopElements', 'clearParentNodeId', 'document',
      'handleFullscreenChange', 'handleClickOutside', 'parentVisibilityObserver',
      `${body}; return onUnmountedFn;`
    )(
      initialized ? () => calls.push('floating') : null, () => calls.push('instance'),
      () => ({ root: {} }), () => calls.push('parent-node'), document, () => {}, () => {}, observer
    );
    unmount();
    return calls;
  };
  assert.equal(execute(sources.original).includes('floating'), false);
  assert.deepEqual(execute(sources.patched), ['floating', 'instance', 'parent-node', 'fullscreen', 'outside-click', 'observer']);
  assert.deepEqual(execute(sources.patched, false), ['instance', 'parent-node', 'fullscreen', 'outside-click', 'observer']);
});

test('TDesign captures click position through Document and retains timer/capture behavior', () => {
  const { patched } = patchedSource('@blueking/tdesign-ui', 'vue3/index.es.min.js', 'blueking-tdesign-ui-0.0.4.patch');
  const start = patched.indexOf('var mousePosition;');
  const end = patched.indexOf('var key = 1;', start);
  assert.ok(start > 0 && end > start);
  const calls = [];
  const document = {
    documentElement: { addEventListener() { assert.fail('listener escaped to the host HTML element'); } },
    addEventListener: (...args) => calls.push(args),
  };
  let timer;
  const position = new Function('window', 'document', 'setTimeout', `${patched.slice(start, end)};return ()=>mousePosition;`)(
    { document }, document, (callback, delay) => { assert.equal(delay, 100); timer = callback; }
  );
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], 'click');
  assert.equal(calls[0][2], true);
  calls[0][1]({ clientX: 23, clientY: 45 });
  assert.deepEqual(position(), { x: 23, y: 45 });
  timer();
  assert.equal(position(), null);
});
