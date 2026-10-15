const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.join(__dirname, '../src/monitor-common/utils');
function declarations(filename, names) {
  const source = ts.createSourceFile(filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true);
  const selected = source.statements.filter(
    node =>
      ts.isVariableStatement(node) &&
      node.declarationList.declarations.some(declaration => names.includes(declaration.name.getText(source)))
  );
  assert.equal(selected.length, names.length, '必须执行源码中的实际业务入口函数和缓存键');
  return selected.map(node => node.getText(source)).join('\n');
}
const code = [
  declarations(path.join(root, 'constant.ts'), ['LOCAL_BIZ_STORE_KEY']),
  declarations(path.join(root, 'utils.js'), ['getUrlParam']),
  declarations(process.env.BUSINESS_ENTRY_TEST_SOURCE || path.join(root, 'index.ts'), [
    'isAlarmCenterRouteHash',
    'parseBizId',
    'setGlobalBizId',
  ]),
].join('\n');
const compiled = ts.transpileModule(code, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const load = new Function('window', 'location', 'localStorage', 'history', 'exports', compiled);

function setup({
  href = 'https://monitor.example.com/',
  localBizId = '202',
  backendBizId = 101,
  defaultBizId = null,
  spaces = [{ bk_biz_id: 101 }, { bk_biz_id: 202 }],
  token,
  storage = new Map(localBizId === null ? [] : [['__biz_id__', localBizId]]),
} = {}) {
  const url = new URL(href);
  const location = { href, origin: url.origin, pathname: url.pathname, search: url.search, hash: url.hash };
  const window = {
    location,
    bk_biz_id: backendBizId,
    cc_biz_id: backendBizId,
    default_biz_id: defaultBizId,
    space_list: spaces,
    __BK_WEWEB_DATA__: token ? { token } : undefined,
  };
  const exports = {};
  load(
    window,
    location,
    { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
    {
      replaceState: (_state, _title, href) => {
        location.href = href;
      },
    },
    exports
  );
  return { window, location, storage, initialize: exports.setGlobalBizId };
}

test('访问带业务参数的策略页后，裸域入口恢复最近业务并保留缓存', () => {
  const visit = setup({
    href: 'https://monitor.example.com/?bizId=202#/strategy-config',
    backendBizId: 202,
    localBizId: '101',
  });
  assert.equal(visit.initialize(), 202);
  assert.equal(visit.storage.get('__biz_id__'), '202');

  const entry = setup({ storage: visit.storage });
  assert.equal(entry.initialize(), false);
  assert.equal(entry.location.href, 'https://monitor.example.com/?bizId=202');
  assert.equal(entry.storage.get('__biz_id__'), '202');

  const landing = setup({ href: entry.location.href, backendBizId: 202, storage: entry.storage });
  assert.equal(landing.initialize(), 202);
  assert.equal(landing.window.cc_biz_id, 202);
  assert.equal(landing.window.bk_biz_id, 202);
  assert.equal(landing.storage.get('__biz_id__'), '202');
});

test('恢复最近业务时保留部署子路径和目标 hash', () => {
  const entry = setup({ href: 'https://monitor.example.com/monitor/#/strategy-config' });
  assert.equal(entry.initialize(), false);
  assert.equal(entry.location.href, 'https://monitor.example.com/monitor/?bizId=202#/strategy-config');
});

test('已设置的默认业务仍优先于最近业务', () => {
  const entry = setup({ defaultBizId: 101, backendBizId: 202 });
  assert.equal(entry.initialize(), false);
  assert.equal(entry.location.href, 'https://monitor.example.com/?bizId=101');
});

test('显式 bizId 优先于默认业务和最近业务', () => {
  const entry = setup({
    href: 'https://monitor.example.com/?bizId=202#/strategy-config',
    backendBizId: 202,
    defaultBizId: 101,
    localBizId: '101',
  });
  assert.equal(entry.initialize(), 202);
  assert.equal(entry.location.href, 'https://monitor.example.com/?bizId=202#/strategy-config');
  assert.equal(entry.storage.get('__biz_id__'), '202');
});

test('显式 space_uid 优先于默认业务和最近业务', () => {
  const entry = setup({
    href: 'https://monitor.example.com/?space_uid=bkcc__202#/strategy-config',
    backendBizId: 202,
    defaultBizId: 101,
    localBizId: '101',
    spaces: [{ bk_biz_id: 101 }, { bk_biz_id: 202, space_uid: 'bkcc__202' }],
  });
  assert.equal(entry.initialize(), 202);
  assert.equal(entry.storage.get('__biz_id__'), '202');
});

for (const localBizId of [null, '', 'invalid', '0', '-1', '303']) {
  test(`缓存 ${JSON.stringify(localBizId)} 无效或不再有权限时使用后端业务`, () => {
    const entry = setup({ localBizId });
    assert.equal(entry.initialize(), false);
    assert.equal(entry.location.href, 'https://monitor.example.com/?bizId=101');
  });
}

test('演示业务缓存不作为最近业务恢复', () => {
  const entry = setup({ spaces: [{ bk_biz_id: 101 }, { bk_biz_id: 202, is_demo: true }] });
  assert.equal(entry.initialize(), false);
  assert.equal(entry.location.href, 'https://monitor.example.com/?bizId=101');
});

test('可恢复负数 ID 的非 CMDB 空间', () => {
  const entry = setup({ localBizId: '-202', spaces: [{ bk_biz_id: 101 }, { bk_biz_id: -202 }] });
  assert.equal(entry.initialize(), false);
  assert.equal(entry.location.href, 'https://monitor.example.com/?bizId=-202');
});

test('本地缓存已失权且后端业务也不存在时回退到空间列表首项', () => {
  const entry = setup({ localBizId: '303', backendBizId: -1 });
  assert.equal(entry.initialize(), false);
  assert.equal(entry.location.href, 'https://monitor.example.com/?bizId=101');
});

test('空业务列表不恢复旧缓存，正常入口仍跳转无业务页面', () => {
  const entry = setup({ spaces: [], backendBizId: -1 });
  assert.equal(entry.initialize(), true);
  assert.equal(entry.location.href, 'https://monitor.example.com/#/no-business');
  assert.equal(entry.storage.get('__biz_id__'), '202');
});

for (const hash of ['#/trace/alarm-center/detail/alert-id', '#/share/example-token']) {
  test(`无业务权限的 ${hash} 显式入口保留目标业务和路由`, () => {
    const href = `https://monitor.example.com/?bizId=303${hash}`;
    const entry = setup({ href });
    assert.equal(entry.initialize(), 303);
    assert.equal(entry.location.href, href);
    assert.equal(entry.window.bk_biz_id, 303);
  });
}

test('无业务权限的微前端 token 入口保留显式业务', () => {
  const entry = setup({ href: 'https://monitor.example.com/?bizId=303#/strategy-config', token: 'example-token' });
  assert.equal(entry.initialize(), 303);
  assert.equal(entry.window.bk_biz_id, 303);
});

for (const [hash, expectedBizId] of [
  ['#/trace/alarm-center/detail/alert-id', 0],
  ['#/share/example-token', -1],
]) {
  test(`空业务列表的 ${hash} 入口不恢复旧缓存且保留目标路由`, () => {
    const href = `https://monitor.example.com/${hash}`;
    const entry = setup({ href, spaces: [], backendBizId: -1 });
    assert.equal(entry.initialize(), expectedBizId);
    assert.equal(entry.location.href, href);
    assert.equal(entry.window.bk_biz_id, expectedBizId);
  });
}

test('空业务列表的微前端 token 入口不恢复旧缓存', () => {
  const entry = setup({ spaces: [], backendBizId: -1, token: 'example-token' });
  assert.equal(entry.initialize(), -1);
  assert.equal(entry.location.href, 'https://monitor.example.com/');
  assert.equal(entry.window.bk_biz_id, -1);
});
