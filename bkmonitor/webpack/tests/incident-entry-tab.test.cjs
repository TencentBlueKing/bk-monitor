const assert = require('node:assert/strict');
const test = require('node:test');
const { createHarness, deferred, flush, panels } = require('./helpers/incident-entry-harness.cjs');

test('short IDs wait for the canonical route before mounting or consuming the requested tab', async t => {
  const lookup = deferred();
  const navigation = deferred();
  const h = createHarness({
    id: '42',
    query: { activeTab: 'FailureTopo' },
    resolveId: lookup.promise,
    routeReady: navigation.promise,
  });
  t.after(h.unmount);
  await flush();
  assert.equal(h.vm.idResolving, true);
  assert.equal(h.vm.refContent, undefined);
  assert.equal(h.route.query.activeTab, 'FailureTopo');
  lookup.resolve({ id: '1700000000000042' });
  await flush();
  assert.equal(h.vm.idResolving, true);
  assert.equal(h.vm.refContent, undefined);
  assert.deepEqual(
    h.calls.api.map(item => item.name),
    ['resolve']
  );
  assert.equal(h.calls.replace.length, 1);
  assert.equal(h.calls.replace[0].query.activeTab, 'FailureTopo');
  navigation.resolve();
  await flush();
  assert.equal(h.route.params.id, '1700000000000042');
  assert.equal(h.vm.refContent.active, 'FailureTopo');
  assert.deepEqual(h.route.query, { from: 'now-7d', to: 'now', fromPage: 'alarm-center' });
  assert.equal(h.calls.api.find(item => item.name === 'detail').params.id, '1700000000000042');
});

test('a late content mount retains the deep link until it can actually select the tab', async t => {
  const h = createHarness({ query: { activeTab: 'FailureTopo' }, mountContent: false });
  t.after(h.unmount);
  await flush();
  assert.equal(h.vm.refContent, undefined);
  assert.equal(h.route.query.activeTab, 'FailureTopo');
  assert.equal(h.calls.replace.length, 0);
  h.contentMounted.value = true;
  await flush();
  assert.equal(h.vm.refContent.active, 'FailureTopo');
  assert.equal(h.route.query.activeTab, undefined);
});

for (const tab of ['FailureTopo', 'FailureView']) {
  test(`an explicit ${tab} wins over a later panel response`, async t => {
    const response = deferred();
    const h = createHarness({ query: { activeTab: tab }, results: response.promise });
    t.after(h.unmount);
    await flush();
    assert.equal(h.vm.refContent.active, tab);
    response.resolve(panels(tab !== 'FailureTopo'));
    await flush();
    assert.equal(h.vm.refContent.active, tab);
    assert.equal(h.route.query.activeTab, undefined);
  });
}

for (const query of [{}, { activeTab: '' }, { activeTab: 'unknown' }, { activeTab: 'FailureTiming' }]) {
  test(`missing or unsupported tabs preserve normal defaults: ${JSON.stringify(query)}`, async t => {
    const response = deferred();
    const h = createHarness({ query, results: response.promise });
    t.after(h.unmount);
    await flush();
    response.resolve(panels(true));
    await flush();
    assert.equal(h.vm.refContent.active, 'FailureTopo');
    if (query.activeTab) assert.equal(h.route.query.activeTab, undefined);
  });
}

test('repeated query values use the first tab and retain unrelated query fields', async t => {
  const h = createHarness({ query: { activeTab: ['FailureView', 'FailureTopo'], incident_task_id: '123' } });
  t.after(h.unmount);
  await flush();
  assert.equal(h.vm.refContent.active, 'FailureView');
  assert.equal(h.route.query.incident_task_id, '123');
  assert.equal(h.route.query.from, 'now-7d');
  assert.equal(h.route.query.activeTab, undefined);
});

test('no tab parameter still defaults to alerts when topology is unavailable', async t => {
  const h = createHarness({ results: panels(false) });
  t.after(h.unmount);
  await flush();
  assert.equal(h.vm.refContent.active, 'FailureView');
  assert.equal(h.calls.replace.length, 0);
});

test('an unsupported first array value does not select a later value or suppress defaults', async t => {
  const response = deferred();
  const h = createHarness({ query: { activeTab: ['unknown', 'FailureView'] }, results: response.promise });
  t.after(h.unmount);
  await flush();
  response.resolve(panels(true));
  await flush();
  assert.equal(h.vm.refContent.active, 'FailureTopo');
});

test('the existing alert-navigation callback remains an alert action', async t => {
  const h = createHarness({ query: { activeTab: 'FailureTopo' } });
  t.after(h.unmount);
  await flush();
  assert.equal(h.vm.refContent.active, 'FailureTopo');
  h.vm.failureNavRef.$emit('changeTab');
  await flush();
  assert.equal(h.vm.refContent.active, 'FailureView');
  h.vm.refContent.handleChangeActive('FailureTopo');
  h.vm.goAlertList({ ids: ['alert-1'] });
  await flush();
  assert.equal(h.vm.refContent.active, 'FailureView');
  assert.equal(h.vm.refContent.activeTab, 'AlarmDetail');
  assert.deepEqual(h.vm.refContent.alertIdsObject, { ids: ['alert-1'] });
});
