import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const root = path.join(import.meta.dirname, '..');
const homeFile = 'src/apm/pages/home/apm-home.tsx';
const listFile = 'src/apm/pages/home/components/apm-home-list.tsx';

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

function home() {
  const requests = [];
  const proto = methods(homeFile, ['getAppList', 'beforeDestroy'], {
    listApplication: () => {
      const request = deferred();
      requests.push(request);
      return request.promise;
    },
    handleTransformToTimestamp: value => value,
    charColor: () => 'gray',
    window: { clearInterval() {} },
  });
  return {
    requests,
    subject: Object.assign(Object.create(proto), {
      appListRequestId: 0,
      appListLoaded: false,
      appListError: false,
      loading: false,
      appName: '',
      originalAppList: [],
      timeRange: [1, 2],
      handleReplaceRouteUrl() {},
    }),
  };
}

// Execute the actual component methods without loading the browser-only chart packages.
function methods(file, names, globals = {}) {
  const source = ts.createSourceFile(
    file,
    fs.readFileSync(path.join(root, file), 'utf8'),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX
  );
  const component = source.statements.find(ts.isClassDeclaration);
  const members = component.members
    .filter(member => names.includes(member.name?.getText(source)))
    .map(member => {
      if (!ts.isMethodDeclaration(member)) return member;
      return ts.factory.updateMethodDeclaration(
        member,
        member.modifiers?.filter(modifier => !ts.isDecorator(modifier)),
        member.asteriskToken,
        member.name,
        member.questionToken,
        member.typeParameters,
        member.parameters,
        member.type,
        member.body
      );
    });
  assert.equal(members.length, names.length);
  const subject = ts.factory.updateClassDeclaration(
    component,
    undefined,
    ts.factory.createIdentifier('Subject'),
    undefined,
    undefined,
    members
  );
  const text = ts.createPrinter().printNode(ts.EmitHint.Unspecified, subject, source);
  const code = ts.transpileModule(text, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, jsxFactory: 'h' },
  }).outputText;
  return vm.runInNewContext(`${code}; Subject.prototype`, { ...globals });
}

test('application requests accept changed time ranges and ignore older responses', async () => {
  const { subject, requests } = home();
  const first = subject.getAppList();
  subject.timeRange = [3, 4];
  const second = subject.getAppList();
  assert.equal(requests.length, 2);
  requests[0].resolve({ data: [{ app_name: 'old' }] });
  await first;
  assert.equal(subject.loading, true);
  assert.equal(subject.originalAppList.length, 0);
  requests[1].resolve({ data: [{ app_name: 'latest' }] });
  await second;
  assert.equal(subject.appName, 'latest');
  assert.equal(subject.loading, false);
  assert.equal(subject.appListLoaded, true);
});

test('failed refresh preserves applications; successful empty response clears selection', async () => {
  const { subject, requests } = home();
  subject.originalAppList = [{ app_name: 'current' }];
  subject.appName = 'current';
  subject.appListLoaded = true;
  const refresh = subject.getAppList();
  requests[0].reject(new Error('offline'));
  await refresh;
  assert.equal(subject.originalAppList[0].app_name, 'current');
  assert.equal(subject.appListError, true);
  assert.equal(subject.loading, false);
  const retry = subject.getAppList();
  requests[1].resolve({ data: [] });
  await retry;
  assert.equal(subject.appName, '');
  assert.equal(subject.appListError, false);
});

test('leaving the home page invalidates pending application data', async () => {
  const { subject, requests } = home();
  const pending = subject.getAppList();
  subject.beforeDestroy();
  requests[0].resolve({ data: [{ app_name: 'late' }] });
  await pending;
  assert.equal(subject.originalAppList.length, 0);
});

function serviceListSubject() {
  const requests = [];
  const metrics = [];
  const proto = methods(listFile, ['getServiceList', 'loadAsyncData', 'beforeDestroy'], {
    serviceList: () => {
      const request = deferred();
      requests.push(request);
      return request.promise;
    },
    serviceListAsync: () => {
      const request = deferred();
      metrics.push(request);
      return request.promise;
    },
    handleTransformToTimestamp: value => value,
    axios: { isCancel: error => error.cancelled, CancelToken: { source: () => ({ token: {}, cancel() {} }) } },
  });
  return {
    requests,
    metrics,
    subject: Object.assign(Object.create(proto), {
      appName: 'app',
      requestId: 0,
      timeRange: [1, 2],
      pagination: { current: 1, limit: 10 },
      tableData: [],
      tableColumns: [],
      filterLoading: true,
      listLoaded: false,
      cancelTokenSource: { token: {} },
      onRouteUrlChange() {},
      mapAsyncData() {},
    }),
  };
}

const listResponse = (name = 'service') => ({
  columns: [],
  data: [{ service_name: { value: name } }],
  total: 1,
  filter: [],
});

