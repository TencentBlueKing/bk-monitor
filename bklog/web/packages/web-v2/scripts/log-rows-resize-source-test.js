/*
 * Static resize source test for log-rows table header.
 *
 * Run:
 *   node scripts/log-rows-resize-source-test.js
 */

const assert = require('node:assert/strict');

const applyResize = ({ visibleFields, fullColumns, col, nextWidth }) => {
  const currentFields = visibleFields.length ? visibleFields : fullColumns;
  const width = nextWidth > 40 ? nextWidth : 40;
  const field = currentFields.find(item => item.field_name === col.field);
  if (!field) return { currentFields, widthChanged: false };
  field.width = width;
  return {
    currentFields: [...currentFields],
    widthChanged: true,
  };
};

const fullColumns = [
  { field_name: 'log', width: 200 },
  { field_name: 'path', width: 160 },
];
const visibleFields = [];
const result = applyResize({
  visibleFields,
  fullColumns,
  col: { field: 'log', width: 200 },
  nextWidth: 320,
});

assert.equal(result.widthChanged, true, 'visibleFields 为空时仍应能更新 fullColumns');
assert.equal(result.currentFields.find(field => field.field_name === 'log').width, 320);
assert.equal(fullColumns.find(field => field.field_name === 'log').width, 320);

const visible = [
  { field_name: 'log', width: 200 },
  { field_name: 'path', width: 160 },
];
const full = [
  { field_name: 'log', width: 100 },
];
const visibleResult = applyResize({
  visibleFields: visible,
  fullColumns: full,
  col: { field: 'path', width: 160 },
  nextWidth: 240,
});

assert.equal(visibleResult.currentFields.find(field => field.field_name === 'path').width, 240);
assert.equal(full.find(field => field.field_name === 'log').width, 100, 'visibleFields 存在时不应改 fullColumns');

console.log(JSON.stringify({
  fullColumnsLogWidth: fullColumns.find(field => field.field_name === 'log').width,
  visiblePathWidth: visible.find(field => field.field_name === 'path').width,
}, null, 2));
