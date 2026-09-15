const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { before, after, test } = require('node:test');
const ts = require('typescript');
const webpack = require('webpack');
const Vue = require('vue');

const webRoot = path.resolve(__dirname, '../..');
const storage = new Map();
const commits = [];
const timezoneUpdates = [];
const picker = {};
const store = {
  getters: { retrieveParams: { format: 'YYYY-MM-DD HH:mm:ss' } },
  commit: (...args) => commits.push(args),
};
const source = fs.readFileSync(path.join(webRoot, 'src/components/time-range/time-range.tsx'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2020,
    module: ts.ModuleKind.CommonJS,
    experimentalDecorators: true,
    jsx: ts.JsxEmit.React,
    jsxFactory: 'h',
  },
}).outputText;
const wrapperModule = { exports: {} };
vm.runInNewContext(compiled, {
  exports: wrapperModule.exports,
  window: { timezone: 'Asia/Shanghai' },
  localStorage: { setItem: (key, value) => storage.set(key, value) },
  h: (type, props, ...children) => ({ type, props, children }),
  require(id) {
    if (id === 'vue-tsx-support') return { Component: Vue };
    if (id === '@blueking/date-picker/vue2') return { default: picker };
    if (id.endsWith('.css')) return {};
    if (id === '../../language/dayjs') return { updateTimezone: value => timezoneUpdates.push(value) };
    if (id === './utils') return { DEFAULT_TIME_RANGE: ['now-1h', 'now'] };
    if (id === '@/store/store.type.ts') return { BK_LOG_STORAGE: { CACHED_BATCH_LIST: 'cachedBatchList' } };
    return require(id);
  },
});
const TimeRange = wrapperModule.exports.default;
function createWrapper() {
  return new TimeRange({
    propsData: { value: ['now-1h', 'now'], timezone: 'Asia/Shanghai', maxDuration: 180 * 86400000 },
    beforeCreate() { this.$store = store; },
  });
}

test('format switching updates the controlled picker, persists and emits once', () => {
  const wrapper = createWrapper();
  const events = [];
  wrapper.$on('format-change', value => events.push(value));
  wrapper.handleFormatChange('YYYY-MM-DD');
  const renderedPicker = wrapper.$options.render.call(wrapper).children[0];
  assert.equal(renderedPicker.props.format, 'YYYY-MM-DD');
  assert.equal(renderedPicker.props.enableFormatClick, true);
  assert.equal(storage.get('SEARCH_DEFAULT_TIME_FORMAT'), 'YYYY-MM-DD');
  assert.deepEqual(events, ['YYYY-MM-DD']);
  wrapper.$destroy();
});

test('timezone remains controlled by the parent and change preserves cache updates', async () => {
  const wrapper = createWrapper();
  const timezones = [];
  wrapper.$on('timezone-change', value => { timezones.push(value); wrapper.timezone = value; });
  wrapper.handleTimezoneChange('Asia/Tokyo');
  await Vue.nextTick();
  assert.equal(wrapper.$options.render.call(wrapper).children[0].props.timezone, 'Asia/Tokyo');
  assert.deepEqual(timezones, ['Asia/Tokyo']);
  assert.equal(timezoneUpdates.at(-1), 'Asia/Tokyo');
  const ranges = [];
  wrapper.$on('change', value => ranges.push(value));
  const next = ['now-2h', 'now'];
  wrapper.handleModelValueChange(next);
  assert.deepEqual(ranges, [next]);
  assert.equal(storage.get('SEARCH_DEFAULT_TIME'), JSON.stringify(next));
  assert.equal(commits.at(-2)[0], 'updateStorage');
  assert.equal(commits.at(-1)[0], 'retrieve/updateCachePickerValue');
  assert.deepEqual(commits.at(-1)[1], wrapper.value);
  assert.equal(wrapper.$options.render.call(wrapper).children[0].props.maxDuration, 180 * 86400000);
  wrapper.$destroy();
});

let DateRange;
let outputDir;
before(async () => {
  outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'date-picker-compat-'));
  await new Promise((resolve, reject) => {
    webpack({
      mode: 'development', target: 'node', context: webRoot,
      entry: require.resolve('@blueking/date-picker/vue2'), devtool: false,
      output: { path: outputDir, filename: 'picker.cjs', library: { type: 'commonjs2' } },
    }, (error, stats) => {
      if (error || stats.hasErrors()) reject(error || new Error(stats.toString({ all: false, errors: true })));
      else resolve();
    });
  });
  // DOM placeholders only allow package initialization; these are data tests, not rendering tests.
  global.document = {
    cookie: '', documentElement: { style: {} }, body: { style: {} },
    createElement: () => ({ style: {} }), addEventListener() {}, removeEventListener() {},
  };
  global.HTMLElement = class {};
  global.PointerEvent = class {};
  global.MouseEvent = class {};
  ({ DateRange } = require(path.join(outputDir, 'picker.cjs')));
});
after(() => {
  for (const name of ['document', 'HTMLElement', 'PointerEvent', 'MouseEvent']) delete global[name];
  fs.rmSync(outputDir, { recursive: true, force: true });
});

test('wall-clock dates use the selected timezone and offset dates retain their instant', () => {
  const wallClock = new DateRange(['2024-01-02 12:00:00', '2024-01-02 13:00:00'], undefined, 'Asia/Tokyo');
  assert.equal(wallClock.startDate.toISOString(), '2024-01-02T03:00:00.000Z');
  const absolute = new DateRange(['2024-01-02T12:00:00+08:00', '2024-01-02T13:00:00+08:00'], undefined, 'Asia/Tokyo');
  assert.equal(absolute.startDate.toISOString(), '2024-01-02T04:00:00.000Z');
  const timestamp = new DateRange([1704168000000, 1704171600000], undefined, 'Asia/Tokyo');
  assert.equal(timestamp.startDate.valueOf(), 1704168000000);
});

test('relative ranges and the inclusive 180-day duration boundary remain valid', () => {
  const relative = new DateRange(['now-1h', 'now'], undefined, 'Asia/Shanghai');
  assert.ok(Math.abs(relative.endDate.valueOf() - relative.startDate.valueOf() - 3600000) < 1000);
  const start = Date.UTC(2024, 0, 1);
  const max = 180 * 86400000;
  assert.equal(new DateRange([start, start + max]).isInValidDuration(0, max), true);
  assert.equal(new DateRange([start, start + max + 1000]).isInValidDuration(0, max), false);
});
