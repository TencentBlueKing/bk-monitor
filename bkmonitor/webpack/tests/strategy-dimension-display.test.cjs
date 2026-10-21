const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.join(__dirname, '../src/monitor-pc/pages/strategy-config');
const typeFile = path.join(root, 'strategy-config-set-new/typings/index.ts');
const source = ts.createSourceFile(typeFile, fs.readFileSync(typeFile, 'utf8'), ts.ScriptTarget.Latest, true);
const declarations = source.statements.filter(node =>
  (ts.isClassDeclaration(node) && node.name?.text === 'MetricDetail') ||
  (ts.isEnumDeclaration(node) && node.name?.text === 'MetricType')
);
assert.equal(declarations.length, 2);
const classCode = ts.transpileModule(declarations.map(node => node.getText(source).replace(/^export /, '')).join('\n'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022 },
}).outputText;
const MetricDetail = new Function('deepClone', 'random', 'INTERVAL_LIST', 'METHOD_LIST', 'CP_METHOD_LIST',
  `${classCode}; return MetricDetail;`)(structuredClone, () => 'test-key', [], [], []);

function loadPageMapper(file, metricList) {
  const text = fs.readFileSync(path.join(root, file), 'utf8');
  const tree = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const callbacks = [];
  function visit(node) {
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) &&
      node.expression.name.text === 'map') {
      const callback = node.arguments[0];
      if (callback && ts.isArrowFunction(callback) && ts.isObjectBindingPattern(callback.parameters[0]?.name) &&
        callback.parameters[0].name.elements.some(item => item.name.getText(tree) === 'agg_dimension') &&
        callback.getText(tree).includes('new MetricDetail')) callbacks.push(callback);
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  assert.equal(callbacks.length, 1, '必须执行页面实际构造指标的回调');
  const code = ts.transpileModule(`const callback = ${callbacks[0].getText(tree)};`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const context = { targetDetail: {}, getAggConditionOfHasDimensionName: conditions => conditions };
  return new Function('MetricDetail', 'metricList', 'targetDetail', 'level', 'metric_type', 'srcData',
    `${code}; return callback;`).call(context, MetricDetail, metricList, {}, 3, 'time_series', { detects: [{ level: 3 }] });
}

const brand = 'base62Mm45BOZ5eM2yBMRzB';
const metric = {
  metric_id: 'custom.demo.__default__.count', data_source_label: 'custom', data_type_label: 'time_series',
  result_table_id: 'demo.__default__', metric_field: 'count', dimensions: [{ id: 'app_name', name: 'APM 应用' }],
};
const query = {
  ...metric, agg_method: 'SUM', agg_interval: 60, agg_condition: [], agg_dimension: [brand, 'app_name'],
  agg_dimension_names: { [brand]: '所属品牌', app_name: 'app_name' },
};

for (const file of ['strategy-config-set-new/strategy-config-set.tsx',
  'strategy-config-detail/strategy-config-detail-common.tsx']) {
  test(`${file}: 打开时直接还原已保存但不在候选列表中的维度`, () => {
    const result = loadPageMapper(file, [metric])(structuredClone(query));
    assert.equal(result.dimensions.find(item => item.id === brand).name, '所属品牌');
    assert.equal(result.dimensions.find(item => item.id === 'app_name').name, 'APM 应用');
    assert.deepEqual(result.agg_dimension, query.agg_dimension);
    assert.equal(metric.dimensions.length, 1);
  });
}

test('已有维度别名优先，重新打开不重复添加未选维度', () => {
  const result = new MetricDetail({
    ...query, dimensions: [...metric.dimensions, { id: brand, name: '自定义品牌名' }],
    agg_dimension_names: { ...query.agg_dimension_names, unused: '未选维度' },
  });
  assert.equal(result.dimensions.filter(item => item.id === brand).length, 1);
  assert.equal(result.dimensions.find(item => item.id === brand).name, '自定义品牌名');
  assert.equal(result.dimensions.some(item => item.id === 'unused'), false);
});
