/*
 * Static fallback field selection test for log-rows table header.
 *
 * Run:
 *   node scripts/log-rows-fallback-fields-test.js
 */

const assert = require('node:assert/strict');

const getFallbackRenderFields = (fields = []) => {
  const renderableFields = fields.filter(field =>
    field?.field_name
    && field.field_type !== '__virtual__'
    && !field.is_virtual_obj_node,
  );
  const preferredFields = ['log', 'body']
    .map(fieldName => renderableFields.find(field => field.field_name === fieldName))
    .filter(Boolean);

  return preferredFields.length
    ? preferredFields
    : renderableFields.slice(0, 4);
};

const fieldsWithLogAndBody = [
  { field_name: '__ext', field_type: 'object', is_virtual_obj_node: true },
  { field_name: '__module__', field_type: '__virtual__' },
  { field_name: 'time', field_type: 'date', is_built_in: true },
  { field_name: 'body', field_type: 'text' },
  { field_name: 'log', field_type: 'text' },
  { field_name: 'serverIp', field_type: 'keyword' },
];

const preferred = getFallbackRenderFields(fieldsWithLogAndBody).map(field => field.field_name);
assert.deepEqual(preferred, ['log', 'body'], '存在 log/body 时必须优先使用 log/body');

const fieldsWithoutLogAndBody = [
  { field_name: '__ext', field_type: 'object', is_virtual_obj_node: true },
  { field_name: '__module__', field_type: '__virtual__' },
  { field_name: 'time', field_type: 'date', is_built_in: true },
  { field_name: 'serverIp', field_type: 'keyword' },
  { field_name: 'path', field_type: 'keyword' },
  { field_name: 'dtEventTimeStamp', field_type: 'date' },
  { field_name: 'gseIndex', field_type: 'long' },
  { field_name: 'iterationIndex', field_type: 'integer' },
];

const firstFour = getFallbackRenderFields(fieldsWithoutLogAndBody).map(field => field.field_name);
assert.deepEqual(
  firstFour,
  ['time', 'serverIp', 'path', 'dtEventTimeStamp'],
  '不存在 log/body 时必须使用前 4 个可渲染字段',
);

console.log(JSON.stringify({
  preferred,
  firstFour,
}, null, 2));
