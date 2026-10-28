import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const vue = createRequire(path.join(root, 'src/trace/package.json'))('vue');
const file = 'src/trace/pages/ai-config/components/source-code-analysis/source-code-analysis.tsx';
const compiled = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
  fileName: file,
  reportDiagnostics: true,
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.React,
    jsxFactory: 'h',
  },
});
assert.equal(compiled.diagnostics.length, 0);
const flush = () => new Promise(resolve => setImmediate(resolve));
const savedConfig = { bkci_project_id: 'project-a', repository_alias: 'team/repository-a', updated_by: 'alice' };

function deferred() {
  let resolve;
  const promise = new Promise(yes => {
    resolve = yes;
  });
  return { promise, resolve };
}

function harness({ config = {}, getConfig = async () => config, save = async () => {} } = {}) {
  const mounted = [];
  const dialogs = [];
  const saves = [];
  const creates = [];
  let ruleQueries = 0;
  const selector = () => ({
    list: vue.shallowRef([]),
    loading: vue.shallowRef(false),
    nameMap: vue.shallowRef(new Map()),
    fetchDataInit() {},
    fetchList() {},
  });
  const dependencies = {
    vue: { ...vue, onMounted: callback => mounted.push(callback) },
    'bkui-vue': {
      Button: 'Button',
      Input: 'Input',
      Select: { Option: 'Option' },
      InfoBox: options => dialogs.push(options),
      Message() {},
    },
    'bkui-vue/lib/icon': { Plus: 'Plus' },
    'trace/directive/overflow-tips': {},
    'vue-i18n': { useI18n: () => ({ t: value => value }) },
    '../../composables/use-ai-resource-select': { useAiResourceSelect: selector },
    '../../composables/use-bkci-projects-select': { useBkciProjectsSelect: selector },
    '../../composables/use-bkci-repositories-select': { useBkciRepositoriesSelect: selector },
    '../../composables/use-match-rule-fields': {
      useMatchRuleFields: () => ({
        fields: vue.shallowRef([]),
        loading: vue.shallowRef(false),
        fetchAllData() {},
        fetchStrategyDimensions() {},
        getValueFn() {},
        tagValueDisplayFormatter() {},
      }),
    },
    '../../constants': { SidesliderTypeEnum: { ADD: 'add', EDIT: 'edit' } },
    '../../services/ai-config': {
      getSourceAnalysisConfigData: getConfig,
      setSaveSourceAnalysisConfig: async params => {
        saves.push({ ...params });
        await save(params);
        return { ...params, updated_by: 'alice' };
      },
    },
    '../../services/source-analysis-rule': {
      listSourceAnalysisRules: async () => {
        ruleQueries++;
        return [];
      },
      createSourceAnalysisRule: async params => {
        creates.push(params);
      },
    },
    '../analysis-config-sideslider/analysis-config-sideslider': {},
    '../analysis-rule-table/analysis-rule-table': {},
    './source-code-analysis.scss': {},
  };
  const module = { exports: {} };
  const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity) });
  new Function('require', 'module', 'exports', 'h', compiled.outputText)(
    id => {
      assert.ok(Object.hasOwn(dependencies, id), `Unexpected dependency: ${id}`);
      return dependencies[id];
    },
    module,
    module.exports,
    h
  );
  const component = module.exports.default;
  const state = component.setup({});
  mounted.forEach(callback => callback());
  const nodes = tree => (tree && typeof tree === 'object' ? [tree, ...(tree.children || []).flatMap(nodes)] : []);
  return {
    state,
    dialogs,
    saves,
    creates,
    get ruleQueries() {
      return ruleQueries;
    },
    button: () =>
      nodes(component.render.call(vue.proxyRefs(state))).find(node => node.props?.onClick === state.handleAddRule),
    saveButton: () =>
      nodes(component.render.call(vue.proxyRefs(state))).find(node => node.props?.onClick === state.handleSaveConfig),
    async confirm() {
      const dialog = dialogs.at(-1);
      const success = await dialog.beforeClose('confirm');
      if (success) dialog.onConfirm();
      return success;
    },
    async cancel() {
      const dialog = dialogs.at(-1);
      if (await dialog.beforeClose('cancel')) dialog.onCancel();
    },
  };
}

test('first configuration requires explicit save confirmation before opening the rule drawer', async () => {
  const h = harness();
  await flush();
  h.state.bkciProjectId.value = savedConfig.bkci_project_id;
  h.state.repositoryAlias.value = savedConfig.repository_alias;
  h.button().props.onClick();
  assert.equal(h.dialogs.length, 1);
  assert.equal(h.dialogs[0].confirmText, '保存并继续');
  assert.equal(h.saves.length, 0);
  assert.equal(h.state.showBindModal.value, false);
  assert.equal(h.button().props.disabled, true);
  assert.equal(await h.confirm(), true);
  assert.deepEqual(h.saves, [
    { bkci_project_id: savedConfig.bkci_project_id, repository_alias: savedConfig.repository_alias },
  ]);
  assert.equal(h.state.showBindModal.value, true);
  assert.equal(h.state.isEdited.value, false);
  assert.equal(h.state.saveConfirmVisible.value, false);
  assert.equal(h.ruleQueries, 2);
  assert.equal(h.creates.length, 0);
});

test('saved unchanged configuration opens directly without saving or prompting', async () => {
  const h = harness({ config: savedConfig });
  await flush();
  h.button().props.onClick();
  assert.equal(h.state.showBindModal.value, true);
  assert.equal(h.dialogs.length, 0);
  assert.equal(h.saves.length, 0);
  assert.equal(h.saveButton().props.disabled, true);
  assert.equal(await h.state.handleSaveConfig(), true);
  assert.equal(h.saves.length, 0);
});