test('cancelled service request cannot end the replacement request loading', async () => {
  const { subject, requests } = serviceListSubject();
  const first = subject.getServiceList();
  const second = subject.getServiceList();
  requests[0].reject({ cancelled: true });
  await first;
  assert.equal(subject.loading, true);
  assert.equal(subject.listError, false);
  requests[1].resolve(listResponse());
  await second;
  assert.equal(subject.loading, false);
  assert.equal(subject.listLoaded, true);
  assert.equal(subject.filterLoading, false);
});

test('older service success cannot replace a newer result', async () => {
  const { subject, requests } = serviceListSubject();
  const first = subject.getServiceList();
  const second = subject.getServiceList();
  requests[1].resolve(listResponse('new'));
  await second;
  requests[0].resolve(listResponse('old'));
  await first;
  assert.equal(subject.tableData[0].service_name.value, 'new');
});

test('failed service refresh keeps rendered rows and releases loading', async () => {
  const { subject, requests } = serviceListSubject();
  subject.listLoaded = true;
  subject.tableData = listResponse('retained').data;
  const pending = subject.getServiceList();
  requests[0].reject(new Error('offline'));
  await pending;
  assert.equal(subject.tableData[0].service_name.value, 'retained');
  assert.equal(subject.listError, true);
  assert.equal(subject.loading, false);
});

test('async metric failures release column and filter skeletons', async () => {
  const { subject, metrics } = serviceListSubject();
  subject.tableColumns = [
    { id: 'trace_data_status', asyncable: true },
    { id: 'request_count', asyncable: true },
  ];
  const pending = subject.loadAsyncData(1, 2, 0);
  assert.equal(metrics.length, 2);
  metrics.forEach(request => request.reject(new Error('offline')));
  await pending;
  assert.equal(subject.filterLoading, false);
  assert.equal(
    subject.tableColumns.every(column => !column.asyncable),
    true
  );
});

test('late async metrics cannot mutate another application or finish its filter skeleton', async () => {
  const { subject, metrics } = serviceListSubject();
  subject.tableColumns = [{ id: 'trace_data_status', asyncable: true }];
  let mutations = 0;
  subject.mapAsyncData = () => mutations++;
  const pending = subject.loadAsyncData(1, 2, 0);
  subject.requestId++;
  metrics[0].resolve({ data: [] });
  await pending;
  assert.equal(mutations, 0);
  assert.equal(subject.filterLoading, true);
});

function keyboardSubject() {
  const proto = methods(
    homeFile,
    [
      'appList',
      'keyboardAppList',
      'keyboardActiveApp',
      'handleKeyboardAppListChange',
      'handleAppListKeydown',
      'handleAppClick',
    ],
    {
      authorityMap: { VIEW_AUTH: 'view' },
    }
  );
  return Object.assign(Object.create(proto), {
    originalAppList: ['alpha', 'blocked', 'beta', 'gamma'].map((name, index) => ({
      app_name: name,
      app_alias: name,
      application_id: index,
      permission: { view: name !== 'blocked' },
    })),
    searchCondition: '',
    appName: 'alpha',
    keyboardAppName: '',
    loading: false,
    appListLoaded: true,
    $refs: {},
    $nextTick: callback => callback(),
  });
}

function keyEvent(key, overrides = {}) {
  const target = {};
  return {
    key,
    target,
    currentTarget: target,
    prevented: false,
    stopped: false,
    preventDefault() {
      this.prevented = true;
    },
    stopPropagation() {
      this.stopped = true;
    },
    ...overrides,
  };
}

test('arrow navigation skips forbidden applications and Enter alone commits selection', () => {
  const subject = keyboardSubject();
  const down = keyEvent('ArrowDown');
  subject.handleAppListKeydown(down);
  assert.equal(subject.keyboardAppName, 'beta');
  assert.equal(subject.appName, 'alpha');
  assert.equal(down.prevented, true);
  assert.equal(down.stopped, true);
  subject.handleAppListKeydown(keyEvent('Enter'));
  assert.equal(subject.appName, 'beta');
});

test('application navigation stops at the first and last permitted rows', () => {
  const subject = keyboardSubject();
  subject.handleAppListKeydown(keyEvent('ArrowUp'));
  assert.equal(subject.keyboardAppName, 'alpha');
  for (let index = 0; index < 5; index++) subject.handleAppListKeydown(keyEvent('ArrowDown'));
  assert.equal(subject.keyboardAppName, 'gamma');
  subject.handleAppListKeydown(keyEvent('ArrowUp'));
  assert.equal(subject.keyboardAppName, 'beta');
  subject.handleAppListKeydown(keyEvent('ArrowUp'));
  assert.equal(subject.keyboardAppName, 'alpha');
});

test('filtered keyboard candidates use the current search results', () => {
  const subject = keyboardSubject();
  subject.keyboardAppName = 'beta';
  subject.searchCondition = 'gamma';
  subject.handleKeyboardAppListChange();
  assert.equal(subject.keyboardAppName, '');
  subject.handleAppListKeydown(keyEvent('Enter'));
  assert.equal(subject.appName, 'gamma');
});

