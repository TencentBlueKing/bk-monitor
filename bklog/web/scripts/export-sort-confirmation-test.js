/* Run: node scripts/export-sort-confirmation-test.js */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const cloneDeep = require('lodash/cloneDeep');
const { parseComponent } = require('vue/compiler-sfc');

const root = path.resolve(__dirname, '../src/views/retrieve-v2/result-comp');
function loadSource(source, filename, dependencies) {
  const output = ts.transpileModule(source, {
    compilerOptions: { allowJs: true, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    fileName: filename,
  });
  const exports = {};
  vm.runInNewContext(
    output.outputText,
    {
      exports,
      require: id => dependencies[id] ?? {},
      console: {
        ...console,
        error: (...args) => assert.fail(`unexpected component error: ${args.join(' ')}`),
        log: (...args) => assert.fail(`unexpected component log: ${args.join(' ')}`),
      },
      setTimeout,
      clearTimeout,
    },
    { filename },
  );
  return exports;
}
const task = loadSource(fs.readFileSync(path.join(root, 'download/exportTask.ts'), 'utf8'), 'exportTask.ts', {
  'lodash-es': { cloneDeep },
});
const { submitExportWithSortConfirmation, buildExportRetryRequest } = task;
const proposal = {
  result: true,
  data: {
    engine: 'sharded',
    requires_sort_confirmation: true,
    sort_list: [
      ['time', 'desc'],
      ['duration', 'asc'],
      ['level', 'desc'],
    ],
  },
};
const success = { result: true, data: { engine: 'sharded', task_id: 123 } };

function context(responses, action = 'confirmFn') {
  const requests = [];
  const dialogs = [];
  const messages = [];
  return {
    requests,
    dialogs,
    messages,
    $bkMessage: message => messages.push(message),
    $t: (text, values = {}) => text.replace('{sort}', values.sort ?? ''),
    $http: {
      request: async (url, config) => {
        requests.push({ url, config: cloneDeep(config) });
        const response = responses.shift();
        if (response instanceof Error) throw response;
        assert.ok(response, 'unexpected extra request');
        return cloneDeep(response);
      },
    },
    $bkInfo: options => {
      dialogs.push(options);
      options[action]();
      options.afterLeaveFn();
    },
  };
}

async function run() {
  let count = 0;
  const waiting = context([proposal, success]);
  waiting.$bkInfo = options => waiting.dialogs.push(options);
  const pending = submitExportWithSortConfirmation(waiting, 'retrieve/exportAsync', { data: {} });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(waiting.requests.length, 1, 'must wait for explicit confirmation before creation');
  waiting.dialogs[0].confirmFn();
  assert.equal((await pending).data.task_id, 123);
  assert.equal(waiting.requests.length, 2);
  count++;
  for (const action of ['cancelFn', 'closeFn', 'afterLeaveFn']) {
    const ctx = context([proposal], action);
    const result = await submitExportWithSortConfirmation(ctx, 'retrieve/exportAsync', {
      data: { sort_list: [['duration', 'asc']] },
    });
    assert.equal(result, null);
    assert.equal(ctx.requests.length, 1, 'cancel must not issue a creation request');
    count++;
  }
  for (const url of ['retrieve/exportAsync', 'retrieve/unionExportAsync', 'retrieve/getSceneAsyncExport']) {
    const config = {
      params: { index_set_id: 7 },
      data: {
        sort_list: [
          ['duration', 'asc'],
          ['time', 'asc'],
          ['level', 'desc'],
        ],
        export_fields: ['message'],
        keyword: 'error',
        start_time: 1,
        end_time: 2,
        addition: [{ key: 'x' }],
        is_desensitize: true,
      },
    };
    const before = cloneDeep(config);
    const ctx = context([proposal, success]);
    const result = await submitExportWithSortConfirmation(ctx, url, config);
    assert.equal(result.data.task_id, 123);
    assert.equal(ctx.requests.length, 2);
    assert.deepEqual(ctx.requests[1], {
      url,
      config: {
        ...before,
        data: { ...before.data, sort_list: proposal.data.sort_list, supports_sort_confirmation: true },
      },
    });
    assert.deepEqual(config, before, 'must not mutate page search params');
    assert.ok(ctx.dialogs[0].subTitle.includes('time 降序 → duration 升序 → level 降序'));
    count++;
  }
  for (const response of [success, { result: true, data: { task_id: 1 } }, { result: false, message: 'denied' }]) {
    const ctx = context([response]);
    await submitExportWithSortConfirmation(ctx, 'retrieve/exportAsync', {
      data: {
        sort_list: [
          ['time', 'asc'],
          ['duration', 'desc'],
        ],
      },
    });
    assert.equal(ctx.requests.length, 1);
    assert.equal(ctx.dialogs.length, 0, 'unchanged time-primary or legacy export must not prompt');
    count++;
  }
  const stale = context([proposal, proposal]);
  assert.equal(await submitExportWithSortConfirmation(stale, 'retrieve/exportAsync', { data: {} }), null);
  assert.equal(stale.requests.length, 2);
  assert.equal(stale.messages.length, 1);
  assert.equal(stale.messages[0].theme, 'error');
  assert.equal(stale.messages[0].message, '导出排序已变化，请重新提交并确认');
  count++;
  const failed = context([new Error('network failed')]);
  await assert.rejects(
    submitExportWithSortConfirmation(failed, 'retrieve/exportAsync', { data: {} }),
    /network failed/,
  );
  assert.equal(failed.dialogs.length, 0);
  assert.equal(failed.messages.length, 0, 'API failures must not get a duplicate helper toast');
  count++;
  const secondFailed = context([proposal, new Error('network failed')]);
  await assert.rejects(
    submitExportWithSortConfirmation(secondFailed, 'retrieve/exportAsync', { data: {} }),
    /network failed/,
  );
  assert.equal(secondFailed.messages.length, 0, 'second-request API failures use the existing global handler');
  count++;
  const sfc = parseComponent('<template><div>script</div></template><script lang="ts">export default {};</script>');
  assert.equal(sfc.script.content, 'export default {};');
  assert.equal(sfc.script.lang, 'ts');
  count++;

  const history = {
    id: 9,
    engine: 'sharded',
    index_set_type: 'single',
    log_index_set_id: 7,
    search_dict: { sort_list: [['duration', 'asc']], keyword: '*' },
  };
  const originalHistory = cloneDeep(history);
  const request = buildExportRetryRequest(history);
  const ctx = context([proposal, success]);
  await submitExportWithSortConfirmation(ctx, request.url, request.config);
  assert.deepEqual(history, originalHistory, 'retry must not mutate historical search params');
  assert.deepEqual(ctx.requests[1].config.data.sort_list, proposal.data.sort_list);
  count++;

  // Execute the real Vue methods with side effects mocked; do not duplicate their implementation.
  for (const componentName of ['export-log.vue', 'export-history.vue']) {
    const { script } = parseComponent(fs.readFileSync(path.join(root, componentName), 'utf8'));
    assert.ok(script, `${componentName} must have a script block`);
    const component = loadSource(script.content, componentName, {
      vuex: { mapState: () => ({}), mapGetters: () => ({}) },
      './download/exportTask': task,
    }).default;
    if (componentName === 'export-log.vue') {
      for (const mode of ['single', 'union', 'scene']) {
        const ctx = Object.assign(context([proposal, success]), {
          retrieveParams: { sort_list: [['duration', 'asc']], keyword: '*' },
          isScene: mode === 'scene',
          isUnionSearch: mode === 'union',
          bkBizId: 2,
          routerIndexSet: 7,
          unionIndexList: [7, 8],
          totalCount: 1000000,
          submitSelectFiledList: ['message'],
          desensitizeRadioType: 'desensitize',
          $bkMessage: () => {},
          fetchCurrentTasks: () => {},
          isShowExportDialog: true,
        });
        await component.methods.downloadAsync.call(ctx);
        assert.equal(ctx.requests.length, 2);
        assert.equal(ctx.isShowExportDialog, false);
        assert.equal(ctx.exportLoading, false);
        count++;
        const staleCtx = {
          ...ctx,
          ...context([proposal, proposal]),
          isShowExportDialog: true,
          fetchCurrentTasks: () => assert.fail('stale sort must not refresh tasks'),
        };
        await component.methods.downloadAsync.call(staleCtx);
        assert.equal(staleCtx.requests.length, 2);
        assert.equal(staleCtx.messages.length, 1, 'stale sort must show exactly one error, not success');
        assert.equal(staleCtx.messages[0].theme, 'error');
        assert.equal(staleCtx.isShowExportDialog, true);
        assert.equal(staleCtx.exportLoading, false);
        count++;
      }
      const ctx = Object.assign(context([proposal], 'cancelFn'), {
        retrieveParams: { sort_list: [['duration', 'asc']] },
        bkBizId: 2,
        routerIndexSet: 7,
        totalCount: 1000000,
        submitSelectFiledList: ['message'],
        desensitizeRadioType: 'desensitize',
        isShowExportDialog: true,
        $bkMessage: () => assert.fail('cancel must not show success'),
      });
      await component.methods.downloadAsync.call(ctx);
      assert.equal(ctx.isShowExportDialog, true, 'cancel keeps the export form open');
      assert.equal(ctx.exportLoading, false);
      count++;
      const retryCtx = Object.assign(context([proposal], 'cancelFn'), {
        failedTaskIds: ['sharded:9'],
        $bkMessage: () => assert.fail('cancel must not show success'),
        fetchCurrentTasks: () => assert.fail('cancel must not refresh tasks'),
      });
      await component.methods.handleRetryExport.call(retryCtx, history);
      assert.equal(retryCtx.requests.length, 1);
      assert.equal(retryCtx.dialogs.length, 1);
      assert.deepEqual(retryCtx.failedTaskIds, ['sharded:9'], 'cancel must not hide failed task');
      count++;
      const staleRetryCtx = Object.assign(context([proposal, proposal]), {
        failedTaskIds: ['sharded:9'],
        fetchCurrentTasks: () => assert.fail('stale sort must not refresh tasks'),
      });
      await component.methods.handleRetryExport.call(staleRetryCtx, history);
      assert.equal(staleRetryCtx.requests.length, 2);
      assert.equal(staleRetryCtx.messages.length, 1);
      assert.equal(staleRetryCtx.messages[0].theme, 'error');
      assert.deepEqual(staleRetryCtx.failedTaskIds, ['sharded:9']);
      count++;
    } else {
      const ctx = Object.assign(context([proposal], 'cancelFn'), {
        $bkMessage: () => assert.fail('cancel must not show success'),
        refreshAfterDownload: () => {},
      });
      assert.equal(await component.methods.downloadAsync.call(ctx, history), false);
      assert.equal(ctx.requests.length, 1);
      count++;
      const staleCtx = Object.assign(context([proposal, proposal]), { refreshAfterDownload: () => {} });
      assert.equal(await component.methods.downloadAsync.call(staleCtx, history), false);
      assert.equal(staleCtx.requests.length, 2);
      assert.equal(staleCtx.messages.length, 1);
      assert.equal(staleCtx.messages[0].theme, 'error');
      count++;
    }
  }
  console.log(`PASS: ${count} export sort confirmation cases (production helper and Vue methods)`);
}
run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
