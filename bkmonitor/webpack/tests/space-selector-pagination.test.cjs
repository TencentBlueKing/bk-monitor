const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const file = path.join(__dirname, '../src/trace/components/space-select/space-selector.tsx');
const source = ts.createSourceFile(
  file,
  fs.readFileSync(file, 'utf8'),
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX
);
let paginationFunction;
function visit(node) {
  if (ts.isFunctionDeclaration(node) && node.name?.text === 'setPaginationData') paginationFunction = node;
  ts.forEachChild(node, visit);
}
visit(source);
assert.ok(paginationFunction, '测试必须执行空间选择器的实际分页函数');
const createPagination = new Function(
  'localSpaceList',
  'pagination',
  `${paginationFunction.getText(source)}; return setPaginationData;`
);

function setup(items) {
  const localSpaceList = { value: items };
  const pagination = { current: 1, limit: 20, count: 0, data: [] };
  return { localSpaceList, pagination, paginate: createPagination(localSpaceList, pagination) };
}

test('大量空间初始化和再次打开时仍能生成首屏列表', () => {
  const items = Array.from({ length: 200000 }, (_, id) => ({ id, show: true, preciseMatch: id === 199999 }));
  const { pagination, paginate } = setup(items);
  paginate(true);
  assert.equal(pagination.count, items.length);
  assert.equal(pagination.data.length, 20);
  assert.equal(pagination.data[0], items[199999]);
  assert.equal(pagination.data[1], items[0]);
  paginate();
  assert.equal(pagination.data.length, 40);
  paginate(true);
  assert.equal(pagination.current, 1);
  assert.equal(pagination.data.length, 20);
});

test('过滤不可见项，精确匹配优先并保留各组原始顺序', () => {
  const items = [
    { id: 1, show: true },
    { id: 2, show: false, preciseMatch: true },
    { id: 3, show: true, preciseMatch: true },
    { id: 4, show: true },
    { id: 5, show: true, preciseMatch: true },
  ];
  const { pagination, paginate } = setup(items);
  paginate(true);
  assert.equal(pagination.count, 4);
  assert.deepEqual(
    pagination.data.map(item => item.id),
    [3, 5, 1, 4]
  );
  assert.deepEqual(
    items.map(item => item.id),
    [1, 2, 3, 4, 5]
  );
});

test('逐页追加至末页不重复，过滤为空后清除旧结果', () => {
  const items = Array.from({ length: 45 }, (_, id) => ({ id, show: true }));
  const { localSpaceList, pagination, paginate } = setup(items);
  paginate(true);
  paginate();
  assert.equal(pagination.current, 2);
  assert.equal(pagination.data.length, 40);
  paginate();
  paginate();
  assert.equal(pagination.current, 3);
  assert.deepEqual(pagination.data, items);
  localSpaceList.value = items.map(item => ({ ...item, show: false }));
  paginate(true);
  assert.equal(pagination.current, 1);
  assert.equal(pagination.count, 0);
  assert.deepEqual(pagination.data, []);
});
