/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { loadScriptSetup } from './helpers/load-script-setup.mjs';

const source = readFileSync(
  new URL(
    '../src/features/collection/current/components/create-operation/step2-custom-report.tsx',
    import.meta.url,
  ),
  'utf8',
);
const style = readFileSync(
  new URL(
    '../src/features/collection/current/components/create-operation/step2-custom-report.scss',
    import.meta.url,
  ),
  'utf8',
);

test('custom report collection step uses native TDesign loading and always releases initialization state', () => {
  assert.match(source, /Loading as TLoading/);
  assert.match(source, /data-testid='collection-custom-report-loading'/);
  assert.match(source, /loading=\{loading\.value \|\| submitLoading\.value\}/);
  assert.match(source, /indicator=\{renderCollectionFormSkeleton\}/);
  assert.match(source, /showOverlay/);
  assert.match(source, /zIndex=\{Z_INDEX_LAYERS\.PAGE_TOP\}/);
  assert.match(source, /@\/shared\/ui\/loading\/native/);
  assert.doesNotMatch(source, /v-bkloading/);

  assert.match(source, /try \{/);
  assert.match(source, /finally \{\s*loading\.value = false;\s*isInitializing\.value = false;/);
  assert.match(style, /\.operation-step2-custom-report-loading/);
  assert.match(style, /background-color: rgba\(255, 255, 255, 0\.9\)/);
});

test('container status polling preserves collapsed groups when the response reorders them', async () => {
  const component = loadScriptSetup(
    new URL('../src/features/index-sets/log-collection/collection-item/manage-collection/components/container-status.vue', import.meta.url),
    {
      mapPiniaState: () => ({}),
      ServicesInstance: {
        collect: {
          getIssuedClusterList: async () => ({
            data: { contents: [2, 1, 3].map(collector_config_id => ({ collector_config_id, child: [] })) },
          }),
        },
      },
    },
  );
  const events = [];
  const vm = {
    ...component.data.call({ $t: text => text }),
    curCollect: { collector_config_id: 1 },
    renderTitleList: [{ collector_config_id: 1, isShowTable: false }, { collector_config_id: 2, isShowTable: true }],
    $emit: (...event) => events.push(event),
  };
  await component.methods.getContainerList.call(vm, 'polling');
  assert.deepEqual(vm.renderTitleList.map(group => [group.collector_config_id, group.isShowTable]), [
    [2, true], [1, false], [3, true],
  ]);
  assert.deepEqual(events, []);
});

test('refreshing sampled logs resets the expansion without changing an open report', () => {
  const component = loadScriptSetup(
    new URL('../src/features/index-sets/log-collection/collection-item/manage-collection/data-status/data-sampling.vue', import.meta.url),
    {},
  );
  const vm = component.data.call({ $t: text => text });
  const origin = { synthetic: 'sample' };
  component.methods.openReportedLog.call(vm, { origin });
  component.methods.showClick.call(vm, 2);
  assert.equal(vm.expandIndex, 2);
  component.methods.showClick.call(vm, 2);
  assert.equal(vm.expandIndex, -1);
  component.methods.showClick.call(vm, 1);
  component.watch.data.call(vm);
  assert.equal(vm.expandIndex, -1);
  assert.equal(vm.defaultSettings.isShow, true);
  assert.equal(vm.jsonText, origin);
});

test('sampling refresh keeps the last successful rows only for the same collector', async t => {
  t.mock.method(console, 'warn', () => {});
  const rows = [{ synthetic: 'first sample' }];
  const refreshed = [{ synthetic: 'refreshed sample' }];
  const responses = [rows, new Error('Synthetic failure'), refreshed, new Error('Synthetic failure')];
  const component = loadScriptSetup(
    new URL('../src/features/index-sets/log-collection/collection-item/manage-collection/data-status/index.vue', import.meta.url),
    {
      ServicesInstance: {
        source: {
          dataList: async () => {
            const data = responses.shift();
            if (data instanceof Error) throw data;
            return { data };
          },
        },
      },
    },
  );
  const vm = { ...component.data(), $route: { params: { collectorId: 'sample-a' } } };
  const fetch = () => component.methods.fetchDataSampling.call(vm);

  await fetch();
  assert.equal(vm.dataSamplingList, rows);
  await fetch();
  assert.equal(vm.dataSamplingFailed, true);
  assert.equal(vm.dataSamplingLoading, false);
  assert.equal(vm.dataSamplingList, rows);

  await fetch();
  assert.equal(vm.dataSamplingFailed, false);
  assert.equal(vm.dataSamplingList, refreshed);

  vm.$route.params.collectorId = 'sample-b';
  const next = fetch();
  assert.deepEqual(vm.dataSamplingList, []);
  await next;
  assert.equal(vm.dataSamplingFailed, true);
  assert.deepEqual(vm.dataSamplingList, []);
});

test('collection status distinguishes a failed request from a successful empty response', async () => {
  let fail = true;
  const component = loadScriptSetup(
    new URL('../src/features/index-sets/log-collection/collection-item/manage-collection/collection-status.vue', import.meta.url),
    {
      mapPiniaState: () => ({}),
      console: { warn() {} },
      window: { ENABLE_CHECK_COLLECTOR: 'false' },
      clearInterval,
      ServicesInstance: {
        source: {
          async collectList() {
            if (fail) throw new Error('Synthetic request failure');
            return { data: { contents: [] } };
          },
        },
      },
    },
  );
  const vm = {
    ...component.data.call({ $t: text => text }),
    ...component.methods,
    $route: { params: { collectorId: 'synthetic' } },
  };

  await vm.getCollectList();
  assert.equal(vm.statusFailed, true);
  assert.equal(vm.basicLoading, false);
  assert.equal(vm.reloadTable, false);
  assert.equal(vm.renderTableList.length, 0);

  fail = false;
  await vm.getCollectList();
  assert.equal(vm.statusFailed, false);
  assert.equal(vm.basicLoading, false);
  assert.equal(vm.reloadTable, false);
  assert.equal(vm.renderTableList.length, 0);
});