test('without a selected search result down starts at the first row and up at the last', () => {
  const subject = keyboardSubject();
  subject.appName = 'missing';
  subject.handleAppListKeydown(keyEvent('ArrowDown'));
  assert.equal(subject.keyboardAppName, 'alpha');
  subject.keyboardAppName = '';
  subject.handleAppListKeydown(keyEvent('ArrowUp'));
  assert.equal(subject.keyboardAppName, 'gamma');
});

test('empty and forbidden-only results never select an application', () => {
  for (const searchCondition of ['missing', 'blocked']) {
    const subject = keyboardSubject();
    subject.searchCondition = searchCondition;
    for (const key of ['ArrowDown', 'ArrowUp', 'Enter']) {
      const event = keyEvent(key);
      subject.handleAppListKeydown(event);
      assert.equal(event.prevented, false);
      assert.equal(subject.appName, 'alpha');
    }
  }
});

test('permissions are rechecked before Enter confirms the highlighted row', () => {
  const subject = keyboardSubject();
  subject.handleAppListKeydown(keyEvent('ArrowDown'));
  subject.originalAppList.find(item => item.app_name === 'beta').permission.view = false;
  subject.handleAppListKeydown(keyEvent('Enter'));
  assert.equal(subject.appName, 'alpha');
});

test('composition, modifiers, other controls and unrelated keys retain their normal behavior', () => {
  for (const overrides of [
    { isComposing: true },
    { keyCode: 229 },
    { ctrlKey: true },
    { metaKey: true },
    { altKey: true },
    { shiftKey: true },
    { target: {} },
    { key: 'Tab' },
  ]) {
    const subject = keyboardSubject();
    const event = keyEvent('ArrowDown', overrides);
    subject.handleAppListKeydown(event);
    assert.equal(subject.keyboardAppName, '');
    assert.equal(event.prevented, false);
  }
});

test('initial loading and open dialogs disable application shortcuts', () => {
  for (const state of [
    { loading: true, appListLoaded: false },
    { isShowAppAdd: true },
    { isShowServiceAdd: true },
    { showGuideDialog: true },
  ]) {
    const subject = Object.assign(keyboardSubject(), state);
    const event = keyEvent('ArrowDown');
    subject.handleAppListKeydown(event);
    assert.equal(subject.keyboardAppName, '');
    assert.equal(event.prevented, false);
  }
});

test('keyboard highlighting only scrolls its own list enough to reveal the row', () => {
  const subject = keyboardSubject();
  let rect = { top: 210, bottom: 246 };
  const list = {
    scrollTop: 50,
    getBoundingClientRect: () => ({ top: 100, bottom: 220 }),
    querySelector: () => ({ getBoundingClientRect: () => rect }),
  };
  subject.$refs.appList = list;
  subject.handleAppListKeydown(keyEvent('ArrowDown'));
  assert.equal(list.scrollTop, 76);
  rect = { top: 90, bottom: 126 };
  subject.handleAppListKeydown(keyEvent('ArrowUp'));
  assert.equal(list.scrollTop, 66);
  rect = { top: 120, bottom: 156 };
  subject.handleAppListKeydown(keyEvent('ArrowDown'));
  assert.equal(list.scrollTop, 66);
});

test('entering APM Home enables arrow navigation without a prior click', () => {
  const proto = methods(homeFile, ['mounted'], { window: { requestIdleCallback() {} } });
  const subject = keyboardSubject();
  let focused = null;
  const page = {
    focus(options) {
      assert.equal(options.preventScroll, true);
      focused = page;
    },
  };
  const list = {
    focus(options) {
      assert.equal(options.preventScroll, true);
      focused = list;
    },
    querySelector: () => null,
  };
  subject.$el = page;
  subject.$refs.appList = list;
  proto.mounted.call(subject);
  assert.equal(focused, page);
  subject.handleAppListKeydown(keyEvent('ArrowDown', { target: page, currentTarget: page }));
  assert.equal(focused, list);
  assert.equal(subject.keyboardAppName, 'beta');
  assert.equal(subject.appName, 'alpha');
  subject.handleAppListKeydown(keyEvent('Enter', { target: list, currentTarget: list }));
  assert.equal(subject.appName, 'beta');
});

test('async cells use the home skeleton slot only while pending and preserve default loading for other consumers', () => {
  const proto = methods('src/monitor-pc/pages/monitor-k8s/components/common-table.tsx', ['handleSetFormatter'], {
    h: (tag, props) => ({ tag, props }),
    loadingIcon: 'spinner.svg',
  });
  const column = { id: 'request_count', type: 'number', asyncable: true };
  const row = { request_count: { value: 0 } };
  const subject = Object.assign(Object.create(proto), {
    columns: [column],
    $scopedSlots: {},
    numberFormatter: item => item.value,
  });
  assert.equal(subject.handleSetFormatter(column.id, row).tag, 'img');
  subject.$scopedSlots.asyncLoading = context => {
    assert.equal(context.column, column);
    assert.equal(context.row, row);
    return 'cell-skeleton';
  };
  assert.equal(subject.handleSetFormatter(column.id, row), 'cell-skeleton');
  column.asyncable = false;
  assert.equal(subject.handleSetFormatter(column.id, row), 0);
});
