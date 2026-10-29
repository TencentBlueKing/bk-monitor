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

function harness({
  config = {},
  getConfig = async () => config,
  getProjects = async () => ({ list: [], total: 0 }),
  getRepositories = async () => ({ list: [], total: 0 }),
  save = async () => {},
} = {}) {
  const mounted = [];
  const dialogs = [];
  const saves = [];
  const creates = [];
  const aiSelectors = [];
  const projectQueries = [];
  const repositoryQueries = [];
  let ruleQueries = 0;
  const services = loadComposable('src/trace/pages/ai-config/services/ai-config.ts', {
    'monitor-api/modules/aiops': {},
    'monitor-api/modules/issue': {
      listSourceAnalysisBkciProjects: getProjects,
      listSourceAnalysisBkciRepositories: getRepositories,
    },
    'monitor-api/modules/strategies': {},
  });
  const bkciDependencies = {
    vue,
    '../services/ai-config': {
      getBkciProjects: params => {
        projectQueries.push({ ...params });
        return services.getBkciProjects(params);
      },
      getBkciRepositories: params => {
        repositoryQueries.push({ ...params });
        return services.getBkciRepositories(params);
      },
    },
  };
  const selector = () => ({
    list: vue.shallowRef([]),
    loading: vue.shallowRef(false),
    nameMap: vue.shallowRef(new Map()),
    fetchDataInit() {},
    fetchList() {},
    reset() {},
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
    '../../composables/use-ai-resource-select': {
      useAiResourceSelect: () => {
        const select = selector();
        select.fetchCount = 0;
        select.resetCount = 0;
        select.fetchList = () => select.fetchCount++;
        select.reset = () => select.resetCount++;
        aiSelectors.push(select);
        return select;
      },
    },
    '../../composables/use-bkci-projects-select': loadComposable(
      'src/trace/pages/ai-config/composables/use-bkci-projects-select.ts',
      bkciDependencies
    ),
    '../../composables/use-bkci-repositories-select': loadComposable(
      'src/trace/pages/ai-config/composables/use-bkci-repositories-select.ts',
      bkciDependencies
    ),
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
    aiSelectors,
    projectQueries,
    repositoryQueries,
    selects: () =>
      nodes(component.render.call(vue.proxyRefs(state))).filter(node => node.type === dependencies['bkui-vue'].Select),
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

function loadComposable(file, dependencies) {
  const compiled = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    fileName: file,
    reportDiagnostics: true,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  assert.equal(compiled.diagnostics.length, 0);
  const module = { exports: {} };
  new Function('require', 'module', 'exports', compiled.outputText)(
    id => {
      assert.ok(Object.hasOwn(dependencies, id), `Unexpected composable dependency: ${id}`);
      return dependencies[id];
    },
    module,
    module.exports
  );
  return module.exports;
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

test('saved binding renders independently without querying the current editors candidates', async () => {
  const h = harness({ config: savedConfig });
  await flush();
  assert.equal(h.state.bkciProjectId.value, savedConfig.bkci_project_id);
  assert.equal(h.state.repositoryAlias.value, savedConfig.repository_alias);
  assert.equal(h.selects()[0].children[0].tag(), savedConfig.bkci_project_id);
  assert.equal(h.selects()[1].children[0].tag(), savedConfig.repository_alias);
  assert.deepEqual(h.projectQueries, []);
  assert.deepEqual(h.repositoryQueries, []);
  assert.equal(h.state.isEdited.value, false);
  assert.ok(h.aiSelectors.every(select => select.fetchCount === 1));
});

test('editor candidates exclude an inaccessible saved binding without changing its owner or value', async () => {
  const projects = [{ id: 'project-b', name: 'Editor B project' }];
  const h = harness({ config: savedConfig, getProjects: async () => ({ list: projects, total: 1 }) });
  await flush();
  await h.state.handleProjectsToggle(true);
  assert.deepEqual(h.state.bkciProjects.value, projects);
  assert.deepEqual(h.projectQueries, [{}]);
  await h.state.handleRepositoriesToggle(true);
  assert.deepEqual(h.repositoryQueries, []);
  assert.deepEqual(h.state.bkciRepositories.value, []);
  assert.equal(h.state.bkciProjectId.value, savedConfig.bkci_project_id);
  assert.equal(h.state.repositoryAlias.value, savedConfig.repository_alias);
  assert.equal(h.state.isEdited.value, false);
  assert.equal(await h.state.handleSaveConfig(), true);
  assert.deepEqual(h.saves, []);
  assert.ok(h.aiSelectors.every(select => select.fetchCount === 1));
});

test('repository candidates use the editors visible project without dropping an inaccessible saved repository', async () => {
  const repositories = [{ id: 'team/editor-repository', name: 'Editor repository' }];
  const h = harness({
    config: savedConfig,
    getProjects: async () => ({ list: [{ id: savedConfig.bkci_project_id, name: 'Shared project' }], total: 1 }),
    getRepositories: async () => ({ list: repositories, total: 1 }),
  });
  await flush();
  await h.state.handleRepositoriesToggle(true);
  assert.deepEqual(h.repositoryQueries, [{ bkci_project_id: savedConfig.bkci_project_id }]);
  assert.deepEqual(h.state.bkciRepositories.value, repositories);
  assert.equal(h.selects()[0].children[0].tag(), 'Shared project');
  assert.equal(h.selects()[1].children[0].tag(), savedConfig.repository_alias);
  assert.equal(h.state.isEdited.value, false);
  h.state.handleChangeBkciProjectId(savedConfig.bkci_project_id);
  assert.equal(h.state.repositoryAlias.value, savedConfig.repository_alias);
});

test('selecting the editors project loads only its candidates and does not change AIDEV identity before saving', async () => {
  const h = harness({
    config: savedConfig,
    getProjects: async () => ({ list: [{ id: 'project-b', name: 'Editor B project' }], total: 1 }),
    getRepositories: async () => ({ list: [{ id: 'team/b', name: 'B repository' }], total: 1 }),
  });
  await flush();
  h.state.handleChangeBkciProjectId('project-b');
  assert.equal(h.state.repositoryAlias.value, '');
  assert.deepEqual(h.repositoryQueries, []);
  await h.state.handleRepositoriesToggle(true);
  assert.deepEqual(h.repositoryQueries, [{ bkci_project_id: 'project-b' }]);
  assert.equal(h.state.isEdited.value, true);
  assert.ok(h.aiSelectors.every(select => select.fetchCount === 1));
});

test('concurrent project and repository dropdowns await the same current-user project request', async () => {
  const projects = deferred();
  const h = harness({ config: savedConfig, getProjects: () => projects.promise });
  await flush();
  const first = h.state.handleProjectsToggle(true);
  const second = h.state.handleRepositoriesToggle(true);
  assert.equal(h.projectQueries.length, 1);
  projects.resolve({ list: [{ id: savedConfig.bkci_project_id, name: 'Shared project' }], total: 1 });
  await Promise.all([first, second]);
  assert.deepEqual(h.repositoryQueries, [{ bkci_project_id: savedConfig.bkci_project_id }]);
  assert.equal(h.state.repositoryAlias.value, savedConfig.repository_alias);
});

test('late responses from a previous project cannot overwrite current repository candidates', async () => {
  const previous = deferred();
  const current = deferred();
  const h = harness({
    config: savedConfig,
    getProjects: async () => ({
      list: [
        { id: 'project-a', name: 'A' },
        { id: 'project-b', name: 'B' },
      ],
      total: 2,
    }),
    getRepositories: params => (params.bkci_project_id === 'project-a' ? previous.promise : current.promise),
  });
  await flush();
  const first = h.state.handleRepositoriesToggle(true);
  await flush();
  h.state.handleChangeBkciProjectId('project-b');
  const second = h.state.handleRepositoriesToggle(true);
  await flush();
  previous.resolve({ list: [{ id: 'team/a', name: 'A' }], total: 1 });
  await first;
  assert.deepEqual(h.state.bkciRepositories.value, []);
  assert.equal(h.state.repositoriesLoading.value, true);
  current.resolve({ list: [{ id: 'team/b', name: 'B' }], total: 1 });
  await second;
  assert.deepEqual(h.state.bkciRepositories.value, [{ id: 'team/b', name: 'B' }]);
  assert.equal(h.state.repositoriesLoading.value, false);
});

test('empty current-user candidate responses preserve the saved binding', async () => {
  const h = harness({ config: savedConfig });
  await flush();
  await h.state.handleProjectsToggle(true);
  await h.state.handleRepositoriesToggle(true);
  assert.deepEqual(h.state.bkciProjects.value, []);
  assert.deepEqual(h.state.bkciRepositories.value, []);
  assert.equal(h.state.bkciProjectId.value, savedConfig.bkci_project_id);
  assert.equal(h.state.repositoryAlias.value, savedConfig.repository_alias);
  assert.equal(h.state.isEdited.value, false);
});

test('reopening dropdowns reuses successfully loaded projects and repositories', async () => {
  const h = harness({
    config: savedConfig,
    getProjects: async () => ({ list: [{ id: 'project-a', name: 'A' }], total: 1 }),
    getRepositories: async () => ({ list: [{ id: 'team/a', name: 'A repository' }], total: 1 }),
  });
  await flush();
  await h.state.handleProjectsToggle(true);
  await h.state.handleProjectsToggle(false);
  await h.state.handleProjectsToggle(true);
  await h.state.handleRepositoriesToggle(true);
  await h.state.handleRepositoriesToggle(false);
  await h.state.handleRepositoriesToggle(true);
  assert.equal(h.projectQueries.length, 1);
  assert.equal(h.repositoryQueries.length, 1);
  assert.equal(h.state.repositoriesLoading.value, false);
});

test('successfully loaded empty project and repository lists are cached', async () => {
  const emptyProjects = harness({ config: savedConfig });
  await flush();
  await emptyProjects.state.handleProjectsToggle(true);
  await emptyProjects.state.handleProjectsToggle(true);
  await emptyProjects.state.handleRepositoriesToggle(true);
  assert.equal(emptyProjects.projectQueries.length, 1);
  assert.equal(emptyProjects.repositoryQueries.length, 0);

  const emptyRepositories = harness({
    config: savedConfig,
    getProjects: async () => ({ list: [{ id: 'project-a', name: 'A' }], total: 1 }),
  });
  await flush();
  await emptyRepositories.state.handleRepositoriesToggle(true);
  await emptyRepositories.state.handleRepositoriesToggle(true);
  assert.equal(emptyRepositories.projectQueries.length, 1);
  assert.equal(emptyRepositories.repositoryQueries.length, 1);
  assert.equal(emptyRepositories.state.repositoryAlias.value, savedConfig.repository_alias);
});

test('repository loading covers project lookup and repository lookup without displaying no data', async () => {
  const projects = deferred();
  const repositories = deferred();
  const h = harness({
    config: savedConfig,
    getProjects: () => projects.promise,
    getRepositories: () => repositories.promise,
  });
  await flush();
  const loading = h.state.handleRepositoriesToggle(true);
  const assertLoading = () => {
    const dropdown = h.selects()[1];
    assert.equal(dropdown.props.loading, true);
    assert.equal(dropdown.props.customContent, true);
    assert.equal(dropdown.props.noDataText, '加载中...');
  };
  assertLoading();
  assert.equal(h.repositoryQueries.length, 0);
  projects.resolve({ list: [{ id: 'project-a', name: 'A' }], total: 1 });
  await flush();
  assertLoading();
  assert.equal(h.repositoryQueries.length, 1);
  repositories.resolve({ list: [], total: 0 });
  await loading;
  assert.equal(h.selects()[1].props.loading, false);
  assert.equal(h.selects()[1].props.noDataText, '无数据');
});

test('failed project lookup is handled and retried instead of caching a successful empty result', async () => {
  let attempt = 0;
  const h = harness({
    config: savedConfig,
    getProjects: async () => {
      if (++attempt === 1) throw new Error('Project lookup failed');
      return { list: [{ id: 'project-a', name: 'A' }], total: 1 };
    },
  });
  await flush();
  await assert.doesNotReject(h.state.handleRepositoriesToggle(true));
  assert.equal(h.projectQueries.length, 1);
  assert.equal(h.repositoryQueries.length, 0);
  assert.equal(h.state.repositoriesLoading.value, false);
  assert.equal(h.state.isEdited.value, false);
  await h.state.handleRepositoriesToggle(true);
  assert.equal(h.projectQueries.length, 2);
  assert.equal(h.repositoryQueries.length, 1);
  assert.equal(h.state.repositoryAlias.value, savedConfig.repository_alias);
});

test('failed repository lookup is handled and retried without reloading projects', async () => {
  let attempt = 0;
  const h = harness({
    config: savedConfig,
    getProjects: async () => ({ list: [{ id: 'project-a', name: 'A' }], total: 1 }),
    getRepositories: async () => {
      if (++attempt === 1) throw new Error('Repository lookup failed');
      return { list: [{ id: 'team/a', name: 'A repository' }], total: 1 };
    },
  });
  await flush();
  await assert.doesNotReject(h.state.handleRepositoriesToggle(true));
  assert.equal(h.state.repositoriesLoading.value, false);
  await h.state.handleRepositoriesToggle(true);
  await h.state.handleRepositoriesToggle(true);
  assert.equal(h.projectQueries.length, 1);
  assert.equal(h.repositoryQueries.length, 2);
  assert.deepEqual(h.state.bkciRepositories.value, [{ id: 'team/a', name: 'A repository' }]);
});

test('synchronous request errors release pending requests so both selectors remain retryable', async () => {
  let projectAttempt = 0;
  let repositoryAttempt = 0;
  const h = harness({
    config: savedConfig,
    getProjects: () => {
      if (++projectAttempt === 1) throw new Error('Synchronous project error');
      return Promise.resolve({ list: [{ id: 'project-a', name: 'A' }], total: 1 });
    },
    getRepositories: () => {
      if (++repositoryAttempt === 1) throw new Error('Synchronous repository error');
      return Promise.resolve({ list: [], total: 0 });
    },
  });
  await flush();
  await h.state.handleRepositoriesToggle(true);
  await h.state.handleRepositoriesToggle(true);
  await h.state.handleRepositoriesToggle(true);
  assert.equal(projectAttempt, 2);
  assert.equal(repositoryAttempt, 2);
  assert.equal(h.state.repositoriesLoading.value, false);
});

test('concurrent repository opens share both in-flight requests', async () => {
  const repositories = deferred();
  const h = harness({
    config: savedConfig,
    getProjects: async () => ({ list: [{ id: 'project-a', name: 'A' }], total: 1 }),
    getRepositories: () => repositories.promise,
  });
  await flush();
  const first = h.state.handleRepositoriesToggle(true);
  await flush();
  const second = h.state.handleRepositoriesToggle(true);
  await flush();
  assert.equal(h.projectQueries.length, 1);
  assert.equal(h.repositoryQueries.length, 1);
  assert.equal(h.state.repositoriesLoading.value, true);
  repositories.resolve({ list: [], total: 0 });
  await Promise.all([first, second]);
  assert.equal(h.state.repositoriesLoading.value, false);
});

test('changing project invalidates repository cache but retains the current users project cache', async () => {
  const h = harness({
    config: savedConfig,
    getProjects: async () => ({
      list: [
        { id: 'project-a', name: 'A' },
        { id: 'project-b', name: 'B' },
      ],
      total: 2,
    }),
  });
  await flush();
  await h.state.handleRepositoriesToggle(true);
  h.state.handleChangeBkciProjectId('project-b');
  await h.state.handleRepositoriesToggle(true);
  await h.state.handleRepositoriesToggle(true);
  assert.equal(h.projectQueries.length, 1);
  assert.deepEqual(h.repositoryQueries, [{ bkci_project_id: 'project-a' }, { bkci_project_id: 'project-b' }]);
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
  assert.equal(h.state.isEdited.value, false);
  assert.equal(h.state.needsOwnerInit.value, true);
  assert.equal(h.saveButton().props.disabled, false);
  h.state.handleAddRule();
  assert.equal(h.dialogs.length, 1);
  assert.equal(h.dialogs[0].title, '仓库配置缺少执行人，是否使用当前用户初始化？');
  assert.equal(await h.confirm(), true);
  assert.equal(h.state.isEdited.value, false);
  assert.equal(h.state.needsOwnerInit.value, false);
  assert.equal(h.saveButton().props.disabled, true);
});

test('missing execution owner is not a dirty form and does not require saving to leave', async () => {
  for (const updated_by of ['', null, 'unknown']) {
    const h = harness({ config: { ...savedConfig, updated_by } });
    await flush();
    assert.equal(h.state.isEdited.value, false);
    assert.equal(h.state.needsOwnerInit.value, true);
    assert.equal(h.saves.length, 0);
    h.state.repositoryAlias.value = 'changed';
    assert.equal(h.state.isEdited.value, true);
  }
});

test('resource options load after repository identity and reset after saving a changed binding', async () => {
  const initial = deferred();
  const h = harness({ getConfig: () => initial.promise });
  assert.ok(h.aiSelectors.every(select => select.fetchCount === 0));
  initial.resolve(savedConfig);
  await flush();
  assert.ok(h.aiSelectors.every(select => select.fetchCount === 1));
  h.state.agentNameMap.value.set('old-agent', 'Old Identity Agent');
  h.state.repositoryAlias.value = 'team/changed';
  await h.state.handleSaveConfig();
  assert.ok(h.aiSelectors.every(select => select.fetchCount === 2 && select.resetCount === 2));
  assert.equal(h.state.agentNameMap.value.size, 0);
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
