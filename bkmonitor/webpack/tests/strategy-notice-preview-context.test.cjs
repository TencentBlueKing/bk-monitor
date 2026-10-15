const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.join(__dirname, '../src/monitor-pc/pages/strategy-config');
const source = file => ts.createSourceFile(file, fs.readFileSync(path.join(root, file), 'utf8'),
  ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const compile = (code, dependencies = {}) => new Function(...Object.keys(dependencies), ts.transpileModule(code, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText)(...Object.values(dependencies));
const model = source('strategy-config-common/promql-query/model.ts');
const getSourceQueries = compile(`${model.statements.find(statement => statement.name?.text === 'getSourceQueries')
  .getText(model).replace(/^export /, '')}; return getSourceQueries;`);
const service = source('strategy-config-common/promql-query/service.ts');
const buildPromqlItem = compile(`${service.statements.find(statement => statement.name?.text === 'buildPromqlItem')
  .getText(service).replace(/^export /, '')}; return buildPromqlItem;`, { getSourceQueries });
const page = source('strategy-config-set-new/strategy-config-set.tsx');
const getter = page.statements.find(ts.isClassDeclaration).members.find(member => member.name?.getText(page) === 'noticePreviewItem');
assert.ok(getter);
const Harness = compile(`class Harness { ${getter.getText(page)} } return Harness;`, { buildPromqlItem, LETTERS: ['a'] });

function draft(overrides = {}) {
  return Object.assign(new Harness(), {
    isMultivariateAnomalyDetection: false,
    monitorDataEditMode: 'Source',
    expression: 'a+b',
    sourceData: {
      sourceCode: 'vector(1)', step: 60,
      queryConfigs: [{ alias: 'a', promql: 'vector(1)' }, { alias: 'b', promql: 'vector(2)' }],
    },
    promqlMultiLocked: false,
    localExpFunctions: [],
    queryOutputConfig: undefined,
    ...overrides,
  });
}

test('new multi-PromQL preview uses the current save query builder and leaves default resolution to the backend', () => {
  const vm = draft();
  const item = vm.noticePreviewItem;
  assert.equal(item.expression, 'a+b');
  assert.equal(item.query_configs.length, 2);
  assert.ok(item.query_configs.every(query => query.expression_mode === 'promql'));
  assert.equal('query_output_config' in JSON.parse(JSON.stringify(item)), false);
  vm.expression = 'a-b';
  vm.sourceData.queryConfigs.push({ alias: 'c', promql: 'vector(9)' });
  assert.equal(vm.noticePreviewItem.expression, 'a-b');
  assert.equal(vm.noticePreviewItem.query_configs[2].alias, 'c');
});

test('draft explicit disabling and custom output identities are preserved without normalization', () => {
  const vm = draft({ queryOutputConfig: null });
  assert.equal(vm.noticePreviewItem.query_output_config, null);
  const custom = { response_contract: 'named_outputs/v1', legacy_output_ref: 'Total',
    output_list: [{ reference_name: 'Total', expression: 'a+b' }] };
  vm.queryOutputConfig = custom;
  assert.equal(vm.noticePreviewItem.query_output_config, custom);
  assert.equal(vm.noticePreviewItem.query_output_config.output_list[0].reference_name, 'Total');
});

test('locked and legacy multi-query previews retain the same original item as save', () => {
  const queries = [{ alias: 'a', promql: 'vector(10)' }, { alias: 'b', promql: 'vector(20)' }];
  const locked = draft({ promqlMultiLocked: true, sourceData: {
    sourceCode: 'edited', step: 60, rawQueryConfigs: queries, rawExpression: 'a/b', rawOriginSql: 'original',
  } });
  assert.equal(locked.noticePreviewItem.expression, 'a/b');
  assert.equal(locked.noticePreviewItem.origin_sql, 'original');
  assert.deepEqual(locked.noticePreviewItem.query_configs, queries);
  const legacy = draft({ sourceData: {
    sourceCode: 'edited', step: 60, legacyMultiQuery: true, legacyQueryConfigs: queries,
    legacyExpression: 'a*b', legacyOriginSql: 'legacy',
  } });
  assert.equal(legacy.noticePreviewItem.expression, 'a*b');
  assert.equal(legacy.noticePreviewItem.origin_sql, 'legacy');
  assert.deepEqual(legacy.noticePreviewItem.query_configs, queries);
});

test('form and multivariate preview items preserve their current query and expression functions', () => {
  const queries = [{ alias: 'a', data_source_label: 'bk_monitor', data_type_label: 'time_series' }];
  const functions = [{ id: 'abs', params: [] }];
  const form = draft({ monitorDataEditMode: 'Edit', expression: 'A+B', localExpFunctions: functions,
    handleQueryConfig: () => queries });
  assert.equal(form.noticePreviewItem.expression, 'a+b');
  assert.equal(form.noticePreviewItem.query_configs, queries);
  assert.equal(form.noticePreviewItem.functions, functions);
  const multivariate = draft({ isMultivariateAnomalyDetection: true, metricData: [{ sceneConfig: { query_configs: queries } }] });
  assert.equal(multivariate.noticePreviewItem.expression, 'a');
  assert.equal(multivariate.noticePreviewItem.query_configs, queries);
  assert.deepEqual(multivariate.noticePreviewItem.functions, []);
});

test('draft and detail callers pass configuration context through the notice component to preview', () => {
  const pageText = page.getFullText();
  assert.ok(pageText.includes('previewItem={this.noticePreviewItem}'));
  assert.ok(pageText.includes('previewStrategyId={this.id && !this.isClone ? this.id : 0}'));
  assert.ok(pageText.includes('bkBizId={this.bizId}'));
  assert.ok(pageText.includes('this.queryOutputConfig = queryOutputConfig;'));
  const notice = source('strategy-config-set-new/notice-config/notice-config.tsx').getFullText();
  assert.ok(notice.includes('previewItem={this.previewItem}'));
  assert.ok(notice.includes('strategyId={this.previewStrategyId}'));
  assert.ok(notice.includes('bkBizId={this.bkBizId}'));
  const detail = source('strategy-config-detail/strategy-config-detail-common.tsx').getFullText();
  assert.ok(detail.includes('previewItem={this.detailData?.items?.[0]}'));
  assert.ok(detail.includes('bkBizId={this.detailData.bk_biz_id}'));
});