test('saving repository configuration is disabled during initialization and enabled only for changes', async () => {
  const initial = deferred();
  const h = harness({ getConfig: () => initial.promise });
  assert.equal(h.saveButton().props.disabled, true);
  initial.resolve(savedConfig);
  await flush();
  assert.equal(h.saveButton().props.disabled, true);
  assert.ok(h.saveButton().children.includes('保存仓库配置'));
  h.state.repositoryAlias.value = 'team/changed';
  assert.equal(h.saveButton().props.disabled, false);
  await h.state.handleSaveConfig();
  assert.equal(h.saveButton().props.disabled, true);
});

test('legacy configuration without a repository owner must be initialized before adding rules', async () => {
  const h = harness({ config: { ...savedConfig, updated_by: 'unknown' } });
  await flush();
  assert.equal(h.state.isEdited.value, true);
  assert.equal(h.saveButton().props.disabled, false);
  h.state.handleAddRule();
  assert.equal(h.dialogs.length, 1);
  assert.equal(await h.confirm(), true);
  assert.equal(h.state.isEdited.value, false);
  assert.equal(h.saveButton().props.disabled, true);
});

test('editing either the saved project or repository requires confirmation', async () => {
  for (const field of ['bkciProjectId', 'repositoryAlias']) {
    const h = harness({ config: savedConfig });
    await flush();
    h.state[field].value = 'changed-value';
    h.state.handleAddRule();
    assert.equal(h.dialogs.length, 1);
    assert.equal(h.state.showBindModal.value, false);
    await h.confirm();
    assert.equal(h.state.showBindModal.value, true);
    assert.equal(h.saves[0][field === 'bkciProjectId' ? 'bkci_project_id' : 'repository_alias'], 'changed-value');
  }
});

test('cancel preserves unsaved input and allows the next attempt to prompt again', async () => {
  const h = harness({ config: savedConfig });
  await flush();
  h.state.repositoryAlias.value = 'team/changed';
  h.state.handleAddRule();
  await h.cancel();
  assert.equal(h.saves.length, 0);
  assert.equal(h.state.showBindModal.value, false);
  assert.equal(h.state.repositoryAlias.value, 'team/changed');
  assert.equal(h.state.isEdited.value, true);
  assert.equal(h.button().props.disabled, false);
  h.state.handleAddRule();
  assert.equal(h.dialogs.length, 2);
});

test('missing required fields show inline errors without opening or saving', async () => {
  const h = harness();
  await flush();
  h.state.handleAddRule();
  assert.equal(h.state.projectErrMsg.value, '必填项');
  assert.equal(h.state.repositoryErrMsg.value, '必填项');
  assert.equal(h.dialogs.length, 0);
  assert.equal(h.saves.length, 0);
  assert.equal(h.state.showBindModal.value, false);
  h.state.bkciProjectId.value = 'project-a';
  h.state.handleAddRule();
  assert.equal(h.state.projectErrMsg.value, '');
  assert.equal(h.state.repositoryErrMsg.value, '必填项');
});

test('failed save retains the confirmation and input; retry succeeds without duplicate dialogs', async () => {
  let fail = true;
  const h = harness({
    config: savedConfig,
    save: async () => {
      if (fail) throw new Error('save failed');
    },
  });
  await flush();
  h.state.repositoryAlias.value = 'team/changed';
  h.state.handleAddRule();
  assert.equal(await h.confirm(), false);
  assert.equal(h.state.showBindModal.value, false);
  assert.equal(h.state.saveLoading.value, false);
  assert.equal(h.state.saveConfirmVisible.value, true);
  assert.equal(h.state.repositoryAlias.value, 'team/changed');
  h.state.handleAddRule();
  assert.equal(h.dialogs.length, 1);
  fail = false;
  assert.equal(await h.confirm(), true);
  assert.equal(h.state.showBindModal.value, true);
});

test('initial loading and pending saves prevent duplicate add, confirm and cancel operations', async () => {
  const initial = deferred();
  const saving = deferred();
  const h = harness({ getConfig: () => initial.promise, save: () => saving.promise });
  assert.equal(h.button().props.disabled, true);
  h.state.handleAddRule();
  assert.equal(h.dialogs.length, 0);
  initial.resolve(savedConfig);
  await flush();
  h.state.repositoryAlias.value = 'team/changed';
  h.state.handleAddRule();
  const confirmation = h.confirm();
  assert.equal(h.button().props.disabled, true);
  h.state.handleAddRule();
  assert.equal(await h.confirm(), false);
  assert.equal(await h.state.handleSaveConfig(), false);
  await h.cancel();
  assert.equal(h.dialogs.length, 1);
  assert.equal(h.saves.length, 1);
  assert.equal(h.state.saveConfirmVisible.value, true);
  saving.resolve();
  assert.equal(await confirmation, true);
  assert.equal(h.state.showBindModal.value, true);
});

test('saving snapshots submitted values rather than edits made during the request', async () => {
  const saving = deferred();
  const h = harness({ config: savedConfig, save: () => saving.promise });
  await flush();
  h.state.repositoryAlias.value = 'team/submitted';
  const request = h.state.handleSaveConfig();
  h.state.repositoryAlias.value = 'team/not-saved';
  saving.resolve();
  assert.equal(await request, true);
  assert.equal(h.state.isEdited.value, true);
  h.state.handleAddRule();
  assert.equal(h.dialogs.length, 1);
  assert.equal(h.state.showBindModal.value, false);
});
