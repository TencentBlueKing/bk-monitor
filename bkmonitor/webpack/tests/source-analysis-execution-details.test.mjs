import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const vue = createRequire(path.join(root, 'src/trace/package.json'))('vue');
const file =
  'src/trace/pages/alarm-center/alarm-issues/issues-detail/components/issues-ai-analysis/analysis-summary-card.tsx';
const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity) });
const nodes = tree => (tree && typeof tree === 'object' ? [tree, ...(tree.children || []).flatMap(nodes)] : []);
const detailButtons = tree =>
  nodes(tree).filter(node => node.type === 'Button' && node.children.includes('查看执行详情'));
const reference = {
  provider: 'bkci',
  identifiers: { project_id: 'project-a', pipeline_id: 'pipeline-a', build_id: 'build-a' },
  url: 'https://devops.example.com/console/pipeline/project-a/pipeline-a/detail/build-a/executeDetail',
};

function renderCard(latest, open = () => {}) {
  const dependencies = {
    vue,
    'bkui-vue': { Button: 'Button', Progress: 'Progress', PopConfirm: 'PopConfirm' },
    'vue-i18n': { useI18n: () => ({ t: value => value }) },
    dayjs: { default: { tz: () => ({ format: () => '' }) } },
    './analysis-summary-card.scss': {},
  };
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
  const module = { exports: {} };
  new Function('require', 'module', 'exports', 'h', 'window', compiled.outputText)(
    id => {
      assert.ok(Object.hasOwn(dependencies, id), `Unexpected dependency: ${id}`);
      return dependencies[id];
    },
    module,
    module.exports,
    h,
    { timezone: 'UTC', open }
  );
  const component = module.exports.default;
  const props = { sourceAnalysisData: { latest }, loading: { retryAnalysis: false, assigneeChange: false } };
  return component.render.call(vue.proxyRefs({ ...props, ...component.setup(props), $emit() {} }));
}

function analysis(resultType = 'HIGH_CONFIDENCE') {
  return {
    status: 'success',
    triggered_by: 'user-a',
    triggered_at: 1,
    execution_reference: reference,
    result: { result_type: resultType, result_card: { description: 'Example analysis', responsibility: null } },
  };
}

for (const resultType of ['HIGH_CONFIDENCE', 'INSUFFICIENT_EVIDENCE']) {
  test(`${resultType}: execution details remain available after reloading the result`, () => {
    const latest = analysis(resultType);
    for (const data of [latest, JSON.parse(JSON.stringify(latest))]) {
      const opened = [];
      const tree = renderCard(data, (...args) => opened.push(args));
      const buttons = detailButtons(tree);
      assert.equal(buttons.length, 1);
      buttons[0].props.onClick();
      assert.deepEqual(opened, [[reference.url, '_blank', 'noopener,noreferrer']]);
      assert.equal(nodes(tree).filter(node => node.children.includes('重新分析')).length, 1);
    }
  });
}

for (const executionReference of [undefined, null, { ...reference, url: null }, { ...reference, url: '' }]) {
  test(`missing execution URL hides the details button: ${JSON.stringify(executionReference)}`, () => {
    const latest = { ...analysis(), execution_reference: executionReference };
    assert.equal(detailButtons(renderCard(latest)).length, 0);
  });
}
