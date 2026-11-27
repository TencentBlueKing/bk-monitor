const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const tick = () => new Promise(done => setImmediate(done));
const file = path.resolve(__dirname, '../src/monitor-pc/pages/home/new-home/components/home-select.tsx');
const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  fileName: file,
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.CommonJS,
    jsx: ts.JsxEmit.React,
    jsxFactory: 'h',
    experimentalDecorators: true,
  },
}).outputText;
const create = new Function('exports', 'require', 'window', 'location', 'fetch', 'h', code);
const t = name => name;
const space = (id, kind) => ({ bk_biz_id: id, space_type_id: kind });
function fixture(paged) {
  const lookups = [],
    streams = [];
  const deps = {
    'vue-property-decorator': { Component: () => x => x, Prop: () => () => {}, Ref: () => () => {} },
    'vue-tsx-support': {
      Component: class {
        $t(s) {
          return s;
        }
      },
    },
    'monitor-common/utils/debounce-decorator': { default: () => () => {} },
    'monitor-common/utils/utils': { random: () => '' },
    'monitor-common/utils/space-directory': { supportsSpaceDirectoryPages: () => paged },
    'monitor-common/utils/space-selection': {
      resolveSelectedSpaces: ids => new Promise(done => lookups.push({ ids, done })),
    },
    'monitor-pc/common/constant': {
      SPACE_TYPE_MAP: { bkcc: { name: '业务' }, bkci: { name: '研发项目' }, bksaas: { name: '蓝鲸应用' } },
    },
    '../utils': {
      ESearchPopoverType: { searchList: 'searchList' },
      ESearchType: { strategy: 'strategy' },
      splitHighlightFragments: name => [{ text: name }],
    },
  };
  const result = {};
  function fetch() {
    return Promise.resolve({
      body: new ReadableStream({
        start(stream) {
          streams.push(stream);
        },
      }),
    });
  }
  create(
    result,
    id => deps[id] ?? {},
    { site_url: '/' },
    { origin: 'https://monitor.example' },
    fetch,
    (_type, props, ...children) => ({ props, children: children.flat(Infinity) })
  );
  const vm = Object.assign(new result.default(), {
    $store: { getters: { bizId: 2, bizList: paged ? [space(2, 'bkcc')] : [space(2, 'bkcc'), space(7, 'bkci')] } },
  });
  function send(index, ...groups) {
    const body = groups
      .map(
        ([type, ids]) =>
          'data:' +
          JSON.stringify({
            type,
            items: ids.map(bk_biz_id => ({ bk_biz_id, name: 'hit', bk_biz_name: 'Space ' + bk_biz_id })),
          }) +
          '\n\n'
      )
      .join('');
    streams[index].enqueue(new TextEncoder().encode(body));
  }
  function tags(id) {
    const row = vm.renderGroupItem({ bk_biz_id: id, name: 'hit' }, 'alert', 0, 0);
    return row.children.filter(node => node?.props?.class === 'list-item-tag').map(node => node.children[0]);
  }
  return { vm, lookups, streams, send, tags };
}
test('streamed search batches visible missing business IDs, renders returned tags and ignores prior searches', async () => {
  const f = fixture(true);
  f.vm.searchValue = 'old';
  f.vm.getSearchList();
  await tick();
  assert.equal(f.lookups.length, 0);
  f.send(0, ['alert', [2, 7]], ['strategy', ['7', -8]]);
  await tick();
  assert.deepEqual(
    f.lookups.map(q => q.ids),
    [[7, -8]]
  );
  f.lookups[0].done([space(7, 'bkci')]);
  await tick();
  assert.deepEqual(f.tags('7'), ['研发项目']);
  assert.deepEqual(f.tags(-8), []);
  f.send(0, ['alert', [7, -8, -9]]);
  await tick();
  assert.deepEqual(f.lookups[1].ids, [-9]);
  f.vm.searchValue = 'new';
  f.vm.getSearchList();
  await tick();
  f.send(1, ['alert', [-11, 2]]);
  await tick();
  f.send(0, ['alert', [111]]);
  f.lookups[2].done([space(-11, 'bksaas')]);
  f.lookups[1].done([space(-9, 'bkci')]);
  await tick();
  assert.deepEqual(
    f.lookups.map(q => q.ids),
    [[7, -8], [-9], [-11]]
  );
  assert.deepEqual(
    f.vm.searchList[0].items.map(row => row.bk_biz_id),
    [-11, 2]
  );
  assert.deepEqual(f.tags(-11), ['蓝鲸应用']);
  assert.deepEqual(f.tags(-9), []);
  assert.deepEqual(f.tags(2), ['业务']);
  f.streams.forEach(stream => stream.close());
});
test('legacy full-directory search renders the cross-business type without a page lookup', async () => {
  const f = fixture(false);
  f.vm.searchValue = 'legacy';
  f.vm.getSearchList();
  await tick();
  f.send(0, ['alert', [7]]);
  await tick();
  assert.deepEqual(f.lookups, []);
  assert.deepEqual(f.tags(7), ['研发项目']);
  f.streams[0].close();
});
